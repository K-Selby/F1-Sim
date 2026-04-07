from __future__ import annotations
import json
import os
import random
from datetime import datetime
from typing import List

from src.sim.RaceState import RaceState, CarSnapshot
from src.agents.TeamAgent import TeamAgent
from src.agents.CarAgent import CarAgent, CarCalibration
from src.models.TyreModel import TyreModel, TyreState

class RaceManager:
    def __init__(self, season: str, grandprix: str, circuit: str, total_laps: int, base_lap_time: float, lap_time_std: float, pit_loss: float, pit_speed: float, starting_grid: list | None = None, circuit_characteristics: dict | None = None, seed: int | None = None, config_filepath: str | None = None):
        # ===== CORE RACE SETUP =====
        self.seed = 0 if seed is None else int(seed)
        self.rng = random.Random(self.seed)
        self.season = season
        self.grandprix = grandprix
        self.circuit_name = circuit
        self.total_laps = max(1, int(total_laps))
        self.base_lap_time = max(0.0, float(base_lap_time))
        self.lap_time_std = max(0.0, float(lap_time_std))
        self.pit_loss = max(0.0, float(pit_loss))
        self.pit_speed = max(0.0, float(pit_speed))
        self.config_filepath = config_filepath
        self.custom_starting_grid = starting_grid if starting_grid is not None else []
        # ===== LIVE RACE STATE =====
        self.sim_time: float = 0.0
        self.dt: float = 1 / 120
        self.lap_number = 0
        self.race_finished = False
        self.track_state = "GREEN"
        self.weather_state = "DRY"
        self.evolution_level = 0.0
        self.winner_finish_time: float | None = None
        self.cars_pitting_this_lap: int = 0
        self.race_state = RaceState()
        self.last_logged_completed_lap = 0
        # ===== TYRE COMPOUND MAP =====
        with open("configs/tyre_compounds.json") as f:
            compound_data = json.load(f)
        self.compound_map = compound_data["season"][self.season][self.grandprix]["compounds"]
        # ===== CIRCUIT DATA =====
        with open("configs/circuits.json") as f:
            circuits_data = json.load(f)
        circuit_data = circuits_data[self.grandprix]
        self.track_length = float(circuit_data["track_model"]["track_length"])
        self.raw_segments = circuit_data["track_model"]["segments"]
        self.drs_zones = circuit_data.get("drs_zones", [])
        # ===== CIRCUIT CHARACTERISTICS =====
        self.characteristics = circuit_data.get("characteristics", {}).copy()
        if circuit_characteristics is not None:
            for name, value in circuit_characteristics.items():
                if value != "Default":
                    self.characteristics[name] = value
        abrasion = float(self.characteristics.get("asphalt_abrasion", 3))
        tyre_stress = float(self.characteristics.get("tyre_stress", 3))
        self.track_deg_multiplier = 1.0 + 0.03 * (abrasion - 3.0) + 0.03 * (tyre_stress - 3.0)
        self.track_deg_multiplier = min(max(self.track_deg_multiplier, 0.80), 1.25)
        # ===== PIT LANE MODEL =====
        pit_cfg = circuit_data.get("pit_lane", {}) or {}
        self.pit_enabled = bool(pit_cfg.get("enabled", False))
        self.pit_entry_point = float(pit_cfg.get("pit_entry_point", 0.0))
        self.pit_exit_point = float(pit_cfg.get("pit_exit_point", 0.0))
        self.pit_lane_distance = float(pit_cfg.get("pit_lane_distance", 0.0))
        self.pit_speed = float(pit_cfg.get("pit_speed_limit_mps", self.pit_speed))
        self.pit_service_time_mean = float(pit_cfg.get("service_time_mean", 2.5))
        self.pit_service_time_std = float(pit_cfg.get("service_time_std", 0.3))
        self.pit_box_position_m = float(pit_cfg.get("pit_box_position_m", self.pit_lane_distance * 0.45))
        self.team_box_busy: dict[str, CarAgent] = {}
        crosses_finish = self.pit_entry_point > self.pit_exit_point
        if crosses_finish:
            self.pit_line_position_m = self.track_length - self.pit_entry_point
            if self.pit_line_position_m > self.pit_lane_distance:
                self.pit_line_position_m = None
        else:
            self.pit_line_position_m = None
        # ===== TRACK MODEL HELPERS =====
        self.segment_boundaries = self.build_segment_boundaries()
        self.normalise_drs_zones()
        # ===== GRID + LOGGING =====
        self.teams, self.cars = self.build_grid()
        self.log_filepath = self.create_log_file()
        self.write_log_header()

    # ===== GRID BUILD =====
    def build_grid(self) -> tuple[List[TeamAgent], List[CarAgent]]:
        with open("configs/teams.json") as f:
            teams_json = json.load(f)[self.season]

        with open("configs/tyres.json") as f:
            tyres_json = json.load(f)

        self.tyre_model = TyreModel(tyres_json)

        teams: List[TeamAgent] = []
        cars: List[CarAgent] = []
        cars_by_config_id: dict[str, CarAgent] = {}

        start_compound = self.compound_map["HARD"]

        for team_name, team_data in teams_json.items():
            perf = team_data["performance"]
            drivers = team_data["drivers"][:2]
            car_objects: List[CarAgent] = []

            for driver in drivers:
                calibration = CarCalibration(
                    mu_team = float(perf["pace_offset"]),
                    k_team = float(perf["degradation_factor"]),
                    reliability_prob = 0.00008,
                )

                tyre_state = TyreState(
                    compound = start_compound,
                    age_laps = 0.0,
                    weekend_role = "MEDIUM",
                )

                car = CarAgent(
                    car_id = driver["name"],
                    team_id = team_name,
                    calibration = calibration,
                    tyre_state = tyre_state,
                    tyre_model = self.tyre_model,
                    rng = self.rng,
                )

                car.set_tyre_inventory({"SOFT": 1, "MEDIUM": 2, "HARD": 2,})

                if not hasattr(car, "drs_eligible_lap"):
                    car.drs_eligible_lap = {}

                cars.append(car)
                car_objects.append(car)

                config_driver_id = f"{driver['name']}_{driver['number']}_{team_name}"
                cars_by_config_id[config_driver_id] = car

            team_agent = TeamAgent(
                team_id = team_name,
                car_a = car_objects[0],
                car_b = car_objects[1],
                mu_team = float(perf["pace_offset"]),
                k_team = float(perf["degradation_factor"]),
                compound_map = self.compound_map,
            )

            teams.append(team_agent)

        grid_spacing = 8.0
        pole_offset = -10.0

        if self.custom_starting_grid:
            ordered_grid = sorted(self.custom_starting_grid, key=lambda item: item["position"])
            assigned_cars: list[CarAgent] = []

            for index, slot in enumerate(ordered_grid):
                driver_id = slot["driver_id"]

                if driver_id in cars_by_config_id:
                    car = cars_by_config_id[driver_id]
                    grid_offset = pole_offset - (index * grid_spacing)
                    car.set_grid_position(grid_offset_m=grid_offset, track_length=self.track_length)
                    assigned_cars.append(car)

            unassigned_cars = [car for car in cars if car not in assigned_cars]

            for index, car in enumerate(unassigned_cars, start=len(assigned_cars)):
                grid_offset = pole_offset - (index * grid_spacing)
                car.set_grid_position(grid_offset_m=grid_offset, track_length=self.track_length)

        else:
            for index, car in enumerate(cars):
                grid_offset = pole_offset - (index * grid_spacing)
                car.set_grid_position(grid_offset_m=grid_offset, track_length=self.track_length)

        return teams, cars

    # ===== BASIC HELPERS =====
    def is_drs_enabled(self) -> bool:
        return (self.lap_number >= 2) and (self.track_state == "GREEN") and (self.weather_state == "DRY")

    @staticmethod
    def did_cross_marker(prev_pos: float, curr_pos: float, marker_pos: float) -> bool:
        if prev_pos <= curr_pos:
            return prev_pos < marker_pos <= curr_pos
        return marker_pos > prev_pos or marker_pos <= curr_pos

    def is_pos_in_circular_window(self, pos: float, start: float, end: float) -> bool:
        if end >= start:
            return start <= pos <= end
        return pos >= start or pos <= end

    def set_car_progress(self, car: CarAgent, progress_m: float) -> None:
        progress_m = max(0.0, progress_m)
        car.lap_count = int(progress_m // self.track_length)
        car.track_position = progress_m % self.track_length
        car.prev_track_position = car.track_position

    def format_time(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    def get_expected_pit_time(self, service_time: float | None = None) -> float:
        # Build expected pit time from the same physical model the cars actually use.
        if not self.pit_enabled:
            return 0.0

        if self.pit_speed <= 0.0:
            return 0.0

        if service_time is None:
            service_time = self.pit_service_time_mean

        travel_time = self.pit_lane_distance / self.pit_speed
        total_time = travel_time + max(0.0, float(service_time))
        return total_time

    # ===== SEGMENT BOUNDARIES =====
    def build_segment_boundaries(self) -> list[dict]:
        # Turn the raw segment list into start / end ranges so position lookups are simple.
        boundaries = []
        current_start = 0.0

        for seg in self.raw_segments:
            start = current_start
            end = start + float(seg["length"])

            boundaries.append({
                "start": start,
                "end": end,
                "data": seg,
            })

            current_start = end

        if abs(current_start - self.track_length) > 0.01:
            raise ValueError(f"Segment lengths ({current_start}) do not match track_length ({self.track_length})")

        return boundaries

    def get_segment_for_position(self, position: float) -> dict:
        for seg in self.segment_boundaries:
            if seg["start"] <= position < seg["end"]:
                return seg["data"]

        return self.segment_boundaries[-1]["data"]

    def get_progress(self, car: CarAgent) -> float:
        # Convert both track running and pit-lane running into one comparable progress value.
        base_progress = car.lap_count * self.track_length

        if not car.in_pit_lane:
            return base_progress + car.track_position

        pit_frac = 0.0
        if car.pit_lane_total_m > 0:
            pit_frac = car.pit_lane_position_m / car.pit_lane_total_m

        if self.pit_exit_point >= self.pit_entry_point:
            race_distance_entry_to_exit = self.pit_exit_point - self.pit_entry_point
            
        else:
            race_distance_entry_to_exit = (self.track_length - self.pit_entry_point) + self.pit_exit_point

        equivalent_track_pos = (self.pit_entry_point + (pit_frac * race_distance_entry_to_exit)) % self.track_length
        return base_progress + equivalent_track_pos

    # ===== CAR TICK FLOW =====
    def step_car_tick(self, car: CarAgent, dt: float, drs_enabled: bool) -> None:
        car.tick_cooldowns(dt)

        if car.lap_count >= self.total_laps:
            return

        if car.in_pit_lane:
            self.handle_pit_lane_tick(car, dt)
            
        else:
            self.handle_on_track_tick(car, dt, drs_enabled)

    def handle_pit_lane_tick(self, car: CarAgent, dt: float) -> None:
        # Move the car through the pit lane and manage the team box if needed.
        previous_phase = car.pit_phase
        crossed_line = car.update_pit_lane_tick(dt, self.pit_speed)

        if crossed_line:
            car.lap_count += 1

            if not car.has_taken_race_start:
                car.has_taken_race_start = True
                car.current_lap_time = 0.0
                
            else:
                self.finalise_lap_if_crossed(car, crossed_line=True, apply_tyre_wear=False)

        if car.pit_phase == "queue":
            occupying_car = self.team_box_busy.get(car.team_id)

            if occupying_car is None:
                self.team_box_busy[car.team_id] = car
                car.pit_phase = "service"

        if previous_phase == "service" and car.pit_phase == "to_exit":
            if self.team_box_busy.get(car.team_id) is car:
                self.team_box_busy.pop(car.team_id, None)

        pit_completed = car.complete_pit_if_done()

        if pit_completed and car.current_pit_entry_sim_time is not None:
            car.last_pit_total_time_s = self.sim_time - car.current_pit_entry_sim_time
            car.current_pit_entry_sim_time = None

    def handle_on_track_tick(self, car: CarAgent, dt: float, drs_enabled: bool) -> None:
        # Run one normal on-track movement step for the car.
        segment = self.get_segment_for_position(car.track_position)
        seg_type = segment.get("type", "straight")

        car.update_drs_active(drs_enabled=drs_enabled, segment_type=seg_type, track_position=car.track_position, drs_zones=self.drs_zones, in_window_fn=self.is_pos_in_circular_window)
        self.maybe_trigger_overtake(car, segment)

        speed = car.compute_speed(
            segment=segment,
            track_length=self.track_length,
            base_lap_time=self.base_lap_time,
            lap_time_std=self.lap_time_std,
            evolution_level=self.evolution_level,
            track_deg_multiplier=self.track_deg_multiplier,
            drs_available=car.drs_active,
            total_laps=self.total_laps,
            track_state=self.track_state,
        )
        car.last_speed_mps = speed

        distance = speed * dt
        crossed_line, crossing_ratio = car.advance_position(distance, self.track_length)

        car.update_drs_eligibility(
            drs_enabled=drs_enabled,
            has_car_ahead=(car.car_ahead is not None),
            gap_ahead_m=car.gap_ahead,
            last_speed_mps=car.last_speed_mps,
            drs_zones=self.drs_zones,
            did_cross_marker_fn=self.did_cross_marker,
            prev_pos=car.prev_track_position,
            curr_pos=car.track_position,
        )

        self.maybe_enter_pit_lane(car)

        if crossed_line and not car.in_pit_lane:
            crossing_dt = dt * crossing_ratio
            overflow_dt = max(0.0, dt - crossing_dt)

            if not car.has_taken_race_start:
                car.has_taken_race_start = True
                car.current_lap_time = overflow_dt
                
            else:
                completed_lap_time = car.current_lap_time + crossing_dt
                self.finalise_lap_if_crossed(
                    car,
                    crossed_line=True,
                    apply_tyre_wear=True,
                    completed_lap_time=completed_lap_time,
                    next_lap_carry_time=overflow_dt,
                )
                
        else:
            car.current_lap_time += dt

    def finalise_lap_if_crossed(self, car: CarAgent, crossed_line: bool, apply_tyre_wear: bool, completed_lap_time: float | None = None, next_lap_carry_time: float = 0.0) -> None:
        # Finalise one lap and store the lap record.
        if not crossed_line:
            return

        completed_lap_number = car.lap_count
        lap_time = completed_lap_time if completed_lap_time is not None else car.current_lap_time

        car.total_time += lap_time
        car.current_lap_time = next_lap_carry_time

        if apply_tyre_wear:
            car.update_tyre_wear(self.track_deg_multiplier)

        car.completed_laps.append({
            "lap": completed_lap_number,
            "lap_time": lap_time,
            "total_time": car.total_time,
            "compound": car.tyre_state.compound,
            "tyre_age": car.tyre_state.age_laps,
            "weekend_role": car.tyre_state.weekend_role,
            "stint_id": car.current_stint_id,
        })

        if car.lap_count >= self.total_laps and self.winner_finish_time is None:
            self.winner_finish_time = car.total_time

    def maybe_enter_pit_lane(self, car: CarAgent) -> None:
        # Send the car into the pit lane once it reaches the entry point.
        if not self.pit_enabled:
            return

        if not car.pending_pit:
            return

        if car.in_pit_lane or car.retired:
            return

        if not self.did_cross_marker(car.prev_track_position, car.track_position, self.pit_entry_point):
            return

        self.apply_pit_stop(car)

    # ===== PUBLIC STATE + BROADCAST =====
    def build_car_snapshots(self) -> List[CarSnapshot]:
        # Build the public race view that the team agents can see.
        snapshots: List[CarSnapshot] = []

        active_cars = [car for car in self.cars if not car.retired]
        active_cars.sort(key=lambda c: self.get_progress(c), reverse=True)

        for car in active_cars:
            live_time = car.total_time + car.current_lap_time

            snapshots.append(
                CarSnapshot(
                    car_id=car.car_id,
                    team_id=car.team_id,
                    total_time=live_time,
                    tyre_compound=car.tyre_state.compound,
                    tyre_age=car.tyre_state.age_laps,
                )
            )

        return snapshots

    def broadcast_public_signals(self) -> None:
        # Push the latest race view into RaceState and all team agents.
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
                track_deg_multiplier=self.track_deg_multiplier,
                pit_lane_distance=self.pit_lane_distance,
                pit_speed=self.pit_speed,
                pit_box_position_m=self.pit_box_position_m,
                pit_service_time_mean=self.pit_service_time_mean,
            )

    def update_global_lap_and_events(self) -> None:
        # Update the global lap counter, logging, and finish state.
        active_cars = [car for car in self.cars if not car.retired]
        if not active_cars:
            self.race_finished = True
            return

        leader = max(active_cars, key=lambda c: (c.lap_count, c.track_position))

        new_global_lap = leader.lap_count
        if new_global_lap > self.lap_number:
            self.lap_number = new_global_lap
            self.on_new_lap()

        self.log_completed_laps_if_ready()

        if self.winner_finish_time is not None:
            if all(car.lap_count >= self.total_laps or car.retired for car in self.cars):
                self.race_finished = True

    # ===== MAIN TICK STEP =====
    def step_tick(self, dt: float) -> None:
        # Run one whole simulation tick.
        self.apply_spatial_dirty_air()

        self.sim_time += dt
        drs_enabled = self.is_drs_enabled()

        for car in self.cars:
            if car.retired:
                continue

            self.step_car_tick(car, dt, drs_enabled)

        self.resolve_side_by_side_battles()
        self.update_global_lap_and_events()

    # ===== LAP EVENTS =====
    def on_new_lap(self) -> None:
        # Run all once-per-lap events after the leader starts a new lap.
        for car in self.cars:
            drs_map = getattr(car, "drs_eligible_lap", None)
            if isinstance(drs_map, dict):
                for znum, stamp in list(drs_map.items()):
                    if stamp < (self.lap_number - 1):
                        drs_map.pop(znum, None)

        for car in self.cars:
            if not car.retired and car.check_reliability_failure():
                car.retired = True
                self.write_to_log(f"[Lap {self.lap_number}] {car.car_id} RETIRES (Mechanical)")

        race_progress = self.lap_number / max(1, self.total_laps)
        self.evolution_level = min(1.0, 1.0 - ((1.0 - race_progress) ** 2.2))
        self.cars_pitting_this_lap = 0

        self.broadcast_public_signals()

        for team in self.teams:
            team.decide()

    def get_lap_record(self, car: CarAgent, lap_number: int):
        for record in car.completed_laps:
            if record["lap"] == lap_number:
                return record
        return None

    # ===== OUTPUT / LOGS =====
    def create_log_file(self) -> str:
        folder_path = "data/RaceData/LoggedData"
        os.makedirs(folder_path, exist_ok=True)

        timestamp = datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
        file_name = f"RaceLog-{timestamp}.txt"
        file_path = os.path.join(folder_path, file_name)

        with open(file_path, "w", encoding="utf-8") as file:
            file.write("")

        return file_path

    def write_to_log(self, text: str) -> None:
        with open(self.log_filepath, "a", encoding="utf-8") as file:
            file.write(text + "\n")

    def write_log_header(self) -> None:
        self.write_to_log("F1 SIMULATION LOG:\n\n")
        self.write_to_log(f"Grand Prix: {self.grandprix}")
        self.write_to_log(f"Circuit: {self.circuit_name}")
        self.write_to_log(f"Season: {self.season}")
        self.write_to_log(f"Seed: {self.seed}")
        self.write_to_log(f"Config File: {self.config_filepath}")
        self.write_to_log(f"Total Laps: {self.total_laps}")
        self.write_to_log(f"Base Lap Time: {self.base_lap_time}")
        self.write_to_log(f"Lap Time Std: {self.lap_time_std}")
        self.write_to_log(f"Pit Loss: {self.pit_loss}")
        self.write_to_log(f"Pit Speed: {self.pit_speed}")
        self.write_to_log(f"Track Length: {self.track_length}")
        self.write_to_log(f"Circuit Characteristics: {self.characteristics}\n\n")
        self.write_to_log("Starting Grid:")

        ordered_grid = sorted(self.custom_starting_grid, key=lambda item: item["position"])
        for item in ordered_grid:
            self.write_to_log(f"P{item['position']:02d} - {item['driver_id']}")

        self.write_to_log("\n\nRACE EVENTS\n\n")

    def log_final_classification(self) -> None:
        self.write_to_log("\n\nFINAL CLASSIFICATION\n\n")

        classified = sorted([car for car in self.cars if not car.retired], key=lambda car: car.total_time)
        retired = [car for car in self.cars if car.retired]

        if not classified:
            for position, car in enumerate(retired, start=1):
                self.write_to_log(
                    f"P{position:02d} | "
                    f"{car.car_id:<12} | "
                    f"{car.team_id:<18} | DNF"
                )
            return

        winner_time = classified[0].total_time
        position = 1

        for car in classified:
            final_time = car.total_time

            if position == 1:
                gap_str = self.format_time(final_time)
            else:
                gap_seconds = max(0.0, final_time - winner_time)
                gap_str = f"+{self.format_time(gap_seconds)}"

            self.write_to_log(
                f"P{position:02d} | "
                f"{car.car_id:<12} | "
                f"{car.team_id:<18} | "
                f"{gap_str} | "
                f"RAW={final_time:.3f}"
            )

            position += 1

        for car in retired:
            self.write_to_log(
                f"P{position:02d} | "
                f"{car.car_id:<12} | "
                f"{car.team_id:<18} | DNF"
            )
            position += 1

    def log_completed_laps_if_ready(self) -> None:
        active_cars = [car for car in self.cars if not car.retired]

        if not active_cars:
            return

        highest_fully_completed_lap = min(car.lap_count for car in active_cars)

        while self.last_logged_completed_lap < highest_fully_completed_lap:
            lap_to_log = self.last_logged_completed_lap + 1
            self.log_lap_summary(lap_to_log)
            self.last_logged_completed_lap = lap_to_log

    def log_lap_summary(self, lap_number: int) -> None:
        self.write_to_log(f"--- LAP {lap_number} COMPLETE ---")

        lap_rows = []

        for car in self.cars:
            lap_record = self.get_lap_record(car, lap_number)
            if lap_record is not None:
                lap_rows.append({
                    "car": car,
                    "lap_time": lap_record["lap_time"],
                    "total_time": lap_record["total_time"],
                    "compound": lap_record["compound"],
                    "tyre_age": lap_record["tyre_age"],
                })

        lap_rows.sort(key=lambda item: item["total_time"])

        for position, row in enumerate(lap_rows, start=1):
            car = row["car"]

            self.write_to_log(
                f"P{position:02d} | "
                f"{car.car_id:<5} | "
                f"Lap Time: {self.format_time(row['lap_time'])} | "
                f"Total: {self.format_time(row['total_time'])} | "
                f"Tyre: {row['compound']} | "
                f"Age: {row['tyre_age']:.2f}"
            )

        self.write_to_log("")

    # ===== PIT STOP APPLICATION =====
    def apply_pit_stop(self, car: CarAgent) -> None:
        # Move the car into the pit lane and record the stop start.
        self.cars_pitting_this_lap += 1
        service_time = max(0.0, self.rng.gauss(self.pit_service_time_mean, self.pit_service_time_std))

        car.start_pit_stop(
            pit_lane_total_m=self.pit_lane_distance,
            pit_box_position_m=self.pit_box_position_m,
            pit_exit_track_pos=self.pit_exit_point,
            pit_service_time_s=service_time,
            pit_line_position_m=self.pit_line_position_m,
        )

        car.current_pit_entry_sim_time = self.sim_time

        self.write_to_log(
            f"[Lap {self.lap_number + 1}] {car.team_id} | {car.car_id} ENTER PIT "
            f"| service={service_time:.2f}s lane={self.pit_lane_distance:.0f}m"
        )

        car.next_compound = car.pit_compound
        car.pit_compound = None
        car.pending_pit = False

    # ===== TRAFFIC LOGIC =====
    def apply_spatial_dirty_air(self) -> None:
        # Update who is near who so slipstream, dirty air, and pressure all make sense.
        active_cars = [car for car in self.cars if not car.retired and not car.in_pit_lane]
        active_cars.sort(key=lambda car: self.get_progress(car), reverse=True)

        for car in active_cars:
            car.traffic_penalty = 0.0
            car.slipstream_bonus = 0.0
            car.following_intensity = 0.0
            car.car_ahead = None
            car.car_behind = None
            car.gap_ahead = float("inf")
            car.gap_behind = float("inf")

        for index, car in enumerate(active_cars):
            car_ahead = active_cars[index - 1] if index > 0 else None
            car_behind = active_cars[index + 1] if index < len(active_cars) - 1 else None
            car_progress = self.get_progress(car)

            if car_ahead is not None:
                ahead_progress = self.get_progress(car_ahead)
                gap = ahead_progress - car_progress
                car.car_ahead = car_ahead
                car.gap_ahead = max(0.0, gap)

            if car_behind is not None:
                behind_progress = self.get_progress(car_behind)
                gap_behind = car_progress - behind_progress
                car.car_behind = car_behind
                car.gap_behind = max(0.0, gap_behind)

            if car.gap_ahead < 10.0:
                car.traffic_penalty = 0.16
                car.slipstream_bonus = 0.10
                car.following_intensity = 0.75

            elif car.gap_ahead < 25.0:
                car.traffic_penalty = 0.07
                car.slipstream_bonus = 0.05
                car.following_intensity = 0.35

    def start_side_by_side(self, attacker: CarAgent, defender: CarAgent) -> None:
        # Mark two cars as fighting side by side for a short period.
        if attacker.side_by_side_with is not None:
            return

        attacker.side_by_side_with = defender
        defender.side_by_side_with = attacker
        attacker.side_by_side_ticks = 5
        defender.side_by_side_ticks = 5

    def resolve_side_by_side_battles(self) -> None:
        # Resolve ongoing side-by-side fights and decide who comes out ahead.
        processed_pairs = set()

        for car in self.cars:
            if car.side_by_side_with is None:
                continue

            opponent = car.side_by_side_with
            pair_id = tuple(sorted([car.car_id, opponent.car_id]))

            if pair_id in processed_pairs:
                continue

            processed_pairs.add(pair_id)

            car.side_by_side_ticks -= 1
            opponent.side_by_side_ticks -= 1

            if car.side_by_side_ticks > 0:
                continue

            segment = self.get_segment_for_position(car.track_position)

            speed_car = car.compute_speed(
                segment=segment,
                track_length=self.track_length,
                base_lap_time=self.base_lap_time,
                lap_time_std=self.lap_time_std,
                evolution_level=self.evolution_level,
                track_deg_multiplier=self.track_deg_multiplier,
                drs_available=car.drs_active,
                total_laps=self.total_laps,
                track_state=self.track_state,
            )
            
            speed_opponent = opponent.compute_speed(
                segment=segment,
                track_length=self.track_length,
                base_lap_time=self.base_lap_time,
                lap_time_std=self.lap_time_std,
                evolution_level=self.evolution_level,
                track_deg_multiplier=self.track_deg_multiplier,
                drs_available=opponent.drs_active,
                total_laps=self.total_laps,
                track_state=self.track_state,
            )

            speed_car += self.rng.gauss(0.0, 0.20)
            speed_opponent += self.rng.gauss(0.0, 0.20)

            winner, loser = (car, opponent) if speed_car > speed_opponent else (opponent, car)

            winner_progress = self.get_progress(winner)
            loser_progress = self.get_progress(loser)

            front_progress = max(winner_progress, loser_progress)
            back_progress = min(winner_progress, loser_progress)

            target_gap = winner.car_length * 1.15
            winner_new_progress = front_progress + (0.20 * winner.car_length)
            loser_new_progress = winner_new_progress - target_gap

            front_lap = int(front_progress // self.track_length)
            back_lap = int(back_progress // self.track_length)

            if int(winner_new_progress // self.track_length) != front_lap:
                winner_new_progress = front_progress

            if int(loser_new_progress // self.track_length) != back_lap:
                loser_new_progress = max(back_progress - 0.10 * loser.car_length, 0.0)

            self.set_car_progress(winner, winner_new_progress)
            self.set_car_progress(loser, loser_new_progress)

            winner.overtake_cooldown = 2.0
            loser.overtake_cooldown = 3.0

            winner.side_by_side_with = None
            loser.side_by_side_with = None
            winner.side_by_side_ticks = 0
            loser.side_by_side_ticks = 0

    # ===== DRS ZONE NORMALISATION =====
    def normalise_drs_zones(self) -> None:
        # Clamp DRS activation windows so they sit on straights only.
        if not self.drs_zones:
            return

        straight_intervals: list[tuple[float, float]] = []
        for seg in self.segment_boundaries:
            seg_type = seg["data"].get("type", "straight")
            if seg_type == "straight":
                straight_intervals.append((float(seg["start"]), float(seg["end"])))

        if not straight_intervals:
            return

        def overlap_len(a0: float, a1: float, b0: float, b1: float) -> float:
            return max(0.0, min(a1, b1) - max(a0, b0))

        def window_to_intervals(start: float, end: float) -> list[tuple[float, float]]:
            if end >= start:
                return [(start, end)]
            return [(start, float(self.track_length)), (0.0, end)]

        new_zones = []

        for zone in self.drs_zones:
            try:
                a0 = float(zone["activation_start"])
                a1 = float(zone["activation_end"])
            except (KeyError, ValueError, TypeError):
                new_zones.append(zone)
                continue

            if a0 == a1:
                new_zones.append(zone)
                continue

            best = None

            for wa0, wa1 in window_to_intervals(a0, a1):
                for s0, s1 in straight_intervals:
                    overlap = overlap_len(wa0, wa1, s0, s1)
                    if overlap > 0:
                        new_start = max(wa0, s0)
                        new_end = min(wa1, s1)

                        if best is None or overlap > best[0]:
                            best = (overlap, new_start, new_end)

            if best is None:
                new_zones.append(zone)
                continue

            _, new_start, new_end = best
            updated_zone = dict(zone)
            updated_zone["activation_start"] = new_start
            updated_zone["activation_end"] = new_end
            new_zones.append(updated_zone)

        self.drs_zones = new_zones

    # ===== OVERTAKING =====
    def maybe_trigger_overtake(self, car: CarAgent, segment: dict) -> None:
        # Decide if a car should start a side-by-side attack.
        if self.track_state != "GREEN":
            return

        if car.retired or car.in_pit_lane:
            return

        if car.car_ahead is None:
            return

        if car.side_by_side_with is not None or car.car_ahead.side_by_side_with is not None:
            return

        seg_type = segment.get("type", "straight")
        if seg_type not in ("straight", "braking"):
            return

        traction = float(self.characteristics.get("traction", 3))
        downforce = float(self.characteristics.get("downforce", 3))
        overtake_difficulty = 1.0 + 0.05 * (3.0 - min(traction, downforce))

        if car.attempt_overtake(segment=segment, drs_available=car.drs_active, overtake_difficulty=overtake_difficulty):
            self.start_side_by_side(car, car.car_ahead)