# Plano do Radar: ofertas melhores, robôs mais eficientes e motivo para voltar à página

Feito em 25/11/2026, com os dados do radar de 24/11 e a auditoria de 20/11.

## Onde estamos (números reais)

| O que | Hoje | Problema |
|---|---|---|
| Jogos acompanhados | 6.912 | só 2.359 têm os 28 dias de histórico que o radar exige (a base tem 52 dias) |
| Ofertas no radar | 64, desconto real mediano de 27% | bom: o critério é honesto |
| Economia em reais | mediana de R$ 38 | 24 das 64 economizam menos de R$ 30; 13 custam menos de R$ 50 |
| Concentração | 16 das 64 são da Place Games | a página fica com cara de vitrine de uma loja |
| Lojas lidas direto | 75 | 47 estavam "em descanso" (bloqueio ou limite) em 23/11 |
| Origem dos preços | 11.006 via Compara Jogos, 1.329 via API do Mercado Livre, 139 via feed de loja | quase tudo depende de uma fonte só |
| Achados da comunidade | 932 em 7 dias | só 278 (30%) têm preço de referência; o resto não dá para dizer se é bom |
| Amazon | fora do radar | falta a chave do Keepa |
| Alertas | cerca de 10 por dia, todos com o mesmo peso | um desconto de R$ 12 avisa igual a um de R$ 200 |
| Medição | nenhuma | não sabemos quais ofertas as pessoas clicam |

O princípio que não muda: **o que traz a pessoa de volta é confiar que a página só mostra oferta boa de verdade.**
Nada de urgência falsa, contagem regressiva inventada ou "últimas unidades" sem prova. Isso já é regra do site
(`PADRAO_EDITORIAL.md`) e é o que diferencia o radar dos canais de promoção.

## Frente 1: só oferta que vale (qualidade)

1. **Nota da oferta (0 a 100)** no lugar de ordenar só por percentual. Entram:
   - desconto real sobre a média (o que já existe);
   - **economia em reais** (R$ 150 de economia pesa mais que 30% de um jogo de R$ 40);
   - menor preço do período ("recorde");
   - qualidade do jogo (nota BGG, prêmio, resenha nossa);
   - frescor (preço visto há menos de 3 horas pesa mais);
   - confiança (loja conferida na página pesa mais que achado de canal).
2. **Piso para destaque:** oferta com economia menor que R$ 30 ou preço menor que R$ 50 continua na página, mas
   não vai para o topo nem vira alerta. (Sugestão da auditoria de 20/11, ainda não feita.)
3. **Limite por loja no topo:** no máximo 3 ofertas da mesma loja entre as 12 primeiras.
4. **Preço final de verdade:** quando há cupom válido da loja (já lemos 73 cupons), mostrar o preço com cupom e
   usar esse preço na nota.
5. **Referência para os achados da comunidade:** subir de 30% para 60% ou mais com casamento melhor de nomes;
   achado sem referência fica numa lista à parte, nunca no topo.

## Frente 2: robôs mais eficientes (ler menos, acertar mais)

1. **Prioridade de leitura.** Hoje o robô relê muita coisa que não muda. Proposta de três faixas:
   - a cada 30 min: o que está no radar, o que está a até 5 pontos do corte e o que caiu de preço nas últimas 24 h;
   - a cada 3 h: jogos bem avaliados (BGG 7+ ou premiados) com histórico suficiente;
   - 1 vez por dia: o resto dos 6.912.
   Resultado: a oferta boa é vista em minutos, com menos páginas pedidas e menos bloqueio.
2. **Menos bloqueio, mais fonte oficial.** 47 de 75 lojas em descanso é o maior gargalo.
   - Ler primeiro o que a loja oferece para máquina (feed de produtos, sitemap com data, API da plataforma) e só
     depois a página. Hoje só 139 ofertas vêm de feed.
   - Ativar o **Keepa** (Amazon) e manter o **Mercado Livre** pela API oficial: são as duas maiores vitrines e
     nenhuma depende de raspar página.
   - Escrever para as 10 lojas com mais ofertas pedindo um feed ou a liberação do robô (ele já se identifica e tem
     página própria em `/black/robo/`). Loja parceira vira fonte estável.
   - Regras de educação continuam: User-Agent próprio, robots.txt, parar no 403/429. Nunca contornar bloqueio.
3. **Confirmar antes de avisar.** Antes de mandar alerta, reler a página da oferta (uma página só). Oferta
   esgotada ou com preço diferente não vira alerta. É o que mais protege a confiança.
4. **Tirar rápido o que acabou.** Hoje o preço fica até 96 horas. Para o que está no topo: reconferir a cada
   ciclo e tirar na hora se esgotou.
5. **Vigia dos robôs.** Se um robô ficar 2 horas sem terminar um ciclo, ou se a página ficar 3 horas sem
   atualizar, aviso no seu Telegram privado. Foi isso que faltou entre 17 e 20/11.

## Frente 3: alertas que as pessoas querem receber

1. **Três níveis** no lugar de um:
   - **Imperdível** (nota 85+): alerta na hora, no máximo 3 por dia;
   - **Boa** (nota 70 a 84): entra no resumo;
   - o resto: só na página.
2. **Resumo com hora marcada:** "As 5 melhores de hoje" às 12h e às 19h, no Telegram, no sininho e no texto
   pronto do WhatsApp. Hora fixa cria hábito; alerta demais faz a pessoa silenciar.
3. **Lista de desejos (o item que mais traz gente de volta).** A pessoa marca os jogos que quer e recebe aviso só
   quando *aquele* jogo baixar. O serviço de notificações do site já existe (9 aparelhos inscritos no Black) e já
   separa por tema; falta separar por jogo. No Telegram: comando `/quero Nome do Jogo` no bot.
4. **Texto do alerta com os três números que importam:** preço de hoje, média real e economia em reais, mais
   "menor preço em X dias" quando for o caso.

## Frente 4: página que dá motivo para voltar

1. **"Novas desde a sua última visita"** no topo (guardado no próprio navegador, sem cadastro).
2. **Gráfico de preço** de cada jogo (os 180 dias que já guardamos): a pessoa vê que o desconto é real.
3. **Seção "Menor preço da história"** separada das demais.
4. **"Acabaram hoje":** lista curta do que saiu, com o preço que tinha. Mostra que a página é viva e que vale
   voltar cedo, sem inventar urgência.
5. **Filtros** por faixa de preço, tipo (família, estratégia, festa, expansão) e número de jogadores.
6. **Ponte com o conteúdo:** selo "tem resenha" com link, e nas resenhas e notícias um aviso quando o jogo está
   no radar.
7. **Depois da Black Friday:** a página continua o ano todo como "Radar de Ofertas", com a Black como edição
   especial. O histórico de preços fica mais forte a cada mês e ninguém mais tem isso em português.

## Frente 5: medir

Sem medir, não dá para saber o que funciona. Tudo sem cookie de terceiros e sem dado pessoal:

| Medida | Como | Meta em 30 dias |
|---|---|---|
| Cliques por oferta | o botão "Ver na loja" passa por um contador no serviço do site | saber as 10 mais clicadas da semana |
| Alerta que vira clique | contador por alerta | 15% ou mais |
| Oferta que já tinha acabado no clique | reconferência + auditoria de links | menos de 5% |
| Tempo entre a queda de preço e a página | hora do preço x hora da publicação | menos de 45 min no topo |
| Lojas em descanso | já registrado | de 47 para menos de 15 |
| Gente que volta | visitas repetidas na semana (contagem anônima) | subir mês a mês |
| Inscritos em alertas | sininho + canal do Telegram | dobrar |

## Ordem sugerida

| Quando | O quê | Por quê |
|---|---|---|
| **Agora (1 a 2 dias)** | vigia dos robôs; piso de R$ 30 / R$ 50 no destaque; limite por loja no topo; chave do Keepa e do ntfy | rápido, e já melhora a página na semana da Black |
| **Semana 1** | nota da oferta; três níveis de alerta; resumo das 12h e das 19h; confirmar antes de avisar | muda a qualidade do que chega às pessoas |
| **Semana 2** | prioridade de leitura em três faixas; mais feeds de loja; contador de cliques | eficiência e medição |
| **Semana 3 e 4** | lista de desejos (site e Telegram); "novas desde a última visita"; gráfico de preço | o que cria o hábito de voltar |
| **Dezembro** | contato com as lojas; "Radar de Ofertas" permanente; filtros | consolidar depois da Black |

## O que depende de você

- Chave do **Keepa** (Amazon) e token do **ntfy**, no Railway.
- Decidir o piso do destaque (sugestão: economia de R$ 30 e preço de R$ 50).
- Decidir os horários do resumo (sugestão: 12h e 19h de Brasília).
- Autorizar o contato com as lojas em nome do site.
