"""Casos numéricos de SETUPS_SWING_TRADE.md: sinal, gap, arrasto, invalidação, intrabar e aquecimento."""
import numpy as np
import pytest

from app.motor.custos import Custos, resultado_trade
from app.motor.indicadores import adx, atr, bollinger, estocastico, ifr, mma, mme, mme_semanal_subindo, trix
from app.motor.metricas import distribuicao_r, indicadores_principais
from app.motor.motor import AVISO_ENTRADA_STOP, executar
from app.motor.tipos import SerieCandles
from app.setups.candle import Setup123, SetupElefante, SetupInside, SetupPFR, SetupPontoContinuo
from app.setups.familia_larry import LarryWilliams92, LarryWilliams93, LarryWilliams94
from app.setups.internacionais import SetupDonchian, SetupHolyGrail, SetupRoss
from app.setups.larry_williams_9_1 import LarryWilliams91
from app.setups.padroes_candle import SetupDeliberante, SetupMatHold, SetupPenetrante, SetupSeparacaoAlta
from app.setups.por_indicador import SetupBollinger, SetupCruzamento, SetupDidi, SetupIFR2, SetupRecuoIFR
from tests.auxiliares import datas_uteis, serie


def rodar(setup, linhas, **params):
    return executar(serie(linhas), setup, setup.Parametros(**params))


def plano(n, candle=(20.0, 20.2, 19.8, 20.0)):
    return [candle] * n


def subida(n, inicio=20.0, passo=0.2):
    return [(inicio + passo * i, inicio + passo * i + 0.1, inicio + passo * i - 0.1, inicio + passo * i) for i in range(n)]


def queda(n, inicio=20.0, passo=0.05):
    return [(inicio - passo * i, inicio - passo * i + 0.1, inicio - passo * i - 0.1, inicio - passo * i) for i in range(n)]


# --- indicadores


def test_mma():
    valores = mma(np.array([1.0, 2.0, 3.0, 4.0]), 2)
    assert np.isnan(valores[0])
    assert valores[1:] == pytest.approx([1.5, 2.5, 3.5])


def test_ifr_de_wilder():
    valores = ifr(np.array([10.0, 11.0, 12.0, 11.0]), 2)
    assert np.isnan(valores[:2]).all()
    assert valores[2] == pytest.approx(100.0)  # sem perdas
    assert valores[3] == pytest.approx(50.0)  # (1 + 0) / 2 de ganho e (0 + 1) / 2 de perda


def test_atr_de_wilder():
    h, l, c = np.array([11.0, 12.0, 13.0]), np.array([9.0, 10.0, 11.0]), np.array([10.0, 11.0, 12.0])
    valores = atr(h, l, c, 2)
    assert np.isnan(valores[0])
    assert valores[1:] == pytest.approx([2.0, 2.0])


def test_bollinger_usa_desvio_populacional():
    meio, sup, inf = bollinger(np.array([1.0, 2.0, 3.0]), 3, 1.0)
    assert meio[2] == pytest.approx(2.0)
    assert sup[2] == pytest.approx(2.0 + np.sqrt(2 / 3))
    assert inf[2] == pytest.approx(2.0 - np.sqrt(2 / 3))


def test_adx_em_tendencia_pura_de_alta():
    h = np.arange(11.0, 21.0)
    l = h - 2
    c = h - 1
    valor, mais, menos = adx(h, l, c, 3)
    assert np.isnan(valor[:5]).all()
    assert np.isnan(mais[:3]).all()
    assert valor[5] == pytest.approx(100.0)
    assert mais[3] == pytest.approx(50.0)  # movimento de 1 em uma faixa de 2
    assert menos[3] == pytest.approx(0.0)


def test_mme_semanal_nao_olha_o_futuro_e_segue_a_direcao():
    n = 200
    datas = datas_uteis(n)
    alta = 20 + 0.1 * np.arange(n, dtype=float)
    assert mme_semanal_subindo(datas, alta)[-1] == 1.0
    assert mme_semanal_subindo(datas, alta[::-1].copy())[-1] == 0.0
    assert np.isnan(mme_semanal_subindo(datas, alta)[:40]).all()  # ainda sem 9 semanas encerradas
    completo = mme_semanal_subindo(datas, alta)
    np.testing.assert_array_equal(mme_semanal_subindo(datas[:100], alta[:100]), completo[:100])


# --- PFR: serve também para as regras gerais de execução (seção 0.4 da especificação)

BASE_PFR = [(10.0, 11.0, 9.5, 10.5), (10.5, 11.0, 10.0, 10.4), (10.3, 10.9, 9.8, 10.6)]


def test_pfr_sinal_entrada_e_alvo_de_2r():
    r = rodar(SetupPFR(), BASE_PFR + [(10.7, 11.0, 10.6, 10.9), (11.0, 13.5, 10.9, 13.4)])
    t = r.trades[0]
    assert t.entrada_preco == pytest.approx(10.91)
    assert t.stop == pytest.approx(9.79)
    assert t.alvo == pytest.approx(10.91 + 2 * 1.12)
    assert t.saida_preco == pytest.approx(13.15)
    assert t.motivo_saida == "alvo"


def test_pfr_validade_de_um_candle():
    r = rodar(SetupPFR(), BASE_PFR + [(10.7, 10.8, 10.6, 10.7), (10.8, 11.5, 10.7, 11.4)])
    assert not r.trades
    assert r.sinais[0].situacao == "cancelado"


def test_gap_acima_executa_na_abertura():
    t = rodar(SetupPFR(), BASE_PFR + [(11.2, 11.5, 11.1, 11.4)]).trades[0]
    assert t.entrada_preco == pytest.approx(11.2)
    assert t.risco == pytest.approx(11.2 - 9.79)


def test_gap_acima_cancela_com_aceitar_gap_desligado():
    r = rodar(SetupPFR(), BASE_PFR + [(11.2, 11.5, 11.1, 11.4)], aceitar_gap=False)
    assert not r.trades
    assert r.sinais[0].situacao == "cancelado"
    assert "gap" in r.sinais[0].motivo


def test_entrada_e_stop_no_mesmo_candle_considera_stopado():
    t = rodar(SetupPFR(), BASE_PFR + [(10.7, 11.0, 9.5, 10.0)]).trades[0]
    assert t.saida_preco == pytest.approx(9.79)
    assert t.motivo_saida == "stop_inicial"
    assert t.avisos == [AVISO_ENTRADA_STOP]


def test_aquecimento_insuficiente_nao_gera_sinal():
    r = rodar(SetupPFR(), BASE_PFR[:2])
    assert not r.sinais
    assert "insuficientes" in r.avisos[0]


def test_pfr_estrito_e_menor_minima_de_n():
    assert not rodar(SetupPFR(), BASE_PFR, pfr_estrito=True).sinais  # 9,80 não está abaixo de 9,50
    assert not rodar(SetupPFR(), BASE_PFR, pfr_minima_n=3).sinais
    assert rodar(SetupPFR(), BASE_PFR, pfr_minima_n=2).sinais


def test_saida_por_stop_movel_so_sobe():
    r = rodar(
        SetupPFR(),
        BASE_PFR + [(10.7, 11.0, 10.6, 10.9), (10.9, 11.5, 10.8, 11.4), (11.3, 11.4, 10.7, 11.0)],
        saida="trailing_minima",
    )
    t = r.trades[0]
    assert t.alvo is None
    assert t.saida_preco == pytest.approx(10.79)
    assert t.motivo_saida == "trailing_minima"


# --- filtros globais (seção 0.6)


def test_filtro_de_volume_minimo():
    linhas = plano(60) + BASE_PFR
    assert not rodar(SetupPFR(), linhas, volume_minimo=2000).sinais
    assert rodar(SetupPFR(), linhas, volume_minimo=500).sinais


def test_filtro_mm200_e_aquecimento_sobem_junto():
    params = SetupPFR.Parametros(filtro_tendencia_mm200=True)
    assert SetupPFR().aquecimento(params) == 600
    assert not rodar(SetupPFR(), BASE_PFR, filtro_tendencia_mm200=True).sinais


def test_filtro_semanal_bloqueia_em_queda():
    linhas = queda(300, inicio=60.0, passo=0.1)
    ultimo = linhas[-1][3]
    sinal = [(ultimo, ultimo + 0.1, ultimo - 0.5, ultimo + 0.05)]
    assert rodar(SetupPFR(), linhas + sinal).sinais
    assert not [s for s in rodar(SetupPFR(), linhas + sinal, filtro_semanal=True).sinais if s.data]


# --- 123


BASE_123 = [(10.0, 11.0, 10.0, 10.5), (10.2, 10.6, 9.5, 10.0), (10.0, 10.8, 9.8, 10.5)]


def test_123_entrada_stop_e_alvo():
    t = rodar(Setup123(), BASE_123 + [(10.7, 11.0, 10.6, 10.9)]).trades[0]
    assert t.entrada_preco == pytest.approx(10.81)
    assert t.stop == pytest.approx(9.49)
    assert t.alvo == pytest.approx(10.81 + 2 * 1.32)


def test_123_arrasto_mantem_o_stop_no_fundo():
    r = rodar(Setup123(), BASE_123 + [(10.4, 10.7, 9.9, 10.2), (10.4, 10.9, 10.1, 10.8)])
    t = r.trades[0]
    assert t.entrada_preco == pytest.approx(10.71)
    assert t.stop == pytest.approx(9.49)
    assert "gatilho_atualizado" in [e.tipo for e in t.eventos]


def test_123_perder_o_fundo_invalida():
    r = rodar(Setup123(), BASE_123 + [(10.3, 10.7, 9.4, 9.6)])
    assert not r.trades
    assert r.sinais[0].situacao == "cancelado"
    assert "fundo" in r.sinais[0].motivo


def test_123_sem_arrasto_expira():
    r = rodar(Setup123(), BASE_123 + [(10.4, 10.7, 9.9, 10.2), (10.4, 10.9, 10.1, 10.8)], arrastar_entrada=False)
    assert not r.trades


def test_123_fechamento_acima_do_fundo():
    linhas = [(10.0, 11.0, 10.0, 10.5), (10.2, 10.6, 9.5, 10.4), (10.0, 10.8, 9.8, 10.3)]
    assert rodar(Setup123(), linhas).sinais
    assert not rodar(Setup123(), linhas, exigir_fechamento_fundo=True).sinais


# --- Inside Bar

BASE_INSIDE = [(10.0, 10.5, 9.8, 10.0), (10.0, 12.0, 9.0, 11.0), (10.5, 11.5, 9.5, 11.0)]


def test_inside_referencia_na_barra_inside():
    t = rodar(SetupInside(), BASE_INSIDE + [(11.0, 11.6, 10.0, 11.5)]).trades[0]
    assert t.entrada_preco == pytest.approx(11.51)
    assert t.stop == pytest.approx(9.49)


def test_inside_referencia_na_barra_mae():
    t = rodar(SetupInside(), BASE_INSIDE + [(11.0, 12.1, 10.0, 12.0)], referencia_inside="mae").trades[0]
    assert t.entrada_preco == pytest.approx(12.01)
    assert t.stop == pytest.approx(8.99)


def test_inside_vale_dois_candles():
    fora = (11.0, 11.4, 9.4, 11.0)  # não é inside: a mínima ficou abaixo
    assert rodar(SetupInside(), BASE_INSIDE + [fora, (11.0, 11.6, 9.3, 11.5)]).trades
    r = rodar(SetupInside(), BASE_INSIDE + [fora, (11.0, 11.45, 9.3, 11.0), (11.0, 11.6, 9.2, 11.5)])
    assert not r.trades


def test_inside_inclusivo():
    linhas = [(10.0, 10.5, 9.8, 10.0), (10.0, 12.0, 9.0, 11.0), (10.5, 12.0, 9.5, 11.0)]
    assert not rodar(SetupInside(), linhas).sinais
    assert rodar(SetupInside(), linhas, inclusivo=True).sinais


# --- Barra Elefante

ELEFANTE = (20.0, 21.0, 19.95, 20.95)


def test_elefante_rompimento():
    t = rodar(SetupElefante(), plano(61) + [ELEFANTE, (21.0, 21.2, 20.9, 21.1)]).trades[0]
    assert t.entrada_preco == pytest.approx(21.01)
    assert t.stop == pytest.approx(19.94)


def test_elefante_no_fechamento_entra_no_proprio_candle():
    r = rodar(SetupElefante(), plano(61) + [ELEFANTE], entrada_elefante="fechamento")
    t = r.trades[0]
    assert t.entrada_preco == pytest.approx(20.95)
    assert t.entrada_data == t.sinal_data
    assert t.aberto


def test_elefante_stop_no_meio_e_regras_de_corpo():
    t = rodar(SetupElefante(), plano(61) + [ELEFANTE, (21.0, 21.2, 20.9, 21.1)], stop_elefante="meio").trades[0]
    assert t.stop == pytest.approx(20.475)
    assert not rodar(SetupElefante(), plano(61) + [(20.0, 20.5, 19.95, 20.4)]).sinais  # candle pequeno
    assert not rodar(SetupElefante(), plano(61) + [(20.0, 21.0, 19.95, 20.2)]).sinais  # corpo pequeno
    assert not rodar(SetupElefante(), plano(61) + [(20.95, 21.0, 19.95, 20.0)]).sinais  # candle de baixa


def test_elefante_filtro_de_volume_compara_com_a_media():
    assert not rodar(SetupElefante(), plano(61) + [ELEFANTE], filtro_volume=True).sinais  # volume igual à média


# --- Família 9.x


def test_9_1_stop_acompanha_o_gatilho_por_padrao():
    linhas = queda(40, inicio=21.0, passo=0.05)
    c = linhas[-1][3]
    linhas += [(c, c + 0.8, c - 0.1, c + 0.7), (c + 0.5, c + 0.7, c + 0.4, c + 0.6)]
    padrao = rodar(LarryWilliams91(), linhas)
    no_sinal = rodar(LarryWilliams91(), linhas, stop_no_candle_vigente=False)
    assert padrao.ordens_ativas[0].stop == pytest.approx(c + 0.39)
    assert no_sinal.ordens_ativas[0].stop == pytest.approx(c - 0.11)
    assert padrao.ordens_ativas[0].preco == no_sinal.ordens_ativas[0].preco == pytest.approx(c + 0.71)


def test_9_1_maxima_igual_nao_arrasta_gatilho_nem_stop():
    linhas = queda(40, inicio=21.0, passo=0.05)
    c = linhas[-1][3]
    linhas += [(c, c + 0.8, c - 0.1, c + 0.7), (c + 0.5, c + 0.8, c + 0.4, c + 0.75)]
    ordem = rodar(LarryWilliams91(), linhas).ordens_ativas[0]
    assert ordem.preco == pytest.approx(c + 0.81)
    assert ordem.stop == pytest.approx(c - 0.11)


def test_9_1_aquecimento_e_3_vezes_o_periodo():
    setup = LarryWilliams91()
    assert setup.aquecimento(setup.Parametros()) == 27
    assert setup.aquecimento(setup.Parametros(periodo_mme=21)) == 63


def test_9_2_sinal_e_saida_pela_media():
    linhas = subida(30) + [(25.9, 26.0, 25.0, 25.2), (25.3, 26.2, 25.2, 26.1)]
    t = rodar(LarryWilliams92(), linhas).trades[0]
    assert t.entrada_preco == pytest.approx(26.01)
    assert t.stop == pytest.approx(24.99)


def test_9_2_exige_media_subindo():
    linhas = queda(30) + [(18.5, 18.6, 18.0, 18.05)]
    assert not rodar(LarryWilliams92(), linhas).sinais


def test_9_3_dois_fechamentos_e_arrasto():
    linhas = subida(30) + [(25.8, 25.85, 25.4, 25.6), (25.6, 25.7, 25.3, 25.5)]
    r = rodar(LarryWilliams93(), linhas)
    assert r.ordens_ativas[0].preco == pytest.approx(25.71)
    assert r.ordens_ativas[0].stop == pytest.approx(25.29)
    r2 = rodar(LarryWilliams93(), linhas + [(25.5, 25.6, 25.1, 25.4)])
    assert r2.ordens_ativas[0].preco == pytest.approx(25.61)
    assert r2.ordens_ativas[0].stop == pytest.approx(25.09)


def test_9_3_fechar_acima_da_referencia_encerra_o_sinal():
    # Gatilho em 26,01: o fechamento de 25,90 passa da referência de 25,80 sem acionar a entrada.
    linhas = subida(30) + [(25.8, 25.85, 25.4, 25.6), (25.6, 26.0, 25.3, 25.5), (25.5, 25.95, 25.4, 25.9)]
    r = rodar(LarryWilliams93(), linhas)
    assert not r.trades
    assert not r.ordens_ativas
    assert r.sinais[0].situacao == "cancelado"


BASE_94 = queda(30) + [(18.6, 19.2, 18.5, 19.1), (19.2, 19.6, 19.1, 19.5)]


def test_9_4_retomada_usa_o_stop_do_9_1_e_nao_conta_o_9_1():
    virada = (18.9, 19.4, 18.7, 18.7)
    r = rodar(LarryWilliams94(), BASE_94 + [virada, (18.8, 19.5, 18.75, 19.4)])
    assert len(r.trades) == 1
    t = r.trades[0]
    assert t.entrada_preco == pytest.approx(19.41)
    assert t.stop == pytest.approx(18.49)


def test_9_4_nao_arma_se_o_stop_do_9_1_foi_perdido():
    r = rodar(LarryWilliams94(), BASE_94 + [(18.9, 19.4, 18.4, 18.7)])
    assert not r.sinais


def test_9_4_nao_arma_sem_9_1_acionado():
    r = rodar(LarryWilliams94(), queda(30) + [(18.6, 19.2, 18.5, 19.1), (18.9, 19.0, 18.7, 18.7)])
    assert not r.sinais


def test_9_4_stop_no_candle_de_sinal():
    r = rodar(LarryWilliams94(), BASE_94 + [(18.9, 19.4, 18.7, 18.7)], stop_tipo="candle_sinal")
    assert r.ordens_ativas[0].stop == pytest.approx(18.69)


# --- Ponto Contínuo

TOQUE = (26.9, 27.0, 25.8, 26.5)


def test_ponto_continuo_toque_e_stop_movel():
    linhas = subida(70, passo=0.1) + [TOQUE, (26.6, 27.2, 26.5, 27.1), (27.0, 27.3, 26.4, 26.6)]
    t = rodar(SetupPontoContinuo(), linhas).trades[0]
    assert t.entrada_preco == pytest.approx(27.01)
    assert t.stop == pytest.approx(25.79)
    assert t.saida_preco == pytest.approx(26.49)
    assert t.motivo_saida == "trailing_minima"


def test_ponto_continuo_exige_fechar_acima_da_media():
    linhas = subida(70, passo=0.1) + [(26.9, 27.0, 25.0, 25.2)]
    assert not rodar(SetupPontoContinuo(), linhas).sinais


def test_ponto_continuo_alvo_no_topo():
    linhas = subida(70, passo=0.1) + [(26.5, 26.8, 25.8, 26.5), (26.6, 26.85, 26.5, 26.7)]
    r = rodar(SetupPontoContinuo(), linhas, saida="alvo_topo")
    assert r.trades[0].alvo == pytest.approx(27.0)


# --- IFR2

SEM_MM200 = {"filtro_tendencia_mm200": False}
QUEDA_IFR = (10.0, 10.1, 9.0, 9.1)
BASE_IFR = plano(6, (10.0, 10.2, 9.8, 10.0)) + [QUEDA_IFR]


def test_ifr2_entra_no_fechamento_e_sai_no_alvo_movel():
    r = rodar(SetupIFR2(), BASE_IFR + [(9.2, 9.5, 9.0, 9.4), (9.4, 10.2, 9.3, 10.0)], **SEM_MM200)
    t = r.trades[0]
    assert t.entrada_preco == pytest.approx(9.1)
    assert t.entrada_data == t.sinal_data
    assert t.stop is None and t.risco is None
    assert t.saida_preco == pytest.approx(10.1)  # max(9,5; 10,1), dos 2 candles anteriores
    assert t.motivo_saida == "alvo_tecnico"


def test_ifr2_primeiro_alvo_vem_da_entrada():
    t = rodar(SetupIFR2(), BASE_IFR + [(9.2, 10.3, 9.0, 10.0)], **SEM_MM200).trades[0]
    assert t.saida_preco == pytest.approx(10.2)
    assert t.motivo_saida == "alvo_tecnico"


def test_ifr2_abertura_acima_do_alvo_sai_na_abertura():
    t = rodar(SetupIFR2(), BASE_IFR + [(10.5, 10.6, 10.4, 10.5)], **SEM_MM200).trades[0]
    assert t.saida_preco == pytest.approx(10.5)


def test_ifr2_saida_por_tempo():
    r = rodar(SetupIFR2(), BASE_IFR + [(9.2, 9.5, 9.0, 9.4), (9.2, 9.3, 9.0, 9.15)], n_candles=2, **SEM_MM200)
    t = r.trades[0]
    assert t.saida_preco == pytest.approx(9.15)
    assert t.motivo_saida == "saida_tempo"
    assert t.duracao_pregoes == 2


def test_ifr2_saida_por_indicador():
    r = rodar(SetupIFR2(), BASE_IFR + [(9.2, 9.8, 9.1, 9.7)], usar_alvo=False, nivel_saida=50, **SEM_MM200)
    assert r.trades[0].motivo_saida == "saida_indicador"
    assert r.trades[0].saida_preco == pytest.approx(9.7)


def test_ifr2_na_abertura_seguinte():
    r = rodar(SetupIFR2(), BASE_IFR + [(9.2, 9.5, 9.0, 9.4)], entrada_ifr2="abertura_seguinte", **SEM_MM200)
    t = r.trades[0]
    assert t.entrada_preco == pytest.approx(9.2)
    assert t.entrada_data != t.sinal_data


def test_ifr2_stop_percentual_define_o_risco():
    t = rodar(SetupIFR2(), BASE_IFR + [(9.2, 9.5, 8.0, 8.5)], stop_pct=5, **SEM_MM200).trades[0]
    assert t.stop == pytest.approx(9.1 * 0.95)
    assert t.risco == pytest.approx(9.1 * 0.05)
    assert t.motivo_saida == "stop_inicial"


def test_ifr2_filtro_mm200_vem_ligado_e_bloqueia_abaixo_da_media():
    assert SetupIFR2.Parametros().filtro_tendencia_mm200 is True
    assert SetupIFR2().aquecimento(SetupIFR2.Parametros()) == 600
    linhas = subida(700, passo=0.05)
    ultimo = linhas[-1][3]
    acima = linhas + [(ultimo, ultimo + 0.1, ultimo - 1.2, ultimo - 1.1)]
    assert rodar(SetupIFR2(), acima).trades
    abaixo = queda(700, inicio=60.0)
    ultimo = abaixo[-1][3]
    assert not rodar(SetupIFR2(), abaixo + [(ultimo, ultimo + 0.1, ultimo - 1.2, ultimo - 1.1)]).trades


def test_trade_sem_stop_nao_tem_resultado_em_r_nem_quebra_as_metricas():
    t = rodar(SetupIFR2(), BASE_IFR + [(9.2, 10.3, 9.0, 10.0)], **SEM_MM200).trades[0]
    res = resultado_trade(t, Custos())
    assert res["bruto_r"] is None and res["liquido_r"] is None
    assert res["bruto_pct"] == pytest.approx((10.2 / 9.1 - 1) * 100)
    registro = {
        "aberto": False, "numero": 1, "entrada_data": t.entrada_data, "saida_data": t.saida_data,
        "duracao_pregoes": 1, "avisos": [], **res,
    }  # fmt: skip
    assert indicadores_principais([registro], [t.entrada_data, t.saida_data])["expectativa_r"] is None
    assert distribuicao_r([registro]) == []


# --- Didi


def _agulhada():
    linhas = queda(70, inicio=30.0, passo=0.1)
    c = linhas[-1][3]
    return linhas + [(c, c + 10.1, c - 0.1, c + 10.0)], c


DOCUMENTO = {"gatilho_didi": "agulhada_neutra", "entrada_didi": "rompimento", "confirma_estocastico": False, "confirma_trix": False}
SEM_CONFIRMACAO = {"confirma_adx": False, "confirma_estocastico": False, "confirma_trix": False}


def test_didi_agulhada_entrada_stop_e_saida():
    linhas, c = _agulhada()
    depois = [(c + 10, c + 10.5, c + 9.9, c + 10.2)] + [(c + 3, c + 3.1, c + 1, c + 2)] * 3
    r = rodar(SetupDidi(), linhas + depois, **{**DOCUMENTO, "confirma_adx": False})
    t = r.trades[0]
    assert t.entrada_preco == pytest.approx(c + 10.11)
    assert t.stop == pytest.approx(c - 0.11)
    assert t.motivo_saida == "cruzamento_inverso"
    assert t.saida_preco == pytest.approx(c + 2)


def test_didi_confirmacao_do_adx_barra_o_sinal_se_ele_nao_subir():
    linhas, _ = _agulhada()
    assert not rodar(SetupDidi(), linhas, **DOCUMENTO).sinais  # em tendência pura de baixa, o ADX cai no candle da virada
    assert rodar(SetupDidi(), linhas, **{**DOCUMENTO, "confirma_adx": False}).sinais


def test_didi_sem_os_dois_cruzamentos_nao_ha_sinal():
    assert not rodar(SetupDidi(), subida(80), **{**DOCUMENTO, "confirma_adx": False}).sinais


def test_didi_janela_aceita_cruzamentos_em_candles_diferentes():
    # A MMA 3 cruza primeiro, com uma alta menor; a MMA 20 cruza a MMA 8 só no candle seguinte.
    linhas = queda(70, inicio=30.0, passo=0.1)
    c = linhas[-1][3]
    pequena = (c, c + 1.6, c - 0.1, c + 1.5)
    grande = (c + 1.5, c + 12.1, c + 1.4, c + 12.0)
    livre = {**DOCUMENTO, "confirma_adx": False}
    assert not rodar(SetupDidi(), linhas + [pequena, grande], **livre).sinais
    assert rodar(SetupDidi(), linhas + [pequena, grande], janela_cruzamento=1, **livre).sinais


def _gatilho_do_video():
    """Queda seguida de alta: a MMA 3 passa a MMA 20 alguns candles depois de passar a MMA 8."""
    linhas = queda(70, inicio=30.0, passo=0.1)
    for _ in range(8):
        c = linhas[-1][3]
        linhas.append((c, c + 0.65, c - 0.05, c + 0.6))
    fech = np.array([x[3] for x in linhas])
    m3, m8, m20 = mma(fech, 3), mma(fech, 8), mma(fech, 20)
    sinal = next(i for i in range(70, len(linhas)) if m3[i - 1] <= m20[i - 1] and m3[i] > m20[i])
    assert m3[sinal] > m8[sinal]
    return linhas, sinal


def test_didi_padrao_compra_na_abertura_seguinte_ao_cruzamento_da_curta_com_a_longa():
    linhas, sinal = _gatilho_do_video()
    seguinte = linhas[sinal + 1]
    r = rodar(SetupDidi(), linhas, **SEM_CONFIRMACAO)
    t = r.trades[0]
    assert r.sinais[0].data == serie(linhas).datas[sinal]
    assert t.entrada_data == serie(linhas).datas[sinal + 1]
    assert t.entrada_preco == pytest.approx(seguinte[0])
    assert t.stop == pytest.approx(linhas[sinal][2] - 0.01)


def test_didi_gatilho_exige_a_curta_acima_da_mma_8():
    # MMA 3 passa a MMA 20 caindo: abaixo da MMA 8 não é sinal.
    linhas = subida(30, inicio=20.0, passo=0.5) + queda(12, inicio=35.0, passo=0.8) + subida(6, inicio=25.5, passo=0.1)
    s = serie(linhas)
    m3, m8, m20 = mma(s.fechamento, 3), mma(s.fechamento, 8), mma(s.fechamento, 20)
    for sinal in rodar(SetupDidi(), linhas, **SEM_CONFIRMACAO).sinais:
        i = s.datas.index(sinal.data)
        assert m3[i] > m8[i] and m3[i] > m20[i] and m3[i - 1] <= m20[i - 1]


def test_didi_cada_sinal_padrao_tem_os_quatro_indicadores_alinhados():
    linhas = passeio_didi()
    s = serie(linhas)
    setup = SetupDidi()
    p = setup.Parametros()
    livre = rodar(setup, linhas, **SEM_CONFIRMACAO).sinais
    completos = executar(s, setup, p).sinais
    assert 0 < len(completos) < len(livre)
    a, di_mais, di_menos = adx(s.maxima, s.minima, s.fechamento, 8)
    k, d = estocastico(s.maxima, s.minima, s.fechamento, 8, 3, 3)
    t, tm = trix(s.fechamento, 8, 3)
    for sinal in completos:
        i = s.datas.index(sinal.data)
        assert a[i] > a[i - 1] and di_mais[i] > di_menos[i]
        assert k[i] > k[i - 1] and k[i] > d[i]
        assert t[i] > t[i - 1] and t[i] > tm[i]
    assert {x.data for x in completos} <= {x.data for x in livre}


def test_didi_adx_minimo_so_reduz_os_sinais():
    linhas = passeio_didi()
    todos = rodar(SetupDidi(), linhas).sinais
    filtrados = rodar(SetupDidi(), linhas, adx_min=32).sinais
    assert len(filtrados) < len(todos)


def test_didi_desenha_tres_paineis_separados():
    setup = SetupDidi()
    grupos = setup.paineis(setup.Parametros())
    assert grupos == [{"adx", "di_mais", "di_menos"}, {"est_k", "est_d"}, {"trix", "trix_media"}]


def passeio_didi(n=4000):
    gerador = np.random.default_rng(7)
    fech = 30.0 * np.exp(np.cumsum(gerador.normal(0.0002, 0.018, n)))
    linhas, anterior = [], fech[0]
    for c in fech:
        linhas.append((anterior, max(anterior, c) * 1.006, min(anterior, c) * 0.994, c))
        anterior = c
    return linhas


# --- Estocástico e TRIX


def test_estocastico_confere_com_conta_manual():
    h = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
    l = np.array([9.0, 9.5, 10.0, 11.0, 12.0])
    c = np.array([9.5, 10.5, 11.0, 12.5, 13.0])
    k, d = estocastico(h, l, c, 2, 2, 2)
    # Janela de 2: (C - menor L) = [-, 1,5, 1,5, 2,5, 2,0] e (maior H - menor L) = [-, 2,0, 2,5, 3,0, 3,0]
    assert np.isnan(k[:2]).all()
    assert k[2:] == pytest.approx([100 * 3.0 / 4.5, 100 * 4.0 / 5.5, 100 * 4.5 / 6.0])
    assert np.isnan(d[:3]).all()
    assert d[3] == pytest.approx((k[2] + k[3]) / 2)


def test_estocastico_sem_amplitude_fica_neutro_e_nao_contamina_a_media():
    h = np.array([10.0] * 6 + [11.0, 12.0, 13.0])
    l = np.array([10.0] * 6 + [10.0, 11.0, 12.0])
    c = np.array([10.0] * 6 + [11.0, 12.0, 13.0])
    k, d = estocastico(h, l, c, 2, 1, 2)
    assert k[3] == 50.0
    assert not np.isnan(d[-1])


def test_trix_confere_com_a_mme_tripla():
    c = np.array([10.0 + 0.3 * i + (i % 3) for i in range(40)])
    linha, media = trix(c, 4, 3)
    e1 = mme(c, 4)
    e2 = np.r_[[np.nan] * 3, mme(e1[3:], 4)]
    e3 = np.r_[[np.nan] * 6, mme(e2[6:], 4)]
    esperado = (e3[10:] / e3[9:-1] - 1) * 100
    assert np.isnan(linha[:10]).all()
    assert linha[10:] == pytest.approx(esperado)
    assert np.isnan(media[:12]).all()
    assert media[12] == pytest.approx(np.mean(linha[10:13]))


def test_trix_com_poucos_candles_fica_vazio():
    linha, media = trix(np.array([1.0, 2.0, 3.0]), 8, 3)
    assert np.isnan(linha).all() and np.isnan(media).all()


# --- Cruzamento de médias

CRUZA = plano(70, (20.0, 20.2, 18.0, 20.0)) + [(20.0, 21.1, 19.9, 21.0)]


def test_cruzamento_no_fechamento_e_cruzamento_inverso():
    r = rodar(SetupCruzamento(), CRUZA + [(21.0, 21.0, 19.0, 19.0)])
    t = r.trades[0]
    assert t.entrada_preco == pytest.approx(21.0)
    assert t.entrada_data == t.sinal_data
    assert t.stop == pytest.approx(17.99)
    assert t.saida_preco == pytest.approx(19.0)
    assert t.motivo_saida == "cruzamento_inverso"


def test_cruzamento_no_rompimento():
    r = rodar(SetupCruzamento(), CRUZA + [(21.2, 21.5, 21.0, 21.4)], entrada_cruzamento="rompimento")
    assert r.trades[0].entrada_preco == pytest.approx(21.2)  # abriu acima de 21,11


def test_cruzamento_rejeita_rapida_maior_que_lenta():
    with pytest.raises(ValueError):
        SetupCruzamento.Parametros(periodo_rapida=21, periodo_lenta=9)


# --- Bollinger

FORA_E_VOLTA = plano(60) + [(20.0, 20.0, 18.9, 19.0), (19.0, 20.0, 18.8, 19.9)]


def test_bollinger_sinal_e_stop_na_minima_de_dois_candles():
    r = rodar(SetupBollinger(), FORA_E_VOLTA)
    ordem = r.ordens_ativas[0]
    assert ordem.preco == pytest.approx(20.01)
    assert ordem.stop == pytest.approx(18.79)


def test_bollinger_alvo_acompanha_a_banda_escolhida():
    gatilho = (19.95, 20.1, 19.9, 20.05)
    central = rodar(SetupBollinger(), FORA_E_VOLTA + [gatilho])
    superior = rodar(SetupBollinger(), FORA_E_VOLTA + [gatilho], saida_bb="superior")
    assert central.ordens_ativas[0].tipo == "saida_alvo"
    assert central.ordens_ativas[0].preco == pytest.approx(central.indicadores["bb_meio"][-1])
    assert superior.ordens_ativas[0].preco == pytest.approx(superior.indicadores["bb_sup"][-1])
    assert central.trades[0].alvo == pytest.approx(central.indicadores["bb_meio"][-1])


# --- Holy Grail

PULLBACK = (26.9, 26.95, 25.8, 26.5)


def test_holy_grail_entrada_alvo_e_stop():
    r = rodar(SetupHolyGrail(), subida(70, passo=0.1) + [PULLBACK])
    ordem = r.ordens_ativas[0]
    assert ordem.preco == pytest.approx(26.96)
    assert ordem.alvo == pytest.approx(27.0)
    assert ordem.stop == pytest.approx(25.79)


def test_holy_grail_so_o_primeiro_toque_e_arrasto():
    segundo = (26.4, 26.7, 25.9, 26.3)
    r = rodar(SetupHolyGrail(), subida(70, passo=0.1) + [PULLBACK, segundo])
    assert len(r.sinais) == 1
    assert r.ordens_ativas[0].preco == pytest.approx(26.71)
    outro = rodar(SetupHolyGrail(), subida(70, passo=0.1) + [PULLBACK, segundo], apenas_primeiro_toque=False)
    assert len(outro.sinais) == 2


def test_holy_grail_exige_adx_forte():
    assert not rodar(SetupHolyGrail(), plano(70) + [PULLBACK]).sinais
    assert not rodar(SetupHolyGrail(), subida(70, passo=0.1) + [PULLBACK], adx_min=100).sinais


# --- 1-2-3 e Ross Hook


def _pivos(minimas):
    return [(l, l + 1.0, l, l + 0.5) for l in minimas]


PONTOS = [12, 11, 10, 11, 12, 13, 14, 13, 12, 13, 14]  # 1: índice 2; 2: índice 6; 3: índice 8


def test_ross_so_arma_depois_de_confirmar_o_pivo():
    assert not rodar(SetupRoss(), _pivos(PONTOS[:10])).ordens_ativas
    r = rodar(SetupRoss(), _pivos(PONTOS))
    assert r.ordens_ativas[0].preco == pytest.approx(15.01)
    assert r.ordens_ativas[0].stop == pytest.approx(11.99)


def test_ross_rompimento_do_ponto_2():
    t = rodar(SetupRoss(), _pivos(PONTOS + [15])).trades[0]
    assert t.entrada_preco == pytest.approx(15.01)
    assert t.stop == pytest.approx(11.99)


def test_ross_perder_o_ponto_3_invalida():
    r = rodar(SetupRoss(), _pivos(PONTOS) + [(13.5, 14.0, 11.5, 11.8)])
    assert not r.trades
    assert r.sinais[0].situacao == "cancelado"


def test_ross_fundo_mais_baixo_que_o_ponto_1_nao_forma_padrao():
    assert not rodar(SetupRoss(), _pivos([12, 11, 10, 11, 12, 13, 14, 13, 9, 13, 14])).ordens_ativas


def test_ross_hook():
    # Rompe o ponto 2 (índice 11), faz nova máxima (12) e para de subir (13): o hook é a máxima de 18.
    linhas = _pivos(PONTOS + [15, 17, 16.5])
    r = rodar(SetupRoss(), linhas, modo="hook")
    assert r.ordens_ativas[0].preco == pytest.approx(18.01)
    assert r.ordens_ativas[0].stop == pytest.approx(16.49)
    correcao = rodar(SetupRoss(), linhas + _pivos([16]), modo="hook")
    assert correcao.ordens_ativas[0].stop == pytest.approx(15.99)
    assert correcao.ordens_ativas[0].preco == pytest.approx(18.01)
    assert rodar(SetupRoss(), linhas + _pivos([17.5]), modo="hook").trades[0].entrada_preco == pytest.approx(18.01)


# --- Tartarugas


def test_donchian_ordem_fica_armada_em_um_sinal_so():
    r = rodar(SetupDonchian(), plano(100))
    assert len(r.sinais) == 1
    assert r.estado == "armado"
    assert r.ordens_ativas[0].preco == pytest.approx(20.21)
    assert r.ordens_ativas[0].stop == pytest.approx(20.21 - 2 * r.indicadores["atr"][-1])


def test_donchian_entrada_e_saida_no_canal():
    linhas = plano(100) + [(20.2, 21.0, 20.1, 20.9), (20.9, 21.0, 19.5, 19.6)]
    t = rodar(SetupDonchian(), linhas).trades[0]
    assert t.entrada_preco == pytest.approx(20.21)
    assert t.saida_preco == pytest.approx(19.79)
    assert t.motivo_saida == "canal_saida"


def test_donchian_sistema_2_aquece_mais():
    assert SetupDonchian().aquecimento(SetupDonchian.Parametros(n_entrada=55, n_saida=20)) == 165


def test_lacuna_recomeca_o_estado_do_setup():
    linhas = _pivos(PONTOS)
    candles: SerieCandles = serie(linhas, quebras=(9,))
    r = executar(candles, SetupRoss(), SetupRoss.Parametros())
    assert not r.ordens_ativas  # o ponto 3 foi confirmado depois da lacuna, e a memória recomeçou nela


# --- Recuo com IFR curto (Stormer)

# Alta forte, com a MME 17 acima da MME 20, e dois candles de queda: o IFR 4 vai a 23,4 no segundo.
RECUO = subida(70) + [(33.8, 33.9, 32.4, 32.5), (32.5, 32.6, 31.9, 32.0)]
DIA_ENTRADA = (32.1, 32.4, 31.95, 32.3)  # fecha com lucro já no dia da entrada


def test_recuo_ifr_entra_na_abertura_com_stop_em_reais_e_espera_o_segundo_pregao():
    r = rodar(SetupRecuoIFR(), RECUO + [DIA_ENTRADA, (32.3, 32.6, 32.0, 32.5)])
    t = r.trades[0]
    assert t.entrada_preco == pytest.approx(32.1)
    assert t.entrada_data != t.sinal_data
    assert t.stop == pytest.approx(31.9 - 0.5)
    # O fechamento do dia da entrada já tinha lucro, mas a saída só vale a partir do segundo pregão.
    assert t.saida_preco == pytest.approx(32.5)
    assert t.motivo_saida == "saida_lucro"
    assert t.duracao_pregoes == 1


def test_recuo_ifr_com_um_pregao_sai_no_proprio_dia_da_entrada():
    t = rodar(SetupRecuoIFR(), RECUO + [DIA_ENTRADA], pregoes_minimos=1).trades[0]
    assert t.saida_data == t.entrada_data
    assert t.saida_preco == pytest.approx(32.3)


def test_recuo_ifr_fechamento_sem_lucro_mantem_a_posicao_ate_o_stop():
    r = rodar(SetupRecuoIFR(), RECUO + [DIA_ENTRADA, (32.0, 32.05, 31.8, 31.9), (31.9, 32.0, 31.0, 31.2)])
    t = r.trades[0]
    assert t.motivo_saida == "stop_inicial"
    assert t.saida_preco == pytest.approx(31.4)


def test_recuo_ifr_nao_compra_com_a_mme_rapida_abaixo_da_lenta():
    linhas = queda(70, 40.0, 0.2) + [(26.2, 26.3, 25.0, 25.1)]
    assert rodar(SetupRecuoIFR(), linhas).sinais == []


def test_recuo_ifr_stop_abaixo_de_zero_nao_gera_sinal():
    assert rodar(SetupRecuoIFR(), RECUO + [DIA_ENTRADA], distancia_stop=40).sinais == []


def test_recuo_ifr_rapida_precisa_ser_menor_que_lenta():
    with pytest.raises(ValueError):
        SetupRecuoIFR.Parametros(periodo_rapida=20, periodo_lenta=20)


# --- Padrões de candle (Bulkowski)


def alta_suave(n=70, inicio=20.0):
    """Alta lenta com corpos de 0,05: a média de corpo fica pequena e a MMA 21 sobe."""
    return [(inicio + 0.05 * i, inicio + 0.05 * i + 0.15, inicio + 0.05 * i - 0.1, inicio + 0.05 * i + 0.05) for i in range(n)]


def queda_suave(n=70, inicio=30.0):
    return [(inicio - 0.05 * i, inicio - 0.05 * i + 0.1, inicio - 0.05 * i - 0.15, inicio - 0.05 * i - 0.05) for i in range(n)]


def deslocar(candles, base):
    return [tuple(base + v for v in c) for c in candles]


ALTA = alta_suave()
P = ALTA[-1][3]  # 23,50
SEPARACAO = deslocar([(0, 0.05, -0.6, -0.55), (0.02, 0.62, -0.02, 0.6)], P)
ROMPE = (P + 0.6, P + 0.8, P + 0.5, P + 0.75)


def test_separacao_alta_compra_o_rompimento_com_stop_no_ultimo_candle():
    t = rodar(SetupSeparacaoAlta(), ALTA + SEPARACAO + [ROMPE]).trades[0]
    assert t.entrada_preco == pytest.approx(P + 0.63)
    assert t.stop == pytest.approx(P - 0.03)
    assert t.alvo == pytest.approx(P + 0.63 + 2 * 0.66)


def test_separacao_alta_stop_na_minima_do_padrao():
    t = rodar(SetupSeparacaoAlta(), ALTA + SEPARACAO + [ROMPE], stop_padrao="minima_padrao").trades[0]
    assert t.stop == pytest.approx(P - 0.61)


def test_separacao_alta_exige_abertura_igual_a_anterior():
    longe = deslocar([(0, 0.05, -0.6, -0.55), (-0.3, 0.62, -0.32, 0.6)], P)
    assert rodar(SetupSeparacaoAlta(), ALTA + longe + [ROMPE]).sinais == []


def test_separacao_alta_exige_tendencia():
    base = queda_suave()
    q = base[-1][3]
    padrao = deslocar([(0, 0.05, -0.6, -0.55), (0.02, 0.62, -0.02, 0.6)], q)
    assert rodar(SetupSeparacaoAlta(), base + padrao).sinais == []
    assert rodar(SetupSeparacaoAlta(), base + padrao, exigir_tendencia=False).sinais


MAT = [(1.00, 1.065, 0.995, 1.06), (1.08, 1.085, 1.065, 1.07), (1.068, 1.07, 1.05, 1.055),
       (1.055, 1.06, 1.04, 1.045), (1.045, 1.12, 1.044, 1.115)]


def test_mat_hold_cinco_candles_e_rompimento():
    padrao = [tuple(v * P for v in c) for c in MAT]
    r = rodar(SetupMatHold(), ALTA + padrao + [(1.115 * P, 1.15 * P, 1.11 * P, 1.14 * P)])
    t = r.trades[0]
    assert t.entrada_preco == pytest.approx(1.12 * P + 0.01)
    assert t.stop == pytest.approx(1.044 * P - 0.01)


def test_mat_hold_correcao_nao_pode_perder_a_minima_do_primeiro():
    ruim = list(MAT)
    ruim[3] = (1.055, 1.06, 0.99, 1.045)  # mínima abaixo da do primeiro candle
    padrao = [tuple(v * P for v in c) for c in ruim]
    assert rodar(SetupMatHold(), ALTA + padrao).sinais == []


QUEDA = queda_suave()
Q = QUEDA[-1][3]  # 26,50
PENETRANTE = deslocar([(0, 0.05, -0.6, -0.58), (-0.7, -0.15, -0.75, -0.2)], Q)


def test_penetrante_abre_abaixo_da_minima_e_fecha_acima_do_meio():
    r = rodar(SetupPenetrante(), QUEDA + PENETRANTE + [deslocar([(-0.2, 0.0, -0.3, -0.05)], Q)[0]])
    t = r.trades[0]
    assert t.entrada_preco == pytest.approx(Q - 0.14)
    assert t.stop == pytest.approx(Q - 0.76)


def test_penetrante_fechamento_abaixo_do_meio_nao_vale():
    raso = deslocar([(0, 0.05, -0.6, -0.58), (-0.7, -0.35, -0.75, -0.4)], Q)
    assert rodar(SetupPenetrante(), QUEDA + raso).sinais == []


def test_penetrante_sem_gap_de_baixa_nao_vale():
    sem_gap = deslocar([(0, 0.05, -0.6, -0.58), (-0.55, -0.15, -0.62, -0.2)], Q)
    assert rodar(SetupPenetrante(), QUEDA + sem_gap).sinais == []


DELIBERANTE = deslocar([(0, 0.6, -0.02, 0.55), (0.55, 1.15, 0.53, 1.1), (1.12, 1.25, 1.05, 1.13)], P)


def test_deliberante_dois_fortes_e_um_pequeno():
    r = rodar(SetupDeliberante(), ALTA + DELIBERANTE + [deslocar([(1.15, 1.4, 1.1, 1.35)], P)[0]])
    t = r.trades[0]
    assert t.entrada_preco == pytest.approx(P + 1.26)
    assert t.stop == pytest.approx(P + 1.04)


def test_deliberante_terceiro_candle_grande_nao_vale():
    grande = DELIBERANTE[:2] + deslocar([(1.12, 1.8, 1.05, 1.75)], P)
    assert rodar(SetupDeliberante(), ALTA + grande).sinais == []
