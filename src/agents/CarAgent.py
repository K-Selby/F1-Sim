# src/agents/CarAgent.py

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
    def __init__(self, car_id: str, team_id: str, calibration: CarCalibration, tyre_state: TyreState, tyre_model: TyreModel):
        self.car_id = car_id
        self.team_id = team_id
        self.calibration = calibration
        self.car_length = 5.5  # metres (F1 approx)

        self.tyre_state = tyre_state
        self.tyre_model = tyre_model

        self.instruction: Optional[str] = None

        self.total_time: float = 0.0
        self.current_lap_time: float = 0.0
        self.retired: bool = False

        # Pit / strategy flags
        self.pending_pit: bool = False
        self.pit_compound: Optional[str] = None     # check these 2
        self.next_compound: Optional[str] = None      #Thsi one as well
        self.in_pit_lane: bool = False
        self.pit_time_remaining: float = 0.0

        # Traffic effects (set by RaceManager)
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
        # DRS eligibility is decided at each zone's detection point.
        # We store a lap "stamp" per zone so pit-straight DRS works when detection is before S/F.
        self.drs_eligible_lap: dict[int, int] = {}   # {zone_number: lap_count_at_detection}
        self.drs_active: bool = False

        # Spatial state
        self.track_position: float = 0.0
        self.lap_count: int = 0
        
        # Driver variance (persists per lap)
        self.lap_execution_noise: float = 0.0
        self.last_lap_for_noise: int = -1

    # ==========================================================
    # SPATIAL HELPERS
    # ==========================================================
    def set_grid_position(self, grid_offset_m: float, track_length: float) -> None:
        self.track_position = grid_offset_m % track_length
        self.lap_count = 0

        # DRS state (managed by RaceManager using circuit JSON)
        self.drs_eligible_lap = {}   # reset all zone eligibility stamps
        self.drs_active = False

        # Needed to detect crossing detection points
        self.prev_track_position: float = self.track_position

    def advance_position(self, distance_m: float, track_length: float) -> bool:
        self.prev_track_position = self.track_position

        new_pos = self.track_position + distance_m
        crossed_line = new_pos >= track_length
        self.track_position = new_pos % track_length

        if crossed_line:
            self.lap_count += 1

        return crossed_line

    # ==========================================================
    # SPEED / PACE MODEL (NOW AGENT CONTROLLED)
    # ==========================================================
    def compute_speed(self, segment: dict, track_length: float, base_lap_time: float, lap_time_std: float, evolution_level: float, track_deg_multiplier: float, drs_available: bool) -> float:
        """
        Returns speed in m/s for this tick.

        Model approach:
        - Compute a clean-air lap-time baseline (seconds)
        - Convert to baseline speed (m/s)
        - Convert baseline speed to baseline *segment time*
        - Apply segment-scaled deltas (seg_frac) for lap noise, traffic, DRS, and micro-variance
        - Convert back to segment speed (m/s)
        """
        if self.retired:
            return 0.0

        std_scale = max(lap_time_std, 1e-6) / 1.0  # 1.0 == "baseline" spread

        # Generate lap-level execution noise once per lap (driver variability)
        if self.lap_count != self.last_lap_for_noise:
            self.lap_execution_noise = random.gauss(0, 0.20 * std_scale)
            self.last_lap_for_noise = self.lap_count

        # Tyre performance (seconds of lap-time delta)
        tyre_delta = self.tyre_model.lap_delta(
            tyre_state=self.tyre_state,
            track_deg_multiplier=track_deg_multiplier,
            team_deg_factor=self.calibration.k_team,
        )

        # Clean-air lap time baseline (seconds)
        effective_lap_time = base_lap_time + self.calibration.mu_team + tyre_delta

        # Track evolution reduces lap time over the race
        # (simple linear effect; keep small so it doesn't dominate calibration)
        evolution_multiplier = 1.0 - (0.02 * evolution_level)
        effective_lap_time *= max(0.90, evolution_multiplier)

        # Convert to baseline clean speed (m/s)
        base_speed = track_length / max(effective_lap_time, 1e-6)

        # Segment geometry
        seg_len = float(segment.get("length", track_length))
        seg_len = max(seg_len, 1e-6)
        seg_frac = seg_len / max(track_length, 1e-6)

        # Baseline time to traverse this segment at clean-air pace
        seg_time = seg_len / max(base_speed, 1e-6)

        # Distribute lap-level noise & traffic across the lap using seg_frac
        # (so longer segments "carry" more of the lap variability)
        seg_time += self.lap_execution_noise * seg_frac
        seg_time += self.traffic_penalty * seg_frac
        seg_time -= self.slipstream_bonus * seg_frac

        # Segment-type micro variance (braking/corners messier than straights)
        seg_type = segment.get("type", "straight")
        severity = float(segment.get("severity", 0.5))
        severity = min(max(severity, 0.0), 1.0)

        if seg_type == "braking":
            sigma_frac = 0.030  # ~3% time noise in braking zones
            sigma = seg_time * sigma_frac * (0.5 + 0.7 * severity) * std_scale
        elif seg_type == "corner":
            sigma_frac = 0.020
            sigma = seg_time * sigma_frac * (0.5 + 0.7 * severity) * std_scale
        else:  # straight
            sigma_frac = 0.010
            sigma = seg_time * sigma_frac * std_scale

        seg_time += random.gauss(0, sigma)

        # Team pace instruction (very small, but allows "push" vs "save" later)
        if self.instruction == "PUSH":
            seg_time *= 0.995
        elif self.instruction == "SAVE":
            seg_time *= 1.005

        # DRS: only meaningful on straights, reduces segment time a bit
        if drs_available and seg_type == "straight":
            seg_time *= 0.94  # ~6% straight-line gain (kept conservative)

        # Tiny per-tick jitter (wind / throttle / kerb usage)
        seg_time += random.gauss(0, 0.002)

        # Convert segment time back to speed
        speed = seg_len / max(seg_time, 1e-6)

        # Defensive modifier (simple m/s penalty when defending)
        speed += self.defend_position()

        return max(0.0, speed)
    
    # ==========================================================
    # TYRES
    # ==========================================================
    def update_tyre_wear(self, track_deg_multiplier: float) -> None:
        # Following increases wear in dirty air / turbulence (simple proxy)
        extra_deg = 1.0 + 0.15 * self.following_intensity

        # Circuit degradation multiplier from characteristics (abrasion/tyre stress)
        extra_deg *= max(0.7, track_deg_multiplier)

        self.tyre_model.advance(self.tyre_state, laps=extra_deg)

    # ==========================================================
    # PIT & TEAM INTERACTION
    # ==========================================================
    def pit(self, new_compound: str) -> None:
        self.pending_pit = True
        self.pit_compound = new_compound

    def apply_team_instruction(self, instruction: str) -> None:
        self.instruction = instruction

    # ==========================================================
    # RACECRAFT 
    # ==========================================================
    def adjust_for_traffic(self, lap_time: float) -> float:
        return lap_time

    def attempt_overtake(self, segment: dict, drs_available: bool, overtake_difficulty: float) -> bool:
        """
        Overtake attempts are evaluated at realistic interaction points (straights/braking),
        with higher success probability if DRS is available on straights.
        """
        if self.retired or self.car_ahead is None:
            return False

        if self.overtake_cooldown > 0:
            return False

        seg_type = segment.get("type", "straight")

        # Realistic: overtakes primarily happen on straights or into braking zones
        if seg_type not in ("straight", "braking"):
            return False

        # Must be close enough to actually attempt (wheel-to-wheel initiation)
        # Allow a *slightly* larger initiation window on straights when DRS is active.
        max_gap = (1.5 * self.car_length) if (drs_available and seg_type == "straight") else (1.1 * self.car_length)
        if self.gap_ahead > max_gap:
            return False

        attacker_pace = self.calibration.mu_team
        defender_pace = self.car_ahead.calibration.mu_team
        pace_delta = defender_pace - attacker_pace  # positive means attacker is faster (lower mu)

        # Tyre advantage (freshness proxy)
        tyre_advantage = (self.car_ahead.tyre_state.age_laps - self.tyre_state.age_laps) * 0.02

        # Base probability tuned conservative
        base_probability = 0.08
        base_probability += max(0.0, pace_delta * 0.35)
        base_probability += max(0.0, tyre_advantage)

        # DRS boost applies only on straights
        if drs_available and seg_type == "straight":
            base_probability += 0.12

        # Circuit difficulty factor (1.0 baseline; >1 harder)
        base_probability /= max(0.7, min(overtake_difficulty, 1.5))
        base_probability = min(max(base_probability, 0.02), 0.50)

        success = random.random() < base_probability
        if success:
            self.overtake_cooldown = 2.0

        return success
    
    def defend_position(self) -> float:
        """
        Returns defensive speed modifier.
        """
        if self.car_behind and self.gap_behind < (1.5 * self.car_length):
            # Defending reduces own pace slightly
            return -0.5  # m/s penalty
        return 0.0

    def tick_cooldowns(self, dt: float) -> None:
        """
        Tick down cooldown timers for this car.
        """
        if self.overtake_cooldown > 0:
            self.overtake_cooldown = max(0.0, self.overtake_cooldown - dt)


    def update_pit_lane_tick(self, dt: float, pit_lane_speed_mps: float, track_length: float) -> bool:
        """
        Advance pit timer and move along the track at pit-lane speed.
        Returns True if the car crossed the start/finish line during this pit tick.
        """
        self.pit_time_remaining -= dt
        self.current_lap_time += dt

        pit_distance = pit_lane_speed_mps * dt
        crossed_line = self.advance_position(pit_distance, track_length)
        self.last_speed_mps = pit_lane_speed_mps

        return crossed_line


    def complete_pit_if_done(self) -> None:
        """
        If pit time has elapsed, exit pit lane and apply deferred tyre change.
        """
        if self.pit_time_remaining <= 0:
            self.in_pit_lane = False
            self.pit_time_remaining = 0.0

            if getattr(self, "next_compound", None) is not None:
                self.tyre_state.compound = self.next_compound
                self.tyre_state.age_laps = 0
                self.next_compound = None


    def update_drs_active(self, drs_enabled: bool, segment_type: str, track_position: float, drs_zones: list[dict], in_window_fn) -> None:
        """
        Update self.drs_active based on: global DRS enabled, current segment type,
        activation window, and stored eligibility stamp for each zone.
        """
        self.drs_active = False
        if not drs_enabled or segment_type != "straight":
            return

        for zone in drs_zones:
            znum = int(zone["zone_number"])
            stamp = self.drs_eligible_lap.get(znum)

            # Eligible if earned this lap OR previous lap (covers S/F edge cases)
            if stamp is None or stamp not in (self.lap_count, self.lap_count - 1):
                continue

            a0 = float(zone["activation_start"])
            a1 = float(zone["activation_end"])

            if in_window_fn(track_position, a0, a1):
                self.drs_active = True
                return


    def update_drs_eligibility(self, drs_enabled: bool, has_car_ahead: bool, gap_ahead_m: float, last_speed_mps: float, drs_zones: list[dict], did_cross_marker_fn, prev_pos: float, curr_pos: float) -> None:
        """
        Update eligibility stamps when crossing detection points.
        Uses a simple 1.0s rule approximation: gap_s = gap_m / speed_mps.
        """
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
        return random.random() < self.calibration.reliability_prob