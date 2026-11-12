"""Fórmulas geométricas de referência; não simulam fluxo térmico nem defeitos."""
from __future__ import annotations

import math
import numpy as np

# Faixas geométricas de um estudo IN625 DED-LB compatível com a planilha.
# Não são critérios universais nem labels de defeito.
REFERENCE_DI_MIN_PCT = 10.0
REFERENCE_DI_MAX_PCT = 30.0
REFERENCE_HW_MIN = 1.0 / 5.0
REFERENCE_HW_MAX = 1.0 / 3.0
REFERENCE_OVERLAP_PCT = 30.0
REFERENCE_SOURCE_URL = "https://link.springer.com/article/10.1007/s11665-026-14887-8"


def _finite(value: float, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} deve ser finito.")
    return number


def hatch_spacing(width_um: float, overlap_pct: float) -> float:
    """Espaçamento entre centros: s = W × (1 - overlap), com W superficial."""
    width = _finite(width_um, "Largura W")
    overlap = _finite(overlap_pct, "Sobreposição")
    if width <= 0:
        raise ValueError("A largura W deve ser positiva.")
    if not 0.0 <= overlap < 100.0:
        raise ValueError("A sobreposição deve estar entre 0% e menos de 100%.")
    return float(width * (1.0 - overlap / 100.0))


def dilution_from_geometry(height_um: float, penetration_um: float) -> float:
    """DI = 100 h/(h+H); geométrica segundo a convenção do estudo de referência."""
    height = _finite(height_um, "Altura H")
    penetration = _finite(penetration_um, "Penetração h")
    if height <= 0 or penetration < 0:
        raise ValueError("H deve ser positivo e a penetração h não pode ser negativa.")
    return float(100.0 * penetration / (penetration + height))


def hw_ratio(height_um: float, width_um: float) -> float:
    height = _finite(height_um, "Altura H")
    width = _finite(width_um, "Largura W")
    if height <= 0 or width <= 0:
        raise ValueError("H e W devem ser positivos.")
    return float(height / width)


def parabolic_track_envelope(height_um: float, width_um: float, spacing_um: float,
                             n_tracks: int = 3, points: int = 700) -> dict:
    """Envelope superficial ilustrativo de parábolas; não calcula remelting/fusão."""
    height = _finite(height_um, "Altura H")
    width = _finite(width_um, "Largura W")
    spacing = _finite(spacing_um, "Espaçamento")
    if height <= 0 or width <= 0 or spacing < 0:
        raise ValueError("Altura/largura devem ser positivas e o espaçamento não negativo.")
    if n_tracks < 2 or points < 10:
        raise ValueError("Use pelo menos dois cordões e dez pontos.")
    centers = (np.arange(n_tracks) - (n_tracks - 1) / 2.0) * spacing
    x = np.linspace(centers[0] - width / 2.0, centers[-1] + width / 2.0, points)
    profiles = []
    for center in centers:
        u = 2.0 * (x - center) / width
        z = np.where(np.abs(u) <= 1.0, height * (1.0 - u**2), 0.0)
        profiles.append(z)
    profiles_array = np.asarray(profiles)
    envelope = profiles_array.max(axis=0)
    valley = height * max(0.0, 1.0 - (spacing / width) ** 2) if spacing <= width else 0.0
    gap = max(0.0, spacing - width)
    return {
        "x_um": x,
        "profiles_um": profiles_array,
        "envelope_um": envelope,
        "centers_um": centers,
        "valley_height_um": float(valley),
        "valley_fraction_of_H": float(valley / height),
        "geometric_gap_um": float(gap),
        "status": "surface_geometry_only",
        "limitations": "Não calcula zona fundida, penetração, remelting, ligação metalúrgica, LoF ou porosidade.",
    }


def audit_reference_window(di_pct: float, hw: float) -> dict:
    """Compara descritores com limites locais sem inferir modo de defeito."""
    di = _finite(di_pct, "DI")
    ratio = _finite(hw, "H/W")
    di_inside = REFERENCE_DI_MIN_PCT < di < REFERENCE_DI_MAX_PCT
    hw_inside = REFERENCE_HW_MIN < ratio < REFERENCE_HW_MAX
    findings = []
    findings.append(
        "DI está dentro da faixa geométrica do estudo de referência."
        if di_inside else "DI está fora da faixa geométrica do estudo de referência."
    )
    findings.append(
        "H/W está dentro da faixa geométrica do estudo de referência."
        if hw_inside else "H/W está fora da faixa geométrica do estudo de referência."
    )
    findings.append("Esta comparação não identifica falta de fusão, keyhole, porosidade ou integridade de ligação.")
    return {
        "di_in_reference": bool(di_inside),
        "hw_in_reference": bool(hw_inside),
        "findings": findings,
        "source_url": REFERENCE_SOURCE_URL,
        "window_scope": "Somente a faixa geométrica relatada pelo estudo de referência; não é universal.",
        "defect_probability": None,
    }
