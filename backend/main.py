import os
import shutil
from pathlib import Path
import time
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph import END, StateGraph

from models import AgentState, AnalysisResponse, ChatRequest, ChatResponse
from modules.ocr import extract_text, is_supported_upload, run_ocr_node
from modules.rag_search import search_rag_node
from modules.rule_validator import validate_rules_node, classifier_node
from modules.chat_agent import generate_chat_response, call_chat_llm
from modules.templates import FORM_TEMPLATES


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
    """Create a report draft using LLM and official FTC templates."""
    print("\n[Node] Report Generation - LLM 동적 초안 작성 시작")
    t0 = time.time()

    if state["signal_color"] == "RED":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your_openai_api_key_here":
            draft = "[공정거래위원회 불공정거래 신고서 초안]\nAPI 키가 없어 자동 작성이 불가능합니다."
        else:
            system_prompt = (
                "당신은 공정거래위원회 및 한국소비자원 신고서를 전문적으로 대리 작성하는 법률 AI 변호사입니다.\n"
                "사용자가 업로드한 문서의 원문과 추출된 독소 조항을 분석하여, 아래 제공된 공정위/소비자원 법정 양식 중 가장 적절한 양식 1개를 선택하세요.\n"
                "그리고 선택된 양식의 빈칸(신고인, 피신고인, 위반사실, 청구취지 및 원인 등)을 추출된 문서 내용에 맞게 최대한 채워 완성된 초안을 작성해 주세요.\n\n"
                "**[제공된 양식 목록 및 본문]**\n"
            )
            for form_name, form_text in FORM_TEMPLATES.items():
                system_prompt += f"--- {form_name} ---\n{form_text}\n\n"
                
            system_prompt += (
                "**[작성 규칙]**\n"
                "1. 가장 적합한 양식 1개만 선택하여 제목으로 적어주세요.\n"
                "2. 선택한 양식의 목차와 틀을 그대로 유지하며 내용을 채워주세요.\n"
                "3. 이름, 날짜, 주소 등 문서 원문에서 확인할 수 없는 정보는 '[직접 기재]'로 남겨두세요.\n"
                "4. 위반 사실과 청구 취지 항목은 추출된 독소 조항과 약관 내용을 바탕으로 논리정연하고 전문적인 법률 용어로 작성하세요.\n"
                "5. 마크다운으로 깔끔하게 포맷팅하여 응답하세요.\n"
            )

            user_prompt = f"[문서 원문]\n{state.get('raw_text', '')}\n\n[발견된 독소 조항 및 위반 사유]\n{state.get('toxic_clauses', [])}"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            draft = call_chat_llm(api_key, messages)
            if not draft:
                draft = "[오류] 초안 생성에 실패했습니다."
    else:
        draft = "안전 또는 주의 등급 문서로 별도의 관공서 신고 서식이 필요하지 않습니다."

    print(f"[Timer ⏱️] Report LLM 작성 소요 시간: {time.time() - t0:.2f}초")
    return {"report_draft": draft}


def ocr_node_wrapper(state: AgentState) -> dict:
    """Bridge the OCR module result into the existing LangGraph state."""
    print("\n[Node] OCR - 이미지 텍스트 추출 시작")
    t0 = time.time()
    state_for_ocr = dict(state)
    state_for_ocr["image_path"] = state["file_path"]
    state_for_ocr["doc_type"] = state["input_type"]

    result = run_ocr_node(state_for_ocr)
    print(f"[Timer ⏱️] OCR 추출 소요 시간: {time.time() - t0:.2f}초")
    return {"raw_text": result.get("raw_text", "")}


workflow = StateGraph(AgentState)
workflow.add_node("ocr", ocr_node_wrapper)
workflow.add_node("rag", search_rag_node)
workflow.add_node("classifier", classifier_node)
workflow.add_node("validate", validate_rules_node)
workflow.add_node("report", report_generation_node)

workflow.set_entry_point("ocr")
workflow.add_edge("ocr", "rag")
workflow.add_edge("ocr", "classifier")
workflow.add_edge("rag", "validate")
workflow.add_edge("classifier", "validate")
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
        "classified_type": "",
    }
    print("\n" + "="*50)
    print("[Pipeline Start] 분석 파이프라인 시작...")
    pipeline_t0 = time.time()
    
    final_output = await compiled_graph.ainvoke(initial_state)

    print(f"\n[Pipeline End] ✨ 전체 분석 파이프라인 총 소요 시간: {time.time() - pipeline_t0:.2f}초")
    print("="*50 + "\n")

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

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """
    문서분석도우미 챗봇 API
    프론트엔드에서 보낸 쿼리와 이전 대화 기록을 받아 응답을 반환합니다.
    """
    # Pydantic 모델(ChatMessage) 리스트를 딕셔너리 리스트로 변환
    history_dicts = [{"role": msg.role, "content": msg.content} for msg in req.history]
    
    # 챗봇 두뇌(chat_agent) 호출
    answer = generate_chat_response(
        query=req.query, 
        chat_history=history_dicts, 
        retrieved_context=req.context
    )
    
    return ChatResponse(response=answer)

