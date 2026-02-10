from typing import List

from src.sim.RaceState import CarSnapshot
from src.agents.CarAgent import CarAgent


class TeamAgent:
    """
    Team agent:
    - Owns strategy decisions
    - Observes race via RaceState (filtered)
    - Commands its cars
    """

    def __init__(self, team_id: str, cars: List[CarAgent]):
        self.team_id = team_id
        self.cars = cars
        self.has_pitted = False

    def observe(self, race_view: List[CarSnapshot]):
        self.race_view = race_view

    def decide(self, lap: int):
        """
        Very simple logic for now:
        - Pit both cars on lap 20
        """
        if lap == 20 and not self.has_pitted:
            for car in self.cars:
                car.pit("C2")
            self.has_pitted = True