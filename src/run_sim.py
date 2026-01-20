# src/run_sim.py
import json
import random
from pathlib import Path

def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)

def main():
    cfg = load_config("F1-sim/configs/toy_race.json")
    rng = random.Random(cfg["random_seed"])

    print(f"Running {cfg['race_name']}")

    for lap in range(1, cfg["laps"] + 1):
        print(f"Lap {lap}")
        for car in cfg["cars"]:
            lap_time = car["base_lap"] + rng.gauss(0, cfg["lap_time_noise_std"])
            print(car["car_id"], round(lap_time, 3))

if __name__ == "__main__":
    main()