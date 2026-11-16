"""Tempo e memória do app em cenários típicos e grandes, para dimensionar o servidor.

Uso, a partir da pasta do projeto:

    python ferramentas/benchmark.py [--saida benchmark.csv] [cenário ...]

Cenários (sem nenhum, roda os padrões):

* ``DF``, ``MG``, ``DF+GO``...: segmentação automática com os dados embutidos da PRF, como ao escolher a UF no app;
  ``BR`` são todas as UFs.
* ``sintetico:SP:100000``: 100 mil sinistros sorteados sobre as vias de SP (SNV e OpenStreetMap), como uma base
  estadual ou municipal enviada em “Usar meus dados de sinistros”; acrescente ``:residenciais`` para incluir as
  ruas residenciais.
* ``arquivo:caminho.xlsx:DF``: uma planilha de sinistros própria, na UF indicada (com as ruas residenciais).

Cada cenário roda num processo separado e mede o tempo de cada etapa (dados, segmentação, trilhas, mapas,
relatório PDF e planilha de resultados) e o pico de memória do processo. O app faz as mesmas etapas, com as
opções padrão das trilhas.
"""
import argparse
import io
import json
import os
import platform
import subprocess
import sys
import time
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PADRAO = ["DF", "PE", "MG", "SP", "BR", "sintetico:DF:5000:residenciais", "sintetico:SP:100000",
          "sintetico:SP:100000:residenciais", "sintetico:SP:1000000"]


def mil(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def memoria_total_gb() -> float:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30
    except (ValueError, OSError, AttributeError):    # Windows
        try:
            import psutil
            return psutil.virtual_memory().total / 2**30
        except ImportError:
            return float("nan")


def pico_mb() -> float:
    try:
        import resource
        kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return kb / 1024 / (1024 if sys.platform == "darwin" else 1)
    except ImportError:          # Windows
        try:
            import psutil
            return psutil.Process().memory_info().peak_wset / 2**20
        except (ImportError, AttributeError):
            return float("nan")


def sinistros_sinteticos(uf, n, residenciais, snv, rng):
    """``n`` sinistros sorteados sobre as vias da UF (SNV e OpenStreetMap), proporcionais à extensão."""
    import numpy as np
    import pandas as pd
    import shapely

    from utils import dados_publicos as dp
    from utils.segmentacao import _PARA_GEO

    caixa = dp.versoes()["osm"]["ufs"][uf]["bbox"]
    vias = dp.ler_vias_osm(tuple(caixa), urbanas=residenciais)
    vias = vias[vias["codigo_via"].str.startswith(f"OSM{uf}")]
    base = snv[snv["com_pista"] & snv["vl_codigo"].eq(snv["codigo_principal"]) & snv["sg_uf"].eq(uf)]
    geoms = np.concatenate([vias["geom_m"].to_numpy(), base["geom_m"].to_numpy()])
    comp = shapely.length(geoms)
    escolha = rng.choice(len(geoms), n, p=comp / comp.sum())
    pontos = shapely.line_interpolate_point(geoms[escolha], rng.uniform(0, 1, n) * comp[escolha])
    xy = shapely.get_coordinates(pontos)
    lon, lat = _PARA_GEO.transform(xy[:, 0], xy[:, 1])
    tabela = pd.DataFrame({"id": np.arange(n).astype(str), "ano": rng.choice([2023, 2024, 2025], n),
                           "latitude": lat, "longitude": lon,
                           "gravidade": rng.choice(["sem vítima", "com vítima", "com óbito"], n, p=[.66, .31, .03])})
    from utils.segmentacao import ler_sinistros_pontuais
    return ler_sinistros_pontuais(tabela)


def rodar(cenario: str) -> dict:
    """Roda um cenário neste processo e devolve tempos (s), contagens e pico de memória (MB)."""
    warnings.filterwarnings("ignore")
    sys.path.insert(0, str(RAIZ))
    import numpy as np
    import pandas as pd

    from models.trilha1_valor_critico import aplicar_valor_critico
    from models.trilha2_kernel import aplicar_kernel
    from models.trilha3_bayes import aplicar_bayes
    from utils import dados_publicos as dp
    from utils.mapas import mapa_criticos, mapa_kde
    from utils.preprocessamento import preparar_dados
    from utils.relatorio import gerar_pdf_completo
    from utils.segmentacao import ler_arquivos_sinistros, preparar_snv, retangulo, segmentar

    r = {"cenário": cenario}
    t = time.perf_counter()

    def etapa(nome):
        nonlocal t
        agora = time.perf_counter()
        r[f"{nome} (s)"] = round(agora - t, 2)
        t = agora

    partes = cenario.split(":")
    anos = dp.anos_completos_prf()[-3:]
    vias = None
    if partes[0] == "sintetico":
        uf, n, residenciais = partes[1], int(partes[2]), "residenciais" in partes
        ufs = [uf]
        snv = preparar_snv(dp.ler_snv(ufs))
        sinistros = sinistros_sinteticos(uf, n, residenciais, snv, np.random.default_rng(1))
        anos = [2023, 2024, 2025]
    elif partes[0] == "arquivo":
        caminho, ufs, residenciais = partes[1], partes[2].split("+"), True
        snv = preparar_snv(dp.ler_snv(ufs))
        sinistros = ler_arquivos_sinistros([(Path(caminho).name, Path(caminho).read_bytes())])
        anos = sorted(int(a) for a in sinistros["ano"].dropna().unique())[-3:]
    else:
        ufs = dp.ufs() if cenario == "BR" else cenario.split("+")
        snv = preparar_snv(dp.ler_snv(ufs))
        sinistros = None
    vmd = dp.ler_vmd()
    if sinistros is None:
        sinistros = dp.ler_sinistros_prf(ufs, anos)
    else:
        no_periodo = sinistros[sinistros["ano"].isin(anos)]
        vias = dp.ler_vias_osm(retangulo(no_periodo, snv, ufs), urbanas=residenciais)
    etapa("dados")

    dados = segmentar(sinistros, snv, ufs, anos, 1.0, False, vmd=vmd, vias_prontas=vias)
    etapa("segmentação")
    resumo = dados.attrs["resumo"]
    r.update(segmentos=len(dados), sinistros=int(resumo["sinistros"]), localizados=int(resumo["atribuidos"]))

    df = preparar_dados(dados, 1, 4, 28)
    resultados = {}
    for chave, f in [("vc", aplicar_valor_critico), ("kde", aplicar_kernel), ("bayes", aplicar_bayes)]:
        inicio = time.perf_counter()
        try:
            resultados[chave] = f(df)
            r[f"críticos {chave}"] = int(resultados[chave]["Critico"].sum())
        except ValueError as e:
            r[f"críticos {chave}"] = f"não roda: {str(e)[:60]}"
        r[f"trilha {chave} (s)"] = round(time.perf_counter() - inicio, 2)
    etapa("trilhas")

    for chave, res in resultados.items():       # mapas como no app: acima de 20 mil pontos, só os críticos
        geo = res if len(res) <= 20_000 else res[res["Critico"].astype(bool)].head(20_000)
        if chave == "vc":
            geo = geo.merge(dados[["segmento_id", "latitude", "longitude"]], on="segmento_id", how="left")
            m = mapa_criticos(geo, "Indice", "Índice")
        elif chave == "bayes":
            m = mapa_criticos(geo, "ajustado", "UPS esperada")
        else:
            m = mapa_kde(geo)
        if m is not None:
            m.get_root().render()
    etapa("mapas")

    gerar_pdf_completo(df, resultados, None)
    etapa("relatório PDF")

    buf = io.BytesIO()
    if sum(len(x) for x in resultados.values()) <= 50_000:
        with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
            for chave, res in resultados.items():
                res.to_excel(w, sheet_name=chave, index=False)
    else:
        import zipfile
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for chave, res in resultados.items():
                z.writestr(f"{chave}.csv", res.to_csv(index=False, sep=";", decimal=","))
    etapa("planilha de resultados")

    r["total (s)"] = round(sum(v for k, v in r.items() if k.endswith("(s)") and not k.startswith("trilha ")), 2)
    r["pico de memória (MB)"] = round(pico_mb())
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cenarios", nargs="*", default=PADRAO)
    ap.add_argument("--saida", default="benchmark.csv")
    ap.add_argument("--um", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.um:
        print(json.dumps(rodar(a.um), ensure_ascii=False))
        return

    import pandas as pd
    maquina = (f"{platform.node()} | {platform.processor() or platform.machine()} | {os.cpu_count()} núcleos | "
               f"{memoria_total_gb():.0f} GB")
    print(f"Máquina: {maquina}\n")
    linhas = []
    for c in a.cenarios:
        print(f"→ {c} ...", flush=True)
        p = subprocess.run([sys.executable, __file__, "--um", c], capture_output=True, text=True, cwd=RAIZ)
        if p.returncode != 0:
            erro = (p.stderr.strip().splitlines() or ["sem mensagem"])[-1]
            if p.returncode < 0 or "MemoryError" in p.stderr:
                erro = "faltou memória" if "MemoryError" in p.stderr or p.returncode == -9 else erro
            print(f"  falhou: {erro}")
            linhas.append({"cenário": c, "erro": erro})
            continue
        r = json.loads(p.stdout.strip().splitlines()[-1])
        print(f"  {mil(r['segmentos'])} segmentos, {mil(r['sinistros'])} sinistros: {r['total (s)']} s, "
              f"{mil(r['pico de memória (MB)'])} MB")
        linhas.append(r)
    tabela = pd.DataFrame(linhas)
    tabela.insert(0, "máquina", maquina)
    tabela.to_csv(a.saida, index=False, sep=";", decimal=",", encoding="utf-8-sig")
    print(f"\nResultados em {a.saida}")


if __name__ == "__main__":
    main()
