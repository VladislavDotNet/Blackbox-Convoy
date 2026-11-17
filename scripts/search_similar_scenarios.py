"""Поиск похожих сценариев в Qdrant по вектору-запросу."""
import pandas as pd
from qdrant_client import QdrantClient

PARQUET_PATH = "data/vectors/scenarios.parquet"
COLLECTION = "av2_scenarios"
TOP_K = 5

def main():
    # 1. Выбираем целевой сценарий для поиска (берём первый из parquet для простоты)
    df = pd.read_parquet(PARQUET_PATH)
    target_row = df.iloc[0]
    target_id = str(target_row["scenario_id"])
    
    print(f"🎯 Целевой сценарий для поиска: {target_id}")
    print(f"   Город: {target_row['city']}, Макс. скорость: {target_row['max_speed']:.2f} м/с, Агентов: {target_row['n_tracks']}")
    print(f"   Файл: {target_row['source_file']}\n")

    # 2. Формируем вектор-запрос (те же 40 колонок v0...v39)
    vector_cols = [f"v{i}" for i in range(40)]
    query_vector = target_row[vector_cols].tolist()

    # 3. Инициализируем клиент и делаем поиск
    client = QdrantClient(host="localhost", port=6337)
    
    print(f"🔍 Ищем топ-{TOP_K} похожих сценариев в коллекции {COLLECTION}...")
    
    results = client.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        limit=TOP_K,
    ).points

    # 4. Выводим результаты
    print(f"\n✅ Найдено {len(results)} результатов:")
    print("-" * 80)
    for i, hit in enumerate(results, 1):
        payload = hit.payload
        score = hit.score
        # Первый результат будет сам целевой сценарий (score = 1.0)
        is_target = "(ЦЕЛЕВОЙ)" if str(payload.get("scenario_id")) == target_id else ""
        
        print(f"#{i} | Score: {score:.4f} {is_target}")
        print(f"    ID: {payload.get('scenario_id')}")
        print(f"    Город: {payload.get('city')} | Макс. скорость: {payload.get('max_speed'):.2f} м/с | Агентов: {payload.get('n_tracks')}")
        print(f"    Файл: {payload.get('source_file')}")
        print("-" * 80)

if __name__ == "__main__":
    main()