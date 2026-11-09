import { useCallback, useEffect, useRef, useState } from "react";
import { BarraAtivos } from "./componentes/BarraAtivos";
import { BarraFiltros } from "./componentes/BarraFiltros";
import { BarraFonte } from "./componentes/BarraFonte";
import { api, ErroApi } from "./lib/api";
import { guardar, lembrar } from "./lib/memoria";
import { erroPeriodo, INICIO_HISTORICO_PADRAO } from "./lib/periodo";
import type { Fonte, Origem, Pagina, ResultadoAnalise, Selecao, SetupInfo, SituacaoDownload, Tema } from "./lib/tipos";
import { Acompanhamento } from "./paginas/Acompanhamento";
import { Analise } from "./paginas/Analise";
import { Comparar } from "./paginas/Comparar";
import { Configuracoes } from "./paginas/Configuracoes";
import { Dashboard } from "./paginas/Dashboard";
import { Dados } from "./paginas/Dados";
import { Setups } from "./paginas/Setups";
import { errosParametros } from "./componentes/FormularioParametros";

const PAGINAS: { id: Pagina; rotulo: string }[] = [
  { id: "analise", rotulo: "Análise" },
  { id: "dashboard", rotulo: "Dashboard" },
  { id: "acompanhamento", rotulo: "Acompanhamento" },
  { id: "comparar", rotulo: "Comparar" },
  { id: "setups", rotulo: "Setups" },
  { id: "dados", rotulo: "Dados" },
  { id: "configuracoes", rotulo: "Configurações" },
];
const PAGINAS_DA_FONTE: Pagina[] = ["analise", "dashboard", "acompanhamento", "comparar"];

const CODIGO_IBOVESPA = "^BVSP";

const SIMULACAO =
  "Resultados são simulações, não representam ordens executadas e não são recomendação de investimento. Resultado passado não garante resultado futuro.";

const SEM_DOWNLOAD: Record<Fonte, SituacaoDownload> = {
  brapi: { carregando: false, erro: null, codigoErro: null },
  yahoo: { carregando: false, erro: null, codigoErro: null },
};

export function App() {
  const [tema, setTema] = useState<Tema>(() => lembrar("tema", "dark"));
  const [pagina, setPagina] = useState<Pagina>(() => lembrar("pagina", "analise"));
  const [fonte, setFonte] = useState<Fonte>(() => lembrar("fonte", "yahoo"));
  const [selecao, setSelecao] = useState<Selecao>(() =>
    lembrar("selecao", { ativo: null, setupId: null, params: {}, inicio: "", fim: "" }),
  );
  const [meusAtivos, setMeusAtivos] = useState<string[]>(
    () => lembrar<string[] | null>("meusAtivos", null) ?? (selecao.ativo ? [selecao.ativo] : []),
  );
  const semListaGuardada = useRef(lembrar<string[] | null>("meusAtivos", null) === null);
  const [setups, setSetups] = useState<SetupInfo[]>([]);
  const [setupsOcultos, setSetupsOcultos] = useState<string[]>([]);
  const [inicioHistorico, setInicioHistorico] = useState(INICIO_HISTORICO_PADRAO);
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [downloads, setDownloads] = useState(SEM_DOWNLOAD);
  const [origens, setOrigens] = useState<Partial<Record<Fonte, Origem>>>({});
  const [resultados, setResultados] = useState<Partial<Record<Fonte, ResultadoAnalise>>>({});
  const [erroAnalise, setErroAnalise] = useState<Partial<Record<Fonte, { codigo: string; mensagem: string }>>>({});
  const [calculando, setCalculando] = useState(false);
  const [versaoDados, setVersaoDados] = useState(0);
  const refBusca = useRef<HTMLInputElement>(null);

  // Precisa valer já na renderização: os gráficos leem as cores do tema enquanto montam as opções.
  document.documentElement.dataset.theme = tema;
  useEffect(() => guardar("tema", tema), [tema]);
  useEffect(() => guardar("pagina", pagina), [pagina]);
  useEffect(() => guardar("fonte", fonte), [fonte]);
  useEffect(() => guardar("selecao", selecao), [selecao]);
  useEffect(() => guardar("meusAtivos", meusAtivos), [meusAtivos]);

  // Na primeira abertura, a lista começa com o que já está baixado. Depois, tirar um ativo da lista é definitivo.
  useEffect(() => {
    if (!semListaGuardada.current) return;
    api.series().then(
      (series) => {
        const baixados = series.map((s) => s.ativo).filter((a) => a !== CODIGO_IBOVESPA);
        setMeusAtivos((lista) => [...new Set([...lista, ...baixados])]);
      },
      () => undefined,
    );
  }, []);

  useEffect(() => {
    // Sem as configurações, o seletor mostra todos os setups: é melhor do que ficar sem nenhum.
    Promise.all([api.setups(), api.configuracoes().catch(() => null)])
      .then(([lista, config]) => {
        const ocultos = config?.setups_ocultos ?? [];
        const historico = config?.inicio_historico ?? INICIO_HISTORICO_PADRAO;
        setInicioHistorico(historico);
        const visiveis = lista.filter((x) => !ocultos.includes(x.id));
        setSetups(lista);
        setSetupsOcultos(ocultos);
        setErroGeral(null);
        setSelecao((s0) => {
          // Um período guardado antes da regra de 2010 volta para "todo o período".
          const s = erroPeriodo(s0, historico) ? { ...s0, inicio: "", fim: "" } : s0;
          const setup = visiveis.find((x) => x.id === s.setupId) ?? visiveis[0];
          if (!setup) return s;
          return s.setupId === setup.id
            ? { ...s, params: { ...setup.padroes, ...s.params } }
            : { ...s, setupId: setup.id, params: setup.padroes };
        });
      })
      .catch((e: ErroApi) => setErroGeral(e.message));
  }, []);

  // Acompanhamento e Comparar seguem usando a lista completa: esconder um setup só muda o seletor.
  const setupsVisiveis = setups.filter((s) => !setupsOcultos.includes(s.id));
  const setupAtual = setups.find((s) => s.id === selecao.setupId) ?? null;

  // Em fila, para que cliques rápidos cheguem ao backend na ordem em que foram feitos.
  const filaOcultos = useRef<Promise<unknown>>(Promise.resolve());
  const mudarSetupsOcultos = async (ocultos: string[]) => {
    const anteriores = setupsOcultos;
    setSetupsOcultos(ocultos);
    if (selecao.setupId && ocultos.includes(selecao.setupId)) {
      const proximo = setups.find((s) => !ocultos.includes(s.id));
      if (proximo) setSelecao((s) => ({ ...s, setupId: proximo.id, params: proximo.padroes }));
    }
    const envio = filaOcultos.current.then(() => api.salvarConfiguracoes({ setups_ocultos: ocultos }));
    filaOcultos.current = envio.catch(() => undefined);
    try {
      await envio;
    } catch (e) {
      setSetupsOcultos(anteriores);
      throw e;
    }
  };
  const paramsValidos = setupAtual ? Object.keys(errosParametros(setupAtual, selecao.params)).length === 0 : false;
  const periodoValido = erroPeriodo(selecao, inicioHistorico) === null;

  const baixar = useCallback(async (f: Fonte, ativo: string) => {
    setDownloads((d) => ({ ...d, [f]: { carregando: true, erro: null, codigoErro: null } }));
    try {
      const origem = await api.atualizar(f, ativo);
      setOrigens((o) => ({ ...o, [f]: origem }));
      setDownloads((d) => ({ ...d, [f]: { carregando: false, erro: null, codigoErro: null } }));
      setVersaoDados((v) => v + 1);
    } catch (e) {
      const erro = e as ErroApi;
      setDownloads((d) => ({ ...d, [f]: { carregando: false, erro: erro.message, codigoErro: erro.codigo } }));
      api.origem(f, ativo).then((origem) => setOrigens((o) => ({ ...o, [f]: origem })), () => undefined);
    }
  }, []);

  // Ao escolher um ativo, cada fonte usa o próprio cache ou baixa o que falta, sem depender da outra.
  const ativo = selecao.ativo;
  useEffect(() => {
    setDownloads(SEM_DOWNLOAD);
    setOrigens({});
    if (!ativo) return;
    let cancelado = false;
    (["yahoo", "brapi"] as Fonte[]).forEach(async (f) => {
      try {
        const origem = await api.origem(f, ativo);
        if (cancelado) return;
        setOrigens((o) => ({ ...o, [f]: origem }));
        if (!origem.tem_dados) await baixar(f, ativo);
      } catch (e) {
        if (!cancelado) {
          const erro = e as ErroApi;
          setDownloads((d) => ({ ...d, [f]: { carregando: false, erro: erro.message, codigoErro: erro.codigo } }));
        }
      }
    });
    return () => {
      cancelado = true;
    };
  }, [ativo, baixar]);

  // Roda o setup na aba aberta. Os dados de uma aba nunca aparecem na outra.
  const chamada = useRef(0);
  const { setupId, params, inicio, fim } = selecao;
  useEffect(() => {
    if (!ativo || !setupId || !paramsValidos || !periodoValido) return;
    const numero = ++chamada.current;
    const temporizador = setTimeout(async () => {
      setCalculando(true);
      try {
        const r = await api.analisar(fonte, {
          ativo,
          setup_id: setupId,
          params,
          inicio: inicio || null,
          fim: fim || null,
        });
        if (numero !== chamada.current) return;
        setResultados((x) => ({ ...x, [fonte]: r }));
        setErroAnalise((x) => ({ ...x, [fonte]: undefined }));
      } catch (e) {
        if (numero !== chamada.current) return;
        const erro = e as ErroApi;
        setResultados((x) => ({ ...x, [fonte]: undefined }));
        setErroAnalise((x) => ({ ...x, [fonte]: { codigo: erro.codigo, mensagem: erro.message } }));
      } finally {
        if (numero === chamada.current) setCalculando(false);
      }
    }, 200);
    return () => clearTimeout(temporizador);
  }, [fonte, ativo, setupId, params, inicio, fim, paramsValidos, periodoValido, versaoDados]);

  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      const alvo = e.target as HTMLElement;
      const digitando = ["INPUT", "SELECT", "TEXTAREA"].includes(alvo.tagName);
      if (e.key === "/" && !digitando) {
        e.preventDefault();
        refBusca.current?.focus();
        refBusca.current?.select();
      }
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, []);

  const escolherAtivo = (codigo: string) => {
    setSelecao((s) => ({ ...s, ativo: codigo }));
    setMeusAtivos((lista) => (lista.includes(codigo) ? lista : [...lista, codigo]));
    // Setups, Dados e Configurações não mostram análise: escolher um ativo lá leva para onde ele aparece.
    if (!PAGINAS_DA_FONTE.includes(pagina)) setPagina("analise");
  };

  const removerAtivo = (codigo: string) => {
    const resto = meusAtivos.filter((a) => a !== codigo);
    setMeusAtivos(resto);
    if (selecao.ativo === codigo) {
      const posicao = meusAtivos.indexOf(codigo);
      setSelecao((s) => ({ ...s, ativo: resto[posicao] ?? resto[posicao - 1] ?? null }));
    }
  };

  const resultadoBruto = resultados[fonte];
  // Resultado de outro ativo ou setup não fica na tela enquanto o novo é calculado.
  const resultado = resultadoBruto?.ativo === ativo && resultadoBruto?.setup.id === setupId ? resultadoBruto : undefined;
  const contexto = {
    fonte,
    selecao,
    setupAtual,
    resultado,
    erro: erroAnalise[fonte],
    calculando,
    download: downloads[fonte],
    tema,
    baixar: () => ativo && baixar(fonte, ativo),
    escolherAtivo,
    irPara: setPagina,
    trocarFonte: setFonte,
    aoMudarDados: () => setVersaoDados((v) => v + 1),
    versaoDados,
    setups,
    inicioHistorico,
  };

  const usaFonte = PAGINAS_DA_FONTE.includes(pagina);

  return (
    <div className="app">
      <header className="topo">
        <div className="marca">
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M5 2v12M11 1v10" stroke="var(--ganho-marca)" strokeWidth="1.4" />
            <rect x="3" y="5" width="4" height="6" fill="var(--ganho-marca)" />
            <rect x="9" y="3" width="4" height="6" fill="var(--ganho-marca)" />
          </svg>
          Swing B3
        </div>
        <nav className="navegacao" aria-label="Telas">
          {PAGINAS.map((p, i) => (
            <span key={p.id} style={{ display: "contents" }}>
              {i === 4 && <span className="separador" aria-hidden="true" />}
              <button aria-current={pagina === p.id ? "page" : undefined} onClick={() => setPagina(p.id)}>
                {p.rotulo}
              </button>
            </span>
          ))}
        </nav>
        <button
          className="botao pequeno botao-tema"
          onClick={() => setTema(tema === "dark" ? "light" : "dark")}
          aria-label={tema === "dark" ? "Mudar para o tema claro" : "Mudar para o tema escuro"}
        >
          {tema === "dark" ? "Tema claro" : "Tema escuro"}
        </button>
      </header>

      <BarraAtivos
        ativos={meusAtivos}
        atual={ativo}
        refBusca={refBusca}
        aoEscolher={escolherAtivo}
        aoRemover={removerAtivo}
      />

      {usaFonte && (
        <>
          <BarraFonte
            fonte={fonte}
            aoMudar={setFonte}
            origem={origens[fonte] ?? resultado?.origem}
            ativo={ativo}
            download={downloads[fonte]}
            aoAtualizar={() => ativo && baixar(fonte, ativo)}
          />
          {(pagina === "analise" || pagina === "dashboard" || pagina === "comparar") && (
            <BarraFiltros
              selecao={selecao}
              setups={setupsVisiveis}
              totalSetups={setups.length}
              setupAtual={setupAtual}
              inicioHistorico={inicioHistorico}
              aoEscolherSetups={() => setPagina("setups")}
              aoMudar={(parcial) => setSelecao((s) => ({ ...s, ...parcial }))}
            />
          )}
          {(downloads[fonte].carregando || calculando) && <div className="progresso" role="progressbar" aria-label="Carregando" />}
        </>
      )}

      <main className="conteudo">
        {erroGeral && (
          <div className="aviso erro" role="alert">
            <span className="icone">!</span> {erroGeral}
          </div>
        )}
        {pagina === "analise" && <Analise {...contexto} />}
        {pagina === "dashboard" && <Dashboard {...contexto} />}
        {pagina === "acompanhamento" && <Acompanhamento {...contexto} />}
        {pagina === "comparar" && <Comparar {...contexto} />}
        {pagina === "dados" && <Dados aoMudarDados={contexto.aoMudarDados} aoAnalisar={escolherAtivo} inicioHistorico={inicioHistorico} />}
        {pagina === "setups" && (
          <Setups
            setups={setups}
            setupsOcultos={setupsOcultos}
            setupAberto={selecao.setupId}
            aoMudarSetupsOcultos={mudarSetupsOcultos}
          />
        )}
        {pagina === "configuracoes" && (
          <Configuracoes aoMudarDados={contexto.aoMudarDados} aoAceitarToken={() => ativo && baixar("brapi", ativo)} />
        )}
      </main>

      <footer className="rodape">
        <span>{SIMULACAO}</span>
        <span>
          Gráficos de candles por{" "}
          <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">
            TradingView
          </a>{" "}
          Lightweight Charts™
        </span>
      </footer>
    </div>
  );
}

export type ContextoPagina = {
  fonte: Fonte;
  selecao: Selecao;
  setupAtual: SetupInfo | null;
  resultado: ResultadoAnalise | undefined;
  erro: { codigo: string; mensagem: string } | undefined;
  calculando: boolean;
  download: SituacaoDownload;
  tema: Tema;
  baixar: () => void;
  escolherAtivo: (codigo: string) => void;
  irPara: (p: Pagina) => void;
  trocarFonte: (f: Fonte) => void;
  aoMudarDados: () => void;
  versaoDados: number;
  setups: SetupInfo[];
  inicioHistorico: string;
};
