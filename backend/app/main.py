"""API local do aplicativo. Sem login: só deve ficar acessível no próprio computador ou em rede privada."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.rotas import rotas
from app.db import inicializar
from app.servicos.dados import aplicar_inicio_historico
from app.erros import ErroApp


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    inicializar()
    aplicar_inicio_historico()
    yield


app = FastAPI(title="Swing Trade B3", version="0.1.0", lifespan=ciclo_de_vida)
app.include_router(rotas)


@app.exception_handler(ErroApp)
async def tratar_erro_app(_: Request, erro: ErroApp) -> JSONResponse:
    return JSONResponse(status_code=erro.status, content={"codigo": erro.codigo, "mensagem": erro.mensagem})
