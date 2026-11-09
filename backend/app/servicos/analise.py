"""Aplica um setup a uma série guardada e monta o resultado de uma aba. Nada combina as duas fontes."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date

from pydantic import BaseModel, ValidationError

from app.ativos_b3 import CODIGO_IBOVESPA
from app.db import conectar
from app.erros import ErroApp
from app.motor.custos import Custos, resultado_trade
from app.motor.metricas import calcular_painel
from app.motor.motor import TEXTO_AVISO, TEXTO_MOTIVO_SAIDA, executar
from app.motor.tipos import Trade
from app.servicos import dados
from app.servicos.configuracoes import ler_configuracoes
from app.setups.base import Setup
from app.setups.registro import SETUPS, obter_setup

AVISO_SIMULACAO = (
    "Resultados são simulações, não representam ordens executadas e não são recomendação de "
    "investimento. Resultado passado não garante resultado futuro."
)


def descrever_setup(setup: Setup) -> dict:
    return {
        "id": setup.id,
        "versao": setup.versao,
        "nome": setup.nome,
        "descricao": setup.descricao,
        "familia": setup.familia,
        "origem": setup.origem,
        "direcao": setup.direcao,
        "esquema": setup.Parametros.model_json_schema(),
        "padroes": setup.Parametros().model_dump(),
    }


def listar_setups() -> list[dict]:
    return [descrever_setup(s) for s in SETUPS.values()]


def validar_parametros(setup: Setup, params: dict) -> BaseModel:
    try:
        return setup.Parametros(**params)
    except ValidationError as erro:
        primeiro = erro.errors()[0]
        campo = str(primeiro["loc"][0]) if primeiro["loc"] else ""
        titulo = setup.Parametros.model_fields.get(campo)
        rotulo = titulo.title if titulo and titulo.title else campo
        raise ErroApp("parametro_invalido", f"{rotulo}: valor fora do permitido.", 422) from erro


def obter_setup_ou_erro(setup_id: str) -> Setup:
    setup = obter_setup(setup_id)
    if setup is None:
        raise ErroApp("setup_desconhecido", f"Setup desconhecido: {setup_id}.", 404)
    return setup


def _trade_para_dict(trade: Trade, custos: Custos) -> dict:
    saida = asdict(trade)
    saida.update(resultado_trade(trade, custos))
    saida["motivo_saida_texto"] = TEXTO_MOTIVO_SAIDA.get(trade.motivo_saida or "", "")
    saida["avisos_texto"] = [TEXTO_AVISO.get(a, a) for a in trade.avisos]
    return saida


def _dentro_da_janela(trade: dict, corte: str | None) -> bool:
    """Na janela da brapi ficam os trades encerrados nela e os que seguem abertos, mesmo iniciados antes."""
    return corte is None or trade["aberto"] or trade["saida_data"] >= corte


def _curva_referencia(datas: list[str], precos: dict[str, float]) -> list[dict]:
    """Base 100 no início do período. Datas sem preço repetem o último valor conhecido."""
    pontos = []
    base = None
    ultimo = None
    for data in datas:
        preco = precos.get(data)
        if preco:
            ultimo = preco
            base = base or preco
        if base:
            pontos.append({"data": data, "valor": ultimo / base * 100})
    return pontos


def _salvar_execucao(
    fonte: str,
    codigo: str,
    serie,
    setup: Setup,
    params: BaseModel,
    custos: Custos,
    inicio: str | None,
    fim: str | None,
    trades: list[dict],
    sinais: list[dict],
) -> int:
    """Guarda ativo, setup, versão, parâmetros, custos, fonte e período. Repetir a análise não duplica."""
    params_json = params.model_dump_json()
    custos_json = custos.model_dump_json()
    chave = hashlib.sha256(
        json.dumps(
            [fonte, codigo, serie["hash"], setup.id, setup.versao, params_json, custos_json, inicio, fim]
        ).encode()
    ).hexdigest()
    conexao = conectar()
    with conexao:
        existente = conexao.execute("SELECT id FROM execucoes WHERE chave = ?", (chave,)).fetchone()
        if existente:
            execucao_id = existente["id"]
        else:
            cursor = conexao.execute(
                """INSERT INTO execucoes (chave, fonte, ativo, serie_versao, serie_hash, setup_id, setup_versao,
                   params, custos, inicio, fim, criada_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    chave, fonte, codigo, serie["versao"], serie["hash"], setup.id, setup.versao,
                    params_json, custos_json, inicio, fim, dados.agora_iso(),
                ),
            )  # fmt: skip
            execucao_id = cursor.lastrowid
            conexao.executemany(
                """INSERT INTO trades (execucao_id, numero, sinal_data, entrada_data, entrada_preco, stop, risco, alvo,
                   saida_data, saida_preco, motivo_saida, duracao_pregoes, aberto, bruto_pct, bruto_r, bruto_reais,
                   liquido_pct, liquido_r, liquido_reais, avisos, eventos)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        execucao_id, t["numero"], t["sinal_data"], t["entrada_data"], t["entrada_preco"], t["stop"],
                        t["risco"], t["alvo"], t["saida_data"], t["saida_preco"], t["motivo_saida"],
                        t["duracao_pregoes"], int(t["aberto"]), t["bruto_pct"], t["bruto_r"], t["bruto_reais"],
                        t["liquido_pct"], t["liquido_r"], t["liquido_reais"],
                        json.dumps(t["avisos"]), json.dumps(t["eventos"], ensure_ascii=False),
                    )
                    for t in trades
                ],
            )  # fmt: skip
            conexao.executemany(
                "INSERT OR REPLACE INTO sinais (execucao_id, data, gatilho, stop, situacao, motivo) VALUES (?, ?, ?, ?, ?, ?)",
                [(execucao_id, s["data"], s["gatilho"], s["stop"], s["situacao"], s["motivo"]) for s in sinais],
            )
    conexao.close()
    return execucao_id


def _avisos_analise(
    fonte: str, indicadores: dict, resultado_avisos: list[str], excluidos: int, qtd_alertas: int,
    linhas: list, serie, custos: Custos, amostra_minima: int,
) -> list[dict]:  # fmt: skip
    avisos = [{"tipo": "aquecimento", "nivel": "alerta", "texto": a} for a in resultado_avisos]
    if indicadores["trades"] < amostra_minima:
        avisos.append(
            {
                "tipo": "amostra_pequena",
                "nivel": "info",
                "texto": f"Amostra pequena: {indicadores['trades']} trades encerrados, menos de {amostra_minima}. "
                "As métricas têm baixa confiabilidade.",
            }
        )
    if fonte == "brapi":
        avisos.append(
            {
                "tipo": "historico_curto",
                "nivel": "info",
                "texto": "Esta aba mostra só os 3 meses mais recentes, limite do plano Gratuito da brapi. "
                "Mapa mensal, resultado anual e taxa móvel têm pouca informação aqui.",
            }
        )
    elif linhas and (date.fromisoformat(linhas[-1]["data"]) - date.fromisoformat(linhas[0]["data"])).days < 3650:
        avisos.append(
            {
                "tipo": "historico_curto",
                "nivel": "info",
                "texto": f"O Yahoo tem menos de 10 anos de histórico deste ativo (desde {_data_br(linhas[0]['data'])}).",
            }
        )
    if qtd_alertas:
        texto = f"{qtd_alertas} alertas de qualidade nos candles deste período."
        if excluidos:
            texto += f" {excluidos} candles inválidos ficaram fora da simulação."
        avisos.append({"tipo": "qualidade", "nivel": "alerta", "texto": texto})
    if indicadores["trades_com_aviso"]:
        avisos.append(
            {
                "tipo": "premissa",
                "nivel": "info",
                "texto": f"{indicadores['trades_com_aviso']} trades dependem de premissa sobre a ordem dos eventos "
                "dentro do candle.",
            }
        )
    if not (custos.corretagem_por_ordem or custos.emolumentos_pct or custos.slippage_pct):
        avisos.append(
            {
                "tipo": "custos_zerados",
                "nivel": "info",
                "texto": "Custos zerados: o resultado líquido é igual ao bruto. Defina os custos em Configurações.",
            }
        )
    if serie["aviso_rebase"]:
        avisos.append({"tipo": "rebase", "nivel": "alerta", "texto": serie["aviso_rebase"]})
    return avisos


def _data_br(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def analisar(
    fonte: str,
    ativo: str,
    setup_id: str,
    params: dict | None = None,
    custos: dict | None = None,
    inicio: str | None = None,
    fim: str | None = None,
    enxuto: bool = False,
) -> dict:
    dados.validar_fonte(fonte)
    codigo = dados.normalizar_codigo(ativo)
    setup = obter_setup_ou_erro(setup_id)
    parametros = validar_parametros(setup, params or {})
    configuracoes = ler_configuracoes()
    custos_validos = Custos(**(custos if custos is not None else configuracoes["custos"]))
    dados.validar_periodo(inicio, fim)

    linhas, serie = dados.ler_candles(fonte, codigo)
    origem = dados.origem_dados(fonte, codigo)
    if not linhas:
        raise ErroApp("sem_dados", f"Ainda não há dados de {codigo} nesta aba. Baixe os candles primeiro.", 404)

    candles, excluidos = dados.serie_para_motor(linhas)
    resultado = executar(candles, setup, parametros, inicio=inicio, fim=fim)

    corte = dados.inicio_janela_visivel(fonte, linhas[-1]["data"])
    desde = max(filter(None, [corte, inicio]), default=None)
    ate = fim or candles.datas[-1] if candles.datas else fim
    indices = [
        i for i, d in enumerate(candles.datas) if (not desde or d >= desde) and (not ate or d <= ate)
    ]
    datas = [candles.datas[i] for i in indices]

    trades = [_trade_para_dict(t, custos_validos) for t in resultado.trades]
    trades = [t for t in trades if _dentro_da_janela(t, corte)]
    sinais = [
        {
            "data": s.data,
            "gatilho": s.gatilho,
            "stop": s.stop,
            "situacao": s.situacao,
            "motivo": s.motivo,
            "data_fim": s.data_fim,
        }
        for s in resultado.sinais
        if not corte or s.data >= corte
    ]

    painel = calcular_painel(trades, datas, configuracoes["janela_movel"])
    alertas = dados.avaliar_qualidade(linhas, desde)
    execucao_id = _salvar_execucao(
        fonte, codigo, serie, setup, parametros, custos_validos, inicio, fim, trades, sinais
    )

    fechamentos = {candles.datas[i]: float(candles.fechamento[i]) for i in indices}
    ibov_linhas, _ = dados.ler_candles(fonte, CODIGO_IBOVESPA)
    ibov = {l["data"]: l["fechamento"] for l in ibov_linhas if l["fechamento"]}
    curvas = {
        "buy_and_hold": _curva_referencia(datas, fechamentos),
        "ibovespa": _curva_referencia(datas, ibov),
    }

    base = {
        "execucao_id": execucao_id,
        "fonte": fonte,
        "ativo": codigo,
        "setup": {"id": setup.id, "nome": setup.nome, "versao": setup.versao},
        "params": parametros.model_dump(),
        "custos": custos_validos.model_dump(),
        "periodo": {"inicio": datas[0] if datas else None, "fim": datas[-1] if datas else None},
        "origem": origem,
        "avisos": _avisos_analise(
            fonte, painel["indicadores"], resultado.avisos, excluidos, len(alertas), linhas, serie,
            custos_validos, configuracoes["amostra_minima"],
        ),  # fmt: skip
        "painel": painel,
        "janela_movel": configuracoes["janela_movel"],
        "referencias": curvas,
        "ibovespa_disponivel": bool(curvas["ibovespa"]),
        "simulacao": AVISO_SIMULACAO,
    }
    if enxuto:
        return base

    return {
        **base,
        "candles": [
            {
                "data": candles.datas[i],
                "abertura": float(candles.abertura[i]),
                "maxima": float(candles.maxima[i]),
                "minima": float(candles.minima[i]),
                "fechamento": float(candles.fechamento[i]),
                "volume": float(candles.volume[i]),
            }
            for i in indices
        ],
        "indicadores": [
            {
                "id": nome,
                "rotulo": rotulo,
                "painel": "inferior" if nome in setup.indicadores_em_painel(parametros) else "preco",
                "painel_indice": next((n for n, grupo in enumerate(setup.paineis(parametros), 1) if nome in grupo), 0),
                "pontos": [
                    {"data": candles.datas[i], "valor": float(resultado.indicadores[nome][i])}
                    for i in indices
                    if resultado.indicadores[nome][i] == resultado.indicadores[nome][i]  # sem NaN
                ],
            }
            for nome, rotulo in setup.indicadores_declarados(parametros).items()
            if nome in resultado.indicadores
        ],
        "trades": trades,
        "sinais": sinais,
        "estado": resultado.estado,
        "ordens": [asdict(o) for o in resultado.ordens_ativas],
        "alertas_qualidade": alertas,
    }


def _numero_br(valor, casas: int = 2) -> str:
    if valor is None:
        return ""
    return f"{valor:.{casas}f}".replace(".", ",")


def exportar_trades_csv(execucao_id: int) -> tuple[str, str]:
    """CSV no padrão brasileiro: separador ponto e vírgula, decimal com vírgula e data DD/MM/AAAA."""
    conexao = conectar()
    execucao = conexao.execute("SELECT * FROM execucoes WHERE id = ?", (execucao_id,)).fetchone()
    if not execucao:
        conexao.close()
        raise ErroApp("execucao_desconhecida", "Execução não encontrada.", 404)
    trades = conexao.execute("SELECT * FROM trades WHERE execucao_id = ? ORDER BY numero", (execucao_id,)).fetchall()
    conexao.close()

    linhas = [
        ";".join(
            [
                "Número", "Fonte", "Ativo", "Setup", "Versão do setup", "Sinal", "Entrada", "Preço de entrada", "Stop",
                "Saída", "Preço de saída", "Motivo da saída", "Duração (pregões)", "Situação",
                "Bruto %", "Bruto R", "Líquido %", "Líquido R", "Líquido R$", "Avisos",
            ]
        )
    ]  # fmt: skip
    for t in trades:
        linhas.append(
            ";".join(
                [
                    str(t["numero"]),
                    execucao["fonte"],
                    execucao["ativo"],
                    execucao["setup_id"],
                    execucao["setup_versao"],
                    _data_br(t["sinal_data"]),
                    _data_br(t["entrada_data"]),
                    _numero_br(t["entrada_preco"], 4),
                    _numero_br(t["stop"], 4),
                    _data_br(t["saida_data"]) if t["saida_data"] else "",
                    _numero_br(t["saida_preco"], 4),
                    TEXTO_MOTIVO_SAIDA.get(t["motivo_saida"] or "", ""),
                    str(t["duracao_pregoes"]),
                    "Aberto" if t["aberto"] else "Encerrado",
                    _numero_br(t["bruto_pct"]),
                    _numero_br(t["bruto_r"]),
                    _numero_br(t["liquido_pct"]),
                    _numero_br(t["liquido_r"]),
                    _numero_br(t["liquido_reais"]),
                    " | ".join(json.loads(t["avisos"])),
                ]
            )
        )
    nome = f"trades_{execucao['ativo']}_{execucao['fonte']}_{execucao_id}.csv"
    return "﻿" + "\r\n".join(linhas) + "\r\n", nome


def comparar(fonte: str, itens: list[dict], custos: dict | None, inicio: str | None, fim: str | None) -> list[dict]:
    """Até 5 itens lado a lado, sempre dentro da mesma aba. Um item sem dados não derruba os outros."""
    if len(itens) > 5:
        raise ErroApp("limite_comparacao", "A comparação aceita até 5 itens.", 422)
    dados.validar_periodo(inicio, fim)
    saida = []
    for item in itens:
        try:
            r = analisar(fonte, item["ativo"], item["setup_id"], item.get("params"), custos, inicio, fim, enxuto=True)
            saida.append(
                {
                    "ativo": r["ativo"],
                    "setup": r["setup"],
                    "params": r["params"],
                    "indicadores": r["painel"]["indicadores"],
                    "curva": [{"data": p["data"], "capital": p["capital"]} for p in r["painel"]["curva"]],
                    "periodo": r["periodo"],
                }
            )
        except ErroApp as erro:
            saida.append({"ativo": item["ativo"], "erro": erro.mensagem})
    return saida
