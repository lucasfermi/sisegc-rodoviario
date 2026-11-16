"""Prepara os dados públicos embutidos no app (pasta dados_publicos/) a partir dos arquivos oficiais.

Uso, na pasta do projeto (cada passo atualiza dados_publicos/versoes.json):

    python ferramentas/preparar_dados.py snv SNV_202610A.shp          (ou um .zip com o shapefile)
    python ferramentas/preparar_dados.py vmd VDM_Modelagem_2019_SNV_202001A.xlsx
    python ferramentas/preparar_dados.py prf datatran2021.zip datatran2022.zip ...
    python ferramentas/preparar_dados.py osm-extrair sudeste.osm.pbf sudeste.parquet principais [oeste,sul,leste,norte]
    python ferramentas/preparar_dados.py osm --extrato=2026-10-24 vias/*.parquet
    python ferramentas/preparar_dados.py exemplo-urbano sinistros_sp.csv SP -46.375,-23.995,-46.295,-23.925 \
        2022-2024 "Santos (SP)" "Infosiga SP (DETRAN-SP)"

O passo ``osm`` usa o SNV já preparado: tira das vias o que o SNV cobre. Os arquivos regionais do
OpenStreetMap vêm de download.geofabrik.de (Brasil: norte, nordeste, centro-oeste, sudeste e sul); o passo
``osm-extrair`` lê um deles e grava as vias de uma classe (principais ou urbanas), com a geometria
simplificada. Para arquivos grandes, extraia por partes (retângulos) e passe todas ao passo ``osm``.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import time
from datetime import date
from multiprocessing import Pool
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import shapely  # noqa: E402

from utils import dados_publicos as dp  # noqa: E402
from utils import osm  # noqa: E402
from utils import segmentacao as sg  # noqa: E402
from utils import trafego as tf  # noqa: E402

PASTA = dp.PASTA
CLASSES = {"principais": osm.CLASSES_PRINCIPAIS, "urbanas": osm.CLASSES_URBANAS}
FEDERAL = r"(?:^|;)\s*BR[- ]?\d"


def _atualizar_versoes(chave: str, valor) -> None:
    arq = PASTA / "versoes.json"
    versoes = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    versoes[chave] = valor
    versoes["gerado_em"] = date.today().isoformat()
    arq.write_text(json.dumps(versoes, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def _gravar(df: pd.DataFrame, arquivo: Path, metadados: dict | None = None, linhas_por_grupo: int = 50_000) -> None:
    tabela = pa.Table.from_pandas(df, preserve_index=False)
    if metadados:
        tabela = tabela.replace_schema_metadata({**(tabela.schema.metadata or {}),
                                                 b"attrs": json.dumps(metadados).encode()})
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(tabela, arquivo, compression="zstd", compression_level=9, row_group_size=linhas_por_grupo)
    print(f"{arquivo.relative_to(RAIZ)}: {len(df):,} linhas, {arquivo.stat().st_size / 1e6:.1f} MB")


def preparar_snv(fonte: str) -> None:
    """Shapefile do SNV (ou .zip com ele) -> dados_publicos/snv/UF.parquet."""
    if fonte.lower().endswith(".zip"):
        bruto = sg.ler_snv_enviado([(Path(fonte).name, Path(fonte).read_bytes())])
    else:
        bruto = sg.carregar_snv(fonte)
    colunas = [*sg.COLUNAS_SNV, "versao_snv"]
    t = bruto[[c for c in colunas if c in bruto] + ["geometry"]].copy()
    for c in colunas:
        if c in t and c not in ("vl_km_inic", "vl_km_fina"):
            t[c] = t[c].astype("string").str.strip()
    t["vl_km_inic"] = sg._numero(t["vl_km_inic"])
    t["vl_km_fina"] = sg._numero(t["vl_km_fina"])
    t = t[t["geometry"].notna()].sort_values(["sg_uf", "vl_br", "vl_km_inic"]).reset_index(drop=True)
    # coordenadas arredondadas a 1e-6 grau (~0,1 m): 42 MB em vez de 73 MB; um arquivo por UF
    t["geometry"] = shapely.to_wkb(shapely.set_precision(t["geometry"].to_numpy(), 1e-6))
    for uf, parte in t.groupby("sg_uf"):
        _gravar(parte.reset_index(drop=True), PASTA / "snv" / f"{uf}.parquet", linhas_por_grupo=2_000)
    versao = str(t["versao_snv"].dropna().iloc[0]) if "versao_snv" in t and t["versao_snv"].notna().any() else None
    _atualizar_versoes("snv", {"versao": versao, "fonte": "DNIT", "trechos": len(t)})


def preparar_vmd(fonte: str) -> None:
    """Planilha de modelagem do PNCT -> dados_publicos/vmd_pnct.parquet."""
    v = tf.ler_vmd_pnct(fonte, nome=Path(fonte).name)
    _gravar(v, PASTA / "vmd_pnct.parquet", metadados=dict(v.attrs))
    _atualizar_versoes("vmd", {**v.attrs, "fonte": "PNCT/DNIT", "trechos": len(v)})


def preparar_prf(fontes: list[str]) -> None:
    """Arquivos datatran da PRF (por ocorrência) -> dados_publicos/sinistros_prf.parquet."""
    s = sg.ler_arquivos_prf([(Path(f).name, Path(f).read_bytes()) for f in fontes])
    s = s[s["ano"].notna()].sort_values(["uf", "ano", "data"]).reset_index(drop=True)
    s["data"] = s["data"].dt.date
    _gravar(s, PASTA / "sinistros_prf.parquet", linhas_por_grupo=25_000)
    _atualizar_versoes("prf", {"fonte": "PRF (dados abertos, por ocorrência)",
                               "anos": sorted(int(a) for a in s["ano"].unique()),
                               "ultima_data": str(max(s["data"])), "sinistros": len(s)})


def extrair_osm(fonte: str, saida: str, conjunto: str, retangulo: str | None = None) -> None:
    """Vias de um .osm.pbf (uma classe: principais ou urbanas) em Parquet, simplificadas a ~4 m."""
    import pyarrow.compute as pc
    from pyogrio.raw import open_arrow

    t0 = time.time()
    onde = "highway IN (" + ",".join(f"'{c}'" for c in CLASSES[conjunto]) + ")"
    bbox = tuple(float(x) for x in retangulo.split(",")) if retangulo else None
    esquema = pa.schema([("osm_id", pa.string()), ("nome", pa.string()), ("ref", pa.string()),
                         ("classe", pa.string()), ("geometry", pa.binary())])
    n = 0
    with open_arrow(fonte, layer="lines", where=onde, columns=["osm_id", "name", "highway", "other_tags"],
                    batch_size=200_000, use_pyarrow=True, bbox=bbox) as (_, leitor), \
            pq.ParquetWriter(saida, esquema, compression="zstd") as escritor:
        for lote in leitor:
            col_geo = [c for c in lote.schema.names if c not in ("osm_id", "name", "highway", "other_tags")][0]
            g = shapely.from_wkb(lote.column(col_geo).to_numpy(zero_copy_only=False))
            g = shapely.set_precision(shapely.simplify(g, 4e-5), 1e-6)
            ok = pa.array(~(shapely.is_missing(g) | shapely.is_empty(g)))
            ref = pc.struct_field(pc.extract_regex(lote.column("other_tags"), r'"ref"=>"(?P<ref>[^"]*)"'), "ref")
            escritor.write_table(pa.table({
                "osm_id": pc.cast(lote.column("osm_id"), pa.string()),
                "nome": pc.cast(lote.column("name"), pa.string()), "ref": ref,
                "classe": pc.cast(lote.column("highway"), pa.string()),
                "geometry": pa.array(shapely.to_wkb(g), pa.binary())}, schema=esquema).filter(ok))
            n += int(pc.sum(ok).as_py() or 0)
    print(f"{saida}: {n:,} vias em {time.time() - t0:.0f} s")


# --- passo osm: vias por UF -------------------------------------------------------------------------
_SNV = None


def _snv_preparado() -> pd.DataFrame:
    global _SNV
    if _SNV is None:
        _SNV = sg.preparar_snv(dp.ler_snv())
    return _SNV


def _montar_uf(tarefa: tuple[str, str, str]) -> tuple[str, str, dict]:
    uf, conjunto, arquivo = tarefa
    t0 = time.time()
    df = pq.read_table(arquivo).to_pandas().drop_duplicates("osm_id")
    refs = df["ref"].astype("string")
    vias_osm = pd.DataFrame({
        "osm_id": df["osm_id"].astype(str), "nome": df["nome"].astype("string").str.strip(),
        "ref": refs.str.split(";").str[0].str.strip(),
        "federal": refs.fillna("").str.upper().str.contains(FEDERAL, regex=True),
        "classe": df["classe"].astype(str), "geometry": shapely.from_wkb(df["geometry"].to_numpy())})
    vias = osm.montar_vias(vias_osm, _snv_preparado())
    sufixo = "R" if conjunto == "urbanas" else ""
    vias["codigo_via"] = [f"OSM{uf}{sufixo}{i:06d}" for i in range(1, len(vias) + 1)]
    # 5 m de simplificação e coordenadas em metros inteiros: um quarto a menos de espaço, sem efeito no
    # corte em segmentos nem na localização dos sinistros (até 50 m)
    geom = shapely.set_precision(shapely.simplify(vias["geom_m"].to_numpy(), 5.0), 1.0)
    limites = shapely.bounds(sg._transformar(geom, sg._PARA_GEO))
    out = pd.DataFrame({
        "codigo_via": vias["codigo_via"], "rotulo": vias["rotulo"].astype("string"),
        "nome": vias["nome"].astype("string"), "classe": vias["classe"].astype(str),
        "comprimento_m": np.round(shapely.length(geom), 1),
        "xmin": limites[:, 0], "ymin": limites[:, 1], "xmax": limites[:, 2], "ymax": limites[:, 3],
        "geometry": shapely.to_wkb(geom)})
    out = out.assign(_faixa=(out["ymin"] // 0.25)).sort_values(["_faixa", "xmin"]).drop(columns="_faixa")
    _gravar(out, PASTA / "osm" / f"{uf}_{conjunto}.parquet", linhas_por_grupo=20_000)
    info = {"vias": len(out), "km": round(float(out["comprimento_m"].sum()) / 1000),
            "bbox": [float(limites[:, 0].min()), float(limites[:, 1].min()), float(limites[:, 2].max()),
                     float(limites[:, 3].max())] if len(out) else None}
    print(f"  {uf} {conjunto}: {len(df):,} pedaços -> {len(out):,} vias, {info['km']:,} km ({time.time() - t0:.0f} s)",
          flush=True)
    return uf, conjunto, info


def preparar_osm(arquivos: list[str], processos: int = 2, extrato: str | None = None) -> None:
    """Vias extraídas (osm-extrair) -> dados_publicos/osm/UF_principais.parquet e UF_urbanas.parquet.

    Cada via vai para a UF do trecho do SNV mais próximo do seu centro; perto das divisas, o app lê as
    UFs vizinhas também."""
    from scipy.spatial import cKDTree

    snv = _snv_preparado()
    base = sg._trechos_base(snv)
    # pontos a cada 500 m ao longo dos trechos: o mais próximo dá a UF (a distância exata a linhas com
    # milhares de vértices seria muito mais lenta e não muda a UF)
    geoms = base["geom_m"].to_numpy()
    n_pts = np.maximum(2, np.ceil(shapely.length(geoms) / 500).astype(int) + 1)
    fracoes = np.concatenate([np.linspace(0, 1, k) for k in n_pts])
    pontos = shapely.line_interpolate_point(np.repeat(geoms, n_pts), fracoes, normalized=True)
    arvore = cKDTree(np.column_stack([shapely.get_x(pontos), shapely.get_y(pontos)]))
    uf_ponto = np.repeat(base["sg_uf"].to_numpy(), n_pts)
    with tempfile.TemporaryDirectory(prefix="osm_uf_") as pasta_tmp:
        escritores: dict[tuple[str, str], pq.ParquetWriter] = {}
        for arquivo in arquivos:
            conjunto = "urbanas" if "urbanas" in Path(arquivo).stem else "principais"
            t0 = time.time()
            for lote in pq.ParquetFile(arquivo).iter_batches(batch_size=200_000):
                tab = pa.Table.from_batches([lote])
                centro = shapely.centroid(shapely.from_wkb(tab.column("geometry").to_numpy(zero_copy_only=False)))
                x, y = sg._PARA_METRICO.transform(shapely.get_x(centro), shapely.get_y(centro))
                _, i_ponto = arvore.query(np.column_stack([x, y]), workers=-1)
                ufs = uf_ponto[i_ponto]
                for uf in np.unique(ufs):
                    chave = (uf, conjunto)
                    if chave not in escritores:
                        escritores[chave] = pq.ParquetWriter(f"{pasta_tmp}/{uf}_{conjunto}.parquet", tab.schema,
                                                             compression="zstd")
                    escritores[chave].write_table(tab.filter(pa.array(ufs == uf)))
            print(f"{Path(arquivo).name}: distribuído entre as UFs ({time.time() - t0:.0f} s)", flush=True)
        for e in escritores.values():
            e.close()
        tarefas = sorted(((uf, c, f"{pasta_tmp}/{uf}_{c}.parquet") for uf, c in escritores),
                         key=lambda t: -Path(t[2]).stat().st_size)
        with Pool(processos) as pool:
            resultados = pool.map(_montar_uf, tarefas, chunksize=1)
    ufs: dict[str, dict] = {}
    for uf, conjunto, info in resultados:
        ufs.setdefault(uf, {})[conjunto] = info
    for info in ufs.values():
        caixas = [i["bbox"] for i in info.values() if i.get("bbox")]
        info["bbox"] = [min(c[0] for c in caixas), min(c[1] for c in caixas), max(c[2] for c in caixas),
                        max(c[3] for c in caixas)] if caixas else None
    datas = [extrato] if extrato else sorted({m.group(1) for a in arquivos
                                              if (m := re.search(r"(\d{6})", Path(a).name))})
    _atualizar_versoes("osm", {"fonte": "© colaboradores do OpenStreetMap (ODbL)", "extratos": datas,
                               "snv": snv["versao_snv"].dropna().iloc[0] if snv["versao_snv"].notna().any() else None,
                               "ufs": dict(sorted(ufs.items()))})


def preparar_exemplo_urbano(fonte: str, uf: str, retangulo: str, anos: str, nome: str, origem: str) -> None:
    """Sinistros do exemplo urbano dos Primeiros passos -> dados_publicos/exemplos/sinistros_urbanos.parquet.

    ``fonte``: planilha de sinistros num formato que o app lê (ex.: os dados abertos do Infosiga SP já com uma
    linha por sinistro, latitude, longitude, ano ou data e gravidade); ``retangulo``: oeste,sul,leste,norte;
    ``anos``: AAAA-AAAA. Só id, ano, coordenada, gravidade e UF vão para o arquivo."""
    s = sg.ler_arquivos_sinistros([(Path(fonte).name, Path(fonte).read_bytes())])
    o, su, le, n = (float(v) for v in retangulo.split(","))
    a0, a1 = (int(v) for v in anos.split("-"))
    s = s[s["ano"].between(a0, a1) & s["longitude"].between(o, le) & s["latitude"].between(su, n)]
    texto = {"sem_vitima": "Sem vítima", "com_vitima": "Com vítima", "com_obito": "Com óbito"}
    saida = pd.DataFrame({"id": s["id"].astype(str), "ano": s["ano"].astype(int),
                          "latitude": s["latitude"].round(7), "longitude": s["longitude"].round(7),
                          "gravidade": s["gravidade"].map(texto), "uf": uf}).sort_values(["ano", "id"])
    _gravar(saida.reset_index(drop=True), PASTA / "exemplos" / "sinistros_urbanos.parquet")
    _atualizar_versoes("exemplo_urbano", {
        "nome": nome, "uf": uf, "anos": list(range(a0, a1 + 1)), "sinistros": len(saida),
        "retangulo": [o, su, le, n], "fonte": origem,
        "licenca": "Creative Commons Atribuição 4.0 (CC BY 4.0)",
        "endereco": "https://dadosabertos.sp.gov.br/dataset/sinistros-infosiga",
        "recorte": "retângulo da área urbana; só id, ano, coordenada, gravidade e UF"})


if __name__ == "__main__":
    passo, *args = sys.argv[1:] or ["ajuda"]
    if passo == "snv":
        preparar_snv(args[0])
    elif passo == "vmd":
        preparar_vmd(args[0])
    elif passo == "prf":
        preparar_prf(args)
    elif passo == "osm-extrair":
        extrair_osm(*args)
    elif passo == "osm":
        extrato = next((a.split("=", 1)[1] for a in args if a.startswith("--extrato=")), None)
        preparar_osm([a for a in args if not a.startswith("--")], extrato=extrato)
    elif passo == "exemplo-urbano":
        preparar_exemplo_urbano(*args)
    else:
        print(__doc__)
