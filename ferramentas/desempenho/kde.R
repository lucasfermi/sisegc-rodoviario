# Trilha 2 (KDE) em R, com o mesmo algoritmo do app (models/trilha2_kernel.py) e da versão em C (kde.c), para
# comparar o desempenho entre linguagens (ver comparar_linguagens.py).
#
# Grade de células de `celula` m a partir de (min - h); densidade calculada só nas células que têm sinistros,
# com núcleo gaussiano truncado em `raio` x h e normalização por n x 2 x pi x h^2; cada sinistro recebe a
# densidade da sua célula. As células são processadas por caixa de busca (raio x h), com operações vetoriais.
#
# Uso:     Rscript kde.R <entrada.bin> <saida.bin> [h=1000] [celula=500] [raio=3]
# Entrada: n (float64) seguido de x[n], y[n] e peso[n] (float64). Saída: densidade[n] (float64).
# Imprime {"tempo": s, "memoria_mb": MB} (tempo só do cálculo).

args <- commandArgs(trailingOnly = TRUE)
h <- if (length(args) > 2) as.numeric(args[3]) else 1000
cs <- if (length(args) > 3) as.numeric(args[4]) else 500
rc <- if (length(args) > 4) as.numeric(args[5]) else 3

con <- file(args[1], "rb")
n <- as.integer(readBin(con, "double", n = 1))
x <- readBin(con, "double", n = n)
y <- readBin(con, "double", n = n)
w <- readBin(con, "double", n = n)
close(con)

pico_mb <- function() {
  status <- tryCatch(readLines("/proc/self/status"), error = function(e) character())
  linha <- grep("^VmHWM:", status, value = TRUE)
  if (length(linha) == 0) return(-1)
  as.numeric(gsub("[^0-9]", "", linha)) / 1024
}

inicio <- proc.time()[["elapsed"]]
xmin <- min(x) - h
ymin <- min(y) - h
M <- 1e8                                          # separa os dois índices numa chave só
ix <- pmax(ceiling((x - xmin) / cs) - 1, 0)
iy <- pmax(ceiling((y - ymin) / cs) - 1, 0)
chave <- ix * M + iy
celulas <- unique(chave)
dono <- match(chave, celulas)
cx <- xmin + (celulas %/% M + 0.5) * cs
cy <- ymin + (celulas %% M + 0.5) * cs

B <- rc * h
caixa_ponto <- floor((x - xmin) / B) * M + floor((y - ymin) / B)
caixa_celula <- floor((cx - xmin) / B) * M + floor((cy - ymin) / B)
pontos_por_caixa <- split(seq_len(n), sprintf("%.0f", caixa_ponto))
celulas_por_caixa <- split(seq_along(celulas), sprintf("%.0f", caixa_celula))

dens <- numeric(length(celulas))
for (k in names(celulas_por_caixa)) {
  ck <- as.numeric(k)
  bx <- ck %/% M
  by <- ck %% M
  vizinhas <- sprintf("%.0f", c(outer(((bx - 1):(bx + 1)) * M, (by - 1):(by + 1), "+")))
  idx <- unlist(pontos_por_caixa[vizinhas], use.names = FALSE)
  if (length(idx) == 0) next
  ic <- celulas_por_caixa[[k]]
  dx <- outer(cx[ic], x[idx], "-")
  dy <- outer(cy[ic], y[idx], "-")
  d2 <- dx * dx + dy * dy
  nucleo <- exp(-0.5 * d2 / (h * h))
  nucleo[d2 > B * B] <- 0
  dens[ic] <- as.vector(nucleo %*% w[idx])
}
dens <- dens / (n * 2 * pi * h^2)
saida <- dens[dono]
tempo <- proc.time()[["elapsed"]] - inicio

con <- file(args[2], "wb")
writeBin(saida, con)
close(con)
cat(sprintf('{"tempo": %.6f, "memoria_mb": %.1f}\n', tempo, pico_mb()))
