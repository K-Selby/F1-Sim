import json
import math
from pathlib import Path

import fastf1
import numpy as np


# -------------------------
# config
# -------------------------

CACHE_DIR = Path("data/fastf1_cache")
OUTPUT_DIR = Path("data/circuit_json")

# friendly names for your simulator
CIRCUIT_NAME_MAP = {
    "Bahrain Grand Prix": "Bahrain",
    "Saudi Arabian Grand Prix": "Jeddah",
    "Australian Grand Prix": "Melbourne",
    "Azerbaijan Grand Prix": "Baku",
    "Miami Grand Prix": "Miami",
    "Emilia Romagna Grand Prix": "Imola",
    "Monaco Grand Prix": "Monaco",
    "Spanish Grand Prix": "Barcelona",
    "Canadian Grand Prix": "Montreal",
    "Austrian Grand Prix": "Austria",
    "British Grand Prix": "Silverstone",
    "Hungarian Grand Prix": "Hungaroring",
    "Belgian Grand Prix": "Spa",
    "Dutch Grand Prix": "Zandvoort",
    "Italian Grand Prix": "Monza",
    "Singapore Grand Prix": "Singapore",
    "Japanese Grand Prix": "Suzuka",
    "Qatar Grand Prix": "Qatar",
    "United States Grand Prix": "COTA",
    "Mexico City Grand Prix": "Mexico",
    "São Paulo Grand Prix": "Interlagos",
    "Las Vegas Grand Prix": "LasVegas",
    "Abu Dhabi Grand Prix": "AbuDhabi",
    "French Grand Prix": "PaulRicard",
    "Portuguese Grand Prix": "Portimao",
    "Turkish Grand Prix": "Istanbul",
    "Russian Grand Prix": "Sochi",
    "Styrian Grand Prix": "Austria",
    "Tuscan Grand Prix": "Mugello",
    "70th Anniversary Grand Prix": "Silverstone",
    "Eifel Grand Prix": "Nurburgring",
}


# -------------------------
# helpers
# -------------------------

def safe_name(name: str) -> str:
    cleaned = CIRCUIT_NAME_MAP.get(name, name)
    return "".join(ch for ch in cleaned if ch.isalnum() or ch in ("_", "-"))


def distance(a, b) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def remove_duplicate_points(points, min_dist=5.0):
    print(f"    remove_duplicate_points() input: {len(points)}")
    if not points:
        return []

    filtered = [points[0]]

    for point in points[1:]:
        if distance(filtered[-1], point) >= min_dist:
            filtered.append(point)

    print(f"    remove_duplicate_points() output: {len(filtered)}")
    return filtered


def centre_and_scale(points):
    print(f"    centre_and_scale() input: {len(points)}")
    if not points:
        return []

    xs = np.array([p[0] for p in points], dtype=float)
    ys = np.array([p[1] for p in points], dtype=float)

    min_x, max_x = xs.min(), xs.max()
    min_y, max_y = ys.min(), ys.max()

    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    scale = max(width, height)

    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    print(f"    bounds x=({min_x:.2f}, {max_x:.2f}) y=({min_y:.2f}, {max_y:.2f})")
    print(f"    width={width:.2f} height={height:.2f} scale={scale:.2f}")
    print(f"    centre=({cx:.2f}, {cy:.2f})")

    normalised = []
    for x, y in points:
        nx = (x - cx) / scale
        ny = (y - cy) / scale
        normalised.append([round(nx, 6), round(ny, 6)])

    print(f"    centre_and_scale() output: {len(normalised)}")
    return normalised


def rotate_points(points, angle_deg):
    print(f"    rotate_points() angle: {angle_deg}")
    if not points:
        return []

    angle = math.radians(angle_deg)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    rotated = []
    for x, y in points:
        rx = x * cos_a - y * sin_a
        ry = x * sin_a + y * cos_a
        rotated.append([rx, ry])

    print(f"    rotate_points() output: {len(rotated)}")
    return rotated


def get_reference_lap(session):
    print("    Getting reference lap...")
    laps = session.laps.pick_quicklaps()
    print(f"    Quicklaps count: {len(laps)}")

    if laps.empty:
        print("    No quicklaps, falling back to all laps")
        laps = session.laps

    print(f"    All laps count: {len(laps)}")

    if laps.empty:
        print("    No laps available at all")
        return None

    fastest = laps.pick_fastest()
    if fastest is None:
        print("    Fastest lap is None")
        return None

    try:
        print(f"    Fastest lap driver: {fastest['Driver']}")
        print(f"    Fastest lap time: {fastest['LapTime']}")
    except Exception:
        pass

    return fastest


def extract_track_points_from_lap(lap):
    print("    Extracting telemetry...")
    telemetry = lap.get_telemetry()

    if telemetry is None:
        print("    Telemetry is None")
        return []

    if telemetry.empty:
        print("    Telemetry is empty")
        return []

    print(f"    Telemetry rows: {len(telemetry)}")
    print(f"    Telemetry columns: {list(telemetry.columns)}")

    if "X" not in telemetry.columns or "Y" not in telemetry.columns:
        print("    Missing X/Y columns")
        return []

    points = []
    skipped_nan = 0

    for _, row in telemetry.iterrows():
        x = row["X"]
        y = row["Y"]

        if np.isnan(x) or np.isnan(y):
            skipped_nan += 1
            continue

        points.append((float(x), float(y)))

    print(f"    Valid telemetry points: {len(points)}")
    print(f"    Skipped NaN points: {skipped_nan}")
    return points


def simplify_track(points):
    print("    Simplifying track...")
    points = remove_duplicate_points(points, min_dist=8.0)
    points = centre_and_scale(points)
    print(f"    simplify_track() final count: {len(points)}")
    return points


# -------------------------
# build one circuit
# -------------------------

def build_circuit_json(year: int, event_name: str):
    print()
    print("=" * 70)
    print(f"Loading session: {year} - {event_name}")
    print("=" * 70)

    session = fastf1.get_session(year, event_name, "R")
    print("  Session object created")

    print("  Calling session.load(...)")
    session.load(telemetry=True, laps=True, weather=False, messages=False)
    print("  Session loaded successfully")

    ref_lap = get_reference_lap(session)
    if ref_lap is None:
        print("  Skipped: no lap data")
        return None

    raw_points = extract_track_points_from_lap(ref_lap)
    if not raw_points:
        print("  Skipped: no X/Y telemetry")
        return None

    print(f"  Raw track points: {len(raw_points)}")
    points = simplify_track(raw_points)
    print(f"  Simplified track points: {len(points)}")

    if len(points) < 20:
        print("  Skipped: too few usable points")
        return None

    rotation = 0.0
    try:
        print("  Trying to get circuit info...")
        circuit_info = session.get_circuit_info()
        print(f"  Circuit info found: {type(circuit_info)}")

        if hasattr(circuit_info, "rotation") and circuit_info.rotation is not None:
            rotation = float(circuit_info.rotation)
            print(f"  Applying rotation: {rotation}")
            points = rotate_points(points, rotation)
            points = centre_and_scale(points)
        else:
            print("  No rotation available")
    except Exception as exc:
        print(f"  Circuit info failed: {exc}")

    event = session.event
    official_name = str(event["EventName"])
    friendly_name = safe_name(official_name)

    print(f"  Official name: {official_name}")
    print(f"  Friendly name: {friendly_name}")

    payload = {
        "circuit_name": friendly_name,
        "official_event_name": official_name,
        "year_source": year,
        "meeting_key": int(event["RoundNumber"]) if "RoundNumber" in event else None,
        "rotation_applied_deg": rotation,
        "point_count": len(points),
        "track_points": [{"x": p[0], "y": p[1]} for p in points],
    }

    print(f"  Payload built with {payload['point_count']} points")
    return friendly_name, payload


# -------------------------
# main
# -------------------------

def main():
    print("Starting build_circuit_diagrams.py")
    print(f"Current working directory: {Path.cwd()}")
    print(f"Cache dir: {CACHE_DIR.resolve()}")
    print(f"Output dir: {OUTPUT_DIR.resolve()}")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Directories checked/created")
    print("Enabling FastF1 cache...")
    fastf1.Cache.enable_cache(str(CACHE_DIR))
    print("FastF1 cache enabled")

    years = [2021, 2022, 2023, 2024]
    built = {}
    index = {}

    print(f"Years to process: {years}")

    for year in years:
        print()
        print("#" * 70)
        print(f"Processing year: {year}")
        print("#" * 70)

        try:
            print(f"Requesting schedule for {year}...")
            schedule = fastf1.get_event_schedule(year)
            print(f"Schedule loaded for {year}")
            print(f"Schedule rows: {len(schedule)}")
        except Exception as exc:
            print(f"Could not load schedule for {year}: {exc}")
            continue

        for i, (_, event) in enumerate(schedule.iterrows(), start=1):
            event_name = str(event["EventName"])
            print()
            print(f"[{year} event {i}/{len(schedule)}] {event_name}")

            mapped_name = safe_name(event_name)
            print(f"  mapped_name: {mapped_name}")

            if mapped_name in built:
                print("  Already built, reusing existing circuit")
                index.setdefault(mapped_name, []).append({
                    "year": year,
                    "event_name": event_name,
                    "used_existing": True
                })
                continue

            try:
                result = build_circuit_json(year, event_name)
            except Exception as exc:
                print(f"  Failed: {year} - {event_name} -> {exc}")
                continue

            if result is None:
                print("  No result returned")
                continue

            circuit_name, payload = result
            built[circuit_name] = payload

            out_file = OUTPUT_DIR / f"{circuit_name}.json"
            print(f"  Writing file: {out_file}")

            with out_file.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            index.setdefault(circuit_name, []).append({
                "year": year,
                "event_name": event_name,
                "used_existing": False
            })

            print(f"  Saved: {out_file}")

    index_file = OUTPUT_DIR / "_index.json"
    print(f"Writing index file: {index_file}")

    with index_file.open("w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print()
    print("=" * 70)
    print(f"Built {len(built)} unique circuits")
    print(f"Index saved to {index_file}")
    print("Finished")
    print("=" * 70)


if __name__ == "__main__":
    main()