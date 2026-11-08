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
    Фичи для ML: скорость/ускорение только между соседними наблюдаемыми
    шагами ОДНОГО трека, с учётом частоты сенсора 10 Гц.
    """
    DT = 0.1  # 10 Гц

    df = df.drop_duplicates()
    df = df.dropna(how='all')
    df.columns = [c.lower() for c in df.columns]

    needed = {'position_x', 'position_y', 'track_id', 'timestep', 'observed'}
    if needed <= set(df.columns):
        # Сортируем: трек -> время. Иначе diff прыгает между треками
        df = df.sort_values(['track_id', 'timestep']).reset_index(drop=True)
        g = df.groupby('track_id', sort=False)

        # Маска валидности: соседний timestep ВНУТРИ трека + оба шага наблюдались
        dt_ok = g['timestep'].diff() == 1
        obs_now = df['observed'].astype(bool)
        obs_prev = g['observed'].shift(1).eq(True)
        valid = dt_ok & obs_now & obs_prev

        # Скорость: расстояние между соседними точками трека / DT
        vx = np.where(valid, g['position_x'].diff() / DT, np.nan)
        vy = np.where(valid, g['position_y'].diff() / DT, np.nan)
        df['velocity_x'] = vx
        df['velocity_y'] = vy
        df['speed'] = np.sqrt(vx**2 + vy**2)

        # Ускорение и yaw rate: diff уже посчитанных скоростей, тоже внутри трека
        g = df.groupby('track_id', sort=False)
        df['acceleration_x'] = np.where(valid, g['velocity_x'].diff() / DT, np.nan)
        df['acceleration_y'] = np.where(valid, g['velocity_y'].diff() / DT, np.nan)
        df['acceleration'] = np.sqrt(df['acceleration_x']**2 + df['acceleration_y']**2)
        if 'heading' in df.columns:
            df['yaw_rate'] = np.where(valid, g['heading'].diff() / DT, np.nan)

    # Агрегаты (NaN игнорируются автоматически)
    if 'speed' in df.columns:
        df['mean_speed'] = df['speed'].mean()
        df['max_speed'] = df['speed'].max()
        df['std_speed'] = df['speed'].std()
    if 'acceleration' in df.columns:
        df['mean_acceleration'] = df['acceleration'].mean()
        df['max_acceleration'] = df['acceleration'].max()
    if 'timestamp' in df.columns:
        df['duration_sec'] = df['timestamp'].max() - df['timestamp'].min()
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