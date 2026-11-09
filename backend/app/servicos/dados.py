"""Importação, armazenamento e validação de candles, sempre separados por fonte."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from statistics import median

import numpy as np

from app.ativos_b3 import CODIGO_IBOVESPA
from app.calendario import (
    INICIO_HISTORICO,
    INICIO_HISTORICO_BR,
    candle_em_formacao,
    eh_pregao,
    menos_tres_meses,
    pregoes_faltantes,
)
from app.db import conectar
from app.erros import ErroApp, ErroProvedor
from app.motor.tipos import SerieCandles
from app.provedores.base import CandleRecebido, Provedor
from app.provedores.brapi import ProvedorBrapi
from app.provedores.yahoo import ProvedorYahoo
from app.servicos.configuracoes import obter_token_brapi

TOLERANCIA_AJUSTE = 0.0005  # diferença relativa abaixo disso é arredondamento da fonte, não provento
SOBREPOSICAO_YAHOO_DIAS = 10
CODIGO_VALIDO = re.compile(r"^[A-Z]{4}\d{1,2}$")

ATIVO_TESTE_TOKEN = "WEGE3"

PROVEDORES: dict[str, Provedor] = {
    "brapi": ProvedorBrapi(obter_token_brapi),
    "yahoo": ProvedorYahoo(),
}


def agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validar_fonte(fonte: str) -> str:
    if fonte not in PROVEDORES:
        raise ErroApp("fonte_invalida", f"Fonte desconhecida: {fonte}.", 404)
    return fonte


def normalizar_codigo(codigo: str) -> str:
    codigo = codigo.strip().upper().removesuffix(".SA")
    if codigo != CODIGO_IBOVESPA and not CODIGO_VALIDO.match(codigo):
        raise ErroApp("codigo_invalido", f"“{codigo}” não é um código de ação da B3, como PETR4.", 400)
    return codigo


def validar_periodo(inicio: str | None, fim: str | None = None) -> None:
    """Nenhuma data de análise pode ser anterior ao início do histórico do app."""
    for valor, rotulo in ((inicio, "inicial"), (fim, "final")):
        if valor and valor < INICIO_HISTORICO:
            raise ErroApp(
                "periodo_invalido",
                f"A data {rotulo} não pode ser anterior a {INICIO_HISTORICO_BR}, início do histórico do app.",
                422,
            )
    if inicio and fim and inicio > fim:
        raise ErroApp("periodo_invalido", "A data inicial é posterior à data final.", 422)


def buscar_ativos(termo: str, limite: int = 12) -> list[dict]:
    """Sem termo, devolve a lista inteira: é o que aparece ao abrir o campo de adicionar ativo."""
    termo = termo.strip()
    conexao = conectar()
    if not termo:
        linhas = conexao.execute("SELECT codigo, nome FROM ativos WHERE tipo = 'acao' ORDER BY codigo").fetchall()
        conexao.close()
        return [dict(l) for l in linhas]
    padrao = f"%{termo}%"
    linhas = conexao.execute(
        """SELECT codigo, nome FROM ativos
           WHERE tipo = 'acao' AND (codigo LIKE ? OR nome LIKE ?)
           ORDER BY CASE WHEN codigo LIKE ? THEN 0 ELSE 1 END, codigo LIMIT ?""",
        (padrao, padrao, f"{termo}%", limite),
    ).fetchall()
    conexao.close()
    return [dict(l) for l in linhas]


def testar_token_brapi() -> dict:
    """Pede à brapi um ativo que exige token. Nada é gravado: serve só para dizer se o token foi aceito."""
    try:
        PROVEDORES["brapi"].buscar(ATIVO_TESTE_TOKEN)
    except ErroProvedor as erro:
        return {"ok": False, "mensagem": erro.mensagem}
    return {"ok": True, "mensagem": f"A brapi aceitou o token: {ATIVO_TESTE_TOKEN}, que exige token, respondeu."}


def _ajustar(c: CandleRecebido) -> tuple[float | None, ...]:
    """Deriva o OHLC ajustado. A brapi e o Yahoo entregam OHLC sem ajuste junto com o fechamento ajustado."""
    fator = 1.0
    if c.ajustado is not None and c.fechamento:
        fator = c.ajustado / c.fechamento
    return tuple(None if v is None else v * fator for v in (c.abertura, c.maxima, c.minima, c.fechamento))


def _linha(serie_id: int, c: CandleRecebido, fator_rebase: float = 1.0, quebra: int = 0) -> tuple:
    a, ma, mi, f = _ajustar(c)
    return (
        serie_id, c.data, a, ma, mi, f, c.volume,
        c.abertura, c.maxima, c.minima, c.fechamento, c.ajustado,
        fator_rebase, quebra,
    )  # fmt: skip


INSERIR_CANDLE = """INSERT OR REPLACE INTO candles
    (serie_id, data, abertura, maxima, minima, fechamento, volume,
     recebido_abertura, recebido_maxima, recebido_minima, recebido_fechamento, recebido_ajustado,
     fator_rebase, quebra)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""


def _recalcular_hash(conexao: sqlite3.Connection, serie_id: int) -> str:
    resumo = hashlib.sha256()
    for linha in conexao.execute(
        "SELECT data, abertura, maxima, minima, fechamento, volume FROM candles WHERE serie_id = ? ORDER BY data",
        (serie_id,),
    ):
        resumo.update(repr(tuple(linha)).encode())
    return resumo.hexdigest()


def _razoes_comuns(
    conexao: sqlite3.Connection, serie_id: int, novos: list[CandleRecebido]
) -> list[tuple[str, float]]:
    """Razão entre o fechamento ajustado que chegou e o guardado, nos pregões em comum, do mais antigo ao mais novo."""
    guardados = {
        l["data"]: l["fechamento"]
        for l in conexao.execute("SELECT data, fechamento FROM candles WHERE serie_id = ?", (serie_id,))
    }
    razoes = []
    for c in novos:
        antigo = guardados.get(c.data)
        fechamento = _ajustar(c)[3]
        if antigo and fechamento:
            razoes.append((c.data, fechamento / antigo))
    return razoes


def _mesclar_com_rebase(
    conexao: sqlite3.Connection, serie_id: int, novos: list[CandleRecebido]
) -> tuple[bool, str | None]:
    """Acúmulo da brapi: guarda o que sai da janela e reaplica a base de ajuste nos candles antigos.

    Devolve (série mudou de versão, aviso). Quem sai da janela não pode ser baixado de novo.
    """
    razoes = _razoes_comuns(conexao, serie_id, novos)
    primeira_nova = novos[0].data
    ha_antigos = conexao.execute(
        "SELECT 1 FROM candles WHERE serie_id = ? AND data < ? LIMIT 1", (serie_id, primeira_nova)
    ).fetchone()
    mudou = False
    aviso = None
    quebra_em = None

    if razoes and ha_antigos:
        # Um provento novo muda a base de todos os candles anteriores a ele; o mais antigo em comum dá o fator.
        fator = razoes[0][1]
        valores = [r for _, r in razoes]
        fator_unico = max(abs(r - median(valores)) for r in valores) <= TOLERANCIA_AJUSTE
        if not fator_unico:
            aviso = (
                "Os pregões em comum não têm um fator de ajuste único. O rebase usou o fator do "
                f"pregão mais antigo em comum ({fator:.4f}) e merece conferência."
            )
        if abs(fator - 1) > TOLERANCIA_AJUSTE:
            conexao.execute(
                """UPDATE candles SET abertura = abertura * ?, maxima = maxima * ?, minima = minima * ?,
                   fechamento = fechamento * ?, fator_rebase = fator_rebase * ?
                   WHERE serie_id = ? AND data < ?""",
                (fator, fator, fator, fator, fator, serie_id, primeira_nova),
            )
            mudou = True
    elif razoes:
        mudou = any(abs(r - 1) > TOLERANCIA_AJUSTE for _, r in razoes)
    elif ha_antigos:
        # Ficou mais tempo sem atualizar do que a janela cobre: a parte perdida não volta mais.
        quebra_em = primeira_nova
        mudou = True
        aviso = (
            f"A atualização ficou atrasada e há uma lacuna antes de {primeira_nova}: "
            "os pregões perdidos não podem mais ser obtidos, e os indicadores recomeçam depois dela."
        )

    quebras = {
        l["data"]
        for l in conexao.execute("SELECT data FROM candles WHERE serie_id = ? AND quebra = 1", (serie_id,))
    }
    conexao.executemany(
        INSERIR_CANDLE,
        [_linha(serie_id, c, 1.0, int(c.data == quebra_em or c.data in quebras)) for c in novos],
    )
    return mudou, aviso


def _mesclar_yahoo(
    conexao: sqlite3.Connection, serie_id: int, novos: list[CandleRecebido], provedor: Provedor, codigo: str
) -> bool:
    """Atualização incremental. Se um ajuste mudou os preços antigos, baixa e troca a série inteira."""
    razoes = _razoes_comuns(conexao, serie_id, novos)
    if any(abs(r - 1) > TOLERANCIA_AJUSTE for _, r in razoes):
        completos = _filtrar_recebidos(provedor.buscar(codigo))
        conexao.execute("DELETE FROM candles WHERE serie_id = ?", (serie_id,))
        conexao.executemany(INSERIR_CANDLE, [_linha(serie_id, c) for c in completos])
        return True
    conexao.executemany(INSERIR_CANDLE, [_linha(serie_id, c) for c in novos])
    return False


def _filtrar_recebidos(candles: list[CandleRecebido]) -> list[CandleRecebido]:
    """Tira o candle do dia em formação e tudo o que vem antes do início do histórico do app."""
    return [c for c in candles if c.data >= INICIO_HISTORICO and not candle_em_formacao(c.data)]


def aplicar_inicio_historico() -> int:
    """Apaga candles anteriores ao início do histórico, guardados por versões antigas do app.

    Só o Yahoo tem candles tão antigos, e eles podem ser baixados de novo. A série muda de versão e de hash,
    então análises antigas não são reaproveitadas. Devolve quantas séries mudaram.
    """
    conexao = conectar()
    with conexao:
        ids = [
            l["serie_id"]
            for l in conexao.execute(
                "SELECT DISTINCT serie_id FROM candles WHERE data < ?", (INICIO_HISTORICO,)
            ).fetchall()
        ]
        for serie_id in ids:
            conexao.execute("DELETE FROM candles WHERE serie_id = ? AND data < ?", (serie_id, INICIO_HISTORICO))
            conexao.execute(
                "UPDATE series SET versao = versao + 1, hash = ? WHERE id = ?",
                (_recalcular_hash(conexao, serie_id), serie_id),
            )
    conexao.close()
    return len(ids)


def _registrar_falha(fonte: str, codigo: str, mensagem: str) -> None:
    conexao = conectar()
    with conexao:
        conexao.execute(
            "UPDATE series SET ultimo_erro = ?, ultimo_erro_em = ? WHERE ativo = ? AND fonte = ?",
            (mensagem, agora_iso(), codigo, fonte),
        )
    conexao.close()


def atualizar_serie(fonte: str, codigo: str) -> dict:
    """Baixa o que falta. Uma falha mantém o cache intacto, fica registrada e só afeta esta fonte."""
    validar_fonte(fonte)
    codigo = normalizar_codigo(codigo)
    provedor = PROVEDORES[fonte]

    conexao = conectar()
    atual = conexao.execute(
        "SELECT s.id, MAX(c.data) AS fim FROM series s LEFT JOIN candles c ON c.serie_id = s.id "
        "WHERE s.ativo = ? AND s.fonte = ? GROUP BY s.id",
        (codigo, fonte),
    ).fetchone()
    conexao.close()

    desde = None
    if atual and atual["fim"] and not provedor.acumula:
        desde = (date.fromisoformat(atual["fim"]) - timedelta(days=SOBREPOSICAO_YAHOO_DIAS)).isoformat()

    try:
        recebidos = _filtrar_recebidos(provedor.buscar(codigo, desde))
        if not recebidos and desde is None:
            raise ErroProvedor(
                "ativo_nao_encontrado",
                f"{provedor.nome} não trouxe pregões encerrados de {codigo} desde {INICIO_HISTORICO_BR}.",
            )

        conexao = conectar()
        with conexao:
            conexao.execute(
                "INSERT OR IGNORE INTO ativos (codigo, nome, tipo) VALUES (?, ?, ?)",
                (codigo, codigo, "indice" if codigo == CODIGO_IBOVESPA else "acao"),
            )
            conexao.execute("INSERT OR IGNORE INTO series (ativo, fonte) VALUES (?, ?)", (codigo, fonte))
            serie = conexao.execute(
                "SELECT id, versao FROM series WHERE ativo = ? AND fonte = ?", (codigo, fonte)
            ).fetchone()
            serie_id = serie["id"]
            aviso = None
            if provedor.acumula:
                mudou, aviso = _mesclar_com_rebase(conexao, serie_id, recebidos) if recebidos else (False, None)
            else:
                mudou = _mesclar_yahoo(conexao, serie_id, recebidos, provedor, codigo) if recebidos else False
            conexao.execute(
                """UPDATE series SET versao = versao + ?, obtida_em = ?, hash = ?, ultimo_erro = NULL,
                   ultimo_erro_em = NULL, aviso_rebase = COALESCE(?, aviso_rebase) WHERE id = ?""",
                (int(mudou), agora_iso(), _recalcular_hash(conexao, serie_id), aviso, serie_id),
            )
        conexao.close()
    except ErroProvedor as erro:
        _registrar_falha(fonte, codigo, erro.mensagem)
        raise
    return origem_dados(fonte, codigo)


def ler_candles(fonte: str, codigo: str) -> tuple[list[sqlite3.Row], sqlite3.Row | None]:
    """Só candles a partir do início do histórico, mesmo que o banco ainda guarde algum mais antigo."""
    conexao = conectar()
    serie = conexao.execute(
        "SELECT * FROM series WHERE ativo = ? AND fonte = ?", (codigo, fonte)
    ).fetchone()
    linhas = []
    if serie:
        linhas = conexao.execute(
            "SELECT * FROM candles WHERE serie_id = ? AND data >= ? ORDER BY data", (serie["id"], INICIO_HISTORICO)
        ).fetchall()
    conexao.close()
    return linhas, serie


def _candle_invalido(l) -> str | None:
    valores = (l["abertura"], l["maxima"], l["minima"], l["fechamento"])
    if any(v is None for v in valores):
        return "preco_ausente"
    if any(v <= 0 for v in valores):
        return "preco_zerado"
    if l["maxima"] < l["minima"]:
        return "maxima_abaixo_da_minima"
    return None


TEXTO_ALERTA = {
    "preco_ausente": "Preço ausente: candle fora da simulação",
    "preco_zerado": "Preço zerado: candle fora da simulação",
    "maxima_abaixo_da_minima": "Máxima abaixo da mínima: candle fora da simulação",
    "pregao_faltando": "Pregão faltando na série",
    "abertura_fora_da_faixa": "Abertura ou fechamento fora da faixa entre mínima e máxima",
    "sem_ajuste": "A fonte não informou o fechamento ajustado: preço usado sem ajuste",
    "volume_zero": "Pregão sem volume",
}


def avaliar_qualidade(linhas: list, janela_desde: str | None = None, indice: bool = False) -> list[dict]:
    """Alertas de candle. O limite evita relatar na tela o que está fora da janela visível.

    Índice não é negociado, então a falta de volume nele não é problema.
    """
    alertas = []
    for l in linhas:
        invalido = _candle_invalido(l)
        if invalido:
            alertas.append({"data": l["data"], "tipo": invalido, "descricao": TEXTO_ALERTA[invalido]})
            continue
        if l["recebido_ajustado"] is None:
            alertas.append({"data": l["data"], "tipo": "sem_ajuste", "descricao": TEXTO_ALERTA["sem_ajuste"]})
        margem = 0.005 * l["maxima"]  # tolera ruído de arredondamento do ajuste
        if not (
            l["minima"] - margem <= l["abertura"] <= l["maxima"] + margem
            and l["minima"] - margem <= l["fechamento"] <= l["maxima"] + margem
        ):
            alertas.append(
                {"data": l["data"], "tipo": "abertura_fora_da_faixa", "descricao": TEXTO_ALERTA["abertura_fora_da_faixa"]}
            )
        if not l["volume"] and not indice:
            alertas.append({"data": l["data"], "tipo": "volume_zero", "descricao": TEXTO_ALERTA["volume_zero"]})

    lacunas = set(_trechos_lacuna(linhas))
    for dia in pregoes_faltantes([l["data"] for l in linhas]):
        if not any(de <= dia <= ate for de, ate in lacunas):
            alertas.append({"data": dia, "tipo": "pregao_faltando", "descricao": TEXTO_ALERTA["pregao_faltando"]})
    if janela_desde:
        alertas = [a for a in alertas if a["data"] >= janela_desde]
    return sorted(alertas, key=lambda a: a["data"])


def _trechos_lacuna(linhas: list) -> list[tuple[str, str]]:
    """Intervalos sem dados, entre o último candle antes de cada quebra e o candle da quebra."""
    trechos = []
    for anterior, atual in zip(linhas, linhas[1:]):
        if atual["quebra"]:
            trechos.append((anterior["data"], atual["data"]))
    return trechos


def serie_para_motor(linhas: list) -> tuple[SerieCandles, int]:
    """Converte para o motor, tirando candles inválidos. Devolve também quantos ficaram de fora."""
    validas = [l for l in linhas if _candle_invalido(l) is None]
    return (
        SerieCandles(
            datas=[l["data"] for l in validas],
            abertura=np.array([l["abertura"] for l in validas], dtype=float),
            maxima=np.array([l["maxima"] for l in validas], dtype=float),
            minima=np.array([l["minima"] for l in validas], dtype=float),
            fechamento=np.array([l["fechamento"] for l in validas], dtype=float),
            volume=np.array([l["volume"] or 0 for l in validas], dtype=float),
            quebra=np.array([bool(l["quebra"]) for l in validas], dtype=bool),
        ),
        len(linhas) - len(validas),
    )


def inicio_janela_visivel(fonte: str, ultimo_pregao: str | None) -> str | None:
    """A aba brapi só mostra os últimos 3 meses, embora guarde tudo para o cálculo da MME."""
    if fonte != "brapi" or not ultimo_pregao:
        return None
    return menos_tres_meses(date.fromisoformat(ultimo_pregao)).isoformat()


def proximo_pregao_atrasado(ultimo_pregao: str | None, hoje: date | None = None) -> bool:
    """Indica se já existe pregão encerrado depois do último candle guardado."""
    if not ultimo_pregao:
        return True
    hoje = hoje or date.today()
    dia = date.fromisoformat(ultimo_pregao) + timedelta(days=1)
    while dia < hoje:
        if eh_pregao(dia):
            return True
        dia += timedelta(days=1)
    return False


def origem_dados(fonte: str, codigo: str) -> dict:
    """Fonte, plano, última atualização e último pregão: tudo o que a tela precisa para mostrar a origem."""
    provedor = PROVEDORES[fonte]
    conexao = conectar()
    serie = conexao.execute(
        """SELECT s.*, MIN(c.data) AS inicio, MAX(c.data) AS fim, COUNT(c.data) AS total
           FROM series s LEFT JOIN candles c ON c.serie_id = s.id
           WHERE s.ativo = ? AND s.fonte = ? GROUP BY s.id""",
        (codigo, fonte),
    ).fetchone()
    conexao.close()
    if not serie or not serie["total"]:
        return {
            "fonte": fonte,
            "provedor": provedor.nome,
            "plano": provedor.plano,
            "ativo": codigo,
            "tem_dados": False,
            "ultimo_erro": serie["ultimo_erro"] if serie else None,
            "ultimo_erro_em": serie["ultimo_erro_em"] if serie else None,
        }
    return {
        "fonte": fonte,
        "provedor": provedor.nome,
        "plano": provedor.plano,
        "ativo": codigo,
        "tem_dados": True,
        "obtida_em": serie["obtida_em"],
        "ultimo_pregao": serie["fim"],
        "versao": serie["versao"],
        "hash": serie["hash"],
        "ultimo_erro": serie["ultimo_erro"],
        "ultimo_erro_em": serie["ultimo_erro_em"],
        "aviso_rebase": serie["aviso_rebase"],
        "atrasada": proximo_pregao_atrasado(serie["fim"]),
    }


def listar_series() -> list[dict]:
    """Tela Dados. Na brapi informa só o período guardado e as lacunas, sem mostrar candles antigos."""
    conexao = conectar()
    series = conexao.execute(
        """SELECT s.ativo, s.fonte, a.nome FROM series s LEFT JOIN ativos a ON a.codigo = s.ativo
           ORDER BY s.ativo, s.fonte"""
    ).fetchall()
    conexao.close()
    saida = []
    for s in series:
        linhas, _ = ler_candles(s["fonte"], s["ativo"])
        origem = origem_dados(s["fonte"], s["ativo"])
        if not linhas:
            saida.append({**origem, "nome": s["nome"], "candles": 0, "lacunas": [], "alertas": 0})
            continue
        desde = inicio_janela_visivel(s["fonte"], linhas[-1]["data"])
        alertas = avaliar_qualidade(linhas, desde, s["ativo"] == CODIGO_IBOVESPA)
        saida.append(
            {
                **origem,
                "nome": s["nome"],
                "inicio_guardado": linhas[0]["data"],
                "candles": len(linhas),
                "lacunas": [{"de": de, "ate": ate} for de, ate in _trechos_lacuna(linhas)],
                "alertas": len(alertas),
                "historico_curto": s["fonte"] == "yahoo" and _menos_de_dez_anos(linhas[0]["data"], linhas[-1]["data"]),
            }
        )
    return saida


def _menos_de_dez_anos(inicio: str, fim: str) -> bool:
    return (date.fromisoformat(fim) - date.fromisoformat(inicio)).days < 3650


def alertas_da_serie(fonte: str, codigo: str) -> list[dict]:
    codigo = normalizar_codigo(codigo)
    linhas, _ = ler_candles(validar_fonte(fonte), codigo)
    if not linhas:
        return []
    return avaliar_qualidade(linhas, inicio_janela_visivel(fonte, linhas[-1]["data"]), codigo == CODIGO_IBOVESPA)


def garantir_ibovespa(fonte: str, ate: str | None) -> None:
    """Melhor esforço: a referência ajuda, mas nunca impede a análise do ativo."""
    origem = origem_dados(fonte, CODIGO_IBOVESPA)
    if origem["tem_dados"] and ate and origem["ultimo_pregao"] >= ate:
        return
    try:
        atualizar_serie(fonte, CODIGO_IBOVESPA)
    except ErroApp:
        pass
