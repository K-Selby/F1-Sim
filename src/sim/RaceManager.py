# src/sim/RaceManager.py

from __future__ import annotations
import json
from typing import List
import random
from src.sim.RaceState import RaceState, CarSnapshot
from src.agents.TeamAgent import TeamAgent
from src.agents.CarAgent import CarAgent, CarCalibration
from src.models.TyreModel import TyreModel, TyreState

class RaceManager:
    def __init__(self, season: str, circuit: str, total_laps: int, base_lap_time: float, lap_time_std: float, pit_loss: float, seed: int | None = None):
        # Seeded randomness (for reproducible simulations)
        if seed is not None:
            random.seed(seed)
        
        self.season = season
        self.circuit_name = circuit
        self.total_laps = total_laps
        self.base_lap_time = base_lap_time
        self.lap_time_std = lap_time_std
        self.pit_loss = pit_loss
        self.pit_speed = 22.0 # add info to circuit file

        # simulation clock (seconds)
        self.sim_time: float = 0.0

        # Fixed timestep (seconds of simulated time per tick)
        self.dt: float = 0.1  # smooth enough for UI later, still fast for optimisation

        # Public environment state
        self.lap_number = 0
        self.race_finished = False
        self.track_state = "GREEN"
        self.weather_state = "DRY"
        self.evolution_level = 0.0
        self.winner_finish_time: float | None = None
        
        self.last_tower_print = -1
        
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
        self.segment_boundaries = self.build_segment_boundaries()

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
    def build_segment_boundaries(self):
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

    def get_progress(self, car: CarAgent) -> float:
        return (car.lap_count * self.track_length) + car.track_position

    # ==========================================================
    # PUBLIC STATE + BROADCAST
    # ==========================================================
    def build_car_snapshots(self) -> List[CarSnapshot]:
        snapshots: List[CarSnapshot] = []

        for car in self.cars:
            if car.retired:
                continue

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
            
            if car.in_pit_lane:
                car.pit_time_remaining -= dt
                car.current_lap_time += dt

                # Move in pit lane
                car.track_position += self.pit_speed * dt
                
                car.last_speed_mps = self.pit_speed

                # Handle start/finish crossing WHILE in pit lane
                if car.track_position >= self.track_length:
                    car.track_position -= self.track_length

                    # Lap is completed even if you're in the pits
                    car.lap_count += 1
                    car.total_time += car.current_lap_time
                    car.current_lap_time = 0.0

                    # Keep tyre/lap mechanics consistent (see note below)
                    car.update_tyre_wear()

                    # Winner capture (same logic as normal path)
                    if car.lap_count >= self.total_laps and self.winner_finish_time is None:
                        self.winner_finish_time = car.total_time

                if car.pit_time_remaining <= 0:
                    car.in_pit_lane = False
                    if getattr(car, "next_compound", None) is not None:
                        car.tyre_state.compound = car.next_compound
                        car.tyre_state.age_laps = 0
                        car.next_compound = None

                continue
            
            # Reduce overtake cooldown
            if car.overtake_cooldown > 0:
                car.overtake_cooldown = max(0.0, car.overtake_cooldown - dt)
            
            # IMPORTANT: once a car has finished, stop updating it
            if car.lap_count >= self.total_laps:
                continue

            segment = self.get_segment_for_position(car.track_position)

            speed = car.compute_speed(
                segment=segment,
                track_length=self.track_length,
                base_lap_time=self.base_lap_time,
                lap_time_std=self.lap_time_std,
                evolution_level=self.evolution_level,
            )
            
            car.last_speed_mps = speed

            distance = speed * dt
            crossed_line = car.advance_position(distance, self.track_length)

            # Time passes for this car
            car.current_lap_time += dt

            if crossed_line:
                # Commit lap time
                car.total_time += car.current_lap_time
                car.current_lap_time = 0.0
                car.update_tyre_wear()
                
                # Capture winner time at the exact finish moment
                if car.lap_count >= self.total_laps and self.winner_finish_time is None:
                    self.winner_finish_time = car.total_time

        # Resolve side-by-side battles
        processed_pairs = set()

        for car in self.cars:
            if car.side_by_side_with is None:
                continue

            opponent = car.side_by_side_with

            # Avoid resolving same pair twice
            pair_id = tuple(sorted([car.car_id, opponent.car_id]))
            if pair_id in processed_pairs:
                continue

            processed_pairs.add(pair_id)

            car.side_by_side_ticks -= 1
            opponent.side_by_side_ticks -= 1

            if car.side_by_side_ticks > 0:
                continue

            # Compute current segment
            segment = self.get_segment_for_position(car.track_position)

            speed_car = car.compute_speed(
                segment,
                self.track_length,
                self.base_lap_time,
                self.lap_time_std,
                self.evolution_level
            )

            speed_opponent = opponent.compute_speed(
                segment,
                self.track_length,
                self.base_lap_time,
                self.lap_time_std,
                self.evolution_level
            )

            # Add small battle randomness
            speed_car += random.gauss(0, 0.5)
            speed_opponent += random.gauss(0, 0.5)

            if speed_car > speed_opponent:
                winner = car
                loser = opponent
            else:
                winner = opponent
                loser = car

            winner_progress = self.get_progress(winner)
            loser_progress = self.get_progress(loser)

            reference_progress = max(winner_progress, loser_progress)

            winner_new = reference_progress + (winner.car_length * 1.2)
            loser_new = winner_new - (winner.car_length * 1.5)

            winner.track_position = winner_new % self.track_length
            loser.track_position = loser_new % self.track_length

            winner.overtake_cooldown = 2.0
            loser.overtake_cooldown = 3.0

            winner.side_by_side_with = None
            loser.side_by_side_with = None

        # Track-based leader (who crossed the line first)
        leader = max([c for c in self.cars if not c.retired], key = lambda c: (c.lap_count, c.track_position), default = None)

        if leader is not None:
            new_global_lap = leader.lap_count

            if new_global_lap > self.lap_number:
                self.lap_number = new_global_lap
                self.on_new_lap()

        if self.winner_finish_time is not None:
            # Wait until all active cars have also completed total_laps
            if all(c.lap_count >= self.total_laps or c.retired for c in self.cars):
                self.race_finished = True
                
        current_second = int(self.sim_time)

        if current_second % 80 == 0 and current_second != self.last_tower_print:
            self.print_timing_tower()
            self.last_tower_print = current_second
                    
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

    def print_timing_tower(self):
        racing = [c for c in self.cars if not c.retired and c.lap_count < self.total_laps]
        finished = [c for c in self.cars if not c.retired and c.lap_count >= self.total_laps]

        # Spatial order: leader is highest progress
        racing.sort(key=lambda c: self.get_progress(c), reverse=True)

        print("\n--- Timing Tower (Spatial) ---")

        position = 1

        if racing:
            leader = racing[0]
            leader_prog = self.get_progress(leader)

        for i, car in enumerate(racing):
            prog = self.get_progress(car)

            if i == 0:
                gap_ahead_str = "-"
                gap_leader_str = "LEADER"
            else:
                ahead = racing[i - 1]
                ahead_prog = self.get_progress(ahead)

                gap_ahead_m = max(0.0, ahead_prog - prog)
                gap_leader_m = max(0.0, leader_prog - prog)

                def fmt_gap(gap_m: float, speed_mps: float) -> str:
                    # Convert big gaps into +xL +ym
                    laps_down = int(gap_m // self.track_length)
                    rem_m = gap_m - (laps_down * self.track_length)

                    # Seconds estimate from last cached speed (never call compute_speed here)
                    speed_mps = max(speed_mps, 1e-6)
                    est_s = rem_m / speed_mps

                    if laps_down > 0:
                        return f"+{laps_down}L +{rem_m:,.0f}m (~{est_s:.1f}s)"
                    return f"+{rem_m:,.0f}m (~{est_s:.2f}s)"

                gap_ahead_str = fmt_gap(gap_ahead_m, car.last_speed_mps)
                gap_leader_str = fmt_gap(gap_leader_m, car.last_speed_mps)

            print(
                f"P{position:02d} "
                f"{car.car_id:<5} "
                f"| Ahead: {gap_ahead_str:<22} "
                f"| Leader: {gap_leader_str}"
            )

            position += 1

        # Finished cars (time-based, as you already do)
        for car in sorted(finished, key=lambda c: c.total_time):
            print(
                f"P{position:02d} "
                f"{car.car_id:<5} "
                f"| FINISHED {self.format_time(car.total_time)}"
            )
            position += 1

    # ==========================================================
    # PIT STOP APPLICATION (ENVIRONMENT RESPONSIBILITY)
    # ==========================================================
    def apply_pit_stop(self, car: CarAgent) -> None:
        pit_loss = self.pit_loss

        congestion_per_extra_car = 1.5
        congestion = self.cars_pitting_this_lap * congestion_per_extra_car
        pit_time_total = pit_loss + congestion

        self.cars_pitting_this_lap += 1

        car.in_pit_lane = True
        car.pit_time_remaining = pit_time_total

        print(
            f"[Lap {self.lap_number+1}] {car.team_id} | {car.car_id} PIT "
            f"| base={pit_loss:.2f}s cong={congestion:.2f}s total_pit={pit_time_total:.2f}s "
            f"| race_total={car.total_time:.2f}s"
        )

        # Defer tyre change until pit stop finishes
        car.next_compound = car.pit_compound

        # Clear pit request flags now
        car.pending_pit = False
        car.pit_compound = None
    
    # ==========================================================
    # Traffic Logic
    # ==========================================================
    def apply_spatial_dirty_air(self):
        """
        Clean traffic model:
        - No artificial time injection
        - No artificial position pushback
        - Only soft speed modifiers
        """
        active_cars = [c for c in self.cars if not c.retired and not c.in_pit_lane]

        # Sort by true race progress
        active_cars.sort(key=lambda c: self.get_progress(c), reverse=True)

        for car in active_cars:
            car.traffic_penalty = 0.0
            car.slipstream_bonus = 0.0
            car.following_intensity = 0.0
            car.car_ahead = None
            car.car_behind = None
            car.gap_ahead = float("inf")
            car.gap_behind = float("inf")

        for i in range(len(active_cars)):
            car = active_cars[i]

            car_ahead = active_cars[i - 1] if i > 0 else None
            car_behind = active_cars[i + 1] if i < len(active_cars) - 1 else None

            car_progress = self.get_progress(car)

            if car_ahead:
                ahead_progress = self.get_progress(car_ahead)
                gap = ahead_progress - car_progress

                car.car_ahead = car_ahead
                car.gap_ahead = max(0.0, gap)

            if car_behind:
                behind_progress = self.get_progress(car_behind)
                gap_b = car_progress - behind_progress

                car.car_behind = car_behind
                car.gap_behind = max(0.0, gap_b)

            # --- Soft dirty air only ---
            if car.gap_ahead < 10:
                car.traffic_penalty = 0.02
                car.slipstream_bonus = 0.015
                car.following_intensity = 0.8

            elif car.gap_ahead < 25:
                car.traffic_penalty = 0.01
                car.slipstream_bonus = 0.01
                car.following_intensity = 0.4

            # Overtake trigger (unchanged)
            if (car.car_ahead and 
                car.side_by_side_with is None and 
                car.car_ahead.side_by_side_with is None):
                
                if car.attempt_overtake():
                    self.start_side_by_side(car, car.car_ahead)
            
    def start_side_by_side(self, attacker: CarAgent, defender: CarAgent):
        if attacker.side_by_side_with is not None:
            return

        attacker.side_by_side_with = defender
        defender.side_by_side_with = attacker

        attacker.side_by_side_ticks = 5
        defender.side_by_side_ticks = 5

    # ==========================================================
    # FINAL OUTPUT
    # ==========================================================
    def print_final_classification(self) -> None:
        print("\nFinal Classification\n")

        # Classification MUST be time-based
        classified = sorted(
            [c for c in self.cars if not c.retired],
            key=lambda c: c.total_time
        )

        retired = [c for c in self.cars if c.retired]

        winner_time = classified[0].total_time

        position = 1

        for car in classified:
            final_time = car.total_time

            if position == 1:
                gap_str = self.format_time(final_time)
            else:
                gap_seconds = max(0.0, final_time - winner_time)
                gap_str = f"+{self.format_time(gap_seconds)}"

            print(
                f"P{position:02d} | "
                f"{car.car_id:<12} | "
                f"{car.team_id:<18} | "
                f"{gap_str} | "
                f"RAW={final_time:.3f}"
            )

            position += 1

        for car in retired:
            print(
                f"P{position:02d} | "
                f"{car.car_id:<12} | "
                f"{car.team_id:<18} | DNF"
            )
            position += 1