import { useEffect, useMemo, useRef, useState } from "react";
import type { ContextoPagina } from "../App";
import { CartoesKpi, ListaAvisos, Painel, SeloEstado, SemResultado } from "../componentes/Comuns";
import { GraficoCandles } from "../componentes/GraficoCandles";
import { GraficoEcharts } from "../componentes/GraficoEcharts";
import { api, ErroApi } from "../lib/api";
import { coresGrafico } from "../lib/cores";
import { classeResultado, comSinal, data, preco, TEXTO_EVENTO, TEXTO_ORDEM } from "../lib/formatos";
import { opcoesCurva } from "../lib/opcoesGraficos";
import type { ResultadoAnalise, Trade } from "../lib/tipos";

export function Analise(props: ContextoPagina) {
  const { resultado, selecao } = props;
  if (!resultado || resultado.ativo !== selecao.ativo) {
    return <SemResultado {...props} ativo={selecao.ativo} />;
  }
  return <Conteudo {...props} resultado={resultado} />;
}

function Conteudo({
  resultado,
  tema,
  irPara,
  setupAtual,
  selecao,
  download,
}: ContextoPagina & { resultado: ResultadoAnalise }) {
  const [selecionado, setSelecionado] = useState<number | null>(null);
  const trades = useMemo(() => [...resultado.trades].reverse(), [resultado.trades]);

  useEffect(() => {
    setSelecionado(null);
  }, [resultado.execucao_id]);

  // As setas navegam entre os trades, a não ser que o foco esteja em um campo.
  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      const alvo = e.target as HTMLElement;
      if (["INPUT", "SELECT", "TEXTAREA"].includes(alvo.tagName)) return;
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      if (!trades.length) return;
      e.preventDefault();
      setSelecionado((atual) => {
        const i = trades.findIndex((t) => t.numero === atual);
        if (i < 0) return trades[0].numero;
        const proximo = e.key === "ArrowDown" ? Math.min(i + 1, trades.length - 1) : Math.max(i - 1, 0);
        return trades[proximo].numero;
      });
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [trades]);

  const trade = resultado.trades.find((t) => t.numero === selecionado) ?? null;
  const opcoes = useMemo(() => opcoesCurva(resultado, coresGrafico()), [resultado, tema]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      {download.erro && (
        <div className="aviso erro" role="alert">
          <span className="icone" aria-hidden="true">
            !
          </span>
          <span>
            A atualização falhou: {download.erro} A tela mostra os últimos dados guardados desta aba, até{" "}
            {data(resultado.origem.ultimo_pregao)}.
          </span>
        </div>
      )}
      <CartoesKpi k={resultado.painel.indicadores} />
      <ListaAvisos avisos={resultado.avisos} aoVerDados={() => irPara("dados")} />
      <div className="grade-analise">
        <div className="painel">
          <GraficoCandles resultado={resultado} selecionado={selecionado} aoSelecionar={setSelecionado} tema={tema} />
        </div>
        <div className="coluna">
          <EstadoAtual resultado={resultado} params={selecao.params} setupId={setupAtual?.id ?? null} />
          <DetalheTrade trade={trade} />
        </div>
      </div>
      <Painel titulo="Evolução do capital (base 100)">
        <div className="painel-corpo">
          <GraficoEcharts
            opcoes={opcoes}
            altura={230}
            tema={tema}
            descricao={`Retorno acumulado do setup em ${resultado.ativo}, com base 100, comparado às referências.`}
          />
          {!resultado.ibovespa_disponivel && (
            <p className="tenue">
              Sem série do Ibovespa nesta aba{resultado.fonte === "brapi" ? ": sem token, a brapi não entrega o índice" : ""}.
            </p>
          )}
        </div>
      </Painel>
      <TabelaTrades
        trades={trades}
        selecionado={selecionado}
        aoSelecionar={setSelecionado}
        execucaoId={resultado.execucao_id}
      />
    </>
  );
}

function EstadoAtual({
  resultado,
  params,
  setupId,
}: {
  resultado: ResultadoAnalise;
  params: Record<string, unknown>;
  setupId: string | null;
}) {
  const [mensagem, setMensagem] = useState<{ ok: boolean; texto: string } | null>(null);
  const aberto = resultado.trades.find((t) => t.aberto);

  useEffect(() => setMensagem(null), [resultado.execucao_id]);

  const acompanhar = async () => {
    if (!setupId) return;
    try {
      await api.acompanhar(resultado.fonte, { ativo: resultado.ativo, setup_id: setupId, params });
      setMensagem({ ok: true, texto: "Na lista de acompanhamento desta aba." });
    } catch (e) {
      setMensagem({ ok: false, texto: (e as ErroApi).message });
    }
  };

  return (
    <Painel
      titulo="Próximo pregão"
      direita={
        <button className="botao pequeno" onClick={acompanhar}>
          Acompanhar
        </button>
      }
    >
      <div className="painel-corpo">
        <SeloEstado estado={resultado.estado} />
        {aberto && (
          <p className="mudo" style={{ marginTop: 4 }}>
            Comprado desde {data(aberto.entrada_data)} a {preco(aberto.entrada_preco)}. Não realizado:{" "}
            <span className={classeResultado(aberto.liquido_pct)}>{comSinal(aberto.liquido_pct, 2, "%")}</span>
          </p>
        )}
        {resultado.ordens.length > 0 || aberto ? (
          <ul className="ordens-lista">
            {resultado.ordens.map((o) => (
              <li key={o.tipo}>
                <div>
                  {TEXTO_ORDEM[o.tipo] ?? o.tipo}
                  {o.tipo !== "entrada_abertura" && (
                    <>
                      {" "}em <b className="numero">{preco(o.preco)}</b>
                    </>
                  )}
                  {o.stop !== null && <span className="mudo"> · stop {preco(o.stop)}</span>}
                </div>
                <div className="mudo" style={{ fontSize: 12 }}>
                  {o.motivo}
                </div>
              </li>
            ))}
            {aberto && (
              <li>
                <div>
                  {aberto.stop === null ? (
                    "Sem stop técnico"
                  ) : (
                    <>
                      Stop inicial em <b className="numero">{preco(aberto.stop)}</b>
                    </>
                  )}
                  {aberto.alvo !== null && <span className="mudo"> · alvo {preco(aberto.alvo)}</span>}
                </div>
              </li>
            )}
          </ul>
        ) : (
          <p className="mudo" style={{ marginTop: 4 }}>
            Nenhuma ordem para o próximo pregão.
          </p>
        )}
        {mensagem && (
          <p className={mensagem.ok ? "confirmacao" : "perda"} style={{ marginTop: 6 }} role="status">
            {mensagem.texto}
          </p>
        )}
      </div>
    </Painel>
  );
}

function DetalheTrade({ trade }: { trade: Trade | null }) {
  if (!trade) {
    return (
      <Painel titulo="Detalhe do trade" classe="detalhe-vazio">
        <div className="painel-corpo mudo">
          Selecione um trade na tabela ou uma marca no gráfico. As setas ↑ ↓ navegam entre eles.
        </div>
      </Painel>
    );
  }
  return (
    <Painel
      titulo={`Trade ${trade.numero}${trade.aberto ? " (aberto)" : ""}`}
      direita={
        <b className={`numero ${classeResultado(trade.liquido_pct)}`}>
          {comSinal(trade.liquido_pct, 2, "%")} · {comSinal(trade.liquido_r, 2, "R")}
        </b>
      }
    >
      <div className="painel-corpo" style={{ maxHeight: 340, overflow: "auto" }}>
        <dl className="detalhe-precos">
          <div>
            <dt>Entrada</dt>
            <dd>{preco(trade.entrada_preco)}</dd>
          </div>
          <div>
            <dt>Stop inicial</dt>
            <dd>{preco(trade.stop)}</dd>
          </div>
          <div>
            <dt>Risco por ação</dt>
            <dd>{preco(trade.risco)}</dd>
          </div>
          <div>
            <dt>{trade.aberto ? "Último fechamento" : "Saída"}</dt>
            <dd>{preco(trade.aberto ? trade.preco_referencia : trade.saida_preco)}</dd>
          </div>
        </dl>
        {trade.avisos_texto.map((a) => (
          <div className="aviso alerta" key={a} style={{ marginBottom: 8 }}>
            <span className="icone" aria-hidden="true">
              !
            </span>
            {a}
          </div>
        ))}
        <ol className="linha-tempo">
          {trade.eventos.map((e, i) => (
            <li key={i}>
              <div className="cabeca">
                <span>{TEXTO_EVENTO[e.tipo] ?? e.tipo}</span>
                <span className="numero mudo">
                  {data(e.data)}
                  {e.preco !== null && ` · ${preco(e.preco)}`}
                </span>
              </div>
              <p>{e.regra}</p>
            </li>
          ))}
        </ol>
      </div>
    </Painel>
  );
}

function TabelaTrades({
  trades,
  selecionado,
  aoSelecionar,
  execucaoId,
}: {
  trades: Trade[];
  selecionado: number | null;
  aoSelecionar: (n: number) => void;
  execucaoId: number;
}) {
  const refSelecionada = useRef<HTMLTableRowElement>(null);
  useEffect(() => {
    refSelecionada.current?.scrollIntoView({ block: "nearest" });
  }, [selecionado]);

  return (
    <Painel
      titulo={`Trades (${trades.length})`}
      direita={
        <a className="botao pequeno" style={{ lineHeight: "22px", textDecoration: "none", color: "inherit" }} href={api.urlCsv(execucaoId)} download>
          Exportar CSV
        </a>
      }
    >
      {trades.length === 0 ? (
        <div className="vazio">
          <h2>O setup não gerou trades neste período</h2>
          <p>Amplie as datas ou ajuste os parâmetros. Na aba brapi a janela de 3 meses costuma gerar poucos trades.</p>
        </div>
      ) : (
        <div className="tabela-rolagem alta" tabIndex={0} aria-label="Lista de trades">
          <table>
            <thead>
              <tr>
                <th className="dir">Nº</th>
                <th>Entrada</th>
                <th className="dir">Preço</th>
                <th className="dir">Stop</th>
                <th>Saída</th>
                <th className="dir">Preço</th>
                <th>Motivo</th>
                <th className="dir">Pregões</th>
                <th className="dir">Bruto %</th>
                <th className="dir">Líquido %</th>
                <th className="dir">Líquido R</th>
                <th className="dir">Líquido R$</th>
                <th>Aviso</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr
                  key={t.numero}
                  ref={t.numero === selecionado ? refSelecionada : undefined}
                  className="clicavel"
                  aria-selected={t.numero === selecionado}
                  onClick={() => aoSelecionar(t.numero)}
                >
                  <td className="dir">{t.numero}</td>
                  <td className="numero">{data(t.entrada_data)}</td>
                  <td className="dir">{preco(t.entrada_preco)}</td>
                  <td className="dir">{preco(t.stop)}</td>
                  <td className="numero">{t.aberto ? "em aberto" : data(t.saida_data)}</td>
                  <td className="dir">{preco(t.saida_preco)}</td>
                  <td>{t.aberto ? "não realizado" : t.motivo_saida_texto}</td>
                  <td className="dir">{t.duracao_pregoes}</td>
                  <td className={`dir ${classeResultado(t.bruto_pct)}`}>{comSinal(t.bruto_pct)}</td>
                  <td className={`dir ${classeResultado(t.liquido_pct)}`}>{comSinal(t.liquido_pct)}</td>
                  <td className={`dir ${classeResultado(t.liquido_r)}`}>{comSinal(t.liquido_r)}</td>
                  <td className={`dir ${classeResultado(t.liquido_reais)}`}>{comSinal(t.liquido_reais)}</td>
                  <td title={t.avisos_texto.join(" ")}>{t.avisos.length ? "! premissa" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Painel>
  );
}
