"""Todos os casos numéricos da especificação do 9.1 no PRD."""
import numpy as np
import pytest

from app.motor.custos import Custos, resultado_trade
from app.motor.indicadores import mme
from app.motor.motor import AVISO_ALVO_STOP, AVISO_ENTRADA_STOP, executar
from app.setups.larry_williams_9_1 import LarryWilliams91, ParametrosLW91
from tests.auxiliares import D1, D2, D3, D4, D5, D6, D7, aquecimento_prd, serie

SETUP = LarryWilliams91()
PADRAO = ParametrosLW91()


def rodar(*candles, params=PADRAO, **kw):
    return executar(serie(aquecimento_prd() + list(candles)), SETUP, params, **kw)


def test_mme_inicia_pela_media_simples():
    valores = mme(np.array([1.0, 2.0, 3.0, 4.0]), 3)
    assert np.isnan(valores[:2]).all()
    assert valores[2] == pytest.approx(2.0)
    assert valores[3] == pytest.approx(0.5 * 4 + 0.5 * 2)


def test_mme_do_exemplo_do_prd():
    r = rodar(D1, D2, D3, D4, D5, D6, D7)
    esperado = [20.10, 20.24, 20.59, 21.17, 21.84, 21.81, 21.71]
    assert r.indicadores["mme"][-7:] == pytest.approx(esperado, abs=0.005)


def test_trade_vencedor_completo():
    r = rodar(D1, D2, D3, D4, D5, D6, D7)
    assert len(r.trades) == 1
    t = r.trades[0]
    assert t.entrada_preco == pytest.approx(20.61)
    assert t.stop == pytest.approx(19.89)
    assert t.risco == pytest.approx(0.72)
    assert t.saida_preco == pytest.approx(21.59)
    assert t.motivo_saida == "saida_armada"
    assert not t.aberto
    assert t.duracao_pregoes == 5
    res = resultado_trade(t, Custos())
    assert res["bruto_pct"] == pytest.approx(4.75, abs=0.01)
    assert res["bruto_r"] == pytest.approx(1.36, abs=0.01)
    assert res["liquido_pct"] == pytest.approx(res["bruto_pct"])
    assert [e.tipo for e in t.eventos] == ["sinal", "entrada", "saida_armada", "saida"]


def test_gatilho_atualizado():
    d2 = (20.20, 20.40, 20.10, 20.35)  # sem entrada, MME segue subindo
    r = rodar(D1, d2)
    assert r.estado == "armado"
    assert r.ordens_ativas[0].preco == pytest.approx(20.41)
    assert r.ordens_ativas[0].stop == pytest.approx(20.09)  # o stop acompanha o candle que passou a valer
    r2 = rodar(D1, d2, (20.30, 20.50, 20.20, 20.45))
    assert r2.trades[0].entrada_preco == pytest.approx(20.41)
    assert r2.trades[0].stop == pytest.approx(20.09)
    r3 = rodar(D1, d2, (20.30, 20.50, 20.20, 20.45), params=ParametrosLW91(stop_no_candle_vigente=False))
    assert r3.trades[0].stop == pytest.approx(19.89)


def test_gatilho_nao_atualizado_vale_so_um_candle():
    params = ParametrosLW91(atualizar_gatilho=False)
    d2 = (20.20, 20.40, 20.10, 20.35)
    r = rodar(D1, d2, params=params)
    assert r.estado == "sem_sinal"
    assert r.sinais[0].situacao == "cancelado"


def test_sinal_cancelado():
    d2 = (20.20, 20.40, 19.95, 19.96)  # 0,2×19,96 + 0,8×20,10 < 20,10: MME vira para baixo
    r = rodar(D1, d2)
    assert r.trades == []
    assert r.estado == "sem_sinal"
    assert r.sinais[0].situacao == "cancelado"
    assert "virou para baixo" in r.sinais[0].motivo


def test_gap_na_entrada():
    d2 = (20.90, 21.20, 20.80, 21.10)
    t = rodar(D1, d2).trades[0]
    assert t.entrada_preco == pytest.approx(20.90)
    assert t.risco == pytest.approx(1.01)


def test_gap_no_stop():
    d3 = (19.50, 19.70, 19.20, 19.40)
    t = rodar(D1, D2, d3).trades[0]
    assert t.saida_preco == pytest.approx(19.50)
    assert t.motivo_saida == "stop_inicial"
    res = resultado_trade(t, Custos())
    assert res["bruto_pct"] == pytest.approx(-5.39, abs=0.01)
    assert res["bruto_r"] == pytest.approx(-1.54, abs=0.01)


def test_stop_no_candle_da_entrada():
    d2 = (20.30, 20.70, 19.70, 20.20)
    r = rodar(D1, d2)
    t = r.trades[0]
    assert t.entrada_preco == pytest.approx(20.61)
    assert t.saida_preco == pytest.approx(19.89)
    assert t.avisos == [AVISO_ENTRADA_STOP]
    res = resultado_trade(t, Custos())
    assert res["bruto_pct"] == pytest.approx(-3.49, abs=0.01)
    assert res["bruto_r"] == pytest.approx(-1.0, abs=0.001)


def test_saida_cancelada():
    d7 = (21.80, 23.20, 21.70, 23.00)  # não perde 21,59 e a MME volta a subir
    r = rodar(D1, D2, D3, D4, D5, D6, d7)
    assert r.estado == "posicionado"
    assert r.trades[0].aberto
    assert "saida_cancelada" in [e.tipo for e in r.trades[0].eventos]
    d8 = (22.00, 22.10, 21.00, 21.90)  # sem saída armada, 21,00 não encerra
    r2 = rodar(D1, D2, D3, D4, D5, D6, d7, d8)
    assert r2.trades[0].aberto


def test_saida_nao_acionada_acompanha_a_minima():
    d7 = (21.70, 21.75, 21.65, 21.66)  # não alcança 21,59 e a MME segue caindo
    r = rodar(D1, D2, D3, D4, D5, D6, d7)
    assert r.estado == "saida_armada"
    assert r.ordens_ativas[0].preco == pytest.approx(21.64)


def test_stop_vale_junto_da_saida_armada_e_ganha_a_ordem_mais_alta():
    d3 = (20.85, 20.90, 20.10, 20.15)  # MME desce: saída armada em 20,09, acima do stop de 19,89
    r = rodar(D1, D2, d3)
    assert r.estado == "saida_armada"
    assert r.ordens_ativas[0].preco == pytest.approx(20.09)
    d4 = (20.05, 20.10, 19.00, 19.20)  # abre abaixo de 20,09: sai na abertura pela ordem mais alta
    t = rodar(D1, D2, d3, d4).trades[0]
    assert t.saida_preco == pytest.approx(20.05)
    assert t.motivo_saida == "saida_armada"


def test_sinais_ignorados_com_posicao_e_nova_busca_depois_da_saida():
    r = rodar(D1, D2, D3, D4, D5, D6, D7)
    assert len(r.sinais) == 1
    assert r.estado == "sem_sinal"


def test_alvo_fixo():
    params = ParametrosLW91(alvo_r=2)
    d3 = (20.90, 22.50, 20.85, 22.00)  # alvo = 20,61 + 2×0,72 = 22,05
    t = rodar(D1, D2, d3, params=params).trades[0]
    assert t.saida_preco == pytest.approx(22.05)
    assert t.motivo_saida == "alvo"


def test_alvo_com_gap_executa_na_abertura():
    params = ParametrosLW91(alvo_r=2)
    d3 = (22.40, 22.50, 22.30, 22.40)
    t = rodar(D1, D2, d3, params=params).trades[0]
    assert t.saida_preco == pytest.approx(22.40)


def test_alvo_e_stop_no_mesmo_candle_considera_o_stop():
    params = ParametrosLW91(alvo_r=2)
    d3 = (20.90, 22.50, 19.00, 20.00)
    t = rodar(D1, D2, d3, params=params).trades[0]
    assert t.motivo_saida == "stop_inicial"
    assert t.saida_preco == pytest.approx(19.89)
    assert t.avisos == [AVISO_ALVO_STOP]


def test_exigir_fechamento_acima_da_mme():
    # Fechamento em 20,50 acima da MME de 20,10: o sinal nasce com o parâmetro ligado.
    assert rodar(D1, params=ParametrosLW91(exigir_fechamento_acima=True)).estado == "armado"


def test_gatilho_abaixo_do_stop_nao_abre_trade_invertido():
    d2 = (19.50, 19.60, 19.30, 20.40)  # MME sobe, gatilho vira 19,61, abaixo do stop 19,89
    d3 = (19.70, 19.95, 19.65, 19.80)
    r = rodar(D1, d2, d3, params=ParametrosLW91(stop_no_candle_vigente=False))
    assert r.trades == []
    assert r.sinais[0].situacao == "invalidado"
    # Com o stop acompanhando o gatilho, ele desce junto e o trade tem risco definido.
    t = rodar(D1, d2, d3).trades[0]
    assert t.stop == pytest.approx(19.29) and t.entrada_preco > t.stop


def test_trade_aberto_nao_entra_como_encerrado():
    r = rodar(D1, D2, D3)
    t = r.trades[0]
    assert t.aberto and t.saida_data is None
    assert t.preco_referencia == pytest.approx(22.00)
    assert r.estado == "posicionado"


def test_aquecimento_primeiro_sinal_so_no_27o_candle():
    # A especificação pede 3 vezes o período: com 26 candles ou menos, nenhum sinal.
    r = executar(serie(aquecimento_prd()[:25] + [D1]), SETUP, PADRAO)
    assert r.sinais == []
    assert r.avisos and "insuficientes" in r.avisos[0]


def test_inicio_limita_sinais_sem_cortar_aquecimento():
    candles = serie(aquecimento_prd() + [D1, D2, D3, D4, D5, D6, D7])
    data_d3 = candles.datas[28]
    r = executar(candles, SETUP, PADRAO, inicio=data_d3)
    assert r.trades == []  # o sinal de D1 ficou fora do período
    assert not np.isnan(r.indicadores["mme"][28])


def test_fim_deixa_trade_aberto():
    candles = serie(aquecimento_prd() + [D1, D2, D3, D4, D5, D6, D7])
    r = executar(candles, SETUP, PADRAO, fim=candles.datas[29])
    assert r.trades[0].aberto


def test_lacuna_recomeca_indicadores():
    linhas = aquecimento_prd() + [D1] + aquecimento_prd()
    r = executar(serie(linhas, quebras=(27,)), SETUP, PADRAO)
    assert np.isnan(r.indicadores["mme"][27])
    assert r.sinais[0].situacao == "cancelado"
    assert "lacuna" in r.sinais[0].motivo


def test_custos_reduzem_o_liquido():
    t = rodar(D1, D2, D3, D4, D5, D6, D7).trades[0]
    custos = Custos(corretagem_por_ordem=5, emolumentos_pct=0.03, slippage_pct=0.05, capital_por_trade=10000)
    res = resultado_trade(t, custos)
    assert res["liquido_pct"] < res["bruto_pct"]
    assert res["liquido_r"] < res["bruto_r"]
