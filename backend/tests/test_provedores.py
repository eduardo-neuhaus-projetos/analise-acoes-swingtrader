"""Provedores com respostas gravadas, incluindo erro, limite excedido e dado inválido."""
import json
from pathlib import Path

import httpx
import pandas as pd
import pytest

from app.erros import ErroProvedor
from app.provedores.brapi import ProvedorBrapi
from app.provedores.yahoo import ProvedorYahoo

GRAVADA = json.loads((Path(__file__).parent / "fixtures" / "brapi_petr4.json").read_text(encoding="utf-8"))


def brapi(tratador, token=None):
    return ProvedorBrapi(lambda: token, transporte=httpx.MockTransport(tratador), esperar=lambda _: None)


def test_brapi_resposta_gravada_em_ordem_de_data():
    candles = brapi(lambda r: httpx.Response(200, json=GRAVADA)).buscar("PETR4")
    assert len(candles) > 50
    assert [c.data for c in candles] == sorted(c.data for c in candles)
    assert candles[0].ajustado is not None
    assert candles[0].data >= "2026-08-01"  # meia-noite no fuso da B3, e não o dia anterior em UTC


def test_brapi_token_vai_no_cabecalho_e_nunca_na_url():
    visto = {}

    def tratador(pedido):
        visto["url"] = str(pedido.url)
        visto["auth"] = pedido.headers.get("authorization")
        return httpx.Response(200, json=GRAVADA)

    brapi(tratador, token="segredo").buscar("PETR4")
    assert "segredo" not in visto["url"]
    assert visto["auth"] == "Bearer segredo"


def test_brapi_sem_token():
    with pytest.raises(ErroProvedor) as erro:
        brapi(lambda r: httpx.Response(401, json={"error": True})).buscar("WEGE3")
    assert erro.value.codigo == "token_necessario"
    assert "WEGE3" in erro.value.mensagem


def test_brapi_token_recusado_nao_pede_para_criar_token():
    with pytest.raises(ErroProvedor) as erro:
        brapi(lambda r: httpx.Response(401, json={"error": True}), token="vencido").buscar("WEGE3")
    assert erro.value.codigo == "token_recusado"
    assert "vencido" not in erro.value.mensagem


def test_brapi_codigo_inexistente():
    with pytest.raises(ErroProvedor) as erro:
        brapi(lambda r: httpx.Response(404, json={"error": True})).buscar("XXXX3")
    assert erro.value.codigo == "ativo_nao_encontrado"


def test_brapi_limite_tenta_de_novo_com_espera_crescente():
    esperas = []
    provedor = ProvedorBrapi(
        lambda: None, transporte=httpx.MockTransport(lambda r: httpx.Response(429)), esperar=esperas.append
    )
    with pytest.raises(ErroProvedor) as erro:
        provedor.buscar("PETR4")
    assert erro.value.codigo == "limite_excedido"
    assert esperas == [1.0, 2.0, 4.0]


def test_brapi_recupera_depois_de_falha_temporaria():
    respostas = iter([httpx.Response(500), httpx.Response(200, json=GRAVADA)])
    assert brapi(lambda r: next(respostas)).buscar("PETR4")


def test_brapi_dado_invalido():
    with pytest.raises(ErroProvedor) as erro:
        brapi(lambda r: httpx.Response(200, text="<html>")).buscar("PETR4")
    assert erro.value.codigo == "dado_invalido"


def tabela_yahoo():
    indice = pd.to_datetime(["2024-01-02", "2024-01-03"]).tz_localize("America/Sao_Paulo")
    return pd.DataFrame(
        {
            "Open": [10.0, 11.0],
            "High": [11.0, 12.0],
            "Low": [9.0, 10.0],
            "Close": [10.5, float("nan")],
            "Adj Close": [10.0, 11.0],
            "Volume": [100, 200],
        },
        index=indice,
    )


def test_yahoo_converte_e_trata_nan():
    candles = ProvedorYahoo(baixar=lambda s, d: tabela_yahoo(), esperar=lambda _: None).buscar("PETR4")
    assert candles[0].data == "2024-01-02"
    assert candles[0].ajustado == 10.0
    assert candles[1].fechamento is None


def test_yahoo_usa_sufixo_sa():
    vistos = []

    def baixar(simbolo, desde):
        vistos.append(simbolo)
        return tabela_yahoo()

    provedor = ProvedorYahoo(baixar=baixar, esperar=lambda _: None)
    provedor.buscar("PETR4")
    provedor.buscar("^BVSP")
    assert vistos == ["PETR4.SA", "^BVSP"]


def test_yahoo_tabela_vazia_e_erro_claro():
    provedor = ProvedorYahoo(baixar=lambda s, d: pd.DataFrame(), esperar=lambda _: None)
    with pytest.raises(ErroProvedor) as erro:
        provedor.buscar("XXXX3")
    assert erro.value.codigo == "ativo_nao_encontrado"


def test_yahoo_incremental_vazio_nao_e_erro():
    provedor = ProvedorYahoo(baixar=lambda s, d: pd.DataFrame(), esperar=lambda _: None)
    assert provedor.buscar("PETR4", desde="2024-01-01") == []


def test_yahoo_falha_de_rede():
    def baixar(simbolo, desde):
        raise ConnectionError("sem rede")

    with pytest.raises(ErroProvedor) as erro:
        ProvedorYahoo(baixar=baixar, esperar=lambda _: None).buscar("PETR4")
    assert erro.value.codigo == "fonte_indisponivel"


def test_yahoo_baixa_desde_2010(monkeypatch):
    import sys
    import types

    from app.provedores import yahoo

    pedidos = []

    class Papel:
        def __init__(self, simbolo):
            pass

        def history(self, **kw):
            pedidos.append(kw)
            return pd.DataFrame()

    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=Papel))
    yahoo._baixar_yfinance("PETR4.SA", None)
    yahoo._baixar_yfinance("PETR4.SA", "2005-01-01")
    yahoo._baixar_yfinance("PETR4.SA", "2024-05-02")
    assert [p["start"] for p in pedidos] == ["2010-01-01", "2010-01-01", "2024-05-02"]
    assert all("period" not in p for p in pedidos)
