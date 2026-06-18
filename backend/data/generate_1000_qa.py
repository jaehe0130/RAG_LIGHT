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
        "**[★가장 중요한 규칙 - 100% 소비자/대국민 중심 설계 및 챗봇 연계]**\n"
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
        "    \"legal_reasoning\": \"법리 해석: '[핵심행위]'은(는) 상대방에게 불이익을 주거나 소비자를 오인하게 할 수 있어 '[적용법률]' 위반으로 볼 수 있다.\",\n"
        "    \"applicable_law\": \"전자상거래법 제17조\",\n"
        "    \"ref_doc\": \"소비자분쟁해결기준\",\n"
        "    \"주의사항\": \"소비자가 이 사안을 겪을 때 알아두어야 할 실질적 한계 및 권리 행사 리스크 대안 설명\",\n"
        "    \"비고\": \"학술 연구 시의 한계점이나 정책적 제언 등 추가적인 제언 사항\"\n"
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
        f"2. 'question': 소비자 보호 관점의 톤앤매너와 가이드라인에 맞는 질문 문장을 작성해 주세요. 질문 내에 피심인 기업명을 직접 쓰지 마십시오.\n"
        f"3. 'answer': 챗봇의 자연스럽고 다채로운 답변 톤앤매너를 반영하여 풍부하게 작성해 주십시오.\n"
        f"   - [절대 금지] 도입부를 매번 동일한 어구(예: '~는 다음과 같습니다', '~검토는 다음과 같습니다')로 고정해 끝내지 마십시오.\n"
        f"   - [절대 금지] 마지막 부분에 기계적인 경고성 꼬리표(예: '구체적인 사안에 대해 더 자세한 검토가 필요하다면...')를 절대 덧붙이지 마십시오. 사안에 어울리는 실무 당부나 결론 문장으로 자연스럽게 매번 다르게 마쳐주십시오.\n"
        f"   - [절대 금지] 마지막에 '• **결론**'이라는 강제적 헤더 조항을 일률적 적용하지 마십시오.\n"
        f"   - [구조]: 질문에 논리적으로 맞받아치는 독창적 도입 문장으로 시작 ➡️ `• **[핵심 쟁점]**`과 필요 시 `- [세부 항목]` 리스트 형태의 본문 단락 2~3개 ➡️ 획일적 꼬리표 없는 깔끔하고 자연스러운 종결 문장.\n"
        f"   - [★실제 챗봇 모범 답변 예시 3가지]:\n"
        f"     * 예시 1: (질문) 숙박 예약 플랫폼에서 당일 취소 시 전액 환불 불가 약관을 적용하는 것이 시장 지배력 남용이나 거래 질서 훼손으로 판단될 수 있는지 법리적 검토가 필요합니다.\n"
        f"              (답변) 제시해주신 사례와 공정거래위원회 심사 지침을 바탕으로 판단할 때, 해당 약관은 다음과 같은 법리적 검토가 가능합니다. \n\n"
        f"                     • **거래상 지위 인정 여부**\n"
        f"                     플랫폼이 시장에서 압도적인 점유율을 차지하여 숙박업소와 소비자에게 필수적인 거래 수단이 되었다면, 플랫폼은 '거래상 지위'를 가진 사업자로 간주됩니다.\n\n"
        f"                     • **불공정거래행위 판단 기준**\n"
        f"                     단순히 환불 불가 규정을 두었다는 사실만으로 위법하지는 않습니다. 다만, 다음 요소들을 종합적으로 고려해 정상적인 거래 관행을 벗어났는지 따져봐야 합니다.\n"
        f"                     - 플랫폼의 우월적 지위 정도\n"
        f"                     - 소비자가 입는 불이익의 내용\n"
        f"     * 예시 2: (질문) 데이팅 앱 내 가상 화폐 판매 시 '청약철회 불가'를 고지하는 것이 전자상거래법상 어떤 법리적 요건을 충족해야 위법성을 피할 수 있습니까?\n"
        f"              (답변) 전자상거래법 제13조 및 관련 판례에 따라, 데이팅 앱 내 가상 화폐(디지털 콘텐츠) 판매 시 '청약철회 불가'를 고지하여 위법성을 피하려면 다음의 요건을 반드시 충족해야 합니다.\n\n"
        f"                     • **거래조건의 명확한 고지**\n"
        f"                     단순히 \"사용 시 철회 불가\"라고만 표시해서는 안 됩니다. 법 제13조 제2항 제5호에 따라 청약철회의 기한, 행사 방법, 효과에 관한 사항을 소비자가 계약 체결 전에 정확히 이해할 수 있도록 구체적으로 고지해야 합니다.\n\n"
        f"                     • **행사 방법의 실질적 제공**\n"
        f"                     청약철회 권리를 행사하는 데 필요한 서식이나 절차를 소비자가 쉽게 접근할 수 있도록 연결해야 합니다. 단순히 안내 문구만 두는 것이 아니라, 소비자가 실제 철회를 실행할 수 있는 시스템적 편의성을 갖추어야 법적 위험을 피할 수 있습니다.\n"
        f"     * 예시 3: (질문) 반려동물 사료 광고 시 '천연 원료 100%', '부작용 없음'과 같은 표현을 사용하려 합니다. 표시광고법상 주의해야 할 점은 무엇인가요?\n"
        f"              (답변) 표시광고법에 따라 '천연 100%'나 '부작용 없음'과 같은 표현을 사용할 때는 매우 엄격한 입증 책임이 따릅니다. 다음 사항을 반드시 주의하세요.\n\n"
        f"                     • **'천연 원료 100%' 표현의 위험성**\n"
        f"                     - 사료 제조 과정에서 사용되는 비타민, 미네랄, 보존제 등 아주 미량의 합성 첨가물이라도 포함되어 있다면 '100%'라는 표현은 거짓·과장 광고에 해당합니다.\n"
        f"                     - 보존제가 포함되어 있음에도 이를 숨기거나 '자연식'으로 광고하는 행위는 공정위의 제재 대상입니다.\n"
        f"                     - 원료의 재배, 가공 과정에서 화학적 공정이 전혀 개입되지 않았음을 객관적으로 증명할 수 있어야 합니다.\n\n"
        f"                     • **'부작용 없음' 표현의 금지**\n"
        f"                     - 의약품이 아닌 사료에서 '부작용 없음'이라는 단정적인 표현을 사용하는 것은 소비자에게 오인 가능성이 매우 큽니다.\n"
        f"                     - 개체별 알레르기 반응이나 체질 차이로 인해 발생할 수 있는 잠재적 위험을 완전히 배제할 수 없으므로, 이러한 표현은 기만적 광고로 판단될 가능성이 높습니다.\n\n"
        f"                     • **입증 책임의 원칙**\n"
        f"                     - 광고 문구에 대해 소비자가 문제를 제기할 경우, 해당 표현이 사실임을 입증할 책임은 전적으로 사업자에게 있습니다.\n"
        f"                     - 성분 분석표, 제조 공정 자료, 공인 기관의 검증 결과 등 객관적이고 과학적인 근거를 반드시 확보해야 합니다.\n\n"
        f"                     • **권장 사항**\n"
        f"                     - '100%'와 같은 단정적인 수식어보다는 실제 사용된 원료의 구체적인 명칭을 나열하는 방식이 안전합니다.\n"
        f"                     - '부작용 없음' 대신 '엄선된 원료 사용' 등 사실에 근거한 완곡한 표현을 사용하는 것이 법적 리스크를 줄이는 방법입니다.\n\n"
        f"                     근거 없는 과장 광고는 시정명령 및 과징금 부과 대상이 될 수 있으므로, 광고 문구 작성 시 매우 신중해야 합니다.\n"
        f"4. 'facts': 반드시 '주체: [피심인기업명] / 상대방: [거래상대방(예: 대리점, 가맹점, 소비자 등)] / 시장: [관련 시장 영역] / 핵심행위: [세부위반유형] / 결과: [구체적 거래제약 또는 피해]' 형식으로 작성해 주세요.\n"
        f"5. 'legal_reasoning': 반드시 '법리 해석: '[세부위반유형]'은(는) 상대방에게 불이익을 주거나 소비자를 오인하게 할 수 있어 '[적용법률]' 위반으로 볼 수 있다.' 형태로 작성해 주세요.\n"
        f"6. 'applicable_law': 구체적인 위반 법률명과 조항을 작성해 주세요 (예: '전자상거래법 제17조', '표시광고법 제3조 제1항').\n"
        f"7. 'ref_doc': 참고 자료나 고시 (예: '소비자분쟁해결기준', '공정위 심결례').\n"
        f"8. '주의사항': [중요] 모든 레코드의 주의사항 문장 구조나 접미사가 기계적으로 반복(예: '~를 판단할 때, ~를 고려하여 ~해야 합니다')되지 않도록 하십시오. 실의결서 데이터로 변환하여 룰 검증을 수행할 때, 검증 실무자가 어떤 구체적 사실관계(예: 기업 신원정보 노출 레이아웃, 앱 내 디지털 콘텐츠 세부 결제/사용 로그 조회, 업종 고시 위약금 한도 일치성 등)를 비교 검증해야 하는지를 케이스별 특징에 커스터마이징된 독창적이고 전문적인 실무 서술형 문장으로 다채롭게 작성하십시오.\n"
        f"9. '비고': 학계 관점에서 이 사건이 가져오는 규제 효과나 학술적인 관점의 추가 코멘트를 기재하십시오.\n"
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
                            "ref_doc": res.get("ref_doc"),
                            "주의사항": res.get("주의사항"),
                            "비고": res.get("비고")
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
    print("🚀 [1,000 QA Generator] Checking existing cache...")
    existing_cache = {}
    if os.path.exists(OUTPUT_CACHE_FILE):
        try:
            with open(OUTPUT_CACHE_FILE, "r", encoding="utf-8") as f:
                existing_cache = json.load(f)
            print(f"🔄 Loaded {len(existing_cache)} existing cases from cache.")
        except Exception as e:
            print(f"⚠️ Failed to load existing cache: {e}")
            existing_cache = {}

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
        # Skip if already exists in cache to perform incremental generation
        if str(i) in existing_cache:
            continue
            
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
    
    if not items_to_generate:
        print("🎉 Cache already contains all 1,000 items! No generation needed.")
        return
        
    # Build batches of 5 items to prevent Max Output Tokens truncation
    batch_size = 5
    all_batches = []
    
    for start_idx in range(0, len(items_to_generate), batch_size):
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
