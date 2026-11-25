# Bot do Telegram da Elite Boardgamers

Publica num canal do Telegram as promoções do Black de Verdade e as notícias e resenhas do site. Opcionalmente,
manda para o seu chat privado o mesmo conteúdo já formatado para o WhatsApp, para você copiar e colar no Canal do
WhatsApp à mão (o WhatsApp não tem API segura para canais).

## Por que é um projeto separado
O repositório antigo do site foi desativado pelo GitHub por causa dos robôs do Black (consultas a lojas a cada
15 minutos e centenas de commits por semana). Este bot foi feito para não repetir isso:

| | Robôs do Black | Este bot |
|---|---|---|
| Consulta lojas | sim | **não**: só lê 2 arquivos públicos do próprio site |
| Commits no GitHub | centenas por semana | **nenhum**: o estado fica num arquivo no servidor |
| Frequência | 15 min, várias lojas | 15 min, 2 pedidos ao próprio site |
| Onde roda | VPS + Actions | **só no servidor** (systemd), nunca no GitHub Actions |

O repositório deste bot só guarda o código. Nunca ligue um workflow de GitHub Actions para rodá-lo.

## Segurança das contas
- Telegram: API oficial de bots, automação permitida. Limites respeitados (máx. 6 posts por rodada, 3,5 s entre
  posts, espera quando o Telegram pede).
- WhatsApp: o bot **não toca** no WhatsApp. Você recebe o texto pronto e publica à mão. Risco zero de banimento.
- Primeira rodada não publica nada (só marca o que já existe), para não despejar 70 itens no canal.
- Item com mais de 12 horas não é publicado.

## Configurar (uma vez)
1. No Telegram, abra o **@BotFather**, mande `/newbot` e copie o token. Não cole o token em chat nem no repositório.
2. Crie um **Canal** público e adicione o bot como **administrador** com permissão de publicar.
3. (Opcional, para o WhatsApp) Mande qualquer mensagem para o seu bot e abra
   `https://api.telegram.org/bot<TOKEN>/getUpdates` no navegador: o número em `"chat":{"id": ...}` é o seu
   `TELEGRAM_CHAT_WHATSAPP`.
4. No servidor:
   ```
   git clone <este repositório> && cd <pasta>
   sudo bash instalar.sh
   sudo nano /opt/bot-telegram-elite/.env      # token, canal e (opcional) chat do WhatsApp
   sudo -u bot-telegram python3 /opt/bot-telegram-elite/bot.py --teste
   sudo systemctl enable --now bot-telegram-elite.timer
   ```

## Dia a dia
- Ver as últimas rodadas: `journalctl -u bot-telegram-elite -n 30`
- Ver o que sairia agora, sem publicar: `sudo -u bot-telegram python3 /opt/bot-telegram-elite/bot.py --simular`
- Pausar: `sudo systemctl disable --now bot-telegram-elite.timer`
- Testes: `python3 -m unittest test_bot`

## Desligar o envio duplicado do robô do Black
O `tools/black/alertas.py` do site também publica no Telegram quando `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CANAL` estão
preenchidos em `/etc/elite-radar.env`. Deixe esses dois **vazios** lá: quem publica é este bot.
