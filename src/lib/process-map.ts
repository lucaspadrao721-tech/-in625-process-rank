import type { Candidate } from "../types";

export interface ProcessPoint {
  candidate: Candidate;
  energyJMm: number;
  powderMgMm: number;
}

export interface ProcessPointGroup {
  key: string;
  energyJMm: number;
  powderMgMm: number;
  points: ProcessPoint[];
}

export function processPointTone(candidate: Candidate): string {
  const pointClass = candidate.screen.pointClass;
  if (pointClass === "boundary") return "boundary";
  if (pointClass === "unavailable") return "unknown";
  if (!candidate.rankEligible) return "unranked";
  return pointClass;
}

export function processPoint(candidate: Candidate): ProcessPoint | null {
  const { powerW, feedGMin, speedMmMin } = candidate.inputs;
  if (powerW === null || feedGMin === null || speedMmMin === null) return null;
  if (![powerW, feedGMin, speedMmMin].every(Number.isFinite)) return null;
  if (powerW <= 0 || feedGMin <= 0 || speedMmMin <= 0) return null;
  const energyJMm = (60 * powerW) / speedMmMin;
  const powderMgMm = (1000 * feedGMin) / speedMmMin;
  if (![energyJMm, powderMgMm].every(Number.isFinite)) return null;
  return { candidate, energyJMm, powderMgMm };
}

export function groupProcessPoints(rows: Candidate[]): ProcessPointGroup[] {
  const groups = new Map<string, ProcessPointGroup>();
  for (const candidate of rows) {
    const point = processPoint(candidate);
    if (!point) continue;
    // Group only exactly equal numerical projections; nearby points are not
    // rounded together. Equal coordinates do not imply equivalent outcomes.
    const key = `${point.energyJMm}:${point.powderMgMm}`;
    const group = groups.get(key);
    if (group) group.points.push(point);
    else
      groups.set(key, {
        key,
        energyJMm: point.energyJMm,
        powderMgMm: point.powderMgMm,
        points: [point],
      });
  }
  return [...groups.values()];
}

export function axisTicks(maxValue: number): number[] {
  if (!Number.isFinite(maxValue) || maxValue <= 0) return [0, 1];
  const desired = (maxValue * 1.08) / 5;
  const magnitude = 10 ** Math.floor(Math.log10(desired));
  const step =
    ([1, 2, 2.5, 5, 10].find((value) => value * magnitude >= desired) ?? 10) *
    magnitude;
  const intervals = Math.ceil((maxValue * 1.08) / step);
  return Array.from({ length: intervals + 1 }, (_, index) =>
    Number((index * step).toPrecision(12)),
  );
}
