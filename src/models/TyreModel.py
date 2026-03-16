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
    # REQUIRED by CarAgent
    # ------------------------------------------------------------
    def advance(self, tyre_state: TyreState, laps: int = 1) -> None:
        """
        Advance tyre age by N laps.
        """
        tyre_state.age_laps += int(laps)

    # ------------------------------------------------------------
    # Lap-time delta calculation
    # ------------------------------------------------------------
    def lap_delta(self, tyre_state, track_deg_multiplier: float, team_deg_factor: float) -> float:
        compound = tyre_state.compound
        age = tyre_state.age_laps

        if compound not in self._tyres:
            raise KeyError(f"Unknown compound passed to TyreModel: {compound}")

        spec = self._tyres[compound]
        delta = 0.0

        # -----------------------------
        # Phase 1: Warmup
        # -----------------------------
        if age < spec.warmup_laps:
            warmup_progress = age / max(1, spec.warmup_laps)
            warmup_penalty = spec.warmup_start_penalty * (1.0 - warmup_progress)
            delta += warmup_penalty

        # -----------------------------
        # Phase 2: Peak window
        # Small reward once tyre is switched on
        # -----------------------------
        if spec.warmup_laps <= age <= spec.peak_life:
            peak_window = max(1, spec.peak_life - spec.warmup_laps + 1)
            peak_progress = (age - spec.warmup_laps) / peak_window

            # Small peak benefit in the middle of the best operating window
            peak_bonus = 0.08 * (1.0 - abs((peak_progress * 2.0) - 1.0))
            delta -= peak_bonus

        # -----------------------------
        # Phase 3: Wear build-up
        # -----------------------------
        if age > spec.peak_life:
            deg_age = age - spec.peak_life
            degradation = (
                spec.deg_linear * deg_age +
                spec.deg_quadratic * (deg_age ** 2)
            )
            delta += degradation

        # -----------------------------
        # Phase 4: Tyre cliff
        # Adds stronger late-stint fall-off
        # -----------------------------
        cliff_start = spec.peak_life + max(2, spec.warmup_laps)
        if age > cliff_start:
            cliff_age = age - cliff_start
            cliff_penalty = 0.03 * (cliff_age ** 2)
            delta += cliff_penalty

        # -----------------------------
        # Track + Team scaling
        # -----------------------------
        delta *= track_deg_multiplier
        delta *= team_deg_factor

        return delta