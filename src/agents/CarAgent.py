# src/agents/CarAgent.py

from __future__ import annotations
from dataclasses import dataclass

from src.models.TyreModel import TyreModel, TyreState


@dataclass(frozen=True)
class CarCalibration:
    """
    Fixed performance values for a car.
    For now these come from the team (same for both cars).
    """
    mu_team: float   # pace offset in seconds (negative = faster)
    k_team: float    # how hard this car is on its tyres


class CarAgent:
    """
    A single car in the race.

    What this class does:
    - Keeps track of its own tyres
    - Calculates its own lap time in clean air
    - Ages its tyres each lap

    What this class does NOT do:
    - Strategy decisions
    - Overtaking or traffic
    - Knowing about other cars
    """

    def __init__(
        self,
        car_id: str,
        team_id: str,
        calibration: CarCalibration,
        tyre_state: TyreState,
        tyre_model: TyreModel,
    ):
        self.car_id = car_id
        self.team_id = team_id
        self.calibration = calibration
        self.tyre_state = tyre_state
        self.tyre_model = tyre_model

    # ---------------------------------------------------------
    # Tyres
    # ---------------------------------------------------------
    def update_tyre_wear(self, laps: int = 1) -> None:
        """
        Increase tyre age by the given number of laps.
        """
        self.tyre_state.age_laps += laps

    # ---------------------------------------------------------
    # Lap time
    # ---------------------------------------------------------
    def estimate_clean_air_lap_time(
        self,
        base_lap_time: float,
        track_deg_multiplier: float,
    ) -> float:
        """
        Calculate lap time assuming no traffic or battles.
        """
        tyre_penalty = self.tyre_model.lap_delta(
            tyre_state=self.tyre_state,
            track_deg_multiplier=track_deg_multiplier,
            team_deg_factor=self.calibration.k_team,
        )

        lap_time = (
            base_lap_time
            + self.calibration.mu_team
            + tyre_penalty
        )

        return max(0.0, lap_time)

    # ---------------------------------------------------------
    # One lap step
    # ---------------------------------------------------------
    def step_lap(
        self,
        base_lap_time: float,
        track_deg_multiplier: float,
    ) -> float:
        """
        Run one lap:
        - get lap time
        - age the tyres
        """
        lap_time = self.estimate_clean_air_lap_time(
            base_lap_time=base_lap_time,
            track_deg_multiplier=track_deg_multiplier,
        )

        self.update_tyre_wear(laps=1)
        return lap_time