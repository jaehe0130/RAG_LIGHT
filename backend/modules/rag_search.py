import csv
import json
import os
import time
import urllib.request
from pathlib import Path

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
RETRIEVE_K = 3
RERANK_TOP_K = 2

_DATA_DIR = Path(__file__).parent.parent / "data"
_RAW_DIR = _DATA_DIR / "raw"
_KCA_CSV = _DATA_DIR / "kca_cases.csv"

# 모듈 임포트 시 1회만 초기화
_model = SentenceTransformer(EMBEDDING_MODEL)
_reranker = CrossEncoder(RERANKER_MODEL)
_client = QdrantClient(path=QDRANT_PATH)

_kiwi = None
_bm25_index = None
_bm25_docs: list[str] = []


def _tokenize_kiwi(text: str) -> list[str]:
    if _kiwi is None:
        return text.split()
    return [token.form for token in _kiwi.tokenize(text)]


def _build_bm25_index() -> None:
    global _kiwi, _bm25_index, _bm25_docs

    try:
        from kiwipiepy import Kiwi
        from rank_bm25 import BM25Okapi
    except ImportError as e:
        print(f"[BM25] 패키지 없음, BM25 비활성화: {e}")
        return

    print("[BM25] 인덱스 구축 중...")
    t0 = time.time()
    _kiwi = Kiwi()

    docs: list[str] = []

    # *_hybrid.json 파일에서 page_content 수집
    hybrid_files = sorted(_RAW_DIR.glob("*_hybrid.json"))
    for f in hybrid_files:
        try:
            chunks: list[dict] = json.loads(f.read_text(encoding="utf-8"))
            for chunk in chunks:
                content = chunk.get("page_content", "").strip()
                if content:
                    docs.append(content)
        except Exception:
            continue

    # kca_cases.csv에서 질문+답변 수집
    if _KCA_CSV.exists():
        try:
            with open(_KCA_CSV, encoding="cp949") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    q = str(row.get("질문", "")).strip()
                    a = str(row.get("답변", "")).strip()
                    if q and a:
                        docs.append(q + "\n" + a)
        except Exception as e:
            print(f"[BM25] CSV 읽기 실패: {e}")

    if not docs:
        print("[BM25] 문서 없음, BM25 비활성화")
        return

    tokenized = [_tokenize_kiwi(doc) for doc in docs]
    _bm25_index = BM25Okapi(tokenized)
    _bm25_docs = docs
    print(f"[BM25] 인덱스 구축 완료: {len(docs)}개 문서 ({time.time() - t0:.1f}초)")


_build_bm25_index()


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


_KEY_SENTENCES_KEYWORDS = [
    "위약금", "환불", "해지", "청약철회", "손해배상", "면책", "책임", "환급", "취소",
    "과장", "허위", "보장", "효능", "한정", "선착순",
]


def extract_key_sentences(text: str, max_chars: int = 500) -> str:
    if len(text) <= max_chars:
        return text

    sentences = [s.strip() for s in text.replace("。", ".").split(".") if s.strip()]
    matched = [s for s in sentences if any(kw in s for kw in _KEY_SENTENCES_KEYWORDS)]

    if not matched:
        return text[:max_chars]

    result = ". ".join(matched)
    return result[:max_chars]


def _rewrite_query(text: str, max_chars: int = 500) -> str:
    """LLM으로 문서 핵심 법률 쟁점을 500자 이내 검색 쿼리로 압축. 실패 시 extract_key_sentences fallback."""
    if len(text) <= max_chars:
        return text

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        return extract_key_sentences(text)

    prompt = (
        "다음은 소비자 계약서 또는 광고 문서입니다.\n"
        "문서에서 소비자에게 불리하거나 불공정할 수 있는 핵심 법률 쟁점을 파악하여 "
        "벡터 DB 검색에 최적화된 한국어 요약문으로 응답하세요. "
        "500자를 넘지 말고, 설명·부연·기호 없이 요약문만 출력하세요.\n\n"
        f"{text[:2000]}"
    )

    result = _call_llm(api_key, prompt)
    if result:
        print(f"[RAG] ✅ Query Rewriting 완료: {result[:80]}")
        return result[:max_chars]
    return extract_key_sentences(text)


def retrieve_similar_cases(query: str, top_k: int = RERANK_TOP_K, retrieve_k: int = RETRIEVE_K) -> list[str]:
    """공정위 및 소비자원 DB에서 쿼리와 유사한 사례를 검색하고 Reranking하여 반환합니다."""
    if not query.strip():
        print("[RAG] 검색 쿼리가 비어있어 검색을 건너뜁니다.")
        return []

    print("[RAG] 🔍 0/4 LLM Query Rewriting 중...")
    query = _rewrite_query(query)

    print("[RAG] 🔍 1/4 질문 임베딩(벡터화) 진행 중...")
    t0 = time.time()
    query_vector = _model.encode(
        "query: " + query,
        normalize_embeddings=True,
    ).tolist()
    print(f"[RAG] ✅ 임베딩 완료 ({time.time() - t0:.2f}초)")

    print("[RAG] 🔍 2/4 Dense 검색 중...")
    t1 = time.time()
    ftc_hits = _client.query_points(
        collection_name=FTC_COLLECTION,
        query=query_vector,
        limit=retrieve_k,
        with_payload=True,
    ).points
    kca_hits = _client.query_points(
        collection_name=KCA_COLLECTION,
        query=query_vector,
        limit=retrieve_k,
        with_payload=True,
    ).points
    dense_docs = [
        hit.payload.get("page_content", "")
        for hit in (ftc_hits + kca_hits)
        if hit.payload
    ]
    print(f"[RAG] ✅ Dense 검색 완료 ({time.time() - t1:.2f}초, {len(dense_docs)}건)")

    print("[RAG] 🔍 3/4 BM25 키워드 검색 중...")
    t2 = time.time()
    bm25_docs: list[str] = []
    if _bm25_index is not None and _bm25_docs:
        tokenized_query = _tokenize_kiwi(query)
        scores = _bm25_index.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:retrieve_k]
        bm25_docs = [_bm25_docs[i] for i in top_indices if scores[i] > 0]
    print(f"[RAG] ✅ BM25 검색 완료 ({time.time() - t2:.2f}초, {len(bm25_docs)}건)")

    # Dense + BM25 결과 합산 후 중복 제거 (page_content 기준)
    seen: set[str] = set()
    all_docs: list[str] = []
    for doc in dense_docs + bm25_docs:
        if doc.strip() and doc not in seen:
            seen.add(doc)
            all_docs.append(doc)

    if not all_docs:
        return []

    print(f"[RAG] 🔍 4/4 후보 {len(all_docs)}건 Reranking(정밀 재정렬) 중...")
    t3 = time.time()
    scores = _reranker.predict([(query, doc) for doc in all_docs])
    ranked = sorted(zip(scores, all_docs), key=lambda x: x[0], reverse=True)
    print(f"[RAG] ✅ Reranking 완료 ({time.time() - t3:.2f}초)")
    return [doc for _, doc in ranked[:top_k]]


def search_rag_node(state: AgentState) -> AgentState:
    print("[Node] 공정위 및 소비자원 DB 하이브리드 검색(Dense+BM25) + Reranking 중...")

    query = state["raw_text"]
    if not query.strip():
        print("[RAG] raw_text가 비어있어 검색을 건너뜁니다.")
        return {"retrieved_docs": []}

    top_docs = retrieve_similar_cases(query)

    return {"retrieved_docs": top_docs}
