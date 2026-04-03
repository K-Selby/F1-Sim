from __future__ import annotations
from typing import List, Optional

from src.agents.CarAgent import CarAgent
from src.sim.RaceState import CarSnapshot
from src.models.TyreModel import TyreState, TyreModel


class TeamAgent:
    """
    Team strategy model built around how F1 teams usually think in dry races:

    - minimise total race time, not just next-stint time
    - use a circuit baseline pit loss, then adjust it for rejoin traffic and team stacking risk
    - avoid unrealistic very-early stops unless the tyre has genuinely fallen away
    - allow repeated compounds across stops
      (e.g. MEDIUM -> HARD -> HARD or MEDIUM -> MEDIUM -> HARD)
    - still force the dry-race legality target:
      at least one pit stop and at least two different dry compounds used by the finish
      unless wet/intermediate tyres are used
    - prefer realistic undercut / cover / clear-air behaviour
    """

    def __init__(
        self,
        team_id: str,
        car_a: CarAgent,
        car_b: CarAgent,
        mu_team: float,
        k_team: float,
        compound_map: dict[str, str],
    ):
        self.team_id = team_id
        self.car_a = car_a
        self.car_b = car_b

        self.mu_team = mu_team
        self.k_team = k_team
        self.compound_map = compound_map

        self.current_lap: int = 0
        self.track_state: str = "GREEN"
        self.race_view: List[CarSnapshot] = []

        self.pit_loss: float = 0.0
        self.base_lap_time: float = 0.0
        self.tyre_model: Optional[TyreModel] = None
        self.total_laps: int = 0
        self.track_deg_multiplier: float = 1.0

        self.projection_horizon = 12
        self.pit_candidates: List[tuple[CarAgent, str]] = []

        self.snapshot_by_id: dict[str, CarSnapshot] = {}
        self.race_order: list[CarSnapshot] = []
        self.position_map: dict[str, int] = {}
        self.candidate_scores: dict[str, float] = {}
        self.team_cars: list[CarAgent] = [self.car_a, self.car_b]
        self.remaining_laps: int = 0

        # Small deterministic variation so all teams do not behave identically.
        self.team_strategy_offset = ((sum(ord(c) for c in self.team_id) % 7) - 3) * 0.04
        self.car_strategy_offset = {
            self.car_a.car_id: ((sum(ord(c) for c in self.car_a.car_id) % 5) - 2) * 0.03,
            self.car_b.car_id: ((sum(ord(c) for c in self.car_b.car_id) % 5) - 2) * 0.03,
        }

        self._code_to_label: dict[str, str] = {}

    # ==========================================================
    # OBSERVATION
    # ==========================================================
    def observe(
        self,
        race_view: List[CarSnapshot],
        lap: int,
        track_state: str,
        pit_loss: float,
        base_lap_time: float,
        tyre_model: TyreModel,
        total_laps: int,
        track_deg_multiplier: float,
    ) -> None:
        self.race_view = race_view
        self.current_lap = lap
        self.track_state = track_state
        self.pit_loss = pit_loss
        self.base_lap_time = base_lap_time
        self.tyre_model = tyre_model
        self.total_laps = total_laps
        self.track_deg_multiplier = track_deg_multiplier

        self.race_order = list(self.race_view)
        self.snapshot_by_id = {snap.car_id: snap for snap in self.race_order}

    # ==========================================================
    # BASIC HELPERS
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

    def get_role_from_code(self, compound_code: str) -> Optional[str]:
        return self._code_to_label.get(compound_code)

    def is_dry_compound(self, compound_code: str) -> bool:
        return compound_code not in {"INTERMEDIATE", "WET"}

    def role_min_stint_age(self, role: Optional[str]) -> float:
        deg_scale = max(0.80, min(1.06, 1.0 - ((self.track_deg_multiplier - 1.0) * 0.90)))

        if role == "SOFT":
            return 6.5 * deg_scale
        if role == "MEDIUM":
            return 10.5 * deg_scale
        if role == "HARD":
            return 17.0 * deg_scale
        return 9.5 * deg_scale

    def role_target_stint(self, role: Optional[str]) -> float:
        deg_scale = max(0.80, min(1.06, 1.0 - ((self.track_deg_multiplier - 1.0) * 0.90)))

        if role == "SOFT":
            return 10.0 * deg_scale
        if role == "MEDIUM":
            return 15.5 * deg_scale
        if role == "HARD":
            return 24.0 * deg_scale
        return 13.5 * deg_scale

    def role_max_stint_age(self, role: Optional[str]) -> float:
        deg_scale = max(0.80, min(1.06, 1.0 - ((self.track_deg_multiplier - 1.0) * 0.90)))

        if role == "SOFT":
            return 14.0 * deg_scale
        if role == "MEDIUM":
            return 21.0 * deg_scale
        if role == "HARD":
            return 31.0 * deg_scale
        return 18.0 * deg_scale

    def ensure_stint_plan(self, car: CarAgent) -> None:
        if car.strategy_plan_stint_id == car.current_stint_id:
            return

        role = car.tyre_state.weekend_role
        compound = car.tyre_state.compound

        # Start from the normal tyre-derived window.
        min_age, target_age, max_age = self.get_stint_window_from_actual_tyre(
            compound_code=compound,
            role=role,
        )

        # Only shift the FIRST stint earlier.
        # This keeps your improved opening-stop behaviour without shortening
        # every later stint and causing fake late-race "must pit" situations.
        if car.current_stint_id == 1:
            min_age = max(3.0, min_age - 3.0)
            target_age = max(min_age + 0.8, target_age - 3.0)
            max_age = max(target_age + 0.8, max_age - 3.0)

        car.set_stint_plan(
            min_review_age=min_age,
            target_age=target_age,
            max_age=max_age,
        )

        # Debug: print estimated first-stint review window when it is created.
        if car.current_stint_id == 1:
            early_review_age = max(3.0, min_age - 2.0)
            print(
                f"[DEBUG FIRST STINT WINDOW] "
                f"{self.team_id} | {car.car_id} | tyre={compound} | role={role} | "
                f"early_review={early_review_age:.2f} | "
                f"min_review={min_age:.2f} | "
                f"target={target_age:.2f} | "
                f"max={max_age:.2f}"
            )

    def get_available_pit_roles(self, car: CarAgent) -> list[str]:
        options: list[str] = []

        for role in ("SOFT", "MEDIUM", "HARD"):
            if car.get_remaining_sets(role) <= 0:
                continue

            # Enforce dry-race compound legality as a hard constraint.
            if not self.can_finish_legally_on_role(car, role):
                continue

            options.append(role)

        return options

    def should_start_live_pit_review(self, car: CarAgent) -> bool:
        self.ensure_stint_plan(car)

        age = car.tyre_state.age_laps

        if self.track_state in {"SC", "VSC"}:
            if car.current_stint_id == 1:
                print(
                    f"[DEBUG FIRST STINT REVIEW] "
                    f"{self.team_id} | {car.car_id} | age={age:.2f} | "
                    f"reason=neutralisation"
                )
            return True

        early_review_age = max(3.0, car.stint_min_review_age - 2.0)
        if age >= early_review_age:
            if car.current_stint_id == 1:
                print(
                    f"[DEBUG FIRST STINT REVIEW] "
                    f"{self.team_id} | {car.car_id} | age={age:.2f} | "
                    f"early_review={early_review_age:.2f} | "
                    f"target={car.stint_target_age:.2f} | "
                    f"max={car.stint_max_age:.2f} | "
                    f"reason=window_open"
                )
            return True

        # Ignore early warmup penalty. Cold-tyre warmup is not the same thing as
        # stint degradation and should not trigger pit review at lap 0 / lap 1.
        spec = self.tyre_model._resolve_spec(car.tyre_state)
        if age < max(2.0, spec.warmup_laps + 0.75):
            return False

        tyre_delta = self.tyre_model.lap_delta(
            tyre_state=car.tyre_state,
            track_deg_multiplier=self.track_deg_multiplier,
            team_deg_factor=car.calibration.k_team,
        )

        if tyre_delta >= 0.95 and age >= car.stint_min_review_age:
            if car.current_stint_id == 1:
                print(
                    f"[DEBUG FIRST STINT REVIEW] "
                    f"{self.team_id} | {car.car_id} | age={age:.2f} | "
                    f"tyre_delta={tyre_delta:.3f} | "
                    f"reason=performance_drop"
                )
            return True

        return False

    def estimate_finish_time_after_delay(
        self,
        car: CarAgent,
        next_compound_code: str,
        pit_cost: float,
        delay_laps: int = 1,
    ) -> float:
        remaining = max(1, self.remaining_laps)
        live_now = self.get_snapshot(car)
        current_total = live_now.total_time if live_now is not None else car.total_time

        total = current_total
        age = car.tyre_state.age_laps
        compound = car.tyre_state.compound
        role = car.tyre_state.weekend_role

        laps_before_stop = min(delay_laps, remaining)

        for lap_idx in range(laps_before_stop):
            temp_state = TyreState(compound=compound, age_laps=age, weekend_role=role)

            tyre_delta = self.tyre_model.lap_delta(
                tyre_state=temp_state,
                track_deg_multiplier=self.track_deg_multiplier,
                team_deg_factor=car.calibration.k_team,
            )

            lap_time = self.base_lap_time + car.calibration.mu_team + tyre_delta
            if lap_idx < 2:
                lap_time += car.traffic_penalty * 0.35

            total += lap_time
            age += 1.0

        total += pit_cost

        new_role = self.get_role_from_code(next_compound_code)
        compound = next_compound_code
        role = new_role
        age = 0.0

        laps_after_stop = max(0, remaining - laps_before_stop)

        for lap_idx in range(laps_after_stop):
            temp_state = TyreState(compound=compound, age_laps=age, weekend_role=role)

            tyre_delta = self.tyre_model.lap_delta(
                tyre_state=temp_state,
                track_deg_multiplier=self.track_deg_multiplier,
                team_deg_factor=car.calibration.k_team,
            )

            lap_time = self.base_lap_time + car.calibration.mu_team + tyre_delta
            total += lap_time
            age += 1.0

        return total

    def estimate_current_lap_time(self, car: CarAgent) -> float:
        tyre_delta = self.tyre_model.lap_delta(
            tyre_state=car.tyre_state,
            track_deg_multiplier=self.track_deg_multiplier,
            team_deg_factor=car.calibration.k_team,
        )

        lap_time = self.base_lap_time + car.calibration.mu_team + tyre_delta
        lap_time += car.traffic_penalty
        lap_time -= car.slipstream_bonus * 0.45
        return lap_time

    def estimate_contextual_pit_loss(self, car: CarAgent) -> float:
        """
        Baseline pit loss plus rejoin / traffic / stacking effects.
        This is much closer to how teams think than using one flat number.
        """
        pit_cost = self.pit_loss

        ahead_snap, behind_snap = self.get_neighbours(car)

        # Rejoin risk: stopping into traffic costs more than the raw lane time.
        if behind_snap is not None:
            gap_behind = behind_snap.total_time - self.get_snapshot(car).total_time
            if gap_behind < 1.5:
                pit_cost += 2.2
            elif gap_behind < 3.0:
                pit_cost += 1.2
            elif gap_behind < 5.0:
                pit_cost += 0.5

        # If running in traffic already, undercut value is a bit higher.
        if car.car_ahead is not None and car.gap_ahead < 2.5:
            pit_cost -= 0.35

        # Double-stack / team congestion risk.
        teammate = self.car_b if car is self.car_a else self.car_a
        if teammate.in_pit_lane:
            pit_cost += 2.8
        elif teammate.pending_pit:
            pit_cost += 1.3

        return max(0.0, pit_cost)

    def estimate_rejoin_gap(
        self,
        car: CarAgent,
        pit_cost: Optional[float] = None,
    ) -> tuple[Optional[CarSnapshot], Optional[CarSnapshot], float]:
        car_snap = self.get_snapshot(car)
        if car_snap is None:
            return None, None, 0.0

        if pit_cost is None:
            pit_cost = self.estimate_contextual_pit_loss(car)

        projected_time = car_snap.total_time + pit_cost

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
        How likely a nearby rival is to pit soon.
        """
        tyre_age = snap.tyre_age
        tyre_compound = snap.tyre_compound

        pressure = max(0.0, tyre_age - 10.0) * 0.08

        compound_pressure = 0.0
        if tyre_compound == self.compound_map.get("SOFT"):
            compound_pressure += 0.30
        elif tyre_compound == self.compound_map.get("MEDIUM"):
            compound_pressure += 0.14

        race_fraction = self.current_lap / max(1, self.total_laps)
        phase_pressure = 0.0
        if 0.18 <= race_fraction <= 0.92:
            phase_pressure += 0.14

        return pressure + compound_pressure + phase_pressure

    def get_nearby_rival_pit_pressure(self, car: CarAgent) -> tuple[float, float]:
        snap = self.get_snapshot(car)
        if snap is None:
            return 0.0, 0.0

        ahead_snap, behind_snap = self.get_neighbours(car)

        undercut_pressure = 0.0
        cover_pressure = 0.0

        if ahead_snap is not None and ahead_snap.team_id != car.team_id:
            gap_to_ahead = max(0.0, snap.total_time - ahead_snap.total_time)
            if gap_to_ahead < 3.0:
                likely_pit = self.estimate_rival_pit_window(ahead_snap)
                undercut_pressure += min(1.40, likely_pit * 0.85)

        if behind_snap is not None and behind_snap.team_id != car.team_id:
            gap_to_behind = max(0.0, behind_snap.total_time - snap.total_time)
            if gap_to_behind < 3.0:
                likely_pit = self.estimate_rival_pit_window(behind_snap)
                cover_pressure += min(1.20, likely_pit * 0.75)

        return undercut_pressure, cover_pressure

    def get_pit_call_threshold(self, car: CarAgent) -> float:
        threshold = 0.95

        threshold += self.team_strategy_offset
        threshold += self.car_strategy_offset.get(car.car_id, 0.0)

        age = car.tyre_state.age_laps
        target = car.stint_target_age
        max_age = car.stint_max_age

        if max_age > target:
            window_progress = min(1.0, max(0.0, (age - target) / (max_age - target)))
        else:
            window_progress = 0.0

        # Start softening earlier so calls begin building before the target.
        if age >= target - 2.0:
            threshold -= 0.22
        if age >= target - 1.0:
            threshold -= 0.30
        if age >= target:
            threshold -= 0.55

        # Once inside the target->max band, reduce the threshold faster.
        threshold -= 1.45 * window_progress

        # Past max, make the stop very easy to trigger.
        if age >= max_age:
            threshold -= 1.00
        if age >= max_age + 0.5:
            threshold -= 1.35

        # Cars in traffic or under pressure should stop a bit sooner.
        if car.car_ahead is not None and car.gap_ahead < 2.5:
            threshold -= 0.14
        if car.car_behind is not None and car.gap_behind < 2.5:
            threshold -= 0.12

        # Keep late-race conservatism, but slightly reduced so it does not overpower normal calls.
        if self.remaining_laps <= 18:
            threshold += 0.30
        if self.remaining_laps <= 12:
            threshold += 0.50
        if self.remaining_laps <= 8:
            threshold += 0.75

        return threshold

    def assess_undercut_overcut(self) -> None:
        updated_candidates = []

        for car, role in self.pit_candidates:
            snap = self.get_snapshot(car)
            if snap is None:
                continue

            score = self.candidate_scores.get(car.car_id, 0.0)
            ahead_snap, behind_snap = self.get_neighbours(car)

            if ahead_snap is not None:
                gap_to_ahead = max(0.0, snap.total_time - ahead_snap.total_time)
                if gap_to_ahead < 2.5:
                    score += 0.65

            if behind_snap is not None:
                gap_to_behind = max(0.0, behind_snap.total_time - snap.total_time)
                if gap_to_behind < 2.5:
                    score += 0.45

            if car.tyre_state.age_laps >= car.stint_target_age:
                score += 0.15

            if car.tyre_state.age_laps >= car.stint_max_age:
                score += 0.55

            if score > self.get_pit_call_threshold(car):
                updated_candidates.append((car, role))
                self.candidate_scores[car.car_id] = score

        self.pit_candidates = updated_candidates

    def get_stint_window_from_actual_tyre(
        self,
        compound_code: str,
        role: Optional[str],
    ) -> tuple[float, float, float]:
        """
        Build the NORMAL tyre-derived stint window from the actual tyre compound spec.

        Important:
        This method now returns the baseline window again.
        Any "first stint should be earlier" behaviour is handled in ensure_stint_plan()
        so later stints are not unintentionally shortened.
        """
        temp_state = TyreState(
            compound=compound_code,
            age_laps=0.0,
            weekend_role=role,
        )

        spec = self.tyre_model._resolve_spec(temp_state)

        peak = float(spec.peak_life)
        cliff = float(spec.cliff_start_age if spec.cliff_start_age is not None else (peak + 2.5))
        collapse = float(spec.collapse_start_age if spec.collapse_start_age is not None else (cliff + 3.5))

        # Mild track scaling only.
        deg_scale = max(0.92, min(1.04, 1.0 - ((self.track_deg_multiplier - 1.0) * 0.35)))

        min_review_age = max(3.0, (peak - 1.0) * deg_scale)
        target_age = max(min_review_age + 1.0, (cliff - 0.75) * deg_scale)
        max_age = max(target_age + 1.0, (collapse - 1.5) * deg_scale)

        return min_review_age, target_age, max_age
    
    def can_current_tyre_reach_finish(self, car: CarAgent, extra_margin: float = 0.75) -> bool:
        """
        Conservative finish check used to block unnecessary late stops.

        Important fix:
        stint_max_age is a strategic planning marker, not a literal "tyre explodes now"
        limit. In the final laps we allow a much larger margin so cars do not make
        nonsense splash-and-dash stops with 2-4 laps left unless the tyre is truly gone.
        """
        laps_remaining = max(0, self.remaining_laps)
        projected_finish_age = car.tyre_state.age_laps + laps_remaining

        effective_margin = extra_margin
        if laps_remaining <= 6:
            effective_margin = max(effective_margin, 3.0)
        if laps_remaining <= 3:
            effective_margin = max(effective_margin, 4.0)

        hard_finish_limit = car.stint_max_age + effective_margin
        return projected_finish_age <= hard_finish_limit

    def allow_late_stop(self, car: CarAgent, alt_role: str) -> bool:
        """
        Very restrictive late-stop gate.

        Late stops are only allowed if:
        - the tyre genuinely looks unable to reach the finish, or
        - it is already clearly beyond the intended operating window.

        Also adds a hard no-pit zone in the final laps unless the tyre truly cannot finish.
        """
        laps_remaining = max(0, self.remaining_laps)
        age = car.tyre_state.age_laps

        # Early / mid-race: normal logic can handle it.
        if laps_remaining > 18:
            return True

        # Hard no-pit zone near the end unless absolutely necessary.
        if laps_remaining <= 3:
            if not self.can_current_tyre_reach_finish(car, extra_margin=4.0):
                return True
            if age >= car.stint_max_age + 3.5:
                return True
            return False

        # If tyre cannot reasonably reach the end, allow the stop.
        if not self.can_current_tyre_reach_finish(car, extra_margin=0.75):
            return True

        # If already significantly beyond the planned max, allow it.
        if age >= car.stint_max_age + 1.5:
            return True

        # Very late in the race, do not pit just for a small pace gain.
        return False
    
    def estimate_finish_time_with_stop_delay(
        self,
        car: CarAgent,
        next_compound_code: str,
        pit_cost: float,
        delay_laps: int,
    ) -> float:
        """
        Project finish time if the car stays out for `delay_laps` more laps,
        then pits onto `next_compound_code`.
        """
        remaining = max(1, self.remaining_laps)
        live_now = self.get_snapshot(car)
        current_total = live_now.total_time if live_now is not None else car.total_time

        total = current_total
        age = car.tyre_state.age_laps
        compound = car.tyre_state.compound
        role = car.tyre_state.weekend_role

        laps_before_stop = min(delay_laps, remaining)

        for lap_idx in range(laps_before_stop):
            temp_state = TyreState(compound=compound, age_laps=age, weekend_role=role)

            tyre_delta = self.tyre_model.lap_delta(
                tyre_state=temp_state,
                track_deg_multiplier=self.track_deg_multiplier,
                team_deg_factor=car.calibration.k_team,
            )

            lap_time = self.base_lap_time + car.calibration.mu_team + tyre_delta

            # Staying in traffic usually still hurts before the stop.
            if lap_idx < 2:
                lap_time += car.traffic_penalty * 0.45
                lap_time -= car.slipstream_bonus * 0.20

            total += lap_time
            age += 1.0

        # Apply stop
        total += pit_cost

        new_role = self.get_role_from_code(next_compound_code)
        compound = next_compound_code
        role = new_role
        age = 0.0

        laps_after_stop = max(0, remaining - laps_before_stop)

        for lap_idx in range(laps_after_stop):
            temp_state = TyreState(compound=compound, age_laps=age, weekend_role=role)

            tyre_delta = self.tyre_model.lap_delta(
                tyre_state=temp_state,
                track_deg_multiplier=self.track_deg_multiplier,
                team_deg_factor=car.calibration.k_team,
            )

            lap_time = self.base_lap_time + car.calibration.mu_team + tyre_delta

            # Slight out-lap / warmup penalty after the stop.
            if lap_idx == 0:
                lap_time += 0.90
            elif lap_idx == 1:
                lap_time += 0.35

            total += lap_time
            age += 1.0

        return total
    
    def can_finish_legally_on_role(self, car: CarAgent, next_role: str) -> bool:
        """
        Dry-race legality check:
        by the finish, the car must have used at least two different dry compounds
        unless wet/intermediate tyres are involved.

        This method answers:
        "If we pit for `next_role` now, is there still a legal path to the flag?"
        """
        # Wet races are exempt from the two-dry-compound rule.
        if not self.is_dry_compound(car.tyre_state.compound):
            return True

        next_code = self.compound_map[next_role]

        if not self.is_dry_compound(next_code):
            return True

        used_now = set(car.used_dry_compounds)
        used_now.add(car.tyre_state.compound)

        used_after_this_stop = set(used_now)
        used_after_this_stop.add(next_code)

        # Already legal after this stop.
        if len(used_after_this_stop) >= 2:
            return True

        # From here onward, legality only matters in dry running.
        available_other_dry_roles = []
        for role in ("SOFT", "MEDIUM", "HARD"):
            code = self.compound_map[role]
            if not self.is_dry_compound(code):
                continue
            if role == next_role:
                continue
            if car.get_remaining_sets(role) > 0:
                available_other_dry_roles.append(role)

        laps_remaining_after_stop = max(0, self.remaining_laps)

        # Estimate whether another stop is realistically possible/necessary later.
        next_target = self.role_target_stint(next_role)
        next_max = self.role_max_stint_age(next_role)

        # If this stop is likely the final stop, then it MUST make the race legal now.
        likely_final_stop = (
            laps_remaining_after_stop <= next_max + 1.5
            or laps_remaining_after_stop <= next_target + 3.0
        )

        if likely_final_stop:
            return False

        # If another stop is possible, make sure at least one different dry compound exists.
        if not available_other_dry_roles:
            return False

        return True
    
    # ==========================================================
    # TIMING PROJECTIONS
    # ==========================================================
    def estimate_finish_time_on_plan(
        self,
        car: CarAgent,
        next_compound_code: Optional[str],
        pit_cost: float,
    ) -> float:
        """
        Simple finish projection from now to the flag.
        Used to compare 'stay out' vs 'pit now'.
        """
        remaining = max(1, self.remaining_laps)
        live_now = self.get_snapshot(car)
        current_total = live_now.total_time if live_now is not None else car.total_time

        total = current_total
        age = car.tyre_state.age_laps
        compound = car.tyre_state.compound
        role = car.tyre_state.weekend_role
        stop_applied = False

        for lap_idx in range(remaining):
            if (next_compound_code is not None) and (not stop_applied):
                compound = next_compound_code
                role = self.get_role_from_code(next_compound_code)
                age = 0.0
                total += pit_cost
                stop_applied = True

            temp_state = TyreState(compound=compound, age_laps=age, weekend_role=role)
            tyre_delta = self.tyre_model.lap_delta(
                tyre_state=temp_state,
                track_deg_multiplier=self.track_deg_multiplier,
                team_deg_factor=car.calibration.k_team,
            )

            lap_time = self.base_lap_time + car.calibration.mu_team + tyre_delta

            # A little carried traffic after a stop or while staying in a train.
            if lap_idx < 2:
                lap_time += car.traffic_penalty * 0.35

            total += lap_time
            age += 1.0

        return total

    def project_stint_time(
        self,
        car: CarAgent,
        compound_code: str,
        laps: Optional[int] = None,
    ) -> float:
        if laps is None:
            laps = min(self.projection_horizon, max(1, self.remaining_laps))

        total = 0.0

        if compound_code != car.tyre_state.compound:
            age = 0.0
            role = self.get_role_from_code(compound_code)
            traffic_carry = 0.0
        else:
            age = car.tyre_state.age_laps
            role = car.tyre_state.weekend_role
            traffic_carry = car.traffic_penalty * 0.40

        for lap_idx in range(laps):
            temp_state = TyreState(compound=compound_code, age_laps=age, weekend_role=role)

            tyre_delta = self.tyre_model.lap_delta(
                tyre_state=temp_state,
                track_deg_multiplier=self.track_deg_multiplier,
                team_deg_factor=car.calibration.k_team,
            )

            lap_time = self.base_lap_time + car.calibration.mu_team + tyre_delta

            if lap_idx < 2:
                lap_time += traffic_carry

            total += lap_time
            age += 1.0

        return total

    # ==========================================================
    # STRATEGY SCORING
    # ==========================================================
    def score_pit_option(self, car: CarAgent, alt_role: str) -> float:
        alt_code = self.compound_map[alt_role]
        current_role = car.tyre_state.weekend_role
        current_code = car.tyre_state.compound

        pit_cost = self.estimate_contextual_pit_loss(car)

        pit_now_finish = self.estimate_finish_time_on_plan(car, alt_code, pit_cost=pit_cost)
        pit_next_lap_finish = self.estimate_finish_time_after_delay(
            car,
            alt_code,
            pit_cost=pit_cost,
            delay_laps=1,
        )

        # Positive means pitting now is better than waiting one more lap.
        timing_gain = pit_next_lap_finish - pit_now_finish

        _, _, rejoin_clear_air = self.estimate_rejoin_gap(car, pit_cost=pit_cost)

        traffic_risk = 0.0
        if rejoin_clear_air < 1.0:
            traffic_risk = 1.8
        elif rejoin_clear_air < 2.5:
            traffic_risk = 0.9
        elif rejoin_clear_air < 4.0:
            traffic_risk = 0.4

        undercut_pressure, cover_pressure = self.get_nearby_rival_pit_pressure(car)

        age = car.tyre_state.age_laps
        target_age = car.stint_target_age
        max_age = car.stint_max_age
        laps_remaining = max(0, self.remaining_laps)

        age_pressure = 0.0
        over_target = max(0.0, age - target_age)
        over_max = max(0.0, age - max_age)

        # General stop pressure as tyre ages.
        if age >= target_age - 1.5:
            age_pressure += (age - (target_age - 1.5)) * 0.95

        if over_target > 0.0:
            age_pressure += 2.20 + (over_target * 1.85) + ((over_target ** 2) * 0.70)

        if over_max > 0.0:
            age_pressure += 5.00 + (over_max * 3.40) + ((over_max ** 2) * 2.20)

        # Strong extra push specifically for the opening stint.
        first_stint_bonus = 0.0
        if car.current_stint_id == 1:
            if age >= target_age - 2.0:
                first_stint_bonus += 4.0

            if age >= target_age - 1.0:
                first_stint_bonus += 5.5

            if age >= target_age:
                first_stint_bonus += 8.5 + (over_target * 3.0)

            if age >= max_age:
                first_stint_bonus += 11.0 + (over_max * 4.0)

        early_stop_penalty = 0.0
        if age < car.stint_min_review_age:
            early_stop_penalty += (car.stint_min_review_age - age) * 0.95

        same_role_penalty = 0.0
        if alt_role == current_role:
            same_role_penalty = 0.60

        legality_bonus = 0.0
        used_now = set(car.used_dry_compounds)
        used_now.add(current_code)

        used_if_pitted = set(used_now)
        used_if_pitted.add(alt_code)

        # Hard legality guard for dry races.
        if self.is_dry_compound(current_code) and self.is_dry_compound(alt_code):
            if not self.can_finish_legally_on_role(car, alt_role):
                return -999.0

        # Small bonus for satisfying the rule earlier rather than later.
        if len(used_if_pitted) >= 2 and len(used_now) < 2:
            legality_bonus += 1.2

        availability_penalty = 0.0
        if car.get_remaining_sets(alt_role) <= 0:
            availability_penalty += 100.0

        durability_bonus = 0.0
        if current_role == "SOFT" and alt_role in {"MEDIUM", "HARD"}:
            durability_bonus += 0.30
        elif current_role == "MEDIUM" and alt_role == "HARD":
            durability_bonus += 0.30

        undercut_value = 0.0
        ahead_snap, _ = self.get_neighbours(car)

        if ahead_snap is not None and ahead_snap.team_id != car.team_id:
            gap_to_ahead = max(0.0, self.get_snapshot(car).total_time - ahead_snap.total_time)
            if gap_to_ahead < 3.0:
                undercut_value += max(0.0, 2.8 - gap_to_ahead) * 0.55

        # Strong discouragement for unnecessary extra stops late in the race.
        late_stop_penalty = 0.0
        if laps_remaining <= 18 and self.can_current_tyre_reach_finish(car, extra_margin=0.75):
            late_stop_penalty += 10.0
        if laps_remaining <= 12 and self.can_current_tyre_reach_finish(car, extra_margin=0.75):
            late_stop_penalty += 14.0
        if laps_remaining <= 8 and self.can_current_tyre_reach_finish(car, extra_margin=0.75):
            late_stop_penalty += 20.0

        projected_total_stops = car.pit_stops_made + 1
        planned_total_stops = 1 if self.total_laps <= 45 else 2

        extra_stop_penalty = 0.0
        if projected_total_stops > planned_total_stops:
            extra_stop_penalty += 12.0
            if laps_remaining <= 18:
                extra_stop_penalty += 6.0
            if laps_remaining <= 12:
                extra_stop_penalty += 8.0

        finish_bias_penalty = 0.0
        if self.can_current_tyre_reach_finish(car, extra_margin=0.75):
            finish_bias_penalty += 0.65 * max(0.0, timing_gain)
            if laps_remaining <= 15:
                finish_bias_penalty += 0.90 * max(0.0, timing_gain)

        # Extra hard block against pointless splash stops near the end.
        # If the tyre can finish and the stop is not clearly worth it, make the option terrible.
        if laps_remaining <= 6 and self.can_current_tyre_reach_finish(car, extra_margin=3.0):
            if timing_gain <= 0.25:
                return -999.0

        if laps_remaining <= 3 and self.can_current_tyre_reach_finish(car, extra_margin=4.0):
            return -999.0

        score = (
            (1.35 * timing_gain)
            + age_pressure
            + first_stint_bonus
            + undercut_pressure
            + cover_pressure
            + undercut_value
            + legality_bonus
            + durability_bonus
            - traffic_risk
            - same_role_penalty
            - early_stop_penalty
            - availability_penalty
            - late_stop_penalty
            - extra_stop_penalty
            - finish_bias_penalty
        )

        return score

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
        self._code_to_label = {v: k for k, v in self.compound_map.items()}

        for car in self.team_cars:
            self.ensure_stint_plan(car)

    def evaluate_stint_outcomes(self) -> None:
        if self.remaining_laps <= 1 or self.track_state not in {"GREEN", "SC", "VSC"}:
            return

        self.pit_candidates = []
        self.candidate_scores = {}

        for car in self.team_cars:
            if car.retired or car.pending_pit or car.in_pit_lane:
                continue

            self.ensure_stint_plan(car)

            if not self.should_start_live_pit_review(car):
                continue

            if car.last_strategy_call_lap == self.current_lap:
                continue

            available_roles = self.get_available_pit_roles(car)
            if not available_roles:
                continue

            age = car.tyre_state.age_laps
            max_age = car.stint_max_age

            # Hard guardrail: once clearly beyond the maximum intended stint, force the stop.
            # Important fix:
            # do NOT let this trigger nonsense late splash stops if the tyre can still finish.
            forced_stop_tolerance = 0.75
            if age >= max_age + forced_stop_tolerance:
                if self.remaining_laps <= 6 and self.can_current_tyre_reach_finish(car, extra_margin=3.0):
                    pass
                else:
                    best_role = None
                    best_score = float("-inf")

                    for alt_role in available_roles:
                        if not self.allow_late_stop(car, alt_role):
                            continue

                        score = self.score_pit_option(car, alt_role)
                        if score > best_score:
                            best_score = score
                            best_role = alt_role

                    if best_role is not None:
                        self.pit_candidates.append((car, best_role))
                        self.candidate_scores[car.car_id] = best_score + 12.0
                        car.last_strategy_call_lap = self.current_lap
                        continue

            best_role = None
            best_score = float("-inf")

            for alt_role in available_roles:
                # Late-race veto: do not even score speculative late stops unless justified.
                if not self.allow_late_stop(car, alt_role):
                    continue

                score = self.score_pit_option(car, alt_role)

                if score > best_score:
                    best_score = score
                    best_role = alt_role

            # If every late-stop option was vetoed, just continue.
            if best_role is None:
                continue

            threshold = self.get_pit_call_threshold(car)

            # Additional softening once target has been reached.
            if age >= car.stint_target_age:
                threshold -= 0.20

            # Stronger push beyond the maximum stint.
            if age >= max_age:
                threshold -= 0.75

            # Debug: show why first stint is or is not triggering a stop.
            if car.current_stint_id == 1:
                print(
                    f"[DEBUG FIRST STINT DECISION] "
                    f"{self.team_id} | {car.car_id} | "
                    f"lap={self.current_lap} | "
                    f"age={car.tyre_state.age_laps:.2f} | "
                    f"best_role={best_role} | "
                    f"best_score={best_score:.3f} | "
                    f"threshold={threshold:.3f} | "
                    f"target={car.stint_target_age:.2f} | "
                    f"max={car.stint_max_age:.2f}"
                )

            if best_role is not None and best_score > threshold:
                self.pit_candidates.append((car, best_role))
                self.candidate_scores[car.car_id] = best_score
                car.last_strategy_call_lap = self.current_lap

    def resolve_team_conflicts(self) -> None:
        if len(self.pit_candidates) <= 1:
            return

        # Teams may double-stack, but only if both calls are genuinely strong.
        self.pit_candidates.sort(
            key=lambda item: self.candidate_scores.get(item[0].car_id, 0.0),
            reverse=True,
        )

        filtered_candidates: list[tuple[CarAgent, str]] = []

        for car, compound in self.pit_candidates:
            score = self.candidate_scores.get(car.car_id, 0.0)
            threshold = self.get_pit_call_threshold(car)

            # Teammate already selected: require a slightly stronger score.
            if filtered_candidates:
                if car.tyre_state.age_laps < car.stint_max_age:
                    continue
                threshold += 0.35

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
        for car, role in self.pit_candidates:
            if car.retired or car.pending_pit or car.in_pit_lane:
                continue

            if car.get_remaining_sets(role) <= 0:
                continue

            compound_code = self.compound_map[role]
            car.pit(compound_code, role)