"""Motor de backtest: percorre os candles em ordem, e cada ordem vale a partir do pregão seguinte.

O mesmo código atende ao backtest, ao acompanhamento e às duas abas, para que todos sigam regras idênticas.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from app.motor.tipos import (
    ContextoCandle,
    EventoTrade,
    Ordem,
    Posicao,
    ResultadoMotor,
    SerieCandles,
    Sinal,
    Trade,
)
from app.setups.base import Setup

AVISO_ENTRADA_STOP = "entrada_e_stop_no_mesmo_candle"
AVISO_ENTRADA_ALVO = "entrada_e_alvo_no_mesmo_candle"
AVISO_ALVO_STOP = "alvo_e_stop_no_mesmo_candle"

TEXTO_AVISO = {
    AVISO_ENTRADA_STOP: (
        "Entrada e stop no mesmo candle: sem dados intradiários a ordem dos eventos é "
        "desconhecida, e o padrão conservador considera o stop executado."
    ),
    AVISO_ENTRADA_ALVO: (
        "Entrada e alvo no mesmo candle: sem dados intradiários a ordem dos eventos é "
        "desconhecida, e o trade foi encerrado no alvo."
    ),
    AVISO_ALVO_STOP: (
        "Alvo e stop no mesmo candle: sem dados intradiários a ordem dos eventos é "
        "desconhecida, e o padrão conservador considera o stop executado."
    ),
}

def preco_br(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",")


TEXTO_MOTIVO_SAIDA = {
    "stop_inicial": "Stop inicial",
    "saida_armada": "Saída armada",
    "alvo": "Alvo fixo",
    "alvo_tecnico": "Alvo técnico",
    "trailing_minima": "Stop móvel",
    "canal_saida": "Canal de saída",
    "saida_tempo": "Saída por tempo",
    "saida_indicador": "Saída por indicador",
    "saida_lucro": "Primeiro fechamento com lucro",
    "cruzamento_inverso": "Cruzamento inverso",
}

TIPOS_ENTRADA = ("entrada_stop", "entrada_abertura", "entrada_fechamento")


def _ordem(ordens: list[Ordem], *tipos: str) -> Ordem | None:
    return next((o for o in ordens if o.tipo in tipos), None)


def _indicadores_por_segmento(
    candles: SerieCandles, setup: Setup, params
) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Calcula os indicadores em cada trecho contínuo: depois de uma lacuna eles recomeçam."""
    n = len(candles)
    pronto = np.zeros(n, dtype=bool)
    if n == 0:
        return {}, pronto
    inicios = [0] + [i for i in range(1, n) if candles.quebra[i]]
    fins = inicios[1:] + [n]
    aquecimento = setup.aquecimento(params)
    partes: dict[str, list[np.ndarray]] = {}
    for inicio, fim in zip(inicios, fins):
        calculados = setup.indicadores(candles.fatia(inicio, fim), params)
        for nome, valores in calculados.items():
            partes.setdefault(nome, []).append(np.asarray(valores, dtype=float))
        if fim - inicio >= aquecimento:
            pronto[inicio + aquecimento - 1 : fim] = True
    indicadores = {nome: np.concatenate(v) for nome, v in partes.items()}
    for valores in indicadores.values():
        valores.setflags(write=False)
    return indicadores, pronto


def executar(
    candles: SerieCandles,
    setup: Setup,
    params,
    inicio: str | None = None,
    fim: str | None = None,
) -> ResultadoMotor:
    """Roda o setup. `inicio` limita os sinais sem cortar os candles do aquecimento; `fim` encerra os dados."""
    if fim is not None:
        ultimo = next((i for i, d in enumerate(candles.datas) if d > fim), len(candles))
        candles = candles.fatia(0, ultimo)

    indicadores, pronto = _indicadores_por_segmento(candles, setup, params)
    n = len(candles)
    avisos: list[str] = []
    if not pronto.any():
        avisos.append(
            f"Candles insuficientes: o setup precisa de {setup.aquecimento(params)} candles "
            f"seguidos para aquecer e a série tem {n}."
        )

    trades: list[Trade] = []
    sinais: list[Sinal] = []
    ordens: list[Ordem] = []
    posicao: Posicao | None = None
    trade_atual: Trade | None = None
    sinal_atual: Sinal | None = None
    memoria: dict = {}

    ab, ma, mi, fe, vo = (
        candles.abertura,
        candles.maxima,
        candles.minima,
        candles.fechamento,
        candles.volume,
    )
    for vetor in (ab, ma, mi, fe, vo):
        vetor.setflags(write=False)

    for i in range(n):
        data = candles.datas[i]
        entrou_neste_candle = False

        # Depois de uma lacuna o gatilho pendente perdeu a validade: os indicadores recomeçam do zero.
        if candles.quebra[i]:
            memoria = {}
        if candles.quebra[i] and sinal_atual is not None:
            sinal_atual.situacao = "cancelado"
            sinal_atual.motivo = "A série foi interrompida por uma lacuna antes da entrada."
            sinal_atual.data_fim = data
            sinal_atual = None
            ordens = [o for o in ordens if o.tipo not in TIPOS_ENTRADA]

        # 1. Ordens definidas no fechamento anterior enfrentam este candle.
        entrada = _ordem(ordens, "entrada_stop", "entrada_abertura")
        if posicao is None and entrada is not None:
            if entrada.tipo == "entrada_abertura":
                ordens = []
                posicao, trade_atual = _abrir_posicao(
                    entrada, float(ab[i]), i, data, sinal_atual, trades, "Compra na abertura do pregão seguinte ao sinal."
                )
                sinal_atual = None
                # A abertura é o primeiro preço do candle: não há dúvida sobre a ordem dos eventos depois dela.
            elif ma[i] >= entrada.preco:
                ordens = []
                em_gap = ab[i] >= entrada.preco
                if em_gap and not entrada.aceitar_gap:
                    sinal_atual.situacao = "cancelado"
                    sinal_atual.motivo = "A abertura ficou acima do gatilho e a entrada em gap está desligada."
                    sinal_atual.data_fim = data
                else:
                    regra = (
                        "A abertura ficou acima do gatilho: a compra stop executa na abertura."
                        if em_gap
                        else f"A máxima alcançou o gatilho de {preco_br(entrada.preco)}."
                    )
                    preco = float(ab[i]) if em_gap else entrada.preco
                    posicao, trade_atual = _abrir_posicao(entrada, preco, i, data, sinal_atual, trades, regra)
                    entrou_neste_candle = posicao is not None
                sinal_atual = None

        if posicao is not None:
            resultado = _avaliar_saida(
                posicao,
                _ordem(ordens, "saida_stop"),
                _ordem(ordens, "saida_alvo"),
                ab[i],
                ma[i],
                mi[i],
                entrou_neste_candle,
            )
            if resultado is not None:
                preco, motivo, aviso, regra = resultado
                _encerrar(trade_atual, posicao, data, i, preco, motivo, aviso, regra)
                posicao = None
                trade_atual = None
                ordens = []

        # 2. Com o candle fechado, o setup define as ordens do próximo pregão.
        if not pronto[i] or (inicio is not None and data < inicio):
            continue
        fim_contexto = i + 1
        contexto = ContextoCandle(
            params=params,
            datas=candles.datas[:fim_contexto],
            abertura=ab[:fim_contexto],
            maxima=ma[:fim_contexto],
            minima=mi[:fim_contexto],
            fechamento=fe[:fim_contexto],
            volume=vo[:fim_contexto],
            indicadores={k: v[:fim_contexto] for k, v in indicadores.items()},
            posicao=replace(posicao) if posicao else None,
            ordens_ativas=list(ordens),
            memoria=memoria,
        )
        novas = list(setup.ao_fechar_candle(contexto))
        sinal_atual = _registrar_mudancas(
            data, ordens, novas, contexto.notas, trade_atual, sinais, sinal_atual
        )
        ordens = novas

        # Alvo móvel: o trade mostra o último alvo calculado.
        alvo_movel = _ordem(ordens, "saida_alvo")
        if trade_atual is not None and alvo_movel is not None:
            trade_atual.alvo = alvo_movel.preco

        # Ordens a fechamento executam no preço já conhecido deste candle, sem depender do próximo pregão.
        saida_agora = _ordem(ordens, "saida_fechamento")
        if posicao is not None and saida_agora is not None:
            _encerrar(
                trade_atual, posicao, data, i, float(fe[i]), saida_agora.motivo_saida or "saida_armada", None,
                saida_agora.motivo,
            )  # fmt: skip
            posicao = None
            trade_atual = None
            ordens = []
        entrada_agora = _ordem(ordens, "entrada_fechamento")
        if posicao is None and entrada_agora is not None:
            ordens = []
            posicao, trade_atual = _abrir_posicao(
                entrada_agora, float(fe[i]), i, data, sinal_atual, trades, "Compra no fechamento do candle do sinal."
            )
            sinal_atual = None

    if trade_atual is not None and n:
        trade_atual.duracao_pregoes = n - 1 - posicao.entrada_indice
        trade_atual.preco_referencia = float(fe[-1])

    if posicao is not None:
        estado = "saida_armada" if any(o.tipo == "saida_stop" for o in ordens) else "posicionado"
    else:
        estado = "armado" if ordens else "sem_sinal"

    return ResultadoMotor(
        trades=trades,
        sinais=sinais,
        estado=estado,
        ordens_ativas=ordens,
        posicao=posicao,
        indicadores=indicadores,
        avisos=avisos,
        candles_usados=n,
    )


def _abrir_posicao(
    entrada: Ordem, preco: float, i: int, data: str, sinal: Sinal, trades: list[Trade], regra: str
) -> tuple[Posicao | None, Trade | None]:
    """Abre a posição, ou descarta o sinal quando o preço de entrada não deixa risco definido."""
    if not entrada.sem_stop and (entrada.stop is None or preco <= entrada.stop):
        # A entrada pode ficar abaixo do stop, por gatilho atualizado ou gap na abertura: sem risco definido, não há trade.
        sinal.situacao = "invalidado"
        sinal.motivo = "O preço de entrada ficou abaixo do stop inicial; ordem descartada."
        sinal.data_fim = data
        return None, None
    stop = None if entrada.sem_stop else entrada.stop
    risco = None if stop is None else preco - stop
    alvo = entrada.alvo if entrada.alvo is not None and entrada.alvo > preco else None
    motivo_alvo = "alvo_tecnico"
    if entrada.alvo_r and risco is not None:
        alvo = preco + entrada.alvo_r * risco
        motivo_alvo = "alvo"
    posicao = Posicao(sinal.data, i, data, preco, stop, risco, alvo, motivo_alvo)
    trade = Trade(
        numero=len(trades) + 1,
        sinal_data=sinal.data,
        entrada_data=data,
        entrada_preco=preco,
        stop=stop,
        risco=risco,
        alvo=alvo,
        eventos=list(sinal.eventos),
    )
    trade.eventos.append(EventoTrade(data, "entrada", preco, regra))
    sinal.situacao = "acionado"
    sinal.gatilho_final = entrada.preco
    sinal.data_fim = data
    trades.append(trade)
    return posicao, trade


def _encerrar(
    trade: Trade, posicao: Posicao, data: str, i: int, preco: float, motivo: str, aviso: str | None, regra: str
) -> None:
    trade.saida_data = data
    trade.saida_preco = preco
    trade.motivo_saida = motivo
    trade.duracao_pregoes = i - posicao.entrada_indice
    trade.aberto = False
    if aviso:
        trade.avisos.append(aviso)
    trade.eventos.append(EventoTrade(data, "saida", preco, regra))


def _avaliar_saida(
    posicao: Posicao,
    saida: Ordem | None,
    alvo_movel: Ordem | None,
    abertura,
    maxima,
    minima,
    entrou_neste_candle: bool,
) -> tuple[float, str, str | None, str] | None:
    """Devolve (preço, motivo, aviso, regra) quando alguma ordem de saída executa neste candle."""
    preco_venda = posicao.stop
    motivo_venda = "stop_inicial"
    regra_venda = "" if posicao.stop is None else f"Stop inicial em {preco_br(posicao.stop)}."
    if saida is not None and (preco_venda is None or saida.preco > preco_venda):
        # Stop e saída armada no mesmo candle: vale a ordem de preço mais alto, a primeira alcançada na queda.
        preco_venda = saida.preco
        motivo_venda = saida.motivo_saida or "saida_armada"
        regra_venda = f"{TEXTO_MOTIVO_SAIDA[motivo_venda]} em {preco_br(saida.preco)}: {saida.motivo}"

    alvo = alvo_movel.preco if alvo_movel is not None else posicao.alvo
    motivo_alvo = (alvo_movel.motivo_saida or "alvo_tecnico") if alvo_movel is not None else posicao.motivo_alvo
    if not entrou_neste_candle:
        # A abertura é o primeiro preço do candle, então um gap decide sem ambiguidade.
        if alvo is not None and abertura >= alvo:
            return float(abertura), motivo_alvo, None, "A abertura ficou acima do alvo: executa na abertura."
        if preco_venda is not None and abertura <= preco_venda:
            return (
                float(abertura),
                motivo_venda,
                None,
                f"{regra_venda} A abertura ficou abaixo da ordem: executa na abertura.",
            )

    atingiu_venda = preco_venda is not None and minima <= preco_venda
    atingiu_alvo = alvo is not None and maxima >= alvo

    if atingiu_venda:
        if entrou_neste_candle:
            aviso = AVISO_ENTRADA_STOP
        elif atingiu_alvo:
            aviso = AVISO_ALVO_STOP
        else:
            aviso = None
        return preco_venda, motivo_venda, aviso, f"{regra_venda} A mínima alcançou a ordem."
    if atingiu_alvo:
        aviso = AVISO_ENTRADA_ALVO if entrou_neste_candle else None
        return float(alvo), motivo_alvo, aviso, f"A máxima alcançou o alvo de {preco_br(alvo)}."
    return None


def _registrar_mudancas(
    data: str,
    antigas: list[Ordem],
    novas: list[Ordem],
    notas: list[tuple[str, str]],
    trade: Trade | None,
    sinais: list[Sinal],
    sinal_atual: Sinal | None,
) -> Sinal | None:
    """Transforma a diferença entre as ordens de dois pregões em eventos rastreáveis."""
    motivo_nota = notas[-1][1] if notas else ""
    entrada_antiga = _ordem(antigas, *TIPOS_ENTRADA)
    entrada_nova = _ordem(novas, *TIPOS_ENTRADA)
    saida_antiga = _ordem(antigas, "saida_stop")
    saida_nova = _ordem(novas, "saida_stop")
    sai_agora = _ordem(novas, "saida_fechamento") is not None

    if entrada_nova is not None and entrada_nova.novo_sinal:
        if sinal_atual is not None:
            sinal_atual.situacao = "substituido"
            sinal_atual.motivo = "Um novo sinal substituiu este antes da entrada."
            sinal_atual.data_fim = data
        sinal_atual = Sinal(data, entrada_nova.preco, entrada_nova.stop)
        sinal_atual.eventos.append(EventoTrade(data, "sinal", entrada_nova.preco, entrada_nova.motivo))
        sinais.append(sinal_atual)
    elif entrada_nova is not None and entrada_antiga is not None:
        if entrada_nova.preco != entrada_antiga.preco:
            sinal_atual.eventos.append(
                EventoTrade(data, "gatilho_atualizado", entrada_nova.preco, entrada_nova.motivo)
            )
    elif entrada_nova is None and entrada_antiga is not None and sinal_atual is not None:
        sinal_atual.situacao = "cancelado"
        sinal_atual.motivo = motivo_nota
        sinal_atual.data_fim = data
        sinal_atual.gatilho_final = entrada_antiga.preco
        sinal_atual.eventos.append(EventoTrade(data, "sinal_cancelado", None, motivo_nota))
        sinal_atual = None

    if trade is not None:
        if saida_nova is not None and saida_antiga is None:
            trade.eventos.append(EventoTrade(data, "saida_armada", saida_nova.preco, saida_nova.motivo))
        elif saida_nova is not None and saida_nova.preco != saida_antiga.preco:
            trade.eventos.append(EventoTrade(data, "saida_atualizada", saida_nova.preco, saida_nova.motivo))
        elif saida_nova is None and saida_antiga is not None and not sai_agora:
            trade.eventos.append(EventoTrade(data, "saida_cancelada", None, motivo_nota))
    return sinal_atual
