"""Загрузка Gold -> ClickHouse с schema-контрактом и quality gate."""
import json
import sys
import os
from pathlib import Path

import numpy as np
import pandas as pd
from clickhouse_connect import get_client

CONTRACT_PATH = Path("config/gold_schema_contract.json")
GOLD_DIR = Path("data/gold/av2/val")
BATCH = 500
SPEED_LIMIT = 50.0          # м/с: физический порог выброса
ROW_BAD_FRACTION = 0.01     # >1% плохих строк в файле = системная проблема
FILE_BAD_FRACTION = 0.001   # >0.1% плохих файлов = пайплайн красный


class SchemaDriftError(Exception):
    """Схема данных разошлась с контрактом."""


def load_contract():
    if not CONTRACT_PATH.exists():
        raise SchemaDriftError(
            f"Контракт не найден: {CONTRACT_PATH}. Запусти scripts/generate_schema_contract.py"
        )
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def check_schema(df: pd.DataFrame, expected: set, context: str):
    actual = set(df.columns)
    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        raise SchemaDriftError(
            f"{context}: дрейф схемы. Отсутствуют: {sorted(missing)}. "
            f"Неожиданные: {sorted(extra)}"
        )


def quality_gate(df: pd.DataFrame):
    """
    Возвращает (df, problems, n_cleaned).
    Единичные выбросы -> обнуляются на уровне строк, файл остаётся.
    Системные проблемы -> problems непуст, файл в карантин.
    """
    if len(df) == 0:
        return df, ["пустой файл"], 0
    if "speed" not in df.columns:
        return df, [], 0

    bad = df["speed"].abs() > SPEED_LIMIT
    n_bad = int(bad.sum())
    if n_bad == 0:
        return df, [], 0

    fraction = n_bad / len(df)
    if fraction > ROW_BAD_FRACTION:
        return df, [f"speed>{SPEED_LIMIT}: {n_bad} строк ({fraction:.1%}) — системно"], 0

    cols = [c for c in ["speed", "velocity_x", "velocity_y",
                        "acceleration", "acceleration_x", "acceleration_y"]
            if c in df.columns]
    df.loc[bad, cols] = np.nan
    return df, [], n_bad


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

    desc = client.query("DESCRIBE TABLE av2_gold_scenarios")
    table_cols = [r[0] for r in desc.result_rows]
    if set(table_cols) != expected:
        raise SchemaDriftError(f"Схема таблицы CH != контракт: {set(table_cols) ^ expected}")

    manifest = pd.read_parquet("data/gold/manifest.parquet")
    print(f"📊 Загрузка {len(manifest)} файлов (контракт + quality gate)...")

    quarantined = []
    cleaned_total = 0
    batch, done, total_rows = [], 0, 0

    for _, row in manifest.iterrows():
        path = GOLD_DIR / row["relative_path"]
        try:
            df = pd.read_parquet(path)
            df["scenario_file"] = row["relative_path"]

            # ГЕЙТ 1: схема
            check_schema(df, expected, row["relative_path"])

            # ГЕЙТ 2: качество (чистка строк + вердикт по файлу)
            df, problems, n_cleaned = quality_gate(df)
            cleaned_total += n_cleaned
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

    # === ИТОГОВЫЙ ВЕРДИКТ ===
    bad_fraction = len(quarantined) / max(len(manifest), 1)
    print(f"\nЗагружено: {done} файлов, {total_rows:,} строк")
    print(f"🧹 Очищено на уровне строк: {cleaned_total:,} выбросов (файлы сохранены)")
    if quarantined:
        print(f"🚫 КАРАНТИН: {len(quarantined)} файлов ({bad_fraction:.2%}):")
        for name, probs in quarantined[:10]:
            print(f"   {name}: {probs}")
    if bad_fraction > FILE_BAD_FRACTION:
        print("\nПайплайн КРАСНЫЙ: доля карантина выше допуска.")
        client.close()
        sys.exit(1)
    print("✅ Пайплайн ЗЕЛЁНЫЙ (с DQ-отчётом выше)")
    client.close()


if __name__ == "__main__":
    main()