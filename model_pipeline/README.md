# Pipeline de dados do IN625 Process Rank

Este diretório contém o núcleo Python de treino, inferência e triagem usado para gerar os dados do painel estático. O painel continua mostrando as 48 condições da grade; o navegador não treina modelos nem prevê combinações arbitrárias. Os comandos abaixo rodam offline, sem API/serviço, Streamlit ou Plotly.

## Ambiente e execução

O ambiente de referência é **CPython 3.12.3**. `requirements.txt` fixa as versões efetivamente instaladas e testadas neste pipeline. Em um ambiente virtual, execute a partir de `model_pipeline/`:

```bash
python -m pip install -r requirements.txt
python train.py
python analyze.py --grid
python export_rank_dashboard.py
```

`train.py` treina o bundle e gera métricas/OOF; `analyze.py --grid` usa o bundle existente para regenerar `artifacts/candidate_assessment.{json,csv}`; `export_rank_dashboard.py` transforma o assessment e os diagnósticos já existentes em `../public/data/ranking.json`. A exportação não treina modelos. Para avaliar candidatos fora da grade há o modo local `--candidate-csv` ou `--power/--feed/--speed`; isso não altera o contrato nem a interface estática.

## Regras de decisão

A referência é estrita: `10 < DI_pct < 30` e `0.2 < H/W < 1/3`. `geometry_reference_screen` mantém o contato com as bordas na classe fora, mas sem acrescentar uma penalidade física artificial: a distância pontual à faixa aberta continua zero na borda. A classe categórica dentro/fora participa antes das medidas de distância no ranking e também é objetivo explícito da fronteira Pareto.

`pareto_front` e `_normalized_quality_key` comparam classe geométrica, adequação pontual normalizada, excesso integral das bandas Q90 e distância máxima normalizada ao rótulo mais próximo entre `h`, `DI` e `H/W`. Alimentação de pó não é objetivo nem desempate de qualidade. IDs apenas tornam a apresentação estável e nunca separam cientificamente candidatos empatados. Critérios normalizados até `1e-12` são equivalentes por resolução numérica; `quality_order` é rank denso compartilhado e `rank_tie_count` informa o tamanho do empate.

`models._target_support` calcula suporte por alvo com a envoltória convexa dos pontos que têm aquele rótulo, após normalização por intervalos marginais. `models._joint_envelope_distance` reduz dimensões afins por SVD, cobrindo também conjuntos colineares, coplanares e constantes. Não há limiar científico de distância: fora da envoltória conjunta, a condição é inelegível, mas sua previsão continua disponível; dentro, a distância ao ponto rotulado mais próximo é apenas descritiva e usada como critério conservador (máximo entre h/DI/HW). A tolerância de `1e-10` só absorve erro numérico ao classificar a fronteira. A tolerância `1e-12` do ranking só decide igualdade entre números normalizados.

As bandas Q90 empíricas originais são usadas integralmente; não são reduzidas e não constituem intervalos conformais, probabilidades ou garantias. O excesso de banda mede apenas a extensão para além dos limites geométricos.

## Contexto dos gates de potência

`config/source_study_context.json` registra os gates de 300/600 W e um SHA-256 canônico da tabela original, abrangendo entradas e rótulos em `COLUMNS`. `analyze._validated_source_context` compara o hash do dataframe carregado ao configurado. Somente uma correspondência exata com `active: true` ativa as restrições; outra base não herda os gates automaticamente. Uma futura campanha só deve ativá-los após atualização explícita e validação científica da configuração.

`source_study_power_gate` aplica apenas o contexto fornecido. O helper histórico `source_study_block_context` permanece fora de `assess_candidate` e do ranking; resultados de blocos multipista não são transferidos para previsões de trilha única. O matcher histórico exige overlap efetivo coincidente com a precisão numérica e não é usado como veto ou classificação.

## Contrato de exportação

O exportador mantém `schemaVersion: 2` e os campos existentes. Cada predição inclui `support.withinTargetJointEnvelope` (`true`, `false` ou `null` sem rótulos) e estados curtos para envelope fora/dentro. Cada candidato contém `exclusionReasons` e `rankTieCount`. O root pode incluir `context` e `bandFeasibility`. A exportação remove URLs, bibliografia e narrativas internas. Predições continuam disponíveis mesmo quando `rankEligible` é falso; nesse caso `qualityOrder` é nulo e o candidato não integra Pareto.

## Arquivos centrais

- `src/data.py`: carregamento da planilha e fingerprint dos dados experimentais.
- `src/models.py`: ajuste, validação cruzada, predição e suporte marginal/conjunto por alvo.
- `src/decision.py`: classificação estrita da referência, adequação, comparação Pareto e resolução numérica.
- `src/defects.py`: contrato de impossibilidade de prever defeitos, gates contextuais e helper histórico de blocos.
- `analyze.py`: assessment de candidatos, regras de elegibilidade/ranking e geração CSV/JSON.
- `export_rank_dashboard.py`: validação e serialização do payload público compacto.
- `tests/test_core.py`: regressões de dados, geometria, suporte, ranking, contexto e exportação.
