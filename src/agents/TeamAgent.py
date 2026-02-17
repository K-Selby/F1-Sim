# src/agents/TeamAgent.py

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

        # Runtime race context (set via observe)
        self.current_lap: int = 0
        self.track_state: str = "GREEN"
        self.race_view: List[CarSnapshot] = []

        self.pit_loss: float = 0.0
        self.base_lap_time: float = 0.0
        self.tyre_model: Optional[TyreModel] = None
        
        # Strategy state
        self.last_pit_lap: Optional[int] = None
        self.projection_horizon = 8

        self.pit_candidates: List[tuple[CarAgent, str]] = []

    # ==========================================================
    # OBSERVATION (called by RaceManager each lap)
    # ==========================================================
    def observe(self, race_view: List[CarSnapshot], lap: int, track_state: str, pit_loss: float, base_lap_time: float, tyre_model: TyreModel, total_laps: int) -> None:
        self.race_view = race_view
        self.current_lap = lap
        self.track_state = track_state
        self.pit_loss = pit_loss
        self.base_lap_time = base_lap_time
        self.tyre_model = tyre_model
        self.total_laps = total_laps

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
    # STRATEGY Logic
    # ==========================================================
    def update_race_context(self) -> None:
        self.pit_candidates = []

    def project_stint_time(self, car: CarAgent, compound: str) -> float:
        """
        Project next N laps if car runs this compound.
        Includes degradation + warmup.
        """

        total = 0.0

        # If switching compound -> start at age 0
        if compound != car.tyre_state.compound:
            age = 0
        else:
            age = car.tyre_state.age_laps

        for _ in range(self.projection_horizon):
            if compound in self.compound_map:
                compound_code = self.compound_map[compound]   # SOFT → C3
                
            else:
                compound_code = compound  # already C1/C2/C3
                
            temp_state = TyreState(compound=compound_code, age_laps=age)
            tyre_delta = self.tyre_model.lap_delta(tyre_state=temp_state, track_deg_multiplier=1.0, team_deg_factor=car.calibration.k_team)

            lap_time = self.base_lap_time + car.calibration.mu_team + tyre_delta
            total += lap_time

            age += 1

        return total

    def evaluate_stint_outcomes(self):
        remaining_laps = self.total_laps - self.current_lap
        
        if remaining_laps <= self.projection_horizon:
            return  # Too late to pit
        
        for car in [self.car_a, self.car_b]:
            if car.retired:
                continue

            current_projection = self.project_stint_time(car, car.tyre_state.compound)

            best_option = None
            best_delta = 0.0

            for compound in self.compound_map:
                if compound == car.tyre_state.compound:
                    continue

                alt_projection = self.project_stint_time(car, compound)
                delta = current_projection - (alt_projection + self.pit_loss)

                if delta > best_delta:
                    best_delta = delta
                    best_option = compound

            if best_option is not None and best_delta > 0:
                self.pit_candidates.append((car, best_option))

    def assess_undercut_overcut(self) -> None:
        updated_candidates = []
        sorted_view = sorted(self.race_view, key=lambda c: c.total_time)

        for car, compound in self.pit_candidates:
            ahead = None

            for i, snap in enumerate(sorted_view):
                if snap.car_id == car.car_id and i > 0:
                    ahead = sorted_view[i - 1]
                    break

            if ahead is None:
                updated_candidates.append((car, compound))
                continue

            gap = car.total_time - ahead.total_time

            fresh_avg = self.project_stint_time(car, compound) / self.projection_horizon
            worn_avg = self.project_stint_time(car, car.tyre_state.compound) / self.projection_horizon

            undercut_gain = worn_avg - fresh_avg
            traffic_penalty = 0.5 if gap > 5 else 0.0
            effective_gain = undercut_gain - traffic_penalty

            if effective_gain > gap:
                updated_candidates.append((car, compound))

        self.pit_candidates = updated_candidates

    def resolve_team_conflicts(self) -> None:
        if len(self.pit_candidates) <= 1:
            return

        # Only allow leading car to pit
        self.pit_candidates = sorted(self.pit_candidates, key=lambda x: x[0].total_time)[:1]
        
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
        for car, compound in self.pit_candidates:

            if self.last_pit_lap == self.current_lap:
                return  # double stack prevention

            print(f"[Lap {self.current_lap}] {self.team_id} orders {car.car_id} to PIT for {compound}")

            if compound in self.compound_map:
                compound_code = self.compound_map[compound]
            else:
                compound_code = compound

            car.pit(compound_code)
            self.last_pit_lap = self.current_lap