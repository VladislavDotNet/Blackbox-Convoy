from clickhouse_connect import get_client
import pandas as pd
from pathlib import Path
import os

client = get_client(host='localhost', port=8124, username='default',
                    password=os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_dev_password'))

# Схема таблицы напрямую из ClickHouse
desc = client.query("DESCRIBE TABLE av2_gold_scenarios")
table_columns = [r[0] for r in desc.result_rows]
table_types = {r[0]: r[1] for r in desc.result_rows}

gold_manifest = pd.read_parquet("data/gold/manifest.parquet")
print(f"📊 Загрузка {len(gold_manifest)} файлов батчами по 500...")

def coerce_df(df):
    """Приводит DataFrame ТОЧНО к схеме таблицы ClickHouse"""
    df = df.reindex(columns=table_columns)
    for col in table_columns:
        t = table_types[col]
        if t == 'String':
            df[col] = df[col].fillna('').astype(str)
        elif t == 'Bool':
            df[col] = df[col].fillna(False).astype(bool)
        else:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

BATCH = 500
batch = []
total_rows = 0
done = 0

for idx, row in gold_manifest.iterrows():
    file_path = Path("data/gold/av2/val") / row['relative_path']
    try:
        df = pd.read_parquet(file_path)
        df['scenario_file'] = row['relative_path']
        batch.append(coerce_df(df))
        done += 1
    except Exception as e:
        print(f"   ⚠️ Ошибка чтения {row['relative_path']}: {e}")
        continue

    if len(batch) >= BATCH:
        combined = pd.concat(batch, ignore_index=True)
        client.insert_df('av2_gold_scenarios', combined)
        total_rows += len(combined)
        batch = []
        print(f"   Загружено файлов: {done}/{len(gold_manifest)} ({total_rows:,} строк)")

if batch:
    combined = pd.concat(batch, ignore_index=True)
    client.insert_df('av2_gold_scenarios', combined)
    total_rows += len(combined)

print(f"✅ Загрузка завершена: {done:,} файлов, {total_rows:,} строк")
client.close()