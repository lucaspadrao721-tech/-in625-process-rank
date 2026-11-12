from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from analyze import _assign_quality_ranks, _load_candidate_csv, _validated_source_context, assess_candidate
from export_rank_dashboard import build_payload, candidate_payload, support_payload
from src.data import INPUTS, dataframe_fingerprint, load_dataset, quality_report
from src.defects import SOURCE_STUDY_BLOCK_CASES, SOURCE_STUDY_POWER_GATES, assess_defect_modes, source_study_block_context, source_study_power_gate
from src.decision import geometry_reference_screen, pareto_front
from src.geometry import (
    audit_reference_window,
    dilution_from_geometry,
    hatch_spacing,
    hw_ratio,
    parabolic_track_envelope,
)
from src.models import _condition_groups, _joint_envelope_distance, _target_support, make_features, predict_one, train_bundle
from src.physics import process_indicators, surface_overlap_indicator

DATA = Path(__file__).resolve().parents[1] / "data" / "TabelaTotalSingleTracksIN625(1).xlsx"
CONTEXT = Path(__file__).resolve().parents[1] / "config" / "source_study_context.json"


def test_workbook_counts_derived_relations_and_provenance():
    df = load_dataset(DATA)
    report = quality_report(df)
    assert len(df) == 48
    assert report["n_unique_conditions"] == 48
    assert report["target_counts"]["H_um"] == 48
    assert report["target_counts"]["W_um"] == 48
    assert report["target_counts"]["HW"] == 48
    assert report["target_counts"]["h_um"] == 22
    assert report["target_counts"]["DI_pct"] == 22
    assert report["hw_max_abs_error"] < 1e-12
    assert report["di_max_abs_error_percentage_points"] < 1e-10


def test_geometric_formulas():
    assert np.isclose(hatch_spacing(692.9, 30), 485.03)
    assert np.isclose(dilution_from_geometry(236.2, 33.2), 12.32368, atol=1e-4)
    assert np.isclose(hw_ratio(236.2, 692.9), 0.340886, atol=1e-6)
    assert np.isclose(hatch_spacing(500, 0), 500)


def test_parabolic_envelope_is_surface_only():
    W, H = 700.0, 250.0
    spacing = hatch_spacing(W, 30.0)
    profile = parabolic_track_envelope(H, W, spacing)
    assert profile["geometric_gap_um"] == 0.0
    assert np.isclose(profile["valley_fraction_of_H"], 1 - 0.7**2)
    assert len(profile["profiles_um"]) == 3
    assert profile["status"] == "surface_geometry_only"
    assert "LoF" in profile["limitations"]


def test_process_indicator_units_are_consistent():
    result = process_indicators(400, 5, 1500)
    assert np.isclose(result["linear_energy_incident_J_mm"], 16.0)
    assert np.isclose(result["powder_feed_per_length_g_mm"], 5 / 1500)
    assert np.isclose(result["incident_energy_per_feed_mass_J_g"], 4800.0)
    assert result["volumetric_energy_density_J_mm3"] is None
    assert result["volumetric_energy_density_status"] == "not_computed_missing_hatch_or_layer_thickness"
    assert result["nominal_power_density_W_mm2"] is None


def test_ved_requires_declared_hatch_and_layer_thickness():
    result = process_indicators(400, 5.2, 1500, hatch_spacing_mm=0.46, layer_thickness_mm=0.583)
    assert np.isclose(result["volumetric_energy_density_J_mm3"], 400 / ((1500 / 60) * 0.46 * 0.583))
    assert result["volumetric_energy_density_status"] == "nominal_formula_using_user_supplied_layer_thickness"


def test_published_block_ed_uses_average_layer_thickness_not_delta_z():
    for case in SOURCE_STUDY_BLOCK_CASES:
        result = process_indicators(
            case["power_W"], case["feed_g_min"], case["speed_mm_min"],
            hatch_spacing_mm=case["hatch_spacing_mm"],
            layer_thickness_mm=case["average_layer_thickness_um"] / 1000.0,
        )
        assert abs(result["volumetric_energy_density_J_mm3"] - case["reported_VED_J_mm3"]) < 1.0


def test_source_study_block_evidence_is_context_not_transferred_label():
    exact = source_study_block_context(
        400, 5.2, 1500, overlap_pct=30, hatch_spacing_mm=0.46, layer_increment_mm=0.60
    )
    assert exact["status"] == "same_source_block_parameters_with_reported_LoF"
    assert exact["exact_source_block_LoF_case_ids"] == ["P415"]
    assert not exact["is_probability"]
    assert "EESC-USP" in exact["corroborating_thesis_citation"]
    assert exact["corroborating_thesis_pages"] == "93–97 impressas; Anexo 1, pp. 181–182"

    nearby = source_study_block_context(
        400, 5.0, 1500, overlap_pct=30, hatch_spacing_mm=0.46, layer_increment_mm=0.60
    )
    assert nearby["status"] == "same_power_speed_literature_context_not_transferable"
    assert np.isclose(nearby["matching_power_speed_cases"][0]["feed_delta_g_min"], -0.2)
    assert nearby["exact_source_block_LoF_case_ids"] == []

    p520 = source_study_block_context(
        500, 5.2, 2000, overlap_pct=30, hatch_spacing_mm=0.53, layer_increment_mm=0.55
    )
    assert p520["status"] == "same_source_block_parameters_no_LoF_observed_in_reported_sections"
    assert p520["exact_source_block_case_ids"] == ["P520"]
    assert p520["exact_source_block_LoF_case_ids"] == []
    assert p520["matching_power_speed_cases"][0]["combined_porosity_and_LoF_vol_pct"] == 0.16
    assert "no_LoF_observed_in_reported_cross_sections" in p520["matching_power_speed_cases"][0]["observed_modes"]

    effective_mismatch = source_study_block_context(
        400, 5.2, 1500, overlap_pct=31.65, hatch_spacing_mm=0.46, layer_increment_mm=0.60
    )
    assert effective_mismatch["status"] == "same_power_speed_literature_context_not_transferable"
    assert not effective_mismatch["matching_power_speed_cases"][0]["same_overlap"]
    assert not effective_mismatch["matching_power_speed_cases"][0]["exact_recorded_process_match"]


def test_source_study_power_gates_are_not_universal_probabilities():
    low = source_study_power_gate(300, context_active=True, context_id="original", power_gates=SOURCE_STUDY_POWER_GATES)
    high = source_study_power_gate(600, context_active=True, context_id="original", power_gates=SOURCE_STUDY_POWER_GATES)
    ordinary = source_study_power_gate(500, context_active=True, context_id="original", power_gates=SOURCE_STUDY_POWER_GATES)
    inactive = source_study_power_gate(300)
    assert low["excluded_from_source_study_ranking"]
    assert "diluição-alvo" in low["reason"]
    assert high["excluded_from_source_study_ranking"]
    assert "independentemente" in high["reason"]
    assert not ordinary["excluded_from_source_study_ranking"]
    assert high["probability_of_defect"] is None
    assert not inactive["excluded_from_source_study_ranking"]
    assert inactive["context_active"] is False


def test_corrected_model_feature_does_not_mix_minute_and_second():
    raw = pd.DataFrame([{"Power_W": 400, "Feed_g_min": 5, "Speed_mm_min": 1500}])
    features = make_features(raw)
    assert np.isclose(features.loc[0, "Linear_energy_incident_J_mm"], 16.0)
    assert np.isclose(features.loc[0, "Powder_feed_per_length_g_mm"], 5 / 1500)


def test_replicates_share_the_same_condition_group():
    raw = pd.DataFrame([
        {"Power_W": 400, "Feed_g_min": 5, "Speed_mm_min": 1500},
        {"Power_W": 400, "Feed_g_min": 5, "Speed_mm_min": 1500},
        {"Power_W": 500, "Feed_g_min": 5, "Speed_mm_min": 1500},
    ])
    groups = _condition_groups(raw)
    assert groups[0] == groups[1]
    assert groups[0] != groups[2]


def test_only_primary_dimensions_are_fitted_and_ratios_are_derived_from_oof(tmp_path):
    data = load_dataset(DATA)
    bundle, validation = train_bundle(data, source_path=str(DATA))
    assert bundle["bundle_version"] == 3
    assert set(bundle["models"]) == {"H_um", "W_um", "h_um"}
    assert bundle["schema"]["feed_unit_confirmation"].startswith("g/min confirmado")
    assert bundle["diagnostics"]["HW"]["n"] == 48
    assert bundle["diagnostics"]["DI_pct"]["n"] == 22
    derived = validation[validation["scheme"] == "derived_from_nested_grouped_component_oof"]
    assert len(derived[derived["target"] == "HW"]) == 48
    assert len(derived[derived["target"] == "DI_pct"]) == 22

    prediction = predict_one(bundle, 450, 6.25, 2250)
    assert np.isclose(prediction["HW"]["prediction"], prediction["H_um"]["prediction"] / prediction["W_um"]["prediction"])
    expected_di = 100 * prediction["h_um"]["prediction"] / (prediction["h_um"]["prediction"] + prediction["H_um"]["prediction"])
    assert np.isclose(prediction["DI_pct"]["prediction"], expected_di)
    assert prediction["DI_pct"]["feature_mode"] == "deterministic_geometry_formula"


def test_reference_window_is_not_a_defect_classifier():
    result = audit_reference_window(0, 0.1)
    assert result["defect_probability"] is None
    assert "não identifica falta de fusão" in result["findings"][-1]
    modes = assess_defect_modes()
    assert modes["probability_of_defect"] is None
    assert modes["modes"]["lateral_intertrack_lack_of_fusion"]["status"] == "not_evaluable"
    assert modes["modes"]["substrate_lack_of_fusion"]["probability"] is None
    assert "lote e caracterização do pó (morfologia/porosidade interna)" in modes["modes"]["gas_porosity"]["minimum_evidence"]


def test_surface_overlap_indicator_never_claims_metal_fusion():
    indicator = surface_overlap_indicator(700, hatch_spacing(700, 30))
    assert np.isclose(indicator["surface_overlap_pct"], 30)
    assert indicator["status"] == "surface_geometry_only"
    assert "não prova" in indicator["interpretation"]
    assert np.isclose(indicator["geometric_gap_um"], 0)


def test_reference_screen_marks_crossing_error_band_as_unresolved():
    result = geometry_reference_screen(
        di_pct=12.0,
        h_over_w=0.25,
        di_error_band={"low": 8.0, "high": 17.0},
        hw_error_band={"low": 0.22, "high": 0.30},
    )
    assert result["point_estimate_inside_reference"]
    assert result["DI_relation"] == "indicative_band_crosses_reference_boundary_not_calibrated"
    assert result["H_over_W_relation"] == "indicative_band_inside_reference_not_calibrated"
    assert result["not_a_defect_probability"]


def test_reference_screen_separates_point_from_indicative_band_robustness():
    contained = geometry_reference_screen(
        di_pct=20.0,
        h_over_w=0.25,
        di_error_band={"low": 15.0, "high": 25.0},
        hw_error_band={"low": 0.22, "high": 0.29},
    )
    assert contained["indicative_screen_status"] == "point_and_both_indicative_bands_inside_reference_not_calibrated"
    assert contained["normalized_indicative_band_violation"] == 0.0

    crossing = geometry_reference_screen(
        di_pct=20.0,
        h_over_w=0.266,
        di_error_band={"low": 15.0, "high": 25.0},
        hw_error_band={"low": 0.10, "high": 0.43},
    )
    assert crossing["indicative_screen_status"] == "point_inside_but_q90_band_crosses_or_exceeds_reference"
    assert crossing["normalized_indicative_band_violation"] > 0
    assert "Não há base calibrada" in crossing["indicative_screen_statement"]


def test_pareto_front_uses_corrected_objectives_and_excludes_ineligible_rows():
    rows = [
        {"candidate_id": "A", "point_estimate_inside_reference": True, "normalized_indicative_band_violation": 0.1, "normalized_point_violation": 0.1, "Feed_g_min": 5.0, "max_target_nearest_distance_normalized": 0.1, "rank_eligible": True},
        {"candidate_id": "B", "point_estimate_inside_reference": True, "normalized_indicative_band_violation": 0.2, "normalized_point_violation": 0.2, "Feed_g_min": 6.0, "max_target_nearest_distance_normalized": 0.2, "rank_eligible": True},
        {"candidate_id": "C", "point_estimate_inside_reference": False, "normalized_indicative_band_violation": 0.3, "normalized_point_violation": 0.3, "Feed_g_min": 4.0, "max_target_nearest_distance_normalized": 0.3, "rank_eligible": True},
        {"candidate_id": "D", "point_estimate_inside_reference": True, "normalized_indicative_band_violation": 0.0, "normalized_point_violation": 0.0, "Feed_g_min": 10.0, "max_target_nearest_distance_normalized": 0.0, "rank_eligible": False},
    ]
    result = pareto_front(rows)
    by_id = {row["candidate_id"]: row for row in result}
    assert by_id["A"]["pareto_nondominated"]
    assert by_id["B"]["pareto_status"] == "dominated"
    assert by_id["C"]["pareto_status"] == "dominated"
    assert by_id["D"]["pareto_status"] == "excluded_from_frontier"
    assert "score" not in by_id["A"]


def test_pareto_uses_q90_band_spill_when_available():
    rows = [
        {"candidate_id": "A", "point_estimate_inside_reference": True, "normalized_indicative_band_violation": 0.1, "normalized_point_violation": 0.1, "Feed_g_min": 5.0, "max_target_nearest_distance_normalized": 0.1, "rank_eligible": True},
        {"candidate_id": "B", "point_estimate_inside_reference": True, "normalized_indicative_band_violation": 0.2, "normalized_point_violation": 0.2, "Feed_g_min": 4.0, "max_target_nearest_distance_normalized": 0.2, "rank_eligible": True},
    ]
    result = pareto_front(rows)
    by_id = {row["candidate_id"]: row for row in result}
    assert by_id["A"]["pareto_nondominated"]
    assert by_id["B"]["pareto_status"] == "dominated"


def test_custom_candidate_csv_accepts_new_conditions_and_rejects_invalid_values(tmp_path):
    path = tmp_path / "candidates.csv"
    path.write_text(
        "candidate_id,Power_W,Feed_g_min,Speed_mm_min\n"
        "N1,450,6.25,2250\n"
        ",500,7.5,2500\n",
        encoding="utf-8",
    )
    result = _load_candidate_csv(path)
    assert result[0][0] == "N1"
    assert result[0][1] == {"Power_W": 450.0, "Feed_g_min": 6.25, "Speed_mm_min": 2250.0}
    assert result[1][0] == "C002"

    invalid = tmp_path / "invalid.csv"
    invalid.write_text("Power_W,Feed_g_min,Speed_mm_min\n450,0,2250\n", encoding="utf-8")
    with pytest.raises(ValueError, match="positivo e finito"):
        _load_candidate_csv(invalid)


@pytest.mark.parametrize(
    "di,hw",
    [(10.0, 0.25), (30.0, 0.25), (20.0, 0.2), (20.0, 1.0 / 3.0)],
)
def test_reference_boundaries_are_outside_without_invented_distance_penalty(di, hw):
    result = geometry_reference_screen(di_pct=di, h_over_w=hw)
    assert result["point_estimate_inside_reference"] is False
    assert result["point_reference_class"] == "boundary"
    assert result["normalized_point_violation"] == 0.0
    assert result["indicative_screen_status"] == "point_on_strict_reference_boundary"


def test_strict_inside_class_dominates_equal_distance_boundary_contact():
    rows = [
        {"candidate_id": "boundary", "point_estimate_inside_reference": False,
         "normalized_point_violation": 0.0, "normalized_indicative_band_violation": 0.0,
         "max_target_nearest_distance_normalized": 0.1, "rank_eligible": True},
        {"candidate_id": "inside", "point_estimate_inside_reference": True,
         "normalized_point_violation": 0.0, "normalized_indicative_band_violation": 0.0,
         "max_target_nearest_distance_normalized": 0.1, "rank_eligible": True},
    ]
    by_id = {row["candidate_id"]: row for row in pareto_front(rows)}
    assert by_id["inside"]["pareto_nondominated"]
    assert by_id["boundary"]["pareto_status"] == "dominated"


def test_joint_envelope_handles_full_reduced_and_constant_dimensions():
    plane = np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]], dtype=float)
    distance, dimension = _joint_envelope_distance(plane, np.asarray([0.4, 0.6, 0.0]))
    assert distance == 0.0
    assert dimension == 2
    outside_distance, outside_dimension = _joint_envelope_distance(plane, np.asarray([1.5, 0.5, 0.0]))
    assert outside_distance == pytest.approx(0.5)
    assert outside_dimension == 2

    line = np.asarray([[0, 0, 0], [1, 0, 0], [0.5, 0, 0]], dtype=float)
    line_distance, line_dimension = _joint_envelope_distance(line, np.asarray([0.5, 0.0, 0.0]))
    assert line_distance == 0.0
    assert line_dimension == 1
    point_distance, point_dimension = _joint_envelope_distance(
        np.zeros((4, 3)), np.zeros(3)
    )
    assert point_distance == 0.0
    assert point_dimension == 0


def test_target_support_requires_joint_envelope_not_only_marginal_ranges():
    schema = {
        "target_training_inputs": {
            "h_um": [
                {"Power_W": 0.0, "Feed_g_min": 0.0, "Speed_mm_min": 1.0},
                {"Power_W": 1.0, "Feed_g_min": 0.0, "Speed_mm_min": 1.0},
                {"Power_W": 0.0, "Feed_g_min": 1.0, "Speed_mm_min": 1.0},
            ]
        },
        "target_support_ranges": {
            "h_um": {"Power_W": [0.0, 1.0], "Feed_g_min": [0.0, 1.0], "Speed_mm_min": [1.0, 1.0]}
        },
    }
    inside = _target_support(schema, "h_um", {"Power_W": 0.2, "Feed_g_min": 0.3, "Speed_mm_min": 1.0})
    outside = _target_support(schema, "h_um", {"Power_W": 0.8, "Feed_g_min": 0.8, "Speed_mm_min": 1.0})
    absent = _target_support({"target_training_inputs": {}}, "DI_pct", {"Power_W": 1, "Feed_g_min": 1, "Speed_mm_min": 1})
    assert inside["within_target_joint_envelope"] is True
    assert inside["status"] == "inside_target_joint_envelope_unlabeled"
    assert outside["within_target_marginal_ranges"] is True
    assert outside["within_target_joint_envelope"] is False
    assert outside["joint_envelope_distance_normalized"] > 0
    assert outside["status"] == "outside_target_joint_envelope"
    assert absent["within_target_joint_envelope"] is None


def test_source_gates_follow_dataframe_fingerprint_and_do_not_inherit_to_new_base():
    data = load_dataset(DATA)
    configured = _validated_source_context(CONTEXT, data)
    changed = data.copy()
    changed.loc[0, "H_um"] += 1.0
    unconfigured = _validated_source_context(CONTEXT, changed)
    assert configured["active"] is True
    assert configured["dataframe_fingerprint"] == dataframe_fingerprint(data)
    assert configured["power_gates"]
    assert unconfigured["active"] is False
    assert unconfigured["power_gates"] == []
    assert source_study_power_gate(300, context_active=unconfigured["active"], power_gates=unconfigured["power_gates"])["excluded_from_source_study_ranking"] is False


def test_assessment_does_not_transfer_multipass_lof_and_excludes_unsupported_predictions():
    data = load_dataset(DATA)

    def fake_prediction(*, supported=True):
        support = {
            "within_target_joint_envelope": supported,
            "within_target_marginal_ranges": True,
            "nearest_distance_normalized": 0.1,
            "joint_envelope_distance_normalized": 0.0 if supported else 0.2,
            "exact_condition_has_label": False,
        }
        def item(value, low, high):
            return {"prediction": value, "indicative_low": low, "indicative_high": high, "support": dict(support)}
        return {
            "H_um": item(200.0, 190.0, 210.0),
            "W_um": item(800.0, 790.0, 810.0),
            "h_um": item(50.0, 45.0, 55.0),
            "HW": item(0.25, 0.23, 0.27),
            "DI_pct": item(20.0, 18.0, 22.0),
            "support_summary": {
                "within_input_marginal_ranges": True,
                "exact_observed_input_combination": True,
                "nearest_design_distance_normalized": 0.0,
            },
        }

    candidate = {"Power_W": 400.0, "Feed_g_min": 5.2, "Speed_mm_min": 1500.0}
    context = {"active": True, "id": "original", "power_gates": SOURCE_STUDY_POWER_GATES}
    with patch("analyze.predict_one", return_value=fake_prediction(supported=True)):
        supported = assess_candidate(
            candidate, bundle={}, data=data, hatch_spacing_mm=0.46,
            layer_increment_mm=0.60, use_reference_window=True,
            candidate_id="track", source_context=context,
        )
    assert supported["rank_eligible"] is True
    assert supported["rank_exclusion_reason"] is None
    assert "source_block_evidence" not in supported
    assert supported["probability_of_defect"] is None

    with patch("analyze.predict_one", return_value=fake_prediction(supported=False)):
        unsupported = assess_candidate(candidate, bundle={}, data=data, use_reference_window=True, candidate_id="outside")
    assert unsupported["predictions"]["DI_pct"]["prediction"] == 20.0
    assert unsupported["rank_eligible"] is False
    assert "Fora do envelope rotulado DI" in unsupported["rank_exclusion_reasons"]
    unsupported = pareto_front([unsupported])[0]
    assert unsupported["pareto_nondominated"] is False
    assert unsupported["quality_order"] is None


def test_feed_and_id_do_not_split_scientific_ties_and_dense_rank_is_shared():
    equal = {
        "point_estimate_inside_reference": True,
        "normalized_point_violation": 0.0,
        "normalized_indicative_band_violation": 0.25,
        "max_target_nearest_distance_normalized": 0.1,
        "rank_eligible": True,
    }
    rows = [
        {**equal, "candidate_id": "B", "Feed_g_min": 10.0},
        {**equal, "candidate_id": "A", "Feed_g_min": 5.0},
        {**equal, "candidate_id": "C", "Feed_g_min": 7.5,
         "normalized_point_violation": 0.1},
    ]
    ordered = _assign_quality_ranks(rows)
    by_id = {row["candidate_id"]: row for row in rows}
    assert by_id["A"]["quality_order"] == by_id["B"]["quality_order"] == 1
    assert by_id["A"]["rank_tie_count"] == by_id["B"]["rank_tie_count"] == 2
    assert by_id["C"]["quality_order"] == 2
    assert by_id["C"]["rank_tie_count"] == 1
    assert [row["candidate_id"] for row in ordered[:2]] == ["A", "B"]


def test_export_payload_exposes_contract_additions_without_changing_schema_version():
    old_status = support_payload({"status": "outside_target_joint_envelope", "within_target_joint_envelope": False})
    absent_status = support_payload({"status": "no_training_labels", "within_target_joint_envelope": None})
    assert old_status["status"] == "fora_do_envelope_rotulado"
    assert old_status["withinTargetJointEnvelope"] is False
    assert absent_status["withinTargetJointEnvelope"] is None
    payload = build_payload()
    assert payload["schemaVersion"] == 2
    assert "context" in payload and "bandFeasibility" in payload
    assert len(payload["candidates"]) == 48
    candidate = payload["candidates"][0]
    assert "exclusionReasons" in candidate and "rankTieCount" in candidate
    assert all("withinTargetJointEnvelope" in pred["support"] for pred in candidate["predictions"].values())
