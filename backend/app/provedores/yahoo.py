"""Yahoo Finance via yfinance: histórico desde o início do app (2010). Sem vínculo oficial com a Yahoo e para uso pessoal."""
from __future__ import annotations

import math
import time
from typing import Callable

import pandas as pd

from app.ativos_b3 import CODIGO_IBOVESPA
from app.calendario import INICIO_HISTORICO
from app.erros import ErroProvedor
from app.provedores.base import CandleRecebido, Provedor


def _baixar_yfinance(simbolo: str, desde: str | None) -> pd.DataFrame:
    import yfinance as yf  # importação tardia: é lenta e os testes não precisam dela

    papel = yf.Ticker(simbolo)
    inicio = max(desde or INICIO_HISTORICO, INICIO_HISTORICO)
    return papel.history(start=inicio, interval="1d", auto_adjust=False, actions=False)


def simbolo_yahoo(codigo: str) -> str:
    return codigo if codigo == CODIGO_IBOVESPA else f"{codigo}.SA"


class ProvedorYahoo(Provedor):
    id = "yahoo"
    nome = "Yahoo Finance"
    plano = "yfinance, sem custo"
    acumula = False

    def __init__(
        self,
        baixar: Callable[[str, str | None], pd.DataFrame] = _baixar_yfinance,
        esperar: Callable[[float], None] = time.sleep,
    ) -> None:
        self._baixar = baixar
        self._esperar = esperar

    def buscar(self, codigo: str, desde: str | None = None) -> list[CandleRecebido]:
        simbolo = simbolo_yahoo(codigo)
        tabela = None
        falhou = False
        # O yfinance devolve tabela vazia tanto para código inexistente quanto para falha de rede.
        for espera in (0.0, 1.0, 2.0):
            if espera:
                self._esperar(espera)
            try:
                tabela = self._baixar(simbolo, desde)
                falhou = False
            except Exception:  # noqa: BLE001 - o yfinance não tem hierarquia de erros estável
                falhou = True
                continue
            if tabela is not None and not tabela.empty:
                break
        if falhou:
            raise ErroProvedor("fonte_indisponivel", "Não foi possível obter dados do Yahoo Finance.")
        if tabela is None or tabela.empty:
            if desde:
                return []
            raise ErroProvedor(
                "ativo_nao_encontrado",
                f"O Yahoo não retornou dados para {codigo}: o código não existe ou a fonte está indisponível.",
            )
        return _converter(tabela)


def _numero(valor) -> float | None:
    if valor is None:
        return None
    numero = float(valor)
    return None if math.isnan(numero) else numero


def _converter(tabela: pd.DataFrame) -> list[CandleRecebido]:
    candles = []
    for indice, linha in tabela.iterrows():
        candles.append(
            CandleRecebido(
                indice.date().isoformat(),
                _numero(linha.get("Open")),
                _numero(linha.get("High")),
                _numero(linha.get("Low")),
                _numero(linha.get("Close")),
                _numero(linha.get("Adj Close")),
                _numero(linha.get("Volume")),
            )
        )
    return candles
