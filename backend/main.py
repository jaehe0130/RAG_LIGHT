from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph import StateGraph, END
import shutil
import os

from models import AgentState, AnalysisResponse
# 독립 파일로 분리된 팀원들의 함수를 탑재
from modules.ocr import run_ocr_node
from modules.rag_search import search_rag_node
from modules.rule_validator import validate_rules_node

app = FastAPI(title="찰칵! 소비자 공정 Guard 통합 API")

# React 앱과의 원활한 통신을 위한 CORS 허용 세팅
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🕸️ 팀원 A(나) 담당 노드: 기획서 기반 '원스톱 피해구제 신청서 작성 에이전트' 구현
def report_generation_node(state: AgentState) -> AgentState:
    print("[Node] 팀원 A - 원클릭 권리 구제 신고서 서식 초안 생성 중...")
    
    if state["signal_color"] == "RED":
        if state["input_type"] == "CONTRACT":
            draft = f"[한국소비자원 피해구제 신청서 초안]\n\n■ 피해 유형: 불공정 계약 및 과도한 위약금\n■ 탐지 조항: {state['toxic_clauses']}\n\n상기 약관은 불공정 약관 의결서 사례 및 소비자분쟁해결기준을 위반하여 과도한 위약금을 부과하므로 피해구제를 신청합니다."
        else:
            draft = f"[공정거래위원회 불공정거래 신고서 초안]\n\n■ 피해 유형: 전자상거래법 위반 및 부당 표시·광고\n■ 기만 행위: {state['toxic_clauses']}\n\n상기 광고 캡처본은 소비자를 기만하고 대국민 오인 가능성을 유발하는 허위·과장 행위에 해당하므로 신고합니다."
    else:
        draft = "안전 또는 주의 등급 약관으로 별도의 관공서 신고 서식이 필요하지 않습니다."
        
    return {"report_draft": draft}

# ocr.py의 인터페이스(image_path, doc_type) 불일치를 해결하기 위한 래퍼 노드
def ocr_node_wrapper(state: AgentState) -> dict:
    state_for_ocr = dict(state)
    state_for_ocr["image_path"] = state["file_path"]
    state_for_ocr["doc_type"] = state["input_type"]
    
    result = run_ocr_node(state_for_ocr)
    return {"raw_text": result.get("raw_text", "")}

# LangGraph 멀티에이전트 파이프라인 조립
workflow = StateGraph(AgentState)
workflow.add_node("ocr", ocr_node_wrapper)
workflow.add_node("rag", search_rag_node)
workflow.add_node("validate", validate_rules_node)
workflow.add_node("report", report_generation_node)

workflow.set_entry_point("ocr")
workflow.add_edge("ocr", "rag")
workflow.add_edge("rag", "validate")
workflow.add_edge("validate", "report")
workflow.add_edge("report", END)

compiled_graph = workflow.compile()


# 📱 팀원 B의 React 화면(약관 진단 탭 / 광고 탐지 탭)과 연동할 메인 API 라우터
@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_contract(
    file: UploadFile = File(...),
    input_type: str = Form(...) # 프론트에서 "terms" 혹은 "ad" 문자열을 넘겨받음
):
    # 프론트엔드 파라미터를 백엔드 상수로 매핑
    backend_input_type = "CONTRACT" if input_type == "terms" else "AD"
    
    # 1. 수신된 약관/광고 문서 파일 저장
    os.makedirs("uploads", exist_ok=True)
    file_path = os.path.join("uploads", file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 2. 초기 상태 바구니 채우고 LangGraph 가동
    initial_state = {
        "file_path": file_path, "input_type": backend_input_type, "raw_text": "",
        "retrieved_ftc_docs": [], "retrieved_kca_docs": [],
        "llm_analysis": "", "toxic_clauses": [], "signal_color": "", "report_draft": ""
    }
    final_output = compiled_graph.invoke(initial_state)
    
    # 3. 기획서의 핵심 산출 지표인 '3색 신호등 결과'와 '유사 피해 통계'를 통합하여 반환
    industry = "민생 밀접 분야(체육시설/요가원 등)" if final_output["input_type"] == "CONTRACT" else "디지털 유통 및 전자상거래"
    return {
        "status": "success",
        "input_type": final_output["input_type"],
        "ocr_text": final_output["raw_text"],
        "analysis": {
            "signal_color": final_output["signal_color"],
            "main_warning": final_output["llm_analysis"],
            "toxic_clauses": final_output["toxic_clauses"]
        },
        "statistics": {
            "industry": industry,
            "dispute_rate": 24.6 if final_output["input_type"] == "CONTRACT" else 8.8, # 기획서 기반 실제 통계 하드코딩맵핑
            "similar_cases_count": 123 if final_output["input_type"] == "CONTRACT" else 44
        },
        "report_form": {
            "title": f"[자동완성] {industry} 피해 관련 구제 신청 문서 초안",
            "content": final_output["report_draft"]
        }
    }
