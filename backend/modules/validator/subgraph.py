import time
from typing import List, Dict, Any, TypedDict
from langgraph.graph import StateGraph, END

# 각 에이전트 모듈의 오리지널 노드 기능 임포트
from .classifier import classifier_node as orig_classifier_node
from .auditor import rule_auditor_node as orig_rule_auditor_node
from .analysts import legal_analyst_node as orig_legal_analyst_node
from .supervisor import consensus_supervisor_node as orig_consensus_supervisor_node

class SubgraphState(TypedDict):
    raw_text: str
    input_type: str
    retrieved_docs: List[str]
    retrieved_ftc_docs: List[str]
    retrieved_kca_docs: List[str]
    classified_type: str
    audit_report: List[Dict[str, Any]]
    llm_analysis: str
    toxic_clauses: List[Dict[str, Any]]
    signal_color: str
    critique_feedback: str
    correction_count: int

# 노드 래퍼 함수들 정의 - 시간 계측 및 터미널 포맷 출력 기능 탑재
def classifier_node(state: SubgraphState) -> dict:
    start_time = time.time()
    
    print("\n┌────────────────────────────────────────────────────────┐")
    print("│ [Node] Classifier Agent - 문서 분류 시작")
    print("└────────────────────────────────────────────────────────┘")
    
    result = orig_classifier_node(state)
    elapsed = time.time() - start_time
    
    print("┌────────────────────────────────────────────────────────┐")
    print("│ [Node] Classifier Agent - 문서 분류 완료")
    print("├────────────────────────────────────────────────────────┤")
    print(f"│ 분류 결과: {result.get('classified_type')}")
    print(f"│ 소요 시간: {elapsed:.3f}초")
    print("└────────────────────────────────────────────────────────┘")
    return result

def rule_auditor_node(state: SubgraphState) -> dict:
    start_time = time.time()
    
    print("\n┌────────────────────────────────────────────────────────┐")
    print("│ [Node] Rule Auditor Agent - 정량적 규칙 검증 시작")
    print("└────────────────────────────────────────────────────────┘")
    
    result = orig_rule_auditor_node(state)
    elapsed = time.time() - start_time
    
    audit_report = result.get("audit_report", [])
    print("┌────────────────────────────────────────────────────────┐")
    print("│ [Node] Rule Auditor Agent - 정량 검증 완료")
    print("├────────────────────────────────────────────────────────┤")
    print(f"│ 검출된 위반 수: {len(audit_report)}건")
    for idx, item in enumerate(audit_report, 1):
        print(f"│   {idx}. 조항: {item['clause']}")
    print(f"│ 소요 시간: {elapsed:.3f}초")
    print("└────────────────────────────────────────────────────────┘")
    return result

def legal_analyst_node(state: SubgraphState) -> dict:
    start_time = time.time()
    
    print("\n┌────────────────────────────────────────────────────────┐")
    print(f"│ [Node] Legal Analyst Agent - 정성적 법률 분석 시작 (보정 횟수: {state.get('correction_count', 0)})")
    print("└────────────────────────────────────────────────────────┘")
    
    result = orig_legal_analyst_node(state)
    elapsed = time.time() - start_time
    
    print("┌────────────────────────────────────────────────────────┐")
    print("│ [Node] Legal Analyst Agent - 정성적 법률 분석 완료")
    print("├────────────────────────────────────────────────────────┤")
    print(f"│ 판정 등급: {result.get('signal_color')}")
    print(f"│ 분석 요약: {result.get('llm_analysis', '')[:30]}...")
    print(f"│ 소요 시간: {elapsed:.3f}초")
    print("└────────────────────────────────────────────────────────┘")
    return result

def consensus_supervisor_node(state: SubgraphState) -> dict:
    start_time = time.time()
    
    print("\n┌────────────────────────────────────────────────────────┐")
    print("│ [Node] Consensus Supervisor Agent - 합의 여부 검증 시작")
    print("└────────────────────────────────────────────────────────┘")
    
    result = orig_consensus_supervisor_node(state)
    elapsed = time.time() - start_time
    
    is_discrepancy = bool(result.get("critique_feedback"))
    final_grade = result.get("signal_color")
    
    print("┌────────────────────────────────────────────────────────┐")
    print("│ [Node] Consensus Supervisor Agent - 합의 조정 완료")
    print("├────────────────────────────────────────────────────────┤")
    print(f"│ 불일치 발생 여부: {is_discrepancy}")
    print(f"│ 현재 보정 횟수: {state.get('correction_count', 0)}회")
    print(f"│ 최종 안전 등급: {final_grade}")
    print(f"│ 소요 시간: {elapsed:.3f}초")
    print("└────────────────────────────────────────────────────────┘")
    return result

def route_after_supervisor(state: SubgraphState):
    if state.get("critique_feedback") and state.get("correction_count", 0) <= 1:
        return "analyst"
    return END

# 검증 서브그래프 워크플로우 정의
subgraph_workflow = StateGraph(SubgraphState)

# 노드 등록
subgraph_workflow.add_node("auditor", rule_auditor_node)
subgraph_workflow.add_node("analyst", legal_analyst_node)
subgraph_workflow.add_node("supervisor", consensus_supervisor_node)

# 순차 워크플로우 엣지 구성
subgraph_workflow.set_entry_point("auditor")
subgraph_workflow.add_edge("auditor", "analyst")
subgraph_workflow.add_edge("analyst", "supervisor")

# 자가 교정 조건부 분기 추가
subgraph_workflow.add_conditional_edges(
    "supervisor",
    route_after_supervisor,
    {
        "analyst": "analyst",
        END: END
    }
)

compiled_subgraph = subgraph_workflow.compile()

def validate_rules_node(state: dict) -> dict:
    """
    RAG 완료 후 메인 그래프에서 유입되어 문서 검증을 대행하는 서브그래프 통합 엔트리포인트 노드입니다.
    """
    print("[Node] 팀원 D - 멀티 에이전트 서브그래프 실행 중...")
    
    subgraph_input = {
        "raw_text": state.get("raw_text", ""),
        "input_type": state.get("input_type", "CONTRACT"),
        "retrieved_docs": state.get("retrieved_docs", []),
        "retrieved_ftc_docs": state.get("retrieved_ftc_docs", []),
        "retrieved_kca_docs": state.get("retrieved_kca_docs", []),
        "classified_type": state.get("classified_type", "OTHER"),
        "audit_report": [],
        "llm_analysis": "",
        "toxic_clauses": [],
        "signal_color": "GREEN",
        "critique_feedback": "",
        "correction_count": 0
    }
    
    final_state = compiled_subgraph.invoke(subgraph_input)
    
    return {
        "llm_analysis": final_state["llm_analysis"],
        "toxic_clauses": final_state["toxic_clauses"],
        "signal_color": final_state["signal_color"]
    }
