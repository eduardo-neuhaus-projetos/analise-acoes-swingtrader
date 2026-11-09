"""Contrato de setup: um setup novo declara parâmetros, indicadores e regras; motor e telas se montam disso."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from pydantic import BaseModel

if TYPE_CHECKING:
    from app.motor.tipos import ContextoCandle, Ordem, SerieCandles


class Setup(ABC):
    id: ClassVar[str]
    versao: ClassVar[str]  # muda quando a regra muda; resultados antigos seguem ligados à versão que os gerou
    nome: ClassVar[str]
    descricao: ClassVar[str] = ""
    familia: ClassVar[str] = "Outros"  # grupo no seletor de setups
    origem: ClassVar[str] = ""  # autor ou divulgador
    direcao: ClassVar[list[str]] = ["long"]
    Parametros: ClassVar[type[BaseModel]]

    @abstractmethod
    def aquecimento(self, params) -> int:
        """Quantos candles seguidos são necessários antes do primeiro sinal."""

    @abstractmethod
    def indicadores(self, candles: "SerieCandles", params) -> dict[str, np.ndarray]:
        """Séries de indicadores, do mesmo tamanho dos candles. Nome com "_" não aparece no gráfico."""

    @abstractmethod
    def indicadores_declarados(self, params) -> dict[str, str]:
        """Rótulo de cada indicador, usado na legenda do gráfico."""

    def indicadores_em_painel(self, params) -> set[str]:
        """Indicadores em outra escala (IFR, ADX): ficam em um painel abaixo dos candles."""
        return set()

    def paineis(self, params) -> list[set[str]]:
        """Um conjunto por painel inferior. Só quem tem escalas diferentes entre si precisa de mais de um."""
        grupo = self.indicadores_em_painel(params)
        return [grupo] if grupo else []

    @abstractmethod
    def ao_fechar_candle(self, ctx: "ContextoCandle") -> list["Ordem"]:
        """Ordens que devem estar ativas no próximo pregão."""
