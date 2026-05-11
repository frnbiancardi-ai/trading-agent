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
    _build_proposal,
    _PROPOSAL_SCHEMA,
    _PROPOSE_TRADE_SCHEMA,
    handle_get_symbol_universe,
    handle_scan_symbol_candidates,
    handle_get_symbol_indicators,
    handle_propose_trade,
    list_tools,
    call_tool,
)
from mcp_tools.handlers.account import (  # noqa: F401
    handle_get_account_state,
    handle_get_risk_profile,
    handle_get_trade_history,
)

import asyncio
import sys


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
