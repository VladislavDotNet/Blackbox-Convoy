from clickhouse_connect import get_client
import pandas as pd
from pathlib import Path
import os

client = get_client(host='localhost', port=8124, username='default',
                    password=os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_dev_password'))

# 1. Читаем один файл Gold, чтобы узнать РЕАЛЬНУЮ схему
gold_manifest = pd.read_parquet("data/gold/manifest.parquet")
sample_path = Path("data/gold/av2/val") / gold_manifest.iloc[0]['relative_path']
df = pd.read_parquet(sample_path)
df['scenario_file'] = 'sample'

print("Реальная схема Gold-слоя:")
for col in df.columns:
    print(f"   {col}: {df[col].dtype}")

# 2. Маппинг pandas dtype -> тип ClickHouse
def map_dtype(dtype):
    name = str(dtype)
    if name.startswith('int'):
        return 'Int64'
    if name.startswith('uint'):
        return 'UInt64'
    if name.startswith('float'):
        return 'Float64'
    if name == 'bool':
        return 'Bool'
    return 'String'

# 3. Собираем CREATE TABLE с обратными кавычками (защита от ключевых слов)
columns_sql = ",\n    ".join(f"`{col}` {map_dtype(df[col].dtype)}" for col in df.columns)

# 4. ORDER BY только из столбцов, которые реально существуют
order_candidates = [c for c in ('scenario_file', 'timestamp', 'track_id') if c in df.columns]
if not order_candidates:
    order_candidates = [df.columns[0]]
order_sql = ", ".join(f"`{c}`" for c in order_candidates)

create_sql = f"""
CREATE TABLE av2_gold_scenarios (
    {columns_sql}
) ENGINE = MergeTree()
ORDER BY ({order_sql})
"""

print("\nСгенерированный SQL:")
print(create_sql)

# 5. Пересоздаём таблицу
client.command("DROP TABLE IF EXISTS av2_gold_scenarios")
client.command(create_sql)
print("✅ Таблица пересоздана по реальной схеме данных")
client.close()