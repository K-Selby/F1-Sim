from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class TyreSpec:
    warmup_laps: int
    warmup_start_penalty: float
    peak_life: int
    deg_linear: float
    deg_quadratic: float


class TyreModel:
    """
    Temporary compound-based tyre model:
    - Warm-up improvement: penalty decreases linearly to 0 over warmup_laps
    - Peak window: no deg until peak_life
    - Post-peak deg: linear + quadratic on (life - peak_life)
    """

    def __init__(self, tyres_json: Dict):
        self._raw = tyres_json
        self._tyres: Dict[str, TyreSpec] = {}
        for k, v in tyres_json["tyres"].items():
            self._tyres[k] = TyreSpec(
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
        team_deg_factor: float,
    ) -> float:
        """
        Returns delta seconds to add to base lap time.
        """
        spec = self._tyres[compound]
        life = max(0, int(life))

        # Warmup: penalty decreases to ~0 across warmup window
        warmup_pen = 0.0
        if spec.warmup_laps > 0 and life < spec.warmup_laps:
            if spec.warmup_laps == 1:
                warmup_pen = spec.warmup_start_penalty
            else:
                # life=0 -> full penalty, life=warmup_laps-1 -> ~0
                frac = 1.0 - (life / (spec.warmup_laps - 1))
                warmup_pen = spec.warmup_start_penalty * max(0.0, frac)

        # Degradation: starts AFTER peak_life
        age = max(0, life - spec.peak_life)
        deg = (spec.deg_linear * age) + (spec.deg_quadratic * (age ** 2))

        # Scale deg by track + team factor (and warmup lightly by track)
        scaled = (warmup_pen * (0.7 + 0.3 * track_deg_multiplier)) + (deg * track_deg_multiplier * team_deg_factor)
        return max(0.0, scaled)