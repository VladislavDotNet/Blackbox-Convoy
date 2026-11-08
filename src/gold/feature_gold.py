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
    Добавляет фичи для ML с учётом пропусков и частоты сенсора (10 Гц).
    """
    # Частота записи AV2: 10 Гц = 0.1 сек между замерами
    DT = 0.1
    
    # === ОЧИСТКА ===
    df = df.drop_duplicates()
    df = df.dropna(how='all')
    df.columns = [col.lower() for col in df.columns]
    
    # === СКОРОСТЬ И УСКОРЕНИЕ (только между соседними наблюдаемыми шагами) ===
    if 'position_x' in df.columns and 'position_y' in df.columns:
        # Проверяем, есть ли timestep и observed
        has_timestep = 'timestep' in df.columns
        has_observed = 'observed' in df.columns
        
        # Маска: соседние шаги И оба наблюдаемые
        if has_timestep and has_observed:
            consecutive = (df['timestep'].diff() == 1) & (df['observed'] == True) & (df['observed'].shift(1) == True)
        else:
            # Fallback: просто соседние шаги
            consecutive = pd.Series([True] * len(df), index=df.index)
        
        # Считаем diff только для последовательных наблюдаемых точек
        df['velocity_x'] = np.where(consecutive, df['position_x'].diff() / DT, np.nan)
        df['velocity_y'] = np.where(consecutive, df['position_y'].diff() / DT, np.nan)
        df['speed'] = np.sqrt(df['velocity_x']**2 + df['velocity_y']**2)
        
        # Ускорение
        df['acceleration_x'] = np.where(consecutive, df['velocity_x'].diff() / DT, np.nan)
        df['acceleration_y'] = np.where(consecutive, df['velocity_y'].diff() / DT, np.nan)
        df['acceleration'] = np.sqrt(df['acceleration_x']**2 + df['acceleration_y']**2)
        
        # Yaw rate
        if 'heading' in df.columns:
            df['yaw_rate'] = np.where(consecutive, df['heading'].diff() / DT, np.nan)
    
    # === АГРЕГАЦИИ (NaN-safe) ===
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
    
    # Добавляем метаданные
    df['source_file'] = ''  # заполнится в цикле обработки
    df['processed_timestamp'] = datetime.now(timezone.utc).isoformat()
    
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