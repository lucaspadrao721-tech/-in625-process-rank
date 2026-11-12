import { TARGET_KEYS, TARGET_INFO } from "../types";
import type { DashboardData } from "../types";
import { formatNumber } from "../lib/ranking";

interface Props {
  data: DashboardData;
}

export default function QualityPanel({ data }: Props) {
  const summary = data.summary;
  const hwQ90 = data.models.HW.q90AbsError;
  const hwWidth = data.window.hw[1] - data.window.hw[0];
  const hwBandTooWide =
    hwQ90 !== null && Number.isFinite(hwQ90) && 2 * hwQ90 >= hwWidth;
  return (
    <section className="quality-panel" aria-labelledby="quality-title">
      <div className="quality-heading">
        <div>
          <p className="eyebrow">DESEMPENHO PREDITIVO · NESTED-GROUP-OOF</p>
          <h2 id="quality-title">Qualidade dos resultados</h2>
        </div>
        <span className="validation-stamp">VALIDAÇÃO FORA DA DOBRA</span>
      </div>
      <p className="quality-intro">
        Métricas estimadas em validação cruzada agrupada por condição. MAE e Q90
        são erros observados fora da dobra, não garantias para novos materiais,
        equipamentos ou campanhas.
      </p>

      <div className="quality-grid">
        {TARGET_KEYS.map((target) => {
          const metric = data.models[target];
          const info = TARGET_INFO[target];
          const errorDigits = target === "DI_pct" ? 2 : info.digits;
          const errorUnit = target === "DI_pct" ? "p.p." : info.unit;
          return (
            <article
              className={`quality-card ${metric.n !== null && metric.n < 48 ? "quality-card-limited" : ""}`}
              key={target}
            >
              <div className="quality-card-top">
                <span>{info.short}</span>
                <small>{info.label}</small>
              </div>
              <div className="quality-n">
                n = <b>{metric.n ?? "—"}</b> rótulos
              </div>
              <div className="quality-stat">
                <span>MAE OOF</span>
                <strong>
                  {formatNumber(metric.mae, errorDigits)}{" "}
                  <small>{errorUnit}</small>
                </strong>
              </div>
              <div className="quality-stat">
                <span>R² OOF</span>
                <strong>{formatNumber(metric.r2, 3)}</strong>
              </div>
              <div className="quality-stat quality-q90">
                <span>Q90 |erro|</span>
                <strong>
                  {formatNumber(metric.q90AbsError, errorDigits)}{" "}
                  <small>{errorUnit}</small>
                </strong>
              </div>
              {metric.n !== null && metric.n < 48 && (
                <div className="coverage-alert">
                  Cobertura menor: {metric.n} de 48 condições rotuladas.
                </div>
              )}
            </article>
          );
        })}
      </div>

      <div className="quality-callouts">
        <article className="quality-callout quality-callout-alert">
          <span className="callout-value">
            {summary.nEligibleWithBothBandsInside ?? 0}
            <small> / {summary.nRankEligible ?? 0}</small>
          </span>
          <div>
            <strong>Bandas DI + H/W inteiramente na faixa</strong>
            <p>
              {hwBandTooWide
                ? "A banda global de H/W é maior que a faixa de referência. Zero contenções não significa zero condições viáveis."
                : "Contenção pelo critério conjunto atual; não representa garantia de qualidade."}
            </p>
          </div>
        </article>
        <article className="quality-callout">
          <span className="callout-value">
            48 <small>→</small> 22
          </span>
          <div>
            <strong>Cobertura desigual</strong>
            <p>
              H/W têm 48 rótulos; h e DI têm 22. A menor cobertura deve pesar na
              leitura das estimativas de penetração e diluição.
            </p>
          </div>
        </article>
      </div>

      <div className="q90-note">
        <span>Q90</span>
        <p>
          Quantil empírico do erro absoluto de validação OOF. A banda é
          indicativa — não é intervalo de confiança/conformal e não representa
          probabilidade de ficar dentro da faixa ou de ocorrer um defeito.
        </p>
      </div>
      <div className="quality-footnote">
        DI: erros em pontos percentuais (p.p.). H/W e DI são alvos geométricos
        derivados das previsões OOF componentes; valores ausentes não são
        imputados como zero.
      </div>
    </section>
  );
}
