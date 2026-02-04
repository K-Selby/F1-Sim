from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.sim.TyreModel import TyreModel


@dataclass
class Strategy:
    start_compound: str  # e.g. "C3"
    pit_lap: int         # e.g. 20
    end_compound: str    # e.g. "C2"


class CarAgent:
    def __init__(
        self,
        driver_code: str,
        team_name: str,
        pace_offset: float,
        degradation_factor: float,
        pit_execution_std: float,
        tyre_model: TyreModel,
        strategy: Strategy,
    ):
        self.driver_code = driver_code
        self.team_name = team_name
        self.pace_offset = float(pace_offset)
        self.degradation_factor = float(degradation_factor)
        self.pit_execution_std = float(pit_execution_std)

        self.tyre_model = tyre_model
        self.strategy = strategy

        self.compound = strategy.start_compound
        self.tyre_life = 0

        self.total_time = 0.0
        self.lap_times: list[float] = []
        self.pitted = False

    def maybe_pit(self, lap: int, pit_loss: float, pit_noise: float) -> Optional[float]:
        """
        If pitting this lap, apply pit time and reset tyres.
        Returns pit_delta if pit happened.
        """
        if (not self.pitted) and lap == self.strategy.pit_lap:
            self.pitted = True
            self.total_time += (pit_loss + pit_noise)
            self.compound = self.strategy.end_compound
            self.tyre_life = 0
            return pit_loss + pit_noise
        return None

    def do_lap(
        self,
        lap: int,
        base_lap_time: float,
        lap_time_noise: float,
        track_deg_multiplier: float,
        start_lap_penalty: float = 0.0,
    ) -> float:
        """
        Simulate one lap for this car, return lap time.
        """
        delta = self.tyre_model.lap_delta(
            compound=self.compound,
            life=self.tyre_life,
            track_deg_multiplier=track_deg_multiplier,
            team_deg_factor=self.degradation_factor,
        )

        lap_time = base_lap_time + self.pace_offset + delta + lap_time_noise

        if lap == 1:
            lap_time += start_lap_penalty

        # Safety clamp
        lap_time = max(1.0, lap_time)

        self.total_time += lap_time
        self.lap_times.append(lap_time)
        self.tyre_life += 1
        return lap_time