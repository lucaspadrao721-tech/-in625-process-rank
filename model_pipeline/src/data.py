"""Leitura, validação dimensional e auditoria da tabela experimental IN625."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import math

import numpy as np
import pandas as pd

COLUMNS = ["Power_W", "Feed_g_min", "Speed_mm_min", "H_um", "h_um", "W_um", "DI_pct", "HW"]
INPUTS = ["Power_W", "Feed_g_min", "Speed_mm_min"]
TARGETS = ["H_um", "W_um", "h_um", "DI_pct", "HW"]
MODEL_TARGETS = ["H_um", "W_um", "h_um"]


def dataframe_fingerprint(data: pd.DataFrame) -> str:
    """Retorna SHA-256 dos valores experimentais normalizados nas colunas COLUMNS.

    O hash inclui ordem de linhas, colunas e rótulos observados; não depende do
    caminho do arquivo nem de colunas auxiliares adicionadas durante a análise.
    """
    missing = [column for column in COLUMNS if column not in data.columns]
    if missing:
        raise ValueError(f"Dataframe sem colunas para fingerprint: {', '.join(missing)}")
    rows = [
        [None if pd.isna(value) else float(value) for value in row]
        for row in data.loc[:, COLUMNS].itertuples(index=False, name=None)
    ]
    canonical = json.dumps(
        {"columns": COLUMNS, "rows": rows},
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _number(value):
    """Converte células do Excel, incluindo hífen, vírgula decimal e separador de milhar."""
    if pd.isna(value):
        return np.nan
    if isinstance(value, (int, float, np.integer, np.floating)):
        number = float(value)
        return number if math.isfinite(number) else np.nan
    text = str(value).strip().replace("\u00a0", "")
    if text in {"", "-", "—", "–", "nan", "None"}:
        return np.nan
    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        result = float(text)
        return result if math.isfinite(result) else np.nan
    except ValueError:
        return np.nan


def load_dataset(path: str | Path) -> pd.DataFrame:
    """Carrega a primeira aba: linha 1 contém cabeçalhos, linha 2 unidades.

    Entradas duplicadas são permitidas como réplicas, mas recebem o mesmo
    condition_group para que não apareçam simultaneamente em treino e teste.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Planilha não encontrada: {path}")
    raw = pd.read_excel(path, sheet_name=0, header=None, engine="openpyxl")
    if raw.shape[1] < 9 or raw.shape[0] < 3:
        raise ValueError("A planilha não contém as 9 colunas e as linhas esperadas.")

    data = raw.iloc[2:, 1:9].copy()
    data.columns = COLUMNS
    for column in COLUMNS:
        data[column] = data[column].map(_number)
    for column in ("Power_W", "Feed_g_min"):
        data[column] = data[column].ffill()
    data = data.dropna(how="all", subset=COLUMNS).reset_index(drop=True)

    if data[INPUTS].isna().any(axis=1).any():
        bad = data.index[data[INPUTS].isna().any(axis=1)].tolist()
        raise ValueError(f"Entradas de processo ausentes nas linhas de dados: {bad}")
    if data[["H_um", "W_um", "HW"]].isna().any().any():
        raise ValueError("H, W e H/W precisam estar presentes em todas as linhas desta tabela.")
    if (data[["Power_W", "Feed_g_min", "Speed_mm_min", "H_um", "W_um"]] <= 0).any().any():
        raise ValueError("Potência, alimentação, velocidade, H e W precisam ser positivos.")
    if (data["h_um"].dropna() < 0).any():
        raise ValueError("A penetração h, quando observada, não pode ser negativa.")
    if (~data["DI_pct"].dropna().between(0.0, 100.0)).any():
        raise ValueError("DI (%) observado deve estar entre 0 e 100.")

    data["HW_calc"] = data["H_um"] / data["W_um"]
    valid_di = data["h_um"].notna()
    data["DI_calc"] = np.nan
    data.loc[valid_di, "DI_calc"] = 100.0 * data.loc[valid_di, "h_um"] / (
        data.loc[valid_di, "h_um"] + data.loc[valid_di, "H_um"]
    )
    # Um ID identifica cada linha; condition_group identifica a condição P/F/v.
    data["condition_group"] = pd.MultiIndex.from_frame(data[INPUTS].astype(float)).factorize(sort=False)[0] + 1
    data["record_id"] = np.arange(1, len(data) + 1)
    return data


def quality_report(data: pd.DataFrame) -> dict:
    """Cobertura, níveis experimentais, réplicas e coerência das variáveis derivadas."""
    hw_valid = data["HW"].notna() & data["HW_calc"].notna()
    di_valid = data["DI_pct"].notna() & data["DI_calc"].notna()
    group_counts = data.groupby("condition_group").size()
    return {
        "n_rows": int(len(data)),
        "n_unique_conditions": int(data["condition_group"].nunique()),
        "n_replicate_rows_beyond_first": int(len(data) - data["condition_group"].nunique()),
        "max_replicates_per_condition": int(group_counts.max()) if len(group_counts) else 0,
        "target_counts": {target: int(data[target].notna().sum()) for target in TARGETS},
        "input_levels": {column: sorted(float(v) for v in data[column].unique()) for column in INPUTS},
        "hw_max_abs_error": float((data.loc[hw_valid, "HW"] - data.loc[hw_valid, "HW_calc"]).abs().max()) if hw_valid.any() else None,
        "di_max_abs_error_percentage_points": float((data.loc[di_valid, "DI_pct"] - data.loc[di_valid, "DI_calc"]).abs().max()) if di_valid.any() else None,
        "missing_by_target": {target: int(data[target].isna().sum()) for target in TARGETS},
        "derived_target_notes": {
            "HW": "A coluna H/W coincide com H/W; é uma resposta derivada, não medição independente.",
            "DI_pct": "A fórmula 100*h/(h+H) coincide nas linhas disponíveis e segue a definição do estudo compatível se h for profundidade de penetração.",
        },
        "source_unit_note": "A unidade da alimentação foi confirmada pelo usuário como g/min. A anotação g/mm na planilha é inconsistente e não é usada pelo pipeline; derivados nominais usam g/min.",
        "design_note": "Rótulos ausentes não são imputados como medições. Réplicas da mesma condição ficam agrupadas na validação por combinação.",
    }
