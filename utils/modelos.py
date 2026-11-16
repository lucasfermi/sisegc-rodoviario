"""Planilhas-modelo para baixar no app: segmentos (“Outras formas de entrada”) e sinistros (“Usar meus dados
de sinistros”). Cada modelo tem a aba de dados e uma aba “Instruções” com o que cada coluna significa.

Os nomes das colunas são os mesmos das planilhas que o app gera (``utils/tabelas.py``) e o leitor reconhece
também os nomes técnicos (``segmento_id``, ``sem_vitima`` etc.), sem acento, com outra caixa ou com espaços.
"""
from __future__ import annotations

import io
from datetime import date

import pandas as pd

COR_CABECALHO = "#0988C3"

COLUNAS_MODELO_SEGMENTOS = ["ID do segmento", "Rodovia ou via", "Latitude", "Longitude", "Extensão (km)",
                            "VMD (veículos/dia)", "Anos de dados", "Sinistros sem vítima", "Sinistros com vítima",
                            "Sinistros com óbito"]
EXEMPLO_SEGMENTOS = [
    ["A1", "Via A, km 0,0 a 1,2", -15.7801, -47.9292, 1.2, 5000, 3, 10, 2, 0],
    ["A2", "Via A, km 1,2 a 2,0", -15.7654, -47.9400, 0.8, 4500, 3, 3, 1, 1],
    ["A3", "Via B, km 0,0 a 1,5", -15.8000, -47.9450, 1.5, 5200, 3, 0, 0, 0],
    ["A4", "Via B, km 1,5 a 3,5", -15.8120, -47.8900, 2.0, 6000, 3, 0, 5, 2],
]
INSTRUCOES_SEGMENTOS = [
    ("ID do segmento", "Sim", "Identificador único de cada segmento (texto ou número).", "Todas"),
    ("Rodovia ou via", "Não", "Nome ou descrição do segmento; aparece nas tabelas, nos mapas e no relatório.", "—"),
    ("Latitude e Longitude", "Para a Trilha 2", "Coordenada do meio do segmento, em graus decimais (ex.: -15,7801). "
     "Sem elas, a Trilha 2 e os mapas não rodam.", "Trilha 2 e mapas"),
    ("Extensão (km)", "Para as Trilhas 1 e 3", "Comprimento do segmento, em quilômetros.", "Trilhas 1 e 3"),
    ("VMD (veículos/dia)", "Para a Trilha 3", "Volume médio diário anual de veículos, somados os dois sentidos. "
     "Sem ele, a Trilha 3 e os métodos de taxa da Trilha 1 não rodam.", "Trilha 3 e taxas da Trilha 1"),
    ("Anos de dados", "Recomendada", "Quantos anos as contagens somam (o Manual recomenda ao menos 3). Sem ela, "
     "o app considera 3 anos.", "Taxas da Trilha 1 e Trilha 3"),
    ("Sinistros sem vítima", "Sim", "Número de sinistros só com danos materiais no período.", "Todas (UPS)"),
    ("Sinistros com vítima", "Sim", "Número de sinistros com feridos (sem mortos) no período.", "Todas (UPS)"),
    ("Sinistros com óbito", "Sim", "Número de sinistros com ao menos um morto no período.", "Todas (UPS)"),
]
NOTAS_SEGMENTOS = [
    "Uma linha por segmento, com os sinistros somados no período. Também servem: uma linha por segmento e ano "
    "(com uma coluna Ano) e as planilhas oficiais, com colunas Sinistros_SV/CV/CO AAAA e VMD AAAA.",
    "O app também reconhece os nomes técnicos (segmento_id, sem_vitima, com_vitima, com_obito, latitude, "
    "longitude, extensao_trecho, volume_trafego, n_anos). Colunas que o app não usa são ignoradas.",
    "Números podem usar vírgula decimal (1,2) ou ponto (1.2).",
    "A planilha “Baixar segmentos (planilha)” do app tem este mesmo formato: dá para baixar, corrigir e enviar de "
    "novo em “Outras formas de entrada”.",
]

COLUNAS_MODELO_SINISTROS = ["ID", "Data", "Latitude", "Longitude", "Gravidade", "UF"]
# Sinistros FICTÍCIOS, sorteados sobre vias reais de Brasília (DF), só para mostrar o formato
EXEMPLO_SINISTROS = [
    ("2023-05-10", -15.788815, -47.929318, "Sem vítima"),
    ("2023-05-31", -15.79684, -47.944776, "Com vítima"),
    ("2023-07-30", -15.820553, -47.936542, "Sem vítima"),
    ("2023-08-04", -15.790387, -47.884016, "Com vítima"),
    ("2023-10-07", -15.813514, -47.907635, "Sem vítima"),
    ("2023-11-12", -15.802253, -47.893565, "Com vítima"),
    ("2023-11-28", -15.815978, -47.920514, "Sem vítima"),
    ("2024-01-02", -15.820851, -47.936486, "Sem vítima"),
    ("2024-01-22", -15.838256, -47.883091, "Sem vítima"),
    ("2024-04-12", -15.792393, -47.94332, "Com vítima"),
    ("2024-05-05", -15.842267, -47.931298, "Com vítima"),
    ("2024-06-07", -15.789376, -47.905269, "Com óbito"),
    ("2024-07-08", -15.835044, -47.81797, "Sem vítima"),
    ("2024-10-01", -15.820827, -47.936427, "Com vítima"),
    ("2024-11-14", -15.717626, -47.863416, "Sem vítima"),
    ("2024-12-06", -15.796248, -47.944655, "Sem vítima"),
    ("2024-12-30", -15.796702, -47.944762, "Sem vítima"),
    ("2025-02-25", -15.796585, -47.944763, "Sem vítima"),
    ("2025-04-23", -15.820435, -47.936581, "Com óbito"),
    ("2025-07-13", -15.814436, -47.897547, "Sem vítima"),
    ("2025-09-07", -15.785831, -47.87355, "Sem vítima"),
    ("2025-09-07", -15.769048, -47.88288, "Sem vítima"),
    ("2025-10-16", -15.798925, -47.925275, "Com vítima"),
    ("2025-11-26", -15.851498, -47.87636, "Sem vítima"),
]
INSTRUCOES_SINISTROS = [
    ("ID", "Não", "Identificador do sinistro (ex.: número do boletim).", "—"),
    ("Data", "Recomendada (ou Ano)", "Data do sinistro: DD/MM/AAAA ou AAAA-MM-DD; a hora, se vier junto, é ignorada. "
     "Pode ser trocada por uma coluna Ano. Sem data ou ano, o sistema assume período de 3 anos.", "Escolha dos anos"),
    ("Latitude e Longitude", "Sim", "Coordenada do sinistro em graus decimais (ex.: -15,7942 e -47,8822), com ponto "
     "ou vírgula. Sinistros sem coordenada ficam de fora e o app avisa.", "Localização na via"),
    ("Gravidade", "Sim (ou Mortos e Feridos)", "Sem vítima, Com vítima (feridos) ou Com óbito (ao menos um morto). "
     "Textos como “Com vítimas fatais” e “Com vítimas feridas”, da PRF, ou pesos numéricos (1, 4, 28) também servem.",
     "UPS"),
    ("Mortos e Feridos", "Alternativa à Gravidade", "Número de mortos e de feridos de cada sinistro: com mortos é "
     "óbito; só com feridos, com vítima; sem nenhum, sem vítima.", "UPS"),
    ("UF", "Não", "Sigla ou nome por extenso da UF do sinistro (ex.: PE ou Pernambuco). Sem ela, valem todos os "
     "sinistros do arquivo na UF escolhida no app.", "Filtro da UF"),
]
NOTAS_SINISTROS = [
    "DADOS FICTÍCIOS: os sinistros do Modelo Preenchido foram sorteados sobre vias de Brasília só para mostrar o "
    "formato. Para testar, envie este arquivo em “Usar meus dados de sinistros” e escolha a UF DF.",
    "Uma linha por sinistro, de qualquer via (municipal, estadual ou federal). O app prende cada sinistro à via mais "
    "próxima: rodovia federal do SNV até 100 m; demais vias do OpenStreetMap até 50 m.",
    "Os arquivos de dados abertos da PRF (datatran, .csv ou .zip) também são aceitos como estão.",
    "Colunas que o app não usa (hora, logradouro, tipo de sinistro...) podem ficar na planilha: são ignoradas.",
]


def _escrever(dados: pd.DataFrame, instrucoes, notas, aba: str, datas: tuple[str, ...] = ()) -> bytes:
    saida = io.BytesIO()
    with pd.ExcelWriter(saida, engine="xlsxwriter", datetime_format="dd/mm/yyyy", date_format="dd/mm/yyyy") as w:
        dados.to_excel(w, sheet_name=aba, index=False)
        wb, ws = w.book, w.sheets[aba]
        cab = wb.add_format({"bold": True, "text_wrap": True, "valign": "vcenter", "align": "center",
                             "fg_color": COR_CABECALHO, "font_color": "#FFFFFF", "border": 1})
        for i, nome in enumerate(dados.columns):
            ws.write(0, i, nome, cab)
            ws.set_column(i, i, 14 if nome in datas else max(len(nome) + 4, 12))
        ws.freeze_panes(1, 0)

        tabela = pd.DataFrame(instrucoes, columns=["Coluna", "Obrigatória?", "O que é", "Usada em"])
        tabela.to_excel(w, sheet_name="Instruções", index=False, startrow=1)
        wi = w.sheets["Instruções"]
        quebra = wb.add_format({"text_wrap": True, "valign": "top"})
        wi.write(0, 0, "Como preencher", wb.add_format({"bold": True, "font_size": 13, "font_color": COR_CABECALHO}))
        for i, nome in enumerate(tabela.columns):
            wi.write(1, i, nome, cab)
        for i, largura in enumerate((24, 22, 70, 24)):
            wi.set_column(i, i, largura, quebra)
        linha = len(tabela) + 3
        for nota in notas:
            wi.merge_range(linha, 0, linha, 3, nota, quebra)
            wi.set_row(linha, 32)
            linha += 1
    return saida.getvalue()


def modelo_segmentos(preenchido: bool) -> bytes:
    """Modelo da planilha de segmentos (``preenchido``: com 4 segmentos de exemplo)."""
    dados = pd.DataFrame(EXEMPLO_SEGMENTOS if preenchido else [], columns=COLUNAS_MODELO_SEGMENTOS)
    return _escrever(dados, INSTRUCOES_SEGMENTOS, NOTAS_SEGMENTOS, "Segmentos")


def modelo_sinistros(preenchido: bool) -> bytes:
    """Modelo da planilha de sinistros (``preenchido``: com 24 sinistros fictícios em Brasília)."""
    linhas = [(f"FIC-{i:04d}", date.fromisoformat(d), la, lo, g, "DF")
              for i, (d, la, lo, g) in enumerate(EXEMPLO_SINISTROS, start=1)] if preenchido else []
    dados = pd.DataFrame(linhas, columns=COLUNAS_MODELO_SINISTROS)
    if preenchido:
        dados["Data"] = pd.to_datetime(dados["Data"])
    notas = NOTAS_SINISTROS if preenchido else NOTAS_SINISTROS[1:]
    return _escrever(dados, INSTRUCOES_SINISTROS, notas, "Sinistros", datas=("Data",))
