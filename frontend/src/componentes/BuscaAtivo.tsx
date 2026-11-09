import { RefObject, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { AtivoBusca } from "../lib/tipos";

interface Props {
  refBusca: RefObject<HTMLInputElement | null>;
  ativos: string[];
  aoEscolher: (codigo: string) => void;
}

const CODIGO_B3 = /^[A-Z]{4}\d{1,2}$/;

export function BuscaAtivo({ refBusca, ativos, aoEscolher }: Props) {
  const [texto, setTexto] = useState("");
  const [lista, setLista] = useState<AtivoBusca[]>([]);
  const [termoDaLista, setTermoDaLista] = useState<string | null>(null);
  const [aberta, setAberta] = useState(false);
  const [indice, setIndice] = useState(0);
  const caixa = useRef<HTMLDivElement>(null);

  // Com o campo vazio a lista traz todos os ativos, para dar para escolher sem saber o código.
  useEffect(() => {
    if (!aberta) return;
    let cancelado = false;
    const termo = texto.trim();
    const t = setTimeout(() => {
      api.buscarAtivos(termo).then(
        (r) => {
          if (!cancelado) {
            setLista(r);
            setTermoDaLista(termo);
            setIndice(0);
          }
        },
        () => !cancelado && setLista([]),
      );
    }, 120);
    return () => {
      cancelado = true;
      clearTimeout(t);
    };
  }, [texto, aberta]);

  useEffect(() => {
    const fora = (e: MouseEvent) => {
      if (!caixa.current?.contains(e.target as Node)) setAberta(false);
    };
    document.addEventListener("mousedown", fora);
    return () => document.removeEventListener("mousedown", fora);
  }, []);

  const digitado = texto.trim();
  const listaEmDia = termoDaLista === digitado;
  const codigoDigitado = digitado.toUpperCase();
  // Código fora da lista inicial: oferece tentar o download, e a fonte responde se ele existe.
  const opcoes: AtivoBusca[] =
    CODIGO_B3.test(codigoDigitado) && !lista.some((a) => a.codigo === codigoDigitado)
      ? [...lista, { codigo: codigoDigitado, nome: "Buscar este código nas fontes" }]
      : lista;

  const escolher = (codigo: string) => {
    aoEscolher(codigo);
    setTexto("");
    setLista([]);
    setTermoDaLista(null);
    setAberta(false);
    refBusca.current?.blur();
  };

  const aoTeclar = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setAberta(true);
      setIndice((i) => Math.min(i + 1, opcoes.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setIndice((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      // Quem tecla Enter antes de a lista chegar não pode cair no resultado da busca anterior.
      if (CODIGO_B3.test(codigoDigitado)) escolher(codigoDigitado);
      else if (aberta && listaEmDia && opcoes[indice]) escolher(opcoes[indice].codigo);
    } else if (e.key === "Escape") {
      setAberta(false);
      refBusca.current?.blur();
    }
  };

  const mostrarLista = aberta && (opcoes.length > 0 || digitado !== "");

  return (
    <div className="busca" ref={caixa}>
      <span className="busca-mais" aria-hidden="true">
        +
      </span>
      <input
        id="busca-ativo"
        ref={refBusca}
        type="search"
        role="combobox"
        aria-label="Adicionar ativo: digite o código ou o nome"
        aria-expanded={mostrarLista}
        aria-controls="busca-lista"
        autoComplete="off"
        placeholder="Adicionar ativo"
        value={texto}
        onChange={(e) => {
          setTexto(e.target.value);
          setAberta(true);
        }}
        onFocus={() => setAberta(true)}
        onClick={() => setAberta(true)}
        onKeyDown={aoTeclar}
      />
      {!texto && <kbd aria-hidden="true">/</kbd>}
      {mostrarLista && (
        <ul className="busca-lista" id="busca-lista" role="listbox" aria-label="Ativos">
          {opcoes.map((a, i) => (
            <li
              key={a.codigo}
              role="option"
              aria-selected={i === indice}
              onMouseEnter={() => setIndice(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                escolher(a.codigo);
              }}
            >
              <b>{a.codigo}</b>
              <span className="mudo">{a.nome}</span>
              {ativos.includes(a.codigo) && <span className="tenue na-lista">na lista</span>}
            </li>
          ))}
          {opcoes.length === 0 && listaEmDia && (
            <li className="sem-resultado">Nenhum ativo com “{digitado}”. Tente o código completo, como PETR4.</li>
          )}
        </ul>
      )}
    </div>
  );
}
