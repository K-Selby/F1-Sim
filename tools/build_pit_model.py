import fastf1
import pandas as pd
import numpy as np
import json
from pathlib import Path

# ---------------------------
# Configuration
# ---------------------------
SEASONS = [2021, 2022, 2023, 2024]
SESSION_TYPE = "R"
CACHE_DIR = Path("data/fastf1_cache")
OUTPUT_FILE = Path("configs/pit_model.json")

CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

fastf1.Cache.enable_cache(CACHE_DIR)

# ---------------------------
# Helpers
# ---------------------------
def is_sc_lap(track_status: str) -> bool:
    """
    TrackStatus codes:
    4 = Safety Car
    6 = Virtual Safety Car
    """
    if pd.isna(track_status):
        return False
    return "4" in track_status or "6" in track_status


# ---------------------------
# Main extraction
# ---------------------------
normal_stops = []
sc_stops = []

for year in SEASONS:
    print(f"\n=== Processing season {year} ===")
    schedule = fastf1.get_event_schedule(year, include_testing=False)

    for _, event in schedule.iterrows():
        try:
            session = fastf1.get_session(year, event["EventName"], SESSION_TYPE)
            session.load()
            laps = session.laps

            pits = laps.dropna(subset=["PitInTime", "PitOutTime"]).copy()
            if pits.empty:
                continue

            pits["pit_duration"] = (
                pits["PitOutTime"] - pits["PitInTime"]
            ).dt.total_seconds()

            pits = pits[pits["pit_duration"].between(10, 60)]

            for _, row in pits.iterrows():
                if is_sc_lap(str(row["TrackStatus"])):
                    sc_stops.append(row["pit_duration"])
                else:
                    normal_stops.append(row["pit_duration"])

        except Exception as e:
            print(f" Skipping {event['EventName']} {year}: {e}")

# ---------------------------
# Statistics
# ---------------------------
def stats(data):
    if len(data) == 0:
        return {
            "mean": None,
            "std_dev": None,
            "samples": 0
        }
    return {
        "mean": round(float(np.mean(data)), 3),
        "std_dev": round(float(np.std(data)), 3),
        "samples": len(data),
    }

pit_model = {
    "description": "Pit stop time loss models derived from FastF1 race data",
    "source": "FastF1 race sessions (2021–2024)",
    "models": {
        "NORMAL": stats(normal_stops),
        "SC_VSC": stats(sc_stops),
    },
}

# ---------------------------
# Write config
# ---------------------------
with open(OUTPUT_FILE, "w") as f:
    json.dump(pit_model, f, indent=2)

print("\n Pit model written to configs/pit_model.json")