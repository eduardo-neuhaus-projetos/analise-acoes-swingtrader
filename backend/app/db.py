"""Banco SQLite de um arquivo. As métricas não ficam aqui: são sempre recalculadas a partir dos trades."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

PASTA_DADOS = Path(__file__).resolve().parent.parent / "data"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS ativos (
    codigo TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'acao',
    situacao TEXT NOT NULL DEFAULT 'ativo'
);

-- Uma série por ativo e fonte. Dados de fontes diferentes nunca se misturam.
CREATE TABLE IF NOT EXISTS series (
    id INTEGER PRIMARY KEY,
    ativo TEXT NOT NULL,
    fonte TEXT NOT NULL CHECK (fonte IN ('brapi', 'yahoo')),
    versao INTEGER NOT NULL DEFAULT 1,
    obtida_em TEXT,
    hash TEXT,
    ultimo_erro TEXT,
    ultimo_erro_em TEXT,
    aviso_rebase TEXT,
    UNIQUE (ativo, fonte)
);

CREATE TABLE IF NOT EXISTS candles (
    serie_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    -- OHLC ajustado por proventos, usado em sinais e simulação
    abertura REAL, maxima REAL, minima REAL, fechamento REAL,
    volume REAL,
    -- Valores exatamente como a fonte entregou
    recebido_abertura REAL, recebido_maxima REAL, recebido_minima REAL, recebido_fechamento REAL,
    recebido_ajustado REAL,
    fator_rebase REAL NOT NULL DEFAULT 1,
    quebra INTEGER NOT NULL DEFAULT 0,  -- primeiro candle depois de uma lacuna
    PRIMARY KEY (serie_id, data)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS execucoes (
    id INTEGER PRIMARY KEY,
    chave TEXT NOT NULL UNIQUE,  -- mesmos candles e parâmetros reaproveitam a mesma execução
    tipo TEXT NOT NULL DEFAULT 'backtest',
    fonte TEXT NOT NULL,
    ativo TEXT NOT NULL,
    serie_versao INTEGER NOT NULL,
    serie_hash TEXT NOT NULL,
    setup_id TEXT NOT NULL,
    setup_versao TEXT NOT NULL,
    params TEXT NOT NULL,
    custos TEXT NOT NULL,
    inicio TEXT,
    fim TEXT,
    criada_em TEXT NOT NULL,
    situacao TEXT NOT NULL DEFAULT 'concluida'
);

CREATE TABLE IF NOT EXISTS trades (
    execucao_id INTEGER NOT NULL REFERENCES execucoes(id) ON DELETE CASCADE,
    numero INTEGER NOT NULL,
    origem TEXT NOT NULL DEFAULT 'backtest',
    sinal_data TEXT,
    entrada_data TEXT, entrada_preco REAL,
    stop REAL, risco REAL, alvo REAL,
    saida_data TEXT, saida_preco REAL, motivo_saida TEXT,
    duracao_pregoes INTEGER,
    aberto INTEGER,
    bruto_pct REAL, bruto_r REAL, bruto_reais REAL,
    liquido_pct REAL, liquido_r REAL, liquido_reais REAL,
    avisos TEXT,
    eventos TEXT,
    PRIMARY KEY (execucao_id, numero)
);

CREATE TABLE IF NOT EXISTS sinais (
    execucao_id INTEGER NOT NULL REFERENCES execucoes(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    gatilho REAL, stop REAL, situacao TEXT, motivo TEXT,
    PRIMARY KEY (execucao_id, data)
);

CREATE TABLE IF NOT EXISTS itens_acompanhamento (
    id INTEGER PRIMARY KEY,
    fonte TEXT NOT NULL CHECK (fonte IN ('brapi', 'yahoo')),
    ativo TEXT NOT NULL,
    setup_id TEXT NOT NULL,
    setup_versao TEXT NOT NULL,
    params TEXT NOT NULL,
    custos TEXT NOT NULL,
    data_inicio TEXT NOT NULL,
    ligado INTEGER NOT NULL DEFAULT 1,
    ultimo_pregao TEXT,
    estado TEXT NOT NULL DEFAULT 'sem_sinal',
    ordens TEXT NOT NULL DEFAULT '[]',
    posicao TEXT,
    ultimo_erro TEXT,
    ultimo_erro_em TEXT,
    criado_em TEXT NOT NULL
);

-- Histórico: nunca é sobrescrito. O preço fica como foi calculado naquele dia.
CREATE TABLE IF NOT EXISTS eventos_acompanhamento (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES itens_acompanhamento(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    tipo TEXT NOT NULL,
    preco REAL,
    descricao TEXT,
    serie_versao INTEGER,
    registrado_em TEXT NOT NULL,
    UNIQUE (item_id, data, tipo)
);

CREATE TABLE IF NOT EXISTS configuracoes (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""


def caminho_banco() -> Path:
    return Path(os.environ.get("TRADER_DB", PASTA_DADOS / "trader.db"))


def conectar() -> sqlite3.Connection:
    caminho = caminho_banco()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho, timeout=30)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.execute("PRAGMA journal_mode = WAL")
    return conexao


def inicializar() -> None:
    from app.ativos_b3 import ATIVOS

    with conectar() as conexao:
        conexao.executescript(ESQUEMA)
        conexao.executemany(
            "INSERT OR IGNORE INTO ativos (codigo, nome) VALUES (?, ?)", ATIVOS
        )
    conexao.close()
