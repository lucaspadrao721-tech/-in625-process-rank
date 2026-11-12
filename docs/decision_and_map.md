# Comparação de trilhas e mapa energia–material

## Escopo da versão

Esta versão mantém o console restaurado e a grade exportada de trilha única. Foram corrigidas regras de decisão, sem retreinar o bundle ou alterar a planilha, as previsões primárias, métricas OOF e quantis. A ordem relativa serve para triagem de condições e planejamento de ensaios; não certifica a qualidade da trilha ou de uma peça.

## Objetivos de comparação

A adequação pontual é avaliada pela referência específica do estudo: 10% < DI < 30% e 1/5 < H/W < 1/3. A desigualdade é estrita: um ponto exatamente no limite não atende à referência. A comparação distingue pertencimento à faixa de distância ao seu interior; não cria uma penalidade física arbitrária para contato com a borda.

Bandas Q90 são quantis empíricos dos erros OOF. O excesso das bandas em relação à referência e o suporte dos rótulos complementam a adequação pontual. São critérios distintos; não compõem uma nota 0–100. A prioridade preserva essas preferências explicitamente, enquanto a fronteira Pareto identifica alternativas não dominadas nos objetivos declarados. IDs são apenas uma ordem estável de apresentação, nunca evidência de vantagem. Critérios equivalentes devem indicar empate.

Alimentação de pó deixou de ser objetivo de qualidade. F mede massa nominal fornecida, não massa efetivamente capturada/depositada, eficiência ou produção. Aumentá-la pode alterar a geometria e o balanço térmico, mas não implica uma melhoria automática. Evidências de blocos multipista não excluem nem rotulam candidatos de trilha única.

## Suporte e contexto

Os limites isolados de P, F e v não descrevem toda a região amostrada. O envelope conjunto normalizado é verificado nos pontos com rótulo de cada resposta; componentes derivados herdam as limitações de seus componentes. A distância ao rótulo mais próximo é um indicador de proximidade, sem um corte de confiança escolhido arbitrariamente. Envelope não é calibração de erro ou probabilidade de sucesso.

Restrições observadas de 300 e 600 W permanecem para a base original identificada pelo perfil de contexto. Outro conjunto não herda automaticamente essas observações. Na campanha-fonte, 300 W não alcançou a diluição-alvo e 600 W mostrou marcas de oxidação; o segundo fato não é diagnóstico de keyhole. Reutilizar o código em outra máquina/campanha exige revisar a configuração e as referências, não apenas trocar o arquivo de dados.[1]

## Incerteza preservada

H e W têm 48 condições rotuladas, h e DI têm 22. No modelo atual, Q90 de H/W é aproximadamente 0,1474, enquanto a largura da referência 0,20–1/3 é aproximadamente 0,1333. Uma banda global simétrica desse tamanho não pode ficar integralmente dentro da faixa. Zero contenções é uma limitação desse critério e da precisão estimada, não uma demonstração de que todas as trilhas sejam ruins. Não foram estreitadas bandas para produzir um resultado favorável.

Médias medidas exibidas pertencem ao treinamento e não validam independentemente as previsões finais do mesmo conjunto. A qualidade fora da dobra é apresentada na aba OOF. Ausência de rótulo de penetração/diluição não equivale a penetração/diluição zero.

## Mapa quantitativo e fundo conceitual

Para potência P em W, velocidade v em mm/min e alimentação F em g/min, os eixos são:

- E_L = 60P/v, energia linear nominal incidente em J/mm.
- m_L = 1000F/v, massa nominal alimentada por comprimento em mg/mm.

A conversão no eixo vertical não altera a unidade da alimentação de entrada: ela continua sendo g/min. A razão entre os indicadores equivale a energia nominal por massa fornecida, não absorvida. Não se inventa espessura de camada nem densidade volumétrica de energia para os dados de trilha única.

O uso conjunto de aporte linear e alimentação/material é sustentado por mapas de DED na literatura.[2] Estudos de trilhas de ligas de níquel distinguiram estados mediante morfologia, rugosidade e diluição; suas fronteiras foram obtidas experimentalmente.[3] Esta base não contém rótulos suficientes para calibrar um classificador de LoF, keyhole ou outros defeitos.

O fundo do gráfico mostra apenas direções conceituais: menor energia relativamente ao material pode favorecer fusão insuficiente; maior energia relativamente ao material pode favorecer sobreaquecimento/diluição excessiva e outros mecanismos. Não há uma região verde livre de defeitos nem limiares numéricos atribuídos à máquina. As cores dos pontos representam triagem geométrica ou ausência de classificação, e o contorno Pareto é uma propriedade da comparação calculada.

A escala é determinada pela grade completa, não muda com filtros e não fornece fronteiras físicas. A projeção reduz três entradas a dois indicadores: combinações distintas podem coincidir sem ter o mesmo resultado físico. O componente preserva os pontos na coordenada verdadeira, reúne os IDs coincidentes e permite selecionar cada condição por botões/setas, sem jitter.

## Referências

[1]: https://link.springer.com/article/10.1007/s11665-026-14887-8 "Estudo específico de IN625 DED-LB, 2026"
[2]: https://www.mdpi.com/2079-6412/9/7/418 "Dass e Moridi — State of the Art in Directed Energy Deposition, 2019"
[3]: https://www.sciencedirect.com/science/article/pii/S0030399221002504 "Shao et al. — Process maps and optimal processing windows of Ni-based alloy, 2021"
