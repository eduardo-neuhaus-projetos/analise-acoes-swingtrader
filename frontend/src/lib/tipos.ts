export type Fonte = "brapi" | "yahoo";
export type Pagina = "analise" | "dashboard" | "acompanhamento" | "comparar" | "setups" | "dados" | "configuracoes";
export type Tema = "dark" | "light";
export type Params = Record<string, unknown>;

export interface AtivoBusca {
  codigo: string;
  nome: string;
}

export interface CampoEsquema {
  type?: string;
  anyOf?: { type: string; exclusiveMinimum?: number; minimum?: number; maximum?: number }[];
  title?: string;
  description?: string;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  default?: unknown;
  enum?: string[];
  rotulos?: Record<string, string>;
  grupo?: string;
}

export interface SetupInfo {
  id: string;
  versao: string;
  nome: string;
  descricao: string;
  familia: string;
  origem: string;
  direcao: string[];
  esquema: { properties: Record<string, CampoEsquema> };
  padroes: Params;
}

export interface Origem {
  fonte: Fonte;
  provedor: string;
  plano: string;
  ativo: string;
  tem_dados: boolean;
  obtida_em?: string;
  ultimo_pregao?: string;
  versao?: number;
  ultimo_erro?: string | null;
  ultimo_erro_em?: string | null;
  aviso_rebase?: string | null;
  atrasada?: boolean;
}

export interface Candle {
  data: string;
  abertura: number;
  maxima: number;
  minima: number;
  fechamento: number;
  volume: number;
}

export interface EventoTrade {
  data: string;
  tipo: string;
  preco: number | null;
  regra: string;
}

export interface Trade {
  numero: number;
  sinal_data: string;
  entrada_data: string;
  entrada_preco: number;
  stop: number | null;
  risco: number | null;
  alvo: number | null;
  saida_data: string | null;
  saida_preco: number | null;
  motivo_saida: string | null;
  motivo_saida_texto: string;
  duracao_pregoes: number;
  aberto: boolean;
  preco_referencia: number | null;
  avisos: string[];
  avisos_texto: string[];
  eventos: EventoTrade[];
  bruto_pct: number;
  bruto_r: number | null;
  bruto_reais: number;
  liquido_pct: number;
  liquido_r: number | null;
  liquido_reais: number;
}

export interface Sinal {
  data: string;
  gatilho: number;
  stop: number;
  situacao: string;
  motivo: string;
  data_fim: string | null;
}

export interface Ordem {
  tipo: "entrada_stop" | "entrada_abertura" | "saida_stop" | "saida_alvo";
  preco: number;
  codigo: string;
  motivo: string;
  stop: number | null;
  alvo_r: number | null;
}

export interface Aviso {
  tipo: string;
  nivel: "info" | "alerta";
  texto: string;
}

export interface Kpis {
  trades: number;
  abertos: number;
  acertos: number;
  erros: number;
  empates: number;
  taxa_acerto: number | null;
  taxa_erro: number | null;
  ganho_medio: number | null;
  perda_media: number | null;
  payoff: number | null;
  fator_lucro: number | null;
  expectativa_r: number | null;
  retorno: number;
  retorno_bruto: number;
  drawdown_maximo: number;
  duracao_media: number | null;
  tempo_exposto: number | null;
  trades_com_aviso: number;
}

export interface Painel {
  indicadores: Kpis;
  curva: { data: string; capital: number; drawdown: number }[];
  taxa_movel: { data: string; taxa: number }[];
  mapa_mensal: { ano: number; mes: number; retorno: number }[];
  anual: { ano: number; trades: number; taxa_acerto: number | null; retorno: number }[];
  distribuicao: { de: number; ate: number; trades: number }[];
  sequencia: { numero: number; data: string; resultado: number }[];
}

export interface ResultadoAnalise {
  execucao_id: number;
  fonte: Fonte;
  ativo: string;
  setup: { id: string; nome: string; versao: string };
  params: Params;
  custos: Custos;
  periodo: { inicio: string | null; fim: string | null };
  origem: Origem;
  avisos: Aviso[];
  painel: Painel;
  janela_movel: number;
  referencias: {
    buy_and_hold: { data: string; valor: number }[];
    ibovespa: { data: string; valor: number }[];
  };
  ibovespa_disponivel: boolean;
  simulacao: string;
  candles: Candle[];
  indicadores: { id: string; rotulo: string; painel: "preco" | "inferior"; painel_indice: number; pontos: { data: string; valor: number }[] }[];
  trades: Trade[];
  sinais: Sinal[];
  estado: string;
  ordens: Ordem[];
  alertas_qualidade: AlertaQualidade[];
}

export interface AlertaQualidade {
  data: string;
  tipo: string;
  descricao: string;
}

export interface Custos {
  corretagem_por_ordem: number;
  emolumentos_pct: number;
  slippage_pct: number;
  capital_por_trade: number;
}

export interface Configuracoes {
  custos: Custos;
  amostra_minima: number;
  janela_movel: number;
  setups_ocultos: string[];
  token_brapi_configurado: boolean;
  /** Fixo: nada antes desta data é baixado, guardado ou simulado. */
  inicio_historico: string;
}

export interface SerieDados extends Origem {
  nome: string | null;
  inicio_guardado?: string;
  candles: number;
  lacunas: { de: string; ate: string }[];
  alertas: number;
  historico_curto?: boolean;
}

export interface ItemAcompanhamento {
  id: number;
  fonte: Fonte;
  ativo: string;
  setup_id: string;
  setup_nome: string;
  setup_versao: string;
  params: Params;
  data_inicio: string;
  ultimo_pregao: string | null;
  estado: string;
  ordens: Ordem[];
  posicao: { entrada_data: string; entrada_preco: number; stop: number | null; alvo: number | null } | null;
  ultimo_erro: string | null;
  ultimo_erro_em: string | null;
}

export interface EventoAcompanhamento {
  id: number;
  ativo: string;
  data: string;
  tipo: string;
  preco: number | null;
  descricao: string;
  serie_versao: number;
  registrado_em: string;
}

export interface ItemComparacao {
  id: string;
  ativo: string;
  setup_id: string;
  setup_nome: string;
  params: Params;
  slot: number;
}

export interface ResultadoComparacao {
  ativo: string;
  erro?: string;
  setup?: { id: string; nome: string; versao: string };
  params?: Params;
  indicadores?: Kpis;
  curva?: { data: string; capital: number }[];
  periodo?: { inicio: string | null; fim: string | null };
}

/** Seleção compartilhada pelas telas: trocar de aba mantém ativo, setup e parâmetros. */
export interface Selecao {
  ativo: string | null;
  setupId: string | null;
  params: Params;
  inicio: string;
  fim: string;
}

export interface SituacaoDownload {
  carregando: boolean;
  erro: string | null;
  codigoErro: string | null;
}
