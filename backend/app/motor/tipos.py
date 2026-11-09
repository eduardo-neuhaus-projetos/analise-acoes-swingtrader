"""Tipos do motor. O setup decide quais ordens quer ativas; o motor decide se e a que preço executam."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

TipoOrdem = Literal[
    "entrada_stop",  # compra quando a máxima alcança o preço, a partir do pregão seguinte
    "entrada_abertura",  # compra na abertura do pregão seguinte
    "entrada_fechamento",  # compra no fechamento do próprio candle do sinal
    "saida_stop",  # vende quando a mínima alcança o preço, a partir do pregão seguinte
    "saida_alvo",  # vende quando a máxima alcança o preço, a partir do pregão seguinte
    "saida_fechamento",  # vende no fechamento do próprio candle
]


@dataclass(frozen=True)
class Ordem:
    tipo: TipoOrdem
    preco: float
    codigo: str  # identificador da regra, ex.: "gatilho_novo"
    motivo: str  # texto mostrado no detalhe do trade
    stop: float | None = None  # entrada: stop inicial que acompanha a posição
    alvo_r: float | None = None  # entrada: alvo em múltiplos do risco
    alvo: float | None = None  # entrada: alvo em preço, ignorado se ficar abaixo da entrada
    novo_sinal: bool = False  # entrada: abre um novo sinal (e não só atualiza o gatilho)
    sem_stop: bool = False  # entrada: a regra do setup não usa stop técnico, e o risco fica indefinido
    aceitar_gap: bool = True  # entrada stop: desligado, a abertura acima do gatilho cancela o sinal
    motivo_saida: str | None = None  # saída: motivo mostrado no trade (ver TEXTO_MOTIVO_SAIDA)


@dataclass
class Posicao:
    sinal_data: str
    entrada_indice: int
    entrada_data: str
    entrada_preco: float
    stop: float | None
    risco: float | None
    alvo: float | None
    motivo_alvo: str = "alvo"


@dataclass
class EventoTrade:
    data: str
    tipo: str
    preco: float | None
    regra: str


@dataclass
class Sinal:
    data: str
    gatilho: float
    stop: float | None
    situacao: str = "armado"  # armado | acionado | cancelado | invalidado | substituido
    motivo: str = ""
    gatilho_final: float | None = None
    data_fim: str | None = None
    eventos: list[EventoTrade] = field(default_factory=list)


@dataclass
class Trade:
    numero: int
    sinal_data: str
    entrada_data: str
    entrada_preco: float
    stop: float | None
    risco: float | None
    alvo: float | None
    saida_data: str | None = None
    saida_preco: float | None = None
    motivo_saida: str | None = None
    duracao_pregoes: int = 0
    aberto: bool = True
    preco_referencia: float | None = None  # último fechamento, para trade aberto
    avisos: list[str] = field(default_factory=list)
    eventos: list[EventoTrade] = field(default_factory=list)


@dataclass
class SerieCandles:
    """Candles ajustados, em ordem de data. `quebra[i]` marca o primeiro candle depois de uma lacuna."""

    datas: list[str]
    abertura: np.ndarray
    maxima: np.ndarray
    minima: np.ndarray
    fechamento: np.ndarray
    volume: np.ndarray
    quebra: np.ndarray

    def __len__(self) -> int:
        return len(self.datas)

    def fatia(self, inicio: int, fim: int) -> "SerieCandles":
        return SerieCandles(
            self.datas[inicio:fim],
            self.abertura[inicio:fim],
            self.maxima[inicio:fim],
            self.minima[inicio:fim],
            self.fechamento[inicio:fim],
            self.volume[inicio:fim],
            self.quebra[inicio:fim],
        )


@dataclass
class ContextoCandle:
    """Só enxerga candles e indicadores até o pregão atual, para o setup não olhar o futuro."""

    params: Any
    datas: list[str]
    abertura: np.ndarray
    maxima: np.ndarray
    minima: np.ndarray
    fechamento: np.ndarray
    volume: np.ndarray
    indicadores: dict[str, np.ndarray]
    posicao: Posicao | None
    ordens_ativas: list[Ordem]
    notas: list[tuple[str, str]] = field(default_factory=list)
    memoria: dict = field(default_factory=dict)  # estado do setup nesta execução; recomeça depois de uma lacuna

    @property
    def indice(self) -> int:
        return len(self.fechamento) - 1

    def anotar(self, codigo: str, motivo: str) -> None:
        """Registra por que uma ordem deixou de existir (ex.: sinal cancelado)."""
        self.notas.append((codigo, motivo))

    def ordem(self, tipo: TipoOrdem) -> Ordem | None:
        return next((o for o in self.ordens_ativas if o.tipo == tipo), None)


@dataclass
class ResultadoMotor:
    trades: list[Trade]
    sinais: list[Sinal]
    estado: str  # sem_sinal | armado | posicionado | saida_armada
    ordens_ativas: list[Ordem]
    posicao: Posicao | None
    indicadores: dict[str, np.ndarray]
    avisos: list[str]
    candles_usados: int
