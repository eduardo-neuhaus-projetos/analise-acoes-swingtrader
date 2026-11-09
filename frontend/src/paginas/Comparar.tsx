import { erroPeriodo } from "../lib/periodo";
import { useEffect, useMemo, useState } from "react";
import type { ContextoPagina } from "../App";
import { Painel } from "../componentes/Comuns";
import { GraficoEcharts } from "../componentes/GraficoEcharts";
import { api, ErroApi } from "../lib/api";
import { coresGrafico } from "../lib/cores";
import { classeResultado, comSinal, NOME_FONTE, numero, percentual, resumoParams } from "../lib/formatos";
import { guardar, lembrar } from "../lib/memoria";
import { opcoesComparacao } from "../lib/opcoesGraficos";
import type { Fonte, ItemComparacao, Kpis, ResultadoComparacao } from "../lib/tipos";

const LIMITE = 5;

const LINHAS: { rotulo: string; valor: (k: Kpis) => string; classe?: (k: Kpis) => string }[] = [
  { rotulo: "Trades", valor: (k) => String(k.trades) },
  { rotulo: "Taxa de acerto", valor: (k) => percentual(k.taxa_acerto) },
  { rotulo: "Taxa de erro", valor: (k) => percentual(k.taxa_erro) },
  { rotulo: "Payoff", valor: (k) => numero(k.payoff) },
  { rotulo: "Fator de lucro", valor: (k) => numero(k.fator_lucro) },
  { rotulo: "Expectativa", valor: (k) => comSinal(k.expectativa_r, 2, "R"), classe: (k) => classeResultado(k.expectativa_r) },
  { rotulo: "Retorno líquido", valor: (k) => comSinal(k.retorno, 1, "%"), classe: (k) => classeResultado(k.retorno) },
  { rotulo: "Drawdown máximo", valor: (k) => comSinal(k.drawdown_maximo, 1, "%"), classe: (k) => (k.drawdown_maximo ? "perda" : "") },
  { rotulo: "Duração média (pregões)", valor: (k) => numero(k.duracao_media, 1) },
  { rotulo: "Tempo exposto", valor: (k) => percentual(k.tempo_exposto, 0) },
  { rotulo: "Trades com aviso", valor: (k) => String(k.trades_com_aviso) },
];

export function Comparar({ fonte, selecao, setupAtual, tema, versaoDados, setups, inicioHistorico }: ContextoPagina) {
  // A lista é de cada aba: a comparação nunca mistura as fontes.
  const [listas, setListas] = useState<Record<Fonte, ItemComparacao[]>>(() =>
    lembrar("comparacao", { brapi: [], yahoo: [] }),
  );
  const itens = listas[fonte];
  const [resposta, setResposta] = useState<{ itens: ItemComparacao[]; resultados: ResultadoComparacao[] } | null>(null);
  const resultados = resposta?.itens === itens ? resposta.resultados : [];
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => guardar("comparacao", listas), [listas]);

  const { inicio, fim } = selecao;
  const periodoValido = erroPeriodo(selecao, inicioHistorico) === null;
  useEffect(() => {
    if (!itens.length) {
      setResposta(null);
      return;
    }
    if (!periodoValido) return;
    let cancelado = false;
    setCarregando(true);
    api
      .comparar(fonte, itens, inicio || null, fim || null)
      .then(
        (r) => {
          if (!cancelado) {
            setResposta({ itens, resultados: r });
            setErro(null);
          }
        },
        (e: ErroApi) => !cancelado && setErro(e.message),
      )
      .finally(() => !cancelado && setCarregando(false));
    return () => {
      cancelado = true;
    };
  }, [fonte, itens, inicio, fim, periodoValido, versaoDados]);

  const adicionar = () => {
    if (!selecao.ativo || !setupAtual) return;
    const ocupados = new Set(itens.map((i) => i.slot));
    const slot = [0, 1, 2, 3, 4].find((s) => !ocupados.has(s)) ?? 0;
    const id = `${selecao.ativo}|${setupAtual.id}|${JSON.stringify(selecao.params)}`;
    if (itens.some((i) => i.id === id)) {
      setErro("Esta combinação já está na comparação.");
      return;
    }
    setErro(null);
    setListas({
      ...listas,
      [fonte]: [
        ...itens,
        { id, ativo: selecao.ativo, setup_id: setupAtual.id, setup_nome: setupAtual.nome, params: selecao.params, slot },
      ],
    });
  };

  const remover = (id: string) => setListas({ ...listas, [fonte]: itens.filter((i) => i.id !== id) });

  const rotulo = (i: ItemComparacao) => {
    const padroes = setups.find((s) => s.id === i.setup_id)?.padroes;
    const texto = resumoParams(i.params, padroes);
    const base = `${i.ativo} · ${i.setup_nome}`;
    return texto === "Parâmetros padrão" ? base : `${base} (${texto})`;
  };

  const opcoes = useMemo(() => {
    const series = itens
      .map((item, n) => ({ item, r: resultados[n] }))
      .filter(({ r }) => r?.curva)
      .map(({ item, r }) => ({ nome: rotulo(item), slot: item.slot, curva: r.curva! }));
    return opcoesComparacao(series, coresGrafico());
  }, [itens, resultados, tema]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <Painel
        titulo={`Comparação na aba ${NOME_FONTE[fonte]} (${itens.length} de ${LIMITE})`}
        direita={
          <button className="botao pequeno primario" onClick={adicionar} disabled={!selecao.ativo || itens.length >= LIMITE}>
            Adicionar seleção atual{selecao.ativo ? ` (${selecao.ativo})` : ""}
          </button>
        }
      >
        <div className="painel-corpo">
          {itens.length === 0 ? (
            <p className="mudo">
              Escolha ativo, setup e parâmetros nos filtros acima e adicione aqui. Dá para comparar até {LIMITE} ativos, setups
              ou conjuntos de parâmetros.
            </p>
          ) : (
            <div className="chips">
              {itens.map((i) => (
                <span className="chip" key={i.id}>
                  <i style={{ background: `var(--serie-${i.slot + 1})` }} />
                  {rotulo(i)}
                  <button onClick={() => remover(i.id)} aria-label={`Remover ${i.ativo} da comparação`}>
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
          {erro && (
            <p className="perda" role="alert" style={{ marginTop: 6 }}>
              {erro}
            </p>
          )}
        </div>
      </Painel>

      {carregando && resultados.length === 0 && (
        <div className="painel vazio" role="status">
          <p>Calculando a comparação…</p>
        </div>
      )}
      {resultados.length > 0 && (
        <>
          <div className="aviso">
            <span className="icone" aria-hidden="true">
              i
            </span>
            Comparar só ativos que já foram bem no passado infla o resultado. Prefira uma lista definida antes do teste.
          </div>
          <Painel titulo="Indicadores lado a lado">
            <div className="tabela-rolagem">
              <table>
                <thead>
                  <tr>
                    <th>Métrica</th>
                    {itens.map((i) => (
                      <th key={i.id} className="dir" style={{ whiteSpace: "normal" }}>
                        {rotulo(i)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {LINHAS.map((l) => (
                    <tr key={l.rotulo}>
                      <td>{l.rotulo}</td>
                      {itens.map((i, n) => {
                        const r = resultados[n];
                        if (!r?.indicadores) {
                          return (
                            <td key={i.id} className="dir tenue">
                              —
                            </td>
                          );
                        }
                        return (
                          <td key={i.id} className={`dir ${l.classe?.(r.indicadores) ?? ""}`}>
                            {l.valor(r.indicadores)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {resultados.filter((r) => r.erro).map((r) => (
              <p key={r.ativo} className="perda painel-corpo" role="alert">
                {r.erro}
              </p>
            ))}
          </Painel>
          <Painel titulo="Evolução do capital (base 100)">
            <div className="painel-corpo">
              <GraficoEcharts
                opcoes={opcoes}
                altura={300}
                tema={tema}
                descricao="Curvas de capital dos itens comparados. Os valores finais estão na tabela de indicadores."
              />
            </div>
          </Painel>
        </>
      )}
    </>
  );
}
