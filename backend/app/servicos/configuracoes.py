"""Padrões do usuário. O token da brapi fica fora do banco, para não viajar junto em cópias do banco."""
from __future__ import annotations

import json
import os
from pathlib import Path

from app.calendario import INICIO_HISTORICO
from app.db import conectar, PASTA_DADOS
from app.erros import ErroApp
from app.motor.custos import Custos
from app.setups.registro import SETUPS

PADROES = {
    "custos": Custos().model_dump(),
    "amostra_minima": 30,
    "janela_movel": 20,
    # Guarda os ocultos, e não os visíveis, para que um setup novo apareça sem ninguém precisar marcá-lo.
    "setups_ocultos": [],
}


def _arquivo_token() -> Path:
    return Path(os.environ.get("TRADER_TOKEN_ARQUIVO", PASTA_DADOS / "brapi_token.txt"))


def obter_token_brapi() -> str | None:
    do_ambiente = os.environ.get("BRAPI_TOKEN")
    if do_ambiente:
        return do_ambiente.strip()
    arquivo = _arquivo_token()
    if arquivo.exists():
        return arquivo.read_text(encoding="utf-8").strip() or None
    return None


def salvar_token_brapi(token: str | None) -> None:
    arquivo = _arquivo_token()
    if not token:
        arquivo.unlink(missing_ok=True)
        return
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(token.strip(), encoding="utf-8")


def ler_configuracoes() -> dict:
    with conectar() as conexao:
        linhas = conexao.execute("SELECT chave, valor FROM configuracoes").fetchall()
    conexao.close()
    salvos = {linha["chave"]: json.loads(linha["valor"]) for linha in linhas}
    saida = {**PADROES, **salvos}
    # Um setup retirado do catálogo não pode deixar a contagem errada nas telas.
    saida["setups_ocultos"] = [i for i in saida["setups_ocultos"] if i in SETUPS]
    saida["token_brapi_configurado"] = bool(obter_token_brapi())
    saida["inicio_historico"] = INICIO_HISTORICO  # fixo, só para leitura: as telas travam datas anteriores
    return saida


def _validar_ocultos(ocultos: list[str]) -> list[str]:
    desconhecidos = [i for i in ocultos if i not in SETUPS]
    if desconhecidos:
        raise ErroApp("setup_desconhecido", f"Setup desconhecido: {desconhecidos[0]}.", 422)
    if set(SETUPS) <= set(ocultos):
        raise ErroApp("sem_setups", "Pelo menos um setup precisa ficar na lista.", 422)
    return sorted(set(ocultos))


def salvar_configuracoes(valores: dict) -> dict:
    if "setups_ocultos" in valores:
        valores = {**valores, "setups_ocultos": _validar_ocultos(valores["setups_ocultos"])}
    with conectar() as conexao:
        for chave, valor in valores.items():
            if chave in PADROES:
                conexao.execute(
                    "INSERT INTO configuracoes (chave, valor) VALUES (?, ?) "
                    "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
                    (chave, json.dumps(valor)),
                )
    conexao.close()
    return ler_configuracoes()
