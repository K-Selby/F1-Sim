from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class TyreSpec:
    warmup_laps: int
    warmup_start_penalty: float
    peak_life: int
    deg_linear: float
    deg_quadratic: float


@dataclass
class TyreState:
    compound: str
    age_laps: int = 0


class TyreModel:
    """
    Proper tyre performance model used by CarAgent.

    Responsibilities:
    - Hold calibrated tyre parameters (from tyres.json)
    - Advance tyre age
    - Compute lap-time delta from tyre effects
    """

    def __init__(self, tyres_json: Dict):
        self._tyres: Dict[str, TyreSpec] = {}

        for compound, cfg in tyres_json["tyres"].items():
            self._tyres[compound] = TyreSpec(
                warmup_laps=int(cfg["warmup_laps"]),
                warmup_start_penalty=float(cfg["warmup_start_penalty"]),
                peak_life=int(cfg["peak_life"]),
                deg_linear=float(cfg["deg_linear"]),
                deg_quadratic=float(cfg["deg_quadratic"]),
            )

    # ------------------------------------------------------------
    # REQUIRED by CarAgent (this was missing)
    # ------------------------------------------------------------
    def advance(self, tyre_state: TyreState, laps: int = 1) -> None:
        """
        Advance tyre age by N laps.
        """
        tyre_state.age_laps += int(laps)

    # ------------------------------------------------------------
    # Lap-time delta calculation
    # ------------------------------------------------------------
    def lap_delta(
        self,
        tyre_state: TyreState,
        track_deg_multiplier: float,
        team_deg_factor: float,
    ) -> float:
        """
        Returns tyre-induced lap time delta (seconds).
        """
        spec = self._tyres[tyre_state.compound]
        life = max(0, tyre_state.age_laps)

        # Warm-up phase (penalty decreases to 0)
        warmup_pen = 0.0
        if spec.warmup_laps > 0 and life < spec.warmup_laps:
            frac = 1.0 - (life / spec.warmup_laps)
            warmup_pen = spec.warmup_start_penalty * max(0.0, frac)

        # Degradation after peak life
        age = max(0, life - spec.peak_life)
        deg_pen = (spec.deg_linear * age) + (spec.deg_quadratic * (age ** 2))

        # Scale degradation
        return (warmup_pen + deg_pen) * track_deg_multiplier * team_deg_factor