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

        # Spatial state
        self.track_position: float = 0.0
        self.lap_count: int = 0
        self.drs_eligible: bool = False
        
        # Driver variance (persists per lap)
        self.lap_execution_noise: float = 0.0
        self.last_lap_for_noise: int = -1

    # ==========================================================
    # SPATIAL HELPERS
    # ==========================================================
    def set_grid_position(self, grid_offset_m: float, track_length: float) -> None:
        self.track_position = grid_offset_m % track_length
        self.lap_count = 0
        self.drs_eligible = False

    def advance_position(self, distance_m: float, track_length: float) -> bool:
        new_pos = self.track_position + distance_m
        crossed_line = new_pos >= track_length
        self.track_position = new_pos % track_length

        if crossed_line:
            self.lap_count += 1

        return crossed_line

    # ==========================================================
    # SPEED / PACE MODEL (NOW AGENT CONTROLLED)
    # ==========================================================
    def compute_speed(self, segment: dict, track_length: float, base_lap_time: float, lap_time_std: float, evolution_level: float) -> float:
        """
        Returns speed in m/s for this tick.
        """
        if self.retired:
            return 0.0

        # Generate lap-level execution noise
        if self.lap_count != self.last_lap_for_noise:
            self.lap_execution_noise = random.gauss(0, 0.20)
            self.last_lap_for_noise = self.lap_count
            
        # Tyre performance
        tyre_delta = self.tyre_model.lap_delta(
            tyre_state = self.tyre_state,
            track_deg_multiplier = 1.0,
            team_deg_factor = self.calibration.k_team,
        )

        effective_lap_time = (base_lap_time + self.calibration.mu_team + tyre_delta + self.lap_execution_noise)

        # Track evolution
        evolution_multiplier = 1.0 - (0.02 * evolution_level)
        effective_lap_time *= evolution_multiplier

        # Segment-specific variance
        seg_type = segment.get("type", "straight")
        severity = segment.get("severity", 0.5)

        if seg_type == "braking":
            # braking zones are messy
            effective_lap_time += random.gauss(0, 0.08 * severity)

        elif seg_type == "corner":
            effective_lap_time += random.gauss(0, 0.05 * severity)

        else:  # straight
            effective_lap_time += random.gauss(0, 0.02)

        # Traffic
        effective_lap_time += self.traffic_penalty
        effective_lap_time -= self.slipstream_bonus

        # Tiny per-tick noise (wind / throttle jitter)
        effective_lap_time += random.gauss(0, 0.01)

        # Convert to speed
        speed = track_length / max(effective_lap_time, 1e-6)
        
        # Defensive modifier
        speed += self.defend_position()

        speed = max(0.0, speed)

        return speed
    
    # ==========================================================
    # TYRES
    # ==========================================================
    def update_tyre_wear(self) -> None:
        extra_deg = 1.0 + 0.15 * self.following_intensity
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
    # RACECRAFT PLACEHOLDERS
    # ==========================================================
    def adjust_for_traffic(self, lap_time: float) -> float:
        return lap_time

    def attempt_overtake(self) -> bool:
        """
        Realistic F1 overtake model with cooldown.
        """
        if self.retired:
            return False

        if self.car_ahead is None:
            return False

        # Cooldown active
        if self.overtake_cooldown > 0:
            return False

        # Must be very close
        if self.gap_ahead > self.car_length:
            return False

        # Pace delta
        attacker_pace = self.calibration.mu_team
        defender_pace = self.car_ahead.calibration.mu_team

        pace_delta = defender_pace - attacker_pace

        if pace_delta < -0.05:
            return False

        # Tyre advantage
        tyre_delta = (
            self.car_ahead.tyre_state.age_laps -
            self.tyre_state.age_laps
        )

        tyre_advantage = tyre_delta * 0.02

        base_probability = 0.12
        base_probability += max(0.0, pace_delta * 0.4)
        base_probability += max(0.0, tyre_advantage)

        base_probability = min(base_probability, 0.45)

        success = random.random() < base_probability

        if success:
            # 2 second cooldown after attempt
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

    # ==========================================================
    # RELIABILITY
    # ==========================================================
    def check_reliability_failure(self) -> bool:
        if self.calibration.reliability_prob <= 0.0:
            return False
        return random.random() < self.calibration.reliability_prob