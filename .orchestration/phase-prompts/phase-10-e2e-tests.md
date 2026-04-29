# Fase 10 — E2E + Tests + README

## Obiettivo
Test E2E su demo FP Markets, finalizzare `tests/test_mt5.py` e `README.md` completo in italiano.

## File da creare/finalizzare

### 1. `tests/test_mt5.py`

`pytest` con skip condizionato:
```python
import os, pytest
from config import Config
from mt5_client import Mt5Client

pytestmark = pytest.mark.skipif(
    not os.getenv("MT5_LOGIN") or not os.getenv("MT5_PASSWORD"),
    reason="MT5 credentials non configurate, skip test ambiente reale"
)

@pytest.fixture(scope="module")
def client():
    cfg = Config()
    c = Mt5Client(cfg)
    if not c.initialize() or not c.login():
        pytest.skip("MT5 initialize/login failed")
    yield c
    c.shutdown()

def test_get_account_state(client):
    state = client.get_account_state()
    assert state.balance >= 0
    assert isinstance(state.open_positions, list)

def test_get_symbol_info(client):
    info = client.get_symbol_info("EURUSD")
    assert info is not None
    assert info.point > 0

def test_get_ohlc(client):
    bars = client.get_ohlc("EURUSD", "M15", 50)
    assert len(bars) == 50
    assert "open" in bars[0]
```

### 2. `README.md` (in italiano, definitivo)

Sezioni obbligatorie:

1. Introduzione — cosa fa il progetto, architettura a blocchi.
2. Prerequisiti — Python 3.12 64-bit, MetaTrader5 installato, conto demo FP Markets, API key Anthropic.
3. Setup:
   ```powershell
   git clone <repo>
   cd trading-agent
   python -m venv .venv
   .venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   copy .env.example .env
   notepad .env   # compila le credenziali
   ```
4. Setup MT5 FP Markets demo — link al sito, come ottenere login/password/server.
5. Lancio in modalità shadow — `python main.py`, cosa aspettarsi nei log.
6. Uso diretto di `claude_agent.py` — esempio Python.
7. Avvio MCP server — `python mcp_server.py`, cosa appare in stderr.
8. Configurazione Claude Desktop:
   - Path: `%APPDATA%\Claude\claude_desktop_config.json`
   - JSON da incollare (con backslash doppi)
   - Riavvio dell'app
   - Verifica: icona tool → deve mostrare `trading-agent` con i 6 tool.
9. Passaggio shadow → paper → live con avvertenze:
   - Almeno 1 settimana di shadow prima di paper.
   - Almeno 1 settimana di paper prima di live.
   - Cambio `EXECUTION_MODE` nel `.env`, mai nel codice.
10. Tests:
    ```powershell
    pytest tests/ -v
    ```
11. Audit trail — `logs/agent.log` e `logs/trades.db`. Esempio di query SQLite.
12. FAQ / Troubleshooting — top 5 errori comuni con soluzioni.
13. Disclaimer — uso a proprio rischio, non è consulenza finanziaria.

### 3. Esecuzione test E2E

Procedura completa:
1. `.env` con credenziali demo, `EXECUTION_MODE=shadow`.
2. `python main.py` → almeno 5 cicli su EURUSD, GBPUSD.
3. Verifica `logs/trades.db`: deve contenere righe sia approvate sia rifiutate.
4. Cambia `EXECUTION_MODE=paper`, ripeti → ordini visibili in MT5.
5. Apri Claude Desktop, chiedi:
   - "Qual è lo stato del mio account?"
   - "Valuta un BUY EURUSD a mercato con SL 30 pips e TP 60 pips."
   - "Mostrami le ultime 5 operazioni."
6. Verifica che ogni chiamata MCP sia loggata in `agent.log`.

### 4. Checklist finale (da includere in fondo a STATE.md)

- [ ] Risk engine ha rifiutato almeno un trade per ogni branch (kill switch, SL, sessione, margine).
- [ ] Logger registra 100% delle decisioni.
- [ ] MCP server riconosciuto da Claude Desktop, 6 tool visibili.
- [ ] `claude_agent.run_cycle` produce proposte coerenti senza loop infinito.
- [ ] `explain_last_trades(5)` produce riassunto in italiano leggibile.
- [ ] `pytest tests/` tutto verde (con skip MT5 se non disponibile).
- [ ] `README.md` ha tutte le 13 sezioni.

## Commit attesi
```
test(mt5): add e2e tests with skip on missing credentials
docs(readme): complete italian readme with 13 sections
feat(phase-10): complete and validated — project ready
```

## Note finali

Dopo Fase 10:
- Tag git: `git tag -a v1.0.0 -m "Trading agent MVP ready for shadow testing"`
- Push tag: `git push origin v1.0.0`
- Aggiorna `STATE.md` → `session_status: COMPLETED`, tutte le fasi `VALIDATED`.
