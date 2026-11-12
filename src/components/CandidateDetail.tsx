import type { Candidate, DashboardData, TargetKey } from "../types";
import { TARGET_INFO } from "../types";
import {
  bandRelationLabel,
  formatNumber,
  formatReferenceNumber,
  pointReferenceLabel,
  supportLabel,
} from "../lib/ranking";
import RangeTrack from "./RangeTrack";

interface Props {
  candidate: Candidate;
  data: DashboardData;
}

const DETAIL_TARGETS: TargetKey[] = ["H_um", "W_um", "h_um", "DI_pct"];

export default function CandidateDetail({ candidate, data }: Props) {
  const di = candidate.predictions.DI_pct;
  const hw = candidate.predictions.HW;
  const screenLabel = pointReferenceLabel(candidate.screen);

  return (
    <aside className="detail-panel" aria-labelledby="detail-title">
      <div className="detail-head">
        <div>
          <p className="eyebrow">INSPEÇÃO DA CONDIÇÃO</p>
          <h2 id="detail-title">{candidate.id}</h2>
        </div>
        {candidate.rankEligible && candidate.qualityOrder !== null ? (
          <span className="rank-badge">
            RANK <b>{String(candidate.qualityOrder).padStart(2, "0")}</b>
          </span>
        ) : (
          <span className="tag tag-muted">Não classificada</span>
        )}
      </div>

      <div className="detail-inputs">
        <div>
          <span>Potência</span>
          <b>
            {formatNumber(candidate.inputs.powerW, 0)} <small>W</small>
          </b>
        </div>
        <div>
          <span>Alimentação</span>
          <b>
            {formatNumber(candidate.inputs.feedGMin, 1)} <small>g/min</small>
          </b>
        </div>
        <div>
          <span>Velocidade</span>
          <b>
            {formatNumber(candidate.inputs.speedMmMin, 0)} <small>mm/min</small>
          </b>
        </div>
      </div>

      <div className="detail-flags">
        <span className={`status-text status-${screenLabel.tone}`}>
          {screenLabel.label}
        </span>
        {candidate.paretoNondominated && (
          <span className="tag tag-pareto">Não dominada</span>
        )}
      </div>

      {candidate.rankEligible && candidate.rankTieCount > 1 && (
        <div className="exclusion-reasons">
          <span className="tag tag-ranked">
            Mesma prioridade · {candidate.rankTieCount} condições
          </span>
        </div>
      )}
      {!candidate.rankEligible && candidate.exclusionReasons?.length > 0 && (
        <div className="exclusion-reasons">
          {candidate.exclusionReasons.map((reason) => (
            <span className="tag tag-muted" key={reason}>
              {reason}
            </span>
          ))}
        </div>
      )}

      <div className="geometry-window">
        <div className="window-title">
          <span>FAIXA GEOMÉTRICA DO ESTUDO</span>
          <span>Não universal</span>
        </div>
        <p>
          {formatNumber(data.window.diPct[0], 0)} &lt; DI &lt;{" "}
          {formatNumber(data.window.diPct[1], 0)}% <i>·</i>{" "}
          {formatNumber(data.window.hw[0], 2)} &lt; H/W &lt;{" "}
          {formatReferenceNumber(data.window.hw[1], 3, data.window.hw)}
        </p>
        <span className="window-note">
          Triagem de descritores geométricos; não é probabilidade de
          conformidade nem diagnóstico de defeito.
        </span>
      </div>

      <div className="detail-metrics">
        {DETAIL_TARGETS.map((target) => {
          const info = TARGET_INFO[target];
          const estimate = candidate.predictions[target];
          const measurement = candidate.measurements[target];
          return (
            <article className="detail-metric" key={target}>
              <div className="metric-title-row">
                <strong>{info.label}</strong>
                <span className="predicted-label">PREVISÃO</span>
              </div>
              <div className="metric-main">
                {target === "DI_pct"
                  ? formatReferenceNumber(
                      estimate?.value,
                      info.digits,
                      data.window.diPct,
                    )
                  : formatNumber(estimate?.value, info.digits)}{" "}
                <small>{info.unit}</small>
              </div>
              <div className="metric-band">
                Banda Q90 indicativa{" "}
                <b>
                  {formatNumber(estimate?.low, info.digits)}–
                  {formatNumber(estimate?.high, info.digits)} {info.unit}
                </b>
              </div>
              <div className="metric-support">
                {estimate
                  ? supportLabel(estimate.support.status)
                  : "Sem suporte reportado"}{" "}
                <span>· n={estimate?.nTrainingLabels ?? "—"} rótulos</span>
              </div>
              {estimate?.support.withinTargetJointEnvelope === false &&
                estimate.support.status !== "fora_do_envelope_rotulado" && (
                  <div className="metric-support">
                    <span>Fora do envelope rotulado</span>
                  </div>
                )}
              <div className="measurement-row">
                <span>Média medida no treino</span>
                <b>
                  {measurement && measurement.n > 0 && measurement.mean !== null
                    ? `${formatNumber(measurement.mean, info.digits)} ${info.unit} · n=${measurement.n}`
                    : "Sem rótulo nesta condição"}
                </b>
              </div>
            </article>
          );
        })}
      </div>

      <p className="measurement-caveat">
        A média medida acima pertence aos dados usados no treino; não é uma
        validação independente da previsão. O desempenho fora da amostra aparece
        na visão “Qualidade OOF”.
      </p>

      <div className="range-section">
        <div className="range-section-title">
          <p className="eyebrow">PONTO × INCERTEZA</p>
          <span>estimativa e banda empírica</span>
        </div>
        {di && (
          <RangeTrack
            label="Diluição DI"
            unit="%"
            value={di.value}
            low={di.low}
            high={di.high}
            limits={data.window.diPct}
            relation={candidate.screen.diBandRelation}
            digits={1}
          />
        )}
        {hw && (
          <RangeTrack
            label="Razão H/W"
            unit=""
            value={hw.value}
            low={hw.low}
            high={hw.high}
            limits={data.window.hw}
            relation={candidate.screen.hwBandRelation}
            digits={3}
          />
        )}
        <div className="band-callout">
          <strong>
            {bandRelationLabel(candidate.screen.diBandRelation).label}
          </strong>
          <span>
            DI e H/W são descritores geométricos. As bandas Q90 não são
            intervalos calibrados nem probabilidades.
          </span>
        </div>
      </div>

      <div className="defect-boundary">
        <span className="boundary-indicator" /> Probabilidade de defeito:{" "}
        <b>não estimável</b> com os dados atuais.
      </div>
    </aside>
  );
}
