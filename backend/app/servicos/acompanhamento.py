"""Acompanhamento simulado: o mesmo motor do backtest, com histórico de eventos que nunca é sobrescrito."""
from __future__ import annotations

import json
from dataclasses import asdict

from app.db import conectar
from app.erros import ErroApp
from app.motor.custos import Custos
from app.motor.motor import TEXTO_MOTIVO_SAIDA, executar
from app.servicos import dados
from app.servicos.analise import obter_setup_ou_erro, validar_parametros
from app.servicos.configuracoes import ler_configuracoes


def _item_para_dict(linha) -> dict:
    item = dict(linha)
    item["params"] = json.loads(item["params"])
    item["custos"] = json.loads(item["custos"])
    item["ordens"] = json.loads(item["ordens"])
    item["posicao"] = json.loads(item["posicao"]) if item["posicao"] else None
    item["ligado"] = bool(item["ligado"])
    return item


def listar_itens(fonte: str) -> list[dict]:
    dados.validar_fonte(fonte)
    conexao = conectar()
    linhas = conexao.execute(
        "SELECT * FROM itens_acompanhamento WHERE fonte = ? AND ligado = 1 ORDER BY ativo, id", (fonte,)
    ).fetchall()
    conexao.close()
    itens = [_item_para_dict(l) for l in linhas]
    for item in itens:
        setup = obter_setup_ou_erro(item["setup_id"])
        item["setup_nome"] = setup.nome
    return itens


def criar_item(fonte: str, ativo: str, setup_id: str, params: dict | None, data_inicio: str | None) -> dict:
    """Cada item pertence a uma aba. Mudar parâmetros significa abrir outro item, sem reescrever o passado."""
    dados.validar_fonte(fonte)
    codigo = dados.normalizar_codigo(ativo)
    setup = obter_setup_ou_erro(setup_id)
    parametros = validar_parametros(setup, params or {})
    dados.validar_periodo(data_inicio)
    linhas, _ = dados.ler_candles(fonte, codigo)
    if not linhas:
        raise ErroApp("sem_dados", f"Baixe os dados de {codigo} nesta aba antes de acompanhar.", 404)
    inicio = data_inicio or linhas[-1]["data"]

    conexao = conectar()
    params_json = parametros.model_dump_json()
    repetido = conexao.execute(
        """SELECT id FROM itens_acompanhamento WHERE fonte = ? AND ativo = ? AND setup_id = ? AND params = ?
           AND ligado = 1""",
        (fonte, codigo, setup_id, params_json),
    ).fetchone()
    if repetido:
        conexao.close()
        raise ErroApp("item_repetido", f"{codigo} já está em acompanhamento com estes parâmetros nesta aba.", 409)
    with conexao:
        cursor = conexao.execute(
            """INSERT INTO itens_acompanhamento (fonte, ativo, setup_id, setup_versao, params, custos, data_inicio, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fonte, codigo, setup_id, setup.versao, params_json,
                Custos(**ler_configuracoes()["custos"]).model_dump_json(), inicio, dados.agora_iso(),
            ),
        )  # fmt: skip
        item_id = cursor.lastrowid
    conexao.close()
    _processar_item(item_id)
    return next(i for i in listar_itens(fonte) if i["id"] == item_id)


def remover_item(item_id: int) -> None:
    """Sai da lista, mas o histórico de eventos continua guardado."""
    conexao = conectar()
    with conexao:
        conexao.execute("UPDATE itens_acompanhamento SET ligado = 0 WHERE id = ?", (item_id,))
    conexao.close()


def _processar_item(item_id: int) -> None:
    conexao = conectar()
    item = conexao.execute("SELECT * FROM itens_acompanhamento WHERE id = ?", (item_id,)).fetchone()
    conexao.close()
    setup = obter_setup_ou_erro(item["setup_id"])
    parametros = validar_parametros(setup, json.loads(item["params"]))
    linhas, serie = dados.ler_candles(item["fonte"], item["ativo"])
    candles, _ = dados.serie_para_motor(linhas)
    resultado = executar(candles, setup, parametros, inicio=item["data_inicio"])

    eventos: list[tuple] = []
    for sinal in resultado.sinais:
        for e in sinal.eventos:
            eventos.append((e.data, e.tipo, e.preco, e.regra))
    for trade in resultado.trades:
        for e in trade.eventos:
            eventos.append((e.data, e.tipo, e.preco, e.regra))
        if trade.motivo_saida:
            eventos.append(
                (
                    trade.saida_data,
                    "trade_encerrado",
                    trade.saida_preco,
                    f"{TEXTO_MOTIVO_SAIDA[trade.motivo_saida]}: "
                    f"{(trade.saida_preco / trade.entrada_preco - 1) * 100:+.2f}% bruto.".replace(".", ",", 1),
                )
            )
    agora = dados.agora_iso()
    conexao = conectar()
    with conexao:
        # OR IGNORE garante as duas regras: repetir não duplica e o registro original nunca é alterado.
        conexao.executemany(
            """INSERT OR IGNORE INTO eventos_acompanhamento
               (item_id, data, tipo, preco, descricao, serie_versao, registrado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [(item_id, d, t, p, r, serie["versao"], agora) for d, t, p, r in sorted(eventos, key=lambda x: x[0])],
        )
        conexao.execute(
            """UPDATE itens_acompanhamento SET setup_versao = ?, estado = ?, ordens = ?, posicao = ?, ultimo_pregao = ?,
               ultimo_erro = NULL, ultimo_erro_em = NULL WHERE id = ?""",
            (
                setup.versao,  # o item sempre roda a regra atual; a tela precisa dizer qual é
                resultado.estado,
                json.dumps([asdict(o) for o in resultado.ordens_ativas], ensure_ascii=False),
                json.dumps(asdict(resultado.posicao)) if resultado.posicao else None,
                candles.datas[-1] if candles.datas else None,
                item_id,
            ),
        )
    conexao.close()


def processar(fonte: str) -> dict:
    """Atualiza os candles dos ativos acompanhados e recalcula. Uma falha fica registrada, sem parar os demais."""
    dados.validar_fonte(fonte)
    itens = listar_itens(fonte)
    falhas: dict[str, str] = {}
    for ativo in sorted({i["ativo"] for i in itens}):
        try:
            dados.atualizar_serie(fonte, ativo)
        except ErroApp as erro:
            falhas[ativo] = erro.mensagem

    conexao = conectar()
    with conexao:
        for item in itens:
            if item["ativo"] in falhas:
                conexao.execute(
                    "UPDATE itens_acompanhamento SET ultimo_erro = ?, ultimo_erro_em = ? WHERE id = ?",
                    (falhas[item["ativo"]], dados.agora_iso(), item["id"]),
                )
    conexao.close()
    for item in itens:
        if item["ativo"] not in falhas:
            _processar_item(item["id"])
    return {"processados": len(itens) - sum(i["ativo"] in falhas for i in itens), "falhas": falhas}


def listar_eventos(fonte: str, limite: int = 200) -> list[dict]:
    dados.validar_fonte(fonte)
    conexao = conectar()
    linhas = conexao.execute(
        """SELECT e.*, i.ativo, i.data_inicio FROM eventos_acompanhamento e
           JOIN itens_acompanhamento i ON i.id = e.item_id
           WHERE i.fonte = ? ORDER BY e.data DESC, e.id DESC LIMIT ?""",
        (fonte, limite),
    ).fetchall()
    ultimo = conexao.execute(
        """SELECT MAX(c.data) AS fim FROM candles c JOIN series s ON s.id = c.serie_id
           WHERE s.fonte = ? AND s.ativo IN (SELECT ativo FROM itens_acompanhamento WHERE fonte = ?)""",
        (fonte, fonte),
    ).fetchone()
    conexao.close()
    corte = dados.inicio_janela_visivel(fonte, ultimo["fim"])
    return [dict(l) for l in linhas if not corte or l["data"] >= corte]
