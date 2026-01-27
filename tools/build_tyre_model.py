import json
from pathlib import Path
from collections import defaultdict

import fastf1
import numpy as np
import pandas as pd

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

CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

fastf1.Cache.enable_cache(str(CACHE_DIR))

with open(TYRE_COMPOUND_FILE, "r") as f:
    tyre_compound_map = json.load(f)["season"]

# compound -> list of (tyre_life, lap_delta_seconds)
tyre_data = defaultdict(list)

for year in YEARS:
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

            # Keep only usable laps
            laps = laps[
                laps["LapTime"].notna()
                & laps["Compound"].notna()
                & laps["TyreLife"].notna()
                & (~laps["Deleted"])
            ].copy()

            # Remove pit in/out laps (easy, high impact)
            if "PitInTime" in laps.columns:
                laps = laps[laps["PitInTime"].isna()]
            if "PitOutTime" in laps.columns:
                laps = laps[laps["PitOutTime"].isna()]

            compound_mapping = season_map[race]["compounds"]

            # Map compounds to C1–C5 / INTERMEDIATE / WET
            def map_compound(row):
                c = row["Compound"]
                if c in ["SOFT", "MEDIUM", "HARD"]:
                    return compound_mapping.get(c)
                if c in ["INTERMEDIATE", "WET"]:
                    return c
                return None

            laps["PirelliCompound"] = laps.apply(map_compound, axis=1)
            laps = laps[laps["PirelliCompound"].notna()].copy()

            # Group by driver + stint (stint = same tyre set)
            if "Driver" not in laps.columns or "Stint" not in laps.columns:
                continue

            for (driver, stint), stint_laps in laps.groupby(["Driver", "Stint"]):
                if len(stint_laps) < 5:
                    continue

                compound = stint_laps["PirelliCompound"].iloc[0]

                # Sort in running order
                stint_laps = stint_laps.sort_values("LapNumber")

                # Ignore first 2 laps of the stint (warm-up/out-lap effects)
                core = stint_laps.iloc[2:].copy()
                if len(core) < 3:
                    continue

                lap_times = core["LapTime"].dt.total_seconds().to_numpy()
                tyre_life = core["TyreLife"].astype(int).to_numpy()

                # Baseline = best lap inside this stint core (simple + robust enough)
                baseline = np.min(lap_times)
                lap_delta = lap_times - baseline

                for life, d in zip(tyre_life, lap_delta):
                    tyre_data[compound].append((int(life), float(d)))

        except Exception:
            continue

# Fit models
tyre_models = {}
for compound, samples in tyre_data.items():
    life = np.array([s[0] for s in samples], dtype=float)
    delta = np.array([s[1] for s in samples], dtype=float)

    # Quadratic delta fit: delta = q*life^2 + l*life + const
    q, l, c0 = np.polyfit(life, delta, deg=2)

    tyre_models[compound] = {
        "model": "quadratic_delta_stint_baselined",
        "coefficients": {
            "linear": float(l),
            "quadratic": float(q),
        },
        "data_points": int(len(samples)),
        "valid_years": "2021-2024",
    }

with open(OUTPUT_FILE, "w") as f:
    json.dump(
        {
            "description": "Tyre degradation delta models by Pirelli compound (C1-C5, Inter, Wet). Deltas are baselined per driver-stint.",
            "source": "FastF1 + Pirelli compound allocations (2021-2024)",
            "tyres": tyre_models,
        },
        f,
        indent=2,
    )

print(f"Done. Tyre model written to: {OUTPUT_FILE}")