const VAZIO = "—";

export function numero(valor: number | null | undefined, casas = 2): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return VAZIO;
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

export function preco(valor: number | null | undefined): string {
  return numero(valor, 2);
}

export function reais(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return VAZIO;
  return valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

/** Sinal explícito: verde e vermelho nunca carregam o significado sozinhos. */
export function comSinal(valor: number | null | undefined, casas = 2, sufixo = ""): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return VAZIO;
  const texto = numero(Math.abs(valor), casas);
  const sinal = valor > 0 ? "+" : valor < 0 ? "−" : "";
  return `${sinal}${texto}${sufixo}`;
}

export function percentual(valor: number | null | undefined, casas = 1): string {
  return valor === null || valor === undefined ? VAZIO : `${numero(valor, casas)}%`;
}

export function data(iso: string | null | undefined): string {
  if (!iso) return VAZIO;
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
}

export function dataHora(iso: string | null | undefined): string {
  if (!iso) return VAZIO;
  const d = new Date(iso);
  return `${d.toLocaleDateString("pt-BR")} ${d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
}

export function volume(valor: number): string {
  return valor.toLocaleString("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
}

export function classeResultado(valor: number | null | undefined): string {
  if (!valor) return "";
  return valor > 0 ? "ganho" : "perda";
}

export const MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

export const TEXTO_ESTADO: Record<string, { rotulo: string; icone: string }> = {
  sem_sinal: { rotulo: "Sem sinal", icone: "○" },
  armado: { rotulo: "Armado", icone: "◔" },
  posicionado: { rotulo: "Posicionado", icone: "●" },
  saida_armada: { rotulo: "Saída armada", icone: "◕" },
};

export const TEXTO_EVENTO: Record<string, string> = {
  sinal: "Sinal",
  gatilho_atualizado: "Gatilho atualizado",
  sinal_cancelado: "Sinal cancelado",
  entrada: "Entrada",
  saida_armada: "Saída armada",
  saida_atualizada: "Saída atualizada",
  saida_cancelada: "Saída cancelada",
  saida: "Saída",
  trade_encerrado: "Trade encerrado",
};

export const TEXTO_ORDEM: Record<string, string> = {
  entrada_stop: "Compra stop",
  entrada_abertura: "Compra na abertura",
  saida_stop: "Venda stop",
  saida_alvo: "Venda no alvo",
};

export const NOME_FONTE: Record<string, string> = { brapi: "brapi", yahoo: "Yahoo" };

export function resumoParams(params: Record<string, unknown>, padroes?: Record<string, unknown>): string {
  const diferentes = Object.entries(params).filter(([k, v]) => !padroes || padroes[k] !== v);
  if (padroes && diferentes.length === 0) return "Parâmetros padrão";
  return diferentes
    .map(([k, v]) => `${k.replaceAll("_", " ")}: ${v === null ? "desligado" : v === true ? "sim" : v === false ? "não" : v}`)
    .join(" · ");
}
