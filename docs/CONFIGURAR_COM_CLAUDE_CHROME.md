# Configurar o Radar Black no ar (roteiro para o Claude in Chrome)

> **Para o Claude que vai executar:** você roda no computador do dono do site, com o Claude in Chrome. Siga as etapas
> na ordem, sem pular. A pessoa faz os logins; você faz o resto. Leia as regras antes de começar.

## Regras

1. **Chaves nunca aparecem no chat.** Copie cada chave da Cloudflare direto para o campo do Railway. Não escreva
   chave nenhuma na conversa, em arquivo nem em print.
2. **Pare e pergunte** antes de:
   - qualquer tela de pagamento, cartão ou troca de plano;
   - apagar qualquer coisa;
   - mexer em algo que não esteja neste roteiro (outros projetos do Railway, como o Radar de Teses, ou outros sites
     da Cloudflare).
3. **Não crie nada no GitHub**: nenhum workflow, Actions, token ou commit. O repositório antigo foi desativado por
   isso.
4. Se um passo falhar 2 vezes, pare e conte para a pessoa o que apareceu na tela.
5. **No fim, preencha o "Relatório final"** (última seção) e mostre à pessoa.

## O que já está pronto (não mexer)

- **Código:** repositório público `Meruvash/bot-telegram-elite`. Tem os robôs do Radar Black, o bot do Telegram, o
  `Dockerfile` e o `railway.toml`.
- **Site:** `eliteboardgamers.com.br`, no Cloudflare Pages, projeto `eliteboardgamers`. Ele já tem o código que lê a
  página `/black/` de um bucket R2 chamado pela variável `RADAR`. Hoje essa ligação não existe, por isso o `/black/`
  está parado em 24/11/2026.
- **Conta Cloudflare:** ID `0b88cc2d6b58c936265686f078d9969f` (dona do domínio).

## Etapa 1: Cloudflare R2, o bucket

1. Abra https://dash.cloudflare.com e peça à pessoa para entrar na conta dona de `eliteboardgamers.com.br`.
2. Confira se a conta é a certa: o ID na barra de endereço precisa ser `0b88cc2d6b58c936265686f078d9969f`.
3. Menu lateral → **R2 Object Storage**.
   - Se aparecer a tela de ativação do R2: **pare e pergunte**. Ela pede cartão (o plano grátis vai até 10 GB e
     não cobra nesse uso). Siga só com o "pode" da pessoa.
4. Veja se já existe um bucket **`elite-radar`**.
   - **Existe:** passe para a Etapa 2.
   - **Não existe:** **Create bucket** → nome `elite-radar` → localização automática → classe **Standard** →
     **Create bucket**.

**Conferir:** `elite-radar` aparece na lista de buckets.

## Etapa 2: Cloudflare R2, a chave de acesso do robô

1. Em **R2 Object Storage**, abra **Manage API tokens** (ou "API" → "Manage API Tokens").
2. **Create Account API token** (se só houver "Create API token", use esse):
   - Token name: `robos-elite-railway`
   - Permissions: **Object Read & Write**
   - Specify bucket(s): **Apply to specific buckets only** → `elite-radar`
   - TTL: **Forever**
   - **Create API Token**
3. A tela mostra **Access Key ID** e **Secret Access Key** **uma vez só**. Mantenha essa aba aberta até terminar a
   Etapa 5. Não copie para o chat.

**Conferir:** o token `robos-elite-railway` aparece na lista de tokens do R2.

## Etapa 3: ligar o bucket ao site

1. Menu lateral → **Workers & Pages** → projeto **`eliteboardgamers`** (Pages).
2. **Settings** → **Bindings** → **Add** → **R2 bucket**:
   - Variable name: **`RADAR`** (exatamente assim, maiúsculo)
   - R2 bucket: `elite-radar`
   - Ambiente: **Production**
   - **Save**
3. A ligação só vale a partir do próximo deploy do site. Vá em **Deployments**, abra o deploy mais recente de
   **Production** e clique em **Retry deployment**. Espere ficar **Success** (1 a 3 minutos).

**Conferir:** em Settings → Bindings aparece `RADAR → elite-radar`, e o último deploy de Production está como Success.

> Enquanto o bucket estiver vazio, o site continua mostrando a cópia antiga do `/black/`. Isso é esperado, e nada
> quebra.

## Etapa 4: Railway, o projeto e o serviço

1. Abra https://railway.com e peça à pessoa para entrar com o **GitHub (`Meruvash`)**. É a mesma conta do projeto
   do Radar de Teses.
2. Se aparecer aviso de plano (Trial vencido, "upgrade to Hobby"): **pare e pergunte**. O Hobby custa US$ 5 por
   mês, com US$ 5 de uso incluídos.
3. **New** (ou "+ New Project") → **Deploy from GitHub repo** → `Meruvash/bot-telegram-elite`.
   - Se o repositório não aparecer: **Configure GitHub App** → libere o acesso a `bot-telegram-elite` → volte e
     escolha.
   - Se ele perguntar "Deploy Now" ou "Add variables": escolha **Add variables** (ou deixe o primeiro deploy rodar;
     ele vai rodar de novo depois das variáveis).
4. Nome do projeto: **Settings** do projeto → Name: `robos-elite`.
5. Clique no serviço (card `bot-telegram-elite`) → **Settings**:
   - **Source:** branch **`main`**.
   - **Build:** deve mostrar **Dockerfile**. O `railway.toml` do repositório já define isso; não troque.
   - **Deploy → Replicas / Instances:** **1**. Nunca mais que 1: duas cópias publicariam tudo em dobro.
   - **Networking:** não gere domínio público. O serviço não tem site, só a agenda.
6. **Volume:** no canvas do projeto, botão direito no serviço → **Attach Volume** (ou "+ New" → Volume, ligado ao
   serviço) → Mount path: **`/dados`** → criar.

**Conferir:** o serviço mostra um volume montado em `/dados` e Replicas = 1.

## Etapa 5: Railway, as variáveis

No serviço → **Variables** → **Raw Editor**. Cole o bloco abaixo e troque os dois valores entre `<...>` pelas chaves
da aba da Etapa 2 (copie de lá direto, sem passar pelo chat):

```
R2_ACCOUNT_ID=0b88cc2d6b58c936265686f078d9969f
R2_ACCESS_KEY_ID=<Access Key ID da Etapa 2>
R2_SECRET_ACCESS_KEY=<Secret Access Key da Etapa 2>
R2_BUCKET=elite-radar
```

Depois, **peça à pessoa** para adicionar ela mesma as do Telegram e as opcionais. Você não deve ver esses valores.

| Variável | Para quê | Obrigatória? |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | token do @BotFather | para o canal do Telegram |
| `TELEGRAM_CANAL` | `@` do canal (o bot precisa ser administrador nele) | para o canal do Telegram |
| `TELEGRAM_CANAL_NOTICIAS` | canal separado para notícias | não |
| `TELEGRAM_CHAT_WHATSAPP` | id do chat privado, para receber os textos prontos do WhatsApp | não |
| `ML_CLIENT_ID`, `ML_CLIENT_SECRET` | ofertas do Mercado Livre (API oficial) | não |
| `KEEPA_KEY` | Amazon | não |
| `NTFY_TOKEN` | avisos no celular pelo app ntfy | não |

Clique em **Update Variables** / **Deploy** (o Railway mostra "Apply changes" → **Deploy**).

**Conferir:** a aba Variables lista as 4 variáveis do R2, com os valores escondidos.

## Etapa 6: primeiro deploy e logs

1. Serviço → **Deployments** → deploy mais recente → **View logs**.
2. **Build:** a montagem leva de 2 a 5 minutos e termina em sucesso.
   - Se falhar, copie as **últimas 30 linhas do log de build** e mostre à pessoa. Não tente consertar o código.
3. **Deploy logs:** em até 1 minuto devem aparecer as duas linhas abaixo. Isso confirma que o volume está ligado e
   que os dados de preço foram restaurados.
   ```
   [agenda ...] volume vazio: abrindo a semente semente-2026-11-24.tgz
   [agenda ...] agenda no ar; robôs ligados: normal, ml, educado, alertas, telegram, notificacoes, auditoria
   ```
   - Se aparecer `agenda no ar` **sem** a linha da semente no primeiro deploy, o volume não está em `/dados`.
     Volte à Etapa 4, passo 6.
4. **Espere o primeiro robô.** O robô `normal` roda nos minutos **:05 e :35** de cada hora (UTC) e leva até
   25 minutos. Ao terminar, aparece:
   ```
   [agenda ...] começando o robô normal
   ...
   R2: N arquivo(s) enviado(s), M sem mudança
   [agenda ...] robô normal terminou (código 0)
   ```
   - `KeyError: 'R2_ACCESS_KEY_ID'` (ou outra `R2_`): falta variável. Volte à Etapa 5.
   - `AccessDenied`, `InvalidAccessKeyId` ou `SignatureDoesNotMatch`: chave errada ou token sem acesso ao bucket.
     Refaça a Etapa 2 e troque as duas variáveis.
   - `NoSuchBucket`: o nome do bucket não é `elite-radar`. Confira a Etapa 1 e `R2_BUCKET`.

## Etapa 7: conferir no ar

1. **R2:** Cloudflare → R2 → `elite-radar` → **Objects**. Deve haver `black/index.html`, `black/alertas.json` e a
   pasta `img/black/`.
2. **Site:** abra https://eliteboardgamers.com.br/black/ numa aba anônima e recarregue. Perto do topo, a frase
   "Atualizado em ..." precisa ter a **data e a hora de hoje** (horário de Brasília).
   - Se ainda mostrar 23/11 ou 24/11 e o R2 já tiver `black/index.html`: o deploy do site da Etapa 3 não rodou
     depois da ligação. Refaça o **Retry deployment**.
3. **Telegram** (se a pessoa preencheu as variáveis): na primeira rodada o bot **não publica nada**, só marca o que
   já existe (log: `primeira rodada: N itens marcados como já vistos`). A partir da próxima promoção nova, ela
   aparece no canal.

## Etapa 8: limpeza

- Feche as abas da Cloudflare que mostravam as chaves.
- Não apague nada do repositório nem do servidor antigo.

## Relatório final

Preencha e mostre à pessoa, sem nenhuma chave:

```
Cloudflare
  [ ] bucket elite-radar existe
  [ ] token R2 robos-elite-railway criado (só elite-radar, Read & Write)
  [ ] binding RADAR -> elite-radar em Production + Retry deployment com Success
Railway
  [ ] projeto robos-elite, serviço do repositório Meruvash/bot-telegram-elite, branch main
  [ ] Replicas = 1, sem domínio público
  [ ] volume em /dados
  [ ] variáveis R2_* preenchidas; Telegram e opcionais: (quais a pessoa preencheu)
  [ ] build com sucesso
  [ ] log "abrindo a semente" + "agenda no ar"
  [ ] robô normal terminou com "R2: N arquivo(s) enviado(s)"   (ou: ainda aguardando, horário previsto ...)
Site
  [ ] /black/ mostra "Atualizado em <hoje>"
Pendências / erros:
  ...
```

## Depois de pronto (para a pessoa)

| Para | Faça |
|---|---|
| Pausar robôs | Railway → Variables → `DESLIGAR=educado,auditoria` (nomes separados por vírgula) |
| Ver o que cada robô fez | Railway → Deployments → View logs |
| Atualizar o código | basta enviar ao repositório; o Railway monta de novo sozinho |
| Custo | Railway → Usage (deve ficar perto dos US$ 5 incluídos no Hobby) |
