"""Calendário de pregões da B3, para não acusar feriado como candle faltando.

Calculado por regra. Fechamentos extraordinários não entram, e no máximo geram um alerta a mais.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

# O Brasil não tem horário de verão desde 2019. Usar deslocamento fixo evita depender do pacote tzdata no Windows.
FUSO_B3 = timezone(timedelta(hours=-3))
HORARIO_FECHAMENTO = (18, 30)  # depois do call de fechamento o candle do dia já é definitivo

# Início do histórico do app. Nada anterior é baixado, guardado, simulado ou aceito como data de análise:
# os dados mais antigos do Yahoo têm erros grosseiros (PETR4 em 05/08/2003 abriu a 67,50 e fechou a 6,85).
INICIO_HISTORICO = "2010-01-01"
INICIO_HISTORICO_BR = "01/01/2010"


def _pascoa(ano: int) -> date:
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    el = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * el) // 451
    mes, dia = divmod(h + el - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


@lru_cache(maxsize=128)
def feriados(ano: int) -> frozenset[date]:
    pascoa = _pascoa(ano)
    dias = {
        date(ano, 1, 1),
        pascoa - timedelta(days=48),  # Carnaval, segunda
        pascoa - timedelta(days=47),  # Carnaval, terça
        pascoa - timedelta(days=2),  # Sexta-feira Santa
        pascoa + timedelta(days=60),  # Corpus Christi
        date(ano, 4, 21),
        date(ano, 5, 1),
        date(ano, 9, 7),
        date(ano, 10, 12),
        date(ano, 11, 2),
        date(ano, 11, 15),
        date(ano, 12, 24),
        date(ano, 12, 25),
        date(ano, 12, 31),
    }
    if ano <= 2021:  # até 2021 a B3 seguia os feriados da cidade de São Paulo
        dias |= {date(ano, 1, 25), date(ano, 7, 9), date(ano, 11, 20)}
    if ano >= 2024:  # Consciência Negra virou feriado nacional
        dias.add(date(ano, 11, 20))
    return frozenset(dias)


def eh_pregao(dia: date) -> bool:
    return dia.weekday() < 5 and dia not in feriados(dia.year)


def pregoes_faltantes(datas: list[str]) -> list[str]:
    """Dias de pregão, entre o primeiro e o último candle, sem candle na série."""
    if len(datas) < 2:
        return []
    presentes = set(datas)
    dia = date.fromisoformat(datas[0])
    fim = date.fromisoformat(datas[-1])
    faltantes = []
    while dia <= fim:
        if eh_pregao(dia) and dia.isoformat() not in presentes:
            faltantes.append(dia.isoformat())
        dia += timedelta(days=1)
    return faltantes


def agora_b3() -> datetime:
    return datetime.now(FUSO_B3)


def candle_em_formacao(data: str, agora: datetime | None = None) -> bool:
    """O candle de hoje só conta depois do fechamento: as fontes entregam o pregão ainda em andamento."""
    agora = agora or agora_b3()
    return data >= agora.date().isoformat() and (agora.hour, agora.minute) < HORARIO_FECHAMENTO


def menos_tres_meses(dia: date) -> date:
    mes = dia.month - 3
    ano = dia.year
    if mes <= 0:
        mes += 12
        ano -= 1
    while True:
        try:
            return dia.replace(year=ano, month=mes)
        except ValueError:  # ex.: 31 de maio menos 3 meses não existe em fevereiro
            dia = dia - timedelta(days=1)
