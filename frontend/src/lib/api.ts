import type {
  AtivoBusca,
  AlertaQualidade,
  Configuracoes,
  Custos,
  EventoAcompanhamento,
  Fonte,
  ItemAcompanhamento,
  ItemComparacao,
  Origem,
  Params,
  ResultadoAnalise,
  ResultadoComparacao,
  SerieDados,
  SetupInfo,
} from "./tipos";

const BASE = "/api/v1";

export class ErroApi extends Error {
  constructor(
    public codigo: string,
    mensagem: string,
    public status: number,
  ) {
    super(mensagem);
  }
}

async function pedir<T>(caminho: string, opcoes?: RequestInit): Promise<T> {
  let resposta: Response;
  try {
    resposta = await fetch(BASE + caminho, {
      ...opcoes,
      headers: opcoes?.body ? { "Content-Type": "application/json" } : undefined,
    });
  } catch {
    throw new ErroApi("sem_conexao", "Não foi possível falar com o backend. Ele está rodando?", 0);
  }
  if (resposta.status === 204) return undefined as T;
  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => null);
    const mensagem =
      corpo?.mensagem ??
      (resposta.status >= 500 ? "O backend não está respondendo. Ele está rodando?" : "Pedido inválido.");
    throw new ErroApi(corpo?.codigo ?? "erro", mensagem, resposta.status);
  }
  return resposta.json();
}

const json = (dados: unknown) => ({ method: "POST", body: JSON.stringify(dados) });
const codigo = (ativo: string) => encodeURIComponent(ativo);

export const api = {
  buscarAtivos: (termo: string) => pedir<AtivoBusca[]>(`/ativos?busca=${encodeURIComponent(termo)}`),
  setups: () => pedir<SetupInfo[]>("/setups"),
  origem: (fonte: Fonte, ativo: string) => pedir<Origem>(`/dados/${fonte}/${codigo(ativo)}`),
  atualizar: (fonte: Fonte, ativo: string) =>
    pedir<Origem>(`/dados/${fonte}/${codigo(ativo)}/atualizar`, { method: "POST" }),
  series: () => pedir<SerieDados[]>("/dados"),
  alertas: (fonte: Fonte, ativo: string) => pedir<AlertaQualidade[]>(`/dados/${fonte}/${codigo(ativo)}/alertas`),
  analisar: (
    fonte: Fonte,
    corpo: { ativo: string; setup_id: string; params: Params; inicio: string | null; fim: string | null },
  ) => pedir<ResultadoAnalise>(`/analise/${fonte}`, json(corpo)),
  comparar: (fonte: Fonte, itens: ItemComparacao[], inicio: string | null, fim: string | null) =>
    pedir<ResultadoComparacao[]>(
      `/comparar/${fonte}`,
      json({
        itens: itens.map((i) => ({ ativo: i.ativo, setup_id: i.setup_id, params: i.params })),
        inicio,
        fim,
      }),
    ),
  acompanhamento: (fonte: Fonte) =>
    pedir<{ itens: ItemAcompanhamento[]; eventos: EventoAcompanhamento[] }>(`/acompanhamento/${fonte}`),
  acompanhar: (fonte: Fonte, corpo: { ativo: string; setup_id: string; params: Params }) =>
    pedir<ItemAcompanhamento>(`/acompanhamento/${fonte}`, json(corpo)),
  processarAcompanhamento: (fonte: Fonte) =>
    pedir<{ processados: number; falhas: Record<string, string> }>(`/acompanhamento/${fonte}/processar`, {
      method: "POST",
    }),
  removerAcompanhamento: (id: number) => pedir<void>(`/acompanhamento/item/${id}`, { method: "DELETE" }),
  configuracoes: () => pedir<Configuracoes>("/configuracoes"),
  salvarConfiguracoes: (corpo: { custos?: Custos; amostra_minima?: number; janela_movel?: number; setups_ocultos?: string[] }) =>
    pedir<Configuracoes>("/configuracoes", { method: "PUT", body: JSON.stringify(corpo) }),
  salvarToken: (token: string | null) =>
    pedir<{ token_brapi_configurado: boolean; teste: { ok: boolean; mensagem: string } | null }>("/configuracoes/token-brapi", {
      method: "PUT",
      body: JSON.stringify({ token }),
    }),
  urlCsv: (execucaoId: number) => `${BASE}/execucoes/${execucaoId}/trades.csv`,
};
