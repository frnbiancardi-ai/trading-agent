"""Phase 6 Wave 3 (Plan 06-04) SC#2: real-broker modify_position integration test.

Marker @pytest.mark.integration → skip default in CI Codespace; runnabile
manualmente su PC con MT5 demo TenTrade attivo prima del merge.

Requisiti per esecuzione locale:
- MT5 demo TenTrade attivo + login valido
- Almeno una posizione aperta manualmente via terminale MT5
- .env configurato con MT5_LOGIN / MT5_PASSWORD / MT5_SERVER
- pacchetto MetaTrader5 installato (pip install MetaTrader5; Windows-only)

Esegui:
    pytest tests/test_mcp_integration_modify.py -m integration -v

Il test verifica D-B3 (stops_level pre-validation con suggested_sl) end-to-end
sul broker reale: SL invalido → rifiuto + suggested; retry con suggested → ok.
"""
from __future__ import annotations

import importlib.util
import os

import pytest
from unittest.mock import MagicMock


pytestmark = pytest.mark.integration


# Skip se MT5_LOGIN non set OPPURE se il pacchetto MetaTrader5 non è installato
# (Codespace Linux non ha MetaTrader5; .env può comunque contenere MT5_LOGIN da
# config locale Windows). Robustezza Rule 1: doppio gate per CI.
def _has_mt5_pkg() -> bool:
    try:
        return importlib.util.find_spec("MetaTrader5") is not None
    except (ImportError, ValueError):
        return False


_HAS_MT5_PKG = _has_mt5_pkg()


@pytest.mark.skipif(
    not os.getenv("MT5_LOGIN") or not _HAS_MT5_PKG,
    reason=(
        "Integration test require both MT5_LOGIN env e pacchetto MetaTrader5 "
        "installato (Windows-only) — skip in CI Codespace"
    ),
)
def test_real_broker_modify():
    """SC#2: modify_position rispetta stops_level su MT5 demo (round-trip reale)."""
    # Import lazy: MetaTrader5 è Windows-only e non installato in Codespace
    from config import Config
    from mcp_tools.handlers.position import handle_modify_position
    from mt5_client import Mt5Client

    cfg = Config()
    mt5 = Mt5Client(cfg)
    assert mt5.initialize() and mt5.login(), "MT5 init/login fallito"

    try:
        import MetaTrader5 as _mt5
        positions = _mt5.positions_get() or []
        if not positions:
            pytest.skip(
                "Nessuna posizione aperta su demo — apri manualmente prima di runnare"
            )
        pos = positions[0]
        pid = int(pos.ticket)

        # Step 1: SL troppo vicino al current_price → stops_level_violation + suggested
        invalid_sl = (
            pos.price_current - 0.000001 if pos.type == 0
            else pos.price_current + 0.000001
        )
        log = MagicMock()
        out = handle_modify_position(
            {"position_id": pid, "new_sl": invalid_sl},
            mt5, cfg, log,
        )
        assert out["ok"] is False
        assert out["error"] == "stops_level_violation"
        assert "suggested_sl" in out
        suggested = out["suggested_sl"]

        # Step 2: retry con suggested_sl → ok (o DRY_RUN se EXECUTION_MODE=shadow)
        out2 = handle_modify_position(
            {"position_id": pid, "new_sl": suggested},
            mt5, cfg, log,
        )
        assert out2["ok"] is True or "DRY_RUN" in str(out2.get("note", ""))
    finally:
        mt5.shutdown()
