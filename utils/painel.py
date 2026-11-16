"""Painel: indicadores e convergência entre as trilhas (aba Painel do app e relatório PDF).

Funções puras sobre ``df_proc`` (segmentos com a UPS, de ``utils/preprocessamento.py``) e os resultados das
trilhas; a interface fica no ``app.py`` e no ``utils/relatorio.py``.
"""
from __future__ import annotations

import math
from itertools import combinations

import numpy as np
import pandas as pd

from utils.constantes import COLUNAS_SINISTROS, ORDEM_TRILHAS, TRILHAS

AZUL = "#0988C3"
# Número de trilhas que apontam o segmento: amarelo (1), vermelho (2) e roxo (3), como nas escalas de alerta. Sem
# verde, que sugeriria segurança. A claridade cai a cada passo (lê-se a ordem também em tons de cinza e com
# daltonismo) e o contorno escuro destaca o amarelo sobre o mapa.
CORES_N_TRILHAS = {1: "#eda100", 2: "#d03b3b", 3: "#6b2a8c"}
NOMES_CORES_N_TRILHAS = {1: "amarelo", 2: "vermelho", 3: "roxo"}
CONTORNO = "#3a3a3a"
CINZA = "#b8b8b8"
COLUNAS_SEGMENTO = ["rodovia", "fonte", "extensao_trecho", "volume_trafego", *COLUNAS_SINISTROS, "total_sinistros",
                    "UPS", "latitude", "longitude"]


def numero(chave: str) -> int:
    return TRILHAS[chave]["numero"]


def rotulo_curto(chave: str) -> str:
    return f"Trilha {numero(chave)}"


def texto_trilhas(numeros) -> str:
    """[1] -> 'Trilha 1'; [1, 3] -> 'Trilhas 1 e 3'; [1, 2, 3] -> 'Trilhas 1, 2 e 3'."""
    n = sorted(numeros)
    if len(n) == 1:
        return f"Trilha {n[0]}"
    return "Trilhas " + ", ".join(map(str, n[:-1])) + f" e {n[-1]}"


def via_de(rodovia: pd.Series) -> pd.Series:
    """Nome da via sem o trecho: 'BR-040/DF, km 10,0 a 11,0' -> 'BR-040/DF'."""
    return rodovia.astype("string").str.replace(r",\s*km\s.*$", "", regex=True).str.strip()


def convergencia(resultados: dict, df_proc: pd.DataFrame, trilhas=None) -> pd.DataFrame:
    """Uma linha por segmento crítico em ao menos uma das ``trilhas`` (todas as que rodaram, por padrão): em
    quais trilhas é crítico, em quantas e os dados do segmento. Ordem: mais trilhas, maior UPS, mais sinistros.
    É a lista de prioridades do painel e do relatório."""
    trilhas = [c for c in (trilhas or ORDEM_TRILHAS) if c in resultados]
    criticos = {c: set(resultados[c].loc[resultados[c]["Critico"].astype(bool), "segmento_id"].astype(str))
                for c in trilhas}
    todos = set().union(*criticos.values()) if criticos else set()
    base = df_proc.drop_duplicates("segmento_id")
    ids = base["segmento_id"].astype(str)
    conv = base.loc[ids.isin(todos), ["segmento_id", *[c for c in COLUNAS_SEGMENTO if c in base]]].copy()
    conv["segmento_id"] = conv["segmento_id"].astype(str)
    for c in trilhas:
        conv[f"critico_{c}"] = conv["segmento_id"].isin(criticos[c])
    flags = [f"critico_{c}" for c in trilhas]
    conv["n_trilhas"] = conv[flags].sum(axis=1).astype(int) if flags else 0
    conv["trilhas"] = conv[flags].apply(
        lambda r: texto_trilhas([numero(c) for c, f in zip(trilhas, r) if f]), axis=1) if len(conv) else ""
    if "rodovia" in conv:
        conv["via"] = via_de(conv["rodovia"])
    ordem = [c for c in ("n_trilhas", "UPS", "total_sinistros") if c in conv]
    return conv.sort_values(ordem, ascending=False, kind="stable").reset_index(drop=True)


def combinacoes(conv: pd.DataFrame, trilhas) -> pd.DataFrame:
    """Quantos segmentos são críticos em cada combinação de trilhas (inclusive as sem nenhum segmento)."""
    linhas = []
    for k in range(1, len(trilhas) + 1):
        for grupo in combinations(trilhas, k):
            fora = [c for c in trilhas if c not in grupo]
            sel = np.ones(len(conv), bool)
            for c in grupo:
                sel &= conv[f"critico_{c}"].to_numpy(bool)
            for c in fora:
                sel &= ~conv[f"critico_{c}"].to_numpy(bool)
            nome = ("Só a " if k == 1 else "") + texto_trilhas([numero(c) for c in grupo])
            linhas.append({"combinacao": nome, "n_trilhas": k, "segmentos": int(sel.sum())})
    return pd.DataFrame(linhas, columns=["combinacao", "n_trilhas", "segmentos"])


def indicadores(df_proc: pd.DataFrame, resultados: dict, conv: pd.DataFrame) -> dict:
    """Números principais: base analisada, críticos por trilha, convergência e quanto os críticos concentram."""
    seg = df_proc.drop_duplicates("segmento_id")
    soma = seg[COLUNAS_SINISTROS].sum()
    total = float(soma.sum())
    km = float(pd.to_numeric(seg["extensao_trecho"], errors="coerce").sum())
    ups = float(seg["UPS"].sum()) if "UPS" in seg else 0.0
    ind = {
        "segmentos": int(len(seg)), "km": km, "sinistros": total, "com_obito": float(soma["com_obito"]),
        "com_sinistro": int((seg[COLUNAS_SINISTROS].sum(axis=1) > 0).sum()), "ups": ups,
        "por_trilha": {c: {"criticos": int(r["Critico"].astype(bool).sum()), "avaliados": int(len(r))}
                       for c, r in resultados.items()},
        "em_pelo_menos": {k: int((conv["n_trilhas"] >= k).sum()) for k in (1, 2, 3)},
    }

    def parcela(minimo: int) -> dict:
        sub = conv[conv["n_trilhas"] >= minimo]
        ext = float(pd.to_numeric(sub["extensao_trecho"], errors="coerce").sum()) if "extensao_trecho" in sub else 0
        obitos = float(soma["com_obito"])

        def fracao(parte, todo):
            return parte / todo if todo else math.nan

        return {"segmentos": int(len(sub)), "km": fracao(ext, km),
                "sinistros": fracao(float(sub[COLUNAS_SINISTROS].sum().sum()), total),
                "com_obito": fracao(float(sub["com_obito"].sum()), obitos),
                "ups": fracao(float(sub["UPS"].sum()), ups)}

    ind["parcela"] = {k: parcela(k) for k in (1, 2, 3)}
    return ind


def vias_criticas(conv: pd.DataFrame, minimo: int = 1, n: int = 10) -> pd.DataFrame:
    """Vias com mais segmentos críticos (em ao menos ``minimo`` trilhas)."""
    if "via" not in conv:
        return pd.DataFrame(columns=["via", "segmentos", "UPS"])
    sub = conv[conv["n_trilhas"] >= minimo]
    g = (sub.groupby("via", dropna=True).agg(segmentos=("segmento_id", "size"), UPS=("UPS", "sum"))
         .reset_index().sort_values(["segmentos", "UPS"], ascending=False))
    return g.head(n).reset_index(drop=True)


def histograma_ups(df_proc: pd.DataFrame, n_faixas: int = 30) -> pd.DataFrame:
    """Faixas da UPS dos segmentos com sinistro (os sem sinistro têm UPS zero e nunca são críticos). A cauda
    acima do percentil 99 fica numa última faixa, para as demais não virarem uma barra só."""
    seg = df_proc.drop_duplicates("segmento_id")
    ups = pd.to_numeric(seg.loc[seg[COLUNAS_SINISTROS].sum(axis=1) > 0, "UPS"], errors="coerce").dropna()
    if ups.empty:
        return pd.DataFrame(columns=["inicio", "fim", "segmentos", "faixa"])
    teto = max(float(np.percentile(ups, 99)), float(ups.min()) + 1)
    largura = max(1.0, math.ceil((teto - 0) / n_faixas))
    bordas = np.arange(0, teto + largura, largura)
    cont, _ = np.histogram(ups[ups < bordas[-1]], bins=bordas)
    linhas = [{"inicio": a, "fim": b, "segmentos": int(c)} for a, b, c in zip(bordas[:-1], bordas[1:], cont)]
    acima = ups[ups >= bordas[-1]]
    if len(acima):
        linhas.append({"inicio": bordas[-1], "fim": bordas[-1] + largura, "segmentos": int(len(acima))})
    df = pd.DataFrame(linhas)
    df = df[df["segmentos"].gt(0).cumsum().gt(0)]          # sem as faixas vazias do começo
    inteiro = largura == 1

    def faixa(r):
        if len(acima) and r.inicio == bordas[-1]:
            return f"{r.inicio:.0f} ou mais"
        if inteiro:
            return f"{r.inicio:.0f}"
        return f"até {r.fim - 1:.0f}" if r.inicio == 0 else f"{r.inicio:.0f} a {r.fim - 1:.0f}"

    df["faixa"] = df.apply(faixa, axis=1)
    return df.reset_index(drop=True)


def detalhes(resultados: dict, ids) -> dict:
    """Métricas de cada trilha para os segmentos ``ids`` (fichas do relatório e lista do painel)."""
    ids = [str(i) for i in ids]
    out = {i: {} for i in ids}
    for c, res in resultados.items():
        r = res.assign(segmento_id=res["segmento_id"].astype(str))
        r = r[r["segmento_id"].isin(ids)].drop_duplicates("segmento_id").set_index("segmento_id")
        for i, linha in r.iterrows():
            if c == "vc":
                out[i][c] = {"critico": bool(linha["Critico"]), "indice": float(linha["Indice"]),
                             "valor_critico": float(linha["Valor_Critico"])}
            elif c == "kde":
                out[i][c] = {"critico": bool(linha["Critico"]), "quartil": linha.get("nivel_densidade"),
                             "relativa": linha.get("indice_densidade")}
            elif c == "bayes":
                out[i][c] = {"critico": bool(linha["Critico"]), "esperada": float(linha["ajustado"]),
                             "prevista": float(linha["N_previsto"])}
    return out
