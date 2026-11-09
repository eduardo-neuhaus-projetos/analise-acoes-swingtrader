"""Camada de provedores. Cada provedor alimenta só a sua aba, e trocar a fonte no futuro mexe só aqui."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class CandleRecebido:
    data: str
    abertura: float | None
    maxima: float | None
    minima: float | None
    fechamento: float | None
    ajustado: float | None
    volume: float | None


class Provedor(ABC):
    id: ClassVar[str]
    nome: ClassVar[str]
    plano: ClassVar[str]
    acumula: ClassVar[bool]  # True: guarda o que sai da janela, pois não pode baixar de novo

    @abstractmethod
    def buscar(self, codigo: str, desde: str | None = None) -> list[CandleRecebido]:
        """Candles diários em ordem de data. `desde` pede só o trecho final, quando a fonte permite."""
