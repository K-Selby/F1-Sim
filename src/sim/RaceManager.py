from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List

from src.agents.CarAgent import CarAgent, CarCalibration
from src.models.TyreModel import TyreModel, TyreState


@dataclass
class CircuitSpec:
    name: str
    base_lap_time: float
    track_deg_multiplier: float


class RaceManager:
    """
    Environment agent builds cars and runs the global loop.
    This patch fixes your current crash by:
    - constructing TyreState(compound, age_laps)
    - passing a shared TyreModel loaded from tyres.json
    """

    def __init__(
        self,
        circuit: CircuitSpec,
        teams_json: Dict,
        tyres_json: Dict,
        start_compound: str = "MEDIUM",
    ):
        self.circuit = circuit

        # Shared calibrated model (NOT per-car state)
        self.tyre_model = TyreModel(tyres_json)

        self.teams_json = teams_json
        self.start_compound = start_compound

        self.cars: List[CarAgent] = self._build_grid()

    def _build_grid(self) -> List[CarAgent]:
        cars: List[CarAgent] = []

        teams = self.teams_json.get("teams", [])
        if not isinstance(teams, list) or not teams:
            raise ValueError("teams.json must contain a list at key 'teams'")

        for team in teams:
            team_id = str(team["team_id"])
            mu_team = float(team["mu_team"])
            k_team = float(team["k_team"])

            # Assuming 2 cars per team (A/B). Adjust if your schema differs.
            for suffix in ("A", "B"):
                car_id = f"{team_id}_{suffix}"

                tyre_state = TyreState(compound=self.start_compound, age_laps=0)
                calibration = CarCalibration(mu_team=mu_team, k_team=k_team)

                car = CarAgent(
                    car_id=car_id,
                    team_id=team_id,
                    calibration=calibration,
                    tyre_state=tyre_state,
                    tyre_model=self.tyre_model,
                )
                cars.append(car)

        return cars

    def step_lap(self) -> List[float]:
        """
        Minimal lap-step to confirm architecture works end-to-end.
        """
        lap_times: List[float] = []
        for car in self.cars:
            car.update_tyre_wear()
            lap_time = car.estimate_clean_air_lap_time(
                base_lap_time=self.circuit.base_lap_time,
                track_deg_multiplier=self.circuit.track_deg_multiplier,
            )
            lap_times.append(lap_time)
        return lap_times


# Optional helper if you want RaceManager to load JSON itself.
def load_json(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)