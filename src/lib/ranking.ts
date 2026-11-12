import type { Candidate, CandidateScreen } from "../types";

export type InputFilterKey = "powerW" | "feedGMin" | "speedMmMin";

export function sortByPythonRank(rows: Candidate[]): Candidate[] {
  return [...rows].sort((a, b) => {
    if (a.rankEligible !== b.rankEligible) return a.rankEligible ? -1 : 1;
    const aRank = a.qualityOrder ?? Number.MAX_SAFE_INTEGER;
    const bRank = b.qualityOrder ?? Number.MAX_SAFE_INTEGER;
    return aRank - bRank || a.id.localeCompare(b.id);
  });
}

export function uniqueInputValues(
  rows: Candidate[],
  key: InputFilterKey,
): number[] {
  return [
    ...new Set(
      rows
        .map((row) => row.inputs[key])
        .filter((value): value is number => value !== null),
    ),
  ].sort((a, b) => a - b);
}

export function filterCandidates(
  rows: Candidate[],
  filters: Record<InputFilterKey, string>,
): Candidate[] {
  return rows.filter((row) => {
    const match = (key: InputFilterKey) =>
      filters[key] === "all" || row.inputs[key] === Number(filters[key]);
    return match("powerW") && match("feedGMin") && match("speedMmMin");
  });
}

export function formatNumber(
  value: number | null | undefined,
  digits = 1,
): string {
  if (value === null || value === undefined || !Number.isFinite(value))
    return "—";
  return value.toLocaleString("pt-BR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatReferenceNumber(
  value: number | null | undefined,
  digits: number,
  limits: number[],
): string {
  if (
    value === null ||
    value === undefined ||
    !Number.isFinite(value) ||
    limits.length < 2
  )
    return formatNumber(value, digits);
  const [low, high] = limits;
  if ((value === low || value === high) && value === 1 / 3) return "1/3";
  const classify = (number: number) =>
    number === low || number === high
      ? "boundary"
      : low < number && number < high
        ? "inside"
        : "outside";
  const actualClass = classify(value);
  for (let precision = digits; precision <= 10; precision += 1) {
    if (classify(Number(value.toFixed(precision))) === actualClass)
      return formatNumber(value, precision);
  }
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 20 });
}

export function pointReferenceLabel(screen: CandidateScreen): {
  label: string;
  tone: "inside" | "outside" | "boundary" | "unknown";
} {
  if (
    screen.pointClass === "unavailable" ||
    screen.status === "not_assessable_missing_geometry_prediction"
  )
    return { label: "Ponto não avaliável", tone: "unknown" };
  if (
    screen.pointClass === "boundary" ||
    screen.status === "point_on_strict_reference_boundary"
  )
    return { label: "Ponto no limite", tone: "boundary" };
  return screen.pointInsideReference
    ? { label: "Ponto dentro", tone: "inside" }
    : { label: "Ponto fora", tone: "outside" };
}

export function bandRelationLabel(relation: string): {
  label: string;
  tone: "contained" | "crossing" | "outside" | "unknown";
} {
  const value = relation.toLowerCase();
  if (value.includes("touch"))
    return { label: "A banda toca o limite estrito", tone: "crossing" };
  if (value.includes("cross") || value.includes("intersect")) {
    return { label: "A banda cruza o limite", tone: "crossing" };
  }
  if (
    value.includes("outside") ||
    value.includes("exceed") ||
    value.includes("excede")
  ) {
    return { label: "A banda fica fora da faixa", tone: "outside" };
  }
  if (value.includes("inside") || value.includes("contained")) {
    return { label: "A banda cabe na faixa geométrica", tone: "contained" };
  }
  return { label: "Faixa indisponível", tone: "unknown" };
}

export function supportLabel(status: string): string {
  switch (status) {
    case "medicao_rotulada":
      return "Há rótulo medido";
    case "sem_rotulo_dentro_das_margens":
      return "Sem rótulo neste ponto";
    case "sem_rotulo_dentro_do_envelope":
      return "Dentro do envelope rotulado";
    case "fora_do_envelope_rotulado":
      return "Fora do envelope rotulado";
    case "fora_das_margens_de_suporte":
      return "Fora das margens observadas";
    default:
      return "Suporte não identificado";
  }
}
