import { useEffect, useMemo, useState } from "react";
import CandidateDetail from "./components/CandidateDetail";
import ProcessMap from "./components/ProcessMap";
import QualityPanel from "./components/QualityPanel";
import ResultsTable from "./components/ResultsTable";
import {
  filterCandidates,
  formatNumber,
  sortByPythonRank,
  uniqueInputValues,
} from "./lib/ranking";
import type { Candidate, DashboardData } from "./types";
import type { InputFilterKey } from "./lib/ranking";

const EMPTY_FILTERS: Record<InputFilterKey, string> = {
  powerW: "all",
  feedGMin: "all",
  speedMmMin: "all",
};
type MainView = "ranking" | "quality";
type RankMode = "quality" | "pareto";
type ResultsView = "table" | "map";

function SummaryCard({
  label,
  value,
  foot,
  accent = false,
}: {
  label: string;
  value: string;
  foot: string;
  accent?: boolean;
}) {
  return (
    <article className={`summary-card ${accent ? "summary-card-accent" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{foot}</small>
    </article>
  );
}

function LoadingState() {
  return (
    <main className="loading-state">
      <div className="brand-mark" aria-hidden="true">
        <i />
        <i />
        <i />
      </div>
      <p>Carregando o snapshot do ranking…</p>
    </main>
  );
}

function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [view, setView] = useState<MainView>("ranking");
  const [rankMode, setRankMode] = useState<RankMode>("quality");
  const [resultsView, setResultsView] = useState<ResultsView>("table");
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [includeExcluded, setIncludeExcluded] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetch(`${import.meta.env.BASE_URL}data/ranking.json`, { cache: "no-cache" })
      .then(async (response) => {
        if (!response.ok)
          throw new Error(`Falha ao carregar os dados (${response.status}).`);
        const payload = (await response.json()) as DashboardData;
        if (
          payload.schemaVersion !== 2 ||
          !Array.isArray(payload.candidates) ||
          !payload.summary
        ) {
          throw new Error(
            "O snapshot não corresponde ao formato Process Rank.",
          );
        }
        if (active) setData(payload);
      })
      .catch((error: unknown) => {
        if (active)
          setLoadError(
            error instanceof Error
              ? error.message
              : "Não foi possível abrir o ranking.",
          );
      });
    return () => {
      active = false;
    };
  }, []);

  const candidatePool = useMemo(() => {
    if (!data) return [];
    const ranked = data.candidates.filter(
      (candidate) => candidate.rankEligible,
    );
    const base =
      rankMode === "pareto"
        ? ranked.filter((candidate) => candidate.paretoNondominated)
        : includeExcluded
          ? data.candidates
          : ranked;
    return filterCandidates(sortByPythonRank(base), filters);
  }, [data, rankMode, includeExcluded, filters]);

  const selected: Candidate | null =
    candidatePool.find((candidate) => candidate.id === selectedId) ??
    candidatePool[0] ??
    null;
  const allRows = data?.candidates ?? [];
  const powers = uniqueInputValues(allRows, "powerW");
  const feeds = uniqueInputValues(allRows, "feedGMin");
  const speeds = uniqueInputValues(allRows, "speedMmMin");
  const setFilter = (key: InputFilterKey, value: string) =>
    setFilters((current) => ({ ...current, [key]: value }));
  const clearFilters = () => {
    setFilters(EMPTY_FILTERS);
    setIncludeExcluded(false);
  };

  if (!data && !loadError) return <LoadingState />;
  if (loadError || !data) {
    return (
      <main className="error-state">
        <p className="eyebrow">LEITURA DO SNAPSHOT</p>
        <h1>Não foi possível abrir o ranking.</h1>
        <p>{loadError ?? "O arquivo de dados não está disponível."}</p>
        <button
          type="button"
          className="button-secondary"
          onClick={() => window.location.reload()}
        >
          Tentar novamente
        </button>
      </main>
    );
  }

  const summary = data.summary;
  const ranks = summary.nRankEligible ?? 0;
  const rowsLabel =
    rankMode === "pareto"
      ? "alternativas não dominadas"
      : includeExcluded
        ? "condições da grade"
        : "condições elegíveis";

  return (
    <div className="console-shell">
      <header className="console-header">
        <a
          className="brand"
          href="#inicio"
          aria-label="IN625 Process Rank — início"
        >
          <span className="brand-mark" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span className="brand-name">
            IN625 <b>/</b> PROCESS RANK
          </span>
        </a>
        <div className="header-meta">
          <span className="system-dot" /> DED-LB <i>·</i> INCONEL 625 <i>·</i>{" "}
          GRADE ESTÁTICA
        </div>
        <nav className="main-tabs" aria-label="Visões do painel">
          <button
            type="button"
            className={view === "ranking" ? "tab-active" : ""}
            aria-pressed={view === "ranking"}
            onClick={() => setView("ranking")}
          >
            Ranking
          </button>
          <button
            type="button"
            className={view === "quality" ? "tab-active" : ""}
            aria-pressed={view === "quality"}
            onClick={() => setView("quality")}
          >
            Qualidade OOF
          </button>
        </nav>
      </header>

      <main id="inicio">
        <section className="console-intro">
          <div>
            <p className="eyebrow">
              PROCESS WINDOW / RANKING · 01—{summary.nCandidates ?? "—"}
            </p>
            <h1>
              Process <span>Rank</span>
            </h1>
            <p className="intro-copy">
              Compare estimativas e alternativas Pareto. A posição do ranking
              não é uma garantia de qualidade ou ausência de defeitos.
            </p>
          </div>
          <div className="reference-chip">
            <span>REFERÊNCIA GEOMÉTRICA</span>
            <strong>
              10 &lt; DI &lt; 30% <i>·</i> 0,20 &lt; H/W &lt; 1/3
            </strong>
            <small>
              Específica do estudo · limites estritos · não universal
            </small>
          </div>
        </section>

        <section className="summary-grid" aria-label="Resumo da grade atual">
          <SummaryCard
            label="CONDIÇÕES AVALIADAS"
            value={String(summary.nCandidates ?? 0)}
            foot="snapshot do pipeline"
          />
          <SummaryCard
            label="ELEGÍVEIS AO RANKING"
            value={String(ranks)}
            foot="geometria, incerteza e suporte"
            accent
          />
          <SummaryCard
            label="PARETO NÃO DOMINADAS"
            value={String(summary.nParetoNondominated ?? 0)}
            foot="alternativas de compromisso"
          />
          <SummaryCard
            label="BANDAS CONTIDAS DI + H/W"
            value={String(summary.nEligibleWithBothBandsInside ?? 0)}
            foot={`de ${ranks} elegíveis com bandas contidas`}
          />
        </section>

        {view === "quality" ? (
          <QualityPanel data={data} />
        ) : (
          <section className="workspace" aria-label="Console de ranking">
            <aside className="filter-panel" aria-label="Filtros do ranking">
              <div className="panel-section-heading">
                <p className="eyebrow">01 / VISTA</p>
                <span>RANKING PYTHON</span>
              </div>
              <div
                className="mode-switch"
                role="group"
                aria-label="Modo do ranking"
              >
                <button
                  type="button"
                  className={rankMode === "quality" ? "mode-active" : ""}
                  aria-pressed={rankMode === "quality"}
                  onClick={() => {
                    setRankMode("quality");
                    setIncludeExcluded(false);
                  }}
                >
                  Prioridade
                  <br />
                  <small>ordem dos critérios</small>
                </button>
                <button
                  type="button"
                  className={rankMode === "pareto" ? "mode-active" : ""}
                  aria-pressed={rankMode === "pareto"}
                  onClick={() => setRankMode("pareto")}
                >
                  Pareto
                  <br />
                  <small>não dominadas</small>
                </button>
              </div>
              <p className="mode-note">
                Geometria, bandas e suporte. Mesma posição indica empate nos
                critérios.
              </p>
              <div className="filters-block">
                <div className="panel-section-heading">
                  <p className="eyebrow">02 / FILTROS</p>
                  <button
                    type="button"
                    className="clear-button"
                    onClick={clearFilters}
                  >
                    Limpar
                  </button>
                </div>
                <label className="select-label">
                  Potência
                  <select
                    value={filters.powerW}
                    onChange={(event) =>
                      setFilter("powerW", event.currentTarget.value)
                    }
                  >
                    <option value="all">Todas</option>
                    {powers.map((value) => (
                      <option key={value} value={String(value)}>
                        {formatNumber(value, 0)} W
                      </option>
                    ))}
                  </select>
                </label>
                <label className="select-label">
                  Alimentação
                  <select
                    value={filters.feedGMin}
                    onChange={(event) =>
                      setFilter("feedGMin", event.currentTarget.value)
                    }
                  >
                    <option value="all">Todas</option>
                    {feeds.map((value) => (
                      <option key={value} value={String(value)}>
                        {formatNumber(value, 1)} g/min
                      </option>
                    ))}
                  </select>
                </label>
                <label className="select-label">
                  Velocidade
                  <select
                    value={filters.speedMmMin}
                    onChange={(event) =>
                      setFilter("speedMmMin", event.currentTarget.value)
                    }
                  >
                    <option value="all">Todas</option>
                    {speeds.map((value) => (
                      <option key={value} value={String(value)}>
                        {formatNumber(value, 0)} mm/min
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {rankMode === "quality" && (
                <label className="include-control">
                  <input
                    type="checkbox"
                    checked={includeExcluded}
                    onChange={(event) =>
                      setIncludeExcluded(event.currentTarget.checked)
                    }
                  />
                  <span>
                    Incluir condições fora do ranking
                    <small>Sem posição atribuída pelas regras atuais.</small>
                  </span>
                </label>
              )}
              <div className="filter-foot">
                <span className="foot-index">!</span>
                <p>
                  Os controles filtram a grade existente. Não há previsão de
                  valores arbitrários nesta página.
                </p>
              </div>
            </aside>

            <section className="results-panel" aria-labelledby="ranking-title">
              <div className="results-heading">
                <div>
                  <p className="eyebrow">03 / PROCESS RANK</p>
                  <h2 id="ranking-title">
                    {rankMode === "quality"
                      ? "Qualidade-prioridade"
                      : "Fronteira Pareto"}
                  </h2>
                </div>
                <div className="visible-count">
                  <b>{candidatePool.length}</b>
                  <span>{rowsLabel}</span>
                </div>
              </div>
              <div
                className="results-view-switch"
                role="group"
                aria-label="Representação das condições"
              >
                <button
                  type="button"
                  className={resultsView === "table" ? "view-active" : ""}
                  aria-pressed={resultsView === "table"}
                  onClick={() => setResultsView("table")}
                >
                  Tabela
                </button>
                <button
                  type="button"
                  className={resultsView === "map" ? "view-active" : ""}
                  aria-pressed={resultsView === "map"}
                  onClick={() => setResultsView("map")}
                >
                  Mapa
                </button>
              </div>
              {resultsView === "table" && (
                <div className="ranking-legend">
                  <span>
                    <i className="legend-rank" /> Prioridade no Python
                  </span>
                  <span>
                    <i className="legend-pareto" /> Pareto
                  </span>
                  <span>
                    <i className="legend-screen" /> Triagem geométrica
                  </span>
                </div>
              )}
              {rankMode === "quality" && includeExcluded && (
                <p className="excluded-note">
                  Sem posição: restrição do estudo ou suporte insuficiente;
                  previsões não equivalem a inspeção de defeitos.
                </p>
              )}
              {resultsView === "table" ? (
                <ResultsTable
                  rows={candidatePool}
                  reference={data.window}
                  selectedId={selected?.id ?? null}
                  onSelect={setSelectedId}
                />
              ) : (
                <ProcessMap
                  rows={candidatePool}
                  domainRows={allRows}
                  selectedId={selected?.id ?? null}
                  onSelect={setSelectedId}
                />
              )}
              <div className="results-foot">
                <span>
                  {candidatePool.length} {rowsLabel}
                </span>
                <span>Ranks preservados após os filtros</span>
              </div>
            </section>

            {selected ? (
              <CandidateDetail candidate={selected} data={data} />
            ) : (
              <aside className="detail-panel empty-detail">
                <p className="eyebrow">SEM RESULTADOS</p>
                <h2>Nenhuma condição aparece com esses filtros.</h2>
                <button
                  type="button"
                  className="button-secondary"
                  onClick={clearFilters}
                >
                  Limpar filtros
                </button>
              </aside>
            )}
          </section>
        )}
      </main>

      <footer className="console-footer">
        <span>
          IN625 / PROCESS RANK <i>·</i> versão analítica
        </span>
        <span>
          Estimativas e triagem geométrica não são probabilidade de defeito,
          certificação ou prova de fusão metalúrgica.
        </span>
        <button
          type="button"
          onClick={() => setView(view === "quality" ? "ranking" : "quality")}
        >
          {view === "quality" ? "Abrir ranking" : "Ver qualidade OOF"} ↗
        </button>
      </footer>
    </div>
  );
}

export default App;
