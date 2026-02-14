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
    def __init__(self, season: str, circuit: str, total_laps: int, base_lap_time: float, track_deg_multiplier: float, lap_time_std: float, pit_loss: float, sim_speed: float):
        self.season = season
        self.circuit_name = circuit
        self.total_laps = total_laps
        self.base_lap_time = base_lap_time
        self.track_deg_multiplier = track_deg_multiplier
        self.lap_time_std = lap_time_std
        self.pit_loss = pit_loss
        self.sim_speed = sim_speed
        
        # Public environment state
        self.lap_number = 0
        self.sector_number = 0
        self.race_finished = False
        self.track_state = "GREEN"
        self.weather_state = "DRY"
        self.evolution_level = 0.0
        
        # Safety car timing multipliers (for pit advantage)
        self.sc_lap_time_factor = 1.4
        # Pit lane congestion
        self.cars_pitting_this_lap: int = 0

        # Shared public RaceState (partial observability)
        self.race_state = RaceState()
        
        with open("configs/tyre_compounds.json") as f:
            compound_data = json.load(f)

        self.compound_map = compound_data["season"][self.season][self.circuit_name]["compounds"]

        self.teams, self.cars = self.build_grid()

    # ==========================================================
    # GRID BUILD
    # ==========================================================
    def build_grid(self):
        with open("configs/teams.json") as f:
            teams_json = json.load(f)[self.season]

        with open("configs/tyres.json") as f:
            tyres_json = json.load(f)

        self.tyre_model = TyreModel(tyres_json)

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
                    reliability_prob=0.0008,
                )

                tyre_state = TyreState(compound="C2")

                car = CarAgent(
                    car_id=driver["name"],
                    team_id=team_name,
                    calibration=calibration,
                    tyre_state=tyre_state,
                    tyre_model=self.tyre_model,
                )

                cars.append(car)
                car_objects.append(car)

            team_agent = TeamAgent(
                team_id=team_name,
                car_a=car_objects[0],
                car_b=car_objects[1],
                mu_team=float(perf["pace_offset"]),
                k_team=float(perf["degradation_factor"]),
                available_compounds=self.compound_map,
            )

            teams.append(team_agent)

        return teams, cars
    
    # ==========================================================
    # PUBLIC STATE + BROADCAST
    # ==========================================================
    def build_car_snapshots(self) -> List[CarSnapshot]:
        snapshots: List[CarSnapshot] = []

        for car in self.cars:
            if car.retired:
                continue

            snapshots.append(
                CarSnapshot(
                    car_id=car.car_id,
                    team_id=car.team_id,
                    total_time=car.total_time,
                    tyre_compound=car.tyre_state.compound,
                    tyre_age=car.tyre_state.age_laps,
                )
            )

        # Sort by race time = "public timing screen"
        snapshots.sort(key=lambda s: s.total_time)
        return snapshots

    def broadcast_public_signals(self) -> None:
        """
        Called once per lap (at Sector 1).
        Updates RaceState and passes public info to TeamAgents.
        """

        snapshots = self.build_car_snapshots()

        # IMPORTANT: broadcast "current lap" as the lap we're ABOUT TO run
        current_lap = self.lap_number + 1

        self.race_state.update(
            lap=current_lap,
            track_state=self.track_state,
            weather_state=self.weather_state,
            car_snapshots=snapshots,
        )

        for team in self.teams:
            team.observe(
                race_view=snapshots,
                lap=self.lap_number,
                track_state=self.track_state,
                pit_loss=self.pit_loss,
                base_lap_time=self.base_lap_time,
                tyre_model=self.tyre_model,
                total_laps=self.total_laps,
            )

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

        # ----------------------------
        # Start of lap (Sector 1)
        # ----------------------------
        if self.sector_number == 1:
            # Reset pit congestion counter ONCE per lap
            self.cars_pitting_this_lap = 0

            # Update public state + teams observe
            self.broadcast_public_signals()

            # Teams decide (may set car.pending_pit)
            for team in self.teams:
                team.decide()

            # Apply any pit stops BEFORE sector running (pit happens on lap boundary)
            for car in self.cars:
                if car.pending_pit and not car.retired:
                    self.apply_pit_stop(car)
                    
        self.apply_gap_based_dirty_air()

        for car in self.cars:
            car.step_sector(sector_base_time=self.base_lap_time / 3, track_deg_multiplier=self.track_deg_multiplier, lap_time_std=self.lap_time_std)

        print(f"Lap {self.lap_number+1} - Sector {self.sector_number}")

        if self.sector_number == 3:
            self.end_lap()

    # ==========================================================
    # PIT STOP APPLICATION (ENVIRONMENT RESPONSIBILITY)
    # ==========================================================
    def apply_pit_stop(self, car: CarAgent) -> None:
        pit_loss = self.pit_loss

        # Safety Car / VSC advantage (step 4)
        if self.track_state == "SC":
            pit_loss *= 0.60
        elif self.track_state == "VSC":
            pit_loss *= 0.80

        # --- Pit lane congestion (ADD THIS HERE) ---
        congestion_per_extra_car = 1.5  # tune later
        congestion = self.cars_pitting_this_lap * congestion_per_extra_car
        pit_time_total = pit_loss + congestion

        # Count this car as pitting this lap (important this happens after using the current count)
        self.cars_pitting_this_lap += 1

        # Apply time
        car.total_time += pit_time_total

        print(
            f"[Lap {self.lap_number+1}] {car.team_id} | {car.car_id} PIT "
            f"| base={pit_loss:.2f}s cong={congestion:.2f}s total_pit={pit_time_total:.2f}s "
            f"| race_total={car.total_time:.2f}s"
        )

        car.tyre_state.compound = car.pit_compound
        car.tyre_state.age_laps = 0
        car.pending_pit = False
        car.pit_compound = None

    # ==========================================================
    # Traffic Logic
    # ==========================================================
    def apply_gap_based_dirty_air(self):
        if self.track_state != "GREEN":
            return

        sorted_cars = sorted(self.cars, key=lambda c: c.total_time)

        for car in sorted_cars:
            car.traffic_penalty = 0.0
            car.slipstream_bonus = 0.0
            car.following_intensity = 0.0

        for i in range(1, len(sorted_cars)):
            car = sorted_cars[i]
            car_ahead = sorted_cars[i - 1]

            if car.retired:
                continue

            gap = car.total_time - car_ahead.total_time

            if gap < 0.7:
                car.traffic_penalty = 0.12
                car.slipstream_bonus = 0.04
                car.following_intensity = 1.0

            elif gap < 1.2:
                car.traffic_penalty = 0.08
                car.slipstream_bonus = 0.03
                car.following_intensity = 0.7

            elif gap < 1.8:
                car.traffic_penalty = 0.04
                car.slipstream_bonus = 0.02
                car.following_intensity = 0.4

    # ==========================================================
    # LAP END
    # ==========================================================
    def end_lap(self):
        # Reliability check once per lap
        for car in self.cars:
            if not car.retired:
                if car.check_reliability_failure():
                    car.retired = True
                    print(f"[Lap {self.lap_number+1}] {car.car_id} RETIRES (Mechanical)")
        
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