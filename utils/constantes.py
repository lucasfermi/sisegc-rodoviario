"""Constantes compartilhadas pela aplicação.

Numeração das trilhas, a mesma do Manual de Identificação de Segmentos Críticos
Rodoviários (2026): Trilha 1 = Valor Crítico, Trilha 2 = Densidade de Kernel (KDE) e
Trilha 3 = Empírico de Bayes. Para mudar a numeração exibida, altere só o dicionário
``TRILHAS``.
"""

# Nome e versão do sistema: os mesmos no app, no relatório PDF e na documentação
NOME_SISTEMA = "Sistema de Identificação de Segmentos Críticos Rodoviários"
SIGLA_SISTEMA = "SISegC Rodoviário"
VERSAO = "4.3.4"

# Pesos da Unidade Padrão de Severidade (Manual, equação 2.1)
PESOS_UPS_PADRAO = {"sem_vitima": 1, "com_vitima": 4, "com_obito": 28}

COLUNAS_SINISTROS = ["sem_vitima", "com_vitima", "com_obito"]

TRILHAS = {
    "vc": {"numero": 1, "nome": "Valor Crítico"},
    "kde": {"numero": 2, "nome": "Densidade de Kernel (KDE)"},
    "bayes": {"numero": 3, "nome": "Empírico de Bayes"},
}

# Chaves na ordem de exibição (pela numeração)
ORDEM_TRILHAS = sorted(TRILHAS, key=lambda c: TRILHAS[c]["numero"])


def rotulo_trilha(chave: str) -> str:
    """Rótulo completo de uma trilha, ex.: 'Trilha 3 — Empírico de Bayes'."""
    t = TRILHAS[chave]
    return f"Trilha {t['numero']} — {t['nome']}"


# Opções de variável de análise para as Trilhas 2 e 3 (Manual 2026, itens 3.2 e 3.3)
VARIAVEIS_ANALISE = {
    "severidade": "Severidade (UPS)",
    "frequencia": "Frequência (total de sinistros)",
}

# Coeficiente k da Normal padrão unicaudal (Manual, Tabela 3.1).
# 97,5% (k = 1,960) foi acrescentado porque é o valor usado pela Trilha de Bayes.
NIVEIS_CONFIANCA_K = {
    85.0: 1.036,
    90.0: 1.282,
    95.0: 1.645,
    97.5: 1.960,
    99.0: 2.326,
    99.5: 2.576,
}


def k_por_nivel(nivel_confianca: float) -> float:
    """Retorna o k da Tabela 3.1 do Manual; outros níveis (entre 0 e 100%) usam a Normal padrão."""
    nivel = float(nivel_confianca)
    if not (0.0 < nivel < 100.0):
        raise ValueError("O nível de confiança deve estar entre 0% e 100%.")
    chave = round(nivel, 4)
    if chave in NIVEIS_CONFIANCA_K:
        return NIVEIS_CONFIANCA_K[chave]
    from scipy.stats import norm

    return round(float(norm.ppf(nivel / 100.0)), 3)
