import pytest

from app.motor.metricas import calcular_painel, distribuicao_r, indicadores_principais, taxa_movel

DATAS = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-02-01"]


def trade(n, saida, pct, r, entrada=None, aberto=False, avisos=()):
    return {
        "numero": n,
        "entrada_data": entrada or saida,
        "saida_data": None if aberto else saida,
        "aberto": aberto,
        "liquido_pct": pct,
        "bruto_pct": pct,
        "liquido_r": r,
        "duracao_pregoes": 1,
        "avisos": list(avisos),
    }


TRADES = [
    trade(1, "2024-01-02", 10.0, 2.0, entrada="2024-01-01"),
    trade(2, "2024-01-03", -5.0, -1.0, avisos=["x"]),
    trade(3, "2024-01-04", 0.0, 0.0),
    trade(4, "2024-02-01", 20.0, 4.0, entrada="2024-01-05"),
    trade(5, "", 3.0, 0.5, entrada="2024-02-01", aberto=True),
]


def test_indicadores_batem_com_resultado_conhecido():
    k = indicadores_principais(TRADES, DATAS)
    assert (k["trades"], k["acertos"], k["erros"], k["empates"], k["abertos"]) == (4, 2, 1, 1, 1)
    assert k["taxa_acerto"] == pytest.approx(200 / 3)
    assert k["taxa_erro"] == pytest.approx(100 / 3)
    assert k["ganho_medio"] == pytest.approx(15)
    assert k["perda_media"] == pytest.approx(-5)
    assert k["payoff"] == pytest.approx(3)
    assert k["fator_lucro"] == pytest.approx(6)
    assert k["expectativa_r"] == pytest.approx(5 / 4)
    assert k["retorno"] == pytest.approx(1.1 * 0.95 * 1.2 * 100 - 100)
    assert k["drawdown_maximo"] == pytest.approx(-5)
    assert k["trades_com_aviso"] == 1


def test_sem_trades_nao_quebra():
    k = indicadores_principais([], DATAS)
    assert k["trades"] == 0 and k["taxa_acerto"] is None and k["payoff"] is None
    assert k["retorno"] == 0


def test_tempo_exposto_conta_pregoes_com_posicao():
    k = indicadores_principais([trade(1, "2024-01-03", 1, 1, entrada="2024-01-02")], DATAS)
    assert k["tempo_exposto"] == pytest.approx(2 / 6 * 100)


def test_taxa_movel():
    t = [trade(i, f"2024-01-{i + 1:02d}", 1.0 if i % 2 else -1.0, 1) for i in range(1, 7)]
    pontos = taxa_movel(t, janela=4)
    assert len(pontos) == 3
    assert all(p["taxa"] == 50 for p in pontos)


def test_distribuicao_inclui_faixas_vazias():
    faixas = distribuicao_r([trade(1, "2024-01-02", 1, -1.0), trade(2, "2024-01-03", 1, 1.2)])
    assert faixas[0] == {"de": -1.0, "ate": -0.5, "trades": 1}
    assert sum(f["trades"] for f in faixas) == 2
    assert len(faixas) == 5


def test_painel_mapa_e_anual():
    p = calcular_painel(TRADES, DATAS)
    assert {(m["ano"], m["mes"]) for m in p["mapa_mensal"]} == {(2024, 1), (2024, 2)}
    assert p["anual"][0]["trades"] == 4
    assert p["curva"][-1]["capital"] == pytest.approx(125.4)
    assert len(p["sequencia"]) == 4
