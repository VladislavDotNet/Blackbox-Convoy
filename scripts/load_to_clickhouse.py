"""Загрузка Gold -> ClickHouse с schema-контрактом и quality gate."""
import json
import sys
import os
from pathlib import Path

import pandas as pd
from clickhouse_connect import get_client

CONTRACT_PATH = Path("config/gold_schema_contract.json")
GOLD_DIR = Path("data/gold/av2/val")
BATCH = 500
SPEED_LIMIT = 50.0  # м/с: физический предел для городского трафика (~180 км/ч)


class SchemaDriftError(Exception):
    """Схема данных разошлась с контрактом."""


def load_contract():
    if not CONTRACT_PATH.exists():
        raise SchemaDriftError(
            f"Контракт не найден: {CONTRACT_PATH}. Запусти scripts/generate_schema_contract.py"
        )
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def check_schema(df: pd.DataFrame, expected: set, context: str):
    """Громко падает при любом расхождении схемы с контрактом."""
    actual = set(df.columns)
    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        raise SchemaDriftError(
            f"{context}: дрейф схемы. Отсутствуют: {sorted(missing)}. "
            f"Неожиданные: {sorted(extra)}"
        )


def quality_gate(df: pd.DataFrame) -> list:
    """Возвращает список нарушений качества данных."""
    problems = []
    if len(df) == 0:
        problems.append("пустой файл")
    if "speed" in df.columns:
        bad = df["speed"].abs() > SPEED_LIMIT
        if bad.any():
            problems.append(
                f"speed > {SPEED_LIMIT}: строк={int(bad.sum())}, max={df['speed'].max():.1f}"
            )
    return problems


def coerce_df(df, columns, types):
    for col in columns:
        t = types[col]
        if t == "String":
            df[col] = df[col].fillna("").astype(str)
        elif t == "Bool":
            df[col] = df[col].fillna(False).astype(bool)
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df[columns]


def main():
    contract = load_contract()
    columns = contract["columns"]
    types = contract["types"]
    expected = set(columns)

    client = get_client(host='localhost', port=8124, username='default',
                        password=os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_dev_password'))

    # Таблица в CH тоже должна совпадать с контрактом
    desc = client.query("DESCRIBE TABLE av2_gold_scenarios")
    table_cols = [r[0] for r in desc.result_rows]
    if set(table_cols) != expected:
        raise SchemaDriftError(f"Схема таблицы CH != контракт: {set(table_cols) ^ expected}")

    manifest = pd.read_parquet("data/gold/manifest.parquet")
    print(f"📊 Загрузка {len(manifest)} файлов (контракт + quality gate)...")

    quarantined = []
    batch, done, total_rows = [], 0, 0

    for _, row in manifest.iterrows():
        path = GOLD_DIR / row["relative_path"]
        try:
            df = pd.read_parquet(path)
            df["scenario_file"] = row["relative_path"]

            # ГЕЙТ 1: схема
            check_schema(df, expected, row["relative_path"])

            # ГЕЙТ 2: качество значений
            problems = quality_gate(df)
            if problems:
                quarantined.append((row["relative_path"], problems))
                continue

            batch.append(coerce_df(df, columns, types))
            done += 1

        except SchemaDriftError:
            raise  # дрейф схемы = немедленная громкая остановка
        except Exception as e:
            quarantined.append((row["relative_path"], [str(e)]))
            continue

        if len(batch) >= BATCH:
            combined = pd.concat(batch, ignore_index=True)
            client.insert_df("av2_gold_scenarios", combined)
            total_rows += len(combined)
            batch = []
            print(f"   загружено {done}/{len(manifest)} ({total_rows:,} строк)")

    if batch:
        combined = pd.concat(batch, ignore_index=True)
        client.insert_df("av2_gold_scenarios", combined)
        total_rows += len(combined)

    print(f"\nЗагружено: {done} файлов, {total_rows:,} строк")

    if quarantined:
        print(f"🚫 КАРАНТИН: {len(quarantined)} файлов не прошли quality gate:")
        for name, probs in quarantined[:10]:
            print(f"   {name}: {probs}")
        print("\nПайплайн КРАСНЫЙ: первопричина — Silver (fillna(0) по координатам).")
        print("Чистые данные загружены, грязные изолированы. Чиним Silver следующим шагом.")
        client.close()
        sys.exit(1)  # ненулевой код выхода = CI/оркестратор остановит конвейер

    print("✅ Пайплайн ЗЕЛЁНЫЙ")
    client.close()


if __name__ == "__main__":
    main()