from clickhouse_connect import get_client
import os

client = get_client(host='localhost', port=8124, username='default',
                    password=os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_dev_password'))

# === АВТОМАТИЧЕСКОЕ ОПРЕДЕЛЕНИЕ СХЕМЫ ===
desc = client.query("DESCRIBE TABLE av2_gold_scenarios")
cols = {r[0]: r[1] for r in desc.result_rows}

print("=" * 60)
print("АНАЛИТИКА ПО ДАТАСЕТУ ARGOVERSE 2 (ClickHouse)")
print("=" * 60)
print(f"\n📋 Доступные столбцы ({len(cols)}):")
for name, typ in cols.items():
    print(f"   {name} ({typ})")

# === ЗАПРОС 1: ОБЩАЯ СТАТИСТИКА ===
result = client.query("""
    SELECT 
        count() as total_rows,
        uniqExact(scenario_file) as total_scenarios
    FROM av2_gold_scenarios
""")
row = result.result_rows[0]
print(f"\n📈 Общая статистика:")
print(f"   Всего записей: {row[0]:,}")
print(f"   Сценариев: {row[1]:,}")

if 'agent_id' in cols:
    r = client.query("SELECT uniqExact(agent_id) FROM av2_gold_scenarios")
    print(f"   Уникальных агентов: {r.result_rows[0][0]:,}")
if 'track_id' in cols:
    r = client.query("SELECT uniqExact(track_id) FROM av2_gold_scenarios")
    print(f"   Уникальных треков: {r.result_rows[0][0]:,}")

# === ЗАПРОС 2: СТАТИСТИКА СКОРОСТИ ===
if 'speed' in cols:
    result = client.query("""
        SELECT 
            round(avg(speed), 2) as avg_speed,
            round(max(speed), 2) as max_speed,
            round(min(speed), 2) as min_speed,
            round(stddevPop(speed), 2) as std_speed
        FROM av2_gold_scenarios
        WHERE speed > 0 AND speed < 100
    """)
    r = result.result_rows[0]
    print(f"\n🚗 Скорость (м/с):")
    print(f"   Средняя: {r[0]}")
    print(f"   Максимальная: {r[1]}")
    print(f"   Минимальная (ненулевая): {r[2]}")
    print(f"   Стд. отклонение: {r[3]}")

# === ЗАПРОС 3: СТАТИСТИКА УСКОРЕНИЯ ===
if 'acceleration' in cols:
    result = client.query("""
        SELECT 
            round(avg(acceleration), 2) as avg_accel,
            round(max(acceleration), 2) as max_accel,
            round(min(acceleration), 2) as min_accel
        FROM av2_gold_scenarios
        WHERE abs(acceleration) > 0.01 AND abs(acceleration) < 20
    """)
    r = result.result_rows[0]
    print(f"\n⚡ Ускорение (м/с²):")
    print(f"   Среднее: {r[0]}")
    print(f"   Максимальное: {r[1]}")
    print(f"   Минимальное (торможение): {r[2]}")

# === ЗАПРОС 4: ТОП-10 ЭКСТРЕМАЛЬНЫХ СЦЕНАРИЕВ (по максимальной скорости) ===
if 'speed' in cols:
    result = client.query("""
        SELECT 
            scenario_file,
            round(max(speed), 2) as max_speed,
            count() as observations
        FROM av2_gold_scenarios
        WHERE speed > 0
        GROUP BY scenario_file
        ORDER BY max_speed DESC
        LIMIT 10
    """)
    print(f"\n🏆 Топ-10 сценариев с максимальной скоростью:")
    for i, r in enumerate(result.result_rows, 1):
        print(f"   {i}. {r[0]} — {r[1]} м/с ({r[2]} наблюдений)")

# === ЗАПРОС 5: СРЕДНИЕ ПОКАЗАТЕЛИ ПО СЦЕНАРИЯМ ===
if 'speed' in cols and 'acceleration' in cols:
    result = client.query("""
        SELECT 
            round(avg(mean_speed), 2) as avg_mean_speed,
            round(max(max_speed), 2) as overall_max_speed,
            round(avg(mean_acceleration), 4) as avg_mean_accel,
            round(max(max_acceleration), 2) as overall_max_accel
        FROM av2_gold_scenarios
        WHERE mean_speed > 0
    """)
    r = result.result_rows[0]
    print(f"\n📊 Сводка агрегированных фич:")
    print(f"   Средняя mean_speed по всем записям: {r[0]} м/с")
    print(f"   Максимальная max_speed во всём датасете: {r[1]} м/с")
    print(f"   Средняя mean_acceleration: {r[2]} м/с²")
    print(f"   Максимальная max_acceleration: {r[3]} м/с²")

# === ЗАПРОС 6: СКОЛЬКО ДАННЫХ МЫ РЕАЛЬНО ЗАЛИЛИ ===
result = client.query("""
    SELECT 
        formatReadableSize(sum(bytes_on_disk)) as total_size,
        sum(rows) as total_rows
    FROM system.parts 
    WHERE table = 'av2_gold_scenarios' AND active = 1
""")
r = result.result_rows[0]
print(f"\n💾 Физическое хранение в ClickHouse:")
print(f"   Размер на диске: {r[0]}")
print(f"   Всего строк в хранилище: {r[1]:,}")

client.close()