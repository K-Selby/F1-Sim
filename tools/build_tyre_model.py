import json
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

# ----------------------------
# Config
# ----------------------------

DATA_DIRS = [
    Path("data/tracing_Insight_cache/2021"),
    Path("data/tracing_Insight_cache/2022"),
]

OUTPUT_FILE = Path("configs/tyres.json")

WARMUP_START_LIFE = 2   # ignore out-lap + first lap
WARMUP_END_LIFE = 5     # inclusive
DEG_START_LIFE = 6      # degradation starts here

# ----------------------------
# Helpers
# ----------------------------

def load_csvs():
    files = []
    for d in DATA_DIRS:
        files.extend(sorted(d.glob("*.csv")))
    if not files:
        raise FileNotFoundError(
            "No CSV files found. Expected something like: "
            "data/tracing_Insight_cache/2021/*.csv"
        )
    return files


def normalise_columns(df):
    df = df.rename(columns={
        "Lap Time": "LapTime",
        "Tyre Life": "TyreLife",
        "Compound": "Compound",
        "Driver": "Driver",
        "Stint": "Stint",
        "Lap": "LapNumber"
    })
    return df


# ----------------------------
# Data collection
# ----------------------------

warmup_data = defaultdict(lambda: defaultdict(list))
deg_data = defaultdict(list)

csv_files = load_csvs()

for csv in csv_files:
    df = pd.read_csv(csv)
    df = normalise_columns(df)

    required = {"LapTime", "TyreLife", "Compound", "Driver", "Stint", "LapNumber"}
    if not required.issubset(df.columns):
        continue

    # Parse lap time to seconds
    df["LapTime"] = pd.to_timedelta(df["LapTime"], errors="coerce").dt.total_seconds()

    # Drop junk
    df = df.dropna(subset=["LapTime", "TyreLife", "Compound"])
    df = df[df["TyreLife"] >= 0].copy()

    # Group by driver + stint
    for (_, _), stint in df.groupby(["Driver", "Stint"]):
        if len(stint) < 8:
            continue

        stint = stint.sort_values("LapNumber").reset_index(drop=True)
        compound = stint["Compound"].iloc[0]

        # Baseline = best lap AFTER warm-up window
        post_warm = stint[stint["TyreLife"] >= DEG_START_LIFE]
        if post_warm.empty:
            continue

        baseline = post_warm["LapTime"].min()
        stint["LapTimeDelta"] = stint["LapTime"] - baseline

        # ----------------------------
        # Warm-up
        # ----------------------------
        warmup = stint[
            (stint["TyreLife"] >= WARMUP_START_LIFE) &
            (stint["TyreLife"] <= WARMUP_END_LIFE)
        ].copy()

        for _, r in warmup.iterrows():
            life = int(r["TyreLife"])
            warmup_data[compound][life].append(r["LapTimeDelta"])

        # ----------------------------
        # Degradation
        # ----------------------------
        deg = stint[stint["TyreLife"] >= DEG_START_LIFE].copy()
        deg = deg.reset_index(drop=True)

        for _, r in deg.iterrows():
            deg_data[compound].append(
                (int(r["TyreLife"]), r["LapTimeDelta"])
            )

# ----------------------------
# Model fitting
# ----------------------------

tyre_models = {}

for compound in sorted(set(warmup_data) | set(deg_data)):

    # ---- Warm-up ----
    warmup_curve = []
    for life in range(0, WARMUP_END_LIFE + 1):
        values = warmup_data[compound].get(life, [])
        warmup_curve.append(
            float(np.mean(values)) if values else 0.0
        )

    # ---- Degradation ----
    samples = deg_data.get(compound, [])
    if len(samples) < 50:
        continue

    life = np.array([s[0] for s in samples], dtype=float)
    delta = np.array([s[1] for s in samples], dtype=float)

    # Fit quadratic WITHOUT intercept (baseline already removed)
    A = np.vstack([life, life**2]).T
    coef, _, _, _ = np.linalg.lstsq(A, delta, rcond=None)

    tyre_models[compound] = {
        "model": "warmup_plus_quadratic_deg",
        "warmup": {
            "warmup_laps": WARMUP_END_LIFE + 1,
            "peak_life_reference": DEG_START_LIFE,
            "warmup_delta_by_life": warmup_curve,
        },
        "degradation": {
            "type": "quadratic_no_intercept",
            "coefficients": {
                "linear": float(coef[0]),
                "quadratic": float(coef[1]),
            },
        },
        "data_points": {
            "warmup": sum(len(v) for v in warmup_data[compound].values()),
            "degradation": len(samples),
        },
        "valid_years": "2021-2022",
    }

# ----------------------------
# Write output
# ----------------------------

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

with open(OUTPUT_FILE, "w") as f:
    json.dump(
        {
            "description": (
                "Tyre model built from CSV race data. "
                "Fixed warm-up window (life 2–5) + post-peak quadratic degradation (life>=6). "
                "Baselined per driver-stint."
            ),
            "source": "Tracing Insight CSV race data (2021-2022)",
            "tyres": tyre_models,
        },
        f,
        indent=2,
    )

print(f"Tyre model written to {OUTPUT_FILE}")