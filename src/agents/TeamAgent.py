# src/agents/TeamAgent.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple
from src.agents.CarAgent import CarAgent
from src.models.TyreModel import TyreModel


@dataclass
class TeamAgent:
    team_name: str
    cars: List[CarAgent]

    def decide_pits_fixed_strategy(
        self,
        current_lap: int,
        pit_lap: int,
        strategy: Tuple[str, str],
        compound_map: Dict[str, str]
    ) -> List[CarAgent]:
        """
        Simple v0 strategy: everyone pits on a fixed lap, switching from strategy[0] to strategy[1].
        Returns the list of cars that will pit.
        """
        if current_lap != pit_lap:
            return []

        # switch to second stint compound
        next_compound = compound_map.get(strategy[1], compound_map.get("HARD", "C2"))

        for car in self.cars:
            car.tyre = TyreModel(compound_code=next_compound, age_laps=0)

        return list(self.cars)