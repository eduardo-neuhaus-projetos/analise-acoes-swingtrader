import type { CoresGrafico } from "./cores";
import { comSinal, data, MESES, numero, percentual } from "./formatos";
import type { Painel, ResultadoAnalise } from "./tipos";

/** Em períodos curtos o mês se repetiria no eixo, então os rótulos passam a ter o dia. */
function rotuloTempo(curto: boolean) {
  return (v: number) => {
    const d = new Date(v);
    if (curto) return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
    return `${MESES[d.getMonth()]}/${String(d.getFullYear()).slice(2)}`;
  };
}

function periodoCurto(datas: string[]) {
  if (datas.length < 2) return true;
  return new Date(datas[datas.length - 1]).getTime() - new Date(datas[0]).getTime() < 400 * 86400000;
}

function baseEixos(c: CoresGrafico, curto = false) {
  return {
    eixoTempo: {
      type: "time" as const,
      axisLine: { lineStyle: { color: c.borda } },
      axisTick: { show: false },
      axisLabel: {
        color: c.textoSec,
        fontSize: 11,
        hideOverlap: true,
        formatter: rotuloTempo(curto),
      },
      splitLine: { show: false },
    },
    eixoValor: {
      type: "value" as const,
      axisLabel: { color: c.textoSec, fontSize: 11, formatter: (v: number) => numero(v, 0) },
      splitLine: { lineStyle: { color: c.grade } },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    dica: {
      backgroundColor: c.painel,
      borderColor: c.borda,
      borderWidth: 1,
      textStyle: { color: c.texto, fontSize: 12 },
      extraCssText: "box-shadow:0 4px 14px rgb(0 0 0 / .3);",
    },
  };
}

function linhaDica(cor: string, rotulo: string, valor: string) {
  return `<div style="display:flex;justify-content:space-between;gap:18px"><span><span style="display:inline-block;width:9px;height:2px;margin-right:6px;vertical-align:middle;background:${cor}"></span>${rotulo}</span><b style="font-variant-numeric:tabular-nums">${valor}</b></div>`;
}

export function dataUtc(iso: string) {
  return `${iso}T12:00:00`;
}

function dataDaDica(valor: number | string | Date) {
  const d = new Date(valor);
  return d.toLocaleDateString("pt-BR");
}

export function opcoesCurva(r: ResultadoAnalise, c: CoresGrafico) {
  const b = baseEixos(c, periodoCurto(r.painel.curva.map((p) => p.data)));
  const series = [
    {
      name: `Setup (${r.setup.nome})`,
      cor: c.serie[0],
      largura: 2,
      pontos: r.painel.curva.map((p) => [dataUtc(p.data), p.capital]),
      degrau: "end" as const,
    },
    {
      name: `Buy and hold ${r.ativo}`,
      cor: c.serie[1],
      largura: 1.5,
      pontos: r.referencias.buy_and_hold.map((p) => [dataUtc(p.data), p.valor]),
      degrau: false as const,
    },
    ...(r.ibovespa_disponivel
      ? [
          {
            name: "Ibovespa",
            cor: c.serie[2],
            largura: 1.5,
            pontos: r.referencias.ibovespa.map((p) => [dataUtc(p.data), p.valor]),
            degrau: false as const,
          },
        ]
      : []),
  ];
  return {
    animation: false,
    grid: { left: 52, right: 14, top: 30, bottom: 24 },
    legend: {
      top: 2,
      left: 0,
      textStyle: { color: c.textoSec, fontSize: 12 },
      icon: "roundRect",
      itemWidth: 14,
      itemHeight: 3,
    },
    tooltip: {
      trigger: "axis",
      ...b.dica,
      axisPointer: { type: "line", lineStyle: { color: c.borda } },
      formatter: (itens: { axisValue: number; seriesName: string; color: string; value: [string, number] }[]) =>
        `<div style="margin-bottom:3px;color:${c.textoSec}">${dataDaDica(itens[0].axisValue)}</div>` +
        itens.map((i) => linhaDica(i.color, i.seriesName, numero(i.value[1], 1))).join(""),
    },
    xAxis: b.eixoTempo,
    yAxis: { ...b.eixoValor, scale: true },
    series: series.map((s) => ({
      name: s.name,
      type: "line",
      data: s.pontos,
      showSymbol: false,
      step: s.degrau,
      sampling: "lttb",
      lineStyle: { color: s.cor, width: s.largura },
      itemStyle: { color: s.cor },
      emphasis: { disabled: true },
    })),
  };
}

export function opcoesDrawdown(p: Painel, c: CoresGrafico) {
  const b = baseEixos(c, periodoCurto(p.curva.map((x) => x.data)));
  return {
    animation: false,
    grid: { left: 52, right: 14, top: 8, bottom: 24 },
    tooltip: {
      trigger: "axis",
      ...b.dica,
      formatter: (itens: { axisValue: number; value: [string, number] }[]) =>
        `<div style="color:${c.textoSec}">${dataDaDica(itens[0].axisValue)}</div>` +
        linhaDica(c.perda, "Queda do pico", comSinal(itens[0].value[1], 1, "%")),
    },
    xAxis: b.eixoTempo,
    yAxis: {
      ...b.eixoValor,
      max: 0,
      min: p.indicadores.drawdown_maximo === 0 ? -1 : undefined,
      minInterval: 1,
      axisLabel: { ...b.eixoValor.axisLabel, formatter: (v: number) => `${numero(v, 0)}%` },
    },
    series: [
      {
        type: "line",
        data: p.curva.map((x) => [dataUtc(x.data), x.drawdown]),
        showSymbol: false,
        step: "end",
        sampling: "lttb",
        lineStyle: { color: c.perda, width: 1.5 },
        itemStyle: { color: c.perda },
        areaStyle: { color: c.perda, opacity: 0.18 },
        emphasis: { disabled: true },
      },
    ],
  };
}

export function opcoesTaxaMovel(p: Painel, janela: number, c: CoresGrafico) {
  const b = baseEixos(c, periodoCurto(p.taxa_movel.map((x) => x.data)));
  const geral = p.indicadores.taxa_acerto;
  return {
    animation: false,
    grid: { left: 42, right: 14, top: 14, bottom: 24 },
    tooltip: {
      trigger: "axis",
      ...b.dica,
      formatter: (itens: { axisValue: number; value: [string, number] }[]) =>
        `<div style="color:${c.textoSec}">${dataDaDica(itens[0].axisValue)}</div>` +
        linhaDica(c.serie[0], `Últimos ${janela} trades`, percentual(itens[0].value[1], 0)) +
        linhaDica(c.textoSec, "Taxa geral", percentual(geral, 1)),
    },
    xAxis: b.eixoTempo,
    yAxis: {
      ...b.eixoValor,
      min: 0,
      max: 100,
      axisLabel: { ...b.eixoValor.axisLabel, formatter: (v: number) => `${v}%` },
    },
    series: [
      {
        type: "line",
        data: p.taxa_movel.map((x) => [dataUtc(x.data), x.taxa]),
        showSymbol: false,
        lineStyle: { color: c.serie[0], width: 2 },
        itemStyle: { color: c.serie[0] },
        emphasis: { disabled: true },
        markLine:
          geral === null
            ? undefined
            : {
                silent: true,
                symbol: "none",
                lineStyle: { color: c.textoSec, type: "dashed", width: 1 },
                label: {
                  color: c.textoSec,
                  fontSize: 11,
                  position: "insideEndTop",
                  formatter: `Geral ${percentual(geral, 1)}`,
                },
                data: [{ yAxis: geral }],
              },
      },
    ],
  };
}

export function opcoesSequencia(p: Painel, c: CoresGrafico) {
  const b = baseEixos(c);
  return {
    animation: false,
    grid: { left: 42, right: 14, top: 14, bottom: 24 },
    tooltip: {
      trigger: "item",
      ...b.dica,
      formatter: (i: { dataIndex: number }) => {
        const t = p.sequencia[i.dataIndex];
        return (
          `<div style="color:${c.textoSec}">Trade ${t.numero} · ${data(t.data)}</div>` +
          linhaDica(t.resultado > 0 ? c.ganho : c.perda, "Líquido", comSinal(t.resultado, 2, "%"))
        );
      },
    },
    xAxis: {
      type: "category",
      data: p.sequencia.map((t) => t.numero),
      axisLine: { lineStyle: { color: c.borda } },
      axisTick: { show: false },
      axisLabel: { color: c.textoSec, fontSize: 11, hideOverlap: true },
    },
    yAxis: { ...b.eixoValor, axisLabel: { ...b.eixoValor.axisLabel, formatter: (v: number) => `${numero(v, 0)}%` } },
    series: [
      {
        type: "bar",
        barMaxWidth: 10,
        data: p.sequencia.map((t) => ({
          value: t.resultado,
          itemStyle: {
            color: t.resultado > 0 ? c.ganho : c.perda,
            borderRadius: t.resultado > 0 ? [3, 3, 0, 0] : [0, 0, 3, 3],
          },
        })),
      },
    ],
  };
}

export function opcoesDistribuicao(p: Painel, c: CoresGrafico) {
  const b = baseEixos(c);
  return {
    animation: false,
    grid: { left: 36, right: 14, top: 14, bottom: 40 },
    tooltip: {
      trigger: "item",
      ...b.dica,
      formatter: (i: { dataIndex: number }) => {
        const f = p.distribuicao[i.dataIndex];
        return `<div style="color:${c.textoSec}">De ${comSinal(f.de, 1, "R")} a ${comSinal(f.ate, 1, "R")}</div>${linhaDica(c.serie[0], "Trades", String(f.trades))}`;
      },
    },
    xAxis: {
      type: "category",
      data: p.distribuicao.map((f) => numero(f.de, 1)),
      name: "Resultado em R (início de cada faixa)",
      nameLocation: "middle",
      nameGap: 24,
      nameTextStyle: { color: c.textoSec, fontSize: 11 },
      axisLine: { lineStyle: { color: c.borda } },
      axisTick: { show: false },
      axisLabel: { color: c.textoSec, fontSize: 11, hideOverlap: true },
    },
    yAxis: { ...b.eixoValor, minInterval: 1 },
    series: [
      {
        type: "bar",
        barCategoryGap: 2,
        barMaxWidth: 44,
        data: p.distribuicao.map((f) => f.trades),
        itemStyle: { color: c.serie[0], borderRadius: [3, 3, 0, 0] },
      },
    ],
  };
}

export function opcoesMapaMensal(p: Painel, c: CoresGrafico) {
  const b = baseEixos(c);
  const anos = [...new Set(p.mapa_mensal.map((m) => m.ano))].sort((x, y) => y - x);
  const limite = Math.max(1, ...p.mapa_mensal.map((m) => Math.abs(m.retorno)));
  // Limita a escala para um único mês extremo não apagar a diferença entre os demais.
  const escala = Math.min(limite, 25);
  const mostrarRotulo = anos.length <= 14;
  return {
    animation: false,
    grid: { left: 44, right: 10, top: 4, bottom: 54 },
    tooltip: {
      ...b.dica,
      formatter: (i: { value: [number, number, number] }) =>
        `<div style="color:${c.textoSec}">${MESES[i.value[0]]}/${anos[i.value[1]]}</div>${linhaDica(i.value[2] > 0 ? c.ganho : c.perda, "Retorno", comSinal(i.value[2], 1, "%"))}`,
    },
    xAxis: {
      type: "category",
      data: MESES,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: c.textoSec, fontSize: 11 },
      splitArea: { show: false },
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: anos,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: c.textoSec, fontSize: 11 },
    },
    visualMap: {
      min: -escala,
      max: escala,
      calculable: false,
      orient: "horizontal",
      left: 44,
      bottom: 0,
      itemHeight: 110,
      itemWidth: 9,
      text: [`+${numero(escala, 0)}%`, `−${numero(escala, 0)}%`],
      textStyle: { color: c.textoSec, fontSize: 11 },
      inRange: { color: [c.divNeg, c.divMeio, c.divPos] },
    },
    series: [
      {
        type: "heatmap",
        data: p.mapa_mensal.map((m) => [m.mes - 1, anos.indexOf(m.ano), m.retorno]),
        label: {
          show: mostrarRotulo,
          fontSize: 10,
          color: c.texto,
          formatter: (i: { value: [number, number, number] }) => comSinal(i.value[2], 0, ""),
        },
        itemStyle: { borderColor: c.painel, borderWidth: 2, borderRadius: 3 },
      },
    ],
  };
}

export function opcoesComparacao(
  series: { nome: string; slot: number; curva: { data: string; capital: number }[] }[],
  c: CoresGrafico,
) {
  const b = baseEixos(c, periodoCurto(series[0]?.curva.map((p) => p.data) ?? []));
  return {
    animation: false,
    grid: { left: 52, right: 14, top: 34, bottom: 24 },
    legend: {
      top: 2,
      left: 0,
      textStyle: { color: c.textoSec, fontSize: 12 },
      icon: "roundRect",
      itemWidth: 14,
      itemHeight: 3,
    },
    tooltip: {
      trigger: "axis",
      ...b.dica,
      formatter: (itens: { axisValue: number; seriesName: string; color: string; value: [string, number] }[]) =>
        `<div style="margin-bottom:3px;color:${c.textoSec}">${dataDaDica(itens[0].axisValue)}</div>` +
        itens.map((i) => linhaDica(i.color, i.seriesName, numero(i.value[1], 1))).join(""),
    },
    xAxis: b.eixoTempo,
    yAxis: { ...b.eixoValor, scale: true },
    series: series.map((s) => ({
      name: s.nome,
      type: "line",
      data: s.curva.map((p) => [dataUtc(p.data), p.capital]),
      showSymbol: false,
      step: "end",
      sampling: "lttb",
      lineStyle: { color: c.serie[s.slot], width: 2 },
      itemStyle: { color: c.serie[s.slot] },
      emphasis: { disabled: true },
    })),
  };
}
