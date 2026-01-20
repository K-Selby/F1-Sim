import fastf1
import numpy as np
import json
from pathlib import Path

# ------------------ CONFIG ------------------

SEASONS = [2021, 2022, 2023, 2024]

OUTPUT_PATH = Path("configs/circuits.json")
CACHE_DIR = Path("data/fastf1_cache")

MIN_SC_LAPS = 2          # minimum laps to count as real SC
MAX_LAP_OUTLIER_Z = 3.0  # remove extreme lap time outliers

# -------------------------------------------

fastf1.Cache.enable_cache(str(CACHE_DIR))


def safe_mean(values):
    vals = [v for v in values if v is not None and not np.isnan(v)]
    return float(np.mean(vals)) if vals else None


def zscore_filter(series, z=3.0):
    mean = series.mean()
    std = series.std()
    if std == 0 or np.isnan(std):
        return series
    return series[np.abs((series - mean) / std) <= z]


def build_circuits():
    circuits = {}

    for year in SEASONS:
        print(f"\n=== Processing season {year} ===")

        schedule = fastf1.get_event_schedule(year, include_testing=False)

        for _, event in schedule.iterrows():
            race_name = event["EventName"]

            try:
                session = fastf1.get_session(year, race_name, "R")
                session.load()
            except Exception as e:
                print(f"Skipping {race_name} {year}: {e}")
                continue

            laps = session.laps
            if laps.empty:
                continue

            # ------------------ GREEN FLAG LAPS ONLY ------------------

            green_laps = laps[
                (laps["TrackStatus"] == "1") &
                laps["LapTime"].notna() &
                laps["PitInTime"].isna() &
                laps["PitOutTime"].isna()
            ]

            if green_laps.empty:
                continue

            lap_times = green_laps["LapTime"].dt.total_seconds()
            lap_times = zscore_filter(lap_times, MAX_LAP_OUTLIER_Z)

            if lap_times.empty:
                continue

            total_laps = int(laps["LapNumber"].max())
            base_lap_time = safe_mean(lap_times)
            lap_time_std = float(np.std(lap_times))

            # ------------------ PIT LOSS ------------------

            pit_losses = []

            pit_laps = laps[laps["PitInTime"].notna() & laps["PitOutTime"].notna()]

            for _, pit in pit_laps.iterrows():
                try:
                    prev_lap = laps[
                        (laps["Driver"] == pit["Driver"]) &
                        (laps["LapNumber"] == pit["LapNumber"] - 1)
                    ]

                    next_lap = laps[
                        (laps["Driver"] == pit["Driver"]) &
                        (laps["LapNumber"] == pit["LapNumber"] + 1)
                    ]

                    if not prev_lap.empty and not next_lap.empty:
                        loss = (
                            pit["LapTime"].total_seconds()
                            - 0.5 * (
                                prev_lap.iloc[0]["LapTime"].total_seconds()
                                + next_lap.iloc[0]["LapTime"].total_seconds()
                            )
                        )
                        if 10 < loss < 40:  # sanity bounds
                            pit_losses.append(loss)
                except Exception:
                    continue

            pit_loss = safe_mean(pit_losses)

            # ------------------ SAFETY CAR / VSC ------------------

            track_status = laps["TrackStatus"].astype(str)

            sc_laps = track_status.str.contains("4").sum()
            vsc_laps = track_status.str.contains("6").sum()

            has_sc = sc_laps >= MIN_SC_LAPS
            has_vsc = vsc_laps >= MIN_SC_LAPS

            # ------------------ OVERTAKING METRIC ------------------

            pos = laps[["Driver", "LapNumber", "Position"]].dropna()
            pos["Position"] = pos["Position"].astype(int)

            pos["pos_change"] = pos.groupby("Driver")["Position"].diff().abs()
            avg_pos_change = pos["pos_change"].mean()

            # Normalise: higher = harder to overtake
            overtake_difficulty = 1.0 - min(avg_pos_change / 2.5, 1.0)

            # ------------------ TRACK DEGRADATION ------------------

            track_deg_multiplier = 1.0  # aligned with tyre model

            # ------------------ AGGREGATE ------------------

            if race_name not in circuits:
                circuits[race_name] = {
                    "total_laps": [],
                    "base_lap_time": [],
                    "lap_time_std": [],
                    "track_deg_multiplier": [],
                    "pit_loss": [],
                    "sc_count": 0,
                    "vsc_count": 0,
                    "race_count": 0,
                    "sc_duration": [],
                    "overtake_difficulty": []
                }

            c = circuits[race_name]
            c["total_laps"].append(total_laps)
            c["base_lap_time"].append(base_lap_time)
            c["lap_time_std"].append(lap_time_std)
            c["track_deg_multiplier"].append(track_deg_multiplier)
            c["overtake_difficulty"].append(overtake_difficulty)
            c["race_count"] += 1
            c["sc_count"] += int(has_sc)
            c["vsc_count"] += int(has_vsc)

            if pit_loss:
                c["pit_loss"].append(pit_loss)

            if has_sc:
                c["sc_duration"].append(sc_laps)

    # ------------------ FINALISE JSON ------------------

    final = {}

    for race, c in circuits.items():
        races = c["race_count"]

        final[race] = {
            "total_laps": int(round(np.mean(c["total_laps"]))),
            "base_lap_time": round(safe_mean(c["base_lap_time"]), 2),
            "lap_time_std": round(safe_mean(c["lap_time_std"]), 2),
            "track_deg_multiplier": round(safe_mean(c["track_deg_multiplier"]), 2),
            "pit_loss": round(safe_mean(c["pit_loss"]) or 22.0, 2),
            "sc_probability": round(c["sc_count"] / races, 2),
            "vsc_probability": round(c["vsc_count"] / races, 2),
            "sc_duration_mean": round(safe_mean(c["sc_duration"]) or 0.0, 2),
            "overtake_difficulty": round(safe_mean(c["overtake_difficulty"]), 2)
        }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(final, f, indent=2)

    print(f"\n Circuit model written to {OUTPUT_PATH}")


if __name__ == "__main__":
    build_circuits()