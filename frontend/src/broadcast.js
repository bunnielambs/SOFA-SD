// Onde assistir no Brasil: detentores dos direitos de cada campeonato na temporada.
// Nao existe fonte gratuita com o canal de CADA jogo no Brasil (TheSportsDB e ESPN vem vazios para o Brasil),
// entao mostramos quem tem os direitos do campeonato, com fonte e data da checagem. Revisar a cada temporada.
export const CHECKED = '16/11/2026'
const T = { aberta: 'TV aberta', fechada: 'TV fechada', streaming: 'Streaming', youtube: 'YouTube (grátis)', ppv: 'Pay-per-view' }
export const BROADCAST = {
  BRA: {
    season: '2026',
    channels: [['Globo', T.aberta], ['Record', T.aberta], ['Premiere', T.ppv], ['SporTV', T.fechada], ['Prime Video', T.streaming], ['CazéTV', T.youtube], ['ge tv', T.youtube]],
    note: 'Cada jogo passa só em parte desses canais: a divisão sai a cada rodada. O Prime Video tem um jogo exclusivo por rodada; Record e CazéTV dividem outro.',
    sources: [['Lance!: divisão dos direitos do Brasileirão 2026', 'https://www.lance.com.br/lance-negocios/onde-assistir-ao-brasileirao-2026-entenda-divisao-dos-direitos-de-transmissao.html'],
      ['Trivela: transmissões do Brasileirão 2026', 'https://trivela.com.br/brasil/como-novo-calendario-baguncou-brasileirao-coluna-allan-simon/']],
  },
  E0: {
    season: '2026/27',
    channels: [['Disney+', T.streaming], ['ESPN', T.fechada], ['CazéTV', T.youtube]],
    note: 'O Disney+ transmite todos os 380 jogos. A ESPN passa jogos selecionados e a CazéTV um jogo por rodada.',
    sources: [['Diario de Pernambuco: Premier League 2026/27', 'https://www.diariodepernambuco.com.br/esportes-dp/internacional/2026/08/11721857-onde-assistir-a-premier-league-2026-27-veja-a-divisao-de-transmissoes.html'],
      ['Band: onde assistir à Premier League', 'https://www.band.com.br/esportes/quando-comeca-a-premier-league-veja-calendario-e-onde-assistir-202607310023']],
  },
  SP1: {
    season: '2026/27',
    channels: [['CazéTV', T.youtube]],
    note: 'A partir desta temporada a LaLiga saiu da ESPN/Disney+.',
    sources: [['Itatiaia: onde assistir aos campeonatos europeus', 'https://www.itatiaia.com.br/esportes/futebol/futebol-internacional/quando-comecam-e-onde-assistir-os-principais-campeonatos-europeus-em-2026/']],
  },
  F1: {
    season: '2026/27',
    channels: [['CazéTV', T.youtube], ['XSports', T.aberta]],
    note: 'A XSports passa três jogos por rodada.',
    sources: [['Trivela: mudanças nas transmissões 2026/27', 'https://trivela.com.br/europa/futebol-europeu-tv-transmissoes-assistir-temporada-2026-27/']],
  },
  D1: {
    season: '2026/27',
    channels: [['SporTV', T.fechada], ['CazéTV', T.youtube], ['SportyNet', T.fechada], ['Canal GOAT', T.youtube], ['XSports', T.aberta], ['Jovem Pan', T.aberta], ['OneFootball', T.streaming], ['Romário TV', T.youtube]],
    note: 'Os jogos são divididos entre vários parceiros a cada rodada.',
    sources: [['Máquina do Esporte: parceiros da Bundesliga 2026/27', 'https://maquinadoesporte.com.br/midia/bundesliga-fecha-com-romario-tv-e-consolida-estrategia-multiplataforma-no-brasil/']],
  },
  I1: {
    season: '2026/27',
    channels: [['ESPN', T.fechada], ['Disney+', T.streaming], ['SportyNet', T.fechada]],
    note: 'A SportyNet passa dois jogos por rodada. Outras fontes também citam a CazéTV; confira antes do jogo.',
    sources: [['Trivela: onde assistir às ligas europeias 2026/27', 'https://trivela.com.br/europa/onde-assistir-ao-vivo-premier-league-laliga-bundesliga-serie-a-ligue/']],
  },
  P1: {
    season: '2026/27',
    channels: [['ESPN', T.fechada], ['Disney+', T.streaming]],
    note: null,
    sources: [['Itatiaia: onde assistir aos campeonatos europeus', 'https://www.itatiaia.com.br/esportes/futebol/futebol-internacional/quando-comecam-e-onde-assistir-os-principais-campeonatos-europeus-em-2026/']],
  },
  E1: null,
  N1: null,
}
