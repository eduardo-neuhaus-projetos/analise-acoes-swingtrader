import { useEffect, useRef, useState } from "react";
import type { ErroApi } from "../lib/api";
import type { SetupInfo } from "../lib/tipos";
import { Painel } from "./Comuns";

interface Props {
  setups: SetupInfo[];
  ocultos: string[];
  setupAberto: string | null;
  aoMudar: (ocultos: string[]) => Promise<void>;
}

function MarcaFamilia({ marcados, total, ...resto }: { marcados: number; total: number } & React.InputHTMLAttributes<HTMLInputElement>) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = marcados > 0 && marcados < total;
  }, [marcados, total]);
  return <input ref={ref} type="checkbox" checked={marcados === total} {...resto} />;
}

/**
 * Um painel por família de setups, na ordem do registro. Salva a cada clique: é uma preferência de lista,
 * sem nada a confirmar, e pode ser desfeita na hora.
 */
export function EscolhaSetups({ setups, ocultos, setupAberto, aoMudar }: Props) {
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const visiveis = setups.length - ocultos.length;
  const familias = [...new Set(setups.map((s) => s.familia))];

  const aplicar = (novos: string[]) => {
    setErro(null);
    const aberto = setups.find((s) => s.id === setupAberto);
    const saiu = aberto && novos.includes(aberto.id) && !ocultos.includes(aberto.id);
    const proximo = setups.find((s) => !novos.includes(s.id));
    setAviso(saiu && proximo ? `${aberto.nome} estava aberto e saiu da lista. A análise passou para ${proximo.nome}.` : null);
    aoMudar(novos).catch((e: ErroApi) => {
      setAviso(null);
      setErro(e.message);
    });
  };

  const alternar = (id: string) => aplicar(ocultos.includes(id) ? ocultos.filter((x) => x !== id) : [...ocultos, id]);

  const alternarFamilia = (ids: string[]) => {
    const todosMarcados = ids.every((id) => !ocultos.includes(id));
    aplicar(todosMarcados ? [...ocultos, ...ids] : ocultos.filter((id) => !ids.includes(id)));
  };

  return (
    <div className="grade-config">
      <Painel
        titulo="Setups nas análises"
        classe="largura-total"
        direita={
          <>
            <span className="mudo" role="status">
              {visiveis} de {setups.length} na lista
            </span>
            <button className="botao pequeno" onClick={() => aplicar([])} disabled={ocultos.length === 0}>
              Marcar todos
            </button>
          </>
        }
      >
        <div className="painel-corpo form">
          <p className="mudo">
            Os setups marcados aparecem no seletor da Análise, do Dashboard e do Comparar. A escolha é salva na hora.
            Tirar um setup da lista não apaga resultados e não interrompe itens em Acompanhamento.
          </p>
          {visiveis === 1 && <p className="mudo">Pelo menos um setup precisa ficar na lista.</p>}
          {aviso && (
            <p className="confirmacao" role="status">
              {aviso}
            </p>
          )}
          {erro && (
            <p className="perda" role="alert">
              ! {erro}
            </p>
          )}
        </div>
      </Painel>

      {familias.map((familia) => {
        const daFamilia = setups.filter((s) => s.familia === familia);
        const ids = daFamilia.map((s) => s.id);
        const marcados = ids.filter((id) => !ocultos.includes(id)).length;
        const idFamilia = `familia-${familia.replace(/\W+/g, "-")}`;
        return (
          <Painel
            key={familia}
            titulo={<span id={idFamilia}>{familia}</span>}
            direita={
              <label className="marca-familia">
                <MarcaFamilia
                  marcados={marcados}
                  total={ids.length}
                  disabled={marcados === visiveis && marcados === ids.length}
                  aria-label={`Todos os setups de ${familia}`}
                  onChange={() => alternarFamilia(ids)}
                />
                <span className="tenue">
                  {marcados} de {ids.length}
                </span>
              </label>
            }
          >
            <div className="painel-corpo" role="group" aria-labelledby={idFamilia}>
              {daFamilia.map((s) => {
                const marcado = !ocultos.includes(s.id);
                return (
                  <label className="opcao-setup" key={s.id}>
                    <input
                      type="checkbox"
                      checked={marcado}
                      disabled={marcado && visiveis === 1}
                      aria-label={s.nome}
                      aria-describedby={`descricao-${s.id}`}
                      onChange={() => alternar(s.id)}
                    />
                    <span>
                      <b>{s.nome}</b>
                      {s.id === setupAberto && <span className="selo-aberto">aberto</span>}
                      <span className="ajuda" id={`descricao-${s.id}`}>
                        {s.descricao}
                      </span>
                      {s.origem && <span className="ajuda tenue">Origem: {s.origem}</span>}
                    </span>
                  </label>
                );
              })}
            </div>
          </Painel>
        );
      })}
    </div>
  );
}
