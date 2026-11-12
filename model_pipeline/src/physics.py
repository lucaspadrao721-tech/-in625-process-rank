"""Indicadores nominais de processo para DED-LB; não são diagnósticos de defeito."""
from __future__ import annotations

import math


def _positive_finite(name: str, value: float) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} deve ser positivo e finito.")
    return number


def process_indicators(
    power_W: float,
    feed_g_min: float,
    speed_mm_min: float,
    beam_diameter_mm: float | None = None,
    hatch_spacing_mm: float | None = None,
    layer_thickness_mm: float | None = None,
) -> dict:
    """Calcula indicadores nominais com unidades consistentes.

    E_L = P/(v/60) [J/mm]; m_L = feed/v [g/mm]; E_F = P/(feed/60) [J/g].
    Se hatch e espessura efetiva de camada t forem informados, calcula
    ED = P/(hatch*(v/60)*t) [J/mm³], definição do estudo-fonte.
    O incremento de posicionamento Δz é outro parâmetro e não substitui t.
    """
    power = _positive_finite("Potência P (W)", power_W)
    feed = _positive_finite("Taxa mássica de pó (g/min)", feed_g_min)
    speed_min = _positive_finite("Velocidade v (mm/min)", speed_mm_min)
    speed_s = speed_min / 60.0
    result = {
        "linear_energy_incident_J_mm": power / speed_s,
        "powder_feed_per_length_g_mm": feed / speed_min,
        "incident_energy_per_feed_mass_J_g": power / (feed / 60.0),
        "speed_mm_s": speed_s,
        "status": "nominal_indicators_only",
        "interpretation": {
            "linear_energy_incident_J_mm": "Potência nominal dividida pela velocidade; não inclui absorptividade nem perdas.",
            "powder_feed_per_length_g_mm": "Pó alimentado nominal por comprimento; não é massa capturada ou depositada.",
            "incident_energy_per_feed_mass_J_g": "Energia nominal do laser por massa alimentada; não é energia absorvida nem produtividade depositada.",
        },
    }

    if (hatch_spacing_mm is None) != (layer_thickness_mm is None):
        raise ValueError("Para calcular ED volumétrica, informe hatch spacing e espessura de camada t juntos.")
    if hatch_spacing_mm is not None and layer_thickness_mm is not None:
        hatch = _positive_finite("Hatch spacing (mm)", hatch_spacing_mm)
        thickness = _positive_finite("Espessura efetiva de camada t (mm)", layer_thickness_mm)
        result["volumetric_energy_density_J_mm3"] = power / (speed_s * hatch * thickness)
        result["volumetric_energy_density_status"] = "nominal_formula_using_user_supplied_layer_thickness"
        result["volumetric_energy_density_note"] = (
            "ED nominal P/(hatch·(v/60)·t), conforme a Eq. 4 do estudo de referência. "
            "t é espessura efetiva/média de camada, não o incremento de posicionamento Δz. "
            "O valor depende da espessura informada e não é energia absorvida nem limiar universal de defeito."
        )
    else:
        result["volumetric_energy_density_J_mm3"] = None
        result["volumetric_energy_density_status"] = "not_computed_missing_hatch_or_layer_thickness"
        result["volumetric_energy_density_note"] = "Não calculado: hatch spacing e espessura efetiva de camada t não foram ambos informados."

    if beam_diameter_mm is not None:
        diameter = _positive_finite("Diâmetro nominal do feixe (mm)", beam_diameter_mm)
        result["nominal_power_density_W_mm2"] = power / (math.pi * (diameter / 2.0) ** 2)
        result["nominal_power_density_note"] = (
            "Potência nominal dividida pela área circular nominal do feixe; não representa perfil óptico, "
            "potência absorvida ou limiar de keyhole. Informe a convenção do diâmetro antes de comparar estudos."
        )
    else:
        result["nominal_power_density_W_mm2"] = None
        result["nominal_power_density_note"] = "Não calculado: diâmetro/perfil/foco do feixe não informado."
    return result


def surface_overlap_indicator(width_um: float, spacing_um: float) -> dict:
    """Indicador geométrico superficial; não mede remelting nem falta de fusão."""
    width = _positive_finite("Largura superficial W (µm)", width_um)
    spacing = float(spacing_um)
    if not math.isfinite(spacing) or spacing < 0:
        raise ValueError("Espaçamento entre centros (µm) deve ser finito e não negativo.")
    return {
        "width_um": width,
        "center_spacing_um": spacing,
        "surface_overlap_pct": 100.0 * (1.0 - spacing / width),
        "geometric_gap_um": max(0.0, spacing - width),
        "status": "surface_geometry_only",
        "interpretation": (
            "Compara largura superficial idealizada e distância entre centros. Sobreposição positiva não prova "
            "fusão metalúrgica; ausência de lacuna superficial não exclui LoF entre trilhas."
        ),
    }
