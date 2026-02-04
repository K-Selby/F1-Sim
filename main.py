from __future__ import annotations

from pathlib import Path

from src.sim.RaceManager import RaceManager, CircuitSpec
from src.io.loaders import load_json  # assuming you have this already


def main() -> None:
    project_root = Path(__file__).resolve().parent  # .../F1-Sim

    circuits_json = load_json(str(project_root / "configs" / "circuits.json"), default={})
    teams_json = load_json(str(project_root / "configs" / "teams.json"), default={})
    tyres_json = load_json(str(project_root / "configs" / "tyres.json"), default={})

    # Pick a circuit entry
    circuit_id = "bahrain_2021"
    c = circuits_json.get(circuit_id, {})

    circuit = CircuitSpec(
        name=str(c.get("name", "Bahrain Grand Prix")),
        base_lap_time=float(c.get("base_lap_time", 96.0)),
        track_deg_multiplier=float(c.get("track_deg_multiplier", 1.0)),
    )

    rm = RaceManager(
        circuit=circuit,
        teams_json=teams_json,
        tyres_json=tyres_json,
        start_compound="MEDIUM",
    )

    # Minimal proof it runs end-to-end:
    lap_times = rm.step_lap()
    print(f"Simulated 1 lap for {len(lap_times)} cars.")
    print(lap_times[:5])


if __name__ == "__main__":
    main()