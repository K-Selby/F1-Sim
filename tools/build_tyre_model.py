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
    "Mexican Grand Prix",
    "Sao Paulo Grand Prix",
    "Las Vegas Grand Prix",
    "Abu Dhabi Grand Prix",
]

CACHE_DIR = Path("data/fastf1_cache")
TYRE_COMPOUND_FILE = Path("configs/tyre_compounds.json")
OUTPUT_FILE = Path("configs/tyres.json")

# ----------------------------
# Setup
# ----------------------------

CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

fastf1.Cache.enable_cache(str(CACHE_DIR))

with open(TYRE_COMPOUND_FILE, "r") as f:
    tyre_compound_map = json.load(f)["season"]

# ----------------------------
# Data containers
# ----------------------------

# compound -> list of (tyre_life, lap_time_seconds)
tyre_data = defaultdict(list)

# ----------------------------
# Extraction
# ----------------------------

for year in YEARS:
    print(f"\n=== Processing season {year} ===")

    season_map = tyre_compound_map.get(str(year), {})

    for race in RACES:
        if race not in season_map:
            continue

        try:
            session = fastf1.get_session(year, race, "R")
            session.load(laps=True, telemetry=False, weather=False)

            laps = session.laps
            if laps.empty:
                continue

            laps = laps[
                (laps["LapTime"].notna()) &
                (laps["Compound"].notna()) &
                (laps["TyreLife"].notna()) &
                (~laps["Deleted"])
            ]

            compound_mapping = season_map[race]["compounds"]

            for _, lap in laps.iterrows():
                base_compound = lap["Compound"]

                # Handle dry compounds via Pirelli mapping
                if base_compound in ["SOFT", "MEDIUM", "HARD"]:
                    if base_compound not in compound_mapping:
                        continue
                    compound = compound_mapping[base_compound]

                # Handle wet tyres directly
                elif base_compound in ["INTERMEDIATE", "WET"]:
                    compound = base_compound

                else:
                    continue

                tyre_life = int(lap["TyreLife"])
                lap_time = lap["LapTime"].total_seconds()

                tyre_data[compound].append((tyre_life, lap_time))

        except Exception:
            continue

# ----------------------------
# Build tyre models
# ----------------------------

tyre_models = {}

for compound, samples in tyre_data.items():
    if len(samples) < 100:
        continue

    life = np.array([s[0] for s in samples])
    lap_time = np.array([s[1] for s in samples])

    # Quadratic degradation model
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
# Write output
# ----------------------------

with open(OUTPUT_FILE, "w") as f:
    json.dump(
        {
            "description": "Tyre degradation models by Pirelli compound (C1–C5, Inter, Wet)",
            "source": "FastF1 + Pirelli compound allocations (2021–2024)",
            "tyres": tyre_models,
        },
        f,
        indent=2,
    )

print(f"\nDone. Tyre model written to: {OUTPUT_FILE}")