# src/sim/Race_Manager.py
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


# ----------------------------
# Data classes (minimal "agents")
# ----------------------------

@dataclass
class TeamAgent:
    name: str
    pace_offset: float
    degradation_factor: float
    pit_execution_std: float


@dataclass
class CarAgent:
    driver: str
    team: TeamAgent
    tyre_compound: str
    tyre_life: int = 0
    total_time: float = 0.0

    def reset_tyre(self, new_compound: str) -> None:
        self.tyre_compound = new_compound
        self.tyre_life = 0


# ----------------------------
# Race Manager
# ----------------------------

class Race_Manager:
    def __init__(
        self,
        season: str,
        circuit_name: str,
        strategy_start_tyre: str,
        strategy_end_tyre: str,
        pit_lap: int,
        seed: int = 42,
        include_formation_lap: bool = True,
        lap1_start_penalty: float = 4.0,
        enable_lap_noise: bool = True,
        enable_pit_noise: bool = True,
    ) -> None:
        self.season = season
        self.circuit_name = circuit_name
        self.strategy_start_tyre = strategy_start_tyre
        self.strategy_end_tyre = strategy_end_tyre
        self.pit_lap = pit_lap

        self.seed = seed
        self.include_formation_lap = include_formation_lap
        self.lap1_start_penalty = lap1_start_penalty
        self.enable_lap_noise = enable_lap_noise
        self.enable_pit_noise = enable_pit_noise

        # Project root: .../F1-Sim
        self.project_root = Path(__file__).resolve().parents[2]

        # Load configs
        self.circuits = self._load_json(self.project_root / "configs" / "circuits.json")
        self.teams_by_year = self._load_json(self.project_root / "configs" / "teams.json")
        self.tyre_compounds = self._load_json(self.project_root / "configs" / "tyre_compounds.json")
        self.tyre_model = self._load_json(self.project_root / "configs" / "tyres.json")["tyres"]

        if circuit_name not in self.circuits:
            raise KeyError(f'Circuit "{circuit_name}" not found in circuits.json')

        if season not in self.teams_by_year:
            raise KeyError(f'Season "{season}" not found in teams.json')

        if season not in self.tyre_compounds.get("season", {}):
            raise KeyError(f'Season "{season}" not found in tyre_compounds.json')

        if circuit_name not in self.tyre_compounds["season"][season]:
            raise KeyError(f'Circuit "{circuit_name}" not found in tyre_compounds.json for season {season}')

        # Circuit values
        self.circuit = self.circuits[circuit_name]
        self.total_laps: int = int(self.circuit["total_laps"])
        self.base_lap_time: float = float(self.circuit["base_lap_time"])
        self.lap_time_std: float = float(self.circuit.get("lap_time_std", 0.0))
        self.track_deg_multiplier: float = float(self.circuit.get("track_deg_multiplier", 1.0))
        self.pit_loss: float = float(self.circuit["pit_loss"])

        # Map strategy tyres (SOFT/MEDIUM/HARD) -> compound (C1..C5) using tyre_compounds.json
        self.start_compound = self._map_label_to_compound(self.strategy_start_tyre)
        self.end_compound = self._map_label_to_compound(self.strategy_end_tyre)

        # RNG
        self.rng = random.Random(self.seed)

        # Build entry list (FORCE 20 CARS)
        self.cars: List[CarAgent] = self._build_cars_force_20(
            season=self.season,
            start_compound=self.start_compound
        )

    # ----------------------------
    # I/O
    # ----------------------------

    def _load_json(self, path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(f"Missing config: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ----------------------------
    # Tyre compound mapping
    # ----------------------------

    def _map_label_to_compound(self, label: str) -> str:
        """
        label: SOFT/MEDIUM/HARD or a direct compound like C3
        Returns: C1..C5, INTERMEDIATE, WET
        """
        label = label.strip().upper()

        # Already a compound
        if label in self.tyre_model:
            return label

        # Map SOFT/MEDIUM/HARD using tyre_compounds.json for this season/circuit
        compounds = self.tyre_compounds["season"][self.season][self.circuit_name]["compounds"]
        if label in compounds:
            mapped = compounds[label].strip().upper()
            if mapped not in self.tyre_model:
                raise KeyError(f'tyres.json missing tyre model for "{mapped}" (mapped from {label})')
            return mapped

        raise KeyError(f'Unknown tyre label "{label}". Expected SOFT/MEDIUM/HARD or C1..C5/INTERMEDIATE/WET.')

    # ----------------------------
    # Entry list (FORCE 20)
    # ----------------------------

    def _build_cars_force_20(self, season: str, start_compound: str) -> List[CarAgent]:
        """
        teams.json sometimes includes reserve drivers.
        For simulation stability, we take ONLY the first 2 drivers per team (20-car grid).
        """
        cars: List[CarAgent] = []
        teams = self.teams_by_year[season]

        for team_name, team_data in teams.items():
            perf = team_data["performance"]
            team = TeamAgent(
                name=team_name,
                pace_offset=float(perf.get("pace_offset", 0.0)),
                degradation_factor=float(perf.get("degradation_factor", 1.0)),
                pit_execution_std=float(perf.get("pit_execution_std", 0.0)),
            )

            drivers = team_data.get("drivers", [])
            # Force exactly two per team (first two listed)
            for d in drivers[:2]:
                driver_code = d["name"]
                cars.append(CarAgent(driver=driver_code, team=team, tyre_compound=start_compound))

        # If we ever end up with not-20 due to weird data, fail loudly.
        if len(cars) != 20:
            raise ValueError(
                f"Expected 20 cars (2 per team). Got {len(cars)}. "
                f"Check teams.json for season {season}."
            )

        return cars

    # ----------------------------
    # Tyre delta model (warm-up -> peak -> accelerating deg)
    # ----------------------------

    def tyre_delta_seconds(self, compound: str, life: int, team_deg_factor: float) -> float:
        """
        Returns tyre time delta (seconds) to add to base pace for this lap.
        Scaled by circuit track_deg_multiplier and team degradation_factor.
        """
        if compound not in self.tyre_model:
            raise KeyError(f'tyres.json missing compound "{compound}"')

        t = self.tyre_model[compound]
        warmup_laps = int(t.get("warmup_laps", 0))
        warmup_start_penalty = float(t.get("warmup_start_penalty", 0.0))
        peak_life = int(t.get("peak_life", 0))
        deg_linear = float(t.get("deg_linear", 0.0))
        deg_quadratic = float(t.get("deg_quadratic", 0.0))

        # --- Warm-up improvement: penalty decreases to 0 over warmup_laps
        warmup_penalty = 0.0
        if warmup_laps > 0 and life < warmup_laps:
            # Linear ramp down from warmup_start_penalty at life=0 to 0 at life=warmup_laps-1
            if warmup_laps == 1:
                warmup_penalty = warmup_start_penalty
            else:
                frac = 1.0 - (life / (warmup_laps - 1))
                warmup_penalty = warmup_start_penalty * max(0.0, frac)

        # --- Degradation after peak life (accelerating quadratic)
        deg = 0.0
        if life > peak_life:
            age = life - peak_life
            deg = (deg_linear * age) + (deg_quadratic * (age ** 2))

        # Scale degradation (not the warmup penalty) by track/team factors
        deg_scaled = deg * self.track_deg_multiplier * team_deg_factor

        return warmup_penalty + deg_scaled

    # ----------------------------
    # Core race loop
    # ----------------------------

    def run(self) -> None:
        print(f"\nSimulating {self.circuit_name} ({self.season})")
        if self.include_formation_lap:
            print("Formation lap complete (not timed)")
        print(f"Strategy (all cars): {self.strategy_start_tyre} → {self.strategy_end_tyre} (pit lap {self.pit_lap})\n")

        for lap in range(1, self.total_laps + 1):
            for car in self.cars:
                # Pit stop event
                if lap == self.pit_lap:
                    # Base pit loss
                    pit = self.pit_loss

                    # Add team pit execution variability
                    if self.enable_pit_noise and car.team.pit_execution_std > 0:
                        pit += self.rng.gauss(0.0, car.team.pit_execution_std)
                        pit = max(0.0, pit)  # don't allow negative pit time

                    car.total_time += pit
                    car.reset_tyre(self.end_compound)

                # Lap time components
                tyre_delta = self.tyre_delta_seconds(
                    compound=car.tyre_compound,
                    life=car.tyre_life,
                    team_deg_factor=car.team.degradation_factor,
                )

                lap_time = self.base_lap_time
                lap_time += car.team.pace_offset
                lap_time += tyre_delta

                # Standing start penalty on lap 1 (traffic, launch, pack effect)
                if lap == 1:
                    lap_time += self.lap1_start_penalty

                # Lap-to-lap randomness (circuit dispersion)
                if self.enable_lap_noise and self.lap_time_std > 0:
                    lap_time += self.rng.gauss(0.0, self.lap_time_std)

                # Clamp to something sensible (prevents freak negative lap times)
                lap_time = max(40.0, lap_time)

                car.total_time += lap_time
                car.tyre_life += 1

        self._print_final_classification()

    def _print_final_classification(self) -> None:
        # Order by total time (no overtaking logic yet — purely cumulative)
        ordered = sorted(self.cars, key=lambda c: c.total_time)

        print(f"\nFinal Classification — {self.circuit_name} ({self.season})")
        print(f"Strategy: {self.strategy_start_tyre} → {self.strategy_end_tyre} (pit lap {self.pit_lap})\n")

        for i, car in enumerate(ordered, start=1):
            print(f"P{i:02d} | {car.driver:<3} | {car.team.name:<18} | Total: {car.total_time:.2f}s")