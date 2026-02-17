# src/sim/RaceManager.py

from __future__ import annotations
import json
from typing import List

from src.sim.RaceState import RaceState, CarSnapshot
from src.agents.TeamAgent import TeamAgent
from src.agents.CarAgent import CarAgent, CarCalibration
from src.models.TyreModel import TyreModel, TyreState


class RaceManager:
    def __init__(self, season: str, circuit: str, total_laps: int, base_lap_time: float, lap_time_std: float, pit_loss: float):
        self.season = season
        self.circuit_name = circuit
        self.total_laps = total_laps
        self.base_lap_time = base_lap_time
        self.lap_time_std = lap_time_std
        self.pit_loss = pit_loss

        # Deterministic simulation clock (seconds)
        self.sim_time: float = 0.0

        # Fixed timestep (seconds of simulated time per tick)
        self.dt: float = 0.1  # smooth enough for UI later, still fast for optimisation

        # Public environment state
        self.lap_number = 0
        self.race_finished = False
        self.track_state = "GREEN"
        self.weather_state = "DRY"
        self.evolution_level = 0.0

        # Pit lane congestion
        self.cars_pitting_this_lap: int = 0

        # Shared public RaceState (partial observability)
        self.race_state = RaceState()

        with open("configs/tyre_compounds.json") as f:
            compound_data = json.load(f)

        self.compound_map = compound_data["season"][self.season][self.circuit_name]["compounds"]

        # ------------------------------------------
        # Load full circuit model (spatial)
        # ------------------------------------------
        with open("configs/circuits.json") as f:
            circuits_data = json.load(f)

        circuit_data = circuits_data[self.circuit_name]

        self.track_length = circuit_data["track_model"]["track_length"]
        self.raw_segments = circuit_data["track_model"]["segments"]
        self.drs_zones = circuit_data.get("drs_zones", [])
        self.characteristics = circuit_data.get("characteristics", {})

        # Build segment boundaries
        self.segment_boundaries = self._build_segment_boundaries()

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

        start_compound = self.compound_map["MEDIUM"]

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

                tyre_state = TyreState(compound=start_compound)

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
                compound_map=self.compound_map,
            )

            teams.append(team_agent)

        # Assign grid positions
        grid_spacing = 8.0
        pole_offset = -10.0  # Pole sits 10m behind the line

        for idx, car in enumerate(cars):
            grid_offset = pole_offset - (idx * grid_spacing)

            car.set_grid_position(
                grid_offset_m=grid_offset,
                track_length=self.track_length
            )

        return teams, cars

    # ==========================================================
    # SEGMENT BOUNDARIES
    # ==========================================================
    def _build_segment_boundaries(self):
        """
        Convert segment length list into (start, end, segment_dict)
        for fast lookup.
        """
        boundaries = []
        current_start = 0.0

        for seg in self.raw_segments:
            start = current_start
            end = start + seg["length"]

            boundaries.append({
                "start": start,
                "end": end,
                "data": seg
            })

            current_start = end

        # Safety check (optional)
        if abs(current_start - self.track_length) > 0.01:
            raise ValueError(f"Segment lengths ({current_start}) do not match track_length ({self.track_length})")

        return boundaries

    def get_segment_for_position(self, position: float):
        """
        Return segment dict for a given track position.
        """
        for seg in self.segment_boundaries:
            if seg["start"] <= position < seg["end"]:
                return seg["data"]

        return self.segment_boundaries[-1]["data"]

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

        snapshots.sort(key=lambda s: s.total_time)
        return snapshots

    def broadcast_public_signals(self) -> None:
        """
        Called once per lap (on lap boundary).
        Updates RaceState and passes public info to TeamAgents.
        """
        snapshots = self.build_car_snapshots()

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
    # DETERMINISTIC TICK RUN (no sleep)
    # ==========================================================
    def run(self):
        print("\nStarting Tick-Based MAS Simulation\n")

        # Initial broadcast at start of race (lap 0 -> about to start lap 1)
        self.broadcast_public_signals()
        for team in self.teams:
            team.decide()

        while not self.race_finished:
            self.step_tick(self.dt)

        self.print_final_classification()

    def format_time(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    # ==========================================================
    # TICK STEP (time + spatial)
    # ==========================================================
    def step_tick(self, dt: float):
        self.apply_spatial_dirty_air()
        self.sim_time += dt

        for car in self.cars:
            if car.retired:
                continue

            segment = self.get_segment_for_position(car.track_position)

            speed = car.compute_speed(
                segment=segment,
                track_length=self.track_length,
                base_lap_time=self.base_lap_time,
                lap_time_std=self.lap_time_std,
                evolution_level=self.evolution_level,
            )

            distance = speed * dt
            crossed_line = car.advance_position(distance, self.track_length)

            # Time passes for this car
            car.total_time += dt

            if crossed_line:
                car.update_tyre_wear()

        leader = min([c for c in self.cars if not c.retired], key=lambda c: c.total_time, default=None)

        if leader is not None:
            new_global_lap = leader.lap_count
            if new_global_lap > self.lap_number:
                self.lap_number = new_global_lap
                self.on_new_lap()

        if leader is not None and leader.lap_count >= self.total_laps:
            self.race_finished = True

    # ==========================================================
    # LAP EVENTS (broadcast/strategy/pit/reliability/evolution)
    # ==========================================================
    def on_new_lap(self):
        print(f"--- LAP {self.lap_number} COMPLETE ---\n")

        # Reliability check once per lap
        for car in self.cars:
            if not car.retired and car.check_reliability_failure():
                car.retired = True
                print(f"[Lap {self.lap_number}] {car.car_id} RETIRES (Mechanical)")

        # Track evolution progression
        self.evolution_level = min(1.0, self.evolution_level + 0.015)

        # Reset pit congestion counter ONCE per lap
        self.cars_pitting_this_lap = 0

        # Broadcast + teams decide at start of new lap
        self.broadcast_public_signals()
        for team in self.teams:
            team.decide()

        # Apply pits immediately (on lap boundary)
        for car in self.cars:
            if car.pending_pit and not car.retired:
                self.apply_pit_stop(car)

    # ==========================================================
    # PIT STOP APPLICATION (ENVIRONMENT RESPONSIBILITY)
    # ==========================================================
    def apply_pit_stop(self, car: CarAgent) -> None:
        pit_loss = self.pit_loss

        congestion_per_extra_car = 1.5
        congestion = self.cars_pitting_this_lap * congestion_per_extra_car
        pit_time_total = pit_loss + congestion

        self.cars_pitting_this_lap += 1

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
    def apply_spatial_dirty_air(self):
        """
        Apply dirty air + slipstream based on spatial proximity.
        """
        active_cars = [c for c in self.cars if not c.retired]

        active_cars.sort(key=lambda c: c.track_position, reverse=True)

        for car in active_cars:
            car.traffic_penalty = 0.0
            car.slipstream_bonus = 0.0
            car.following_intensity = 0.0

        for i in range(len(active_cars)):
            car = active_cars[i]
            car_ahead = active_cars[i - 1] if i > 0 else active_cars[-1]

            gap = car_ahead.track_position - car.track_position
            if gap <= 0:
                gap += self.track_length

            if gap < 15:
                car.traffic_penalty = 0.15
                car.slipstream_bonus = 0.05
                car.following_intensity = 1.0

            elif gap < 30:
                car.traffic_penalty = 0.10
                car.slipstream_bonus = 0.04
                car.following_intensity = 0.7

            elif gap < 50:
                car.traffic_penalty = 0.05
                car.slipstream_bonus = 0.02
                car.following_intensity = 0.4

    # ==========================================================
    # FINAL OUTPUT
    # ==========================================================
    def print_final_classification(self) -> None:
        print("\nFinal Classification\n")

        classified = sorted(
            [c for c in self.cars if not c.retired],
            key=lambda c: c.total_time,
        )

        retired = [c for c in self.cars if c.retired]

        position = 1
        winner_time = classified[0].total_time if classified else 0.0

        for car in classified:
            gap = car.total_time - winner_time

            if position == 1:
                gap_str = self.format_time(car.total_time)
            else:
                gap_str = f"+{self.format_time(gap)}"

            print(f"P{position:02d} | {car.car_id:<12} | {car.team_id:<18} | {gap_str}")
            position += 1

        for car in retired:
            print(f"P{position:02d} | {car.car_id:<12} | {car.team_id:<18} | DNF")
            position += 1