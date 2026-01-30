from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class DriverInfo:
    code: str
    number: int


class Car_Agent:
    """
    Minimal car agent for MVP:
    - State: driver, team, tyre, tyre_life, total_time
    - Simulates lap time given circuit + tyre model + team modifiers
    - Pit is triggered by Race_Manager using a fixed global strategy
    """

    def __init__(self, driver: DriverInfo, team_name: str, team_agent, start_tyre: str):
        self.driver = driver
        self.team_name = team_name
        self.team = team_agent

        self.tyre = start_tyre
        self.tyre_life = 0

        self.total_time = 0.0

    def set_tyre(self, tyre: str):
        self.tyre = tyre
        self.tyre_life = 0

    def step_lap(
        self,
        lap_index: int,
        circuit: Dict[str, Any],
        tyre_params: Dict[str, Any],
        rng,
        include_start_penalty: bool = True,
        start_lap_penalty: float = 4.0,
        enable_noise: bool = True,
    ) -> float:
        """
        Returns lap_time (seconds), and updates total_time and tyre_life.
        """

        base_lap_time = float(circuit["base_lap_time"])
        lap_time_std = float(circuit.get("lap_time_std", 0.0))
        track_deg_multiplier = float(circuit.get("track_deg_multiplier", 1.0))

        # Team pace offset shifts baseline
        lap_time = base_lap_time + float(self.team.pace_offset)

        # Lap 1 "start lap" penalty (traffic, standing start, etc.)
        if include_start_penalty and lap_index == 1:
            lap_time += float(start_lap_penalty)

        # Tyre model
        t = tyre_params[self.tyre]
        warmup_laps = int(t.get("warmup_laps", 0))
        warmup_start_penalty = float(t.get("warmup_start_penalty", 0.0))
        peak_life = int(t.get("peak_life", 0))
        deg_linear = float(t.get("deg_linear", 0.0))
        deg_quadratic = float(t.get("deg_quadratic", 0.0))

        # Warm-up improvement: penalty decreases from start -> 0 over warmup_laps
        warmup_pen = 0.0
        if warmup_laps > 0 and self.tyre_life < warmup_laps:
            if warmup_laps == 1:
                warmup_pen = warmup_start_penalty
            else:
                # life=0 => full penalty, life=warmup_laps-1 => ~0 penalty
                frac = self.tyre_life / (warmup_laps - 1)
                warmup_pen = warmup_start_penalty * (1.0 - frac)
                if warmup_pen < 0:
                    warmup_pen = 0.0
        lap_time += warmup_pen

        # Degradation: accelerating after peak_life (quadratic in "deg_age")
        deg_age = max(0, self.tyre_life - peak_life)
        deg_pen = (deg_linear * deg_age) + (deg_quadratic * (deg_age ** 2))

        # Apply track + team tyre management scaling
        deg_pen *= track_deg_multiplier
        deg_pen *= float(self.team.degradation_factor)

        lap_time += deg_pen

        # Random noise (optional): captures lap-to-lap variance
        if enable_noise and lap_time_std > 0:
            lap_time += float(rng.normal(0.0, lap_time_std))

        # Update state
        self.total_time += lap_time
        self.tyre_life += 1

        return lap_time