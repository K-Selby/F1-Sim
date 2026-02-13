# main.py

from src.sim.RaceManager import RaceManager
import json


CIRCUIT_FILE = "configs/circuits.json"
SIM_CONFIG_FILE = "configs/sim_configuration.json"


def main():
    """
    Thin entry point.
    No race logic lives here.
    Only wiring of configuration.
    """

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
    print(f"Track Deg Multiplier: {circuit_params['track_deg_multiplier']}\n")

    # ------------------------------------------
    # Build Race Manager using circuit params
    # ------------------------------------------
    rm = RaceManager(
        season="2021",
        total_laps=circuit_params["total_laps"],
        base_lap_time=circuit_params["base_lap_time"],
        track_deg_multiplier=circuit_params["track_deg_multiplier"],
        sim_speed=1000.0  # playback speed multiplier
    )

    rm.run()


if __name__ == "__main__":
    main()