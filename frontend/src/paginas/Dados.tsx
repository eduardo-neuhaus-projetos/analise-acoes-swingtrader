import { useCallback, useEffect, useState } from "react";
import { Painel } from "../componentes/Comuns";
import { api, ErroApi } from "../lib/api";
import { data, dataHora, NOME_FONTE } from "../lib/formatos";
import type { AlertaQualidade, Fonte, SerieDados } from "../lib/tipos";

const CODIGO_IBOVESPA = "^BVSP";

export function Dados({
  aoMudarDados,
  aoAnalisar,
  inicioHistorico,
}: {
  aoMudarDados: () => void;
  aoAnalisar: (ativo: string) => void;
  inicioHistorico: string;
}) {
  const [series, setSeries] = useState<SerieDados[] | null>(null);
  const [ocupados, setOcupados] = useState<Set<string>>(new Set());
  const [erros, setErros] = useState<Record<string, string>>({});
  const [aberta, setAberta] = useState<{ fonte: Fonte; ativo: string; alertas: AlertaQualidade[] } | null>(null);
  const [erroGeral, setErroGeral] = useState<string | null>(null);

  const carregar = useCallback(() => {
    api.series().then(setSeries, (e: ErroApi) => setErroGeral(e.message));
  }, []);
  useEffect(carregar, [carregar]);

  const atualizar = async (s: SerieDados) => {
    const chave = `${s.fonte}|${s.ativo}`;
    setOcupados((o) => new Set(o).add(chave));
    setErros(({ [chave]: _, ...resto }) => resto);
    try {
      await api.atualizar(s.fonte, s.ativo);
      aoMudarDados();
    } catch (e) {
      setErros((x) => ({ ...x, [chave]: (e as ErroApi).message }));
    } finally {
      setOcupados((o) => {
        const n = new Set(o);
        n.delete(chave);
        return n;
      });
      carregar();
    }
  };

  const verAlertas = async (s: SerieDados) => {
    if (aberta?.ativo === s.ativo && aberta.fonte === s.fonte) return setAberta(null);
    setAberta({ fonte: s.fonte, ativo: s.ativo, alertas: await api.alertas(s.fonte, s.ativo) });
  };

  return (
    <>
      {erroGeral && (
        <div className="aviso erro" role="alert">
          <span className="icone" aria-hidden="true">
            !
          </span>
          {erroGeral}
        </div>
      )}
      <div className="aviso">
        <span className="icone" aria-hidden="true">
          i
        </span>
        <span>
          <b>Histórico desde {data(inicioHistorico)}.</b> Candles anteriores não são baixados, guardados nem usados na
          simulação, porque os dados mais antigos do Yahoo têm erros grosseiros. Indicadores e aquecimento dos setups
          começam nessa data.
        </span>
      </div>
      <Painel titulo="Ativos em cache">
        {series?.length === 0 ? (
          <div className="vazio">
            <h2>Nada baixado ainda</h2>
            <p>Use o campo “Adicionar ativo”, no alto da tela. Cada fonte guarda a própria série, e elas nunca se misturam.</p>
          </div>
        ) : (
          <div className="tabela-rolagem">
            <table>
              <thead>
                <tr>
                  <th>Ativo</th>
                  <th>Fonte</th>
                  <th>Período guardado</th>
                  <th className="dir">Candles</th>
                  <th>Último pregão</th>
                  <th>Atualizado em</th>
                  <th className="dir">Versão</th>
                  <th>Lacunas</th>
                  <th>Alertas</th>
                  <th>Situação</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(series ?? []).map((s) => {
                  const chave = `${s.fonte}|${s.ativo}`;
                  return (
                    <tr key={chave}>
                      <td title={s.nome ?? undefined}>
                        <b>{s.ativo}</b>
                      </td>
                      <td>{NOME_FONTE[s.fonte]}</td>
                      <td className="numero">
                        {data(s.inicio_guardado)} a {data(s.ultimo_pregao)}
                        {s.historico_curto && <span className="tenue"> · menos de 10 anos</span>}
                      </td>
                      <td className="dir">{s.candles.toLocaleString("pt-BR")}</td>
                      <td className="numero">{data(s.ultimo_pregao)}</td>
                      <td className="numero">{dataHora(s.obtida_em)}</td>
                      <td className="dir">{s.versao ?? "—"}</td>
                      <td className="numero" style={{ whiteSpace: "normal" }}>
                        {s.lacunas.length
                          ? s.lacunas.map((l) => `${data(l.de)} a ${data(l.ate)}`).join("; ")
                          : "Nenhuma"}
                      </td>
                      <td>
                        {s.alertas > 0 ? (
                          <button className="botao pequeno" onClick={() => verAlertas(s)} aria-expanded={aberta?.ativo === s.ativo && aberta.fonte === s.fonte}>
                            ! {s.alertas}
                          </button>
                        ) : (
                          <span className="mudo">Nenhum</span>
                        )}
                      </td>
                      <td style={{ whiteSpace: "normal", maxWidth: 280 }}>
                        {erros[chave] || s.ultimo_erro ? (
                          <span className="perda">! {erros[chave] ?? s.ultimo_erro}</span>
                        ) : s.aviso_rebase ? (
                          <span>! {s.aviso_rebase}</span>
                        ) : s.atrasada ? (
                          <span className="mudo">Há pregão mais novo</span>
                        ) : (
                          <span className="mudo">Em dia</span>
                        )}
                      </td>
                      <td>
                        <div className="linha">
                          {s.ativo !== CODIGO_IBOVESPA && (
                            <button className="botao pequeno" onClick={() => aoAnalisar(s.ativo)}>
                              Analisar
                            </button>
                          )}
                          <button className="botao pequeno" disabled={ocupados.has(chave)} onClick={() => atualizar(s)}>
                            {ocupados.has(chave) ? "Atualizando…" : "Atualizar"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Painel>
      {aberta && (
        <Painel titulo={`Alertas de ${aberta.ativo} · ${NOME_FONTE[aberta.fonte]} (${aberta.alertas.length})`}>
          <div className="tabela-rolagem alta" tabIndex={0} aria-label="Alertas de qualidade">
            <table>
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Alerta</th>
                </tr>
              </thead>
              <tbody>
                {aberta.alertas.map((a) => (
                  <tr key={`${a.data}-${a.tipo}`}>
                    <td className="numero">{data(a.data)}</td>
                    <td>{a.descricao}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Painel>
      )}
      <p className="tenue">
        Os candles acumulados da brapi não podem ser baixados de novo no plano Gratuito. Na aba brapi, só os 3 meses mais
        recentes aparecem em gráficos e resultados.
      </p>
    </>
  );
}
