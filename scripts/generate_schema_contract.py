"""Замораживает текущую схему Gold как контракт"""
import json
from pathlib import Path
from clickhouse_connect import get_client
import os

client = get_client(host='localhost', port=8124, username='default',
                    password=os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_dev_password'))

desc = client.query("DESCRIBE TABLE av2_gold_scenarios")
contract = {
    "columns": [r[0] for r in desc.result_rows],
    "types": {r[0]: r[1] for r in desc.result_rows},
}

out = Path("config/gold_schema_contract.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"✅ Контракт заморожен: {out} ({len(contract['columns'])} столбцов)")
print("Любое будущее изменение схемы = явная регенерация контракта + code review.")
client.close()