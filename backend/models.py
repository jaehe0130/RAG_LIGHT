from pydantic import BaseModel
from typing import List, Dict, Any, TypedDict

# 1. LangGraph 노드 간 실시간 데이터 공유 및 상태 관리를 위한 바구니
class AgentState(TypedDict):
    file_path: str                # 업로드된 파일 경로 (이미지 및 PDF)
    input_type: str               # "CONTRACT"(약관) 또는 "AD"(광고) 분기 플래그
    raw_text: str                 # OCR 추출 원본 텍스트
    
    # 다중 지식베이스 결합 검색 + reranker 결과 저장소
    retrieved_docs: List[str]     # 공정위+소비자원 통합 reranking 상위 결과
    
    llm_analysis: str             # OpenAI API 기반 친근한 법률 요약/해설
    toxic_clauses: List[Dict[str, Any]] # 추출된 불공정 독소조항 및 기만행위 목록
    signal_color: str             # ● 안전 / ● 주의 / ● 위험 최종 라벨
    
    report_draft: str             # 관공서 양식에 맞춘 신고서 초안 텍스트
    classified_type: str          # 분류 에이전트가 분류한 문서 카테고리 (SPORTS, ECOMMERCE 등)

# 2. React 프론트엔드가 바로 화면에 뿌릴 수 있도록 서빙하는 최종 API 응답 포맷
class AnalysisResponse(BaseModel):
    status: str
    input_type: str
    ocr_text: str
    analysis: Dict[str, Any]      # signal_color, main_warning, toxic_clauses
    statistics: Dict[str, Any]    # React 차트 시각화용 소비자원 통계 (dispute_rate, count)
    report_form: Dict[str, Any]   # 원클릭 신고서/신청서 초안 서식 데이터
    reference_cases: List[str]    # RAG 검색으로 찾아온 공정위/소비자원 유사 사례 문서들

# 3. 챗봇 통신을 위한 요청/응답 포맷
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    query: str
    history: List[ChatMessage] = []
    context: str = ""

class ChatResponse(BaseModel):
    response: str

