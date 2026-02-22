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
        self.pit_speed = 22.0  # TODO: move to circuit json later

        self.sim_time: float = 0.0
        self.dt: float = 0.1

        self.lap_number = 0
        self.race_finished = False
        self.track_state = "GREEN"
        self.weather_state = "DRY" # configuration + weather change if time allows
        self.evolution_level = 0.0
        self.winner_finish_time: float | None = None

        self.last_tower_print = -1
        self.cars_pitting_this_lap: int = 0
        self.race_state = RaceState()

        with open("configs/tyre_compounds.json") as f:
            compound_data = json.load(f)

        self.compound_map = compound_data["season"][self.season][self.circuit_name]["compounds"]

        # Load full circuit model
        with open("configs/circuits.json") as f:
            circuits_data = json.load(f)

        circuit_data = circuits_data[self.circuit_name]

        self.track_length = circuit_data["track_model"]["track_length"]
        self.raw_segments = circuit_data["track_model"]["segments"]
        self.drs_zones = circuit_data.get("drs_zones", [])
        self.characteristics = circuit_data.get("characteristics", {})

        # Track degradation multiplier from characteristics (abrasion + tyre stress)
        # Baseline is ~1.0 at value 3; higher values increase wear modestly.
        abrasion = float(self.characteristics.get("asphalt_abrasion", 3))
        tyre_stress = float(self.characteristics.get("tyre_stress", 3))
        self.track_deg_multiplier = 1.0 + 0.03 * (abrasion - 3.0) + 0.03 * (tyre_stress - 3.0)
        self.track_deg_multiplier = min(max(self.track_deg_multiplier, 0.80), 1.25)

        self.segment_boundaries = self.build_segment_boundaries()

        # Make DRS activation windows match real F1 behaviour:
        # clamp activation_start/end to actual straight segment intervals
        self.normalise_drs_zones()

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
                    reliability_prob=0.00008,
                )

                tyre_state = TyreState(compound=start_compound)

                car = CarAgent(
                    car_id=driver["name"],
                    team_id=team_name,
                    calibration=calibration,
                    tyre_state=tyre_state,
                    tyre_model=self.tyre_model,
                )

                # Ensure DRS eligibility dict exists (RaceManager uses this)
                if not hasattr(car, "drs_eligible_lap"):
                    car.drs_eligible_lap = {}

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
    # HELPER METHODS
    # ==========================================================
    def is_drs_enabled(self) -> bool:
        """
        Global DRS enable rule (race control): enabled from lap 3 onward in this simplified model,
        only under GREEN and DRY.
        """
        return (self.lap_number >= 2) and (self.track_state == "GREEN") and (self.weather_state == "DRY")

    @staticmethod
    def did_cross_marker(prev_pos: float, curr_pos: float, marker_pos: float) -> bool:
        """
        True if we crossed marker_pos moving from prev_pos to curr_pos on a circular track.
        """
        if prev_pos <= curr_pos:
            return prev_pos < marker_pos <= curr_pos
        # wrap-around
        return marker_pos > prev_pos or marker_pos <= curr_pos

    def is_pos_in_circular_window(self, pos: float, start: float, end: float) -> bool:
        """
        True if pos lies inside [start, end] on a circular track.
        Supports windows that wrap across start/finish (end < start).
        """
        if end >= start:
            return start <= pos <= end
        return pos >= start or pos <= end

    def step_car_tick(self, car: CarAgent, dt: float, drs_enabled: bool) -> None:
        """
        Step a single car for this tick (pit lane or on-track).
        """
        # Cooldowns tick down regardless of state (but harmless in pit)
        car.tick_cooldowns(dt)

        # Finished cars do nothing
        if car.lap_count >= self.total_laps:
            return

        if car.in_pit_lane:
            self.handle_pit_lane_tick(car, dt)
        else:
            self.handle_on_track_tick(car, dt, drs_enabled)

    def handle_pit_lane_tick(self, car: CarAgent, dt: float) -> None:
        """
        Pit lane tick: apply time penalty, move at pit-lane speed, finalise lap if S/F is crossed,
        and apply tyre change when pit completes.
        """
        crossed_line = car.update_pit_lane_tick(dt, self.pit_speed, self.track_length)

        if crossed_line:
            self.finalise_lap_if_crossed(car, crossed_line=True, apply_tyre_wear=False)

        car.complete_pit_if_done()

    def handle_on_track_tick(self, car: CarAgent, dt: float, drs_enabled: bool) -> None:
        """
        On-track tick: compute DRS state, maybe trigger overtake, compute speed, move car,
        update DRS eligibility, and finalise lap if crossed.
        """
        segment = self.get_segment_for_position(car.track_position)
        seg_type = segment.get("type", "straight")

        # 1) Update DRS active NOW (car mutates itself)
        car.update_drs_active(
            drs_enabled=drs_enabled,
            segment_type=seg_type,
            track_position=car.track_position,
            drs_zones=self.drs_zones,
            in_window_fn=self.is_pos_in_circular_window,
        )

        # 2) Overtake trigger uses *current tick* drs_active
        self.maybe_trigger_overtake(car, segment)

        # 3) Speed + move
        speed = car.compute_speed(
            segment=segment,
            track_length=self.track_length,
            base_lap_time=self.base_lap_time,
            lap_time_std=self.lap_time_std,
            evolution_level=self.evolution_level,
            track_deg_multiplier=self.track_deg_multiplier,
            drs_available=car.drs_active,
        )
        car.last_speed_mps = speed

        distance = speed * dt
        crossed_line = car.advance_position(distance, self.track_length)
        car.current_lap_time += dt

        # 4) DRS eligibility at detection points (car mutates itself)
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

        # 5) Lap complete
        if crossed_line:
            self.finalise_lap_if_crossed(car, crossed_line=True, apply_tyre_wear=True)

    def finalise_lap_if_crossed(self, car: CarAgent, crossed_line: bool, apply_tyre_wear: bool) -> None:
        """
        Finalise lap time, reset lap timer, optionally apply tyre wear, and set winner finish time.
        """
        if not crossed_line:
            return

        car.total_time += car.current_lap_time
        car.current_lap_time = 0.0

        if apply_tyre_wear:
            car.update_tyre_wear(self.track_deg_multiplier)

        if car.lap_count >= self.total_laps and self.winner_finish_time is None:
            self.winner_finish_time = car.total_time

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
            )

    def update_global_lap_and_events(self) -> None:
        """
        Update race lap counter based on on-road leader progress, trigger on_new_lap,
        and end race when all cars are finished/retired after a winner exists.
        """
        leader = max(
            [c for c in self.cars if not c.retired],
            key=lambda c: (c.lap_count, c.track_position),
            default=None,
        )

        if leader is not None:
            new_global_lap = leader.lap_count
            if new_global_lap > self.lap_number:
                self.lap_number = new_global_lap
                self.on_new_lap()

        if self.winner_finish_time is not None:
            if all(c.lap_count >= self.total_laps or c.retired for c in self.cars):
                self.race_finished = True

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
        # Update traffic/gaps/dirty-air first (NO overtake triggers here)
        self.apply_spatial_dirty_air()

        self.sim_time += dt
        drs_enabled = self.is_drs_enabled()

        # Step each car
        for car in self.cars:
            if car.retired:
                continue
            self.step_car_tick(car, dt, drs_enabled)

        # Resolve pairwise battles + swaps
        self.resolve_side_by_side_battles()

        # Lap progression + lap events
        self.update_global_lap_and_events()
            
    # ==========================================================
    # LAP EVENTS (broadcast/strategy/pit/reliability/evolution)
    # ==========================================================
    def on_new_lap(self):
        print(f"--- LAP {self.lap_number} COMPLETE ---\n")

        # Keep only stamps from this lap or immediately previous lap (S/F edge case support)
        for car in self.cars:
            d = getattr(car, "drs_eligible_lap", None)
            if isinstance(d, dict):
                for znum, stamp in list(d.items()):
                    if stamp < (self.lap_number - 1):
                        d.pop(znum, None)

        for car in self.cars:
            if not car.retired and car.check_reliability_failure():
                car.retired = True
                print(f"[Lap {self.lap_number}] {car.car_id} RETIRES (Mechanical)")

        self.evolution_level = min(1.0, self.evolution_level + 0.015)
        self.cars_pitting_this_lap = 0

        self.broadcast_public_signals()
        for team in self.teams:
            team.decide()

        for car in self.cars:
            if car.pending_pit and not car.retired:
                self.apply_pit_stop(car)

        self.print_timing_tower()

    def print_timing_tower(self):
        active = [c for c in self.cars if not c.retired]
        finished = [c for c in active if c.lap_count >= self.total_laps]
        running = [c for c in active if c.lap_count < self.total_laps]

        # Finished: time-based
        finished.sort(key=lambda c: c.total_time)

        # Running: on-road order is progress-based
        running.sort(key=lambda c: self.get_progress(c), reverse=True)

        print("\n--- Timing Tower (Mixed) ---")

        position = 1
        winner_time = finished[0].total_time if finished else None
        winner_progress_total = self.total_laps * self.track_length if winner_time is not None else None

        # 1) FINISHED first
        for car in finished:
            if winner_time is not None and position == 1:
                gap_str = self.format_time(car.total_time)
            elif winner_time is not None:
                gap_str = f"+{self.format_time(max(0.0, car.total_time - winner_time))}"
            else:
                gap_str = self.format_time(car.total_time)

            print(f"P{position:02d} {car.car_id:<5} | FINISHED {gap_str}")
            position += 1

        # 2) RUNNING next
        if running:
            leader = running[0]
            leader_prog = self.get_progress(leader)

            def fmt_gap_progress(gap_m: float, speed_mps: float) -> str:
                laps_down = int(gap_m // self.track_length)
                rem_m = gap_m - (laps_down * self.track_length)

                speed_mps = max(speed_mps, 1e-6)
                est_s = rem_m / speed_mps

                if laps_down > 0:
                    return f"+{laps_down}L +{rem_m:,.0f}m (~{est_s:.1f}s)"
                return f"+{rem_m:,.0f}m (~{est_s:.2f}s)"

            for i, car in enumerate(running):
                # Status for the car itself
                if car.in_pit_lane:
                    status = f"IN PIT ({max(0.0, car.pit_time_remaining):.1f}s)"
                else:
                    status = None

                prog = self.get_progress(car)

                # Ahead gap (on-road, progress-based)
                if i == 0:
                    gap_ahead_str = "-"
                else:
                    ahead = running[i - 1]
                    gap_ahead_m = max(0.0, self.get_progress(ahead) - prog)
                    gap_ahead_str = fmt_gap_progress(gap_ahead_m, car.last_speed_mps)

                # Reference gap
                if winner_time is not None and winner_progress_total is not None:
                    # After winner exists, use progress deficit to finished distance (stable mid-lap)
                    gap_to_winner_m = max(0.0, winner_progress_total - prog)
                    ref_label = "Winner"
                    gap_ref_str = fmt_gap_progress(gap_to_winner_m, car.last_speed_mps)
                else:
                    # Before winner exists, show gap to on-road leader
                    gap_to_leader_m = max(0.0, leader_prog - prog)
                    ref_label = "Leader"
                    gap_ref_str = "LEADER" if i == 0 else fmt_gap_progress(gap_to_leader_m, car.last_speed_mps)

                # If the car itself is in the pit, override the "Ahead" display with status (but keep ref gap meaningful)
                if status is not None:
                    gap_ahead_str = status

                print(
                    f"P{position:02d} "
                    f"{car.car_id:<5} "
                    f"| Ahead: {gap_ahead_str:<22} "
                    f"| {ref_label}: {gap_ref_str}"
                )
                position += 1

        # 3) DNFs last
        dnfs = [c for c in self.cars if c.retired]
        for car in dnfs:
            print(f"P{position:02d} {car.car_id:<5} | DNF")
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

        # Pit is modelled as time penalty + pit-lane traversal handled per-tick
        car.in_pit_lane = True
        car.pit_time_remaining = pit_time_total

        print(
            f"[Lap {self.lap_number+1}] {car.team_id} | {car.car_id} PIT "
            f"| base={pit_loss:.2f}s cong={congestion:.2f}s total_pit={pit_time_total:.2f}s "
            f"| race_total={car.total_time:.2f}s"
        )

        # Defer tyre change until pit finishes
        car.next_compound = car.pit_compound
        car.pit_compound = None
        car.pending_pit = False
    
    # ==========================================================
    # Traffic Logic
    # ==========================================================
    def apply_spatial_dirty_air(self):
        """
        Traffic model:
        - soft speed modifiers (converted into time deltas inside CarAgent via seg_frac)
        - computes nearest neighbours + gaps for DRS eligibility and racecraft
        (Overtake attempts are triggered in step_tick AFTER DRS state is computed.)
        """
        active_cars = [c for c in self.cars if not c.retired and not c.in_pit_lane]
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

            # Dirty air / slipstream as *lap-time deltas* (seconds), later distributed by seg_frac
            if car.gap_ahead < 10:
                car.traffic_penalty = 0.20
                car.slipstream_bonus = 0.12
                car.following_intensity = 0.8
                
            elif car.gap_ahead < 25:
                car.traffic_penalty = 0.10
                car.slipstream_bonus = 0.08
                car.following_intensity = 0.4
            
    def start_side_by_side(self, attacker: CarAgent, defender: CarAgent):
        if attacker.side_by_side_with is not None:
            return

        attacker.side_by_side_with = defender
        defender.side_by_side_with = attacker

        attacker.side_by_side_ticks = 5
        defender.side_by_side_ticks = 5

    def resolve_side_by_side_battles(self) -> None:
        """
        Resolve side-by-side battles when their tick timer expires and perform the position swap.
        """
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
                segment,
                self.track_length,
                self.base_lap_time,
                self.lap_time_std,
                self.evolution_level,
                self.track_deg_multiplier,
                car.drs_active,
            )
            speed_opponent = opponent.compute_speed(
                segment,
                self.track_length,
                self.base_lap_time,
                self.lap_time_std,
                self.evolution_level,
                self.track_deg_multiplier,
                opponent.drs_active,
            )

            speed_car += random.gauss(0, 0.5)
            speed_opponent += random.gauss(0, 0.5)

            winner, loser = (car, opponent) if speed_car > speed_opponent else (opponent, car)

            reference_progress = max(self.get_progress(winner), self.get_progress(loser))
            winner_new = reference_progress + (winner.car_length * 1.2)
            loser_new = winner_new - (winner.car_length * 1.5)

            winner.track_position = winner_new % self.track_length
            loser.track_position = loser_new % self.track_length

            winner.overtake_cooldown = 2.0
            loser.overtake_cooldown = 3.0
            winner.side_by_side_with = None
            loser.side_by_side_with = None

    def normalise_drs_zones(self) -> None:
        """
        Clamp each DRS zone's activation window to the parts of the track that are
        actually 'straight' segments. Supports activation windows that wrap across
        start/finish (activation_end < activation_start).

        Detection points are NOT changed (they can be in corners/braking, as in real F1).
        """
        if not self.drs_zones:
            return

        # Build list of straight intervals [(start, end), ...]
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
            # Convert possibly-wrapping window into linear intervals
            if end >= start:
                return [(start, end)]
            # wrap: [start, track_length) and [0, end]
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

            # Search best overlap between (possibly wrapped) activation window and straights
            best = None  # (overlap_length, new_start, new_end)
            for wa0, wa1 in window_to_intervals(a0, a1):
                for s0, s1 in straight_intervals:
                    ol = overlap_len(wa0, wa1, s0, s1)
                    if ol > 0:
                        ns = max(wa0, s0)
                        ne = min(wa1, s1)
                        if best is None or ol > best[0]:
                            best = (ol, ns, ne)

            if best is None:
                # No straight overlap; keep as-is
                new_zones.append(zone)
                continue

            _, ns, ne = best
            z = dict(zone)
            z["activation_start"] = ns
            z["activation_end"] = ne
            new_zones.append(z)

        self.drs_zones = new_zones

    def maybe_trigger_overtake(self, car: CarAgent, segment: dict) -> None:
        """
        Trigger an overtake attempt (enter side-by-side) only at realistic interaction points,
        using the car's CURRENT-TICK drs_active state.
        """
        if car.retired or car.in_pit_lane:
            return
        if car.car_ahead is None:
            return
        if car.side_by_side_with is not None or car.car_ahead.side_by_side_with is not None:
            return

        # Only consider overtakes at straights/braking zones (realistic interaction points)
        seg_type = segment.get("type", "straight")
        if seg_type not in ("straight", "braking"):
            return

        # Simple circuit-specific difficulty (use downforce/traction as proxy if present)
        traction = float(self.characteristics.get("traction", 3))
        downforce = float(self.characteristics.get("downforce", 3))
        overtake_difficulty = 1.0 + 0.05 * (3.0 - min(traction, downforce))

        if car.attempt_overtake(
            segment=segment,
            drs_available=car.drs_active,
            overtake_difficulty=overtake_difficulty
        ):
            self.start_side_by_side(car, car.car_ahead)

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