import fastf1
import numpy as np
import json
from pathlib import Path

# ------------------ CONFIG ------------------

SEASONS = [2021, 2022, 2023, 2024]

OUTPUT_PATH = Path("configs/circuits.json")
CACHE_DIR = Path("data/fastf1_cache")

MIN_SC_LAPS = 2          # minimum laps to count as real SC/VSC
MAX_LAP_OUTLIER_Z = 3.0  # remove extreme lap time outliers
PIT_LOSS_FALLBACK = 22.0

# -------------------------------------------

fastf1.Cache.enable_cache(str(CACHE_DIR))


def safe_mean(values):
    vals = [v for v in values if v is not None and not np.isnan(v)]
    return float(np.mean(vals)) if vals else None


def zscore_filter(series, z=3.0):
    series = series.dropna()
    if series.empty:
        return series
    mean = series.mean()
    std = series.std()
    if std == 0 or np.isnan(std):
        return series
    return series[np.abs((series - mean) / std) <= z]


def count_status_laps(laps, code_char: str) -> int:
    """
    TrackStatus is stored per driver-lap.
    This counts UNIQUE LapNumbers where ANY driver saw the status.
    """
    ts = laps["TrackStatus"].astype(str)
    per_lap = ts.str.contains(code_char).groupby(laps["LapNumber"]).any()
    return int(per_lap.sum())


def build_pit_loss(laps, baseline_lap_time: float):
    """
    Approx pit loss using in-lap + out-lap penalty compared to two baseline laps.

    For each driver:
    - in-lap is where PitInTime exists
    - out-lap is next lap where PitOutTime exists
    """
    if baseline_lap_time is None or np.isnan(baseline_lap_time):
        return None

    pit_losses = []

    for drv, dlaps in laps.groupby("Driver"):
        dlaps = dlaps.sort_values("LapNumber")

        in_laps = dlaps[dlaps["PitInTime"].notna() & dlaps["LapTime"].notna()]
        for _, inlap in in_laps.iterrows():
            ln = int(inlap["LapNumber"])
            outlap = dlaps[dlaps["LapNumber"] == ln + 1]
            if outlap.empty:
                continue

            outlap = outlap.iloc[0]
            if outlap["PitOutTime"] is None or (hasattr(outlap["PitOutTime"], "isna") and outlap["PitOutTime"].isna()):
                continue

            try:
                in_t = inlap["LapTime"].total_seconds()
                out_t = outlap["LapTime"].total_seconds() if outlap["LapTime"] is not None else None
                if out_t is None or np.isnan(out_t):
                    continue

                # Pit loss = (in + out) - (2 * baseline)
                loss = (in_t + out_t) - (2.0 * baseline_lap_time)

                # sanity bounds (keeps it realistic)
                if 8.0 < loss < 45.0:
                    pit_losses.append(loss)
            except Exception:
                continue

    return safe_mean(pit_losses)


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

            # ------------------ BASIC METRICS ------------------

            total_laps = int(laps["LapNumber"].max())

            # green-ish racing laps only (per row)
            green_laps = laps[
                (laps["TrackStatus"].astype(str) == "1") &
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

            base_lap_time = safe_mean(lap_times)
            lap_time_std = float(np.std(lap_times))

            # ------------------ PIT LOSS (circuit specific) ------------------

            pit_loss = build_pit_loss(laps, base_lap_time)

            # ------------------ SAFETY CAR / VSC ------------------

            sc_laps = count_status_laps(laps, "4")   # unique lap numbers with SC
            vsc_laps = count_status_laps(laps, "6")  # unique lap numbers with VSC

            has_sc = sc_laps >= MIN_SC_LAPS
            has_vsc = vsc_laps >= MIN_SC_LAPS

            # ------------------ OVERTAKING METRIC ------------------

            pos = laps[["Driver", "LapNumber", "Position"]].dropna()
            pos["Position"] = pos["Position"].astype(int)
            pos["pos_change"] = pos.groupby("Driver")["Position"].diff().abs()
            avg_pos_change = pos["pos_change"].mean()

            overtake_difficulty = 1.0 - min((avg_pos_change or 0.0) / 2.5, 1.0)

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
                    "sc_duration": [],  # store SC laps per race (unique lap count)
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

            if pit_loss is not None:
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
            "pit_loss": round(safe_mean(c["pit_loss"]) or PIT_LOSS_FALLBACK, 2),
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