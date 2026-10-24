import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import xxhash

# === КОНФИГУРАЦИЯ ===
SILVER_DIR = Path("data/silver/av2/val")
GOLD_DIR = Path("data/gold/av2/val")
GOLD_MANIFEST = Path("data/gold/manifest.parquet")


def load_silver_manifest():
    """Загружает манифест Silver-слоя"""
    return pd.read_parquet("data/silver/manifest.parquet")


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Добавляет фичи для ML-модели предсказания движения.
    Работает с траекториями агентов (x, y координаты во времени).
    """
    # === ПРОИЗВОДНЫЕ ПРИЗНАКИ ===

    # 1. Скорость (первая производная позиции)
    if 'position_x' in df.columns and 'position_y' in df.columns:
        df['velocity_x'] = df['position_x'].diff()
        df['velocity_y'] = df['position_y'].diff()

        # Модуль скорости
        df['speed'] = np.sqrt(df['velocity_x'] ** 2 + df['velocity_y'] ** 2)

        # 2. Ускорение (вторая производная)
        df['acceleration_x'] = df['velocity_x'].diff()
        df['acceleration_y'] = df['velocity_y'].diff()
        df['acceleration'] = np.sqrt(df['acceleration_x'] ** 2 + df['acceleration_y'] ** 2)

        # 3. Yaw rate (изменение направления)
        if 'heading' in df.columns:
            df['yaw_rate'] = df['heading'].diff()

    # === АГРЕГАЦИИ НА УРОВНЕ СЦЕНАРИЯ ===

    # 4. Статистики траектории
    if 'speed' in df.columns:
        df['mean_speed'] = df['speed'].mean()
        df['max_speed'] = df['speed'].max()
        df['std_speed'] = df['speed'].std()

    if 'acceleration' in df.columns:
        df['mean_acceleration'] = df['acceleration'].mean()
        df['max_acceleration'] = df['acceleration'].max()

    # 5. Длительность сценария (если есть timestamp)
    if 'timestamp' in df.columns:
        df['duration_sec'] = df['timestamp'].max() - df['timestamp'].min()

    # 6. Количество уникальных агентов (если есть agent_id)
    if 'agent_id' in df.columns:
        df['agent_count'] = df['agent_id'].nunique()

    return df


def process_all_silver_files():
    """Обрабатывает все файлы из Silver и сохраняет в Gold с фичами"""
    print(f"🚀 Обработка Silver → Gold (feature engineering)...")

    # Создаём директорию Gold
    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    # Загружаем Silver-манифест
    silver_manifest = load_silver_manifest()

    print(f"   Найдено {len(silver_manifest)} файлов в Silver")

    gold_records = []
    total_rows = 0

    for idx, row in silver_manifest.iterrows():
        file_path = SILVER_DIR / row['relative_path']

        try:
            # Читаем очищенные данные
            df = pd.read_parquet(file_path)

            # Добавляем фичи
            df = engineer_features(df)

            # Сохраняем в Gold
            output_path = GOLD_DIR / row['relative_path']
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(output_path, index=False)

            # Собираем метаданные
            file_hash = xxhash.xxh64(str(output_path).encode()).hexdigest()

            gold_records.append({
                'relative_path': row['relative_path'],
                'file_size_bytes': output_path.stat().st_size,
                'xxhash': file_hash,
                'row_count': len(df),
                'feature_count': len(df.columns),
                'processed_timestamp': datetime.now(timezone.utc).isoformat()
            })

            total_rows += len(df)

        except Exception as e:
            print(f"   ⚠️ Ошибка обработки {row['relative_path']}: {e}")

    # Создаём Gold-манифест
    gold_manifest_df = pd.DataFrame(gold_records)
    gold_manifest_df.to_parquet(GOLD_MANIFEST, index=False)

    print(f"✅ Gold-слой готов")
    print(f"   Обработано файлов: {len(gold_records)}")
    print(f"   Всего строк: {total_rows:,}")
    print(f"   Манифест: {GOLD_MANIFEST}")


def main():
    print("=== GOLD LAYER: FEATURE ENGINEERING ===")
    process_all_silver_files()


if __name__ == "__main__":
    main()