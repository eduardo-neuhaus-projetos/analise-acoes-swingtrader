"""Padrões de candle de compra testados por Thomas Bulkowski, conforme o vídeo
https://www.youtube.com/watch?v=P3xgP_alm48. O vídeo descreve os padrões no gráfico; os limites numéricos
("candle forte", "fecha perto da máxima") são a leitura adotada aqui e ficam como parâmetros.

Bebê engolido e Três quedas, também do vídeo, são padrões de venda e ficam fora: o app só simula compra.
"""
from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field

from app.motor.indicadores import mma
from app.motor.tipos import ContextoCandle, Ordem, SerieCandles
from app.setups.candle import _SetupCandle, ParametrosSaidaAlvo
from app.setups.comum import compra_stop, subindo

ORIGEM = "Thomas Bulkowski, apresentado no vídeo “6 padrões de candle” (YouTube P3xgP_alm48)"
ROTULOS_STOP = {"candle_sinal": "Mínima do último candle do padrão", "minima_padrao": "Menor mínima do padrão"}


class ParametrosPadrao(ParametrosSaidaAlvo):
    n_media_corpo: int = Field(20, ge=2, le=200, title="Candles da média de corpo")
    fator_forte: float = Field(
        1.3,
        gt=0,
        le=10,
        title="Candle forte: corpo mínimo (vezes a média)",
        description="Média dos corpos dos candles anteriores ao padrão.",
    )
    extremo_pct: float = Field(
        25.0,
        gt=0,
        le=100,
        title="Fechamento no extremo: distância máxima (% do candle)",
        description="Quanto o fechamento pode ficar longe da máxima (alta) ou da mínima (baixa).",
    )
    stop_padrao: Literal["candle_sinal", "minima_padrao"] = Field(
        "candle_sinal", title="Stop inicial", json_schema_extra={"rotulos": ROTULOS_STOP}
    )


class ParametrosContinuidade(ParametrosPadrao):
    exigir_tendencia: bool = Field(
        True, title="Exigir MMA 21 subindo", description="Os padrões de continuidade pedem tendência de alta."
    )


class ParametrosSeparacao(ParametrosContinuidade):
    tolerancia_abertura_pct: float = Field(
        10.0,
        ge=0,
        le=100,
        title="Abertura igual à anterior: tolerância (% do candle anterior)",
    )


class ParametrosDeliberante(ParametrosContinuidade):
    fator_pequeno: float = Field(
        0.5, gt=0, le=10, title="Terceiro candle pequeno: corpo máximo (vezes a média)"
    )
    tolerancia_abertura_pct: float = Field(
        10.0,
        ge=0,
        le=100,
        title="Abertura junto do fechamento anterior: tolerância (% do candle anterior)",
    )


class ParametrosPenetrante(ParametrosPadrao):
    exigir_queda: bool = Field(
        True,
        title="Exigir queda anterior",
        description="O primeiro candle fecha abaixo da MMA 21: o padrão é de reversão depois de queda.",
    )


class _SetupPadrao(_SetupCandle):
    """Base: mede corpos e extremos. O índice -1 é o último candle do padrão."""

    familia = "Padrões de candle"
    origem = ORIGEM
    tamanho: int = 2  # candles do padrão

    def periodos(self, params: ParametrosPadrao) -> list[int]:
        return [params.n_media_corpo, 21]

    def calcular(self, candles: SerieCandles, params: ParametrosPadrao) -> dict[str, np.ndarray]:
        corpo = np.abs(candles.fechamento - candles.abertura)
        return {"_corpo_medio": mma(corpo, params.n_media_corpo), "_mma21": mma(candles.fechamento, 21)}

    # --- medidas do candle k (negativo, contado do fim)
    @staticmethod
    def _corpo(ctx: ContextoCandle, k: int) -> float:
        return float(abs(ctx.fechamento[k] - ctx.abertura[k]))

    @staticmethod
    def _alta(ctx: ContextoCandle, k: int) -> bool:
        return bool(ctx.fechamento[k] > ctx.abertura[k])

    @staticmethod
    def _baixa(ctx: ContextoCandle, k: int) -> bool:
        return bool(ctx.fechamento[k] < ctx.abertura[k])

    def _media(self, ctx: ContextoCandle) -> float:
        """Média dos corpos até o candle anterior ao padrão, para o próprio padrão não inflar a régua."""
        return float(ctx.indicadores["_corpo_medio"][-self.tamanho - 1])

    def _forte(self, ctx: ContextoCandle, k: int) -> bool:
        media = self._media(ctx)
        return media > 0 and self._corpo(ctx, k) >= ctx.params.fator_forte * media

    @staticmethod
    def _fecha_na_maxima(ctx: ContextoCandle, k: int) -> bool:
        faixa = ctx.maxima[k] - ctx.minima[k]
        return bool(faixa > 0 and ctx.maxima[k] - ctx.fechamento[k] <= ctx.params.extremo_pct / 100 * faixa)

    @staticmethod
    def _fecha_na_minima(ctx: ContextoCandle, k: int) -> bool:
        faixa = ctx.maxima[k] - ctx.minima[k]
        return bool(faixa > 0 and ctx.fechamento[k] - ctx.minima[k] <= ctx.params.extremo_pct / 100 * faixa)

    def _tendencia_ok(self, ctx: ContextoCandle) -> bool:
        return not getattr(ctx.params, "exigir_tendencia", False) or subindo(ctx.indicadores["_mma21"])

    def _padrao(self, ctx: ContextoCandle) -> bool:
        raise NotImplementedError

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        if not (self._tendencia_ok(ctx) and self._padrao(ctx)):
            return None
        p: ParametrosPadrao = ctx.params
        base = float(np.min(ctx.minima[-self.tamanho:])) if p.stop_padrao == "minima_padrao" else float(ctx.minima[-1])
        return compra_stop(
            ctx, ctx.maxima[-1], base - p.tick, f"{self.nome}: compra no rompimento da máxima.", alvo_r=self.alvo_r(ctx)
        )


class SetupSeparacaoAlta(_SetupPadrao):
    id = "separacao_alta"
    versao = "1.0"
    nome = "Linha de separação de alta"
    descricao = (
        "Na alta, um candle forte de baixa seguido de um candle forte de alta que abre no mesmo preço e fecha perto "
        "da máxima. Compra o rompimento da máxima. Bulkowski: 72% de continuidade."
    )
    Parametros = ParametrosSeparacao
    tamanho = 2

    def _padrao(self, ctx: ContextoCandle) -> bool:
        p: ParametrosSeparacao = ctx.params
        o = ctx.abertura
        faixa_anterior = ctx.maxima[-2] - ctx.minima[-2]
        return (
            self._baixa(ctx, -2)
            and self._forte(ctx, -2)
            and self._alta(ctx, -1)
            and self._forte(ctx, -1)
            and self._fecha_na_maxima(ctx, -1)
            and abs(o[-1] - o[-2]) <= p.tolerancia_abertura_pct / 100 * faixa_anterior
        )


class SetupMatHold(_SetupPadrao):
    id = "mat_hold"
    versao = "1.0"
    nome = "Mat Hold"
    descricao = (
        "Cinco candles: um forte de alta, um de baixa fechando acima dele, mais dois em correção, todos acima da "
        "mínima do primeiro, e um quinto forte fechando acima das 4 máximas. Bulkowski: 78% de continuidade."
    )
    Parametros = ParametrosContinuidade
    tamanho = 5

    def _padrao(self, ctx: ContextoCandle) -> bool:
        c, h, l = ctx.fechamento, ctx.maxima, ctx.minima
        return (
            self._alta(ctx, -5)
            and self._forte(ctx, -5)
            and self._fecha_na_maxima(ctx, -5)
            and self._baixa(ctx, -4)
            and c[-4] > c[-5]
            and self._baixa(ctx, -3)
            and c[-3] < c[-4]
            and c[-2] < c[-3]
            and bool(np.min(l[-4:-1]) > l[-5])
            and self._alta(ctx, -1)
            and self._forte(ctx, -1)
            and c[-1] > float(np.max(h[-5:-1]))
        )


class SetupPenetrante(_SetupPadrao):
    id = "penetrante"
    versao = "1.0"
    nome = "Padrão penetrante"
    descricao = (
        "Depois de queda, um candle forte de baixa e um de alta que abre abaixo da mínima dele e fecha acima do meio "
        "do corpo, sem passar da abertura. Compra o rompimento da máxima, com stop na mínima."
    )
    Parametros = ParametrosPenetrante
    tamanho = 2

    def _padrao(self, ctx: ContextoCandle) -> bool:
        p: ParametrosPenetrante = ctx.params
        o, c, l = ctx.abertura, ctx.fechamento, ctx.minima
        meio = (o[-2] + c[-2]) / 2
        if p.exigir_queda and not c[-2] < ctx.indicadores["_mma21"][-2]:
            return False
        return (
            self._baixa(ctx, -2)
            and self._forte(ctx, -2)
            and self._fecha_na_minima(ctx, -2)
            and o[-1] < l[-2]
            and meio < c[-1] < o[-2]
        )


class SetupDeliberante(_SetupPadrao):
    id = "deliberante"
    versao = "1.0"
    nome = "Padrão deliberante"
    descricao = (
        "Na alta, dois candles fortes de alta e um terceiro pequeno, que abre junto do fechamento do segundo. "
        "Compra o rompimento da máxima. O vídeo cita 77% de continuidade."
    )
    Parametros = ParametrosDeliberante
    tamanho = 3

    def _padrao(self, ctx: ContextoCandle) -> bool:
        p: ParametrosDeliberante = ctx.params
        o, c = ctx.abertura, ctx.fechamento
        faixa_segundo = ctx.maxima[-2] - ctx.minima[-2]
        return (
            self._alta(ctx, -3)
            and self._forte(ctx, -3)
            and self._alta(ctx, -2)
            and self._forte(ctx, -2)
            and c[-2] > c[-3]
            and abs(o[-1] - c[-2]) <= p.tolerancia_abertura_pct / 100 * faixa_segundo
            and self._corpo(ctx, -1) <= p.fator_pequeno * self._media(ctx)
        )
