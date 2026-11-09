"""Setups baseados em indicadores, seção 3 de SETUPS_SWING_TRADE.md."""
from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field, model_validator

from app.motor.indicadores import adx, bollinger, estocastico, ifr, mma, mme, trix
from app.motor.tipos import ContextoCandle, Ordem, SerieCandles
from app.setups.comum import ParametrosComuns, SetupCompra, compra_stop, subindo

ROTULOS_ENTRADA = {"rompimento": "Rompimento da máxima", "fechamento": "No fechamento do candle"}


def _entrada_fechamento(preco: float, stop: float, motivo: str, alvo_r: float | None = None) -> Ordem:
    return Ordem("entrada_fechamento", preco, "gatilho_novo", motivo, stop=stop, alvo_r=alvo_r, novo_sinal=True)


def _saida_fechamento(motivo_saida: str, motivo: str, preco: float) -> Ordem:
    return Ordem("saida_fechamento", preco, motivo_saida, motivo, motivo_saida=motivo_saida)


class ParametrosIFR2(ParametrosComuns):
    # Neste setup o filtro de tendência vem ligado, conforme a especificação.
    filtro_tendencia_mm200: bool = Field(True, title="Só comprar acima da MMA 200", json_schema_extra={"grupo": "comum"})
    periodo_ifr: int = Field(2, ge=2, le=50, title="Período do IFR")
    nivel_compra: float = Field(25.0, gt=0, lt=100, title="Comprar com o IFR abaixo de")
    entrada_ifr2: Literal["fechamento", "abertura_seguinte"] = Field(
        "fechamento",
        title="Entrada",
        json_schema_extra={"rotulos": {"fechamento": "No fechamento do candle", "abertura_seguinte": "Na abertura seguinte"}},
    )
    usar_alvo: bool = Field(True, title="Alvo na maior máxima dos 2 candles anteriores")
    n_candles: int = Field(7, ge=1, le=100, title="Sair no fechamento depois de (candles)")
    nivel_saida: float | None = Field(
        None, gt=0, lt=100, title="Sair com o IFR acima de", description="Vazio deixa esta saída desligada."
    )
    stop_pct: float | None = Field(
        None,
        gt=0,
        le=50,
        title="Stop abaixo do fechamento do sinal (%)",
        description="Vazio segue a regra original, sem stop: o trade não tem resultado em R.",
    )


class SetupIFR2(SetupCompra):
    id = "ifr2"
    versao = "1.0"
    nome = "IFR2"
    familia = "Indicadores"
    origem = "Larry Connors"
    descricao = (
        "Compra com o IFR de 2 períodos muito baixo, acima da MMA 200. Sai na maior máxima dos 2 candles anteriores "
        "ou depois de 7 candles. A entrada padrão é no fechamento do sinal, e a regra original não usa stop."
    )
    Parametros = ParametrosIFR2

    def periodos(self, params: ParametrosIFR2) -> list[int]:
        return [params.periodo_ifr]

    def calcular(self, candles: SerieCandles, params: ParametrosIFR2) -> dict[str, np.ndarray]:
        return {"ifr": ifr(candles.fechamento, params.periodo_ifr)}

    def rotulos(self, params: ParametrosIFR2) -> dict[str, str]:
        return {"ifr": f"IFR {params.periodo_ifr}"}

    def indicadores_em_painel(self, params: ParametrosIFR2) -> set[str]:
        return {"ifr"}

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        p: ParametrosIFR2 = ctx.params
        if not ctx.indicadores["ifr"][-1] < p.nivel_compra:
            return None
        fechamento = float(ctx.fechamento[-1])
        stop = fechamento * (1 - p.stop_pct / 100) if p.stop_pct else None
        alvo = float(max(ctx.maxima[-1], ctx.maxima[-2])) if p.usar_alvo else None
        fechar = p.entrada_ifr2 == "fechamento"
        return Ordem(
            "entrada_fechamento" if fechar else "entrada_abertura",
            fechamento,
            "gatilho_novo",
            f"IFR abaixo de {p.nivel_compra:g}: compra {'no fechamento do candle' if fechar else 'na abertura seguinte'}.",
            stop=stop,
            alvo=alvo,
            sem_stop=stop is None,
            novo_sinal=True,
        )

    def gerenciar(self, ctx: ContextoCandle) -> list[Ordem]:
        p: ParametrosIFR2 = ctx.params
        fechamento = float(ctx.fechamento[-1])
        if ctx.indice - ctx.posicao.entrada_indice >= p.n_candles:
            return [_saida_fechamento("saida_tempo", f"Passaram {p.n_candles} candles sem atingir o alvo.", fechamento)]
        if p.nivel_saida and ctx.indicadores["ifr"][-1] > p.nivel_saida:
            return [_saida_fechamento("saida_indicador", f"IFR acima de {p.nivel_saida:g}.", fechamento)]
        if not p.usar_alvo:
            return []
        alvo = float(max(ctx.maxima[-1], ctx.maxima[-2]))
        return [Ordem("saida_alvo", alvo, "alvo_movel", "Maior máxima dos 2 candles anteriores.", motivo_saida="alvo_tecnico")]


class ParametrosRecuoIFR(ParametrosComuns):
    periodo_rapida: int = Field(17, ge=2, le=200, title="MME rápida")
    periodo_lenta: int = Field(20, ge=3, le=400, title="MME lenta")
    periodo_ifr: int = Field(4, ge=2, le=50, title="Período do IFR", description="O vídeo usa 4; com 2 há mais sinais.")
    nivel_compra: float = Field(25.0, gt=0, lt=100, title="Comprar com o IFR abaixo de")
    distancia_stop: float = Field(
        0.50, gt=0, le=100, title="Stop abaixo da mínima do sinal (R$)", description="Valor fixo em reais, como no vídeo."
    )
    pregoes_minimos: int = Field(
        2,
        ge=1,
        le=50,
        title="Pregões na posição antes de sair com lucro",
        description="Conta o pregão da entrada. Com 1, pode sair no fechamento do próprio dia da entrada.",
    )

    @model_validator(mode="after")
    def _rapida_menor_que_lenta(self):
        if self.periodo_rapida >= self.periodo_lenta:
            raise ValueError("A MME rápida precisa ter período menor que a lenta.")
        return self


class SetupRecuoIFR(SetupCompra):
    id = "recuo_ifr_curto"
    versao = "1.0"
    nome = "Recuo com IFR curto (Stormer)"
    familia = "Indicadores"
    origem = "Stormer, vídeo no YouTube (Ue8RUMy-0KI)"
    descricao = (
        "Compra o recuo de uma alta: MME 17 acima da MME 20 e IFR de 4 períodos abaixo de 25. Entra na abertura "
        "seguinte, com stop R$ 0,50 abaixo da mínima do sinal, e sai no primeiro fechamento com lucro a partir do "
        "segundo pregão na posição."
    )
    Parametros = ParametrosRecuoIFR

    def periodos(self, params: ParametrosRecuoIFR) -> list[int]:
        return [params.periodo_lenta, params.periodo_ifr]

    def calcular(self, candles: SerieCandles, params: ParametrosRecuoIFR) -> dict[str, np.ndarray]:
        return {
            "mme_rapida": mme(candles.fechamento, params.periodo_rapida),
            "mme_lenta": mme(candles.fechamento, params.periodo_lenta),
            "ifr": ifr(candles.fechamento, params.periodo_ifr),
        }

    def rotulos(self, params: ParametrosRecuoIFR) -> dict[str, str]:
        return {
            "mme_rapida": f"MME {params.periodo_rapida}",
            "mme_lenta": f"MME {params.periodo_lenta}",
            "ifr": f"IFR {params.periodo_ifr}",
        }

    def indicadores_em_painel(self, params: ParametrosRecuoIFR) -> set[str]:
        return {"ifr"}

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        p: ParametrosRecuoIFR = ctx.params
        ind = ctx.indicadores
        if not (ind["mme_rapida"][-1] > ind["mme_lenta"][-1] and ind["ifr"][-1] < p.nivel_compra):
            return None
        stop = float(ctx.minima[-1]) - p.distancia_stop
        if stop <= 0:
            # Em ação de poucos reais, o stop em reais cairia abaixo de zero: sem risco definido, não há sinal.
            return None
        return Ordem(
            "entrada_abertura",
            float(ctx.fechamento[-1]),
            "gatilho_novo",
            f"MME {p.periodo_rapida} acima da MME {p.periodo_lenta} e IFR {p.periodo_ifr} abaixo de "
            f"{p.nivel_compra:g}: compra na abertura seguinte.",
            stop=stop,
            novo_sinal=True,
        )

    def gerenciar(self, ctx: ContextoCandle) -> list[Ordem]:
        p: ParametrosRecuoIFR = ctx.params
        fechamento = float(ctx.fechamento[-1])
        na_posicao = ctx.indice - ctx.posicao.entrada_indice + 1
        if na_posicao >= p.pregoes_minimos and fechamento > ctx.posicao.entrada_preco:
            return [_saida_fechamento("saida_lucro", "Primeiro fechamento com lucro.", fechamento)]
        return []


class ParametrosDidi(ParametrosComuns):
    gatilho_didi: Literal["curta_cruza_longa", "agulhada_neutra"] = Field(
        "curta_cruza_longa",
        title="Gatilho",
        description="O primeiro é a leitura do vídeo. O segundo é a regra de SETUPS_SWING_TRADE.md, bem mais rara.",
        json_schema_extra={
            "rotulos": {
                "curta_cruza_longa": "MMA 3 cruza a MMA 20, acima da MMA 8",
                "agulhada_neutra": "MMA 3 e MMA 20 cruzam a MMA 8 juntas",
            }
        },
    )
    janela_cruzamento: int = Field(
        0, ge=0, le=5, title="Candles de tolerância entre os cruzamentos", description="Só vale no gatilho em que as duas cruzam a MMA 8."
    )
    confirma_adx: bool = Field(True, title="Confirmar com ADX subindo e DI+ acima de DI-")
    adx_periodo: int = Field(8, ge=2, le=50, title="Período do ADX")
    adx_min: float | None = Field(
        None,
        gt=0,
        le=100,
        title="ADX mínimo",
        description="Vazio deixa desligado. O vídeo olha 32 no gráfico de 5 minutos; no diário, 32 deixa pouquíssimos sinais.",
    )
    confirma_estocastico: bool = Field(True, title="Confirmar com Estocástico subindo e %K acima de %D")
    est_periodo: int = Field(8, ge=2, le=50, title="Período do Estocástico")
    est_suavizacao: int = Field(3, ge=1, le=20, title="Suavização do Estocástico")
    est_sinal: int = Field(3, ge=1, le=20, title="Média %D do Estocástico")
    confirma_trix: bool = Field(True, title="Confirmar com TRIX subindo e acima da média dele")
    trix_periodo: int = Field(8, ge=2, le=50, title="Período do TRIX")
    trix_sinal: int = Field(3, ge=1, le=20, title="Média do TRIX")
    confirma_bollinger: bool = Field(False, title="Confirmar com as Bandas de Bollinger abrindo")
    bb_periodo: int = Field(8, ge=2, le=100, title="Período de Bollinger")
    bb_desvios: float = Field(2.0, gt=0, le=5, title="Desvios de Bollinger")
    entrada_didi: Literal["abertura", "rompimento", "fechamento"] = Field(
        "abertura",
        title="Entrada",
        json_schema_extra={"rotulos": {"abertura": "Na abertura do pregão seguinte", **ROTULOS_ENTRADA}},
    )
    stop_didi: Literal["candle_sinal", "minima_3"] = Field(
        "candle_sinal",
        title="Stop inicial",
        json_schema_extra={"rotulos": {"candle_sinal": "Mínima do candle", "minima_3": "Mínima dos últimos 3 candles"}},
    )
    saida_didi: Literal["curta_cruza", "agulhada_venda", "alvo_r"] = Field(
        "curta_cruza",
        title="Saída",
        json_schema_extra={
            "rotulos": {
                "curta_cruza": "MMA 3 cruza abaixo da MMA 8",
                "agulhada_venda": "Agulhada de venda",
                "alvo_r": "Alvo fixo em R",
            }
        },
    )
    alvo_r: float = Field(2.0, gt=0, le=20, title="Alvo em múltiplos do risco (R)")


class SetupDidi(SetupCompra):
    id = "didi"
    versao = "1.1"
    nome = "Agulhada do Didi"
    familia = "Indicadores"
    origem = "Odir Aguiar (Didi); leitura dos quatro indicadores conforme vídeo do canal TraderDicas"
    descricao = (
        "No Didi Index, a MMA 3 cruza a MMA 20 para cima, acima da MMA 8, com ADX, Estocástico e TRIX "
        "sincronizados para cima. A entrada padrão é na abertura do pregão seguinte."
    )
    Parametros = ParametrosDidi

    def periodos(self, params: ParametrosDidi) -> list[int]:
        return [20, params.adx_periodo, params.est_periodo, params.trix_periodo, params.bb_periodo]

    def calcular(self, candles: SerieCandles, params: ParametrosDidi) -> dict[str, np.ndarray]:
        c = candles.fechamento
        m3, m8, m20 = mma(c, 3), mma(c, 8), mma(c, 20)
        valor_adx, di_mais, di_menos = adx(candles.maxima, candles.minima, c, params.adx_periodo)
        _, sup, inf = bollinger(c, params.bb_periodo, params.bb_desvios)
        est_k, est_d = estocastico(
            candles.maxima, candles.minima, c, params.est_periodo, params.est_suavizacao, params.est_sinal
        )
        linha_trix, media_trix = trix(c, params.trix_periodo, params.trix_sinal)
        return {
            "mma3": m3,
            "mma8": m8,
            "mma20": m20,
            "adx": valor_adx,
            "di_mais": di_mais,
            "di_menos": di_menos,
            "est_k": est_k,
            "est_d": est_d,
            "trix": linha_trix,
            "trix_media": media_trix,
            "_bb_sup": sup,
            "_bb_inf": inf,
        }

    def rotulos(self, params: ParametrosDidi) -> dict[str, str]:
        return {
            "mma3": "MMA 3",
            "mma8": "MMA 8",
            "mma20": "MMA 20",
            "adx": f"ADX {params.adx_periodo}",
            "di_mais": "DI+",
            "di_menos": "DI-",
            "est_k": "%K",
            "est_d": "%D",
            "trix": f"TRIX {params.trix_periodo}",
            "trix_media": f"Média {params.trix_sinal}",
        }

    def indicadores_em_painel(self, params: ParametrosDidi) -> set[str]:
        return {"adx", "di_mais", "di_menos", "est_k", "est_d", "trix", "trix_media"}

    def paineis(self, params: ParametrosDidi) -> list[set[str]]:
        # O TRIX fica perto de zero: na mesma escala do ADX e do Estocástico, viraria uma linha reta.
        return [{"adx", "di_mais", "di_menos"}, {"est_k", "est_d"}, {"trix", "trix_media"}]

    @staticmethod
    def _cruzou_para_cima(rapida: np.ndarray, base: np.ndarray, deslocamento: int) -> bool:
        i = -1 - deslocamento
        return bool(rapida[i - 1] <= base[i - 1] and rapida[i] > base[i])

    @staticmethod
    def _cruzou_para_baixo(rapida: np.ndarray, base: np.ndarray, deslocamento: int) -> bool:
        i = -1 - deslocamento
        return bool(rapida[i - 1] >= base[i - 1] and rapida[i] < base[i])

    def _agulhada(self, ctx: ContextoCandle, compra: bool) -> bool:
        """Os dois cruzamentos dentro da janela, com ao menos um deles neste candle."""
        ind = ctx.indicadores
        janela = ctx.params.janela_cruzamento
        if len(ind["mma3"]) < janela + 2:
            return False
        curta = self._cruzou_para_cima if compra else self._cruzou_para_baixo
        longa = self._cruzou_para_baixo if compra else self._cruzou_para_cima
        deslocamentos = range(janela + 1)
        curtas = [curta(ind["mma3"], ind["mma8"], d) for d in deslocamentos]
        longas = [longa(ind["mma20"], ind["mma8"], d) for d in deslocamentos]
        return any(curtas) and any(longas) and (curtas[0] or longas[0])

    def _gatilho(self, ctx: ContextoCandle, compra: bool) -> bool:
        if ctx.params.gatilho_didi == "agulhada_neutra":
            return self._agulhada(ctx, compra)
        ind = ctx.indicadores
        if compra:
            return self._cruzou_para_cima(ind["mma3"], ind["mma20"], 0) and bool(ind["mma3"][-1] > ind["mma8"][-1])
        return self._cruzou_para_baixo(ind["mma3"], ind["mma20"], 0) and bool(ind["mma3"][-1] < ind["mma8"][-1])

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        p: ParametrosDidi = ctx.params
        ind = ctx.indicadores
        if not self._gatilho(ctx, compra=True):
            return None
        if p.confirma_estocastico and not (subindo(ind["est_k"]) and ind["est_k"][-1] > ind["est_d"][-1]):
            return None
        if p.confirma_trix and not (subindo(ind["trix"]) and ind["trix"][-1] > ind["trix_media"][-1]):
            return None
        if p.confirma_adx and not (subindo(ind["adx"]) and ind["di_mais"][-1] > ind["di_menos"][-1]):
            return None
        if p.adx_min and not ind["adx"][-1] >= p.adx_min:
            return None
        if p.confirma_bollinger and not (ind["_bb_sup"][-1] > ind["_bb_sup"][-2] and ind["_bb_inf"][-1] < ind["_bb_inf"][-2]):
            return None
        base = float(ctx.minima[-1]) if p.stop_didi == "candle_sinal" else float(np.min(ctx.minima[-3:]))
        alvo_r = p.alvo_r if p.saida_didi == "alvo_r" else None
        motivo = (
            "Agulhada de compra: a MMA 3 cruzou a MMA 8 para cima e a MMA 20 para baixo."
            if p.gatilho_didi == "agulhada_neutra"
            else "Agulhada de compra: a MMA 3 cruzou a MMA 20 para cima, acima da MMA 8."
        )
        if p.entrada_didi == "fechamento":
            return _entrada_fechamento(float(ctx.fechamento[-1]), base - p.tick, motivo, alvo_r)
        if p.entrada_didi == "abertura":
            return Ordem(
                "entrada_abertura",
                float(ctx.fechamento[-1]),
                "gatilho_novo",
                f"{motivo} Compra na abertura seguinte.",
                stop=base - p.tick,
                alvo_r=alvo_r,
                novo_sinal=True,
            )
        return compra_stop(ctx, ctx.maxima[-1], base - p.tick, motivo, alvo_r=alvo_r)

    def gerenciar(self, ctx: ContextoCandle) -> list[Ordem]:
        p: ParametrosDidi = ctx.params
        ind = ctx.indicadores
        fechamento = float(ctx.fechamento[-1])
        if p.saida_didi == "curta_cruza" and self._cruzou_para_baixo(ind["mma3"], ind["mma8"], 0):
            return [_saida_fechamento("cruzamento_inverso", "A MMA 3 cruzou abaixo da MMA 8.", fechamento)]
        if p.saida_didi == "agulhada_venda" and self._gatilho(ctx, compra=False):
            return [_saida_fechamento("cruzamento_inverso", "Agulhada de venda.", fechamento)]
        return []


class ParametrosCruzamento(ParametrosComuns):
    tipo_rapida: Literal["mme", "mma"] = Field(
        "mme", title="Média rápida", json_schema_extra={"rotulos": {"mme": "Exponencial", "mma": "Aritmética"}}
    )
    periodo_rapida: int = Field(9, ge=2, le=200, title="Período da média rápida")
    tipo_lenta: Literal["mme", "mma"] = Field(
        "mma", title="Média lenta", json_schema_extra={"rotulos": {"mme": "Exponencial", "mma": "Aritmética"}}
    )
    periodo_lenta: int = Field(21, ge=3, le=400, title="Período da média lenta")
    exigir_lenta_subindo: bool = Field(False, title="Exigir média lenta subindo")
    entrada_cruzamento: Literal["fechamento", "rompimento"] = Field(
        "fechamento", title="Entrada", json_schema_extra={"rotulos": ROTULOS_ENTRADA}
    )
    n_stop: int = Field(5, ge=1, le=50, title="Stop na mínima dos últimos (candles)")
    saida_cruzamento: Literal["cruzamento", "alvo_r"] = Field(
        "cruzamento",
        title="Saída",
        json_schema_extra={"rotulos": {"cruzamento": "Cruzamento inverso", "alvo_r": "Alvo fixo em R"}},
    )
    alvo_r: float = Field(2.0, gt=0, le=20, title="Alvo em múltiplos do risco (R)")

    @model_validator(mode="after")
    def _rapida_menor_que_lenta(self):
        if self.periodo_rapida >= self.periodo_lenta:
            raise ValueError("A média rápida precisa de período menor que o da lenta.")
        return self


def _media(tipo: str, valores: np.ndarray, periodo: int) -> np.ndarray:
    return mme(valores, periodo) if tipo == "mme" else mma(valores, periodo)


class SetupCruzamento(SetupCompra):
    id = "cruz_9_21"
    versao = "1.0"
    nome = "Cruzamento de médias"
    familia = "Indicadores"
    descricao = "A média rápida cruza a lenta para cima. A entrada padrão é no fechamento do candle do cruzamento, e a saída, no cruzamento inverso."
    Parametros = ParametrosCruzamento

    def periodos(self, params: ParametrosCruzamento) -> list[int]:
        return [params.periodo_rapida, params.periodo_lenta]

    def calcular(self, candles: SerieCandles, params: ParametrosCruzamento) -> dict[str, np.ndarray]:
        return {
            "rapida": _media(params.tipo_rapida, candles.fechamento, params.periodo_rapida),
            "lenta": _media(params.tipo_lenta, candles.fechamento, params.periodo_lenta),
        }

    def rotulos(self, params: ParametrosCruzamento) -> dict[str, str]:
        return {
            "rapida": f"{params.tipo_rapida.upper()} {params.periodo_rapida}",
            "lenta": f"{params.tipo_lenta.upper()} {params.periodo_lenta}",
        }

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        p: ParametrosCruzamento = ctx.params
        r, l = ctx.indicadores["rapida"], ctx.indicadores["lenta"]
        if not (r[-2] <= l[-2] and r[-1] > l[-1]):
            return None
        if p.exigir_lenta_subindo and not subindo(l):
            return None
        stop = float(np.min(ctx.minima[-p.n_stop :])) - p.tick
        alvo_r = p.alvo_r if p.saida_cruzamento == "alvo_r" else None
        motivo = "A média rápida cruzou a lenta para cima."
        if p.entrada_cruzamento == "fechamento":
            return _entrada_fechamento(float(ctx.fechamento[-1]), stop, motivo, alvo_r)
        return compra_stop(ctx, ctx.maxima[-1], stop, motivo, alvo_r=alvo_r)

    def gerenciar(self, ctx: ContextoCandle) -> list[Ordem]:
        r, l = ctx.indicadores["rapida"], ctx.indicadores["lenta"]
        if ctx.params.saida_cruzamento == "cruzamento" and r[-2] >= l[-2] and r[-1] < l[-1]:
            return [_saida_fechamento("cruzamento_inverso", "A média rápida cruzou a lenta para baixo.", float(ctx.fechamento[-1]))]
        return []


class ParametrosBollinger(ParametrosComuns):
    periodo_bb: int = Field(20, ge=2, le=200, title="Período de Bollinger")
    desvios_bb: float = Field(2.0, gt=0, le=5, title="Desvios de Bollinger")
    exigir_alta: bool = Field(False, title="Exigir fechamento acima do anterior")
    saida_bb: Literal["central", "superior"] = Field(
        "central",
        title="Alvo",
        json_schema_extra={"rotulos": {"central": "Banda central", "superior": "Banda superior"}},
    )


class SetupBollinger(SetupCompra):
    id = "bb_retorno"
    versao = "1.0"
    nome = "Bollinger: fechamento fora e retorno"
    familia = "Indicadores"
    descricao = "Um fechamento abaixo da banda inferior seguido de um fechamento de volta para dentro. O alvo acompanha a banda a cada candle."
    Parametros = ParametrosBollinger

    def periodos(self, params: ParametrosBollinger) -> list[int]:
        return [params.periodo_bb]

    def calcular(self, candles: SerieCandles, params: ParametrosBollinger) -> dict[str, np.ndarray]:
        meio, sup, inf = bollinger(candles.fechamento, params.periodo_bb, params.desvios_bb)
        return {"bb_meio": meio, "bb_sup": sup, "bb_inf": inf}

    def rotulos(self, params: ParametrosBollinger) -> dict[str, str]:
        return {"bb_meio": f"MMA {params.periodo_bb}", "bb_sup": "Banda superior", "bb_inf": "Banda inferior"}

    def sinal(self, ctx: ContextoCandle) -> Ordem | None:
        p: ParametrosBollinger = ctx.params
        c, inf = ctx.fechamento, ctx.indicadores["bb_inf"]
        if not (c[-2] < inf[-2] and c[-1] > inf[-1]):
            return None
        if p.exigir_alta and not c[-1] > c[-2]:
            return None
        return compra_stop(
            ctx,
            ctx.maxima[-1],
            float(min(ctx.minima[-1], ctx.minima[-2])) - p.tick,
            "O fechamento voltou para dentro das bandas: gatilho na máxima mais 1 tick, stop na mínima dos 2 candles.",
        )

    def gerenciar(self, ctx: ContextoCandle) -> list[Ordem]:
        banda = "bb_meio" if ctx.params.saida_bb == "central" else "bb_sup"
        return [
            Ordem(
                "saida_alvo",
                float(ctx.indicadores[banda][-1]),
                "alvo_movel",
                "O alvo acompanha a banda de Bollinger.",
                motivo_saida="alvo_tecnico",
            )
        ]
