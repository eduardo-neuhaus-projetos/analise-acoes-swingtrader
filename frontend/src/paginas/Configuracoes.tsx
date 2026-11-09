import { useEffect, useState } from "react";
import { Painel } from "../componentes/Comuns";
import { data } from "../lib/formatos";
import { INICIO_HISTORICO_PADRAO } from "../lib/periodo";
import { api, ErroApi } from "../lib/api";
import type { Configuracoes as Config, Custos } from "../lib/tipos";

const CAMPOS_CUSTO: { chave: keyof Custos; rotulo: string; ajuda: string }[] = [
  { chave: "corretagem_por_ordem", rotulo: "Corretagem por ordem (R$)", ajuda: "Cobrada na entrada e na saída." },
  { chave: "emolumentos_pct", rotulo: "Emolumentos por ordem (%)", ajuda: "Sobre o valor de cada ordem." },
  { chave: "slippage_pct", rotulo: "Slippage por ordem (%)", ajuda: "Piora o preço de entrada e de saída." },
  { chave: "capital_por_trade", rotulo: "Capital por trade (R$)", ajuda: "Base do resultado em reais." },
];

interface Props {
  aoMudarDados: () => void;
  aoAceitarToken: () => void;
}

export function Configuracoes({ aoMudarDados, aoAceitarToken }: Props) {
  const [config, setConfig] = useState<Config | null>(null);
  const [custos, setCustos] = useState<Record<string, string>>({});
  const [amostra, setAmostra] = useState("30");
  const [janela, setJanela] = useState("20");
  const [token, setToken] = useState("");
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [mensagemToken, setMensagemToken] = useState<{ ok: boolean; texto: string } | null>(null);
  const [testando, setTestando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.configuracoes().then((c) => {
      setConfig(c);
      setCustos(Object.fromEntries(Object.entries(c.custos).map(([k, v]) => [k, String(v)])));
      setAmostra(String(c.amostra_minima));
      setJanela(String(c.janela_movel));
    }, (e: ErroApi) => setErro(e.message));
  }, []);

  const salvar = async (e: React.FormEvent) => {
    e.preventDefault();
    setMensagem(null);
    setErro(null);
    try {
      const numeros = Object.fromEntries(Object.entries(custos).map(([k, v]) => [k, Number(v)])) as unknown as Custos;
      const c = await api.salvarConfiguracoes({ custos: numeros, amostra_minima: Number(amostra), janela_movel: Number(janela) });
      setConfig(c);
      setMensagem("Salvo. As próximas análises usam estes valores.");
      aoMudarDados();
    } catch (x) {
      setErro((x as ErroApi).message);
    }
  };

  const salvarToken = async (valor: string | null) => {
    setMensagemToken(null);
    setTestando(true);
    try {
      const r = await api.salvarToken(valor);
      setConfig((c) => c && { ...c, token_brapi_configurado: r.token_brapi_configurado });
      setToken("");
      if (!r.teste) {
        setMensagemToken({ ok: true, texto: "Token removido." });
      } else if (r.teste.ok) {
        setMensagemToken({ ok: true, texto: `Token guardado. ${r.teste.mensagem}` });
        aoAceitarToken();
      } else {
        setMensagemToken({ ok: false, texto: `Token guardado, mas o teste falhou. ${r.teste.mensagem}` });
      }
    } catch (x) {
      setMensagemToken({ ok: false, texto: (x as ErroApi).message });
    } finally {
      setTestando(false);
    }
  };

  return (
    <div className="grade-config">
      <Painel titulo="Provedor: brapi">
        <form
          className="painel-corpo form"
          onSubmit={(e) => {
            e.preventDefault();
            if (token.trim()) salvarToken(token.trim());
          }}
        >
          <p className="mudo">
            Sem token, a brapi só responde para PETR4, MGLU3, VALE3 e ITUB4. Para outros ativos na aba brapi, use um token
            da conta gratuita. A aba Yahoo não precisa de token.
          </p>
          <ol className="passos">
            <li>
              Crie uma conta gratuita em{" "}
              <a href="https://brapi.dev/" target="_blank" rel="noreferrer">
                brapi.dev
              </a>
              .
            </li>
            <li>Copie o token no painel da conta.</li>
            <li>Cole abaixo. O aplicativo testa o token na hora.</li>
          </ol>
          <p className="mudo">
            A conta gratuita continua limitada a 3 meses de candles. O token fica em um arquivo local, fora do banco, e
            nunca volta para a tela.
          </p>
          <p>
            Situação: <b>{config?.token_brapi_configurado ? "token configurado" : "sem token"}</b>
          </p>
          <div className="campo">
            <label htmlFor="token">Token da brapi</label>
            <input
              id="token"
              type="password"
              autoComplete="off"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
          </div>
          <div className="linha">
            <button className="botao primario" type="submit" disabled={!token.trim() || testando}>
              {testando ? "Testando…" : "Guardar e testar"}
            </button>
            {config?.token_brapi_configurado && (
              <button className="botao" type="button" onClick={() => salvarToken(null)}>
                Remover
              </button>
            )}
          </div>
          {mensagemToken && (
            <p className={mensagemToken.ok ? "confirmacao" : "perda"} role={mensagemToken.ok ? "status" : "alert"}>
              {mensagemToken.ok ? "" : "! "}
              {mensagemToken.texto}
            </p>
          )}
        </form>
      </Painel>

      <Painel titulo="Custos e leitura">
        <form className="painel-corpo form" onSubmit={salvar}>
          {CAMPOS_CUSTO.map((c) => (
            <div className="campo-form" key={c.chave}>
              <label htmlFor={c.chave}>{c.rotulo}</label>
              <input
                id={c.chave}
                type="number"
                min={c.chave === "capital_por_trade" ? 1 : 0}
                step="any"
                required
                value={custos[c.chave] ?? ""}
                onChange={(e) => setCustos({ ...custos, [c.chave]: e.target.value })}
              />
              <span className="ajuda">{c.ajuda}</span>
            </div>
          ))}
          <div className="campo-form">
            <label htmlFor="amostra">Limite do aviso de amostra pequena (trades)</label>
            <input
              id="amostra"
              type="number"
              min={1}
              max={1000}
              required
              value={amostra}
              onChange={(e) => setAmostra(e.target.value)}
            />
          </div>
          <div className="campo-form">
            <label htmlFor="janela">Janela da taxa de acerto móvel (trades)</label>
            <input
              id="janela"
              type="number"
              min={2}
              max={200}
              required
              value={janela}
              onChange={(e) => setJanela(e.target.value)}
            />
          </div>
          <div className="linha">
            <button className="botao primario" type="submit">
              Salvar
            </button>
            {mensagem && (
              <span className="confirmacao" role="status">
                {mensagem}
              </span>
            )}
          </div>
          {erro && (
            <p className="perda" role="alert">
              {erro}
            </p>
          )}
        </form>
      </Painel>

      <Painel titulo="Sobre os dados">
        <div className="painel-corpo form mudo">
          <p>
            <b>Histórico desde {data(config?.inicio_historico ?? INICIO_HISTORICO_PADRAO)}</b>, fixo para as duas fontes.
            Candles anteriores não são baixados, guardados nem simulados, e o calendário de período não aceita datas
            anteriores.
          </p>
          <p>
            Yahoo Finance via yfinance, sem vínculo oficial com a Yahoo e para uso pessoal. Plano Gratuito da brapi, limitado
            a 3 meses. Os dados baixados não são publicados nem compartilhados por este aplicativo.
          </p>
          <p>
            Candles com <a href="https://github.com/tradingview/lightweight-charts" target="_blank" rel="noreferrer">TradingView Lightweight Charts</a>,
            licença Apache 2.0. Painéis com Apache ECharts.
          </p>
          <p>Sem login: use só no próprio computador ou em rede privada.</p>
        </div>
      </Painel>
    </div>
  );
}
