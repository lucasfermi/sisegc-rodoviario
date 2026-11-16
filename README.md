<p align="center"><img src="assets/logo_horizontal.png" alt="SISegC Rodoviário" width="420"></p>

# SISegC Rodoviário — Sistema de Identificação de Segmentos Críticos Rodoviários

O **SISegC Rodoviário** é uma aplicação web (Streamlit) que identifica segmentos rodoviários críticos a partir de
dados de sinistros, seguindo o **Manual de Identificação de Segmentos Críticos Rodoviários (2026)**. Corta a
malha em segmentos, localiza os sinistros e aplica as três trilhas do Manual (Valor Crítico, Densidade de
Kernel e Empírico de Bayes), com um painel de indicadores, mapas, tabelas, relatório executivo em PDF e
planilhas para baixar. Versão estável atual: **4.3.4** (ver `CHANGELOG.md`).

## Métodos

| Trilha | Método | Dados necessários |
| --- | --- | --- |
| 1 | Valor Crítico: frequência de sinistros, severidade (UPS), taxa de frequência e taxa de severidade (Manual, item 3.1) | sinistros e extensão; VMD para os métodos de taxa |
| 2 | Densidade de Kernel (KDE), banda de 1 km, células de 500 m, quartil superior das densidades dos sinistros, por severidade (UPS) ou frequência (Manual, item 3.2) | sinistros e coordenadas |
| 3 | Empírico de Bayes: Binomial Negativa sobre a exposição (Manual 2026, item 3.3); opções: Binomial Negativa por tipo de sinistro (Hauer/HSM), Média Global por tipo de sinistro (Marshall, 1991) e procedimento da v4 | sinistros, extensão e VMD |

A numeração das trilhas segue o Manual de Identificação de Segmentos Críticos Rodoviários (2026) e o Manual de Utilização (`utils/constantes.py`).

A severidade usa a Unidade Padrão de Severidade: `UPS = 1 × sem vítima + 4 × com vítima + 28 × com óbito`
(pesos ajustáveis na interface).

## Como executar

Requer Python 3.13. Use um ambiente virtual só para esta versão: o pacote `fpdf` antigo, usado até a v4,
conflita com o `fpdf2` (erro `No module named 'fpdf.enums'`). Se o ambiente estiver errado, o app mostra
os comandos abaixo em vez do erro.

Windows (cmd ou PowerShell), na pasta do projeto:

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

Linux ou macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

No VS Code, selecione o interpretador `.venv` (Ctrl+Shift+P → “Python: Select Interpreter”).

Para hospedar o app (Streamlit Community Cloud ou servidor próprio com Docker), veja `docs/IMPLANTACAO.md`.

Testes: instale `requirements-dev.txt` no mesmo ambiente e rode `python -m pytest`. Os testes da Trilha 1
reproduzem os exemplos resolvidos do Manual (Tabelas 5.1 a 5.5).

## Como usar

Quem abre o app pela primeira vez encontra o botão **Primeiros passos**: um guia com imagens das telas e dois
exemplos prontos, um de rodovias federais (sinistros da PRF no DF) e um urbano (sinistros do Infosiga SP num
recorte de Santos). Logo abaixo dele, o botão **Manual de Utilização (PDF)** abre o manual completo numa nova
aba. O caminho de uma análise:

1. **Dados:** na barra lateral, em “Entrada de dados”, escolha a UF e os anos (segmentação automática com os
   dados embutidos), envie seus sinistros em “Usar meus dados de sinistros” ou uma planilha de segmentos em
   “Outras formas de entrada”. Cada opção tem um Modelo Preenchido e um Modelo em Branco, com uma aba de
   instruções.
2. **Características dos dados carregados:** bloco recolhido abaixo das configurações, com o resumo dos dados
   (segmentos, extensão, sinistros por gravidade, cobertura do VMD), os avisos de qualidade (sinistros fora da
   análise, VMD de outro ano, coordenadas repetidas) e a tabela dos segmentos.
3. **Painel:** as três trilhas juntas, com filtros por trilha, via e número mínimo de trilhas: números
   principais, críticos por trilha, quanto os críticos concentram dos sinistros, convergência entre as
   trilhas, distribuição da UPS, mapa, vias com mais críticos e o ordenamento dos segmentos críticos.
4. **Trilhas:** uma aba por trilha, com o mapa e a tabela de todos os segmentos.
5. **Relatório e planilhas:** o relatório executivo em PDF reúne o painel num arquivo (números principais,
   mapa, convergência, fichas dos 10 primeiros segmentos do ordenamento, distribuição da UPS, resultados por trilha,
   limitações e a metodologia com os parâmetros usados); a planilha traz o resumo, o ordenamento dos segmentos críticos (aba `Ordenamento`) e uma
   aba por trilha, com nomes de colunas por extenso. No mapa do relatório, o fundo do OpenStreetMap é baixado
   na hora; sem internet, o mapa sai só com o desenho da malha.

Nos mapas e gráficos de convergência, a cor diz em quantas trilhas o segmento é crítico: amarelo (uma),
vermelho (duas) e roxo (as três).

## Segmentação automática

O app já traz os dados públicos de que precisa (pasta `dados_publicos/`): a malha do SNV 202610A (DNIT), os
sinistros por ocorrência da PRF de 2021 a 2026, o VMD modelado pelo PNCT (2019) e as vias do OpenStreetMap
fora do SNV, por UF. Basta escolher a UF, os anos e o comprimento do segmento (1 km por padrão; de 0,1 a
10 km): o app corta a malha, localiza os sinistros e roda as três trilhas sozinho, sem envio de arquivos.

- **Sinistros da PRF (padrão):** cobrem só as rodovias federais. O ano mais recente costuma estar
  incompleto, por isso os anos sugeridos são os três últimos completos.
- **Meus dados de sinistros:** planilha com latitude, longitude, data (DD/MM/AAAA ou AAAA-MM-DD, com ou
  sem hora) ou ano e gravidade de cada sinistro, de qualquer via; também servem os arquivos da PRF
  (`datatranAAAA`, inclusive “por pessoa”). A gravidade vem de uma coluna de texto (“Sem vítima”, “Com
  vítima”, “Com óbito”) ou das contagens (`mortos` maior que zero = com óbito; `feridos` = com vítima). Os
  sinistros fora do SNV vão para as vias do OpenStreetMap; as ruas residenciais entram por padrão, menos
  quando os sinistros cobrem uma área grande (ex.: uma UF inteira): com elas, SP passa de 1 milhão de
  segmentos e a análise leva minutos e cerca de 3 GB de memória. A malha (SNV e OpenStreetMap) fica no
  retângulo dos sinistros: com a base de um município, os segmentos do SNV de outras regiões, que a base não
  cobre, não entram como segmentos sem sinistros.
- **Avançado:** um SNV ou um VMD mais novo que o embutido pode ser enviado no lugar dele.

Cada trecho do SNV com pista é dividido em segmentos que não atravessam o limite do trecho; uma sobra menor
que meio segmento se junta ao segmento anterior. O ID segue o código do SNV (`010BDF0010-002` é o 2º
segmento do trecho) e a coluna `rodovia` traz a BR e os km. BRs coincidentes (mesma pista) contam uma vez,
no trecho principal. Cada sinistro da PRF vai para o ponto mais próximo da BR informada pela coordenada
(até 500 m); sem coordenada, vale o km. Sinistros só com coordenada vão para o trecho mais próximo (até
100 m); se esse trecho for de outra UF, o sinistro fica de fora e aparece no resumo.

**VMD.** Cada segmento recebe o VMD do trecho de mesmo código na planilha do PNCT, com a posição levada
pela fração do trecho (o km pode mudar entre versões do SNV); se o código não existir, vale o trecho da
mesma BR que contém o km do meio do segmento, só no eixo principal (acessos, contornos, travessias, variantes
e anéis têm quilometragem própria). O VMD do segmento é a soma dos dois sentidos (com a análise
por sentido, cada sentido usa o seu). O app avisa quando o PNCT marca o trecho como “Não Simulável” e quando
o ano do VMD difere do ano dos sinistros. Sem VMD, a Trilha 3 e os métodos de taxa da Trilha 1 não rodam.
Com a planilha de 2019 e o SNV 202610A, 15% dos segmentos do país ficam sem VMD: dois terços são rodovias
não pavimentadas, que o PNCT não modela; o resto são trechos pavimentados depois de 2019, trechos que o
PNCT não conseguiu simular e trechos criados depois da versão 202001A do SNV.

**OpenStreetMap.** As vias de cada UF foram preparadas a partir dos extratos regionais da Geofabrik: classes
de via expressa a via local, mais as ruas residenciais em arquivo à parte; sem as rodovias federais e sem o
que fica a até 40 m do SNV; pedaços com o mesmo nome ou código (ex.: DF-001) unidos; uma só pista onde a via
é duplicada. O app lê as vias do retângulo dos sinistros, corta-as em segmentos do mesmo comprimento (IDs
`OSMDF000001-001`) e prende cada sinistro à via mais próxima, até 50 m. Os dados do OpenStreetMap são
© colaboradores do OpenStreetMap, sob a licença ODbL; a atribuição aparece no app e no relatório.

## Formato dos dados

Quem já tem os segmentos numa planilha pode usá-la em “Outras formas de entrada”, na barra lateral. A
planilha (CSV ou .xlsx) pode estar no modelo do app (botão “Modelo Preenchido”), ser a planilha baixada da
segmentação automática ou estar no formato das planilhas oficiais (`ID`, `CodigoSNV`, `Comprimento`,
`Latitude Média`, `Longitude Média`, `Sentido`, `VMD AAAA`, `Sinistros_SV/CV/CO AAAA`).

| Coluna (nome técnico também aceito) | Conteúdo | Usada em |
| --- | --- | --- |
| ID do segmento (`segmento_id`) | identificador do segmento | todas |
| Sinistros sem vítima, com vítima e com óbito (`sem_vitima`, `com_vitima`, `com_obito`) | número de sinistros de cada tipo no período | todas |
| Extensão (km) (`extensao_trecho`) | extensão em km (o Manual recomenda segmentos de 1 km) | Trilhas 1 e 3 |
| VMD (veículos/dia) (`volume_trafego`) | volume médio diário anual, nos dois sentidos | Trilha 3 e taxas da Trilha 1 |
| Latitude e Longitude | graus decimais | Trilha 2 e mapas |
| Anos de dados (`n_anos`) ou `ano` | anos somados nas contagens; com `ano`, várias linhas do mesmo segmento são somadas | período |
| Rodovia ou via (`rodovia`) | descrição do segmento, opcional | tabelas e relatório |

Uma planilha com um sinistro por linha (sem a extensão dos segmentos) vai em “Usar meus dados de
sinistros”, na segmentação automática; como planilha de segmentos, só a Trilha 2 roda com ela, e o app
avisa. CSV com `;` e vírgula decimal (padrão do
Excel em português) é aceito. Em planilhas oficiais, o mesmo `ID`
nos dois sentidos vira dois segmentos (`25-C` e `25-D`).

## Privacidade

O app não grava os arquivos enviados: os dados ficam na memória da sessão e são descartados quando ela
termina. Os mapas buscam no OpenStreetMap as imagens (tiles) da área analisada: os do app, pelo navegador; o do
relatório PDF, pelo servidor. Nenhum dado de sinistro vai junto. Para o servidor não buscar o fundo do mapa do
relatório, defina a variável de ambiente `SISEGC_MAPA_DE_FUNDO=0`. O repositório traz só dados públicos, sem dados pessoais (`dados_publicos/`, ver o LEIA-ME da pasta);
os arquivos de `data/` são exemplos fictícios usados nos testes.

## Estrutura

```
app.py                 interface Streamlit
models/                trilha1_valor_critico.py, trilha2_kernel.py, trilha3_bayes.py
utils/                 entrada (leitura e validação), preprocessamento (UPS), segmentacao (SNV e
                       sinistros), trafego (VMD do PNCT), osm (vias do OpenStreetMap), dados_publicos
                       (leitura dos dados embutidos), painel (indicadores e convergência), tabelas (nomes
                       das colunas), modelos (planilhas-modelo), mapas, relatorio (PDF executivo)
dados_publicos/        SNV, sinistros da PRF, VMD do PNCT e vias do OpenStreetMap por UF, prontos para uso,
                       e o exemplo urbano dos Primeiros passos (exemplos/)
ferramentas/           preparar_dados.py (gera dados_publicos/ a partir dos arquivos oficiais),
                       benchmark.py (tempo e memória), exemplos_demonstracao.py (planilhas de
                       exemplo), desempenho/ (o KDE em Python, C e R, para comparar o desempenho)
                       e servidor/ (instalação e atualização num Ubuntu Server)
static/fonts/          fonte Roboto (SIL OFL 1.1), servida localmente
static/manual/         Manual de Utilização (PDF), aberto pelo botão da barra lateral
assets/                logo do sistema e ícone (ver assets/LEIA-ME.md); guia/ com as imagens dos Primeiros passos
data/                  exemplos fictícios usados nos testes, inclusive os 15 segmentos do Manual
docs/                  guia de hospedagem (IMPLANTACAO.md)
tests/                 testes automatizados (pytest), também rodados no GitHub a cada envio
Dockerfile, compose.yaml   imagem para servidor próprio
```

## Como contribuir

Sugestões e correções são bem-vindas por *issues* e *pull requests*. Antes de enviar uma alteração, rode
`python -m pytest`.

## Desenvolvimento e autoria técnica

- **Desenvolvimento institucional:** Programa de Pós-Graduação em Transportes da Universidade de Brasília (PPGT/UnB).
- **Desenvolvedor técnico:** Lucas Fermi Pereira de Oliveira, Programa de Pós-Graduação em Transportes da Universidade de Brasília (PPGT/UnB).

## Como citar

Os dados de citação estão em `CITATION.cff` (o GitHub os mostra em “Cite this repository”).

> OLIVEIRA, Lucas Fermi Pereira de. **SISegC Rodoviário: Sistema de Identificação de Segmentos Críticos
> Rodoviários**. Versão 4.3.4. Brasília: Universidade de Brasília, 2026. Software.

```bibtex
@software{sisegc_rodoviario,
  author    = {Oliveira, Lucas Fermi Pereira de},
  title     = {{SISegC Rodoviário}: Sistema de Identificação de Segmentos Críticos Rodoviários},
  version   = {4.3.4},
  year      = {2026},
  publisher = {Universidade de Brasília}
}
```

## Referências

Método:

- Manual de Identificação de Segmentos Críticos Rodoviários. Brasília, 2026.
- AASHTO. *Highway Safety Manual*. 1. ed. Washington, DC: American Association of State Highway and
  Transportation Officials, 2010.
- HAUER, E.; HARWOOD, D. W.; COUNCIL, F. M.; GRIFFITH, M. S. Estimating safety by the empirical Bayes
  method: a tutorial. *Transportation Research Record*, n. 1784, p. 126–131, 2002.
- MARSHALL, R. J. Mapping disease and mortality rates using empirical Bayes estimators. *Journal of the
  Royal Statistical Society: Series C (Applied Statistics)*, v. 40, n. 2, p. 283–294, 1991.
- SILVERMAN, B. W. *Density Estimation for Statistics and Data Analysis*. London: Chapman and Hall, 1986.

Dados embutidos:

- DNIT. Sistema Nacional de Viação (SNV), versão 202610A.
- DNIT. Plano Nacional de Contagem de Tráfego (PNCT): VMD modelado, 2019.
- PRF. Dados abertos de sinistros de trânsito por ocorrência (datatran), 2021 a 2026.
- Colaboradores do OpenStreetMap. Extratos regionais da Geofabrik de 24/10/2026, sob a licença ODbL 1.0.
- DETRAN-SP. Infosiga SP: sinistros de trânsito, dados abertos (dadosabertos.sp.gov.br), sob a licença
  CC BY 4.0; recorte de Santos (SP), 2022 a 2024, no exemplo urbano.

## Versões

O histórico está em `CHANGELOG.md`. Cada versão publicada tem uma *tag* (`v4.1.0`, `v4.1.1`, `v4.1.2`,
`v4.2.0`, `v4.3.0`, `v4.3.1`, `v4.3.2`, `v4.3.3`, `v4.3.4`) e uma página de *release* no GitHub com as notas da
versão; a 4.3.4 é a versão estável atual. A série 4.1, revisão do protótipo, segue no ramo `versao-4.1` (versão
4.1.3).

## Licença

O código-fonte e os ativos próprios do repositório (`assets/`) são distribuídos sob a licença **MIT** (`LICENSE`),
permitindo livre utilização, modificação e redistribuição. As dependências têm licenças compatíveis com a licença
MIT (ver `THIRD_PARTY_LICENSES.md`); a fonte Roboto segue a SIL OFL 1.1 (`static/fonts/OFL.txt`).
Os dados de `dados_publicos/` têm as condições das suas fontes: os do DNIT e da PRF são de livre uso com
crédito à fonte, os do OpenStreetMap (`dados_publicos/osm/`) seguem a ODbL 1.0 e o exemplo urbano
(`dados_publicos/exemplos/`, Infosiga SP) segue a CC BY 4.0.
