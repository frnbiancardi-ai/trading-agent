"""mcp/types.py — Stub locale per shadowing SDK (Phase 6 D-E1).

Re-esporta TextContent e Tool dall'SDK PyPI `mcp.types` tramite importlib,
bypassando il package locale `mcp/` che oscura l'SDK.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_sdk_types():
    """Carica mcp/types.py dell'SDK dal path site-packages."""
    import site
    for sp in site.getsitepackages() + [site.getusersitepackages()]:
        cand = Path(sp) / "mcp" / "types.py"
        if cand.exists():
            alias = "mcp_sdk.types"
            if alias in sys.modules:
                return sys.modules[alias]
            spec = importlib.util.spec_from_file_location(alias, cand)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[alias] = mod
            spec.loader.exec_module(mod)
            return mod
    return None


_types_mod = _load_sdk_types()

if _types_mod is not None:
    TextContent = _types_mod.TextContent
    Tool = _types_mod.Tool
else:
    # Fallback stub minimale per CI headless senza SDK
    import dataclasses

    @dataclasses.dataclass
    class TextContent:
        """Stub minimale TextContent per CI senza SDK."""
        type: str
        text: str

    @dataclasses.dataclass
    class Tool:
        """Stub minimale Tool per CI senza SDK."""
        name: str
        description: str
        inputSchema: dict


__all__ = ["TextContent", "Tool"]
