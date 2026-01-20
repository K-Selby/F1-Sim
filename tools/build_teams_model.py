import fastf1
import numpy as np
import json
from pathlib import Path
from collections import defaultdict

# ------------------ CONFIG ------------------

SEASONS = [2021, 2022, 2023, 2024]

CACHE_DIR = Path("data/fastf1_cache")
OUTPUT_PATH = Path("configs/teams.json")

MIN_PIT_SAMPLES = 10

PACE_CLAMP = (-2.0, 2.0)
DEG_CLAMP = (0.85, 1.15)
PIT_STD_CLAMP = (0.6, 2.5)

# -------------------------------------------

fastf1.Cache.enable_cache(str(CACHE_DIR))


def clamp(x, lo, hi):
    return max(lo, min(x, hi))


def safe_mean(vals):
    vals = [v for v in vals if v is not None and not np.isnan(v)]
    return float(np.mean(vals)) if vals else None


def build_teams():
    teams_by_season = {}

    for year in SEASONS:
        print(f"\n=== Processing season {year} ===")

        schedule = fastf1.get_event_schedule(year, include_testing=False)

        team_lap_times = defaultdict(list)
        team_deg_samples = defaultdict(list)
        team_pit_deltas = defaultdict(list)
        team_drivers = defaultdict(dict)

        for _, event in schedule.iterrows():
            race_name = event["EventName"]

            try:
                session = fastf1.get_session(year, race_name, "R")
                session.load()
            except Exception:
                continue

            laps = session.laps
            if laps.empty:
                continue

            # ------------------ DRIVER / TEAM MAPPING ------------------

            for drv in laps["Driver"].unique():
                sub = laps[laps["Driver"] == drv].iloc[0]
                team = sub["Team"]
                num = int(sub["DriverNumber"])
                team_drivers[team][drv] = num

            # ------------------ GREEN FLAG LAPS ------------------

            green = laps[
                (laps["TrackStatus"] == "1") &
                laps["LapTime"].notna() &
                laps["PitInTime"].isna() &
                laps["PitOutTime"].isna()
            ]

            for _, lap in green.iterrows():
                team_lap_times[lap["Team"]].append(
                    lap["LapTime"].total_seconds()
                )

            # ------------------ TYRE DEGRADATION ------------------

            for team, g in green.groupby("Team"):
                stints = g.groupby(["Driver", "Stint"])
                for _, stint in stints:
                    if len(stint) < 5:
                        continue
                    laps_sec = stint["LapTime"].dt.total_seconds()
                    deg = np.polyfit(range(len(laps_sec)), laps_sec, 1)[0]
                    if 0 < deg < 0.25:
                        team_deg_samples[team].append(deg)

            # ------------------ PIT EXECUTION ------------------

            pit_laps = laps[laps["PitInTime"].notna() & laps["PitOutTime"].notna()]

            for _, pit in pit_laps.iterrows():
                team = pit["Team"]
                drv = pit["Driver"]
                lap_no = pit["LapNumber"]

                prev = laps[(laps["Driver"] == drv) & (laps["LapNumber"] == lap_no - 1)]
                next_ = laps[(laps["Driver"] == drv) & (laps["LapNumber"] == lap_no + 1)]

                if prev.empty or next_.empty:
                    continue

                delta = (
                    pit["LapTime"].total_seconds()
                    - 0.5 * (
                        prev.iloc[0]["LapTime"].total_seconds()
                        + next_.iloc[0]["LapTime"].total_seconds()
                    )
                )

                if 5 < delta < 40:
                    team_pit_deltas[team].append(delta)

        # ------------------ FINALISE SEASON ------------------

        all_laps = []
        for laps in team_lap_times.values():
            all_laps.extend(laps)

        season_mean = np.mean(all_laps)

        season_data = {}

        for team, laps in team_lap_times.items():
            pace_offset = clamp(
                np.mean(laps) - season_mean,
                *PACE_CLAMP
            )

            deg_factor = clamp(
                1.0 + safe_mean(team_deg_samples[team] or [0.0]),
                *DEG_CLAMP
            )

            pit_std = (
                np.std(team_pit_deltas[team])
                if len(team_pit_deltas[team]) >= MIN_PIT_SAMPLES
                else 1.0
            )
            pit_std = clamp(pit_std, *PIT_STD_CLAMP)

            season_data[team] = {
                "drivers": [
                    {"name": d, "number": n}
                    for d, n in team_drivers[team].items()
                ],
                "performance": {
                    "pace_offset": round(pace_offset, 3),
                    "degradation_factor": round(deg_factor, 2),
                    "pit_execution_std": round(pit_std, 2)
                },
                "strategy_profile": {
                    "risk_tolerance": 0.5,
                    "undercut_bias": 0.5,
                    "overcut_bias": 0.5
                }
            }

        teams_by_season[str(year)] = season_data

    # ------------------ WRITE JSON ------------------

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(teams_by_season, f, indent=2)

    print(f"\n Teams model written to {OUTPUT_PATH}")


if __name__ == "__main__":
    build_teams()