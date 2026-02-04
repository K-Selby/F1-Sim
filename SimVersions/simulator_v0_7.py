# SimVersions/simulator_v0_7.py
from __future__ import annotations

import sys
from pathlib import Path

# ----------------------------
# VS Code "run file" workaround:
# ensures project root is on sys.path even when running this file directly
# ----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../F1-Sim
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.sim.RaceManager import Race_Manager  # noqa: E402


def main() -> None:
    sim = Race_Manager(
        season="2021",
        circuit_name="Bahrain Grand Prix",

        # Everyone runs the same simple strategy for now
        strategy_start_tyre="MEDIUM",
        strategy_end_tyre="HARD",
        pit_lap=20,

        # Seeded randomness (REPEATABLE runs)
        seed=42,

        # Formation/start behaviour
        include_formation_lap=True,
        lap1_start_penalty=4.0,  # adds seconds to lap 1 (standing start + traffic)

        # Noise switches
        enable_lap_noise=True,       # uses circuits.json -> lap_time_std
        enable_pit_noise=True,       # uses teams.json -> pit_execution_std
    )
    sim.run()


if __name__ == "__main__":
    main()