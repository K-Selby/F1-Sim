from dataclasses import dataclass

from src.models.TyreModel import TyreModel, TyreState


@dataclass
class CarCalibration:
    mu_team: float        # pace offset (seconds)
    k_team: float         # degradation multiplier


class CarAgent:
    """
    Car agent.
    Executes laps and pit stops.
    Does NOT decide strategy.
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
        self.calibration = calibration
        self.tyre_state = tyre_state
        self.tyre_model = tyre_model

        self.total_time: float = 0.0
        self.current_lap: int = 0
        self.has_pitted: bool = False

    def pit(self, new_compound: str):
        """
        Execute a pit stop.
        Compound MUST be C1–C5.
        """
        self.tyre_state = TyreState(
            compound=new_compound,
            age_laps=0
        )
        self.has_pitted = True

    def step_lap(
        self,
        base_lap_time: float,
        track_deg_multiplier: float,
    ):
        """
        Run one clean-air lap.
        """
        self.current_lap += 1

        tyre_delta = self.tyre_model.lap_delta(
            tyre_state=self.tyre_state,
            track_deg_multiplier=track_deg_multiplier,
            team_deg_factor=self.calibration.k_team,
        )

        lap_time = (
            base_lap_time
            + self.calibration.mu_team
            + tyre_delta
        )

        self.total_time += lap_time

        # Tyres age after lap completes
        self.tyre_state.age_laps += 1