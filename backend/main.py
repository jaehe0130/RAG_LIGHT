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
from modules.rule_validator import validate_rules_node
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
workflow.add_node("validate", validate_rules_node)
workflow.add_node("report", report_generation_node)

workflow.set_entry_point("ocr")
workflow.add_edge("ocr", "rag")
workflow.add_edge("rag", "validate")
workflow.add_edge("validate", "report")
workflow.add_edge("report", END)

compiled_graph = workflow.compile()

analysis_workflow = StateGraph(AgentState)
analysis_workflow.add_node("rag", search_rag_node)
analysis_workflow.add_node("validate", validate_rules_node)
analysis_workflow.add_node("report", report_generation_node)
analysis_workflow.set_entry_point("rag")
analysis_workflow.add_edge("rag", "validate")
analysis_workflow.add_edge("validate", "report")
analysis_workflow.add_edge("report", END)

compiled_analysis_graph = analysis_workflow.compile()

FORM_RECOMMENDATIONS = {
    "unfair_contract_terms": {
        "keywords": ("환불 불가", "환불불가", "과도한 위약금", "위약금", "계약 해지", "해지 제한", "중도 해지", "면책", "책임지지"),
        "forms": [
            {
                "title": "불공정약관 심사청구서",
                "description": "환불 불가, 과도한 위약금, 계약 해지 제한처럼 소비자에게 불리한 약관 조항을 심사 요청할 때 사용합니다.",
                "file": "/forms/form8.pdf",
                "reason": "분석 결과에 불공정 약관 또는 소비자에게 불리한 계약 조항이 포함되어 있습니다.",
            },
            {
                "title": "불공정거래행위 신고서",
                "description": "거래 조건이 소비자에게 일방적으로 불리하거나 사업자의 부당한 거래 조건이 의심될 때 참고합니다.",
                "file": "/forms/form5.pdf",
                "reason": "약관 조항 외에도 일반적인 불공정 거래 조건으로 다툴 여지가 있습니다.",
            },
        ],
    },
    "false_or_exaggerated_advertising": {
        "keywords": ("허위 광고", "과장 광고", "효과 보장", "효능", "보장", "광고", "기만", "중요한 조건", "표시"),
        "forms": [
            {
                "title": "표시·광고법 위반 신고서",
                "description": "허위·과장 광고, 효과 보장 표현, 중요한 조건 누락 등 광고 문구가 문제될 때 사용합니다.",
                "file": "/forms/form6.pdf",
                "reason": "광고 문구의 허위·과장 또는 기만 가능성이 분석되었습니다.",
            },
            {
                "title": "전자상거래법 위반 신고서",
                "description": "온라인 판매 광고와 구매 조건 고지가 함께 문제될 때 참고할 수 있습니다.",
                "file": "/forms/form9.pdf",
                "reason": "광고가 온라인 구매 조건과 연결되어 있을 가능성이 있습니다.",
            },
        ],
    },
    "door_to_door_sales": {
        "keywords": ("방문판매", "전화권유판매", "전화권유", "청약철회 제한", "청약 철회 제한", "청약철회", "계속거래"),
        "forms": [
            {
                "title": "방문판매법 위반 신고서",
                "description": "방문판매, 전화권유판매, 청약철회 제한 등 특수판매 관련 피해를 신고할 때 사용합니다.",
                "file": "/forms/form7.pdf",
                "reason": "방문판매·전화권유판매 또는 청약철회 제한과 관련된 표현이 확인되었습니다.",
            },
            {
                "title": "불공정약관 심사청구서",
                "description": "청약철회나 해지를 제한하는 약관 조항이 함께 있을 때 참고합니다.",
                "file": "/forms/form8.pdf",
                "reason": "계약 해지·철회 제한 조항이 약관 문제로도 이어질 수 있습니다.",
            },
        ],
    },
    "installment_transaction": {
        "keywords": ("할부거래", "할부", "선불식 할부", "선불식", "중도해지 제한", "중도 해지 제한", "장기 결제"),
        "forms": [
            {
                "title": "할부거래법 위반 신고서",
                "description": "할부 계약, 선불식 할부, 중도해지 제한 등 할부거래 관련 분쟁에 사용합니다.",
                "file": "/forms/form10.pdf",
                "reason": "할부거래 또는 선불식 결제·중도해지 제한과 관련된 위험이 감지되었습니다.",
            },
            {
                "title": "불공정약관 심사청구서",
                "description": "중도해지 제한이나 위약금 조항이 약관으로 포함되어 있을 때 함께 검토합니다.",
                "file": "/forms/form8.pdf",
                "reason": "해지 제한 조항이 불공정 약관 문제로도 볼 수 있습니다.",
            },
        ],
    },
    "ecommerce_consumer_protection": {
        "keywords": ("전자상거래", "온라인 쇼핑몰", "온라인", "쇼핑몰", "배송", "반품", "환불 제한", "고지 미흡", "청약철회"),
        "forms": [
            {
                "title": "전자상거래법 위반 신고서",
                "description": "온라인 쇼핑몰 환불 제한, 배송·반품 고지 미흡, 청약철회 제한 등에 사용합니다.",
                "file": "/forms/form9.pdf",
                "reason": "전자상거래에서 환불·배송·반품 고지가 문제될 수 있습니다.",
            },
            {
                "title": "표시·광고법 위반 신고서",
                "description": "온라인 상품 설명이나 광고 표시가 소비자를 오인하게 할 때 참고합니다.",
                "file": "/forms/form6.pdf",
                "reason": "온라인 표시·광고 내용도 함께 문제될 가능성이 있습니다.",
            },
        ],
    },
    "unfair_trade_practice": {
        "keywords": ("불공정 거래", "불공정거래", "거래 조건", "거래상 지위", "부당", "강제", "차별", "일방적"),
        "forms": [
            {
                "title": "불공정거래행위 신고서",
                "description": "일반적인 불공정 거래 조건, 거래상 지위 남용, 부당한 거래 강제 등이 의심될 때 사용합니다.",
                "file": "/forms/form5.pdf",
                "reason": "일반적인 불공정 거래 조건으로 볼 수 있는 내용이 포함되어 있습니다.",
            },
            {
                "title": "불공정약관 심사청구서",
                "description": "불리한 거래 조건이 약관 조항 형태로 제시된 경우 함께 검토할 수 있습니다.",
                "file": "/forms/form8.pdf",
                "reason": "문제가 되는 거래 조건이 약관 조항으로 작동할 수 있습니다.",
            },
        ],
    },
}

DEFAULT_RECOMMENDED_FORMS = [
    {
        "title": "공정거래위원회 신고서",
        "description": "위반 유형을 특정하기 어려울 때 공정거래위원회 신고 절차를 검토할 수 있는 기본 양식입니다.",
        "file": "/forms/form5.pdf",
        "reason": "명확한 추천 양식이 없어서 일반 불공정거래 신고 양식을 기본값으로 제안합니다.",
    }
]


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


def _combine_input_text(ocr_text: str, user_text: str) -> str:
    parts = []
    if ocr_text.strip():
        parts.append(ocr_text.strip())
    if user_text.strip():
        parts.append(user_text.strip())
    return "\n\n--- 직접 입력 텍스트 ---\n\n".join(parts)


def _resolve_input_type(raw_text: str, input_type: str | None = None) -> str:
    if input_type == "terms":
        return "CONTRACT"
    if input_type == "ad":
        return "AD"

    contract_keywords = ("약관", "계약", "환불", "위약금", "해지", "청약철회", "취소", "손해배상", "책임")
    ad_keywords = ("광고", "선착순", "오늘만", "마감", "할인", "효능", "다이어트", "화장품", "감량", "이벤트", "한정")
    contract_score = sum(1 for keyword in contract_keywords if keyword in raw_text)
    ad_score = sum(1 for keyword in ad_keywords if keyword in raw_text)
    return "AD" if ad_score > contract_score else "CONTRACT"


def _detect_violation_type(final_output: dict) -> str:
    text_parts = [
        final_output.get("raw_text", ""),
        final_output.get("llm_analysis", ""),
        final_output.get("report_draft", ""),
        str(final_output.get("toxic_clauses", [])),
    ]
    haystack = " ".join(part for part in text_parts if part)

    best_type = ""
    best_score = 0
    for violation_type, config in FORM_RECOMMENDATIONS.items():
        score = sum(1 for keyword in config["keywords"] if keyword in haystack)
        if score > best_score:
            best_type = violation_type
            best_score = score

    return best_type or "general_guidance"


def _recommended_forms_for_violation(violation_type: str) -> list[dict]:
    return FORM_RECOMMENDATIONS.get(violation_type, {}).get("forms", DEFAULT_RECOMMENDED_FORMS)


@app.post("/ocr")
async def ocr_upload(file: UploadFile = File(...)):
    """Upload a file and return only the OCR result JSON."""
    _validate_upload(file)
    file_path = _save_upload_file(file)
    return extract_text(file_path)


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_contract(
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    input_type: str | None = Form(None),
):
    """Run OCR when needed, then analyze file text and/or direct text."""
    user_text = (text or "").strip()
    if file is None and not user_text:
        raise HTTPException(status_code=400, detail="파일 또는 텍스트를 입력해주세요.")

    ocr_text = ""
    file_path = ""
    if file is not None:
        _validate_upload(file)
        file_path = _save_upload_file(file)
        ocr_result = extract_text(file_path)
        ocr_text = ocr_result.get("text", "")

    raw_text = _combine_input_text(ocr_text, user_text)
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="파일 또는 텍스트를 입력해주세요.")

    backend_input_type = _resolve_input_type(raw_text, input_type)

    initial_state = {
        "file_path": file_path,
        "input_type": backend_input_type,
        "raw_text": raw_text,
        "retrieved_docs": [],
        "llm_analysis": "",
        "toxic_clauses": [],
        "signal_color": "",
        "report_draft": "",
    }
    print("\n" + "="*50)
    print("[Pipeline Start] 분석 파이프라인 시작...")
    pipeline_t0 = time.time()
    
    final_output = compiled_analysis_graph.invoke(initial_state)

    print(f"\n[Pipeline End] ✨ 전체 분석 파이프라인 총 소요 시간: {time.time() - pipeline_t0:.2f}초")
    print("="*50 + "\n")

    industry = "민생 밀접 분야(체육시설/요가원 등)" if final_output["input_type"] == "CONTRACT" else "디지털 유통 및 전자상거래"
    reference_docs = final_output.get("retrieved_docs", [])
    violation_type = _detect_violation_type(final_output)
    recommended_forms = _recommended_forms_for_violation(violation_type)

    return {
        "status": "success",
        "input_type": final_output["input_type"],
        "ocr_text": final_output["raw_text"],
        "analysis": {
            "signal_color": final_output["signal_color"],
            "main_warning": final_output["llm_analysis"],
            "toxic_clauses": final_output["toxic_clauses"],
            "violation_type": violation_type,
            "recommended_forms": recommended_forms,
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

