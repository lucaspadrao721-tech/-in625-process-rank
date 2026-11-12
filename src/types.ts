export const TARGET_KEYS = ["H_um", "W_um", "h_um", "HW", "DI_pct"] as const;
export type TargetKey = (typeof TARGET_KEYS)[number];

export interface Inputs {
  powerW: number | null;
  feedGMin: number | null;
  speedMmMin: number | null;
}

export type SupportStatus =
  | "medicao_rotulada"
  | "sem_rotulo_dentro_das_margens"
  | "sem_rotulo_dentro_do_envelope"
  | "fora_do_envelope_rotulado"
  | "fora_das_margens_de_suporte"
  | "suporte_nao_identificado";

export interface TargetSupport {
  status: SupportStatus;
  withinTargetMarginalRanges: boolean;
  withinTargetJointEnvelope: boolean | null;
  exactConditionHasLabel: boolean;
  nearestDistanceNormalized: number | null;
}

export interface Prediction {
  value: number | null;
  low: number | null;
  high: number | null;
  q90AbsError: number | null;
  nTrainingLabels: number | null;
  support: TargetSupport;
}

export interface Measurement {
  n: number;
  mean: number | null;
  std: number | null;
  min: number | null;
  max: number | null;
}

export interface CandidateScreen {
  pointInsideReference: boolean;
  pointClass: "inside" | "boundary" | "outside" | "unavailable";
  status: string;
  pointViolation: number | null;
  bandViolation: number | null;
  diBandRelation: string;
  hwBandRelation: string;
}

export interface Candidate {
  id: string;
  inputs: Inputs;
  rankEligible: boolean;
  qualityOrder: number | null;
  rankTieCount: number;
  exclusionReasons: string[];
  paretoNondominated: boolean;
  supportLabel: string;
  predictions: Partial<Record<TargetKey, Prediction>>;
  measurements: Partial<Record<TargetKey, Measurement>>;
  screen: CandidateScreen;
}

export interface ModelMetric {
  n: number | null;
  mae: number | null;
  rmse: number | null;
  r2: number | null;
  q90AbsError: number | null;
  oofRows: number;
}

export interface DashboardSummary {
  nCandidates: number | null;
  nRankEligible: number | null;
  nPointInsideReference: number | null;
  nEligiblePointInsideReference: number | null;
  nEligiblePointInsideButBandCrosses: number | null;
  nEligibleWithBothBandsInside: number | null;
  nParetoNondominated: number | null;
  defectProbabilitiesAvailable: boolean;
}

export interface ReferenceWindow {
  diPct: [number, number] | number[];
  hw: [number, number] | number[];
  description: string;
}

export interface DashboardData {
  schemaVersion: 2;
  summary: DashboardSummary;
  window: ReferenceWindow;
  models: Record<TargetKey, ModelMetric>;
  candidates: Candidate[];
  context?: { active: boolean; id: string };
  bandFeasibility?: {
    hwBandCanFit: boolean | null;
    diBandCanFit: boolean | null;
  };
  interpretation: {
    prediction: string;
    measurement: string;
    q90: string;
    defects: string;
  };
}

export const TARGET_INFO: Record<
  TargetKey,
  { label: string; unit: string; digits: number; short: string }
> = {
  H_um: { label: "Altura H", unit: "µm", digits: 1, short: "H" },
  W_um: { label: "Largura W", unit: "µm", digits: 1, short: "W" },
  h_um: { label: "Penetração h", unit: "µm", digits: 1, short: "h" },
  HW: { label: "Razão H/W", unit: "adimensional", digits: 3, short: "H/W" },
  DI_pct: { label: "Diluição DI", unit: "%", digits: 1, short: "DI" },
};
