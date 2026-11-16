#!/usr/bin/env bash
# Atualiza o app no servidor: baixa a versão do GitHub, remonta a imagem e reinicia (cerca de 1 minuto fora do ar).
#
# Uso, na pasta do projeto:   bash ferramentas/servidor/atualizar.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

if [[ -d .git ]]; then
    git pull --ff-only
else
    echo "A pasta não é um clone do Git: copie a versão nova para cá antes de rodar este script."
fi
sudo docker compose up -d --build
sudo docker image prune -f >/dev/null            # apaga as imagens antigas
for _ in $(seq 1 60); do
    curl -fsS http://127.0.0.1:8501/_stcore/health 2>/dev/null | grep -q ok && { echo "App atualizado e no ar."; exit 0; }
    sleep 2
done
echo "O app não respondeu. Veja o registro: sudo docker compose logs --tail 50"
exit 1
