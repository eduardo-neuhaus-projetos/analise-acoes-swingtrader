"""Setups 9.2, 9.3 e 9.4 de Larry Williams, seções 1.2 a 1.4 de SETUPS_SWING_TRADE.md."""
from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field

from app.motor.indicadores import mme
from app.motor.tipos import ContextoCandle, Ordem, SerieCandles
from app.setups.comum import (
    SetupCompra,
    caindo,
    compra_stop,
    manter_ordem,
    minima_do_pullback,
    mover_gatilho,
    subindo,
    virou_para_baixo,
    virou_para_cima,
)
from app.setups.larry_williams_9_1 import ParametrosFamiliaLarry, saida_pela_media

ROTULOS_STOP = {"candle_sinal": "Mínima do candle de sinal", "minima_pullback": "Mínima do pullback"}


class _SetupFamilia(SetupCompra):
    familia = "Larry Williams"
    origem = "Larry Williams; popularizado no Brasil por Alexandre Wolwacz (Stormer)"

    def periodos(self, params) -> list[int]:
        return [params.periodo_mme]

    def calcular(self, candles: SerieCandles, params) -> dict[str, np.ndarray]:
        return {"mme": mme(candles.fechamento, params.periodo_mme)}

    def rotulos(self, params) -> dict[str, str]:
        return {"mme": f"MME {params.periodo_mme}"}

    def gerenciar(self, ctx: ContextoCandle) -> list[Ordem]:
        return saida_pela_media(ctx)


def _stop_do_pullback(ctx: ContextoCandle) -> float:
    p = ctx.params
    base = minima_do_pullback(ctx) if p.stop_tipo == "minima_pullback" else float(ctx.minima[-1])
    return base - p.tick


class ParametrosLW92(ParametrosFamiliaLarry):
    stop_tipo: Literal["candle_sinal", "minima_pullback"] = Field(
        "candle_sinal", title="Stop inicial", json_schema_extra={"rotulos": ROTULOS_STOP}
    )


class LarryWilliams92(_SetupFamilia):
    id = "lw_9_2"
    versao = "1.0"
    nome = "Larry Williams 9.2"
    descricao = (
        "Com a MME subindo, um fechamento abaixo da mínima anterior marca o pullback. Compra o rompimento da "
        "máxima desse candle e sai pela regra da média."
    )
    Parametros = ParametrosLW92

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        # O arrasto é o próprio sinal repetido: outro fechamento abaixo da mínima anterior substitui a ordem.
        if not (subindo(ctx.indicadores["mme"]) and ctx.fechamento[-1] < ctx.minima[-2]):
            return None
        return compra_stop(
            ctx,
            ctx.maxima[-1],
            _stop_do_pullback(ctx),
            "A MME sobe e o fechamento ficou abaixo da mínima anterior: gatilho na máxima do candle mais 1 tick.",
            alvo_r=ctx.params.alvo_r,
        )


class ParametrosLW93(ParametrosFamiliaLarry):
    stop_tipo: Literal["candle_sinal", "minima_pullback"] = Field(
        "candle_sinal", title="Stop inicial", json_schema_extra={"rotulos": ROTULOS_STOP}
    )


class LarryWilliams93(_SetupFamilia):
    id = "lw_9_3"
    versao = "1.0"
    nome = "Larry Williams 9.3"
    descricao = (
        "Com a MME subindo, dois fechamentos seguidos abaixo do fechamento de referência marcam o pullback. Compra "
        "o rompimento da máxima do último candle e sai pela regra da média."
    )
    Parametros = ParametrosLW93

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        c = ctx.fechamento
        if not (subindo(ctx.indicadores["mme"]) and c[-2] < c[-3] and c[-1] < c[-3]):
            return None
        ctx.memoria["referencia"] = float(c[-3])
        return compra_stop(
            ctx,
            ctx.maxima[-1],
            _stop_do_pullback(ctx),
            "A MME sobe e dois fechamentos ficaram abaixo do fechamento de referência: gatilho na máxima mais 1 tick.",
            alvo_r=ctx.params.alvo_r,
        )

    def manter(self, ctx: ContextoCandle, pendente: Ordem) -> list[Ordem]:
        referencia = ctx.memoria.get("referencia")
        if not subindo(ctx.indicadores["mme"]):
            ctx.anotar("sinal_cancelado", "A MME deixou de subir antes da entrada.")
            return []
        if referencia is not None and ctx.fechamento[-1] < referencia:
            return [
                mover_gatilho(
                    ctx,
                    pendente,
                    ctx.maxima[-1],
                    "Novo fechamento abaixo da referência: gatilho na máxima do candle mais recente mais 1 tick.",
                    stop=_stop_do_pullback(ctx),
                )
            ]
        ctx.anotar("sinal_expirado", "O fechamento voltou acima da referência sem acionar a entrada.")
        return []


class ParametrosLW94(ParametrosFamiliaLarry):
    janela_94: int = Field(
        3,
        ge=1,
        le=20,
        title="Janela depois do 9.1 (candles)",
        description="Quanto tempo depois de encerrado o 9.1 ainda pode valer, e quanto dura a ordem.",
    )
    stop_tipo: Literal["stop_do_9_1", "candle_sinal"] = Field(
        "stop_do_9_1",
        title="Stop inicial",
        json_schema_extra={"rotulos": {"stop_do_9_1": "Stop original do 9.1", "candle_sinal": "Mínima do candle de sinal"}},
    )


class LarryWilliams94(_SetupFamilia):
    id = "lw_9_4"
    versao = "1.0"
    nome = "Larry Williams 9.4"
    descricao = (
        "Depois de um 9.1 acionado, a MME vira para baixo sem perder o stop original. Compra o rompimento da máxima "
        "desse candle: o trade é só o da retomada, e o 9.1 é acompanhado à parte, sem entrar nos resultados."
    )
    Parametros = ParametrosLW94

    def observar(self, ctx: ContextoCandle) -> None:
        """Simula o 9.1 à parte: o 9.4 depende dele, mas o 9.1 não é um trade deste setup."""
        m = ctx.memoria
        p = ctx.params
        media = ctx.indicadores["mme"]
        maxima, minima = float(ctx.maxima[-1]), float(ctx.minima[-1])

        if m.get("gatilho") is not None and maxima >= m["gatilho"]:
            m.update(comprado=True, gatilho=None, saida=None, stop_91=m["stop_pendente"], fim_91=None)
        if m.get("comprado"):
            if minima <= m["stop_91"]:
                m.update(comprado=False, saida=None, stop_91=None, fim_91=None)
            elif m.get("saida") is not None and minima <= m["saida"]:
                m.update(comprado=False, saida=None, fim_91=ctx.indice)

        if m.get("comprado"):
            m["saida"] = minima - p.tick if caindo(media) else None if subindo(media) else m.get("saida")
        elif virou_para_cima(media):
            m.update(gatilho=maxima + p.tick, stop_pendente=minima - p.tick)
        elif caindo(media):
            m["gatilho"] = None
        elif subindo(media) and m.get("gatilho") is not None:
            m["gatilho"] = maxima + p.tick

    def _contexto_valido(self, ctx: ContextoCandle) -> bool:
        m = ctx.memoria
        if m.get("stop_91") is None:
            return False
        recente = m.get("fim_91") is not None and ctx.indice - m["fim_91"] <= ctx.params.janela_94
        return bool(m.get("comprado") or recente)

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        p = ctx.params
        if not (virou_para_baixo(ctx.indicadores["mme"]) and self._contexto_valido(ctx)):
            return None
        if not ctx.minima[-1] > ctx.memoria["stop_91"]:
            return None
        ctx.memoria["sinal_94"] = ctx.indice
        stop = ctx.memoria["stop_91"] if p.stop_tipo == "stop_do_9_1" else float(ctx.minima[-1]) - p.tick
        return compra_stop(
            ctx,
            ctx.maxima[-1],
            stop,
            "A MME virou para baixo depois de um 9.1 acionado, sem perder o stop original: gatilho na máxima mais 1 tick.",
            alvo_r=p.alvo_r,
        )

    def manter(self, ctx: ContextoCandle, pendente: Ordem) -> list[Ordem]:
        stop_91 = ctx.memoria.get("stop_91")
        if stop_91 is None or ctx.minima[-1] <= stop_91:
            ctx.anotar("sinal_cancelado", "O stop original do 9.1 foi perdido antes da entrada.")
            return []
        if ctx.indice - ctx.memoria.get("sinal_94", ctx.indice) >= ctx.params.janela_94:
            ctx.anotar("sinal_expirado", "A janela do 9.4 terminou sem acionar a entrada.")
            return []
        return [manter_ordem(pendente)]
