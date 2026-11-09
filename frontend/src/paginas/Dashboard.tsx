import { useMemo } from "react";
import type { ContextoPagina } from "../App";
import { CartoesKpi, ListaAvisos, Painel, SemResultado } from "../componentes/Comuns";
import { GraficoEcharts } from "../componentes/GraficoEcharts";
import { coresGrafico } from "../lib/cores";
import { classeResultado, comSinal, percentual } from "../lib/formatos";
import {
  opcoesCurva,
  opcoesDistribuicao,
  opcoesDrawdown,
  opcoesMapaMensal,
  opcoesSequencia,
  opcoesTaxaMovel,
} from "../lib/opcoesGraficos";
import type { ResultadoAnalise } from "../lib/tipos";

export function Dashboard(props: ContextoPagina) {
  const { resultado, selecao } = props;
  if (!resultado || resultado.ativo !== selecao.ativo) {
    return <SemResultado {...props} ativo={selecao.ativo} />;
  }
  return <Paineis {...props} resultado={resultado} />;
}

function Paineis({ resultado, tema, irPara }: ContextoPagina & { resultado: ResultadoAnalise }) {
  const p = resultado.painel;
  const k = p.indicadores;
  const JANELA = resultado.janela_movel;
  const o = useMemo(() => {
    const c = coresGrafico();
    return {
      curva: opcoesCurva(resultado, c),
      drawdown: opcoesDrawdown(p, c),
      movel: opcoesTaxaMovel(p, JANELA, c),
      sequencia: opcoesSequencia(p, c),
      mapa: opcoesMapaMensal(p, c),
      distribuicao: opcoesDistribuicao(p, c),
    };
  }, [resultado, tema]); // eslint-disable-line react-hooks/exhaustive-deps

  const alturaMapa = Math.min(620, 90 + new Set(p.mapa_mensal.map((m) => m.ano)).size * 22);

  return (
    <>
      <CartoesKpi k={k} />
      <ListaAvisos avisos={resultado.avisos} aoVerDados={() => irPara("dados")} />
      {k.trades === 0 && (
        <div className="painel vazio">
          <h2>Sem trades encerrados neste período</h2>
          <p>Amplie as datas ou ajuste os parâmetros para ver as curvas e os mapas.</p>
        </div>
      )}
      {k.trades > 0 && (
        <div className="grade-dashboard">
          <Painel titulo="Evolução do capital (base 100)" classe="largo">
            <div className="painel-corpo">
              <GraficoEcharts
                opcoes={o.curva}
                altura={280}
                tema={tema}
                descricao="Retorno acumulado do setup com base 100, comparado ao buy and hold e ao Ibovespa."
              />
              <h3 className="mudo" style={{ fontSize: 12, fontWeight: 600, marginTop: 6 }}>
                Queda da curva
              </h3>
              <GraficoEcharts
                opcoes={o.drawdown}
                altura={110}
                tema={tema}
                descricao={`Drawdown em cada data. A maior queda foi de ${comSinal(k.drawdown_maximo, 1, "%")}.`}
              />
            </div>
          </Painel>
          <Painel titulo={`Taxa de acerto nos últimos ${JANELA} trades`}>
            <div className="painel-corpo">
              {p.taxa_movel.length === 0 ? (
                <p className="mudo">
                  São necessários {JANELA} trades encerrados para esta curva, e há {k.trades}.
                </p>
              ) : (
                <GraficoEcharts
                  opcoes={o.movel}
                  altura={220}
                  tema={tema}
                  descricao={`Taxa de acerto móvel, com a taxa geral de ${percentual(k.taxa_acerto)} como referência.`}
                />
              )}
            </div>
          </Painel>
          <Painel titulo="Sequência de trades (líquido %)">
            <div className="painel-corpo">
              <GraficoEcharts
                opcoes={o.sequencia}
                altura={220}
                tema={tema}
                descricao="Resultado líquido de cada trade, em ordem cronológica, em barras acima e abaixo de zero."
              />
            </div>
          </Painel>
          <Painel titulo="Retorno por mês e ano (%)">
            <div className="painel-corpo">
              <GraficoEcharts
                opcoes={o.mapa}
                altura={alturaMapa}
                tema={tema}
                descricao="Mapa de calor com o retorno composto de cada mês. Os valores do resultado anual estão na tabela ao lado."
              />
            </div>
          </Painel>
          <div className="coluna">
            <Painel titulo="Resultado anual">
              <div className="tabela-rolagem" style={{ maxHeight: 260 }} tabIndex={0} aria-label="Resultado por ano">
                <table>
                  <thead>
                    <tr>
                      <th>Ano</th>
                      <th className="dir">Trades</th>
                      <th className="dir">Taxa de acerto</th>
                      <th className="dir">Retorno</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...p.anual].reverse().map((a) => (
                      <tr key={a.ano}>
                        <td className="numero">{a.ano}</td>
                        <td className="dir">{a.trades}</td>
                        <td className="dir">{percentual(a.taxa_acerto, 0)}</td>
                        <td className={`dir ${classeResultado(a.retorno)}`}>{comSinal(a.retorno, 1, "%")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Painel>
            <Painel titulo="Distribuição dos resultados em R">
              <div className="painel-corpo">
                {resultado.painel.distribuicao.length === 0 ? (
                  <p className="mudo">
                    Sem resultado em R: é preciso um trade encerrado com stop. Sem stop técnico, como no IFR2 padrão, o
                    risco de cada trade fica indefinido.
                  </p>
                ) : (
                  <GraficoEcharts
                    opcoes={o.distribuicao}
                    altura={210}
                    tema={tema}
                    descricao="Histograma com a quantidade de trades por faixa de resultado em R."
                  />
                )}
              </div>
            </Painel>
          </div>
        </div>
      )}
    </>
  );
}
