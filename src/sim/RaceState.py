# src/sim/RaceState.py

from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass
class CarSnapshot:
    car_id: str
    team_id: str
    total_time: float
    tyre_compound: str
    tyre_age: int


class RaceState:

    def __init__(self):
        self.lap: int = 0
        self.track_state: str = "GREEN"
        self.weather_state: str = "DRY"
        self.car_snapshots: List[CarSnapshot] = []

    def update(self, lap: int, track_state: str, weather_state: str, car_snapshots: List[CarSnapshot]) -> None:
        self.lap = lap
        self.track_state = track_state
        self.weather_state = weather_state
        self.car_snapshots = car_snapshots

    def get_public_view(self) -> List[CarSnapshot]:
        return self.car_snapshots