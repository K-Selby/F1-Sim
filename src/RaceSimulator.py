# src/RaceSimulator.py

from src.sim.RaceManager import RaceManager
import json

# ===== FILE PATHS =====
circuit_filepath = "configs/circuits.json"

# ===== CONFIG LOADERS =====
def load_simulation_config(sim_filepath):
    # Load the saved custom simulation config
    with open(sim_filepath, "r") as config_file:
        return json.load(config_file)

def load_circuit_database():
    # Load the default circuit database
    with open(circuit_filepath, "r") as circuit_file:
        return json.load(circuit_file)

# ===== CIRCUIT SETUP =====
def build_final_characteristics(config_characteristics, default_characteristics):
    # Replace "Default" values with the circuit defaults
    final_characteristics = {}

    for key, value in config_characteristics.items():
        if value == "Default":
            final_characteristics[key] = default_characteristics[key]
        else:
            final_characteristics[key] = int(value)

    return final_characteristics


# ===== MAIN ENTRY =====
def main(sim_filepath):
    # Load saved race config
    config_data = load_simulation_config(sim_filepath)

    selected_circuit = config_data["circuit"]
    selected_grandprix = config_data["grandprix"].replace("\n", " ")
    race_year = config_data["race_year"]
    starting_grid = config_data["starting_grid"]
    config_characteristics = config_data["circuit_characteristics"]

    # Load default circuit data
    circuits = load_circuit_database()

    if selected_grandprix not in circuits:
        raise ValueError(f"Circuit '{selected_grandprix}' not found in circuits.json")

    circuit_params = circuits[selected_grandprix]

    # Build final circuit characteristics
    final_characteristics = build_final_characteristics(config_characteristics, circuit_params["characteristics"])

    # Create and return the race manager
    rm = RaceManager(
        season = race_year,
        grandprix = selected_grandprix,
        circuit = selected_circuit,
        total_laps = circuit_params["total_laps"],
        base_lap_time = circuit_params["base_lap_time"],
        lap_time_std = circuit_params["lap_time_std"],
        pit_loss = circuit_params["pit_loss"],
        pit_speed = circuit_params["pit_lane"]["pit_speed_limit_mps"],
        starting_grid = starting_grid,
        circuit_characteristics = final_characteristics,
        seed = None,
        config_filepath = sim_filepath
    )

    return rm