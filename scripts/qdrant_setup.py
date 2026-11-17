"""Создаёт коллекцию Qdrant под векторы сценариев AV2."""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

COLLECTION = "av2_scenarios"
DIM = 40  # 8 агрегатов + 32 координаты формы траектории (16 точек x,y)

client = QdrantClient(host="localhost", port=6337)

if client.collection_exists(COLLECTION):
    print(f"Коллекция {COLLECTION} уже существует — пропускаем создание")
else:
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=DIM, distance=Distance.COSINE),
    )
    print(f"Коллекция {COLLECTION} создана: dim={DIM}, metric=Cosine")

print(client.get_collection(COLLECTION))