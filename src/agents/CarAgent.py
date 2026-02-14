# src/agents/CarAgent.py

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from src.models.TyreModel import TyreModel, TyreState


@dataclass
class CarCalibration:
    mu_team: float
    k_team: float
    reliability_prob: float = 0.0

class CarAgent:
    def __init__(self, car_id: str, team_id: str, calibration: CarCalibration, tyre_state: TyreState, tyre_model: TyreModel):
        self.car_id = car_id
        self.team_id = team_id
        self.calibration = calibration

        self.tyre_state = tyre_state
        self.tyre_model = tyre_model

        self.gap_ahead: Optional[float] = None
        self.gap_behind: Optional[float] = None
        self.track_state: str = "GREEN"

        self.instruction: Optional[str] = None

        self.total_time: float = 0.0
        self.retired: bool = False

        self._sector_counter: int = 0
        
        self.pending_pit: Optional[str] = None
        self._pit_loss: float = 0.0
        self.pit_compound: Optional[str] = None
        self.traffic_penalty = 0.0
        self.slipstream_bonus = 0.0
        self.following_intensity = 0.0

    # ==========================================================
    # SECTOR STEP
    # ==========================================================
    def step_sector(self, sector_base_time: float, track_deg_multiplier: float, lap_time_std: float,) -> float:
        if self.retired:
            return 0.0

        if self._check_reliability_failure():
            self.retired = True
            return 0.0

        tyre_delta = self.tyre_model.lap_delta(tyre_state=self.tyre_state, track_deg_multiplier=track_deg_multiplier, team_deg_factor=self.calibration.k_team,)
        sector_time = (sector_base_time + self.calibration.mu_team / 3 + tyre_delta / 3 + self.traffic_penalty - self.slipstream_bonus)
        
        # Add sector-level randomness
        sector_std = self.calibration.lap_time_std / 3 if hasattr(self.calibration, 'lap_time_std') else 0.0
        randomness = random.gauss(0, sector_std)
        sector_time += randomness

        sector_time = self.adjust_for_traffic(sector_time)
        self.total_time += sector_time

        self._sector_counter += 1
        if self._sector_counter == 3:
            self.update_tyre_wear()
            self._sector_counter = 0

        # Execute pit stop at end of lap
        if self.pending_pit and self._sector_counter == 0:
            pit_time = self._pit_loss

            # Safety Car discount
            if self.track_state == "SC":
                pit_time *= 0.6  # 40% cheaper under SC

            self.total_time += pit_time

            print(
                f"{self.car_id} PIT STOP | +{pit_time:.2f}s | "
                f"Total {self.total_time:.2f}s"
            )

            self.pit(self._pending_pit)
            self._pending_pit = None

        return sector_time

    # ==========================================================
    # TYRES
    # ==========================================================
    def update_tyre_wear(self) -> None:
        extra_deg = 1.0 + 0.15 * self.following_intensity
        self.tyre_model.advance(self.tyre_state, laps=extra_deg)

    # ==========================================================
    # RACECRAFT PLACEHOLDERS
    # ==========================================================
    def adjust_for_traffic(self, lap_time: float) -> float:
        return lap_time

    def attempt_overtake(self) -> bool:
        return False

    def defend_position(self) -> None:
        pass

    # ==========================================================
    # PIT & TEAM INTERACTION
    # ==========================================================
    def pit(self, new_compound: str) -> None:
        """
        Request a pit stop.
        Actual time loss handled by RaceManager.
        """
        self.pending_pit = True
        self.pit_compound = new_compound

    def apply_team_instruction(self, instruction: str) -> None:
        self.instruction = instruction

    # ==========================================================
    # RELIABILITY
    # ==========================================================
    def _check_reliability_failure(self) -> bool:
        if self.calibration.reliability_prob <= 0.0:
            return False
        return random.random() < self.calibration.reliability_prob