# Dados públicos embutidos

Bases que o app usa na segmentação automática, para que ninguém precise baixar e enviar arquivos. Todas
são públicas e não têm dados pessoais. Foram geradas por `ferramentas/preparar_dados.py` a partir dos
arquivos oficiais; as versões e datas estão em `versoes.json`.

| Arquivo | Conteúdo | Fonte |
| --- | --- | --- |
| `snv/UF.parquet` | trechos do Sistema Nacional de Viação de cada UF, com a geometria (coordenadas arredondadas a ~0,1 m) | DNIT |
| `vmd_pnct.parquet` | VMD anual modelado por trecho do SNV e sentido | PNCT/DNIT |
| `sinistros_prf.parquet` | sinistros por ocorrência nas rodovias federais (data, UF, BR, km, coordenada, gravidade, sentido, município) | PRF, dados abertos |
| `osm/UF_principais.parquet` | vias do OpenStreetMap fora do SNV (via expressa a via local), já unidas e com uma pista por via | OpenStreetMap |
| `osm/UF_urbanas.parquet` | ruas residenciais e vias compartilhadas do OpenStreetMap | OpenStreetMap |
| `exemplos/sinistros_urbanos.parquet` | exemplo urbano dos Primeiros passos: sinistros de 2022 a 2024 num recorte retangular de Santos (SP), só com id, ano, coordenada, gravidade e UF | Infosiga SP (DETRAN-SP), dados abertos |

## Condições de uso

- **SNV, PNCT e PRF:** dados do Poder Executivo federal, de livre utilização pela sociedade (Decreto
  nº 8.777/2016, art. 4º), com crédito à fonte. O app e o relatório citam DNIT, PNCT e PRF.
- **OpenStreetMap:** os arquivos da pasta `osm/` são um banco de dados derivado do OpenStreetMap e estão
  sob a Open Database License (ODbL 1.0), não sob a licença do código. Dados © colaboradores do
  OpenStreetMap (<https://www.openstreetmap.org/copyright>). Quem redistribuir esses arquivos, ou uma
  versão modificada deles, deve manter a atribuição e a mesma licença.

- **Infosiga SP:** o exemplo urbano é um recorte dos dados abertos do Infosiga SP, publicados pelo
  Departamento Estadual de Trânsito de São Paulo (DETRAN-SP) em
  <https://dadosabertos.sp.gov.br/dataset/sinistros-infosiga> sob a licença Creative Commons Atribuição 4.0
  (CC BY 4.0, <https://creativecommons.org/licenses/by/4.0/>). Alterações: recorte de Santos (SP) e de 2022 a
  2024, só as colunas que o app usa, gravidade em texto. O app mostra a fonte e a licença sempre que o exemplo
  é usado.

## Como atualizar

Na pasta do projeto, com os arquivos oficiais baixados:

```bash
python ferramentas/preparar_dados.py snv SNV_202610A.shp            # shapefile extraído do pub_AAAAMMA.zip
python ferramentas/preparar_dados.py vmd VDM_Modelagem_2019_SNV_202001A.xlsx
python ferramentas/preparar_dados.py prf datatran2021.zip datatran2022.zip ...
python ferramentas/preparar_dados.py osm-extrair sudeste-latest.osm.pbf sudeste.parquet principais
python ferramentas/preparar_dados.py osm-extrair sudeste-latest.osm.pbf sudeste_urbanas.parquet urbanas
python ferramentas/preparar_dados.py osm --extrato=AAAA-MM-DD *.parquet
python ferramentas/preparar_dados.py exemplo-urbano sinistros_sp.csv SP -46.375,-23.995,-46.295,-23.925 \
    2022-2024 "Santos (SP)" "Infosiga SP (DETRAN-SP)"
```

O passo `osm` usa o SNV já preparado: rode-o depois de atualizar o SNV. Os extratos regionais do
OpenStreetMap estão em <https://download.geofabrik.de/south-america/brazil.html>.
