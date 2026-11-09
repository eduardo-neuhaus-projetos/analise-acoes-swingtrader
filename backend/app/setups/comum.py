"""Base dos setups de compra: filtros globais, aquecimento, ordens e saídas que se repetem entre eles."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import replace
from typing import ClassVar

import numpy as np
from pydantic import BaseModel, Field

from app.motor.indicadores import mma, mme_semanal_subindo
from app.motor.tipos import ContextoCandle, Ordem, SerieCandles
from app.setups.base import Setup

COMUM = {"grupo": "comum"}  # o formulário mostra estes campos depois das regras do setup


class ParametrosComuns(BaseModel):
    tick: float = Field(0.01, gt=0, title="Tick (R$)", json_schema_extra=COMUM)
    aceitar_gap: bool = Field(
        True,
        title="Aceitar entrada em gap",
        description="Desligado, abrir acima do gatilho cancela o sinal.",
        json_schema_extra=COMUM,
    )
    filtro_tendencia_mm200: bool = Field(False, title="Só comprar acima da MMA 200", json_schema_extra=COMUM)
    filtro_semanal: bool = Field(False, title="Só comprar com a MME 9 semanal subindo", json_schema_extra=COMUM)
    volume_minimo: float | None = Field(
        None,
        gt=0,
        title="Volume médio mínimo em 20 pregões",
        description="Vazio deixa o filtro desligado.",
        json_schema_extra=COMUM,
    )


class SetupCompra(Setup):
    """Separa o que muda em cada setup: o sinal, a ordem pendente e a gestão da posição."""

    direcao: ClassVar[list[str]] = ["long"]
    candles_minimos: ClassVar[int] = 3  # candles que a regra compara, para setups sem indicador

    def periodos(self, params) -> list[int]:
        """Períodos dos indicadores do setup, usados no aquecimento de 3 vezes o maior período."""
        return []

    @abstractmethod
    def calcular(self, candles: SerieCandles, params) -> dict[str, np.ndarray]:
        """Indicadores da regra. Os dos filtros globais a base acrescenta."""

    def rotulos(self, params) -> dict[str, str]:
        return {}

    def observar(self, ctx: ContextoCandle) -> None:
        """Roda em todo candle fechado, com ou sem posição. Serve a quem guarda estado em `ctx.memoria`."""

    @abstractmethod
    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        """Ordem de entrada de um sinal novo neste candle."""

    def manter(self, ctx: ContextoCandle, pendente: Ordem) -> list[Ordem]:
        """O que fazer com a entrada não acionada. Por padrão ela vale um pregão só."""
        ctx.anotar("sinal_expirado", "A ordem valia só no pregão seguinte ao sinal.")
        return []

    def gerenciar(self, ctx: ContextoCandle) -> list[Ordem]:
        """Ordens de saída enquanto há posição. Sem ordem, valem o stop e o alvo definidos na entrada."""
        return []

    def aquecimento(self, params) -> int:
        candles = max([3 * p for p in self.periodos(params)] + [self.candles_minimos])
        if params.filtro_tendencia_mm200:
            candles = max(candles, 3 * 200)
        if params.volume_minimo:
            candles = max(candles, 3 * 20)
        if params.filtro_semanal:
            candles = max(candles, 3 * 9 * 5)
        return candles

    def indicadores(self, candles: SerieCandles, params) -> dict[str, np.ndarray]:
        saida = dict(self.calcular(candles, params))
        if params.filtro_tendencia_mm200:
            saida["mm200"] = mma(candles.fechamento, 200)
        if params.volume_minimo:
            saida["_volume_medio"] = mma(candles.volume, 20)
        if params.filtro_semanal:
            saida["_semanal"] = mme_semanal_subindo(candles.datas, candles.fechamento)
        return saida

    def indicadores_declarados(self, params) -> dict[str, str]:
        rotulos = dict(self.rotulos(params))
        if params.filtro_tendencia_mm200:
            rotulos["mm200"] = "MMA 200"
        return rotulos

    def filtros_ok(self, ctx: ContextoCandle) -> bool:
        p = ctx.params
        ind = ctx.indicadores
        if p.filtro_tendencia_mm200 and not ctx.fechamento[-1] > ind["mm200"][-1]:
            return False
        if p.volume_minimo and not ind["_volume_medio"][-1] >= p.volume_minimo:
            return False
        if p.filtro_semanal and not ind["_semanal"][-1] == 1.0:
            return False
        return True

    def ao_fechar_candle(self, ctx: ContextoCandle) -> list[Ordem]:
        self.observar(ctx)
        if ctx.posicao is not None:
            return self.gerenciar(ctx)
        nova = self.sinal(ctx) if self.filtros_ok(ctx) else None
        if nova is not None:
            return [nova]
        pendente = ctx.ordem("entrada_stop")
        return self.manter(ctx, pendente) if pendente is not None else []


def compra_stop(
    ctx: ContextoCandle,
    referencia: float,
    stop: float,
    motivo: str,
    alvo_r: float | None = None,
    alvo: float | None = None,
) -> Ordem:
    """Sinal novo: compra stop um tick acima da referência."""
    return Ordem(
        "entrada_stop",
        float(referencia) + ctx.params.tick,
        "gatilho_novo",
        motivo,
        stop=float(stop),
        alvo_r=alvo_r,
        alvo=None if alvo is None else float(alvo),
        novo_sinal=True,
        aceitar_gap=ctx.params.aceitar_gap,
    )


def mover_gatilho(ctx: ContextoCandle, pendente: Ordem, referencia: float, motivo: str, stop: float | None = None) -> Ordem:
    """A entrada não acionada passa a valer em outro preço, sem abrir um sinal novo."""
    return replace(
        pendente,
        preco=float(referencia) + ctx.params.tick,
        stop=pendente.stop if stop is None else float(stop),
        codigo="gatilho_atualizado",
        motivo=motivo,
        novo_sinal=False,
    )


def manter_ordem(pendente: Ordem) -> Ordem:
    return replace(pendente, novo_sinal=False)


def stop_movel_na_minima(ctx: ContextoCandle) -> list[Ordem]:
    """Venda stop na mínima do último candle menos 1 tick. O stop móvel só sobe."""
    preco = float(ctx.minima[-1]) - ctx.params.tick
    atual = ctx.ordem("saida_stop")
    if atual is not None:
        preco = max(preco, atual.preco)
    return [
        Ordem(
            "saida_stop",
            preco,
            "stop_movel",
            "Stop móvel: mínima do candle anterior menos 1 tick.",
            motivo_saida="trailing_minima",
        )
    ]


def minima_do_pullback(ctx: ContextoCandle, janela: int = 20) -> float:
    """Menor mínima desde a maior máxima dos últimos `janela` candles."""
    maximas = ctx.maxima[-janela:]
    topo = len(maximas) - 1 - int(np.argmax(maximas[::-1]))
    return float(np.min(ctx.minima[-janela:][topo:]))


def subindo(valores: np.ndarray) -> bool:
    return bool(valores[-1] > valores[-2])


def caindo(valores: np.ndarray) -> bool:
    return bool(valores[-1] < valores[-2])


def virou_para_cima(valores: np.ndarray) -> bool:
    return bool(valores[-1] > valores[-2] and valores[-2] <= valores[-3])


def virou_para_baixo(valores: np.ndarray) -> bool:
    return bool(valores[-1] < valores[-2] and valores[-2] >= valores[-3])
