"""Загрузка векторов сценариев из Parquet в Qdrant."""
import pandas as pd
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

PARQUET_PATH = "data/vectors/scenarios.parquet"
COLLECTION = "av2_scenarios"
BATCH_SIZE = 500

def main():
    print(f"Читаем векторы из {PARQUET_PATH}...")
    df = pd.read_parquet(PARQUET_PATH)
    print(f"Всего сценариев для загрузки: {len(df)}")

    client = QdrantClient(host="localhost", port=6337)
    
    # Список колонок, которые идут в вектор (v0 ... v39)
    vector_cols = [f"v{i}" for i in range(40)]
    # Список колонок, которые идут в payload (метаданные)
    payload_cols = ["scenario_id", "city", "source_file", "max_speed", "n_tracks"]

    points = []
    uploaded_count = 0

    print("Начинаем загрузку батчами...")
    for idx, row in df.iterrows():
        # Формируем payload (словарь метаданных)
        payload = {col: row[col] for col in payload_cols}
        
        # Формируем вектор (список из 40 float)
        vector = row[vector_cols].tolist()
        
        # Создаем точку. ID берем из scenario_id (Qdrant поддерживает строковые ID)
        point = PointStruct(
            id=str(row["scenario_id"]),
            vector=vector,
            payload=payload
        )
        points.append(point)

        # Отправляем батч
        if len(points) >= BATCH_SIZE:
            client.upsert(collection_name=COLLECTION, points=points)
            uploaded_count += len(points)
            print(f"   Загружено: {uploaded_count}/{len(df)}")
            points = []  # Очищаем для следующего батча

    # Догружаем остаток
    if points:
        client.upsert(collection_name=COLLECTION, points=points)
        uploaded_count += len(points)
        print(f"   Загружено: {uploaded_count}/{len(df)}")

    print(f"✅ Загрузка завершена. Всего точек: {uploaded_count}")
    
    # Финальная проверка
    info = client.get_collection(COLLECTION)
    print(f"Статус коллекции: {info.status}, точек в базе: {info.points_count}")

if __name__ == "__main__":
    main()