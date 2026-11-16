# SOFA SD

Aplicativo de futebol com dados reais e previsões estatísticas próprias. Custo adicional: zero.
Nenhum dado é inventado: quando a fonte gratuita não entrega algo, a tela mostra "indisponível" e o motivo.

## Como rodar

Requisitos: Python 3.10 ou mais novo e internet.

- Windows: dois cliques em `iniciar.bat`
- Mac/Linux: `./iniciar.sh`

Na primeira vez ele baixa a base histórica (45 MB), atualiza a temporada atual, treina os modelos (2 a 5 minutos)
e abre http://127.0.0.1:8000. Depois disso abre em segundos. Para treinar de novo: `python run.py --retreinar`
ou o botão na aba "Fontes e modelos".

## Interface

Feita em React com Framer Motion, SVG e animações em CSS. Preto, branco e grafite, pensada primeiro para celular.
O código fica em `frontend/` e a versão compilada, que o servidor Python entrega, em `web/dist/index.html`.
Para mexer no visual: `cd frontend`, `npm install`, `npm run build` (precisa do Node.js). Para só usar o app, não precisa do Node.

- Comemoração de gol, sons e vibração só disparam quando o placar real muda entre duas consultas (a cada 60 s, com o app aberto).
  O autor do gol aparece apenas se a API-Football enviar o evento.
- Sons são sintetizados no navegador e ficam desligados até a pessoa ligar. Vibração não existe no iPhone.
- Escudos são monogramas genéricos. Com a chave do football-data.org entram os escudos enviados pela fonte.
- Quem ativa "reduzir movimento" no aparelho vê a interface sem animações.

## Fontes (todas gratuitas, verificadas em 16/11/2026)

| Fonte | Chave | Entrega | Limite |
|---|---|---|---|
| Base histórica aberta (football-data.co.uk espelhado no GitHub) | não | 238.854 partidas de 2000 a set/2026, 38 ligas, com chutes, escanteios e cartões | sem limite |
| football-data.co.uk | não | resultados e estatísticas da temporada atual, atualizado algumas vezes por semana | sem limite |
| openfootball | não | calendário e placares de 9 ligas (atualiza com atraso) | sem limite |
| football-data.org | grátis, por e-mail | jogos do dia, ao vivo com atraso, tabela oficial, artilharia, elencos | 10 req/min |
| API-Football | grátis, por e-mail | eventos e estatísticas ao vivo | 100 req/dia, 10 req/min |

As chaves são coladas na aba "Fontes e modelos" e ficam em `data/keys.json`, só no seu computador.
Sem chave o app funciona com calendário, resultados, tabela calculada, times, confrontos e previsões.

Ligas: Brasileirão Série A, Premier League, Championship, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Primeira Liga.

## Limitações conhecidas

- Ao vivo só com a chave do football-data.org, e o placar chega com atraso no plano gratuito.
- API-Football: há relatos de que o plano gratuito recusa a temporada atual. Se recusar, o app mostra a mensagem da própria API.
- Brasileirão: nenhuma fonte gratuita traz escanteios e cartões, então essas estimativas ficam indisponíveis.
  Eredivisie e Primeira Liga só têm essas estatísticas a partir de 2017.
- Dados por jogador (artilharia, elenco) só via football-data.org. Não há estatística individual por partida de graça.
- O modelo ao vivo foi validado só no intervalo (placar real do 1º tempo). Não existe base gratuita minuto a minuto.
  O efeito de cartão vermelho usa valor da literatura (Vecer, Kopriva e Ichiba, 2009), não estimado aqui.
- As chamadas ao football-data.org e à API-Football foram escritas pela documentação oficial, mas ainda não rodaram
  com uma chave real. O download direto do football-data.co.uk também não pôde ser executado no ambiente de desenvolvimento.

## Modelos (Python, Pandas, NumPy, SciPy, scikit-learn)

- Atributos pré-jogo calculados só com partidas anteriores: Elo próprio, forma (5 e 12 jogos), médias de chutes,
  escanteios e cartões, desempenho em casa/fora, descanso, médias da liga e confronto direto.
- Gols: dois regressores Poisson (gradient boosting) + correção Dixon-Coles ajustada com SciPy. Dessa matriz de placares
  saem 1X2, ambos marcam e mais de 1,5 / 2,5 / 3,5. O 1X2 é misturado com um classificador direto.
- Escanteios e cartões: regressão Poisson com dispersão binomial negativa.
- Divisão temporal: treino até jun/2024, validação 2024/25, teste de jul/2025 a set/2026 (8.231 partidas nunca vistas).

Resultado no teste: log loss 1X2 de 1,015 (casas de aposta: 1,002; chute pela frequência: 1,077). Calibração e demais
métricas ficam na aba "Fontes e modelos" e em `data/metrics.json`. Previsões são probabilidades, não certezas.
Uma previsão só aparece se os dois times tiverem pelo menos 8 partidas no histórico.

## Estrutura

    run.py                 prepara dados, treina e sobe o servidor
    sofasd/config.py       ligas, fontes e limites
    sofasd/http.py         cache, limite de requisições, falhas de conexão
    sofasd/db.py           banco SQLite
    sofasd/sources/        uma integração por fonte
    sofasd/aliases.py      liga o nome do time em cada fonte ao histórico (cruzando resultados reais)
    sofasd/features.py     Elo, forma e atributos
    sofasd/train.py        treino e avaliação
    sofasd/predict.py      probabilidades pré-jogo e ao vivo
    sofasd/service.py      regras do app
    sofasd/server.py       API (FastAPI)
    frontend/src/          interface em React (App, pages, ui, sound, api, styles)
    web/dist/index.html    interface compilada
