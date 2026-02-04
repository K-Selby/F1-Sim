from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List, Tuple

from src.sim.TyreModel import TyreModel
from src.agents.CarAgent import CarAgent, Strategy


class RaceManager:
    def __init__(
        self,
        season: int,
        circuit_name: str,
        fixed_strategy: Tuple[str, str, int],  # ("MEDIUM","HARD",20) using tyre-types
        seed: int = 42,
        driver_noise_scale: float = 0.35,      # scales circuit lap_time_std
        start_lap_penalty: float = 4.0,        # starting lap extra seconds
        formation_lap: bool = True,
    ):
        self.season = int(season)
        self.circuit_name = circuit_name
        self.fixed_strategy = fixed_strategy
        self.seed = int(seed)
        self.driver_noise_scale = float(driver_noise_scale)
        self.start_lap_penalty = float(start_lap_penalty)
        self.formation_lap = bool(formation_lap)

        self.root = Path(__file__).resolve().parents[2]  # project root (F1-Sim/)
        self.configs = self.root / "configs"

        self.circuits = self._load_json(self.configs / "circuits.json")
        self.teams = self._load_json(self.configs / "teams.json")
        self.tyre_compounds = self._load_json(self.configs / "tyre_compounds.json")
        self.tyres_json = self._load_json(self.configs / "tyres.json")

        self.circuit = self.circuits[self.circuit_name]
        self.tyre_model = TyreModel(self.tyres_json)

        random.seed(self.seed)

    @staticmethod
    def _load_json(path: Path) -> Dict:
        with open(path, "r") as f:
            return json.load(f)

    def _resolve_compound(self, tyre_type: str) -> str:
        """
        tyre_type is one of: "SOFT", "MEDIUM", "HARD"
        returns compound code: "C1".."C5"
        """
        season_key = str(self.season)
        mapping = self.tyre_compounds["season"][season_key][self.circuit_name]["compounds"]
        return mapping[tyre_type]

    def _build_grid(self) -> List[CarAgent]:
        season_key = str(self.season)
        season_teams = self.teams[season_key]

        tyre_type_start, tyre_type_end, pit_lap = self.fixed_strategy
        start_compound = self._resolve_compound(tyre_type_start)
        end_compound = self._resolve_compound(tyre_type_end)

        cars: List[CarAgent] = []
        for team_name, team_blob in season_teams.items():
            perf = team_blob["performance"]
            pace_offset = perf["pace_offset"]
            deg_factor = perf["degradation_factor"]
            pit_std = perf.get("pit_execution_std", 1.0)

            for d in team_blob["drivers"]:
                driver_code = d["name"]
                strat = Strategy(
                    start_compound=start_compound,
                    pit_lap=int(pit_lap),
                    end_compound=end_compound,
                )
                cars.append(
                    CarAgent(
                        driver_code=driver_code,
                        team_name=team_name,
                        pace_offset=pace_offset,
                        degradation_factor=deg_factor,
                        pit_execution_std=pit_std,
                        tyre_model=self.tyre_model,
                        strategy=strat,
                    )
                )
        return cars

    def run(self, verbose: bool = False) -> List[CarAgent]:
        total_laps = int(self.circuit["total_laps"])
        base_lap_time = float(self.circuit["base_lap_time"])
        lap_time_std = float(self.circuit["lap_time_std"])
        track_deg_multiplier = float(self.circuit["track_deg_multiplier"])
        pit_loss = float(self.circuit["pit_loss"])

        cars = self._build_grid()

        tyre_type_start, tyre_type_end, pit_lap = self.fixed_strategy
        print(f"\nSimulating {self.circuit_name} ({self.season})")
        if self.formation_lap:
            print("Formation lap complete (not timed)")
        print(f"Strategy (all cars): {tyre_type_start} → {tyre_type_end} (pit lap {pit_lap})\n")

        for lap in range(1, total_laps + 1):
            # each driver does pit logic + lap
            for car in cars:
                # pit noise for THIS stop (only if they pit this lap)
                pit_noise = random.gauss(0.0, car.pit_execution_std)

                pit_delta = car.maybe_pit(lap=lap, pit_loss=pit_loss, pit_noise=pit_noise)

                # lap noise (driver variance)
                lap_noise = random.gauss(0.0, lap_time_std * self.driver_noise_scale)

                car.do_lap(
                    lap=lap,
                    base_lap_time=base_lap_time,
                    lap_time_noise=lap_noise,
                    track_deg_multiplier=track_deg_multiplier,
                    start_lap_penalty=self.start_lap_penalty if lap == 1 else 0.0,
                )

            # positions purely by cumulative time
            cars.sort(key=lambda c: c.total_time)

            if verbose:
                leader = cars[0]
                p2 = cars[1]
                gap = p2.total_time - leader.total_time
                print(f"Lap {lap:02d} Leader: {leader.driver_code} ({leader.team_name})  Gap P2: +{gap:.2f}s")

        # Final classification
        print(f"\nFinal Classification — {self.circuit_name} ({self.season})")
        print(f"Strategy: {tyre_type_start} → {tyre_type_end} (pit lap {pit_lap})\n")

        for i, car in enumerate(sorted(cars, key=lambda c: c.total_time), start=1):
            print(f"P{i:02d} | {car.driver_code:<3} | {car.team_name:<18} | Total: {car.total_time:.2f}s")

        return cars