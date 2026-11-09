/** Lê os tokens do CSS, para os gráficos em canvas seguirem o tema ativo. */
export function cor(token: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(token).trim();
}

export function coresGrafico() {
  return {
    painel: cor("--painel"),
    texto: cor("--texto"),
    textoSec: cor("--texto-sec"),
    textoTer: cor("--texto-ter"),
    grade: cor("--grade"),
    borda: cor("--borda"),
    ganho: cor("--ganho-marca"),
    perda: cor("--perda-marca"),
    alerta: cor("--alerta"),
    serie: [1, 2, 3, 4, 5, 6, 7, 8].map((n) => cor(`--serie-${n}`)),
    divNeg: cor("--div-neg"),
    divPos: cor("--div-pos"),
    divMeio: cor("--div-meio"),
  };
}

export type CoresGrafico = ReturnType<typeof coresGrafico>;
