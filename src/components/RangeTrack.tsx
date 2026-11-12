import {
  bandRelationLabel,
  formatNumber,
  formatReferenceNumber,
} from "../lib/ranking";

interface Props {
  label: string;
  unit: string;
  value: number | null;
  low: number | null;
  high: number | null;
  limits: [number, number] | number[];
  relation: string;
  digits?: number;
}

function clamp(value: number): number {
  return Math.max(0, Math.min(100, value));
}

export default function RangeTrack({
  label,
  unit,
  value,
  low,
  high,
  limits,
  relation,
  digits = 1,
}: Props) {
  if (value === null || low === null || high === null || limits.length < 2) {
    return (
      <div className="range-track range-track-unknown">
        <div className="range-track-heading">
          <strong>{label}</strong>
          <span>Faixa indisponível</span>
        </div>
      </div>
    );
  }

  const min = Number(limits[0]);
  const max = Number(limits[1]);
  const span = Math.max(max - min, 0.000001);
  const domainMin = Math.min(min, low) - span * 0.12;
  const domainMax = Math.max(max, high) + span * 0.12;
  const position = (number: number) =>
    clamp(((number - domainMin) / (domainMax - domainMin)) * 100);
  const status = bandRelationLabel(relation);
  const bandLeft = position(Math.min(low, high));
  const bandRight = position(Math.max(low, high));

  return (
    <div className={`range-track tone-${status.tone}`}>
      <div className="range-track-heading">
        <strong>{label}</strong>
        <span>{status.label}</span>
      </div>
      <div
        className="range-plot"
        role="img"
        aria-label={`${label}: estimativa ${formatReferenceNumber(value, digits, limits)} ${unit}; banda indicativa ${formatReferenceNumber(low, digits, limits)} a ${formatReferenceNumber(high, digits, limits)} ${unit}; faixa geométrica estrita de ${formatReferenceNumber(min, digits, limits)} a ${formatReferenceNumber(max, digits, limits)} ${unit}`}
      >
        <div
          className="range-reference"
          style={{
            left: `${position(min)}%`,
            width: `${Math.max(0, position(max) - position(min))}%`,
          }}
        />
        <div
          className="range-band"
          style={{
            left: `${bandLeft}%`,
            width: `${Math.max(1, bandRight - bandLeft)}%`,
          }}
        />
        <span className="range-point" style={{ left: `${position(value)}%` }} />
      </div>
      <div className="range-scale">
        <span>{formatNumber(domainMin, digits)}</span>
        <span className="range-limit-label">
          referência {formatReferenceNumber(min, digits, limits)}–
          {formatReferenceNumber(max, digits, limits)} {unit}
        </span>
        <span>{formatNumber(domainMax, digits)}</span>
      </div>
      <p className="range-value">
        Ponto{" "}
        <b>
          {formatReferenceNumber(value, digits, limits)} {unit}
        </b>
        <span>
          Q90 indicativa {formatReferenceNumber(low, digits, limits)}–
          {formatReferenceNumber(high, digits, limits)} {unit}
        </span>
      </p>
    </div>
  );
}
