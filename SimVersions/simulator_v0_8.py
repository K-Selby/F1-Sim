# SimVersions/simulator_v0_8.py
"""
v0_8: Multi-car race sim with per-lap top-10 classification output.
- Prints top-10 EVERY lap
- Shows gap to leader and gap to car ahead
- Prints pit events as they happen
- Keeps the "VS Code workaround" (sets project root on sys.path)

Assumptions (based on your project so far):
- configs/ contains: circuits.json, teams.json, tyres.json, tyre_compounds.json
- src/sim/Race_Manager.py exists and works (we DO NOT import it here to avoid path issues)
- We'll run this module directly: python SimVersions/simulator_v0_8.py
"""

from __future__ import annotations

import json
import os
import sys
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# ------------------------------------------------------------
# VS Code / "run as script" workaround: ensure project root on sys.path
# ------------------------------------------------------------
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ------------------------------------------------------------
# Config: change these
# ------------------------------------------------------------
SEASON = "2021"
CIRCUIT = "Bahrain Grand Prix"

# Everyone runs same strategy for now (no agents/optimiser yet)
START_TYRE_LABEL = "MEDIUM"   # SOFT / MEDIUM / HARD (mapped to C1-C5 per race)
END_TYRE_LABEL = "HARD"
PIT_LAP = 20

# Formation / start-lap behaviour (simple)
FORMATION_LAP = True
START_LAP_EXTRA = 4.0  # lap 1 is slower because of standing start / traffic (seconds)

# Randomness
RNG_SEED = 42
USE_LAP_NOISE = True   # uses circuit["lap_time_std"]
USE_PIT_NOISE = True   # uses team["pit_execution_std"]

# Printing
PRINT_TOP_N = 10


# ------------------------------------------------------------
# Data models
# ------------------------------------------------------------
@dataclass
class TeamPerf:
    pace_offset: float
    degradation_factor: float
    pit_execution_std: float


@dataclass
class DriverState:
    code: str
    team: str
    total_time: float = 0.0
    tyre_compound: str = ""        # e.g., "C3"
    tyre_life: int = 0
    pitted: bool = False


# ------------------------------------------------------------
# Load JSON helpers
# ------------------------------------------------------------
def load_json(rel_path: str) -> dict:
    path = os.path.join(PROJECT_ROOT, rel_path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------
# Tyre model (temporary JSON format you already use)
# tyres.json keys: warmup_laps, warmup_start_penalty, peak_life, deg_linear, deg_quadratic
#
# We model delta as:
#   warmup: a penalty that linearly decreases to 0 over warmup_laps
#   deg: after peak_life, add accelerating degradation:
#        deg = (deg_linear * age) + (deg_quadratic * age^2), where age = life - peak_life
#
# Then scaled by:
#   circuit track_deg_multiplier and team degradation_factor
# ------------------------------------------------------------
def tyre_delta_seconds(
    tyres_cfg: dict,
    compound: str,
    life: int,
    track_deg_multiplier: float,
    team_deg_factor: float,
) -> float:
    cfg = tyres_cfg[compound]

    warmup_laps = int(cfg["warmup_laps"])
    warmup_start_penalty = float(cfg["warmup_start_penalty"])
    peak_life = int(cfg["peak_life"])
    deg_linear = float(cfg["deg_linear"])
    deg_quadratic = float(cfg["deg_quadratic"])

    # Warmup penalty (improves towards 0)
    warmup_pen = 0.0
    if warmup_laps > 0 and life < warmup_laps:
        # life=0 -> full penalty, life=warmup_laps-1 -> small penalty
        frac = 1.0 - (life / warmup_laps)
        warmup_pen = warmup_start_penalty * frac

    # Degradation after peak
    deg_pen = 0.0
    if life > peak_life:
        age = life - peak_life
        deg_pen = (deg_linear * age) + (deg_quadratic * (age ** 2))

    return (warmup_pen + deg_pen) * track_deg_multiplier * team_deg_factor


# ------------------------------------------------------------
# Resolve race tyre label -> actual compound (C1-C5) using tyre_compounds.json
# ------------------------------------------------------------
def resolve_compound(
    tyre_compounds_cfg: dict,
    season: str,
    circuit: str,
    label: str,  # SOFT/MEDIUM/HARD
) -> str:
    season_block = tyre_compounds_cfg["season"][season]
    circuit_block = season_block[circuit]
    return circuit_block["compounds"][label]


# ------------------------------------------------------------
# Build starting grid (simple: sort teams by pace_offset, then drivers)
# NOTE: this is NOT real qualifying; just deterministic ordering for now.
# ------------------------------------------------------------
def build_grid(teams_cfg: dict, season: str) -> Tuple[List[DriverState], Dict[str, TeamPerf]]:
    season_teams = teams_cfg[season]
    team_perf: Dict[str, TeamPerf] = {}

    # Store team performance
    for team_name, data in season_teams.items():
        perf = data["performance"]
        team_perf[team_name] = TeamPerf(
            pace_offset=float(perf["pace_offset"]),
            degradation_factor=float(perf["degradation_factor"]),
            pit_execution_std=float(perf["pit_execution_std"]),
        )

    # Sort teams by pace_offset (more negative = faster)
    sorted_teams = sorted(season_teams.keys(), key=lambda t: team_perf[t].pace_offset)

    drivers: List[DriverState] = []
    for team_name in sorted_teams:
        for d in season_teams[team_name]["drivers"]:
            code = d["name"]
            # Filter out reserve/extra drivers if you want only 20;
            # but we’ll keep whatever is in your JSON for that season.
            drivers.append(DriverState(code=code, team=team_name))

    # If you want exactly 20 cars for 2021, uncomment this:
    # drivers = drivers[:20]

    return drivers, team_perf


# ------------------------------------------------------------
# Ranking + gaps
# ------------------------------------------------------------
def classify(drivers: List[DriverState]) -> List[DriverState]:
    return sorted(drivers, key=lambda x: x.total_time)


def format_gap(seconds: float) -> str:
    if seconds < 0.0005:
        return "0.000"
    return f"{seconds:.3f}"


def print_top10_with_gaps(lap: int, classified: List[DriverState], top_n: int) -> None:
    leader_time = classified[0].total_time
    print(f"\n--- Lap {lap:02d} Classification (Top {top_n}) ---")
    for i, d in enumerate(classified[:top_n]):
        gap_leader = d.total_time - leader_time
        gap_ahead = 0.0 if i == 0 else d.total_time - classified[i - 1].total_time
        print(
            f"P{i+1:02d} | {d.code:<3} | {d.team:<16} | "
            f"Total: {d.total_time:8.2f}s | "
            f"+Leader {format_gap(gap_leader)} | "
            f"+Ahead {format_gap(gap_ahead)} | "
            f"{d.tyre_compound}({d.tyre_life})"
        )


# ------------------------------------------------------------
# Main simulation
# ------------------------------------------------------------
def main() -> None:
    random.seed(RNG_SEED)

    circuits_cfg = load_json("configs/circuits.json")
    teams_cfg = load_json("configs/teams.json")
    tyres_cfg = load_json("configs/tyres.json")["tyres"]
    tyre_compounds_cfg = load_json("configs/tyre_compounds.json")

    circuit = circuits_cfg[CIRCUIT]
    total_laps = int(circuit["total_laps"])
    base_lap_time = float(circuit["base_lap_time"])
    lap_time_std = float(circuit["lap_time_std"])
    track_deg_multiplier = float(circuit.get("track_deg_multiplier", 1.0))
    pit_loss = float(circuit["pit_loss"])

    start_compound = resolve_compound(tyre_compounds_cfg, SEASON, CIRCUIT, START_TYRE_LABEL)
    end_compound = resolve_compound(tyre_compounds_cfg, SEASON, CIRCUIT, END_TYRE_LABEL)

    drivers, team_perf = build_grid(teams_cfg, SEASON)

    # Init driver states
    for d in drivers:
        d.tyre_compound = start_compound
        d.tyre_life = 0
        d.total_time = 0.0
        d.pitted = False

    print(f"\nSimulating {CIRCUIT} ({SEASON})")
    if FORMATION_LAP:
        print("Formation lap complete (not timed)")
    print(f"Strategy (all cars): {START_TYRE_LABEL} → {END_TYRE_LABEL} (pit lap {PIT_LAP})")
    print(f"Mapped compounds: {START_TYRE_LABEL}={start_compound}, {END_TYRE_LABEL}={end_compound}\n")

    # Race loop
    for lap in range(1, total_laps + 1):
        # Pit events
        if lap == PIT_LAP:
            print(f"Lap {lap:02d}: PIT WINDOW (everyone pits this lap)")

        for d in drivers:
            perf = team_perf[d.team]

            # Pit stop on PIT_LAP
            if lap == PIT_LAP and not d.pitted:
                pit_noise = 0.0
                if USE_PIT_NOISE and perf.pit_execution_std > 0:
                    pit_noise = random.gauss(0.0, perf.pit_execution_std)
                pit_time = pit_loss + pit_noise

                d.total_time += pit_time
                d.tyre_compound = end_compound
                d.tyre_life = 0
                d.pitted = True

                print(f"  PIT | {d.code:<3} ({d.team}) +{pit_time:.2f}s (noise {pit_noise:+.2f}s)")

            # Lap time components
            tyre_pen = tyre_delta_seconds(
                tyres_cfg,
                d.tyre_compound,
                d.tyre_life,
                track_deg_multiplier,
                perf.degradation_factor,
            )

            # Team pace offset: applied every lap
            # pace_offset is already in seconds (negative = faster)
            team_pace = perf.pace_offset

            # Start-lap extra
            start_extra = START_LAP_EXTRA if lap == 1 else 0.0

            # Lap noise
            noise = 0.0
            if USE_LAP_NOISE and lap_time_std > 0:
                noise = random.gauss(0.0, lap_time_std)

            lap_time = base_lap_time + team_pace + tyre_pen + start_extra + noise
            if lap_time < 0:
                lap_time = 0.0  # safety

            d.total_time += lap_time
            d.tyre_life += 1

        # Classification and per-lap top-10
        classified = classify(drivers)
        print_top10_with_gaps(lap, classified, PRINT_TOP_N)

    # Final results
    classified = classify(drivers)
    print(f"\nFinal Classification — {CIRCUIT} ({SEASON})")
    print(f"Strategy: {START_TYRE_LABEL} → {END_TYRE_LABEL} (pit lap {PIT_LAP})\n")
    for i, d in enumerate(classified[:20], start=1):
        print(f"P{i:02d} | {d.code:<3} | {d.team:<16} | Total: {d.total_time:.2f}s")


if __name__ == "__main__":
    main()