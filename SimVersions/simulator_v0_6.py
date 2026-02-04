from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # F1-Sim/
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    
from src.sim.RaceManager import RaceManager


def main():
    # Match your existing configs (example: Bahrain 2021)
    SEASON = 2021
    CIRCUIT = "Bahrain Grand Prix"

    # Everyone same strategy for now (tyre-types, not C-codes)
    # Actual C-compounds are resolved via tyre_compounds.json per season + circuit
    FIXED_STRATEGY = ("MEDIUM", "HARD", 20)

    rm = RaceManager(
        season=SEASON,
        circuit_name=CIRCUIT,
        fixed_strategy=FIXED_STRATEGY,
        seed=42,
        driver_noise_scale=0.35,
        start_lap_penalty=4.0,
        formation_lap=True,
    )

    # verbose=True prints lap-by-lap leader/gap
    rm.run(verbose=False)


if __name__ == "__main__":
    main()