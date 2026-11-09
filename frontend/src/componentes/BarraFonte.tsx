import { data, dataHora, NOME_FONTE } from "../lib/formatos";
import type { Fonte, Origem, SituacaoDownload } from "../lib/tipos";

interface Props {
  fonte: Fonte;
  aoMudar: (f: Fonte) => void;
  origem: Origem | undefined;
  ativo: string | null;
  download: SituacaoDownload;
  aoAtualizar: () => void;
}

const DESCRICAO: Record<Fonte, string> = { brapi: "3 meses", yahoo: "histórico longo" };

/** A fonte ativa fica sempre visível, junto da origem dos dados que estão na tela. */
export function BarraFonte({ fonte, aoMudar, origem, ativo, download, aoAtualizar }: Props) {
  return (
    <div className="barra-fonte">
      <div className="abas-fonte" role="tablist" aria-label="Fonte dos dados">
        {(["brapi", "yahoo"] as Fonte[]).map((f) => (
          <button key={f} role="tab" aria-selected={fonte === f} onClick={() => aoMudar(f)}>
            {NOME_FONTE[f]}
            <small>{DESCRICAO[f]}</small>
          </button>
        ))}
      </div>
      <div className="origem" aria-live="polite">
        {origem && (
          <span>
            Fonte: <b>{origem.provedor}</b> · {origem.plano}
          </span>
        )}
        {origem?.tem_dados && (
          <>
            <span>
              Atualizado em <b className="numero">{dataHora(origem.obtida_em)}</b>
            </span>
            <span>
              Último pregão <b className="numero">{data(origem.ultimo_pregao)}</b>
            </span>
            {origem.atrasada && !download.carregando && <span className="tenue">há pregão mais novo para baixar</span>}
          </>
        )}
        {download.carregando && <span>Baixando {ativo}…</span>}
        {ativo && (
          <button className="botao pequeno acoes" onClick={aoAtualizar} disabled={download.carregando}>
            Atualizar {ativo}
          </button>
        )}
      </div>
    </div>
  );
}
