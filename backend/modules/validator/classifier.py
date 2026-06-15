from .utils import call_llm_text

class ClassifierAgent:
    def classify(self, raw_text: str, input_type: str) -> str:
        """
        입력 문서의 카테고리(SPORTS, ECOMMERCE, AD_DIET, AD_FOMO, OTHER)를 판단합니다.
        LLM 호출이 불가능하거나 지연될 경우 정규 표현식 기반 로컬 룰에 의한 Fallback 분류를 적용합니다.
        """
        system_prompt = (
            "당신은 소비자가 업로드한 약관 이미지나 온라인 광고 문구를 분석하기 전, 문서의 카테고리를 분류하는 분류 에이전트입니다.\n"
            "제공된 텍스트를 정밀 분석하여 반드시 다음 5가지 카테고리 중 하나로만 분류하여 대문자 단어로 응답하세요. 설명이나 다른 텍스트는 절대 포함하지 마십시오.\n\n"
            "- SPORTS: 체육시설 약관 (헬스장, 요가, 필라테스, 골프 등)\n"
            "- ECOMMERCE: 전자상거래 약관 (인터넷 쇼핑몰, 인터넷 강의 패키지, 구매 대행 등)\n"
            "- AD_DIET: 건강/뷰티 광고 (다이어트 보조제, 화장품, 식품 등)\n"
            "- AD_FOMO: 쇼핑몰 마감 임박 광고 (선착순, 오늘만 혜택, 카운트다운 타이머 등 다크패턴 광고)\n"
            "- OTHER: 기타 일반 약관/광고"
        )
        user_prompt = f"입력 타입: {input_type}\n분석할 텍스트:\n{raw_text}"
        
        # 1차 시도: LLM 기반 카테고리 분류
        classified = call_llm_text(system_prompt, user_prompt)
        
        if classified:
            classified = classified.upper().strip()
            for val in ("SPORTS", "ECOMMERCE", "AD_DIET", "AD_FOMO", "OTHER"):
                if val in classified:
                    return val

        # 2차 시도 (Fallback): 주요 키워드 매칭 기반 로컬 분류
        lower_text = raw_text.lower()
        if input_type == "CONTRACT":
            if any(w in lower_text for w in ("헬스", "요가", "필라테스", "체육", "회원권", "스포츠", "피트니스", "수영")):
                return "SPORTS"
            if any(w in lower_text for w in ("쇼핑몰", "배송", "상품", "구매", "결제", "인강", "수강", "환불", "반품")):
                return "ECOMMERCE"
        else:
            if any(w in lower_text for w in ("다이어트", "부작용", "효능", "보조제", "화장품", "체중", "감량", "피부")):
                return "AD_DIET"
            if any(w in lower_text for w in ("마감", "선착순", "오늘만", "타이머", "마지막", "남은")):
                return "AD_FOMO"

        return "OTHER"

def classifier_node(state: dict) -> dict:
    """
    LangGraph 서브그래프의 진입분류 노드
    """
    print("[SubgraphNode] Classifier Agent - 문서 분류 시작")
    classifier = ClassifierAgent()
    classified_type = classifier.classify(state["raw_text"], state["input_type"])
    print(f"  └─ 분류 결과: {classified_type}")
    return {"classified_type": classified_type}
