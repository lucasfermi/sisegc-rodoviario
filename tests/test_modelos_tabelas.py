"""Planilhas-modelo, nomes claros das colunas e o caminho de volta: o que o app baixa, o app lê de novo."""
import io

import numpy as np
import pandas as pd
import pytest

from utils import segmentacao as sg
from utils.entrada import adaptar_planilha, ler_arquivo
from utils.modelos import (
    COLUNAS_MODELO_SEGMENTOS,
    COLUNAS_MODELO_SINISTROS,
    EXEMPLO_SINISTROS,
    modelo_segmentos,
    modelo_sinistros,
)
from utils.tabelas import NOMES, tabela_resultado, tabela_segmentos


def test_modelo_de_segmentos_preenchido_e_lido_pelo_app():
    xlsx = modelo_segmentos(True)
    abas = pd.ExcelFile(io.BytesIO(xlsx)).sheet_names
    assert abas == ["Segmentos", "Instruções"]
    dados, avisos = adaptar_planilha(ler_arquivo("modelo.xlsx", xlsx))
    assert list(dados["segmento_id"]) == ["A1", "A2", "A3", "A4"]
    assert dados["n_anos"].eq(3).all() and dados["volume_trafego"].tolist() == [5000, 4500, 5200, 6000]
    assert dados["com_obito"].tolist() == [0, 1, 0, 2] and dados["extensao_trecho"].tolist() == [1.2, 0.8, 1.5, 2.0]
    assert dados["rodovia"].iloc[0] == "Via A, km 0,0 a 1,2"
    assert not avisos
    vazio = pd.read_excel(io.BytesIO(modelo_segmentos(False)))
    assert list(vazio.columns) == COLUNAS_MODELO_SEGMENTOS and vazio.empty


def test_modelo_de_sinistros_preenchido_e_lido_pelo_app():
    xlsx = modelo_sinistros(True)
    s = sg.ler_arquivos_sinistros([("modelo_sinistros.xlsx", xlsx)])
    assert len(s) == len(EXEMPLO_SINISTROS) and s.attrs["sem_ano"] == 0 and s.attrs["sem_coordenada"] == 0
    assert sorted(s["ano"].unique()) == [2023, 2024, 2025]
    assert s["gravidade"].value_counts().to_dict() == {"sem_vitima": 15, "com_vitima": 7, "com_obito": 2}
    assert s["uf"].eq("DF").all()
    vazio = pd.read_excel(io.BytesIO(modelo_sinistros(False)))
    assert list(vazio.columns) == COLUNAS_MODELO_SINISTROS


@pytest.mark.parametrize("texto,esperado", [
    ("2023-01-05", "2023-01-05"), ("2023-01-25", "2023-01-25"), ("2023-1-5", "2023-01-05"),
    ("05/01/2023", "2023-01-05"), ("25/01/2023 14:30", "2023-01-25"), ("2023-02-03 10:11:12", "2023-02-03"),
    ("5/1/2023", "2023-01-05"), ("05-03-2024", "2024-03-05"),
])
def test_datas_iso_e_brasileiras(texto, esperado):
    """O leitor antigo (dayfirst=True) lia 2023-01-05 como 1º de maio e perdia 2023-01-25."""
    s = sg.ler_sinistros_pontuais(pd.DataFrame({"latitude": [-15.7], "longitude": [-47.9], "data": [texto]}))
    assert str(s.loc[0, "data"].date()) == esperado and s.loc[0, "ano"] == int(esperado[:4])


def test_coluna_data_hora_e_ano_em_branco():
    s = sg.ler_sinistros_pontuais(pd.DataFrame({"lat": [-15.7, -15.8, -15.9], "lon": [-47.9, -47.9, -47.9],
                                                "Data/Hora": ["2024-03-05 08:00", "data errada", None],
                                                "gravidade": ["Sem vítima", "Com vítima", "Com óbito"]}))
    assert s["ano"].tolist()[0] == 2024 and s.attrs["sem_ano"] == 2


def test_coordenadas_concentradas():
    pts = pd.DataFrame({"latitude": [-23.5] * 40 + list(np.linspace(-23.6, -23.7, 20)),
                        "longitude": [-46.6] * 40 + list(np.linspace(-46.7, -46.8, 20))})
    c = sg.coordenadas_concentradas(pts, minimo=30)
    assert c["pontos"] == 1 and c["sinistros"] == 40 and c["total"] == 60
    assert c["maiores"][0] == (-23.5, -46.6, 40)
    assert sg.coordenadas_concentradas(pts, minimo=41) is None


def _segmentos_auto():
    return pd.DataFrame({
        "segmento_id": ["040BDF0010-001", "040BDF0010-002", "OSMDF000001-001"],
        "latitude": [-15.8, -15.81, -15.79], "longitude": [-47.9, -47.91, -47.92],
        "extensao_trecho": [1.0, 0.8, 0.5], "volume_trafego": [12000.0, 12000.0, np.nan], "n_anos": [3, 3, 3],
        "sem_vitima": [3, 0, 1], "com_vitima": [2, 1, 0], "com_obito": [1, 0, 0],
        "rodovia": ["BR-040/DF, km 0,0 a 1,0", "BR-040/DF, km 1,0 a 1,8", "Avenida X, km 0,0 a 0,5"],
        "codigo_snv": ["040BDF0010", "040BDF0010", None], "km_inicial": [0.0, 1.0, 0.0], "km_final": [1.0, 1.8, 0.5],
        "vmd_origem": ["código do SNV", "código do SNV", None], "vmd_classificacao": [None, None, None],
        "fonte": ["SNV", "SNV", "OpenStreetMap"], "codigo_via": [None, None, "OSMDF000001"],
        "classe": [None, None, "primary"]})


def test_planilha_de_segmentos_baixada_volta_igual():
    """A planilha do botão “Baixar segmentos”, com os nomes claros, entra de novo em “Outras formas de
    entrada” com os mesmos valores (inclusive a descrição da via, que vale mais que o código do SNV)."""
    dados = _segmentos_auto()
    tabela = tabela_segmentos(dados)
    assert list(tabela.columns[:3]) == ["ID do segmento", "Rodovia ou via", "Fonte da via"]
    buf = io.BytesIO()
    tabela.to_excel(buf, index=False)
    lido, avisos = adaptar_planilha(ler_arquivo("segmentos.xlsx", buf.getvalue()))
    assert list(lido["segmento_id"]) == list(dados["segmento_id"])
    for c in ("sem_vitima", "com_vitima", "com_obito", "extensao_trecho", "n_anos", "latitude", "longitude"):
        assert lido[c].tolist() == pytest.approx(dados[c].tolist()), c
    assert lido["volume_trafego"].iloc[:2].tolist() == [12000, 12000] and pd.isna(lido["volume_trafego"].iloc[2])
    assert list(lido["rodovia"]) == list(dados["rodovia"])
    assert not avisos


def test_resultado_com_nomes_claros_e_unidade_do_metodo():
    from models.trilha1_valor_critico import aplicar_valor_critico
    from models.trilha3_bayes import aplicar_bayes
    from utils.preprocessamento import preparar_dados

    dados = _segmentos_auto()
    df = preparar_dados(dados, 1, 4, 28)
    t1 = tabela_resultado("vc", aplicar_valor_critico(df, metodo="numero"), dados)
    assert list(t1.columns[:4]) == [
        "ID do segmento", "Rodovia ou via", "Crítico", "Índice de frequência — Ifsi (sinistros/km)"
    ]
    assert set(t1["Crítico"]) <= {"Sim", "Não"}
    assert "Sinistros com óbito" in t1 and "Latitude" in t1          # vêm dos dados do segmento
    com_vmd = dados.assign(volume_trafego=[12000.0, 12000.0, 8000.0])     # a Trilha 3 pede 3 segmentos com VMD
    t3 = tabela_resultado("bayes", aplicar_bayes(preparar_dados(com_vmd, 1, 4, 28)), com_vmd)
    assert t3.columns[3] == NOMES["ajustado"] and list(t3.columns).count("UPS") == 0
    assert not any(c in t3 for c in ("Metrica_Obs", "x_proj", "hotspot_kde", "peso"))
