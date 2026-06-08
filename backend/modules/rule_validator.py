import os
import re
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def extract_penalty_percentages(text: str) -> list:
    """
    텍스트에서 위약금/수수료 관련 퍼센트(%) 수치를 정규표현식으로 추출합니다.
    """
    patterns = [
        r'(?:위약금|수수료|공제|취소\s*수수료|환불\s*수수료|위약)\s*(?:은|는)?\s*(?:총\s*결제\s*금액의\s*)?(\d+)\s*(?:%|퍼센트)',
        r'(?:취소|환불|반환)\s*시\s*(?:총\s*금액의\s*)?(\d+)\s*(?:%|퍼센트)\s*(?:공제|부과)'
    ]
    percentages = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            try:
                percentages.append(int(match))
            except ValueError:
                continue
    return percentages

def extract_krw_amount(text: str) -> list:
    """
    텍스트에서 양도 수수료 등 원 단위 금액을 정규표현식으로 추출합니다.
    (예: 50,000원 -> 50000, 30000원 -> 30000)
    """
    pattern = r'(?:양도\s*수수료|양도비|양도\s*비용|변경\s*수수료|변경비)\s*(?:은|는)?\s*(\d{1,3}(?:,\d{3})*|\d+)\s*원'
    matches = re.findall(pattern, text)
    amounts = []
    for m in matches:
        clean_m = m.replace(",", "")
        try:
            amounts.append(int(clean_m))
        except ValueError:
            continue
    return amounts

def extract_refund_days(text: str) -> list:
    """
    텍스트에서 환불/청약철회 가능 일수(일)를 정규표현식으로 추출합니다.
    """
    pattern_days = r'(?:환불|취소|청약\s*철회|청약철회|반품)\s*(?:가능\s*)?(?:기한|기간)?\s*(\d+)\s*(?:일|하루)'
    pattern_after = r'(?:배송|구매|결제|인도)\s*(?:후|완료\s*후)\s*(\d+)\s*(?:일\s*이내|일\s*동안|일\s*안에)'
    days = []
    for pat in [pattern_days, pattern_after]:
        matches = re.findall(pat, text)
        for m in matches:
            try:
                days.append(int(m))
            except ValueError:
                continue
    return days

def call_openai_api(api_key: str, prompt: str) -> dict:
    """
    urllib를 사용하여 외부 의존성 없이 OpenAI API 호환 규격으로 LLM을 호출합니다.
    API Key 형식에 따라 자동으로 OpenAI 혹은 Google Gemini로 호스트 및 모델명을 전환합니다.
    """
    if api_key.startswith("AIzaSy"):
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        model_name = "gemini-3.5-flash"
    else:
        url = "https://api.openai.com/v1/chat/completions"
        model_name = "gpt-4o-mini"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    system_prompt = (
        "당신은 대한민국 공정거래위원회 약관법, 소비자분쟁해결기준, 표시광고법, 전자상거래법에 정통한 소비자 권리 보호 전문 AI 변호사입니다.\n"
        "제공된 텍스트(약관 또는 광고)를 먼저 카테고리별로 정밀 분류하고, 이에 따른 불공정 조항을 분석하여 반드시 아래 JSON 규격으로만 결과를 반환하세요.\n\n"
        "1. 카테고리 분류 기준 (classified_type):\n"
        "   - SPORTS: 체육시설 약관 (헬스장, 요가, 필라테스 등)\n"
        "   - ECOMMERCE: 전자상거래 약관 (인터넷 쇼핑몰, 인강 패키지 등)\n"
        "   - AD_DIET: 건강/뷰티 광고 (다이어트 보조제, 화장품 등)\n"
        "   - AD_FOMO: 쇼핑몰 마감 임박 광고 (선착순, 카운트다운 타이머 등 다크패턴)\n"
        "   - OTHER: 기타 일반 약관/광고\n\n"
        "2. 판정 색상(signal_color) 기준:\n"
        "   - RED: 명백한 법률 위반, 환불 절대 불가 조항, 법정 한도 초과 위약금, 객관적 근거가 전혀 없는 부작용 무조건 없음 등의 기만 광고.\n"
        "   - YELLOW: 법 위반은 아니나 소비자에게 다소 불리한 조항, 사은품 과다 청구, 모호한 약관 내용 등 주의 필요.\n"
        "   - GREEN: 공정위 표준약관 준수, 청약철회 및 환불 규정이 공정하고 명확함.\n\n"
        "3. 반드시 아래 스키마의 JSON 객체로만 응답하세요. 백틱(```)이나 마크다운 없이 순수 JSON만 반환해야 합니다:\n"
        "{\n"
        "  \"classified_type\": \"SPORTS\" | \"ECOMMERCE\" | \"AD_DIET\" | \"AD_FOMO\" | \"OTHER\",\n"
        "  \"llm_analysis\": \"전체 약관/광고의 핵심 위법성 또는 문제점을 친근하고 명확하게 요약한 설명 (한국어)\",\n"
        "  \"toxic_clauses\": [\n"
        "    {\n"
        "      \"clause\": \"문제가 되는 조항의 일부 텍스트 또는 명칭 (예: '제5조 환불 불가 조항')\",\n"
        "      \"reason\": \"해당 조항이 왜 불공정하거나 위법한지에 대한 법적 근거가 포함된 구체적 이유\"\n"
        "    }\n"
        "  ],\n"
        "  \"signal_color\": \"RED\" | \"YELLOW\" | \"GREEN\"\n"
        "}"
    )
    
    data = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0
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
            content = res_json["choices"][0]["message"]["content"].strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())
    except Exception as e:
        print(f"[Error] OpenAI API 호출 실패: {e}")
        return None

def validate_rules_node(state: dict) -> dict:
    print("[Node] 팀원 D - 규칙 기반 수치 검증 및 OpenAI 연동 신호등 판정 중...")
    
    raw_text = state.get("raw_text", "")
    input_type = state.get("input_type", "CONTRACT")
    
    # OpenAI API 호출 시도
    api_key = os.getenv("OPENAI_API_KEY")
    result = None
    
    if api_key and api_key != "your_openai_api_key_here":
        prompt = f"분류 타입: {input_type}\n분석할 텍스트:\n{raw_text}"
        result = call_openai_api(api_key, prompt)
        
    if not result:
        # Fallback 로직: API 키가 없거나 호출에 실패한 경우 로컬 규칙 기반 판정
        print("[Rule_Validator] 로컬 규칙 기반 Fallback 모드로 판정을 수행합니다.")
        
        # 1차 카테고리 로컬 분류
        classified_type = "OTHER"
        lower_text = raw_text.lower()
        if any(w in lower_text for w in ["헬스", "요가", "필라테스", "체육", "회원권"]):
            classified_type = "SPORTS"
        elif any(w in lower_text for w in ["쇼핑몰", "배송", "상품", "구매", "결제", "인강"]):
            classified_type = "ECOMMERCE"
        elif any(w in lower_text for w in ["다이어트", "부작용", "효능", "보조제", "화장품"]):
            classified_type = "AD_DIET"
        elif any(w in lower_text for w in ["마감", "선착순", "오늘만", "타이머"]):
            classified_type = "AD_FOMO"
            
        signal_color = "GREEN"
        llm_analysis = "약관/광고 내용에서 명백한 법적 위반 조항이 검출되지 않았습니다."
        toxic_clauses = []
        
        result = {
            "classified_type": classified_type,
            "llm_analysis": llm_analysis,
            "toxic_clauses": toxic_clauses,
            "signal_color": signal_color
        }

    # 3. [교차 검증 및 강제 보정] 명확한 정량적 기준에 맞춰 RED로 강제 교정 (Override)
    doc_type = result.get("classified_type", "OTHER")
    override_reasons = []

    # 3-1. 공통 강제 금지 키워드 검증
    # 약관에서 '환불 불가' 등의 강행법규 위반 문구 검출 시 무조건 RED
    if doc_type in ["SPORTS", "ECOMMERCE", "OTHER"]:
        forbidden_keywords = ["환불 불가", "취소 불가", "반환 불가", "환불이 불가", "취소가 불가"]
        if any(kw in raw_text for kw in forbidden_keywords):
            override_reasons.append({
                "clause": "환불/취소 절대 불가 조항",
                "reason": "약관법 제6조 및 전자상거래법 제17조에 따라 청약철회/해지 권리를 원천 박탈하는 면책 약관은 강행규정 위반으로 무효(RED)입니다."
            })

    # 3-2. SPORTS (체육시설 약관) 정밀 검증
    if doc_type == "SPORTS":
        # 기준 A: 위약금 10% 초과 여부
        penalty_pcts = extract_penalty_percentages(raw_text)
        if penalty_pcts and max(penalty_pcts) > 10:
            override_reasons.append({
                "clause": f"위약금/수수료 {max(penalty_pcts)}% 규정",
                "reason": f"소비자분쟁해결기준(체육시설업 고시)에 명시된 위약금 법수한도(10%)를 초과하는 {max(penalty_pcts)}%의 위약금을 규정하여 약관법 제8조에 따라 무효에 해당합니다."
            })
        
        # 기준 B: 양도 수수료 3만원 초과 여부
        transfer_amounts = extract_krw_amount(raw_text)
        if transfer_amounts and max(transfer_amounts) > 30000:
            override_reasons.append({
                "clause": f"양도 수수료 {max(transfer_amounts):,}원 조항",
                "reason": f"회원권 양도 대행 및 명의변경 수수료가 합리적인 실비 기준(정액 3만 원)을 초과하는 {max(transfer_amounts):,}원으로 명시되어 부당한 고객 불이익 조항(RED)에 해당합니다."
            })

    # 3-3. ECOMMERCE (전자상거래 약관) 정밀 검증
    elif doc_type == "ECOMMERCE":
        # 기준 A: 단순변심 환불 기간 7일 미만 제한
        refund_days = extract_refund_days(raw_text)
        if refund_days and min(refund_days) < 7:
            override_reasons.append({
                "clause": f"청약철회 기간 {min(refund_days)}일 제한 조항",
                "reason": f"전자상거래법 제17조에 따른 법정 단순 변심 청약철회 보장 기간(7일)을 무단으로 단축하는 {min(refund_days)}일 취소 제한 규정으로 무효(RED)입니다."
            })
            
        # 기준 B: 개봉 시 환불 불가 등 기만 조항
        if "개봉 시 환불" in raw_text or "박스 훼손 시" in raw_text or "비닐 제거 시" in raw_text:
            override_reasons.append({
                "clause": "단순 포장 개봉 시 환불 불가 조항",
                "reason": "전자상거래법 제17조 제2항에 의거, 상품 가치가 완전히 멸실되지 않고 단순히 내용물 확인을 위해 포장을 개봉한 경우 청약철회가 가능하므로 위법한 면책 조항(RED)입니다."
            })

    # 3-4. AD_DIET (건강/뷰티 기만 광고) 정밀 검증
    elif doc_type == "AD_DIET":
        # 기준 A: 안전성/부작용 제로 확정적 기만 표현
        fomo_words = ["부작용 100% 없음", "부작용 전혀 없음", "부작용 제로", "부작용 0%"]
        if any(w in raw_text for w in fomo_words):
            override_reasons.append({
                "clause": "부작용 없음 확정적 문구",
                "reason": "표시광고법 제3조에 의거하여 의학적/객관적 근거 없이 안전성을 100% 단정 짓는 기만적 과장 광고 행위(RED)에 해당합니다."
            })

    # 3-5. 강제 보정 적용
    if override_reasons:
        print(f"[Rule_Validator] 정량 기준 위반 검출. 최종 신호등을 RED로 강제 교정합니다. (검출 건수: {len(override_reasons)})")
        result["signal_color"] = "RED"
        
        # 독소 조항 목록에 중복되지 않게 검증 위반 조항 병합
        for reason_item in override_reasons:
            if not any(c["clause"] == reason_item["clause"] for c in result["toxic_clauses"]):
                result["toxic_clauses"].append(reason_item)
                
        # 요약 설명 강제 보강
        warning_prefix = "[정량 검증 위반 발견] 해당 문서에서 명백한 법적 위반 기준이 감지되어 강제 RED 판정되었습니다. "
        if warning_prefix not in result["llm_analysis"]:
            result["llm_analysis"] = warning_prefix + result["llm_analysis"]

    return result
