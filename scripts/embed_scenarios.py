"""Векторизация Gold-сценариев: 40D вектор + payload -> data/vectors/scenarios.parquet."""
import numpy as np
import pandas as pd
from pathlib import Path

GOLD_DIR = Path("data/gold/av2/val")
OUT = Path("data/vectors/scenarios.parquet")
N_PTS = 16          # точек формы траектории (x,y) -> 32 координаты
DT = 0.1            # 10 Гц
AGG_COLS = ["mean_speed", "max_speed", "std_speed",
            "mean_acceleration", "max_acceleration"]


def shape_coords(df: pd.DataFrame) -> np.ndarray:
    """32 координаты формы траектории фокального агента, инвариантные к повороту/масштабу."""
    focal = df[df["track_id"] == df["focal_track_id"].iloc[0]]
    focal = focal[focal["observed"].astype(bool)].sort_values("timestep")
    if len(focal) < 2:
        return np.zeros(N_PTS * 2)
    x = focal["position_x"].to_numpy(float)
    y = focal["position_y"].to_numpy(float)
    h0 = float(focal["heading"].iloc[0])
    dx, dy = x - x[0], y - y[0]
    c, s = np.cos(-h0), np.sin(-h0)
    rx, ry = dx * c - dy * s, dx * s + dy * c
    t = np.linspace(0, 1, len(rx))
    ti = np.linspace(0, 1, N_PTS)
    sx, sy = np.interp(ti, t, rx), np.interp(ti, t, ry)
    scale = np.hypot(rx[-1], ry[-1]) or 1.0
    return np.concatenate([sx / scale, sy / scale])


def vectorize(df: pd.DataFrame) -> np.ndarray:
    aggs = [float(df[c].dropna().iloc[0]) if df[c].notna().any() else 0.0
            for c in AGG_COLS]
    mean_yaw = float(df["yaw_rate"].mean()) if df["yaw_rate"].notna().any() else 0.0
    duration = float(df["timestep"].max() - df["timestep"].min()) * DT
    n_tracks = float(df["track_id"].nunique())
    vec = np.array(aggs + [mean_yaw, duration, n_tracks] + list(shape_coords(df)))
    return np.nan_to_num(vec, nan=0.0)


def main():
    manifest = pd.read_parquet("data/gold/manifest.parquet")
    print(f"Векторизация {len(manifest)} сценариев...")
    rows = []
    for i, r in manifest.iterrows():
        df = pd.read_parquet(GOLD_DIR / r["relative_path"])
        vec = vectorize(df)
        rows.append({
            "scenario_id": str(df["scenario_id"].iloc[0]),
            "city": str(df["city"].iloc[0]),
            "source_file": r["relative_path"],
            "max_speed": float(df["max_speed"].dropna().iloc[0]) if df["max_speed"].notna().any() else 0.0,
            "n_tracks": int(df["track_id"].nunique()),
            **{f"v{j}": vec[j] for j in range(40)},
        })
        if (i + 1) % 5000 == 0:
            print(f"   {i + 1}/{len(manifest)}")

    out = pd.DataFrame(rows)
    vcols = [f"v{j}" for j in range(40)]
    mu, sd = out[vcols].mean(), out[vcols].std().replace(0, 1)
    out[vcols] = (out[vcols] - mu) / sd   # z-score по датасету

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    print(f"✅ Сохранено: {OUT}, форма {out.shape}")
    print(out[vcols].describe().loc[["mean", "std"]].round(3).to_string())


if __name__ == "__main__":
    main()