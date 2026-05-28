"""mcp/server/stdio.py — Re-esporta stdio_server dall'SDK PyPI (Phase 6 D-E1).

Permette `from mcp.server.stdio import stdio_server` anche quando il
package locale `mcp/` oscura l'SDK PyPI.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _get_sdk_mcp_dir() -> Path | None:
    import site
    for sp in site.getsitepackages() + [site.getusersitepackages()]:
        cand = Path(sp) / "mcp" / "__init__.py"
        if cand.exists():
            return cand.parent
    return None


_sdk_dir = _get_sdk_mcp_dir()

if _sdk_dir is not None:
    try:
        _alias = "mcp_sdk.server.stdio"
        if _alias not in sys.modules:
            _stdio_path = _sdk_dir / "server" / "stdio.py"
            _spec = importlib.util.spec_from_file_location(_alias, _stdio_path)
            _mod = importlib.util.module_from_spec(_spec)
            sys.modules[_alias] = _mod
            _spec.loader.exec_module(_mod)
        stdio_server = sys.modules[_alias].stdio_server
    except Exception as _exc:
        import logging as _logging
        _logging.getLogger(__name__).warning("stdio_server stub: %s", _exc)
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def stdio_server():  # type: ignore[no-redef]
            import asyncio
            yield asyncio.StreamReader(), None
else:
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def stdio_server():  # type: ignore
        """Stub per CI headless senza SDK."""
        import asyncio
        yield asyncio.StreamReader(), None


__all__ = ["stdio_server"]
