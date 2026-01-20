import json
from pathlib import Path
from collections import defaultdict

import fastf1
import numpy as np

# ----------------------------
# Configuration
# ----------------------------

YEARS = range(2021, 2025)

RACES = [
    "Bahrain Grand Prix",
    "Saudi Arabian Grand Prix",
    "Australian Grand Prix",
    "Emilia Romagna Grand Prix",
    "Miami Grand Prix",
    "Spanish Grand Prix",
    "Monaco Grand Prix",
    "Canadian Grand Prix",
    "British Grand Prix",
    "Austrian Grand Prix",
    "Hungarian Grand Prix",
    "Belgian Grand Prix",
    "Dutch Grand Prix",
    "Italian Grand Prix",
    "Singapore Grand Prix",
    "Japanese Grand Prix",
    "Qatar Grand Prix",
    "United States Grand Prix",
    "Mexico City Grand Prix",
    "Sao Paulo Grand Prix",
    "Las Vegas Grand Prix",
    "Abu Dhabi Grand Prix",
] 

CACHE_DIR = Path("data/fastf1_cache")
OUTPUT_FILE = Path("configs/tyres.json")

# ----------------------------
# Setup
# ----------------------------

CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

fastf1.Cache.enable_cache(str(CACHE_DIR))

# ----------------------------
# Data containers
# ----------------------------

# tyre -> list of (tyre_life, lap_time_seconds)
tyre_data = defaultdict(list)

# ----------------------------
# Extraction
# ----------------------------

for year in YEARS:
    print(f"\n=== Processing season {year} ===")
    for race in RACES:
        try:
            session = fastf1.get_session(year, race, "R")
            session.load(laps=True, telemetry=False, weather=False)

            laps = session.laps

            if laps.empty:
                continue

            # keep only valid race laps with tyre info
            laps = laps[
                (laps["LapTime"].notna()) &
                (laps["Compound"].notna()) &
                (laps["TyreLife"].notna()) &
                (~laps["Deleted"])
            ]

            for _, lap in laps.iterrows():
                compound = lap["Compound"]
                tyre_life = int(lap["TyreLife"])
                lap_time = lap["LapTime"].total_seconds()

                tyre_data[compound].append((tyre_life, lap_time))

        except Exception:
            # expected for some races – skip silently
            continue

# ----------------------------
# Build tyre model parameters
# ----------------------------

tyre_models = {}

for compound, samples in tyre_data.items():
    if len(samples) < 100:
        continue  # insufficient data

    life = np.array([s[0] for s in samples])
    lap_time = np.array([s[1] for s in samples])

    # Fit simple non-linear degradation: a + b*x + c*x^2
    coeffs = np.polyfit(life, lap_time, deg=2)

    tyre_models[compound] = {
        "model": "quadratic",
        "coefficients": {
            "a": float(coeffs[2]),
            "b": float(coeffs[1]),
            "c": float(coeffs[0]),
        },
        "data_points": int(len(samples)),
        "valid_years": "2021-2024",
    }

# ----------------------------
# Write config file
# ----------------------------

with open(OUTPUT_FILE, "w") as f:
    json.dump(
        {
            "description": "Tyre degradation models fitted from FastF1 race data",
            "source": "FastF1 (2021-2024 race sessions)",
            "tyres": tyre_models,
        },
        f,
        indent=2,
    )

print(f"\nDone. Tyre model written to: {OUTPUT_FILE}")