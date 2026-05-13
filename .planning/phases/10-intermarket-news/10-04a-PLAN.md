---
phase: 10
plan: 04a
type: execute
wave: 2
depends_on:
  - 10-02
  - 10-03
files_modified:
  - config.py
  - .env.example
  - strategy/confluence.py
  - strategy/context.py
  - strategy/_shim.py
  - strategy/setups/a_breakout.py
  - strategy/setups/b_reversal.py
  - strategy/setups/c_compression.py
  - strategy/setups/d_pullback.py
autonomous: true
requirements:
  - MCP-10

must_haves:
  truths:
    - "config.py _attach_intermarket_macro(Config) chiamato (6 nuovi attributi: ENABLE_INTERMARKET, MACRO_CSV_ROOT, FF_RSS_URL, CALENDAR_CACHE_TTL_MINUTES, CALENDAR_CACHE_PATH, CALENDAR_DEFAULT_WINDOW_MINUTES)"
    - ".env.example documenta i nuovi env (ENABLE_INTERMARKET=false default)"
    - "compute_confidence signature estesa con direction param (Path A da Open Question 3)"
    - "Callsite confluence.py:266 passa direction al intermarket_score_fn (signature 2-arg semplificata Warning #4)"
    - "Hardcoded threshold `score > 0` documentato in commento riferimento Open Question 4 + D-10-D1 (Warning #5)"
    - "TypeError su intermarket_score_fn log.debug + skip adjuster (NO fallback 1-arg, Warning #4)"
    - "4 setups callsite (a_breakout, b_reversal, c_compression, d_pullback) passano direction=direction kwarg"
    - "_shim.py (strategy/_shim.py:83 IntradayStrategy lockedlocation) wire init-time intermarket_score_fn (build se ENABLE_INTERMARKET, None se False)"
    - "ENABLE_INTERMARKET=false default mantiene baseline Phase 5 parquet byte-identical (D-10-D2 verified)"
  artifacts:
    - path: "config.py"
      provides: "_attach_intermarket_macro(Config) con 6 env attributi"
    - path: ".env.example"
      provides: "Documentazione block ENABLE_INTERMARKET + 5 altri env (append fallback se ENABLE_NEWS_SENTIMENT block assente, Warning #9)"
    - path: "strategy/confluence.py"
      provides: "compute_confidence(direction=...) extended signature + Pitfall 5 patch semplificato (Warning #4)"
    - path: "strategy/_shim.py"
      provides: "_build_intermarket_score_fn(cfg) helper + build_ctx_live(intermarket_score_fn=self._intermarket_score_fn) wire (IntradayStrategy locato a _shim.py:83, Warning #8)"
  key_links:
    - from: "strategy/confluence.py:266"
      to: "ctx.intermarket_score_fn(symbol, direction_norm)"
      via: "callsite signature 2-arg only (Warning #4 simplification)"
      pattern: "intermarket_score_fn\\(.*dir_norm"
    - from: "strategy/_shim.py:83 (class IntradayStrategy)"
      to: "intermarket.loader + intermarket.score"
      via: "init-time singleton (graceful failure)"
      pattern: "_build_intermarket_score_fn"

threat_model:
  trust_boundaries:
    - boundary: "config.py->os.environ"
      description: "env var read + bound parsing (max(1, int(...)))"
    - boundary: "strategy/_shim.py (init)->intermarket singletons"
      description: "Graceful bootstrap (try/except log+None on failure)"
  stride_register:
    - id: "T-10-04a-01"
      category: "Tampering (Backward-Compat)"
      component: "compute_confidence signature extend (Pitfall 5 + Warning #4)"
      disposition: "mitigate"
      mitigation: "direction param con default `None` (Path A). Callsite gated `if direction is not None and ctx.intermarket_score_fn is not None`. TypeError catch → _log.debug + skip adjuster (Warning #4 simplification: NO retry 1-arg call). Commento esplicita 'production fn from build_intermarket_score è sempre 2-arg per D-10-D1'. ASVS V5. Pitfall 5."
    - id: "T-10-04a-02"
      category: "DoS (Bootstrap)"
      component: "_shim.py:83 IntradayStrategy._build_intermarket_score_fn"
      disposition: "mitigate"
      mitigation: "try/except graceful: ritorna None on failure, log error, IntradayStrategy continua. Phase 7 ML singleton pattern analog. ASVS V12 partial."
    - id: "T-10-04a-03"
      category: "Data Integrity (D-10-C0)"
      component: "ENABLE_INTERMARKET=false default Phase 5 baseline preservation"
      disposition: "mitigate"
      mitigation: "Default false -> _build_intermarket_score_fn ritorna None -> ctx.intermarket_score_fn=None -> adjuster skipped (existing try/except no-op). Test 10-01 test_phase10_no_phase5_drift ancora PASS. ASVS V6 partial. D-10-D2 zero-impact rollout."
    - id: "T-10-04a-04"
      category: "Tampering (Hardcoded Threshold, Warning #5)"
      component: "strategy/confluence.py:266 `score > 0` threshold"
      disposition: "accept"
      mitigation: "Threshold=0 hardcoded matcha la semantica sign-flip di build_intermarket_score (Claude's Discretion D-10-D1). Commento esplicito documenta retrofit Phase 11+ a cfg.INTERMARKET_THRESHOLD se paper trading rivela tuning need. Consistente con _PAIR_WEIGHTS hardcode (Open Question 4)."
---

<objective>
Wave 2 MCP-10 wiring layer Strategy + Config (split del Plan 10-04 originale, Warning #3): integrare gli artefatti Wave 1 (intermarket/ + calendar_rss/) nel layer Strategy + Config, lasciando il layer MCP (handlers + server + errors) al Plan 10-04b parallel.

Purpose:
- Wire intermarket_score_fn nello strategy pipeline con signature extend backward-compat (D-10-D1 + Pitfall 5 patch).
- ENABLE_INTERMARKET env flag (D-10-D2 zero-impact rollout) — default FALSE per preservare Phase 5 baseline.
- Patch Pitfall 5 visibility semplificata (Warning #4): try/except: pass -> try 2-arg call, on TypeError → _log.debug + skip (no retry 1-arg call dead-code).
- Documentare threshold `score > 0` hardcoded (Warning #5) come Claude's Discretion D-10-D1 semantic match.

Output:
- 9 file modificati (config, .env.example, confluence, context, _shim, 4 setups callsite)
- Phase 4 strategy regression test GREEN
- 0 regression Phase 5 baseline
- Wave 2 parallel partner: 10-04b (MCP layer).
</objective>

<execution_context>
@C:/trading-agent/.claude/get-shit-done/workflows/execute-plan.md
@C:/trading-agent/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/10-intermarket-news/10-01-PLAN.md
@.planning/phases/10-intermarket-news/10-02-PLAN.md
@.planning/phases/10-intermarket-news/10-03-PLAN.md
@.planning/phases/10-intermarket-news/10-CONTEXT.md
@.planning/phases/10-intermarket-news/10-RESEARCH.md
@.planning/phases/10-intermarket-news/10-PATTERNS.md

# File da modificare (lettura OBBLIGATORIA prima di toccare)
@config.py
@.env.example
@strategy/confluence.py
@strategy/context.py
@strategy/_shim.py
@strategy/setups/a_breakout.py
@strategy/setups/b_reversal.py
@strategy/setups/c_compression.py
@strategy/setups/d_pullback.py
@intermarket/__init__.py

<interfaces>
<!-- Contracts critici da PRESERVARE. -->

From strategy/confluence.py:244-269 (signature attuale + callsite da modificare):
```python
def compute_confidence(
    grade, ctx, setup_name,
    factors=None, indicators=None, cfg=None,
) -> float:
    # line 264-269:
    if ctx.intermarket_score_fn is not None:
        try:
            if ctx.intermarket_score_fn(ctx.symbol) > 0:   # signature 1-arg
                delta += float(adj["intermarket_confirmation"])
        except Exception:
            pass  # stub safety
```

From strategy/setups (callsite local var `direction` gia disponibile):
- a_breakout.py:140-143 direction=BUY/SELL locale -> callsite riga 182
- b_reversal.py direction locale -> callsite riga 270
- c_compression.py direction locale -> callsite riga 295
- d_pullback.py direction locale -> callsite riga 264

From strategy/_shim.py:83 (Warning #8 verified location, single candidate):
```python
class IntradayStrategy:
    """Ctor a strategy/_shim.py:83 — UNICA location (verified grep 2026-05-13).
    NESSUNA classe IntradayStrategy in strategy/__init__.py — solo re-export.
    """
```

From strategy/_shim.py:127-135 (ctor flow attuale):
```python
ctx = build_ctx_live(
    symbol=symbol, ..., intermarket_score_fn=None,
    news_blackout_fn=getattr(self.env, "is_news_window", None) if self.env else None,
)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: config.py + .env.example — _attach_intermarket_macro env block</name>
  <files>
    config.py
    .env.example
  </files>
  <read_first>
    - config.py (linea 178 AVOID_MAJOR_NEWS_TIMES legacy, 214-235 _attach_news_sentiment template)
    - .env.example (sezione ENABLE_NEWS_SENTIMENT da imitare — se presente; vedi fallback Warning #9 sotto)
    - .planning/phases/10-intermarket-news/10-RESEARCH.md §config.py extension (Code Example completo)
    - .planning/phases/10-intermarket-news/10-CONTEXT.md D-10-D2 (ENABLE_INTERMARKET=false default)
    - .planning/phases/10-intermarket-news/10-RESEARCH.md §Open Question 5 (AVOID_MAJOR_NEWS_TIMES legacy resolution)
  </read_first>
  <action>
    File 1 — `config.py`:
    Aggiungi dopo `_attach_news_sentiment(Config)` (~linea 235) una NUOVA funzione + chiamata:
    ```python
    def _attach_intermarket_macro(cls):
        """Phase 10 D-10-D2 env block: intermarket + economic calendar (default OFF, zero-impact rollout)."""
        cls.ENABLE_INTERMARKET = _get_bool("ENABLE_INTERMARKET", False)  # D-10-D2
        cls.MACRO_CSV_ROOT = os.getenv("MACRO_CSV_ROOT", "data/historical/macro").strip()
        cls.FF_RSS_URL = os.getenv(
            "FF_RSS_URL",
            "https://nfs.faireconomy.media/ff_calendar_thisweek.xml",
        ).strip()
        cls.CALENDAR_CACHE_TTL_MINUTES = max(1, int(os.getenv("CALENDAR_CACHE_TTL_MINUTES", "60")))
        cls.CALENDAR_CACHE_PATH = os.getenv("CALENDAR_CACHE_PATH", "data/cache/calendar_rss.json").strip()
        cls.CALENDAR_DEFAULT_WINDOW_MINUTES = max(1, int(os.getenv("CALENDAR_DEFAULT_WINDOW_MINUTES", "15")))
        return cls


    _attach_intermarket_macro(Config)
    ```

    Apri-Question 5 sull'AVOID_MAJOR_NEWS_TIMES legacy (linea 178): NON rimuovere. Aggiungi commento sopra la riga:
    ```python
    # DEPRECATED Phase 10 D-10-C0: drop auto-reject blackout. Flag no-op fino a Phase 11+
    # retrofit (vedi .planning/phases/10-intermarket-news/10-CONTEXT.md Deferred Ideas).
    AVOID_MAJOR_NEWS_TIMES: bool = _get_bool("AVOID_MAJOR_NEWS_TIMES", True)
    ```

    File 2 — `.env.example` (Warning #9 — fallback se ENABLE_NEWS_SENTIMENT block assente):
    ```bash
    # Detector: append dopo ENABLE_NEWS_SENTIMENT block (se presente), altrimenti end-of-file
    if grep -q '^ENABLE_NEWS_SENTIMENT=' .env.example; then
        # Trova ultima riga del blocco e appendi dopo
        # (executor: localizza riga ENABLE_NEWS_SENTIMENT=, individua fine blocco contiguo, inserisci sotto)
        echo "append dopo ENABLE_NEWS_SENTIMENT block"
    else
        # Append at end-of-file (fallback Warning #9)
        echo "append at end-of-file"
    fi
    ```
    Contenuto del blocco da appendere:
    ```
    # ============================================================================
    # Phase 10: Intermarket + Economic Calendar (MCP-10 / MCP-13)
    # ============================================================================
    # D-10-D2: zero-impact rollout. Default OFF preserva Phase 5 baseline parquet
    # byte-identical (1076 x 59 cols). Flip a true SOLO post-Phase-11 paper trading
    # se metric mostra value-add dell'intermarket adjuster.
    ENABLE_INTERMARKET=false

    # Root path dei 4 macro CSV statici committati (DXY/US10Y/XAUUSD/WTI/daily.csv).
    # Refresh manuale via scripts/refresh_macro_csv.py (Plan 10-05).
    MACRO_CSV_ROOT=data/historical/macro

    # ForexFactory RSS feed URL (next 7 days, default NY timezone).
    FF_RSS_URL=https://nfs.faireconomy.media/ff_calendar_thisweek.xml

    # Cache TTL on-demand fetch FF feed (minuti). D-10-B2 default 60.
    CALENDAR_CACHE_TTL_MINUTES=60

    # Path JSON cache (gitignored, sopravvive restart).
    CALENDAR_CACHE_PATH=data/cache/calendar_rss.json

    # Default window_minutes per get_economic_calendar (D-10-B4).
    CALENDAR_DEFAULT_WINDOW_MINUTES=15
    ```

    Tutti i commenti italiani.
  </action>
  <verify>
    <automated>python -c "from config import Config; c=Config; assert c.ENABLE_INTERMARKET is False; assert c.MACRO_CSV_ROOT == 'data/historical/macro'; assert c.FF_RSS_URL.startswith('https://nfs.faireconomy.media'); assert c.CALENDAR_CACHE_TTL_MINUTES == 60; assert c.CALENDAR_DEFAULT_WINDOW_MINUTES == 15; print('config OK')" && grep -q "^ENABLE_INTERMARKET=false" .env.example && grep -q "DEPRECATED Phase 10 D-10-C0" config.py</automated>
  </verify>
  <done>
    - config.py contiene _attach_intermarket_macro + chiamata
    - 6 nuovi Config attributes (default ENABLE_INTERMARKET=False)
    - AVOID_MAJOR_NEWS_TIMES tenuto con commento DEPRECATED (Open Question 5)
    - .env.example documenta il blocco Phase 10 con 6 env italiano (append dopo ENABLE_NEWS_SENTIMENT block se presente, fallback end-of-file Warning #9)
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: strategy/confluence.py + context.py + 4 setups — signature extend direction (Path A) + Pitfall 5 semplificato (Warning #4)</name>
  <files>
    strategy/confluence.py
    strategy/context.py
    strategy/setups/a_breakout.py
    strategy/setups/b_reversal.py
    strategy/setups/c_compression.py
    strategy/setups/d_pullback.py
  </files>
  <read_first>
    - strategy/confluence.py (intera compute_confidence linee 244-300, callsite Pitfall 5 a 264-269)
    - strategy/context.py (linee 7-23 dataclass StrategyContext)
    - strategy/setups/a_breakout.py:140-185 (direction local var + callsite riga 182)
    - strategy/setups/b_reversal.py riga 270 callsite
    - strategy/setups/c_compression.py riga 295 callsite
    - strategy/setups/d_pullback.py riga 264 callsite
    - .planning/phases/10-intermarket-news/10-RESEARCH.md §strategy/confluence.py:266 modify + §Open Question 3 (Path A scelto)
    - .planning/phases/10-intermarket-news/10-RESEARCH.md §Pitfall 5 (try/except pass replace)
  </read_first>
  <action>
    File 1 — `strategy/context.py`:
    Trova riga 17 (intermarket_score_fn) e sostituisci il commento:
    ```python
    intermarket_score_fn: Callable | None = None  # D-10-D1: fn(symbol, direction) -> float [-1,1]
    news_blackout_fn: Callable | None = None      # Phase 11+ retrofit (D-10-C0: drop blackout in Phase 10)
    ```

    File 2 — `strategy/confluence.py`:
    Step 2a — Header logger (se assente):
    ```python
    import logging
    _log = logging.getLogger(__name__)
    ```

    Step 2b — Estendi signature `compute_confidence` (linea 244):
    ```python
    def compute_confidence(
        grade: Grade,
        ctx: StrategyContext,
        setup_name: str,
        factors: dict[str, bool] | None = None,
        indicators=None,
        cfg: StrategyConfig | None = None,
        direction: str | None = None,  # D-10-D1: Path A Open Question 3
    ) -> float:
    ```
    Aggiorna docstring "Calibra confidence..." per documentare:
    ```
    Args:
        direction: 'BUY' | 'SELL' | None. Quando provided + intermarket_score_fn disponibile,
                   callsite passa direction (normalizzato long/short) al adjuster sign-flip.
                   Default None per backward-compat (Pitfall 5).
    ```

    Step 2c — Sostituisci callsite (linee 263-269) con (**Warning #4 simplification + Warning #5 documentation**):
    ```python
    # Adjuster 1: intermarket_confirmation (D-10-D1 signature extend + Pitfall 5 visibility).
    #
    # Warning #4 (semplificazione retry semantics): la production fn da
    # `build_intermarket_score` (intermarket/score.py) e' SEMPRE 2-arg per D-10-D1.
    # L'unica 1-arg legacy proviene da test stub (lambda s: 0.0). On TypeError →
    # _log.debug + skip adjuster (NO fallback 1-arg call): il path 1-arg e' test-only,
    # mai production.
    #
    # Warning #5 (threshold hardcoded): la soglia `score > 0` matcha la semantica
    # sign-flip di build_intermarket_score (Claude's Discretion D-10-D1). Phase 11+
    # retrofit a `cfg.INTERMARKET_THRESHOLD` se paper trading rivela tuning need.
    # Coerente con _PAIR_WEIGHTS hardcode (Open Question 4).
    if ctx.intermarket_score_fn is not None and direction is not None:
        # Normalize BUY/SELL -> long/short per D-10-D1 contract intermarket/score.py
        dir_norm = "long" if direction == "BUY" else ("short" if direction == "SELL" else None)
        if dir_norm is not None:
            try:
                score = ctx.intermarket_score_fn(ctx.symbol, dir_norm)
                if score > 0:  # threshold 0 hardcoded D-10-D1 semantic match (Warning #5)
                    delta += float(adj["intermarket_confirmation"])
            except TypeError:
                # Pitfall 5 + Warning #4: stub legacy 1-arg test-only — production fn
                # da build_intermarket_score e' sempre 2-arg per D-10-D1. Skip adjuster
                # silently con _log.debug per visibilita'.
                _log.debug(
                    "intermarket_score_fn signature legacy 1-arg detected, skipping adjuster (Pitfall 5)"
                )
            except Exception as exc:
                # Pitfall 5: NON pass silente. _log.debug per visibility errori inattesi.
                _log.debug("intermarket_score_fn errore: %s", exc)
    ```

    File 3-6 — Modifica callsite nei 4 setups (aggiungi kwarg `direction=direction`):

    `strategy/setups/a_breakout.py` riga ~182:
    ```python
    confidence = compute_confidence(
        grade, ctx, "A_breakout", factors=factors, indicators=indicators, direction=direction,
    )
    ```

    `strategy/setups/b_reversal.py` riga ~270:
    ```python
    confidence = compute_confidence(
        grade, ctx, "B_reversal", factors=factors, indicators=indicators, direction=direction,
    )
    ```

    `strategy/setups/c_compression.py` riga ~295:
    ```python
    confidence = compute_confidence(
        grade, ctx, "C_compression", factors=factors, indicators=indicators, direction=direction,
    )
    ```

    `strategy/setups/d_pullback.py` riga ~264:
    ```python
    confidence = compute_confidence(
        grade, ctx, "D_pullback", factors=factors, indicators=indicators, direction=direction,
    )
    ```

    NB: `direction` gia disponibile come local var in ognuno dei 4 setup (verified grep Wave 0). NO altro cambio. Tutti i commenti italiani.
  </action>
  <verify>
    <automated>pytest tests/test_strategy_confluence.py tests/test_setup_a_breakout.py tests/test_setup_b_reversal.py tests/test_setup_c_compression.py tests/test_setup_d_pullback.py -x --tb=short 2>&1 | tail -10 && python -c "from strategy.confluence import compute_confidence; import inspect; sig = inspect.signature(compute_confidence); assert 'direction' in sig.parameters, 'direction param missing'; assert sig.parameters['direction'].default is None, 'direction default not None'; print('signature OK')" && grep -q "Warning #4" strategy/confluence.py && grep -q "Warning #5" strategy/confluence.py</automated>
  </verify>
  <done>
    - strategy/confluence.py compute_confidence signature estesa con direction param (Path A backward-compat default None)
    - Callsite intermarket_score_fn passa (symbol, dir_norm) con normalize BUY->long SELL->short
    - Warning #4: TypeError catch → _log.debug + skip adjuster (NO fallback 1-arg call dead-code)
    - Warning #5: commento esplicita threshold `score > 0` hardcoded D-10-D1 semantic match + retrofit Phase 11+ documentato
    - _log.debug per visibility silent failure
    - 4 setups callsite aggiornati con direction=direction kwarg
    - Test Phase 4 setups GREEN (no regression)
    - strategy/context.py:17-18 commento aggiornato (D-10-D1 + news_blackout_fn dormant)
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: strategy/_shim.py — wire intermarket_score_fn init-time singleton (location locked _shim.py:83, Warning #8)</name>
  <files>
    strategy/_shim.py
  </files>
  <read_first>
    - strategy/_shim.py (intero file; **class IntradayStrategy a riga 83** — verified grep 2026-05-13: NO altre classi con quel nome nel codebase, NO ctor in __init__.py)
    - .planning/phases/10-intermarket-news/10-RESEARCH.md §strategy/_shim.py:133 modify (Code Example completo lines 920-941)
    - .planning/phases/10-intermarket-news/10-CONTEXT.md D-10-D2 (ENABLE_INTERMARKET zero-impact rollout)
    - intermarket/__init__.py (build_intermarket_score + MacroLoader API)
  </read_first>
  <action>
    **Warning #8: location locked a `strategy/_shim.py:83 (class IntradayStrategy)`.** Verified via grep:
    `grep -nE "class IntradayStrategy" strategy/_shim.py strategy/__init__.py`
    → unica match: `strategy/_shim.py:83`. NESSUNA modifica a `strategy/__init__.py` (solo re-export, niente ctor).

    Step 1 — Nel `__init__` della class IntradayStrategy (strategy/_shim.py:83), aggiungi PRIMA del primo body statement non-assignment:
    ```python
        # Phase 10 D-10-D2: init-time intermarket_score_fn (zero-impact rollout)
        self._intermarket_score_fn = self._build_intermarket_score_fn(cfg)
    ```

    Step 2 — Aggiungi metodo statico `_build_intermarket_score_fn` alla classe IntradayStrategy (strategy/_shim.py):
    ```python
        @staticmethod
        def _build_intermarket_score_fn(cfg):
            """D-10-D2 zero-impact rollout. Default OFF; opt-in via ENABLE_INTERMARKET=true env.

            Returns None se ENABLE_INTERMARKET=false o se bootstrap fallisce (graceful).
            """
            if not getattr(cfg, "ENABLE_INTERMARKET", False):
                return None
            try:
                from intermarket.loader import MacroLoader
                from intermarket.score import build_intermarket_score
                root = getattr(cfg, "MACRO_CSV_ROOT", "data/historical/macro")
                loader = MacroLoader.from_repo(root=root)
                return build_intermarket_score(loader)
            except Exception as exc:
                logging.getLogger(__name__).error(
                    "IntradayStrategy intermarket bootstrap fallito (graceful, None): %s", exc
                )
                return None
    ```
    (verifica `import logging` presente nel file `strategy/_shim.py`; se assente aggiungere alle import header).

    Step 3 — Modifica callsite `build_ctx_live(intermarket_score_fn=None, ...)` a riga ~133 di strategy/_shim.py:
    Sostituisci `intermarket_score_fn=None` con `intermarket_score_fn=self._intermarket_score_fn`. La modifica conserva backward-compat: se ENABLE_INTERMARKET=false, `self._intermarket_score_fn` è None (zero diff rispetto al comportamento pre-Phase-10).

    Tutti i commenti italiani.

    NB: NESSUNA modifica a `strategy/__init__.py` (Warning #8: ctor location locked a _shim.py:83 unica).
    NB: NESSUNA modifica a `strategy/adapters/live.py` o `strategy/adapters/backtest.py` (signature `intermarket_score_fn: Callable | None = None` gia accetta entrambi i casi).
  </action>
  <verify>
    <automated>pytest tests/test_strategy_shim.py tests/test_setup_a_breakout.py -x --tb=short 2>&1 | tail -10 && python -c "from strategy._shim import IntradayStrategy; import inspect; assert hasattr(IntradayStrategy, '_build_intermarket_score_fn'), 'helper missing'; print('shim wire OK')" && grep -nE "intermarket_score_fn=self\._intermarket_score_fn|_build_intermarket_score_fn" strategy/_shim.py && grep -cE "^class IntradayStrategy" strategy/_shim.py | grep -q "^1$"</automated>
  </verify>
  <done>
    - strategy/_shim.py:83 IntradayStrategy.__init__ inizializza self._intermarket_score_fn = self._build_intermarket_score_fn(cfg)
    - _build_intermarket_score_fn statico: ENABLE_INTERMARKET=false -> None; true -> MacroLoader.from_repo + build_intermarket_score (graceful try/except)
    - build_ctx_live(intermarket_score_fn=self._intermarket_score_fn) wired
    - Test Phase 4 shim suite GREEN (no regression)
    - D-10-D2 zero-impact rollout verificato: ENABLE_INTERMARKET=false invariato vs pre-Phase-10
    - Warning #8: location locked, nessuna ambiguità _shim.py vs __init__.py
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| config.py->os.environ | env var read + bound parsing (`max(1, int(...))`) |
| strategy/_shim.py:83 (init)->intermarket singletons | Graceful bootstrap (try/except log+None on failure) |
| strategy/confluence.py:266->ctx.intermarket_score_fn | 2-arg call only (Warning #4: NO fallback 1-arg in production) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-10-04a-01 | Tampering (Backward-Compat) | compute_confidence signature extend (Pitfall 5 + Warning #4) | mitigate | direction param default None. TypeError catch → _log.debug + skip adjuster. Production fn sempre 2-arg per D-10-D1; 1-arg path test-stub-only (Warning #4 semplificazione: NO retry dead code). ASVS V5. |
| T-10-04a-02 | DoS (Bootstrap) | _shim.py:83 IntradayStrategy._build_intermarket_score_fn | mitigate | try/except graceful: ritorna None on failure, log error, IntradayStrategy continua. Pattern Phase 7 ML singleton analog. ASVS V12 partial. |
| T-10-04a-03 | Data Integrity (D-10-C0) | ENABLE_INTERMARKET=false default Phase 5 preservation | mitigate | Default false -> _build_intermarket_score_fn None -> ctx.intermarket_score_fn=None -> adjuster skipped. Test 10-01 immutability gate PASS. ASVS V6 partial. D-10-D2. |
| T-10-04a-04 | Spoofing (Direction Mismatch) | dir_norm BUY->long SELL->short normalize | mitigate | Hardcoded mapping in confluence.py callsite. dir_norm=None se direction not in (BUY, SELL) -> adjuster skipped safely. ASVS V5. |
| T-10-04a-05 | Tampering (Hardcoded Threshold, Warning #5) | strategy/confluence.py:266 `score > 0` | accept | Threshold=0 hardcoded matcha semantica sign-flip D-10-D1 (Claude's Discretion). Commento esplicita retrofit Phase 11+ a cfg.INTERMARKET_THRESHOLD. Coerente con _PAIR_WEIGHTS hardcode (Open Question 4). |
</threat_model>

<verification>
After all 3 tasks complete:

```bash
# Phase 4 strategy regression (signature extend backward-compat)
pytest tests/test_strategy_confluence.py tests/test_strategy_shim.py \
       tests/test_setup_a_breakout.py tests/test_setup_b_reversal.py \
       tests/test_setup_c_compression.py tests/test_setup_d_pullback.py \
       -x --tb=short
# Atteso: tutti GREEN (no regression)

# Phase 10 immutability gate still PASS (ENABLE_INTERMARKET=false default)
pytest tests/test_phase10_no_phase5_drift.py -x --tb=short
# Atteso: 5 passed (1 skipif if parquet non in Codespace)

# Full suite
pytest -x --tb=short 2>&1 | tail -5
# Atteso: passed count >= baseline pre-10-04a + zero new failure

# Warning #4 + #5 marker grep
grep -c "Warning #4\|Warning #5" strategy/confluence.py
# Atteso: >= 2
```

D-10-D2 baseline preservation manual gate (PC con parquet, post Wave 1+2):
```bash
ENABLE_INTERMARKET=false pytest tests/test_phase10_no_phase5_drift.py -x --tb=short
# Atteso: 5 passed (gate ATTIVO incluso umbrella canonical test_baseline_immutato_with_flag_off)
```
</verification>

<success_criteria>
- [x] config.py contiene _attach_intermarket_macro + 6 env attributi (ENABLE_INTERMARKET=false default)
- [x] .env.example documenta i 6 env Phase 10 in italiano (append fallback Warning #9)
- [x] strategy/confluence.py compute_confidence(direction=...) extended + Warning #4 simplification + Warning #5 documentation
- [x] strategy/context.py:17-18 commenti aggiornati (D-10-D1 + news_blackout_fn dormant)
- [x] 4 setups callsite passano direction=direction
- [x] strategy/_shim.py:83 _build_intermarket_score_fn helper + ctor wire init-time singleton (Warning #8 location locked)
- [x] Phase 4 strategy regression GREEN (no regression)
- [x] D-10-D2 verified: ENABLE_INTERMARKET=false preserva Phase 5 baseline byte-identical
- [x] Wave 2 parallel partner Plan 10-04b (MCP layer) può essere eseguito simultaneamente
</success_criteria>

<output>
After completion, create `.planning/phases/10-intermarket-news/10-04a-SUMMARY.md` con:
- File modificati + LOC delta (config.py ~15, .env.example ~25, confluence.py ~30 delta incluso comment block, _shim.py ~25 delta, 4 setups ~4 delta cad.)
- Test pass count flipped (Phase 4 strategy regression GREEN)
- D-10-D2 baseline preservation check result
- Warning #4 simplification documentation (TypeError dead-code path eliminated)
- Warning #5 threshold hardcoded retrofit plan Phase 11+
- Warning #8 location locked _shim.py:83
- Warning #9 .env.example append fallback applied
- Open Question 3 resolution: Path A scelto
- Open Question 5 resolution: AVOID_MAJOR_NEWS_TIMES tenuto DEPRECATED
- Next: Plan 10-04b (MCP layer) in Wave 2 parallel + Plan 10-05 (ops + docs Wave 3)
</output>
</output>
