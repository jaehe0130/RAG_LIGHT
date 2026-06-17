import re
from .utils import get_api_key, get_embedding, cosine_similarity

def is_clause_matched(llm_clause: dict, override_item: dict) -> bool:
    """
    LLM이 분석한 독소 조항과 정량 검증기(Auditor)가 검출한 위반 항목이 동일한지 판단합니다.
    1. 단순 부분곱/서브스트링 매칭
    2. 조항 내 핵심 수치(예: 20%, 50,000원 등) 대조
    3. 환불/취소 불가성 키워드 매칭
    """
    c_name = str(llm_clause.get("clause", "")).lower()
    c_reason = str(llm_clause.get("reason", "")).lower()
    
    o_name = str(override_item.get("clause", "")).lower()
    
    # 1. 서브스트링 매칭 (기본 필터)
    match_in_paren = re.search(r'\(([^)]+)\)', o_name)
    raw_match = match_in_paren.group(1) if match_in_paren else o_name
    
    raw_match_clean = re.sub(r'\s+', '', raw_match)
    c_name_clean = re.sub(r'\s+', '', c_name)
    c_reason_clean = re.sub(r'\s+', '', c_reason)
    
    if (raw_match_clean in c_name_clean) or (c_name_clean in raw_match_clean) or (raw_match_clean in c_reason_clean):
        return True
        
    # 2. 수치 데이터 매칭 (예: 20 -> 20%, 50000 -> 50,000원 또는 5만)
    o_numbers = re.findall(r'\d+', o_name.replace(",", ""))
    if o_numbers:
        c_text_clean = (c_name + " " + c_reason).replace(",", "")
        matches_all = True
        for num in o_numbers:
            num_val = int(num)
            # 만 단위 한글 변환 대응 (예: 50000 -> 5만)
            if num_val >= 10000 and num_val % 10000 == 0:
                korean_man = f"{num_val // 10000}만"
                if num not in c_text_clean and korean_man not in c_text_clean:
                    matches_all = False
                    break
            else:
                if num not in c_text_clean:
                    matches_all = False
                    break
        if matches_all:
            return True
            
    # 3. 환불/취소 절대 불가 키워드 매칭
    if any(w in o_name for w in ("환불", "취소", "반품")):
        if any(w in o_name for w in ("불가", "금지", "제한")):
            if any(w in c_name_clean or w in c_reason_clean for w in ("환불", "취소", "반품", "교환")):
                if any(w in c_name_clean or w in c_reason_clean for w in ("불가", "금지", "제한", "어렵", "안됨")):
                    return True
                    
    # 4. 임베딩 기반 코사인 유사도 판단 (최종 폴백)
    o_text = override_item.get("clause", "")
    c_text = f"{llm_clause.get('clause', '')} {llm_clause.get('reason', '')}"
    if o_text and c_text:
        emb_o = get_embedding(o_text)
        emb_c = get_embedding(c_text)
        if emb_o and emb_c:
            sim = cosine_similarity(emb_o, emb_c)
            # 유사도 0.70 이상이면 동일한 조항으로 매칭 처리
            if sim >= 0.70:
                return True
                    
    return False

def check_discrepancy(result: dict, override_reasons: list) -> bool:
    """
    정성적 LLM 검출 결과와 정량적 Rule 검출 엔진의 결과물 간 모순 여부를 판단합니다.
    """
    if not override_reasons:
        return False
    
    # 1. 만약 검출된 정량 규칙 중 RED severity가 존재하는데, 최종 판정이 RED가 아니라면 모순입니다.
    has_red = any(r.get("severity", "RED") == "RED" for r in override_reasons)
    if has_red and result.get("signal_color") != "RED":
        return True
        
    # 2. 만약 검출된 정량 규칙에 YELLOW severity가 존재하는데, 최종 판정이 GREEN이라면 모순입니다 (YELLOW나 RED여야 함).
    has_yellow = any(r.get("severity", "RED") == "YELLOW" for r in override_reasons)
    if has_yellow and result.get("signal_color") == "GREEN":
        return True
        
    # 3. 또한 정량 검증기에서 잡은 위반 조항들이 LLM의 toxic_clauses에 정상 매핑되어 있는지 확인합니다.
    llm_clauses = result.get("toxic_clauses", [])
    for item in override_reasons:
        found = False
        for c in llm_clauses:
            if is_clause_matched(c, item):
                found = True
                break
        if not found:
            return True
            
    return False

def consensus_supervisor_node(state: dict) -> dict:
    """
    정성/정량 분석 결과의 합의를 감시하고, 모순 발견 시 1차 자가 피드백 루프를 작동시킵니다.
    최종 상태에서도 정합이 맞지 않을 경우, 정량 룰을 강제 적용하는 오버라이드(Safety Override)를 행사합니다.
    """
    print("[SubgraphNode] Consensus Supervisor Agent - 합의 여부 검증 시작")
    audit_report = state.get("audit_report", [])
    api_key = get_api_key()
    
    temp_result = {
        "signal_color": state.get("signal_color", "GREEN"),
        "toxic_clauses": state.get("toxic_clauses", []),
        "llm_analysis": state.get("llm_analysis", "")
    }
    
    discrepancy = check_discrepancy(temp_result, audit_report)
    correction_count = state.get("correction_count", 0)
    
    if discrepancy and correction_count < 1 and api_key:
        critique_items = []
        for item in audit_report:
            critique_items.append(f"- 위반 조항: {item['clause']}\n  이유: {item['reason']} (등급: {item.get('severity', 'RED')})")
        
        has_red = any(r.get("severity", "RED") == "RED" for r in audit_report)
        target_color = "RED" if has_red else "YELLOW"
        
        feedback_message = (
            "정량 검증기에서 다음 위반 사항이 탐지되었습니다. 이전 분석 결과에 이 항목들이 누락되었거나 판정이 잘못되었습니다.\n\n"
            + "\n".join(critique_items)
            + f"\n\n이 피드백을 반영하여 반드시 signal_color를 {target_color}로 보정하고, 해당 독소 조항을 toxic_clauses에 추가하여 다시 제출해 주세요."
        )
        print(f"  └─ [조정] 1차 분석과 정량 검증 결과 불일치. 피드백 루프 작동 (보정 횟수: {correction_count + 1})")
        return {
            "critique_feedback": feedback_message,
            "correction_count": correction_count + 1
        }
    
    final_override_reasons = state.get("audit_report", [])
    final_result = {
        "signal_color": state.get("signal_color", "GREEN"),
        "toxic_clauses": list(state.get("toxic_clauses", [])),
        "llm_analysis": state.get("llm_analysis", ""),
        "classified_type": state.get("classified_type", "OTHER")
    }
    
    apply_fallback_override = False
    if final_override_reasons:
        has_red = any(r.get("severity", "RED") == "RED" for r in final_override_reasons)
        if has_red:
            # RED 규칙이 존재하는데 최종 판정이 RED가 아니면 오버라이드 대상
            if final_result["signal_color"] != "RED":
                apply_fallback_override = True
        else:
            # YELLOW 규칙만 존재하는데 최종 판정이 GREEN이면 오버라이드 대상 (YELLOW로 상향 필요)
            if final_result["signal_color"] == "GREEN":
                apply_fallback_override = True
                
        # 매핑 검사 추가
        if not apply_fallback_override:
            llm_clauses = final_result.get("toxic_clauses", [])
            for item in final_override_reasons:
                found = False
                for c in llm_clauses:
                    if is_clause_matched(c, item):
                        found = True
                        break
                if not found:
                    apply_fallback_override = True
                    break

    if apply_fallback_override and final_override_reasons:
        print("  └─ [조정] 최종 안전장치 작동: 미반영된 정량적 규칙 위반 사항을 결과에 강제 주입합니다.")
        has_red = any(r.get("severity", "RED") == "RED" for r in final_override_reasons)
        
        if has_red:
            final_result["signal_color"] = "RED"
        else:
            # RED가 없고 YELLOW만 존재할 때, LLM의 기존 판정이 RED가 아니었다면 YELLOW로 오버라이드
            if final_result["signal_color"] != "RED":
                final_result["signal_color"] = "YELLOW"
        
        for reason_item in final_override_reasons:
            exists = False
            for c in final_result["toxic_clauses"]:
                if is_clause_matched(c, reason_item):
                    exists = True
                    break
            if not exists:
                final_result["toxic_clauses"].append({
                    "clause": reason_item["clause"],
                    "reason": reason_item["reason"]
                })
                
        reasons_summary = ", ".join([f"'{r['clause']}'" for r in final_override_reasons])
        original_analysis = final_result.get("llm_analysis", "").strip()
        
        color_desc = "위험(RED)" if has_red else "주의(YELLOW)"
        if not original_analysis or "위반 조항이 검출되지 않았습니다" in original_analysis:
            final_result["llm_analysis"] = (
                f"[정량 검증 위반 발견] 본 문서에서 명백한 법률 위반 기준({reasons_summary})이 감지되어 강제 {color_desc} 판정되었습니다. "
                f"자세한 위법성 여부는 아래에 탐지된 독소 조항과 상세 법적 근거를 확인해 주세요."
            )
        else:
            if reasons_summary not in original_analysis:
                final_result["llm_analysis"] = (
                    f"{original_analysis}\n\n(정량 검증 위반 탐지: {reasons_summary})"
                )

    print(f"  └─ 합의/조정 완료. 최종 등급: {final_result['signal_color']}")
    return {
        "signal_color": final_result["signal_color"],
        "toxic_clauses": final_result["toxic_clauses"],
        "llm_analysis": final_result["llm_analysis"],
        "classified_type": final_result["classified_type"],
        "critique_feedback": ""
    }
