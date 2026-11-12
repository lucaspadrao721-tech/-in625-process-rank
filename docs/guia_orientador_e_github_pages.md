# Guia prático — IN625 Process Rank

## Texto pronto para encaminhar ao orientador

> O IN625 Process Rank é um painel de apoio à comparação de condições de trilha única de Inconel 625 produzidas por DED-LB. Nesta versão, ele organiza e mostra previsões e critérios calculados previamente pelo pipeline Python para a grade experimental existente de 48 combinações. Não é um formulário de simulação de parâmetros arbitrários: os filtros selecionam condições dessa grade.
>
> Para cada condição, o painel apresenta H (altura), W (largura), h (penetração), DI (diluição), uma faixa empírica indicativa Q90 e informações de suporte dos dados. A ordem de prioridade compara adequação geométrica, incerteza e suporte; Pareto destaca alternativas não dominadas, sem declarar um único vencedor universal. O mapa mostra energia linear nominal e massa de pó alimentada por comprimento, com tendências conceituais de insuficiência/excesso, mas não é um detector de falta de fusão nem um mapa calibrado de defeitos. A aba Qualidade OOF resume o erro fora da amostra. Os resultados servem para triagem e planejamento de novos ensaios, não para garantir que uma trilha ou peça será aprovada.

## Como usar o site, na prática

### 1. Leia os quatro números do topo

**Condições avaliadas: 48** é o total de combinações que o snapshot atual contém. **Elegíveis ao ranking: 12** são as condições que passaram pelas regras de comparação e têm suporte suficiente para receber uma posição. Elegível não significa “aprovada para fabricar”.

**Pareto não dominadas: 3** são três alternativas que representam compromissos diferentes nos critérios do modelo. Uma alternativa Pareto não é automaticamente a melhor em tudo; outra pode favorecer algum critério e perder em outro. **Bandas contidas DI + H/W: 0** informa que nenhuma das 12 elegíveis tem simultaneamente as duas faixas Q90 inteiras dentro da referência geométrica. Isso não significa que as 12 sejam ruins: a faixa global Q90 de H/W é mais larga que a janela geométrica usada.

### 2. Escolha a forma de ordenar

**Prioridade** mostra a ordem Python dos critérios declarados: adequação geométrica, bandas de incerteza e suporte. Posições iguais significam empate segundo esses critérios; por exemplo, no snapshot atual três condições compartilham o rank 1. O número de posição não é uma nota de qualidade e não prova que a primeira será a melhor peça.

**Pareto** mostra somente as alternativas não dominadas. Em linguagem prática, dentro dos objetivos comparados, nenhuma outra condição é melhor em todos os critérios considerados e estritamente melhor em pelo menos um. Se alguém priorizar outro objetivo de fabricação, a escolha pode mudar; esse painel não calcula um ótimo universal.

### 3. Use os filtros para localizar condições da grade

Os menus **Potência**, **Alimentação** e **Velocidade** reduzem a lista às combinações existentes com aqueles valores. Eles não criam uma nova combinação. Os ranks permanecem os calculados pelo Python: filtrar não recalcula nem renumera o ranking.

A caixa **Incluir condições fora do ranking** permite inspecionar a grade completa, inclusive condições sem posição porque uma restrição do estudo ou a falta de suporte impede uma comparação responsável. Em modo Pareto, a lista continua sendo somente a fronteira não dominada.

### 4. Leia a Tabela

Cada linha é uma combinação de potência P, alimentação F e velocidade v. **DI prevista** é a diluição estimada e **H/W previsto** é a razão altura/largura derivada das estimativas geométricas. **Triagem pontual** diz se esses descritores previstos ficam dentro, fora ou no limite da referência geométrica específica do estudo. Não é inspeção de defeitos.

**Pareto** identifica uma alternativa não dominada; **Classificada** quer dizer que ela recebeu posição, mas não está na fronteira; **Não classificada** quer dizer que a regra não atribuiu posição. Clique no rank ou nos parâmetros para inspecionar a condição à direita.

### 5. Leia o Mapa

**Tabela | Mapa** alterna duas representações dos mesmos dados e preserva filtros e condição selecionada. No mapa, o eixo horizontal é a energia linear nominal `E_L = 60P/v`, em J/mm. O eixo vertical é a massa nominal de pó alimentada por comprimento `m_L = 1000F/v`, em mg/mm. A unidade original de alimentação do formulário/base continua sendo g/min.

Cada marcador representa uma condição. A cor mostra a triagem geométrica da condição; o losango mostra Pareto. O fundo apenas sugere uma tendência física: energia relativamente baixa diante do pó alimentado pode favorecer fusão insuficiente; uma razão relativamente alta pode favorecer excesso de energia. Essas áreas são conceituais, sem limites calibrados para declarar falta de fusão, keyhole ou zona segura. Os eixos também não medem energia absorvida ou massa efetivamente capturada.

Duas condições podem cair exatamente no mesmo ponto do mapa e, ainda assim, ter previsões diferentes. Se houver sobreposição, use clique, teclado/setas ou os botões com IDs para alternar entre elas. O site preserva as coordenadas reais; não desloca os pontos para facilitar a leitura.

### 6. Inspecione uma condição

O painel da condição mostra P, F e v, sua posição ou a razão de não ter sido classificada, e a triagem frente à referência do estudo. A referência estrita usada nesta versão é `10% < DI < 30%` e `0,20 < H/W < 1/3`; ela é específica do estudo, não um padrão universal.

Para **H, W, h e DI**, o número principal é a previsão. A faixa **Q90 indicativa** descreve a incerteza empírica observada nos erros OOF do modelo; não é um intervalo calibrado de confiança e não fornece a probabilidade de defeito. `n` informa quantos rótulos experimentais daquele resultado estão disponíveis para apoiar o modelo. A cobertura é diferente por resposta: H e W têm 48 rótulos; h e DI têm 22.

Quando aparece **Média medida no treino**, ela pertence a dados usados para treinar o modelo e não constitui uma confirmação independente da previsão. Em condições medidas que não são essa combinação, o site pode não ter média experimental para mostrar. Não interprete campo sem rótulo como zero.

A visualização **Ponto × incerteza** compara a previsão pontual e a banda com a mesma referência geométrica. “A banda cabe”, “cruza” ou “fica fora” descreve apenas essa comparação geométrica. O próprio site informa que a **probabilidade de defeito não é estimável** com estes dados.

### 7. Use a aba Qualidade OOF para julgar o modelo

OOF significa que cada erro foi calculado para observações deixadas fora do ajuste que gerou aquela previsão de validação, com divisão agrupada por condição. É uma estimativa mais informativa do erro em dados não usados naquela dobra do que o erro de treino, mas não substitui uma validação independente em outra campanha, máquina ou laboratório.

**MAE OOF** é o erro absoluto médio, nas unidades do alvo. **R² OOF** resume quanto da variação o modelo acompanha nas previsões fora da dobra; quanto mais perto de 1, melhor o ajuste relativo, mas isso não é garantia individual. **Q90 |erro|** é o percentil 90 do erro absoluto observado na validação OOF e dá escala às bandas indicativas usadas nos detalhes.

No snapshot atual, H tem MAE de aproximadamente 32,1 µm, R² 0,910 e Q90 77,7 µm; W, MAE 27,5 µm, R² 0,957 e Q90 73,8 µm; h, MAE 7,24 µm, R² 0,779 e Q90 17,2 µm; DI, MAE 2,35 pontos percentuais, R² 0,861 e Q90 5,45 pontos percentuais. H/W tem MAE 0,055, R² 0,820 e Q90 0,147. H/W e DI são derivados das previsões dos componentes, e não alvos experimentais medidos diretamente em todas as condições.

### O que esta versão não faz

O site não aceita P/F/v arbitrários, não gera uma varredura nova no navegador, não diagnostica porosidade/falta de fusão e não calcula uma probabilidade de sucesso. Para atualizar a grade é preciso rodar offline o analisador/exportador Python e publicar um novo `public/data/ranking.json`. Simulações de tela também não são novos dados experimentais; para melhorar o modelo é necessário adicionar medições reais e retreinar com o procedimento documentado.

## Colocar o site acessível pelo GitHub

A versão atual é um site **estático**: a interface React lê o arquivo de dados `public/data/ranking.json`; não precisa de API Python para funcionar online. GitHub Pages pode publicar a pasta compilada `dist/` por meio de GitHub Actions. O workflow e a configuração de caminho para sites de projeto estão incluídos neste pacote. O Vite requer o caminho base correto quando a URL contém o nome do repositório; esta versão configura isso automaticamente durante o build no GitHub Actions.[1] [2]

1. **Baixe e extraia o ZIP atualizado.** Não use o ZIP antigo chamado `IN625_Trilhas_GitHub.zip`: ele corresponde a uma versão anterior com API dinâmica e não é o pacote deste site estático. Extraia `IN625_ProcessRank_GitHubPages.zip` para uma pasta.

2. **Crie um repositório vazio no GitHub.** Na conta GitHub, escolha **New repository**. Um nome simples como `in625-process-rank` funciona. Se o objetivo é um site público, selecione **Public** somente depois de confirmar que a planilha e os demais dados experimentais podem ser compartilhados. Não marque para criar README nem `.gitignore`: eles já vêm no pacote. O pacote não inclui uma licença; decida com o orientador/grupo se o código e os dados terão licença antes de acrescentar uma.

3. **Use GitHub Desktop para enviar os arquivos.** Instale o GitHub Desktop e entre na conta. Escolha **File → Clone repository**, selecione o repositório vazio recém-criado e escolha onde salvá-lo. Abra a pasta onde extraiu o ZIP e copie todo o conteúdo para a pasta clonada — arquivos da raiz e subpastas — sem copiar uma pasta externa inteira como subpasta. Preserve a pasta `.github/workflows`; é ela que contém a rotina de publicação automática. Não substitua nem apague a pasta `.git` criada pelo GitHub Desktop.

4. **Ative a publicação do Pages antes do primeiro envio.** Abra o repositório no navegador do GitHub. Vá a **Settings → Pages → Build and deployment → Source** e selecione **GitHub Actions**. Salve se o GitHub solicitar. Em uma conta GitHub Free, a documentação do GitHub informa que o repositório de Pages precisa ser público.[3]

5. **Revise e envie a versão inicial.** No GitHub Desktop, confira que aparecem `package.json`, `vite.config.ts`, `src/`, `public/`, `model_pipeline/`, `docs/` e `.github/workflows/deploy-pages.yml`. Escreva uma mensagem, por exemplo `Publicar Process Rank IN625`, clique **Commit to main** e depois **Push origin**. Esse push inicia o primeiro build já com o Pages configurado.

6. **Aguarde o build e confira o endereço.** Abra a aba **Actions** e selecione o workflow **Publicar IN625 Process Rank no GitHub Pages**. Espere os trabalhos `build` e `deploy` terminarem em verde. Depois volte a **Settings → Pages** e clique em **Visit site**. Para o repositório `in625-process-rank`, o endereço será `https://SEU_USUARIO.github.io/in625-process-rank/`. A primeira publicação pode levar alguns minutos.[3]

7. **Para atualizar depois**, faça as mudanças na pasta clonada. No GitHub Desktop revise os arquivos, crie um commit em `main` e clique **Push origin**. O workflow recompila e publica a nova versão. Se o deploy falhar, abra **Actions**, clique na execução vermelha e leia o primeiro passo que falhou.

### Importante antes de tornar público

GitHub Pages é acessível na internet. Um repositório público também permite baixar o código e seus arquivos; neste pacote isso inclui o snapshot e os arquivos de dados/modelo usados para reproduzir o estudo. Mesmo que o plano do GitHub permita manter o repositório privado, um site Pages publicado pode continuar público. Confirme com o orientador e os responsáveis pelos dados que a planilha, os resultados e o modelo podem ser divulgados antes de fazer o primeiro `Push origin`.[3]

O passo acima cria uma cópia sob a conta GitHub do usuário. Ele não conecta automaticamente essa cópia ao projeto do Manus e não publica o site pelo Manus.

## Referências

[1]: https://vite.dev/guide/static-deploy "Vite — Deploying a Static Site"
[2]: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site "GitHub Docs — Configuring a publishing source for GitHub Pages"
[3]: https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site "GitHub Docs — Creating a GitHub Pages site"
