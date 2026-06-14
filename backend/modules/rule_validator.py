import os
import re
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

# .env 파일 로드
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "rules_config.json")

def load_rules_config() -> dict:
    """rules_config.json 설정 파일을 로드합니다."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Warning] rules_config.json 로드 실패, 기본값 사용: {e}")
        return {
            "SPORTS": {
                "max_penalty_percent": 10,
                "max_transfer_fee": 30000,
                "forbidden_keywords": ["일시정지 불가", "가입비 반환 불가", "가입비 환불 불가"]
            },
            "ECOMMERCE": {
                "min_refund_days": 7,
                "opening_restrictions": ["개봉 시 환불", "박스 훼손 시", "비닐 제거 시"]
            },
            "COMMON": {
                "forbidden_keywords": ["환불 불가", "취소 불가", "반환 불가", "환불이 불가", "취소가 불가"]
            },
            "AD_DIET": {
                "fomo_words": ["부작용 100% 없음", "부작용 전혀 없음", "부작용 제로", "부작용 0%"]
            },
            "AD_FOMO": {
                "fomo_keywords": [
                    "오늘 단 하루", "오늘만 이 가격", "마지막 기회", "마감 임박", "선착순 10명", 
                    "선착순 5명", "남은 수량 1개", "실시간 구매", "카운트다운", "마감 직전",
                    "오늘만 이 혜택", "선착순 마감"
                ]
            }
        }

def clean_ocr_typos(text: str) -> str:
    """
    OCR 인식 시 발생하기 쉬운 수치 관련 오타를 보정합니다.
    (예: 1O% -> 10%, l0% -> 10%, 3만원 -> 3만원)
    """
    if not text:
        return ""
    # 1. 숫자 바로 뒤의 영문 O, o를 0으로 보정 (예: 1O% -> 10%)
    text = re.sub(r'(?<=\d)[Oo](?=\b|%|\s|원)', '0', text)
    # 2. % 바로 앞이나 숫자 사이의 소문자 l, 대문자 I를 숫자 1로 보정 (예: l0% -> 10%, 1I% -> 11%)
    text = re.sub(r'(?<=\b)[lL](?=\d)', '1', text)
    text = re.sub(r'(?<=\d)[iIlL](?=\b|%)', '1', text)
    return text

def parse_korean_number_to_int(val: str) -> int:
    """
    다양한 형태의 한글 수치(예: "삼십오", "오십", "10", "3만")를 아라비아 숫자 정수로 변환합니다.
    """
    val = val.strip().replace(",", "")
    if not val:
        return 0
    if val.isdigit():
        return int(val)
    try:
        return int(float(val))
    except ValueError:
        pass
    
    # 한글 수치 매핑 사전
    units = {"십": 10, "백": 100, "천": 1000, "만": 10000}
    digits = {
        "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9,
        "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "0": 0
    }
    
    total = 0
    current = 0
    
    for char in val:
        if char in digits:
            current += digits[char]
        elif char in units:
            unit_val = units[char]
            if current == 0:
                current = 1
            if unit_val == 10000:
                total += current
                total *= 10000
                current = 0
            else:
                total += current * unit_val
                current = 0
    total += current
    return total

def extract_penalty_percentages(text: str) -> list:
    """
    텍스트에서 위약금/수수료 관련 퍼센트(%) 수치를 정규표현식으로 추출합니다.
    """
    text = clean_ocr_typos(text)
    num_pattern = r'(\d+(?:\.\d+)?|[일이삼사오육칠팔구십백천만십오이십오삼십오사십오오십오]+)'
    patterns = [
        r'(?:위약금|수수료|공제|취소\s*수수료|환불\s*수수료|위약)\s*(?:은|는)?\s*(?:총\s*결제\s*금액의\s*)?' + num_pattern + r'\s*(?:%|퍼센트)',
        r'(?:취소|환불|반환)\s*시\s*(?:총\s*금액의\s*)?' + num_pattern + r'\s*(?:%|퍼센트)\s*(?:공제|부과)',
        num_pattern + r'\s*(?:%|퍼센트)\s*(?:이|가)?\s*(?:위약금|수수료|공제|위약)\s*(?:으로|로)?\s*(?:부과|청구|공제)'
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
    (예: 50,000원 -> 50000, 3만 원 -> 30000, 오만원 -> 50000)
    """
    text = clean_ocr_typos(text)
    num_pattern = r'(\d{1,3}(?:,\d{3})*|\d+(?:\.\d+)?|[일이삼사오육칠팔구십백천만\s]+)'
    pattern = r'(?:양도\s*수수료|양도비|양도\s*비용|변경\s*수수료|변경비)\s*(?:은|는)?\s*' + num_pattern + r'\s*원'
    matches = re.findall(pattern, text)
    amounts = []
    
    for m in matches:
        m_clean = m.replace(" ", "").replace(",", "")
        float_man_match = re.match(r'^(\d+(?:\.\d+)?)\s*만$', m_clean)
        if float_man_match:
            val = int(float(float_man_match.group(1)) * 10000)
        else:
            val = parse_korean_number_to_int(m_clean)
        if val > 0:
            amounts.append(val)
    return amounts

def extract_refund_days(text: str) -> list:
    """
    텍스트에서 환불/청약철회 가능 일수(일)를 정규표현식으로 추출합니다.
    (예: 7일, 일주일, 14일, 십사일)
    """
    text = clean_ocr_typos(text)
    num_pattern = r'(\d+|일주일|이주일|하루|이틀|사흘|나흘|주일|[일이삼사오육칠팔구십]+주일|[일이삼사오육칠팔구십]+주|[일이삼사오육칠팔구십]+일|[일이삼사오육칠팔구십]+)'
    
    pattern_days = r'(?:환불|취소|청약\s*철회|청약철회|반품)\s*(?:가능\s*)?(?:기한|기간)?\s*' + num_pattern + r'\s*(?:일|하루|주일|주)?'
    pattern_after = r'(?:배송|구매|결제|인도)\s*(?:후|완료\s*후)\s*' + num_pattern + r'\s*(?:일|주일|주|하루)?\s*(?:이내|동안|안에)'
    
    days = []
    
    def parse_days(days_str: str) -> int:
        days_str = days_str.strip().replace(" ", "")
        if not days_str:
            return 0
            
        if days_str in ["일주일", "1주일", "1주", "주일", "주", "칠일", "7일"]:
            return 7
        if days_str in ["이주일", "2주일", "2주", "이주", "십사일", "14일"]:
            return 14
        if days_str in ["하루", "1일", "일일"]:
            return 1
        if days_str in ["이틀", "2일"]:
            return 2
        if days_str in ["사흘", "3일"]:
            return 3
        if days_str in ["나흘", "4일"]:
            return 4
            
        week_match = re.match(r'^([일이삼사오육칠팔구십\d]+)(?:주일|주)$', days_str)
        if week_match:
            val = parse_korean_number_to_int(week_match.group(1))
            return val * 7
            
        day_match = re.match(r'^([일이삼사오육칠팔구십\d]+)일$', days_str)
        if day_match:
            return parse_korean_number_to_int(day_match.group(1))
            
        return parse_korean_number_to_int(days_str)

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
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    else:
        url = "https://api.openai.com/v1/chat/completions"
        model_name = "gpt-4o-mini"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    system_prompt = (
        "당신은 대한민국 공정거래위원회 약관법, 소비자분쟁해결기준, 표시광고법, 전자상거래법에 정통하며 대국민 소비자 보호를 책임지는 공정거래 전문 AI 변호사입니다.\n"
        "제공된 텍스트를 정밀 분석하여 소비자가 겪을 수 있는 불공정 피해(과도한 위약금, 다크패턴 기만광고 등)를 사전 예방하기 위해 아래 지침을 준수하여 분석을 수행하세요.\n\n"
        "1. 모든 분석과 해설은 반드시 철저하게 '일반 소비자의 시각(Consumer-centric)'에서 쉽고 친근하게 기술되어야 합니다.\n"
        "   - 기업 간 행정 처벌 중심의 어려운 용어를 배제하고, 해당 행위가 소비자의 호주머니(생활비 부담, 위약금 손해, 선택권 제한 등)에 미치는 실질적인 피해와 영향 위주로 설명하세요.\n"
        "   - 만약 다이어트 보조제, 화장품, 노년층 표적 상품이거나 심각한 안전/부작용 기만 광고인 경우, 분석 요약(llm_analysis)의 최전두에 반드시 '**[어르신 주의!]**' 문구와 함께 직관적이고 쉬운 반말/존댓말 혼용 경고를 포함하세요.\n"
        "   - 전문적인 분석이 요구되는 법적 근거가 있을 경우, 분석 요약 하단에 '**[법리 리포트]**' 머리글과 함께 관련 공정위 의결서 번호나 대법원 판례를 정확히 인용하여 근거를 병기하세요.\n\n"
        "2. 카테고리 분류 기준 (classified_type):\n"
        "   - SPORTS: 체육시설 약관 (헬스장, 요가, 필라테스 등)\n"
        "   - ECOMMERCE: 전자상거래 약관 (인터넷 쇼핑몰, 인강 패키지 등)\n"
        "   - AD_DIET: 건강/뷰티 광고 (다이어트 보조제, 화장품 등)\n"
        "   - AD_FOMO: 쇼핑몰 마감 임박 광고 (선착순, 카운트다운 타이머 등 다크패턴)\n"
        "   - OTHER: 기타 일반 약관/광고\n\n"
        "3. 판정 색상(signal_color) 기준:\n"
        "   - RED: 소비자 권리를 박탈하는 환불 절대 불가 조항, 법정 한도(10%) 초과 위약금, 안전성 단정 기만 광고 등 명백한 소비자 피해 유발 조항.\n"
        "   - YELLOW: 소비자에게 불리한 조항, 사은품 과다 공제, 정보가 모호하여 주의가 필요한 광고.\n"
        "   - GREEN: 소비자 관련 법률을 준수하여 소비자 권리가 공정하게 보장됨.\n\n"
        "4. 반드시 아래 스키마의 JSON 객체로만 응답하세요. 백틱(```)이나 마크다운 없이 순수 JSON만 반환해야 합니다:\n"
        "{\n"
        "  \"classified_type\": \"SPORTS\" | \"ECOMMERCE\" | \"AD_DIET\" | \"AD_FOMO\" | \"OTHER\",\n"
        "  \"llm_analysis\": \"소비자 관점에서의 요약 설명 (반드시 지침에 따라 [어르신 주의!] 혹은 [법리 리포트] 형식을 적용할 것)\",\n"
        "  \"toxic_clauses\": [\n"
        "    {\n"
        "      \"clause\": \"문제가 되는 조항의 일부 텍스트 또는 명칭 (예: '제5조 환불 불가 조항')\",\n"
        "      \"reason\": \"소비자에게 왜 불공정하거나 위법한지에 대한 법적 근거가 포함된 구체적 이유\"\n"
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
        with urllib.request.urlopen(req, timeout=30) as response:
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
    if not raw_text or not raw_text.strip():
        print("[Rule_Validator] 추출된 텍스트가 없어 분석을 생략합니다.")
        return {
            "classified_type": "OTHER",
            "llm_analysis": "추출된 텍스트가 없어 공정거래 분석을 수행할 수 없습니다. 문서 이미지를 다시 촬영하거나 선명한 파일로 업로드해주세요.",
            "toxic_clauses": [],
            "signal_color": "YELLOW"
        }
        
    input_type = state.get("input_type", "CONTRACT")
    
    # rules_config.json 로드
    rules_cfg = load_rules_config()
    
    # 1. 수치 사전 감지 (Regex를 이용한 선측정 및 LLM 프롬프트 가이딩)
    pre_detected = []
    penalty_pcts = extract_penalty_percentages(raw_text)
    if penalty_pcts:
        pre_detected.append(f"- 위약금/수수료 비율: {max(penalty_pcts)}%")
    transfer_amounts = extract_krw_amount(raw_text)
    if transfer_amounts:
        pre_detected.append(f"- 양도/명의변경 수수료 금액: {max(transfer_amounts):,}원")
    refund_days = extract_refund_days(raw_text)
    if refund_days:
        pre_detected.append(f"- 단순변심 청약철회/환불 가능 기간: {min(refund_days)}일")
        
    # AD_FOMO 키워드 사전 체크
    fomo_cfg = rules_cfg.get("AD_FOMO", {}).get("fomo_keywords", [])
    detected_fomo = [w for w in fomo_cfg if w in raw_text]
    if detected_fomo:
        pre_detected.append(f"- 마감 압박/선착순 다크패턴 키워드 감지: {', '.join(detected_fomo)}")
        
    # API 호출 시도 (OPENAI_API_KEY 환경변수에 기입된 키 사용)
    api_key = os.getenv("OPENAI_API_KEY")
    result = None
    if api_key and api_key != "your_openai_api_key_here":
        # RAG 검색 문서들을 컨텍스트로 프롬프트에 결합
        retrieved_docs = state.get("retrieved_docs", [])
        
        context_str = ""
        if retrieved_docs:
            context_str += "\n[참고 공정거래위원회 및 한국소비자원 유사 사례]\n"
            for i, doc in enumerate(retrieved_docs[:3], 1):
                context_str += f"사례 {i}:\n{doc}\n\n"
                
        prompt = f"분류 타입: {input_type}\n\n분석할 약관/광고 텍스트:\n{raw_text}\n"
        
        # [사전 감지 정량 수치]를 프롬프트 컨텍스트에 주입하여 LLM의 환각 방지
        if pre_detected:
            prompt += "\n--- [시스템 사전 감지 정량 지표] ---\n"
            prompt += "\n".join(pre_detected)
            prompt += "\n\n(참고: 위 정량 수치 및 감지된 내용은 시스템 정규식에 의해 추출된 사실입니다. 이를 바탕으로 카테고리를 정확히 인지하고 법률 위반 여부를 판정하세요.)\n"
            
        if context_str:
            prompt += f"\n--- RAG 검색 참조 유사 사례 ---\n{context_str}"
            prompt += "\n참조 사례에 기재된 공정위 및 소비자원의 위법 판단 논리와 근거 법조문을 적극 참고하여, 분석 대상 텍스트의 위법 여부를 정밀하게 판정하고 이유를 설명하세요."
            
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

    # 결과 데이터 구조 정규화
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

    # [교차 검증 및 강제 보정] JSON 설정 파일 기준에 맞춰 RED로 강제 교정 (Override)
    doc_type = result.get("classified_type", "OTHER")
    override_reasons = []

    # 1. 공통 강제 금지 키워드 검증
    common_cfg = rules_cfg.get("COMMON", {})
    forbidden_keywords = common_cfg.get("forbidden_keywords", [])
    if doc_type in ["SPORTS", "ECOMMERCE", "OTHER"]:
        if any(kw in raw_text for kw in forbidden_keywords):
            override_reasons.append({
                "clause": "환불/취소 절대 불가 조항",
                "reason": "약관법 제6조 및 전자상거래법 제17조에 따라 청약철회/해지 권리를 원천 박탈하는 면책 약관은 강행규정 위반으로 무효(RED)입니다."
            })

    # 2. SPORTS (체육시설 약관) 정밀 검증
    if doc_type == "SPORTS":
        sports_cfg = rules_cfg.get("SPORTS", {})
        max_pct = sports_cfg.get("max_penalty_percent", 10)
        max_fee = sports_cfg.get("max_transfer_fee", 30000)
        sports_forbidden = sports_cfg.get("forbidden_keywords", [])
        
        # 기준 A: 위약금 10% 초과 여부
        if penalty_pcts and max(penalty_pcts) > max_pct:
            override_reasons.append({
                "clause": f"위약금/수수료 {max(penalty_pcts)}% 규정",
                "reason": f"소비자분쟁해결기준(체육시설업 고시)에 명시된 위약금 법수한도({max_pct}%)를 초과하는 {max(penalty_pcts)}%의 위약금을 규정하여 약관법 제8조에 따라 무효에 해당합니다."
            })
        
        # 기준 B: 양도 수수료 3만원 초과 여부
        if transfer_amounts and max(transfer_amounts) > max_fee:
            override_reasons.append({
                "clause": f"양도 수수료 {max(transfer_amounts):,}원 조항",
                "reason": f"회원권 양도 대행 및 명의변경 수수료가 합리적인 실비 기준(정액 {max_fee // 10000}만 원)을 초과하는 {max(transfer_amounts):,}원으로 명시되어 부당한 고객 불이익 조항(RED)에 해당합니다."
            })
            
        # 기준 C: SPORTS 개별 금지 키워드 체크
        for kw in sports_forbidden:
            if kw in raw_text:
                override_reasons.append({
                    "clause": f"체육시설 이용 제한 조항 ({kw})",
                    "reason": "소비자분쟁해결기준 및 약관법 제6조에 의거하여, 이용자에게 부당하게 불리한 이용 제한 및 중도해지 방해 조항에 해당하므로 무효(RED)입니다."
                })

    # 3. ECOMMERCE (전자상거래 약관) 정밀 검증
    elif doc_type == "ECOMMERCE":
        ecom_cfg = rules_cfg.get("ECOMMERCE", {})
        min_days = ecom_cfg.get("min_refund_days", 7)
        opening_restrictions = ecom_cfg.get("opening_restrictions", [])
        
        # 기준 A: 단순변심 환불 기간 7일 미만 제한
        if refund_days and min(refund_days) < min_days:
            override_reasons.append({
                "clause": f"청약철회 기간 {min(refund_days)}일 제한 조항",
                "reason": f"전자상거래법 제17조에 따른 법정 단순 변심 청약철회 보장 기간({min_days}일)을 무단으로 단축하는 {min(refund_days)}일 취소 제한 규정으로 무효(RED)입니다."
            })
            
        # 기준 B: 개봉 시 환불 불가 등 기만 조항
        if any(w in raw_text for w in opening_restrictions):
            override_reasons.append({
                "clause": "단순 포장 개봉 시 환불 불가 조항",
                "reason": "전자상거래법 제17조 제2항에 의거, 상품 가치가 완전히 멸실되지 않고 단순히 내용물 확인을 위해 포장을 개봉한 경우 청약철회가 가능하므로 위법한 면책 조항(RED)입니다."
            })

    # 4. AD_DIET (건강/뷰티 기만 광고) 정밀 검증
    elif doc_type == "AD_DIET":
        diet_cfg = rules_cfg.get("AD_DIET", {})
        fomo_words = diet_cfg.get("fomo_words", [])
        
        # 기준 A: 안전성/부작용 제로 확정적 기만 표현
        if any(w in raw_text for w in fomo_words):
            override_reasons.append({
                "clause": "부작용 없음 확정적 문구",
                "reason": "표시광고법 제3조 위반으로, 의학적/객관적 근거 없이 안전성을 100% 장담하여 소비자를 현혹하고, 고령층 및 건강 취약계층의 오인 및 과다 지출을 유도하며 잠재적 건강 위협을 은폐하는 대표적인 기만 광고 행위(RED)에 해당합니다."
            })

    # 5. AD_FOMO (쇼핑몰 마감 임박 광고 - 다크패턴) 정밀 검증
    elif doc_type == "AD_FOMO":
        fomo_cfg = rules_cfg.get("AD_FOMO", {})
        fomo_keywords = fomo_cfg.get("fomo_keywords", [])
        
        # 기준 A: 마감 압박 및 선착순 기만 표현 감지
        detected_words = [w for w in fomo_keywords if w in raw_text]
        if detected_words:
            override_reasons.append({
                "clause": f"마감 압박 및 선착순 기만 표현 감지 ({', '.join(detected_words)})",
                "reason": "전자상거래법 제21조 제1항 제1호(기만적 방법을 사용하여 소비자를 유인) 및 표시광고법 제3조에 의거하여, 합리적인 근거 없이 소비자의 불안이나 충동구매를 유도하는 마감 임박 및 선착순 기만 광고 조항(RED)에 해당합니다."
            })

    # 강제 보정 적용 및 설명 보강
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
                
        # 요약 설명 강제 보강 (기존 분석에 정량 교차 검증 적용 사유 추가)
        reasons_summary = ", ".join([f"'{r['clause']}'" for r in override_reasons])
        original_analysis = result.get("llm_analysis", "").strip()
        
        if not original_analysis or "위반 조항이 검출되지 않았습니다" in original_analysis:
            result["llm_analysis"] = (
                f"[정량 검증 위반 발견] 본 문서에서 명백한 법률 위반 기준({reasons_summary})이 감지되어 강제 RED 판정되었습니다. "
                f"자세한 위법성 여부는 아래에 탐지된 독소 조항과 상세 법적 근거를 확인해 주세요."
            )
        else:
            result["llm_analysis"] = (
                f"{original_analysis}\n\n[정량 교차 검증 적용 사유] 본 문서에서 명백한 법률 위반 기준({reasons_summary})이 감지되어 강제 RED 판정되었습니다."
            )

    return result
