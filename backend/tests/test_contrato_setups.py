"""Suíte comum: todo setup registrado passa por contrato, reprodutibilidade e ausência de olhar o futuro."""
from dataclasses import asdict

import numpy as np
import pytest

from app.motor.motor import executar
from app.motor.tipos import SerieCandles
from app.setups.registro import SETUPS
from tests.auxiliares import datas_uteis


def passeio(n=800, semente=7) -> SerieCandles:
    gerador = np.random.default_rng(semente)
    fechamento = 20 * np.exp(np.cumsum(gerador.normal(0, 0.018, n)))
    abertura = np.r_[fechamento[0], fechamento[:-1]] * (1 + gerador.normal(0, 0.004, n))
    maxima = np.maximum(abertura, fechamento) * (1 + np.abs(gerador.normal(0, 0.008, n)))
    minima = np.minimum(abertura, fechamento) * (1 - np.abs(gerador.normal(0, 0.008, n)))
    return SerieCandles(
        datas_uteis(n), abertura, maxima, minima, fechamento, np.full(n, 1e6), np.zeros(n, dtype=bool)
    )


@pytest.fixture(params=list(SETUPS.values()), ids=list(SETUPS))
def setup(request):
    return request.param


def test_contrato(setup):
    assert setup.id and setup.versao and setup.nome
    assert setup.direcao == ["long"]
    params = setup.Parametros()
    assert setup.aquecimento(params) > 0
    assert setup.Parametros.model_json_schema()["properties"]
    visiveis = {k for k in setup.indicadores(passeio(50), params) if not k.startswith("_")}
    assert set(setup.indicadores_declarados(params)) == visiveis
    assert setup.indicadores_em_painel(params) <= visiveis
    for nome, campo in setup.Parametros.model_json_schema()["properties"].items():
        assert campo.get("title"), f"{nome} precisa de título para o formulário"


def test_indicador_nao_muda_com_candles_futuros(setup):
    params = setup.Parametros()
    completa = passeio(900)
    final = setup.indicadores(completa, params)
    for corte in (150, 400, 777):
        parcial = setup.indicadores(completa.fatia(0, corte), params)
        for nome, valores in parcial.items():
            np.testing.assert_allclose(valores, final[nome][:corte], err_msg=nome)


# Padrões de candle exigem gaps e formatos que um passeio aleatório quase não produz: os limites ficam frouxos.
FROUXOS = {
    "separacao_alta": {"fator_forte": 0.3, "extremo_pct": 80, "tolerancia_abertura_pct": 100, "exigir_tendencia": False},
    "mat_hold": {"exigir_tendencia": False},
    "penetrante": {"fator_forte": 0.3, "extremo_pct": 80, "exigir_queda": False},
    "deliberante": {"fator_forte": 0.5, "extremo_pct": 60, "exigir_tendencia": False},
}

# Mat Hold de 5 candles, em múltiplos do preço: forte de alta, baixa acima dele, correção e rompimento forte.
MAT_HOLD = [(1.00, 1.065, 0.995, 1.06), (1.08, 1.085, 1.065, 1.07), (1.068, 1.07, 1.05, 1.055),
            (1.055, 1.06, 1.04, 1.045), (1.045, 1.12, 1.044, 1.115)]
DEPOIS = [(1.115, 1.15, 1.11, 1.14)]  # rompe a máxima e aciona a compra


def com_trades(setup):
    """Os quatro indicadores do Didi quase nunca se alinham em 800 candles aleatórios."""
    if setup.id == "didi":
        return setup.Parametros(confirma_adx=False, confirma_estocastico=False, confirma_trix=False)
    return setup.Parametros(**FROUXOS.get(setup.id, {}))


def serie_de(setup) -> SerieCandles:
    """Passeio aleatório; para o Mat Hold, com o padrão plantado a cada 60 candles."""
    s = passeio()
    if setup.id != "mat_hold":
        return s
    for inicio in range(100, len(s.datas) - 10, 60):
        base = s.fechamento[inicio - 1]
        for k, (o, h, l, c) in enumerate(MAT_HOLD + DEPOIS):
            s.abertura[inicio + k], s.maxima[inicio + k] = o * base, h * base
            s.minima[inicio + k], s.fechamento[inicio + k] = l * base, c * base
    return s


def test_reprodutibilidade(setup):
    params = com_trades(setup)
    a = executar(serie_de(setup), setup, params)
    b = executar(serie_de(setup), setup, params)
    assert a.trades, "a série sintética deveria gerar trades"
    assert [asdict(t) for t in a.trades] == [asdict(t) for t in b.trades]


def test_sem_olhar_o_futuro(setup):
    """Incluir candles novos nunca altera trades já encerrados."""
    params = com_trades(setup)
    completa = serie_de(setup)
    final = executar(completa, setup, params)
    for corte in range(100, len(completa), 97):
        parcial = executar(completa.fatia(0, corte), setup, params)
        encerrados = [asdict(t) for t in parcial.trades if not t.aberto]
        assert encerrados == [asdict(t) for t in final.trades[: len(encerrados)]]


def test_contexto_nao_enxerga_candles_futuros(setup):
    params = setup.Parametros()
    candles = passeio(setup.aquecimento(params) + 50)
    vistos = []
    original = setup.ao_fechar_candle

    class Espiao(type(setup)):
        def ao_fechar_candle(self, ctx):
            vistos.append((len(ctx.fechamento), ctx.datas[-1]))
            assert all(len(v) == len(ctx.fechamento) for v in ctx.indicadores.values())
            return original(ctx)

    executar(candles, Espiao(), params)
    assert vistos
    for tamanho, data in vistos:
        assert candles.datas[tamanho - 1] == data
