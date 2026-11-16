# Histórico de versões

## 4.3.4 — novembro de 2026

Revisão metodológica e de interface, com alinhamento ao Manual de Identificação de Segmentos Críticos Rodoviários (edição 2026).

- **Trilha 3 (Empírico de Bayes):** passa a usar por padrão a regressão **Binomial Negativa do Manual 2026**
  (`nb_manual`: `Nobservado ~ log(Exposicao)`, com $\omega = 1 / (1 + N_{\text{previsto}}/k)$ e critério
  $N_{\text{esperado}} > N_{\text{previsto}} + 1{,}96\,\text{DP}$), reproduzindo integralmente os resultados de
  referência do Manual (Tabela 5.10: 21 segmentos críticos no DF, 225 em PE e 373 em MG por UPS; 9, 52 e 80 por
  frequência). Os métodos anteriores
  (Binomial Negativa por gravidade, Média Global de Marshall e procedimento da v4) permanecem nas configurações
  avançadas.
- **Variável de análise nas Trilhas 2 e 3:** inclusão do seletor **Severidade (UPS)** (padrão) ou **Frequência
  (total de sinistros)** nas abas de configuração das Trilhas 2 e 3.
- **Trilha 1 (Valor Crítico):**
  - Rótulo padronizado para “Valor crítico de frequência (sinistros por km)” (primeiro método da lista) e “Valor
    crítico de severidade (UPS por km)”, que segue como padrão.
  - Nível de confiança em campo numérico aberto (entre 50% e 99,9%), com cálculo automático do coeficiente $k$ da
    Normal padrão (mantendo os valores tabelados da Tabela 3.1 para os níveis padrões).
  - Notação da correção de continuidade padronizada como $-0{,}5/E$ (Manual) e $+1/(2E)$ (variante de referência),
    com nota explicativa para valores críticos negativos em segmentos muito curtos.
  - Nota técnica automática nos métodos baseados em taxa recomendando o uso da Trilha 3 quando houver VMD confiável.
  - Remoção da referência indevida “(item 5.1 do Manual)” no aviso sobre exclusão de segmentos sem sinistros.
- **Padronização de nomenclatura e tabelas:**
  - Cabeçalhos das tabelas de resultados e planilhas exportadas alinhados às variáveis do Manual 2026 (`Ifsi`,
    `CFsi`, `Ifs`; `Isi`, `CSi`, `Is`; `Tfsi`, `CTfsi`, `Tfs`; `Tsi`, `CTsi`, `Ts`; `Nesperado`, `Nprevisto`,
    `Nobservado`, `Excesso`, `Desvio-padrão (DP)`).
  - Substituição dos termos “Prioridades” e “Segmentos prioritários” por **Ordenamento dos segmentos críticos** na
    interface, nas abas do Excel e no relatório PDF.
  - Formatação de percentuais no relatório PDF e no painel com 1 casa decimal para valores entre 99,5% e 100% (ex.:
    `99,6%`), evitando arredondamento visual para `100%`.
- **Leitura de planilhas e segmentação:**
  - Seleção automática da aba de dados em arquivos Excel com múltiplas abas, mesmo quando a aba `Instruções` tiver
    sido movida para a primeira posição.
  - Normalização automática de nomes de estados por extenso (ex.: `Pernambuco` $\to$ `PE`, `Distrito Federal` $\to$
    `DF`, `Minas Gerais` $\to$ `MG`) na coluna `UF`.
  - Coluna de `Ano` ou `Data` passa a ser opcional em planilhas de sinistros pontuais (assumindo período padrão de
    3 anos com aviso informativo quando ausente), além de suporte a coluna única de `Gravidade` numérica (`1, 4, 28`)
    ou textual em `Outras formas de entrada`.
  - Confirmação visual na barra lateral ao carregar planilha própria de sinistros e seleção automática das UFs
    presentes no arquivo.
- **Mapas e linguagem:**
  - Na Trilha 2 (KDE), filtragem prévia de segmentos sem sinistros (`densidade` nula) antes do limite de pontos do
    mapa e ajuste de CSS no controle de camadas para evitar barras de rolagem.
  - Aviso sobre o VMD embutido do PNCT (2019) esclarecendo tratar-se da base pública de VMD mais atualizada
    disponível em âmbito nacional.
  - Revisão da linguagem do guia *Primeiros passos* e do relatório PDF para tom técnico e impessoal.
- **Testes:** a Trilha 3 padrão é conferida com os resultados do `MASS::glm.nb` do R em dados sintéticos, por
  severidade e por frequência.

## 4.3.3 — novembro de 2026

- **Manual de Utilização no app:** botão “Manual de Utilização (PDF)” na barra lateral, abaixo de “Primeiros
  passos”, e no fim do guia Primeiros passos. O PDF fica em `static/manual/` e o próprio app o serve; o navegador
  o abre numa nova aba. O Manual passa para a versão 4.3.3.
- **Logo:** `README.md` e `assets/LEIA-ME.md` atualizados.
- `ferramentas/desempenho/`: o KDE da Trilha 2 em C (`kde.c`) e em R (`kde.R`), com o mesmo algoritmo do app,
  e `comparar_linguagens.py`, que roda as três versões nos mesmos dados (sinistros da PRF no DF, em PE, em MG
  e no Brasil e 1 milhão de sinistros sintéticos em SP), confere que dão a mesma densidade e mede tempo e
  memória. Em 1 milhão de sinistros, o cálculo leva cerca de 10 s em Python, 2 s em C e 14 s em R.

## 4.3.2 — novembro de 2026

- **Barra lateral:** o bloco de dados passa a se chamar **Entrada de dados**, com “Usar meus dados de sinistros”,
  “Outras formas de entrada” e “Atualizar a malha ou o VMD (avançado)”, nessa ordem, acima da UF e dos anos.
  O guia Primeiros passos e o Manual acompanham a nova ordem.

## 4.3.1 — novembro de 2026

Ajustes de leitura no Primeiros passos, nas cores da convergência e no mapa do relatório.

- **Mapa do relatório com fundo:** o mapa dos segmentos críticos do PDF passa a ter o mapa do OpenStreetMap ao
  fundo, em cinza claro para as cores se destacarem, com a atribuição no canto e a escala medida no centro do
  mapa. Os tiles da área são baixados na geração do relatório (no máximo 30 por mapa, guardados na memória do
  servidor); sem internet, o mapa sai como antes, só com o desenho da malha, e o texto avisa. A variável de
  ambiente `SISEGC_MAPA_DE_FUNDO=0` desliga a busca.
- **Cores da convergência:** amarelo (crítico em uma trilha), vermelho (em duas) e roxo (nas três), no lugar de
  três tons de vermelho difíceis de distinguir, e sem verde, que sugeriria segurança. Valem para o mapa e para
  o gráfico de convergência, no Painel e no relatório, com contorno escuro nos pontos e legenda.
- **Primeiros passos:** sem o emoji no título e nos botões; o convite da tela inicial passa a “Novo por aqui?
  Veja os primeiros passos e abra um exemplo”; os exemplos se chamam “Rodovias Federais” e “Área Urbana”, com
  descrições mais curtas; o passo 1 diz que o app analisa a região “por meio de três métodos diferentes (as
  trilhas)”. O botão da barra lateral ganha contorno, como os demais.
- **Fontes dos dados embutidos:** na barra lateral, uma frase curta (“Dados públicos embutidos: DNIT, PRF, PNCT
  e © OpenStreetMap”) com o “?” que mostra os detalhes em tópicos: versão do SNV, período da PRF, ano do VMD e
  data do extrato do OpenStreetMap.

## 4.3.0 — novembro de 2026

Painel, relatório executivo e Primeiros passos.

- **Painel:** primeira aba dos resultados, com as três trilhas juntas e filtros (trilhas, rodovia ou via e
  número mínimo de trilhas) que valem para o painel inteiro: números principais, críticos por trilha entre os
  segmentos com sinistro, quanto os críticos concentram da extensão, dos sinistros, dos óbitos e da UPS,
  convergência entre as trilhas, distribuição da UPS dos segmentos com sinistro, mapa colorido pelo número de
  trilhas, vias com mais críticos e a lista de prioridades (mais trilhas primeiro; no empate, a maior UPS).
- **Relatório executivo em PDF**, no lugar do relatório técnico: números principais, mapa dos críticos (sem
  depender da internet), convergência, fichas dos 10 segmentos prioritários (com as métricas de cada trilha e
  o link da coordenada), distribuição da UPS, resultados por trilha, dados e limitações (com os avisos sobre
  os dados carregados) e a metodologia com os parâmetros usados; no anexo, a lista de prioridades. O PDF e as
  planilhas são gerados só no clique.
- **Planilhas com nomes de colunas por extenso** (“ID do segmento”, “Sinistros com óbito”, “Índice observado
  (UPS/km)”...), sem colunas repetidas; a de resultados ganha as abas Resumo e Prioridades. A planilha dos
  segmentos baixada pode ser corrigida e enviada de novo: o leitor reconhece os nomes novos e prefere a
  descrição da via ao código do SNV.
- **Barra lateral mais enxuta:** “Outras formas de entrada” sobe para o topo; os avisos sobre os dados saem da
  barra e vão para o bloco recolhido **Características dos dados carregados**, abaixo das configurações, com o
  resumo (segmentos, extensão, sinistros por gravidade, cobertura do VMD), os avisos, a tabela dos segmentos e
  o botão para baixá-la. A atribuição do OpenStreetMap fica sempre visível, junto das fontes embutidas.
- **Modelos da planilha de sinistros** (Modelo Preenchido, com 24 sinistros fictícios em Brasília, e Modelo em
  Branco) em “Usar meus dados de sinistros”; os modelos de segmentos passam aos nomes por extenso. Todos têm
  uma aba de instruções.
- **Primeiros passos:** guia com imagens das telas e dois exemplos prontos: rodovias federais (PRF no DF) e
  área urbana (6.186 sinistros do Infosiga SP, DETRAN-SP, de 2022 a 2024 num recorte de Santos, sob a CC BY
  4.0, em `dados_publicos/exemplos/`, gerado por `ferramentas/preparar_dados.py exemplo-urbano`).
- **Coordenadas repetidas:** com sinistros próprios, o app avisa quando muitos sinistros caem na mesma
  coordenada (30 ou mais) e lista as maiores, com link para o mapa; costumam ser pontos padrão do
  geocodificador.
- **Sinistros próprios de uma só área** (ex.: um município): os segmentos do SNV fora do retângulo dos
  sinistros e sem sinistros saem da análise, como já acontecia com as vias do OpenStreetMap. Antes, toda a
  malha federal da UF entrava com zero sinistros e pesava na média da Trilha 1, na referência da Trilha 3 e
  na extensão analisada.
- **Datas:** o leitor de sinistros lia 2023-01-05 como 1º de maio e perdia datas como 2023-01-25 (formato
  AAAA-MM-DD com o dia primeiro); agora lê AAAA-MM-DD e DD/MM/AAAA, com ou sem hora, aceita a coluna
  “Data/Hora” e avisa quantos sinistros ficaram sem data ou ano. A gravidade escrita como `sem_vitima` não vira
  mais “com vítima”.
- Barra lateral: os botões das planilhas-modelo ficam um embaixo do outro e passam a se chamar
  “Modelo Preenchido” e “Modelo em Branco”.
- Trilha 2: o mapa abre só com o mapa de calor (ilustrativo); as camadas dos quartis da densidade começam
  desmarcadas, e o 4º quartil continua reunindo os segmentos críticos.
- Trilha 2: sai a opção do quartil sobre os segmentos (critério da v4, que punha um quarto dos segmentos como
  críticos por construção). O quartil é sempre tomado sobre os sinistros, como no Manual.
- Mapas: números com vírgula decimal e a via de cada segmento também nas Trilhas 1 e 3; os pontos são montados
  só quando o mapa é desenhado.
- Nova dependência direta: altair (já vinha com o streamlit), nos gráficos do painel.

## 4.2.0 — novembro de 2026

Versão estável. O sistema passa a se chamar **Sistema de Identificação de Segmentos Críticos Rodoviários
(SISegC Rodoviário)**.

- Nome e logo do sistema no app (barra lateral, título e ícone da aba) e no relatório PDF (cabeçalho, rodapé
  com a versão e metadados); nome e versão definidos num só lugar (`utils/constantes.py`).
- Autoria, referências e forma de citar no `README.md` e em `CITATION.cff`; relação das bibliotecas e licenças
  atualizada em `THIRD_PARTY_LICENSES.md`.
- Segmentação automática por padrão, sem envio de arquivos: o app traz a malha do SNV 202610A
  (DNIT), os sinistros da PRF de 2021 a 2026, o VMD do PNCT (2019) e as vias do OpenStreetMap por UF
  (`dados_publicos/`, gerados por `ferramentas/preparar_dados.py`). O usuário escolhe UF, anos e
  comprimento do segmento (1 km por padrão, de 0,1 a 10 km); a segmentação e as três trilhas rodam
  sozinhas, sem botão.
  - Segmentos dentro de cada trecho do SNV com pista, com ID derivado do código do SNV e sobra menor que
    meio segmento somada ao anterior; trechos planejados e travessias ficam de fora.
  - BRs coincidentes contam uma vez, no trecho principal; a posição passa de uma BR para outra pela fração
    do trecho, inclusive quando a geometria está no sentido oposto.
  - Sinistro da PRF localizado pela coordenada, presa à BR informada (até 500 m); sem coordenada, pelo km.
  - Opção de separar por sentido da via; planilha dos segmentos para baixar.
- Sinistros próprios (municipais ou estaduais): planilha com latitude, longitude e ano (ou data), com a
  gravidade em texto ou em contagens; os que ficam fora do SNV vão para as vias do OpenStreetMap
  embutidas, com as ruas residenciais por padrão. Arquivos da PRF “por pessoa” contam cada ocorrência uma
  vez. Sinistro preso a uma rodovia federal de outra UF fica de fora e aparece no resumo.
- VMD por segmento (`utils/trafego.py`): mesmo código do SNV, com a posição pela fração do trecho, ou
  mesma BR e km no eixo principal (acessos, contornos e travessias têm quilometragem própria); avisos para
  trechos “Não Simulável” e para VMD de ano diferente dos sinistros. SNV e VMD mais novos podem ser
  enviados no lugar dos embutidos.
- Vias do OpenStreetMap (`utils/osm.py`): sem as vias federais e o que fica a até 40 m do SNV, pedaços da
  mesma via unidos, pista dupla tratada como uma via; corte e localização dos sinistros vetorizados (uma
  UF inteira com ruas urbanas em segundos). Atribuição ODbL no app e no relatório.
- Bases grandes: as planilhas para baixar (resultados e segmentos) são geradas só no clique, as tabelas na
  tela mostram as primeiras 20 mil linhas e a segmentação mostra o andamento. Com sinistros espalhados por
  uma área grande, as ruas residenciais começam desmarcadas. Teste de estresse com 100 mil sinistros de SP:
  25 s e 1,6 GB só com as vias principais; 51 s e cerca de 3 GB com as ruas residenciais (1,07 milhão de
  segmentos).
- Planilha com um sinistro por linha enviada como planilha de segmentos: o app avisa que só a Trilha 2
  roda e indica a segmentação automática; as mensagens das Trilhas 1 e 3 dizem o que fazer quando faltam
  extensão ou VMD.
- Planilha oficial com um sinistro (ou um ano) por linha (também na 4.1.2): os dois sentidos do mesmo ID continuam como dois
  segmentos (`25-C` e `25-D`); antes eram somados num só.
- Trilha 2 segue o Manual (item 3.3; também na 4.1.2): o quartil superior é tomado sobre os sinistros (cada segmento conta
  tantas vezes quanto tem sinistros) e são críticos os do nível 4 do código R, acima do P75. Segmento sem
  sinistro não tem densidade e nunca é crítico. O app e o relatório mostram a avaliação do Manual
  (coincidência com a soma da UPS na célula). O quartil sobre os segmentos, da v4, fica como opção. O
  resultado é igual ao do código R do Manual em todos os segmentos.
- Servidor próprio: `ferramentas/servidor/instalar.sh` (Docker num Ubuntu Server) e `atualizar.sh`; capacidade
  medida em `docs/IMPLANTACAO.md`; registro do Docker limitado.
- `ferramentas/benchmark.py`: tempo e memória por etapa em cenários típicos e grandes, para rodar em qualquer
  servidor. `ferramentas/exemplos_demonstracao.py`: planilhas de exemplo (sinistros fictícios no DF, segmentos do
  DF com dados públicos e o exemplo resolvido do Manual).
- Relatório: fontes dos dados (versão do SNV, VMD do PNCT, OpenStreetMap). Tabelas de resultados mostram a
  rodovia e os km de cada segmento; a planilha aceita a coluna `n_anos`.
- Novas dependências: shapely, pyproj e pyogrio. O repositório passa a ter cerca de 380 MB de dados
  públicos.

## 4.1.2 — outubro de 2026

A Trilha 2 passa a seguir o Manual (item 3.3).

- Trilha 2: o quartil superior é tomado sobre os sinistros (cada segmento conta tantas vezes quanto tem
  sinistros) e são críticos os do nível 4 do código R do Manual (item 3.3), acima do P75. Segmento sem
  sinistro não tem densidade e nunca é crítico. O app e o relatório mostram a avaliação do Manual
  (coincidência com a soma da UPS na célula). O quartil sobre os segmentos, da v4, fica como opção. O
  resultado é igual ao do código R do Manual em todos os segmentos.
- Planilha oficial com um sinistro (ou um ano) por linha: os dois sentidos do mesmo ID continuam como dois
  segmentos (`25-C` e `25-D`); antes eram somados num só.

## 4.1.1 — outubro de 2026

Correções encontradas nos testes da segmentação automática, que gera muitos segmentos curtos ou sem
sinistros.

- Trilha 1: segmento sem sinistros podia sair crítico. Com a correção de −0,5/m do Manual, o valor crítico
  de um segmento curto fica negativo e o índice zero passava dele; na planilha de DF, MG e PE eram 2
  segmentos no padrão (severidade, 95%) e até 18 em outras configurações. Agora o app avisa e não os marca.
- Trilha 2: quando 75% ou mais dos segmentos não têm sinistros no raio do núcleo, o limite do quartil
  superior era zero e todos os segmentos viravam críticos; agora só a densidade positiva conta.

## 4.1 — outubro de 2026

Correções da auditoria de código da versão 4.

### Erros corrigidos

- Trilha de Bayes falhava sempre com pandas 3 (`params[0]`).
- Relatório PDF quebrava em Linux por causa dos caches `.pkl` do fpdf com caminho do Windows; migrado para
  fpdf2, sem caches.
- O adaptador descartava a coluna `segmento_id` do modelo do app.
- O `ID` repetido nos dois sentidos das planilhas oficiais misturava sentidos na Trilha 1 e duplicava
  linhas nos mapas; agora cada sentido é um segmento (`25-C`, `25-D`).
- O KDE ignorava os pesos UPS escolhidos na interface.
- O upload era reprocessado a cada clique: os resultados sumiam, registros manuais se perdiam e “Limpar”
  não limpava.
- PDF: numeração das trilhas igual à do app, histograma de UPS que nunca aparecia,
  densidade que saía “0.00”, “óbitos” que eram sinistros com óbito, contagem por segmento único.
- Colunas de sinistro reconhecidas por padrão exato (uma coluna “TOTAL_COM_VITIMA” não vira mais óbito);
  linhas sem ID ou de total são descartadas com aviso; CSV com `;` e vírgula decimal é aceito.
- Arquivo temporário do gráfico (erro no Windows) substituído por memória.
- Parâmetros obsoletos do Streamlit (`use_container_width`, `components.html`) substituídos.
- O app confere as versões das bibliotecas ao abrir e, se o ambiente for o da v4 (com o `fpdf` antigo),
  mostra os comandos para criar o ambiente certo em vez de um erro de importação.

### Métodos

- Trilha 1: os quatro métodos do Manual (número, severidade, taxa de sinistros, taxa de severidade), com
  índice por km (eq. 3.1 a 3.12). Sinal da correção e exclusão de segmentos sem sinistros configuráveis.
  Testes reproduzem os exemplos resolvidos do Manual.
- Trilha 2 (KDE): mesmo algoritmo da v4 e do código R do Manual, com resultado idêntico, calculado só nas
  células ocupadas e com KD-tree.
- Trilha 3 (Empírico de Bayes): padrão Média Global (Marshall, 1991) aplicada a cada tipo de sinistro;
  opções: Binomial Negativa por tipo (Hauer/HSM) e o procedimento da v4 (igual ao script R).
- Numeração oficial: a da v4 (1 = Valor Crítico, 2 = KDE, 3 = Empírico de Bayes), definida num só lugar
  (`utils/constantes.py`). O Manual de 2025 usa outra ordem.

### Desempenho

- KDE: 47 s e 4,5 GB (PE, 970 segmentos) passaram a 5 ms; DF+MG+PE (3.560) e SP (733 mil sinistros),
  inviáveis na v4, rodam em 0,02 s e 37 s.
- Mapas em camada GeoJSON única: 4,7 MB e 4,1 s viraram 1,0 MB e 0,1 s para 3.560 pontos.
- PDF e planilha de resultados gerados uma vez por execução, não a cada clique; mapas em cache e, acima de
  20 mil pontos, só com os segmentos críticos.

### Repositório

- Licença MIT (`LICENSE`).
- Coleta de estatísticas de uso do Streamlit desativada (`.streamlit/config.toml`); regras de lint em
  `ruff.toml`.
- `requirements.txt` com versões fixadas e só o que é usado; `requirements-dev.txt`, `.gitignore`,
  `.python-version`, `README.md`, `THIRD_PARTY_LICENSES.md`, testes em `tests/`.
- Barra lateral mostra o nome do sistema em texto quando `assets/` está vazia (ver `assets/LEIA-ME.md`).
- Hospedagem: `Dockerfile` e `compose.yaml` para servidor próprio e guia para o Streamlit Community Cloud
  (`docs/IMPLANTACAO.md`); testes e lint rodam no GitHub a cada envio (`.github/workflows/testes.yml`).
- Só o aplicativo é publicado: nenhuma planilha real no repositório (o `.gitignore` bloqueia planilhas fora
  dos exemplos fictícios de `data/`).
- Removidos: caches `.pkl`, `__pycache__`, notebook vazio, imagens não usadas e a planilha de dados que vinha com a v4.
