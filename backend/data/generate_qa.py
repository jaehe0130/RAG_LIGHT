import json
import os
import time
import urllib.request
import urllib.error
import re
from dotenv import load_dotenv

load_dotenv()

# .env 파일에서 불러온 설정값 (모델은 gemini-3.1-flash-lite로 지정)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "qa_dataset.json")
TARGET_COUNT = 1000

# 기획서(idea.pdf) 4.4절 설계에 기치한 데이터 세부 분포 구성
# 1. 페르소나 지분: 일반 국민 33.9% (339건), 논문 준비 학생 33.2% (332건), 청장년층 32.9% (329건)
# 2. 질문 유형: 유사사례 검색 33.1% (331건), 시장 영향 23.7% (237건), 제재 중심 23.6% (236건), 법령 및 심화 질문 19.6% (196건)
# 3. 답변 톤: 쉽고 친근한 언어 66.8% (668건), 학술적·분석적 언어 33.2% (332건)
# 4. 신호등 위험도 판정: 주의(노란불) 75.2% (752건), 안전(초록불) 16.6% (166건), 위험(빨간불) 8.2% (82건)

def get_deterministic_metadata():
    """기획서의 수치적 분포를 정확히 만족하는 1,000건의 메타데이터 세트를 생성합니다.
    랜덤 모듈을 전혀 쓰지 않고 결정론적 합동 수식으로 분배합니다.
    """
    meta_list = []
    for i in range(1000):
        # 신호등 비율 분배
        if i < 752:
            color = "YELLOW"
        elif i < 918:
            color = "GREEN"
        else:
            color = "RED"
            
        # 페르소나 유형 분배
        if i < 339:
            p_type = "일반 국민"
        elif i < 671:
            p_type = "논문 준비 학생"
        else:
            p_type = "청장년층"
            
        # 질문 유형 분배
        if i < 331:
            q_type = "유사사례 검색"
        elif i < 568:
            q_type = "시장 영향"
        elif i < 804:
            q_type = "제재 중심"
        else:
            q_type = "법령 및 심화 질문"
            
        # 답변 톤 분배
        if i < 668:
            tone = "쉽고 친근한 언어"
        else:
            tone = "학술적·분석적 언어"
            
        meta_list.append({
            "color": color,
            "persona_type": p_type,
            "question_type": q_type,
            "tone": tone
        })
        
    # 결정론적 LCG 알고리즘을 이용한 셔플 (순서가 고루 섞여 배치당 균형 배치)
    shuffled = []
    curr = 0
    for _ in range(1000):
        curr = (curr * 32719 + 3) % 1000
        shuffled.append(meta_list[curr])
    return shuffled

def call_gemini_api(prompt: str) -> list:
    """urllib를 이용해 외부 라이브러리 의존성 없이 Gemini API를 호출합니다."""
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_openai_api_key_here":
        raise ValueError(".env 파일에 올바른 GEMINI_API_KEY 또는 OPENAI_API_KEY를 설정해주세요.")

    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GEMINI_API_KEY}"
    }
    
    system_prompt = (
        "당신은 대한민국의 공정거래위원회 약관법, 전자상거래법, 표시광고법 및 소비자분쟁해결기준에 정통한 소비자 권리 보호 전문 AI 변호사입니다.\n"
        "지정된 개별 요구사항(페르소나 유형, 질문 유형, 답변 톤, 색상 등급)에 완벽히 매핑되는 소비자 QA 데이터셋을 생성해야 합니다.\n\n"
        "응답은 반드시 마크다운(```json)이나 다른 설명 텍스트 없이 순수한 JSON 배열 포맷으로만 반환해야 합니다. 예시:\n"
        "[\n"
        "  {\n"
        "    \"persona\": \"요구사항에 부합하는 한국인 이름과 나이, 직업 정보가 포함된 페르소나 (예: '대학생 김민준 (21세)')\",\n"
        "    \"query\": \"요구사항의 질문 유형(유사사례 검색, 시장 영향 등)에 부합하며 실제 소비자가 작성한 듯한 자연스러운 한국어 문장. (예: '헬스장 회원권 양도 수수료로 5만원을 달라는데...')\",\n"
        "    \"answer\": \"요구사항의 답변 톤(쉽고 친근한 언어 또는 학술적·분석적 언어)에 정확히 일치하며 관련 고시 및 법률에 기반한 모범 답안\",\n"
        "    \"signal_color\": \"RED\" | \"YELLOW\" | \"GREEN\",\n"
        "    \"applicable_law\": \"해당 문제에 적용되는 명확한 법률명 및 조항 (예: '소비자분쟁해결기준 (체육시설업), 약관법 제8조')\"\n"
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
        with urllib.request.urlopen(req, timeout=45) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            content = res_json["choices"][0]["message"]["content"].strip()
            
            # 정규식을 이용해 마크다운 백틱 안의 JSON 텍스트 정밀 추출 (공백 방어)
            json_match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
            if json_match:
                content = json_match.group(1).strip()
            else:
                content = content.strip()
                
            return json.loads(content)
    except Exception as e:
        print(f"❌ Gemini API 호출 중 오류 발생: {e}")
        return []

def run_generator():
    print(f"🚀 [Gemini QA Generator] {MODEL_NAME} 모델을 이용해 기획서(idea.pdf) 스펙 준수 1,000건 QA 생성을 시작합니다.")
    
    # 1. 1000개의 결정론적 메타데이터 시나리오 셋 로드
    metadata_scenarios = get_deterministic_metadata()
    
    # 2. 기존 파일 확인 및 이어쓰기 지원
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                dataset = json.load(f)
            print(f"🔄 기존 데이터 {len(dataset)}건을 불러왔습니다. 이어서 생성합니다.")
        except Exception:
            dataset = []
    else:
        dataset = []

    batch_size = 20  # 한 번 호출 시 20개씩 생성하여 총 50배치 수행
    
    while len(dataset) < TARGET_COUNT:
        start_idx = len(dataset)
        needed = min(batch_size, TARGET_COUNT - start_idx)
        current_batch_meta = metadata_scenarios[start_idx : start_idx + needed]
        
        # 이번 배치의 프롬프트 요구사항 조립
        requirements_str = ""
        for i, meta in enumerate(current_batch_meta, start=1):
            requirements_str += (
                f"{i}. 페르소나유형: '{meta['persona_type']}', "
                f"질문유형: '{meta['question_type']}', "
                f"답변톤: '{meta['tone']}', "
                f"색상등급: '{meta['color']}'\n"
            )
            
        print(f"📈 [진행도: {start_idx}/{TARGET_COUNT}] {needed}개 항목 생성 중...")
        
        prompt = (
            f"당신은 소비자의 다양한 민원, 판례 학술 연구, 제재 내역 등에 부합하는 사실적인 데이터셋을 생성해야 합니다.\n"
            f"아래의 개별 요구사항 {needed}개에 정확히 매핑되는 소비자 QA 데이터 {needed}개를 생성하여 순서대로 JSON 배열로 반환하세요.\n\n"
            f"[개별 요구사항 목록]\n{requirements_str}\n"
            f"[필수 가이드 및 참고 사례 (기획서 4.3절 반영)]\n"
            f"- '일반 국민' 페르소나는 일상 거래에서 겪는 직관적인 민원을 구어체로 질문하고, 답변은 쉽고 친근한 언어로 공정거래 상식을 설명해야 합니다. (예: 불스원 재판매가격유지 사건(사건번호 25200) 관련 용품점 가격 강제 대리점 불공정 조항 등)\n"
            f"- '논문 준비 학생' 페르소나는 학술적/법리적인 깊은 질문을 해야 하며, 답변 또한 판례번호나 공정위 의결서 조항을 명시한 학술적·분석적 언어로 분석해야 합니다. (예: 동성제약 부당 고객유인 사건(사건번호 25544) 관련 리베이트 및 환자 권익 침해 법리 등)\n"
            f"- '청장년층' 페르소나는 인터넷 인강 환불, 헬스장 위약금, 다이어트 보조제 과장광고, 다크패턴(가짜 타이머, 자동체크 안심결제) 등 디지털 환경에서 겪는 실생활 피해 위주로 질문해야 합니다.\n"
            f"- 질문(query)들은 절대 템플릿 형태로 중복되거나 동일한 어조를 쓰지 말고, 1000건이 각각 다 다르게 고유한 실제 사연처럼 작성해주세요.\n"
            f"- 답변(answer)은 질문자가 이해하기 쉽도록 질문의 법적 위법 여부와 한도를 정확히 명시해주세요.\n"
            f"- applicable_law 필드에는 관련된 구체적 법률명과 조항을 적어주세요."
        )
        
        batch_data = call_gemini_api(prompt)
        
        if batch_data and isinstance(batch_data, list):
            valid_count = 0
            for item in batch_data:
                # 데이터 유효성 검사 및 정량 데이터 삽입
                if all(k in item for k in ["persona", "query", "answer", "signal_color", "applicable_law"]):
                    dataset.append(item)
                    valid_count += 1
            
            print(f"✅ {valid_count}개의 고품질 데이터 추가 완료. (누적: {len(dataset)}개)")
            
            # 중간 저장 실행
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(dataset, f, ensure_ascii=False, indent=2)
        else:
            print("⚠️ 이번 배치 생성에 실패했습니다. 5초 후 다시 시도합니다.")
            time.sleep(5)
            continue
            
        # API Rate Limit (15 RPM) 회피용 4초 대기
        time.sleep(4)

    print(f"🎉 1,000건의 기획서 맞춤형 고품질 QA 데이터셋 구축이 완료되었습니다! 경로: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_generator()
