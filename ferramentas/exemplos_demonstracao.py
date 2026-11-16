"""Planilhas de exemplo para demonstrar o app.

Uso, a partir da pasta do projeto:

    python ferramentas/exemplos_demonstracao.py <pasta de saída>

Gera:

* ``Exemplo A - sinistros georreferenciados FICTÍCIOS (DF).xlsx``: um sinistro por linha, no formato de uma base
  de DETRAN ou município (data, latitude, longitude, gravidade). Os pontos são **sorteados** sobre as vias do
  OpenStreetMap e do SNV no DF, com alguns pontos de concentração; não são sinistros reais. Entra em
  “Usar meus dados de sinistros”.
* ``Exemplo B - segmentos do DF com dados públicos.xlsx``: a planilha de segmentos que o app gera com os dados
  embutidos (SNV, PRF e VMD do PNCT) para o DF; entra em “Outras formas de entrada”.
* ``Exemplo C - exemplo resolvido do Manual (Trilha 1).xlsx``: os 15 segmentos do exemplo do Manual, com os
  críticos que o Manual encontra; entra em “Outras formas de entrada”.

O sorteio usa semente fixa: rodar de novo dá as mesmas planilhas.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import shapely

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from utils import dados_publicos as dp  # noqa: E402
from utils.entrada import ler_arquivo  # noqa: E402
from utils.segmentacao import _PARA_GEO, preparar_snv, segmentar  # noqa: E402

UF = "DF"
ANOS = [2023, 2024, 2025]
CAIXA_DF = (-48.28, -16.04, -47.32, -15.51)       # oeste, sul, leste, norte: dentro do DF
PESO_CLASSE = {"trunk": 6, "primary": 6, "motorway": 6, "secondary": 4, "tertiary": 2.5, "unclassified": 0.6,
               "residential": 0.6, "living_street": 0.3}
GRAVIDADES = ["Sem vítima", "Com vítima", "Com óbito"]
AVISO = ("DADOS FICTÍCIOS. Os sinistros desta planilha foram sorteados sobre as vias do OpenStreetMap e do SNV no "
         "DF, só para demonstrar o formato e o funcionamento do app. Não representam sinistros reais.")


def _pontos_ao_longo(geoms, n, rng, distancia=None, centro=None, raio=None):
    """``n`` pontos sobre as linhas ``geoms`` (uma por ponto); com ``centro``, a até ``raio`` m dele na linha."""
    comp = shapely.length(geoms)
    if centro is None:
        pos = rng.uniform(0, 1, n) * comp
    else:
        pos = np.clip(centro + rng.uniform(-raio, raio, n), 0, comp)
    return shapely.line_interpolate_point(geoms, pos)


def sinistros_ficticios(rng):
    vias = dp.ler_vias_osm(CAIXA_DF, urbanas=True)
    vias = vias[vias["codigo_via"].str.startswith(f"OSM{UF}")].reset_index(drop=True)
    snv = preparar_snv(dp.ler_snv([UF]))
    snv = snv[snv["com_pista"] & snv["vl_codigo"].eq(snv["codigo_principal"])].reset_index(drop=True)

    linhas = pd.DataFrame({"geom": list(vias["geom_m"]) + list(snv["geom_m"]),
                           "classe": list(vias["classe"]) + ["federal"] * len(snv),
                           "via": [n if isinstance(n, str) and n else (r if isinstance(r, str) else "")
                                   for n, r in zip(vias["nome"], vias["rotulo"])]
                           + [f"BR-{b}" for b in snv["vl_br"]]})
    linhas["comp"] = shapely.length(np.array(linhas["geom"]))
    linhas["peso"] = linhas["comp"] * linhas["classe"].map({**PESO_CLASSE, "federal": 5}).fillna(0.5)

    # sinistros espalhados, proporcionais à extensão e à classe da via
    n_base = 3600
    escolha = rng.choice(len(linhas), n_base, p=linhas["peso"] / linhas["peso"].sum())
    geoms = np.array(linhas["geom"])[escolha]
    pontos = list(_pontos_ao_longo(geoms, n_base, rng))
    via = list(linhas["via"].to_numpy()[escolha])
    grave = list(rng.choice(3, n_base, p=[0.66, 0.31, 0.03]))

    # pontos de concentração: 30 locais em vias arteriais (5 em rodovias federais), com 20 a 70 sinistros cada
    arteriais = linhas.index[linhas["classe"].isin(["trunk", "primary", "secondary"]) & (linhas["comp"] > 1500)]
    federais = linhas.index[linhas["classe"].eq("federal") & (linhas["comp"] > 1500)]
    locais = list(rng.choice(arteriais, 25, replace=False)) + list(rng.choice(federais, 5, replace=False))
    for i in locais:
        g, k = linhas.at[i, "geom"], int(rng.integers(20, 71))
        centro = rng.uniform(0.2, 0.8) * linhas.at[i, "comp"]
        pontos += list(_pontos_ao_longo(np.full(k, g), k, rng, centro=centro, raio=150))
        via += [linhas.at[i, "via"]] * k
        grave += list(rng.choice(3, k, p=[0.55, 0.39, 0.06]))

    xy = shapely.get_coordinates(np.array(pontos)) + rng.normal(0, 6, (len(pontos), 2))   # erro de GPS de ~6 m
    lon, lat = _PARA_GEO.transform(xy[:, 0], xy[:, 1])
    n = len(pontos)
    ano = rng.choice(ANOS, n, p=[0.32, 0.33, 0.35])
    dia = pd.to_datetime([f"{a}-01-01" for a in ano]) + pd.to_timedelta(rng.integers(0, 365, n), unit="D")
    hora = [f"{h:02d}:{m:02d}" for h, m in zip(rng.choice(24, n, p=_horas()), rng.integers(0, 60, n))]
    s = pd.DataFrame({"data": dia, "hora": hora, "latitude": np.round(lat, 6), "longitude": np.round(lon, 6),
                      "gravidade": [GRAVIDADES[g] for g in grave], "logradouro": via})
    s = s.sort_values(["data", "hora"]).reset_index(drop=True)
    sem = rng.choice(n, 12, replace=False)                     # 12 registros sem coordenada, como nas bases reais
    s.loc[sem, ["latitude", "longitude"]] = np.nan
    s.insert(0, "id", [f"FIC-{i:05d}" for i in range(1, n + 1)])
    s["data"] = s["data"].dt.strftime("%d/%m/%Y")
    return s, locais, linhas


def _horas():
    p = np.array([2, 1.5, 1, 1, 1, 2, 4, 6, 6, 5, 5, 5, 6, 6, 6, 6, 7, 8, 8, 6, 5, 4, 3, 2.5])
    return p / p.sum()


def escrever(caminho, abas: dict[str, pd.DataFrame], leia: list[str]):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    with pd.ExcelWriter(caminho, engine="openpyxl") as w:
        for nome, df in abas.items():
            df.to_excel(w, sheet_name=nome, index=False)
        pd.DataFrame({"Leia-me": leia}).to_excel(w, sheet_name="Leia-me", index=False)
        for ws in w.book.worksheets:
            ws.freeze_panes = "A2"
            for c in ws[1]:
                c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F4E79")
            for i, col in enumerate(ws.iter_cols(min_row=1, max_row=min(ws.max_row, 300)), start=1):
                larg = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[get_column_letter(i)].width = min(max(9, larg + 2), 45)
        ws = w.book["Leia-me"]
        ws.column_dimensions["A"].width = 120
        for linha in ws.iter_rows(min_row=2):
            linha[0].alignment = Alignment(wrap_text=True, vertical="top")


def main(saida):
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(2026)

    # A. sinistros fictícios
    s, locais, linhas = sinistros_ficticios(rng)
    cont = s["gravidade"].value_counts()
    escrever(saida / "Exemplo A - sinistros georreferenciados FICTÍCIOS (DF).xlsx", {"Sinistros": s}, [
        AVISO, "",
        f"{len(s):,} sinistros de {ANOS[0]} a {ANOS[-1]} (".replace(",", ".")
        + ", ".join(f"{cont.get(g, 0):,} {g.lower()}".replace(",", ".") for g in GRAVIDADES) + ").",
        "Formato: um sinistro por linha, com id, data, latitude, longitude e gravidade (em texto). As colunas hora e "
        "logradouro são só informativas; o app ignora colunas que não usa.",
        "12 linhas não têm coordenada, como acontece nas bases reais: o app avisa e as deixa de fora.",
        f"Há {len(locais)} pontos de concentração (25 em vias arteriais e 5 em rodovias federais), para que as "
        "análises encontrem segmentos críticos.",
        "",
        "Como usar no app: na barra lateral, abra “Usar meus dados de sinistros”, envie esta planilha e escolha a UF "
        "DF. Os sinistros nas rodovias federais vão para o SNV; os demais, para as vias do OpenStreetMap (com as "
        "ruas residenciais). Como as vias do OpenStreetMap não têm VMD, a Trilha 3 e os métodos de taxa da Trilha 1 "
        "rodam só nos segmentos do SNV.",
        "",
        "Gerado por ferramentas/exemplos_demonstracao.py (semente fixa).",
    ])

    # B. segmentos do DF com os dados embutidos
    snv = preparar_snv(dp.ler_snv([UF]))
    seg = segmentar(dp.ler_sinistros_prf([UF], ANOS), snv, [UF], ANOS, 1.0, False, vmd=dp.ler_vmd())
    resumo = seg.attrs.get("resumo", {})
    seg = seg.reset_index(drop=True)
    escrever(saida / "Exemplo B - segmentos do DF com dados públicos.xlsx", {"Segmentos": seg}, [
        "Planilha de segmentos gerada pelo app com os dados públicos embutidos: malha do SNV "
        f"{resumo.get('versao_snv', '')} (DNIT), sinistros da PRF de {ANOS[0]} a {ANOS[-1]} e VMD do PNCT (2019).",
        f"{len(seg):,} segmentos de cerca de 1 km nas rodovias federais do DF; "
        f"{int(seg[['sem_vitima', 'com_vitima', 'com_obito']].sum().sum()):,} sinistros.".replace(",", "."),
        "É a mesma planilha do botão “Baixar segmentos (planilha)” da segmentação automática.",
        "",
        "Como usar no app: abra “Outras formas de entrada” e envie esta planilha. As três trilhas rodam com ela, sem "
        "a segmentação; o resultado é o mesmo de escolher DF e os anos 2023 a 2025 na segmentação automática.",
        "Serve de modelo para quem já tem os segmentos: uma linha por segmento (ou por segmento e ano), com "
        "extensão, VMD e as contagens de sinistros sem vítima, com vítima e com óbito.",
    ])

    # C. exemplo resolvido do Manual
    arq = RAIZ / "data" / "exemplo_manual_trilha1.csv"
    manual = ler_arquivo(arq.name, arq.read_bytes())
    escrever(saida / "Exemplo C - exemplo resolvido do Manual (Trilha 1).xlsx", {"Segmentos": manual}, [
        "Exemplo resolvido do Manual (capítulo 5): 15 segmentos, 3 anos (uma linha por segmento e ano).",
        "Críticos que o Manual encontra e que o app reproduz (Trilha 1, nível de confiança de 95%):",
        "  número de sinistros: segmentos 7, 8 e 9;",
        "  severidade (UPS, padrão do app): segmentos 7, 8, 9 e 11;",
        "  taxa de severidade: segmentos 3, 7, 8 e 9 (Tabela 5.5).",
        "Os valores conferem com o Manual até a segunda casa decimal; os testes do app (tests/test_trilha1_manual.py) "
        "checam esses números a cada mudança no código.",
        "Observação: o Manual imprime Ns = 15,73 no método do número de sinistros, mas a soma da Tabela 5.1 dá "
        "226/15 = 15,07; o app usa a conta certa e chega aos mesmos críticos.",
        "",
        "Como usar no app: abra “Outras formas de entrada” e envie esta planilha. Não há coordenadas, então a "
        "Trilha 2 (KDE) não roda e o app avisa.",
    ])
    print(f"A: {len(s)} sinistros; B: {len(seg)} segmentos; C: {manual['segmento_id'].nunique()} segmentos")


if __name__ == "__main__":
    main(sys.argv[1])
