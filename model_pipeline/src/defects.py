"""Contrato de evidência para defeitos; mantém casos de blocos separados do treino."""
from __future__ import annotations

import math

SOURCE_STUDY_BLOCK_CASES = (
    {
        "case_id": "P415",
        "power_W": 400.0,
        "feed_g_min": 5.2,
        "speed_mm_min": 1500.0,
        "single_bead_width_mm": 0.66,
        "hatch_spacing_mm": 0.46,
        "overlap_pct": 30.0,
        "layer_increment_mm": 0.60,
        "reported_VED_J_mm3": 60.0,
        "average_layer_thickness_um": 583.0,
        "layer_thickness_plus_minus_um": 22.0,
        "combined_porosity_and_LoF_vol_pct": 2.40,
        "observed_modes": ["lack_of_fusion", "porosity"],
    },
    {
        "case_id": "P515",
        "power_W": 500.0,
        "feed_g_min": 5.2,
        "speed_mm_min": 1500.0,
        "single_bead_width_mm": 0.80,
        "hatch_spacing_mm": 0.56,
        "overlap_pct": 30.0,
        "layer_increment_mm": 0.60,
        "reported_VED_J_mm3": 63.0,
        "average_layer_thickness_um": 570.0,
        "layer_thickness_plus_minus_um": 16.0,
        "combined_porosity_and_LoF_vol_pct": 0.20,
        "observed_modes": ["lack_of_fusion", "porosity"],
    },
    {
        "case_id": "P420",
        "power_W": 400.0,
        "feed_g_min": 5.2,
        "speed_mm_min": 2000.0,
        "single_bead_width_mm": 0.63,
        "hatch_spacing_mm": 0.44,
        "overlap_pct": 30.0,
        "layer_increment_mm": 0.55,
        "reported_VED_J_mm3": 53.0,
        "average_layer_thickness_um": 518.0,
        "layer_thickness_plus_minus_um": 8.0,
        "combined_porosity_and_LoF_vol_pct": 2.42,
        "observed_modes": ["lack_of_fusion", "porosity"],
    },
    {
        "case_id": "P520",
        "power_W": 500.0,
        "feed_g_min": 5.2,
        "speed_mm_min": 2000.0,
        "single_bead_width_mm": 0.75,
        "hatch_spacing_mm": 0.53,
        "overlap_pct": 30.0,
        "layer_increment_mm": 0.55,
        "reported_VED_J_mm3": 58.0,
        "average_layer_thickness_um": 488.0,
        "layer_thickness_plus_minus_um": 14.0,
        "combined_porosity_and_LoF_vol_pct": 0.16,
        "observed_modes": ["scattered_porosity", "no_LoF_observed_in_reported_cross_sections"],
    },
)
SOURCE_STUDY_BLOCK_URL = "https://link.springer.com/article/10.1007/s11665-026-14887-8/tables/4"
SOURCE_STUDY_THESIS_CITATION = (
    "Bon, Douglas Geovanni. Caracterização microestrutural e mecânica de peças de Inconel 625 "
    "produzidas por meio de manufatura aditiva usando deposição por energia direcionada. "
    "Tese de doutorado, EESC-USP, versão corrigida, 2025, pp. 93–97."
)
SOURCE_STUDY_POWER_GATES = (
    {
        "power_W": 300.0,
        "gate_id": "source_study_300W_dilution",
        "reason": "O artigo relata que os cordões a 300 W não atingiram a diluição-alvo e foram descartados da seleção.",
    },
    {
        "power_W": 600.0,
        "gate_id": "source_study_600W_oxidation",
        "reason": "O artigo relata marcas de oxidação a 600 W independentemente da alimentação de pó e velocidade; essas condições foram excluídas da análise subsequente.",
    },
)


def source_study_power_gate(
    power_W: float,
    *,
    context_active: bool = False,
    context_id: str | None = None,
    power_gates: tuple[dict, ...] | list[dict] | None = None,
) -> dict:
    """Aplica gates somente quando o chamador validou o contexto da base.

    Sem contexto explicitamente ativo, nenhuma potência é excluída. A decisão
    de ativação por fingerprint pertence ao analisador; esta função não infere
    contexto científico a partir do valor de potência.
    """
    power = float(power_W)
    configured_gates = power_gates if context_active and power_gates is not None else (
        SOURCE_STUDY_POWER_GATES if context_active else ()
    )
    for gate in configured_gates:
        if math.isclose(power, gate["power_W"], rel_tol=0, abs_tol=1e-8):
            return {
                "excluded_from_source_study_ranking": True,
                **gate,
                "context_active": True,
                "context_id": context_id,
                "source_url": SOURCE_STUDY_BLOCK_URL.replace("/tables/4", ""),
                "probability_of_defect": None,
                "scope": "Seleção conservadora condicionada ao mesmo contexto IN625 DED-LB do artigo; não é um limite universal nem se transfere automaticamente a outra máquina/processo.",
            }
    return {
        "excluded_from_source_study_ranking": False,
        "power_W": power,
        "gate_id": None,
        "reason": (
            "Contexto do estudo-fonte não validado para esta base; gates de potência desativados."
            if not context_active else
            "Nenhum gate de potência do estudo-fonte registrado para este nível; isso não indica ausência de defeito."
        ),
        "context_active": bool(context_active),
        "context_id": context_id if context_active else None,
        "source_url": SOURCE_STUDY_BLOCK_URL.replace("/tables/4", ""),
        "probability_of_defect": None,
        "scope": "Não é uma conclusão universal; aplicam-se os limites de suporte e domínio do modelo.",
    }


def source_study_block_context(
    power_W: float,
    feed_g_min: float,
    speed_mm_min: float,
    *,
    overlap_pct: float | None = None,
    hatch_spacing_mm: float | None = None,
    layer_increment_mm: float | None = None,
) -> dict:
    """Anexa contexto histórico de blocos sem transferir rótulos para a trilha.

    ``overlap_pct`` deve ser a sobreposição efetiva correspondente ao hatch e à
    largura da trilha que se deseja comparar, não somente a sobreposição
    nominal de construção. A equivalência percentual usa tolerância numérica.
    """
    p, feed, speed = float(power_W), float(feed_g_min), float(speed_mm_min)
    matching = []
    for source_case in SOURCE_STUDY_BLOCK_CASES:
        if not (math.isclose(p, source_case["power_W"]) and math.isclose(speed, source_case["speed_mm_min"])):
            continue
        case = dict(source_case)
        case["feed_delta_g_min"] = feed - source_case["feed_g_min"]
        case["same_feed_rate"] = math.isclose(feed, source_case["feed_g_min"], abs_tol=1e-8)
        case["same_overlap"] = overlap_pct is not None and math.isclose(
            float(overlap_pct), source_case["overlap_pct"], rel_tol=0, abs_tol=1e-6
        )
        case["same_hatch_spacing"] = hatch_spacing_mm is not None and math.isclose(float(hatch_spacing_mm), source_case["hatch_spacing_mm"], abs_tol=0.01)
        case["same_layer_increment"] = layer_increment_mm is not None and math.isclose(float(layer_increment_mm), source_case["layer_increment_mm"], abs_tol=0.005)
        case["exact_recorded_process_match"] = bool(
            case["same_feed_rate"] and case["same_overlap"] and case["same_hatch_spacing"] and case["same_layer_increment"]
        )
        matching.append(case)

    exact_matches = [item for item in matching if item["exact_recorded_process_match"]]
    exact_with_lof = [
        item for item in matching
        if item["exact_recorded_process_match"] and "lack_of_fusion" in item["observed_modes"]
    ]
    if exact_with_lof:
        status = "same_source_block_parameters_with_reported_LoF"
    elif exact_matches:
        status = "same_source_block_parameters_no_LoF_observed_in_reported_sections"
    elif matching:
        status = "same_power_speed_literature_context_not_transferable"
    else:
        status = "no_source_block_with_same_power_and_speed"
    return {
        "status": status,
        "source_url": SOURCE_STUDY_BLOCK_URL,
        "corroborating_thesis_citation": SOURCE_STUDY_THESIS_CITATION,
        "corroborating_thesis_pages": "93–97 impressas; Anexo 1, pp. 181–182",
        "source_equipment_context": {
            "machine": "BeAM Modulo 250",
            "laser": "Nd:YAG, diâmetro nominal 0,8 mm no foco de deposição",
            "single_bead_substrate": "AISI 1020 steel",
            "transfer_warning": "Correspondência de números de processo não assegura equivalência de óptica, bocal, pó, estratégia de deposição ou condição térmica do usuário.",
        },
        "matching_power_speed_cases": matching,
        "exact_source_block_case_ids": [item["case_id"] for item in exact_matches],
        "exact_source_block_LoF_case_ids": [item["case_id"] for item in exact_with_lof],
        "is_model_prediction": False,
        "is_probability": False,
        "interpretation": (
            "Artigo reporta resultados observados em blocos multipista, com alimentação 5,2 g/min, hatch e incremento Z próprios. "
            "Casos com diferença de qualquer entrada são contexto, não rótulos transferidos nem probabilidades para a condição avaliada."
        ),
    }


def assess_defect_modes(*, labels_available: bool = False, multipass_data_available: bool = False) -> dict:
    """Retorna o que pode ser avaliado sem inventar probabilidade."""
    if labels_available:
        status = "labels_available_but_model_not_calibrated"
        generic_reason = (
            "Rótulos presentes não calibram probabilidades por si sós. Verifique protocolo, representatividade, "
            "prevalência e validação independente antes de estimar risco."
        )
    else:
        status = "not_evaluable"
        generic_reason = (
            "A planilha de trilhas únicas não contém rótulos de defeito observados por amostra, método de inspeção "
            "ou prevalência; não há base para treinar/calibrar uma probabilidade de defeito."
        )
    lateral_reason = (
        "LoF lateral/intertrilha exige espaçamento e sequência de passes, geometria de zona fundida/remelting e inspeção "
        "de amostras multipista. Uma razão entre hatch e largura superficial não basta."
        if not multipass_data_available else generic_reason
    )
    return {
        "probability_of_defect": None,
        "warning": "Nenhum indicador de energia ou geometria deste pacote representa probabilidade de defeito.",
        "modes": {
            "lateral_intertrack_lack_of_fusion": {
                "status": "not_evaluable" if not multipass_data_available or not labels_available else status,
                "probability": None,
                "reason": lateral_reason,
                "minimum_evidence": ["espacamento e ordem de passes", "remelting/zona fundida entre trilhas", "inspeção de amostras multipista", "rótulos por amostra com método/resolução"],
            },
            "substrate_lack_of_fusion": {
                "status": status,
                "probability": None,
                "reason": generic_reason + " DI baixa pode motivar inspeção, mas não prova falta de ligação; DI=0 não é rótulo de LoF.",
                "minimum_evidence": ["seção da interface", "protocolo metalográfico", "rótulo por amostra", "validação independente"],
            },
            "keyhole_porosity": {
                "status": status,
                "probability": None,
                "reason": generic_reason + " P/v, H/W e altura não identificam cavidade keyhole ou porosidade.",
                "minimum_evidence": ["diâmetro/perfil/foco/absorção do feixe", "monitoramento da poça", "rótulos por inspeção", "validação e calibração independentes"],
            },
            "gas_porosity": {
                "status": status,
                "probability": None,
                "reason": generic_reason + " Geometria superficial não mede porosidade volumétrica.",
                "minimum_evidence": ["CT ou seções com protocolo", "rótulos separando gás, keyhole e LoF", "lote e caracterização do pó (morfologia/porosidade interna)", "validação independente"],
            },
            "solidification_cracking": {
                "status": status,
                "probability": None,
                "reason": generic_reason + " A tabela não registra trincas ou condições termomecânicas suficientes.",
                "minimum_evidence": ["inspeção metalográfica", "rótulos por amostra", "histórico térmico/composição", "validação independente"],
            },
        },
    }
