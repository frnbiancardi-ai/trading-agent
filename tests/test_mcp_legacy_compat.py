"""Legacy compatibility tests per Phase 6 MCP split (D-E1).

Wave 1 implementa il shim mcp_server.py → mcp_tools/server.py.
Wave 4 completa il conteggio tool a 25.
"""
import pytest


# Wave 1 — D-E1: shim mcp_server.py → mcp_tools/server.py
def test_legacy_entrypoint_imports():
    """Verifica che mcp_server.py sia un thin shim valido dopo lo split D-E1.

    - import mcp_server non solleva
    - mcp_server.server è lo stesso oggetto di mcp_tools.server.server
    - attributi mt5, cfg, log sono accessibili
    """
    import mcp_server
    import mcp_tools.server

    # Verifico attributi essenziali
    assert hasattr(mcp_server, "server"), "mcp_server.server mancante"
    assert hasattr(mcp_server, "mt5"), "mcp_server.mt5 mancante"
    assert hasattr(mcp_server, "cfg"), "mcp_server.cfg mancante"
    assert hasattr(mcp_server, "log"), "mcp_server.log mancante"

    # Verifico che server sia lo stesso oggetto (shim re-export)
    assert mcp_server.server is mcp_tools.server.server, (
        "mcp_server.server non è lo stesso oggetto di mcp_tools.server.server"
    )

    # Verifico che le funzioni handler siano disponibili
    assert callable(mcp_server.handle_get_symbol_universe)
    assert callable(mcp_server.handle_scan_symbol_candidates)
    assert callable(mcp_server.handle_get_symbol_indicators)
    assert callable(mcp_server.handle_propose_trade)
    assert callable(mcp_server.handle_get_account_state)
    assert callable(mcp_server.handle_get_risk_profile)
    assert callable(mcp_server.handle_get_trade_history)


# Wave 4 — tools/list totale 25 tool dopo tutti i wave
def test_list_tools_count():
    pytest.xfail("MISSING — Wave 4 — total 25 tools after all waves")


# Wave 4 — skill regression: forex-trader-pro compat
def test_skill_compat_reads():
    pytest.xfail("MISSING — Wave 4 skill regression check")
