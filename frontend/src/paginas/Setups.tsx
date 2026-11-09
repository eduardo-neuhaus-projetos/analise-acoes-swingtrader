import { EscolhaSetups } from "../componentes/EscolhaSetups";
import type { SetupInfo } from "../lib/tipos";

interface Props {
  setups: SetupInfo[];
  setupsOcultos: string[];
  setupAberto: string | null;
  aoMudarSetupsOcultos: (ocultos: string[]) => Promise<void>;
}

/** Escolha dos setups que aparecem nas análises, um painel por família. */
export function Setups({ setups, setupsOcultos, setupAberto, aoMudarSetupsOcultos }: Props) {
  return <EscolhaSetups setups={setups} ocultos={setupsOcultos} setupAberto={setupAberto} aoMudar={aoMudarSetupsOcultos} />;
}
