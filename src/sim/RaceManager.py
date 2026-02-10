from typing import Dict, List

from src.sim.RaceState import RaceState
from src.agents.CarAgent import CarAgent, CarCalibration
from src.agents.TeamAgent import TeamAgent
from src.models.TyreModel import TyreModel, TyreState


class RaceManager:
    """
    Environment agent.
    Owns the race clock and enforces physics.
    """

    def __init__(
        self,
        base_lap_time: float,
        track_deg_multiplier: float,
        total_laps: int,
        teams_json: Dict,
        tyres_json: Dict,
    ):
        self.base_lap_time = base_lap_time
        self.track_deg_multiplier = track_deg_multiplier

        self.race_state = RaceState(total_laps)
        self.tyre_model = TyreModel(tyres_json)

        self.cars: List[CarAgent] = []
        self.teams: List[TeamAgent] = []

        # 🔧 TEMP: hard-map starting tyre to real compound
        self.start_compound = "C3"  # MEDIUM ≈ C3

        self._build_agents(teams_json)

    def _build_agents(self, teams_json: Dict):
        for team_id, team_data in teams_json.items():
            calibration = CarCalibration(
                mu_team=team_data["performance"]["pace_offset"],
                k_team=team_data["performance"]["degradation_factor"],
            )

            team_cars: List[CarAgent] = []

            for idx in range(2):
                car_id = f"{team_id}_{idx+1}"

                tyre_state = TyreState(
                    compound=self.start_compound,
                    age_laps=0,
                )

                car = CarAgent(
                    car_id=car_id,
                    team_id=team_id,
                    calibration=calibration,
                    tyre_state=tyre_state,
                    tyre_model=self.tyre_model,
                )

                self.cars.append(car)
                team_cars.append(car)

            self.teams.append(TeamAgent(team_id, team_cars))

    def run(self):
        for lap in range(1, self.race_state.total_laps + 1):
            self.race_state.current_lap = lap

            # Teams observe and decide
            for team in self.teams:
                team.observe(self.race_state.team_view(team.team_id))
                team.decide(lap)

            # Cars execute one lap
            for car in self.cars:
                car.step_lap(
                    self.base_lap_time,
                    self.track_deg_multiplier,
                )

                self.race_state.update_car(
                    car_id=car.car_id,
                    team_id=car.team_id,
                    total_time=car.total_time,
                    lap=car.current_lap,
                    tyre=car.tyre_state.compound,
                    tyre_age=car.tyre_state.age_laps,
                )

        self._print_results()

    def _print_results(self):
        print("\nFinal Classification\n")
        for i, car in enumerate(self.race_state.classification(), start=1):
            print(
                f"P{i:02d} | {car.car_id:<10} | "
                f"{car.team_id:<12} | "
                f"{car.total_time:.2f}s | "
                f"{car.tyre}({car.tyre_age})"
            )