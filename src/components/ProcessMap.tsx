import { useId, useMemo } from "react";
import type { KeyboardEvent } from "react";
import type { Candidate } from "../types";
import { formatNumber, pointReferenceLabel } from "../lib/ranking";
import {
  axisTicks,
  groupProcessPoints,
  processPointTone,
  processPoint,
} from "../lib/process-map";
import type { ProcessPointGroup } from "../lib/process-map";

interface Props {
  rows: Candidate[];
  domainRows: Candidate[];
  selectedId: string | null;
  onSelect: (candidateId: string) => void;
}

const LEFT = 64;
const TOP = 48;
const WIDTH = 460;
const HEIGHT = 310;
const RIGHT = LEFT + WIDTH;
const BOTTOM = TOP + HEIGHT;

function pointTone(candidate: Candidate): string {
  return processPointTone(candidate);
}

function pointLabel(candidate: Candidate): string {
  const rank = candidate.rankEligible
    ? `rank ${candidate.qualityOrder}`
    : "sem classificação";
  return `${candidate.id}: ${formatNumber(candidate.inputs.powerW, 0)} W; ${formatNumber(candidate.inputs.feedGMin, 1)} g/min; ${formatNumber(candidate.inputs.speedMmMin, 0)} mm/min; ${rank}; ${pointReferenceLabel(candidate.screen).label}`;
}

export default function ProcessMap({
  rows,
  domainRows,
  selectedId,
  onSelect,
}: Props) {
  const gradientId = useId().replace(/:/g, "");
  const groups = useMemo(() => groupProcessPoints(rows), [rows]);
  const ticks = useMemo(() => {
    const points = domainRows
      .map(processPoint)
      .filter((point) => point !== null);
    return {
      x: axisTicks(Math.max(1, ...points.map((point) => point.energyJMm))),
      y: axisTicks(Math.max(1, ...points.map((point) => point.powderMgMm))),
    };
  }, [domainRows]);
  const xMax = ticks.x[ticks.x.length - 1];
  const yMax = ticks.y[ticks.y.length - 1];
  const x = (value: number) => LEFT + (value / xMax) * WIDTH;
  const y = (value: number) => BOTTOM - (value / yMax) * HEIGHT;
  const selectedGroup = groups.find((group) =>
    group.points.some((point) => point.candidate.id === selectedId),
  );
  const selectedPoint = selectedGroup?.points.find(
    (point) => point.candidate.id === selectedId,
  );

  const selectNext = (group: ProcessPointGroup, offset: number) => {
    const current = group.points.findIndex(
      (point) => point.candidate.id === selectedId,
    );
    const index =
      current < 0
        ? 0
        : (current + offset + group.points.length) % group.points.length;
    onSelect(group.points[index].candidate.id);
  };

  const handleKey = (
    event: KeyboardEvent<SVGGElement>,
    group: ProcessPointGroup,
  ) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(
        group.points.find((point) => point.candidate.id === selectedId)
          ?.candidate.id ?? group.points[0].candidate.id,
      );
    } else if (
      ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)
    ) {
      event.preventDefault();
      selectNext(
        group,
        ["ArrowRight", "ArrowDown"].includes(event.key) ? 1 : -1,
      );
    }
  };

  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <strong>Nenhuma condição nesta vista.</strong>
        <span>Limpe os filtros para visualizar o mapa.</span>
      </div>
    );
  }

  return (
    <div className="process-map">
      <div className="map-heading">
        <strong>Mapa energia–material</strong>
        <span title="Energia incidente e pó alimentado, não energia absorvida ou material efetivamente depositado.">
          INDICADORES NOMINAIS
        </span>
      </div>
      <svg
        className="process-map-svg"
        viewBox="0 0 556 426"
        aria-labelledby={`${gradientId}-title ${gradientId}-desc`}
      >
        <title id={`${gradientId}-title`}>
          Energia linear e pó alimentado por comprimento
        </title>
        <desc id={`${gradientId}-desc`}>
          O fundo indica tendências conceituais, sem fronteiras calibradas de
          defeito. As cores dos pontos vêm da triagem geométrica. Selecione por
          clique, Enter ou espaço. Setas alternam condições sobrepostas. A
          escala permanece a mesma após os filtros.
        </desc>
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffc477" stopOpacity=".13" />
            <stop offset="47%" stopColor="#101d24" stopOpacity="0" />
            <stop offset="58%" stopColor="#101d24" stopOpacity="0" />
            <stop offset="100%" stopColor="#ff897e" stopOpacity=".14" />
          </linearGradient>
        </defs>
        <rect
          x={LEFT}
          y={TOP}
          width={WIDTH}
          height={HEIGHT}
          fill={`url(#${gradientId})`}
        />
        {ticks.x.map((value) => (
          <g key={`x-${value}`} className="map-grid">
            <line x1={x(value)} x2={x(value)} y1={TOP} y2={BOTTOM} />
            <text x={x(value)} y={BOTTOM + 19} textAnchor="middle">
              {formatNumber(value, Number.isInteger(value) ? 0 : 1)}
            </text>
          </g>
        ))}
        {ticks.y.map((value) => (
          <g key={`y-${value}`} className="map-grid">
            <line x1={LEFT} x2={RIGHT} y1={y(value)} y2={y(value)} />
            <text x={LEFT - 10} y={y(value) + 3} textAnchor="end">
              {formatNumber(value, Number.isInteger(value) ? 0 : 1)}
            </text>
          </g>
        ))}
        <rect
          className="map-frame"
          x={LEFT}
          y={TOP}
          width={WIDTH}
          height={HEIGHT}
        />
        <text
          className="map-axis-label"
          x={(LEFT + RIGHT) / 2}
          y={BOTTOM + 48}
          textAnchor="middle"
        >
          Energia linear · E_L = 60P/v [J/mm]
        </text>
        <text
          className="map-axis-label"
          transform={`translate(17 ${(TOP + BOTTOM) / 2}) rotate(-90)`}
          textAnchor="middle"
        >
          Pó por comprimento · m_L [mg/mm]
        </text>
        <g className="map-tendency map-tendency-low" aria-hidden="true">
          <text x={LEFT + 12} y={TOP + 17}>
            ENERGIA / MATERIAL ↓
          </text>
          <text x={LEFT + 12} y={TOP + 31}>
            Tendência à subfusão
          </text>
        </g>
        <g className="map-tendency map-tendency-high" aria-hidden="true">
          <text x={RIGHT - 12} y={BOTTOM - 27} textAnchor="end">
            ENERGIA / MATERIAL ↑
          </text>
          <text x={RIGHT - 12} y={BOTTOM - 13} textAnchor="end">
            Tendência ao excesso
          </text>
        </g>
        {groups.map((group) => {
          const selected = group.points.some(
            (point) => point.candidate.id === selectedId,
          );
          const representative =
            group.points.find((point) => point.candidate.id === selectedId) ??
            group.points[0];
          const candidate = representative.candidate;
          const multiple = group.points.length > 1;
          return (
            <g
              key={group.key}
              className={`map-point map-point-${pointTone(candidate)} ${selected ? "map-point-selected" : ""}`}
              transform={`translate(${x(group.energyJMm)} ${y(group.powderMgMm)})`}
              role="button"
              tabIndex={0}
              aria-label={`${pointLabel(candidate)}${multiple ? `; ${group.points.length} condições nesta coordenada, use setas para alternar` : ""}`}
              aria-pressed={selected}
              onClick={() => onSelect(candidate.id)}
              onKeyDown={(event) => handleKey(event, group)}
            >
              <title>
                {group.points
                  .map((point) => pointLabel(point.candidate))
                  .join("\n")}
                {"\n"}E_L = {formatNumber(group.energyJMm, 2)} J/mm · m_L ={" "}
                {formatNumber(group.powderMgMm, 2)} mg/mm
                {candidate.exclusionReasons?.length
                  ? `\n${candidate.exclusionReasons.join(" · ")}`
                  : ""}
              </title>
              <circle className="map-hit-area" r={14} fill="transparent" />
              {selected && (
                <circle className="map-selection-ring" r={multiple ? 13 : 11} />
              )}
              {candidate.paretoNondominated && (
                <rect
                  className="map-pareto-ring"
                  x={-9}
                  y={-9}
                  width={18}
                  height={18}
                  transform="rotate(45)"
                />
              )}
              <circle className="map-marker" r={multiple ? 8 : 5.5} />
              {multiple && (
                <text
                  className="map-overlap-count"
                  y={3}
                  textAnchor="middle"
                  aria-hidden="true"
                >
                  {group.points.length}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <div className="map-legend" aria-label="Legenda do mapa">
        <span>
          <i className="map-key map-key-inside" /> Ponto dentro
        </span>
        <span>
          <i className="map-key map-key-outside" /> Ponto fora
        </span>
        {rows.some(
          (row) => pointReferenceLabel(row.screen).tone === "boundary",
        ) && (
          <span>
            <i className="map-key map-key-boundary" /> No limite
          </span>
        )}
        <span>
          <i className="map-key map-key-unranked" /> Sem classificação
        </span>
        <span>
          <i className="legend-pareto" /> Pareto
        </span>
      </div>
      {selectedPoint && (
        <div className="map-selected-values">
          <b>{selectedPoint.candidate.id}</b>
          <span>
            E_L <strong>{formatNumber(selectedPoint.energyJMm, 2)}</strong> J/mm
          </span>
          <span>
            m_L <strong>{formatNumber(selectedPoint.powderMgMm, 2)}</strong>{" "}
            mg/mm
          </span>
        </div>
      )}
      {selectedGroup && selectedGroup.points.length > 1 && (
        <div
          className="map-overlap-options"
          aria-label="Condições na mesma coordenada"
        >
          <span>Nesta coordenada:</span>
          {selectedGroup.points.map(({ candidate }) => (
            <button
              key={candidate.id}
              type="button"
              aria-pressed={candidate.id === selectedId}
              onClick={() => onSelect(candidate.id)}
            >
              {candidate.id}
            </button>
          ))}
        </div>
      )}
      <p className="map-caption">
        Fundo conceitual, sem fronteiras de defeito calibradas. Cores dos
        pontos: triagem calculada.
      </p>
    </div>
  );
}
