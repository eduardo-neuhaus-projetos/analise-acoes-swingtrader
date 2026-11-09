import type { RefObject } from "react";
import { BuscaAtivo } from "./BuscaAtivo";

interface Props {
  ativos: string[];
  atual: string | null;
  refBusca: RefObject<HTMLInputElement | null>;
  aoEscolher: (codigo: string) => void;
  aoRemover: (codigo: string) => void;
}

/** Fica em todas as telas: é daqui que se adiciona um ativo e se troca o ativo em análise. */
export function BarraAtivos({ ativos, atual, refBusca, aoEscolher, aoRemover }: Props) {
  return (
    <div className="barra-ativos">
      <span className="barra-ativos-titulo" id="titulo-meus-ativos">
        Meus ativos
      </span>
      {ativos.length > 0 && (
        <ul className="lista-ativos" aria-labelledby="titulo-meus-ativos">
          {ativos.map((codigo) => (
            <li key={codigo} className={codigo === atual ? "atual" : undefined}>
              <button
                className="ativo-abrir"
                aria-current={codigo === atual ? "true" : undefined}
                onClick={() => aoEscolher(codigo)}
              >
                {codigo}
              </button>
              <button
                className="ativo-tirar"
                aria-label={`Tirar ${codigo} da lista`}
                title="Tira da lista. Os dados guardados continuam."
                onClick={() => aoRemover(codigo)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <BuscaAtivo refBusca={refBusca} ativos={ativos} aoEscolher={aoEscolher} />
    </div>
  );
}
