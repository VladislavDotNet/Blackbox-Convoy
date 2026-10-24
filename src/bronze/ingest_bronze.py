import tarfile
import os
import hashlib
import xxhash
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

# === КОНФИГУРАЦИЯ ===
RAW_ARCHIVE = Path("data/raw/val_raw.tar")
BRONZE_DIR = Path("data/bronze/av2/val")
MANIFEST_PATH = Path("data/bronze/manifest.parquet")


def compute_xxhash(file_path: Path) -> str:
    """Вычисляет xxhash64 для файла (быстрее MD5, достаточно для проверки целостности)"""
    h = xxhash.xxh64()
    with open(file_path, "rb") as f:
        # Читаем чанками по 8 МБ, чтобы не грузить весь файл в память
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_archive():
    """Распаковывает tar-архив в Bronze-директорию"""
    print(f"📦 Распаковка {RAW_ARCHIVE} в {BRONZE_DIR}...")

    # Создаём директорию, если её нет
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)

    # Открываем tar-архив (без сжатия, т.к. файл .tar, а не .tar.gz)
    with tarfile.open(RAW_ARCHIVE, "r") as tar:
        # Распаковываем все файлы
        tar.extractall(path=BRONZE_DIR)

    print(f"✅ Распаковка завершена")


def build_manifest():
    """Сканирует Bronze-директорию и строит манифест в формате Parquet"""
    print(f"📋 Построение манифеста...")

    records = []

    # Рекурсивно обходим все файлы в Bronze-директории
    for file_path in BRONZE_DIR.rglob("*"):
        if file_path.is_file():
            # Относительный путь от Bronze-директории
            relative_path = file_path.relative_to(BRONZE_DIR)

            # Вычисляем метаданные
            file_size = file_path.stat().st_size
            file_hash = compute_xxhash(file_path)
            ingestion_time = datetime.now(timezone.utc)

            records.append({
                "relative_path": str(relative_path),
                "file_size_bytes": file_size,
                "xxhash": file_hash,
                "ingestion_timestamp": ingestion_time.isoformat()
            })

    # Создаём DataFrame и сохраняем в Parquet
    df = pd.DataFrame(records)
    df.to_parquet(MANIFEST_PATH, index=False)

    print(f"✅ Манифест сохранён: {MANIFEST_PATH}")
    print(f"   Всего файлов: {len(df)}")
    print(f"   Общий размер: {df['file_size_bytes'].sum() / (1024 ** 3):.2f} GB")


def main():
    print("=== BRONZE LAYER: INGESTION ===")
    extract_archive()
    build_manifest()


if __name__ == "__main__":
    main()