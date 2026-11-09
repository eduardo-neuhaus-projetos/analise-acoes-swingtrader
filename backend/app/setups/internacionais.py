"""Holy Grail, 1-2-3 com Ross Hook e Tartarugas, seção 4 de SETUPS_SWING_TRADE.md."""
from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field

from app.motor.indicadores import adx, atr, mme
from app.motor.tipos import ContextoCandle, Ordem, SerieCandles
from app.setups.comum import (
    ParametrosComuns,
    SetupCompra,
    compra_stop,
    manter_ordem,
    minima_do_pullback,
    mover_gatilho,
    stop_movel_na_minima,
)


class _SetupInternacional(SetupCompra):
    familia = "Internacionais"


class ParametrosHolyGrail(ParametrosComuns):
    adx_periodo: int = Field(14, ge=2, le=50, title="Período do ADX")
    adx_min: float = Field(30.0, gt=0, le=100, title="ADX mínimo")
    periodo_mme: int = Field(20, ge=2, le=200, title="Período da MME")
    apenas_primeiro_toque: bool = Field(True, title="Só o primeiro toque depois de o ADX passar do mínimo")
    arrastar_entrada: bool = Field(True, title="Arrastar a entrada enquanto a máxima baixar")
    saida: Literal["alvo_topo", "trailing_minima"] = Field(
        "alvo_topo",
        title="Saída",
        json_schema_extra={"rotulos": {"alvo_topo": "Alvo no topo anterior", "trailing_minima": "Stop móvel na mínima"}},
    )
    janela_topo: int = Field(20, ge=2, le=200, title="Candles para achar o topo e o pullback")


class SetupHolyGrail(_SetupInternacional):
    id = "holy_grail"
    versao = "1.0"
    nome = "Holy Grail"
    origem = "Linda Raschke"
    descricao = "Em tendência forte de alta (ADX acima de 30 e DI+ acima de DI-), o pullback que toca a MME 20 arma a compra no rompimento da máxima."
    Parametros = ParametrosHolyGrail

    def periodos(self, params: ParametrosHolyGrail) -> list[int]:
        return [params.adx_periodo, params.periodo_mme]

    def calcular(self, candles: SerieCandles, params: ParametrosHolyGrail) -> dict[str, np.ndarray]:
        valor_adx, di_mais, di_menos = adx(candles.maxima, candles.minima, candles.fechamento, params.adx_periodo)
        return {
            "mme": mme(candles.fechamento, params.periodo_mme),
            "adx": valor_adx,
            "di_mais": di_mais,
            "di_menos": di_menos,
        }

    def rotulos(self, params: ParametrosHolyGrail) -> dict[str, str]:
        return {"mme": f"MME {params.periodo_mme}", "adx": f"ADX {params.adx_periodo}", "di_mais": "DI+", "di_menos": "DI-"}

    def indicadores_em_painel(self, params: ParametrosHolyGrail) -> set[str]:
        return {"adx", "di_mais", "di_menos"}

    def observar(self, ctx: ContextoCandle) -> None:
        # O primeiro toque volta a valer quando o ADX cai abaixo do mínimo e sobe de novo.
        if not ctx.indicadores["adx"][-1] > ctx.params.adx_min:
            ctx.memoria["tocou"] = False

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        p: ParametrosHolyGrail = ctx.params
        ind = ctx.indicadores
        if not (ind["adx"][-1] > p.adx_min and ind["di_mais"][-1] > ind["di_menos"][-1]):
            return None
        if not ctx.minima[-1] <= ind["mme"][-1]:
            return None
        if p.apenas_primeiro_toque and ctx.memoria.get("tocou"):
            return None
        ctx.memoria["tocou"] = True
        return compra_stop(
            ctx,
            ctx.maxima[-1],
            minima_do_pullback(ctx, p.janela_topo) - p.tick,
            "Tendência forte e toque na MME: gatilho na máxima do candle mais 1 tick, stop na mínima do pullback.",
            alvo=float(np.max(ctx.maxima[-p.janela_topo :])) if p.saida == "alvo_topo" else None,
        )

    def manter(self, ctx: ContextoCandle, pendente: Ordem) -> list[Ordem]:
        if ctx.params.arrastar_entrada and ctx.maxima[-1] < ctx.maxima[-2]:
            return [
                mover_gatilho(
                    ctx,
                    pendente,
                    ctx.maxima[-1],
                    "O pullback continua: gatilho na máxima do candle mais recente mais 1 tick.",
                    stop=minima_do_pullback(ctx, ctx.params.janela_topo) - ctx.params.tick,
                )
            ]
        ctx.anotar("sinal_expirado", "O pullback terminou sem acionar a entrada.")
        return []

    def gerenciar(self, ctx: ContextoCandle) -> list[Ordem]:
        # Sinal no próprio topo deixa o alvo abaixo da entrada: sem alvo válido, vale o stop móvel.
        sem_alvo = ctx.params.saida == "alvo_topo" and ctx.posicao.alvo is None
        return stop_movel_na_minima(ctx) if ctx.params.saida == "trailing_minima" or sem_alvo else []


class ParametrosRoss(ParametrosComuns):
    modo: Literal["123", "hook", "ambos"] = Field(
        "123",
        title="Entradas",
        json_schema_extra={"rotulos": {"123": "1-2-3 de fundo", "hook": "Só Ross Hook", "ambos": "1-2-3 e Ross Hook"}},
    )
    n_pivo: int = Field(2, ge=1, le=10, title="Candles de cada lado do pivô")
    lookback: int = Field(20, ge=3, le=200, title="Candles para o fundo do ponto 1")
    validade_hook: int = Field(10, ge=1, le=100, title="Validade da ordem do hook (candles)")
    saida: Literal["trailing_minima", "alvo_r"] = Field(
        "trailing_minima",
        title="Saída",
        json_schema_extra={"rotulos": {"trailing_minima": "Stop móvel na mínima", "alvo_r": "Alvo fixo em R"}},
    )
    alvo_r: float = Field(2.0, gt=0, le=20, title="Alvo em múltiplos do risco (R)")


class SetupRoss(_SetupInternacional):
    id = "ross_123"
    versao = "1.0"
    nome = "1-2-3 e Ross Hook"
    origem = "Joe Ross"
    descricao = (
        "Detecta pivôs: fundo (1), topo (2) e fundo mais alto (3). Compra o rompimento do ponto 2. O Ross Hook compra "
        "a retomada depois desse rompimento. Cada pivô só é confirmado depois de os candles seguintes fecharem."
    )
    Parametros = ParametrosRoss

    def aquecimento(self, params: ParametrosRoss) -> int:
        return max(super().aquecimento(params), 2 * params.n_pivo + 1)

    def calcular(self, candles: SerieCandles, params: ParametrosRoss) -> dict[str, np.ndarray]:
        return {}

    def observar(self, ctx: ContextoCandle) -> None:
        """Mantém os pontos do 1-2-3 e o estado do hook. Só usa pivôs já confirmados por `n_pivo` candles."""
        m, p = ctx.memoria, ctx.params
        h, l, i = ctx.maxima, ctx.minima, ctx.indice
        k = i - p.n_pivo
        if k - p.n_pivo >= 0:
            if l[k] == np.min(l[k - p.n_pivo : i + 1]):
                inicio = max(0, k - p.lookback + 1)
                if l[k] == np.min(l[inicio : k + 1]) or (m.get("p1") is not None and l[k] <= l[m["p1"]]):
                    m.update(p1=k, p2=None, p3=None)
                elif m.get("p2") is not None and k > m["p2"] and m.get("p3") is None:
                    m["p3"] = k
            if h[k] == np.max(h[k - p.n_pivo : i + 1]) and m.get("p1") is not None and k > m["p1"] and m.get("p3") is None:
                if m.get("p2") is None or h[k] >= h[m["p2"]]:
                    m["p2"] = k

        # Rompeu o ponto 2: o padrão termina aqui, e o hook passa a procurar o fim do movimento.
        if m.get("p3") is not None and np.max(h[m["p3"] : i + 1]) > h[m["p2"]]:
            m.update(p1=None, p2=None, p3=None, hook_max=float(h[i]), hook_h=None, hook_usado=False)
            return
        if m.get("hook_max") is None:
            return
        if m.get("hook_h") is None:
            if h[i] > m["hook_max"]:
                m["hook_max"] = float(h[i])
            else:
                m.update(hook_h=m["hook_max"], hook_i=i, correcao=float(l[i]))
        else:
            m["correcao"] = min(m["correcao"], float(l[i]))

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        m, p = ctx.memoria, ctx.params
        h, l = ctx.maxima, ctx.minima
        alvo_r = p.alvo_r if p.saida == "alvo_r" else None
        if p.modo in ("123", "ambos") and m.get("p3") is not None and m.get("armou") != m["p3"]:
            m.update(armou=m["p3"], ordem="123", fundo=float(l[m["p3"]]))
            return compra_stop(
                ctx,
                h[m["p2"]],
                float(l[m["p3"]]) - p.tick,
                "Pivôs 1-2-3 confirmados: gatilho na máxima do ponto 2 mais 1 tick, stop no ponto 3 menos 1 tick.",
                alvo_r=alvo_r,
            )
        if p.modo in ("hook", "ambos") and m.get("hook_h") is not None and not m.get("hook_usado"):
            m.update(hook_usado=True, ordem="hook")
            return compra_stop(
                ctx,
                m["hook_h"],
                m["correcao"] - p.tick,
                "Ross Hook: o movimento parou de fazer novas máximas. Gatilho na máxima do movimento mais 1 tick.",
                alvo_r=alvo_r,
            )
        return None

    def manter(self, ctx: ContextoCandle, pendente: Ordem) -> list[Ordem]:
        m, p = ctx.memoria, ctx.params
        if m.get("ordem") == "123":
            if m.get("p3") is None or ctx.minima[-1] < m["fundo"]:
                ctx.anotar("sinal_cancelado", "O ponto 3 foi perdido antes da entrada.")
                return []
            return [manter_ordem(pendente)]
        if ctx.indice - m["hook_i"] >= p.validade_hook:
            ctx.anotar("sinal_expirado", "A validade da ordem do hook terminou sem acionar a entrada.")
            return []
        return [
            mover_gatilho(
                ctx,
                pendente,
                m["hook_h"],
                "A correção continua: o stop acompanha a mínima da correção menos 1 tick.",
                stop=m["correcao"] - p.tick,
            )
        ]

    def gerenciar(self, ctx: ContextoCandle) -> list[Ordem]:
        return stop_movel_na_minima(ctx) if ctx.params.saida == "trailing_minima" else []


class ParametrosDonchian(ParametrosComuns):
    n_entrada: int = Field(20, ge=2, le=400, title="Canal de entrada (candles)", description="Sistema 1: 20. Sistema 2: 55.")
    n_saida: int = Field(10, ge=2, le=400, title="Canal de saída (candles)", description="Sistema 1: 10. Sistema 2: 20.")
    periodo_atr: int = Field(20, ge=2, le=200, title="Período do ATR")
    multiplo_atr: float = Field(2.0, gt=0, le=20, title="Stop inicial em múltiplos do ATR")


class SetupDonchian(_SetupInternacional):
    id = "donchian"
    versao = "1.0"
    nome = "Tartarugas (Donchian)"
    origem = "Richard Dennis"
    descricao = "Compra o rompimento da maior máxima de 20 candles. O stop inicial fica a 2 ATR da entrada, e a saída, na menor mínima de 10 candles."
    Parametros = ParametrosDonchian

    def periodos(self, params: ParametrosDonchian) -> list[int]:
        return [params.n_entrada, params.n_saida, params.periodo_atr]

    def calcular(self, candles: SerieCandles, params: ParametrosDonchian) -> dict[str, np.ndarray]:
        return {"atr": atr(candles.maxima, candles.minima, candles.fechamento, params.periodo_atr)}

    def rotulos(self, params: ParametrosDonchian) -> dict[str, str]:
        return {"atr": f"ATR {params.periodo_atr}"}

    def indicadores_em_painel(self, params: ParametrosDonchian) -> set[str]:
        return {"atr"}

    def _canal(self, ctx: ContextoCandle) -> tuple[float, float]:
        topo = float(np.max(ctx.maxima[-ctx.params.n_entrada :]))
        return topo, topo + ctx.params.tick - ctx.params.multiplo_atr * float(ctx.indicadores["atr"][-1])

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        # A ordem fica sempre armada no topo do canal: atualiza o preço em vez de abrir um sinal por dia.
        if ctx.ordem("entrada_stop") is not None:
            return None
        topo, stop = self._canal(ctx)
        return compra_stop(
            ctx,
            topo,
            stop,
            f"Canal de {ctx.params.n_entrada} candles: gatilho na maior máxima mais 1 tick, stop a {ctx.params.multiplo_atr:g} ATR.",
        )

    def manter(self, ctx: ContextoCandle, pendente: Ordem) -> list[Ordem]:
        topo, stop = self._canal(ctx)
        return [mover_gatilho(ctx, pendente, topo, "O canal mudou: gatilho na maior máxima mais 1 tick.", stop=stop)]

    def gerenciar(self, ctx: ContextoCandle) -> list[Ordem]:
        p: ParametrosDonchian = ctx.params
        return [
            Ordem(
                "saida_stop",
                float(np.min(ctx.minima[-p.n_saida :])) - p.tick,
                "canal_saida",
                f"Menor mínima de {p.n_saida} candles menos 1 tick.",
                motivo_saida="canal_saida",
            )
        ]
