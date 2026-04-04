# src/sim/RaceState.py

from __future__ import annotations
from dataclasses import dataclass
from typing import List

# ===== PUBLIC CAR SNAPSHOT =====
@dataclass
class CarSnapshot:
    car_id: str
    team_id: str
    total_time: float
    tyre_compound: str
    tyre_age: float

class RaceState:
    def __init__(self):
        # ===== PUBLIC RACE STATE =====
        self.lap: int = 0
        self.track_state: str = "GREEN"
        self.weather_state: str = "DRY"
        self.car_snapshots: List[CarSnapshot] = []

    # ===== STATE UPDATE =====
    def update(self, lap: int, track_state: str, weather_state: str, car_snapshots: List[CarSnapshot]) -> None:
        # Basic sanity checks so the shared race state stays clean
        self.lap = max(0, int(lap))
        self.track_state = str(track_state).upper()
        self.weather_state = str(weather_state).upper()

        # Store a shallow copy so outside code does not accidentally mutate the live list
        self.car_snapshots = list(car_snapshots)

    # ===== PUBLIC ACCESS =====
    def get_public_view(self) -> List[CarSnapshot]:
        # Return a copy of the public snapshot list to avoid external mutation
        return list(self.car_snapshots)