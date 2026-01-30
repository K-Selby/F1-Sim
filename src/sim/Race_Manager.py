from __future__ import annotations

import json
from typing import Dict, Any, List, Tuple

import numpy as np

from src.agents.Team_Agent import Team_Agent, TeamPerformance, StrategyProfile
from src.agents.Car_Agent import Car_Agent, DriverInfo


class Race_Manager:
    """
    MVP race manager:
    - Loads configs
    - Creates teams + cars for a given season
    - Runs fixed strategy for all cars
    - No overtakes logic: order = sort by total_time
    """

    # Handle known naming mismatches between circuits.json and tyre_compounds.json
    CIRCUIT_ALIASES = {
        "Mexico City Grand Prix": "Mexican Grand Prix",
        "Mexican Grand Prix": "Mexico City Grand Prix",
    }

    def __init__(
        self,
        circuits_path: str = "configs/circuits.json",
        teams_path: str = "configs/teams.json",
        tyres_path: str = "configs/tyres.json",
        tyre_compounds_path: str = "configs/tyre_compounds.json",
        seed: int = 7,
    ):
        with open(circuits_path) as f:
            self.circuits = json.load(f)
        with open(teams_path) as f:
            self.teams_cfg = json.load(f)
        with open(tyres_path) as f:
            self.tyres_cfg = json.load(f)
        with open(tyre_compounds_path) as f:
            self.tyre_compounds_cfg = json.load(f)

        self.rng = np.random.default_rng(seed)

    def _resolve_compound(self, season: str, circuit_name: str, semantic: str) -> str:
        """
        semantic in {"SOFT","MEDIUM","HARD"} -> returns "C1".."C5"
        """
        season_block = self.tyre_compounds_cfg.get("season", {}).get(season, {})
        if circuit_name in season_block:
            return season_block[circuit_name]["compounds"][semantic]

        # Try alias
        alias = self.CIRCUIT_ALIASES.get(circuit_name)
        if alias and alias in season_block:
            return season_block[alias]["compounds"][semantic]

        raise KeyError(f"No tyre compound mapping for season={season} circuit='{circuit_name}' (or alias).")

    def _build_teams_and_grid(self, season: str) -> Tuple[Dict[str, Team_Agent], List[Car_Agent]]:
        season_data = self.teams_cfg.get(season)
        if season_data is None:
            raise KeyError(f"Season '{season}' not found in teams.json")

        team_agents: Dict[str, Team_Agent] = {}
        cars: List[Car_Agent] = []

        for team_name, team_block in season_data.items():
            perf = team_block["performance"]
            strat = team_block.get("strategy_profile", {})

            team_agent = Team_Agent(
                name=team_name,
                performance=TeamPerformance(
                    pace_offset=float(perf["pace_offset"]),
                    degradation_factor=float(perf["degradation_factor"]),
                    pit_execution_std=float(perf.get("pit_execution_std", 1.0)),
                ),
                strategy=StrategyProfile(
                    risk_tolerance=float(strat.get("risk_tolerance", 0.5)),
                    undercut_bias=float(strat.get("undercut_bias", 0.5)),
                    overcut_bias=float(strat.get("overcut_bias", 0.5)),
                ),
            )
            team_agents[team_name] = team_agent

            # MVP: take first 2 listed drivers only (stand-ins exist in JSON)
            drivers = team_block.get("drivers", [])[:2]
            for d in drivers:
                driver = DriverInfo(code=d["name"], number=int(d["number"]))
                # tyre will be assigned later by run()
                cars.append(Car_Agent(driver=driver, team_name=team_name, team_agent=team_agent, start_tyre="C3"))

        # Sanity check: should be 20 cars
        if len(cars) != 20:
            # Still run, but warn via exception message for now (you can change to print)
            raise ValueError(f"Expected 20 cars for season {season}, got {len(cars)}. Check teams.json driver lists.")

        return team_agents, cars

    def run(
        self,
        season: str,
        circuit_name: str,
        start_semantic: str = "MEDIUM",
        end_semantic: str = "HARD",
        pit_lap: int = 20,
        include_formation_lap: bool = True,
        include_start_lap_penalty: bool = True,
        start_lap_penalty: float = 4.0,
        enable_noise: bool = True,
        print_interval: int = 0,  # 0 = only final result, 1 = every lap
    ) -> List[Car_Agent]:

        if circuit_name not in self.circuits:
            raise KeyError(f"Circuit '{circuit_name}' not found in circuits.json")

        circuit = self.circuits[circuit_name]
        total_laps = int(circuit["total_laps"])

        tyre_params = self.tyres_cfg["tyres"]

        # Map semantic compounds to actual Cx for that season/circuit
        start_tyre = self._resolve_compound(season, circuit_name, start_semantic)
        end_tyre = self._resolve_compound(season, circuit_name, end_semantic)

        _, cars = self._build_teams_and_grid(season)

        # Assign starting tyre
        for car in cars:
            car.set_tyre(start_tyre)

        pit_loss = float(circuit["pit_loss"])

        if include_formation_lap:
            if print_interval:
                print(f"Simulating {circuit_name} ({season})")
                print("Formation lap complete (not timed)")
                print(f"Strategy: {start_semantic}({start_tyre}) → {end_semantic}({end_tyre}) on lap {pit_lap}\n")

        for lap in range(1, total_laps + 1):
            # Pit stop for all cars (same lap, same strategy) — MVP
            if lap == pit_lap:
                for car in cars:
                    # add pit loss + per-team pit execution variance
                    pit_std = float(car.team.pit_execution_std)
                    exec_noise = float(self.rng.normal(0.0, pit_std)) if enable_noise and pit_std > 0 else 0.0
                    car.total_time += (pit_loss + exec_noise)
                    car.set_tyre(end_tyre)

            # Run lap for each car
            for car in cars:
                car.step_lap(
                    lap_index=lap,
                    circuit=circuit,
                    tyre_params=tyre_params,
                    rng=self.rng,
                    include_start_penalty=include_start_lap_penalty,
                    start_lap_penalty=start_lap_penalty,
                    enable_noise=enable_noise,
                )

            # Sort by total time (positions)
            cars.sort(key=lambda c: c.total_time)

            if print_interval == 1:
                leader = cars[0]
                p1 = f"{leader.driver.code} ({leader.team_name})"
                print(f"Lap {lap:02d} - P1: {p1}  Total: {leader.total_time:.2f}s")

        # Final classification
        return cars