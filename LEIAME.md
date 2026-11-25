# Robôs da Elite Boardgamers

Todos os robôs que antes rodavam a partir do repositório do site, agora num repositório próprio e **sem nada que
possa fazer o GitHub desativar o repositório**.

| Robô | O que faz | Frequência | Antes era |
|---|---|---|---|
| `normal` | lojas com feed e catálogo, Promobit, canais públicos de promoção | 30 min | radar-normal.yml |
| `ml` | Mercado Livre pela API oficial, vigia de PS5 | 30 min | radar-ml.yml |
| `educado` | lista inteira do Compara Jogos, lojas devagar (domingo: varredura completa) | 3 h | radar-educado.yml |
| `alertas` | fila de avisos do ntfy | 15 min | alertas.yml |
| `telegram` | publica promoções, notícias e resenhas no canal do Telegram | 15 min | (novo) |
| `notificacoes` | plano B das notificações do sininho do site | 15 min | notificacoes.yml |
| `auditoria` | confere se os links de oferta do /black/ levam ao produto certo | 6 h | auditoria-links.yml |
| `calibragem` | guarda os posts dos canais de curadoria e, a cada 7 dias, retreina os pesos da nota das ofertas (`tools/black/calibrar.py`); só troca os pesos com 150+ positivos e acerto maior que o atual | 1 dia | (novo) |

A checagem de duplicatas (black-sem-duplicata.yml) e a de link de afiliado de terceiros rodam dentro de cada ciclo,
antes de publicar. Ficaram de fora: `radar-reserva.yml` (reserva no GitHub Actions, que existia por causa dos atrasos
do GitHub) e os testes manuais de chaves (`teste-apis`, `teste-vendas`); `radar/tools/black/teste_apis.py` continua
aqui para rodar à mão.

## Por que o repositório antigo caiu e o que mudou

O repositório antigo do site (Meruvash/Golden-Geek) foi desativado pelo GitHub em 24/11/2026. Os robôs rodavam no
**GitHub Actions em laço quase 24 horas por dia**, disparavam o próprio workflow para nunca parar e faziam **um commit
por ciclo** (cerca de 700 por semana). Usar o Actions como servidor permanente fere os termos do GitHub.

| | Antes | Agora |
|---|---|---|
| Onde roda | GitHub Actions, em laço | **servidor da Oracle** (systemd) |
| Commits | ~700 por semana | **nenhum**: dados só no disco do servidor |
| Busca de código | `git fetch` a cada ciclo (~200 por dia) | **só à mão**, com `servidor/atualizar.sh` |
| GitHub Actions | 10 workflows | **nenhum**: o repositório não tem `.github/` |
| Publicação do /black/ | commit no repositório do site | **Cloudflare R2** (como já era desde 24/11) |

**Regras que não se quebram** (o `checar_seguranca.py` confere todas e falha se alguma for quebrada):
1. Nunca criar `.github/workflows/` neste repositório.
2. Nenhum robô faz commit, push, pull, fetch ou chama a API do GitHub.
3. Nenhum timer ou cron chama `git`. Código novo só com `servidor/atualizar.sh`, rodado à mão.
4. Dados (`radar/conteudo/`, `radar/img/`, `radar/black/`) nunca entram no git (estão no `.gitignore`).
5. Chaves só em `/etc/elite-robos.env` no servidor, nunca no repositório.

Antes de cada commit neste repositório: `python3 checar_seguranca.py && python3 -m unittest discover -s telegram`.

## Onde roda: Railway

Um serviço só no Railway, construído pelo `Dockerfile`, com a agenda `railway/agenda.py` sempre ligada (ela faz o papel
dos timers do systemd). Os dados ficam num **volume montado em `/dados`**; no primeiro início, com o volume vazio, a
agenda abre `railway/semente-2026-11-24.tgz` (o histórico de preços do Radar até 24/11/2026). A semente é a única
cópia de dados no repositório, gravada uma vez; os robôs nunca a atualizam.

Configuração no painel do Railway:
1. New Project → Deploy from GitHub repo → `Meruvash/bot-telegram-elite`.
2. No serviço: Settings → **Replicas = 1** (dois processos publicariam em dobro).
3. Botão direito no serviço → **Attach Volume** → mount path `/dados`.
4. Variables: as chaves (lista abaixo). Robô que não tem a chave dele pula essa parte.
5. Teste um robô: no serviço, aba de comandos, `python3 railway/agenda.py --agora telegram`.

Variáveis: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `ML_CLIENT_ID`,
`ML_CLIENT_SECRET`, `KEEPA_KEY`, `NTFY_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CANAL`, `TELEGRAM_CANAL_NOTICIAS`,
`TELEGRAM_CHAT_WHATSAPP`, `TELEGRAM_CHAT_AVISOS`. Para pausar robôs sem mexer no código: `DESLIGAR=educado,auditoria`.

**Vigia:** a agenda confere a cada 5 minutos e avisa no Telegram privado (`TELEGRAM_CHAT_AVISOS`, ou o chat de
`TELEGRAM_CHAT_WHATSAPP`) quando:
- um robô fica sem terminar uma rodada sem erro por 2 h (o educado, por 8 h);
- um robô erra 2 vezes seguidas;
- a página `/black/` fica 3 h sem ser refeita.

O mesmo aviso só se repete depois de 6 h, e chega um "resolvido" quando o problema passa.

**Cuidado com deploy:** cada envio ao repositório faz o Railway reiniciar o serviço, o que interrompe o robô que
estiver rodando (o educado leva até 4 h). Os dados não se perdem (há cópia antes de cada rodada), mas a leitura
daquela rodada sim. Prefira enviar mudanças longe dos minutos :05 e :35.

**Piso do destaque** (`radar/tools/black/radar.py`, `DESTAQUE_ECONOMIA_MIN` e `DESTAQUE_PRECO_MIN`): oferta que
economiza menos de R$ 30 ou custa menos de R$ 50 fica na página, mas não entra em "Últimas novidades", não vira
cartão "Destaque" nem alerta.

O Railway lê o repositório quando o código muda (deploy), como a Cloudflare faz com o site. Isso não é GitHub Actions,
não faz commit e não roda nada no GitHub.

O jeito antigo, com servidor próprio (`servidor/instalar.sh` e `systemd/`), continua valendo como alternativa.

## Estrutura

```
radar/       cópia da parte do site que os robôs usam (tools/black, layout da página, fontes, logo)
             radar/ORIGEM.txt diz de qual commit do site ela veio
telegram/    bot do Telegram
railway/     agenda.py (agenda sempre ligada) e a semente dos dados
servidor/    rodar.sh (uma rodada), publicar_r2.py, instalar.sh, atualizar.sh, systemd/ (agenda)
```

`pauta.json` e `busca.json` (jogos com resenha no site) o servidor baixa do **site no ar** a cada 6 horas, não do
GitHub. A página do /black/ usa o layout do site copiado em `radar/tools/`: se o visual do site mudar, copie de novo
os arquivos de `tools/` do repositório do site para `radar/tools/` e atualize `radar/ORIGEM.txt`.

## Migrar do jeito antigo (uma vez, no servidor da Oracle)

```
sudo git clone https://github.com/Meruvash/bot-telegram-elite /opt/elite-robos
sudo bash /opt/elite-robos/servidor/instalar.sh
```

O repositório é privado: o `git clone` pede seu usuário do GitHub e, no lugar da senha, um token de acesso
(github.com/settings/tokens, permissão só de leitura no repositório).

O `instalar.sh`:
1. desliga os robôs antigos (`elite-radar-*`), que buscavam código no repositório do site a cada ciclo;
2. copia os dados de `/opt/elite/site` (histórico de preços, estado dos alertas, imagens), para nada recomeçar do zero;
3. cria `/etc/elite-robos.env` a partir de `/etc/elite-radar.env`, com as mesmas chaves;
4. instala a agenda nova (`elite-robo-*`), ainda desligada.

Depois:
```
sudo nano /etc/elite-robos.env      # TELEGRAM_BOT_TOKEN e TELEGRAM_CANAL; confira as chaves do R2
sudo systemctl start elite-robo@telegram && journalctl -u elite-robo@telegram -n 20
sudo systemctl start elite-robo@normal   && journalctl -u elite-robo@normal -n 30
sudo systemctl enable --now elite-robo-{normal,ml,educado,alertas,telegram,notificacoes,auditoria}.timer
```
Se tudo estiver certo, a pasta antiga `/opt/elite/site` pode ser apagada depois de alguns dias.

## Telegram

1. No Telegram, **@BotFather** → `/newbot` → copie o token (não cole em chat nem no repositório).
2. Crie um **Canal** público e adicione o bot como **administrador** com permissão de publicar.
3. (Opcional, para o WhatsApp) mande qualquer mensagem ao bot e abra
   `https://api.telegram.org/bot<TOKEN>/getUpdates`: o número em `"chat":{"id": ...}` vai em `TELEGRAM_CHAT_WHATSAPP`.
   Cada item chega no seu chat já formatado para o WhatsApp: segure, copie e cole no Canal do WhatsApp.
   O bot nunca mexe no WhatsApp (risco zero de banimento lá).
4. Notícias num canal separado: preencha `TELEGRAM_CANAL_NOTICIAS`.

O bot lê só as listas públicas do site (`/black/alertas.json` e `/alertas/conteudo.json`), publica no máximo
6 itens por rodada com 3,5 s entre eles, não publica nada na primeira rodada e ignora itens com mais de 12 horas.

## Dia a dia
- Agenda: `systemctl list-timers 'elite-robo*'`
- Última rodada de um robô: `journalctl -u elite-robo@normal -n 50`
- O que o Telegram publicaria agora: `sudo -u elite /opt/elite-robos/.venv/bin/python /opt/elite-robos/telegram/bot.py --simular`
- Pausar tudo: `sudo systemctl stop 'elite-robo-*.timer'`
- Atualizar o código (à mão): `sudo bash /opt/elite-robos/servidor/atualizar.sh`
