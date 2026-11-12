"""Triagem geométrica estrita e ranking exploratório, sem proxy de produtividade."""
from __future__ import annotations

import math
from typing import Iterable

from .geometry import REFERENCE_DI_MAX_PCT, REFERENCE_DI_MIN_PCT, REFERENCE_HW_MAX, REFERENCE_HW_MIN


# Resolução usada apenas para comparar números normalizados sujeitos a ruído
# binário; equivale a 1e-12 da largura de cada faixa, não a tolerância física.
RANK_NUMERIC_RESOLUTION = 1e-12

SOURCE_STUDY_WINDOW = {
    "id": "in625_ded_lb_source_study_2026",
    "material": "IN625",
    "process": "DED-LB alimentado por pó",
    "limits": {
        "DI_pct": [REFERENCE_DI_MIN_PCT, REFERENCE_DI_MAX_PCT],
        "H_over_W": [REFERENCE_HW_MIN, REFERENCE_HW_MAX],
    },
    "boundary_policy": "strict",
    "provenance": "Critérios geométricos relatados pelo estudo compatível com a tabela, não limites universais nem classes observadas de defeito.",
    "source_url": "https://link.springer.com/article/10.1007/s11665-026-14887-8",
}


def _finite(value) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _window_relation(value, low, high, error_band=None) -> str:
    """Classifica ponto/banda; contato com borda não satisfaz faixa estrita."""
    x = _finite(value)
    if x is None:
        return "unavailable"
    inside = low < x < high
    boundary = x == low or x == high
    if error_band is None:
        if inside:
            return "point_inside_reference"
        return "point_on_reference_boundary" if boundary else "point_outside_reference"

    lo = _finite(error_band.get("low"))
    hi = _finite(error_band.get("high"))
    if lo is None or hi is None:
        if inside:
            return "point_inside_reference"
        return "point_on_reference_boundary" if boundary else "point_outside_reference"
    if lo > low and hi < high:
        return "indicative_band_inside_reference_not_calibrated"
    if hi < low or lo > high:
        return "indicative_band_outside_reference_not_calibrated"
    if hi == low or lo == high or lo == low or hi == high:
        return "indicative_band_touches_reference_boundary_not_calibrated"
    return "indicative_band_crosses_reference_boundary_not_calibrated"


def geometry_reference_screen(
    *,
    di_pct: float | None,
    h_over_w: float | None,
    di_error_band: dict | None = None,
    hw_error_band: dict | None = None,
    window: dict | None = None,
) -> dict:
    """Compara ponto e bandas indicativas às faixas abertas de uma referência.

    As bandas são quantis de erro CV do modelo e não intervalos conformais,
    probabilidades ou garantias de cobertura. Violações são distâncias fora da
    faixa divididas por sua largura; estar exatamente na borda tem excesso zero,
    mas pertence explicitamente à classe fora (não à classe dentro).
    """
    ref = window or SOURCE_STUDY_WINDOW
    di_low, di_high = ref["limits"]["DI_pct"]
    hw_low, hw_high = ref["limits"]["H_over_W"]
    di_value = _finite(di_pct)
    hw_value = _finite(h_over_w)
    di_rel = _window_relation(di_value, di_low, di_high, di_error_band)
    hw_rel = _window_relation(hw_value, hw_low, hw_high, hw_error_band)

    def band_spill(band, low, high):
        if not isinstance(band, dict):
            return None
        band_low, band_high = _finite(band.get("low")), _finite(band.get("high"))
        if band_low is None or band_high is None:
            return None
        return (max(low - band_low, 0.0) + max(band_high - high, 0.0)) / (high - low)

    di_band_spill = band_spill(di_error_band, di_low, di_high)
    hw_band_spill = band_spill(hw_error_band, hw_low, hw_high)
    available_spills = [value for value in (di_band_spill, hw_band_spill) if value is not None]
    normalized_band_spill = float(sum(available_spills)) if len(available_spills) == 2 else None

    violations = []
    if di_value is not None:
        violations.append(max(di_low - di_value, 0.0, di_value - di_high) / (di_high - di_low))
    if hw_value is not None:
        violations.append(max(hw_low - hw_value, 0.0, hw_value - hw_high) / (hw_high - hw_low))
    point_inside = (
        di_value is not None and hw_value is not None
        and di_low < di_value < di_high and hw_low < hw_value < hw_high
    )
    point_available = di_value is not None and hw_value is not None
    point_on_boundary = point_available and (
        di_value in (di_low, di_high) or hw_value in (hw_low, hw_high)
    )
    point_class = (
        "inside" if point_inside else
        "boundary" if point_on_boundary else
        "outside" if point_available else "unavailable"
    )
    band_inside_relations = {"indicative_band_inside_reference_not_calibrated"}
    bands_available = di_band_spill is not None and hw_band_spill is not None
    both_bands_inside = bands_available and di_rel in band_inside_relations and hw_rel in band_inside_relations
    any_band_crosses = any(
        relation in {
            "indicative_band_crosses_reference_boundary_not_calibrated",
            "indicative_band_touches_reference_boundary_not_calibrated",
        }
        for relation in (di_rel, hw_rel)
    )
    if not point_available:
        screen_status = "not_assessable_missing_geometry_prediction"
        screen_statement = "Não há previsões de DI e H/W suficientes para comparar com a referência."
    elif both_bands_inside:
        screen_status = "point_and_both_indicative_bands_inside_reference_not_calibrated"
        screen_statement = "O ponto previsto e as duas bandas q90 indicativas ficam estritamente dentro da referência geométrica. É um indício favorável, não uma probabilidade nem uma garantia de qualidade; as bandas não são calibradas localmente."
    elif point_inside and (any_band_crosses or (bands_available and not both_bands_inside)):
        screen_status = "point_inside_but_q90_band_crosses_or_exceeds_reference"
        screen_statement = "O ponto previsto fica dentro da referência, mas pelo menos uma banda q90 indicativa cruza, toca ou excede um limite. Não há base calibrada para afirmar que a próxima amostra provavelmente ficará dentro."
    elif point_inside:
        screen_status = "point_inside_reference_band_unavailable"
        screen_statement = "O ponto previsto fica dentro da referência, mas faltam bandas de erro para avaliar sua robustez. Isso não é uma probabilidade de conformidade."
    elif point_class == "boundary":
        screen_status = "point_on_strict_reference_boundary"
        screen_statement = "O ponto previsto toca um limite; a faixa é estrita e o contato não equivale a estar dentro. A comparação não classifica defeitos metalúrgicos."
    elif any_band_crosses:
        screen_status = "point_outside_but_q90_band_intersects_or_touches_reference"
        screen_statement = "O ponto previsto fica fora da referência, embora uma banda q90 indicativa cruze ou toque a faixa. A triagem é inconclusiva e não representa probabilidade de conformidade."
    else:
        screen_status = "point_outside_reference"
        screen_statement = "O ponto previsto fica fora da referência geométrica. A comparação não classifica um defeito metalúrgico."
    return {
        "window_id": ref["id"],
        "window_provenance": ref["provenance"],
        "point_estimate_inside_reference": bool(point_inside),
        "point_reference_class": point_class,
        "normalized_point_violation": float(sum(violations)) if len(violations) == 2 else None,
        "normalized_indicative_band_violation": normalized_band_spill,
        "indicative_screen_status": screen_status,
        "indicative_screen_statement": screen_statement,
        "DI_relation": di_rel,
        "H_over_W_relation": hw_rel,
        "not_a_defect_probability": True,
        "interpretation": (
            "Triagem de descritores geométricos contra uma referência publicada e específica. "
            "Não é probabilidade de conformidade, certificação, nem diagnóstico de LoF, keyhole ou porosidade."
        ),
    }


def _dominates(
    a: dict,
    b: dict,
    objectives: tuple[str, ...],
    directions: dict[str, str],
    *,
    class_key: str,
) -> bool:
    """Dominância com classe booleana exata e resolução só numérica nos demais objetivos."""
    no_worse = True
    strictly_better = False
    for key in objectives:
        av, bv = a[key], b[key]
        direction = directions[key]
        if key == class_key:
            if direction == "max":
                no_worse &= bool(av) >= bool(bv)
                strictly_better |= bool(av) > bool(bv)
            else:
                no_worse &= bool(av) <= bool(bv)
                strictly_better |= bool(av) < bool(bv)
            continue
        av, bv = float(av), float(bv)
        resolution = RANK_NUMERIC_RESOLUTION
        if direction == "min":
            no_worse &= av <= bv + resolution
            strictly_better |= av < bv - resolution
        else:
            no_worse &= av + resolution >= bv
            strictly_better |= av > bv + resolution
    return bool(no_worse and strictly_better)


def pareto_front(
    rows: Iterable[dict],
    *,
    violation_key: str = "normalized_point_violation",
    support_distance_key: str = "max_target_nearest_distance_normalized",
    band_violation_key: str | None = "normalized_indicative_band_violation",
    inside_key: str = "point_estimate_inside_reference",
    eligible_key: str = "rank_eligible",
) -> list[dict]:
    """Marca a fronteira sem pesos usando classe, adequação, Q90 e suporte.

    Menor excesso de banda q90, menor violação pontual e menor distância máxima
    aos rótulos h/DI/HW são preferidos; estar estritamente dentro é um objetivo
    categórico explícito. A alimentação não participa da dominância. As métricas
    não são probabilidades e o envelope de suporte não usa corte de distância.
    """
    items = [dict(row) for row in rows]
    active_candidates = [row for row in items if row.get(eligible_key, False)]
    use_band = bool(
        band_violation_key
        and active_candidates
        and all(_finite(row.get(band_violation_key)) is not None for row in active_candidates)
    )
    objectives: tuple[str, ...] = (inside_key, violation_key, support_distance_key)
    directions = {inside_key: "max", violation_key: "min", support_distance_key: "min"}
    if use_band:
        assert band_violation_key is not None
        objectives = (inside_key, band_violation_key, violation_key, support_distance_key)
        directions[band_violation_key] = "min"
    active = [
        row for row in active_candidates
        if isinstance(row.get(inside_key), bool)
        and all(_finite(row.get(key)) is not None for key in objectives if key != inside_key)
    ]
    for item in items:
        item["pareto_nondominated"] = False
        item["pareto_status"] = "excluded_from_frontier"
    for i, candidate in enumerate(active):
        dominated = any(
            _dominates(other, candidate, objectives, directions, class_key=inside_key)
            for j, other in enumerate(active) if i != j
        )
        candidate["pareto_nondominated"] = not dominated
        candidate["pareto_status"] = "non_dominated" if not dominated else "dominated"
    return items
