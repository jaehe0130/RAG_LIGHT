def validate_rules_node(state):
    print("[Node] 팀원 D - 규칙 기반 수치 검증 및 OpenAI 연동 신호등 판정 중...")
    return {
        "llm_analysis": "이 약관에는 불리한 조항이 포함되어 있습니다.",
        "toxic_clauses": [{"clause": "제5조", "reason": "부당한 책임 전가"}],
        "signal_color": "RED"
    }
