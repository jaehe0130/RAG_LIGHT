"""
팀원 C 전용: Qdrant 데이터 초기 적재 (Ingestion) 스크립트

이 스크립트는 서버 구동 전 '최초 1회(또는 업데이트 시)' 실행되며,
raw/ 폴더의 *_hybrid.json + *_metadata.json 쌍을 읽어
intfloat/multilingual-e5-large-instruct 모델로 벡터화하여
Qdrant 로컬 DB에 upsert합니다.
"""

import json
import uuid
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

load_dotenv()

RAW_DIR = Path(__file__).parent / "raw"
QDRANT_PATH = str(Path(__file__).parent / "qdrant_storage")
COLLECTION_NAME = "ftc_decisions"
EMBEDDING_MODEL = "intfloat/multilingual-e5-large-instruct"
VECTOR_DIM = 1024


def _to_point_id(chunk_id: str) -> str:
    """chunk_id 문자열 → 결정론적 UUID (Qdrant point ID로 사용)"""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))


def _get_existing_ids(client: QdrantClient, point_ids: list[str]) -> set[str]:
    """Qdrant에 이미 존재하는 point ID 집합 반환"""
    if not point_ids:
        return set()
    results = client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=point_ids,
        with_payload=False,
        with_vectors=False,
    )
    return {str(r.id) for r in results}


def ingest_data_to_qdrant():
    print("🚀 [Ingestion] 공정위 의결서 데이터 Qdrant 초기 적재 프로세스 시작...")

    # 임베딩 모델 로드 (최초 실행 시 허깅페이스에서 자동 다운로드)
    print(f"[Ingestion] 임베딩 모델 로딩 중: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    # Qdrant 로컬 파일 방식 클라이언트
    client = QdrantClient(path=QDRANT_PATH)

    # 컬렉션이 없으면 생성
    existing_collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing_collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        print(f"[Ingestion] 컬렉션 '{COLLECTION_NAME}' 신규 생성")
    else:
        print(f"[Ingestion] 컬렉션 '{COLLECTION_NAME}' 기존 재사용")

    # raw/ 폴더에서 *_hybrid.json 파일 목록 수집
    hybrid_files = sorted(RAW_DIR.glob("*_hybrid.json"))
    total = len(hybrid_files)
    if total == 0:
        print(f"⚠️  [Ingestion] {RAW_DIR} 에서 hybrid.json 파일을 찾을 수 없습니다.")
        return
    print(f"[Ingestion] 처리 대상 파일 수: {total}개\n")

    for idx, hybrid_path in enumerate(hybrid_files, start=1):
        # 파일명에서 "_hybrid" 접미사를 "_metadata"로 교체하여 쌍 파일 경로 구성
        metadata_path = hybrid_path.parent / hybrid_path.name.replace(
            "_hybrid.json", "_metadata.json"
        )
        base_name = hybrid_path.name.replace("_hybrid.json", "")

        print(f"[{idx:>3}/{total}] {base_name}")

        if not metadata_path.exists():
            print(f"  ⚠️  metadata 파일 없음, 건너뜀")
            continue

        with open(hybrid_path, encoding="utf-8") as f:
            chunks: list[dict] = json.load(f)
        with open(metadata_path, encoding="utf-8") as f:
            doc_meta: dict = json.load(f)

        # 전체 청크에 대한 point ID 계산
        chunk_pid_pairs = [
            (chunk, _to_point_id(chunk["metadata"]["chunk_id"])) for chunk in chunks
        ]

        # 이미 적재된 chunk는 건너뜀 (중복 실행 방지)
        existing_ids = _get_existing_ids(client, [pid for _, pid in chunk_pid_pairs])
        new_pairs = [(c, pid) for c, pid in chunk_pid_pairs if pid not in existing_ids]

        if not new_pairs:
            print(f"  ✅ 전체 {len(chunks)}개 청크 이미 적재됨, 건너뜀")
            continue

        print(f"  → 신규 청크 {len(new_pairs)}개 / 전체 {len(chunks)}개 — 임베딩 중...")

        # 문서 임베딩: "passage: " 접두사 부착
        texts = ["passage: " + c["page_content"] for c, _ in new_pairs]
        embeddings = model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )

        # payload: 청크 메타데이터 + 사건 정보 병합
        points = [
            PointStruct(
                id=pid,
                vector=embedding.tolist(),
                payload={
                    **chunk["metadata"],
                    "page_content": chunk["page_content"],
                    "의결서관리번호": doc_meta.get("의결서관리번호"),
                    "의결서제목": doc_meta.get("의결서제목"),
                    "공개일자": doc_meta.get("공개일자"),
                    "의결서파일명": doc_meta.get("의결서파일명"),
                    "피심인정보": doc_meta.get("피심인정보", []),
                },
            )
            for (chunk, pid), embedding in zip(new_pairs, embeddings)
        ]

        client.upsert(collection_name=COLLECTION_NAME, points=points)
        print(f"  ✅ {len(points)}개 upsert 완료")

    total_count = client.count(collection_name=COLLECTION_NAME).count
    print(f"\n✅ [Ingestion] 전체 완료! 컬렉션 총 포인트 수: {total_count:,}개")


if __name__ == "__main__":
    ingest_data_to_qdrant()
