"""O servidor de publicação entrega a interface e a API no mesmo endereço."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rotas import rotas
from app.main import montar_frontend


def _app_com_build(pasta):
    app = FastAPI()
    app.include_router(rotas)
    return app, montar_frontend(app, pasta)


def test_sem_build_nada_e_montado(tmp_path, banco):
    app, montado = _app_com_build(tmp_path / "nao_existe")
    assert montado is False
    assert TestClient(app).get("/").status_code == 404


def test_build_e_servido_na_raiz_e_a_api_continua_respondendo(tmp_path, banco):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>Swing B3</title>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    app, montado = _app_com_build(tmp_path)
    assert montado is True
    cliente = TestClient(app)

    raiz = cliente.get("/")
    assert raiz.status_code == 200 and "Swing B3" in raiz.text
    assert cliente.get("/assets/app.js").text == "console.log(1)"

    api = cliente.get("/api/v1/setups")
    assert api.status_code == 200 and isinstance(api.json(), list)
