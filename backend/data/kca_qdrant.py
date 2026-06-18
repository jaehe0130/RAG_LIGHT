import pandas as pd
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

CSV_PATH = "/kca_cases.csv"
QDRANT_PATH = "/qdrant_storage"
COLLECTION_NAME = "kca_cases"
EMBEDDING_MODEL = "intfloat/multilingual-e5-large-instruct"
VECTOR_DIM = 1024
MAX_ROWS = 11371


def _to_point_id(text: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, text))


# 데이터 로드
df = pd.read_csv(CSV_PATH, encoding="cp949")
df = df.head(MAX_ROWS)
df = df[df["질문"].notna() & df["답변"].notna()]
print(f"총 {len(df)}건 로드 완료")

# 모델 및 클라이언트 초기화
print("임베딩 모델 로딩 중...")
model = SentenceTransformer(EMBEDDING_MODEL)
client = QdrantClient(path=QDRANT_PATH)

# 컬렉션 생성
existing_collections = [c.name for c in client.get_collections().collections]
if COLLECTION_NAME not in existing_collections:
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
    )
    print(f"컬렉션 '{COLLECTION_NAME}' 생성 완료")
else:
    print(f"컬렉션 '{COLLECTION_NAME}' 기존 재사용")

# 임베딩 및 upsert
BATCH_SIZE = 64
rows = df.to_dict("records")
total = len(rows)

for i in range(0, total, BATCH_SIZE):
    batch = rows[i : i + BATCH_SIZE]
    texts = ["passage: " + str(row["질문"]) + " " + str(row["답변"]) for row in batch]
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    points = [
        PointStruct(
            id=_to_point_id(str(row["질문"])[:100]),
            vector=embedding.tolist(),
            payload={
                "page_content": str(row["질문"]) + "\n" + str(row["답변"]),
                "질문": str(row["질문"]),
                "답변": str(row["답변"]),
                "대분류": str(row.get("대분류", "")),
                "중분류": str(row.get("중분류", "")),
                "품목": str(row.get("품목", "")),
                "출처": str(row.get("출처", "")),
            },
        )
        for row, embedding in zip(batch, embeddings)
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"[{min(i+BATCH_SIZE, total)}/{total}] upsert 완료")

total_count = client.count(collection_name=COLLECTION_NAME).count
print(f"\n✅ 전체 완료! 총 포인트 수: {total_count:,}개")
