"""Sistema de Identificação de Segmentos Críticos Rodoviários (SISegC Rodoviário): interface Streamlit."""
import hashlib
import io
import json
import os
import traceback
import zipfile

import streamlit as st

from utils.ambiente import instrucoes_instalacao, python_em_uso, verificar_ambiente
from utils.constantes import NOME_SISTEMA, SIGLA_SISTEMA, VERSAO

BASE = os.path.dirname(os.path.abspath(__file__))
ICONE = os.path.join(BASE, "assets", "icone.png")
LOGO = os.path.join(BASE, "assets", "logo_horizontal.png")
# Manual de Utilização: o app serve a pasta static/ (enableStaticServing), e o navegador abre o PDF numa nova aba
MANUAL = os.path.join(BASE, "static", "manual", "manual-de-utilizacao-sisegc.pdf")
URL_MANUAL = "./app/static/manual/manual-de-utilizacao-sisegc.pdf"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title=SIGLA_SISTEMA,
    page_icon=ICONE if os.path.exists(ICONE) else "🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- 1a. AMBIENTE: versões erradas viram uma mensagem com a solução, não um traceback ---
ERROS_AMBIENTE, AVISOS_AMBIENTE = verificar_ambiente()
if ERROS_AMBIENTE:
    st.error(f"O ambiente Python em uso não tem as bibliotecas da versão {VERSAO}:\n\n"
             + "\n".join(f"- {e}" for e in ERROS_AMBIENTE))
    st.markdown("Crie um ambiente só para esta versão (cada versão tem as suas bibliotecas) e abra o app por ele. "
                "Na pasta do projeto:")
    st.code(instrucoes_instalacao(), language="bash")
    st.caption(f"Python em uso agora: `{python_em_uso()}`")
    st.stop()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from models.trilha1_valor_critico import METODOS as METODOS_VC  # noqa: E402
from models.trilha1_valor_critico import aplicar_valor_critico  # noqa: E402
from models.trilha2_kernel import aplicar_kernel  # noqa: E402
from models.trilha3_bayes import CRITERIO_PADRAO, CRITERIOS, aplicar_bayes  # noqa: E402
from models.trilha3_bayes import METODOS as METODOS_EB  # noqa: E402
from utils import dados_publicos as dp  # noqa: E402
from utils import painel  # noqa: E402
from utils.constantes import (  # noqa: E402
    COLUNAS_SINISTROS,
    ORDEM_TRILHAS,
    PESOS_UPS_PADRAO,
    VARIAVEIS_ANALISE,
    k_por_nivel,
    rotulo_trilha,
)
from utils.entrada import ErroEntrada, adaptar_planilha, ler_arquivo  # noqa: E402
from utils.mapas import mapa_convergencia, mapa_criticos, mapa_kde  # noqa: E402
from utils.modelos import modelo_segmentos, modelo_sinistros  # noqa: E402
from utils.osm import ATRIBUICAO  # noqa: E402
from utils.preprocessamento import preparar_dados  # noqa: E402
from utils.relatorio import gerar_pdf_completo  # noqa: E402
from utils.segmentacao import (  # noqa: E402
    COMPRIMENTO_PADRAO,
    LIMITES_COMPRIMENTO,
    LONGE_DAS_VIAS,
    ler_arquivos_sinistros,
    ler_snv_enviado,
    preparar_snv,
    retangulo,
    segmentar,
)
from utils.tabelas import tabela_resultado, tabela_segmentos  # noqa: E402
from utils.trafego import ler_vmd_pnct  # noqa: E402

for _aviso in AVISOS_AMBIENTE:
    st.warning(_aviso)

# --- 2. IDENTIDADE VISUAL (a fonte Roboto é servida pelo próprio app; ver .streamlit/config.toml) ---
st.markdown("""
    <style>
        h1 { color: #0988C3 !important; font-weight: 700; border-bottom: 4px solid #FFC900;
             padding-bottom: 10px; margin-bottom: 20px; }
        h2, h3, h4 { color: #64609A; }
        @media (prefers-color-scheme: dark) { h2, h3, h4 { color: #9E9AC8; } }
        div.stButton > button { border-radius: 8px; font-weight: bold; }
        [data-testid="stSidebar"] { border-right: 1px solid #E0E0E0; }
    </style>
""", unsafe_allow_html=True)

ESTADO_INICIAL = {"dados": None, "avisos_entrada": [], "erro_entrada": None, "arquivo_id": None, "uploader_key": 0,
                  "resultados": {}, "erros": {}, "avisos": {}, "df_proc": None, "assinatura": None,
                  "mapas": {}, "msgs_segmentacao": None,
                  "auto_chave": None, "fonte": None, "descricao_fonte": None, "tabelas": {}, "exemplo": None,
                  "guia": False}
for chave, valor in ESTADO_INICIAL.items():
    st.session_state.setdefault(chave, valor)


def limpar_resultados():
    for chave in ("resultados", "erros", "avisos"):
        st.session_state[chave] = {}
    st.session_state.update(df_proc=None, assinatura=None, mapas={}, tabelas={},
                            _memo={})


def memo(nome: str, chave, calcular):
    """Último resultado de cada cálculo do painel, na sessão: as abas são montadas a cada interação."""
    caixa = st.session_state.setdefault("_memo", {})
    if nome not in caixa or caixa[nome][0] != chave:
        caixa[nome] = (chave, calcular())
    return caixa[nome][1]


def assinatura(dados: pd.DataFrame, opcoes: dict) -> str:
    """Identifica dados + opções. O hash dos dados é calculado uma vez por tabela (bases de 1 milhão de
    segmentos levariam quase 1 s a cada clique)."""
    if st.session_state.get("_hash_id") != id(dados):
        st.session_state["_hash_dados"] = hashlib.sha1(
            pd.util.hash_pandas_object(dados, index=False).to_numpy().tobytes()).hexdigest()
        st.session_state["_hash_id"] = id(dados)
    h = hashlib.sha1(st.session_state["_hash_dados"].encode())
    h.update(json.dumps(opcoes, sort_keys=True).encode())
    return h.hexdigest()


LIMITE_LINHAS_TABELA = 20_000


def mostrar_tabela(df: pd.DataFrame, total: int | None = None) -> None:
    """Tabelas muito grandes pesam no navegador: mostra as primeiras linhas (as mais críticas, nos resultados)."""
    total = len(df) if total is None else total
    if total > LIMITE_LINHAS_TABELA:
        st.caption(f"Mostrando {LIMITE_LINHAS_TABELA:,} de {total:,} linhas; a planilha para baixar tem todas."
                   .replace(",", "."))
        df = df.head(LIMITE_LINHAS_TABELA)
    df = df.copy()
    df.attrs = {}        # os attrs (resumo da segmentação) iriam para o navegador, e um NaN neles quebra a tabela
    st.dataframe(df, width="stretch", hide_index=True)


@st.cache_data(show_spinner=False)
def modelo(tipo: str, preenchido: bool) -> bytes:
    """Planilhas-modelo (``utils/modelos.py``), geradas uma vez por servidor."""
    return (modelo_segmentos if tipo == "segmentos" else modelo_sinistros)(preenchido)


def botoes_modelo(tipo: str) -> None:
    """Os dois botões das planilhas-modelo, um embaixo do outro."""
    st.download_button("📥 Modelo Preenchido", data=modelo(tipo, True), file_name=f"modelo_{tipo}_preenchido.xlsx",
                       mime=MIME_XLSX, on_click="ignore", width="stretch", key=f"modelo_{tipo}_preenchido")
    st.download_button("📋 Modelo em Branco", data=modelo(tipo, False), file_name=f"modelo_{tipo}_em_branco.xlsx",
                       mime=MIME_XLSX, on_click="ignore", width="stretch", key=f"modelo_{tipo}_em_branco")


LIMITE_EXCEL = 50_000


def formato_planilha(n_linhas: int, nome: str) -> tuple[str, str]:
    """Excel até 50 mil linhas; acima disso, CSV num .zip (gerar Excel de 1 milhão de linhas leva minutos)."""
    return (f"{nome}.xlsx", MIME_XLSX) if n_linhas <= LIMITE_EXCEL else (f"{nome}.zip", "application/zip")


def resumo_planilha(df_proc: pd.DataFrame, resultados: dict, conv: pd.DataFrame, contexto: dict) -> pd.DataFrame:
    """Aba Resumo: números principais e parâmetros (o mesmo do relatório PDF)."""
    from utils.relatorio import _parametros

    ind = painel.indicadores(df_proc, resultados, conv)
    linhas = [("Dados", contexto.get("descricao_fonte") or ""),
              ("Segmentos analisados", ind["segmentos"]), ("Extensão (km)", round(ind["km"], 1)),
              ("Segmentos com sinistro", ind["com_sinistro"]), ("Sinistros", int(ind["sinistros"])),
              ("Sinistros com óbito", int(ind["com_obito"]))]
    linhas += [(f"Críticos na {rotulo_trilha(c)}", p["criticos"]) for c, p in ind["por_trilha"].items()]
    n = len(resultados)
    linhas += [("Críticos em ao menos 1 trilha" if k == 1 else f"Críticos em {k} ou mais trilhas" if k < n
                else f"Críticos nas {n} trilhas", ind["em_pelo_menos"][k]) for k in (1, 2, 3) if k <= n]
    parametros = _parametros(resultados, df_proc.attrs.get("pesos_ups", PESOS_UPS_PADRAO), contexto)
    linhas += list(parametros[parametros["Parâmetro"] != "Dados"].itertuples(index=False, name=None))
    return pd.DataFrame(linhas, columns=["Item", "Valor"])


def resultados_planilha(resultados: dict, dados: pd.DataFrame, df_proc: pd.DataFrame | None = None,
                        contexto: dict | None = None) -> tuple[bytes, str, str]:
    """Excel com o resumo, o ordenamento dos segmentos críticos e uma aba por trilha, com nomes de colunas claros
    (``utils/tabelas.py``); acima de 50 mil linhas, CSVs num .zip."""
    output = io.BytesIO()
    tabelas = {}
    if df_proc is not None:
        conv = painel.convergencia(resultados, df_proc)
        tabelas["Resumo"] = resumo_planilha(df_proc, resultados, conv, contexto or {})
        tabelas["Ordenamento"] = tabela_prioridades(conv)
    tabelas.update({rotulo_trilha(c).split(" — ")[0]: tabela_resultado(c, r, dados) for c, r in resultados.items()})
    if sum(len(t) for t in tabelas.values()) <= LIMITE_EXCEL:
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            for aba, tabela in tabelas.items():
                tabela.to_excel(writer, sheet_name=aba, index=False)
                ws = writer.sheets[aba]
                ws.freeze_panes(1, 1 if aba != "Resumo" else 0)
                if aba == "Resumo":
                    ws.set_column(0, 0, 32)
                    ws.set_column(1, 1, 90)
        return output.getvalue(), "resultados_segmentos_criticos.xlsx", MIME_XLSX
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for aba, tabela in tabelas.items():
            z.writestr(f"{aba.replace(' ', '_').lower()}.csv", tabela.to_csv(index=False, sep=";", decimal=","))
    return output.getvalue(), "resultados_segmentos_criticos.zip", "application/zip"


def contexto_relatorio(opcoes: dict) -> dict:
    """O que o relatório precisa saber além dos resultados: a fonte, as mensagens sobre os dados e as opções."""
    fonte = st.session_state.fonte
    mensagens = (list(st.session_state.msgs_segmentacao or []) if fonte == "auto"
                 else [("warning", a) for a in st.session_state.avisos_entrada] if fonte == "planilha" else [])
    dados = st.session_state.dados
    resumo = dados.attrs.get("resumo", {}) if dados is not None else {}
    segmentacao = None
    if fonte == "auto" and st.session_state.auto_chave:
        _, _, comprimento, por_sentido, residenciais, _, usar_vmd = st.session_state.auto_chave
        segmentacao = {"comprimento": comprimento, "por_sentido": por_sentido, "residenciais": residenciais,
                       "vmd": usar_vmd}
    return {"descricao_fonte": st.session_state.descricao_fonte, "mensagens": mensagens,
            "segmentacao": segmentacao, "excluir_zeros": opcoes["vc"][3], "erros": dict(st.session_state.erros),
            "prf": fonte == "auto" and bool(resumo.get("com_km"))}


def relatorio_pdf(df_proc: pd.DataFrame, resultados: dict, contexto: dict) -> bytes:
    return gerar_pdf_completo(df_proc, resultados, LOGO, contexto)


LIMITE_PONTOS_MAPA = 20_000


def _chave(arquivos) -> tuple:
    return tuple((a.name, a.size, getattr(a, "file_id", None)) for a in arquivos)


@st.cache_resource(max_entries=2, show_spinner="Lendo o SNV...")
def snv_preparado(chave, _arquivos):
    """SNV lido e preparado uma vez por envio (compartilhado entre execuções)."""
    return preparar_snv(ler_snv_enviado([(a.name, a.getvalue()) for a in _arquivos]))


@st.cache_resource(max_entries=2, show_spinner="Lendo os sinistros...")
def sinistros_lidos(chave, _arquivos):
    return ler_arquivos_sinistros([(a.name, a.getvalue()) for a in _arquivos])


@st.cache_resource(max_entries=2, show_spinner="Lendo o VMD...")
def vmd_pnct(chave, _arquivo):
    return ler_vmd_pnct(_arquivo.getvalue(), nome=_arquivo.name)


@st.cache_resource(max_entries=8, show_spinner=False)
def snv_embutido(ufs: tuple) -> pd.DataFrame:
    return preparar_snv(dp.ler_snv(list(ufs)))


@st.cache_resource(show_spinner=False)
def vmd_embutido() -> pd.DataFrame:
    return dp.ler_vmd()


def sem_vmd(dados: pd.DataFrame) -> pd.DataFrame:
    """Os segmentos sem o volume de tráfego, quando o usuário desmarca o VMD na barra lateral: as Trilhas 1
    (frequência e severidade) e 2 seguem iguais; a Trilha 3 e os métodos de taxa da Trilha 1 deixam de rodar."""
    d = dados.drop(columns=[c for c in ("vmd_origem", "vmd_classificacao") if c in dados])
    d["volume_trafego"] = np.nan
    resumo = {**dados.attrs.get("resumo", {}), "vmd": None, "vmd_desativado": True}
    d.attrs = {**dados.attrs, "resumo": resumo}
    return d


def segmentacao_automatica(ufs: tuple, anos: tuple, comprimento: float, por_sentido: bool, residenciais: bool,
                           chave_arquivos: tuple, _sinistros=None, _snv=None, _vmd=None,
                           _andamento=None) -> pd.DataFrame:
    """Segmenta com os dados embutidos (ou os enviados). Com os sinistros da PRF, o resultado fica em cache
    e serve a todos os usuários; com sinistros próprios (bases que podem passar de 1 milhão de segmentos com
    as ruas urbanas), fica só na sessão."""
    if _sinistros is None:
        return _segmentacao_prf(ufs, anos, comprimento, por_sentido, chave_arquivos, _snv=_snv, _vmd=_vmd)
    return _segmentar(ufs, anos, comprimento, por_sentido, residenciais, _sinistros, _snv, _vmd, _andamento)


@st.cache_resource(max_entries=4, show_spinner=False)
def _segmentacao_prf(ufs: tuple, anos: tuple, comprimento: float, por_sentido: bool, chave_arquivos: tuple,
                     _snv=None, _vmd=None) -> pd.DataFrame:
    return _segmentar(ufs, anos, comprimento, por_sentido, False, None, _snv, _vmd)


def _segmentar(ufs, anos, comprimento, por_sentido, residenciais, _sinistros, _snv, _vmd,
               _andamento=None) -> pd.DataFrame:
    def etapa(texto):
        if _andamento is not None:
            _andamento.update(label=texto)
            _andamento.write(texto)

    snv = _snv if _snv is not None else snv_embutido(ufs)
    vmd = _vmd if _vmd is not None else vmd_embutido()
    vias = area = None
    if _sinistros is None:
        sinistros = dp.ler_sinistros_prf(list(ufs), list(anos))
    else:
        sinistros = _sinistros
        no_periodo = sinistros[sinistros["ano"].isin(anos)] if (anos and sinistros["ano"].notna().any()) else sinistros
        etapa("Lendo as vias do OpenStreetMap na área dos sinistros...")
        area = retangulo(no_periodo, snv, ufs)       # a malha (SNV e OpenStreetMap) fica na área dos sinistros
        vias = dp.ler_vias_osm(area, urbanas=residenciais)
        etapa(f"Cortando {len(vias):,} vias em segmentos e localizando {len(no_periodo):,} sinistros..."
              .replace(",", "."))
    return segmentar(sinistros, snv, list(ufs), list(anos), comprimento, por_sentido, vmd=vmd, vias_prontas=vias,
                     area=area)


def area_grande(sinistros: pd.DataFrame, limite_graus: float = 1.5) -> bool:
    """Sinistros espalhados por mais de ~150 km (ex.: uma UF inteira), sem contar 1% de cada ponta."""
    pts = sinistros[["latitude", "longitude"]].dropna()
    if len(pts) < 10:
        return False
    q = pts.quantile([0.01, 0.99])
    return bool(((q.loc[0.99] - q.loc[0.01]) > limite_graus).any())


def texto_fontes(v: dict) -> tuple[str, str]:
    """Bases embutidas, para a barra lateral: uma frase curta e os detalhes em tópicos (no “?” ao lado dela)."""
    topicos = []
    if v.get("snv"):
        topicos.append(f"**Malha das rodovias federais:** SNV {v['snv'].get('versao')}, do DNIT")
    if v.get("prf", {}).get("anos"):
        anos = v["prf"]["anos"]
        ate = "/".join(reversed(str(v["prf"].get("ultima_data", "")).split("-")))
        topicos.append(f"**Sinistros nas rodovias federais:** PRF, de {anos[0]} a {anos[-1]} (até {ate})")
    if v.get("vmd"):
        topicos.append(f"**Volume de tráfego:** VMD do PNCT (DNIT), {v['vmd'].get('ano')}")
    if v.get("osm"):
        data = "/".join(reversed(str((v["osm"].get("extratos") or [""])[0]).split("-")))
        topicos.append(f"**Outras vias:** OpenStreetMap, extrato de {data}; {ATRIBUICAO}")
    return ("Dados públicos embutidos: DNIT, PRF, PNCT e [© OpenStreetMap](https://www.openstreetmap.org/copyright).",
            "\n".join(f"- {t}" for t in topicos))


SEM_EXTENSAO = ("Nenhuma linha tem a extensão do segmento: a planilha parece ter um sinistro por linha. Com ela, "
                "só a Trilha 2 (KDE) roda. Para as três trilhas, envie-a em “Usar meus dados de sinistros”, na "
                "segmentação automática.")


def avisos_sem_extensao(dados: pd.DataFrame, avisos: list[str]) -> list[str]:
    """Planilha sem nenhuma extensão (em geral, um sinistro por linha): um aviso que indica a Opção 2."""
    if dados["extensao_trecho"].isna().all():
        return [SEM_EXTENSAO] + [a for a in avisos if "sem extensão válida" not in a]
    return avisos


def dica_erro(mensagem: str, dados: pd.DataFrame) -> str:
    """O que o usuário pode fazer quando uma trilha não roda por falta de extensão ou de VMD."""
    sem_extensao = "extensao_trecho" not in dados or dados["extensao_trecho"].isna().all()
    if ("extensão" in mensagem or "VMD" in mensagem) and sem_extensao:
        return (" A planilha não traz a extensão dos segmentos (parece ter um sinistro por linha): envie-a em "
                "“Usar meus dados de sinistros”, na segmentação automática.")
    if "VMD" in mensagem and dados.attrs.get("resumo", {}).get("vmd_desativado"):
        return (" O VMD está desmarcado na barra lateral: marque “Usar o volume de tráfego (VMD)” para rodar esta "
                "análise.")
    if "VMD" in mensagem and "fonte" in dados and dados["fonte"].eq("OpenStreetMap").all():
        return (" As vias do OpenStreetMap não têm VMD: em áreas urbanas, use a Trilha 1 (número de sinistros ou "
                "severidade) e a Trilha 2.")
    if "VMD" in mensagem:
        return " Inclua a coluna volume_trafego na planilha ou use a segmentação automática, que traz o VMD do PNCT."
    return ""


def mensagens_segmentacao(resumo: dict, residenciais: bool | None = None) -> list[tuple[str, str]]:
    """Resumo da segmentação em mensagens (tipo, texto) para a barra lateral."""
    n, ok = resumo["sinistros"], resumo["atribuidos"]
    onde = "na área dos sinistros, em" if "fora_da_area" in resumo else "em"
    if resumo["segmentos"] or not resumo.get("osm"):
        inicio = (f"{_br(resumo['segmentos'])} segmentos do SNV de cerca de {resumo['comprimento']:g} km {onde} "
                  f"{', '.join(resumo['ufs'])}")
    else:
        inicio = "Nenhuma rodovia federal (SNV) na área dos sinistros"
    msgs = [("success", f"{inicio}; {_br(ok)} de {_br(n)} sinistros localizados ({_pct(ok / n) if n else '0%'}). "
                        f"SNV {resumo['versao_snv']}.")]
    fora = {k: v for k, v in resumo["situacoes"].items() if not k.startswith("localizado")}
    if fora:
        msgs.append(("warning", "Fora da análise: " + "; ".join(f"{v:,} {k}".replace(",", ".")
                                                             for k, v in fora.items()) + "."))
    longe = resumo["situacoes"].get(LONGE_DAS_VIAS, 0)
    if residenciais is False and longe > 0.1 * n:
        msgs.append(("info", f"{longe:,}".replace(",", ".") + " sinistros ficaram longe das vias: marque “Incluir "
                             "ruas residenciais” para considerar as ruas urbanas."))
    if resumo["sem_sentido"]:
        msgs.append(("warning", f"{resumo['sem_sentido']} sinistro(s) sem sentido informado ficaram de fora."))
    osm = resumo.get("osm")
    if osm:
        msgs.append(("success", f"OpenStreetMap: {osm['segmentos']:,} segmentos em {osm['km']:,} km de vias fora do "
                                f"SNV; {osm['sinistros']:,} sinistros nessas vias.".replace(",", ".")))
    vmd = resumo.get("vmd")
    if resumo.get("vmd_desativado"):
        msgs.append(("info", "Volume de tráfego (VMD) desmarcado na barra lateral: as Trilhas 1 (frequência e "
                             "severidade) e 2 não dependem dele; a Trilha 3 e os métodos de taxa da Trilha 1 não "
                             "rodam."))
    elif vmd is None:
        msgs.append(("info", "Sem volume de tráfego (VMD), a Trilha 3 e os métodos de taxa da Trilha 1 não rodam."))
    elif not resumo["segmentos"]:
        msgs.append(("info", "As vias do OpenStreetMap não têm VMD: a Trilha 3 e os métodos de taxa da Trilha 1 não "
                             "rodam nelas."))
    else:
        ano = vmd["ano"] or "ano não informado"
        msgs.append(("success", f"VMD do PNCT ({ano}, SNV {vmd['versao_snv']}) em {_pct(vmd['cobertura'])} dos "
                                "segmentos do SNV" + ("; as vias do OpenStreetMap não têm VMD." if osm else ".")
                                + " Trata-se do banco de dados público de VMD mais atualizado disponível (estimativa "
                                "da modelagem nacional do PNCT/DNIT)."))
        if vmd["nao_simulavel"]:
            msgs.append(("warning", f"{vmd['nao_simulavel']} segmento(s) com VMD marcado pelo PNCT como "
                                    "“Não Simulável” (perto de áreas urbanas): avaliar com cautela."))
        if vmd["ano"] and resumo["anos"] and vmd["ano"] not in resumo["anos"]:
            msgs.append(("warning", f"O VMD embutido refere-se ao ano-base {vmd['ano']} (base pública mais recente do "
                                    f"PNCT) e os sinistros ao período {', '.join(map(str, resumo['anos']))}: "
                                    "caso disponha de contagens mais recentes, envie-as em "
                                    "“Atualizar a malha ou o VMD”."))
    conc = resumo.get("concentradas")
    if conc:
        msgs.append(("warning", f"{_br(conc['pontos'])} coordenada(s) com {conc['minimo']} sinistros ou mais cada "
                                f"({_br(conc['sinistros'])} sinistros, "
                                f"{_pct(conc['sinistros'] / conc['total'])} dos que "
                                "têm coordenada). Podem ser cruzamentos movimentados, mas também pontos padrão do "
                                "geocodificador (centro do município, do bairro ou da via), que inflam os segmentos "
                                "onde caem: confira as maiores em “Coordenadas repetidas”, logo abaixo."))
    return msgs


def mensagens_leitura(sinistros: pd.DataFrame) -> list[tuple[str, str]]:
    """Avisos da leitura dos sinistros enviados. Os sem coordenada aparecem no resumo da segmentação, só os do
    período escolhido."""
    a, msgs = sinistros.attrs, []
    if a.get("linhas_repetidas"):
        msgs.append(("info", f"{_br(a['linhas_repetidas'])} linhas repetiam a mesma ocorrência (arquivos da PRF por "
                             f"pessoa) e foram contadas uma vez: {_br(len(sinistros))} sinistros."))
    if a.get("sem_coluna_ano"):
        msgs.append(("info", "A planilha de sinistros não informa coluna de data ou ano: todos os registros foram "
                             "incluídos considerando o período padrão de 3 anos."))
    elif a.get("sem_ano"):
        msgs.append(("warning", f"{_br(a['sem_ano'])} sinistro(s) sem data ou ano reconhecido ficaram fora da análise "
                                "(use DD/MM/AAAA ou AAAA-MM-DD)."))
    return msgs


def _br(n, casas: int = 0) -> str:
    """Número no padrão brasileiro: 1.234.567 ou 1.234,5."""
    return f"{n:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(x: float) -> str:
    if x == 0:
        return "0%"
    if x < 0.01:
        return "<1%"
    if 0.995 <= x < 1.0:
        return f"{min(99.9, np.floor(1000 * x + 1e-9) / 10):.1f}%".replace(".", ",")   # nunca 100% se não for
    return f"{100 * x:.0f}%"


def mostrar_caracteristicas(dados: pd.DataFrame | None) -> None:
    """Resumo, avisos e tabela dos dados carregados, num bloco recolhido abaixo das configurações: a barra lateral
    fica só com a entrada de dados."""
    if dados is None or dados.empty:
        return
    fonte = st.session_state.fonte
    if fonte == "auto":
        msgs = [m for m in (st.session_state.msgs_segmentacao or []) if m[0] != "error"]
    elif fonte == "planilha":
        msgs = [("warning", a) for a in st.session_state.avisos_entrada]
    else:
        msgs = []
    n_avisos = sum(tipo == "warning" for tipo, _ in msgs)
    rotulo = "📋 Características dos dados carregados"
    if n_avisos:
        rotulo += f" · {n_avisos} aviso" + ("s" if n_avisos > 1 else "")
    with st.expander(rotulo):
        if st.session_state.descricao_fonte:
            st.markdown(f"**{st.session_state.descricao_fonte}**")
        def numero(coluna):            # colunas que podem vir como texto ou com NA (planilhas e formulário)
            return pd.to_numeric(dados[coluna], errors="coerce").astype(float)

        sin = pd.DataFrame({c: numero(c) for c in COLUNAS_SINISTROS}).fillna(0)
        por_tipo = sin.sum()
        com_sinistro = sin.sum(axis=1) > 0
        ext = numero("extensao_trecho")
        com_vmd = numero("volume_trafego").fillna(0) > 0
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Segmentos", _br(len(dados)))
        c2.metric("Extensão", f"{_br(ext.sum())} km" if ext.notna().any() else "—")
        c3.metric("Sinistros", _br(por_tipo.sum()))
        c4.metric("Segmentos com sinistro", _pct(com_sinistro.mean()), help="Só eles podem ser críticos.")
        c5.metric("Segmentos com VMD", _pct(com_vmd.mean()), help="A Trilha 3 e os métodos de taxa da Trilha 1 "
                                                                    "usam só os segmentos com VMD.")
        n_anos = numero("n_anos").max()
        partes = [f"{_br(por_tipo['sem_vitima'])} sem vítima, {_br(por_tipo['com_vitima'])} com vítima e "
                  f"{_br(por_tipo['com_obito'])} com óbito"]
        if pd.notna(n_anos):
            partes.append(f"período de {n_anos:g} ano" + ("s" if n_anos != 1 else ""))
        if "fonte" in dados and dados["fonte"].eq("OpenStreetMap").any():
            n_osm = int(dados["fonte"].eq("OpenStreetMap").sum())
            partes.append(f"{_br(len(dados) - n_osm)} segmentos no SNV e {_br(n_osm)} em vias do OpenStreetMap")
        st.caption("Sinistros: " + "; ".join(partes) + ".")
        for tipo, texto in msgs:
            getattr(st, tipo)(texto)
        conc = dados.attrs.get("resumo", {}).get("concentradas") if fonte == "auto" else None
        if conc:
            st.markdown("##### Coordenadas repetidas")
            maiores = pd.DataFrame(conc["maiores"], columns=["Latitude", "Longitude", "Sinistros"])
            maiores["Mapa"] = [f"https://www.openstreetmap.org/?mlat={la:.5f}&mlon={lo:.5f}#map=18/{la:.5f}/{lo:.5f}"
                               for la, lo in zip(maiores["Latitude"], maiores["Longitude"])]
            st.dataframe(maiores, hide_index=True, width="stretch",
                         column_config={"Mapa": st.column_config.LinkColumn("Mapa", display_text="ver no mapa")})
        st.markdown(f"##### Tabela dos segmentos ({_br(len(dados))})")
        mostrar_tabela(tabela_segmentos(dados.head(LIMITE_LINHAS_TABELA)), total=len(dados))
        nome_arq, mime = formato_planilha(len(dados), "segmentos")
        st.download_button("📥 Baixar segmentos (planilha)", data=lambda d=dados: arquivo_segmentos(d)[0],
                           file_name=nome_arq, mime=mime, on_click="ignore")


def arquivo_segmentos(dados: pd.DataFrame) -> tuple[bytes, str, str]:
    """Planilha dos segmentos, com os nomes claros de ``utils/tabelas.py`` (o leitor os reconhece, então ela
    pode ser corrigida e enviada de novo): Excel até 50 mil linhas; acima disso, CSV num .zip."""
    output = io.BytesIO()
    dados = tabela_segmentos(dados)
    if len(dados) <= LIMITE_EXCEL:
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            dados.to_excel(writer, sheet_name="Segmentos", index=False)
        return output.getvalue(), "segmentos.xlsx", MIME_XLSX
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("segmentos.csv", dados.to_csv(index=False, sep=";", decimal=","))
    return output.getvalue(), "segmentos.zip", "application/zip"


def mostrar_mapa(chave, construir, altura=520):
    """Monta o mapa uma vez por execução (fica em cache na sessão)."""
    if chave not in st.session_state.mapas:
        mapa = construir()
        st.session_state.mapas[chave] = None if mapa is None else mapa.get_root().render()
    html_mapa = st.session_state.mapas[chave]
    if html_mapa is None:
        st.info("Sem coordenadas para exibir o mapa.")
    else:  # textos vindos da planilha já são escapados em utils/mapas.py
        st.iframe(html_mapa, height=altura)


def aviso_mapa(res: pd.DataFrame) -> None:
    n_validos = int(res["densidade"].notna().sum()) if "densidade" in res else len(res)
    if n_validos > LIMITE_PONTOS_MAPA:
        st.caption(f"Base com {_br(n_validos)} pontos: o mapa exibe até {_br(LIMITE_PONTOS_MAPA)} pontos.")


def para_mapa(res: pd.DataFrame, dados: pd.DataFrame) -> pd.DataFrame:
    """Pontos do mapa: em bases muito grandes, só os críticos (ou amostra por quartil no KDE); coordenadas e via
    vêm de ``dados`` quando a trilha não as traz (Trilhas 1 e 3). Chamada só quando o mapa é montado."""
    if "densidade" in res:
        res = res[res["densidade"].notna()]
        if len(res) > LIMITE_PONTOS_MAPA:
            por_quartil = LIMITE_PONTOS_MAPA // 4
            res = res.groupby("nivel_densidade", group_keys=False).head(por_quartil)
    elif len(res) > LIMITE_PONTOS_MAPA:
        res = res[res["Critico"].astype(bool)].head(LIMITE_PONTOS_MAPA)
    falta = [c for c in ("latitude", "longitude", "rodovia", "sentido") if c in dados and c not in res]
    if falta:
        res = res.merge(dados[["segmento_id", *falta]].drop_duplicates("segmento_id"), on="segmento_id", how="left")
    return res


def _eixo_br():
    """Rótulos dos eixos com ponto nos milhares (o Vega usa vírgula)."""
    return "replace(datum.label, regexp(',', 'g'), '.')"


def mostrar_legenda_trilhas(niveis) -> None:
    """Legenda das cores do número de trilhas, com bolinhas nas cores do mapa (st.caption deixaria as cores
    desbotadas, pois a legenda dele é semitransparente)."""
    itens = " &nbsp; ".join(f'<span style="color:{painel.CORES_N_TRILHAS[n]};font-size:1.3em;line-height:1">●</span> '
                            f"{NOMES_N_TRILHAS[n]}" for n in sorted(niveis))
    st.markdown(f'<div style="font-size:0.875rem">{itens}</div>', unsafe_allow_html=True)


def grafico_barras(df: pd.DataFrame, rotulo: str, valor: str, titulo_valor: str, ordem=None, cor_trilhas=None):
    """Barras horizontais com o valor na ponta e na dica; numa cor só ou, com ``cor_trilhas`` (coluna com o
    número de trilhas), nas cores do mapa da convergência."""
    import altair as alt

    df = df.assign(_texto=df[valor].map(_br))
    base = alt.Chart(df).encode(
        y=alt.Y(f"{rotulo}:N", sort=ordem if ordem is not None else "-x", title=None,
                axis=alt.Axis(labelLimit=280)),
        x=alt.X(f"{valor}:Q", title=titulo_valor, axis=alt.Axis(tickMinStep=1, tickCount=6,
                                                                labelExpr=_eixo_br())),
        tooltip=[alt.Tooltip(f"{rotulo}:N", title=" "), alt.Tooltip("_texto:N", title=titulo_valor)],
    )
    if cor_trilhas:
        barras = base.mark_bar(size=18, cornerRadiusEnd=4).encode(color=alt.Color(
            f"{cor_trilhas}:O", legend=None, scale=alt.Scale(domain=list(painel.CORES_N_TRILHAS),
                                                             range=list(painel.CORES_N_TRILHAS.values()))))
    else:
        barras = base.mark_bar(color=painel.AZUL, size=18, cornerRadiusEnd=4)
    textos = base.mark_text(align="left", dx=4).encode(text="_texto:N")
    return (barras + textos).properties(height=max(110, 32 * len(df)))


def grafico_histograma(faixas: pd.DataFrame):
    import altair as alt

    largura = (faixas["fim"] - faixas["inicio"]).min()
    faixas = faixas.assign(_texto=faixas["segmentos"].map(_br), _fim=faixas["fim"] - 0.12 * largura)  # vão
    return alt.Chart(faixas).mark_bar(color=painel.AZUL, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("inicio:Q", title="UPS no período", axis=alt.Axis(labelExpr=_eixo_br())),
        x2="_fim:Q",
        y=alt.Y("segmentos:Q", title="Segmentos", axis=alt.Axis(tickMinStep=1, labelExpr=_eixo_br())),
        y2=alt.datum(0),                       # com x e x2, a barra precisa da base explícita
        tooltip=[alt.Tooltip("faixa:N", title="UPS"), alt.Tooltip("_texto:N", title="Segmentos")],
    ).properties(height=260)


NOMES_N_TRILHAS = {1: "Crítico em 1 trilha", 2: "Em 2 trilhas", 3: "Nas 3 trilhas"}


def tabela_prioridades(conv: pd.DataFrame) -> pd.DataFrame:
    """Lista de prioridades com nomes claros (tela e planilha)."""
    colunas = {"segmento_id": "ID do segmento", "rodovia": "Rodovia ou via", "trilhas": "Crítico nas",
               "n_trilhas": "Nº de trilhas", "UPS": "UPS", "total_sinistros": "Total de sinistros",
               "com_obito": "Sinistros com óbito", "com_vitima": "Sinistros com vítima",
               "sem_vitima": "Sinistros sem vítima", "extensao_trecho": "Extensão (km)",
               "volume_trafego": "VMD (veículos/dia)", "fonte": "Fonte da via", "latitude": "Latitude",
               "longitude": "Longitude"}
    t = conv[[c for c in colunas if c in conv]].rename(columns=colunas)
    t.insert(0, "Posição", range(1, len(t) + 1))
    return t


def mostrar_painel(resultados: dict, df_proc: pd.DataFrame, sig: str) -> None:
    """Aba Painel: as três trilhas juntas, com filtros que valem para o painel inteiro."""
    disponiveis = [c for c in ORDEM_TRILHAS if c in resultados]
    if not disponiveis:
        st.info("Nenhuma trilha rodou com estes dados: veja as mensagens nas abas das trilhas.")
        return
    st.caption("As três trilhas juntas. Os filtros abaixo valem para o painel inteiro; o relatório PDF, no fim da "
               "página, traz a análise completa, sem filtros.")
    f1, f2, f3 = st.columns([2.5, 2.5, 1.4])
    trilhas = f1.multiselect("Trilhas", disponiveis, default=disponiveis, format_func=painel.rotulo_curto,
                             key=f"pn_trilhas_{sig[:12]}")
    if not trilhas:
        st.info("Escolha ao menos uma trilha.")
        return
    conv_todas = memo("convergencia", (sig, tuple(trilhas)),
                      lambda: painel.convergencia(resultados, df_proc, trilhas))
    opcoes_vias = conv_todas["via"].value_counts().index.tolist() if "via" in conv_todas else []
    vias = f2.multiselect("Rodovias ou vias", opcoes_vias, placeholder="Todas (só as com segmentos críticos)",
                          key=f"pn_vias_{sig[:12]}", disabled=not opcoes_vias)
    minimo = f3.selectbox("Críticos em ao menos", list(range(1, len(trilhas) + 1)), index=min(1, len(trilhas) - 1),
                          format_func=lambda n: f"{n} trilha" + ("s" if n > 1 else ""),
                          key=f"pn_minimo_{sig[:12]}_{len(trilhas)}")

    def filtrar():
        if not vias:
            return df_proc, {c: resultados[c] for c in trilhas}, conv_todas
        base = df_proc[painel.via_de(df_proc["rodovia"]).isin(vias)]
        ids = set(base["segmento_id"].astype(str))
        res = {c: resultados[c][resultados[c]["segmento_id"].astype(str).isin(ids)] for c in trilhas}
        return base, res, conv_todas[conv_todas["via"].isin(vias)]

    base, res_f, conv = memo("filtro", (sig, tuple(trilhas), tuple(vias)), filtrar)
    ind = memo("indicadores", (sig, tuple(trilhas), tuple(vias)), lambda: painel.indicadores(base, res_f, conv))

    c = st.columns(4)
    c[0].metric("Segmentos analisados", _br(ind["segmentos"]), border=True,
                help=f"{_br(ind['com_sinistro'])} com ao menos um sinistro; {_br(ind['km'])} km.")
    c[1].metric("Sinistros", _br(ind["sinistros"]), border=True, help=f"{_br(ind['com_obito'])} com óbito.")
    c[2].metric("Críticos em ao menos 1 trilha", _br(ind["em_pelo_menos"][1]), border=True)
    if len(trilhas) > 1:
        c[3].metric(f"Críticos em {'2 ou mais' if len(trilhas) > 2 else 'ambas as'} trilhas",
                    _br(ind["em_pelo_menos"][2]), border=True,
                    help=f"{_br(ind['em_pelo_menos'][3])} nas três trilhas." if len(trilhas) > 2 else None)
    colunas = st.columns(len(trilhas))
    for coluna, chave in zip(colunas, trilhas):
        r = res_f[chave]
        n_com = int((r[[x for x in COLUNAS_SINISTROS if x in r]].sum(axis=1) > 0).sum()
                    if set(COLUNAS_SINISTROS) <= set(r) else (r["total_sinistros"] > 0).sum())
        coluna.metric(rotulo_trilha(chave), f"{_br(ind['por_trilha'][chave]['criticos'])} críticos",
                      help="Segmentos com sinistro avaliados pela trilha (a Trilha 3 só avalia os que têm VMD).")
        coluna.caption(f"entre {_br(n_com)} segmentos com sinistro avaliados")

    parte = ind["parcela"][minimo]
    if parte["segmentos"]:
        nome = f"em {minimo} ou mais trilhas" if minimo < len(trilhas) else (
            "em todas as trilhas escolhidas" if minimo > 1 else "na trilha escolhida")
        if minimo == 1 and len(trilhas) > 1:
            nome = "em ao menos uma trilha"
        st.markdown(f"Os **{_br(parte['segmentos'])} segmentos críticos {nome}** são **{_pct(parte['km'])} da "
                    f"extensão** analisada e reúnem **{_pct(parte['sinistros'])} dos sinistros**, "
                    f"**{_pct(parte['com_obito'])} dos sinistros com óbito** e **{_pct(parte['ups'])} da UPS**.")
    else:
        st.info(f"Nenhum segmento é crítico em {minimo} ou mais das trilhas escolhidas.")

    g1, g2 = st.columns(2)
    with g1:
        if len(trilhas) > 1:
            st.markdown("##### Convergência entre as trilhas")
            comb = painel.combinacoes(conv, trilhas)
            mostrar_legenda_trilhas(comb["n_trilhas"].astype(int).unique())
            st.altair_chart(grafico_barras(comb, "combinacao", "segmentos", "Segmentos críticos",
                                           ordem=list(comb["combinacao"]), cor_trilhas="n_trilhas"),
                            width="stretch")
        else:
            st.markdown("##### Convergência entre as trilhas")
            st.caption("Escolha duas trilhas ou mais para ver a convergência.")
    with g2:
        pesos = df_proc.attrs.get("pesos_ups", PESOS_UPS_PADRAO)
        st.markdown("##### UPS dos segmentos com sinistro")
        faixas = memo("histograma", (sig, tuple(vias)), lambda: painel.histograma_ups(base))
        st.caption(f"UPS = {pesos['sem_vitima']} × sem vítima + {pesos['com_vitima']} × com vítima + "
                   f"{pesos['com_obito']} × com óbito, somada no período.")
        if len(faixas):
            st.altair_chart(grafico_histograma(faixas), width="stretch")

    sel = conv[conv["n_trilhas"] >= minimo]
    st.markdown(f"##### Mapa dos segmentos críticos em {minimo} ou mais trilha" + ("s" if minimo > 1 else ""))
    if len(sel):
        mostrar_legenda_trilhas(sel["n_trilhas"].astype(int).unique())
    if len(sel) > LIMITE_PONTOS_MAPA:
        st.caption(f"{_br(len(sel))} segmentos: o mapa mostra os {_br(LIMITE_PONTOS_MAPA)} primeiros do ordenamento "
                   "de segmentos críticos.")
    chave_mapa = f"painel-{sig[:12]}-{'-'.join(trilhas)}-{hash(tuple(vias))}-{minimo}"
    for k in [k for k in st.session_state.mapas if k.startswith("painel-") and k != chave_mapa]:
        del st.session_state.mapas[k]                    # só o mapa dos filtros atuais fica na memória
    mostrar_mapa(chave_mapa, lambda: mapa_convergencia(sel.head(LIMITE_PONTOS_MAPA).iloc[::-1],
                                                       painel.CORES_N_TRILHAS, NOMES_N_TRILHAS, painel.CONTORNO))

    vias_top = painel.vias_criticas(conv, minimo)
    if len(vias_top) > 1:
        st.markdown(f"##### Vias com mais segmentos críticos em {minimo} ou mais trilha" + ("s" if minimo > 1 else ""))
        st.altair_chart(grafico_barras(vias_top, "via", "segmentos", "Segmentos críticos"), width="stretch")

    st.markdown("##### Ordenamento dos segmentos críticos")
    st.caption("Segmentos hierarquizados pelo número de trilhas convergentes e, em caso de empate, pela maior UPS "
               "(Capítulo 4 do Manual). A relação completa consta na planilha de resultados.")
    mostrar_tabela(tabela_prioridades(sel.head(LIMITE_LINHAS_TABELA)), total=len(sel))


def limpar_tudo(**extra) -> int:
    """Volta ao início: sem dados, sem resultados e com os campos de envio vazios (novas chaves de widget).
    Retorna a nova chave dos widgets da barra lateral."""
    nova = st.session_state.uploader_key + 1
    st.session_state.update({"dados": None, "avisos_entrada": [], "erro_entrada": None, "arquivo_id": None,
                             "msgs_segmentacao": None, "auto_chave": None, "fonte": None, "descricao_fonte": None,
                             "uploader_key": nova, "exemplo": None, **extra})
    limpar_resultados()
    return nova


def abrir_exemplo(tipo: str) -> None:
    """Botões dos Primeiros passos: carregam o exemplo de rodovia (sinistros da PRF no DF) ou o urbano (recorte
    do Infosiga SP, embutido em dados_publicos/exemplos). Os anos e o comprimento ficam nos padrões."""
    nova = limpar_tudo(guia=False, exemplo=tipo if tipo == "urbano" else None)
    st.session_state[f"ufs_{nova}"] = ["DF"] if tipo == "rodovia" else [dp.exemplo_urbano()["uf"]]


@st.cache_resource(show_spinner=False)
def sinistros_exemplo() -> pd.DataFrame:
    return dp.ler_exemplo_urbano()


PASTA_GUIA = os.path.join(BASE, "assets", "guia")
PASSOS_GUIA = [
    ("Seleção da base de dados e segmentação",
     "Na barra lateral, em **Entrada de dados**, selecione a **UF** e o **período (anos)**. O sistema subdivide a "
     "malha rodoviária federal (SNV/DNIT) em segmentos homogêneos (padrão de 1 km), georreferencia os registros da "
     "Polícia Rodoviária Federal (PRF), associa o volume médio diário (VMD) da modelagem nacional do PNCT e executa "
     "as três trilhas metodológicas do Manual.\n\n"
     "Para análises em rodovias estaduais ou vias municipais, envie uma planilha de ocorrências em **Usar meus dados "
     "de sinistros** (utilizando os modelos disponíveis para download). Caso já disponha da malha previamente "
     "segmentada com as contagens agregadas, utilize a seção **Outras formas de entrada**.",
     "passo_1_dados.png"),
    ("Verificação das características e consistência dos dados",
     "Expanda o bloco **Características dos dados carregados**, localizado abaixo das configurações: são apresentados "
     "os totais de segmentos, a extensão analisada, o percentual de sinistros georreferenciados, a cobertura de VMD "
     "e alertas automáticos sobre a consistência dos registros (como concentração atípica em coordenadas idênticas). "
     "Recomenda-se a leitura dessas informações antes da interpretação dos resultados.",
     "passo_2_caracteristicas.png"),
    ("Análise integrada no Painel de Convergência",
     "A aba **Painel** sintetiza os resultados das três trilhas: indicadores globais, quantidade de segmentos "
     "críticos por método, gráfico de convergência metodológica, mapa interativo e o **ordenamento dos segmentos "
     "críticos**. Os filtros superiores atualizam todo o painel. Segmentos classificados como críticos por múltiplas "
     "trilhas apresentam maior robustez estatística e espacial para fins de inspeção técnica.",
     "passo_3_painel.png"),
    ("Inspeção detalhada de cada trilha metodológica",
     "**Trilha 1 (Valor Crítico):** confronta o índice observado de frequência ou severidade de cada segmento com o "
     "limite estatístico da malha analisada.  \n"
     "**Trilha 2 (Densidade de Kernel — KDE):** estima a concentração espacial contínua dos sinistros por severidade "
     "ou frequência, classificando os registros por quartis de densidade.  \n"
     "**Trilha 3 (Empírico de Bayes):** combina os registros observados com o valor previsto por regressão Binomial "
     "Negativa em função da exposição ao tráfego (VMD e extensão), corrigindo o viés de regressão à média.  \n"
     "Cada aba disponibiliza o mapa temático e a tabela completa de parâmetros por segmento.",
     "passo_4_trilha.png"),
    ("Exportação de relatórios e planilhas",
     "Ao final da página, o **relatório executivo em PDF** consolida os indicadores, mapas, gráficos de convergência, "
     "fichas técnicas dos segmentos de maior criticidade, limitações dos dados e memória metodológica. A **planilha "
     "de resultados** exporta as tabelas completas de todas as trilhas e o ordenamento geral. Na seção "
     "**Configurações das análises**, é possível ajustar os pesos da UPS e os parâmetros específicos de cada método.",
     "passo_5_relatorio.png"),
]
GLOSSARIO = [
    ("Segmento", "subdivisão da via com extensão padronizada (1 km por recomendação do Manual), adotada como unidade "
                 "espacial de referência para contagem e modelagem de sinistros."),
    ("UPS", "Unidade Padrão de Severidade: pondera os sinistros do período conforme a gravidade, adotando como padrão "
            "os pesos 1 (sem vítima), 4 (com vítima ferida) e 28 (com vítima fatal)."),
    ("Segmento crítico", "segmento cujo indicador de acidentalidade supera o limiar estatístico ou espacial definido "
                         "pela trilha metodológica, constituindo indicação técnica para diagnóstico de engenharia."),
    ("Convergência", "quantidade de trilhas metodológicas que classificam simultaneamente o mesmo segmento como "
                     "crítico. Maior convergência indica maior consistência da identificação."),
    ("VMD", "Volume Médio Diário anual de veículos nos dois sentidos. Na segmentação automática das rodovias federais, "
            "utiliza-se a base pública modelada pelo PNCT/DNIT; vias urbanas do OpenStreetMap não dispõem de VMD."),
    ("SNV", "Sistema Nacional de Viação, base cartográfica oficial das rodovias federais mantida pelo DNIT."),
]


def botao_manual(rotulo: str, key: str) -> None:
    """Link para o Manual de Utilização (PDF servido pelo próprio app), se o arquivo estiver na pasta static/."""
    if os.path.exists(MANUAL):
        st.link_button(rotulo, URL_MANUAL, key=key, help="Abre o Manual de Utilização (PDF) numa nova aba.")


def mostrar_guia() -> None:
    """Primeiros passos: apresentação estruturada do fluxo de análise, com imagens e dois estudos de caso."""
    st.button("← Voltar para a análise", on_click=lambda: st.session_state.update(guia=False))
    st.header("Primeiros passos")
    st.markdown("O **SISegC Rodoviário** realiza a identificação e o ordenamento de segmentos críticos da malha "
                "viária a partir de registros históricos de sinistros, aplicando as três trilhas metodológicas do "
                "*Manual de Identificação de Segmentos Críticos Rodoviários*. O fluxo de trabalho compreende três "
                "etapas: seleção e segmentação dos dados, verificação de consistência e avaliação integrada dos "
                "resultados. Para explorar o funcionamento do sistema, selecione um dos estudos de caso abaixo:")
    anos_prf = dp.anos_completos_prf()[-3:]
    info = dp.exemplo_urbano()
    c1, c2 = st.columns(2)
    with c1.container(border=True):
        st.markdown("#### 🛣️ Rodovias Federais")
        st.markdown(f"Sinistros da **PRF** no **Distrito Federal**, de {anos_prf[0]} a {anos_prf[-1]}, na malha do "
                    "SNV e com o VMD do PNCT.")
        st.button("Abrir o exemplo de rodovia", on_click=abrir_exemplo, args=("rodovia",), type="primary",
                  width="stretch")
    with c2.container(border=True):
        st.markdown("#### 🏙️ Área Urbana")
        if info:
            st.markdown(f"{_br(info['sinistros'])} sinistros do **{info['fonte']}** em **{info['nome']}**, de "
                        f"{info['anos'][0]} a {info['anos'][-1]}.")
        st.button("Abrir o exemplo urbano", on_click=abrir_exemplo, args=("urbano",), type="primary",
                  width="stretch", disabled=info is None)
        if info:
            st.caption(f"Dados abertos do {info['fonte']}, sob a licença {info['licenca']}; recorte de "
                       f"{info['nome']} convertido para o formato do app.")
    for i, (titulo, texto, imagem) in enumerate(PASSOS_GUIA, start=1):
        st.markdown("---")
        st.markdown(f"### {i}. {titulo}")
        texto_col, imagem_col = st.columns([2, 3])
        texto_col.markdown(texto)
        caminho = os.path.join(PASTA_GUIA, imagem)
        if os.path.exists(caminho):
            imagem_col.image(caminho)
    st.markdown("---")
    with st.expander("Termos usados no app"):
        st.markdown("\n".join(f"- **{termo}:** {texto}" for termo, texto in GLOSSARIO))
    st.markdown("O **Manual de Utilização** detalha cada tela, os métodos e as limitações.")
    botao_manual("Abrir o Manual de Utilização (PDF)", key="manual_guia")
    st.button("← Voltar para a análise", on_click=lambda: st.session_state.update(guia=False), key="voltar_fim")


def entrada_planilha() -> None:
    """“Outras formas de entrada”, na barra lateral: planilha de segmentos já pronta e o formulário para inserir
    ou corrigir um segmento. Roda antes da segmentação automática, que só refaz os segmentos quando a UF, os
    anos ou os arquivos mudam."""
    with st.expander("Outras formas de entrada", expanded=st.session_state.fonte == "planilha"):
        st.markdown("**Planilha de segmentos**")
        arquivo = st.file_uploader("Planilha já dividida em segmentos (CSV ou Excel)", type=["csv", "xlsx"],
                                   key=f"upload_{st.session_state.uploader_key}")
        if arquivo is not None:
            ident = [arquivo.name, arquivo.size, getattr(arquivo, "file_id", None)]
            if st.session_state.arquivo_id != ident:          # processa só quando o arquivo muda
                limpar_resultados()
                st.session_state.update(msgs_segmentacao=None, fonte="planilha",
                                        descricao_fonte=f"Planilha de segmentos: {arquivo.name}.")
                try:
                    dados, avisos = adaptar_planilha(ler_arquivo(arquivo.name, arquivo.getvalue()))
                    avisos = avisos_sem_extensao(dados, avisos)
                    st.session_state.update(dados=dados, avisos_entrada=avisos, erro_entrada=None, arquivo_id=ident)
                except ErroEntrada as e:
                    st.session_state.update(dados=None, avisos_entrada=[], erro_entrada=str(e), arquivo_id=ident)
                except Exception as e:  # noqa: BLE001
                    st.session_state.update(dados=None, avisos_entrada=[], arquivo_id=ident,
                                            erro_entrada=f"Não foi possível ler a planilha ({type(e).__name__}: {e}).")
            if st.session_state.erro_entrada:         # o resumo e os avisos ficam em “Características dos dados”
                st.error(f"❌ {st.session_state.erro_entrada}")

        botoes_modelo("segmentos")

        st.markdown("**Inserir ou corrigir segmento**")
        with st.form(key="formulario_trecho", clear_on_submit=True):
            segmento = st.text_input("ID do segmento*", help="Um ID já existente substitui o registro anterior.")
            st.markdown("**Georreferenciamento**")
            latitude = st.number_input("Latitude", value=None, min_value=-90.0, max_value=90.0, format="%.6f")
            longitude = st.number_input("Longitude", value=None, min_value=-180.0, max_value=180.0, format="%.6f")
            st.markdown("**Dados do Segmento**")
            extensao = st.number_input("Extensão (km)", min_value=0.01, value=1.0, format="%.3f")
            volume = st.number_input("VMD (veículos/dia)", min_value=0, value=None)
            n_anos = st.number_input("Anos de dados", min_value=1, max_value=20, value=3)
            st.markdown("**Dados de Sinistros (soma do período)**")
            sem_vitima = st.number_input("Sem vítima*", min_value=0, value=None)
            com_vitima = st.number_input("Com vítima*", min_value=0, value=None)
            com_obito = st.number_input("Com óbito*", min_value=0, value=None)
            if st.form_submit_button("➕ Adicionar registro"):
                if not segmento or sem_vitima is None or com_vitima is None or com_obito is None:
                    st.error("Preencha os campos obrigatórios (*)")
                else:
                    novo = pd.DataFrame([{
                        "segmento_id": segmento.strip(), "latitude": latitude if latitude is not None else np.nan,
                        "longitude": longitude if longitude is not None else np.nan, "extensao_trecho": extensao,
                        "volume_trafego": volume if volume is not None else np.nan, "n_anos": n_anos,
                        "sem_vitima": sem_vitima, "com_vitima": com_vitima, "com_obito": com_obito,
                    }])
                    atual = st.session_state.dados
                    if atual is not None and segmento.strip() in set(atual["segmento_id"]):
                        atual = atual[atual["segmento_id"] != segmento.strip()]
                        st.success(f"Registro '{segmento}' atualizado!")
                    else:
                        st.success(f"Registro '{segmento}' adicionado!")
                    st.session_state.dados = novo if atual is None else pd.concat([atual, novo], ignore_index=True)
                    limpar_resultados()


# --- 3. BARRA LATERAL: ENTRADA DE DADOS ---
with st.sidebar:
    if os.path.exists(LOGO):          # marcas do projeto: ver assets/LEIA-ME.md
        st.image(LOGO, width="stretch")
    else:
        st.markdown(
            """<div style="text-align: center; margin-bottom: 25px;">
            <div style="background-color: #0988C3; height: 4px; width: 40px; margin: 0 auto 10px auto;
                        border-radius: 2px;"></div>
            <h2 style="color: #0988C3; margin: 0; padding: 0; font-weight: 700; font-size: 1.4rem;">
                SISegC Rodoviário</h2>
            <h3 style="color: #1A7F4B; margin: 0; padding: 0; font-weight: 300; font-size: 0.95rem;">
                Sistema de Identificação de Segmentos Críticos Rodoviários</h3>
            </div>""",
            unsafe_allow_html=True,
        )
    st.markdown("---")
    st.header("Entrada de dados")
    chave_up = st.session_state.uploader_key
    dica_inicio = None
    if not dp.disponivel():
        st.error("A pasta dados_publicos, com a malha do SNV e os sinistros da PRF, não foi encontrada. Gere-a com "
                 "ferramentas/preparar_dados.py ou use uma planilha de segmentos em “Outras formas de entrada”.")
        entrada_planilha()
    else:
        curto, detalhes = texto_fontes(dp.versoes())
        st.caption(curto, help=detalhes)
        sinistros = None
        lidos = True
        exemplo = None
        with st.expander("Usar meus dados de sinistros", expanded=st.session_state.exemplo == "urbano"):
            st.caption("Planilha com latitude, longitude, data (ou ano) e gravidade de cada sinistro, de qualquer via: "
                       "municipal, estadual ou federal. Sem ela, valem os sinistros da PRF, que cobrem só as rodovias "
                       "federais. Os modelos mostram o formato.")
            arqs_sin = st.file_uploader("Sinistros (.csv, .xlsx ou .zip)", type=["csv", "zip", "xlsx"],
                                        accept_multiple_files=True, key=f"sin_{chave_up}")
            if arqs_sin:
                st.session_state.exemplo = None             # os arquivos enviados valem mais que o exemplo
                try:
                    sinistros = sinistros_lidos(_chave(arqs_sin), arqs_sin)
                    st.success(f"{_br(len(sinistros))} sinistros lidos do(s) arquivo(s) enviado(s).")
                except Exception as e:  # noqa: BLE001
                    lidos = False
                    st.error(f"❌ Não foi possível ler os sinistros ({type(e).__name__}: {e}).")
            elif st.session_state.exemplo == "urbano" and dp.exemplo_urbano():
                exemplo = dp.exemplo_urbano()
                sinistros = sinistros_exemplo()
                st.info(f"Exemplo urbano dos Primeiros passos: {_br(len(sinistros))} sinistros do {exemplo['fonte']} "
                        f"em {exemplo['nome']}. Envie seus sinistros acima para trocar.")
                st.button("Sair do exemplo", on_click=limpar_tudo, key="sair_exemplo", width="stretch")
            grande = sinistros is not None and area_grande(sinistros)
            residenciais = st.checkbox("Incluir ruas residenciais", value=not grande,
                                       key=f"res_{chave_up}_{_chave(arqs_sin or [])}",
                                       help="As vias fora do SNV vêm do OpenStreetMap. Sinistros urbanos costumam "
                                            "estar em ruas residenciais.")
            if grande:
                st.caption("Os sinistros cobrem uma área grande: as ruas residenciais começam desmarcadas, porque com "
                           "elas uma UF inteira passa de 1 milhão de segmentos e a análise leva vários minutos.")
            botoes_modelo("sinistros")
        entrada_planilha()                              # entre os sinistros próprios e o bloco avançado
        with st.expander("Atualizar a malha ou o VMD (avançado)"):
            st.caption("Para usar uma versão do SNV ou do VMD mais nova que a embutida.")
            arqs_snv = st.file_uploader("SNV do DNIT (shapefile em .zip, ou .shp, .shx, .dbf e .prj)",
                                        type=["zip", "shp", "shx", "dbf", "prj", "cpg"], accept_multiple_files=True,
                                        key=f"snv_{chave_up}")
            arq_vmd = st.file_uploader("VMD por trecho do SNV (planilha de modelagem do PNCT)", type=["xlsx"],
                                       key=f"vmd_{chave_up}")
        snv_enviado = vmd_enviado = None
        try:
            if arqs_snv:
                snv_enviado = snv_preparado(_chave(arqs_snv), arqs_snv)
            if arq_vmd is not None:
                vmd_enviado = vmd_pnct(_chave([arq_vmd]), arq_vmd)
        except Exception as e:  # noqa: BLE001
            lidos = False
            st.error(f"❌ Não foi possível ler os arquivos ({type(e).__name__}: {e}).")
        if lidos:
            proprios = sinistros is not None
            ufs_disp = sorted(snv_enviado["sg_uf"].dropna().unique()) if snv_enviado is not None else dp.ufs()
            sem_coluna_ano = False
            if proprios:      # avisos da leitura: em “Características dos dados carregados”
                sem_coluna_ano = bool(sinistros.attrs.get("sem_coluna_ano"))
                anos_disp = sorted(int(a) for a in sinistros["ano"].dropna().unique())
                anos_padrao = anos_disp[-3:]
                if not anos_disp and not sem_coluna_ano:
                    st.error("❌ Nenhum sinistro com data ou ano reconhecido. Use uma coluna data (DD/MM/AAAA ou "
                             "AAAA-MM-DD) ou ano; veja o Modelo Preenchido em “Usar meus dados de sinistros”.")
                # pré-seleciona automaticamente a UF quando a planilha enviada informa UF reconhecida
                if arqs_sin and "uf" in sinistros and sinistros["uf"].notna().any():
                    chave_sin_uf = _chave(arqs_sin)
                    if st.session_state.get("_sin_uf_auto") != chave_sin_uf:
                        ufs_arq = [u for u in sorted(sinistros["uf"].dropna().unique()) if u in ufs_disp]
                        if ufs_arq and not st.session_state.get(f"ufs_{chave_up}"):
                            st.session_state[f"ufs_{chave_up}"] = ufs_arq
                        st.session_state["_sin_uf_auto"] = chave_sin_uf
            else:
                anos_disp, anos_padrao = dp.anos_prf(), dp.anos_completos_prf()[-3:]
            ufs = st.multiselect("UF", ufs_disp, placeholder="Escolha a UF", key=f"ufs_{chave_up}")
            anos = st.multiselect("Anos", anos_disp, default=anos_padrao, key=f"anos_{chave_up}_{int(proprios)}",
                                  disabled=sem_coluna_ano,
                                  help="Período de análise (quando a planilha não informa data/ano, todos os registros "
                                       "são considerados num período de 3 anos)." if sem_coluna_ano
                                  else "O ano mais recente da PRF costuma estar incompleto.")
            comprimento = st.number_input("Comprimento do segmento (km)", min_value=LIMITES_COMPRIMENTO[0],
                                          max_value=LIMITES_COMPRIMENTO[1], value=COMPRIMENTO_PADRAO, step=0.1,
                                          format="%.1f", help="O Manual recomenda segmentos de 1 km.",
                                          key=f"comp_{chave_up}")
            com_km = not proprios or bool(sinistros.attrs.get("com_km"))
            por_sentido = st.checkbox("Separar por sentido da via", disabled=not com_km, key=f"sent_{chave_up}",
                                      help="Só para dados com o sentido da via, como os da PRF.") and com_km
            usar_vmd = st.checkbox("Usar o volume de tráfego (VMD)", value=True, key=f"usavmd_{chave_up}",
                                   help="O VMD vem da modelagem do PNCT/DNIT, uma estimativa (a embutida é de 2019). "
                                        "Desmarque se não confiar nele: as Trilhas 1 (frequência e severidade) e 2 "
                                        "não usam o VMD; sem ele, a Trilha 3 e os métodos de taxa da Trilha 1 não "
                                        "rodam.")
            if ufs and (anos or sem_coluna_ano):
                chave_sinistros = _chave(arqs_sin or []) or ((("exemplo", exemplo["nome"]),) if exemplo else ())
                chave_arquivos = (chave_sinistros, _chave(arqs_snv or []),
                                  _chave([arq_vmd]) if arq_vmd is not None else ())
                chave_auto = (tuple(ufs), tuple(sorted(anos)), float(comprimento), bool(por_sentido),
                              bool(residenciais) and proprios, chave_arquivos)
                chave_estado = (*chave_auto, bool(usar_vmd))      # trocar só o VMD não refaz a segmentação
                if chave_estado != st.session_state.auto_chave:
                    try:
                        with st.status("Segmentando a malha e localizando os sinistros...") as andamento:
                            dados = segmentacao_automatica(*chave_auto, _sinistros=sinistros, _snv=snv_enviado,
                                                           _vmd=vmd_enviado, _andamento=andamento).copy()
                            andamento.update(label="Segmentação pronta.", state="complete", expanded=False)
                        if not usar_vmd:
                            dados = sem_vmd(dados)
                        resumo = dados.attrs["resumo"]
                        limpar_resultados()
                        periodo_txt = (
                            ", ".join(map(str, sorted(anos))) if anos else "período de 3 anos (sem coluna ano)"
                        )
                        st.session_state.update(
                            dados=dados, avisos_entrada=[], erro_entrada=None, arquivo_id=None, fonte="auto",
                            msgs_segmentacao=(mensagens_leitura(sinistros) if proprios else [])
                            + mensagens_segmentacao(resumo, bool(residenciais) if proprios else None),
                            descricao_fonte=(f"Segmentação automática: {', '.join(ufs)}, "
                                             f"{periodo_txt}, sinistros "
                                             + (f"do exemplo urbano: {exemplo['fonte']}, CC BY 4.0, recorte de "
                                                f"{exemplo['nome']}" if exemplo
                                                else "enviados" if proprios else "da PRF") + "."))
                    except ValueError as e:
                        limpar_resultados()
                        st.session_state.update(dados=None, fonte="auto", msgs_segmentacao=[("error", str(e))])
                    st.session_state.auto_chave = chave_estado
            else:
                if st.session_state.fonte == "auto":
                    limpar_resultados()
                    st.session_state.update(dados=None, msgs_segmentacao=None, fonte=None)
                st.session_state.auto_chave = None
                if ufs:
                    dica_inicio = "Escolha ao menos um ano na barra lateral."
                elif proprios:
                    dica_inicio = (f"Planilha com {_br(len(sinistros))} sinistros carregada em “Usar meus dados de "
                                   "sinistros”. Selecione a UF correspondente na barra lateral para segmentar a malha "
                                   "e iniciar as análises.")

    st.markdown("---")
    st.button("Primeiros passos", on_click=lambda: st.session_state.update(guia=True),
              help="Como usar o app, com imagens e dois exemplos prontos.")
    botao_manual("Manual de Utilização (PDF)", key="manual_barra")
    st.button("Limpar todos os registros", on_click=limpar_tudo)
    st.caption(f"{SIGLA_SISTEMA}, versão {VERSAO}")

# --- 4. PAINEL PRINCIPAL ---
st.title(NOME_SISTEMA)
if st.session_state.guia:
    mostrar_guia()
    st.stop()

with st.expander("⚙️ Configurações das análises"):
    aba_pesos, *abas_config = st.tabs(["Pesos UPS"] + [rotulo_trilha(c) for c in ORDEM_TRILHAS])
    aba_config = dict(zip(ORDEM_TRILHAS, abas_config))
    with aba_pesos:
        st.info("Pesos do Manual: 1 (sem vítima), 4 (com vítima) e 28 (com óbito). Valem para as três trilhas.")
        c1, c2, c3 = st.columns(3)
        peso_sv = c1.slider("Peso Sem Vítima", 1, 10, PESOS_UPS_PADRAO["sem_vitima"])
        peso_cv = c2.slider("Peso Com Vítima", 1, 50, PESOS_UPS_PADRAO["com_vitima"])
        peso_co = c3.slider("Peso Com Óbito", 1, 100, PESOS_UPS_PADRAO["com_obito"])
    with aba_config["vc"]:
        # frequência primeiro, como no Manual; a severidade é o padrão quando há a gravidade dos sinistros
        metodo_vc = st.selectbox("Método", list(METODOS_VC), index=list(METODOS_VC).index("severidade"),
                                 format_func=METODOS_VC.get)
        nivel_vc = st.number_input(
            "Nível de confiança (%)", min_value=50.0, max_value=99.9, value=95.0, step=0.5, format="%.1f",
            help="O nível de confiança mais utilizado na literatura e recomendado pelo Manual (Tabela 3.1) é 95% "
                 "(k = 1,645). Outros valores tabelados no Manual: 85% (k = 1,036), 90% (k = 1,282), 99% (k = 2,326) "
                 "e 99,5% (k = 2,576).",
        )
        st.caption(f"Coeficiente normal unicaudal correspondente: k = {_br(k_por_nivel(nivel_vc), 3)}")
        sinal_vc = st.radio("Correção de continuidade", [-1, 1], horizontal=True,
                            format_func=lambda s: "−0,5/E (Manual)" if s < 0 else "+1/(2E) (literatura clássica)",
                            help="O Manual adota −0,5/E (Eqs. 3.3 e 3.6); manuais clássicos (HSM) adotam +1/(2E).")
        excluir_zeros = st.checkbox(
            "Excluir segmentos sem sinistros", value=False,
            help="Por recomendação do Manual, todos os segmentos da malha (inclusive os sem sinistros) devem ser "
                 "incluídos no cálculo da média; marque apenas para análises específicas entre segmentos "
                 "com sinistros.",
        )
    with aba_config["bayes"]:
        variavel_eb = st.selectbox(
            "Variável de análise", list(VARIAVEIS_ANALISE), format_func=VARIAVEIS_ANALISE.get,
            key="var_eb", help="Análise por severidade (UPS) ou por frequência (total de sinistros).",
        )
        metodo_eb = st.selectbox("Método", list(METODOS_EB), format_func=METODOS_EB.get)
        criterio_eb = st.radio("Critério de criticidade", list(CRITERIOS), format_func=CRITERIOS.get,
                               index=list(CRITERIOS).index(CRITERIO_PADRAO[metodo_eb]))
        nivel_eb = st.number_input(
            "Nível de confiança do critério z (%)", min_value=50.0, max_value=99.9, value=97.5, step=0.5,
            format="%.1f", key="nivel_eb", disabled=criterio_eb != "z",
            help="O Manual adota z = 1,96, que corresponde a 97,5% (unicaudal), o padrão. Outros níveis usam a "
                 "Normal padrão (ex.: 95% → z = 1,645; 99% → z = 2,326).",
        )
        if criterio_eb == "z":
            st.caption(f"Valor de z correspondente: {_br(k_por_nivel(nivel_eb), 3)}")
    with aba_config["kde"]:
        variavel_kde = st.selectbox(
            "Variável de análise", list(VARIAVEIS_ANALISE), format_func=VARIAVEIS_ANALISE.get,
            key="var_kde", help="Análise por severidade (UPS) ou por frequência (total de sinistros).",
        )
        c1, c2, c3 = st.columns(3)
        banda = c1.number_input("Largura de banda (m)", min_value=100, max_value=10000, value=1000, step=100)
        celula = c2.number_input("Tamanho da célula (m)", min_value=50, max_value=5000, value=500, step=50)
        percentil = c3.number_input("Percentil de corte", min_value=50, max_value=99, value=75, step=1)

opcoes = {"pesos": [peso_sv, peso_cv, peso_co], "vc": [metodo_vc, nivel_vc, sinal_vc, excluir_zeros],
          "eb": [metodo_eb, criterio_eb, nivel_eb, variavel_eb], "kde": [banda, celula, percentil, variavel_kde]}

dados = st.session_state.dados
mostrar_caracteristicas(dados)
if dados is None or dados.empty:
    erros = [texto for tipo, texto in (st.session_state.msgs_segmentacao or []) if tipo == "error"]
    if erros and st.session_state.fonte == "auto":
        st.error(f"❌ {erros[0]}")
    else:
        st.info("ℹ️ " + (dica_inicio or "Escolha a UF na barra lateral: o app segmenta a malha e analisa os "
                                         "sinistros sozinho, com os dados públicos embutidos. Se já tiver os segmentos "
                                         "numa planilha, use “Outras formas de entrada”."))
    st.button("Novo por aqui? Veja os primeiros passos e abra um exemplo", type="primary",
              on_click=lambda: st.session_state.update(guia=True))
    st.stop()

sig = assinatura(dados, opcoes)

if st.session_state.assinatura != sig:         # dados ou opções novos: as trilhas rodam de novo
    limpar_resultados()
    with st.spinner("Calculando as três trilhas..."):
        df_proc = preparar_dados(dados, peso_sv, peso_cv, peso_co)
        tarefas = {
            "vc": lambda: aplicar_valor_critico(df_proc, nivel_confianca=nivel_vc, metodo=metodo_vc,
                                                sinal_correcao=sinal_vc, incluir_sem_sinistros=not excluir_zeros),
            "kde": lambda: aplicar_kernel(df_proc, bandwidth=float(banda), cell_size=float(celula),
                                          percentil=float(percentil), variavel=variavel_kde),
            "bayes": lambda: aplicar_bayes(df_proc, metodo=metodo_eb, criterio=criterio_eb,
                                           nivel_confianca=nivel_eb, variavel=variavel_eb),
        }
        for chave, tarefa in tarefas.items():
            try:
                res = tarefa()
                st.session_state.resultados[chave] = res
                st.session_state.avisos[chave] = res.attrs.get("avisos", [])
            except ValueError as e:
                st.session_state.erros[chave] = str(e) + dica_erro(str(e), dados)
            except Exception as e:  # noqa: BLE001
                st.session_state.erros[chave] = f"Erro inesperado ({type(e).__name__}): {e}"
                traceback.print_exc()
        tabelas = {chave: (tabela_resultado(chave, res.head(LIMITE_LINHAS_TABELA), dados), len(res))
                   for chave, res in st.session_state.resultados.items()}
        st.session_state.update(df_proc=df_proc, assinatura=sig, tabelas=tabelas)

# --- 5. RESULTADOS ---
if st.session_state.assinatura == sig:
    st.subheader("📊 Resultados das Análises")
    resultados = st.session_state.resultados
    aba_painel, *abas = st.tabs(["Painel"] + [rotulo_trilha(c) for c in ORDEM_TRILHAS])
    with aba_painel:
        mostrar_painel(resultados, st.session_state.df_proc, sig)
    for chave, aba in zip(ORDEM_TRILHAS, abas):
        with aba:
            if chave in st.session_state.erros:
                st.warning(st.session_state.erros[chave])
                continue
            res = resultados[chave]
            for aviso in st.session_state.avisos.get(chave, []):
                st.caption(f"⚠️ {aviso}")
            st.metric("Segmentos críticos", f"{int(res['Critico'].sum())} de {len(res)}")
            if chave == "kde" and res.attrs.get("coincidencia") is not None:
                coincidencia = f"{res.attrs['coincidencia']:.1f}".replace(".", ",")
                rot_soma = "da UPS" if res.attrs.get("variavel", "severidade") == "severidade" else "de sinistros"
                st.caption(f"Avaliação do Manual: em {coincidencia}% dos sinistros, o quartil superior da densidade "
                           f"coincide com o da soma {rot_soma} na célula.")
            if chave == "vc":
                st.markdown("##### Mapa: críticos em vermelho")
                aviso_mapa(res)
                mostrar_mapa(chave, lambda r=res: mapa_criticos(para_mapa(r, dados), "Indice", "Índice observado"))
            elif chave == "bayes":
                st.markdown("##### Mapa: críticos em vermelho")
                aviso_mapa(res)
                mostrar_mapa(chave, lambda r=res: mapa_criticos(para_mapa(r, dados), "ajustado", "Nesperado"))
            else:
                st.markdown("##### Mapa de calor (ilustrativo)")
                st.caption("Marque os quartis da densidade no controle de camadas do mapa; o 4º quartil, em "
                           "vermelho, reúne os segmentos críticos.")
                aviso_mapa(res)
                mostrar_mapa(chave, lambda r=res: mapa_kde(para_mapa(r, dados)))
            tabela, total = st.session_state.tabelas[chave]
            mostrar_tabela(tabela, total)

    if resultados:
        st.markdown("---")
        st.subheader("📄 Relatório e planilhas")
        st.caption("O relatório executivo em PDF consolida os resultados do painel para consulta externa: indicadores "
                   "principais, mapa dos segmentos críticos, análise de convergência entre as trilhas, fichas técnicas "
                   "dos 10 primeiros segmentos do ordenamento por criticidade, limitações dos dados e memória "
                   "metodológica com os parâmetros adotados. A planilha exporta todos os segmentos avaliados em cada "
                   "trilha, o ordenamento geral por criticidade e o resumo executivo.")
        st.warning("⚠️ **Nota de responsabilidade:** o relatório é processado automaticamente e não substitui a "
                   "análise técnica.")
        contexto = contexto_relatorio(opcoes)
        c1, c2 = st.columns(2)
        c1.download_button("📥 Baixar relatório PDF", type="primary",    # gerado só no clique
                           data=lambda r=resultados, proc=st.session_state.df_proc, ctx=contexto: relatorio_pdf(
                               proc, r, ctx),
                           file_name="relatorio_segmentos_criticos.pdf", mime="application/pdf",
                           on_click="ignore", width="stretch")
        nome_planilha, mime_planilha = formato_planilha(sum(len(r) for r in resultados.values()),
                                                        "resultados_segmentos_criticos")
        c2.download_button("📊 Baixar resultados (planilha)",
                           data=lambda r=resultados, d=dados, proc=st.session_state.df_proc, ctx=contexto:
                           resultados_planilha(r, d, proc, ctx)[0],
                           file_name=nome_planilha, mime=mime_planilha, on_click="ignore", width="stretch")
