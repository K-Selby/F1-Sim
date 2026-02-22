# main.py

from src.sim.RaceManager import RaceManager
import json

CIRCUIT_FILE = "configs/circuits.json"
SIM_CONFIG_FILE = "configs/sim_configuration.json"

def main():
    # ------------------------------------------
    # Load simulation configuration
    # ------------------------------------------
    with open(SIM_CONFIG_FILE, "r") as config_file:
        config_data = json.load(config_file)["Configurations"][0]

    selected_gp = config_data["Grand Prix"]

    # ------------------------------------------
    # Load circuit database
    # ------------------------------------------
    with open(CIRCUIT_FILE, "r") as circuit_file:
        circuits = json.load(circuit_file)

    if selected_gp not in circuits:
        raise ValueError(f"Circuit '{selected_gp}' not found in circuits.json")

    circuit_params = circuits[selected_gp]

    print(f"\nLoaded Circuit: {selected_gp}")
    print(f"Total Laps: {circuit_params['total_laps']}")
    print(f"Base Lap Time: {circuit_params['base_lap_time']}")

    # ------------------------------------------
    # Build Race Manager using circuit params
    # ------------------------------------------
    rm = RaceManager(
        season = "2024",
        circuit = selected_gp,
        total_laps = circuit_params["total_laps"],
        base_lap_time = circuit_params["base_lap_time"],
        lap_time_std = circuit_params["lap_time_std"],
        pit_loss = circuit_params["pit_loss"],
        seed = 24
    )

    rm.run()

if __name__ == "__main__":
    main()