import os
import glob
import json
import time
import urllib.request
import urllib.error
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

# Force output encoding to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# Env load
from dotenv import load_dotenv
load_dotenv(dotenv_path='backend/.env')

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
OUTPUT_CACHE_FILE = "backend/data/qa_1000_raw.json"

file_lock = threading.Lock()

def extract_cases():
    files = sorted(glob.glob("backend/data/raw/*_metadata.json"))
    print(f"📊 [Data Extractor] Found {len(files)} total metadata files.")
    
    cases = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
        except Exception as e:
            print(f"⚠️ Error reading {f}: {e}")
            continue
            
        title = data.get("의결서제목", "")
        no = data.get("의결서관리번호", "")
        
        # Strictly filter for consumer-centric cases
        # (E-commerce, False Ads, Door-to-door sales, Unfair Terms, Consumer Protection)
        is_consumer = any(kw in str(data) for kw in ['전자상거래', '표시광고', '표시·광고', '방문판매', '약관', '소비자'])
        is_b2b_or_subcontract = any(kw in str(data) for kw in ['공동행위', '담합', '하도급'])
        
        if is_consumer and not is_b2b_or_subcontract:
            p_info_list = data.get("피심인정보", [])
            if p_info_list:
                info = p_info_list[0]
                corp_name = info.get("피심인기업명", "")
                violation = info.get("세부위반유형") or info.get("위반유형") or "소비자 규정 위반"
                sanction = info.get("조치유형") or "시정명령"
                law = info.get("위반유형") or "소비자법"
            else:
                corp_name = title.split("의")[0].strip() if "의" in title else "피심인"
                violation = "소비자 규정 위반"
                sanction = "시정명령"
                law = "소비자법"
                
            if not corp_name:
                corp_name = "피심인"
                
            cases.append({
                "의결서관리번호": no,
                "의결서제목": title,
                "피심인기업명": corp_name,
                "위반유형": law,
                "세부위반유형": violation,
                "조치유형": sanction
            })
            
    print(f"📊 [Data Extractor] Filtered down to {len(cases)} strictly consumer-centric cases.")
    return cases

def call_gemini_api(prompt: str) -> list:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in env.")

    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GEMINI_API_KEY}"
    }
    
    system_prompt = (
        "당신은 대한민국의 공정거래위원회 약관법, 전자상거래법, 표시광고법, 방문판매법, 할부거래법 등 소비자 권익 보호 법률에 정통한 소비자 전문 AI 변호사입니다.\n"
        "지정된 개별 요구사항(피심인기업명, 위반유형, 세부위반유형, 조치유형, 페르소나, 질문유형, 난이도 등)에 완벽히 매핑되는 소비자 QA 데이터를 생성해야 합니다.\n\n"
        "**[★가장 중요한 규칙 - 100% 소비자/대국민 중심 설계]**\n"
        "이 프로젝트는 대국민 및 일반 소비자 보호 서비스인 '소비자 공정 Guard'입니다.\n"
        "따라서 질문과 답변은 반드시 **최종 소비자가 겪는 부당한 가격 부담, 환불 제한 피해, 계약 독소조항, 기만적 광고 피해, 소비자 피해 구제 및 분쟁 해결 방법, 또는 기업 준법 측면에서의 소비자 권익 침해 방지 및 신뢰 저해 리스크**의 관점에서만 작성해야 합니다.\n"
        "기업 간의 B2B 거래나 담합, 하도급 분쟁과 관련된 관점은 절대 포함하지 마십시오.\n\n"
        "응답은 반드시 마크다운(```json)이나 다른 설명 텍스트 없이 순수한 JSON 배열 포맷으로만 반환해야 합니다. 예시:\n"
        "[\n"
        "  {\n"
        "    \"idx\": 0,\n"
        "    \"question\": \"질문 내용...\",\n"
        "    \"answer\": \"답변 내용...\",\n"
        "    \"facts\": \"주체: ... / 상대방: ... / 시장: ... / 핵심행위: ... / 결과: ...\",\n"
        "    \"legal_reasoning\": \"법리 해석: '[핵심행위]'은(는) 상대방에게 불이익을 주거나 소비자를 오인하게 할 수 있어 '[위반법률]' 위반으로 볼 수 있다.\",\n"
        "    \"applicable_law\": \"전자상거래법 제17조\",\n"
        "    \"ref_doc\": \"소비자분쟁해결기준\"\n"
        "  }\n"
        "]"
    )
    
    data = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            content = res_json["choices"][0]["message"]["content"].strip()
            
            json_match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
            if json_match:
                content = json_match.group(1).strip()
            
            return json.loads(content)
    except Exception as e:
        print(f"❌ Gemini API Call Error: {e}")
        return []

def process_batch(batch_items, thread_id):
    print(f"🧵 [Thread {thread_id}] Starting generation of {len(batch_items)} items...")
    
    req_str = ""
    for item in batch_items:
        req_str += (
            f"- Index: {item['idx']}\n"
            f"  의결서제목: {item['의결서제목']}\n"
            f"  피심인기업명: {item['피심인기업명']}\n"
            f"  위반유형: {item['위반유형']}\n"
            f"  세부위반유형: {item['세부위반유형']}\n"
            f"  조치유형: {item['조치유형']}\n"
            f"  페르소나: {item['persona']}\n"
            f"  질문유형: {item['question_type']}\n"
            f"  난이도: {item['difficulty']}\n"
            f"  주제: {item['subject']}\n"
            f"  가이드라인: {item['rule']}\n\n"
        )
        
    prompt = (
        f"당신은 대국민 소비자 보호 서비스인 '소비자 공정 Guard'의 핵심 데이터 설계자입니다.\n"
        f"아래 {len(batch_items)}개 요구사항을 바탕으로 각 페르소나와 질문유형에 맞는 고품질 QA 세트를 생성하십시오.\n\n"
        f"**[★가장 중요한 규칙 - 100% 소비자/대국민 중심 설계]**\n"
        f"각 레코드는 반드시 일반 소비자의 권익 침해, 피해 구제, 실생활 민생 경제(환불 제한, 표시광고 기만, 부당 약관 독소조항 등) 관점에서 구성해야 합니다. B2B 담합이나 하도급 단가 협상 같은 기업 중심의 시선은 절대 배제하십시오.\n\n"
        f"[요구사항 목록]\n{req_str}\n"
        f"[지침]\n"
        f"1. 각 Index에 대응하는 JSON 객체를 반환하십시오. 반환값은 반드시 JSON 배열 형태여야 합니다.\n"
        f"2. 'question': 소비자 보호 관점의 톤앤매너와 가이드라인에 맞는 질문 문장을 작성해 주세요.\n"
        f"3. 'answer': 소비자 보호 관점의 톤앤매너와 가이드라인에 맞는 풍부하고 상세한 답변을 작성해 주세요.\n"
        f"4. 'facts': 반드시 '주체: [피심인기업명] / 상대방: [거래상대방(예: 대리점, 가맹점, 소비자 등)] / 시장: [관련 시장 영역] / 핵심행위: [세부위반유형] / 결과: [구체적 거래제약 또는 피해]' 형식으로 작성해 주세요.\n"
        f"5. 'legal_reasoning': 반드시 '법리 해석: '[세부위반유형]'은(는) 상대방에게 불이익을 주거나 소비자를 오인하게 할 수 있어 '[적용법률]' 위반으로 볼 수 있다.' 형태로 작성해 주세요.\n"
        f"6. 'applicable_law': 구체적인 위반 법률명과 조항을 작성해 주세요 (예: '전자상거래법 제17조', '표시광고법 제3조 제1항').\n"
        f"7. 'ref_doc': 참고 자료나 고시 (예: '소비자분쟁해결기준', '공정위 심결례').\n"
    )
    
    for attempt in range(3):
        batch_data = call_gemini_api(prompt)
        if batch_data and isinstance(batch_data, list):
            with file_lock:
                try:
                    if os.path.exists(OUTPUT_CACHE_FILE):
                        with open(OUTPUT_CACHE_FILE, "r", encoding="utf-8") as f:
                            current_cache = json.load(f)
                    else:
                        current_cache = {}
                except Exception:
                    current_cache = {}
                    
                for res in batch_data:
                    idx_str = str(res.get("idx"))
                    if idx_str in [str(item["idx"]) for item in batch_items]:
                        orig = [it for it in batch_items if str(it["idx"]) == idx_str][0]
                        res_merged = {
                            "idx": orig["idx"],
                            "의결서관리번호": orig["의결서관리번호"],
                            "의결서제목": orig["의결서제목"],
                            "피심인기업명": orig["피심인기업명"],
                            "위반유형": orig["위반유형"],
                            "세부위반유형": orig["세부위반유형"],
                            "조치유형": orig["조치유형"],
                            "persona": orig["persona"],
                            "question_type": orig["question_type"],
                            "difficulty": orig["difficulty"],
                            "subject": orig["subject"],
                            "question": res.get("question"),
                            "answer": res.get("answer"),
                            "facts": res.get("facts"),
                            "legal_reasoning": res.get("legal_reasoning"),
                            "applicable_law": res.get("applicable_law"),
                            "ref_doc": res.get("ref_doc")
                        }
                        current_cache[idx_str] = res_merged
                        
                with open(OUTPUT_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(current_cache, f, ensure_ascii=False, indent=2)
                    
            print(f"✅ [Thread {thread_id}] Batch completed successfully. (Cache size: {len(current_cache)}/1000)")
            return True
        else:
            print(f"⚠️ [Thread {thread_id}] Batch failed, retrying in 10 seconds... (Attempt {attempt+1}/3)")
            time.sleep(10)
            
    print(f"❌ [Thread {thread_id}] Batch failed permanently.")
    return False

def main():
    print("🚀 [1,000 QA Generator] Overwriting old cache to ensure strict consumer cases...")
    if os.path.exists(OUTPUT_CACHE_FILE):
        try:
            os.remove(OUTPUT_CACHE_FILE)
            print("🧹 Removed old cache file.")
        except Exception as e:
            print(f"⚠️ Failed to remove cache: {e}")

    cases = extract_cases()
    if not cases:
        print("❌ Critical: No consumer cases found!")
        return
        
    personas = ["일반국민", "기업 컴플라이언스 담당자", "논문 준비 학생"]
    question_types = ["제재중심", "법령중심", "유사사례", "통계기반", "시장영향"]
    difficulties = ["기초", "중급", "심화"]
    
    personas_info = {
        "일반국민": {
            "style": "쉽고 직관적인 설명",
            "point": "생활 속 사례와 쉽게 풀어쓴 설명",
            "suffix": "(소비자 피해)",
            "rule": "일반 소비자가 겪을 법한 부당한 환불 제한, 전자상거래 계약 독소조항, 과다 위약금, 허위 광고 기만 피해 사연을 담은 구어체 질문(~되나요?, ~했는데요 등)과, 구제 절차와 권리 위주로 설명한 답변."
        },
        "기업 컴플라이언스 담당자": {
            "style": "리스크 및 준법 중심 설명",
            "point": "위반 위험요소, 내부통제 포인트, 재발방지 관점",
            "suffix": "(준법 리스크)",
            "rule": "기업 준법 실무진 관점에서 자사의 불공정 약관이나 허위 광고가 소비자 피해 및 소송 리스크, 소비자단체 비판으로 번지는 평판 리스크를 방지하기 위한 준법 통제 전략 및 예방 조치 설명."
        },
        "논문 준비 학생": {
            "style": "학술·연구 중심 설명",
            "point": "쟁점, 판단 구조, 비교법적·통계적 해석",
            "suffix": "(학술적 법리)",
            "rule": "사건 행위가 최종 소비자 후생(Consumer Welfare) 왜곡, 구매력 저하, 소비자법상 주요 쟁점 및 법률적 파급 효과에 미치는 영향에 관한 학술적 분석형 질문과 답변."
        }
    }
    
    items_to_generate = []
    for i in range(1000):
        case_idx = i % len(cases)
        c = cases[case_idx]
        
        p_name = personas[i % 3]
        q_type = question_types[(i // 3) % 5]
        diff = difficulties[(i // 15) % 3]
        
        p_info = personas_info[p_name]
        subject = f"{c['피심인기업명']}의 {c['세부위반유형']} {p_info['suffix']} ({q_type})"
        
        items_to_generate.append({
            "idx": i,
            "의결서관리번호": c["의결서관리번호"],
            "의결서제목": c["의결서제목"],
            "피심인기업명": c["피심인기업명"],
            "위반유형": c["위반유형"],
            "세부위반유형": c["세부위반유형"],
            "조치유형": c["조치유형"],
            "persona": p_name,
            "question_type": q_type,
            "difficulty": diff,
            "subject": subject,
            "rule": p_info["rule"]
        })
        
    print(f"📊 [1,000 QA Generator] Configured {len(items_to_generate)} items for generation.")
    
    # Build batches of 35 items
    batch_size = 35
    all_batches = []
    
    for start_idx in range(0, 1000, batch_size):
        all_batches.append(items_to_generate[start_idx : start_idx + batch_size])
            
    print(f"📦 Total batches to generate: {len(all_batches)}")
    
    # Execute using ThreadPoolExecutor with 3 workers
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for idx, batch in enumerate(all_batches):
            futures.append(executor.submit(process_batch, batch, idx + 1))
            time.sleep(12)
            
        for future in futures:
            future.result()
            
    print(f"🎉 1,000 Raw QA datasets generated successfully! Cache path: {OUTPUT_CACHE_FILE}")

if __name__ == "__main__":
    main()
