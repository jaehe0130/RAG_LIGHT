import re

def parse_korean_number_to_float(val: str) -> float:
    """
    한글 수치 및 천단위 쉼표, 소수점이 들어간 숫자를 실수(float)로 변환합니다.
    """
    val = val.strip().replace(",", "")
    try:
        return float(val)
    except ValueError:
        pass
    
    ko_nums = {
        "일": 1.0, "이": 2.0, "삼": 3.0, "사": 4.0, "오": 5.0, "육": 6.0, "칠": 7.0, "팔": 8.0, "구": 9.0,
        "십": 10.0, "이십": 20.0, "삼십": 30.0, "사십": 40.0, "오십": 50.0, "육십": 60.0, "칠십": 70.0, "팔십": 80.0, "구십": 90.0, "백": 100.0,
        "십오": 15.0, "이십오": 25.0, "삼십오": 35.0, "사십오": 45.0, "오십오": 55.0
    }
    return ko_nums.get(val, 0.0)

def parse_korean_number_to_int(val: str) -> int:
    """
    하위 호환성을 위해 정수(int) 형태를 반환하도록 유지합니다.
    """
    return int(parse_korean_number_to_float(val))

def extract_penalty_percentages(text: str) -> list:
    """
    약관 본문 내 위약금/수수료 비율(%)을 정규식 패턴으로 추출합니다 (실수 지원).
    매치 바로 뒤에 '이하', '이내', '미만' 등 허용 범위 표현이 오면 정량 위반 대상에서 배제합니다.
    """
    num_pattern = r'(\d+(?:\.\d+)?|이십오|삼십오|사십오|오십오|십오|이십|삼십|사십|오십|육십|칠십|팔십|구십|일|이|삼|사|오|육|칠|팔|구|십|백)'
    patterns = [
        r'(?:위약금|수수료|공제|취소\s*수수료|환불\s*수수료|위약)\s*(?:은|는)?\s*(?:총\s*결제\s*금액의\s*)?' + num_pattern + r'\s*(?:%|퍼센트)',
        r'(?:취소|환불|반환)\s*시\s*(?:총\s*금액의\s*)?' + num_pattern + r'\s*(?:%|퍼센트)\s*(?:공제|부과)',
        num_pattern + r'\s*(?:%|퍼센트)\s*(?:이|가)?\s*(?:위약금|수수료|공제|위약)\s*(?:으로|로)?\s*(?:부과|청구|공제)'
    ]
    percentages = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            num_str = match.group(1)
            val = parse_korean_number_to_float(num_str)
            if val > 0:
                # 매치 직후의 문맥을 분석하여 예외 조건 필터링
                end_pos = match.end()
                lookahead = text[end_pos:end_pos+10].strip()
                if any(w in lookahead for w in ("이하", "이내", "미만", "적법", "준수")):
                    continue
                percentages.append(val)
    return percentages

def extract_krw_amount(text: str) -> list:
    """
    양도비, 변경 수수료 등 정액 원화 금액(KRW) 수치를 추출합니다.
    매치 뒤에 '이하', '이내' 등 한도 범위 표현이 오면 배제합니다.
    """
    pattern = r'(?:양도\s*수수료|양도비|양도\s*비용|변경\s*수수료|변경비)\s*(?:은|는)?\s*(\d{1,3}(?:,\d{3})*|\d+(?:\.\d+)?|일만|이만|삼만|사만|오만|육만|칠만|팔만|구만|십만|이십|삼십|사십|오십|십|일|이|삼|사|오|육|칠|팔|구)\s*(만)?\s*원'
    amounts = []
    
    ko_map = {
        "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9,
        "십": 10, "이십": 20, "삼십": 30, "사십": 40, "오십": 50,
        "일만": 10000, "이만": 20000, "삼만": 30000, "사만": 40000, "오만": 50000,
        "육만": 60000, "칠만": 70000, "팔만": 80000, "구만": 90000, "십만": 100000
    }
    
    for match in re.finditer(pattern, text):
        m = match.group(1)
        man = match.group(2)
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
            end_pos = match.end()
            lookahead = text[end_pos:end_pos+10].strip()
            if any(w in lookahead for w in ("이하", "이내", "미만")):
                continue
            amounts.append(val)
    return amounts

def extract_refund_days(text: str) -> list:
    """
    환불 또는 청약철회가 가능한 기한(일수)을 추출합니다.
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

def run_quantitative_checks(raw_text: str, doc_type: str) -> list:
    """
    공정거래 약관 고시 및 전자상거래법의 강행 법규 위반 사항을 결정론적으로 검출합니다.
    """
    override_reasons = []

    # 1. 공통 환불 절대 불가 표현 감지 (약관법 제6조 위배)
    if doc_type in ("SPORTS", "ECOMMERCE", "OTHER"):
        forbidden_keywords = (
            "환불 불가", "취소 불가", "반환 불가", "환불이 불가", "취소가 불가",
            "반품 불가", "반품이 불가", "교환 불가", "교환이 불가", "환불 안됨", "환불은 안됨", "교환 안됨"
        )
        if any(kw in raw_text for kw in forbidden_keywords):
            override_reasons.append({
                "clause": "환불/취소 절대 불가 조항",
                "reason": "약관법 제6조 및 전자상거래법 제17조에 따라 청약철회/해지 권리를 원천 박탈하는 면책 약관은 강행규정 위반으로 무효(RED)입니다."
            })

    # 2. SPORTS (체육시설업 고시 위약금 한도 10% 및 양도 수수료 3만원 한도 검증)
    if doc_type == "SPORTS":
        penalty_pcts = extract_penalty_percentages(raw_text)
        if penalty_pcts and max(penalty_pcts) > 10:
            override_reasons.append({
                "clause": f"위약금/수수료 {max(penalty_pcts)}% 규정",
                "reason": f"소비자분쟁해결기준(체육시설업 고시)에 명시된 위약금 법수한도(10%)를 초과하는 {max(penalty_pcts)}%의 위약금을 규정하여 약관법 제8조에 따라 무효에 해당합니다."
            })
        
        transfer_amounts = extract_krw_amount(raw_text)
        if transfer_amounts and max(transfer_amounts) > 30000:
            override_reasons.append({
                "clause": f"양도 수수료 {max(transfer_amounts):,}원 조항",
                "reason": f"회원권 양도 대행 및 명의변경 수수료가 합리적인 실비 기준(정액 3만 원)을 초과하는 {max(transfer_amounts):,}원으로 명시되어 부당한 고객 불이익 조항(RED)에 해당합니다."
            })

    # 3. ECOMMERCE (전자상거래법상 7일 청약철회 기한 및 포장 단순개봉 환불 보장 검증)
    elif doc_type == "ECOMMERCE":
        refund_days = extract_refund_days(raw_text)
        if refund_days and min(refund_days) < 7:
            override_reasons.append({
                "clause": f"청약철회 기간 {min(refund_days)}일 제한 조항",
                "reason": f"전자상거래법 제17조에 따른 법정 단순 변심 청약철회 보장 기간(7일)을 무단으로 단축하는 {min(refund_days)}일 취소 제한 규정으로 무효(RED)입니다."
            })
            
        if any(w in raw_text for w in ("개봉 시 환불", "박스 훼손 시", "비닐 제거 시")):
            override_reasons.append({
                "clause": "단순 포장 개봉 시 환불 불가 조항",
                "reason": "전자상거래법 제17조 제2항에 의거, 상품 가치가 완전히 멸실되지 않고 단순히 내용물 확인을 위해 포장을 개봉한 경우 청약철회가 가능하므로 위법한 면책 조항(RED)입니다."
            })

    # 4. AD_DIET (표시광고법상 단정적 안전성 광고 검증)
    elif doc_type == "AD_DIET":
        fomo_words = ("부작용 100% 없음", "부작용 전혀 없음", "부작용 제로", "부작용 0%")
        if any(w in raw_text for w in fomo_words):
            override_reasons.append({
                "clause": "부작용 없음 확정적 문구",
                "reason": "표시광고법 제3조에 의거하여 의학적/객관적 근거 없이 안전성을 100% 단정 짓는 기만적 과장 광고 행위(RED)에 해당합니다."
            })

    # 5. AD_FOMO (전자상거래법상 기만적 소비자 유인 다크패턴 기법 검출)
    elif doc_type == "AD_FOMO":
        fomo_keywords = (
            "오늘 단 하루", "오늘만 이 가격", "마지막 기회", "마감 임박", "선착순 10명", 
            "선착순 5명", "남은 수량 1개", "실시간 구매", "카운트다운", "마감 직전",
            "오늘만 이 혜택", "선착순 마감"
        )
        detected_words = [w for w in fomo_keywords if w in raw_text]
        if detected_words:
            override_reasons.append({
                "clause": f"마감 압박 및 선착순 기만 표현 감지 ({', '.join(detected_words)})",
                "reason": "전자상거래법 제21조 제1항 제1호(기만적 방법을 사용하여 소비자를 유인) 및 표시광고법 제3조에 의거하여, 합리적인 근거 없이 소비자의 불안이나 충동구매를 유도하는 마감 임박 및 선착순 기만 광고 조항(RED)에 해당합니다."
            })

    return override_reasons

class RuleAuditor:
    def audit(self, raw_text: str, classified_type: str) -> list:
        return run_quantitative_checks(raw_text, classified_type)

def rule_auditor_node(state: dict) -> dict:
    """
    LangGraph 서브그래프의 정량 위반 룰 검출 노드
    """
    print("[SubgraphNode] Rule Auditor Agent - 정량적 규칙 검증 시작")
    auditor = RuleAuditor()
    audit_report = auditor.audit(state["raw_text"], state["classified_type"])
    print(f"  └─ 검출된 위반 수: {len(audit_report)}건")
    return {"audit_report": audit_report}

