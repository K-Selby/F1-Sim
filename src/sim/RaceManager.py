# src/sim/RaceManager.py

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List

from src.agents.CarAgent import CarAgent, CarCalibration
from src.agents.TeamAgent import TeamAgent
from src.models.TyreModel import TyreModel, TyreState


# ---------------------------------------------------------
# Simple circuit container
# ---------------------------------------------------------
@dataclass
class CircuitSpec:
    name: str
    total_laps: int
    base_lap_time: float
    track_deg_multiplier: float
    pit_loss: float


# ---------------------------------------------------------
# Race Manager (environment / orchestrator)
# ---------------------------------------------------------
class RaceManager:
    """
    The RaceManager is the environment.

    It:
    - Loads cars and teams
    - Runs the lap loop
    - Asks TeamAgents for decisions
    - Steps CarAgents forward one lap
    """

    def __init__(
        self,
        circuit: CircuitSpec,
        teams_json: Dict,
        tyres_json: Dict,
        tyre_compounds_json: Dict,
        season: str,
        circuit_name: str,
    ):
        self.circuit = circuit
        self.season = season
        self.circuit_name = circuit_name

        # Shared tyre model (same physics for all cars)
        self.tyre_model = TyreModel(tyres_json)

        # Build teams + cars
        self.teams: List[TeamAgent] = []
        self._build_teams(
            teams_json=teams_json,
            tyre_compounds_json=tyre_compounds_json,
        )

        self.current_lap: int = 0

    # ---------------------------------------------------------
    # Build grid
    # ---------------------------------------------------------
    def _build_teams(
        self,
        teams_json: Dict,
        tyre_compounds_json: Dict,
    ) -> None:
        season_teams = teams_json[self.season]

        for team_name, team_data in season_teams.items():
            perf = team_data["performance"]

            cars: List[CarAgent] = []

            for driver in team_data["drivers"]:
                tyre_label = "MEDIUM"
                compound = tyre_compounds_json["season"][self.season][self.circuit_name]["compounds"][tyre_label]

                tyre_state = TyreState(
                    compound=compound,
                    age_laps=0,
                )

                calibration = CarCalibration(
                    mu_team=float(perf["pace_offset"]),
                    k_team=float(perf["degradation_factor"]),
                )

                car = CarAgent(
                    car_id=driver["name"],
                    team_id=team_name,
                    calibration=calibration,
                    tyre_state=tyre_state,
                    tyre_model=self.tyre_model,
                )
                cars.append(car)

            # Only keep 2 cars per team
            cars = cars[:2]

            team_agent = TeamAgent(team_id=team_name, cars=cars)

            # Temporary hard-coded strategy
            team_agent.set_basic_strategy(
                pit_lap=20,
                compound=tyre_compounds_json["season"][self.season][self.circuit_name]["compounds"]["HARD"],
            )

            self.teams.append(team_agent)

    # ---------------------------------------------------------
    # One race lap
    # ---------------------------------------------------------
    def step_lap(self) -> List[float]:
        """
        Run one full race lap.
        """
        self.current_lap += 1
        lap_times: List[float] = []

        # Ask each team what they want to do
        for team in self.teams:
            decision = team.decide(self.current_lap)
            team.apply_decision(
                decision=decision,
                pit_loss=self.circuit.pit_loss,
            )

        # Step each car
        for team in self.teams:
            for car in team.cars:
                car.update_tyre_wear()

                lap_time = car.estimate_clean_air_lap_time(
                    base_lap_time=self.circuit.base_lap_time,
                    track_deg_multiplier=self.circuit.track_deg_multiplier,
                )

                lap_times.append(lap_time)

        return lap_times

    # ---------------------------------------------------------
    # Run full race
    # ---------------------------------------------------------
    def run_race(self) -> None:
        """
        Run the full race distance.
        """
        print(f"Simulating {self.circuit.name} ({self.season})\n")

        for _ in range(self.circuit.total_laps):
            lap_times = self.step_lap()

            for idx, lap_time in enumerate(lap_times, start=1):
                print(f"Car {idx:02d} lap time: {lap_time:.3f}s")