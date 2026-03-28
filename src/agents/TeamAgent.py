from __future__ import annotations
from typing import List, Optional

from src.agents.CarAgent import CarAgent
from src.sim.RaceState import CarSnapshot
from src.models.TyreModel import TyreState, TyreModel

class TeamAgent:
    def __init__(self, team_id: str, car_a: CarAgent, car_b: CarAgent, mu_team: float, k_team: float, compound_map: dict[str, str]):
        self.team_id = team_id
        self.car_a = car_a
        self.car_b = car_b

        self.mu_team = mu_team
        self.k_team = k_team
        
        self.compound_map = compound_map

        # Runtime race context
        self.current_lap: int = 0
        self.track_state: str = "GREEN"
        self.race_view: List[CarSnapshot] = []

        self.pit_loss: float = 0.0
        self.base_lap_time: float = 0.0
        self.tyre_model: Optional[TyreModel] = None
        self.total_laps: int = 0
        self.track_deg_multiplier: float = 1.0

        # Strategy state
        self.projection_horizon = 8
        self.pit_candidates: List[tuple[CarAgent, str]] = []

        self.snapshot_by_id: dict[str, CarSnapshot] = {}
        self.race_order: list[CarSnapshot] = []
        self.position_map: dict[str, int] = {}
        self.candidate_scores: dict[str, float] = {}
        self.team_cars: list[CarAgent] = [self.car_a, self.car_b]
        self.remaining_laps: int = 0

        # Small deterministic offsets so teams do not all react identically
        self.team_strategy_offset = ((sum(ord(c) for c in self.team_id) % 7) - 3) * 0.04
        self.car_strategy_offset = {
            self.car_a.car_id: ((sum(ord(c) for c in self.car_a.car_id) % 5) - 2) * 0.03,
            self.car_b.car_id: ((sum(ord(c) for c in self.car_b.car_id) % 5) - 2) * 0.03,
        }

    # ==========================================================
    # OBSERVATION
    # ==========================================================
    def observe(self, race_view: List[CarSnapshot], lap: int, track_state: str, pit_loss: float, base_lap_time: float, tyre_model: TyreModel, total_laps: int, track_deg_multiplier: float) -> None:
        self.race_view = race_view
        self.current_lap = lap
        self.track_state = track_state
        self.pit_loss = pit_loss
        self.base_lap_time = base_lap_time
        self.tyre_model = tyre_model
        self.total_laps = total_laps
        self.track_deg_multiplier = track_deg_multiplier

        # Keep RaceManager order, because it is now true race order by progress
        self.race_order = list(self.race_view)
        self.snapshot_by_id = {snap.car_id: snap for snap in self.race_order}

    # ==========================================================
    # HELPERS
    # ==========================================================
    def get_snapshot(self, car: CarAgent) -> Optional[CarSnapshot]:
        return self.snapshot_by_id.get(car.car_id)

    def get_neighbours(self, car: CarAgent) -> tuple[Optional[CarSnapshot], Optional[CarSnapshot]]:
        idx = self.position_map.get(car.car_id)
        if idx is None:
            return None, None

        ahead = self.race_order[idx - 1] if idx > 0 else None
        behind = self.race_order[idx + 1] if idx < len(self.race_order) - 1 else None
        return ahead, behind

    def estimate_current_lap_time(self, car: CarAgent) -> float:
        tyre_delta = self.tyre_model.lap_delta(
            tyre_state=car.tyre_state,
            track_deg_multiplier=self.track_deg_multiplier,
            team_deg_factor=car.calibration.k_team,
        )

        lap_time = self.base_lap_time + car.calibration.mu_team + tyre_delta
        lap_time += car.traffic_penalty
        lap_time -= car.slipstream_bonus * 0.5
        return lap_time

    def estimate_rejoin_gap(self, car: CarAgent) -> tuple[Optional[CarSnapshot], Optional[CarSnapshot], float]:
        car_snap = self.get_snapshot(car)
        if car_snap is None:
            return None, None, 0.0

        projected_time = car_snap.total_time + self.pit_loss

        ahead = None
        behind = None

        for snap in self.race_order:
            if snap.car_id == car.car_id:
                continue

            if snap.total_time <= projected_time:
                ahead = snap
            else:
                behind = snap
                break

        gap_ahead = float("inf") if ahead is None else projected_time - ahead.total_time
        gap_behind = float("inf") if behind is None else behind.total_time - projected_time
        clear_air_score = min(gap_ahead, gap_behind)

        return ahead, behind, clear_air_score

    def estimate_rival_pit_window(self, snap: CarSnapshot) -> float:
        """
        Returns a simple pit-likelihood score for a rival.
        Higher means more likely to pit soon.
        """
        tyre_age = snap.tyre_age
        tyre_compound = snap.tyre_compound

        # Base age pressure
        pressure = max(0.0, tyre_age - 10) * 0.08

        # Softer compounds should enter the window earlier
        compound_pressure = 0.0
        if tyre_compound == self.compound_map.get("SOFT"):
            compound_pressure += 0.30
        elif tyre_compound == self.compound_map.get("MEDIUM"):
            compound_pressure += 0.12

        # Mid-race is where most normal dry stops happen
        race_fraction = self.current_lap / max(1, self.total_laps)
        phase_pressure = 0.0
        if 0.20 <= race_fraction <= 0.85:
            phase_pressure += 0.15

        return pressure + compound_pressure + phase_pressure

    def get_nearby_rival_pit_pressure(self, car: CarAgent) -> tuple[float, float]:
        """
        Returns:
        - undercut pressure from rival ahead
        - cover pressure from rival behind
        Only looks at nearby rivals, which keeps it simple and realistic.
        """
        snap = self.get_snapshot(car)
        if snap is None:
            return 0.0, 0.0

        ahead_snap, behind_snap = self.get_neighbours(car)

        undercut_pressure = 0.0
        cover_pressure = 0.0

        if ahead_snap is not None and ahead_snap.team_id != car.team_id:
            gap_to_ahead = max(0.0, snap.total_time - ahead_snap.total_time)
            if gap_to_ahead < 4.0:
                likely_pit = self.estimate_rival_pit_window(ahead_snap)
                undercut_pressure += min(0.60, likely_pit * 0.35)

        if behind_snap is not None and behind_snap.team_id != car.team_id:
            gap_to_behind = max(0.0, behind_snap.total_time - snap.total_time)
            if gap_to_behind < 4.0:
                likely_pit = self.estimate_rival_pit_window(behind_snap)
                cover_pressure += min(0.55, likely_pit * 0.30)

        return undercut_pressure, cover_pressure

    def get_pit_call_threshold(self, car: CarAgent) -> float:
        threshold = 0.55
        threshold += self.team_strategy_offset
        threshold += self.car_strategy_offset.get(car.car_id, 0.0)

        # Older tyres lower the threshold
        threshold -= min(0.25, max(0.0, car.tyre_state.age_laps - 14) * 0.03)

        # Close racing encourages earlier calls
        if car.car_ahead is not None and car.gap_ahead < 2.5:
            threshold -= 0.08
        if car.car_behind is not None and car.gap_behind < 2.5:
            threshold -= 0.06

        # Slightly more conservative late on
        if self.remaining_laps <= 10:
            threshold += 0.08
        if self.remaining_laps <= 5:
            threshold += 0.12

        return max(0.20, threshold)

    # ==========================================================
    # DECISION PIPELINE
    # ==========================================================
    def decide(self) -> None:
        self.update_race_context()
        self.evaluate_stint_outcomes()
        self.assess_undercut_overcut()
        self.resolve_team_conflicts()
        self.issue_commands()

    # ==========================================================
    # STRATEGY LOGIC
    # ==========================================================
    def update_race_context(self) -> None:
        self.pit_candidates = []
        self.candidate_scores = {}
        self.remaining_laps = max(0, self.total_laps - self.current_lap)

        self.position_map = {}
        for idx, snap in enumerate(self.race_order):
            self.position_map[snap.car_id] = idx

        self.team_cars = [self.car_a, self.car_b]

    def project_stint_time(self, car: CarAgent, compound_code: str, laps: Optional[int] = None) -> float:
        """
        Project next N laps if car runs this compound code.
        """
        if laps is None:
            laps = min(self.projection_horizon, max(1, self.remaining_laps))

        total = 0.0

        if compound_code != car.tyre_state.compound:
            age = 0
            traffic_carry = 0.0
        else:
            age = car.tyre_state.age_laps
            traffic_carry = car.traffic_penalty * 0.5

        for lap_idx in range(laps):
            temp_state = TyreState(compound=compound_code, age_laps=age)

            tyre_delta = self.tyre_model.lap_delta(
                tyre_state=temp_state,
                track_deg_multiplier=self.track_deg_multiplier,
                team_deg_factor=car.calibration.k_team,
            )

            lap_time = self.base_lap_time + car.calibration.mu_team + tyre_delta

            # carry a little current traffic into the first part of the projection
            if lap_idx < 2:
                lap_time += traffic_carry

            total += lap_time
            age += 1

        return total

    def score_pit_option(self, car: CarAgent, alt_code: str) -> float:
        current_code = car.tyre_state.compound
        horizon = min(self.projection_horizon, max(1, self.remaining_laps))

        stay_out_time = self.project_stint_time(car, current_code, laps=horizon)
        pit_time = self.project_stint_time(car, alt_code, laps=horizon) + self.pit_loss
        raw_gain = stay_out_time - pit_time

        _, _, rejoin_clear_air = self.estimate_rejoin_gap(car)

        traffic_risk = 0.0
        if rejoin_clear_air < 1.0:
            traffic_risk = 2.4
        elif rejoin_clear_air < 2.5:
            traffic_risk = 1.2
        elif rejoin_clear_air < 4.0:
            traffic_risk = 0.5

        rival_pressure = 0.0
        if car.car_ahead is not None and car.gap_ahead < 2.5:
            rival_pressure += 0.45
        if car.car_behind is not None and car.gap_behind < 2.5:
            rival_pressure += 0.35

        tyre_pressure = max(0.0, car.tyre_state.age_laps - 12) * 0.09

        compound_switch_bonus = 0.08 if alt_code != current_code else 0.0

        # NEW: nearby rival pit awareness
        undercut_pressure, cover_pressure = self.get_nearby_rival_pit_pressure(car)

        score = (
            raw_gain
            - traffic_risk
            + rival_pressure
            + tyre_pressure
            + compound_switch_bonus
            + undercut_pressure
            + cover_pressure
        )
        return score

    def evaluate_stint_outcomes(self) -> None:
        if self.remaining_laps <= 2:
            return

        self.pit_candidates = []
        self.candidate_scores = {}

        option_codes = list(self.compound_map.values())
        self._code_to_label = {v: k for k, v in self.compound_map.items()}

        for car in self.team_cars:
            if car.retired or car.pending_pit or car.in_pit_lane:
                continue

            best_option_code = None
            best_score = float("-inf")

            for alt_code in option_codes:
                if alt_code == car.tyre_state.compound:
                    continue

                score = self.score_pit_option(car, alt_code)

                if score > best_score:
                    best_score = score
                    best_option_code = alt_code

            threshold = self.get_pit_call_threshold(car)

            if best_option_code is not None and best_score > threshold:
                self.pit_candidates.append((car, best_option_code))
                self.candidate_scores[car.car_id] = best_score

    def assess_undercut_overcut(self) -> None:
        updated_candidates = []

        for car, compound in self.pit_candidates:
            snap = self.get_snapshot(car)
            if snap is None:
                continue

            ahead_snap, behind_snap = self.get_neighbours(car)
            score = self.candidate_scores.get(car.car_id, 0.0)

            if ahead_snap is not None:
                gap_to_ahead = max(0.0, snap.total_time - ahead_snap.total_time)
                if gap_to_ahead < 2.5:
                    score += 0.5

            if behind_snap is not None:
                gap_to_behind = max(0.0, behind_snap.total_time - snap.total_time)
                if gap_to_behind < 2.5:
                    score += 0.3

            if score > self.get_pit_call_threshold(car):
                updated_candidates.append((car, compound))
                self.candidate_scores[car.car_id] = score

        self.pit_candidates = updated_candidates

    def resolve_team_conflicts(self) -> None:
        if len(self.pit_candidates) <= 1:
            return

        # Allow double-stack if both cars genuinely meet the threshold
        self.pit_candidates.sort(
            key=lambda item: self.candidate_scores.get(item[0].car_id, 0.0),
            reverse=True
        )

        filtered_candidates: list[tuple[CarAgent, str]] = []

        for car, compound in self.pit_candidates:
            score = self.candidate_scores.get(car.car_id, 0.0)
            threshold = self.get_pit_call_threshold(car)

            if score > threshold:
                filtered_candidates.append((car, compound))

        self.pit_candidates = filtered_candidates[:2]

    # ==========================================================
    # COMMANDS
    # ==========================================================
    def issue_commands(self) -> None:
        self.issue_pace_commands()
        self.issue_pit_decision()

    def issue_pace_commands(self) -> None:
        self.car_a.apply_team_instruction("NORMAL")
        self.car_b.apply_team_instruction("NORMAL")

    def issue_pit_decision(self) -> None:
        for car, compound_code in self.pit_candidates:
            if car.retired or car.pending_pit or car.in_pit_lane:
                continue
            car.pit(compound_code)