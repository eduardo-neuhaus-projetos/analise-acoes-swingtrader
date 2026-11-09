"""Setups de candle e preço, seção 2 de SETUPS_SWING_TRADE.md."""
from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field

from app.motor.indicadores import mma, mme
from app.motor.tipos import ContextoCandle, Ordem, SerieCandles
from app.setups.comum import (
    ParametrosComuns,
    SetupCompra,
    compra_stop,
    manter_ordem,
    mover_gatilho,
    stop_movel_na_minima,
    subindo,
)

ROTULOS_SAIDA = {"alvo_r": "Alvo fixo em R", "trailing_minima": "Stop móvel na mínima"}


class ParametrosSaidaAlvo(ParametrosComuns):
    saida: Literal["alvo_r", "trailing_minima"] = Field(
        "alvo_r", title="Saída", json_schema_extra={"rotulos": ROTULOS_SAIDA}
    )
    alvo_r: float = Field(2.0, gt=0, le=20, title="Alvo em múltiplos do risco (R)")


class _SetupCandle(SetupCompra):
    familia = "Candle e preço"

    def calcular(self, candles: SerieCandles, params) -> dict[str, np.ndarray]:
        return {}

    def alvo_r(self, ctx: ContextoCandle) -> float | None:
        return ctx.params.alvo_r if ctx.params.saida == "alvo_r" else None

    def gerenciar(self, ctx: ContextoCandle) -> list[Ordem]:
        return stop_movel_na_minima(ctx) if ctx.params.saida == "trailing_minima" else []


class Parametros123(ParametrosSaidaAlvo):
    exigir_fechamento_fundo: bool = Field(False, title="Exigir fechamento acima do fechamento do fundo")
    exigir_tendencia: Literal["nenhuma", "mme9", "mma21"] = Field(
        "nenhuma",
        title="Exigir média subindo",
        json_schema_extra={"rotulos": {"nenhuma": "Não exigir", "mme9": "MME 9", "mma21": "MMA 21"}},
    )
    arrastar_entrada: bool = Field(True, title="Arrastar a entrada não acionada")


class Setup123(_SetupCandle):
    id = "s_123"
    versao = "1.0"
    nome = "Setup 123"
    origem = "Larry Williams e Joe Ross; versão brasileira difundida por Stormer"
    descricao = "Três candles com a menor mínima no do meio. Compra o rompimento da máxima do terceiro, com stop no fundo."
    Parametros = Parametros123

    def periodos(self, params: Parametros123) -> list[int]:
        return {"nenhuma": [], "mme9": [9], "mma21": [21]}[params.exigir_tendencia]

    def calcular(self, candles: SerieCandles, params: Parametros123) -> dict[str, np.ndarray]:
        if params.exigir_tendencia == "mme9":
            return {"media": mme(candles.fechamento, 9)}
        if params.exigir_tendencia == "mma21":
            return {"media": mma(candles.fechamento, 21)}
        return {}

    def rotulos(self, params: Parametros123) -> dict[str, str]:
        return {"mme9": {"media": "MME 9"}, "mma21": {"media": "MMA 21"}}.get(params.exigir_tendencia, {})

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        p: Parametros123 = ctx.params
        l, c = ctx.minima, ctx.fechamento
        if not (l[-2] < l[-3] and l[-2] < l[-1]):
            return None
        if p.exigir_fechamento_fundo and not c[-1] > c[-2]:
            return None
        if p.exigir_tendencia != "nenhuma" and not subindo(ctx.indicadores["media"]):
            return None
        ctx.memoria["fundo"] = float(l[-2])
        return compra_stop(
            ctx,
            ctx.maxima[-1],
            float(l[-2]) - p.tick,
            "O candle do meio tem a menor mínima: gatilho na máxima do terceiro mais 1 tick, stop no fundo menos 1 tick.",
            alvo_r=self.alvo_r(ctx),
        )

    def manter(self, ctx: ContextoCandle, pendente: Ordem) -> list[Ordem]:
        if ctx.minima[-1] < ctx.memoria["fundo"]:
            ctx.anotar("sinal_cancelado", "O fundo do 123 foi perdido antes da entrada.")
            return []
        if ctx.params.arrastar_entrada and ctx.maxima[-1] < ctx.maxima[-2]:
            return [
                mover_gatilho(
                    ctx, pendente, ctx.maxima[-1], "O fundo segue valendo e a máxima baixou: gatilho na nova máxima mais 1 tick."
                )
            ]
        ctx.anotar("sinal_expirado", "A ordem não foi acionada e o candle não permite arrastar a entrada.")
        return []


class ParametrosPFR(ParametrosSaidaAlvo):
    pfr_estrito: bool = Field(False, title="Versão estrita", description="A mínima fica abaixo das duas mínimas anteriores.")
    pfr_minima_n: int | None = Field(
        None,
        ge=2,
        le=200,
        title="Menor mínima dos últimos N candles",
        description="Vazio deixa o filtro desligado. Sugestão: 5 a 10.",
    )


class SetupPFR(_SetupCandle):
    id = "pfr"
    versao = "1.0"
    nome = "PFR (Preço de Fechamento de Reversão)"
    descricao = "O candle faz mínima menor e fecha acima do fechamento anterior. Compra o rompimento da máxima, com validade de 1 pregão."
    Parametros = ParametrosPFR

    def aquecimento(self, params: ParametrosPFR) -> int:
        return max(super().aquecimento(params), params.pfr_minima_n or 0)

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        p: ParametrosPFR = ctx.params
        l, c = ctx.minima, ctx.fechamento
        referencia = min(l[-2], l[-3]) if p.pfr_estrito else l[-2]
        if not (l[-1] < referencia and c[-1] > c[-2]):
            return None
        if p.pfr_minima_n and l[-1] > np.min(l[-p.pfr_minima_n :]):
            return None
        return compra_stop(
            ctx,
            ctx.maxima[-1],
            float(l[-1]) - p.tick,
            "Mínima menor e fechamento acima do anterior: gatilho na máxima mais 1 tick, stop na mínima menos 1 tick.",
            alvo_r=self.alvo_r(ctx),
        )


class ParametrosPontoContinuo(ParametrosComuns):
    periodo_mma: int = Field(21, ge=2, le=200, title="Período da MMA")
    k_subindo: int = Field(3, ge=1, le=50, title="Média subindo há pelo menos (candles)")
    p_acima: int = Field(3, ge=1, le=50, title="Fechamentos anteriores acima da média")
    tolerancia_pct: float = Field(0.0, ge=0, le=5, title="Tolerância do toque (%)")
    tolerancia_fechamento_pct: float = Field(0.0, ge=0, le=5, title="Tolerância do fechamento abaixo da média (%)")
    saida: Literal["trailing_minima", "alvo_topo", "alvo_r"] = Field(
        "trailing_minima",
        title="Saída",
        json_schema_extra={
            "rotulos": {
                "trailing_minima": "Stop móvel na mínima",
                "alvo_topo": "Alvo no último topo",
                "alvo_r": "Alvo fixo em R",
            }
        },
    )
    alvo_r: float = Field(2.0, gt=0, le=20, title="Alvo em múltiplos do risco (R)")
    n_topo: int = Field(20, ge=2, le=200, title="Candles para achar o último topo")


class SetupPontoContinuo(_SetupCandle):
    id = "ponto_cont"
    versao = "1.0"
    nome = "Ponto Contínuo"
    origem = "Difundido por Stormer"
    descricao = "Pullback que toca a MMA 21 subindo e fecha na média ou acima. Compra o rompimento da máxima do candle do toque."
    Parametros = ParametrosPontoContinuo

    def periodos(self, params: ParametrosPontoContinuo) -> list[int]:
        return [params.periodo_mma]

    def calcular(self, candles: SerieCandles, params: ParametrosPontoContinuo) -> dict[str, np.ndarray]:
        return {"mma": mma(candles.fechamento, params.periodo_mma)}

    def rotulos(self, params: ParametrosPontoContinuo) -> dict[str, str]:
        return {"mma": f"MMA {params.periodo_mma}"}

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        # O arrasto é o próprio sinal repetido: outro toque na média substitui a ordem.
        p: ParametrosPontoContinuo = ctx.params
        media, c, l = ctx.indicadores["mma"], ctx.fechamento, ctx.minima
        if len(c) <= max(p.k_subindo, p.p_acima):
            return None
        if not (subindo(media) and media[-1] > media[-1 - p.k_subindo]):
            return None
        if not np.all(c[-1 - p.p_acima : -1] > media[-1 - p.p_acima : -1]):
            return None
        tocou = l[-1] <= media[-1] * (1 + p.tolerancia_pct / 100)
        fechou_acima = c[-1] >= media[-1] * (1 - p.tolerancia_fechamento_pct / 100)
        if not (tocou and fechou_acima):
            return None
        alvo = float(np.max(ctx.maxima[-p.n_topo :])) if p.saida == "alvo_topo" else None
        return compra_stop(
            ctx,
            ctx.maxima[-1],
            float(l[-1]) - p.tick,
            "O pullback tocou a média subindo: gatilho na máxima do candle mais 1 tick, stop na mínima menos 1 tick.",
            alvo_r=p.alvo_r if p.saida == "alvo_r" else None,
            alvo=alvo,
        )

    def gerenciar(self, ctx: ContextoCandle) -> list[Ordem]:
        p: ParametrosPontoContinuo = ctx.params
        # Sinal no próprio topo deixa o alvo abaixo da entrada: sem alvo válido, vale o stop móvel.
        sem_alvo = p.saida == "alvo_topo" and ctx.posicao.alvo is None
        return stop_movel_na_minima(ctx) if p.saida == "trailing_minima" or sem_alvo else []


class ParametrosElefante(ParametrosSaidaAlvo):
    fator: float = Field(2.0, gt=0, le=20, title="Tamanho mínimo (vezes a média)")
    n_media: int = Field(20, ge=2, le=200, title="Candles da média de tamanho")
    base_tamanho: Literal["range", "corpo"] = Field(
        "range",
        title="Medir o tamanho por",
        json_schema_extra={"rotulos": {"range": "Máxima menos mínima", "corpo": "Corpo do candle"}},
    )
    corpo_min: float = Field(0.70, gt=0, le=1, title="Corpo mínimo (fração do candle)")
    pavio_max: float = Field(0.25, ge=0, le=1, title="Pavio superior máximo (fração do candle)")
    filtro_volume: bool = Field(False, title="Exigir volume acima da média de 20")
    entrada_elefante: Literal["rompimento", "fechamento"] = Field(
        "rompimento",
        title="Entrada",
        json_schema_extra={"rotulos": {"rompimento": "Rompimento da máxima", "fechamento": "No fechamento do candle"}},
    )
    stop_elefante: Literal["minima", "meio"] = Field(
        "minima",
        title="Stop inicial",
        json_schema_extra={"rotulos": {"minima": "Mínima do candle", "meio": "Meio do candle"}},
    )


class SetupElefante(_SetupCandle):
    id = "elefante"
    versao = "1.0"
    nome = "Barra Elefante"
    descricao = "Candle de alta bem maior que a média, com corpo dominante e fechamento perto da máxima."
    Parametros = ParametrosElefante

    def periodos(self, params: ParametrosElefante) -> list[int]:
        return [params.n_media]

    def calcular(self, candles: SerieCandles, params: ParametrosElefante) -> dict[str, np.ndarray]:
        faixa = candles.maxima - candles.minima
        if params.base_tamanho == "corpo":
            faixa = np.abs(candles.fechamento - candles.abertura)
        saida = {"_tamanho_medio": mma(faixa, params.n_media)}
        if params.filtro_volume:
            saida["_volume_20"] = mma(candles.volume, 20)
        return saida

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        p: ParametrosElefante = ctx.params
        o, h, l, c = float(ctx.abertura[-1]), float(ctx.maxima[-1]), float(ctx.minima[-1]), float(ctx.fechamento[-1])
        faixa = h - l
        corpo = abs(c - o)
        if not (c > o and faixa > 0):
            return None
        tamanho = corpo if p.base_tamanho == "corpo" else faixa
        if not tamanho >= p.fator * ctx.indicadores["_tamanho_medio"][-2]:
            return None
        if corpo / faixa < p.corpo_min or (h - c) / faixa > p.pavio_max:
            return None
        if p.filtro_volume and not ctx.volume[-1] > ctx.indicadores["_volume_20"][-1]:
            return None
        stop = (h + l) / 2 if p.stop_elefante == "meio" else l - p.tick
        alvo_r = self.alvo_r(ctx)
        if p.entrada_elefante == "fechamento":
            return Ordem(
                "entrada_fechamento",
                c,
                "gatilho_novo",
                "Barra elefante: compra no fechamento do candle.",
                stop=stop,
                alvo_r=alvo_r,
                novo_sinal=True,
            )
        return compra_stop(ctx, h, stop, "Barra elefante: gatilho na máxima do candle mais 1 tick.", alvo_r=alvo_r)


class ParametrosInside(ParametrosSaidaAlvo):
    inclusivo: bool = Field(False, title="Aceitar máxima e mínima iguais às da barra mãe")
    filtro_tendencia: Literal["nenhum", "mme9", "mma21"] = Field(
        "nenhum",
        title="Filtro de tendência",
        json_schema_extra={"rotulos": {"nenhum": "Desligado", "mme9": "MME 9 subindo", "mma21": "Fechamento acima da MMA 21"}},
    )
    referencia_inside: Literal["inside", "mae"] = Field(
        "inside",
        title="Referência da entrada e do stop",
        json_schema_extra={"rotulos": {"inside": "Barra inside", "mae": "Barra mãe"}},
    )
    validade: int = Field(2, ge=1, le=20, title="Validade da ordem (candles)")


class SetupInside(_SetupCandle):
    id = "inside"
    versao = "1.0"
    nome = "Inside Bar"
    descricao = "Candle contido no anterior. Compra o rompimento da máxima da barra inside ou da barra mãe."
    Parametros = ParametrosInside

    def periodos(self, params: ParametrosInside) -> list[int]:
        return {"nenhum": [], "mme9": [9], "mma21": [21]}[params.filtro_tendencia]

    def calcular(self, candles: SerieCandles, params: ParametrosInside) -> dict[str, np.ndarray]:
        if params.filtro_tendencia == "mme9":
            return {"media": mme(candles.fechamento, 9)}
        if params.filtro_tendencia == "mma21":
            return {"media": mma(candles.fechamento, 21)}
        return {}

    def rotulos(self, params: ParametrosInside) -> dict[str, str]:
        return {"mme9": {"media": "MME 9"}, "mma21": {"media": "MMA 21"}}.get(params.filtro_tendencia, {})

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        p: ParametrosInside = ctx.params
        h, l = ctx.maxima, ctx.minima
        contida = h[-1] <= h[-2] and l[-1] >= l[-2] if p.inclusivo else h[-1] < h[-2] and l[-1] > l[-2]
        if not contida:
            return None
        if p.filtro_tendencia == "mme9" and not subindo(ctx.indicadores["media"]):
            return None
        if p.filtro_tendencia == "mma21" and not ctx.fechamento[-1] > ctx.indicadores["media"][-1]:
            return None
        ctx.memoria["sinal_inside"] = ctx.indice
        indice = -1 if p.referencia_inside == "inside" else -2
        return compra_stop(
            ctx,
            h[indice],
            float(l[indice]) - p.tick,
            "Candle contido no anterior: gatilho na máxima da referência mais 1 tick, stop na mínima menos 1 tick.",
            alvo_r=self.alvo_r(ctx),
        )

    def manter(self, ctx: ContextoCandle, pendente: Ordem) -> list[Ordem]:
        if ctx.indice - ctx.memoria["sinal_inside"] >= ctx.params.validade:
            ctx.anotar("sinal_expirado", "A validade da ordem terminou sem acionar a entrada.")
            return []
        return [manter_ordem(pendente)]
