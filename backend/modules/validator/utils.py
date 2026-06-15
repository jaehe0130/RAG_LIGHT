import os
import re
import json
import time
import urllib.request
import urllib.error
import logging
import math
from functools import lru_cache

logger = logging.getLogger("RAG_LIGHT.validator")

# 이미 메모리에 로드된 SentenceTransformer 모델(_model)을 재사용하기 위해 가져옵니다.
try:
    from modules.rag_search import _model as local_embedding_model
except ImportError:
    local_embedding_model = None

def get_api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()

def parse_json_safely(content: str) -> dict | None:
    """
    LLM 응답에서 마크다운 포맷(```json ...) 제거 및 JSON 객체 파싱 실패 시 
    가장 바깥쪽 괄호 중 중괄호(curly braces) 구조를 파싱하여 예외를 방어합니다.
    """
    content = content.strip()
    
    if content.startswith("```"):
        match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", content, re.DOTALL)
        if match:
            content = match.group(1).strip()
            
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        try:
            # 완벽한 JSON 형식이 아니더라도 첫 번째 { 와 마지막 } 매칭을 통해 강제 파싱 시도
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and start < end:
                return json.loads(content[start:end+1])
        except Exception as e:
            logger.error(f"[Utils] Failed to extract fallback JSON: {e}")
    return None

def call_llm(
    system_prompt: str, 
    user_prompt: str, 
    assistant_message: str = None, 
    feedback_prompt: str = None, 
    retries: int = 3, 
    backoff: float = 1.5
) -> dict | None:
    """
    OpenAI 호환 규격(Gemini/GPT)으로 LLM 컴플리션을 요청합니다.
    self-correction 피드백 유입 시 3-turn 대화 형태로 메시지 배열을 재구성합니다.
    """
    api_key = get_api_key()
    if not api_key or api_key == "your_openai_api_key_here":
        logger.warning("[Utils] Valid API key is not configured.")
        return None

    # AIzaSy 접두어 감지 시 Gemini API로 라우팅 (Gemini OpenAI 호환 endpoint 활용)
    if api_key.startswith("AIzaSy"):
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    else:
        url = "https://api.openai.com/v1/chat/completions"
        model_name = "gpt-4o-mini"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    messages = [{"role": "system", "content": system_prompt}]
    
    if assistant_message and feedback_prompt:
        messages.extend([
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_message},
            {"role": "user", "content": feedback_prompt}
        ])
    else:
        messages.append({"role": "user", "content": user_prompt})

    data = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.0
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    # 불안정한 외부 API 커넥션을 보완하기 위한 Exponential Backoff 재시도 로직
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)
                content = res_json["choices"][0]["message"]["content"].strip()
                
                parsed_res = parse_json_safely(content)
                if parsed_res is not None:
                    return parsed_res
                logger.warning(f"[Utils] LLM raw response was not parseable as JSON (Attempt {attempt}/{retries})")
        except urllib.error.HTTPError as e:
            logger.error(f"[Utils] HTTP {e.code} Error on attempt {attempt}: {e.reason}")
        except Exception as e:
            logger.error(f"[Utils] Connection error on attempt {attempt}: {e}")
        
        if attempt < retries:
            sleep_time = backoff * (2 ** (attempt - 1))
            logger.info(f"[Utils] Retrying LLM call in {sleep_time:.1f}s...")
            time.sleep(sleep_time)
            
    return None

def call_llm_text(
    system_prompt: str, 
    user_prompt: str, 
    retries: int = 3, 
    backoff: float = 1.5
) -> str | None:
    """
    단순 문자열 응답이 필요할 때 사용합니다 (예: ClassifierAgent).
    """
    api_key = get_api_key()
    if not api_key or api_key == "your_openai_api_key_here":
        return None

    if api_key.startswith("AIzaSy"):
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    else:
        url = "https://api.openai.com/v1/chat/completions"
        model_name = "gpt-4o-mini"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    data = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.0
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)
                return res_json["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"[Utils] Text LLM Error on attempt {attempt}: {e}")
        
        if attempt < retries:
            sleep_time = backoff * (2 ** (attempt - 1))
            time.sleep(sleep_time)
            
    return None

def normalize_result_schema(result: dict) -> dict:
    """
    LLM의 반환 규격이 누락되거나 다른 타입으로 나올 경우를 대비한 스키마 정규화
    """
    if not isinstance(result, dict):
        result = {}
    
    result.setdefault("classified_type", "OTHER")
    result.setdefault("llm_analysis", "")
    if not isinstance(result.get("llm_analysis"), str):
        result["llm_analysis"] = str(result["llm_analysis"])
        
    result.setdefault("toxic_clauses", [])
    if not isinstance(result["toxic_clauses"], list):
        result["toxic_clauses"] = []
        
    result.setdefault("signal_color", "GREEN")
    if result["signal_color"] not in ("RED", "YELLOW", "GREEN"):
        result["signal_color"] = "GREEN"
        
    return result

@lru_cache(maxsize=128)
def get_embedding(text: str) -> list[float] | None:
    """
    텍스트의 임베딩 벡터를 가져옵니다.
    메모리에 이미 로딩된 local_embedding_model(_model)을 최우선으로 재사용하며,
    가용하지 않을 경우 OpenAI/Gemini API를 폴백 호출합니다.
    """
    # 1. 메모리에 로딩된 로컬 모델이 있으면 최우선으로 재사용
    if local_embedding_model is not None:
        try:
            # E5 모델은 대칭 비교를 위해 "query: " 프리픽스를 추가하여 인코딩
            emb = local_embedding_model.encode("query: " + text, normalize_embeddings=True)
            return emb.tolist()
        except Exception as e:
            logger.error(f"[Utils] Local embedding encoding failed: {e}")

    # 2. 로컬 모델이 없을 경우 API 폴백
    api_key = get_api_key()
    if not api_key or api_key == "your_openai_api_key_here":
        logger.warning("[Utils] Valid API key is not configured for API embedding fallback.")
        return None

    # AIzaSy 접두어 감지 시 Gemini API로 라우팅
    if api_key.startswith("AIzaSy"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        data = {
            "model": "models/gemini-embedding-2",
            "content": {
                "parts": [{"text": text}]
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)
                return res_json["embedding"]["values"]
        except Exception as e:
            logger.error(f"[Utils] Gemini Embedding API call failed: {e}")
    else:
        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": "text-embedding-3-small",
            "input": text
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)
                return res_json["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"[Utils] OpenAI Embedding API call failed: {e}")

    return None

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """
    두 벡터 간의 코사인 유사도를 계산합니다.
    """
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(x * y for x, y in zip(v1, v2))
    norm_v1 = math.sqrt(sum(x * x for x in v1))
    norm_v2 = math.sqrt(sum(y * y for y in v2))
    if norm_v1 == 0.0 or norm_v2 == 0.0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)
