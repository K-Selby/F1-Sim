from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Dict, Optional


@dataclass
class TyreSpec:
    warmup_laps: float
    warmup_start_penalty: float
    peak_life: float
    deg_linear: float
    deg_quadratic: float

    peak_bonus: float = 0.06
    cliff_start_age: float | None = None
    cliff_linear: float = 0.10
    cliff_power: float = 1.70
    collapse_start_age: float | None = None
    collapse_linear: float = 0.18
    collapse_power: float = 1.50


@dataclass
class TyreState:
    compound: str
    age_laps: float = 0.0
    weekend_role: Optional[str] = None  # SOFT / MEDIUM / HARD / None


class TyreModel:
    def __init__(self, tyres_json: Dict):
        self._tyres: Dict[str, TyreSpec] = {}
        self._role_modifiers: Dict[str, Dict] = tyres_json.get("role_modifiers", {})

        for compound, cfg in tyres_json["tyres"].items():
            self._tyres[compound] = TyreSpec(
                warmup_laps=float(cfg["warmup_laps"]),
                warmup_start_penalty=float(cfg["warmup_start_penalty"]),
                peak_life=float(cfg["peak_life"]),
                deg_linear=float(cfg["deg_linear"]),
                deg_quadratic=float(cfg["deg_quadratic"]),
                peak_bonus=float(cfg.get("peak_bonus", 0.06)),
                cliff_start_age=(
                    float(cfg["cliff_start_age"])
                    if cfg.get("cliff_start_age") is not None else None
                ),
                cliff_linear=float(cfg.get("cliff_linear", 0.10)),
                cliff_power=float(cfg.get("cliff_power", 1.70)),
                collapse_start_age=(
                    float(cfg["collapse_start_age"])
                    if cfg.get("collapse_start_age") is not None else None
                ),
                collapse_linear=float(cfg.get("collapse_linear", 0.18)),
                collapse_power=float(cfg.get("collapse_power", 1.50)),
            )

    def advance(self, tyre_state: TyreState, laps: float = 1.0) -> None:
        tyre_state.age_laps = max(0.0, tyre_state.age_laps + float(laps))

    def _resolve_spec(self, tyre_state: TyreState) -> TyreSpec:
        compound = tyre_state.compound

        if compound not in self._tyres:
            raise KeyError(f"Unknown compound passed to TyreModel: {compound}")

        base = self._tyres[compound]
        role = tyre_state.weekend_role

        if role is None or role not in self._role_modifiers:
            return base

        mod = self._role_modifiers[role]

        return replace(
            base,
            warmup_laps=base.warmup_laps * float(mod.get("warmup_laps_mult", 1.0)),
            warmup_start_penalty=base.warmup_start_penalty * float(mod.get("warmup_start_penalty_mult", 1.0)),
            peak_life=base.peak_life * float(mod.get("peak_life_mult", 1.0)),
            deg_linear=base.deg_linear * float(mod.get("deg_linear_mult", 1.0)),
            deg_quadratic=base.deg_quadratic * float(mod.get("deg_quadratic_mult", 1.0)),
            peak_bonus=base.peak_bonus * float(mod.get("peak_bonus_mult", 1.0)),
            cliff_start_age=(
                None if base.cliff_start_age is None
                else base.cliff_start_age * float(mod.get("cliff_start_age_mult", 1.0))
            ),
            cliff_linear=base.cliff_linear * float(mod.get("cliff_linear_mult", 1.0)),
            cliff_power=base.cliff_power * float(mod.get("cliff_power_mult", 1.0)),
            collapse_start_age=(
                None if base.collapse_start_age is None
                else base.collapse_start_age * float(mod.get("collapse_start_age_mult", 1.0))
            ),
            collapse_linear=base.collapse_linear * float(mod.get("collapse_linear_mult", 1.0)),
            collapse_power=base.collapse_power * float(mod.get("collapse_power_mult", 1.0)),
        )

    def lap_delta(self, tyre_state: TyreState, track_deg_multiplier: float, team_deg_factor: float) -> float:
        age = float(tyre_state.age_laps)
        spec = self._resolve_spec(tyre_state)

        delta = 0.0

        # Phase 1: warm-up
        if age < spec.warmup_laps:
            warmup_progress = age / max(spec.warmup_laps, 1e-6)
            cold_factor = 1.0 - min(1.0, max(0.0, warmup_progress))
            delta += spec.warmup_start_penalty * (cold_factor ** 1.22)

        # Phase 2: peak window
        if spec.warmup_laps <= age <= spec.peak_life:
            peak_centre = 0.5 * (spec.warmup_laps + spec.peak_life)
            peak_half_span = max(0.70, 0.5 * (spec.peak_life - spec.warmup_laps))
            distance = abs(age - peak_centre) / peak_half_span
            shape = max(0.0, 1.0 - (distance ** 1.40))
            delta -= spec.peak_bonus * shape

        wear_delta = 0.0

        # Phase 3: primary wear
        if age > spec.peak_life:
            deg_age = age - spec.peak_life
            wear_delta += (
                spec.deg_linear * deg_age
                + spec.deg_quadratic * (deg_age ** 2)
            )

        # Phase 4: cliff
        cliff_start = (
            spec.cliff_start_age
            if spec.cliff_start_age is not None
            else (spec.peak_life + 2.5)
        )

        if age > cliff_start:
            cliff_age = age - cliff_start
            wear_delta += spec.cliff_linear * (cliff_age ** spec.cliff_power)

        # Phase 5: collapse
        collapse_start = (
            spec.collapse_start_age
            if spec.collapse_start_age is not None
            else (cliff_start + 4.0)
        )

        if age > collapse_start:
            collapse_age = age - collapse_start
            wear_delta += spec.collapse_linear * (collapse_age ** spec.collapse_power)

        # Slight extra pressure once tyre is clearly beyond peak.
        if age > spec.peak_life:
            post_peak_age = age - spec.peak_life
            wear_delta += 0.010 * (post_peak_age ** 1.35)

        # Track and team scaling
        team_scale = 1.0 + (0.42 * (float(team_deg_factor) - 1.0))
        wear_scale = float(track_deg_multiplier) * team_scale
        wear_scale = min(max(wear_scale, 0.90), 1.26)

        delta += wear_delta * wear_scale

        return max(-0.10, delta)