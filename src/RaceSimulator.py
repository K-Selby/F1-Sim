# src/RaceSimulator.py

from src.sim.RaceManager import RaceManager
import json

circuit_filepath = "configs/circuits.json"


def main(sim_filepath):
    # Load custom simulation config
    with open(sim_filepath, "r") as config_file:
        config_data = json.load(config_file)

    selected_circuit = config_data["circuit"]
    selected_grandprix = config_data["grandprix"].replace("\n", " ")
    race_year = config_data["race_year"]
    starting_grid = config_data["starting_grid"]
    config_characteristics = config_data["circuit_characteristics"]

    # Load default circuit database
    with open(circuit_filepath, "r") as circuit_file:
        circuits = json.load(circuit_file)

    if selected_grandprix not in circuits:
        raise ValueError(f"Circuit '{selected_grandprix}' not found in circuits.json")

    circuit_params = circuits[selected_grandprix]

    # Build final circuit characteristics
    final_characteristics = {}

    for key, value in config_characteristics.items():
        if value == "Default":
            final_characteristics[key] = circuit_params["characteristics"][key]
        else:
            final_characteristics[key] = int(value)

    rm = RaceManager(
        season=race_year,
        grandprix=selected_grandprix,
        circuit=selected_circuit,
        total_laps=circuit_params["total_laps"],
        base_lap_time=circuit_params["base_lap_time"],
        lap_time_std=circuit_params["lap_time_std"],
        pit_loss=circuit_params["pit_loss"],
        pit_speed=circuit_params["pit_lane"]["pit_speed_limit_mps"],
        starting_grid=starting_grid,
        circuit_characteristics=final_characteristics,
        seed=1,
        config_filepath=sim_filepath
    )

    return rm