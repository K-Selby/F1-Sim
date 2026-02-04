from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class TyreSpec:
    """
    Calibrated per-compound parameters loaded from configs/tyres.json.
    """
    warmup_laps: int
    warmup_start_penalty: float
    peak_life: int
    deg_linear: float
    deg_quadratic: float


@dataclass
class TyreState:
    """
    Per-car tyre STATE (lives on CarAgent in the design):
    - compound: current compound code (e.g., SOFT/MEDIUM/HARD)
    - age_laps: laps on this set of tyres (stint age)
    """
    compound: str
    age_laps: int = 0


class TyreModel:
    """
    Shared calibrated tyre MODEL (loaded once from JSON), used by CarAgent each lap.

    Matches the design intent:
    - degradation depends on stint age and compound coefficients
    - scaled by team tyre management factor (k_team) and track degradation multiplier
    """

    def __init__(self, tyres_json: Dict):
        if "tyres" not in tyres_json or not isinstance(tyres_json["tyres"], dict):
            raise ValueError("tyres_json must contain a 'tyres' object mapping compound -> parameters")

        self._raw = tyres_json
        self._tyres: Dict[str, TyreSpec] = {}

        for compound, v in tyres_json["tyres"].items():
            self._tyres[str(compound)] = TyreSpec(
                warmup_laps=int(v["warmup_laps"]),
                warmup_start_penalty=float(v["warmup_start_penalty"]),
                peak_life=int(v["peak_life"]),
                deg_linear=float(v["deg_linear"]),
                deg_quadratic=float(v["deg_quadratic"]),
            )

    def lap_delta(
        self,
        compound: str,
        life: int,
        track_deg_multiplier: float,
        k_team: float,
    ) -> float:
        """
        Returns delta seconds to add to baseline lap time due to warm-up + degradation.

        Parameters
        ----------
        compound : str
            Compound code key (must exist in tyres.json)
        life : int
            Stint age in laps (>=0)
        track_deg_multiplier : float
            Circuit/conditions multiplier (>=0). 1.0 = nominal.
        k_team : float
            Team tyre management factor (>=0). Lower = better tyre life, higher = worse.
        """
        if compound not in self._tyres:
            raise KeyError(f"Unknown compound '{compound}'. Check configs/tyres.json keys.")

        spec = self._tyres[compound]
        life = max(0, int(life))
        track_deg_multiplier = max(0.0, float(track_deg_multiplier))
        k_team = max(0.0, float(k_team))

        # 1) Warmup: penalty decreases linearly to ~0 over warmup window
        warmup_pen = 0.0
        if spec.warmup_laps > 0 and life < spec.warmup_laps:
            if spec.warmup_laps == 1:
                warmup_pen = spec.warmup_start_penalty
            else:
                # life=0 -> full penalty, life=warmup_laps-1 -> ~0
                frac = 1.0 - (life / (spec.warmup_laps - 1))
                warmup_pen = spec.warmup_start_penalty * max(0.0, frac)

        # 2) Degradation: starts AFTER peak_life
        age_post_peak = max(0, life - spec.peak_life)
        deg = (spec.deg_linear * age_post_peak) + (spec.deg_quadratic * (age_post_peak ** 2))

        # 3) Scale by track + team
        # Warmup is lightly track-sensitive; degradation is fully scaled.
        scaled = (warmup_pen * (0.7 + 0.3 * track_deg_multiplier)) + (deg * track_deg_multiplier * k_team)
        return max(0.0, scaled)

    def advance(self, tyre_state: TyreState, laps: int = 1) -> TyreState:
        """
        Increments stint age and returns the updated state (pure + explicit).
        """
        laps = max(0, int(laps))
        tyre_state.age_laps = max(0, int(tyre_state.age_laps) + laps)
        return tyre_state