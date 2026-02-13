# src/agents/TeamAgent.py

from __future__ import annotations
from typing import List, Optional

from src.agents.CarAgent import CarAgent
from src.sim.RaceState import CarSnapshot


class TeamAgent:

    def __init__(self, team_id: str, car_a: CarAgent, car_b: CarAgent, mu_team: float, k_team: float):

        self.team_id = team_id
        self.car_a = car_a
        self.car_b = car_b

        self.mu_team = mu_team
        self.k_team = k_team

        self.current_lap: int = 0
        self.track_state: str = "GREEN"
        self.race_view: List[CarSnapshot] = []

        self.has_pitted: bool = False
        self.target_compound: Optional[str] = None

    # ==========================================================
    # OBSERVATION
    # ==========================================================

    def observe(self, race_view: List[CarSnapshot], lap: int, track_state: str) -> None:
        self.race_view = race_view
        self.current_lap = lap
        self.track_state = track_state

    # ==========================================================
    # DECISION
    # ==========================================================

    def decide(self) -> None:

        self.update_race_context()
        self.evaluate_stint_outcomes()
        self.assess_undercut_overcut()
        self.resolve_team_conflicts()
        self.issue_commands()

    # ==========================================================
    # STRATEGY PLACEHOLDERS
    # ==========================================================

    def update_race_context(self) -> None:
        pass

    def evaluate_stint_outcomes(self) -> None:
        pass

    def assess_undercut_overcut(self) -> None:
        pass

    def resolve_team_conflicts(self) -> None:
        pass

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
        if self.current_lap == 5 and not self.has_pitted:
            self.target_compound = "C2"
            self.car_a.pit(self.target_compound)
            self.car_b.pit(self.target_compound)
            self.has_pitted = True