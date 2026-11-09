"""Indicadores calculados só com dados passados. Posições sem dados suficientes ficam NaN."""
from __future__ import annotations

from datetime import date

import numpy as np


def _vazio(valores: np.ndarray) -> np.ndarray:
    return np.full(len(valores), np.nan, dtype=float)


def mme(valores: np.ndarray, periodo: int) -> np.ndarray:
    """Média móvel exponencial iniciada pela média simples dos `periodo` primeiros valores.

    As posições anteriores à semente ficam NaN: nenhum sinal pode nascer delas.
    """
    resultado = _vazio(valores)
    if len(valores) < periodo:
        return resultado
    fator = 2.0 / (periodo + 1)
    atual = float(np.mean(valores[:periodo]))
    resultado[periodo - 1] = atual
    for i in range(periodo, len(valores)):
        atual = fator * float(valores[i]) + (1.0 - fator) * atual
        resultado[i] = atual
    return resultado


def mma(valores: np.ndarray, periodo: int) -> np.ndarray:
    """Média móvel aritmética."""
    resultado = _vazio(valores)
    if len(valores) < periodo:
        return resultado
    acumulado = np.cumsum(np.insert(np.asarray(valores, dtype=float), 0, 0.0))
    resultado[periodo - 1 :] = (acumulado[periodo:] - acumulado[:-periodo]) / periodo
    return resultado


def _wilder(valores: np.ndarray, periodo: int, inicio: int = 0) -> np.ndarray:
    """Suavização de Wilder, com semente na média simples dos `periodo` valores a partir de `inicio`."""
    resultado = _vazio(valores)
    if len(valores) < inicio + periodo:
        return resultado
    atual = float(np.mean(valores[inicio : inicio + periodo]))
    resultado[inicio + periodo - 1] = atual
    for i in range(inicio + periodo, len(valores)):
        atual = (atual * (periodo - 1) + float(valores[i])) / periodo
        resultado[i] = atual
    return resultado


def ifr(fechamento: np.ndarray, periodo: int) -> np.ndarray:
    """IFR de Wilder. Sem perdas no período vale 100; sem ganhos nem perdas, 50."""
    if len(fechamento) < 2:
        return _vazio(fechamento)
    variacao = np.diff(fechamento, prepend=fechamento[0])
    ganho = _wilder(np.clip(variacao, 0, None), periodo, inicio=1)
    perda = _wilder(np.clip(-variacao, 0, None), periodo, inicio=1)
    resultado = _vazio(fechamento)
    for i in range(len(fechamento)):
        if np.isnan(ganho[i]):
            continue
        if perda[i] == 0:
            resultado[i] = 100.0 if ganho[i] > 0 else 50.0
        else:
            resultado[i] = 100.0 - 100.0 / (1.0 + ganho[i] / perda[i])
    return resultado


def _true_range(maxima: np.ndarray, minima: np.ndarray, fechamento: np.ndarray) -> np.ndarray:
    anterior = np.r_[np.nan, fechamento[:-1]]
    return np.fmax(np.fmax(maxima - minima, np.abs(maxima - anterior)), np.abs(minima - anterior))


def atr(maxima: np.ndarray, minima: np.ndarray, fechamento: np.ndarray, periodo: int) -> np.ndarray:
    return _wilder(_true_range(maxima, minima, fechamento), periodo)


def adx(
    maxima: np.ndarray, minima: np.ndarray, fechamento: np.ndarray, periodo: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ADX, DI+ e DI- de Wilder. O ADX é a média de Wilder do DX, por isso nasce depois dos DIs."""
    n = len(fechamento)
    vazio = _vazio(fechamento)
    if n < periodo + 1:
        return vazio, vazio.copy(), vazio.copy()
    sobe = np.r_[0.0, maxima[1:] - maxima[:-1]]
    desce = np.r_[0.0, minima[:-1] - minima[1:]]
    dm_mais = np.where((sobe > desce) & (sobe > 0), sobe, 0.0)
    dm_menos = np.where((desce > sobe) & (desce > 0), desce, 0.0)
    tr = _wilder(_true_range(maxima, minima, fechamento), periodo, inicio=1)
    suave_mais = _wilder(dm_mais, periodo, inicio=1)
    suave_menos = _wilder(dm_menos, periodo, inicio=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        di_mais = np.where(tr > 0, 100.0 * suave_mais / tr, 0.0)
        di_menos = np.where(tr > 0, 100.0 * suave_menos / tr, 0.0)
        soma = di_mais + di_menos
        dx = np.where(soma > 0, 100.0 * np.abs(di_mais - di_menos) / soma, 0.0)
    di_mais[: periodo] = np.nan
    di_menos[: periodo] = np.nan
    return _wilder(dx, periodo, inicio=periodo), di_mais, di_menos


def bollinger(fechamento: np.ndarray, periodo: int, desvios: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Meio, banda superior e inferior, com desvio padrão populacional."""
    meio = mma(fechamento, periodo)
    superior = _vazio(fechamento)
    inferior = _vazio(fechamento)
    if len(fechamento) >= periodo:
        janelas = np.lib.stride_tricks.sliding_window_view(np.asarray(fechamento, dtype=float), periodo)
        desvio = janelas.std(axis=1, ddof=0)
        superior[periodo - 1 :] = meio[periodo - 1 :] + desvios * desvio
        inferior[periodo - 1 :] = meio[periodo - 1 :] - desvios * desvio
    return meio, superior, inferior


def estocastico(
    maxima: np.ndarray, minima: np.ndarray, fechamento: np.ndarray, periodo: int, suavizacao: int, sinal: int
) -> tuple[np.ndarray, np.ndarray]:
    """Estocástico lento, como no MetaTrader: devolve %K e %D, a média aritmética de %K.

    Sem amplitude nenhuma na janela, %K fica em 50: um NaN aqui contaminaria a média de %D dali em diante.
    """
    n = len(fechamento)
    k = np.full(n, np.nan, dtype=float)
    d = np.full(n, np.nan, dtype=float)
    primeiro = periodo + suavizacao - 2
    if n <= primeiro:
        return k, d
    menor = np.lib.stride_tricks.sliding_window_view(minima, periodo).min(axis=1)
    maior = np.lib.stride_tricks.sliding_window_view(maxima, periodo).max(axis=1)
    fech = np.asarray(fechamento[periodo - 1 :], dtype=float)
    numerador = mma(fech - menor, suavizacao)[suavizacao - 1 :]
    denominador = mma(maior - menor, suavizacao)[suavizacao - 1 :]
    k[primeiro:] = np.divide(
        numerador * 100.0, denominador, out=np.full(len(numerador), 50.0), where=denominador > 0
    )
    d[primeiro:] = mma(k[primeiro:], sinal)
    return k, d


def _mme_sobre_valida(valores: np.ndarray, periodo: int) -> np.ndarray:
    """MME de uma série que já começa com NaN, como a média de outra média."""
    resultado = _vazio(valores)
    validos = np.flatnonzero(~np.isnan(valores))
    if len(validos):
        resultado[validos[0] :] = mme(valores[validos[0] :], periodo)
    return resultado


def trix(fechamento: np.ndarray, periodo: int, sinal: int) -> tuple[np.ndarray, np.ndarray]:
    """TRIX: variação percentual da MME tripla. Devolve a linha e a média aritmética dela."""
    tripla = mme(fechamento, periodo)
    for _ in range(2):
        tripla = _mme_sobre_valida(tripla, periodo)
    linha = _vazio(fechamento)
    linha[1:] = (tripla[1:] / tripla[:-1] - 1.0) * 100.0
    media = _vazio(fechamento)
    validos = np.flatnonzero(~np.isnan(linha))
    if len(validos):
        media[validos[0] :] = mma(linha[validos[0] :], sinal)
    return linha, media


def mme_semanal_subindo(datas: list[str], fechamento: np.ndarray, periodo: int = 9) -> np.ndarray:
    """1 quando a MME semanal sobe, 0 quando não sobe, NaN antes de haver semanas suficientes.

    A semana em formação usa o fechamento de cada dia: não é preciso saber qual será seu último pregão.
    """
    resultado = _vazio(fechamento)
    fator = 2.0 / (periodo + 1)
    encerradas: list[float] = []
    media: float | None = None  # MME das semanas já encerradas
    semana = None
    ultimo = 0.0
    for i, texto in enumerate(datas):
        atual = date.fromisoformat(texto).isocalendar()[:2]
        if semana is not None and atual != semana:
            if media is not None:
                media = fator * ultimo + (1.0 - fator) * media
            else:
                encerradas.append(ultimo)
                if len(encerradas) == periodo:
                    media = float(np.mean(encerradas))
        semana = atual
        ultimo = float(fechamento[i])
        if media is not None:
            resultado[i] = 1.0 if fator * ultimo + (1.0 - fator) * media > media else 0.0
    return resultado
