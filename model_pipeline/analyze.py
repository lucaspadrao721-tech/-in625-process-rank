"""Estima uma condição DED-LB ou gera triagem/ranking da grade experimental."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.data import INPUTS, dataframe_fingerprint, load_dataset
from src.defects import assess_defect_modes, source_study_power_gate
from src.decision import RANK_NUMERIC_RESOLUTION, SOURCE_STUDY_WINDOW, geometry_reference_screen, pareto_front
from src.geometry import dilution_from_geometry, hatch_spacing
from src.models import load_bundle, predict_one
from src.physics import process_indicators, surface_overlap_indicator


def _source_context(power_W: float, *, context_active: bool) -> str:
    if not context_active:
        return ""
    notes = []
    if np.isclose(power_W, 300.0):
        notes.append(
            "O estudo-fonte relata que 300 W não atingiu a diluição-alvo e a planilha não tem rótulos h/DI nessa potência; "
            "isso é observação daquele estudo, não classificação de defeito desta previsão."
        )
    if np.isclose(power_W, 600.0):
        notes.append(
            "O estudo-fonte relata marcas de oxidação em amostras a 600 W; isso não é um rótulo por condição nem uma previsão do modelo."
        )
    return " ".join(notes) if notes else ""


def _validated_source_context(path: str | Path, data: pd.DataFrame) -> dict:
    """Ativa gates apenas se o fingerprint das medições coincidir com a config."""
    config_path = Path(path)
    if not config_path.is_file():
        return {
            "active": False,
            "id": "",
            "power_gates": [],
            "dataframe_fingerprint": dataframe_fingerprint(data),
            "configured_fingerprint": None,
        }
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"Configuração de contexto inválida: {config_path}")
    actual_fingerprint = dataframe_fingerprint(data)
    configured_fingerprint = config.get("dataframe_fingerprint")
    active = bool(config.get("active") is True and configured_fingerprint == actual_fingerprint)
    gates = config.get("power_gates", []) if active else []
    if not isinstance(gates, list):
        raise ValueError(f"power_gates deve ser uma lista em {config_path}")
    return {
        "active": active,
        "id": str(config.get("id", "")),
        "power_gates": gates,
        "dataframe_fingerprint": actual_fingerprint,
        "configured_fingerprint": configured_fingerprint,
    }


def _actual_row(data: pd.DataFrame, candidate: dict) -> dict | None:
    match = np.ones(len(data), dtype=bool)
    for key in INPUTS:
        match &= np.isclose(data[key].to_numpy(dtype=float), float(candidate[key]), rtol=0, atol=1e-8)
    hits = data.loc[match]
    if hits.empty:
        return None
    result = {"record_ids": [int(value) for value in hits["record_id"]]}
    for target in ("H_um", "W_um", "h_um", "DI_pct", "HW"):
        values = pd.to_numeric(hits[target], errors="coerce").dropna()
        result[target] = {
            "n": int(len(values)),
            "mean": float(values.mean()) if len(values) else None,
            "std": float(values.std(ddof=1)) if len(values) > 1 else None,
            "min": float(values.min()) if len(values) else None,
            "max": float(values.max()) if len(values) else None,
        }
    return result


def _load_candidate_csv(path: str | Path) -> list[tuple[str, dict]]:
    """Carrega candidatos com Power_W, Feed_g_min e Speed_mm_min; ID é opcional."""
    table = pd.read_csv(path)
    missing = [key for key in INPUTS if key not in table.columns]
    if missing:
        raise ValueError(f"CSV de candidatos sem colunas obrigatórias: {', '.join(missing)}")
    if table.empty:
        raise ValueError("CSV de candidatos sem linhas de dados.")

    output = []
    seen_ids = set()
    for index, row in table.iterrows():
        candidate = {}
        for key in INPUTS:
            value = pd.to_numeric(row[key], errors="coerce")
            if pd.isna(value) or not np.isfinite(float(value)) or float(value) <= 0:
                raise ValueError(f"Linha {index + 2}: {key} deve ser positivo e finito.")
            candidate[key] = float(value)
        raw_id = row.get("candidate_id")
        candidate_id = str(raw_id).strip() if pd.notna(raw_id) else f"C{index + 1:03d}"
        if not candidate_id:
            candidate_id = f"C{index + 1:03d}"
        if candidate_id in seen_ids:
            raise ValueError(f"candidate_id duplicado no CSV: {candidate_id}")
        seen_ids.add(candidate_id)
        output.append((candidate_id, candidate))
    return output


def assess_candidate(
    candidate: dict,
    *,
    bundle: dict,
    data: pd.DataFrame,
    overlap_pct: float = 30.0,
    hatch_spacing_mm: float | None = None,
    layer_increment_mm: float | None = None,
    layer_thickness_mm: float | None = None,
    use_reference_window: bool = True,
    candidate_id: str = "C001",
    source_context: dict | None = None,
) -> dict:
    """Monta um registro com valores previstos e origem/limites de cada resultado."""
    if not np.isfinite(overlap_pct) or not 0 <= overlap_pct < 100:
        raise ValueError("overlap_pct deve estar entre 0% e menos de 100%.")
    for name, value in (
        ("hatch_spacing_mm", hatch_spacing_mm),
        ("layer_increment_mm", layer_increment_mm),
        ("layer_thickness_mm", layer_thickness_mm),
    ):
        if value is not None and (not np.isfinite(value) or value <= 0):
            raise ValueError(f"{name} deve ser positivo e finito.")
    p = float(candidate["Power_W"])
    f = float(candidate["Feed_g_min"])
    v = float(candidate["Speed_mm_min"])
    prediction = predict_one(bundle, p, f, v)
    context = source_context or {"active": False, "id": "", "power_gates": []}
    source_power_gate = source_study_power_gate(
        p,
        context_active=bool(context.get("active", False)),
        context_id=context.get("id"),
        power_gates=context.get("power_gates", []),
    )

    h_value = prediction.get("h_um", {}).get("prediction")
    H_value = prediction.get("H_um", {}).get("prediction")
    W_value = prediction.get("W_um", {}).get("prediction")
    hw_model = prediction.get("HW", {}).get("prediction")
    di_model = prediction.get("DI_pct", {}).get("prediction")
    hw_from_H_W = H_value / W_value if H_value is not None and W_value else None
    di_from_h_H = dilution_from_geometry(H_value, h_value) if H_value is not None and h_value is not None and H_value > 0 and h_value >= 0 else None

    if W_value is not None:
        if hatch_spacing_mm is None:
            spacing = hatch_spacing(W_value, overlap_pct)
            hatch_used_mm = spacing / 1000.0
            spacing_source = "derived_from_predicted_W_and_overlap"
        else:
            hatch_used_mm = float(hatch_spacing_mm)
            spacing = hatch_used_mm * 1000.0
            spacing_source = "user_supplied_hatch_spacing"
        surface_geometry = surface_overlap_indicator(W_value, spacing)
        actual_overlap_pct = surface_geometry["surface_overlap_pct"]
    else:
        spacing = None
        hatch_used_mm = None
        spacing_source = "unavailable_without_W_prediction"
        surface_geometry = None
        actual_overlap_pct = None

    ed_hatch = hatch_used_mm if layer_thickness_mm is not None else None
    ed_thickness = layer_thickness_mm if hatch_used_mm is not None else None
    physics = process_indicators(
        p, f, v,
        hatch_spacing_mm=ed_hatch,
        layer_thickness_mm=ed_thickness,
    )
    def band(target: str) -> dict | None:
        item = prediction.get(target)
        if not item:
            return None
        return {"low": item["indicative_low"], "high": item["indicative_high"]}

    window_result = geometry_reference_screen(
        di_pct=di_model,
        h_over_w=hw_model,
        di_error_band=band("DI_pct"),
        hw_error_band=band("HW"),
    ) if use_reference_window else {
        "window_id": "none",
        "window_provenance": "Nenhuma referência geométrica selecionada.",
        "point_estimate_inside_reference": None,
        "normalized_point_violation": None,
        "DI_relation": "not_evaluated",
        "H_over_W_relation": "not_evaluated",
        "normalized_indicative_band_violation": None,
        "indicative_screen_status": "not_evaluated_no_reference_window",
        "indicative_screen_statement": "Nenhuma janela geométrica foi selecionada; não há triagem de compatibilidade.",
        "not_a_defect_probability": True,
        "interpretation": "Sem limites de aplicação/especificação, não há evento geométrico de conformidade a avaliar.",
    }

    support = prediction["support_summary"]
    target_support = {
        target: prediction.get(target, {}).get("support", {})
        for target in ("h_um", "DI_pct", "HW")
    }
    target_distances = [
        item.get("nearest_distance_normalized") for item in target_support.values()
    ]
    complete_target_distances = all(value is not None and np.isfinite(value) for value in target_distances)
    max_target_distance = float(max(target_distances)) if complete_target_distances else None
    all_target_envelopes = all(
        item.get("within_target_joint_envelope") is True for item in target_support.values()
    )
    rank_eligible = bool(
        use_reference_window
        and support["within_input_marginal_ranges"]
        and all_target_envelopes
        and complete_target_distances
        and window_result["normalized_point_violation"] is not None
        and window_result.get("normalized_indicative_band_violation") is not None
        and not source_power_gate["excluded_from_source_study_ranking"]
    )
    if source_power_gate["excluded_from_source_study_ranking"]:
        support_label = "excluded_by_source_study_process_observation"
    elif not support["within_input_marginal_ranges"]:
        support_label = "outside_input_range_extrapolation"
    elif not all_target_envelopes:
        missing_or_outside = [
            target for target, item in target_support.items()
            if item.get("within_target_joint_envelope") is not True
        ]
        support_label = "outside_joint_target_support:" + ",".join(missing_or_outside)
    elif support["exact_observed_input_combination"]:
        support_label = "exact_input_combination_with_target_envelope_support"
    else:
        support_label = "unmeasured_combination_inside_target_envelopes"

    exclusion_reasons: list[str] = []
    if not use_reference_window:
        exclusion_reasons.append("Sem referência geométrica")
    if not support["within_input_marginal_ranges"]:
        exclusion_reasons.append("Fora das margens de entrada")
    target_labels = {"h_um": "h", "DI_pct": "DI", "HW": "H/W"}
    for target, item in target_support.items():
        if item.get("within_target_joint_envelope") is not True:
            exclusion_reasons.append(f"Fora do envelope rotulado {target_labels[target]}")
    if window_result["normalized_point_violation"] is None or window_result.get("normalized_indicative_band_violation") is None:
        exclusion_reasons.append("Previsão geométrica incompleta")
    if source_power_gate["excluded_from_source_study_ranking"]:
        exclusion_reasons.append(f"Restrição do contexto: {p:g} W")
    rank_exclusion_reason = "; ".join(exclusion_reasons) if exclusion_reasons else None

    actual = _actual_row(data, candidate)
    mode_assessment = assess_defect_modes(labels_available=False, multipass_data_available=False)
    return {
        "candidate_id": candidate_id,
        **{key: float(candidate[key]) for key in INPUTS},
        **physics,
        "overlap_pct_assumed": float(overlap_pct),
        "hatch_spacing_mm_used": hatch_used_mm,
        "hatch_spacing_source": spacing_source,
        "hatch_spacing_um_from_predicted_W": float(spacing) if spacing is not None else None,
        "layer_increment_mm_assumed": float(layer_increment_mm) if layer_increment_mm is not None else None,
        "layer_thickness_mm_assumed_for_ED": float(layer_thickness_mm) if layer_thickness_mm is not None else None,
        "surface_overlap_indicator": surface_geometry,
        "predictions": prediction,
        "H_over_W_from_predicted_H_W": hw_from_H_W,
        "DI_from_predicted_h_H_pct": di_from_h_H,
        "study_reference_screen": window_result,
        "point_estimate_inside_reference": window_result["point_estimate_inside_reference"],
        "point_reference_class": window_result["point_reference_class"],
        "actual_training_measurements": actual,
        "support_label": support_label,
        "nearest_di_label_distance_normalized": target_support["DI_pct"].get("nearest_distance_normalized"),
        "max_target_nearest_distance_normalized": max_target_distance,
        "rank_eligible": rank_eligible,
        "Feed_g_min": f,
        "normalized_point_violation": window_result["normalized_point_violation"],
        "normalized_indicative_band_violation": window_result.get("normalized_indicative_band_violation"),
        "pareto_nondominated": False,
        "pareto_status": "excluded_from_frontier",
        "quality_order": None,
        "rank_tie_count": 1,
        "rank_exclusion_reason": rank_exclusion_reason,
        "rank_exclusion_reasons": exclusion_reasons,
        "source_study_power_gate": source_power_gate,
        "source_study_observation": _source_context(p, context_active=bool(context.get("active", False))),
        "defect_assessment": mode_assessment,
        "probability_of_geometric_conformity": None,
        "probability_of_defect": None,
        "claim_boundary": (
            "Predições de geometria e triagem contra referência do estudo; não é probabilidade calibrada de conformidade "
            "nem previsão de LoF, keyhole, porosidade, trinca ou integridade da peça."
        ),
    }


def _flatten(record: dict) -> dict:
    predictions = record["predictions"]
    flat = {
        "candidate_id": record["candidate_id"],
        **{key: record[key] for key in INPUTS},
        "linear_energy_incident_J_mm": record["linear_energy_incident_J_mm"],
        "powder_feed_per_length_g_mm": record["powder_feed_per_length_g_mm"],
        "incident_energy_per_feed_mass_J_g": record["incident_energy_per_feed_mass_J_g"],
        "volumetric_energy_density_J_mm3": record["volumetric_energy_density_J_mm3"],
        "overlap_pct_assumed": record["overlap_pct_assumed"],
        "hatch_spacing_mm_used": record["hatch_spacing_mm_used"],
        "hatch_spacing_source": record["hatch_spacing_source"],
        "layer_increment_mm_assumed": record["layer_increment_mm_assumed"],
        "layer_thickness_mm_assumed_for_ED": record["layer_thickness_mm_assumed_for_ED"],
        "hatch_spacing_um_from_predicted_W": record["hatch_spacing_um_from_predicted_W"],
        "surface_overlap_pct_indicator": (record["surface_overlap_indicator"] or {}).get("surface_overlap_pct"),
        "geometric_surface_gap_um": (record["surface_overlap_indicator"] or {}).get("geometric_gap_um"),
        "H_um_prediction": predictions.get("H_um", {}).get("prediction"),
        "H_um_error_band_low_indicative": predictions.get("H_um", {}).get("indicative_low"),
        "H_um_error_band_high_indicative": predictions.get("H_um", {}).get("indicative_high"),
        "W_um_prediction": predictions.get("W_um", {}).get("prediction"),
        "W_um_error_band_low_indicative": predictions.get("W_um", {}).get("indicative_low"),
        "W_um_error_band_high_indicative": predictions.get("W_um", {}).get("indicative_high"),
        "h_um_prediction": predictions.get("h_um", {}).get("prediction"),
        "h_um_error_band_low_indicative": predictions.get("h_um", {}).get("indicative_low"),
        "h_um_error_band_high_indicative": predictions.get("h_um", {}).get("indicative_high"),
        "DI_pct_prediction": predictions.get("DI_pct", {}).get("prediction"),
        "DI_pct_error_band_low_indicative": predictions.get("DI_pct", {}).get("indicative_low"),
        "DI_pct_error_band_high_indicative": predictions.get("DI_pct", {}).get("indicative_high"),
        "H_over_W_prediction": predictions.get("HW", {}).get("prediction"),
        "H_over_W_error_band_low_indicative": predictions.get("HW", {}).get("indicative_low"),
        "H_over_W_error_band_high_indicative": predictions.get("HW", {}).get("indicative_high"),
        "H_over_W_from_predicted_H_W": record["H_over_W_from_predicted_H_W"],
        "DI_from_predicted_h_H_pct": record["DI_from_predicted_h_H_pct"],
        "reference_window_id": record["study_reference_screen"]["window_id"],
        "point_estimate_inside_reference": record["study_reference_screen"]["point_estimate_inside_reference"],
        "point_reference_class": record["study_reference_screen"]["point_reference_class"],
        "normalized_point_violation": record["normalized_point_violation"],
        "normalized_indicative_band_violation": record["normalized_indicative_band_violation"],
        "indicative_screen_status": record["study_reference_screen"]["indicative_screen_status"],
        "indicative_screen_statement": record["study_reference_screen"]["indicative_screen_statement"],
        "DI_relation": record["study_reference_screen"]["DI_relation"],
        "H_over_W_relation": record["study_reference_screen"]["H_over_W_relation"],
        "support_label": record["support_label"],
        "nearest_di_label_distance_normalized": record["nearest_di_label_distance_normalized"],
        "max_target_nearest_distance_normalized": record["max_target_nearest_distance_normalized"],
        "rank_eligible": record["rank_eligible"],
        "pareto_nondominated": record["pareto_nondominated"],
        "pareto_status": record["pareto_status"],
        "quality_order": record["quality_order"],
        "rank_tie_count": record["rank_tie_count"],
        "rank_exclusion_reason": record["rank_exclusion_reason"],
        "rank_exclusion_reasons": "; ".join(record["rank_exclusion_reasons"]),
        "source_study_power_gate_excluded": record["source_study_power_gate"]["excluded_from_source_study_ranking"],
        "source_study_power_gate_id": record["source_study_power_gate"]["gate_id"],
        "source_study_power_gate_reason": record["source_study_power_gate"]["reason"],
        "source_study_context_active": record["source_study_power_gate"]["context_active"],
        "source_study_context_id": record["source_study_power_gate"]["context_id"],
        "probability_of_geometric_conformity": None,
        "probability_of_defect": None,
        "defect_status": "not_evaluable",
        "source_study_observation": record["source_study_observation"],
    }
    actual = record["actual_training_measurements"]
    if actual is not None:
        for target, statistics in actual.items():
            if target == "record_ids":
                flat["observed_record_ids"] = ";".join(str(value) for value in statistics)
                continue
            flat[f"observed_{target}"] = statistics["mean"]
            flat[f"observed_{target}_n"] = statistics["n"]
            flat[f"observed_{target}_std"] = statistics["std"]
            flat[f"observed_{target}_min"] = statistics["min"]
            flat[f"observed_{target}_max"] = statistics["max"]
    return flat


def _json_clean(value):
    if isinstance(value, dict):
        return {str(k): _json_clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _normalized_quality_key(row: dict) -> tuple[int, int, int, int]:
    """Chave científica do ranking; IDs servem apenas para apresentação estável."""
    resolution = RANK_NUMERIC_RESOLUTION
    return (
        0 if row["point_estimate_inside_reference"] else 1,
        int(round(float(row["normalized_point_violation"]) / resolution)),
        int(round(float(row["normalized_indicative_band_violation"]) / resolution)),
        int(round(float(row["max_target_nearest_distance_normalized"]) / resolution)),
    )


def _assign_quality_ranks(rows: list[dict]) -> list[dict]:
    """Atribui rank denso compartilhado; ID apenas ordena a apresentação do empate."""
    eligible = [row for row in rows if row.get("rank_eligible")]
    for row in rows:
        if not row.get("rank_eligible"):
            row["quality_order"] = None
            row["rank_tie_count"] = 1
    ordered = sorted(eligible, key=lambda row: (*_normalized_quality_key(row), row["candidate_id"]))
    tie_counts: dict[tuple[int, int, int, int], int] = {}
    for row in ordered:
        key = _normalized_quality_key(row)
        tie_counts[key] = tie_counts.get(key, 0) + 1
    previous_key = None
    dense_rank = 0
    for row in ordered:
        key = _normalized_quality_key(row)
        if key != previous_key:
            dense_rank += 1
            previous_key = key
        row["quality_order"] = dense_rank
        row["rank_tie_count"] = tie_counts[key]
    return ordered


def main() -> None:
    parser = argparse.ArgumentParser(description="Estima geometria e faz triagem Pareto exploratória para IN625 DED-LB.")
    parser.add_argument("--data", default="data/TabelaTotalSingleTracksIN625(1).xlsx", help="Planilha com medições experimentais")
    parser.add_argument("--bundle", default="artifacts/model_bundle.joblib", help="Bundle gerado por train.py")
    parser.add_argument("--context-config", default="config/source_study_context.json", help="Config de gates vinculada ao fingerprint da base")
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--grid", action="store_true", help="Avalia as combinações existentes na planilha")
    input_group.add_argument("--candidate-csv", help="Compara candidatos listados num CSV com Power_W, Feed_g_min e Speed_mm_min; candidate_id opcional")
    parser.add_argument("--power", type=float, help="Potência laser (W) para uma condição")
    parser.add_argument("--feed", type=float, help="Taxa mássica de pó (g/min) para uma condição")
    parser.add_argument("--speed", type=float, help="Velocidade de varredura (mm/min) para uma condição")
    parser.add_argument("--overlap-pct", type=float, default=30.0, help="Sobreposição geométrica assumida; 30%% é referência de um estudo, não regra universal")
    parser.add_argument("--hatch-spacing-mm", type=float, help="Hatch spacing de construção (mm); substitui o calculado a partir de W e overlap")
    parser.add_argument("--layer-increment-mm", type=float, help="Incremento de posicionamento Δz (mm); usado apenas para comparar com os blocos publicados")
    parser.add_argument("--layer-thickness-mm", type=float, help="Espessura efetiva/média de camada t (mm); junto com hatch permite calcular ED nominal")
    parser.add_argument("--window-profile", choices=["source-study-2026", "none"], default="source-study-2026", help="Faixa geométrica local, ou nenhuma faixa")
    parser.add_argument("--out", default="artifacts/candidate_assessment.csv", help="CSV de saída")
    parser.add_argument("--json-out", default="artifacts/candidate_assessment.json", help="JSON detalhado de saída")
    args = parser.parse_args()

    data_path = Path(args.data)
    bundle_path = Path(args.bundle)
    data = load_dataset(data_path)
    bundle = load_bundle(str(bundle_path))
    try:
        source_context = _validated_source_context(args.context_config, data)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(f"Configuração de contexto inválida: {exc}")
    use_window = args.window_profile == "source-study-2026"

    single_values = (args.power, args.feed, args.speed)
    if (args.grid or args.candidate_csv) and any(value is not None for value in single_values):
        parser.error("Use --grid, --candidate-csv ou os três parâmetros de um candidato único, não mais de um modo.")
    if any(value is not None for value in single_values) and not all(value is not None for value in single_values):
        parser.error("Para um candidato único, informe --power, --feed e --speed juntos.")

    if args.grid:
        candidates = data.loc[:, INPUTS].drop_duplicates().reset_index(drop=True).to_dict(orient="records")
        candidate_specs = [(f"C{i:03d}", candidate) for i, candidate in enumerate(candidates, start=1)]
    elif args.candidate_csv:
        try:
            candidate_specs = _load_candidate_csv(args.candidate_csv)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
    elif all(value is not None for value in single_values):
        candidate_specs = [("C001", {"Power_W": args.power, "Feed_g_min": args.feed, "Speed_mm_min": args.speed})]
    else:
        parser.error("Informe --grid, --candidate-csv ou os três argumentos --power, --feed e --speed.")

    records = [
        assess_candidate(candidate, bundle=bundle, data=data, overlap_pct=args.overlap_pct,
                         hatch_spacing_mm=args.hatch_spacing_mm, layer_increment_mm=args.layer_increment_mm,
                         layer_thickness_mm=args.layer_thickness_mm,
                         use_reference_window=use_window, candidate_id=candidate_id,
                         source_context=source_context)
        for candidate_id, candidate in candidate_specs
    ]
    if use_window:
        records = pareto_front(records)
        _assign_quality_ranks(records)

    out_path = Path(args.out)
    json_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([_flatten(row) for row in records]).to_csv(out_path, index=False)

    eligible = [row for row in records if row["rank_eligible"]]
    summary = {
        "n_candidates": len(records),
        "n_rank_eligible": len(eligible),
        "n_point_estimates_inside_reference": sum(bool(row["study_reference_screen"]["point_estimate_inside_reference"]) for row in records),
        "n_rank_eligible_point_inside_reference": sum(bool(row["rank_eligible"] and row["study_reference_screen"]["point_estimate_inside_reference"]) for row in records),
        "n_rank_eligible_point_inside_but_q90_band_not_contained": sum(row["rank_eligible"] and row["study_reference_screen"]["indicative_screen_status"] == "point_inside_but_q90_band_crosses_or_exceeds_reference" for row in records),
        "n_rank_eligible_point_and_both_q90_bands_inside_reference": sum(row["rank_eligible"] and row["study_reference_screen"]["indicative_screen_status"] == "point_and_both_indicative_bands_inside_reference_not_calibrated" for row in records),
        "n_pareto_nondominated": sum(bool(row["pareto_nondominated"]) for row in records),
        "n_source_study_power_gate_exclusions": sum(bool(row["source_study_power_gate"]["excluded_from_source_study_ranking"]) for row in records),
        "n_candidates_within_all_target_joint_envelopes": sum(
            all(row["predictions"].get(target, {}).get("support", {}).get("within_target_joint_envelope") is True
                for target in ("h_um", "DI_pct", "HW"))
            for row in records
        ),
        "defect_probabilities_available": False,
        "window": SOURCE_STUDY_WINDOW if use_window else None,
        "source_context": {
            "active": bool(source_context["active"]),
            "id": str(source_context["id"]),
            "dataframe_fingerprint": source_context["dataframe_fingerprint"],
        },
        "ranking_numeric_resolution": RANK_NUMERIC_RESOLUTION,
        "ranking_numeric_resolution_semantics": "1e-12 em critérios normalizados, somente para igualdade numérica; não é tolerância física nem distância de suporte para elegibilidade.",
        "ranking_rule": "Elegíveis ordenados lexicograficamente: classe dentro da janela estrita antes de fora/contato; menor violação geométrica pontual normalizada; menor excesso das bandas Q90 integrais; menor distância máxima normalizada ao rótulo mais próximo entre h, DI e H/W. Empates numéricos até 1e-12 normalizado compartilham quality_order (rank denso); candidate_id só estabiliza a apresentação. Pareto usa classe, violação pontual, excesso Q90 e distância máxima de suporte; Feed não é objetivo. Envelope conjunto convexo dos rótulos h/DI/HW não usa corte de distância.",
        "interpretation": "Estimativas geométricas de trilhas únicas e triagem contra referência específica; não são probabilidades calibradas nem diagnóstico de defeitos. A evidência multipista não é transferida às trilhas. Gates de potência só se aplicam quando o fingerprint da base coincide com o contexto configurado.",
    }
    payload = _json_clean({"summary": summary, "candidates": records})
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    print(f"Candidatos avaliados: {len(records)}")
    print(f"Elegíveis dentro dos envelopes conjuntos rotulados: {len(eligible)}")
    print(f"Estimativas pontuais dentro da referência geométrica: {summary['n_point_estimates_inside_reference']}")
    print(f"Candidatos elegíveis com ponto dentro, mas banda q90 não contida: {summary['n_rank_eligible_point_inside_but_q90_band_not_contained']}")
    print(f"Candidatos elegíveis com ponto e ambas as bandas q90 dentro: {summary['n_rank_eligible_point_and_both_q90_bands_inside_reference']}")
    print(f"Não dominados na fronteira Pareto: {summary['n_pareto_nondominated']}")
    print(f"Contexto de gates ativo: {source_context['active']} ({source_context['id'] or 'sem contexto'})")
    print(f"Exclusões pelos gates de potência do contexto: {summary['n_source_study_power_gate_exclusions']}")
    print("Probabilidade de defeito: não avaliável (sem rótulos de defeito por amostra).")
    print(f"CSV: {out_path.resolve()}")
    print(f"JSON: {json_path.resolve()}")


if __name__ == "__main__":
    main()
