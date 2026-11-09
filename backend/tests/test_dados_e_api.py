"""Armazenamento, rebase, lacunas, separação das abas e API de ponta a ponta, sem rede."""
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import db
from app.calendario import FUSO_B3, candle_em_formacao, eh_pregao, menos_tres_meses, pregoes_faltantes
from app.erros import ErroProvedor
from app.main import app
from app.provedores.base import CandleRecebido, Provedor
from app.servicos import acompanhamento, dados
from tests.auxiliares import D1, D2, D3, D4, D5, D6, D7, aquecimento_prd, datas_uteis


class ProvedorFalso(Provedor):
    plano = "teste"

    def __init__(self, id_, acumula):
        self.id = id_
        self.nome = id_
        self.acumula = acumula
        self.respostas = {}
        self.falha = None
        self.pedidos = []

    def buscar(self, codigo, desde=None):
        self.pedidos.append((codigo, desde))
        if self.falha:
            raise self.falha
        if codigo not in self.respostas:
            raise ErroProvedor("ativo_nao_encontrado", f"{self.id} não encontrou {codigo}.")
        return [c for c in self.respostas[codigo] if not desde or c.data >= desde]


def candles_de(linhas, datas=None, fator=1.0):
    datas = datas or datas_uteis(len(linhas))
    return [
        CandleRecebido(d, a, ma, mi, f, f * fator, 1000.0) for d, (a, ma, mi, f) in zip(datas, linhas)
    ]


LINHAS_PRD = aquecimento_prd() + [D1, D2, D3, D4, D5, D6, D7]


@pytest.fixture
def falsos(banco, monkeypatch):
    brapi = ProvedorFalso("brapi", True)
    yahoo = ProvedorFalso("yahoo", False)
    monkeypatch.setattr(dados, "PROVEDORES", {"brapi": brapi, "yahoo": yahoo})
    return brapi, yahoo


@pytest.fixture
def cliente(falsos):
    with TestClient(app) as c:
        yield c


def fechamentos(fonte, codigo):
    linhas, _ = dados.ler_candles(fonte, codigo)
    return {l["data"]: l["fechamento"] for l in linhas}


# --- calendário


def test_calendario_conhece_feriados_moveis_e_fixos():
    assert not eh_pregao(date(2024, 2, 13))  # Carnaval
    assert not eh_pregao(date(2024, 3, 29))  # Sexta-feira Santa
    assert not eh_pregao(date(2024, 5, 30))  # Corpus Christi
    assert not eh_pregao(date(2024, 12, 25))
    assert not eh_pregao(date(2024, 11, 20))
    assert eh_pregao(date(2023, 11, 20))  # em 2022 e 2023 a B3 abriu
    assert not eh_pregao(date(2021, 11, 20 - 1 + 1)) or date(2021, 11, 20).weekday() >= 5
    assert not eh_pregao(date(2024, 1, 6))  # sábado
    assert eh_pregao(date(2024, 1, 2))


def test_pregoes_faltantes_ignora_feriado():
    # 24/12 e 25/12/2024 são sem pregão, e 27/12 falta de verdade.
    datas = ["2024-12-23", "2024-12-26", "2024-12-30"]
    assert pregoes_faltantes(datas) == ["2024-12-27"]


def test_candle_de_hoje_so_conta_depois_do_fechamento():
    pregao = datetime(2026, 11, 6, 14, 0, tzinfo=FUSO_B3)
    fechado = datetime(2026, 11, 6, 19, 0, tzinfo=FUSO_B3)
    assert candle_em_formacao("2026-11-06", pregao)
    assert not candle_em_formacao("2026-11-06", fechado)
    assert not candle_em_formacao("2026-11-05", pregao)


def test_menos_tres_meses_com_fim_de_mes():
    assert menos_tres_meses(date(2026, 11, 6)) == date(2026, 8, 6)
    assert menos_tres_meses(date(2026, 5, 31)) == date(2026, 2, 28)
    assert menos_tres_meses(date(2026, 1, 15)) == date(2025, 10, 15)


# --- ajuste, cache e isolamento


def test_ohlc_e_ajustado_pelo_fator_e_o_recebido_fica_guardado(falsos):
    brapi, _ = falsos
    brapi.respostas["PETR4"] = [CandleRecebido("2024-01-02", 10.0, 12.0, 9.0, 10.0, 9.0, 100.0)]
    dados.atualizar_serie("brapi", "PETR4")
    linhas, _ = dados.ler_candles("brapi", "PETR4")
    assert linhas[0]["abertura"] == pytest.approx(9.0)
    assert linhas[0]["maxima"] == pytest.approx(10.8)
    assert linhas[0]["minima"] == pytest.approx(8.1)
    assert linhas[0]["recebido_maxima"] == 12.0


def test_candle_em_formacao_nao_e_gravado(falsos, monkeypatch):
    brapi, _ = falsos
    brapi.respostas["PETR4"] = candles_de(LINHAS_PRD)
    ultimo = brapi.respostas["PETR4"][-1].data
    monkeypatch.setattr(dados, "candle_em_formacao", lambda d: d == ultimo)
    dados.atualizar_serie("brapi", "PETR4")
    assert ultimo not in fechamentos("brapi", "PETR4")


def test_fontes_nao_se_misturam_e_falha_nao_troca_de_fonte(falsos):
    brapi, yahoo = falsos
    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD)
    dados.atualizar_serie("yahoo", "PETR4")
    brapi.falha = ErroProvedor("fonte_indisponivel", "brapi fora do ar")
    with pytest.raises(ErroProvedor):
        dados.atualizar_serie("brapi", "PETR4")
    assert fechamentos("brapi", "PETR4") == {}
    assert fechamentos("yahoo", "PETR4")


def test_falha_mantem_o_cache_e_fica_registrada(falsos):
    brapi, _ = falsos
    brapi.respostas["PETR4"] = candles_de(LINHAS_PRD)
    dados.atualizar_serie("brapi", "PETR4")
    antes = fechamentos("brapi", "PETR4")
    brapi.falha = ErroProvedor("fonte_indisponivel", "brapi fora do ar")
    with pytest.raises(ErroProvedor):
        dados.atualizar_serie("brapi", "PETR4")
    assert fechamentos("brapi", "PETR4") == antes
    assert dados.origem_dados("brapi", "PETR4")["ultimo_erro"] == "brapi fora do ar"


def test_yahoo_atualiza_so_o_que_falta(falsos):
    _, yahoo = falsos
    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD)
    dados.atualizar_serie("yahoo", "PETR4")
    dados.atualizar_serie("yahoo", "PETR4")
    assert yahoo.pedidos[0] == ("PETR4", None)
    assert yahoo.pedidos[1][1] is not None
    assert len(yahoo.pedidos) == 2


def test_yahoo_reprocessa_quando_ajuste_muda_preco_antigo(falsos):
    _, yahoo = falsos
    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD)
    dados.atualizar_serie("yahoo", "PETR4")
    versao = dados.origem_dados("yahoo", "PETR4")["versao"]
    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD, fator=0.9)
    dados.atualizar_serie("yahoo", "PETR4")
    assert dados.origem_dados("yahoo", "PETR4")["versao"] == versao + 1
    assert yahoo.pedidos[-1] == ("PETR4", None)  # baixou a série inteira de novo
    primeiro = fechamentos("yahoo", "PETR4")[datas_uteis(1)[0]]
    assert primeiro == pytest.approx(20.10 * 0.9)


# --- acúmulo da brapi


def _janela(datas, ini, fim, preco=20.0, fator=1.0):
    return [
        CandleRecebido(d, preco, preco + 1, preco - 1, preco, preco * fator, 1000.0) for d in datas[ini:fim]
    ]


def test_brapi_guarda_o_que_saiu_da_janela(falsos):
    brapi, _ = falsos
    datas = datas_uteis(40)
    brapi.respostas["PETR4"] = _janela(datas, 0, 20)
    dados.atualizar_serie("brapi", "PETR4")
    brapi.respostas["PETR4"] = _janela(datas, 10, 30)
    dados.atualizar_serie("brapi", "PETR4")
    guardados = fechamentos("brapi", "PETR4")
    assert sorted(guardados) == datas[:30]
    assert dados.origem_dados("brapi", "PETR4")["versao"] == 1


def test_brapi_rebase_aplica_fator_unico_nos_candles_antigos(falsos):
    brapi, _ = falsos
    datas = datas_uteis(40)
    brapi.respostas["PETR4"] = _janela(datas, 0, 20)
    dados.atualizar_serie("brapi", "PETR4")
    brapi.respostas["PETR4"] = _janela(datas, 10, 30, fator=0.95)  # provento novo
    dados.atualizar_serie("brapi", "PETR4")
    linhas, _ = dados.ler_candles("brapi", "PETR4")
    por_data = {l["data"]: l for l in linhas}
    antigo = por_data[datas[0]]
    assert antigo["fechamento"] == pytest.approx(19.0)  # rebaseado
    assert antigo["recebido_fechamento"] == 20.0  # recebido fica como veio
    assert antigo["fator_rebase"] == pytest.approx(0.95)
    assert por_data[datas[15]]["fechamento"] == pytest.approx(19.0)  # sem salto na emenda
    assert dados.origem_dados("brapi", "PETR4")["versao"] == 2
    assert dados.origem_dados("brapi", "PETR4")["aviso_rebase"] is None


def test_brapi_rebase_sem_fator_unico_gera_alerta(falsos):
    brapi, _ = falsos
    datas = datas_uteis(40)
    brapi.respostas["PETR4"] = _janela(datas, 0, 20)
    dados.atualizar_serie("brapi", "PETR4")
    brapi.respostas["PETR4"] = _janela(datas, 10, 15, fator=0.95) + _janela(datas, 15, 30)
    dados.atualizar_serie("brapi", "PETR4")
    assert "fator de ajuste único" in dados.origem_dados("brapi", "PETR4")["aviso_rebase"]


def test_brapi_lacuna_marca_a_serie_como_interrompida(falsos):
    brapi, _ = falsos
    datas = datas_uteis(80)
    brapi.respostas["PETR4"] = _janela(datas, 0, 20)
    dados.atualizar_serie("brapi", "PETR4")
    brapi.respostas["PETR4"] = _janela(datas, 50, 70)
    dados.atualizar_serie("brapi", "PETR4")
    linhas, _ = dados.ler_candles("brapi", "PETR4")
    quebras = [l["data"] for l in linhas if l["quebra"]]
    assert quebras == [datas[50]]
    assert "lacuna" in dados.origem_dados("brapi", "PETR4")["aviso_rebase"]
    # Lacuna conhecida não vira uma enxurrada de alertas de pregão faltando.
    assert not [a for a in dados.avaliar_qualidade(linhas) if a["tipo"] == "pregao_faltando"]
    serie = next(s for s in dados.listar_series() if s["fonte"] == "brapi")
    assert serie["lacunas"] == [{"de": datas[19], "ate": datas[50]}]


# --- validação


def test_validacao_aponta_candles_ruins_e_motor_os_exclui(falsos):
    brapi, _ = falsos
    datas = datas_uteis(5)
    brapi.respostas["PETR4"] = [
        CandleRecebido(datas[0], 10, 11, 9, 10, 10, 100),
        CandleRecebido(datas[1], 10, 9, 11, 10, 10, 100),  # máxima abaixo da mínima
        CandleRecebido(datas[2], 0, 0, 0, 0, 0, 100),  # zerado
        CandleRecebido(datas[3], 10, 11, 9, 10, None, 0),  # sem ajuste e sem volume
    ]
    dados.atualizar_serie("brapi", "PETR4")
    linhas, _ = dados.ler_candles("brapi", "PETR4")
    tipos = {a["tipo"] for a in dados.avaliar_qualidade(linhas)}
    assert {"maxima_abaixo_da_minima", "preco_zerado", "sem_ajuste", "volume_zero"} <= tipos
    candles, excluidos = dados.serie_para_motor(linhas)
    assert excluidos == 2
    assert len(candles) == 2


# --- API


def test_busca_de_ativos(cliente):
    codigos = [a["codigo"] for a in cliente.get("/api/v1/ativos", params={"busca": "PETR"}).json()]
    assert codigos[:2] == ["PETR3", "PETR4"]  # quem casa pelo código vem antes de quem casa pelo nome
    assert set(codigos) <= {"PETR3", "PETR4", "PRIO3", "RECV3"}  # PetroRio e PetroRecôncavo casam pelo nome
    assert cliente.get("/api/v1/ativos", params={"busca": "magazine"}).json()[0]["codigo"] == "MGLU3"
    assert cliente.get("/api/v1/ativos", params={"busca": "ZZZZ"}).json() == []


def test_busca_sem_termo_lista_todos_os_ativos(cliente):
    codigos = [a["codigo"] for a in cliente.get("/api/v1/ativos").json()]
    assert {"PETR4", "WEGE3"} <= set(codigos)
    assert codigos == sorted(codigos)
    assert len(codigos) > 12
    assert "^BVSP" not in codigos


def test_todos_os_setups_rodam_pela_api_e_declaram_familia(cliente, falsos):
    falsos[1].respostas["PETR4"] = candles_de(LINHAS_PRD)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    setups = cliente.get("/api/v1/setups").json()
    assert len(setups) == 21
    for s in setups:
        assert s["familia"]
        r = cliente.post("/api/v1/analise/yahoo", json={"ativo": "PETR4", "setup_id": s["id"]})
        assert r.status_code == 200, s["id"]
        assert all(i["painel"] in ("preco", "inferior") for i in r.json()["indicadores"])


def test_opcao_fora_da_lista_e_recusada(cliente, falsos):
    falsos[1].respostas["PETR4"] = candles_de(LINHAS_PRD)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    r = cliente.post(
        "/api/v1/analise/yahoo", json={"ativo": "PETR4", "setup_id": "pfr", "params": {"saida": "inexistente"}}
    )
    assert r.status_code == 422
    assert r.json()["codigo"] == "parametro_invalido"


def test_trade_sem_stop_passa_pela_analise_pelo_csv_e_pelo_acompanhamento(cliente, falsos):
    # Plano seguido de uma queda forte: o IFR 2 vai a zero e a compra acontece no fechamento, sem stop.
    plano = [(10.0, 10.2, 9.8, 10.0)] * 30
    falsos[1].respostas["PETR4"] = candles_de(plano + [(10.0, 10.1, 9.0, 9.1), (9.2, 10.3, 9.0, 10.0), (10.0, 10.1, 9.9, 10.0)])
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    pedido = {"ativo": "PETR4", "setup_id": "ifr2", "params": {"filtro_tendencia_mm200": False}}
    r = cliente.post("/api/v1/analise/yahoo", json=pedido).json()
    t = r["trades"][0]
    assert t["stop"] is None and t["risco"] is None and t["liquido_r"] is None
    assert t["motivo_saida_texto"] == "Alvo técnico"
    assert r["painel"]["indicadores"]["expectativa_r"] is None
    assert r["painel"]["distribuicao"] == []
    assert [i["painel"] for i in r["indicadores"]] == ["inferior"]
    csv = cliente.get(f"/api/v1/execucoes/{r['execucao_id']}/trades.csv")
    assert csv.status_code == 200
    assert "Alvo técnico" in csv.text

    item = cliente.post("/api/v1/acompanhamento/yahoo", json={**pedido, "data_inicio": "2024-01-01"})
    assert item.status_code == 200
    eventos = cliente.get("/api/v1/acompanhamento/yahoo").json()["eventos"]
    assert any("Alvo técnico" in (e["descricao"] or "") for e in eventos)


def test_setups_vem_do_registro_com_esquema(cliente):
    setups = cliente.get("/api/v1/setups").json()
    assert setups[0]["id"] == "larry_williams_9_1"
    assert setups[0]["padroes"]["periodo_mme"] == 9
    assert setups[0]["esquema"]["properties"]["periodo_mme"]["maximum"] == 200


def test_codigo_invalido_tem_mensagem_clara(cliente):
    r = cliente.post("/api/v1/dados/yahoo/PETROBRAS/atualizar")
    assert r.status_code == 400
    assert "não é um código" in r.json()["mensagem"]


def test_codigo_inexistente_tem_mensagem_clara(cliente):
    r = cliente.post("/api/v1/dados/yahoo/XXXX3/atualizar")
    assert r.status_code == 502
    assert "XXXX3" in r.json()["mensagem"]


def analisar(cliente, fonte="yahoo", **extra):
    corpo = {"ativo": "PETR4", "setup_id": "larry_williams_9_1", **extra}
    return cliente.post(f"/api/v1/analise/{fonte}", json=corpo)


def test_analise_sem_dados_pede_download(cliente):
    r = analisar(cliente)
    assert r.status_code == 404
    assert r.json()["codigo"] == "sem_dados"


def test_analise_de_ponta_a_ponta_com_o_exemplo_do_prd(cliente, falsos):
    falsos[1].respostas["PETR4"] = candles_de(LINHAS_PRD)
    assert cliente.post("/api/v1/dados/yahoo/PETR4/atualizar").status_code == 200
    r = analisar(cliente).json()
    assert len(r["trades"]) == 1
    t = r["trades"][0]
    assert t["entrada_preco"] == pytest.approx(20.61)
    assert t["saida_preco"] == pytest.approx(21.59)
    assert t["liquido_pct"] == pytest.approx(4.755, abs=0.01)
    assert t["motivo_saida_texto"] == "Saída armada"
    k = r["painel"]["indicadores"]
    assert k["acertos"] == 1 and k["taxa_acerto"] == 100
    assert k["retorno"] == pytest.approx(t["liquido_pct"])
    assert r["origem"]["provedor"] == "yahoo"
    assert r["execucao_id"] > 0
    assert r["indicadores"][0]["rotulo"] == "MME 9"
    assert {a["tipo"] for a in r["avisos"]} >= {"amostra_pequena", "custos_zerados"}
    assert r["simulacao"]


def test_analise_reproduz_e_reaproveita_a_execucao(cliente, falsos):
    falsos[1].respostas["PETR4"] = candles_de(LINHAS_PRD)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    a, b = analisar(cliente).json(), analisar(cliente).json()
    assert a["execucao_id"] == b["execucao_id"]
    assert a["trades"] == b["trades"]


def test_abas_nao_compartilham_resultado(cliente, falsos):
    falsos[1].respostas["PETR4"] = candles_de(LINHAS_PRD)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    assert analisar(cliente, "brapi").status_code == 404
    assert analisar(cliente, "yahoo").status_code == 200


def test_parametro_fora_do_limite(cliente, falsos):
    falsos[1].respostas["PETR4"] = candles_de(LINHAS_PRD)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    r = analisar(cliente, params={"periodo_mme": 500})
    assert r.status_code == 422
    assert "Período da MME" in r.json()["mensagem"]


def test_brapi_nao_mostra_nada_antes_da_janela_de_3_meses(cliente, falsos, monkeypatch):
    brapi, _ = falsos
    # Trade encerrado há muito tempo, seguido de meses de preço parado.
    datas = datas_uteis(150)
    planos = [(21.0, 21.2, 20.8, 21.0)] * (150 - len(LINHAS_PRD))
    brapi.respostas["PETR4"] = candles_de(LINHAS_PRD + planos, datas)
    cliente.post("/api/v1/dados/brapi/PETR4/atualizar")
    r = analisar(cliente, "brapi").json()
    corte = menos_tres_meses(date.fromisoformat(datas[-1])).isoformat()
    assert r["candles"][0]["data"] >= corte
    assert r["trades"] == []
    assert all(s["data"] >= corte for s in r["sinais"])
    assert r["painel"]["curva"][0]["data"] >= corte
    # O dado antigo segue guardado e serve à MME: o primeiro ponto visível já tem valor.
    assert r["indicadores"][0]["pontos"][0]["data"] == r["candles"][0]["data"]


def test_brapi_mostra_trade_aberto_iniciado_antes_da_janela(cliente, falsos):
    brapi, _ = falsos
    subindo = [(30 + i * 0.1, 30.5 + i * 0.1, 29.8 + i * 0.1, 30.2 + i * 0.1) for i in range(135)]
    linhas = aquecimento_prd() + [D1, D2] + subindo
    brapi.respostas["PETR4"] = candles_de(linhas, datas_uteis(len(linhas)))
    cliente.post("/api/v1/dados/brapi/PETR4/atualizar")
    r = analisar(cliente, "brapi").json()
    assert len(r["trades"]) == 1 and r["trades"][0]["aberto"]
    assert r["trades"][0]["entrada_data"] < r["candles"][0]["data"]
    assert r["estado"] == "posicionado"


def test_csv_em_formato_brasileiro(cliente, falsos):
    falsos[1].respostas["PETR4"] = candles_de(LINHAS_PRD)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    execucao = analisar(cliente).json()["execucao_id"]
    r = cliente.get(f"/api/v1/execucoes/{execucao}/trades.csv")
    assert r.status_code == 200
    linhas = r.text.lstrip("﻿").strip().split("\r\n")
    assert len(linhas) == 2
    assert "20,6100" in linhas[1]
    assert "Saída armada" in linhas[1]
    assert ";" in linhas[1]


def test_comparacao_limita_a_cinco_e_isola_erro(cliente, falsos):
    falsos[1].respostas["PETR4"] = candles_de(LINHAS_PRD)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    item = {"ativo": "PETR4", "setup_id": "larry_williams_9_1"}
    assert cliente.post("/api/v1/comparar/yahoo", json={"itens": [item] * 6}).status_code == 422
    r = cliente.post(
        "/api/v1/comparar/yahoo",
        json={"itens": [item, {"ativo": "VALE3", "setup_id": "larry_williams_9_1"}]},
    ).json()
    assert r[0]["indicadores"]["trades"] == 1
    assert "VALE3" in r[1]["erro"]


# --- acompanhamento


def novo_item(cliente, **extra):
    return cliente.post(
        "/api/v1/acompanhamento/yahoo", json={"ativo": "PETR4", "setup_id": "larry_williams_9_1", **extra}
    )


def test_acompanhamento_estado_ordens_e_sem_duplicar(cliente, falsos):
    _, yahoo = falsos
    datas = datas_uteis(len(LINHAS_PRD))
    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD[:27], datas)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    item = novo_item(cliente, data_inicio=datas[0]).json()
    assert item["estado"] == "armado"
    assert item["ordens"][0]["preco"] == pytest.approx(20.61)

    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD, datas)
    assert cliente.post("/api/v1/acompanhamento/yahoo/processar").json()["processados"] == 1
    primeira = cliente.get("/api/v1/acompanhamento/yahoo").json()
    assert primeira["itens"][0]["estado"] == "sem_sinal"
    tipos = {e["tipo"] for e in primeira["eventos"]}
    assert {"sinal", "entrada", "saida_armada", "saida", "trade_encerrado"} <= tipos

    cliente.post("/api/v1/acompanhamento/yahoo/processar")
    segunda = cliente.get("/api/v1/acompanhamento/yahoo").json()
    assert len(segunda["eventos"]) == len(primeira["eventos"])


def test_acompanhamento_passa_a_mostrar_a_versao_atual_do_setup(cliente, falsos):
    from app.db import conectar

    _, yahoo = falsos
    datas = datas_uteis(len(LINHAS_PRD))
    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD, datas)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    novo_item(cliente, data_inicio=datas[0])
    with conectar() as conexao:
        conexao.execute("UPDATE itens_acompanhamento SET setup_versao = '1.0'")
    conexao.close()
    cliente.post("/api/v1/acompanhamento/yahoo/processar")
    assert cliente.get("/api/v1/acompanhamento/yahoo").json()["itens"][0]["setup_versao"] == "1.2"


def test_acompanhamento_nao_reescreve_evento_depois_de_ajuste(cliente, falsos):
    _, yahoo = falsos
    datas = datas_uteis(len(LINHAS_PRD))
    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD, datas)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    novo_item(cliente, data_inicio=datas[0])
    entrada = lambda: next(  # noqa: E731
        e for e in cliente.get("/api/v1/acompanhamento/yahoo").json()["eventos"] if e["tipo"] == "entrada"
    )
    original = entrada()
    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD, datas, fator=0.9)  # provento muda o passado
    cliente.post("/api/v1/acompanhamento/yahoo/processar")
    depois = entrada()
    assert depois["preco"] == original["preco"]
    assert depois["serie_versao"] == 1
    assert dados.origem_dados("yahoo", "PETR4")["versao"] == 2


def test_acompanhamento_item_repetido_e_por_aba(cliente, falsos):
    brapi, yahoo = falsos
    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD)
    brapi.respostas["PETR4"] = candles_de(LINHAS_PRD)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    cliente.post("/api/v1/dados/brapi/PETR4/atualizar")
    assert novo_item(cliente).status_code == 200
    assert novo_item(cliente).status_code == 409
    r = cliente.post("/api/v1/acompanhamento/brapi", json={"ativo": "PETR4", "setup_id": "larry_williams_9_1"})
    assert r.status_code == 200
    assert len(cliente.get("/api/v1/acompanhamento/yahoo").json()["itens"]) == 1


def test_acompanhamento_falha_mostra_motivo(cliente, falsos):
    _, yahoo = falsos
    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    novo_item(cliente)
    yahoo.falha = ErroProvedor("fonte_indisponivel", "Yahoo fora do ar")
    r = cliente.post("/api/v1/acompanhamento/yahoo/processar").json()
    assert r["falhas"] == {"PETR4": "Yahoo fora do ar"}
    item = cliente.get("/api/v1/acompanhamento/yahoo").json()["itens"][0]
    assert item["ultimo_erro"] == "Yahoo fora do ar"
    assert item["ultimo_pregao"]


def test_remover_item_guarda_historico(cliente, falsos):
    _, yahoo = falsos
    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    item = novo_item(cliente, data_inicio=datas_uteis(1)[0]).json()
    assert cliente.delete(f"/api/v1/acompanhamento/item/{item['id']}").status_code == 204
    r = cliente.get("/api/v1/acompanhamento/yahoo").json()
    assert r["itens"] == []
    assert r["eventos"]


# --- configurações


def test_token_nunca_volta_pela_api(cliente):
    assert cliente.get("/api/v1/configuracoes").json()["token_brapi_configurado"] is False
    r = cliente.put("/api/v1/configuracoes/token-brapi", json={"token": "abc123segredo"})
    assert r.json()["token_brapi_configurado"] is True
    corpo = cliente.get("/api/v1/configuracoes").text
    assert "abc123segredo" not in corpo
    cliente.put("/api/v1/configuracoes/token-brapi", json={"token": None})
    assert cliente.get("/api/v1/configuracoes").json()["token_brapi_configurado"] is False


def test_guardar_token_testa_com_ativo_que_exige_token_sem_gravar(cliente, falsos):
    brapi = falsos[0]
    brapi.respostas["WEGE3"] = candles_de(LINHAS_PRD)
    r = cliente.put("/api/v1/configuracoes/token-brapi", json={"token": "abc123segredo"}).json()
    assert r["teste"]["ok"] is True
    assert "abc123segredo" not in str(r)
    assert brapi.pedidos == [("WEGE3", None)]
    assert cliente.get("/api/v1/dados").json() == []


def test_token_recusado_fica_guardado_e_avisa(cliente, falsos):
    falsos[0].falha = ErroProvedor("token_recusado", "A brapi recusou o token guardado.")
    r = cliente.put("/api/v1/configuracoes/token-brapi", json={"token": "ruim"}).json()
    assert r["token_brapi_configurado"] is True
    assert r["teste"] == {"ok": False, "mensagem": "A brapi recusou o token guardado."}


def test_remover_token_nao_consulta_a_brapi(cliente, falsos):
    r = cliente.put("/api/v1/configuracoes/token-brapi", json={"token": None}).json()
    assert r["teste"] is None
    assert falsos[0].pedidos == []


def test_custos_das_configuracoes_entram_na_analise(cliente, falsos):
    falsos[1].respostas["PETR4"] = candles_de(LINHAS_PRD)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    custos = {"corretagem_por_ordem": 5, "emolumentos_pct": 0.03, "slippage_pct": 0, "capital_por_trade": 10000}
    assert cliente.put("/api/v1/configuracoes", json={"custos": custos}).status_code == 200
    t = analisar(cliente).json()["trades"][0]
    assert t["liquido_pct"] < t["bruto_pct"]


def test_setups_ocultos_sao_salvos_sem_mexer_no_resto(cliente, falsos):
    assert cliente.get("/api/v1/configuracoes").json()["setups_ocultos"] == []
    cliente.put("/api/v1/configuracoes", json={"amostra_minima": 12})
    r = cliente.put("/api/v1/configuracoes", json={"setups_ocultos": ["pfr", "didi", "pfr"]})
    assert r.status_code == 200
    assert r.json()["setups_ocultos"] == ["didi", "pfr"]
    assert r.json()["amostra_minima"] == 12
    # Salvar custos não pode limpar a lista.
    cliente.put("/api/v1/configuracoes", json={"janela_movel": 25})
    assert cliente.get("/api/v1/configuracoes").json()["setups_ocultos"] == ["didi", "pfr"]
    # Voltar a mostrar todos é uma lista vazia, que não pode ser ignorada como "campo ausente".
    assert cliente.put("/api/v1/configuracoes", json={"setups_ocultos": []}).json()["setups_ocultos"] == []


def test_setups_ocultos_recusa_id_desconhecido_e_lista_sem_nenhum_setup(cliente, falsos):
    r = cliente.put("/api/v1/configuracoes", json={"setups_ocultos": ["nao_existe"]})
    assert r.status_code == 422
    todos = [s["id"] for s in cliente.get("/api/v1/setups").json()]
    r = cliente.put("/api/v1/configuracoes", json={"setups_ocultos": todos})
    assert r.status_code == 422
    assert "Pelo menos um setup" in r.json()["mensagem"]
    assert cliente.get("/api/v1/configuracoes").json()["setups_ocultos"] == []


def test_setup_retirado_do_catalogo_some_da_lista_de_ocultos(cliente, falsos):
    from app.db import conectar

    with conectar() as conexao:
        conexao.execute("INSERT INTO configuracoes (chave, valor) VALUES ('setups_ocultos', ?)", ('["antigo", "pfr"]',))
    conexao.close()
    assert cliente.get("/api/v1/configuracoes").json()["setups_ocultos"] == ["pfr"]


def test_setup_oculto_continua_analisavel(cliente, falsos):
    """Itens de acompanhamento e comparações de um setup oculto continuam rodando."""
    falsos[1].respostas["PETR4"] = candles_de(LINHAS_PRD)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    cliente.put("/api/v1/configuracoes", json={"setups_ocultos": ["larry_williams_9_1"]})
    assert analisar(cliente).status_code == 200
    assert len(cliente.get("/api/v1/setups").json()) == 21


def test_regras_mostradas_usam_virgula_decimal(cliente, falsos):
    falsos[1].respostas["PETR4"] = candles_de(LINHAS_PRD)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    eventos = analisar(cliente).json()["trades"][0]["eventos"]
    entrada = next(e for e in eventos if e["tipo"] == "entrada")
    assert "20,61" in entrada["regra"]


def test_indice_sem_volume_nao_gera_alerta(falsos):
    _, yahoo = falsos
    yahoo.respostas["^BVSP"] = [CandleRecebido("2024-01-02", 10, 11, 9, 10, 10, 0)]
    dados.atualizar_serie("yahoo", "^BVSP")
    assert dados.alertas_da_serie("yahoo", "^BVSP") == []


# --- Início do histórico do app em 01/01/2010


def test_candles_anteriores_a_2010_nao_sao_guardados(falsos):
    _, yahoo = falsos
    datas = datas_uteis(len(LINHAS_PRD), "2009-12-14")
    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD, datas)
    dados.atualizar_serie("yahoo", "PETR4")
    linhas, _ = dados.ler_candles("yahoo", "PETR4")
    assert linhas[0]["data"] >= "2010-01-01"
    assert len(linhas) == len([d for d in datas if d >= "2010-01-01"])
    assert dados.origem_dados("yahoo", "PETR4")["tem_dados"]


def test_ativo_so_com_pregoes_antes_de_2010_e_erro_claro(falsos):
    _, yahoo = falsos
    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD[:5], datas_uteis(5, "2005-03-01"))
    with pytest.raises(ErroProvedor, match="desde 01/01/2010"):
        dados.atualizar_serie("yahoo", "PETR4")


def test_banco_antigo_perde_candles_anteriores_a_2010_e_muda_de_versao(falsos):
    _, yahoo = falsos
    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD, datas_uteis(len(LINHAS_PRD), "2010-01-04"))
    dados.atualizar_serie("yahoo", "PETR4")
    antes = dados.origem_dados("yahoo", "PETR4")
    # Simula o que uma versão antiga do app guardava: um candle de 2003.
    conexao = db.conectar()
    with conexao:
        serie_id = conexao.execute("SELECT id FROM series WHERE ativo = 'PETR4'").fetchone()["id"]
        conexao.execute(
            "INSERT INTO candles (serie_id, data, abertura, maxima, minima, fechamento, volume) "
            "VALUES (?, '2003-08-05', 67.5, 67.5, 6.8, 6.85, 1000)",
            (serie_id,),
        )
    conexao.close()
    assert dados.ler_candles("yahoo", "PETR4")[0][0]["data"] >= "2010-01-01"

    assert dados.aplicar_inicio_historico() == 1
    depois = dados.origem_dados("yahoo", "PETR4")
    assert depois["versao"] == antes["versao"] + 1
    assert depois["hash"] == antes["hash"]  # o hash volta a ser o da série sem o candle antigo
    conexao = db.conectar()
    assert conexao.execute("SELECT COUNT(*) FROM candles WHERE data < '2010-01-01'").fetchone()[0] == 0
    conexao.close()
    assert dados.aplicar_inicio_historico() == 0


def test_datas_antes_de_2010_sao_recusadas(cliente, falsos):
    _, yahoo = falsos
    yahoo.respostas["PETR4"] = candles_de(LINHAS_PRD)
    cliente.post("/api/v1/dados/yahoo/PETR4/atualizar")
    pedido = {"ativo": "PETR4", "setup_id": "larry_williams_9_1"}
    for corpo in ({"inicio": "2009-12-31"}, {"fim": "2009-12-31"}):
        r = cliente.post("/api/v1/analise/yahoo", json={**pedido, **corpo})
        assert r.status_code == 422
        assert "01/01/2010" in r.json()["mensagem"]
    r = cliente.post("/api/v1/comparar/yahoo", json={"itens": [pedido], "inicio": "2009-06-01"})
    assert r.status_code == 422
    r = cliente.post("/api/v1/acompanhamento/yahoo", json={**pedido, "data_inicio": "2009-06-01"})
    assert r.status_code == 422
    assert cliente.post("/api/v1/analise/yahoo", json={**pedido, "inicio": "2010-01-01"}).status_code == 200


def test_configuracoes_informam_o_inicio_do_historico(cliente):
    assert cliente.get("/api/v1/configuracoes").json()["inicio_historico"] == "2010-01-01"
