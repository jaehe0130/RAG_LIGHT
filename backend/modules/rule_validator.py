import os
import re
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def parse_korean_number_to_int(val: str) -> int:
    val = val.strip().replace(",", "")
    if val.isdigit():
        return int(val)
    try:
        return int(float(val))
    except ValueError:
        pass
    
    ko_nums = {
        "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9,
        "십": 10, "이십": 20, "삼십": 30, "사십": 40, "오십": 50, "육십": 60, "칠십": 70, "팔십": 80, "구십": 90, "백": 100,
        "십오": 15, "이십오": 25, "삼십오": 35, "사십오": 45, "오십오": 55
    }
    return ko_nums.get(val, 0)

def extract_penalty_percentages(text: str) -> list:
    """
    텍스트에서 위약금/수수료 관련 퍼센트(%) 수치를 정규표현식으로 추출합니다.
    """
    num_pattern = r'(\d+|이십오|삼십오|사십오|오십오|십오|이십|삼십|사십|오십|육십|칠십|팔십|구십|일|이|삼|사|오|육|칠|팔|구|십|백)'
    patterns = [
        r'(?:위약금|수수료|공제|취소\s*수수료|환불\s*수수료|위약)\s*(?:은|는)?\s*(?:총\s*결제\s*금액의\s*)?' + num_pattern + r'\s*(?:%|퍼센트)',
        r'(?:취소|환불|반환)\s*시\s*(?:총\s*금액의\s*)?' + num_pattern + r'\s*(?:%|퍼센트)\s*(?:공제|부과)'
    ]
    percentages = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            val = parse_korean_number_to_int(match)
            if val > 0:
                percentages.append(val)
    return percentages

def extract_krw_amount(text: str) -> list:
    """
    텍스트에서 양도 수수료 등 원 단위 금액을 정규표현식으로 추출합니다.
    (예: 50,000원 -> 50000, 30000원 -> 30000)
    """
    pattern = r'(?:양도\s*수수료|양도비|양도\s*비용|변경\s*수수료|변경비)\s*(?:은|는)?\s*(\d{1,3}(?:,\d{3})*|\d+(?:\.\d+)?|일만|이만|삼만|사만|오만|육만|칠만|팔만|구만|십만|이십|삼십|사십|오십|십|일|이|삼|사|오|육|칠|팔|구)\s*(만)?\s*원'
    matches = re.findall(pattern, text)
    amounts = []
    
    ko_map = {
        "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9,
        "십": 10, "이십": 20, "삼십": 30, "사십": 40, "오십": 50,
        "일만": 10000, "이만": 20000, "삼만": 30000, "사만": 40000, "오만": 50000,
        "육만": 60000, "칠만": 70000, "팔만": 80000, "구만": 90000, "십만": 100000
    }
    
    for m, man in matches:
        amount_str = m.strip().replace(",", "")
        has_man = bool(man)
        val = 0
        if amount_str in ko_map:
            val = ko_map[amount_str]
            if val < 10000 and has_man:
                val *= 10000
        else:
            try:
                val = int(float(amount_str))
                if has_man or val < 100:
                    if val < 1000:
                        val *= 10000
            except ValueError:
                continue
        if val > 0:
            amounts.append(val)
    return amounts

def extract_refund_days(text: str) -> list:
    """
    텍스트에서 환불/청약철회 가능 일수(일)를 정규표현식으로 추출합니다.
    """
    pattern_days = r'(?:환불|취소|청약\s*철회|청약철회|반품)\s*(?:가능\s*)?(?:기한|기간)?\s*(\d+주일|\d+주|일주일|이주일|1주일|2주일|주일|이틀|하루|일일|십사일|삼일|오일|육일|칠일|팔일|구일|십일|일|이|삼|사|오|육|칠|팔|구|십|이주|2주|주|\d+)\s*(?:일|하루|주일|주)?'
    pattern_after = r'(?:배송|구매|결제|인도)\s*(?:후|완료\s*후)\s*(\d+주일|\d+주|일주일|이주일|1주일|2주일|주일|이틀|하루|일일|십사일|삼일|오일|육일|칠일|팔일|구일|십일|일|이|삼|사|오|육|칠|팔|구|십|이주|2주|주|\d+)\s*(?:일|주일|주|하루)?\s*(?:이내|동안|안에)'
    days = []
    
    def parse_days(days_str: str) -> int:
        days_str = days_str.strip()
        if days_str.endswith("주일") and days_str[:-2].isdigit():
            return int(days_str[:-2]) * 7
        if days_str.endswith("주") and days_str[:-1].isdigit():
            return int(days_str[:-1]) * 7
            
        if days_str in ["일주일", "1주일", "1주", "주일", "7일", "칠일", "칠", "주"]:
            return 7
        if days_str in ["이주일", "2주", "2주일", "14일", "십사일", "이주"]:
            return 14
        if days_str in ["하루", "일일", "1일", "일"]:
            return 1
        if days_str in ["이틀", "2일", "이일", "이"]:
            return 2
        if days_str in ["사흘", "3일", "삼일", "삼"]:
            return 3
        if days_str in ["나흘", "4일", "사일", "사"]:
            return 4
        if days_str in ["5일", "오일", "오"]:
            return 5
        if days_str in ["6일", "육일", "육"]:
            return 6
        if days_str in ["8일", "팔일", "팔"]:
            return 8
        if days_str in ["9일", "구일", "구"]:
            return 9
        if days_str in ["10일", "십일", "십"]:
            return 10
            
        try:
            return int(days_str)
        except ValueError:
            return 0

    for pat in [pattern_days, pattern_after]:
        matches = re.findall(pat, text)
        for m in matches:
            val = parse_days(m)
            if val > 0:
                days.append(val)
    return days

def call_openai_api(api_key: str, prompt: str) -> dict:
    """
    urllib를 사용하여 외부 의존성 없이 OpenAI API 호환 규격으로 LLM을 호출합니다.
    API Key 형식에 따라 자동으로 OpenAI 혹은 Google Gemini로 호스트 및 모델명을 전환합니다.
    """
    if api_key.startswith("AIzaSy"):
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        model_name = "gemini-3.1-flash-lite"
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
        if input_type == "CONTRACT":
            if any(w in lower_text for w in ["헬스", "요가", "필라테스", "체육", "회원권"]):
                classified_type = "SPORTS"
            elif any(w in lower_text for w in ["쇼핑몰", "배송", "상품", "구매", "결제", "인강"]):
                classified_type = "ECOMMERCE"
        else: # AD
            if any(w in lower_text for w in ["다이어트", "부작용", "효능", "보조제", "화장품"]):
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

    # 2-1. 결과 데이터 구조 정규화 및 방어적 초기화 (Defensive schema check)
    if not isinstance(result, dict):
        result = {}
    if "classified_type" not in result:
        result["classified_type"] = "OTHER"
    if "llm_analysis" not in result or not isinstance(result["llm_analysis"], str):
        result["llm_analysis"] = str(result.get("llm_analysis", ""))
    if "toxic_clauses" not in result or not isinstance(result["toxic_clauses"], list):
        result["toxic_clauses"] = []
    if "signal_color" not in result or not isinstance(result["signal_color"], str):
        result["signal_color"] = "GREEN"

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

    # 3-5. AD_FOMO (쇼핑몰 마감 임박 광고 - 다크패턴) 정밀 검증
    elif doc_type == "AD_FOMO":
        # 기준 A: 선착순, 마감 임박, 카운트다운 타이머 조작 등 압박용 다크패턴 표현
        fomo_keywords = [
            "오늘 단 하루", "오늘만 이 가격", "마지막 기회", "마감 임박", "선착순 10명", 
            "선착순 5명", "남은 수량 1개", "실시간 구매", "카운트다운", "마감 직전",
            "오늘만 이 혜택", "선착순 마감"
        ]
        detected_words = [w for w in fomo_keywords if w in raw_text]
        if detected_words:
            override_reasons.append({
                "clause": f"마감 압박 및 선착순 기만 표현 감지 ({', '.join(detected_words)})",
                "reason": "전자상거래법 제21조 제1항 제1호(기만적 방법을 사용하여 소비자를 유인) 및 표시광고법 제3조에 의거하여, 합리적인 근거 없이 소비자의 불안이나 충동구매를 유도하는 마감 임박 및 선착순 기만 광고 조항(RED)에 해당합니다."
            })

    # 3-6. 강제 보정 적용
    if override_reasons:
        print(f"[Rule_Validator] 정량 기준 위반 검출. 최종 신호등을 RED로 강제 교정합니다. (검출 건수: {len(override_reasons)})")
        result["signal_color"] = "RED"
        
        # 독소 조항 목록에 중복되지 않게 검증 위반 조항 병합
        for reason_item in override_reasons:
            exists = False
            for c in result["toxic_clauses"]:
                if isinstance(c, dict) and c.get("clause") == reason_item["clause"]:
                    exists = True
                    break
            if not exists:
                result["toxic_clauses"].append(reason_item)
                
        # 요약 설명 강제 보강 (문맥 모순 방지를 위해 기존 의견을 덮어쓰고 위반 항목 리스트업)
        reasons_summary = ", ".join([f"'{r['clause']}'" for r in override_reasons])
        result["llm_analysis"] = (
            f"[정량 검증 위반 발견] 본 문서에서 명백한 법률 위반 기준({reasons_summary})이 감지되어 강제 RED 판정되었습니다. "
            f"자세한 위법성 여부는 아래에 탐지된 독소 조항과 상세 법적 근거를 확인해 주세요."
        )

    return result
