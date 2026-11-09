/** Último ativo, setup e filtros voltam ao reabrir. O armazenamento pode falhar, e a tela segue funcionando sem ele. */
const PREFIXO = "swing-b3:";

export function lembrar<T>(chave: string, padrao: T): T {
  try {
    const salvo = localStorage.getItem(PREFIXO + chave);
    return salvo === null ? padrao : (JSON.parse(salvo) as T);
  } catch {
    return padrao;
  }
}

export function guardar(chave: string, valor: unknown): void {
  try {
    localStorage.setItem(PREFIXO + chave, JSON.stringify(valor));
  } catch {
    /* sem armazenamento: a preferência vale só nesta sessão */
  }
}
