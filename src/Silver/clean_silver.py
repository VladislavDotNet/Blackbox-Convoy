import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
import xxhash

# === КОНФИГУРАЦИЯ ===
BRONZE_DIR = Path("data/bronze/av2/val")
SILVER_DIR = Path("data/silver/av2/val")
SILVER_MANIFEST = Path("data/silver/manifest.parquet")


def load_bronze_manifest():
    """Загружает манифест Bronze-слоя"""
    return pd.read_parquet("data/bronze/manifest.parquet")


def clean_and_normalize(file_path: Path) -> pd.DataFrame:
    """
    Очищает и нормализует один parquet-файл из Bronze.
    Возвращает DataFrame с единой схемой.
    """
    # Читаем исходный файл
    df = pd.read_parquet(file_path)

    # === ОЧИСТКА ===
    # 1. Удаляем дубликаты (если есть)
    df = df.drop_duplicates()

    # 2. Удаляем строки с полностью пустыми значениями
    df = df.dropna(how='all')

    # === НОРМАЛИЗАЦИЯ ===
    # 3. Приводим имена столбцов к нижнему регистру (если нужно)
    df.columns = [col.lower() for col in df.columns]

    # 4. Добавляем метаданные
    df['source_file'] = file_path.name
    df['processed_timestamp'] = datetime.now(timezone.utc).isoformat()

    return df


def process_all_bronze_files():
    """Обрабатывает все parquet-файлы из Bronze и сохраняет в Silver"""
    print(f"🔄 Обработка Bronze → Silver...")

    # Создаём директорию Silver
    SILVER_DIR.mkdir(parents=True, exist_ok=True)

    # Загружаем Bronze-манифест
    bronze_manifest = load_bronze_manifest()

    # Фильтруем только parquet-файлы
    parquet_files = bronze_manifest[
        bronze_manifest['relative_path'].str.endswith('.parquet')
    ]

    print(f"   Найдено {len(parquet_files)} parquet-файлов в Bronze")

    silver_records = []
    total_rows = 0

    for idx, row in parquet_files.iterrows():
        file_path = BRONZE_DIR / row['relative_path']

        try:
            # Очищаем и нормализуем
            df = clean_and_normalize(file_path)

            # Сохраняем в Silver (тот же относительный путь)
            output_path = SILVER_DIR / row['relative_path']
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(output_path, index=False)

            # Собираем метаданные для Silver-манифеста
            file_hash = xxhash.xxh64(str(output_path).encode()).hexdigest()

            silver_records.append({
                'relative_path': row['relative_path'],
                'file_size_bytes': output_path.stat().st_size,
                'xxhash': file_hash,
                'row_count': len(df),
                'processed_timestamp': datetime.now(timezone.utc).isoformat()
            })

            total_rows += len(df)

        except Exception as e:
            print(f"   ⚠️ Ошибка обработки {row['relative_path']}: {e}")

    # Создаём Silver-манифест
    silver_manifest_df = pd.DataFrame(silver_records)
    silver_manifest_df.to_parquet(SILVER_MANIFEST, index=False)

    print(f"✅ Silver-слой готов")
    print(f"   Обработано файлов: {len(silver_records)}")
    print(f"   Всего строк: {total_rows:,}")
    print(f"   Манифест: {SILVER_MANIFEST}")


def main():
    print("=== SILVER LAYER: CLEAN & NORMALIZE ===")
    process_all_bronze_files()


if __name__ == "__main__":
    main()