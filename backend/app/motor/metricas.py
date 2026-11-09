"""Métricas do dashboard, sempre calculadas a partir da lista de trades e nunca guardadas como dado de origem."""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from statistics import mean


def _encerrados(trades: list[dict]) -> list[dict]:
    fechados = [t for t in trades if not t["aberto"]]
    return sorted(fechados, key=lambda t: (t["saida_data"], t["numero"]))


def curva_capital(trades: list[dict], datas: list[str]) -> list[dict]:
    """Retorno composto dos trades em sequência, base 100, com o drawdown em cada data."""
    fatores: dict[str, float] = {}
    for t in _encerrados(trades):
        fatores[t["saida_data"]] = fatores.get(t["saida_data"], 1.0) * (1 + t["liquido_pct"] / 100)
    capital = 100.0
    pico = 100.0
    curva = []
    for data in datas:
        capital *= fatores.get(data, 1.0)
        pico = max(pico, capital)
        curva.append({"data": data, "capital": capital, "drawdown": (capital / pico - 1) * 100})
    return curva


def indicadores_principais(trades: list[dict], datas: list[str]) -> dict:
    fechados = _encerrados(trades)
    acertos = [t for t in fechados if t["liquido_pct"] > 0]
    erros = [t for t in fechados if t["liquido_pct"] < 0]
    empates = len(fechados) - len(acertos) - len(erros)
    decididos = len(acertos) + len(erros)

    ganho_medio = mean(t["liquido_pct"] for t in acertos) if acertos else None
    perda_media = mean(t["liquido_pct"] for t in erros) if erros else None
    soma_ganhos = sum(t["liquido_pct"] for t in acertos)
    soma_perdas = sum(t["liquido_pct"] for t in erros)

    em_r = [t["liquido_r"] for t in fechados if t["liquido_r"] is not None]
    curva = curva_capital(trades, datas)
    retorno = curva[-1]["capital"] - 100 if curva else 0.0
    drawdown = min((p["drawdown"] for p in curva), default=0.0)

    return {
        "trades": len(fechados),
        "abertos": sum(1 for t in trades if t["aberto"]),
        "acertos": len(acertos),
        "erros": len(erros),
        "empates": empates,
        "taxa_acerto": len(acertos) / decididos * 100 if decididos else None,
        "taxa_erro": len(erros) / decididos * 100 if decididos else None,
        "ganho_medio": ganho_medio,
        "perda_media": perda_media,
        "payoff": ganho_medio / abs(perda_media) if ganho_medio is not None and perda_media else None,
        "fator_lucro": soma_ganhos / abs(soma_perdas) if soma_perdas else None,
        "expectativa_r": mean(em_r) if em_r else None,
        "retorno": retorno,
        "drawdown_maximo": drawdown,
        "duracao_media": mean(t["duracao_pregoes"] for t in fechados) if fechados else None,
        "tempo_exposto": _tempo_exposto(trades, datas),
        "trades_com_aviso": sum(1 for t in fechados if t["avisos"]),
        "retorno_bruto": _retorno_bruto(fechados),
    }


def _retorno_bruto(fechados: list[dict]) -> float:
    capital = 100.0
    for t in fechados:
        capital *= 1 + t["bruto_pct"] / 100
    return capital - 100


def _tempo_exposto(trades: list[dict], datas: list[str]) -> float | None:
    if not datas:
        return None
    exposto = [False] * len(datas)
    for t in trades:
        ini = bisect_left(datas, t["entrada_data"])
        fim = bisect_right(datas, t["saida_data"]) if t["saida_data"] else len(datas)
        for i in range(ini, fim):
            exposto[i] = True
    return sum(exposto) / len(datas) * 100


def taxa_movel(trades: list[dict], janela: int = 20) -> list[dict]:
    """Taxa de acerto móvel dos últimos `janela` trades; empates não entram na conta."""
    decididos = [t for t in _encerrados(trades) if t["liquido_pct"] != 0]
    pontos = []
    for i in range(janela - 1, len(decididos)):
        grupo = decididos[i - janela + 1 : i + 1]
        pontos.append(
            {
                "data": grupo[-1]["saida_data"],
                "taxa": sum(1 for t in grupo if t["liquido_pct"] > 0) / janela * 100,
            }
        )
    return pontos


def mapa_mensal(trades: list[dict]) -> list[dict]:
    fatores: dict[tuple[int, int], float] = {}
    for t in _encerrados(trades):
        chave = (int(t["saida_data"][:4]), int(t["saida_data"][5:7]))
        fatores[chave] = fatores.get(chave, 1.0) * (1 + t["liquido_pct"] / 100)
    return [
        {"ano": ano, "mes": mes, "retorno": (fator - 1) * 100}
        for (ano, mes), fator in sorted(fatores.items())
    ]


def resultado_anual(trades: list[dict]) -> list[dict]:
    grupos: dict[int, list[dict]] = {}
    for t in _encerrados(trades):
        grupos.setdefault(int(t["saida_data"][:4]), []).append(t)
    linhas = []
    for ano, grupo in sorted(grupos.items()):
        acertos = sum(1 for t in grupo if t["liquido_pct"] > 0)
        erros = sum(1 for t in grupo if t["liquido_pct"] < 0)
        capital = 1.0
        for t in grupo:
            capital *= 1 + t["liquido_pct"] / 100
        linhas.append(
            {
                "ano": ano,
                "trades": len(grupo),
                "taxa_acerto": acertos / (acertos + erros) * 100 if acertos + erros else None,
                "retorno": (capital - 1) * 100,
            }
        )
    return linhas


def distribuicao_r(trades: list[dict], largura: float = 0.5) -> list[dict]:
    """Histograma do resultado em R. Cada faixa inclui o limite inferior e exclui o superior."""
    fechados = [t for t in _encerrados(trades) if t["liquido_r"] is not None]
    if not fechados:
        return []
    contagem: dict[int, int] = {}
    for t in fechados:
        indice = int(t["liquido_r"] // largura)
        contagem[indice] = contagem.get(indice, 0) + 1
    return [
        {"de": i * largura, "ate": (i + 1) * largura, "trades": contagem.get(i, 0)}
        for i in range(min(contagem), max(contagem) + 1)
    ]


def calcular_painel(trades: list[dict], datas: list[str], janela_movel: int = 20) -> dict:
    return {
        "indicadores": indicadores_principais(trades, datas),
        "curva": curva_capital(trades, datas),
        "taxa_movel": taxa_movel(trades, janela_movel),
        "mapa_mensal": mapa_mensal(trades),
        "anual": resultado_anual(trades),
        "distribuicao": distribuicao_r(trades),
        "sequencia": [
            {"numero": t["numero"], "data": t["saida_data"], "resultado": t["liquido_pct"]}
            for t in _encerrados(trades)
        ],
    }
