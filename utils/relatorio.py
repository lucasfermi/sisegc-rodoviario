"""Relatório executivo em PDF (fpdf2): o painel do app num arquivo, para uso fora da aplicação.

Ordem: números principais, mapa dos críticos, convergência entre as trilhas, fichas dos segmentos
prioritários, distribuição da UPS, resultados por trilha, dados e limitações, metodologia com os parâmetros
usados e, no anexo, a lista de prioridades.
"""
import io
import os
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from fpdf import FPDF  # noqa: E402
from fpdf.enums import MethodReturnValue, XPos, YPos  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from utils import painel  # noqa: E402
from utils.constantes import NOME_SISTEMA, ORDEM_TRILHAS, SIGLA_SISTEMA, VERSAO, rotulo_trilha  # noqa: E402
from utils.tabelas import UNIDADE_VC  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
PASTA_FONTES = BASE / "static" / "fonts"

COR_AZUL = (9, 136, 195)     # #0988C3
COR_VERDE = (92, 193, 4)     # #5CC104
COR_AMARELO = (255, 201, 0)  # #FFC900
COR_ROXO = (100, 96, 154)    # #64609A
COR_CINZA = (128, 128, 128)
COR_TEXTO = (20, 20, 20)
COR_FUNDO = (242, 248, 252)
TINTA, TINTA_2, MUDA, GRADE = "#141414", "#52514e", "#898781", "#e1e0d9"   # textos e eixos dos gráficos

LIMITE_ANEXO = 100
CINZA_MALHA = "#b5b4ad"          # segmentos analisados, sem mapa de fundo
CINZA_MALHA_FUNDO = "#7d7c76"    # sobre o mapa de fundo (já claro), um cinza mais escuro
NOMES_N = {1: "em 1 trilha", 2: "em 2 trilhas", 3: "nas 3 trilhas"}

for _arquivo in ("Roboto-Regular.ttf", "Roboto-Bold.ttf"):
    if (PASTA_FONTES / _arquivo).exists():
        font_manager.fontManager.addfont(str(PASTA_FONTES / _arquivo))
_FONTE_GRAFICOS = "Roboto" if (PASTA_FONTES / "Roboto-Regular.ttf").exists() else "DejaVu Sans"


def _br(valor, casas=1):
    """Formata número no padrão brasileiro: 1.234,5."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(x) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    if x == 0:
        return "0%"
    if x < 0.01:
        return "menos de 1%"
    if 0.995 <= x < 1.0:
        return f"{min(99.9, np.floor(1000 * x + 1e-9) / 10):.1f}%".replace(".", ",")   # nunca 100% se não for
    return f"{100 * x:.0f}%"


def _plural(n, singular, plural=None):
    return singular if n == 1 else (plural or singular + "s")


class PDFRelatorio(FPDF):
    def __init__(self, logo_path=None):
        super().__init__()
        self.logo_path = logo_path
        self.set_auto_page_break(auto=True, margin=20)
        self.set_title(f"Relatório executivo do {SIGLA_SISTEMA}")
        self.set_creator(f"{NOME_SISTEMA} ({SIGLA_SISTEMA}), versão {VERSAO}")
        self.fonte = "helvetica"
        regular = PASTA_FONTES / "Roboto-Regular.ttf"
        if regular.exists():
            self.add_font("Roboto", "", str(regular))
            self.add_font("Roboto", "B", str(PASTA_FONTES / "Roboto-Bold.ttf"))
            self.add_font("Roboto", "I", str(PASTA_FONTES / "Roboto-Italic.ttf"))
            self.fonte = "Roboto"

    def header(self):
        self.set_line_width(2)
        self.set_draw_color(*COR_AZUL)
        self.line(0, 5, 210, 5)
        self.set_draw_color(*COR_VERDE)
        self.line(0, 7, 150, 7)
        self.set_draw_color(*COR_AMARELO)
        self.line(0, 9, 100, 9)
        if self.logo_path and Path(self.logo_path).exists():
            self.image(str(self.logo_path), 10, 13, 34)
        self.set_y(15)
        self.set_font(self.fonte, "B", 9)
        self.set_text_color(*COR_ROXO)
        self.cell(0, 5, NOME_SISTEMA, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font(self.fonte, "", 8)
        self.set_text_color(*COR_AZUL)
        self.cell(0, 4, f"{SIGLA_SISTEMA} · relatório executivo", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(12)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.fonte, "I", 8)
        self.set_text_color(*COR_CINZA)
        self.cell(0, 10, f"{SIGLA_SISTEMA} {VERSAO} | Página {self.page_no()} | Gerado em "
                         f"{datetime.now().strftime('%d/%m/%Y')}", align="C")

    def espaco(self, altura):
        """Nova página se não couber ``altura`` mm (evita título ou caixa órfã no pé da página)."""
        if self.get_y() + altura > self.page_break_trigger:
            self.add_page()

    def capitulo_titulo(self, label, minimo=40):
        """Título de seção; ``minimo``: espaço (mm) que o título e o começo da seção pedem na página."""
        self.espaco(minimo)
        self.ln(3)
        self.set_font(self.fonte, "B", 14)
        self.set_text_color(*COR_AZUL)
        self.set_fill_color(*COR_AMARELO)
        self.rect(10, self.get_y() + 2.5, 5, 5, "F")
        self.set_x(18)
        self.cell(0, 10, label, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def subtitulo(self, label):
        self.espaco(25)
        self.set_font(self.fonte, "B", 11)
        self.set_text_color(*COR_ROXO)
        self.cell(0, 7, label, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def texto_corpo(self, text, tamanho=10.5):
        self.set_font(self.fonte, "", tamanho)
        self.set_text_color(*COR_TEXTO)
        self.multi_cell(0, 5.5, text, markdown=True, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def itens(self, linhas, tamanho=9.5):
        self.set_font(self.fonte, "", tamanho)
        self.set_text_color(*COR_TEXTO)
        for linha in linhas:
            self.set_x(14)
            self.multi_cell(0, 5, f"•  {linha}", markdown=True, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(0.8)
        self.ln(2)

    def destaque_box(self, text, tipo="info"):
        self.set_font(self.fonte, "B", 10)
        if tipo == "conclusao":
            self.set_fill_color(*COR_FUNDO)
            self.set_text_color(*COR_AZUL)
            self.set_draw_color(*COR_AZUL)
        else:
            self.set_fill_color(255, 250, 205)
            self.set_text_color(*COR_ROXO)
            self.set_draw_color(*COR_AMARELO)
        self.set_line_width(0.3)
        linhas = self.multi_cell(0, 6.5, text, padding=2, markdown=True, dry_run=True, output=MethodReturnValue.LINES)
        self.espaco(6.5 * len(linhas) + 6)                 # a caixa não se divide entre duas páginas
        self.multi_cell(0, 6.5, text, border=1, align="L", fill=True, padding=2, markdown=True,
                        new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)

    def indicadores(self, caixas):
        """Caixas com um número grande e o rótulo embaixo, três por linha."""
        largura, altura, folga = 60, 22, 5
        for i in range(0, len(caixas), 3):
            self.espaco(altura + 4)
            y = self.get_y()
            for j, (valor, rotulo) in enumerate(caixas[i:i + 3]):
                x = 10 + j * (largura + folga)
                self.set_fill_color(*COR_FUNDO)
                self.set_draw_color(*COR_AZUL)
                self.set_line_width(0.3)
                self.rect(x, y, largura, altura, "DF")
                self.set_xy(x, y + 2.5)
                self.set_font(self.fonte, "B", 17)
                self.set_text_color(*COR_AZUL)
                self.cell(largura, 9, valor, align="C")
                self.set_xy(x + 2, y + 12)
                self.set_font(self.fonte, "", 8.5)
                self.set_text_color(*COR_TEXTO)
                self.multi_cell(largura - 4, 4, rotulo, align="C")
            self.set_xy(10, y + altura + 4)

    def adicionar_tabela(self, df, larguras=None, tamanho=8, alinhar=None):
        """Tabela com cabeçalho azul repetido a cada página; ``alinhar``: 'L' ou 'C' por coluna (padrão: texto
        longo à esquerda, o resto centrado)."""
        if df.empty:
            return
        cols = list(df.columns)
        larguras = larguras or [190 / len(cols)] * len(cols)
        alinhar = alinhar or ["L" if c in ("Rodovia ou via", "Valor", "Parâmetro") else "C" for c in cols]
        limites = [max(6, int(w / 1.7)) for w in larguras]

        def cabecalho():
            self.set_line_width(0.2)
            self.set_draw_color(180, 180, 180)
            self.set_font(self.fonte, "B", tamanho)
            linhas = [self.multi_cell(w - 2, 4, str(c), dry_run=True, output=MethodReturnValue.LINES)
                      for c, w in zip(cols, larguras)]
            altura = max(7, 4 * max(len(x) for x in linhas) + 2)
            y, x = self.get_y(), self.l_margin
            for col, w, ls in zip(cols, larguras, linhas):
                self.set_fill_color(*COR_AZUL)
                self.rect(x, y, w, altura, "DF")
                self.set_text_color(255, 255, 255)
                self.set_xy(x + 1, y + (altura - 4 * len(ls)) / 2)
                self.multi_cell(w - 2, 4, str(col), align="C")
                x += w
            self.set_xy(self.l_margin, y + altura)

        self.espaco(20)
        cabecalho()
        self.set_font(self.fonte, "", tamanho)
        fill = False
        for _, row in df.iterrows():
            if self.get_y() + 6 > self.page_break_trigger:
                self.add_page()
                cabecalho()
                self.set_font(self.fonte, "", tamanho)
            self.set_text_color(0, 0, 0)
            self.set_fill_color(245, 245, 245)
            for col, w, lim, al in zip(cols, larguras, limites, alinhar):
                v = row[col]
                if isinstance(v, (float, np.floating)):
                    val = "—" if np.isnan(v) else (_br(v, 0) if float(v).is_integer() else _br(v, 2))
                elif isinstance(v, (int, np.integer)):
                    val = _br(v, 0)
                else:
                    val = "" if pd.isna(v) else str(v)
                if len(val) > lim:
                    val = val[:lim - 1] + "…"
                self.cell(w, 6, (" " + val) if al == "L" else val, border=1, align=al, fill=fill)
            self.ln()
            fill = not fill
        self.ln(4)

    def adicionar_grafico(self, fig, largura=170):
        """Insere a figura (ou o PNG já pronto de ``png_da_figura``) centralizada, com ``largura`` mm."""
        buf = fig[0] if isinstance(fig, tuple) else png_da_figura(fig)[0]
        self.image(buf, x=(210 - largura) / 2, w=largura)
        self.ln(3)


# ---------------------------------------------------------------------------------------------------
# Gráficos (mesmas cores do painel do app)
# ---------------------------------------------------------------------------------------------------
def _eixos(ax, grade="x"):
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color("#c3c2b7")
        ax.spines[lado].set_linewidth(0.8)
    ax.tick_params(colors=MUDA, labelsize=8, length=0)
    ax.grid(axis=grade, color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)


def png_da_figura(fig):
    """PNG da figura (como entra no PDF) e o tamanho em pixels, para saber a altura antes de inserir."""
    from PIL import Image

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    largura, altura = Image.open(buf).size
    buf.seek(0)
    return buf, largura, altura


def _figura(largura, altura):
    plt.rcParams["font.family"] = _FONTE_GRAFICOS
    return plt.subplots(figsize=(largura, altura))


def figura_barras(rotulos, valores, titulo_valor, cores=None):
    fig, ax = _figura(8, max(1.6, 0.42 * len(rotulos) + 0.6))
    y = np.arange(len(rotulos))[::-1]
    ax.barh(y, valores, height=0.55, color=cores if cores is not None else painel.AZUL)
    ax.set_yticks(y, labels=rotulos, color=TINTA, fontsize=8.5)
    ax.set_xlabel(titulo_valor, color=TINTA_2, fontsize=8.5)
    maximo = max(valores) if len(valores) and max(valores) > 0 else 1
    for yi, v in zip(y, valores):
        ax.text(v + maximo * 0.01, yi, _br(v, 0), va="center", ha="left", fontsize=8, color=TINTA)
    ax.set_xlim(0, maximo * 1.12)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _br(v, 0)))
    _eixos(ax, "x")
    return fig


def figura_histograma(faixas, pesos):
    fig, ax = _figura(8, 2.8)
    larg = (faixas["fim"] - faixas["inicio"]).to_numpy()
    ax.bar(faixas["inicio"], faixas["segmentos"], width=larg * 0.92, align="edge", color=painel.AZUL)
    ax.set_xlabel(f"UPS no período (pesos {pesos['sem_vitima']}, {pesos['com_vitima']} e {pesos['com_obito']})",
                  color=TINTA_2, fontsize=8.5)
    ax.set_ylabel("Segmentos", color=TINTA_2, fontsize=8.5)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _br(v, 0)))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _br(v, 0)))
    if faixas["faixa"].iloc[-1].endswith("ou mais"):
        ultima = faixas.iloc[-1]
        ax.annotate(ultima["faixa"], (ultima["inicio"] + larg[-1] / 2, ultima["segmentos"]), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=7.5, color=TINTA_2)
    _eixos(ax, "y")
    return fig


# --- Mapa: pontos em Web Mercator (EPSG:3857) sobre o mapa do OpenStreetMap --------------------------------
RAIO_TERRA = 6378137.0
METADE_MUNDO = np.pi * RAIO_TERRA          # 20.037.508 m: o mundo vai de -METADE_MUNDO a +METADE_MUNDO
URL_FUNDO = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
AGENTE = f"{SIGLA_SISTEMA}-Rodoviario/{VERSAO} (relatorio PDF)"   # a política de uso dos tiles pede um nome próprio
ALVO_PX = 1000           # largura do fundo em pixels dos tiles (o mapa sai com cerca de 16 cm)
LIMITE_TILES = 30        # teto de tiles por mapa
LIMITE_CACHE = 400       # tiles guardados na memória do servidor (relatórios seguidos da mesma área não baixam de novo)
TEMPO_TILE = 5.0         # segundos por tile
CREDITO_FUNDO = "© colaboradores do OpenStreetMap"
_CACHE_TILES: dict = {}
_TRAVA_CACHE = threading.Lock()      # várias sessões podem gerar relatórios ao mesmo tempo


def projetar_mercator(lon, lat):
    """Longitude e latitude (graus) em metros da projeção Web Mercator, a dos mapas na web."""
    lon = np.asarray(lon, dtype=float)
    lat = np.clip(np.asarray(lat, dtype=float), -85.05112878, 85.05112878)
    return RAIO_TERRA * np.radians(lon), RAIO_TERRA * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def _latitude(y):
    return float(np.degrees(2 * np.arctan(np.exp(y / RAIO_TERRA)) - np.pi / 2))


def _enquadrar(x, y, razao, folga=0.05, minimo=3000.0):
    """Retângulo (em metros) com todos os pontos, uma folga e a proporção largura/altura da figura."""
    x0, x1, y0, y1 = float(np.min(x)), float(np.max(x)), float(np.min(y)), float(np.max(y))
    w, h = max(x1 - x0, minimo) * (1 + 2 * folga), max(y1 - y0, minimo) * (1 + 2 * folga)
    if w / h < razao:
        w = h * razao
    else:
        h = w / razao
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2


def _tiles_da_area(x0, x1, y0, y1, alvo_px=ALVO_PX, limite=LIMITE_TILES):
    """Zoom e faixa de tiles (x0, x1, y0, y1) que cobrem a área com cerca de ``alvo_px`` de largura, sem passar
    do teto de tiles."""
    z = int(np.clip(np.floor(np.log2(alvo_px * 2 * METADE_MUNDO / (256 * max(x1 - x0, 1.0)))), 1, 17))
    while True:
        lado, n = 2 * METADE_MUNDO / 2 ** z, 2 ** z
        tx0, tx1 = (int(np.clip((v + METADE_MUNDO) // lado, 0, n - 1)) for v in (x0, x1))
        ty0, ty1 = (int(np.clip((METADE_MUNDO - v) // lado, 0, n - 1)) for v in (y1, y0))
        if (tx1 - tx0 + 1) * (ty1 - ty0 + 1) <= limite or z == 1:
            return z, tx0, tx1, ty0, ty1
        z -= 1


def _buscar_tile(z, x, y) -> bytes:
    pedido = urllib.request.Request(URL_FUNDO.format(z=z, x=x, y=y), headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pedido, timeout=TEMPO_TILE) as resposta:
        return resposta.read()


def _tile(z, x, y) -> bytes:
    chave = (z, x, y)
    dados = _CACHE_TILES.get(chave)
    if dados is None:
        dados = _buscar_tile(z, x, y)
        with _TRAVA_CACHE:
            if len(_CACHE_TILES) >= LIMITE_CACHE:
                _CACHE_TILES.pop(next(iter(_CACHE_TILES)))
            _CACHE_TILES[chave] = dados
    return dados


def mapa_de_fundo(x0, x1, y0, y1):
    """Mapa do OpenStreetMap recortado na área (metros Web Mercator), em cinza claro para as cores dos
    segmentos se destacarem. Retorna None sem internet, se algum tile falhar ou com SISEGC_MAPA_DE_FUNDO=0."""
    if os.environ.get("SISEGC_MAPA_DE_FUNDO", "1") == "0":
        return None
    from PIL import Image, ImageOps

    z, tx0, tx1, ty0, ty1 = _tiles_da_area(x0, x1, y0, y1)
    pedidos = [(z, tx, ty) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]
    try:
        dados = [_tile(*pedidos[0])]                     # sem internet, desiste já no primeiro
        with ThreadPoolExecutor(max_workers=2) as ex:    # poucas conexões, como pede a política de uso
            dados += list(ex.map(lambda p: _tile(*p), pedidos[1:]))
        mosaico = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256), "white")
        for (_, tx, ty), d in zip(pedidos, dados):
            mosaico.paste(Image.open(io.BytesIO(d)).convert("RGB"), ((tx - tx0) * 256, (ty - ty0) * 256))
    except Exception:
        return None
    px = 256 / (2 * METADE_MUNDO / 2 ** z)              # pixels por metro
    ox, oy = tx0 * 256 / px - METADE_MUNDO, METADE_MUNDO - ty0 * 256 / px
    recorte = mosaico.crop((round((x0 - ox) * px), round((oy - y1) * px), round((x1 - ox) * px),
                            round((oy - y0) * px)))
    claro = ImageOps.grayscale(recorte).point(lambda v: 255 - round((255 - v) * 0.6))
    return np.asarray(claro.convert("RGB"))


def figura_mapa(df_proc, conv):
    """Mapa dos segmentos críticos, coloridos pelo número de trilhas que os apontam, sobre o mapa do
    OpenStreetMap em cinza claro; os demais segmentos analisados ficam em cinza. Sem internet, sai sem o
    fundo (só o desenho da malha). Retorna (figura ou None, se o fundo entrou)."""
    seg = df_proc.dropna(subset=["latitude", "longitude"])
    crit = conv.dropna(subset=["latitude", "longitude"])
    if seg.empty:
        return None, False
    largura, altura = 8, 5.6
    fig, ax = _figura(largura, altura)
    fig.subplots_adjust(0, 0, 1, 1)
    sx, sy = projetar_mercator(seg["longitude"], seg["latitude"])
    cx, cy = projetar_mercator(crit["longitude"], crit["latitude"])
    x0, x1, y0, y1 = _enquadrar(sx, sy, largura / altura)
    fundo = mapa_de_fundo(x0, x1, y0, y1)
    if fundo is not None:
        ax.imshow(fundo, extent=(x0, x1, y0, y1), interpolation="bilinear", zorder=0)
    ax.scatter(sx, sy, s=0.6 if len(seg) > 20000 else (2 if len(seg) > 2000 else 5),
               c=CINZA_MALHA if fundo is None else CINZA_MALHA_FUNDO, linewidths=0, rasterized=True, zorder=1)
    for n in sorted(crit["n_trilhas"].unique()):
        m = (crit["n_trilhas"] == n).to_numpy()
        ax.scatter(cx[m], cy[m], s=8 + 8 * n, c=painel.CORES_N_TRILHAS[int(n)], edgecolors=painel.CONTORNO,
                   linewidths=0.45, label=NOMES_N[int(n)], zorder=2 + n)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ax.spines.values():
        lado.set_visible(fundo is not None)
        lado.set_color(GRADE)
    if len(crit):
        leg = ax.legend(loc="lower right", bbox_to_anchor=(0.99, 0.05), fontsize=8, frameon=True, framealpha=0.92,
                        edgecolor=GRADE, title="Segmentos críticos", title_fontsize=8.5)
        leg.get_title().set_color(TINTA)
        leg.set_zorder(12)
    _escala(ax)
    _nomes_vias(ax, crit, cx, cy)
    if fundo is not None:
        ax.text(0.995, 0.006, CREDITO_FUNDO, transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5,
                color=TINTA_2, zorder=12, bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none", "pad": 1.5})
    return fig, fundo is not None


def _contorno_branco(largura=2.5):
    from matplotlib import patheffects

    return [patheffects.withStroke(linewidth=largura, foreground="white")]


def _nomes_vias(ax, crit, x, y, n=6):
    """Nome das vias com mais segmentos críticos, junto do crítico de maior UPS de cada uma."""
    if "via" not in crit or crit.empty:
        return
    crit = crit.assign(_x=x, _y=y)
    for via in crit["via"].value_counts().head(n).index:
        ponto = crit[crit["via"] == via].sort_values("UPS", ascending=False).iloc[0]
        ax.annotate(str(via)[:28], (ponto["_x"], ponto["_y"]), xytext=(6, 6), textcoords="offset points",
                    fontsize=7.5, color=TINTA, zorder=10, path_effects=_contorno_branco())


def _escala(ax):
    """Barra de escala no canto inferior esquerdo, medida na latitude do centro do mapa (na Web Mercator a
    escala muda com a latitude; a barra vale para o centro)."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    fator = np.cos(np.radians(_latitude((y0 + y1) / 2)))    # metros no terreno por metro do mapa
    alvo = (x1 - x0) * fator / 1000 / 5
    passo = min((0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500), key=lambda v: abs(v - alvo))
    comprimento = passo * 1000 / fator
    xa, ya = x0 + (x1 - x0) * 0.03, y0 + (y1 - y0) * 0.04
    ax.plot([xa, xa + comprimento], [ya, ya], color=TINTA_2, linewidth=2, solid_capstyle="butt", zorder=11,
            path_effects=_contorno_branco(4))
    ax.text(xa + comprimento / 2, ya + (y1 - y0) * 0.015, f"{passo:g} km" if passo >= 1 else "500 m",
            ha="center", va="bottom", fontsize=7.5, color=TINTA_2, zorder=11, path_effects=_contorno_branco())


# ---------------------------------------------------------------------------------------------------
# Textos
# ---------------------------------------------------------------------------------------------------
def _texto_mapa(conv, com_fundo):
    """Legenda do mapa por extenso: as cores que aparecem e de onde vem o fundo."""
    quantas = {1: "uma trilha", 2: "duas trilhas", 3: "as três trilhas"}
    niveis = sorted(int(n) for n in conv["n_trilhas"].dropna().unique()) if len(conv) else []
    if niveis:
        cores = "; ".join(f"**{painel.NOMES_CORES_N_TRILHAS[n]}**, {quantas[n]}" for n in niveis)
        texto = (f"Os segmentos críticos estão coloridos pelo número de trilhas que os apontam ({cores}); em cinza, "
                 "os demais segmentos analisados.")
    else:
        texto = "Nenhum segmento crítico; em cinza, os segmentos analisados."
    if com_fundo:
        return texto + f" Mapa de fundo: {CREDITO_FUNDO}."
    return texto + (" O mapa de fundo (OpenStreetMap) não pôde ser carregado ao gerar o relatório; o desenho em "
                    "cinza mostra a malha analisada.")


def _fontes(df_proc):
    """Fontes da segmentação automática (SNV, VMD e OpenStreetMap), quando os dados vierem dela."""
    if "codigo_snv" not in df_proc:
        return None
    resumo = df_proc.attrs.get("resumo", {})
    partes = [f"Segmentos cortados na malha do SNV do DNIT (versão {resumo.get('versao_snv', 'não informada')})."]
    vmd = resumo.get("vmd")
    if vmd:
        partes.append(f"Volume de tráfego (VMD) da modelagem do PNCT/DNIT ({vmd.get('ano') or 'ano não informado'}, "
                      f"SNV {vmd.get('versao_snv')}).")
    if "fonte" in df_proc and (df_proc["fonte"] == "OpenStreetMap").any():
        partes.append("Vias fora do SNV: © colaboradores do OpenStreetMap, dados sob a licença ODbL "
                      "(openstreetmap.org/copyright).")
    return "Fontes: " + " ".join(partes)


def _texto_metodologia(resultados, pesos):
    from models.trilha3_bayes import CRITERIOS, METODOS
    from utils.constantes import VARIAVEIS_ANALISE

    def vc(a):
        sinal = "−0,5/E (Manual)" if a.get("sinal_correcao", -1) < 0 else "+1/(2E) (literatura clássica)"
        return (f"compara o índice observado de cada segmento com um limite estatístico de referência "
                f"(nível de confiança de {_br(a.get('nivel_confianca', 95), 1)}%, k = {_br(a.get('k', 1.645), 3)}, "
                f"termo de correção de continuidade {sinal}).")

    def kde(a):
        p = float(a.get("percentil", 75))
        var_nome = VARIAVEIS_ANALISE.get(a.get("variavel", "severidade"), "Severidade (UPS)").lower()
        corte = "no quartil superior" if p == 75 else f"acima do percentil {_br(p, 0)}"
        criterio = (f"Classificam-se como críticos os segmentos cujos registros de sinistros encontram-se {corte} "
                    "da distribuição de densidades de kernel, conforme especificado no Manual.")
        if a.get("coincidencia") is not None:
            criterio += (f" Na métrica de verificação espacial do Manual, o quartil superior da densidade coincide com "
                         f"o quartil superior da soma na célula em {_br(a['coincidencia'], 1)}% dos sinistros.")
        return (f"estima a concentração espacial contínua por {var_nome} (largura de banda de "
                f"{_br(a.get('bandwidth', 1000), 0)} m e grade com células de "
                f"{_br(a.get('cell_size', 500), 0)} m). {criterio}")

    def bayes(a):
        var_nome = VARIAVEIS_ANALISE.get(a.get("variavel", "severidade"), "Severidade (UPS)")
        return ("estima o valor esperado de sinistros (Nesperado) combinando a contagem observada no segmento "
                "(Nobservado) com o valor previsto por um modelo de referência (Nprevisto) ponderado pelo volume "
                "de tráfego e pela extensão, mitigando o viés de regressão à média. "
                f"Variável analisada: {var_nome}. Método: {METODOS.get(a.get('metodo'), '')}. "
                f"Critério: {CRITERIOS.get(a.get('criterio'), '')}.")

    texto = {"vc": vc, "kde": kde, "bayes": bayes}
    partes = [("Os procedimentos analíticos seguem as diretrizes do Manual de Identificação de Segmentos Críticos "
               "Rodoviários (2026). Nas análises ponderadas por severidade, adota-se a Unidade Padrão de Severidade "
               f"(UPS) com pesos {pesos.get('sem_vitima', 1)} (sinistros sem vítima), "
               f"{pesos.get('com_vitima', 4)} (com vítima ferida) e {pesos.get('com_obito', 28)} (com óbito).")]
    for chave in ORDEM_TRILHAS:
        if chave in resultados:
            partes.append(f"**{rotulo_trilha(chave)}**: {texto[chave](resultados[chave].attrs)}")
    partes.append("**Convergência metodológica**: contabiliza o número de trilhas em que cada segmento é classificado "
                  "como crítico. Por integrarem abordagens complementares (controle estatístico por extensão, "
                  "agrupamento espacial por densidade de kernel e modelagem preditiva com correção de regressão à "
                  "média), os segmentos identificados simultaneamente por múltiplas trilhas constituem as indicações "
                  "técnicas mais consistentes para inspeção diagnóstica.")
    return partes


def _parametros(resultados, pesos, contexto, com_dados=True):
    """Tabela dos parâmetros adotados. Na primeira página, a fonte dos dados já aparece logo abaixo do título
    (``com_dados=False``)."""
    from models.trilha1_valor_critico import METODOS as METODOS_VC
    from models.trilha3_bayes import CRITERIOS, METODOS
    from utils.constantes import VARIAVEIS_ANALISE

    linhas = []
    if com_dados and contexto.get("descricao_fonte"):
        linhas.append(("Dados", contexto["descricao_fonte"].rstrip(".")))
    seg = contexto.get("segmentacao")
    if seg:
        linhas.append(("Segmentação", f"segmentos de cerca de {_br(seg['comprimento'], 1)} km"
                       + ("; por sentido da via" if seg.get("por_sentido") else "")
                       + ("; com ruas residenciais" if seg.get("residenciais") else "")))
        if seg.get("vmd") is False:
            linhas.append(("Volume de tráfego (VMD)", "não usado, por opção do usuário: a Trilha 3 e os métodos de "
                           "taxa da Trilha 1 não rodam"))
        elif seg.get("vmd"):
            linhas.append(("Volume de tráfego (VMD)", "usado (modelagem do PNCT/DNIT)"))
    linhas.append(("Pesos da UPS", f"{pesos.get('sem_vitima', 1)} (sem vítima), {pesos.get('com_vitima', 4)} "
                   f"(com vítima), {pesos.get('com_obito', 28)} (com óbito)"))
    if "vc" in resultados:
        a = resultados["vc"].attrs
        linhas.append(("Trilha 1: método", METODOS_VC.get(a.get("metodo"), str(a.get("metodo")))))
        linhas.append(("Trilha 1: confiança", f"{_br(a.get('nivel_confianca', 95), 1)}% (k = {_br(a.get('k', 0), 3)})"
                       f"; correção {'−0,5/E' if a.get('sinal_correcao', -1) < 0 else '+1/(2E)'}"))
        if contexto.get("excluir_zeros") is not None:
            linhas.append(("Trilha 1: sem sinistros", "excluídos do cálculo da média" if contexto["excluir_zeros"]
                           else "incluídos no cálculo da média (padrão do Manual)"))
    if "kde" in resultados:
        a = resultados["kde"].attrs
        var_kde = VARIAVEIS_ANALISE.get(a.get("variavel", "severidade"), "Severidade (UPS)")
        linhas.append(("Trilha 2", f"{var_kde}; banda de {_br(a.get('bandwidth', 1000), 0)} m, células de "
                       f"{_br(a.get('cell_size', 500), 0)} m, corte no percentil {_br(a.get('percentil', 75), 0)}"))
    if "bayes" in resultados:
        a = resultados["bayes"].attrs
        var_eb = VARIAVEIS_ANALISE.get(a.get("variavel", "severidade"), "Severidade (UPS)")
        criterio = CRITERIOS.get(a.get("criterio"), "")
        if a.get("z"):
            criterio += f" (z = {_br(a['z'], 3)})"
        linhas.append(("Trilha 3: variável", var_eb))
        linhas.append(("Trilha 3: método", METODOS.get(a.get("metodo"), "")))
        linhas.append(("Trilha 3: critério", criterio))
    linhas.append(("Sistema", f"{SIGLA_SISTEMA}, versão {VERSAO}"))
    return pd.DataFrame(linhas, columns=["Parâmetro", "Valor"])


def _limitacoes(df_proc, contexto):
    resumo = df_proc.attrs.get("resumo", {})
    itens = ["Os resultados dependem da precisão e da completude das bases de entrada: ocorrências subnotificadas, "
             "com inconsistência de quilometragem ou desprovidas de coordenadas geográficas não são computadas.",
             "A ocorrência de sinistros está sujeita a flutuações estocásticas entre períodos (regressão à média). "
             "As Trilhas 1 e 2 operam diretamente sobre as contagens e severidades observadas; a Trilha 3 corrige o "
             "efeito de regressão à média mediante função de desempenho de segurança dependente do VMD."]
    vmd = resumo.get("vmd")
    if resumo.get("vmd_desativado"):
        itens.append("O volume de tráfego (VMD) não foi usado nesta análise, por opção do usuário: a Trilha 3 e os "
                     "métodos de taxa da Trilha 1, que dependem dele, não foram executados.")
    if vmd:
        ano_vmd = vmd.get("ano") or "ano não informado"
        itens.append(f"O volume médio diário (VMD) provém da modelagem nacional do PNCT/DNIT ({ano_vmd}), "
                     "que constitui a base pública nacional mais atualizada disponível até o momento. Por se tratar "
                     "de estimativa modelada em ano-base específico, eventuais variações recentes de tráfego devem ser "
                     "ponderadas na análise técnica; segmentos sem cobertura de VMD não são avaliados na Trilha 3 nem "
                     "nos métodos de taxa da Trilha 1.")
    if "fonte" in df_proc and (df_proc["fonte"] == "OpenStreetMap").any():
        itens.append("As vias provenientes do OpenStreetMap não dispõem de dados públicos de VMD, não sendo avaliadas "
                     "pela Trilha 3 nem pelos métodos de taxa da Trilha 1. A geometria e a classificação viária "
                     "decorrem de mapeamento colaborativo.")
    if contexto.get("prf"):
        itens.append("A base da Polícia Rodoviária Federal (PRF) abrange exclusivamente a malha rodoviária federal, e "
                     "o exercício corrente pode apresentar consolidação parcial. Em registros anteriores a 2025, "
                     "observa-se concentração de coordenadas em marcos quilométricos inteiros, sendo cada registro "
                     "associado ao segmento correspondente da BR informada até o limite de 500 m.")
    ext = pd.to_numeric(df_proc.get("extensao_trecho"), errors="coerce") if "extensao_trecho" in df_proc else None
    if ext is not None and ext.notna().any() and ext.median() < 0.5:
        itens.append("Em malhas com elevada proporção de segmentos curtos, a ocorrência de um único sinistro eleva "
                     "substancialmente o índice por quilômetro na Trilha 1. Recomenda-se priorizar a análise conjunta "
                     "de convergência entre as trilhas.")
    itens.append("A identificação e o ordenamento de segmentos críticos constituem a etapa inicial de triagem "
                 "epidemiológica da malha (Capítulo 4 do Manual), não substituindo as etapas subsequentes de "
                 "investigação detalhada, inspeção de campo e análise econômica para priorização de projetos.")
    return itens


def _ficha(pdf, posicao, linha, det, unidade_vc):
    """Ficha de um segmento prioritário: via, trilhas, sinistros e as métricas de cada trilha."""
    via = linha.get("rodovia")
    titulo = f"{posicao}. {via}" if isinstance(via, str) and via else f"{posicao}. Segmento {linha['segmento_id']}"
    partes_trilhas = []
    for c in ORDEM_TRILHAS:
        d = det.get(c)
        if not d:
            continue
        marca = "crítico" if d["critico"] else "não crítico"
        if c == "vc":
            partes_trilhas.append(f"**Trilha 1** ({marca}): índice {_br(d['indice'], 1)} × valor crítico "
                                  f"{_br(d['valor_critico'], 1)} {unidade_vc}")
        elif c == "kde":
            q = d.get("quartil")
            q = f"{int(q)}º quartil da densidade" if q is not None and not pd.isna(q) else "sem densidade"
            rel = d.get("relativa")
            rel = f" ({_br(rel, 0)}% do máximo)" if rel is not None and not pd.isna(rel) else ""
            partes_trilhas.append(f"**Trilha 2** ({marca}): {q}{rel}")
        elif c == "bayes":
            partes_trilhas.append(f"**Trilha 3** ({marca}): Nesperado {_br(d['esperada'], 1)} × Nprevisto "
                                  f"{_br(d['prevista'], 1)}")
    sin = (f"{_br(linha.get('total_sinistros', 0), 0)} sinistros ({_br(linha.get('com_obito', 0), 0)} com óbito, "
           f"{_br(linha.get('com_vitima', 0), 0)} com vítima, {_br(linha.get('sem_vitima', 0), 0)} sem vítima)")
    vmd = linha.get("volume_trafego")
    ext = linha.get("extensao_trecho")
    dados = [f"ID {linha['segmento_id']} · crítico n{'as' if linha['n_trilhas'] > 1 else 'a'} {linha['trilhas']}",
             f"UPS {_br(linha.get('UPS', 0), 0)} · {sin}",
             (f"Extensão {_br(ext, 2)} km" if ext is not None and not pd.isna(ext) else "Extensão não informada")
             + (f" · VMD {_br(vmd, 0)} veíc./dia" if vmd is not None and not pd.isna(vmd) else " · sem VMD")]
    lat, lon = linha.get("latitude"), linha.get("longitude")
    pdf.espaco(22 + 4.4 * len(partes_trilhas))
    y0 = pdf.get_y()
    pdf.set_draw_color(*COR_AZUL)
    pdf.set_fill_color(*COR_AZUL)
    pdf.rect(10, y0, 1.6, 4, "F")
    pdf.set_xy(14, y0 - 0.5)
    pdf.set_font(pdf.fonte, "B", 10.5)
    pdf.set_text_color(*COR_AZUL)
    pdf.cell(0, 5, titulo[:95], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf.fonte, "", 8.8)
    pdf.set_text_color(*COR_TEXTO)
    for t in dados:
        pdf.set_x(14)
        pdf.cell(0, 4.4, t, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for t in partes_trilhas:
        pdf.set_x(14)
        pdf.multi_cell(0, 4.4, t, markdown=True, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if lat is not None and lon is not None and not (pd.isna(lat) or pd.isna(lon)):
        pdf.set_x(14)
        pdf.set_text_color(*COR_AZUL)
        url = f"https://www.openstreetmap.org/?mlat={lat:.5f}&mlon={lon:.5f}#map=17/{lat:.5f}/{lon:.5f}"
        pdf.cell(0, 4.4, f"Coordenada {_br(lat, 5)}, {_br(lon, 5)} · ver no mapa", link=url,
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(220, 220, 220)
    pdf.set_line_width(0.2)
    pdf.line(14, pdf.get_y() + 1.5, 200, pdf.get_y() + 1.5)
    pdf.ln(4)


# ---------------------------------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------------------------------
def gerar_pdf_completo(df_proc, resultados, logo_path=None, contexto: dict | None = None):
    """Gera o PDF. ``df_proc`` é a tabela já processada (com a coluna UPS); ``contexto`` traz a descrição da
    fonte, as mensagens sobre os dados e as opções da análise (tudo opcional)."""
    contexto = contexto or {}
    pdf = PDFRelatorio(logo_path)
    pdf.add_page()
    pesos = df_proc.attrs.get("pesos_ups", {"sem_vitima": 1, "com_vitima": 4, "com_obito": 28})
    trilhas = [c for c in ORDEM_TRILHAS if c in resultados]
    conv = painel.convergencia(resultados, df_proc, trilhas)
    ind = painel.indicadores(df_proc, resultados, conv)

    pdf.set_font(pdf.fonte, "B", 20)
    pdf.set_text_color(*COR_AZUL)
    pdf.cell(0, 10, "Relatório executivo", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf.fonte, "", 11)
    pdf.set_text_color(*COR_ROXO)
    pdf.cell(0, 6, "Identificação de segmentos críticos de sinistros de trânsito", new_x=XPos.LMARGIN,
             new_y=YPos.NEXT)
    if contexto.get("descricao_fonte"):
        pdf.set_font(pdf.fonte, "", 9.5)
        pdf.set_text_color(*COR_TEXTO)
        pdf.multi_cell(0, 5, contexto["descricao_fonte"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # 1. Números principais
    pdf.capitulo_titulo("1. Números principais")
    caixas = [(_br(ind["segmentos"], 0), f"segmentos analisados ({_br(ind['km'], 0)} km)"),
              (_br(ind["sinistros"], 0), f"sinistros, {_br(ind['com_obito'], 0)} com óbito"),
              (_br(ind["em_pelo_menos"][1], 0), "segmentos críticos em ao menos uma trilha")]
    for c in trilhas:
        p = ind["por_trilha"][c]
        caixas.append((_br(p["criticos"], 0), f"críticos na {rotulo_trilha(c)}"))
    pdf.indicadores(caixas)
    if len(trilhas) > 1:
        minimo = 2
        parte = ind["parcela"][minimo]
        if parte["segmentos"]:
            nome = "em 2 ou mais trilhas" if len(trilhas) > 2 else "nas duas trilhas"
            pdf.destaque_box(f"Os {_br(parte['segmentos'], 0)} segmentos críticos {nome} são {_pct(parte['km'])} da "
                             f"extensão analisada e reúnem {_pct(parte['sinistros'])} dos sinistros, "
                             f"{_pct(parte['com_obito'])} dos sinistros com óbito e {_pct(parte['ups'])} da UPS.",
                             tipo="conclusao")
        else:
            pdf.texto_corpo("Nenhum segmento foi apontado por mais de uma trilha. Isso pode acontecer porque cada "
                            "método mede um aspecto diferente; veja os resultados de cada trilha.")
    erros = contexto.get("erros") or {}
    for c, msg in erros.items():
        pdf.texto_corpo(f"**{rotulo_trilha(c)}** não rodou: {msg}", tamanho=9.5)
    fontes = _fontes(df_proc)
    if fontes:
        pdf.texto_corpo(fontes, tamanho=9)
    pdf.subtitulo("Parâmetros adotados")
    pdf.adicionar_tabela(_parametros(resultados, pesos, contexto, com_dados=False), [50, 140], tamanho=8.5,
                         alinhar=["L", "L"])

    # 2. Mapa
    fig, com_fundo = figura_mapa(df_proc, conv)
    if fig is not None:
        pdf.capitulo_titulo("2. Mapa dos segmentos críticos", minimo=145)
        pdf.texto_corpo(_texto_mapa(conv, com_fundo), tamanho=9.5)
        pdf.adicionar_grafico(fig, largura=165)
    n = 3 if fig is not None else 2

    # 3. Convergência
    if len(trilhas) > 1:
        comb = painel.combinacoes(conv, trilhas)
        cores = [painel.CORES_N_TRILHAS[int(k)] for k in comb["n_trilhas"]]
        png = png_da_figura(figura_barras(list(comb["combinacao"]), list(comb["segmentos"]), "Segmentos críticos",
                                          cores))
        altura = 150 * png[2] / png[1]                      # o gráfico, em mm, com 150 de largura
        pdf.capitulo_titulo(f"{n}. Convergência entre as trilhas", minimo=altura + 30)   # título, texto e gráfico
        pdf.texto_corpo(f"{_br(ind['em_pelo_menos'][1], 0)} segmentos são críticos em ao menos uma trilha, "
                        f"{_br(ind['em_pelo_menos'][2], 0)} em duas ou mais"
                        + (f" e {_br(ind['em_pelo_menos'][3], 0)} nas três." if len(trilhas) > 2 else ".")
                        + " As cores seguem as do mapa.")
        pdf.adicionar_grafico(png, largura=150)
        n += 1

    # 4. Ordenamento dos segmentos críticos
    if len(conv):
        pdf.capitulo_titulo(f"{n}. Ordenamento dos segmentos críticos", minimo=75)
        pdf.texto_corpo(
            f"Os {min(10, len(conv))} primeiros segmentos do ordenamento por criticidade (maior "
            "convergência entre as trilhas e, em caso de empate, maior UPS). Conforme o Capítulo 4 do Manual, "
            "este ordenamento orienta a inspeção técnica diagnóstica, etapa distinta da priorização econômica "
            "de intervenções.", tamanho=9.5,
        )
        topo = conv.head(10)
        det = painel.detalhes(resultados, topo["segmento_id"])
        unidade = UNIDADE_VC.get(resultados["vc"].attrs.get("metodo"), "") if "vc" in resultados else ""
        for i, (_, linha) in enumerate(topo.iterrows(), start=1):
            _ficha(pdf, i, linha, det.get(str(linha["segmento_id"]), {}), unidade)
        n += 1

    # 5. Distribuição da UPS
    faixas = painel.histograma_ups(df_proc)
    if len(faixas):
        pdf.capitulo_titulo(f"{n}. Distribuição da UPS", minimo=95)
        pdf.texto_corpo(f"Distribuição da UPS nos {_br(ind['com_sinistro'], 0)} segmentos com ao menos um sinistro "
                        "registrado (segmentos sem sinistros apresentam UPS nula e não são classificados como "
                        "críticos). A UPS pondera o total de sinistros do período pelos fatores de severidade.",
                        tamanho=9.5)
        pdf.espaco(60)
        pdf.adicionar_grafico(figura_histograma(faixas, pesos), largura=165)
        n += 1

    # 6. Resultados por trilha
    pdf.capitulo_titulo(f"{n}. Resultados por trilha")
    base_seg = df_proc.drop_duplicates("segmento_id")
    via = base_seg.set_index(base_seg["segmento_id"].astype(str))["rodovia"] if "rodovia" in base_seg else None
    for chave in trilhas:
        res = resultados[chave]
        criticos = res[res["Critico"].astype(bool)]
        pdf.subtitulo(f"{rotulo_trilha(chave)}")
        pdf.texto_corpo(f"{_br(len(criticos), 0)} de {_br(len(res), 0)} segmentos avaliados são críticos"
                        + (". Os 10 primeiros no ordenamento da trilha:" if len(criticos) else "."), tamanho=9.5)
        for av in res.attrs.get("avisos", []):
            if "métodos baseados em taxa" in av:
                pdf.texto_corpo(f"*Nota técnica:* {av}", tamanho=8.8)
        if criticos.empty:
            continue
        top = criticos.head(10)
        if chave == "vc":
            unidade = UNIDADE_VC.get(res.attrs.get("metodo"), "")
            t = pd.DataFrame({"Segmento": top["segmento_id"], f"Índice ({unidade})": top["Indice"].astype(float),
                              "Valor crítico": top["Valor_Critico"].astype(float)})
        elif chave == "bayes":
            t = pd.DataFrame({"Segmento": top["segmento_id"], "Nobservado": top["N_observado"].astype(float),
                              "Nesperado": top["ajustado"].astype(float),
                              "Nprevisto": top["N_previsto"].astype(float)})
        else:
            t = pd.DataFrame({"Segmento": top["segmento_id"], "UPS": top["UPS"].astype(float),
                              "Densidade relativa (%)": top["indice_densidade"].astype(float)})
        if via is not None:
            t.insert(1, "Rodovia ou via", top["segmento_id"].astype(str).map(via).fillna("").to_numpy())
            larguras = [38, 62] + [90 / (t.shape[1] - 2)] * (t.shape[1] - 2)
        else:
            larguras = None
        pdf.adicionar_tabela(t.reset_index(drop=True), larguras)
    n += 1

    # 7. Dados e limitações
    pdf.capitulo_titulo(f"{n}. Dados e limitações")
    msgs = [texto for tipo, texto in contexto.get("mensagens", []) if tipo != "error"]
    if msgs:
        pdf.subtitulo("Características dos dados carregados")
        pdf.itens(msgs)
    pdf.subtitulo("Limitações")
    pdf.itens(_limitacoes(df_proc, contexto))
    n += 1

    # 8. Metodologia (os parâmetros adotados estão na primeira página, no item 1)
    pdf.capitulo_titulo(f"{n}. Metodologia")
    for paragrafo in _texto_metodologia(resultados, pesos):
        pdf.texto_corpo(paragrafo, tamanho=9.5)
    pdf.texto_corpo("Os parâmetros adotados nesta análise estão no item 1.", tamanho=9.5)

    # Anexo
    if len(conv):
        pdf.capitulo_titulo("Anexo: ordenamento dos segmentos críticos")
        mais = len(conv) > LIMITE_ANEXO
        pdf.texto_corpo(f"{_br(len(conv), 0)} segmentos classificados como críticos em ao menos uma trilha"
                        + (f"; apresentam-se abaixo os {LIMITE_ANEXO} primeiros. A relação completa consta na "
                           "planilha de resultados." if mais else "."), tamanho=9.5)
        anexo = conv.head(LIMITE_ANEXO)
        t = pd.DataFrame({"Nº": range(1, len(anexo) + 1), "Segmento": anexo["segmento_id"],
                          "Rodovia ou via": anexo["rodovia"] if "rodovia" in anexo else "",
                          "Crítico nas": anexo["trilhas"].str.replace("Só a ", "", regex=False),
                          "UPS": anexo["UPS"].astype(float),
                          "Sinistros": anexo["total_sinistros"].astype(float)})
        pdf.adicionar_tabela(t, [10, 36, 66, 36, 20, 22], tamanho=7.5)

    pdf.destaque_box("Nota de responsabilidade: relatório gerado automaticamente a partir dos dados inseridos. "
                     "Não substitui a análise técnica nem os estudos de engenharia necessários às intervenções.")
    return bytes(pdf.output())
