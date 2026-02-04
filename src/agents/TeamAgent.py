from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TeamPerformance:
    pace_offset: float
    degradation_factor: float
    pit_execution_std: float


@dataclass
class StrategyProfile:
    risk_tolerance: float = 0.5
    undercut_bias: float = 0.5
    overcut_bias: float = 0.5


class Team_Agent:
    """
    Minimal team agent for MVP:
    - Holds performance parameters (pace_offset, degradation_factor, pit_execution_std)
    - No decision-making yet (strategy is fixed globally in v0.5)
    """

    def __init__(self, name: str, performance: TeamPerformance, strategy: StrategyProfile | None = None):
        self.name = name
        self.performance = performance
        self.strategy = strategy or StrategyProfile()

    @property
    def pace_offset(self) -> float:
        return float(self.performance.pace_offset)

    @property
    def degradation_factor(self) -> float:
        return float(self.performance.degradation_factor)

    @property
    def pit_execution_std(self) -> float:
        return float(self.performance.pit_execution_std)