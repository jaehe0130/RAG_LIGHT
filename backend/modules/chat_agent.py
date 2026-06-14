import os
import json
import time
import urllib.request
from typing import List, Dict
from modules.rag_search import retrieve_similar_cases, _summarize_cases

def call_chat_llm(api_key: str, messages: List[Dict[str, str]]) -> str | None:
    """
    대화 기록(messages)을 포함하여 LLM을 호출하고 응답 문자열을 반환합니다.
    API 키가 AIzaSy로 시작하면 Gemini를, 그렇지 않으면 OpenAI를 사용합니다.
    """
    if api_key.startswith("AIzaSy"):
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    else:
        url = "https://api.openai.com/v1/chat/completions"
        model_name = "gpt-4o-mini"

    data = json.dumps({
        "model": model_name,
        "messages": messages,
        "temperature": 0.5, # 챗봇 특성상 약간의 창의성과 유연성 부여 (0.5)
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    print("[ChatAgent] 💬 최종 챗봇 답변을 생성하기 위해 LLM을 호출합니다...")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = json.loads(resp.read().decode("utf-8"))
            print(f"[ChatAgent] ✅ 답변 생성 완료 ({time.time() - t0:.2f}초)")
            return content["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[ChatAgent] ❌ LLM 호출 실패: {e} ({time.time() - t0:.2f}초)")
        return None

def generate_chat_response(query: str, chat_history: List[Dict[str, str]] = None, retrieved_context: str = "") -> str:
    """
    사용자 쿼리와 대화 기록, RAG 검색 결과를 바탕으로 챗봇 응답을 생성합니다.
    
    :param query: 사용자가 입력한 최신 질문
    :param chat_history: 이전 대화 내역 (role: 'user' 또는 'assistant')
    :param retrieved_context: RAG 등에서 검색된 배경 지식/판례 텍스트
    """
    raw_api_key = os.getenv("OPENAI_API_KEY")
    api_key = raw_api_key.strip() if raw_api_key else None
    
    if not api_key or api_key == "your_openai_api_key_here":
        return "API 키가 설정되지 않았습니다. 관리자에게 문의하여 .env 파일을 확인해 주세요."

    # 1. 챗봇의 페르소나와 기본 시스템 프롬프트 정의
    system_prompt = (
        "당신은 대한민국 공정거래위원회 규정을 바탕으로 소비자의 권리를 보호해 주는 전문적이고 친근한 '문서분석도우미'입니다.\n"
        "답변 작성 시 다음 규칙을 무조건 엄수하세요:\n"
        "1. 기계적인 인사말, 불필요한 부연 설명, 장황한 기능 나열 등 AI 챗봇 특유의 말투를 절대 피하세요. 사람처럼 자연스럽게 대화하세요.\n"
        "2. 답변은 핵심만 아주 간결하게 작성하고, 한 문단이 너무 길어지지 않도록 가독성 있게 줄바꿈을 자주 하세요.\n"
        "3. 내용이 여러 개일 경우 글머리 기호(-, •)를 사용하여 깔끔하게 나누어 설명하세요.\n"
        "4. 문서 분석 결과를 물어보면, 법률과 규정에 근거하여 명확히 답변하세요."
    )
    
    # 2. 검색된 컨텍스트(RAG)가 있다면 프롬프트에 추가
    combined_context = retrieved_context
    
    # 2.5 실시간 Qdrant DB 검색 수행 (Top 2개만 추출)
    # [최적화] 속도 향상을 위해 검색량(retrieve_k)을 줄이고, 중간 LLM 요약(_summarize_cases) 단계를 생략합니다.
    print("🤖 [ChatAgent] 질문 기반 실시간 Qdrant DB 검색 수행 중 (초고속 모드)...")
    realtime_docs = retrieve_similar_cases(query, top_k=2, retrieve_k=3)
    if realtime_docs:
        # LLM 중간 요약을 생략하고 원문을 바로 문맥에 주입 (LLM 호출 1회 제거로 속도 2배 단축)
        realtime_context = "\n".join([f"[사례 {i+1}]\n{doc}" for i, doc in enumerate(realtime_docs)])
        if combined_context:
            combined_context += f"\n\n[실시간 채팅 기반 추가 검색 판례]\n{realtime_context}"
        else:
            combined_context = f"[실시간 채팅 기반 검색 판례]\n{realtime_context}"

    if combined_context:
        system_prompt += f"\n\n[참조할 관련 판례/규정 및 분석 결과]\n{combined_context}\n\n"
        system_prompt += "위 정보를 우선적으로 참고하여 답변해 주시고, 묻지 않은 내용을 너무 길게 나열하지 마세요."

    messages = [{"role": "system", "content": system_prompt}]
    
    # 3. 이전 대화 기록 추가 (문맥 유지)
    if chat_history:
        messages.extend(chat_history)
        
    # 4. 현재 질문 추가
    messages.append({"role": "user", "content": query})

    # [디버깅용] 터미널에 완성된 프롬프트와 컨텍스트 출력
    print("\n" + "="*50)
    print("🤖 [ChatAgent] LLM으로 전송되는 프롬프트 세트 확인")
    print("="*50)
    for idx, msg in enumerate(messages):
        print(f"[{msg['role'].upper()}] (길이: {len(msg['content'])}자)")
        # 너무 길면 앞부분만 자릿수 잘라서 출력
        preview = msg['content'][:300] + ("..." if len(msg['content']) > 300 else "")
        print(f"{preview}\n")
    print("="*50 + "\n")

    # 5. LLM 호출
    response = call_chat_llm(api_key, messages)
    if not response:
        return "죄송합니다. 현재 응답을 생성하는 데 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
        
    return response
