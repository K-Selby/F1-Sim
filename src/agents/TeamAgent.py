# src/agents/TeamAgent.py

from __future__ import annotations
from dataclasses import dataclass
from typing import List

from src.agents.CarAgent import CarAgent


@dataclass
class StrategyDecision:
    """
    What the team wants the car to do.
    For now this is very simple and fixed.
    """
    pit_now: bool = False
    next_compound: str | None = None


class TeamAgent:
    """
    A team agent controls two cars.

    What this class does:
    - Holds the two CarAgents
    - Decides when to pit (later this becomes intelligent)
    - Applies the same strategy logic to both cars

    What this class does NOT do:
    - Lap time calculations
    - Tyre physics
    - Race control logic
    """

    def __init__(self, team_id: str, cars: List[CarAgent]):
        if len(cars) != 2:
            raise ValueError("A TeamAgent must control exactly 2 cars")

        self.team_id = team_id
        self.cars = cars

        # Simple placeholder strategy
        self.planned_pit_lap: int | None = None
        self.target_compound: str | None = None

    # ---------------------------------------------------------
    # Strategy
    # ---------------------------------------------------------
    def set_basic_strategy(self, pit_lap: int, compound: str) -> None:
        """
        Hard-code a simple strategy for now.
        """
        self.planned_pit_lap = pit_lap
        self.target_compound = compound

    def decide(self, current_lap: int) -> StrategyDecision:
        """
        Decide what to do this lap.
        """
        if self.planned_pit_lap is None:
            return StrategyDecision()

        if current_lap == self.planned_pit_lap:
            return StrategyDecision(
                pit_now=True,
                next_compound=self.target_compound,
            )

        return StrategyDecision()

    # ---------------------------------------------------------
    # Apply decision to cars
    # ---------------------------------------------------------
    def apply_decision(
        self,
        decision: StrategyDecision,
        pit_loss: float,
    ) -> None:
        """
        Apply the team's decision to both cars.
        """
        if not decision.pit_now:
            return

        for car in self.cars:
            # Add pit stop time
            car.tyre_state.age_laps = 0
            car.tyre_state.compound = decision.next_compound