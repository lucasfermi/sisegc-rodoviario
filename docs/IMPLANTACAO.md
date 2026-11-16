# Hospedagem

O SISegC Rodoviário (Sistema de Identificação de Segmentos Críticos Rodoviários) não guarda os arquivos
enviados: os dados ficam na memória da sessão e são descartados quando ela termina. Qualquer instituição pode hospedá-lo de uma das formas abaixo.

## Servidor próprio com Docker

### Requisitos

- Processador de 4 núcleos ou mais, **16 GB de memória** e 30 GB livres em disco (de preferência SSD). Mais
  memória só faz diferença com várias análises simultâneas de UFs inteiras com ruas residenciais (ver
  [Capacidade](#capacidade)).
- Linux com Docker. O script de instalação foi feito para o Ubuntu Server 24.04 LTS ou 26.04 LTS.
- Para o servidor voltar sozinho depois de uma queda de energia, ative na BIOS a opção de ligar quando a
  energia volta (em geral, *AC Recovery* ou *Restore on AC Power Loss*).

### Instalação

1. Traga o projeto para o servidor: `git clone` do repositório ou cópia da pasta, com a pasta
   `dados_publicos/` (cerca de 380 MB).
2. Na pasta do projeto, rode o script de instalação:

   ```bash
   bash ferramentas/servidor/instalar.sh
   ```

   O script instala o Docker, monta a imagem do app (a primeira vez leva alguns minutos) e confere se ele
   respondeu. O app fica em <http://127.0.0.1:8501> e volta sozinho depois de reinícios.

### Endereço na rede

Por padrão o app só responde na própria máquina. Para abrir na rede local, troque em `compose.yaml`
`"127.0.0.1:8501:8501"` por `"8501:8501"`. Para publicar na internet, use um proxy reverso com HTTPS (ex.:
Caddy ou Nginx) ou um túnel que só faz conexões de saída, conforme as regras da rede da instituição. O
Streamlit usa WebSocket: o proxy precisa repassá-lo.

### Operação

| Tarefa | Comando (na pasta do projeto) |
| --- | --- |
| Atualizar para a versão do repositório | `bash ferramentas/servidor/atualizar.sh` |
| Ver o registro | `sudo docker compose logs -f --tail 100` |
| Situação | `sudo docker compose ps` e `curl http://127.0.0.1:8501/_stcore/health` (responde `ok`) |
| Parar e iniciar | `sudo docker compose down` e `sudo docker compose up -d` |
| Medir o desempenho desta máquina | `sudo docker compose exec app python ferramentas/benchmark.py --saida /tmp/b.csv` |

### Segurança

- O app não tem login: quem tiver o endereço usa o app. Os arquivos enviados ficam só na memória da sessão e
  não são gravados em disco.
- Mantenha o sistema com as atualizações de segurança (o script ativa as automáticas do Ubuntu).
- Para restringir o acesso, publique só na rede interna ou atrás de um proxy com autenticação.
- O mapa do relatório PDF baixa o fundo do OpenStreetMap (`tile.openstreetmap.org`) da área analisada, no
  máximo 30 tiles por mapa. Sem acesso à internet, o relatório sai com o mapa sem fundo. Para desligar a busca,
  acrescente ao serviço `app` do `compose.yaml` o bloco `environment:` com `SISEGC_MAPA_DE_FUNDO: "0"`.

### Capacidade

Medido com `ferramentas/benchmark.py` numa máquina virtual de 2 núcleos e 8 GB (novembro de 2026). O tempo é o
de escolher a UF até os resultados e o relatório PDF; a planilha de resultados é gerada só no clique.

| Cenário | Segmentos | Sinistros | Tempo | Memória |
| --- | ---: | ---: | ---: | ---: |
| DF, sinistros da PRF (3 anos) | 225 | 3.044 | 1 s | 0,3 GB |
| PE, sinistros da PRF | 2.258 | 9.246 | 3,5 s | 0,4 GB |
| MG, sinistros da PRF (maior malha federal) | 8.342 | 27.883 | 12 s | 0,5 GB |
| Brasil inteiro, sinistros da PRF | 75.128 | 213.497 | 1,5 min | 1,1 GB |
| Base municipal: 5 mil sinistros no DF, com ruas residenciais | 63.991 | 5.000 | 2 s | 0,5 GB |
| Base estadual: 100 mil sinistros em SP, vias principais | 437.617 | 100.000 | 28 s | 1,5 GB |
| Base estadual: 100 mil sinistros em SP, com ruas residenciais | 1.006.220 | 100.000 | 49 s | 2,9 GB |
| Base estadual: 1 milhão de sinistros em SP, vias principais | 438.822 | 1.000.000 | 1 min | 1,6 GB |

As bases municipal e estaduais são sinistros sorteados sobre as vias, para medir o desempenho.

- A memória cresce com o número de segmentos (cerca de 2,5 GB por milhão, mais 0,4 GB fixos). Com 16 GB, uma
  análise vai até uns 5 milhões de segmentos: qualquer UF inteira com ruas residenciais (MG, a maior, tem cerca
  de 2 milhões). Com 32 GB, uns 11 milhões: o Brasil inteiro só com as vias principais (cerca de 8 milhões).
- O primeiro usuário de cada UF espera a segmentação; os seguintes recebem o resultado guardado. O processo do
  app fica com 0,4 a 0,9 GB depois de atender várias UFs.
- Sessões simultâneas dividem os núcleos: 4 UFs médias ao mesmo tempo levaram de 25 a 33 s cada (contra uns 5 s
  sozinhas) na máquina de 2 núcleos, que também rodava os navegadores do teste. Com 16 GB, cabem umas 4 análises
  simultâneas do porte de SP com ruas residenciais (2,9 GB cada), ou dezenas com os dados da PRF.

## Streamlit Community Cloud (gratuito, sem servidor)

1. Publique o repositório no GitHub.
2. Entre em <https://share.streamlit.io> com a conta do GitHub e clique em **Create app**.
3. Escolha o repositório, a branch `main` e o arquivo `app.py`. Em **App URL**, escolha o endereço.
4. Em **Advanced settings**, selecione **Python 3.13** e clique em **Deploy**.

Cada envio para a branch `main` atualiza o app. Sem acessos por 12 horas, o app hiberna; quem abrir o link
clica em “Yes, get this app back up!” e ele volta. O limite é de cerca de 2 núcleos e 2,7 GB de memória.
Apps de repositórios privados só abrem para quem tem acesso ao repositório; para liberar a qualquer pessoa,
use **Share → Make this app public** ou torne o repositório público.

O repositório traz cerca de 380 MB de dados públicos (`dados_publicos/`); o primeiro deploy demora um pouco
mais. Com os sinistros da PRF, uma UF usa poucas centenas de MB de memória; sinistros próprios de uma UF
inteira com ruas residenciais (ex.: SP) pedem mais memória do que a Community Cloud oferece: nesse caso, use
um servidor próprio.

## Sem Docker

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py --server.headless true
```

Para manter no ar, crie um serviço do systemd que rode o último comando.
