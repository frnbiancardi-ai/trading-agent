"""Test AST purity gate — moduli pure-fn non devono importare broker/log/db/print (STRAT-08, D-15).

Esegue introspezione AST sui 7 moduli pure-fn della strategy package e verifica:
  1. nessun import vietato (mt5, MetaTrader5, requests, sqlite3, subprocess, logging, http*)
  2. nessuna chiamata a logging.getLogger / logger.info / logger.warning / etc.
  3. nessuna chiamata a print() o open() (eccezione: confluence.py usa open() per yaml load)

Living invariant (D-16): qualunque futura aggiunta di import broker/logging/IO ai moduli
puri farà fallire questo test, gating Wave 2 detector e tutto il lavoro Phase 4+ successivo.
Il test e' AST-based (zero side effect, < 100ms total) e indipendente da pytest fixtures.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Moduli che DEVONO restare puri (Wave 0 skeleton + Wave 1 implementazioni).
# strategy/adapters/* sono ESCLUSI per design — sono I/O bridge verso MT5/backtest.
PURE_MODULES = [
    "strategy/setups/a_breakout.py",
    "strategy/setups/b_reversal.py",
    "strategy/setups/c_compression.py",
    "strategy/setups/d_pullback.py",
    "strategy/setups/__init__.py",
    "strategy/confluence.py",
    "strategy/proposal.py",
    "strategy/context.py",
]

# Top-level package roots vietati. Si confronta solo il primo segmento del nome di import
# (es. "urllib.request" -> "urllib") per coprire tutte le sotto-librerie in un colpo.
FORBIDDEN_IMPORTS = {
    # broker / market-data IO
    "mt5",
    "MetaTrader5",
    "mt5_client",
    # network IO
    "requests",
    "urllib",
    "urllib2",
    "urllib3",
    "httpx",
    "aiohttp",
    "http",
    # storage IO
    "sqlite3",
    # process IO
    "subprocess",
    # logging (hard block: anche solo importarlo e' vietato)
    "logging",
}

# File con eccezioni motivate: solo confluence.py puo' chiamare open() per il
# yaml singleton loader (D-08 schema cached via lru_cache).
OPEN_EXEMPT_FILES = {"strategy/confluence.py"}

# Metodi di logger riconosciuti come violazione quando chiamati su una variabile
# il cui nome contiene "log" (heuristica nome-based per catch self.logger.info(...),
# log.error(...), my_logger.warning(...), etc.).
LOG_METHODS = {
    "info",
    "warning",
    "error",
    "debug",
    "critical",
    "exception",
    "log",
    "getLogger",
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _parse(module_path: str) -> tuple[ast.Module, str]:
    """Carica un file pure-fn e ritorna (AST tree, source). Fail-fast se mancante."""
    path = Path(module_path)
    if not path.exists():
        pytest.fail(f"modulo pure-fn mancante: {module_path}")
    source = path.read_text(encoding="utf-8")
    try:
        return ast.parse(source, filename=module_path), source
    except SyntaxError as e:  # pragma: no cover -- defensive
        pytest.fail(f"{module_path}: SyntaxError {e}")


def _import_root(name: str | None) -> str:
    """Estrae il primo segmento di un nome di import ('urllib.request' -> 'urllib')."""
    if name is None:
        return ""
    return name.split(".")[0]


# --------------------------------------------------------------------------
# Test 1 — import vietati
# --------------------------------------------------------------------------


def test_strategy_purity_no_forbidden_imports():
    """Nessun import di broker/network/db/logging nei moduli pure-fn (STRAT-08, D-15)."""
    violations: list[str] = []
    for mod_path in PURE_MODULES:
        tree, _ = _parse(mod_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = _import_root(alias.name)
                    if root in FORBIDDEN_IMPORTS:
                        violations.append(
                            f"{mod_path}:{node.lineno}: forbidden 'import {alias.name}'"
                        )
            elif isinstance(node, ast.ImportFrom):
                root = _import_root(node.module)
                if root in FORBIDDEN_IMPORTS:
                    violations.append(
                        f"{mod_path}:{node.lineno}: forbidden 'from {node.module} import ...'"
                    )
    assert not violations, (
        "Pure modules contengono import vietati:\n  " + "\n  ".join(violations)
    )


# --------------------------------------------------------------------------
# Test 2 — chiamate logging.* / logger.*
# --------------------------------------------------------------------------


def test_strategy_purity_no_logging_calls():
    """Nessuna chiamata a logging.* o a metodi di un Logger (.info/.warning/...)."""
    violations: list[str] = []
    for mod_path in PURE_MODULES:
        tree, _ = _parse(mod_path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            attr = func.attr
            # Caso a: logging.<method>(...) — modulo logging direttamente referenziato
            if isinstance(func.value, ast.Name) and func.value.id == "logging":
                violations.append(
                    f"{mod_path}:{node.lineno}: forbidden 'logging.{attr}(...)'"
                )
            # Caso b: <name>.<log-method>(...) dove <name> contiene 'log' (logger,
            # my_log, self.log, ...). Heuristica nome-based per catch logger calls
            # senza dover importare/eseguire il modulo.
            elif (
                attr in LOG_METHODS
                and isinstance(func.value, ast.Name)
                and ("log" in func.value.id.lower())
            ):
                violations.append(
                    f"{mod_path}:{node.lineno}: forbidden '{func.value.id}.{attr}(...)' (logger call)"
                )
    assert not violations, (
        "Pure modules contengono chiamate logging:\n  " + "\n  ".join(violations)
    )


# --------------------------------------------------------------------------
# Test 3 — print() / open() vietati (eccezione yaml loader confluence)
# --------------------------------------------------------------------------


def test_strategy_purity_no_print_calls():
    """Nessuna chiamata a print() o open() nei moduli puri.

    Eccezione: strategy/confluence.py puo' chiamare open() perche' usa il yaml
    singleton loader (D-08 schema, lru_cache-ato — l'unico I/O concesso).
    """
    violations: list[str] = []
    for mod_path in PURE_MODULES:
        tree, _ = _parse(mod_path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Name):
                continue
            if func.id == "print":
                violations.append(
                    f"{mod_path}:{node.lineno}: forbidden 'print(...)'"
                )
            elif func.id == "open" and mod_path not in OPEN_EXEMPT_FILES:
                violations.append(
                    f"{mod_path}:{node.lineno}: forbidden 'open(...)' "
                    f"(non-exempt; only {sorted(OPEN_EXEMPT_FILES)} allowed)"
                )
    assert not violations, (
        "Pure modules contengono print/open vietati:\n  " + "\n  ".join(violations)
    )


# --------------------------------------------------------------------------
# Test 4 — sanity: tutti i moduli puri esistono
# --------------------------------------------------------------------------


def test_pure_modules_all_exist():
    """Sanity check: tutti i moduli puri devono esistere prima dei test 1/2/3.

    Fallisce per primo (ordine alfabetico ast/exist) con messaggio chiaro se
    qualcuno cancella accidentalmente uno dei 7 moduli puri tracciati.
    """
    missing = [m for m in PURE_MODULES if not Path(m).exists()]
    assert not missing, f"moduli puri mancanti: {missing}"


# --------------------------------------------------------------------------
# Test 5 — adapters/ ESCLUSO dal gate (deliberate-bypass invariant)
# --------------------------------------------------------------------------


def test_adapters_subpackage_excluded_from_purity_gate():
    """Verifica esplicita che strategy/adapters/* NON sia tra i moduli puri.

    Gli adapter (live/backtest) sono I/O bridge per design: importano mt5_client,
    chiamano broker, leggono file CSV. Devono restare ESCLUSI dal gate altrimenti
    il loro lavoro normale sarebbe falsamente classificato come violazione.
    Questo test e' la guard che evita di aggiungere accidentalmente
    'strategy/adapters/...' a PURE_MODULES.
    """
    leaked = [m for m in PURE_MODULES if m.startswith("strategy/adapters/")]
    assert not leaked, (
        "strategy/adapters/* deve restare ESCLUSO dal purity gate "
        f"(I/O bridge intenzionale): trovato {leaked}"
    )
