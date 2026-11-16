import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from models.trilha3_bayes import _marshall, aplicar_bayes
from utils.preprocessamento import preparar_dados


def _base(n=300, semente=0):
    rng = np.random.default_rng(semente)
    vmd = rng.lognormal(8.5, 0.6, n)
    L = np.where(rng.random(n) < 0.9, 1.0, rng.uniform(0.2, 1.0, n))
    risco = rng.gamma(2.0, 0.5, n)
    mu = 0.4e-6 * vmd * 365 * 3 * L * risco
    d = pd.DataFrame({"segmento_id": [f"s{i}" for i in range(n)], "latitude": -15.8, "longitude": -47.9,
                      "extensao_trecho": L, "volume_trafego": vmd, "n_anos": 3,
                      "sem_vitima": rng.poisson(mu * 0.15), "com_vitima": rng.poisson(mu * 0.75),
                      "com_obito": rng.poisson(mu * 0.08)})
    return preparar_dados(d, 1, 4, 28)


def _v4_original(d):
    """Cópia da lógica de models/trilha3_bayes.py da v4 (com o índice por nome)."""
    df = d.copy()
    df["exposicao"] = df["volume_trafego"] * df["extensao_trecho"] * 365 * 3
    y = df["UPS"]
    X = sm.add_constant(np.log(df["exposicao"]))
    nb = sm.NegativeBinomial(y, X, loglike_method="nb2").fit(disp=False)
    df["N_previsto"] = nb.predict(X)
    df["resid2"] = ((df["UPS"] - df["N_previsto"]) ** 2).replace(0, 1e-6)
    c = sm.OLS(np.log(df["resid2"]), sm.add_constant(np.log(df["extensao_trecho"]))).fit().params.iloc[0]
    df["phi"] = np.exp(c + np.log(df["extensao_trecho"]))
    df["omega"] = 1 / (1 + df["N_previsto"] * df["phi"])
    df["ajustado"] = df["omega"] * df["N_previsto"] + (1 - df["omega"]) * df["UPS"]
    df["dp"] = np.sqrt((1 - df["omega"]) * df["ajustado"])
    df["Critico"] = df["ajustado"] > df["N_previsto"] + 1.96 * df["dp"]
    return df.set_index("segmento_id")


def test_modo_v4_reproduz_a_v4():
    d = _base()
    ref = _v4_original(d)
    res = aplicar_bayes(d, metodo="v4_script_r").set_index("segmento_id").loc[ref.index]
    np.testing.assert_allclose(res["ajustado"], ref["ajustado"], rtol=1e-5, atol=1e-6)
    assert (res["Critico"] == ref["Critico"]).all()


def test_marshall_encolhe_para_a_media_global():
    rng = np.random.default_rng(5)
    n = rng.uniform(1, 20, 500)
    x = rng.poisson(0.5 * n * rng.gamma(4, 0.25, 500)).astype(float)
    esperado, peso, previsto = _marshall(x, n)
    assert ((peso >= 0) & (peso <= 1)).all()
    taxa_global = x.sum() / n.sum()
    # a estimativa fica entre o observado e a média global
    lo = np.minimum(x / n, taxa_global) - 1e-12
    hi = np.maximum(x / n, taxa_global) + 1e-12
    assert ((esperado / n >= lo) & (esperado / n <= hi)).all()
    # segmentos com menos exposição encolhem mais
    assert np.corrcoef(n, peso)[0, 1] < 0


@pytest.mark.parametrize("metodo", ["nb_manual", "media_global", "nb_gravidade"])
def test_metodos_padrao_e_por_gravidade_corrigem_regressao_a_media(metodo):
    d = _base(n=1500, semente=3)
    res = aplicar_bayes(d, metodo=metodo)
    assert res["omega"].median() > 0.05                     # na v4 a mediana fica perto de 0,002
    v4 = aplicar_bayes(d, metodo="v4_script_r")
    assert v4["omega"].median() < 0.05


def test_padrao_da_trilha3_e_nb_manual_e_aceita_frequencia():
    d = _base(n=200, semente=11)
    padrao = aplicar_bayes(d)
    assert padrao.attrs["metodo"] == "nb_manual"
    assert padrao.attrs["criterio"] == "z"
    assert padrao.attrs["variavel"] == "severidade"
    freq = aplicar_bayes(d, variavel="frequencia")
    assert freq.attrs["variavel"] == "frequencia"
    assert (freq["N_observado"] == freq[["sem_vitima", "com_vitima", "com_obito"]].sum(axis=1)).all()


def test_sem_vmd_da_erro_claro():
    d = _base(20)
    d["volume_trafego"] = np.nan
    with pytest.raises(ValueError, match="volume de tráfego"):
        aplicar_bayes(d)


# Dados sintéticos (40 segmentos, 3 anos) e resultados do MASS::glm.nb do R (R 4.3.3, MASS 7.3-60) com o
# procedimento do Manual (2026, item 3.3): Nobservado ~ log(Exposicao), k = 1/theta, omega = 1/(1 + Nprevisto/k)
# e crítico se Nesperado > Nprevisto + 1,96 DP.
VMD_R = [3861, 9009, 8123, 11201, 9375, 4054, 1177, 1972, 8149, 4000, 17176, 6864, 4314, 9307, 19659, 9663, 6886,
         4968, 5149, 6667, 12814, 4513, 18525, 1591, 7695, 3461, 2675, 10236, 3411, 18818, 16766, 6988, 7815, 1210,
         9067, 2274, 5162, 3681, 3087, 2037]
EXT_R = [1.0, 1.0, 0.82, 1.0, 1.0, 1.0, 1.0, 0.72, 0.43, 1.0, 0.71, 1.0, 0.9, 1.0, 1.0, 1.0, 1.0, 0.95, 1.0, 1.0, 1.0,
         1.0, 1.0, 1.0, 1.0, 0.54, 1.0, 1.0, 1.0, 1.0, 1.0, 0.79, 1.0, 0.73, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
SV_R = [1, 2, 1, 2, 3, 1, 0, 1, 0, 2, 4, 2, 1, 1, 5, 3, 2, 3, 0, 1, 7, 1, 5, 3, 8, 1, 0, 2, 1, 4, 2, 7, 5, 0, 4, 2, 1,
        1, 1, 0]
CV_R = [2, 4, 1, 0, 3, 0, 0, 0, 1, 6, 3, 0, 3, 1, 9, 6, 3, 1, 0, 2, 5, 2, 2, 3, 10, 0, 0, 11, 1, 8, 4, 3, 14, 0, 8, 4,
        7, 0, 2, 2]
CO_R = [0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 2, 3, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 2, 0,
        0, 0, 0]
# segmento: (Nprevisto, omega, Nesperado, desvio-padrão)
REF_R = {
    "severidade": {"criticos": [10, 15, 16, 25, 28, 32, 33, 36],
                   "valores": {1: (16.15657681, 0.08116211, 9.58084290, 2.96702569),
                               7: (5.90491093, 0.19464304, 1.14934980, 0.96210023),
                               25: (28.98142801, 0.04693188, 47.10742263, 6.70049122),
                               40: (9.39831189, 0.13183118, 8.18434111, 2.66559370)}},
    "frequencia": {"criticos": [25, 33],
                   "valores": {1: (3.84471728, 0.09733467, 3.08222028, 1.66799682),
                               7: (1.47071838, 0.21990030, 0.32341141, 0.50228791),
                               25: (6.71644881, 0.05813708, 17.34400729, 4.04174187),
                               40: (2.29204616, 0.15317131, 2.04473309, 1.31587942)}},
}


@pytest.mark.parametrize("variavel", ["severidade", "frequencia"])
def test_padrao_reproduz_o_glm_nb_do_r(variavel):
    d = pd.DataFrame({"segmento_id": range(1, 41), "latitude": -15.8, "longitude": -47.9, "extensao_trecho": EXT_R,
                      "volume_trafego": VMD_R, "n_anos": 3, "sem_vitima": SV_R, "com_vitima": CV_R,
                      "com_obito": CO_R})
    res = aplicar_bayes(preparar_dados(d, 1, 4, 28), variavel=variavel).set_index("segmento_id")
    ref = REF_R[variavel]
    assert sorted(res.index[res["Critico"].astype(bool)]) == ref["criticos"]
    for seg, valores in ref["valores"].items():
        obtido = res.loc[seg, ["N_previsto", "omega", "ajustado", "desvio_padrao"]].to_numpy(float)
        np.testing.assert_allclose(obtido, valores, rtol=1e-4)
