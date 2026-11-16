"""Trilha 3 — Método Empírico de Bayes.

Quatro variantes, escolhidas pelo parâmetro ``metodo``:

* ``nb_manual`` (padrão): procedimento do Manual de Identificação de Segmentos
  Críticos Rodoviários (2026, item 3.3 e script R oficial). Ajusta uma Regressão
  Binomial Negativa (``glm.nb``) sobre ``Nobservado`` (UPS na análise de severidade,
  ou contagem total de sinistros na análise de frequência) em função do logaritmo da
  exposição em veículos-km (``V = VMDa x E x 365 x n``), com ``phi = theta``,
  ``k = 1 / phi`` e ``Omega = 1 / (1 + Nprevisto / k)``.
* ``nb_gravidade``: EB com Binomial Negativa por tipo de sinistro (Hauer; HSM),
  com superdispersão k = alpha / extensão.
* ``media_global``: EB pela Média Global com o estimador de Marshall (1991),
  aplicado a cada tipo de sinistro e somado com os pesos da UPS.
* ``v4_script_r``: procedimento da v4 anterior (Binomial Negativa sobre a UPS +
  regressão de log(resíduo²) em log(extensão)). Mantido para comparação histórica.

Critério de criticidade (``criterio``):

* ``z`` (padrão no ``nb_manual`` e ``v4_script_r``): ``Nesperado > Nprevisto + z x DP``,
  com ``z = 1,96`` (nível de confiança de 97,5% unicaudal / 95% bicaudal do Manual).
* ``manual``: ``Nesperado > Nprevisto`` (sem margem de desvio-padrão).
"""
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm

from utils.constantes import COLUNAS_SINISTROS, k_por_nivel

METODOS = {
    "nb_manual": "Regressão Binomial Negativa — Manual (item 3.3)",
    "nb_gravidade": "Binomial Negativa por tipo de sinistro (Hauer; HSM)",
    "media_global": "Média Global por tipo de sinistro (Marshall, 1991)",
    "v4_script_r": "Binomial Negativa + ajuste φ por extensão (v4)",
}
CRITERIOS = {
    "z": "Nesperado > Nprevisto + z × DP (Manual, item 3.3.2)",
    "manual": "Nesperado > Nprevisto (sem margem de desvio-padrão)",
}
CRITERIO_PADRAO = {
    "nb_manual": "z",
    "media_global": "manual",
    "nb_gravidade": "manual",
    "v4_script_r": "z",
}


def _exposicao(d):
    """Exposição no período, em milhões de veículos-km."""
    return d["volume_trafego"] * d["n_anos"] * 365 * d["extensao_trecho"] * 1e-6


def _marshall(x, n):
    """Estimador EB global de Marshall (1991) para as taxas x/n.

    Retorna (esperado, peso da referência, previsto), em contagens do período."""
    x = np.asarray(x, float)
    n = np.asarray(n, float)
    r = x / n
    m = x.sum() / n.sum()
    s2 = np.sum(n * (r - m) ** 2) / n.sum()
    A = max(s2 - m / n.mean(), 0.0)          # variância entre segmentos
    C = A / (A + m / n) if A > 0 else np.zeros_like(n)
    taxa = m + C * (r - m)
    return taxa * n, 1 - C, m * n


def _nb_manual(y, exp_veic_km):
    """Procedimento do Manual (2026, item 3.3 / script R): ``glm.nb(Nobservado ~ log(Exposicao))``."""
    y = np.asarray(y, float)
    exp_veic_km = np.asarray(exp_veic_km, float)
    if y.sum() <= 0 or len(y) < 4 or np.allclose(exp_veic_km, exp_veic_km[0]):
        raise RuntimeError("dados insuficientes para regressão Binomial Negativa")
    X = sm.add_constant(np.log(exp_veic_km), has_constant="add")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        modelo_nb = sm.NegativeBinomial(y, X, loglike_method="nb2").fit(disp=False, maxiter=300)
    params = np.asarray(modelo_nb.params, float)
    b0, b1, alpha = float(params[0]), float(params[1]), float(params[-1])
    previsto = np.exp(b0) * (exp_veic_km ** b1)
    if not (np.isfinite(previsto).all() and (previsto > 0).all() and np.isfinite(alpha) and alpha > 0):
        raise RuntimeError("a Binomial Negativa não convergiu")
    # No MASS::glm.nb do R, phi = modelo_nb$theta (= 1 / alpha) e k = 1 / phi (= alpha);
    # Omega = 1 / (1 + Nprevisto / k)
    k = alpha
    omega = 1.0 / (1.0 + (previsto / k))
    ajustado = omega * previsto + (1.0 - omega) * y
    dp = np.sqrt((1.0 - omega) * ajustado)
    return ajustado, omega, previsto, dp


def _nb_hauer(x, n, L):
    """EB com Binomial Negativa (NB2) e k = alpha / L (Hauer, 2001)."""
    x = np.asarray(x, float)
    X = sm.add_constant(np.log(np.asarray(n, float)), has_constant="add")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = sm.NegativeBinomial(x, X, loglike_method="nb2").fit(disp=False, maxiter=300)
    mu = np.asarray(res.predict(X), float)
    alpha = float(np.asarray(res.params)[-1])
    if not np.isfinite(alpha) or alpha <= 0 or not res.mle_retvals.get("converged", True):
        raise RuntimeError("a Binomial Negativa não convergiu")
    w = 1.0 / (1.0 + (alpha / np.asarray(L, float)) * mu)
    return w * mu + (1 - w) * x, w, mu


def _v4_script_r(y, n, L):
    """Procedimento da v4 (equivalente ao script R antigo), com o índice corrigido para pandas 3."""
    y = np.asarray(y, float)
    X = sm.add_constant(np.log(np.asarray(n, float)), has_constant="add")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        modelo_nb = sm.NegativeBinomial(y, X, loglike_method="nb2").fit(disp=False)
    previsto = np.asarray(modelo_nb.predict(X), float)
    resid2 = (y - previsto) ** 2
    resid2[resid2 == 0] = 1e-6
    X_res = sm.add_constant(np.log(np.asarray(L, float)), has_constant="add")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        c = float(np.asarray(sm.OLS(np.log(resid2), X_res).fit().params)[0])
    phi = np.exp(c + np.log(np.asarray(L, float)))
    omega = 1 / (1 + previsto * phi)
    ajustado = omega * previsto + (1 - omega) * y
    return ajustado, omega, previsto, np.sqrt((1 - omega) * ajustado)


def aplicar_bayes(df, metodo="nb_manual", criterio=None, nivel_confianca=97.5, pesos=None, variavel="severidade"):
    """Aplica a Trilha 3. ``pesos`` = pesos da UPS (padrão: os usados em preparar_dados).
    ``variavel``: ``'severidade'`` (usa a UPS) ou ``'frequencia'`` (usa o total de sinistros, peso 1).

    Devolve uma linha por segmento com: N_observado, N_previsto, omega, ajustado (Nesperado),
    desvio_padrao, excesso (ajustado - previsto) e Critico.
    """
    if metodo not in METODOS:
        raise ValueError(f"Método desconhecido: {metodo}")
    if variavel not in ("severidade", "frequencia"):
        raise ValueError(f"Variável desconhecida: {variavel}")
    criterio = criterio or CRITERIO_PADRAO[metodo]
    pesos_ups = pesos or df.attrs.get("pesos_ups") or {"sem_vitima": 1, "com_vitima": 4, "com_obito": 28}
    pesos_calc = {"sem_vitima": 1, "com_vitima": 1, "com_obito": 1} if variavel == "frequencia" else pesos_ups

    d = df.copy()
    if "n_anos" not in d:
        d["n_anos"] = 1
    if "volume_trafego" not in d or not (pd.to_numeric(d["volume_trafego"], errors="coerce") > 0).any():
        raise ValueError("A Trilha 3 precisa do volume de tráfego (VMD) dos segmentos.")
    d["exposicao"] = _exposicao(d)
    avisos = []
    validos = d["exposicao"] > 0
    if (~validos).any():
        avisos.append(f"{int((~validos).sum())} segmento(s) sem VMD ou extensão ficaram fora da Trilha 3.")
    d = d[validos].copy()
    if len(d) < 3:
        raise ValueError("A Trilha 3 precisa de pelo menos 3 segmentos com VMD e extensão.")

    n = d["exposicao"].to_numpy(float)
    L = d["extensao_trecho"].to_numpy(float)
    ups_real = sum(pesos_ups[c] * d[c].to_numpy(float) for c in COLUNAS_SINISTROS)
    n_obs = sum(pesos_calc[c] * d[c].to_numpy(float) for c in COLUNAS_SINISTROS)

    if metodo == "nb_manual":
        try:
            ajustado, omega, previsto, dp = _nb_manual(n_obs, n * 1e6)
        except Exception:
            ajustado, omega, previsto = _marshall(n_obs, n)
            dp = np.sqrt((1.0 - omega) * ajustado)
            avisos.append(
                "Binomial Negativa sem convergência na amostra reduzida: "
                "estimativa calculada pela Média Global."
            )
    elif metodo == "v4_script_r":
        # mesma escala de exposição da v4 (veículos-km), para reproduzir o ajuste numérico
        ajustado, omega, previsto, dp = _v4_script_r(n_obs, n * 1e6, L)
    else:
        ajustado = np.zeros(len(d))
        previsto = np.zeros(len(d))
        variancia = np.zeros(len(d))
        for c in COLUNAS_SINISTROS:
            x = d[c].to_numpy(float)
            if pesos_calc[c] == 0:
                continue
            if x.sum() == 0:            # nenhum sinistro desse tipo na base
                continue
            if metodo == "nb_gravidade":
                try:
                    esp, w, prev = _nb_hauer(x, n, L)
                except Exception:
                    esp, w, prev = _marshall(x, n)
                    avisos.append(f"Binomial Negativa sem convergência para '{c}': usada a Média Global.")
            else:
                esp, w, prev = _marshall(x, n)
            ajustado += pesos_calc[c] * esp
            previsto += pesos_calc[c] * prev
            variancia += pesos_calc[c] ** 2 * (1 - w) * esp
        dp = np.sqrt(variancia)
        with np.errstate(divide="ignore", invalid="ignore"):
            omega = np.where(n_obs != previsto, (n_obs - ajustado) / (n_obs - previsto), 1.0)

    if criterio == "manual":
        critico = ajustado > previsto
        z = None
    else:
        z = k_por_nivel(nivel_confianca)
        critico = ajustado > previsto + z * dp

    res = d.assign(
        N_observado=n_obs, N_previsto=previsto, omega=np.clip(omega, 0, 1), ajustado=ajustado,
        desvio_padrao=dp, excesso=ajustado - previsto, Critico=critico, UPS=ups_real,
    )
    colunas = ["segmento_id", "latitude", "longitude", "extensao_trecho", "volume_trafego", "n_anos",
               *COLUNAS_SINISTROS, "UPS", "exposicao", "N_observado", "N_previsto", "omega", "ajustado",
               "desvio_padrao", "excesso", "Critico"]
    res = res[[c for c in colunas if c in res]].sort_values("ajustado", ascending=False).reset_index(drop=True)
    res.attrs.update({"avisos": avisos, "metodo": metodo, "criterio": criterio, "z": z, "variavel": variavel})
    return res


# Nome usado pela v4
def aplicar_bayes_trilha3(df, metrica="UPS"):
    return aplicar_bayes(df, metodo="v4_script_r", criterio="z", nivel_confianca=97.5)
