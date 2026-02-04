import fastf1
from pathlib import Path

# -------------------------------
# Cache location
# -------------------------------
CACHE_DIR = Path("data/fastf1_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

fastf1.Cache.enable_cache(CACHE_DIR)

# -------------------------------
# Seasons you want cached
# -------------------------------
SEASONS = [2021, 2022, 2023, 2024]

# Session types to cache
SESSION_TYPES = ["R"]  # Race only (change to ["FP1","FP2","FP3","Q","R"] if needed)

print(f"FastF1 cache directory: {CACHE_DIR.resolve()}")
print("Starting cache build...\n")

# -------------------------------
# Cache all races
# -------------------------------
for season in SEASONS:
    print(f"Season {season}")
    schedule = fastf1.get_event_schedule(season)

    for _, event in schedule.iterrows():
        event_name = event["EventName"]

        for session_type in SESSION_TYPES:
            try:
                print(f"  Caching {event_name} ({session_type})")
                session = fastf1.get_session(season, event_name, session_type)
                session.load()
            except Exception as e:
                print(f"    Skipped {event_name} ({session_type}) — {e}")

print("\nFastF1 cache build complete.")