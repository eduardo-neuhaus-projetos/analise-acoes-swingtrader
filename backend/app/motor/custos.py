"""Resultado bruto e líquido de cada trade, em %, em R e em reais."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.motor.tipos import Trade


class Custos(BaseModel):
    corretagem_por_ordem: float = Field(0.0, ge=0, title="Corretagem por ordem (R$)")
    emolumentos_pct: float = Field(0.0, ge=0, le=5, title="Emolumentos por ordem (%)")
    slippage_pct: float = Field(0.0, ge=0, le=5, title="Slippage por ordem (%)")
    capital_por_trade: float = Field(10000.0, gt=0, title="Capital por trade (R$)")


def resultado_trade(trade: Trade, custos: Custos) -> dict[str, float | None]:
    """Em trade aberto o cálculo usa o último fechamento e representa um resultado não realizado."""
    saida = trade.saida_preco if not trade.aberto else trade.preco_referencia
    if saida is None:
        return dict.fromkeys(
            ("bruto_pct", "bruto_r", "bruto_reais", "liquido_pct", "liquido_r", "liquido_reais")
        )
    entrada = trade.entrada_preco
    quantidade = custos.capital_por_trade / entrada
    bruto = saida - entrada

    slip = custos.slippage_pct / 100
    entrada_efetiva = entrada * (1 + slip)
    saida_efetiva = saida * (1 - slip)
    emolumentos = (custos.emolumentos_pct / 100) * (entrada_efetiva + saida_efetiva)
    corretagem = 2 * custos.corretagem_por_ordem / quantidade
    liquido = saida_efetiva - entrada_efetiva - emolumentos - corretagem

    return {
        "bruto_pct": bruto / entrada * 100,
        "bruto_r": bruto / trade.risco if trade.risco else None,
        "bruto_reais": bruto * quantidade,
        "liquido_pct": liquido / entrada * 100,
        "liquido_r": liquido / trade.risco if trade.risco else None,
        "liquido_reais": liquido * quantidade,
    }
