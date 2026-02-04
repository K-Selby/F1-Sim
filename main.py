# main.py

import json

from src.sim.RaceManager import RaceManager, CircuitSpec


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    # Load configs
    circuits = load_json("configs/circuits.json")
    teams = load_json("configs/teams.json")
    tyres = load_json("configs/tyres.json")
    tyre_compounds = load_json("configs/tyre_compounds.json")

    season = "2021"
    circuit_name = "Bahrain Grand Prix"

    c = circuits[circuit_name]
    circuit = CircuitSpec(
        name=circuit_name,
        total_laps=int(c["total_laps"]),
        base_lap_time=float(c["base_lap_time"]),
        track_deg_multiplier=float(c["track_deg_multiplier"]),
        pit_loss=float(c["pit_loss"]),
    )

    rm = RaceManager(
        circuit=circuit,
        teams_json=teams,
        tyres_json=tyres,
        tyre_compounds_json=tyre_compounds,
        season=season,
        circuit_name=circuit_name,
    )

    rm.run_race()


if __name__ == "__main__":
    main()