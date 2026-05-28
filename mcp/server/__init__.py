"""mcp/server/__init__.py — Stub locale che re-esporta dall'SDK PyPI (Phase 6 D-E1).

Il package locale `mcp/` oscura l'SDK PyPI `mcp`. Questo package
(`mcp/server/`) replica la struttura dell'SDK in modo che gli import
standard continuino a funzionare:
  from mcp.server import Server          ← da qui
  from mcp.server.stdio import stdio_server  ← da mcp/server/stdio.py

Implementazione: carica i moduli SDK tramite importlib.util dal path
site-packages assoluto, bypassando il package locale corrente.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _get_sdk_mcp_dir() -> Path | None:
    """Trova la directory mcp nell'SDK (site-packages)."""
    import site
    for sp in site.getsitepackages() + [site.getusersitepackages()]:
        cand = Path(sp) / "mcp" / "__init__.py"
        if cand.exists():
            return cand.parent
    return None


def _load_sdk_submodule(sdk_dir: Path, rel_path: str, alias: str):
    """Carica un modulo SDK dalla path assoluta come alias."""
    if alias in sys.modules:
        return sys.modules[alias]
    target = sdk_dir / rel_path
    if not target.exists():
        raise ImportError(f"SDK module non trovato: {target}")
    spec = importlib.util.spec_from_file_location(
        alias,
        target,
        submodule_search_locations=[str(target.parent)] if target.suffix == "" else None,
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    # Assicuriamo che i parent alias siano in sys.modules prima dell'exec
    spec.loader.exec_module(mod)
    return mod


_sdk_dir = _get_sdk_mcp_dir()

if _sdk_dir is None:
    import logging as _logging
    _logging.getLogger(__name__).error(
        "SDK mcp non trovato in site-packages. Installare: pip install mcp>=1.27.0"
    )

    class Server:  # type: ignore
        """Stub Server per ambienti senza SDK."""
        def __init__(self, name: str, **kwargs):
            self.name = name
            self._tools_handlers = []
            self._call_handlers = []

        def list_tools(self):
            def decorator(fn):
                self._tools_handlers.append(fn)
                return fn
            return decorator

        def call_tool(self):
            def decorator(fn):
                self._call_handlers.append(fn)
                return fn
            return decorator

        def create_initialization_options(self):
            return {}

        async def run(self, read, write, init_options):
            pass

else:
    # Carica lowlevel server (contiene la classe Server principale)
    try:
        # Prima carichiamo mcp_sdk namespace per evitare ricorsione
        if "mcp_sdk" not in sys.modules:
            _sdk_spec = importlib.util.spec_from_file_location(
                "mcp_sdk",
                _sdk_dir / "__init__.py",
                submodule_search_locations=[str(_sdk_dir)],
            )
            _sdk_mod = importlib.util.module_from_spec(_sdk_spec)
            sys.modules["mcp_sdk"] = _sdk_mod
            # NON exec_module qui — lo facciamo lazy per evitare import circolari

        # Carichiamo direttamente lowlevel/server.py con un namespace pulito
        _ll_path = _sdk_dir / "server" / "lowlevel" / "server.py"
        if _ll_path.exists():
            _ll_spec = importlib.util.spec_from_file_location(
                "mcp_sdk.server.lowlevel.server",
                _ll_path,
            )
            _ll_mod = importlib.util.module_from_spec(_ll_spec)
            sys.modules["mcp_sdk.server.lowlevel.server"] = _ll_mod
            _ll_spec.loader.exec_module(_ll_mod)
            Server = _ll_mod.Server
        else:
            raise ImportError(f"lowlevel/server.py non trovato in {_sdk_dir}")
    except Exception as _exc:
        import logging as _log
        _log.getLogger(__name__).warning("Fallback stub Server: %s", _exc)

        class Server:  # type: ignore[no-redef]
            def __init__(self, name: str, **kwargs):
                self.name = name
                self._tools_handlers = []
                self._call_handlers = []

            def list_tools(self):
                def decorator(fn):
                    self._tools_handlers.append(fn)
                    return fn
                return decorator

            def call_tool(self):
                def decorator(fn):
                    self._call_handlers.append(fn)
                    return fn
                return decorator

            def create_initialization_options(self):
                return {}

            async def run(self, read, write, init_options):
                pass


__all__ = ["Server"]
