import { BarChart, HeatmapChart, LineChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";
import type { Tema } from "../lib/tipos";

echarts.use([
  LineChart,
  BarChart,
  HeatmapChart,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

interface Props {
  opcoes: echarts.EChartsCoreOption;
  altura: number;
  tema: Tema;
  descricao: string;
}

export function GraficoEcharts({ opcoes, altura, tema, descricao }: Props) {
  const caixa = useRef<HTMLDivElement>(null);
  const instancia = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!caixa.current) return;
    const grafico = echarts.init(caixa.current, undefined, { locale: "PT-br" });
    instancia.current = grafico;
    const observador = new ResizeObserver(() => grafico.resize());
    observador.observe(caixa.current);
    return () => {
      observador.disconnect();
      grafico.dispose();
      instancia.current = null;
    };
  }, [tema]);

  useEffect(() => {
    instancia.current?.setOption(opcoes, true);
  }, [opcoes, tema]);

  return <div ref={caixa} className="grafico" style={{ height: altura }} role="img" aria-label={descricao} />;
}
