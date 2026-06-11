from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from models import AgentState

QDRANT_PATH = "data/qdrant_storage"
FTC_COLLECTION = "ftc_decisions"
KCA_COLLECTION = "kca_cases"
EMBEDDING_MODEL = "intfloat/multilingual-e5-large-instruct"
TOP_K = 5

# 모듈 임포트 시 1회만 초기화
_model = SentenceTransformer(EMBEDDING_MODEL)
_client = QdrantClient(path=QDRANT_PATH)


def search_rag_node(state: AgentState) -> AgentState:
    print("[Node] 공정위 의결서 + 소비자원 판례 Dense 검색 중...")

    # 쿼리 임베딩: "query: " prefix 필수 (passage: 와 대칭)
    query_vector = _model.encode(
        "query: " + state["raw_text"],
        normalize_embeddings=True,
    ).tolist()

    ftc_results = _client.query_points(
        collection_name=FTC_COLLECTION,
        query=query_vector,
        limit=TOP_K,
        with_payload=True,
    ).points

    kca_results = _client.query_points(
        collection_name=KCA_COLLECTION,
        query=query_vector,
        limit=TOP_K,
        with_payload=True,
    ).points

    return {
        "retrieved_ftc_docs": [
            hit.payload.get("page_content", "") for hit in ftc_results if hit.payload
        ],
        "retrieved_kca_docs": [
            hit.payload.get("page_content", "") for hit in kca_results if hit.payload
        ],
    }
