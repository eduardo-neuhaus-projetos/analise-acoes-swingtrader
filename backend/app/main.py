"""API do aplicativo. Sem login: quem acessa o endereço pode mudar dados e configurações.

Com o build do frontend disponível, o mesmo servidor entrega a interface, num endereço só
(é assim que roda no container publicado no Render). No desenvolvimento, o Vite continua na 5173.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.rotas import rotas
from app.db import inicializar
from app.servicos.dados import aplicar_inicio_historico
from app.erros import ErroApp

# Build do React (npm run build). SWING_B3_FRONTEND troca a pasta, como no Dockerfile.
PASTA_FRONTEND_PADRAO = Path(__file__).resolve().parents[2] / "frontend" / "dist"


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


def montar_frontend(destino: FastAPI, pasta: Path) -> bool:
    """Serve o build do frontend na raiz, depois das rotas da API, que continuam tendo prioridade."""
    if not (pasta / "index.html").is_file():
        return False
    destino.mount("/", StaticFiles(directory=pasta, html=True), name="frontend")
    return True


montar_frontend(app, Path(os.environ.get("SWING_B3_FRONTEND", PASTA_FRONTEND_PADRAO)))
