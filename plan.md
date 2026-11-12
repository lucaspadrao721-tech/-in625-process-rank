# Plano — IN625 Process Rank: ranking conservador e mapa complementar

## Objetivo e fluxo

Console React/TypeScript estático, em português brasileiro, para comparar as 48 condições de trilha única DED-LB IN625 registradas na base. Os resultados exibidos são do pipeline Python e o browser não inventa parâmetros, reestima respostas ou recalcula ranks. A tabela continua a visualização inicial. **Tabela | Mapa** alterna a mesma população filtrada, seleção e estado Pareto; a aba Qualidade OOF mostra o desempenho fora da amostra. O propósito é priorizar condições experimentais para consideração, não declarar que uma peça terá qualidade garantida.

O snapshot atual contém 48 condições, 12 elegíveis, 3 não dominadas e 0 condições elegíveis com ambas as bandas Q90 totalmente contidas. C015, C027 e C032 empatam no rank 1 segundo todos os critérios usados; não há desempate por ID ou pela alimentação. Totais e ranks são exportados pelo Python, não hardcoded.

## Comparação, incerteza e rigor científico

A elegibilidade e a prioridade resultam da adequação à referência geométrica aberta `10% < DI < 30%` e `0,20 < H/W < 1/3`, do excesso das bandas indicativas e do suporte dos rótulos h/DI/HW. O Pareto considera geometria, violação pontual normalizada, excesso Q90 quando disponível e distância normalizada ao conjunto rotulado. A ordem é densa: critérios equivalentes compartilham posição. Nenhum escore 0–100 ou probabilidade foi introduzido.

A taxa de alimentação F não é objetivo de qualidade ou proxy de produtividade. Observações de blocos multipista não vetam as condições de trilha única. Os gates experimentais de 300/600 W só se aplicam ao perfil vinculado por fingerprint à base/contexto original; outros dados não herdam essas regras automaticamente. Suporte conjunto é descritor de cobertura, não probabilidade de acerto. Extrapolações e candidatos não comparáveis ficam sem rank/Pareto fabricados, mas podem ser incluídos pelo controle de exibição.

H, W, h, DI e H/W continuam marcados como previsões; médias medidas são dados de treino e não são validação independente. MAE, R² e quantis Q90 derivam de nested-group-OOF, com cobertura 48 para H/W e 22 para h/DI. Q90 é uma faixa empírica indicativa, não uma banda calibrada/conformal nem probabilidade de defeito. A referência geométrica é específica do estudo, não um limite universal. Nenhuma inferência de LoF, keyhole, porosidade ou qualidade certificada é feita.

## Mapa energia–material

O SVG quantitativo plota as mesmas condições nos indicadores nominais:

- Eixo X: `E_L = 60 P / v` em J/mm, P em W e v em mm/min.
- Eixo Y: `m_L = 1000 F / v` em mg/mm, F em g/min.

O mapa não assume absorção nem massa capturada, e não inventa VED sem espessura de camada. O fundo indica, em gradiente conceitual sem fronteiras numéricas, que energia relativamente baixa frente ao material alimentado pode favorecer insuficiência e energia relativamente alta pode favorecer excesso. Não há regiões “seguras”, limites LoF/keyhole calibrados, ou cor interpretada como probabilidade. As cores acompanhadas por legenda identificam a triagem geométrica e condições sem classificação; marcador diamante indica Pareto.

A projeção em dois indicadores pode fazer condições diferentes coincidirem, sem que seus resultados físicos sejam iguais. O código agrupa somente coordenadas numericamente idênticas; não aplica jitter nem combina pontos quase iguais por arredondamento. Todos os IDs coincidentes permanecem selecionáveis por clique, teclado, setas e botões de condição. A escala permanece fixa à grade completa após filtros.

## Arquitetura e estrutura

- `model_pipeline/`: treinamento offline, limpeza/unidades, geometria e física, suporte por resposta, regras de contexto e decisão, relatórios e testes Python.
- `model_pipeline/artifacts/candidate_assessment.json` e `.csv`: avaliação calculada offline da grade; não são servidos como lista bruta diretamente pela interface.
- `model_pipeline/export_rank_dashboard.py`: valida e reduz o contrato; gera `public/data/ranking.json` com previsões, bandas, cobertura, razões da decisão, classe pontual e empates, sem URLs/bibliografia desnecessária.
- `public/data/ranking.json`: snapshot versionado pelo site; o cliente envia `cache: no-cache`. A rota publicada do WebDev também tem regra gerenciada `no-cache`, fora deste repositório; em outro host, confirme a política de cache de forma independente.
- `src/App.tsx`: filtros, modos de prioridade/Pareto, seleção, troca de representação e aba de qualidade.
- `src/components/ResultsTable.tsx`, `ProcessMap.tsx`, `CandidateDetail.tsx`, `RangeTrack.tsx`, `QualityPanel.tsx`: lista, mapa, resposta selecionada, bandas versus referências e métricas OOF.
- `src/lib/ranking.ts`: ordenação/filtros e formatação sem recalcular decisões; `src/lib/process-map.ts`: conversão, agrupamento de coordenadas idênticas e escalas SVG.
- `public/manus-routes.json`: única página `/`. O build permanece estático Vite em `dist/`; não há API, banco de dados nem login na aplicação.
- `docs/decision_and_map.md`: referências e justificativa científica no repositório, sem bibliografia extensa na tela.

## Direção visual e de marca

**Design movement:** console de instrumentação industrial/laboratorial e painel de operação de processos, em vez de estética editorial.

**Princípios centrais:** (1) evidência e status antes de decoração; (2) densidade técnica com leitura hierárquica; (3) previsões, incerteza e triagem visualmente separadas; (4) acessibilidade e precisão antes de animação.

**Filosofia de cores:** grafite azulado `#081116` e superfícies de carvão criam contraste e foco. Ciano elétrico `#42DFF4` identifica foco/seleção e elementos de Pareto, nunca aprovação. Âmbar marca bordas e ressalvas; coral marca saída da referência geométrica. Cada estado tem texto/símbolo, não só cor.

**Paradigma de layout:** trilha operacional lateral de filtros, painel central que alterna tabela/mapa e painel à direita para inspecionar uma condição selecionada. O cabeçalho compacto ancora a marca e a navegação; telas estreitas refluem os painéis sem criar uma tabela ampla.

**Elementos assinatura:** (1) pequeno sinal de três barras como marca de processo; (2) rótulos monoespaçados de unidades/ranks; (3) indicadores geométricos ciano/âmbar/coral e contorno em losango para Pareto.

**Interação:** controles simples filtram os dados existentes; seleção é compartilhada entre tabela, mapa e detalhe; foco por teclado, tooltips textuais e IDs preservam acesso aos pontos sobrepostos. Nenhum rank é refeito no cliente após filtragem.

**Animação:** transições curtas de estado sem movimento decorativo, sem piscar ou pulsar; honrar `prefers-reduced-motion` e manter navegação funcional sem animação.

**Tipografia:** IBM Plex Sans para leitura e IBM Plex Mono para parâmetros, valores, unidades, ranks e indicadores. A escala privilegia números e status; explicações ficam como microtexto contextual.

**Essência da marca:** console para pesquisadores compararem condições candidatas de trilha IN625, mostrando compromisso, suporte e incerteza em vez de vender um “ótimo” infundado. Personalidade: precisa, sóbria, útil.

**Voz:** rótulos diretos, técnicos e cautelosos. Exemplos: “Mesma prioridade: empate nos critérios calculados.” “Q90 indicativo; não é probabilidade de defeito.”

**Wordmark/logo:** wordmark `IN625 / PROCESS RANK`; marca geométrica com três barras ascendentes, sugerindo sinal de processo e trilha sem representar uma peça ou um defeito.

**Cor proprietária:** ciano `#42DFF4`, usado como foco/seleção Pareto e não como semáforo de qualidade.

## Implementação e serving

Manter hospedagem estática e configuração de build existente. Python gera o snapshot offline; para outra grade, o usuário roda o CLI/analisador e exportador e, em seguida, atualiza o snapshot publicado. Não executar treinamento no navegador. Auto-publicação permanece desligada; qualquer mudança entregue é um checkpoint separado de Publish.


## Pacote acessível pelo GitHub Pages

A versão atual é estática: React/Vite lê o snapshot JSON; não existe API ou execução de Python no site publicado. Preparar um workflow GitHub Actions para instalar pnpm, compilar `dist/` e publicar no GitHub Pages em cada push a `main`. Ajustar `base` do Vite pelo `GITHUB_REPOSITORY` apenas nos builds GitHub Actions, de modo que project pages em `/<repo>/` funcionem, preservando `/` em Preview/local e em `<user>.github.io`. Incluir um guia em português para explicar a interface ao orientador e orientar cópia/clonagem, configuração Pages, monitoramento de Actions e acesso ao URL público. O guia alerta que publicar o site expõe publicamente o snapshot e que a visibilidade do repositório também pode expor a planilha/modelo/relatórios; validar autorização de compartilhamento antes de tornar o conteúdo público. Entregar um novo ZIP derivado do HEAD mais recente, nunca o ZIP anterior com a API dinâmica.