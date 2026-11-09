"""Erros esperados da aplicação, já com a mensagem que a tela deve mostrar."""
from __future__ import annotations


class ErroApp(Exception):
    def __init__(self, codigo: str, mensagem: str, status: int = 400) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.status = status


class ErroProvedor(ErroApp):
    """Falha em uma fonte. Só afeta a aba dela: nunca há troca automática de fonte."""

    def __init__(self, codigo: str, mensagem: str) -> None:
        super().__init__(codigo, mensagem, status=502)
