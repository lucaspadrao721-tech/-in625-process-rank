"""Modelos de geometria, validação agrupada e suporte experimental IN625 DED-LB."""
from __future__ import annotations

import math
import joblib
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.spatial import ConvexHull
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from .data import INPUTS, MODEL_TARGETS, TARGETS

RANDOM_STATE = 42
MODEL_SPECS = ("ridge_linear_raw", "ridge_quadratic_raw", "ridge_linear_physics")
SUPPORT_ENVELOPE_NUMERICAL_TOLERANCE = 1e-10


def make_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Features nominais com unidades consistentes.

    E_L = P/(v/60) [J/mm]. A massa de pó por comprimento é feed/v [g/mm],
    pois feed e velocidade estão ambos em unidades por minuto. Não é massa capturada.
    """
    p = np.asarray(raw["Power_W"], dtype=float)
    feed = np.asarray(raw["Feed_g_min"], dtype=float)
    speed = np.asarray(raw["Speed_mm_min"], dtype=float)
    values = np.column_stack([p, feed, speed])
    if not np.isfinite(values).all() or np.any(values <= 0):
        raise ValueError("Potência, alimentação e velocidade precisam ser positivas e finitas.")
    return pd.DataFrame({
        "Power_W": p,
        "Feed_g_min": feed,
        "Speed_mm_min": speed,
        "Linear_energy_incident_J_mm": p * 60.0 / speed,
        "Powder_feed_per_length_g_mm": feed / speed,
    }, index=raw.index)


def _legacy_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Reproduz unidades do bundle v1 somente para inferência com artefato antigo."""
    p = np.asarray(raw["Power_W"], dtype=float)
    feed = np.asarray(raw["Feed_g_min"], dtype=float)
    speed = np.asarray(raw["Speed_mm_min"], dtype=float)
    return pd.DataFrame({
        "Power_W": p,
        "Feed_g_min": feed,
        "Speed_mm_min": speed,
        "Linear_energy_J_mm": p / (speed / 60.0),
        "Powder_per_length_g_mm": feed / (speed / 60.0),
    }, index=raw.index)


def _feature_frame(raw: pd.DataFrame, mode: str) -> pd.DataFrame:
    if mode == "raw":
        return raw.loc[:, INPUTS].astype(float).reset_index(drop=True)
    if mode == "physics":
        return make_features(raw.loc[:, INPUTS]).reset_index(drop=True)
    if mode == "legacy_physics":
        return _legacy_features(raw.loc[:, INPUTS]).reset_index(drop=True)
    raise ValueError(f"Modo de features desconhecido: {mode}")


def _condition_groups(raw: pd.DataFrame) -> np.ndarray:
    return pd.MultiIndex.from_frame(raw.loc[:, INPUTS].astype(float)).factorize(sort=False)[0]


def _new_estimator(model_name: str) -> Pipeline:
    if model_name == "ridge_linear_raw":
        return Pipeline([("scale", StandardScaler()), ("reg", Ridge(alpha=1.0))])
    if model_name == "ridge_quadratic_raw":
        return Pipeline([
            ("poly", PolynomialFeatures(degree=2, include_bias=False)),
            ("scale", StandardScaler()),
            ("reg", Ridge(alpha=1.0)),
        ])
    if model_name == "ridge_linear_physics":
        return Pipeline([("scale", StandardScaler()), ("reg", Ridge(alpha=1.0))])
    raise ValueError(f"Modelo desconhecido: {model_name}")


def _model_mode(model_name: str) -> str:
    return "physics" if model_name == "ridge_linear_physics" else "raw"


def _group_splits(raw: pd.DataFrame, max_splits: int, seed: int):
    groups = _condition_groups(raw)
    n_groups = int(len(np.unique(groups)))
    n_splits = min(max_splits, n_groups)
    if n_splits < 2:
        return []
    splitter = GroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    return list(splitter.split(raw, groups=groups))


def _group_cv_mae(raw: pd.DataFrame, y: np.ndarray, model_name: str, seed: int) -> float:
    splits = _group_splits(raw, max_splits=3, seed=seed)
    if not splits:
        return float("inf")
    prediction = np.full(len(y), np.nan, dtype=float)
    mode = _model_mode(model_name)
    for train_idx, test_idx in splits:
        estimator = _new_estimator(model_name)
        estimator.fit(_feature_frame(raw.iloc[train_idx], mode), y[train_idx])
        prediction[test_idx] = estimator.predict(_feature_frame(raw.iloc[test_idx], mode))
    return float(mean_absolute_error(y, prediction))


def _select_model_name(raw: pd.DataFrame, y: np.ndarray, seed: int) -> tuple[str, dict[str, float]]:
    """Escolhe entre três especificações curtas apenas nos dados de treino recebidos."""
    scores = {name: _group_cv_mae(raw.reset_index(drop=True), y, name, seed) for name in MODEL_SPECS}
    selected = min(MODEL_SPECS, key=lambda name: (scores[name], MODEL_SPECS.index(name)))
    return selected, scores


def _safe_r2(actual: np.ndarray, predicted: np.ndarray) -> float | None:
    if len(actual) < 2 or np.var(actual) == 0:
        return None
    return float(r2_score(actual, predicted))


def _error_quantile(abs_errors: np.ndarray, coverage: float = 0.90) -> float:
    """Ordem amostral conservadora; não é quantil conformal calibrado."""
    values = np.sort(np.asarray(abs_errors, dtype=float))
    if len(values) == 0:
        return float("nan")
    index = min(len(values) - 1, max(0, math.ceil((len(values) + 1) * coverage) - 1))
    return float(values[index])


def _factor_level_holdout(raw: pd.DataFrame, y: np.ndarray, seed: int) -> dict:
    """Stress test aninhado, omitindo por vez um nível inteiro de cada entrada."""
    results: dict[str, dict] = {}
    for factor_index, factor in enumerate(INPUTS):
        fold_rows = []
        all_actual: list[float] = []
        all_predicted: list[float] = []
        for level_index, value in enumerate(sorted(raw[factor].unique())):
            test_idx = np.flatnonzero(np.isclose(raw[factor].to_numpy(dtype=float), float(value)))
            train_idx = np.setdiff1d(np.arange(len(raw)), test_idx)
            train_raw = raw.iloc[train_idx].reset_index(drop=True)
            if len(test_idx) == 0 or len(np.unique(_condition_groups(train_raw))) < 8:
                continue
            y_train = y[train_idx]
            model_name, inner_scores = _select_model_name(train_raw, y_train, seed + factor_index * 100 + level_index)
            mode = _model_mode(model_name)
            estimator = _new_estimator(model_name)
            estimator.fit(_feature_frame(train_raw, mode), y_train)
            prediction = estimator.predict(_feature_frame(raw.iloc[test_idx], mode))
            actual = y[test_idx]
            fold_rows.append({
                "held_out_factor": factor,
                "held_out_level": float(value),
                "n_test": int(len(test_idx)),
                "selected_model": model_name,
                "inner_group_cv_mae_by_model": inner_scores,
                "mae": float(mean_absolute_error(actual, prediction)),
                "rmse": float(np.sqrt(mean_squared_error(actual, prediction))),
            })
            all_actual.extend(float(v) for v in actual)
            all_predicted.extend(float(v) for v in prediction)
        results[factor] = {
            "interpretation": "Stress test interno: cada nível é omitido por vez; não valida outra máquina, campanha, lote ou material.",
            "n_levels_held_out": len(fold_rows),
            "mae": float(mean_absolute_error(all_actual, all_predicted)) if all_actual else None,
            "rmse": float(np.sqrt(mean_squared_error(all_actual, all_predicted))) if all_actual else None,
            "folds": fold_rows,
        }
    return results


def _derived_diagnostics(actual: list[float], predicted: list[float], baseline: list[float], n_conditions: int, components: list[str]) -> dict:
    y = np.asarray(actual, dtype=float)
    pred = np.asarray(predicted, dtype=float)
    base = np.asarray(baseline, dtype=float)
    abs_errors = np.abs(y - pred)
    return {
        "n": int(len(y)),
        "n_unique_conditions": int(n_conditions),
        "selected_model": "derived_from_component_predictions",
        "feature_mode": "deterministic_geometry_formula",
        "component_targets": components,
        "cv_method": "Fórmula aplicada somente a predições OOF dos componentes; os modelos-base são validados separadamente por condição.",
        "cv_outer_folds": None,
        "cv_mae": float(mean_absolute_error(y, pred)),
        "cv_rmse": float(np.sqrt(mean_squared_error(y, pred))),
        "cv_r2": _safe_r2(y, pred),
        "baseline_cv_mae": float(mean_absolute_error(y, base)),
        "residual_abs_q90": _error_quantile(abs_errors, 0.90),
        "error_band_semantics": "Quantil amostral dos erros absolutos da fórmula aplicada a predições OOF; indicativo, não calibrado e sem capturar a covariância entre componentes.",
        "outer_models": [],
        "factor_level_holdout": {},
    }


def fit_target(raw_inputs: pd.DataFrame, y_series: pd.Series, seed: int = RANDOM_STATE) -> tuple[object, dict, np.ndarray]:
    """Validação aninhada por condição (até 4 folds externos, 3 internos)."""
    raw = raw_inputs.loc[:, INPUTS].astype(float).reset_index(drop=True)
    y = np.asarray(y_series, dtype=float)
    if len(raw) != len(y):
        raise ValueError("Entradas e resposta têm contagens diferentes.")
    groups = _condition_groups(raw)
    n_groups = int(len(np.unique(groups)))
    if n_groups < 8:
        raise ValueError(f"Poucas condições únicas para treino exploratório: {n_groups} (mínimo operacional=8).")
    if not np.isfinite(y).all():
        raise ValueError("A resposta observada contém valor não finito.")

    outer_splits = _group_splits(raw, max_splits=4, seed=seed)
    oof = np.full(len(y), np.nan, dtype=float)
    baseline_oof = np.full(len(y), np.nan, dtype=float)
    outer_models: list[str] = []
    for fold_index, (train_idx, test_idx) in enumerate(outer_splits):
        train_raw = raw.iloc[train_idx].reset_index(drop=True)
        y_train = y[train_idx]
        model_name, _ = _select_model_name(train_raw, y_train, seed + fold_index + 1)
        mode = _model_mode(model_name)
        estimator = _new_estimator(model_name)
        estimator.fit(_feature_frame(train_raw, mode), y_train)
        oof[test_idx] = estimator.predict(_feature_frame(raw.iloc[test_idx], mode))
        baseline = DummyRegressor(strategy="median").fit(np.zeros((len(y_train), 1)), y_train)
        baseline_oof[test_idx] = baseline.predict(np.zeros((len(test_idx), 1)))
        outer_models.append(model_name)

    if not np.isfinite(oof).all() or not np.isfinite(baseline_oof).all():
        raise RuntimeError("A validação cruzada não produziu previsão para todos os rótulos.")
    final_name, final_inner_scores = _select_model_name(raw, y, seed + 99)
    final_mode = _model_mode(final_name)
    final_estimator = _new_estimator(final_name)
    final_estimator.fit(_feature_frame(raw, final_mode), y)
    abs_errors = np.abs(y - oof)
    diagnostics = {
        "n": int(len(y)),
        "n_unique_conditions": n_groups,
        "selected_model": final_name,
        "feature_mode": final_mode,
        "selected_parameters": {"ridge_alpha": 1.0, "polynomial_degree": 2 if final_name == "ridge_quadratic_raw" else 1},
        "inner_group_cv_mae_by_model": final_inner_scores,
        "cv_method": "CV aninhada agrupada por condição: até 4 folds externos e até 3 folds internos; réplicas da mesma combinação ficam juntas",
        "cv_outer_folds": len(outer_splits),
        "cv_mae": float(mean_absolute_error(y, oof)),
        "cv_rmse": float(np.sqrt(mean_squared_error(y, oof))),
        "cv_r2": _safe_r2(y, oof),
        "baseline_cv_mae": float(mean_absolute_error(y, baseline_oof)),
        "residual_abs_q90": _error_quantile(abs_errors, 0.90),
        "error_band_semantics": "Quantil amostral de erros nested-group-CV; banda empírica indicativa, não intervalo conformal nem probabilidade.",
        "outer_models": outer_models,
        "factor_level_holdout": _factor_level_holdout(raw, y, seed + 500),
        "oof_actual": y.tolist(),
        "oof_predicted": oof.tolist(),
        "baseline_oof_predicted": baseline_oof.tolist(),
    }
    return final_estimator, diagnostics, oof


def train_bundle(data: pd.DataFrame, source_path: str = "") -> tuple[dict, pd.DataFrame]:
    """Treina H, W e h; deriva H/W e DI sem ajustar regressões redundantes."""
    models: dict[str, object] = {}
    modes: dict[str, str] = {}
    diagnostics: dict[str, dict] = {}
    validation_rows: list[dict] = []
    oof_by_target: dict[str, dict[int, dict[str, float]]] = {}
    for idx, target in enumerate(MODEL_TARGETS):
        mask = data[target].notna().to_numpy()
        n_target = int(mask.sum())
        rows = data.loc[mask].reset_index(drop=True)
        n_conditions = int(rows["condition_group"].nunique()) if n_target else 0
        if n_conditions < 8:
            diagnostics[target] = {"n": n_target, "n_unique_conditions": n_conditions, "status": "não treinado: menos de 8 condições únicas"}
            continue
        estimator, report, _ = fit_target(rows[INPUTS], rows[target].rename(target), RANDOM_STATE + idx)
        models[target] = estimator
        modes[target] = report["feature_mode"]
        diagnostics[target] = report
        oof_by_target[target] = {
            int(row["record_id"]): {
                "oof": float(report["oof_predicted"][i]),
                "baseline": float(report["baseline_oof_predicted"][i]),
            }
            for i, (_, row) in enumerate(rows.iterrows())
        }
        for i, row in rows.iterrows():
            validation_rows.append({
                "scheme": "nested_grouped_condition_cv",
                "target": target,
                "record_id": int(row["record_id"]),
                "condition_group": int(row["condition_group"]),
                "Power_W": float(row["Power_W"]),
                "Feed_g_min": float(row["Feed_g_min"]),
                "Speed_mm_min": float(row["Speed_mm_min"]),
                "actual": float(report["oof_actual"][i]),
                "oof_prediction": float(report["oof_predicted"][i]),
                "baseline_prediction": float(report["baseline_oof_predicted"][i]),
            })
        for key in ("oof_actual", "oof_predicted", "baseline_oof_predicted"):
            diagnostics[target].pop(key, None)

    def derive_target(target: str, component_targets: list[str], formula) -> None:
        actuals: list[float] = []
        predictions: list[float] = []
        baselines: list[float] = []
        derived_rows: list[dict] = []
        for _, row in data.loc[data[target].notna()].iterrows():
            record_id = int(row["record_id"])
            if any(record_id not in oof_by_target.get(component, {}) for component in component_targets):
                continue
            component_oof = {component: oof_by_target[component][record_id]["oof"] for component in component_targets}
            component_baseline = {component: oof_by_target[component][record_id]["baseline"] for component in component_targets}
            predicted = formula(component_oof)
            baseline = formula(component_baseline)
            if predicted is None or baseline is None or not np.isfinite(predicted) or not np.isfinite(baseline):
                continue
            actual = float(row[target])
            actuals.append(actual)
            predictions.append(float(predicted))
            baselines.append(float(baseline))
            derived_rows.append({
                "scheme": "derived_from_nested_grouped_component_oof",
                "target": target,
                "record_id": record_id,
                "condition_group": int(row["condition_group"]),
                **{key: float(row[key]) for key in INPUTS},
                "actual": actual,
                "oof_prediction": float(predicted),
                "baseline_prediction": float(baseline),
            })
        validation_rows.extend(derived_rows)
        diagnostics[target] = _derived_diagnostics(
            actuals, predictions, baselines,
            n_conditions=len({item["condition_group"] for item in derived_rows}),
            components=component_targets,
        )

    derive_target(
        "HW", ["H_um", "W_um"],
        lambda values: values["H_um"] / values["W_um"] if values["W_um"] > 0 else None,
    )
    derive_target(
        "DI_pct", ["h_um", "H_um"],
        lambda values: 100.0 * values["h_um"] / (values["h_um"] + values["H_um"])
        if values["H_um"] > 0 and values["h_um"] + values["H_um"] > 0 else None,
    )

    target_training_inputs: dict[str, list[dict[str, float]]] = {}
    target_ranges: dict[str, dict[str, list[float]]] = {}
    for target in TARGETS:
        rows = data.loc[data[target].notna(), INPUTS]
        target_training_inputs[target] = [
            {key: float(record[key]) for key in INPUTS}
            for record in rows.to_dict(orient="records")
        ]
        target_ranges[target] = {
            key: [float(rows[key].min()), float(rows[key].max())] if not rows.empty else [None, None]
            for key in INPUTS
        }

    all_inputs = data.loc[:, INPUTS]
    input_ranges = {key: [float(all_inputs[key].min()), float(all_inputs[key].max())] for key in INPUTS}
    schema = {
        "inputs": INPUTS,
        "targets": TARGETS,
        "fitted_targets": MODEL_TARGETS,
        "derived_targets": {"HW": "H_um / W_um", "DI_pct": "100 * h_um / (h_um + H_um)"},
        "input_units": {"Power_W": "W", "Feed_g_min": "g/min", "Speed_mm_min": "mm/min"},
        "output_units": {"H_um": "µm", "W_um": "µm", "h_um": "µm", "DI_pct": "%", "HW": "dimensionless"},
        "target_definitions": {
            "H_um": "mean deposited height above original substrate surface",
            "W_um": "mean apparent bead width",
            "h_um": "source column h mean; treated as penetration depth under the source-study definition",
            "DI_pct": "source-table dilution percentage; source article defines 100*h/(h+H)",
            "HW": "derived table ratio H/W; not an independent physical measurement",
        },
        "input_ranges": input_ranges,
        "power_range_W": input_ranges["Power_W"],
        "feed_range_g_min": input_ranges["Feed_g_min"],
        "speed_range_mm_min": input_ranges["Speed_mm_min"],
        "target_support_ranges": target_ranges,
        "target_training_inputs": target_training_inputs,
        "observed_combinations": [{key: float(record[key]) for key in INPUTS} for record in all_inputs.to_dict(orient="records")],
        "n_experiments": int(len(data)),
        "n_unique_conditions": int(data["condition_group"].nunique()),
        "feed_unit_confirmation": "g/min confirmado pelo usuário; o rótulo g/mm na planilha é inconsistente e foi sobrescrito.",
        "source_path": str(source_path),
        "support_note": "Marginal bounds do not guarantee support throughout their Cartesian product; distances are descriptive only.",
    }
    bundle = {"bundle_version": 3, "models": models, "feature_modes": modes, "diagnostics": diagnostics, "schema": schema}
    return bundle, pd.DataFrame(validation_rows)


def save_bundle(bundle: dict, path: str) -> None:
    joblib.dump(bundle, path, compress=3)


def load_bundle(path: str) -> dict:
    return joblib.load(path)


def _joint_envelope_distance(normalized_points: np.ndarray, normalized_query: np.ndarray) -> tuple[float, int]:
    """Distância à envoltória convexa, projetando corretamente pontos de dimensão reduzida.

    A tolerância de classificação (1e-10 unidade normalizada) é somente para
    erro de ponto flutuante. Uma dimensão afim é removida via SVD antes do teste
    geométrico; dimensões constantes tornam-se resíduos fora desse subespaço.
    """
    center = normalized_points.mean(axis=0)
    centered = normalized_points - center
    _, singular_values, right_vectors = np.linalg.svd(centered, full_matrices=False)
    leading = float(singular_values[0]) if len(singular_values) else 0.0
    rank_tolerance = max(centered.shape) * np.finfo(float).eps * max(leading, 1.0)
    dimension = int(np.count_nonzero(singular_values > rank_tolerance))
    query_delta = normalized_query - center
    if dimension == 0:
        distance = float(np.linalg.norm(query_delta))
        return distance, 0

    basis = right_vectors[:dimension].T
    points_reduced = centered @ basis
    query_reduced = query_delta @ basis
    orthogonal_residual = query_delta - query_reduced @ basis.T
    orthogonal_distance = float(np.linalg.norm(orthogonal_residual))
    if dimension == 1:
        lower = float(points_reduced[:, 0].min())
        upper = float(points_reduced[:, 0].max())
        projected = float(np.clip(query_reduced[0], lower, upper))
        distance = math.hypot(orthogonal_distance, float(query_reduced[0] - projected))
        return distance, dimension

    hull = ConvexHull(points_reduced)
    signed_facet_distances = (
        hull.equations[:, :-1] @ query_reduced + hull.equations[:, -1]
    )
    within_affine_hull = (
        orthogonal_distance <= SUPPORT_ENVELOPE_NUMERICAL_TOLERANCE
        and float(signed_facet_distances.max()) <= SUPPORT_ENVELOPE_NUMERICAL_TOLERANCE
    )
    if within_affine_hull:
        return 0.0, dimension

    vertices = points_reduced[hull.vertices]
    nearest_vertex = int(np.argmin(np.sum((vertices - query_reduced) ** 2, axis=1)))
    initial = np.zeros(len(vertices), dtype=float)
    initial[nearest_vertex] = 1.0

    def objective(weights: np.ndarray) -> float:
        difference = weights @ vertices - query_reduced
        return float(difference @ difference)

    def gradient(weights: np.ndarray) -> np.ndarray:
        difference = weights @ vertices - query_reduced
        return 2.0 * (vertices @ difference)

    projection = minimize(
        objective,
        initial,
        jac=gradient,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * len(vertices),
        constraints={"type": "eq", "fun": lambda weights: float(weights.sum() - 1.0),
                     "jac": lambda weights: np.ones_like(weights)},
        options={"ftol": 1e-14, "maxiter": 1000},
    )
    if not projection.success:
        raise RuntimeError(f"Não foi possível projetar no envelope conjunto: {projection.message}")
    projected_point = projection.x @ vertices
    distance = math.hypot(orthogonal_distance, float(np.linalg.norm(projected_point - query_reduced)))
    return distance, dimension


def _target_support(schema: dict, target: str, query: dict[str, float]) -> dict:
    """Classifica suporte de um alvo por seu envelope conjunto de pontos rotulados."""
    points = schema.get("target_training_inputs", {}).get(target, [])
    if not points:
        return {
            "status": "no_training_labels",
            "within_target_marginal_ranges": False,
            "within_target_joint_envelope": None,
            "exact_condition_has_label": False,
            "nearest_distance_normalized": None,
            "joint_envelope_distance_normalized": None,
            "joint_envelope_dimension": None,
        }
    matrix = np.asarray([[float(row[key]) for key in INPUTS] for row in points], dtype=float)
    query_vector = np.asarray([float(query[key]) for key in INPUTS], dtype=float)
    ranges = schema.get("target_support_ranges", {}).get(target, {})
    lower = np.asarray([float(ranges[key][0]) for key in INPUTS], dtype=float)
    upper = np.asarray([float(ranges[key][1]) for key in INPUTS], dtype=float)
    widths = upper - lower
    # Faixa zero significa dimensão constante; usa-se 1 unidade de entrada só
    # para expressar distância fora do subespaço, nunca para alargar o envelope.
    scale = np.where(widths > 0.0, widths, 1.0)
    normalized_points = (matrix - lower) / scale
    normalized_query = (query_vector - lower) / scale
    distances = np.sqrt(np.sum((normalized_points - normalized_query) ** 2, axis=1))
    exact = bool(np.any(np.all(np.isclose(matrix, query_vector, rtol=0, atol=1e-8), axis=1)))
    within_marginal = bool(np.all((query_vector >= lower) & (query_vector <= upper)))
    envelope_distance, envelope_dimension = _joint_envelope_distance(normalized_points, normalized_query)
    within_envelope = bool(envelope_distance <= SUPPORT_ENVELOPE_NUMERICAL_TOLERANCE)
    status = (
        "exact_condition_has_label" if exact else
        "outside_target_marginal_range" if not within_marginal else
        "outside_target_joint_envelope" if not within_envelope else
        "inside_target_joint_envelope_unlabeled"
    )
    return {
        "status": status,
        "within_target_marginal_ranges": within_marginal,
        "within_target_joint_envelope": within_envelope,
        "exact_condition_has_label": exact,
        "nearest_distance_normalized": float(distances.min()),
        "joint_envelope_distance_normalized": float(envelope_distance),
        "joint_envelope_dimension": envelope_dimension,
        "distance_semantics": (
            "Distância euclidiana normalizada pelo intervalo marginal do alvo; "
            "não é incerteza calibrada. O suporte conjunto é a envoltória convexa "
            "dos pontos rotulados, sem limiar de distância; tolerância 1e-10 serve apenas à precisão numérica."
        ),
    }


def predict_one(bundle: dict, power_W: float, feed_g_min: float, speed_mm_min: float) -> dict:
    """Prevê respostas contínuas, anota suporte e não estima defeitos."""
    query = {"Power_W": float(power_W), "Feed_g_min": float(feed_g_min), "Speed_mm_min": float(speed_mm_min)}
    q = np.asarray(list(query.values()), dtype=float)
    if not np.isfinite(q).all() or np.any(q <= 0):
        raise ValueError("Potência, alimentação e velocidade devem ser positivas e finitas.")
    raw = pd.DataFrame([query])
    result: dict = {}
    schema = bundle["schema"]
    for target, estimator in bundle["models"].items():
        mode = bundle.get("feature_modes", {}).get(target)
        if bundle.get("bundle_version", 1) < 2:
            mode = "raw" if mode == "raw" else "legacy_physics"
        elif mode is None:
            mode = "physics"
        features = _feature_frame(raw, mode)
        raw_prediction = float(estimator.predict(features)[0])
        prediction = raw_prediction
        if target in {"H_um", "W_um", "h_um", "HW"}:
            prediction = max(0.0, raw_prediction)
        elif target == "DI_pct":
            prediction = float(np.clip(raw_prediction, 0.0, 100.0))
        q90 = float(bundle["diagnostics"][target].get("residual_abs_q90", 0.0))
        upper_bound = 100.0 if target == "DI_pct" else math.inf
        result[target] = {
            "prediction": prediction,
            "raw_prediction": raw_prediction,
            "indicative_low": max(0.0, prediction - q90),
            "indicative_high": min(upper_bound, prediction + q90),
            "cv_q90_abs_error": q90,
            "error_band_semantics": bundle["diagnostics"][target].get("error_band_semantics"),
            "n_training_labels": int(bundle["diagnostics"][target].get("n", 0)),
            "feature_mode": mode,
            "support": _target_support(schema, target, query),
            "provenance": "model_estimate_not_measurement",
        }

    if bundle.get("bundle_version", 1) >= 3:
        def derived_item(target: str, prediction: float, support_target: str, formula_label: str, upper: float = math.inf) -> dict:
            q90 = float(bundle["diagnostics"][target].get("residual_abs_q90", 0.0))
            return {
                "prediction": prediction,
                "raw_prediction": prediction,
                "indicative_low": max(0.0, prediction - q90),
                "indicative_high": min(upper, prediction + q90),
                "cv_q90_abs_error": q90,
                "error_band_semantics": bundle["diagnostics"][target].get("error_band_semantics"),
                "n_training_labels": int(bundle["diagnostics"][target].get("n", 0)),
                "feature_mode": "deterministic_geometry_formula",
                "formula": formula_label,
                "support": _target_support(schema, support_target, query),
                "provenance": "derived_from_predicted_primary_geometry_not_independent_model",
            }

        H = result.get("H_um", {}).get("prediction")
        W = result.get("W_um", {}).get("prediction")
        h = result.get("h_um", {}).get("prediction")
        if H is not None and W is not None and W > 0:
            result["HW"] = derived_item("HW", H / W, "HW", "H_um / W_um")
        if H is not None and h is not None and H > 0 and H + h > 0:
            result["DI_pct"] = derived_item(
                "DI_pct", 100.0 * h / (h + H), "DI_pct", "100 * h_um / (h_um + H_um)", upper=100.0,
            )

    input_ranges = schema.get("input_ranges") or {
        "Power_W": schema.get("power_range_W"),
        "Feed_g_min": schema.get("feed_range_g_min"),
        "Speed_mm_min": schema.get("speed_range_mm_min"),
    }
    observed_rows = schema.get("observed_combinations") or schema.get("target_training_inputs", {}).get("H_um", [])
    if input_ranges and all(input_ranges.get(key) for key in INPUTS):
        within_input = all(input_ranges[key][0] <= query[key] <= input_ranges[key][1] for key in INPUTS)
    else:
        within_input = False
    if observed_rows:
        observed = np.asarray([[float(row[k]) for k in INPUTS] for row in observed_rows], dtype=float)
        scale = np.asarray([input_ranges[k][1] - input_ranges[k][0] for k in INPUTS], dtype=float)
        scale[scale == 0] = 1.0
        distances = np.sqrt(np.sum(((observed - q) / scale) ** 2, axis=1))
        nearest_distance = float(distances.min())
        exact_grid = bool(np.any(np.all(np.isclose(observed, q, rtol=0, atol=1e-8), axis=1)))
    else:
        nearest_distance = None
        exact_grid = False
    result["support_summary"] = {
        "within_input_marginal_ranges": bool(within_input),
        "exact_observed_input_combination": exact_grid,
        "nearest_design_distance_normalized": nearest_distance,
        "interpretation": "Marginal range and nearest-point checks do not establish calibrated confidence or full support in the parameter space.",
    }
    return result
