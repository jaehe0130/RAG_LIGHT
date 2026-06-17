from .utils import call_llm, normalize_result_schema

class LegalAnalyst:
    def __init__(self, api_key: str = None):
        pass

    def get_specialized_system_prompt(self, classified_type: str) -> str:
        """
        문서 분류 유형에 대응하는 공정위 기준 전문 심사 가이드를 설정합니다.
        """
        base_instruction = (
            "당신은 대한민국 공정거래위원회 약관법, 소비자분쟁해결기준, 표시광고법, 전자상거래법에 정통한 소비자 권리 보호 전문 AI 변호사입니다.\n"
            "제공된 텍스트를 정밀 분석하고 불공정성 여부를 판단하여 반드시 아래 JSON 규격으로만 결과를 반환하세요.\n\n"
            "반드시 아래 스키마의 JSON 객체로만 응답하세요. 백틱(```)이나 마크다운 없이 순수 JSON만 반환해야 합니다:\n"
            "{\n"
            "  \"llm_analysis\": \"전체 약관/광고의 핵심 위법성 또는 문제점을 친근하고 명확하게 요약한 설명 (한국어)\",\n"
            "  \"toxic_clauses\": [\n"
            "    {\n"
            "      \"clause\": \"문제가 되는 조항의 일부 텍스트 또는 명칭 (예: '제5조 환불 불가 조항')\",\n"
            "      \"reason\": \"해당 조항이 왜 불공정하거나 위법한지에 대한 법적 근거가 포함된 구체적 이유\"\n"
            "    }\n"
            "  ],\n"
            "  \"signal_color\": \"RED\" | \"YELLOW\" | \"GREEN\"\n"
            "}\n\n"
        )

        if classified_type == "SPORTS":
            return base_instruction + (
                "## [스포츠 시설 약관 검토 기준]\n"
                "1. 위약금/취소수수료가 총 결제 금액의 10%를 초과하는지 확인하세요 (예: 위약금 20%, 30% 등). 10%를 초과하면 무조건 RED (약관법 제8조 및 고시 위반)\n"
                "2. 회원권 양도 및 명의변경 수수료가 실비 기준인 30,000원을 초과하는지 확인하세요. 30,000원을 초과하면 무조건 RED\n"
                "3. '환불 불가', '취소 불가' 등 해지 및 청약철회 권리를 원천 박탈하면 무조건 RED\n"
                "※ 약관 내에 여러 개의 독소 조항이 존재할 경우, 단 하나만 적지 말고 발견한 모든 조항을 `toxic_clauses` 리스트에 빠짐없이 기재하세요."
            )
        elif classified_type == "ECOMMERCE":
            return base_instruction + (
                "## [전자상거래 약관 검토 기준]\n"
                "1. 단순변심 청약철회/환불 가능 기간이 법정 보장 기한인 7일 미만으로 제한되어 있으면 무조건 RED (전자상거래법 제17조 위반)\n"
                "2. 상품 개봉, 박스 훼손, 비닐 제거만을 이유로 환불을 원천 차단하면 무조건 RED (상품 가치 멸실이 아닌 단순 확인용 개봉은 법적으로 환불 가능)\n"
                "3. '교환/환불 절대 불가' 조항이 있으면 무조건 RED\n"
                "※ 약관 내에 여러 개의 독소 조항이 존재할 경우, 단 하나만 적지 말고 발견한 모든 조항을 `toxic_clauses` 리스트에 빠짐없이 기재하세요."
            )
        elif classified_type == "AD_DIET":
            return base_instruction + (
                "## [건강/뷰티 기만 광고 검토 기준]\n"
                "1. '부작용 100% 없음', '부작용 전혀 없음', '부작용 제로' 등 객관적 의학적 근거가 없는 단정적 안전성 광고는 무조건 RED (표시광고법 제3조 위반)\n"
                "2. 단 한 건도 발생하지 않았다는 식의 임상 데이터 과장도 경고 사유입니다.\n"
                "※ 발견한 모든 기만 광고 문구를 `toxic_clauses` 리스트에 기재하고, 판정 색상(signal_color)을 RED로 지정해 주세요."
            )
        elif classified_type == "AD_FOMO":
            return base_instruction + (
                "## [쇼핑몰 마감 임박 및 선착순 광고 검토 기준]\n"
                "1. '오늘 단 하루', '선착순 10명', '마지막 기회' 등 합리적 근거 없이 소비자의 심리를 조작하여 충동구매를 유도하는 다크패턴 기만 광고는 YELLOW (주의)로 지정해 주세요 (계약 자체의 무효 사유는 아니지만, 소비자의 합리적 구매 의사결정을 왜곡하므로).\n"
                "※ 발견한 모든 마감 압박성 표현을 `toxic_clauses` 리스트에 기재하고, 판정 색상(signal_color)을 YELLOW로 지정해 주세요."
            )
        else:
            return base_instruction + (
                "## [기타 일반 약관/광고 검토 기준]\n"
                "1. 소비자에게 일방적으로 부당하거나 불리한 조항(과도한 위약금, 면책 조항, 청약철회 박탈 등)이 있는지 정밀하게 확인하십시오.\n"
                "2. 위반 수준에 따라 RED(심각한 법률 위반), YELLOW(주의 필요), GREEN(안전) 중 하나로 판정하십시오."
            )

    def analyze(self, raw_text: str, classified_type: str, context_str: str, feedback: str = "", previous_analysis: dict = None) -> dict:
        """
        지정된 문서 유형 가이드를 적용하여 LLM 정성 분석을 요청합니다.
        자가 보정 피드백 유입 시 3-turn multi-turn 모드로 응답을 유도합니다.
        """
        system_prompt = self.get_specialized_system_prompt(classified_type)
        
        user_prompt = f"분류 타입: {classified_type}\n\n분석할 약관/광고 텍스트:\n{raw_text}\n"
        if context_str:
            user_prompt += f"\n\n--- RAG 검색 참조 유사 사례 ---\n{context_str}\n"
            user_prompt += "참조 사례에 기재된 공정위 및 소비자원의 위법 판단 논리를 적극 참고하세요."

        feedback_prompt = None
        if feedback:
            feedback_prompt = f"[이전 분석 결과에 대한 수정 피드백]\n{feedback}\n위 피드백 사항을 반드시 반영하여 판정 및 독소조항을 재보정하세요."

        if feedback_prompt:
            import json
            # 이전 분석 결과가 존재할 경우 실제 이전 응답을 assistant_message로 바인딩하여 문맥 상실을 예방
            if previous_analysis:
                assistant_message = json.dumps({
                    "llm_analysis": previous_analysis.get("llm_analysis", ""),
                    "toxic_clauses": previous_analysis.get("toxic_clauses", []),
                    "signal_color": previous_analysis.get("signal_color", "GREEN")
                }, ensure_ascii=False)
            else:
                assistant_message = '{"llm_analysis": "1차 분석 완료", "toxic_clauses": [], "signal_color": "GREEN"}'
                
            result = call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                assistant_message=assistant_message,
                feedback_prompt=feedback_prompt
            )
        else:
            result = call_llm(system_prompt=system_prompt, user_prompt=user_prompt)

        if result:
            result = normalize_result_schema(result)
            result["classified_type"] = classified_type
            return result

        return {
            "llm_analysis": "API 호출 실패로 인한 Fallback 분석입니다.",
            "toxic_clauses": [],
            "signal_color": "GREEN"
        }

def legal_analyst_node(state: dict) -> dict:
    """
    LangGraph 서브그래프의 도메인 특화 법률 분석 노드
    """
    print(f"[SubgraphNode] Legal Analyst Agent - 정성적 법률 분석 시작 (보정 횟수: {state.get('correction_count', 0)})")
    analyst = LegalAnalyst()
    
    retrieved_ftc = state.get("retrieved_ftc_docs", [])
    retrieved_kca = state.get("retrieved_kca_docs", [])
    retrieved_docs = state.get("retrieved_docs", [])
    
    context_str = ""
    if retrieved_ftc:
        context_str += "\n[참고 공정거래위원회 심결례 (의결서)]\n"
        for i, doc in enumerate(retrieved_ftc[:2], 1):
            context_str += f"사례 {i}:\n{doc}\n\n"
    if retrieved_kca:
        context_str += "\n[참고 한국소비자원 분쟁조정/피해구제 사례]\n"
        for i, doc in enumerate(retrieved_kca[:2], 1):
            context_str += f"사례 {i}:\n{doc}\n\n"
    if retrieved_docs and not context_str:
        context_str += "\n[참고 유사 사례]\n"
        for i, doc in enumerate(retrieved_docs[:2], 1):
            context_str += f"사례 {i}:\n{doc}\n\n"

    # 자가 보정 시 활용할 실제 이전 정성 분석 결과 준비
    previous_analysis = None
    if state.get("critique_feedback"):
        previous_analysis = {
            "llm_analysis": state.get("llm_analysis", ""),
            "toxic_clauses": state.get("toxic_clauses", []),
            "signal_color": state.get("signal_color", "GREEN")
        }

    result = analyst.analyze(
        raw_text=state["raw_text"],
        classified_type=state["classified_type"],
        context_str=context_str,
        feedback=state.get("critique_feedback", ""),
        previous_analysis=previous_analysis
    )
    
    return {
        "llm_analysis": result.get("llm_analysis", ""),
        "toxic_clauses": result.get("toxic_clauses", []),
        "signal_color": result.get("signal_color", "GREEN")
    }
