import type { Selecao } from "./tipos";

/** Início do histórico do app. O backend informa o valor em Configurações; este é só o valor de partida. */
export const INICIO_HISTORICO_PADRAO = "2010-01-01";

/** Nenhuma data do filtro pode ser anterior ao início do histórico, e o início não pode passar do fim. */
export function erroPeriodo(selecao: Pick<Selecao, "inicio" | "fim">, inicioHistorico: string): string | null {
  const { inicio, fim } = selecao;
  if ((inicio && inicio < inicioHistorico) || (fim && fim < inicioHistorico)) {
    return `Use datas a partir de ${dataCurta(inicioHistorico)}, início do histórico do app.`;
  }
  if (inicio && fim && inicio > fim) return "A data inicial é posterior à data final.";
  return null;
}

function dataCurta(iso: string): string {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
}
