import { useCallback, useEffect, useState } from "react";
import type { ContextoPagina } from "../App";
import { Painel, SeloEstado } from "../componentes/Comuns";
import { api, ErroApi } from "../lib/api";
import { data, dataHora, NOME_FONTE, preco, TEXTO_ORDEM, resumoParams, TEXTO_EVENTO } from "../lib/formatos";
import type { EventoAcompanhamento, ItemAcompanhamento, Ordem } from "../lib/tipos";

function textoOrdem(o: Ordem) {
  return o.tipo === "entrada_abertura" ? TEXTO_ORDEM[o.tipo] : `${TEXTO_ORDEM[o.tipo] ?? o.tipo} ${preco(o.preco)}`;
}

export function Acompanhamento({ fonte, selecao, setups, aoMudarDados }: ContextoPagina) {
  const [itens, setItens] = useState<ItemAcompanhamento[]>([]);
  const [eventos, setEventos] = useState<EventoAcompanhamento[]>([]);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resumo, setResumo] = useState<string | null>(null);

  const carregar = useCallback(() => {
    api.acompanhamento(fonte).then(
      (r) => {
        setItens(r.itens);
        setEventos(r.eventos);
      },
      (e: ErroApi) => setErro(e.message),
    );
  }, [fonte]);

  useEffect(() => {
    setErro(null);
    setResumo(null);
    carregar();
  }, [carregar]);

  const processar = async () => {
    setOcupado(true);
    setErro(null);
    setResumo(null);
    try {
      const r = await api.processarAcompanhamento(fonte);
      const falhas = Object.entries(r.falhas);
      setResumo(`${r.processados} ${r.processados === 1 ? "item atualizado" : "itens atualizados"}${falhas.length ? `, ${falhas.length} com falha` : ""}.`);
      aoMudarDados();
    } catch (e) {
      setErro((e as ErroApi).message);
    } finally {
      setOcupado(false);
      carregar();
    }
  };

  const adicionar = async () => {
    if (!selecao.ativo || !selecao.setupId) return;
    setErro(null);
    try {
      await api.acompanhar(fonte, { ativo: selecao.ativo, setup_id: selecao.setupId, params: selecao.params });
      carregar();
    } catch (e) {
      setErro((e as ErroApi).message);
    }
  };

  const remover = async (id: number) => {
    await api.removerAcompanhamento(id).catch((e: ErroApi) => setErro(e.message));
    carregar();
  };

  return (
    <>
      {erro && (
        <div className="aviso erro" role="alert">
          <span className="icone" aria-hidden="true">
            !
          </span>
          {erro}
        </div>
      )}
      <Painel
        titulo={`Lista de acompanhamento · aba ${NOME_FONTE[fonte]}`}
        direita={
          <>
            {resumo && (
              <span className="confirmacao" role="status">
                {resumo}
              </span>
            )}
            {selecao.ativo && (
              <button className="botao pequeno" onClick={adicionar}>
                Adicionar {selecao.ativo}
              </button>
            )}
            <button className="botao pequeno primario" onClick={processar} disabled={ocupado || !itens.length}>
              {ocupado ? "Atualizando…" : "Atualizar agora"}
            </button>
          </>
        }
      >
        {itens.length === 0 ? (
          <div className="vazio">
            <h2>Nenhum item nesta aba</h2>
            <p>
              Abra um ativo na Análise e use “Acompanhar”. Cada item combina ativo, setup e parâmetros, e pertence só a
              esta aba.
            </p>
          </div>
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela-cartoes">
              <thead>
                <tr>
                  <th>Ativo</th>
                  <th>Estado</th>
                  <th>Ordens para o próximo pregão</th>
                  <th>Setup</th>
                  <th>Desde</th>
                  <th>Último pregão</th>
                  <th>Situação</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {itens.map((i) => {
                  const padroes = setups.find((s) => s.id === i.setup_id)?.padroes;
                  return (
                    <tr key={i.id}>
                      <td data-rotulo="Ativo">
                        <b>{i.ativo}</b>
                      </td>
                      <td data-rotulo="Estado">
                        <SeloEstado estado={i.estado} />
                      </td>
                      <td data-rotulo="Ordens" className="numero">
                        {i.ordens.length ? i.ordens.map(textoOrdem).join(" · ") : "Nenhuma"}
                        {i.posicao && (
                          <span className="mudo"> · comprado a {preco(i.posicao.entrada_preco)}, {i.posicao.stop === null ? "sem stop" : `stop ${preco(i.posicao.stop)}`}{i.posicao.alvo !== null && `, alvo ${preco(i.posicao.alvo)}`}</span>
                        )}
                        {i.ordens[0]?.stop != null && <span className="mudo"> · stop {preco(i.ordens[0].stop)}</span>}
                      </td>
                      <td data-rotulo="Setup">
                        {i.setup_nome} v{i.setup_versao}
                        <div className="mudo" style={{ fontSize: 11, whiteSpace: "normal" }}>
                          {resumoParams(i.params, padroes)}
                        </div>
                      </td>
                      <td data-rotulo="Desde" className="numero">
                        {data(i.data_inicio)}
                      </td>
                      <td data-rotulo="Último pregão" className="numero">
                        {data(i.ultimo_pregao)}
                      </td>
                      <td data-rotulo="Situação" style={{ whiteSpace: "normal" }}>
                        {i.ultimo_erro ? (
                          <span className="perda">
                            ! Falhou em {dataHora(i.ultimo_erro_em)}: {i.ultimo_erro}
                          </span>
                        ) : (
                          <span className="mudo">Em dia</span>
                        )}
                      </td>
                      <td data-rotulo="">
                        <button className="botao pequeno" onClick={() => remover(i.id)} aria-label={`Remover ${i.ativo}`}>
                          Remover
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Painel>
      <Painel titulo="Eventos recentes">
        {eventos.length === 0 ? (
          <div className="painel-corpo mudo">Sinais, entradas e saídas aparecem aqui a partir da data de início de cada item.</div>
        ) : (
          <div className="tabela-rolagem alta" tabIndex={0} aria-label="Eventos recentes">
            <table className="tabela-cartoes">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Ativo</th>
                  <th>Evento</th>
                  <th className="dir">Preço</th>
                  <th>Regra</th>
                  <th className="dir">Versão da série</th>
                </tr>
              </thead>
              <tbody>
                {eventos.map((e) => (
                  <tr key={e.id}>
                    <td data-rotulo="Data" className="numero">
                      {data(e.data)}
                    </td>
                    <td data-rotulo="Ativo">{e.ativo}</td>
                    <td data-rotulo="Evento">{TEXTO_EVENTO[e.tipo] ?? e.tipo}</td>
                    <td data-rotulo="Preço" className="dir">
                      {preco(e.preco)}
                    </td>
                    <td data-rotulo="Regra" className="mudo" style={{ whiteSpace: "normal" }}>
                      {e.descricao}
                    </td>
                    <td data-rotulo="Versão" className="dir">
                      {e.serie_versao}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Painel>
      <p className="tenue">
        Nesta versão a atualização é manual, no botão “Atualizar agora”. O agendamento automático após o pregão fica para
        a próxima.
      </p>
    </>
  );
}
