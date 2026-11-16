#!/usr/bin/env bash
# Instala o app num Ubuntu Server (24.04 ou 26.04 LTS) com Docker.
#
# Uso, na pasta do projeto (clonada do repositório ou copiada):
#     bash ferramentas/servidor/instalar.sh            # Docker + app em http://127.0.0.1:8501
#
# Pode rodar de novo sem problema: o que já está instalado fica como está.
set -euo pipefail

PASTA="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
passo() { printf '\n\033[1;34m== %s\033[0m\n' "$*"; }

[[ -f "$PASTA/compose.yaml" ]] || { echo "Rode este script de dentro da pasta do projeto (falta compose.yaml)."; exit 1; }
grep -qi ubuntu /etc/os-release || echo "Aviso: o script foi pensado para o Ubuntu Server."

passo "1/4 Pacotes do sistema"
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl git unattended-upgrades
sudo systemctl enable --now unattended-upgrades >/dev/null 2>&1 || true   # atualizações de segurança automáticas

passo "2/4 Docker"
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sudo sh            # script oficial de instalação do Docker
fi
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER" || true                   # vale a partir do próximo login

passo "3/4 App (a primeira montagem baixa a imagem do Python e leva alguns minutos)"
cd "$PASTA"
sudo docker compose up -d --build

passo "4/4 Conferindo se o app respondeu"
for i in $(seq 1 60); do
    if curl -fsS http://127.0.0.1:8501/_stcore/health 2>/dev/null | grep -q ok; then
        echo "App no ar em http://127.0.0.1:8501"
        break
    fi
    sleep 2
    [[ $i == 60 ]] && { echo "O app não respondeu. Veja o registro: sudo docker compose logs --tail 50"; exit 1; }
done

echo
echo "Pronto. Para publicar na rede, veja docs/IMPLANTACAO.md. Para atualizar: bash ferramentas/servidor/atualizar.sh"
