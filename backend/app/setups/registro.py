"""Registro de setups: incluir um setup aqui basta para ele aparecer na API e nas telas."""
from __future__ import annotations

from app.setups.base import Setup
from app.setups.candle import Setup123, SetupElefante, SetupInside, SetupPFR, SetupPontoContinuo
from app.setups.familia_larry import LarryWilliams92, LarryWilliams93, LarryWilliams94
from app.setups.internacionais import SetupDonchian, SetupHolyGrail, SetupRoss
from app.setups.larry_williams_9_1 import LarryWilliams91
from app.setups.padroes_candle import SetupDeliberante, SetupMatHold, SetupPenetrante, SetupSeparacaoAlta
from app.setups.por_indicador import SetupBollinger, SetupCruzamento, SetupDidi, SetupIFR2, SetupRecuoIFR

SETUPS: dict[str, Setup] = {
    s.id: s
    for s in [
        LarryWilliams91(),
        LarryWilliams92(),
        LarryWilliams93(),
        LarryWilliams94(),
        Setup123(),
        SetupPFR(),
        SetupPontoContinuo(),
        SetupElefante(),
        SetupInside(),
        SetupSeparacaoAlta(),
        SetupMatHold(),
        SetupPenetrante(),
        SetupDeliberante(),
        SetupIFR2(),
        SetupRecuoIFR(),
        SetupDidi(),
        SetupCruzamento(),
        SetupBollinger(),
        SetupHolyGrail(),
        SetupRoss(),
        SetupDonchian(),
    ]
}


def obter_setup(setup_id: str) -> Setup | None:
    return SETUPS.get(setup_id)
