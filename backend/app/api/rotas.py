"""Rotas finas: toda a regra fica na camada de serviços."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field

from app.motor.custos import Custos
from app.servicos import acompanhamento, analise, configuracoes, dados

rotas = APIRouter(prefix="/api/v1")


class PedidoAnalise(BaseModel):
    ativo: str
    setup_id: str
    params: dict = Field(default_factory=dict)
    custos: Custos | None = None
    inicio: date | None = None
    fim: date | None = None


class ItemComparacao(BaseModel):
    ativo: str
    setup_id: str
    params: dict = Field(default_factory=dict)


class PedidoComparacao(BaseModel):
    itens: list[ItemComparacao]
    inicio: date | None = None
    fim: date | None = None


class PedidoAcompanhamento(BaseModel):
    ativo: str
    setup_id: str
    params: dict = Field(default_factory=dict)
    data_inicio: date | None = None


class PedidoConfiguracoes(BaseModel):
    custos: Custos | None = None
    amostra_minima: int | None = Field(None, ge=1, le=1000)
    janela_movel: int | None = Field(None, ge=2, le=200)
    setups_ocultos: list[str] | None = None


class PedidoToken(BaseModel):
    token: str | None = None


def _iso(valor: date | None) -> str | None:
    return valor.isoformat() if valor else None


@rotas.get("/saude")
def saude() -> dict:
    return {"situacao": "ok"}


@rotas.get("/ativos")
def buscar_ativos(busca: str = Query("", max_length=40)) -> list[dict]:
    return dados.buscar_ativos(busca)


@rotas.get("/setups")
def listar_setups() -> list[dict]:
    return analise.listar_setups()


@rotas.get("/dados")
def listar_dados() -> list[dict]:
    return dados.listar_series()


@rotas.get("/dados/{fonte}/{ativo}")
def origem(fonte: str, ativo: str) -> dict:
    dados.validar_fonte(fonte)
    return dados.origem_dados(fonte, dados.normalizar_codigo(ativo))


@rotas.get("/dados/{fonte}/{ativo}/alertas")
def alertas(fonte: str, ativo: str) -> list[dict]:
    return dados.alertas_da_serie(fonte, ativo)


@rotas.post("/dados/{fonte}/{ativo}/atualizar")
def atualizar(fonte: str, ativo: str) -> dict:
    resultado = dados.atualizar_serie(fonte, ativo)
    dados.garantir_ibovespa(fonte, resultado.get("ultimo_pregao"))
    return resultado


@rotas.post("/analise/{fonte}")
def analisar(fonte: str, pedido: PedidoAnalise) -> dict:
    return analise.analisar(
        fonte,
        pedido.ativo,
        pedido.setup_id,
        pedido.params,
        pedido.custos.model_dump() if pedido.custos else None,
        _iso(pedido.inicio),
        _iso(pedido.fim),
    )


@rotas.get("/execucoes/{execucao_id}/trades.csv")
def exportar_csv(execucao_id: int) -> Response:
    conteudo, nome = analise.exportar_trades_csv(execucao_id)
    return Response(
        conteudo,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@rotas.post("/comparar/{fonte}")
def comparar(fonte: str, pedido: PedidoComparacao) -> list[dict]:
    return analise.comparar(
        fonte, [i.model_dump() for i in pedido.itens], None, _iso(pedido.inicio), _iso(pedido.fim)
    )


@rotas.get("/acompanhamento/{fonte}")
def listar_acompanhamento(fonte: str) -> dict:
    return {"itens": acompanhamento.listar_itens(fonte), "eventos": acompanhamento.listar_eventos(fonte)}


@rotas.post("/acompanhamento/{fonte}")
def criar_acompanhamento(fonte: str, pedido: PedidoAcompanhamento) -> dict:
    return acompanhamento.criar_item(fonte, pedido.ativo, pedido.setup_id, pedido.params, _iso(pedido.data_inicio))


@rotas.post("/acompanhamento/{fonte}/processar")
def processar_acompanhamento(fonte: str) -> dict:
    return acompanhamento.processar(fonte)


@rotas.delete("/acompanhamento/item/{item_id}", status_code=204)
def remover_acompanhamento(item_id: int) -> None:
    acompanhamento.remover_item(item_id)


@rotas.get("/configuracoes")
def ler_configuracoes() -> dict:
    return configuracoes.ler_configuracoes()


@rotas.put("/configuracoes")
def salvar_configuracoes(pedido: PedidoConfiguracoes) -> dict:
    return configuracoes.salvar_configuracoes(pedido.model_dump(exclude_none=True))


@rotas.put("/configuracoes/token-brapi")
def salvar_token(pedido: PedidoToken) -> dict:
    configuracoes.salvar_token_brapi(pedido.token)
    return {
        "token_brapi_configurado": bool(configuracoes.obter_token_brapi()),
        "teste": dados.testar_token_brapi() if pedido.token else None,
    }
