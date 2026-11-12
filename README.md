# IN625 Process Rank

Console científico estático em português para comparar a geometria prevista de trilhas DED-LB de Inconel 625. Mantém filtros, ranking, Pareto, detalhe da condição e métricas OOF; a vista **Mapa** mostra as mesmas condições no plano energia–material. Não existe uma nota arbitrária de qualidade nem inferência de probabilidade de defeito.

Os controles filtram o snapshot existente. Inserir parâmetros arbitrários ou gerar uma nova grade no navegador não faz parte desta versão; o código Python pode avaliar outra grade offline e exportá-la ao painel.

Para uma explicação prática pronta para encaminhar ao orientador e os passos para publicar esta versão estática no GitHub Pages, consulte o [guia do painel e do GitHub Pages](docs/guia_orientador_e_github_pages.md).

## Executar o site

Use Node.js 22.18+ compatível com Vite 8 e pnpm 11.25.0:

```bash
pnpm install --frozen-lockfile
pnpm dev
```

Abra `http://localhost:3000`. A página inicia em **Tabela**. O seletor **Tabela | Mapa** preserva filtros e condição selecionada. Clique ou use teclado nos pontos para inspecionar H, W, h e DI; setas e os botões de IDs alternam condições com a mesma coordenada. Pareto e ranks são calculados no Python e preservados após filtros.

```bash
pnpm typecheck
pnpm build
node --experimental-strip-types --test src/lib/*.test.mjs
```

## Atualizar o snapshot sem retreinar

O bundle e as métricas OOF já estão em `model_pipeline/artifacts/`. Use Python 3.12 e um ambiente virtual. Depois de instalar `model_pipeline/requirements.txt`, execute a partir da pasta do pipeline:

```bash
cd model_pipeline
python analyze.py --grid --out artifacts/candidate_assessment.csv --json-out artifacts/candidate_assessment.json
python export_rank_dashboard.py
python -m pytest -q
```

O exportador grava `../public/data/ranking.json`, sem bibliografia, URLs ou rótulos de blocos multipista. Para outro conjunto de parâmetros, use `analyze.py --candidate-csv <arquivo.csv>` e os mesmos caminhos de saída. A interface mostrará apenas o conjunto exportado.

Retreinar é outra operação: altere a base medida e execute `train.py` conforme o README do pipeline. Revise o perfil de contexto antes de reaplicar as restrições do estudo em outra campanha. Não carregue bundles Joblib de terceiros não confiáveis.

## Critérios e limites

A comparação usa referência geométrica estrita, bandas empíricas e suporte dos rótulos. Maior alimentação não é objetivo de qualidade nem prova de produtividade depositada. Resultados de blocos não vetam trilhas. Empates de critérios compartilham prioridade; ordenar IDs para exibição não estabelece superioridade científica. Verificar suporte conjunto não mede probabilidade nem garante erro preditivo pequeno.

Previsões finais e médias medidas usadas no treino são separadas. MAE, R² e Q90 vêm da validação OOF, não do erro aparente do ajuste final. Os quantis foram preservados: a banda global de H/W é mais larga que a referência atual, portanto zero contenções não implica que todas as condições sejam ruins.

O mapa usa E_L = 60P/v em J/mm e m_L = 1000F/v em mg/mm, para v em mm/min e F em g/min. Mostra energia nominal incidente e pó alimentado, não absorção ou massa capturada. O fundo é conceitual, sem fronteiras de defeito calibradas; a cor dos pontos vem da triagem calculada e o contorno indica Pareto. Duas condições na mesma coordenada não são necessariamente equivalentes fisicamente.

A justificativa e as limitações estão em [critérios de comparação e mapa](docs/decision_and_map.md). Essa documentação fica no repositório, não na tela principal.

## Estrutura

`src/App.tsx` compartilha filtros e seleção entre tabela, mapa e detalhe. `src/components/ProcessMap.tsx` renderiza o SVG; `src/lib/process-map.ts` calcula somente coordenadas e agrupamento da projeção. `public/data/ranking.json` é o snapshot compacto. `model_pipeline/` contém treino/análise offline, suporte conjunto, contexto do estudo e regressões. `public/manus-routes.json` declara a página `/`.

O build publicado é estático (`dist/`). Nenhuma API, banco ou login é necessário para esta versão. O treino Python não é executado pelo build do frontend.

O cliente solicita `/data/ranking.json` com `cache: no-cache`. No WebDev, a rota estática publicada também tem regra gerenciada `no-cache` fora do repositório. Outro host não herda essa configuração: configure a revalidação do JSON fixo ou versione seu URL quando atualizar os dados.
