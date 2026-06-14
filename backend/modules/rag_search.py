import json
import os
import time
import urllib.request

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from sentence_transformers import CrossEncoder, SentenceTransformer

from models import AgentState

load_dotenv()

QDRANT_PATH = "data/qdrant_storage"
FTC_COLLECTION = "ftc_decisions"
KCA_COLLECTION = "kca_cases"
EMBEDDING_MODEL = "intfloat/multilingual-e5-large-instruct"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
RETRIEVE_K = 10  # 컬렉션당 후보 수
RERANK_TOP_K = 5  # reranker 통과 후 최종 반환 수

# 모듈 임포트 시 1회만 초기화
_model = SentenceTransformer(EMBEDDING_MODEL)
_reranker = CrossEncoder(RERANKER_MODEL)
_client = QdrantClient(path=QDRANT_PATH)


def _call_llm(api_key: str, prompt: str) -> str | None:
    """시스템 프롬프트 없이 LLM을 호출하고 응답 문자열을 반환. 실패 시 None."""
    if api_key.startswith("AIzaSy"):
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        model_name = "gemini-3.1-flash-lite"
    else:
        url = "https://api.openai.com/v1/chat/completions"
        model_name = "gpt-4o-mini"

    data = json.dumps({
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = json.loads(resp.read().decode("utf-8"))
            return content["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[RAG] LLM 호출 실패: {e}")
        return None


def _summarize_cases(query: str, docs: list[str]) -> list[str]:
    """검색된 원문 청크를 LLM으로 친근한 말투로 변환. API 키 없으면 원문 그대로 반환."""
    docs = [d for d in docs if d.strip()]
    if not docs:
        return []

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        return docs

    numbered = "\n\n".join(f"[사례 {i+1}]\n{doc}" for i, doc in enumerate(docs))
    prompt = (
        f"다음은 '{query}'와 관련된 공정거래위원회 및 한국소비자원 실제 사례들입니다.\n\n"
        f"{numbered}\n\n"
        "각 사례의 내용을 빠짐없이 유지하되, 딱딱한 법률 문체를 소비자가 읽기 편한 친근한 말투로만 바꿔주세요.\n"
        "내용 축약이나 생략 없이 말투만 부드럽게 변환해주세요.\n"
        "반드시 아래 JSON 배열 형식으로만 응답하세요 (백틱 없이):\n"
        "[\"사례1 변환 결과\", \"사례2 변환 결과\", ...]"
    )

    print(f"[RAG] 📝 검색된 판례 {len(docs)}건에 대해 LLM 요약 요청 중...")
    t0 = time.time()
    response = _call_llm(api_key, prompt)
    if response is None:
        print("[RAG] ❌ 요약 실패 (LLM 에러)")
        return docs
    print(f"[RAG] ✅ 판례 요약 완료 ({time.time() - t0:.2f}초)")
    try:
        result = json.loads(response)
        if isinstance(result, list):
            return [str(item) for item in result]
    except json.JSONDecodeError:
        pass
    return docs


def retrieve_similar_cases(query: str, top_k: int = RERANK_TOP_K, retrieve_k: int = RETRIEVE_K) -> list[str]:
    """공정위 및 소비자원 DB에서 쿼리와 유사한 사례를 검색하고 Reranking하여 반환합니다."""
    if not query.strip():
        print("[RAG] 검색 쿼리가 비어있어 검색을 건너뜁니다.")
        return []

    print("[RAG] 🔍 1/3 질문 임베딩(벡터화) 진행 중...")
    t0 = time.time()
    # 쿼리 임베딩: "query: " prefix 필수 (passage: 와 대칭)
    query_vector = _model.encode(
        "query: " + query,
        normalize_embeddings=True,
    ).tolist()
    print(f"[RAG] ✅ 임베딩 완료 ({time.time() - t0:.2f}초)")

    print("[RAG] 🔍 2/3 Qdrant 벡터 DB 검색 중...")
    t1 = time.time()
    # 1. 공정위 의결서 검색 (후보 retrieve_k개)
    ftc_hits = _client.query_points(
        collection_name=FTC_COLLECTION,
        query=query_vector,
        limit=retrieve_k,
        with_payload=True,
    ).points

    # 2. 한국소비자원 피해구제 사례 검색 (후보 retrieve_k개)
    kca_hits = _client.query_points(
        collection_name=KCA_COLLECTION,
        query=query_vector,
        limit=retrieve_k,
        with_payload=True,
    ).points
    print(f"[RAG] ✅ DB 검색 완료 ({time.time() - t1:.2f}초)")

    # 3. 두 컬렉션 후보 합산 후 reranker로 정밀 재정렬
    all_docs = [
        hit.payload.get("page_content", "")
        for hit in (ftc_hits + kca_hits)
        if hit.payload
    ]

    if not all_docs:
        return []

    print(f"[RAG] 🔍 3/3 검색된 문서 {len(all_docs)}건 Reranking(정밀 재정렬) 중...")
    t2 = time.time()
    scores = _reranker.predict([(query, doc) for doc in all_docs])
    ranked = sorted(zip(scores, all_docs), key=lambda x: x[0], reverse=True)
    print(f"[RAG] ✅ Reranking 완료 ({time.time() - t2:.2f}초)")
    return [doc for _, doc in ranked[:top_k]]


def search_rag_node(state: AgentState) -> AgentState:
    print("[Node] 공정위 및 소비자원 DB Dense 검색 + Reranking 중...")

    query = state["raw_text"]
    if not query.strip():
        print("[RAG] raw_text가 비어있어 검색을 건너뜁니다.")
        return {"retrieved_docs": []}

    top_docs = retrieve_similar_cases(query)

    return {"retrieved_docs": _summarize_cases(query, top_docs)}
