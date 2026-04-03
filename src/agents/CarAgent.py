from __future__ import annotations
import random
from dataclasses import dataclass
from typing import Optional

from src.models.TyreModel import TyreModel, TyreState


@dataclass
class CarCalibration:
    mu_team: float
    k_team: float
    reliability_prob: float = 0.0


class CarAgent:
    def __init__(self, car_id: str, team_id: str, calibration: CarCalibration, tyre_state: TyreState, tyre_model: TyreModel, rng):        
        self.car_id = car_id
        self.team_id = team_id
        self.calibration = calibration
        self.car_length = 5.5
        self.tyre_state = tyre_state
        self.tyre_model = tyre_model
        self.rng = rng
        self.instruction: Optional[str] = None
        self.total_time: float = 0.0
        self.current_lap_time: float = 0.0
        self.retired: bool = False

        # Pit / strategy flags
        self.pending_pit: bool = False
        self.pit_compound: Optional[str] = None
        self.next_compound: Optional[str] = None
        self.next_role: Optional[str] = None
        self.in_pit_lane: bool = False
        self.pit_stops_made: int = 0
        self.current_stint_id: int = 1

        # Tyre set inventory for the race weekend allocation used in the sim.
        # This includes the starting tyre, so the starting set is removed when assigned.
        self.tyre_set_inventory: dict[str, int] = {
            "SOFT": 1,
            "MEDIUM": 2,
            "HARD": 2,
        }

        # Stint plan / pit review window
        self.strategy_plan_stint_id: int = 0
        self.stint_min_review_age: float = 0.0
        self.stint_target_age: float = 0.0
        self.stint_max_age: float = 0.0
        self.last_strategy_call_lap: int = -1
        
        

        # Dry compound legality tracking
        self.used_dry_compounds: set[str] = set()
        if self.tyre_state.compound not in {"INTERMEDIATE", "WET"}:
            self.used_dry_compounds.add(self.tyre_state.compound)

        # Separate pit-lane spatial state
        self.pit_lane_position_m: float = 0.0
        self.pit_lane_total_m: float = 0.0
        self.pit_box_position_m: float = 0.0
        self.pit_exit_track_pos: float = 0.0
        self.pit_line_position_m: float | None = None
        self.pit_line_crossed: bool = False
        self.pit_service_remaining_s: float = 0.0
        self.pit_phase: str = "none"

        # Traffic effects
        self.traffic_penalty = 0.0
        self.slipstream_bonus = 0.0
        self.following_intensity = 0.0
        self.last_speed_mps: float = 0.0
        self.side_by_side_with: Optional[CarAgent] = None
        self.side_by_side_ticks: int = 0
        self.overtake_cooldown: float = 0.0
        self.car_ahead: Optional[CarAgent] = None
        self.car_behind: Optional[CarAgent] = None
        self.gap_ahead: float = float("inf")
        self.gap_behind: float = float("inf")

        # DRS
        self.drs_eligible_lap: dict[int, int] = {}
        self.drs_active: bool = False

        # Spatial state
        self.track_position: float = 0.0
        self.lap_count: int = 0
        self.completed_laps: list[dict] = []
        self.has_taken_race_start = False

        # Variance
        self.lap_execution_noise: float = 0.0
        self.last_lap_for_noise: int = -1

    # ==========================================================
    # SPATIAL HELPERS
    # ==========================================================
    def set_grid_position(self, grid_offset_m: float, track_length: float) -> None:
        self.track_position = grid_offset_m % track_length
        self.lap_count = 0
        self.has_taken_race_start = False
        self.drs_eligible_lap = {}
        self.drs_active = False
        self.prev_track_position: float = self.track_position

    def advance_position(self, distance_m: float, track_length: float) -> tuple[bool, float]:
        self.prev_track_position = self.track_position

        old_pos = self.track_position
        new_pos = old_pos + distance_m
        crossed_line = new_pos >= track_length
        self.track_position = new_pos % track_length

        crossing_ratio = 1.0
        if crossed_line:
            distance_to_line = max(0.0, track_length - old_pos)
            crossing_ratio = min(max(distance_to_line / max(distance_m, 1e-9), 0.0), 1.0)
            self.lap_count += 1

        return crossed_line, crossing_ratio

    # ==========================================================
    # SPEED / PACE MODEL
    # ==========================================================
    def compute_speed(
        self,
        segment: dict,
        track_length: float,
        base_lap_time: float,
        lap_time_std: float,
        evolution_level: float,
        track_deg_multiplier: float,
        drs_available: bool,
        total_laps: int,
        track_state: str = "GREEN",
    ) -> float:
        if self.retired:
            return 0.0

        std_scale = max(lap_time_std, 1e-6)

        if self.lap_count != self.last_lap_for_noise:
            self.lap_execution_noise = self.rng.gauss(0.0, 0.16 * std_scale)
            self.last_lap_for_noise = self.lap_count

        tyre_delta = self.tyre_model.lap_delta(
            tyre_state=self.tyre_state,
            track_deg_multiplier=track_deg_multiplier,
            team_deg_factor=self.calibration.k_team,
        )

        race_fraction = min(1.0, max(0.0, self.lap_count / max(1, total_laps)))

        # Reduced slightly so fuel burn does not hide tyre degradation too much.
        fuel_penalty = 1.70 * (1.0 - race_fraction)

        effective_lap_time = (
            base_lap_time
            + self.calibration.mu_team
            + tyre_delta
            + fuel_penalty
        )

        effective_lap_time *= (1.0 - (0.0055 * evolution_level))

        if track_state == "VSC":
            effective_lap_time *= 1.28
        elif track_state == "SC":
            effective_lap_time *= 1.55

        base_speed = track_length / max(effective_lap_time, 1e-6)

        seg_len = float(segment.get("length", track_length))
        seg_len = max(seg_len, 1e-6)
        seg_frac = seg_len / max(track_length, 1e-6)
        seg_time = seg_len / max(base_speed, 1e-6)

        seg_time += self.lap_execution_noise * seg_frac
        seg_time += self.traffic_penalty * seg_frac
        seg_time -= self.slipstream_bonus * seg_frac

        seg_type = segment.get("type", "straight")
        severity = float(segment.get("severity", 0.5))
        severity = min(max(severity, 0.0), 1.0)

        if seg_type == "braking":
            sigma_frac = 0.017
            sigma = seg_time * sigma_frac * (0.65 + 0.70 * severity) * std_scale
        elif seg_type == "corner":
            sigma_frac = 0.013
            sigma = seg_time * sigma_frac * (0.65 + 0.65 * severity) * std_scale
        else:
            sigma_frac = 0.008
            sigma = seg_time * sigma_frac * std_scale

        seg_time += self.rng.gauss(0.0, sigma)

        if self.instruction == "PUSH":
            seg_time *= 0.997
        elif self.instruction == "SAVE":
            seg_time *= 1.004

        if drs_available and seg_type == "straight" and track_state == "GREEN":
            seg_time *= 0.9815

        seg_time += self.rng.gauss(0.0, 0.0012)

        speed = seg_len / max(seg_time, 1e-6)
        speed += self.defend_position()

        return max(0.0, speed)
    # ==========================================================
    # TYRES
    # ==========================================================
    def update_tyre_wear(self, track_deg_multiplier: float) -> None:
        base_wear = min(max(float(track_deg_multiplier), 0.92), 1.22)

        # Traffic should hurt tyres more than before.
        traffic_wear = 1.0 + (0.16 * self.following_intensity)

        wear_step = base_wear * traffic_wear

        if self.instruction == "PUSH":
            wear_step *= 1.07
        elif self.instruction == "SAVE":
            wear_step *= 0.96

        self.tyre_model.advance(self.tyre_state, laps=wear_step)

    def set_tyre_inventory(self, inventory: dict[str, int]) -> None:
        self.tyre_set_inventory = {k: int(v) for k, v in inventory.items()}

        start_role = self.tyre_state.weekend_role
        if start_role in self.tyre_set_inventory:
            self.tyre_set_inventory[start_role] = max(0, self.tyre_set_inventory[start_role] - 1)

    def set_stint_plan(self, min_review_age: float, target_age: float, max_age: float) -> None:
        self.stint_min_review_age = float(min_review_age)
        self.stint_target_age = float(target_age)
        self.stint_max_age = float(max_age)
        self.strategy_plan_stint_id = self.current_stint_id

    def get_remaining_sets(self, role: str) -> int:
        return int(self.tyre_set_inventory.get(role, 0))
    
    # ==========================================================
    # PIT & TEAM INTERACTION
    # ==========================================================
    def pit(self, new_compound: str, new_role: Optional[str] = None) -> None:
        if self.retired or self.in_pit_lane or self.pending_pit:
            return

        self.pending_pit = True
        self.pit_compound = new_compound
        self.next_role = new_role

    def apply_team_instruction(self, instruction: str) -> None:
        self.instruction = instruction

    def start_pit_stop(
        self,
        pit_lane_total_m: float,
        pit_box_position_m: float,
        pit_exit_track_pos: float,
        pit_service_time_s: float,
        pit_line_position_m: float | None,
    ) -> None:
        self.in_pit_lane = True

        self.pit_lane_position_m = 0.0
        self.pit_lane_total_m = float(max(0.0, pit_lane_total_m))
        self.pit_box_position_m = float(min(self.pit_lane_total_m, max(0.0, pit_box_position_m)))
        self.pit_exit_track_pos = float(pit_exit_track_pos)
        self.pit_line_position_m = pit_line_position_m
        self.pit_line_crossed = False

        self.pit_service_remaining_s = float(max(0.0, pit_service_time_s))
        self.pit_phase = "to_box"

        self.last_speed_mps = 0.0
        self.last_pit_service_time_s = float(max(0.0, pit_service_time_s))
        self.current_pit_entry_sim_time = None
        self.last_pit_total_time_s = 0.0

    # ==========================================================
    # RACECRAFT
    # ==========================================================
    def adjust_for_traffic(self, lap_time: float) -> float:
        return lap_time

    def attempt_overtake(self, segment: dict, drs_available: bool, overtake_difficulty: float) -> bool:
        if self.retired or self.car_ahead is None:
            return False

        if self.overtake_cooldown > 0:
            return False

        seg_type = segment.get("type", "straight")
        if seg_type not in ("straight", "braking"):
            return False

        max_gap = (1.35 * self.car_length) if (drs_available and seg_type == "straight") else (1.00 * self.car_length)
        if self.gap_ahead > max_gap:
            return False

        attacker_pace = self.calibration.mu_team
        defender_pace = self.car_ahead.calibration.mu_team
        pace_delta = defender_pace - attacker_pace

        tyre_advantage = (self.car_ahead.tyre_state.age_laps - self.tyre_state.age_laps) * 0.015

        base_probability = 0.05
        base_probability += max(0.0, pace_delta * 0.28)
        base_probability += max(0.0, tyre_advantage)

        if drs_available and seg_type == "straight":
            base_probability += 0.08

        base_probability /= max(0.75, min(overtake_difficulty, 1.5))
        base_probability = min(max(base_probability, 0.015), 0.35)

        success = self.rng.random() < base_probability
        if success:
            self.overtake_cooldown = 2.0

        return success

    def defend_position(self) -> float:
        if self.car_behind and self.gap_behind < (1.5 * self.car_length):
            return -0.5
        return 0.0

    def tick_cooldowns(self, dt: float) -> None:
        if self.overtake_cooldown > 0:
            self.overtake_cooldown = max(0.0, self.overtake_cooldown - dt)

    def update_pit_lane_tick(self, dt: float, pit_lane_speed_mps: float) -> bool:
        self.current_lap_time += dt
        crossed_pit_line = False

        def check_pit_line(prev_pos: float, curr_pos: float) -> bool:
            if self.pit_line_position_m is None or self.pit_line_crossed:
                return False
            return prev_pos < self.pit_line_position_m <= curr_pos

        if self.pit_phase == "to_box":
            prev_pos = self.pit_lane_position_m
            move_dist = pit_lane_speed_mps * dt
            self.pit_lane_position_m = min(self.pit_box_position_m, self.pit_lane_position_m + move_dist)
            self.last_speed_mps = pit_lane_speed_mps

            if check_pit_line(prev_pos, self.pit_lane_position_m):
                self.pit_line_crossed = True
                crossed_pit_line = True

            if self.pit_lane_position_m >= self.pit_box_position_m:
                self.pit_phase = "service"
                self.last_speed_mps = 0.0

            return crossed_pit_line

        if self.pit_phase == "service":
            self.pit_service_remaining_s = max(0.0, self.pit_service_remaining_s - dt)
            self.last_speed_mps = 0.0

            if self.pit_service_remaining_s <= 0.0:
                self.pit_phase = "to_exit"

            return False

        if self.pit_phase == "to_exit":
            prev_pos = self.pit_lane_position_m
            move_dist = pit_lane_speed_mps * dt
            self.pit_lane_position_m = min(self.pit_lane_total_m, self.pit_lane_position_m + move_dist)
            self.last_speed_mps = pit_lane_speed_mps

            if check_pit_line(prev_pos, self.pit_lane_position_m):
                self.pit_line_crossed = True
                crossed_pit_line = True

            return crossed_pit_line

        self.last_speed_mps = 0.0
        return False

    def complete_pit_if_done(self) -> bool:
        if self.pit_phase != "to_exit":
            return False

        if self.pit_lane_position_m < self.pit_lane_total_m:
            return False

        self.in_pit_lane = False
        self.track_position = self.pit_exit_track_pos
        self.prev_track_position = self.track_position

        if self.next_compound is not None:
            fitted_role = self.next_role

            self.tyre_state.compound = self.next_compound
            self.tyre_state.age_laps = 0.0
            self.tyre_state.weekend_role = fitted_role

            if self.tyre_state.compound not in {"INTERMEDIATE", "WET"}:
                self.used_dry_compounds.add(self.tyre_state.compound)

            if fitted_role in self.tyre_set_inventory:
                self.tyre_set_inventory[fitted_role] = max(0, self.tyre_set_inventory[fitted_role] - 1)

            self.next_compound = None
            self.next_role = None
            self.pit_stops_made += 1
            self.current_stint_id += 1

        self.pit_lane_position_m = 0.0
        self.pit_lane_total_m = 0.0
        self.pit_box_position_m = 0.0
        self.pit_exit_track_pos = 0.0
        self.pit_line_position_m = None
        self.pit_line_crossed = False
        self.pit_service_remaining_s = 0.0
        self.pit_phase = "none"

        return True

    def update_drs_active(self, drs_enabled: bool, segment_type: str, track_position: float, drs_zones: list[dict], in_window_fn) -> None:
        self.drs_active = False
        if not drs_enabled or segment_type != "straight":
            return

        for zone in drs_zones:
            znum = int(zone["zone_number"])
            stamp = self.drs_eligible_lap.get(znum)

            if stamp is None or stamp not in (self.lap_count, self.lap_count - 1):
                continue

            a0 = float(zone["activation_start"])
            a1 = float(zone["activation_end"])

            if in_window_fn(track_position, a0, a1):
                self.drs_active = True
                return

    def update_drs_eligibility(
        self,
        drs_enabled: bool,
        has_car_ahead: bool,
        gap_ahead_m: float,
        last_speed_mps: float,
        drs_zones: list[dict],
        did_cross_marker_fn,
        prev_pos: float,
        curr_pos: float,
    ) -> None:
        if not drs_enabled or not has_car_ahead:
            return

        speed = max(last_speed_mps, 1e-6)

        for zone in drs_zones:
            znum = int(zone["zone_number"])
            detect = float(zone["detection_point"])

            if did_cross_marker_fn(prev_pos, curr_pos, detect):
                gap_s = gap_ahead_m / speed
                if gap_s <= 1.0:
                    self.drs_eligible_lap[znum] = self.lap_count
                else:
                    self.drs_eligible_lap.pop(znum, None)

    # ==========================================================
    # RELIABILITY
    # ==========================================================
    def check_reliability_failure(self) -> bool:
        if self.calibration.reliability_prob <= 0.0:
            return False
        return self.rng.random() < self.calibration.reliability_prob