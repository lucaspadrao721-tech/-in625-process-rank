import type { Candidate, ReferenceWindow } from "../types";
import {
  formatNumber,
  formatReferenceNumber,
  pointReferenceLabel,
} from "../lib/ranking";

interface Props {
  rows: Candidate[];
  reference: ReferenceWindow;
  selectedId: string | null;
  onSelect: (candidateId: string) => void;
}

export default function ResultsTable({
  rows,
  reference,
  selectedId,
  onSelect,
}: Props) {
  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <strong>Nenhuma condição nesta vista.</strong>
        <span>
          Limpe os filtros ou volte ao ranking de qualidade-prioridade.
        </span>
      </div>
    );
  }

  return (
    <div className="table-scroll">
      <table className="results-table">
        <thead>
          <tr>
            <th scope="col">Rank</th>
            <th scope="col">Condição · P / F / v</th>
            <th scope="col">DI prevista</th>
            <th scope="col">H/W previsto</th>
            <th scope="col">Triagem pontual</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const selected = row.id === selectedId;
            const di = row.predictions.DI_pct?.value ?? null;
            const hw = row.predictions.HW?.value ?? null;
            const screenLabel = pointReferenceLabel(row.screen);
            const rowLabel = `${row.id}, ${formatNumber(row.inputs.powerW, 0)} watts, ${formatNumber(row.inputs.feedGMin, 1)} gramas por minuto, ${formatNumber(row.inputs.speedMmMin, 0)} milímetros por minuto`;
            return (
              <tr
                key={row.id}
                className={`${selected ? "row-selected" : ""} ${row.rankEligible ? "" : "row-unranked"}`}
              >
                <td className="rank-cell">
                  <button
                    type="button"
                    className="rank-button"
                    aria-label={`Selecionar ${rowLabel}; posição ${row.qualityOrder ?? "não classificada"}`}
                    aria-pressed={selected}
                    onClick={() => onSelect(row.id)}
                  >
                    {row.rankEligible && row.qualityOrder !== null
                      ? String(row.qualityOrder).padStart(2, "0")
                      : "—"}
                  </button>
                  {row.rankEligible && row.rankTieCount > 1 && (
                    <small
                      className="rank-tie"
                      title={`${row.rankTieCount} condições com a mesma prioridade nos critérios.`}
                    >
                      empate ×{row.rankTieCount}
                    </small>
                  )}
                </td>
                <td>
                  <button
                    type="button"
                    className="condition-button"
                    aria-pressed={selected}
                    onClick={() => onSelect(row.id)}
                  >
                    <strong>{formatNumber(row.inputs.powerW, 0)} W</strong>
                    <span>
                      {formatNumber(row.inputs.feedGMin, 1)} g/min <i>·</i>{" "}
                      {formatNumber(row.inputs.speedMmMin, 0)} mm/min
                    </span>
                    <small>{row.id}</small>
                  </button>
                </td>
                <td className="numeric-cell">
                  {formatReferenceNumber(di, 1, reference.diPct)}
                  <small>%</small>
                </td>
                <td className="numeric-cell">
                  {formatReferenceNumber(hw, 3, reference.hw)}
                </td>
                <td>
                  <span className={`status-text status-${screenLabel.tone}`}>
                    {screenLabel.label}
                  </span>
                </td>
                <td className="status-cell">
                  {!row.rankEligible && (
                    <span
                      className="tag tag-muted"
                      title={row.exclusionReasons?.join(" · ")}
                    >
                      Não classificada
                    </span>
                  )}
                  {row.paretoNondominated && (
                    <span className="tag tag-pareto">Pareto</span>
                  )}
                  {row.rankEligible && !row.paretoNondominated && (
                    <span className="tag tag-ranked">Classificada</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
