"""Tabelas para a tela e para as planilhas: colunas na ordem de leitura e com nomes claros.

Os nomes internos (``segmento_id``, ``sem_vitima``...) continuam no código e nas trilhas; só a apresentação
muda. O leitor de planilhas (``utils/entrada.py``) reconhece os nomes daqui, então a planilha dos segmentos
baixada pode ser corrigida e enviada de novo em “Outras formas de entrada”.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from utils.constantes import COLUNAS_SINISTROS

NOMES = {
    "segmento_id": "ID do segmento",
    "rodovia": "Rodovia ou via",
    "Critico": "Crítico",
    "fonte": "Fonte da via",
    "sentido": "Sentido",
    "km_inicial": "km inicial",
    "km_final": "km final",
    "extensao_trecho": "Extensão (km)",
    "volume_trafego": "VMD (veículos/dia)",
    "n_anos": "Anos de dados",
    "sem_vitima": "Sinistros sem vítima",
    "com_vitima": "Sinistros com vítima",
    "com_obito": "Sinistros com óbito",
    "total_sinistros": "Total de sinistros",
    "UPS": "UPS",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "codigo_snv": "Código SNV",
    "codigo_via": "Código da via (OSM)",
    "classe": "Classe da via (OSM)",
    "vmd_origem": "Origem do VMD",
    "vmd_classificacao": "Classificação do VMD (PNCT)",
    # Trilha 1
    "Indice": "Índice observado",
    "Valor_Critico": "Valor crítico",
    "Media_Referencia": "Média de referência",
    # Trilha 2
    "nivel_densidade": "Quartil da densidade (1 a 4)",
    "densidade": "Densidade de kernel",
    "indice_densidade": "Densidade relativa (% do máximo)",
    # Trilha 3 (variáveis padronizadas com o Manual 2026, item 3.3)
    "ajustado": "Nesperado",
    "N_previsto": "Nprevisto",
    "excesso": "Excesso (Nesperado − Nprevisto)",
    "desvio_padrao": "Desvio-padrão (DP)",
    "omega": "Peso da referência (ω)",
    "N_observado": "Nobservado",
    "exposicao": "Exposição (milhões de veíc.·km)",
}

# Unidade e notação das variáveis da Trilha 1 em cada método (Manual 2026, item 3.1)
UNIDADE_VC = {
    "numero": "sinistros/km",
    "severidade": "UPS/km",
    "taxa_sinistros": "sinistros por milhão de veíc.·km",
    "taxa_severidade": "UPS por milhão de veíc.·km",
}

ROTULOS_VC = {
    "numero": {
        "Indice": "Índice de frequência — Ifsi",
        "Valor_Critico": "Valor crítico — CFsi",
        "Media_Referencia": "Valor médio da frequência — Ifs",
    },
    "severidade": {
        "Indice": "Índice de severidade — Isi",
        "Valor_Critico": "Valor crítico — CSi",
        "Media_Referencia": "Índice de severidade médio — Is",
    },
    "taxa_sinistros": {
        "Indice": "Taxa de frequência — Tfsi",
        "Valor_Critico": "Valor crítico — CTfsi",
        "Media_Referencia": "Taxa média de frequência — Tfs",
    },
    "taxa_severidade": {
        "Indice": "Taxa de severidade — Tsi",
        "Valor_Critico": "Valor crítico — CTsi",
        "Media_Referencia": "Taxa média de severidade — Ts",
    },
}

ORDEM_SEGMENTOS = ["segmento_id", "rodovia", "fonte", "km_inicial", "km_final", "sentido", "extensao_trecho",
                   "volume_trafego", "n_anos", *COLUNAS_SINISTROS, "latitude", "longitude", "codigo_snv",
                   "codigo_via", "classe", "vmd_origem", "vmd_classificacao"]
_DADOS_SEGMENTO = ["total_sinistros", "UPS", *COLUNAS_SINISTROS, "extensao_trecho", "volume_trafego", "n_anos"]
COLUNAS_TRILHA = {
    "vc": ["Indice", "Valor_Critico", "Media_Referencia", *_DADOS_SEGMENTO],
    "kde": ["nivel_densidade", "densidade", "indice_densidade", *_DADOS_SEGMENTO],
    "bayes": ["ajustado", "N_previsto", "excesso", "desvio_padrao", "omega", "N_observado", "exposicao",
              *[c for c in _DADOS_SEGMENTO if c != "UPS"]],          # a UPS observada já está acima
}
EXTRAS_FIM = ["km_inicial", "km_final", "sentido", "fonte", "latitude", "longitude", "codigo_snv", "codigo_via",
              "classe", "vmd_origem", "vmd_classificacao"]


def nomes_trilha(chave: str, attrs: dict | None = None) -> dict:
    """Nomes das colunas de uma trilha; na Trilha 1, com a variável do Manual e a unidade do método."""
    nomes = dict(NOMES)
    if chave == "vc":
        metodo = (attrs or {}).get("metodo")
        unidade = UNIDADE_VC.get(metodo)
        rotulos = ROTULOS_VC.get(metodo, {})
        if unidade:
            for c in ("Indice", "Valor_Critico", "Media_Referencia"):
                base = rotulos.get(c, NOMES[c])
                nomes[c] = f"{base} ({unidade})"
    return nomes


def tabela_segmentos(dados: pd.DataFrame) -> pd.DataFrame:
    """Segmentos com nomes claros, na ordem de leitura (colunas desconhecidas vão para o fim, como estão)."""
    colunas = [c for c in ORDEM_SEGMENTOS if c in dados] + [c for c in dados.columns if c not in ORDEM_SEGMENTOS]
    return dados[colunas].rename(columns=NOMES)


def tabela_resultado(chave: str, res: pd.DataFrame, dados: pd.DataFrame | None = None) -> pd.DataFrame:
    """Resultado de uma trilha para a tela ou a planilha: ID, via, se é crítico e as métricas da trilha
    primeiro; depois os dados do segmento (os que a trilha não traz vêm de ``dados``)."""
    t = res
    if dados is not None:
        falta = [c for c in ("rodovia", *_DADOS_SEGMENTO, *EXTRAS_FIM) if c not in t and c in dados]
        if falta:
            t = t.merge(dados[["segmento_id", *falta]].drop_duplicates("segmento_id"), on="segmento_id", how="left")
    ordem = ["segmento_id", "rodovia", "Critico", *COLUNAS_TRILHA[chave], *EXTRAS_FIM]
    t = t[[c for c in ordem if c in t]].copy()
    t["Critico"] = np.where(t["Critico"].astype(bool), "Sim", "Não")
    if "nivel_densidade" in t:
        t["nivel_densidade"] = pd.to_numeric(t["nivel_densidade"], errors="coerce").round().astype("Int64")
    return t.rename(columns=nomes_trilha(chave, res.attrs))
