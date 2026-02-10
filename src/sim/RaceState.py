from dataclasses import dataclass
from typing import Dict, List


@dataclass
class CarSnapshot:
    car_id: str
    team_id: str
    total_time: float
    lap: int
    tyre: str
    tyre_age: int


class RaceState:
    """
    Global race state.
    This is the ONLY place that knows the full truth.
    Agents receive filtered views of this.
    """

    def __init__(self, total_laps: int):
        self.total_laps = total_laps
        self.current_lap = 0
        self.cars: Dict[str, CarSnapshot] = {}

    def update_car(
        self,
        car_id: str,
        team_id: str,
        total_time: float,
        lap: int,
        tyre: str,
        tyre_age: int,
    ):
        self.cars[car_id] = CarSnapshot(
            car_id=car_id,
            team_id=team_id,
            total_time=total_time,
            lap=lap,
            tyre=tyre,
            tyre_age=tyre_age,
        )

    def classification(self) -> List[CarSnapshot]:
        return sorted(self.cars.values(), key=lambda c: c.total_time)

    def team_view(self, team_id: str) -> List[CarSnapshot]:
        """
        What a team is allowed to see:
        - Their own cars
        - Full classification ordering (but no hidden internals)
        """
        return self.classification()