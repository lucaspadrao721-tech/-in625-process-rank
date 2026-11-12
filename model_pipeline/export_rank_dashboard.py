"""Exporta os artefatos IN625 para o payload compacto e sem bibliografia da interface.

Execute na raiz de model_pipeline: python export_rank_dashboard.py
O ranking e os indicadores permanecem os calculados pelo pipeline Python; este
arquivo somente valida e serializa os campos necessários ao site.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
ARTIFACTS = BASE / "artifacts"
OUTPUT = PROJECT / "public" / "data" / "ranking.json"
TARGETS = ("H_um", "W_um", "h_um", "HW", "DI_pct")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Artefato obrigatório não encontrado: {path}")
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"Formato JSON inválido em {path}")
    return value


def finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def safe_int(value: Any) -> int | None:
    parsed = finite(value)
    return int(parsed) if parsed is not None else None


def target_measurement(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "n": safe_int(value.get("n")) or 0,
        "mean": finite(value.get("mean")),
        "std": finite(value.get("std")),
        "min": finite(value.get("min")),
        "max": finite(value.get("max")),
    }


def support_payload(value: Any) -> dict[str, Any]:
    value = value if isinstance(value, dict) else {}
    raw_status = str(value.get("status", "unknown"))
    status = {
        "exact_condition_has_label": "medicao_rotulada",
        "inside_target_margins_unlabeled_condition": "sem_rotulo_dentro_das_margens",
        "inside_target_joint_envelope_unlabeled": "sem_rotulo_dentro_do_envelope",
        "outside_target_marginal_range": "fora_das_margens_de_suporte",
        "outside_target_joint_envelope": "fora_do_envelope_rotulado",
    }.get(raw_status, "suporte_nao_identificado")
    within_joint = value.get("within_target_joint_envelope")
    return {
        "status": status,
        "withinTargetMarginalRanges": bool(value.get("within_target_marginal_ranges", False)),
        "withinTargetJointEnvelope": None if within_joint is None else bool(within_joint),
        "exactConditionHasLabel": bool(value.get("exact_condition_has_label", False)),
        "nearestDistanceNormalized": finite(value.get("nearest_distance_normalized")),
    }


def prediction_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "value": finite(value.get("prediction")),
        "low": finite(value.get("indicative_low")),
        "high": finite(value.get("indicative_high")),
        "q90AbsError": finite(value.get("cv_q90_abs_error")),
        "nTrainingLabels": safe_int(value.get("n_training_labels")),
        "support": support_payload(value.get("support")),
    }


def candidate_payload(row: dict[str, Any]) -> dict[str, Any]:
    predictions = row.get("predictions") or {}
    measurements = row.get("actual_training_measurements") or {}
    screen = row.get("study_reference_screen") or {}
    rank_eligible = bool(row.get("rank_eligible", False))
    reasons = row.get("rank_exclusion_reasons") or []
    if not isinstance(reasons, list):
        reasons = []

    measured = {
        target: target_measurement(measurements.get(target))
        for target in TARGETS
        if target_measurement(measurements.get(target)) is not None
    }
    return {
        "id": str(row.get("candidate_id", "")),
        "inputs": {
            "powerW": finite(row.get("Power_W")),
            "feedGMin": finite(row.get("Feed_g_min")),
            "speedMmMin": finite(row.get("Speed_mm_min")),
        },
        "rankEligible": rank_eligible,
        "qualityOrder": safe_int(row.get("quality_order")),
        "rankTieCount": safe_int(row.get("rank_tie_count")) or 1,
        "paretoNondominated": bool(row.get("pareto_nondominated", False)),
        "exclusionReasons": [str(reason) for reason in reasons],
        "supportLabel": "elegível ao ranking" if rank_eligible else "não classificada pelas regras atuais",
        "predictions": {
            target: prediction_payload(predictions.get(target))
            for target in TARGETS
            if prediction_payload(predictions.get(target)) is not None
        },
        "measurements": measured,
        "screen": {
            "pointInsideReference": bool(screen.get("point_estimate_inside_reference", False)),
            "pointClass": str(screen.get("point_reference_class", "inside" if screen.get("point_estimate_inside_reference", False) else "outside")),
            "status": str(screen.get("indicative_screen_status", "indisponivel")),
            "pointViolation": finite(screen.get("normalized_point_violation")),
            "bandViolation": finite(screen.get("normalized_indicative_band_violation")),
            "diBandRelation": str(screen.get("DI_relation", "indisponivel")),
            "hwBandRelation": str(screen.get("H_over_W_relation", "indisponivel")),
        },
    }


def count_oof_rows(path: Path) -> dict[str, int]:
    if not path.is_file():
        raise FileNotFoundError(f"Artefato obrigatório não encontrado: {path}")
    counts: dict[str, int] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or "target" not in reader.fieldnames:
            raise ValueError(f"CSV de validação sem a coluna 'target': {path}")
        for row in reader:
            target = str(row.get("target", "")).strip()
            if target:
                counts[target] = counts.get(target, 0) + 1
    return counts


def build_payload() -> dict[str, Any]:
    assessment = load_json(ARTIFACTS / "candidate_assessment.json")
    report = load_json(ARTIFACTS / "training_report.json")
    summary = assessment.get("summary")
    source_candidates = assessment.get("candidates")
    diagnostics = report.get("model_diagnostics")
    if not isinstance(summary, dict) or not isinstance(source_candidates, list):
        raise ValueError("candidate_assessment.json não possui summary/candidates no formato esperado.")
    if not isinstance(diagnostics, dict):
        raise ValueError("training_report.json não possui model_diagnostics no formato esperado.")
    if int(summary.get("n_candidates", -1)) != len(source_candidates):
        raise ValueError("A contagem de candidatos não corresponde ao summary do artefato.")

    oof_rows = count_oof_rows(ARTIFACTS / "validation_predictions.csv")
    models: dict[str, Any] = {}
    for target in TARGETS:
        item = diagnostics.get(target)
        if not isinstance(item, dict):
            raise ValueError(f"Diagnóstico OOF ausente para o alvo {target}.")
        models[target] = {
            "n": safe_int(item.get("n")),
            "mae": finite(item.get("cv_mae")),
            "rmse": finite(item.get("cv_rmse")),
            "r2": finite(item.get("cv_r2")),
            "q90AbsError": finite(item.get("residual_abs_q90")),
            "oofRows": oof_rows.get(target, 0),
        }

    window = summary.get("window") or {}
    limits = window.get("limits") or {}
    context = summary.get("source_context") or {}
    di_width = finite((limits.get("DI_pct") or [None, None])[1])
    di_low = finite((limits.get("DI_pct") or [None, None])[0])
    hw_width = finite((limits.get("H_over_W") or [None, None])[1])
    hw_low = finite((limits.get("H_over_W") or [None, None])[0])
    di_q90 = finite((diagnostics.get("DI_pct") or {}).get("residual_abs_q90"))
    hw_q90 = finite((diagnostics.get("HW") or {}).get("residual_abs_q90"))

    def can_fit_strict_band(low: float | None, high: float | None, q90: float | None) -> bool | None:
        if low is None or high is None or q90 is None:
            return None
        return bool(2.0 * q90 < high - low)

    candidates = [candidate_payload(row) for row in source_candidates]
    candidates.sort(key=lambda row: (
        not row["rankEligible"],
        row["qualityOrder"] if row["qualityOrder"] is not None else 10**9,
        row["id"],
    ))

    return {
        "schemaVersion": 2,
        "context": {
            "active": bool(context.get("active", False)),
            "id": str(context.get("id", "")),
        },
        "bandFeasibility": {
            "hwBandCanFit": can_fit_strict_band(hw_low, hw_width, hw_q90),
            "diBandCanFit": can_fit_strict_band(di_low, di_width, di_q90),
        },
        "summary": {
            "nCandidates": safe_int(summary.get("n_candidates")),
            "nRankEligible": safe_int(summary.get("n_rank_eligible")),
            "nPointInsideReference": safe_int(summary.get("n_point_estimates_inside_reference")),
            "nEligiblePointInsideReference": safe_int(summary.get("n_rank_eligible_point_inside_reference")),
            "nEligiblePointInsideButBandCrosses": safe_int(summary.get("n_rank_eligible_point_inside_but_q90_band_not_contained")),
            "nEligibleWithBothBandsInside": safe_int(summary.get("n_rank_eligible_point_and_both_q90_bands_inside_reference")),
            "nParetoNondominated": safe_int(summary.get("n_pareto_nondominated")),
            "defectProbabilitiesAvailable": bool(summary.get("defect_probabilities_available", False)),
        },
        "window": {
            "diPct": limits.get("DI_pct", [10.0, 30.0]),
            "hw": limits.get("H_over_W", [0.2, 1.0 / 3.0]),
            "description": "Triagem geométrica específica do estudo; não é limite universal.",
        },
        "models": models,
        "candidates": candidates,
        "interpretation": {
            "prediction": "Estimativa do modelo final; não é uma medição.",
            "measurement": "Média de rótulos observados no conjunto de treino; não é validação independente.",
            "q90": "Quantil empírico de erro OOF, indicativo e não calibrado como probabilidade.",
            "defects": "Não há probabilidade estimável nem diagnóstico de defeito neste conjunto.",
        },
    }


def main() -> None:
    payload = build_payload()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    summary = payload["summary"]
    print(f"Exportadas {summary['nCandidates']} condições para {OUTPUT}")
    print(f"Elegíveis: {summary['nRankEligible']} | Pareto: {summary['nParetoNondominated']} | bandas ambas contidas: {summary['nEligibleWithBothBandsInside']}")
    for target, values in payload["models"].items():
        print(f"{target}: n={values['n']}, MAE={values['mae']}, R²={values['r2']}, Q90={values['q90AbsError']}")


if __name__ == "__main__":
    main()
