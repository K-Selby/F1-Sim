import fastf1

# Enable caching (folder must exist)
fastf1.Cache.enable_cache("fastf1_cache")

# Load a known race session
session = fastf1.get_session(2023, "Bahrain", "R")
session.load()

# Basic sanity checks
print("Event:", session.event["EventName"])
print("Year:", session.event["EventDate"].year)
print("Total laps:", session.total_laps)

# Access lap data
laps = session.laps
print("Total lap records:", len(laps))
print("Columns:", list(laps.columns))