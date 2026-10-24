import pandas as pd
from pathlib import Path

# Загружаем манифест Gold-слоя
gold_manifest = pd.read_parquet("data/gold/manifest.parquet")
print(f"Всего файлов в Gold: {len(gold_manifest)}")
print(f"Среднее количество фич (столбцов) на файл: {gold_manifest['feature_count'].mean():.0f}")

# Смотрим на реальные данные первого файла
first_gold_file = Path("data/gold/av2/val") / gold_manifest.iloc[0]['relative_path']
df = pd.read_parquet(first_gold_file)

print(f"\nСтруктура данных первого сценария:")
print(f"  Строк: {len(df)}, Столбцов: {len(df.columns)}")
print(f"\nНовые фичи (примеры столбцов):")
new_features = [col for col in df.columns if any(x in col.lower() for x in ['speed', 'acceleration', 'yaw', 'duration', 'agent_count', 'mean_', 'max_'])]
print(new_features[:10])