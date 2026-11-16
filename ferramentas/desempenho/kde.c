/*
 * Trilha 2 (KDE) em C, com o mesmo algoritmo do app (models/trilha2_kernel.py), para comparar o desempenho
 * entre linguagens (ver comparar_linguagens.py).
 *
 * Grade de células de `celula` m a partir de (min - h); densidade calculada só nas células que têm sinistros,
 * com núcleo gaussiano truncado em `raio` x h e normalização por n x 2 x pi x h^2; cada sinistro recebe a
 * densidade da sua célula. Os vizinhos de cada célula vêm de uma grade de busca com caixas de raio x h.
 *
 * Uso:    kde <entrada.bin> <saida.bin> [h=1000] [celula=500] [raio=3]
 * Entrada: n (float64) seguido de x[n], y[n] e peso[n] (float64, metros na projeção de Mercator do Manual).
 * Saída:   densidade[n] (float64). Imprime {"tempo": s, "memoria_mb": MB} (tempo só do cálculo).
 * Compilar: gcc -O2 -fopenmp -o kde kde.c -lm   (sem OpenMP, roda num núcleo só)
 */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef struct {
    int64_t chave;
    int64_t indice;
} Par;

static double agora(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (double)t.tv_sec + 1e-9 * (double)t.tv_nsec;
}

static int comparar(const void *a, const void *b) {
    int64_t x = ((const Par *)a)->chave, y = ((const Par *)b)->chave;
    return (x > y) - (x < y);
}

static double pico_mb(void) {          /* VmHWM do /proc (Linux); -1 se não houver */
    FILE *f = fopen("/proc/self/status", "r");
    char linha[256];
    double kb = -1;
    if (!f) return -1;
    while (fgets(linha, sizeof linha, f))
        if (strncmp(linha, "VmHWM:", 6) == 0) kb = atof(linha + 6);
    fclose(f);
    return kb < 0 ? -1 : kb / 1024.0;
}

/* primeira posição com chave >= alvo num vetor ordenado */
static int64_t inicio_de(const Par *v, int64_t n, int64_t alvo) {
    int64_t a = 0, b = n;
    while (a < b) {
        int64_t m = a + (b - a) / 2;
        if (v[m].chave < alvo) a = m + 1; else b = m;
    }
    return a;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "uso: kde <entrada.bin> <saida.bin> [h] [celula] [raio]\n");
        return 1;
    }
    double h = argc > 3 ? atof(argv[3]) : 1000.0, cs = argc > 4 ? atof(argv[4]) : 500.0;
    double rc = argc > 5 ? atof(argv[5]) : 3.0;
    FILE *f = fopen(argv[1], "rb");
    double nd;
    if (!f || fread(&nd, sizeof(double), 1, f) != 1) { fprintf(stderr, "entrada inválida\n"); return 1; }
    int64_t n = (int64_t)nd;
    double *x = malloc(n * sizeof(double)), *y = malloc(n * sizeof(double)), *w = malloc(n * sizeof(double));
    if (fread(x, sizeof(double), n, f) != (size_t)n || fread(y, sizeof(double), n, f) != (size_t)n ||
        fread(w, sizeof(double), n, f) != (size_t)n) { fprintf(stderr, "entrada incompleta\n"); return 1; }
    fclose(f);

    double t0 = agora();
    double xmin = x[0], ymin = y[0];
    for (int64_t i = 1; i < n; i++) { if (x[i] < xmin) xmin = x[i]; if (y[i] < ymin) ymin = y[i]; }
    xmin -= h;
    ymin -= h;
    const int64_t M = 100000000;        /* separa os dois índices numa chave só */
    double B = rc * h, raio2 = B * B;

    /* célula de cada sinistro (ceil - 1, como o which.min do código R) e células únicas */
    Par *cel = malloc(n * sizeof(Par));
    for (int64_t i = 0; i < n; i++) {
        int64_t ix = (int64_t)ceil((x[i] - xmin) / cs) - 1, iy = (int64_t)ceil((y[i] - ymin) / cs) - 1;
        if (ix < 0) ix = 0;
        if (iy < 0) iy = 0;
        cel[i].chave = ix * M + iy;
        cel[i].indice = i;
    }
    qsort(cel, n, sizeof(Par), comparar);
    int64_t *dono = malloc(n * sizeof(int64_t));   /* sinistro -> célula única */
    int64_t *chaves = malloc(n * sizeof(int64_t));
    int64_t nc = 0;
    for (int64_t k = 0; k < n; k++) {
        if (k == 0 || cel[k].chave != cel[k - 1].chave) chaves[nc++] = cel[k].chave;
        dono[cel[k].indice] = nc - 1;
    }

    /* sinistros ordenados pela caixa de busca */
    Par *cx = malloc(n * sizeof(Par));
    for (int64_t i = 0; i < n; i++) {
        cx[i].chave = (int64_t)floor((x[i] - xmin) / B) * M + (int64_t)floor((y[i] - ymin) / B);
        cx[i].indice = i;
    }
    qsort(cx, n, sizeof(Par), comparar);

    double *dens = calloc(nc, sizeof(double));
#pragma omp parallel for schedule(dynamic, 256)
    for (int64_t c = 0; c < nc; c++) {
        double px = xmin + ((double)(chaves[c] / M) + 0.5) * cs, py = ymin + ((double)(chaves[c] % M) + 0.5) * cs;
        int64_t bx = (int64_t)floor((px - xmin) / B), by = (int64_t)floor((py - ymin) / B);
        double soma = 0;
        for (int64_t dx = -1; dx <= 1; dx++)
            for (int64_t dy = -1; dy <= 1; dy++) {
                int64_t alvo = (bx + dx) * M + (by + dy);
                for (int64_t k = inicio_de(cx, n, alvo); k < n && cx[k].chave == alvo; k++) {
                    int64_t i = cx[k].indice;
                    double ex = x[i] - px, ey = y[i] - py, d2 = ex * ex + ey * ey;
                    if (d2 <= raio2) soma += w[i] * exp(-0.5 * d2 / (h * h));
                }
            }
        dens[c] = soma / ((double)n * 2.0 * M_PI * h * h);
    }
    double *saida = malloc(n * sizeof(double));
    for (int64_t i = 0; i < n; i++) saida[i] = dens[dono[i]];
    double t1 = agora();

    f = fopen(argv[2], "wb");
    fwrite(saida, sizeof(double), n, f);
    fclose(f);
    printf("{\"tempo\": %.6f, \"memoria_mb\": %.1f}\n", t1 - t0, pico_mb());
    return 0;
}
