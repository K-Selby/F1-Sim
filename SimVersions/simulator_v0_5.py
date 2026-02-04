from __future__ import annotations
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # F1-Sim
sys.path.insert(0, str(PROJECT_ROOT))

from sim.RaceManager import Race_Manager


def main():
    # ----------------------------
    # Configuration
    # ----------------------------
    SEASON = "2021"
    CIRCUIT = "Bahrain Grand Prix"

    # Everyone runs same simple strategy (MVP)
    START = "MEDIUM"
    END = "HARD"
    PIT_LAP = 20

    # ----------------------------
    # Run
    # ----------------------------
    rm = Race_Manager(
        circuits_path="configs/circuits.json",
        teams_path="configs/teams.json",
        tyres_path="configs/tyres.json",
        tyre_compounds_path="configs/tyre_compounds.json",
        seed=7,
    )

    cars = rm.run(
        season=SEASON,
        circuit_name=CIRCUIT,
        start_semantic=START,
        end_semantic=END,
        pit_lap=PIT_LAP,
        include_formation_lap=True,
        include_start_lap_penalty=True,
        start_lap_penalty=4.0,
        enable_noise=True,
        print_interval=0,  # set to 1 if you want per-lap leader prints
    )

    print(f"\nFinal Classification — {CIRCUIT} ({SEASON})")
    print(f"Strategy: {START} → {END} (pit lap {PIT_LAP})\n")

    for i, car in enumerate(cars, start=1):
        print(f"P{i:02d} | {car.driver.code:<3} | {car.team_name:<18} | Total: {car.total_time:.2f}s")


if __name__ == "__main__":
    main()