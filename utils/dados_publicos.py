"""Dados públicos embutidos no app (pasta dados_publicos/), para a segmentação automática sem envio de arquivos.

- ``snv/UF.parquet``: trechos do SNV (DNIT) de cada UF, com a geometria;
- ``vmd_pnct.parquet``: VMD modelado pelo PNCT (DNIT) por trecho do SNV;
- ``sinistros_prf.parquet``: sinistros por ocorrência dos dados abertos da PRF;
- ``osm/UF_principais.parquet`` e ``osm/UF_urbanas.parquet``: vias do OpenStreetMap fora do SNV, já unidas
  (``osm.montar_vias``), com a geometria em metros (EPSG:5880);
- ``exemplos/sinistros_urbanos.parquet``: sinistros do exemplo urbano dos Primeiros passos (recorte de uma
  cidade nos dados abertos do Infosiga SP);
- ``versoes.json``: versões e datas de cada base.

Os arquivos são gerados por ``ferramentas/preparar_dados.py`` a partir dos arquivos oficiais.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import shapely

PASTA = Path(__file__).resolve().parent.parent / "dados_publicos"
COLUNAS_VIAS = ["codigo_via", "rotulo", "nome", "classe", "comprimento_m", "geom_m"]


def disponivel() -> bool:
    return (PASTA / "versoes.json").exists() and any((PASTA / "snv").glob("*.parquet"))


@lru_cache(maxsize=1)
def versoes() -> dict:
    return json.loads((PASTA / "versoes.json").read_text(encoding="utf-8"))


def ufs() -> list[str]:
    return sorted(a.stem for a in (PASTA / "snv").glob("*.parquet"))


def anos_prf() -> list[int]:
    return list(versoes().get("prf", {}).get("anos", []))


def anos_completos_prf() -> list[int]:
    """Anos da PRF com o ano inteiro publicado (o último costuma estar pela metade)."""
    info = versoes().get("prf", {})
    anos = list(info.get("anos", []))
    if anos and not str(info.get("ultima_data", "")).endswith("-12-31"):
        anos = anos[:-1]
    return anos


def ler_snv(ufs: list[str] | None = None) -> pd.DataFrame:
    """Trechos do SNV das ``ufs`` (todas, se vazio), no formato de ``segmentacao.carregar_snv``."""
    arquivos = [PASTA / "snv" / f"{uf}.parquet" for uf in ufs] if ufs else sorted((PASTA / "snv").glob("*.parquet"))
    t = pd.concat([pq.read_table(a).to_pandas() for a in arquivos if a.exists()], ignore_index=True)
    t["geometry"] = shapely.from_wkb(t["geometry"].to_numpy())
    return t


def ler_vmd() -> pd.DataFrame:
    """VMD do PNCT por trecho, no formato de ``trafego.ler_vmd_pnct`` (com ``attrs`` de ano e versão)."""
    tabela = pq.read_table(PASTA / "vmd_pnct.parquet")
    v = tabela.to_pandas()
    v.attrs.update(json.loads((tabela.schema.metadata or {}).get(b"attrs", b"{}")))
    return v


def ler_sinistros_prf(ufs: list[str] | None = None, anos: list[int] | None = None) -> pd.DataFrame:
    """Sinistros da PRF no formato de ``segmentacao.ler_sinistros_prf``."""
    filtros = []
    if ufs:
        filtros.append(("uf", "in", list(ufs)))
    if anos:
        filtros.append(("ano", "in", [int(a) for a in anos]))
    s = pq.read_table(PASTA / "sinistros_prf.parquet", filters=filtros or None).to_pandas()
    for c in ("id", "uf", "br", "sentido", "municipio"):
        if c in s:
            s[c] = s[c].astype("string")
    s["ano"] = s["ano"].astype("Int64")
    s["data"] = pd.to_datetime(s["data"])
    s.attrs.update(linhas_repetidas=0, sem_coordenada=int(s["latitude"].isna().sum()), com_km=True)
    return s


def exemplo_urbano() -> dict | None:
    """Descrição do exemplo urbano (nome, UF, anos, fonte, licença), ou ``None`` se o arquivo não existir."""
    if not (PASTA / "exemplos" / "sinistros_urbanos.parquet").exists():
        return None
    return versoes().get("exemplo_urbano")


def ler_exemplo_urbano() -> pd.DataFrame:
    """Sinistros do exemplo urbano, lidos como uma planilha enviada pelo usuário."""
    from utils.segmentacao import ler_sinistros_pontuais

    s = ler_sinistros_pontuais(pq.read_table(PASTA / "exemplos" / "sinistros_urbanos.parquet").to_pandas())
    s.attrs["com_km"] = False
    return s


def ler_vias_osm(retangulo, urbanas: bool = False) -> pd.DataFrame:
    """Vias do OpenStreetMap (já unidas por UF) que cruzam o ``retangulo`` (oeste, sul, leste, norte), no
    formato de ``osm.montar_vias``. Lê todas as UFs cujas vias chegam ao retângulo."""
    o, s, leste, n = retangulo
    partes = []
    for uf, info in versoes().get("osm", {}).get("ufs", {}).items():
        caixa = info.get("bbox")
        if not caixa or caixa[0] > leste or caixa[2] < o or caixa[1] > n or caixa[3] < s:
            continue
        for conjunto in ("principais", "urbanas") if urbanas else ("principais",):
            arquivo = PASTA / "osm" / f"{uf}_{conjunto}.parquet"
            if arquivo.exists():
                filtros = [("xmin", "<=", leste), ("xmax", ">=", o), ("ymin", "<=", n), ("ymax", ">=", s)]
                partes.append(pq.read_table(arquivo, filters=filtros).to_pandas())
    if not partes:
        return pd.DataFrame(columns=COLUNAS_VIAS)
    v = pd.concat(partes, ignore_index=True)
    v["geom_m"] = shapely.from_wkb(v.pop("geometry").to_numpy())
    return v[COLUNAS_VIAS].reset_index(drop=True)
