import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef, useState } from "react";
import { coresGrafico } from "../lib/cores";
import { comSinal, data, numero, preco, volume } from "../lib/formatos";
import type { Candle, ResultadoAnalise, Tema, Trade } from "../lib/tipos";

interface Props {
  resultado: ResultadoAnalise;
  selecionado: number | null;
  aoSelecionar: (numero: number) => void;
  tema: Tema;
}

const PERIODOS: { rotulo: string; candles: number | null }[] = [
  { rotulo: "3M", candles: 63 },
  { rotulo: "1A", candles: 252 },
  { rotulo: "5A", candles: 1260 },
  { rotulo: "Tudo", candles: null },
];

export function GraficoCandles({ resultado, selecionado, aoSelecionar, tema }: Props) {
  const caixa = useRef<HTMLDivElement>(null);
  const grafico = useRef<IChartApi | null>(null);
  const serieCandles = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const serieVolume = useRef<ISeriesApi<"Histogram"> | null>(null);
  const seriesIndicadores = useRef<ISeriesApi<"Line">[]>([]);
  const seriesTrade = useRef<ISeriesApi<"Line">[]>([]);
  const marcas = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const refResultado = useRef(resultado);
  const refAoSelecionar = useRef(aoSelecionar);
  refResultado.current = resultado;
  refAoSelecionar.current = aoSelecionar;
  const [foco, setFoco] = useState<Candle | null>(null);
  const [tick, setTick] = useState(0);

  // O gráfico é recriado só com o tema; os dados entram nos efeitos abaixo, sem perder o zoom à toa.
  useEffect(() => {
    if (!caixa.current) return;
    const c = coresGrafico();
    const chart = createChart(caixa.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: c.painel },
        textColor: c.textoSec,
        fontSize: 11,
        fontFamily: '"Segoe UI", system-ui, sans-serif',
      },
      grid: { vertLines: { color: c.grade }, horzLines: { color: c.grade } },
      rightPriceScale: { borderColor: c.borda, scaleMargins: { top: 0.08, bottom: 0.2 } },
      timeScale: { borderColor: c.borda, minBarSpacing: 0.3 },
      crosshair: { mode: CrosshairMode.Normal },
      localization: {
        locale: "pt-BR",
        dateFormat: "dd/MM/yyyy",
        priceFormatter: (v: number) => preco(v),
      },
    });
    const velas = chart.addSeries(CandlestickSeries, {
      upColor: c.ganho,
      downColor: c.perda,
      wickUpColor: c.ganho,
      wickDownColor: c.perda,
      borderVisible: false,
      priceLineVisible: false,
    });
    const barras = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
      priceLineVisible: false,
      lastValueVisible: false,
    });
    chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.84, bottom: 0 } });

    seriesTrade.current = [c.textoSec, c.perda, c.alerta].map((cor, i) =>
      chart.addSeries(LineSeries, {
        color: cor,
        lineWidth: i === 0 ? 1 : 2,
        lineStyle: i === 1 ? LineStyle.Dashed : LineStyle.Solid,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        pointMarkersVisible: true,
        pointMarkersRadius: 2,
      }),
    );

    grafico.current = chart;
    serieCandles.current = velas;
    serieVolume.current = barras;
    marcas.current = createSeriesMarkers(velas, []);

    chart.subscribeCrosshairMove((p) => {
      const candles = refResultado.current.candles;
      if (!p.time) return setFoco(null);
      setFoco(candles.find((x) => x.data === p.time) ?? null);
    });
    chart.subscribeClick((p) => {
      if (!p.time) return;
      const trades = refResultado.current.trades;
      const id = typeof p.hoveredObjectId === "string" ? p.hoveredObjectId : "";
      const porMarca = id.startsWith("trade-") ? Number(id.split("-")[1]) : null;
      const alvo =
        porMarca ?? trades.find((t) => t.entrada_data === p.time || t.saida_data === p.time)?.numero ?? null;
      if (alvo !== null) refAoSelecionar.current(alvo);
    });
    setTick((t) => t + 1);

    return () => {
      chart.remove();
      grafico.current = null;
      seriesIndicadores.current = [];
    };
  }, [tema]);

  const candles = resultado.candles;
  const chaveDados = `${resultado.execucao_id}-${candles.length}-${resultado.fonte}`;

  useEffect(() => {
    const chart = grafico.current;
    if (!chart || !serieCandles.current || !serieVolume.current) return;
    const c = coresGrafico();
    serieCandles.current.setData(
      candles.map((x) => ({ time: x.data, open: x.abertura, high: x.maxima, low: x.minima, close: x.fechamento })),
    );
    serieVolume.current.setData(
      candles.map((x) => ({
        time: x.data,
        value: x.volume,
        color: (x.fechamento >= x.abertura ? c.ganho : c.perda) + "55",
      })),
    );
    seriesIndicadores.current.forEach((s) => chart.removeSeries(s));
    // A cor recomeça em cada painel: assim, linhas lado a lado nunca repetem a cor, mesmo com muitos indicadores.
    const usadasNoPainel = new Map<number, number>();
    seriesIndicadores.current = resultado.indicadores.map((ind) => {
      const ordem = usadasNoPainel.get(ind.painel_indice) ?? 0;
      usadasNoPainel.set(ind.painel_indice, ordem + 1);
      const s = chart.addSeries(
        LineSeries,
        {
          color: c.serie[ordem % c.serie.length],
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
          title: ind.rotulo,
          // IFR, ADX e ATR não estão em reais: no painel inferior, a escala mostra o valor sem R$.
          // Abaixo de 1, como no TRIX, uma casa decimal mostraria sempre zero.
          ...(ind.painel === "inferior" ? { priceFormat: { type: "custom" as const, formatter: (v: number) => numero(v, Math.abs(v) < 1 ? 3 : 1), minMove: 0.001 } } : {}),
        },
        ind.painel_indice,
      );
      s.setData(ind.pontos.map((p) => ({ time: p.data, value: p.valor })));
      return s;
    });
    const inferiores = Math.max(0, ...resultado.indicadores.map((x) => x.painel_indice));
    // Com vários painéis, a proporção divide o espaço por igual; ajustar um por um rouba altura do vizinho.
    chart.panes().forEach((p, i) => {
      p.setStretchFactor(i === 0 ? (inferiores > 1 ? 4 : 1) : 1);
    });
    if (inferiores === 1) chart.panes()[1]?.setHeight(110);
    // A primeira visão mostra cerca de um ano; 10 anos inteiros ficariam ilegíveis.
    enquadrar(chart, candles.length, candles.length > 300 ? 252 : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chaveDados, tick]);

  useEffect(() => {
    if (!marcas.current) return;
    const c = coresGrafico();
    const presentes = new Set(candles.map((x) => x.data));
    const lista: SeriesMarker<Time>[] = [];
    for (const s of resultado.sinais) {
      if (!presentes.has(s.data)) continue;
      lista.push({
        time: s.data,
        position: "belowBar",
        shape: "circle",
        size: 0.5,
        color: s.situacao === "acionado" ? c.serie[0] : c.textoTer,
        id: `sinal-${s.data}`,
      });
    }
    for (const t of resultado.trades) {
      const ativo = t.numero === selecionado;
      if (presentes.has(t.entrada_data)) {
        lista.push({
          time: t.entrada_data,
          position: "belowBar",
          shape: "arrowUp",
          size: ativo ? 1.6 : 0.9,
          color: c.serie[0],
          id: `trade-${t.numero}-entrada`,
          text: ativo ? `Entrada ${preco(t.entrada_preco)}` : undefined,
        });
      }
      if (t.saida_data && presentes.has(t.saida_data)) {
        lista.push({
          time: t.saida_data,
          position: "aboveBar",
          shape: "arrowDown",
          size: ativo ? 1.6 : 0.9,
          color: t.liquido_pct > 0 ? c.ganho : c.perda,
          id: `trade-${t.numero}-saida`,
          text: ativo ? `Saída ${preco(t.saida_preco)} (${comSinal(t.liquido_pct, 2, "%")})` : undefined,
        });
      }
    }
    lista.sort((a, b) => (String(a.time) < String(b.time) ? -1 : String(a.time) > String(b.time) ? 1 : 0));
    marcas.current.setMarkers(lista);

    const [linhaEntrada, linhaStop, linhaSaidaArmada] = seriesTrade.current;
    const trade = resultado.trades.find((t) => t.numero === selecionado);
    if (!trade || !linhaEntrada) {
      seriesTrade.current.forEach((s) => s.setData([]));
      return;
    }
    const pontos = trechoTrade(trade, candles);
    linhaEntrada.setData(pontos.map((d) => ({ time: d, value: trade.entrada_preco })));
    const stop = trade.stop;
    linhaStop.setData(stop === null ? [] : pontos.map((d) => ({ time: d, value: stop })));
    linhaSaidaArmada.setData(trade.alvo ? pontos.map((d) => ({ time: d, value: trade.alvo as number })) : []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resultado, selecionado, tick]);

  // Clicar em um trade centraliza o gráfico nele.
  useEffect(() => {
    const chart = grafico.current;
    const trade = resultado.trades.find((t) => t.numero === selecionado);
    if (!chart || !trade) return;
    const ini = candles.findIndex((x) => x.data >= trade.entrada_data);
    const fimBusca = trade.saida_data ? candles.findIndex((x) => x.data >= trade.saida_data!) : candles.length - 1;
    const fim = fimBusca < 0 ? candles.length - 1 : fimBusca;
    if (ini < 0) return;
    const margem = Math.max(25, Math.round((fim - ini) * 0.8));
    chart.timeScale().setVisibleLogicalRange({ from: ini - margem, to: fim + margem });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selecionado]);

  const mostrado = foco ?? candles[candles.length - 1];
  const variacao = mostrado ? (mostrado.fechamento / mostrado.abertura - 1) * 100 : 0;

  return (
    <>
      <div className="painel-topo">
        <h2>
          {resultado.ativo} <span className="mudo">· candles diários ajustados · {resultado.origem.provedor}</span>
        </h2>
        <div className="direita">
          <div className="chave-marcas" aria-label="Legenda das marcas">
            <span>
              <i style={{ color: "var(--serie-1)" }}>●</i>sinal
            </span>
            <span>
              <i style={{ color: "var(--serie-1)" }}>▲</i>entrada
            </span>
            <span>
              <i style={{ color: "var(--ganho)" }}>▼</i>saída com ganho
            </span>
            <span>
              <i style={{ color: "var(--perda)" }}>▼</i>saída com perda
            </span>
            <span>
              <i className="tenue">●</i>sinal sem entrada
            </span>
          </div>
          <div className="grupo-botoes" role="group" aria-label="Período visível">
            {PERIODOS.map((p) => (
              <button
                key={p.rotulo}
                className="botao pequeno"
                onClick={() => grafico.current && enquadrar(grafico.current, candles.length, p.candles)}
              >
                {p.rotulo}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className={`grafico-candles${Math.max(0, ...resultado.indicadores.map((x) => x.painel_indice)) > 1 ? " varios-paineis" : ""}`}>
        <div className="legenda" aria-hidden="true">
          {mostrado && (
            <>
              <b>{data(mostrado.data)}</b>
              <span>A {preco(mostrado.abertura)}</span>
              <span>M {preco(mostrado.maxima)}</span>
              <span>m {preco(mostrado.minima)}</span>
              <span>F {preco(mostrado.fechamento)}</span>
              <span>{comSinal(variacao, 2, "%")}</span>
              <span>Vol {volume(mostrado.volume)}</span>
            </>
          )}
        </div>
        <div ref={caixa} style={{ position: "absolute", inset: 0 }} role="img" aria-label={`Gráfico de candles de ${resultado.ativo}. Os mesmos dados dos trades estão na tabela abaixo.`} />
      </div>
    </>
  );
}

function enquadrar(chart: IChartApi, total: number, candles: number | null) {
  if (!total) return;
  if (candles === null || candles >= total) {
    chart.timeScale().fitContent();
    return;
  }
  chart.timeScale().setVisibleLogicalRange({ from: total - candles, to: total + 3 });
}

/** Do início ao fim do trade, para desenhar entrada e stop só onde valeram. */
function trechoTrade(trade: Trade, candles: Candle[]): string[] {
  const fim = trade.saida_data ?? candles[candles.length - 1]?.data;
  return candles.filter((c) => c.data >= trade.entrada_data && c.data <= fim).map((c) => c.data);
}
