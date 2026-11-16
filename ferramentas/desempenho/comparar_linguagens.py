"""Desempenho da Trilha 2 (KDE) em Python, C e R, com o mesmo algoritmo e os mesmos dados.

Uso, a partir da pasta do projeto (precisa do gcc e do Rscript no PATH):

    python ferramentas/desempenho/comparar_linguagens.py [--saida pasta] [--repeticoes 3] [cenário ...]

Cenários (sem nenhum, roda todos):

* ``DF``, ``PE``, ``MG``: sinistros da PRF embutidos na UF, nos três últimos anos completos;
* ``BR``: os sinistros da PRF de todas as UFs, nos mesmos anos;
* ``SP1M``: 1 milhão de sinistros sorteados sobre as vias principais de SP (SNV e OpenStreetMap), como em
  ``ferramentas/benchmark.py``.

O KDE é a rotina mais pesada das trilhas: cada sinistro pesa a sua UPS (1, 4 ou 28) e a densidade é calculada
na grade de 500 m do Manual, com núcleo gaussiano de 1 km truncado em 3 km. As três versões fazem a mesma conta:

* **Python**: a função ``densidade_kde`` do app (NumPy e a KD-tree do SciPy), em um núcleo e em todos;
* **C**: ``kde.c``, compilado com ``gcc -O2 -fopenmp``, em um núcleo e em todos;
* **R**: ``kde.R``, em R puro (sem pacotes), vetorizado por caixa de busca.

Com ``--manual-r arquivo.R``, roda também o código R do Manual (que calcula a densidade em todas as células da
grade), só nos cenários de até ``--limite-manual`` sinistros. Cada versão roda num processo separado; o tempo é o
do cálculo (sem a leitura dos dados) e a memória é o pico do processo. As densidades de todas as versões são
comparadas com as do app.
"""
import argparse
import csv
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
CENARIOS = ["DF", "PE", "MG", "BR", "SP1M"]
PESOS = {"sem_vitima": 1.0, "sem vítima": 1.0, "com_vitima": 4.0, "com vítima": 4.0, "com_obito": 28.0,
         "com óbito": 28.0}


def milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def pico_mb() -> float:
    """Pico de memória do processo (VmHWM, Linux); -1 onde não houver /proc."""
    try:
        for linha in Path("/proc/self/status").read_text().splitlines():
            if linha.startswith("VmHWM:"):
                return float(linha.split()[1]) / 1024
    except OSError:
        pass
    return -1.0


def gravar(caminho: Path, x, y, w) -> None:
    with open(caminho, "wb") as f:
        np.array([len(x)], dtype=np.float64).tofile(f)
        for v in (x, y, w):
            np.asarray(v, dtype=np.float64).tofile(f)


def ler(caminho: Path):
    dados = np.fromfile(caminho, dtype=np.float64)
    n = int(dados[0])
    return dados[1:1 + n], dados[1 + n:1 + 2 * n], dados[1 + 2 * n:1 + 3 * n]


def sinistros(cenario: str):
    """Coordenadas (Mercator do Manual) e pesos UPS dos sinistros do cenário."""
    sys.path.insert(0, str(RAIZ))
    from models.trilha2_kernel import projetar_mercator
    from utils import dados_publicos as dp

    anos = dp.anos_completos_prf()[-3:]
    if cenario == "SP1M":
        import importlib.util

        from utils.segmentacao import preparar_snv
        spec = importlib.util.spec_from_file_location("benchmark", RAIZ / "ferramentas" / "benchmark.py")
        benchmark = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(benchmark)
        tabela = benchmark.sinistros_sinteticos("SP", 1_000_000, False, preparar_snv(dp.ler_snv(["SP"])),
                                                np.random.default_rng(2026))
    else:
        tabela = dp.ler_sinistros_prf(None if cenario == "BR" else [cenario], anos)
    lat = np.asarray(tabela["latitude"], dtype=float)
    lon = np.asarray(tabela["longitude"], dtype=float)
    w = tabela["gravidade"].astype(str).str.lower().map(PESOS).to_numpy(dtype=float)
    ok = np.isfinite(lat) & np.isfinite(lon) & np.isfinite(w)
    x, y = projetar_mercator(lat[ok], lon[ok])
    return x, y, w[ok]


def celulas_ocupadas(x, y, h=1000.0, cs=500.0) -> int:
    ix = np.maximum(np.ceil((x - x.min() + h) / cs) - 1, 0)
    iy = np.maximum(np.ceil((y - y.min() + h) / cs) - 1, 0)
    return len(np.unique(np.column_stack([ix, iy]), axis=0))


def celulas_da_grade(x, y, h=1000.0, cs=500.0) -> int:
    """Células da grade inteira, como no código R do Manual."""
    nx = len(np.arange(x.min() - h, x.max() + h - cs + 1e-9, cs))
    ny = len(np.arange(y.min() - h, y.max() + h - cs + 1e-9, cs))
    return nx * ny


def rodar_python(entrada: str, saida: str, nucleos: int) -> None:
    """Executado num processo filho: a função do app, com a KD-tree em ``nucleos`` núcleos (0 = todos)."""
    sys.path.insert(0, str(RAIZ))
    from scipy.spatial import cKDTree

    from models import trilha2_kernel

    class Arvore(cKDTree):
        def query_ball_point(self, *args, **kwargs):
            kwargs["workers"] = nucleos or -1
            return super().query_ball_point(*args, **kwargs)

    trilha2_kernel.cKDTree = Arvore
    x, y, w = ler(Path(entrada))
    inicio = time.perf_counter()
    dens = trilha2_kernel.densidade_kde(x, y, w)
    tempo = time.perf_counter() - inicio
    dens.astype(np.float64).tofile(saida)
    print(json.dumps({"tempo": tempo, "memoria_mb": pico_mb()}))


def executar(comando, saida: Path, n: int, ambiente=None, limite=3600):
    """Roda uma versão; devolve (tempo, memória, densidades) ou (None, None, None) se passar do limite."""
    try:
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=limite, check=True,
                                   env={**os.environ, **(ambiente or {})})
    except subprocess.TimeoutExpired:
        return None, None, None
    medida = json.loads(resultado.stdout.strip().splitlines()[-1])
    return medida["tempo"], medida["memoria_mb"], np.fromfile(saida, dtype=np.float64, count=n)


def versao(comando) -> str:
    resultado = subprocess.run(comando, capture_output=True, text=True)
    return (resultado.stdout.strip() or resultado.stderr.strip()).splitlines()[0]


def diferenca_relativa(a, b) -> float:
    escala = np.max(np.abs(b))
    return float(np.max(np.abs(a - b)) / escala) if escala > 0 else float(np.max(np.abs(a - b)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cenarios", nargs="*", default=CENARIOS)
    ap.add_argument("--saida", default="comparacao_linguagens", help="pasta dos resultados")
    ap.add_argument("--repeticoes", type=int, default=3, help="repetições nos cenários com menos de 100 mil")
    ap.add_argument("--manual-r", help="código R do Manual adaptado para a entrada binária (opcional)")
    ap.add_argument("--limite-manual", type=int, default=10_000, help="maior cenário para o código do Manual")
    ap.add_argument("--limite", type=int, default=3600, help="tempo máximo de cada execução (s)")
    args = ap.parse_args()

    pasta = Path(args.saida)
    pasta.mkdir(parents=True, exist_ok=True)
    trabalho = Path(tempfile.mkdtemp(prefix="kde_"))
    binario = trabalho / "kde"
    subprocess.run(["gcc", "-O2", "-fopenmp", "-o", str(binario), str(AQUI / "kde.c"), "-lm"], check=True)
    nucleos = os.cpu_count() or 1
    versoes = [
        ("Python (app)", 1, lambda e, s: [sys.executable, __file__, "--python", e, s, "1"], None),
        ("Python (app)", nucleos, lambda e, s: [sys.executable, __file__, "--python", e, s, "0"], None),
        ("C", 1, lambda e, s: [str(binario), e, s], {"OMP_NUM_THREADS": "1"}),
        ("C", nucleos, lambda e, s: [str(binario), e, s], {"OMP_NUM_THREADS": str(nucleos)}),
        ("R", 1, lambda e, s: ["Rscript", str(AQUI / "kde.R"), e, s], None),
    ]
    linhas = []
    for cenario in args.cenarios:
        x, y, w = sinistros(cenario)
        n = len(x)
        entrada = trabalho / f"{cenario}.bin"
        gravar(entrada, x, y, w)
        info = {"cenario": cenario, "sinistros": n, "celulas_ocupadas": celulas_ocupadas(x, y),
                "celulas_grade": celulas_da_grade(x, y)}
        print(f"\n{cenario}: {milhar(n)} sinistros, {milhar(info['celulas_ocupadas'])} células ocupadas, "
              f"{milhar(info['celulas_grade'])} na grade inteira", flush=True)
        repeticoes = args.repeticoes if n < 100_000 else 1
        referencia = None
        lista = list(versoes)
        if args.manual_r and n <= args.limite_manual:
            lista.append(("R (código do Manual)", 1, lambda e, s: ["Rscript", args.manual_r, e, s], None))
        for nome, nuc, comando, ambiente in lista:
            saida = trabalho / f"{cenario}_saida.bin"
            tempos, memoria, dens = [], None, None
            for _ in range(repeticoes if "Manual" not in nome else 1):
                tempo, memoria, dens = executar(comando(str(entrada), str(saida)), saida, n, ambiente, args.limite)
                if tempo is None:
                    break
                tempos.append(tempo)
            if referencia is None and dens is not None:
                referencia = dens
            linha = {**info, "versao": nome, "nucleos": nuc,
                     "tempo_s": round(float(np.median(tempos)), 4) if tempos else None,
                     "memoria_mb": round(memoria, 1) if memoria else None,
                     "diferenca_relativa": diferenca_relativa(dens, referencia) if dens is not None else None,
                     "concluiu": bool(tempos)}
            linhas.append(linha)
            tempo = f"{linha['tempo_s']:.3f} s" if tempos else f"não terminou em {args.limite} s"
            print(f"  {nome:22s} {nuc} núcleo(s): {tempo}, {linha['memoria_mb']} MB, "
                  f"diferença {linha['diferenca_relativa']}", flush=True)
    with open(pasta / "resultados.csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)
    (pasta / "maquina.json").write_text(json.dumps({
        "processador": platform.processor() or platform.machine(), "nucleos": nucleos,
        "sistema": platform.platform(), "python": platform.python_version(),
        "gcc": versao(["gcc", "--version"]), "r": versao(["Rscript", "--version"]),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nResultados em {pasta / 'resultados.csv'}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--python":
        rodar_python(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    else:
        main()
