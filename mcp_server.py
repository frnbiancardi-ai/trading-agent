"""Shim retrocompatibile per `python -m mcp_server`.

Il vero codice vive in `mcp_tools/server.py` dopo lo split D-E1 della Phase 6.
Questo file esiste solo per non rompere CLI/script esterni che lanciano
`python -m mcp_server`, e per permettere ai test esistenti (test_mcp_tools_v2.py)
di continuare a fare `import mcp_server` e monkeypatching di `mcp_server.mt5`,
`mcp_server.cfg`, ecc.

Strategia retrocompatibilità:
- I nomi pubblici sono re-esportati via `from mcp_tools.server import ...`
- PEP 562 (__getattr__ + __setattr__ a livello modulo): quando monkeypatch
  imposta `mcp_server.cfg = mock`, il set viene propagato ANCHE a
  `mcp_tools.server.cfg` così le funzioni nel modulo reale vedono il mock.
"""
from mcp_tools.server import (  # noqa: F401
    cfg,
    log,
    mt5,
    _mt5_ready,
    server,
    _bootstrap_mt5,
    _bootstrap_state,
    _serve,
    _text,
    _PROPOSAL_SCHEMA,
    _PROPOSE_TRADE_SCHEMA,
    list_tools,
    call_tool,
)
from mcp_tools.handlers.account import (  # noqa: F401
    handle_get_account_state,
    handle_get_risk_profile,
    handle_get_trade_history,
)
from mcp_tools.handlers.market import (
    handle_get_market_snapshot as _market_snapshot,  # noqa: F401
    handle_scan_symbol_candidates as _market_scan,
    handle_get_symbol_indicators as _market_symbol_indicators,
    handle_get_symbol_universe as _market_symbol_universe,
)
from mcp_tools.handlers.proposal import (
    handle_propose_trade as _proposal_propose,
    handle_evaluate_trade_proposal as _proposal_evaluate,  # noqa: F401
    handle_submit_order_if_approved as _proposal_submit,  # noqa: F401
)

import asyncio
import dataclasses
import sys


# ── Wrapper retrocompat per test legacy ───────────────────────────────────────
# I test (tests/test_mcp_tools_v2.py) chiamano queste funzioni con la vecchia
# signature posizionale. I nuovi handler in mcp_tools/handlers/{market,proposal}.py
# hanno signature standardizzata (args: dict, mt5_client, cfg). I wrapper
# qui sotto traducono la vecchia API alla nuova così i test pre-Phase 6 girano
# senza modifiche.

def handle_get_symbol_universe(filter_asset_class: str | None = None) -> dict:
    """Shim legacy: deriva cfg dal modulo, delega al nuovo handler market."""
    return _market_symbol_universe(cfg, filter_asset_class=filter_asset_class)


def handle_scan_symbol_candidates(symbols: list[str], timeframe: str | None = None) -> dict:
    """Shim legacy: costruisce args dict, delega al nuovo handler market."""
    args = {"symbols": list(symbols or []), "timeframe": timeframe}
    return _market_scan(args, mt5, cfg)


def handle_get_symbol_indicators(symbol: str, timeframe: str | None = None) -> dict:
    """Shim legacy: delega al nuovo handler market con kwargs."""
    return _market_symbol_indicators(symbol, mt5, cfg, timeframe=timeframe)


def handle_propose_trade(args: dict) -> dict:
    """Shim legacy: aggiunge log/cfg dal modulo, delega al nuovo handler proposal."""
    return _proposal_propose(args, log, cfg)


def _build_proposal(args: dict):
    """Shim legacy: costruisce TradeProposal (usato dai test legacy)."""
    from models import TradeProposal
    return TradeProposal(
        symbol=args["symbol"],
        direction=args["direction"],
        entry_price=args["entry_price"],
        stop_loss_price=args["stop_loss_price"],
        take_profit_price=args["take_profit_price"],
        timeframe=cfg.TIMEFRAME,
        comment="mcp",
        confidence=args["confidence"],
        rationale=args["rationale"],
    )


# ── PEP 562: propaga monkeypatch a mcp_tools.server ──────────────────────────
# I test fanno `monkeypatch.setattr(mcp_server, "cfg", mock)`.
# Dobbiamo propagare il set anche a `mcp_tools.server` così le funzioni
# all'interno del modulo reale vedono il mock.
_PROPAGATED_ATTRS = frozenset(["cfg", "mt5", "log", "_mt5_ready"])


class _ShimModule(sys.modules[__name__].__class__):
    """Module con __setattr__ PEP 562 per propagare monkeypatch."""

    def __setattr__(self, name: str, value) -> None:
        super().__setattr__(name, value)
        if name in _PROPAGATED_ATTRS:
            import mcp_tools.server as _srv
            try:
                setattr(_srv, name, value)
            except Exception:
                pass


sys.modules[__name__].__class__ = _ShimModule


def main() -> None:
    """Entry point per `python -m mcp_server`."""
    _bootstrap_mt5()
    _bootstrap_state()
    try:
        asyncio.run(_serve())
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
