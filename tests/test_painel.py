"""Painel e relatório executivo: convergência entre as trilhas, indicadores, faixas da UPS e o PDF."""
import pandas as pd
import pytest

from utils import painel


def _resultados():
    ids = [f"S{i}" for i in range(1, 9)]
    df = pd.DataFrame({"segmento_id": ids, "rodovia": [f"BR-0{10 * (i % 2 + 1)}/DF, km {i},0 a {i + 1},0"
                                                          for i in range(8)],
                       "extensao_trecho": [1.0] * 8, "volume_trafego": [1000.0] * 8,
                       "sem_vitima": [5, 4, 3, 2, 1, 0, 0, 0], "com_vitima": [2, 2, 1, 1, 0, 0, 1, 0],
                       "com_obito": [1, 0, 0, 0, 0, 0, 0, 0], "latitude": [-15.8] * 8, "longitude": [-47.9] * 8})
    df["total_sinistros"] = df[["sem_vitima", "com_vitima", "com_obito"]].sum(axis=1)
    df["UPS"] = df["sem_vitima"] + 4 * df["com_vitima"] + 28 * df["com_obito"]
    df.attrs["pesos_ups"] = {"sem_vitima": 1, "com_vitima": 4, "com_obito": 28}

    def res(criticos):
        return pd.DataFrame({"segmento_id": ids, "Critico": [i in criticos for i in ids]})

    return df, {"vc": res({"S1", "S2", "S3"}), "kde": res({"S1", "S2"}), "bayes": res({"S1", "S4"})}


def test_convergencia_ordena_por_trilhas_e_ups():
    df, res = _resultados()
    conv = painel.convergencia(res, df)
    assert list(conv["segmento_id"]) == ["S1", "S2", "S3", "S4"]
    assert list(conv["n_trilhas"]) == [3, 2, 1, 1]
    assert conv.loc[0, "trilhas"] == "Trilhas 1, 2 e 3" and conv.loc[3, "trilhas"] == "Trilha 3"
    assert conv.loc[0, "via"] == "BR-010/DF"
    so_duas = painel.convergencia(res, df, ["vc", "kde"])
    assert list(so_duas["n_trilhas"]) == [2, 2, 1]


def test_combinacoes_e_indicadores():
    df, res = _resultados()
    conv = painel.convergencia(res, df)
    comb = painel.combinacoes(conv, ["vc", "kde", "bayes"]).set_index("combinacao")["segmentos"].to_dict()
    assert comb == {"Só a Trilha 1": 1, "Só a Trilha 2": 0, "Só a Trilha 3": 1, "Trilhas 1 e 2": 1,
                    "Trilhas 1 e 3": 0, "Trilhas 2 e 3": 0, "Trilhas 1, 2 e 3": 1}
    ind = painel.indicadores(df, res, conv)
    assert ind["segmentos"] == 8 and ind["com_sinistro"] == 6 and ind["sinistros"] == 23
    assert ind["em_pelo_menos"] == {1: 4, 2: 2, 3: 1}
    duas = ind["parcela"][2]                                # S1 e S2
    assert duas["km"] == pytest.approx(2 / 8) and duas["sinistros"] == pytest.approx(14 / 23)
    assert duas["com_obito"] == pytest.approx(1.0)
    assert painel.vias_criticas(conv, 1)["segmentos"].sum() == 4


def test_cores_da_convergencia_escurecem_com_as_trilhas():
    def luminancia(cor):
        r, g, b = (int(cor[i:i + 2], 16) / 255 for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    lum = [luminancia(painel.CORES_N_TRILHAS[n]) for n in (1, 2, 3)]
    assert lum[0] > lum[1] > lum[2]                     # amarelo, vermelho, roxo: a ordem se lê sem a cor
    assert set(painel.NOMES_CORES_N_TRILHAS) == set(painel.CORES_N_TRILHAS)


def test_faixas_da_ups_sem_os_segmentos_sem_sinistro():
    df, _ = _resultados()
    faixas = painel.histograma_ups(df, n_faixas=5)
    assert faixas["segmentos"].sum() == 6                     # 2 segmentos sem sinistro ficam de fora
    assert faixas["inicio"].is_monotonic_increasing


def test_relatorio_executivo_com_contexto():
    from models.trilha1_valor_critico import aplicar_valor_critico
    from models.trilha2_kernel import aplicar_kernel
    from utils.preprocessamento import preparar_dados
    from utils.relatorio import gerar_pdf_completo

    df, _ = _resultados()
    df["latitude"] = [-15.80, -15.81, -15.82, -15.83, -15.84, -15.85, -15.86, -15.87]
    proc = preparar_dados(df.drop(columns=["total_sinistros", "UPS"]), 1, 4, 28)
    res = {"vc": aplicar_valor_critico(proc), "kde": aplicar_kernel(proc)}
    ctx = {"descricao_fonte": "Planilha de segmentos: teste.xlsx.", "mensagens": [("warning", "Aviso de teste.")],
           "erros": {"bayes": "A Trilha 3 precisa do VMD."}, "excluir_zeros": False}
    pdf = gerar_pdf_completo(proc, res, None, ctx)
    assert pdf[:4] == b"%PDF" and len(pdf) > 20_000
