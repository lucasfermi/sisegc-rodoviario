"""Dados públicos embutidos (pasta dados_publicos/): leitura no formato que a segmentação espera."""
import pytest
import shapely

from utils import dados_publicos as dp
from utils import segmentacao as sg

pytestmark = pytest.mark.skipif(not dp.disponivel(), reason="pasta dados_publicos ausente")


def test_versoes_e_listas():
    v = dp.versoes()
    assert {"snv", "prf", "vmd"} <= set(v)
    assert len(dp.ufs()) == 27
    assert dp.anos_completos_prf() == [a for a in dp.anos_prf() if a < 2026] or \
        dp.versoes()["prf"]["ultima_data"].endswith("-12-31")


def test_snv_sinistros_e_vmd_de_uma_uf():
    snv = sg.preparar_snv(dp.ler_snv(["DF"]))
    assert set(snv["sg_uf"]) == {"DF"} and snv["geom_m"].notna().all()
    s = dp.ler_sinistros_prf(["DF"], [2023])
    assert set(s["uf"]) == {"DF"} and set(s["ano"]) == {2023}
    assert {"br", "km", "latitude", "longitude", "gravidade", "sentido"} <= set(s.columns)
    assert s.attrs["com_km"]
    v = dp.ler_vmd()
    assert v.attrs["ano"] == 2019 and v["vmd_c"].notna().any()


@pytest.mark.skipif(not (dp.PASTA / "osm" / "DF_principais.parquet").exists(), reason="OSM ausente")
def test_vias_do_osm_no_retangulo():
    df = (-48.0, -15.9, -47.8, -15.7)
    principais = dp.ler_vias_osm(df)
    todas = dp.ler_vias_osm(df, urbanas=True)
    assert len(todas) > len(principais) > 100
    assert principais["codigo_via"].is_unique
    assert (shapely.get_type_id(principais["geom_m"].to_numpy()) == 1).all()
    assert dp.ler_vias_osm((-30.0, -10.0, -29.9, -9.9)).empty          # no mar


@pytest.mark.skipif(not (dp.PASTA / "osm" / "DF_principais.parquet").exists(), reason="OSM ausente")
def test_sinistros_proprios_no_snv_e_no_osm_embutidos():
    """Planilha própria (só coordenadas): um sinistro numa via do OpenStreetMap, outro numa BR."""
    import pandas as pd

    snv = sg.preparar_snv(dp.ler_snv(["DF"]))
    vias = dp.ler_vias_osm((-48.0, -15.9, -47.8, -15.7))
    via = vias.sort_values("comprimento_m").iloc[-1]
    meio = shapely.line_interpolate_point(via["geom_m"], 0.5, normalized=True)
    lon_osm, lat_osm = sg._PARA_GEO.transform(meio.x, meio.y)
    br = sg._trechos_base(snv).iloc[0]
    p_br = shapely.line_interpolate_point(br["geometry"], 0.5, normalized=True)
    s = sg.ler_sinistros_pontuais(pd.DataFrame({"ano": [2024, 2024], "latitude": [lat_osm, p_br.y],
                                                "longitude": [lon_osm, p_br.x], "com_vitima": [1, 1],
                                                "com_obito": [0, 0]}))
    dados = sg.segmentar(s, snv, ["DF"], [2024], vias_prontas=vias)
    assert dados.groupby("fonte")["com_vitima"].sum().to_dict() == {"OpenStreetMap": 1, "SNV": 1}
    assert dados.loc[dados["com_vitima"] > 0, "segmento_id"].str.startswith(("OSMDF", br["vl_codigo"])).all()


@pytest.mark.skipif(dp.exemplo_urbano() is None, reason="exemplo urbano ausente")
def test_exemplo_urbano_segmenta_na_area_dos_sinistros():
    """Exemplo dos Primeiros passos (Infosiga, Santos): a malha fica na área dos sinistros, sem segmentos do SNV
    de outras regiões, e o resumo não tem NaN (os attrs da tabela vão para o navegador em JSON)."""
    import json

    info = dp.exemplo_urbano()
    s = dp.ler_exemplo_urbano()
    assert len(s) == info["sinistros"] and s.attrs["sem_ano"] == 0
    snv = sg.preparar_snv(dp.ler_snv([info["uf"]]))
    area = sg.retangulo(s, snv, [info["uf"]])
    vias = dp.ler_vias_osm(area, urbanas=True)
    dados = sg.segmentar(s, snv, [info["uf"]], info["anos"], vmd=dp.ler_vmd(), vias_prontas=vias, area=area)
    r = dados.attrs["resumo"]
    assert r["atribuidos"] / r["sinistros"] > 0.95
    snv_fica = dados[dados["fonte"] == "SNV"]
    dentro = snv_fica["longitude"].between(area[0], area[2]) & snv_fica["latitude"].between(area[1], area[3])
    assert (dentro | snv_fica[["sem_vitima", "com_vitima", "com_obito"]].sum(axis=1).gt(0)).all()
    assert r["fora_da_area"] > 0 and (dados["fonte"] == "OpenStreetMap").any()
    json.dumps(r, allow_nan=False, default=str)
