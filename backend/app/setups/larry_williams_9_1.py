"""Larry Williams 9.1, somente compra, conforme a seção 1.1 de SETUPS_SWING_TRADE.md."""
from __future__ import annotations

import numpy as np
from pydantic import Field

from app.motor.indicadores import mme
from app.motor.tipos import ContextoCandle, Ordem, SerieCandles
from app.setups.comum import (
    ParametrosComuns,
    SetupCompra,
    caindo,
    compra_stop,
    manter_ordem,
    mover_gatilho,
    subindo,
    virou_para_cima,
)


class ParametrosFamiliaLarry(ParametrosComuns):
    periodo_mme: int = Field(9, ge=2, le=200, title="Período da MME")
    alvo_r: float | None = Field(None, gt=0, title="Alvo fixo em R", description="Vazio deixa o alvo desligado.")
    trailing_na_minima: bool = Field(
        False,
        title="Subir o stop com a média subindo",
        description="Mantém uma venda stop na mínima do candle enquanto a MME sobe.",
    )
    arrastar_saida: bool = Field(
        True,
        title="Arrastar a saída com a média caindo",
        description="Desligado, a saída fica na mínima do candle em que a média virou.",
    )


def saida_pela_media(ctx: ContextoCandle) -> list[Ordem]:
    """Saída padrão da família 9.x: a venda stop nasce quando a MME cai e é cancelada quando ela volta a subir."""
    p = ctx.params
    media = ctx.indicadores["mme"]
    saida = ctx.ordem("saida_stop")
    minima = float(ctx.minima[-1])
    if caindo(media):
        if saida is not None and saida.codigo == "saida_armada" and not p.arrastar_saida:
            return [saida]
        preco = minima - p.tick
        if saida is not None and saida.codigo == "stop_movel":
            preco = max(preco, saida.preco)
        return [
            Ordem(
                "saida_stop",
                preco,
                "saida_armada",
                "A MME está caindo: ordem na mínima do candle menos 1 tick.",
            )
        ]
    if subindo(media):
        if p.trailing_na_minima:
            preco = minima - p.tick
            if saida is not None and saida.codigo == "stop_movel":
                preco = max(preco, saida.preco)
            return [
                Ordem(
                    "saida_stop",
                    preco,
                    "stop_movel",
                    "A MME está subindo: stop na mínima do candle menos 1 tick.",
                    motivo_saida="trailing_minima",
                )
            ]
        if saida is not None:
            ctx.anotar("saida_cancelada", "A MME voltou a subir antes de a saída executar.")
        return []
    return [saida] if saida is not None else []


class ParametrosLW91(ParametrosFamiliaLarry):
    exigir_fechamento_acima: bool = Field(False, title="Exigir fechamento acima da MME no sinal")
    atualizar_gatilho: bool = Field(
        True,
        title="Atualizar gatilho não acionado",
        description="Desligado, o gatilho vale só no pregão seguinte ao sinal.",
    )
    stop_no_candle_vigente: bool = Field(
        True,
        title="Stop acompanha o gatilho atualizado",
        description="Ligado, o stop vai para a mínima do candle que passou a valer. Desligado, fica no candle do sinal.",
    )


class LarryWilliams91(SetupCompra):
    id = "larry_williams_9_1"
    versao = "1.2"
    nome = "Larry Williams 9.1"
    familia = "Larry Williams"
    origem = "Larry Williams; popularizado no Brasil por Alexandre Wolwacz (Stormer)"
    descricao = (
        "Compra o rompimento da máxima do candle em que a MME vira para cima e sai quando "
        "ela vira para baixo e a mínima desse candle é perdida."
    )
    Parametros = ParametrosLW91

    def periodos(self, params: ParametrosLW91) -> list[int]:
        return [params.periodo_mme]

    def calcular(self, candles: SerieCandles, params: ParametrosLW91) -> dict[str, np.ndarray]:
        return {"mme": mme(candles.fechamento, params.periodo_mme)}

    def rotulos(self, params: ParametrosLW91) -> dict[str, str]:
        return {"mme": f"MME {params.periodo_mme}"}

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        p: ParametrosLW91 = ctx.params
        media = ctx.indicadores["mme"]
        if not virou_para_cima(media):
            return None
        if p.exigir_fechamento_acima and not float(ctx.fechamento[-1]) > float(media[-1]):
            return None
        return compra_stop(
            ctx,
            ctx.maxima[-1],
            float(ctx.minima[-1]) - p.tick,
            "A MME virou para cima: gatilho na máxima do candle mais 1 tick, stop na mínima menos 1 tick.",
            alvo_r=p.alvo_r,
        )

    def manter(self, ctx: ContextoCandle, pendente: Ordem) -> list[Ordem]:
        p: ParametrosLW91 = ctx.params
        media = ctx.indicadores["mme"]
        if caindo(media):
            ctx.anotar("sinal_cancelado", "A MME virou para baixo antes da entrada.")
            return []
        if not p.atualizar_gatilho:
            ctx.anotar("sinal_expirado", "O gatilho valia só no pregão seguinte ao sinal.")
            return []
        # O arrasto só vale com máxima menor: máxima igual mantém o gatilho e o stop do candle vigente.
        if subindo(media) and float(ctx.maxima[-1]) + p.tick < pendente.preco:
            stop = float(ctx.minima[-1]) - p.tick if p.stop_no_candle_vigente else None
            return [
                mover_gatilho(
                    ctx,
                    pendente,
                    ctx.maxima[-1],
                    "A MME segue subindo: gatilho na máxima do candle mais recente mais 1 tick.",
                    stop=stop,
                )
            ]
        return [manter_ordem(pendente)]

    def gerenciar(self, ctx: ContextoCandle) -> list[Ordem]:
        return saida_pela_media(ctx)
