import type { CampoEsquema, Params, SetupInfo } from "../lib/tipos";

/** O formulário nasce do esquema do setup: um setup novo não exige mudança nesta tela. */
function descrever(campo: CampoEsquema) {
  const principal = campo.anyOf?.find((o) => o.type !== "null") ?? campo;
  const anulavel = !!campo.anyOf?.some((o) => o.type === "null");
  return {
    tipo: principal.type,
    anulavel,
    minimo: principal.minimum,
    maximo: principal.maximum,
    minimoExclusivo: principal.exclusiveMinimum,
  };
}

function validar(campo: CampoEsquema, valor: unknown): string | null {
  const d = descrever(campo);
  if (d.tipo === "boolean") return null;
  if (campo.enum) return campo.enum.includes(String(valor)) ? null : "Escolha uma opção.";
  if (valor === null || valor === undefined || valor === "") {
    return d.anulavel ? null : "Informe um valor.";
  }
  const n = Number(valor);
  if (Number.isNaN(n)) return "Informe um número.";
  if (d.tipo === "integer" && !Number.isInteger(n)) return "Use um número inteiro.";
  if (d.minimo !== undefined && n < d.minimo) return `O mínimo é ${d.minimo}.`;
  if (d.maximo !== undefined && n > d.maximo) return `O máximo é ${d.maximo}.`;
  if (d.minimoExclusivo !== undefined && n <= d.minimoExclusivo) return `Use um valor acima de ${d.minimoExclusivo}.`;
  return null;
}

export function errosParametros(setup: SetupInfo, valores: Params): Record<string, string> {
  const erros: Record<string, string> = {};
  for (const [nome, campo] of Object.entries(setup.esquema.properties)) {
    const erro = validar(campo, valores[nome]);
    if (erro) erros[nome] = erro;
  }
  return erros;
}

interface Props {
  setup: SetupInfo;
  valores: Params;
  aoMudar: (valores: Params) => void;
}

export function FormularioParametros({ setup, valores, aoMudar }: Props) {
  const erros = errosParametros(setup, valores);
  const mudar = (nome: string, valor: unknown) => aoMudar({ ...valores, [nome]: valor });
  const campos = Object.entries(setup.esquema.properties);
  const regras = campos.filter(([, c]) => c.grupo !== "comum");
  const comuns = campos.filter(([, c]) => c.grupo === "comum");

  const desenhar = ([nome, campo]: [string, CampoEsquema]) => {
        const d = descrever(campo);
        const id = `param-${nome}`;
        if (campo.enum) {
          return (
            <div className="campo-form" key={nome}>
              <label htmlFor={id}>{campo.title ?? nome}</label>
              <select id={id} value={String(valores[nome] ?? "")} onChange={(e) => mudar(nome, e.target.value)}>
                {campo.enum.map((opcao) => (
                  <option key={opcao} value={opcao}>
                    {campo.rotulos?.[opcao] ?? opcao}
                  </option>
                ))}
              </select>
              {campo.description && <span className="ajuda">{campo.description}</span>}
            </div>
          );
        }
        if (d.tipo === "boolean") {
          return (
            <div className="campo-form marcar" key={nome}>
              <label htmlFor={id}>
                <input id={id} type="checkbox" checked={!!valores[nome]} onChange={(e) => mudar(nome, e.target.checked)} />
                <span>
                  {campo.title ?? nome}
                  {campo.description && <span className="ajuda"><br />{campo.description}</span>}
                </span>
              </label>
            </div>
          );
        }
        const limites =
          d.minimo !== undefined && d.maximo !== undefined ? ` (${d.minimo} a ${d.maximo})` : "";
        return (
          <div className="campo-form" key={nome}>
            <label htmlFor={id}>
              {campo.title ?? nome}
              {limites}
            </label>
            <input
              id={id}
              type="number"
              step={d.tipo === "integer" ? 1 : "any"}
              value={valores[nome] === null || valores[nome] === undefined ? "" : String(valores[nome])}
              aria-invalid={!!erros[nome]}
              aria-describedby={erros[nome] ? `${id}-erro` : undefined}
              onChange={(e) => {
                const texto = e.target.value;
                mudar(nome, texto === "" ? (d.anulavel ? null : "") : Number(texto));
              }}
            />
            {campo.description && <span className="ajuda">{campo.description}</span>}
            {erros[nome] && (
              <span className="invalido" id={`${id}-erro`}>
                {erros[nome]}
              </span>
            )}
          </div>
        );
  };

  return (
    <>
      {regras.map(desenhar)}
      {comuns.length > 0 && <h3 className="grupo-form">Execução e filtros</h3>}
      {comuns.map(desenhar)}
      <div>
        <button className="botao pequeno" onClick={() => aoMudar(setup.padroes)}>
          Voltar ao padrão
        </button>
      </div>
    </>
  );
}
