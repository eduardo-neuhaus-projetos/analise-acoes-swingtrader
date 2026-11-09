"""Plano Gratuito da brapi: 3 meses, 1 ativo por requisição, sempre uma requisição por vez."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

import httpx

from app.erros import ErroProvedor
from app.provedores.base import CandleRecebido, Provedor

URL_HISTORICO = "https://brapi.dev/api/v2/stocks/historical"
FUSO_B3 = timezone(timedelta(hours=-3))
ESPERAS_S = (1.0, 2.0, 4.0)

_fila = threading.Lock()


class ProvedorBrapi(Provedor):
    id = "brapi"
    nome = "brapi"
    plano = "Gratuito (3 meses)"
    acumula = True

    def __init__(
        self,
        obter_token: Callable[[], str | None],
        transporte: httpx.BaseTransport | None = None,
        esperar: Callable[[float], None] = time.sleep,
    ) -> None:
        self._obter_token = obter_token
        self._transporte = transporte
        self._esperar = esperar

    def buscar(self, codigo: str, desde: str | None = None) -> list[CandleRecebido]:
        # O token vai no cabeçalho, e não na URL, para nunca aparecer em registros de requisição.
        token = self._obter_token()
        cabecalhos = {"Authorization": f"Bearer {token}"} if token else {}
        parametros = {"symbols": codigo, "range": "3mo", "interval": "1d", "sortOrder": "asc"}
        with _fila, httpx.Client(transport=self._transporte, timeout=30, headers=cabecalhos) as cliente:
            resposta = self._com_novas_tentativas(cliente, parametros, codigo)
        return _interpretar(resposta, codigo)

    def _com_novas_tentativas(self, cliente: httpx.Client, parametros: dict, codigo: str) -> httpx.Response:
        erro: ErroProvedor | None = None
        for espera in (0.0, *ESPERAS_S):
            if espera:
                self._esperar(espera)
            try:
                resposta = cliente.get(URL_HISTORICO, params=parametros)
            except httpx.HTTPError:
                erro = ErroProvedor("fonte_indisponivel", "Não foi possível conectar à brapi.")
                continue
            if resposta.status_code == 429:
                erro = ErroProvedor(
                    "limite_excedido", "A brapi recusou o pedido por limite de requisições do plano."
                )
                continue
            if resposta.status_code >= 500:
                erro = ErroProvedor("fonte_indisponivel", f"A brapi respondeu com erro {resposta.status_code}.")
                continue
            if resposta.status_code == 401:
                if "Authorization" in cliente.headers:
                    raise ErroProvedor(
                        "token_recusado", "A brapi recusou o token guardado. Confira o token em Configurações."
                    )
                raise ErroProvedor(
                    "token_necessario",
                    f"Sem token, a brapi só responde para PETR4, MGLU3, VALE3 e ITUB4. Para {codigo}, "
                    "crie uma conta gratuita em brapi.dev e guarde o token em Configurações.",
                )
            if resposta.status_code == 403:
                raise ErroProvedor("plano_insuficiente", f"O plano Gratuito da brapi não inclui {codigo}.")
            if resposta.status_code in (400, 404):
                raise ErroProvedor("ativo_nao_encontrado", f"A brapi não encontrou dados para {codigo}.")
            return resposta
        raise erro


def _interpretar(resposta: httpx.Response, codigo: str) -> list[CandleRecebido]:
    try:
        corpo = resposta.json()
        resultados = corpo.get("results") or []
        pontos = resultados[0].get("data", {}).get("historicalDataPrice") if resultados else None
    except (ValueError, AttributeError) as exc:
        raise ErroProvedor("dado_invalido", "A brapi devolveu uma resposta em formato inesperado.") from exc
    if not pontos:
        raise ErroProvedor("ativo_nao_encontrado", f"A brapi não encontrou dados para {codigo}.")

    candles = []
    try:
        for p in pontos:
            data = datetime.fromtimestamp(p["date"], FUSO_B3).date().isoformat()
            candles.append(
                CandleRecebido(
                    data,
                    p.get("open"),
                    p.get("high"),
                    p.get("low"),
                    p.get("close"),
                    p.get("adjustedClose"),
                    p.get("volume"),
                )
            )
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise ErroProvedor("dado_invalido", "A brapi devolveu um candle em formato inesperado.") from exc
    return sorted(candles, key=lambda c: c.data)
