"""Monta séries sintéticas para os casos de referência do PRD."""
from datetime import date, timedelta

import numpy as np

from app.motor.tipos import SerieCandles


def datas_uteis(n: int, inicio: str = "2024-01-01") -> list[str]:
    atual = date.fromisoformat(inicio)
    saida = []
    while len(saida) < n:
        if atual.weekday() < 5:
            saida.append(atual.isoformat())
        atual += timedelta(days=1)
    return saida


def serie(linhas: list[tuple[float, float, float, float]], quebras: tuple[int, ...] = ()) -> SerieCandles:
    n = len(linhas)
    a = np.array(linhas, dtype=float).reshape(n, 4)
    quebra = np.zeros(n, dtype=bool)
    for i in quebras:
        quebra[i] = True
    return SerieCandles(
        datas_uteis(n), a[:, 0].copy(), a[:, 1].copy(), a[:, 2].copy(), a[:, 3].copy(), np.full(n, 1000.0), quebra
    )


def aquecimento_prd() -> list[tuple[float, float, float, float]]:
    """26 candles que deixam a MME 9 em 20,10 e 20,00 nos dois pregões anteriores ao D1 do PRD.

    O D1 é o 27º candle, o primeiro depois do aquecimento de 3 vezes o período. Com o preço parado, a MME não muda.
    """
    plano = [(20.10, 20.20, 20.00, 20.10)] * 25
    return plano + [(20.10, 20.20, 19.50, 19.60)]


D1 = (20.00, 20.60, 19.90, 20.50)
D2 = (20.55, 20.90, 20.40, 20.80)
D3 = (20.90, 22.10, 20.85, 22.00)
D4 = (22.10, 23.60, 22.00, 23.50)
D5 = (23.50, 24.60, 23.40, 24.50)
D6 = (23.00, 23.10, 21.60, 21.70)
D7 = (21.70, 21.80, 21.20, 21.30)
