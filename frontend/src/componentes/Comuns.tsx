import type { ReactNode } from "react";
import { classeResultado, comSinal, numero, percentual, TEXTO_ESTADO } from "../lib/formatos";
import type { Aviso, Fonte, Kpis, Pagina, SituacaoDownload } from "../lib/tipos";

export function CartoesKpi({ k }: { k: Kpis }) {
  const cartoes: { rotulo: string; valor: string; detalhe?: string; classe?: string }[] = [
    { rotulo: "Trades", valor: String(k.trades), detalhe: k.abertos ? `+ ${k.abertos} aberto` : "encerrados" },
    { rotulo: "Taxa de acerto", valor: percentual(k.taxa_acerto), detalhe: `${k.acertos} acertos` },
    {
      rotulo: "Taxa de erro",
      valor: percentual(k.taxa_erro),
      detalhe: `${k.erros} erros${k.empates ? `, ${k.empates} empates` : ""}`,
    },
    {
      rotulo: "Payoff",
      valor: numero(k.payoff),
      detalhe: `${comSinal(k.ganho_medio, 1, "%")} / ${comSinal(k.perda_media, 1, "%")}`,
    },
    { rotulo: "Fator de lucro", valor: numero(k.fator_lucro), detalhe: "ganhos ÷ perdas" },
    {
      rotulo: "Expectativa",
      valor: comSinal(k.expectativa_r, 2, "R"),
      classe: classeResultado(k.expectativa_r),
      detalhe: "média por trade",
    },
    {
      rotulo: "Retorno líquido",
      valor: comSinal(k.retorno, 1, "%"),
      classe: classeResultado(k.retorno),
      detalhe: `bruto ${comSinal(k.retorno_bruto, 1, "%")}`,
    },
    {
      rotulo: "Drawdown máximo",
      valor: comSinal(k.drawdown_maximo, 1, "%"),
      classe: k.drawdown_maximo ? "perda" : "",
      detalhe: `exposto ${percentual(k.tempo_exposto, 0)}`,
    },
  ];
  return (
    <dl className="kpis" style={{ margin: 0 }}>
      {cartoes.map((c) => (
        <div className="kpi" key={c.rotulo}>
          <dt>{c.rotulo}</dt>
          <dd className={c.classe}>
            {c.valor}
            {c.detalhe && <small>{c.detalhe}</small>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function ListaAvisos({ avisos, aoVerDados }: { avisos: Aviso[]; aoVerDados?: () => void }) {
  if (!avisos.length) return null;
  return (
    <ul className="avisos" aria-label="Avisos sobre esta análise">
      {avisos.map((a) => (
        <li key={a.tipo} className={`aviso ${a.nivel === "alerta" ? "alerta" : ""}`}>
          <span className="icone" aria-hidden="true">
            {a.nivel === "alerta" ? "!" : "i"}
          </span>
          <span>
            {a.texto}{" "}
            {a.tipo === "qualidade" && aoVerDados && (
              <button className="link" onClick={aoVerDados}>
                Ver a lista
              </button>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function SeloEstado({ estado }: { estado: string }) {
  const info = TEXTO_ESTADO[estado] ?? { rotulo: estado, icone: "○" };
  return (
    <span className="estado">
      <span aria-hidden="true">{info.icone}</span>
      {info.rotulo}
    </span>
  );
}

export function Painel({
  titulo,
  direita,
  children,
  classe,
}: {
  titulo: ReactNode;
  direita?: ReactNode;
  children: ReactNode;
  classe?: string;
}) {
  return (
    <section className={`painel ${classe ?? ""}`}>
      <div className="painel-topo">
        <h2>{titulo}</h2>
        {direita && <div className="direita">{direita}</div>}
      </div>
      {children}
    </section>
  );
}

/** Estados da tela antes de haver resultado: primeiro uso, carregando, falha da fonte. */
export function SemResultado({
  ativo,
  erro,
  download,
  baixar,
  escolherAtivo,
  calculando,
  fonte,
  irPara,
  trocarFonte,
}: {
  ativo: string | null;
  erro?: { codigo: string; mensagem: string };
  download: SituacaoDownload;
  baixar: () => void;
  escolherAtivo: (c: string) => void;
  calculando: boolean;
  fonte: Fonte;
  irPara: (p: Pagina) => void;
  trocarFonte: (f: Fonte) => void;
}) {
  if (!ativo) {
    return (
      <div className="painel vazio">
        <h2>Adicione o primeiro ativo</h2>
        <p>Use o campo “Adicionar ativo”, no alto da tela, ou comece por um destes, que funcionam nas duas abas sem cadastro:</p>
        <div className="acoes">
          {["PETR4", "VALE3", "ITUB4", "MGLU3"].map((c) => (
            <button key={c} className="botao" onClick={() => escolherAtivo(c)}>
              {c}
            </button>
          ))}
        </div>
      </div>
    );
  }
  if (download.carregando) {
    return (
      <div className="painel vazio" role="status">
        <h2>Baixando {ativo}…</h2>
        <p>No primeiro download de um ativo, o histórico do Yahoo desde 2010 leva alguns segundos.</p>
      </div>
    );
  }
  if (download.codigoErro === "token_necessario" || download.codigoErro === "token_recusado") {
    return (
      <div className="painel vazio" role="alert">
        <h2>A aba brapi precisa de um token para {ativo}</h2>
        <p>{download.erro}</p>
        <p className="tenue">A conta gratuita da brapi mostra só os 3 meses mais recentes. A aba Yahoo não pede cadastro.</p>
        <div className="acoes">
          <button className="botao primario" onClick={() => irPara("configuracoes")}>
            Configurar o token
          </button>
          <button className="botao" onClick={() => trocarFonte("yahoo")}>
            Ver {ativo} na aba Yahoo
          </button>
        </div>
      </div>
    );
  }
  if (download.erro) {
    return (
      <div className="painel vazio" role="alert">
        <h2>Esta fonte não trouxe dados de {ativo}</h2>
        <p>{download.erro}</p>
        <p className="tenue">A outra aba não é afetada, e uma fonte nunca substitui a outra.</p>
        <div className="acoes">
          <button className="botao" onClick={baixar}>
            Tentar de novo
          </button>
          {fonte === "brapi" && (
            <button className="botao" onClick={() => trocarFonte("yahoo")}>
              Ver {ativo} na aba Yahoo
            </button>
          )}
        </div>
      </div>
    );
  }
  if (erro?.codigo === "sem_dados") {
    return (
      <div className="painel vazio">
        <h2>Ainda não há dados de {ativo} nesta aba</h2>
        <div className="acoes">
          <button className="botao primario" onClick={baixar}>
            Baixar candles
          </button>
        </div>
      </div>
    );
  }
  if (erro) {
    return (
      <div className="aviso erro" role="alert">
        <span className="icone" aria-hidden="true">
          !
        </span>
        {erro.mensagem}
      </div>
    );
  }
  return (
    <div className="painel vazio" role="status">
      <p>{calculando ? "Calculando…" : "Preparando a análise…"}</p>
    </div>
  );
}
