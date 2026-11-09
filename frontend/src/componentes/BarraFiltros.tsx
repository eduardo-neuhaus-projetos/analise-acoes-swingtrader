import { useEffect, useRef, useState } from "react";
import { data, resumoParams } from "../lib/formatos";
import { erroPeriodo } from "../lib/periodo";
import type { Selecao, SetupInfo } from "../lib/tipos";
import { errosParametros, FormularioParametros } from "./FormularioParametros";

interface Props {
  selecao: Selecao;
  setups: SetupInfo[];
  totalSetups: number;
  setupAtual: SetupInfo | null;
  inicioHistorico: string;
  aoMudar: (parcial: Partial<Selecao>) => void;
  aoEscolherSetups: () => void;
}

export function BarraFiltros({
  selecao,
  setups,
  totalSetups,
  setupAtual,
  inicioHistorico,
  aoMudar,
  aoEscolherSetups,
}: Props) {
  const [aberto, setAberto] = useState(false);
  const ancora = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => {
      if (!ancora.current?.contains(e.target as Node)) setAberto(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setAberto(false);
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", esc);
    };
  }, [aberto]);

  const erroDatas = erroPeriodo(selecao, inicioHistorico);
  // O navegador deixa digitar qualquer ano. Ao sair do campo, uma data anterior ao histórico vira o primeiro dia dele.
  const corrigir = (campo: "inicio" | "fim", valor: string) => {
    if (valor && valor < inicioHistorico) aoMudar({ [campo]: inicioHistorico });
  };
  const qtdErros = setupAtual ? Object.keys(errosParametros(setupAtual, selecao.params)).length : 0;

  return (
    <div className="barra-filtros">
      <div className="campo">
        <div className="rotulo-com-acao">
          <label htmlFor="setup">Setup</label>
          <button
            className="botao-texto"
            onClick={aoEscolherSetups}
            aria-label={`Escolher os setups da lista: ${setups.length} de ${totalSetups}`}
          >
            Editar lista ({setups.length} de {totalSetups})
          </button>
        </div>
        <select
          id="setup"
          value={selecao.setupId ?? ""}
          onChange={(e) => {
            const novo = setups.find((s) => s.id === e.target.value);
            if (novo) aoMudar({ setupId: novo.id, params: novo.padroes });
          }}
        >
          {[...new Set(setups.map((s) => s.familia))].map((familia) => (
            <optgroup key={familia} label={familia}>
              {setups
                .filter((s) => s.familia === familia)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.nome} (v{s.versao})
                  </option>
                ))}
            </optgroup>
          ))}
        </select>
      </div>
      <div className="campo ancora" ref={ancora}>
        <span className="rotulo">Parâmetros</span>
        <button
          className="botao"
          aria-expanded={aberto}
          aria-haspopup="dialog"
          onClick={() => setAberto(!aberto)}
          title={setupAtual ? resumoParams(selecao.params, setupAtual.padroes) : undefined}
        >
          {qtdErros ? `Corrigir ${qtdErros}` : setupAtual && resumoParams(selecao.params, setupAtual.padroes) === "Parâmetros padrão" ? "Padrão" : "Personalizados"} ▾
        </button>
        {aberto && setupAtual && (
          <div className="popover" role="dialog" aria-label={`Parâmetros de ${setupAtual.nome}`}>
            <p className="mudo">{setupAtual.descricao}</p>
            {setupAtual.origem && <p className="tenue">Origem: {setupAtual.origem}.</p>}
            <FormularioParametros
              setup={setupAtual}
              valores={selecao.params}
              aoMudar={(params) => aoMudar({ params })}
            />
          </div>
        )}
      </div>
      <div className="campo">
        <label htmlFor="inicio">Início</label>
        <input
          id="inicio"
          type="date"
          value={selecao.inicio}
          min={inicioHistorico}
          max={selecao.fim || undefined}
          aria-invalid={!!selecao.inicio && selecao.inicio < inicioHistorico}
          aria-describedby="nota-periodo"
          onChange={(e) => aoMudar({ inicio: e.target.value })}
          onBlur={(e) => corrigir("inicio", e.target.value)}
        />
      </div>
      <div className="campo">
        <label htmlFor="fim">Fim</label>
        <input
          id="fim"
          type="date"
          value={selecao.fim}
          min={selecao.inicio && selecao.inicio > inicioHistorico ? selecao.inicio : inicioHistorico}
          aria-invalid={!!selecao.fim && selecao.fim < inicioHistorico}
          aria-describedby="nota-periodo"
          onChange={(e) => aoMudar({ fim: e.target.value })}
          onBlur={(e) => corrigir("fim", e.target.value)}
        />
      </div>
      {(selecao.inicio || selecao.fim) && (
        <button className="botao" onClick={() => aoMudar({ inicio: "", fim: "" })}>
          Todo o período
        </button>
      )}
      {erroDatas ? (
        <span id="nota-periodo" className="nota-periodo invalido" role="alert">
          {erroDatas}
        </span>
      ) : (
        <span id="nota-periodo" className="nota-periodo">
          Histórico desde {data(inicioHistorico)}
        </span>
      )}
    </div>
  );
}
