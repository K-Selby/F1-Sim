import json

from src.sim.RaceManager import RaceManager


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    circuits = load_json("configs/circuits.json")
    teams = load_json("configs/teams.json")["2021"]
    tyres = load_json("configs/tyres.json")

    circuit = circuits["Bahrain Grand Prix"]

    rm = RaceManager(
        base_lap_time=circuit["base_lap_time"],
        track_deg_multiplier=circuit["track_deg_multiplier"],
        total_laps=circuit["total_laps"],
        teams_json=teams,
        tyres_json=tyres,
    )

    rm.run()


if __name__ == "__main__":
    main()