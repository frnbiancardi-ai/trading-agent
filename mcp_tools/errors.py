"""Re-export di ErrorCodes/envelope da mcp.errors (Wave 0) per mcp_tools.

Il codice originale vive in mcp/errors.py (Wave 0 plan 06-01).
Questo modulo esiste per permettere a tutti gli handler in mcp_tools/
di importare via `from mcp_tools.errors import ErrorCodes, envelope`
senza dipendere dal path `mcp.errors` (che è il pacchetto locale Wave 0,
non il SDK PyPI).
"""
from mcp.errors import ErrorCodes, envelope  # noqa: F401

__all__ = ["ErrorCodes", "envelope"]
