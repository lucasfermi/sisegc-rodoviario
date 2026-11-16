"""Trilha 1 — Métodos de Determinação do Valor Crítico.

Implementa os métodos de frequência e severidade do Manual de Identificação de
Segmentos Críticos Rodoviários (2026, item 3.1) e os métodos complementares de
taxa da literatura (Apêndice D do Manual):

=================  =========================================  ==============
método             índice do segmento                         equações
=================  =========================================  ==============
numero             Ifs_i = soma dos sinistros / E_i           3.1, 3.2, 3.3
severidade         Is_i = soma da UPS / E_i                   3.4, 3.5, 3.6
taxa_sinistros     Tfs_i = sinistros x 10^6 / (VMDa n 365 E_i) Apêndice D
taxa_severidade    Ts_i = UPS x 10^6 / (VMDa n 365 E_i)       Apêndice D
=================  =========================================  ==============

Valor crítico: média + k * sqrt(média / E) + sinal * 0,5 / E, em que E é a
extensão em km (métodos de frequência e severidade) ou a exposição em milhões de
veículos-km (métodos de taxa). O Manual usa sinal negativo (-0,5/E); a
literatura clássica (HSM, DER/PR PSR-D 01/24) usa +1/(2E). O sinal é parâmetro.
"""
import numpy as np

from utils.constantes import k_por_nivel

METODOS = {
    "numero": "Valor crítico de frequência (sinistros por km)",
    "severidade": "Valor crítico de severidade (UPS por km)",
    "taxa_sinistros": "Valor crítico da taxa de sinistros (por milhão de veículos-km)",
    "taxa_severidade": "Valor crítico da taxa de severidade (UPS por milhão de veículos-km)",
}


def aplicar_valor_critico(df, nivel_confianca=95.0, metodo="severidade", sinal_correcao=-1,
                          incluir_sem_sinistros=True):
    """Aplica a Trilha 1 e devolve uma linha por segmento, ordenada pelo índice.

    Parâmetros
    ----------
    nivel_confianca : nível de confiança em % (padrão 95,0%; Tabela 3.1 do Manual).
    metodo : 'numero', 'severidade', 'taxa_sinistros' ou 'taxa_severidade'.
    sinal_correcao : -1 (Manual: -0,5/E) ou +1 (literatura clássica: +1/(2E)).
    incluir_sem_sinistros : por recomendação do Manual, todos os segmentos da malha
        (inclusive os sem sinistros) entram no cálculo da média; pode ser desativado
        em análises personalizadas.
    """
    if metodo not in METODOS:
        raise ValueError(f"Método desconhecido: {metodo}")
    d = df.copy()
    if "total_sinistros" not in d:
        d["total_sinistros"] = d["sem_vitima"] + d["com_vitima"] + d["com_obito"]
    if "n_anos" not in d:
        d["n_anos"] = 1
    if "volume_trafego" not in d:
        d["volume_trafego"] = np.nan

    g = d.groupby("segmento_id", sort=False).agg(
        extensao_trecho=("extensao_trecho", "first"),
        total_sinistros=("total_sinistros", "sum"),
        UPS=("UPS", "sum"),
        volume_trafego=("volume_trafego", "mean"),
        n_anos=("n_anos", "max"),
    ).reset_index()

    avisos = []
    if metodo in ("taxa_sinistros", "taxa_severidade"):
        avisos.append("Nos métodos baseados em taxa (que assumem relação linear com o VMD), quando houver dados "
                      "confiáveis de volume de tráfego é preferível utilizar a Trilha 3 (Empírico de Bayes), "
                      "que modela a não linearidade da exposição e corrige a regressão à média.")
    if not incluir_sem_sinistros:
        n0 = int((g["total_sinistros"] == 0).sum())
        g = g[g["total_sinistros"] > 0]
        if n0:
            avisos.append(f"{n0} segmento(s) sem sinistros foram excluídos do cálculo da média "
                          "(a recomendação padrão do Manual inclui todos os segmentos analisados).")

    sem_ext = ~(g["extensao_trecho"] > 0)
    if sem_ext.all():
        raise ValueError("A Trilha 1 precisa da extensão dos segmentos (coluna extensao_trecho).")
    if sem_ext.any():
        avisos.append(f"{int(sem_ext.sum())} segmento(s) sem extensão ficaram fora da Trilha 1.")
        g = g[~sem_ext]

    k = k_por_nivel(nivel_confianca)
    E = g["extensao_trecho"].astype(float)
    x = g["UPS"] if metodo in ("severidade", "taxa_severidade") else g["total_sinistros"]

    if metodo in ("numero", "severidade"):
        indice = x / E                                   # Eq. 3.1 / 3.4
        media = indice.mean()                            # Eq. 3.2 / 3.5
        m = E
    else:
        sem_vmd = ~(g["volume_trafego"] > 0)
        if sem_vmd.all():
            raise ValueError("Os métodos de taxa precisam do volume de tráfego (VMD) dos segmentos.")
        if sem_vmd.any():
            avisos.append(f"{int(sem_vmd.sum())} segmento(s) sem VMD ficaram fora do método de taxa.")
            g, x, E = g[~sem_vmd], x[~sem_vmd], E[~sem_vmd]
        m = g["volume_trafego"] * g["n_anos"] * 365 * E * 1e-6   # milhões de veículos-km
        indice = x / m                                   # Eq. 3.7 / 3.10
        media = x.sum() / m.sum()                        # Eq. 3.8 / 3.11 (média ponderada)

    valor_critico = media + k * np.sqrt(media / m) + sinal_correcao * 0.5 / m   # Eq. 3.3, 3.6

    g = g.assign(Indice=indice, Valor_Critico=valor_critico, Media_Referencia=media)
    # com a correção -0,5/E, o valor crítico de segmentos muito curtos pode ficar negativo; sem sinistros, o
    # segmento nunca é classificado como crítico
    sem_sinistro_acima = (g["Indice"] > g["Valor_Critico"]) & (x <= 0)
    if sem_sinistro_acima.any():
        avisos.append(f"{int(sem_sinistro_acima.sum())} segmento(s) de pequena extensão e sem sinistros "
                      "apresentaram valor crítico negativo (em razão do termo de correção −0,5/E do Manual) "
                      "e foram mantidos como não críticos.")
    g["Critico"] = (g["Indice"] > g["Valor_Critico"]) & (x > 0)
    g["Metrica_Obs"] = g["Indice"]          # nome usado pela v4
    g = g.sort_values("Indice", ascending=False).reset_index(drop=True)
    g.attrs.update({"avisos": avisos, "metodo": metodo, "k": k, "nivel_confianca": nivel_confianca,
                    "sinal_correcao": sinal_correcao, "media": float(media)})
    return g
