from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.data import INPUTS, load_dataset, quality_report
from src.defects import SOURCE_STUDY_BLOCK_CASES, SOURCE_STUDY_BLOCK_URL, SOURCE_STUDY_POWER_GATES
from src.models import save_bundle, train_bundle
from src.physics import process_indicators


def main() -> None:
    parser = argparse.ArgumentParser(description="Treina modelos geométricos e valida o suporte para IN625 DED-LB.")
    parser.add_argument("--data", default="data/TabelaTotalSingleTracksIN625(1).xlsx", help="Planilha Excel de entrada")
    parser.add_argument("--out", default="artifacts", help="Pasta dos modelos e relatórios")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    data = load_dataset(args.data)
    data_quality = quality_report(data)
    bundle, validation = train_bundle(data, source_path=args.data)

    save_bundle(bundle, str(out / "model_bundle.joblib"))
    validation.to_csv(out / "validation_predictions.csv", index=False)
    data.to_csv(out / "dataset_clean.csv", index=False)

    indicators = []
    for _, row in data.iterrows():
        derived = process_indicators(row["Power_W"], row["Feed_g_min"], row["Speed_mm_min"])
        indicators.append({
            "record_id": int(row["record_id"]),
            **{key: float(row[key]) for key in INPUTS},
            "linear_energy_incident_J_mm": derived["linear_energy_incident_J_mm"],
            "powder_feed_per_length_g_mm": derived["powder_feed_per_length_g_mm"],
            "incident_energy_per_feed_mass_J_g": derived["incident_energy_per_feed_mass_J_g"],
            "volumetric_energy_density_J_mm3": derived["volumetric_energy_density_J_mm3"],
            "volumetric_energy_density_status": derived["volumetric_energy_density_status"],
            "indicator_status": derived["status"],
        })
    pd.DataFrame(indicators).to_csv(out / "process_indicators.csv", index=False)

    full_report = {
        "project": "IN625 DED-LB single-track geometry screening",
        "data_quality": data_quality,
        "model_diagnostics": bundle["diagnostics"],
        "schema": bundle["schema"],
        "interpretation_guardrails": [
            "Only H, W and h are fitted as regressors; H/W and DI are derived deterministically from their predictions.",
            "This package predicts measured geometric targets; it does not classify defects.",
            "Nested grouped cross-validation uses up to 4 outer and 3 inner folds; it primarily estimates interpolation within this small design.",
            "Factor-level holdouts are internal stress tests; they do not validate transfer to another machine, campaign, material, substrate, or optical setup.",
            "Empirical absolute-error bands are not conformal intervals or probabilities of geometric conformity.",
            "No defect probability is trained because no per-specimen defect labels and inspection protocol were supplied.",
            "Energy and powder-per-length values are nominal indicators, not absorbed energy, captured mass, deposition productivity, or electrical efficiency.",
            "Powder feed unit g/min was confirmed by the user; the inconsistent spreadsheet label g/mm is overridden.",
            "The four multipass block outcomes from the source article are stored as external context, not as single-track training labels.",
        ],
        "reference_window": {
            "source": "https://link.springer.com/article/10.1007/s11665-026-14887-8",
            "DI_pct": [10.0, 30.0],
            "H_over_W": [0.2, 1.0 / 3.0],
            "scope": "Study-specific geometric screening only; not universal defect thresholds.",
        },
        "source_study_multipass_block_evidence": {
            "source": SOURCE_STUDY_BLOCK_URL,
            "cases": SOURCE_STUDY_BLOCK_CASES,
            "use": "Context-only evidence for candidate assessment; not included in model fitting or interpreted as transferable defect probabilities.",
            "measured_percentage_definition": "Table 4 porosity (%) includes both porosity and lack of fusion.",
        },
        "source_study_power_gates": {
            "cases": SOURCE_STUDY_POWER_GATES,
            "use": "Selection observations from the source article; not defect classifier labels or universal material/process thresholds.",
        },
    }
    (out / "training_report.json").write_text(
        json.dumps(full_report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )

    print("\nTreinamento concluído")
    print(f"  Registros: {len(data)}")
    for target, diagnostics in bundle["diagnostics"].items():
        if "cv_mae" not in diagnostics:
            print(f"  {target}: {diagnostics.get('status', 'sem modelo')}")
            continue
        print(
            f"  {target}: n={diagnostics['n']} ({diagnostics['n_unique_conditions']} condições); modelo={diagnostics['selected_model']}; "
            f"MAE nested-group-CV={diagnostics['cv_mae']:.3f}; "
            f"baseline mediana={diagnostics['baseline_cv_mae']:.3f}; "
            f"banda de erro absoluta q90={diagnostics['residual_abs_q90']:.3f} (indicativa)"
        )
        for factor, result in diagnostics["factor_level_holdout"].items():
            mae = result.get("mae")
            print(f"    stress test omitindo nível de {factor}: MAE={mae:.3f}" if mae is not None else f"    stress test {factor}: n/d")
    print(f"\nArquivos gravados em: {out.resolve()}")
    print("Nenhum classificador de LoF, keyhole, porosidade ou trinca foi treinado: a planilha de trilha única não tem rótulos por amostra; quatro resultados de blocos permanecem contexto separado.")
    print("Para triagem da grade e exportação de resultados, execute: python analyze.py --grid")


if __name__ == "__main__":
    main()
