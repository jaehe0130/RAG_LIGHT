import os
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph import END, StateGraph

from models import AgentState, AnalysisResponse
from modules.ocr import extract_text, is_supported_upload, run_ocr_node
from modules.rag_search import search_rag_node
from modules.rule_validator import validate_rules_node


app = FastAPI(title="찰칵! 소비자 공정 Guard 통합 API")

# Allow the React frontend to call the FastAPI backend during local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def report_generation_node(state: AgentState) -> AgentState:
    """Create a simple report draft after OCR/RAG/rule validation."""
    print("[Node] report - generating draft")

    if state["signal_color"] == "RED":
        if state["input_type"] == "CONTRACT":
            draft = (
                "[한국소비자원 피해구제 신청서 초안]\n\n"
                "■ 피해 유형: 불공정 계약 및 과도한 위약금\n"
                f"■ 탐지 조항: {state['toxic_clauses']}\n\n"
                "상기 약관은 불공정 약관 의결서 사례 및 소비자분쟁해결기준을 "
                "위반하여 과도한 위약금을 부과하므로 피해구제를 신청합니다."
            )
        else:
            draft = (
                "[공정거래위원회 불공정거래 신고서 초안]\n\n"
                "■ 피해 유형: 전자상거래법 위반 및 부당 표시·광고\n"
                f"■ 기만 행위: {state['toxic_clauses']}\n\n"
                "상기 광고 캡처본은 소비자를 기만하고 대국민 오인 가능성을 "
                "유발하는 허위·과장 행위에 해당하므로 신고합니다."
            )
    else:
        draft = "안전 또는 주의 등급 약관으로 별도의 관공서 신고 서식이 필요하지 않습니다."

    return {"report_draft": draft}


def ocr_node_wrapper(state: AgentState) -> dict:
    """Bridge the OCR module result into the existing LangGraph state."""
    state_for_ocr = dict(state)
    state_for_ocr["image_path"] = state["file_path"]
    state_for_ocr["doc_type"] = state["input_type"]

    result = run_ocr_node(state_for_ocr)
    return {"raw_text": result.get("raw_text", "")}


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


def _save_upload_file(file: UploadFile) -> str:
    """Save an uploaded PDF/JPG/PNG into uploads/ using a safe temporary name."""
    os.makedirs("uploads", exist_ok=True)

    original_name = Path(file.filename or "upload").name
    suffix = Path(original_name).suffix.lower()
    safe_name = f"{uuid4().hex}{suffix}"
    file_path = os.path.join("uploads", safe_name)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path


def _validate_upload(file: UploadFile) -> None:
    if not is_supported_upload(file.filename or "", file.content_type):
        raise HTTPException(status_code=400, detail="Only PDF, JPG, and PNG files are supported.")


@app.post("/ocr")
async def ocr_upload(file: UploadFile = File(...)):
    """Upload a file and return only the OCR result JSON."""
    _validate_upload(file)
    file_path = _save_upload_file(file)
    return extract_text(file_path)


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_contract(
    file: UploadFile = File(...),
    input_type: str = Form(...),
):
    """Run the existing OCR -> RAG -> rule validation workflow."""
    _validate_upload(file)

    backend_input_type = "CONTRACT" if input_type == "terms" else "AD"
    file_path = _save_upload_file(file)

    initial_state = {
        "file_path": file_path,
        "input_type": backend_input_type,
        "raw_text": "",
        "retrieved_docs": [],
        "llm_analysis": "",
        "toxic_clauses": [],
        "signal_color": "",
        "report_draft": "",
    }
    final_output = compiled_graph.invoke(initial_state)

    industry = "민생 밀접 분야(체육시설/요가원 등)" if final_output["input_type"] == "CONTRACT" else "디지털 유통 및 전자상거래"
    reference_docs = final_output.get("retrieved_docs", [])

    return {
        "status": "success",
        "input_type": final_output["input_type"],
        "ocr_text": final_output["raw_text"],
        "analysis": {
            "signal_color": final_output["signal_color"],
            "main_warning": final_output["llm_analysis"],
            "toxic_clauses": final_output["toxic_clauses"],
        },
        "statistics": {
            "industry": industry,
            "dispute_rate": 24.6 if final_output["input_type"] == "CONTRACT" else 8.8,
            "similar_cases_count": len(reference_docs) if reference_docs else (123 if final_output["input_type"] == "CONTRACT" else 44),
        },
        "report_form": {
            "title": f"[자동완성] {industry} 피해 관련 구제 신청 문서 초안",
            "content": final_output["report_draft"],
        },
        "reference_cases": reference_docs,
    }
