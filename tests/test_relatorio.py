"""Mapa do relatório: projeção, escolha dos tiles, fundo do OpenStreetMap e o mapa sem internet."""
import io

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from PIL import Image

from utils import relatorio


def _png(cor=(200, 220, 240)):
    buf = io.BytesIO()
    Image.new("RGB", (256, 256), cor).save(buf, format="PNG")
    return buf.getvalue()


def _dados():
    n = 40
    df = pd.DataFrame({"segmento_id": [f"S{i}" for i in range(n)], "latitude": np.linspace(-15.6, -16.0, n),
                       "longitude": np.linspace(-48.1, -47.6, n)})
    conv = df.head(6).assign(n_trilhas=[3, 2, 2, 1, 1, 1], UPS=[60, 50, 40, 30, 20, 10],
                             via=["BR-040/DF"] * 3 + ["BR-020/DF"] * 3)
    return df, conv


def test_projecao_e_escolha_dos_tiles():
    x, y = relatorio.projetar_mercator([0, 180], [0, 0])
    assert x[0] == 0 and y[0] == pytest.approx(0, abs=1e-6) and x[1] == pytest.approx(relatorio.METADE_MUNDO)
    _, yb = relatorio.projetar_mercator([-47.9], [-15.8])
    assert relatorio._latitude(yb[0]) == pytest.approx(-15.8)
    area = relatorio._enquadrar(*relatorio.projetar_mercator([-48.3, -47.3], [-16.05, -15.5]), 8 / 5.6)
    assert (area[1] - area[0]) / (area[3] - area[2]) == pytest.approx(8 / 5.6)
    z, tx0, tx1, ty0, ty1 = relatorio._tiles_da_area(*area)
    assert z == 10 and (tx1 - tx0 + 1) * (ty1 - ty0 + 1) <= relatorio.LIMITE_TILES      # o DF em ~1000 px
    brasil = relatorio._enquadrar(*relatorio.projetar_mercator([-74, -34], [5, -34]), 8 / 5.6)
    z2, bx0, bx1, by0, by1 = relatorio._tiles_da_area(*brasil)                          # o zoom cai até caber
    assert z2 < z and (bx1 - bx0 + 1) * (by1 - by0 + 1) <= relatorio.LIMITE_TILES


def test_mapa_com_fundo_do_openstreetmap(monkeypatch):
    chamadas = []
    monkeypatch.setenv("SISEGC_MAPA_DE_FUNDO", "1")
    monkeypatch.setattr(relatorio, "_CACHE_TILES", {})
    monkeypatch.setattr(relatorio, "_buscar_tile", lambda z, x, y: chamadas.append((z, x, y)) or _png())
    df, conv = _dados()
    fig, com_fundo = relatorio.figura_mapa(df, conv)
    assert com_fundo and fig.axes[0].images
    fundo = np.asarray(fig.axes[0].images[0].get_array())
    assert fundo.shape[2] == 3 and int(fundo.min()) >= 100                # em cinza claro, sob as cores
    assert any(t.get_text() == relatorio.CREDITO_FUNDO for t in fig.axes[0].texts)
    plt.close(fig)
    n = len(chamadas)
    fig, _ = relatorio.figura_mapa(df, conv)                               # mesma área: tiles da memória
    plt.close(fig)
    assert len(chamadas) == n
    assert relatorio.CREDITO_FUNDO in relatorio._texto_mapa(conv, True)


def test_mapa_sem_internet_sai_so_com_a_malha(monkeypatch):
    chamadas = []

    def sem_rede(z, x, y):
        chamadas.append((z, x, y))
        raise OSError("sem rede")

    monkeypatch.setenv("SISEGC_MAPA_DE_FUNDO", "1")
    monkeypatch.setattr(relatorio, "_CACHE_TILES", {})
    monkeypatch.setattr(relatorio, "_buscar_tile", sem_rede)
    df, conv = _dados()
    fig, com_fundo = relatorio.figura_mapa(df, conv)
    assert fig is not None and not com_fundo and not fig.axes[0].images
    plt.close(fig)
    assert len(chamadas) == 1                                              # desiste já no primeiro tile
    assert "não pôde ser carregado" in relatorio._texto_mapa(conv, False)
    assert "roxo" not in relatorio._texto_mapa(conv[conv["n_trilhas"] < 3], True)   # só as cores presentes


def test_mapa_desligado_nao_busca_nada(monkeypatch):
    monkeypatch.setattr(relatorio, "_buscar_tile", lambda *a: pytest.fail("não devia buscar tiles"))
    df, conv = _dados()
    fig, com_fundo = relatorio.figura_mapa(df, conv)                       # SISEGC_MAPA_DE_FUNDO=0 (conftest)
    plt.close(fig)
    assert not com_fundo


def test_percentual_so_mostra_100_quando_e_100():
    from utils.relatorio import _pct

    assert _pct(1.0) == "100%"
    assert _pct(2999 / 3000) == "99,9%"
    assert _pct(0.996) == "99,6%"
    assert _pct(0.98) == "98%"


def test_parametros_na_primeira_pagina_e_vmd():
    import pandas as pd

    from utils.relatorio import _parametros

    contexto = {"descricao_fonte": "Segmentação automática: DF, 2024, sinistros da PRF.",
                "segmentacao": {"comprimento": 1.0, "por_sentido": False, "residenciais": False, "vmd": False}}
    pesos = {"sem_vitima": 1, "com_vitima": 4, "com_obito": 28}
    capa = _parametros({}, pesos, contexto, com_dados=False)
    assert isinstance(capa, pd.DataFrame) and "Dados" not in capa["Parâmetro"].tolist()
    vmd = capa.set_index("Parâmetro").loc["Volume de tráfego (VMD)", "Valor"]
    assert vmd.startswith("não usado")
    assert "Dados" in _parametros({}, pesos, contexto)["Parâmetro"].tolist()
