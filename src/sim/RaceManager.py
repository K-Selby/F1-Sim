# src/sim/RaceManager.py

from __future__ import annotations
import time
import json
from typing import List

from src.sim.RaceState import RaceState, CarSnapshot
from src.agents.TeamAgent import TeamAgent
from src.agents.CarAgent import CarAgent, CarCalibration
from src.models.TyreModel import TyreModel, TyreState


class RaceManager:

    def __init__(self, season: str, total_laps: int, base_lap_time: float, track_deg_multiplier: float, lap_time_std: float, pit_loss: float, sim_speed: float = 10.0):

        self.season = season
        self.total_laps = total_laps
        self.base_lap_time = base_lap_time
        self.track_deg_multiplier = track_deg_multiplier
        self.lap_time_std = lap_time_std
        self.pit_loss = pit_loss
        self.sim_speed = sim_speed

        self.lap_number = 0
        self.sector_number = 0
        self.race_finished = False

        self.track_state = "GREEN"
        self.weather_state = "DRY"
        self.evolution_level = 0.0

        self.race_state = RaceState()

        self.teams, self.cars = self._build_grid()

    # ==========================================================
    # GRID BUILD
    # ==========================================================

    def _build_grid(self):

        with open("configs/teams.json") as f:
            teams_json = json.load(f)[self.season]

        with open("configs/tyres.json") as f:
            tyres_json = json.load(f)

        tyre_model = TyreModel(tyres_json)

        teams: List[TeamAgent] = []
        cars: List[CarAgent] = []

        for team_name, team_data in teams_json.items():

            perf = team_data["performance"]
            drivers = team_data["drivers"][:2]

            car_objects = []

            for driver in drivers:

                calibration = CarCalibration(
                    mu_team=float(perf["pace_offset"]),
                    k_team=float(perf["degradation_factor"]),
                    reliability_prob=0.001,
                )

                tyre_state = TyreState(compound="C2")

                car = CarAgent(
                    car_id=driver["name"],
                    team_id=team_name,
                    calibration=calibration,
                    tyre_state=tyre_state,
                    tyre_model=tyre_model,
                )

                cars.append(car)
                car_objects.append(car)
                
            print(f"\nTeam: {team_name}")
            print("Car A calibration id:", id(car_objects[0].calibration))
            print("Car B calibration id:", id(car_objects[1].calibration))

            team_agent = TeamAgent(
                team_id=team_name,
                car_a=car_objects[0],
                car_b=car_objects[1],
                mu_team=float(perf["pace_offset"]),
                k_team=float(perf["degradation_factor"]),
            )

            teams.append(team_agent)

        return teams, cars

    # ==========================================================
    # REAL-TIME RUN
    # ==========================================================

    def run(self):

        print("\nStarting Real-Time MAS Simulation\n")

        sim_time = 0.0
        last_time = time.time()

        seconds_per_lap = self.base_lap_time
        seconds_per_sector = seconds_per_lap / 3

        next_trigger = seconds_per_sector

        while not self.race_finished:

            now = time.time()
            delta = now - last_time
            last_time = now

            sim_time += delta * self.sim_speed

            if sim_time >= next_trigger:
                self.step_sector(seconds_per_sector)
                next_trigger += seconds_per_sector

            time.sleep(0.001)

        self.print_final_classification()

    # ==========================================================
    # SECTOR STEP
    # ==========================================================

    def step_sector(self, sector_time):

        self.sector_number += 1

        if self.sector_number == 1:
            for team in self.teams:
                team.decide()

        for car in self.cars:
            car.step_sector(sector_base_time=self.base_lap_time / 3, track_deg_multiplier=self.track_deg_multiplier, lap_time_std=self.lap_time_std)

        print(f"Lap {self.lap_number+1} - Sector {self.sector_number}")

        if self.sector_number == 3:
            self.end_lap()
            
        for car in self.cars:
            if car.pending_pit and not car.retired:
                self.apply_pit_stop(car)

    def apply_pit_stop(self, car: CarAgent) -> None:
        """
        Apply pit stop time loss and change tyres.
        """
        pit_loss = self.pit_loss

        car.total_time += pit_loss

        # Change tyres
        car.tyre_state.compound = car.pit_compound
        car.tyre_state.age_laps = 0

        car.pending_pit = False
        car.pit_compound = None

    # ==========================================================
    # LAP END
    # ==========================================================

    def end_lap(self):

        self.lap_number += 1
        self.sector_number = 0

        print(f"--- LAP {self.lap_number} COMPLETE ---\n")

        if self.lap_number >= self.total_laps:
            self.race_finished = True

    # ==========================================================
    # FINAL OUTPUT
    # ==========================================================

    def print_final_classification(self) -> None:
        print("\nFinal Classification\n")

        # Finished cars
        classified = sorted(
            [c for c in self.cars if not c.retired],
            key=lambda c: c.total_time,
        )

        # Retired cars
        retired = [c for c in self.cars if c.retired]

        position = 1

        # Print finishers
        for car in classified:
            print(
                f"P{position:02d} | {car.car_id:<5} | {car.team_id:<18} "
                f"| {car.total_time:.2f}s"
            )
            position += 1

        # Print DNFs
        for car in retired:
            print(
                f"P{position:02d} | {car.car_id:<5} | {car.team_id:<18} "
                f"| DNF"
            )
            position += 1