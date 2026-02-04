from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.models.TyreModel import TyreModel, TyreState


@dataclass
class CarCalibration:
    """
    Team-calibrated parameters used by the car each lap.
    """
    mu_team: float   # baseline pace offset (seconds)
    k_team: float    # tyre management scaling factor


class CarAgent:
    """
    CarAgent holds tyre STATE (compound + age) and uses the shared TyreModel to compute wear/pace,
    matching the design's separation: state on agent, model shared and calibrated.
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

        self.mu_team = float(calibration.mu_team)
        self.k_team = float(calibration.k_team)

        self.tyre_state = tyre_state
        self.tyre_model = tyre_model

        # Optional (if/when you wire in traffic + commands)
        self.pace_command: Optional[str] = None
        self.last_lap_time: Optional[float] = None

    @property
    def tyre_compound(self) -> str:
        return self.tyre_state.compound

    @property
    def tyre_age(self) -> int:
        return int(self.tyre_state.age_laps)

    def update_tyre_wear(self) -> None:
        """
        Per-lap tyre ageing (stint age increments by 1 lap).
        """
        self.tyre_model.advance(self.tyre_state, laps=1)

    def estimate_clean_air_lap_time(
        self,
        base_lap_time: float,
        track_deg_multiplier: float,
    ) -> float:
        """
        Clean-air estimate using:
        base_lap_time + mu_team + tyre_delta(...)
        """
        tyre_delta = self.tyre_model.lap_delta(
            compound=self.tyre_state.compound,
            life=self.tyre_state.age_laps,
            track_deg_multiplier=track_deg_multiplier,
            k_team=self.k_team,
        )
        lap_time = float(base_lap_time) + self.mu_team + tyre_delta
        self.last_lap_time = lap_time
        return lap_time