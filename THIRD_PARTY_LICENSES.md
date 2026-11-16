# Componentes de terceiros do SISegC Rodoviário

Levantamento feito em 02/11/2026 com as versões do `requirements.txt` instaladas do zero em Python 3.13
(Linux x86_64). O código do SISegC Rodoviário é distribuído sob a licença MIT (`LICENSE`).

## Resumo das obrigações

- **Nenhuma dependência impõe copyleft ao código do app.** O app usa as bibliotecas sem modificá-las, como
  pacotes instalados à parte pelo `pip`; o repositório não inclui o código delas.
- **Copyleft fraco (LGPL e MPL), restrito às próprias bibliotecas:** fpdf2 (LGPL-3.0), GEOS (LGPL-2.1, dentro
  dos pacotes binários do shapely e do pyogrio), libquadmath (LGPL-2.1, dentro do numpy e do scipy) e certifi
  (MPL-2.0). Quem modificar uma delas e distribuir a versão modificada deve publicar essa modificação sob a
  mesma licença. Usá-las sem modificação não muda a licença do app.
- **libgfortran** (dentro do numpy e do scipy) é GPL-3.0 com a exceção de biblioteca de execução do GCC, que
  permite distribuí-la junto com programas de qualquer licença.
- **Imagem Docker:** quem distribuir a imagem (e não só o código) distribui também essas bibliotecas; basta
  manter os avisos de licença que vêm nos pacotes e indicar onde obter o código-fonte de cada uma (os
  endereços estão nos próprios pacotes).
- **Dados:** os arquivos de `dados_publicos/osm/` estão sob a ODbL 1.0 (atribuição e mesma licença para
  versões modificadas desse banco de dados), não sob a licença do código. Os demais dados são de livre uso com crédito à
  fonte.
- **Fonte e logo:** a fonte Roboto segue a SIL OFL 1.1; o logo segue a licença MIT do repositório (ver `assets/LEIA-ME.md`).

## Bibliotecas Python usadas diretamente

| Pacote | Versão | Licença | Uso |
| --- | --- | --- | --- |
| streamlit | 1.66.0 | Apache-2.0 | interface web |
| pandas | 3.0.6 | BSD-3-Clause | tabelas |
| numpy | 2.5.4 | BSD-3-Clause (com partes 0BSD, MIT, Zlib e CC0-1.0) | cálculo |
| scipy | 1.18.1 | BSD-3-Clause | KD-tree (Trilha 2), Normal padrão |
| statsmodels | 0.15.0 | BSD-3-Clause | Binomial Negativa (Trilha 3) |
| folium | 0.20.0 | MIT | mapas |
| altair | 6.3.0 | BSD-3-Clause | gráficos do painel (instalada com o streamlit; fixada no `requirements.txt`) |
| matplotlib | 3.11.2 | Matplotlib License (baseada na PSF, compatível com BSD) | gráficos e mapa do PDF |
| pillow | 12.3.0 | MIT-CMU | fundo do mapa do PDF (instalada com o matplotlib; fixada no `requirements.txt`) |
| fpdf2 | 2.8.9 | LGPL-3.0-only | relatório PDF (usada como biblioteca, sem modificação) |
| xlsxwriter | 3.2.9 | BSD-2-Clause | exportação Excel |
| openpyxl | 3.1.5 | MIT | leitura de .xlsx |
| shapely | 2.2.0 | BSD-3-Clause | geometria da segmentação |
| pyproj | 3.8.0 | MIT | conversão de coordenadas |
| pyogrio | 0.13.0 | MIT | leitura do SNV e do OpenStreetMap |

## Bibliotecas Python instaladas por elas

| Pacote | Licença | Pacote | Licença |
| --- | --- | --- | --- |
| anyio | MIT | protobuf | BSD-3-Clause |
| attrs | MIT | pyarrow | Apache-2.0 |
| branca | MIT | pydeck | Apache-2.0 |
| certifi | MPL-2.0 | pyparsing | MIT |
| charset-normalizer | MIT | python-dateutil | Apache-2.0 ou BSD-3-Clause |
| click | BSD-3-Clause | python-multipart | Apache-2.0 |
| contourpy | BSD-3-Clause | referencing | MIT |
| cycler | BSD-3-Clause | requests | Apache-2.0 |
| defusedxml | PSF-2.0 | rpds-py | MIT |
| et_xmlfile | MIT | starlette | BSD-3-Clause |
| fonttools | MIT | typing_extensions | PSF-2.0 |
| formulaic | MIT | tzdata | Apache-2.0 |
| h11 | MIT | urllib3 | MIT |
| idna | BSD-3-Clause | uvicorn | BSD-3-Clause |
| interface_meta | MIT | watchdog | Apache-2.0 |
| itsdangerous | BSD-3-Clause | websockets | BSD-3-Clause |
| Jinja2 e MarkupSafe | BSD-3-Clause | wrapt | BSD-2-Clause |
| jsonschema e jsonschema-specifications | MIT | xyzservices | BSD-3-Clause |
| kiwisolver | BSD-3-Clause | narwhals | MIT |
| patsy | BSD-2-Clause | | |

A v4 listava também scikit-learn, geopandas, seaborn, streamlit-folium, numexpr e pyFFTW, que não eram
importados. O pyFFTW foi retirado também por embutir o FFTW, distribuído sob GPL.

## Bibliotecas nativas dentro dos pacotes binários

Os pacotes que o `pip` baixa já vêm compilados e trazem bibliotecas em C, C++ ou Fortran, com os avisos de
licença no próprio pacote.

| Pacote | Bibliotecas embutidas | Licenças |
| --- | --- | --- |
| numpy, scipy | OpenBLAS; libgfortran; libquadmath | BSD-3-Clause; GPL-3.0 com a exceção de execução do GCC; LGPL-2.1 |
| shapely | GEOS | LGPL-2.1 |
| pyogrio | GDAL, com GEOS e PROJ dentro | MIT; LGPL-2.1 (GEOS); MIT (PROJ) |
| pyproj | PROJ, libcurl, nghttp2, SQLite, libtiff | MIT; curl; MIT; domínio público; libtiff |
| pillow | FreeType, HarfBuzz, libjpeg, libpng, libtiff, libwebp, OpenJPEG, Little CMS, zstd, xz, brotli, libavif, libxcb | FreeType License (escolhida entre FTL e GPL-2.0), MIT, BSD e licenças próprias permissivas |
| pyarrow | componentes do Apache Arrow e dependências | Apache-2.0 e licenças permissivas listadas no NOTICE do pacote |

## Componentes carregados pelo navegador (via folium, por CDN)

| Componente | Licença |
| --- | --- |
| Leaflet 1.9.3 | BSD-2-Clause |
| Leaflet.heat (versão incluída no folium) | BSD-2-Clause |
| jQuery 3.7.1 | MIT |
| Bootstrap 5.2.2 e Glyphicons do Bootstrap 3 | MIT |
| Font Awesome Free 6.2.0 | ícones CC BY 4.0, fontes SIL OFL 1.1, código MIT |
| Leaflet.awesome-markers 2.0.2 | MIT |

## Dados embutidos (pasta `dados_publicos/`)

| Base | Fonte | Condições |
| --- | --- | --- |
| Malha do SNV 202610A | DNIT | dados do Poder Executivo federal, de livre utilização com crédito à fonte (Decreto nº 8.777/2016, art. 4º) |
| VMD modelado (2019) | PNCT/DNIT | idem |
| Sinistros por ocorrência, 2021 a 2026 | PRF, dados abertos (gov.br/prf) | idem; a página de dados abertos da PRF permite usar, reutilizar e redistribuir |
| Vias fora do SNV, por UF | OpenStreetMap, extratos da Geofabrik de 24/10/2026 | Open Database License (ODbL 1.0) |
| Exemplo urbano: sinistros de 2022 a 2024 num recorte de Santos (SP) | Infosiga SP, DETRAN-SP (dadosabertos.sp.gov.br/dataset/sinistros-infosiga) | Creative Commons Atribuição 4.0 (CC BY 4.0): uso livre com crédito à fonte, indicação da licença e das alterações |

Os arquivos de `dados_publicos/osm/` são um banco de dados derivado do OpenStreetMap: estão sob a ODbL, não
sob a licença do código. A ODbL pede atribuição (“© colaboradores do OpenStreetMap”, com o link
<https://www.openstreetmap.org/copyright>) e, para versões modificadas que forem publicadas, a mesma licença.
O app mostra a atribuição ao lado dos resultados e o relatório PDF cita as fontes. Quem publicar a planilha de
segmentos com vias do OpenStreetMap (coluna `fonte`) deve citar o OpenStreetMap e seguir as regras da ODbL.

O exemplo urbano dos Primeiros passos (`dados_publicos/exemplos/`) é um recorte dos dados abertos do Infosiga SP,
sob a CC BY 4.0: só id, ano, coordenada, gravidade e UF de cada sinistro, de 2022 a 2024, num retângulo de
Santos. O app mostra a fonte e a licença onde o exemplo aparece (Primeiros passos, barra lateral e descrição
dos dados, que entra no relatório).

Os arquivos que o usuário envia (sinistros próprios, SNV ou VMD mais novos) ficam só na memória da sessão.

## Mapa de fundo

Tiles do OpenStreetMap (dados © colaboradores do OpenStreetMap, ODbL). A atribuição aparece no mapa.
A política de uso dos tiles (https://operations.osmfoundation.org/policies/tiles/) proíbe uso pesado e
não garante disponibilidade; em produção institucional, prefira um provedor de tiles próprio ou contratado.

## Fonte

Roboto 3.009, © 2011 The Roboto Project Authors, SIL Open Font License 1.1 (`static/fonts/OFL.txt`).
A fonte é servida pelo próprio app; não há chamada ao Google Fonts.

## Logo

O logo do SISegC Rodoviário (`assets/logo_horizontal.png` e `assets/icone.png`) acompanha a licença MIT do
repositório (ver `assets/LEIA-ME.md`).
