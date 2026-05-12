---
created: 2026-05-11
project: trading-agent
purpose: guida step-by-step per configurare un PC secondario che esegua il backtest Plan 05-09 in parallelo al lavoro GSD sul PC primario
linked_from: .planning/RESUME-PLAN.md (STEP 7)
target_audience: utente progetto (Francesco) — operazione manuale, non automatica
---

> **IMPORTANTE — root cause incidente 2026-05-12:** sul secondario era stato fatto un *download ZIP* del branch invece di un `git clone`. Risultato: `config/strategy.yaml` e altri file di config con drift silenzioso → `profile_filters` letti in modo invertito → backtest ha prodotto 419 rows (CONSERVATIVE 205 > MODERATE 151 > AGGRESSIVE 63) invece dei 1076 attesi (AGGRESSIVE 540 > MODERATE 448 > CONSERVATIVE 88), spreco ~3h wall-clock. **Da ora in poi: SOLO `git clone`, MAI download ZIP.** Il §2 pre-flight ora include una verifica SHA256 esplicita su `config/strategy.yaml` che intercetta questa classe di problema in <5 secondi.

# Setup PC Secondario — Esecuzione Backtest Plan 05-09

> **Scopo:** distribuire il carico tra due PC. Il PC primario (questo) orchestra GSD (Phase 6 execute + discuss-phase 8/9/10/11 + plan Phase 5). Il PC secondario esegue solo lo script Python del Plan 05-09 (~3h18m wall-clock).
>
> **Vincolo dichiarato:** il PC primario non regge backtest 23.5y + altre attività in parallelo.

---

## 0. Prerequisiti

### 0.1 — Sul PC secondario (chiunque sia)

| Item | Min | Note |
|------|-----|------|
| **Sistema operativo** | Windows 10+ / Ubuntu 22.04+ / macOS 13+ | Vedi path A/B/C sotto |
| **Python** | **ESATTAMENTE 3.12.x** | ⚠️ **NO 3.13, NO 3.14, NO altre versioni.** Su 3.13+ `pydantic-core` non ha wheel precompiled e pip prova a compilare da source con Rust + MSVC `link.exe` → fallisce su Windows senza Visual Studio Build Tools. Su 3.12 wheel precompiled = install in 30s. Su Windows usa `py -3.12 -m venv .venv` per forzare la versione corretta. Verifica `python --version` mostra 3.12.x dopo `activate`. Incidente 2026-05-12: Python 3.14 ha bloccato install requirements.txt. |
| **RAM** | 8 GB | Worker pool fino a 9 processi paralleli |
| **CPU** | 4+ core | Ottimale 8+ (worker = min(9, cpu_count)) |
| **Disco libero** | 2 GB | Repo ~300 MB + .venv ~500 MB + output ~50 MB + buffer |
| **Git** | qualsiasi recente | Per clone e push risultati |
| **GitHub account** | con accesso al repo | Push branch o PR per consegnare risultati |
| **Connessione internet** | stabile | Solo per clone + push, non durante run |

### 0.2 — Sul PC primario (questo, da fare PRIMA di passare al secondario)

- [ ] Plan 05-09 esistente e plan-checker PASS (STEP 6 di RESUME-PLAN.md completato)
- [ ] Script wrapper creato: `scripts/run_baseline_05_09.py` (deve essere committato nel Plan 05-09)
- [ ] Pytest del writer esteso committato: `tests/test_baseline_dataset_writer.py` (validation schema)
- [ ] Commit pushato su `feature/update-pythono-pure-strategy`: `git push origin feature/update-pythono-pure-strategy`
- [ ] **`.env.backtest.example` committato** (template minimal solo-backtest, valori allineati al `.env` primario). Sul secondario sarà `cp .env.backtest.example .env`. Vantaggi: zero trasferimento manuale, riproducibile via git, valori commitati = audit trail.

---

## 1. Scegli la strada di setup

Tre opzioni equivalenti per il risultato. Scegli in base all'OS dell'altro PC e alle tue preferenze.

| Path | OS | Pro | Contro | Tempo setup |
|------|------|-----|--------|-------------|
| **A — Python nativo** | Linux/macOS | Veloce, no Docker | MetaTrader5 da skippare manualmente | ~10 min |
| **B — Python nativo** | Windows | Setup identico al PC primario | MT5 si installa anche se non serve | ~15 min |
| **C — Docker devcontainer** | Tutti | Identico al PC primario, isolato, portabile | Richiede Docker Desktop + ~2 GB immagine | ~20-30 min |

**Raccomandazione:** se l'altro PC è Windows → **Path B**. Se Linux/Mac → **Path A**. Se vuoi massima riproducibilità o usi VS Code Remote-Containers → **Path C**.

---

## PATH A — Python nativo su Linux/macOS

### A.1 — Verifica Python 3.12

```bash
python3 --version    # Deve essere 3.12.x
which python3
```

Se manca o è versione sbagliata:
- **Ubuntu/Debian**: `sudo apt update && sudo apt install python3.12 python3.12-venv python3-pip`
- **macOS (Homebrew)**: `brew install python@3.12`
- **Altri**: scarica da https://www.python.org/downloads/

### A.2 — Clona il repo

> **CRITICO: usa `git clone`, NON il download ZIP da GitHub.** Il download ZIP non garantisce coerenza di tutti i file di config (incidente 2026-05-12: drift silenzioso su `config/strategy.yaml` ha prodotto backtest con risultato invertito sui profili rischio). Con `git clone` ogni file ha l'hash blob verificato da git.

```bash
cd ~                                                              # o dove preferisci
git clone https://github.com/<tuo-user>/trading-agent.git         # sostituisci con URL reale
cd trading-agent
git checkout feature/update-pythono-pure-strategy
git pull
```

**Verifica:**
```bash
git log -1 --oneline    # Deve mostrare l'ultimo commit del PC primario con Plan 05-09
ls data/historical/     # Deve mostrare EURUSD/ GBPUSD/ USDJPY/
ls scripts/run_baseline_05_09.py    # Deve esistere
ls data/configs/baseline.yaml       # Deve esistere
```

### A.3 — Crea venv e installa deps

```bash
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Installa requirements MA escludi MetaTrader5 (solo Windows, non serve per backtest)
grep -v "^MetaTrader5" requirements.txt > requirements-backtest.txt

# Aggiungi tqdm esplicitamente (bug latente nel requirements.txt principale)
echo "tqdm>=4.66" >> requirements-backtest.txt

pip install -r requirements-backtest.txt
pip install -r requirements-dev.txt    # pandas-ta per oracle test
```

**Verifica deps:**
```bash
python -c "import pyarrow, pandas, yaml, tqdm; print('OK runtime deps')"
python -c "from backtest.baseline.runner import load_baseline_config; print('OK import backtest module')"
```

### A.4 — Configura .env minimo

Per il backtest **non servono** MT5 credenziali né Claude API. Bastano i parametri di profilo rischio e strategia. Il repo include `.env.backtest.example` già pronto, con valori identici al `.env` del PC primario (audit trail via git, niente trasferimento manuale):

```bash
cp .env.backtest.example .env
```

**Verifica:**
```bash
python -c "import config; print('OK config load')"
```

> Se in futuro qualcuno aggiunge env vars al backtest, aggiornare `.env.backtest.example` nel repo invece di chiedere all'utente di trasferire chiavi manualmente.

→ Vai alla sezione **2 — Pre-flight + Run** sotto.

---

## PATH B — Python nativo su Windows

### B.1 — Verifica Python 3.12 (CRITICO — NO 3.13/3.14)

In PowerShell:
```powershell
# Lista TUTTE le versioni Python installate
py -0
# Deve includere `-V:3.12` o `-V:3.12-64`. Se manca, vedi sotto.

# Verifica versione di default
python --version
```

Se 3.12 manca o non è di default:

1. Scarica **Python 3.12.x** (NON 3.13, NON 3.14) da https://www.python.org/downloads/release/python-31210/ (o release 3.12.x più recente).
2. Durante installazione spunta:
   - ✅ "Add Python to PATH"
   - ✅ Mantieni attivo il `py` launcher (default)
3. **NON** disinstallare versioni Python preesistenti — basta avere 3.12 anche solo affianco. Userai `py -3.12` per forzare l'uso.

> ⚠️ Se hai già provato l'install requirements.txt con Python ≥ 3.13 e visto errori tipo `Failed building wheel for pydantic-core` / `linker link.exe not found` / `Rust not found` → è esattamente questo problema. La soluzione NON è installare Rust / Visual Studio Build Tools (~5 GB di download). È usare Python 3.12, che ha wheel precompiled per tutte le deps del repo.

### B.2 — Clona il repo

> **CRITICO: usa `git clone`, NON il download ZIP da GitHub.** Il download ZIP non garantisce coerenza di tutti i file di config (incidente 2026-05-12: drift silenzioso su `config/strategy.yaml` ha prodotto backtest con risultato invertito sui profili rischio). Con `git clone` ogni file ha l'hash blob verificato da git.

```powershell
cd C:\
git clone https://github.com/<tuo-user>/trading-agent.git
cd C:\trading-agent
git checkout feature/update-pythono-pure-strategy
git pull
```

**Verifica:**
```powershell
git log -1 --oneline
dir data\historical
dir scripts\run_baseline_05_09.py
dir data\configs\baseline.yaml
```

### B.3 — Crea venv e installa deps

> **USA `py -3.12`, NON `python`**, per evitare di prendere una versione Python diversa di default.

```powershell
# Forza Python 3.12 per la venv (anche se altre versioni sono installate)
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
# Se PowerShell blocca lo script: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# Verifica DENTRO la venv: deve essere 3.12.x
python --version

python -m pip install --upgrade pip setuptools wheel

# Su Windows MetaTrader5 si installa senza problemi (è il suo OS nativo).
# Lo installiamo ma NON lo importeremo (il modulo backtest non lo usa).
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Aggiungi tqdm esplicitamente (bug latente)
pip install "tqdm>=4.66"
```

**Verifica deps:**
```powershell
python -c "import pyarrow, pandas, yaml, tqdm; print('OK runtime deps')"
python -c "from backtest.baseline.runner import load_baseline_config; print('OK import backtest module')"
```

### B.4 — Configura .env

Il repo include `.env.backtest.example` già pronto, con valori identici al `.env` del PC primario:

```powershell
copy .env.backtest.example .env
```

**Verifica:**
```powershell
python -c "import config; print('OK config load')"
```

> Se in futuro qualcuno aggiunge env vars al backtest, aggiornare `.env.backtest.example` nel repo invece di chiedere all'utente di trasferire chiavi manualmente.

→ Vai alla sezione **2 — Pre-flight + Run** sotto.

---

## PATH C — Docker devcontainer (cross-platform)

### C.1 — Installa Docker Desktop

- **Windows/macOS**: https://www.docker.com/products/docker-desktop/
- **Linux**: `sudo apt install docker.io docker-compose` (Ubuntu) o equivalente

Conferma:
```bash
docker --version
docker ps    # deve rispondere senza errori
```

### C.2 — Installa VS Code + Dev Containers extension

- VS Code: https://code.visualstudio.com/
- Extension: cerca "Dev Containers" (id `ms-vscode-remote.remote-containers`)

### C.3 — Clona e apri in container

> **CRITICO: usa `git clone`, NON il download ZIP da GitHub.** Il download ZIP non garantisce coerenza di tutti i file di config (incidente 2026-05-12: drift silenzioso su `config/strategy.yaml` ha prodotto backtest con risultato invertito sui profili rischio). Con `git clone` ogni file ha l'hash blob verificato da git.

```bash
git clone https://github.com/<tuo-user>/trading-agent.git
cd trading-agent
git checkout feature/update-pythono-pure-strategy
git pull
code .
```

In VS Code: `F1` → "Dev Containers: Reopen in Container" → attende build (~5-10 min primo run).

### C.4 — Setup deps dentro container

Apri terminale integrato VS Code (è dentro il container):

```bash
# Stesso flow del Path A (il container è Ubuntu-based)
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
grep -v "^MetaTrader5" requirements.txt > requirements-backtest.txt
echo "tqdm>=4.66" >> requirements-backtest.txt
pip install -r requirements-backtest.txt
pip install -r requirements-dev.txt
```

### C.5 — .env nel container

Il repo include `.env.backtest.example` già pronto:

```bash
cp .env.backtest.example .env
```

→ Vai alla sezione **2 — Pre-flight + Run** sotto.

---

## 2. Pre-flight check (OBBLIGATORIO prima del full run)

> **Tempo totale:** ~1-2 minuti. **Non saltare**: scopre il 95% dei bug schema/writer/config prima di sprecare 3h18m.

### 2.0 — Integrity check `config/strategy.yaml` (5 secondi)

> Aggiunto post-incidente 2026-05-12 (file YAML drift sul secondario → backtest invertito sui profili rischio). PRIMA di tutto il resto, verifica che `config/strategy.yaml` sia esattamente quello commitato:

**Linux/macOS/Docker:**
```bash
sha256sum config/strategy.yaml
```

**Windows PowerShell:**
```powershell
Get-FileHash config\strategy.yaml -Algorithm SHA256
```

**Atteso (al commit 2026-05-12 — aggiorna questo valore se il file cambia in futuro):**
```
1570bcd8732642d293854aef4487659fccd1e653ea4e6df691bf98aece5b90dc  config/strategy.yaml
```

Verifica anche che `profile_filters` sia nell'ordine canonico (CONSERVATIVE tight → AGGRESSIVE loose):
```bash
grep -A 3 "^profile_filters:" config/strategy.yaml
# Atteso:
# profile_filters:
#   CONSERVATIVE: {min_grade: "A",  min_rr: 2.5, min_confidence: 0.65}
#   MODERATE:     {min_grade: "B",  min_rr: 1.8, min_confidence: 0.50}
#   AGGRESSIVE:   {min_grade: "C",  min_rr: 1.3, min_confidence: 0.40}
```

- [ ] SHA combacia
- [ ] `profile_filters` ha CONSERVATIVE con min_rr 2.5 (gate tighter) e AGGRESSIVE con min_rr 1.3 (gate looser) — se invertito, **STOP** e ricloniare il repo da zero
- [ ] `git status config/strategy.yaml` → nessuna modifica locale
- [ ] `echo "STRATEGY_CONFIG_PATH=$STRATEGY_CONFIG_PATH"` (Linux) / `echo "STRATEGY_CONFIG_PATH=$env:STRATEGY_CONFIG_PATH"` (PowerShell) → **vuoto** (override env var rompe la riproducibilità)

### 2.1 — Test pytest sul writer esteso

```bash
# Linux/Mac/Docker:
source .venv/bin/activate
# Windows:
# .venv\Scripts\Activate.ps1

pytest tests/test_baseline_dataset_writer.py -v
pytest tests/test_baseline_runner.py -v
```

- [ ] Tutti i test verdi
- [ ] Nessun warning su schema/columns

### 2.2 — Smoke run mini-range (~30-60 sec)

> Il comando esatto è definito in `scripts/run_baseline_05_09.py --smoke` (deve esistere post-Plan 05-09). Esempio fallback se lo script non ha flag `--smoke`:

```bash
python -c "
from backtest.baseline.runner import run_baseline, load_baseline_config
cfg = load_baseline_config()
run_baseline(
    cfg,
    symbols=['EURUSD'],
    timeframes=['H1'],
    profiles=['MODERATE'],
    date_start='2025-04-01',
    date_end='2025-05-01',
    out_dir='data/training/_smoke_05_09',
)
print('SMOKE OK')
"
```

- [ ] Termina senza eccezioni
- [ ] File parquet creato in `data/training/_smoke_05_09/baseline_decisions/`

### 2.3 — Schema validation

```bash
python -c "
import pyarrow.parquet as pq
t = pq.read_table('data/training/_smoke_05_09/baseline_decisions/part-0.parquet')
required = {
    'rsi_14', 'atr_14', 'bollinger_upper', 'bollinger_lower',
    'adx_14', 'macd', 'stochastic_k', 'donchian_upper',
    'keltner_upper', 'vwap', 'hurst', 'closing_score',
    'nr4', 'nr7', 'volatility_regime', 'multi_tf_alignment',
    'profile', 'regime', 'run_id', 'decision_ts_utc',
}
missing = required - set(t.column_names)
assert not missing, f'COLS MANCANTI: {missing}'
print(f'OK: {len(t.column_names)} cols, {t.num_rows} rows')
"
```

- [ ] Asserzione passa
- [ ] Stampa "OK: N cols, M rows"

### 2.4 — Cleanup smoke

```bash
rm -rf data/training/_smoke_05_09/
# Windows: rmdir /s /q data\training\_smoke_05_09
```

- [ ] Cartella smoke rimossa

---

## 3. Full run notturno

### 3.0 — Hardware notes (AMD Ryzen 7 5800H + 16 GB + RTX 3060)

> Specifiche conosciute del PC secondario, con implicazioni operative.

**CPU AMD Ryzen 7 5800H (8 core / 16 thread, Zen 3, 3.2-4.4 GHz, 16 MB L3):**
- `max_workers: 9` in `data/configs/baseline.yaml` è OK così com'è. NON aumentare.
- Stima wall-clock: ~2h45m-3h00m (5-15% più veloce del Phase 5 originale).
- Thermal sustained: 9 thread a ~3.6 GHz (sotto il boost massimo 4.4, normale per laptop).

**RAM 16 GB (margine ristretto ma sufficiente):**
- Stima utilizzo durante run: ~10-12 GB (9 worker × ~800 MB pandas + OS + buffer).
- **Buffer libero: ~4-5 GB**. Sembra abbastanza ma è facile saturare se tieni applicazioni pesanti aperte.
- **PRIMA di lanciare il backtest, chiudi**: browser con molte tab, Outlook/Mail, Slack/Teams, Spotify, qualsiasi IDE che non sia VS Code (e se possibile anche VS Code se usi tmux/PowerShell esterna).
- Monitor RAM durante il run: Task Manager → Performance → Memory. Se vedi >14 GB, c'è rischio swap → considera kill di processi non essenziali.

**GPU NVIDIA RTX 3060 Laptop (6 GB VRAM):**
- **NON usata per il backtest** — l'engine è event-driven sequenziale, GPU non aiuta (vedi analisi tecnica in chat).
- **Usata da Phase 7 ML training** — LightGBM con `device=gpu` dà speedup 5-10× su training+tuning. Setup CUDA + LightGBM-GPU verrà coperto in una sezione bonus quando arriverà il momento di Phase 7. Per ora ignora.
- Per il backtest puoi ignorare la GPU completamente.

### 3.1 — Preparazione

- [ ] Tutti i check §2 passati
- [ ] PC con corrente attaccata
- [ ] Power management: disabilita sleep/hibernation per la notte
  - **Windows**: Impostazioni → Sistema → Alimentazione → Sospensione: "Mai"
  - **macOS**: System Settings → Battery → Options → Prevent automatic sleeping when display is off
  - **Linux**: `systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target` (oppure GUI)
- [ ] Connessione internet non strettamente necessaria durante il run (è offline-safe)
- [ ] Backup parquet pre-esistente sul PC primario (NON sul secondario; il secondario lavora pulito): `cp -r data/training/baseline_decisions data/training/baseline_decisions.pre-05-09` (fatto sul PC primario prima del push)
- [ ] **Applicazioni pesanti chiuse** (vedi §3.0 RAM notes): browser, Outlook, Slack/Teams, IDE non necessari

### 3.2 — Lancio del run

**Path A/C (Linux/macOS/Docker) — con tmux o nohup:**

```bash
# Opzione tmux (raccomandata se installato):
tmux new -s baseline-05-09
source .venv/bin/activate
python scripts/run_baseline_05_09.py 2>&1 | tee 05-09-RUN.log
# Detach: Ctrl+B poi D
# Riattacca dopo: tmux attach -t baseline-05-09

# Opzione nohup:
nohup python scripts/run_baseline_05_09.py > 05-09-RUN.log 2>&1 &
echo $! > /tmp/baseline-05-09.pid
disown
tail -f 05-09-RUN.log    # per monitorare
```

**Path B (Windows) — con Start-Process o screen:**

```powershell
# Apri finestra dedicata che resta aperta:
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
  ".venv\Scripts\Activate.ps1; python scripts\run_baseline_05_09.py 2>&1 | Tee-Object -FilePath 05-09-RUN.log"

# Oppure semplicemente in una PowerShell che lasci aperta tutta la notte:
.venv\Scripts\Activate.ps1
python scripts\run_baseline_05_09.py 2>&1 | Tee-Object -FilePath 05-09-RUN.log
```

- [ ] Processo lanciato
- [ ] Log `05-09-RUN.log` cresce (tail per verifica)
- [ ] PID/finestra annotata per controllo

### 3.3 — Monitor wall-clock

Atteso ~3h18m. Riferimento progress: il log dovrebbe mostrare tqdm bar su 27 run totali.

```bash
# Linux/Mac:
tail -f 05-09-RUN.log

# Windows:
Get-Content 05-09-RUN.log -Wait
```

### 3.4 — Criteri di completamento

A fine run, conferma:

```bash
python -c "
import pyarrow.parquet as pq
t = pq.read_table('data/training/baseline_decisions/part-0.parquet')
print(f'Rows: {t.num_rows}, Cols: {t.num_columns}')
required = {'rsi_14','atr_14','profile','regime','run_id','decision_ts_utc'}
missing = required - set(t.column_names)
assert not missing, f'MISSING: {missing}'
print('SCHEMA OK')
"
```

- [ ] 27/27 run completati
- [ ] `data/training/baseline_decisions/part-0.parquet` esiste con schema esteso
- [ ] Rows ≥ 1076 (parità minima)
- [ ] Log finale: nessuna eccezione

---

## 4. Consegna risultati al PC primario

### 4.1 — Verifica dimensione output

```bash
du -sh data/training/baseline_decisions/    # Linux/Mac
# Windows:
dir data\training\baseline_decisions
```

Stima attesa: 1-3 MB (1076 rows × 50+ cols, compressione snappy).

### 4.2 — Commit + push (parquet via git)

Verifica che `data/training/` NON sia in `.gitignore` (controllato: solo `.env` è gitignored). Quindi:

```bash
git add data/training/baseline_decisions/
git add 05-09-RUN.log    # se vuoi conservare il log per audit
git add .planning/phases/05-baseline-backtest/05-09-SUMMARY.md  # se hai compilato sommario su questo PC
git commit -m "feat(05-09): baseline re-run completato — 27/27 run, parquet schema esteso (D-02 chiuso)"
git push origin feature/update-pythono-pure-strategy
```

- [ ] Push completato senza conflitti

### 4.3 — Pull e verifica sul PC primario

Sul PC primario, torna a questa sessione Claude Code:

```bash
git pull origin feature/update-pythono-pure-strategy
ls -la data/training/baseline_decisions/    # parquet aggiornato
python -c "
import pyarrow.parquet as pq
t = pq.read_table('data/training/baseline_decisions/part-0.parquet')
print(f'Rows: {t.num_rows}, Cols: {t.num_columns}')
"
```

Poi avvia `/gsd-resume-work` → routerà a STEP 8 (Phase 7 planning + execution).

---

## 5. Troubleshooting

### 5.1 — Install MetaTrader5 fallisce su Linux/Mac

**Errore:** `ERROR: Could not find a version that satisfies the requirement MetaTrader5`.

**Causa:** wheel solo Windows.

**Soluzione:** usa il workaround di §A.3:
```bash
grep -v "^MetaTrader5" requirements.txt > requirements-backtest.txt
pip install -r requirements-backtest.txt
```

### 5.2 — `ModuleNotFoundError: No module named 'tqdm'`

**Causa:** `tqdm` non è esplicitamente in `requirements.txt` ma è importato dal `runner.py`.

**Soluzione:**
```bash
pip install "tqdm>=4.66"
```

### 5.3 — `FileNotFoundError: data/configs/baseline.yaml`

**Causa:** path relativo. Lancia gli script dalla root del repo, non da sottocartelle.

**Soluzione:** `cd` alla root prima di lanciare:
```bash
cd /path/to/trading-agent    # o C:\trading-agent
python scripts/run_baseline_05_09.py
```

### 5.4 — `OSError: [Errno 28] No space left on device`

**Causa:** disco pieno. I 27 parquet shard intermedi (~50 MB cad) + log possono saturare.

**Soluzione:**
```bash
df -h    # verifica spazio libero
# Pulisci .pytest_cache, __pycache__, vecchi shard
find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null
rm -rf .pytest_cache/
```

### 5.5 — Run interrotto a metà (crash / PC spento)

**Strategia di recovery:**

1. Ispeziona quali run sono completati guardando i parquet shard per-worker in `data/training/baseline_decisions/`.
2. Identifica i run mancanti dal log (cerca "ERROR" o run_id senza summary line).
3. Re-lancia solo i mancanti modificando lo script `scripts/run_baseline_05_09.py` con `force_rerun=False` e una whitelist di run_id.

(Il pattern esatto dipende da come è scritto lo script — il Plan 05-09 deve documentare il modo di re-run parziale.)

### 5.6 — pytest fallisce su `tests/test_baseline_runner.py`

Probabili cause: deps mancanti (`pandas-ta` non installato → installa `requirements-dev.txt`), oppure regression introdotta dal writer extension.

Apri issue / annota nel `.continue-here.md` del PC secondario e contatta il PC primario via commit message + chat.

### 5.7 — `ImportError: cannot import name 'compute_all_extended'`

**Causa:** indicators package non aggiornato (Phase 2 fix non pullato).

**Soluzione:** `git pull` e verifica branch corretto: `git status` deve dire `feature/update-pythono-pure-strategy`.

### 5.9 — `Failed building wheel for pydantic-core` / `linker link.exe not found` / `Rust not found`

**Sintomo:** `pip install -r requirements.txt` fallisce con catena di errori:
```
Building wheel for pydantic-core (pyproject.toml) ... error
error: linker `link.exe` not found
note: please ensure that Visual Studio 2017 or later... were installed with the Visual C++ option
Python reports SOABI: cp31X-win_amd64   ← X >= 13
```

**Causa:** stai usando **Python 3.13 o 3.14** (vedi cp31X nel log). Pydantic-core (e altre deps Rust-based) non hanno wheel precompiled per quelle versioni → pip tenta di compilare da source → serve Rust toolchain + MSVC linker, che non sono installati. **Soluzione corretta NON è installare Rust/VS Build Tools** (~5 GB), è usare Python 3.12.

**Soluzione:**
1. Installa Python 3.12.x da https://www.python.org/downloads/release/python-31210/ (latest 3.12.x). Tieni la versione attuale, basta affiancare.
2. Cancella la venv corrotta:
   ```powershell
   Remove-Item -Recurse -Force .venv
   ```
3. Ricrea con `py -3.12`:
   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\Activate.ps1
   python --version    # deve dire 3.12.x
   ```
4. Reinstalla deps (ora con wheel precompiled, velocissimo):
   ```powershell
   python -m pip install --upgrade pip setuptools wheel
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   pip install "tqdm>=4.66"
   ```

**Prevenzione:** §B.1 ora elenca esplicitamente "NO 3.13, NO 3.14" e mostra `py -0` per listare versioni Python installate prima di partire.

### 5.8 — Backtest completa 27/27 ma row count molto basso (<1050)

**Sintomo:** wall-clock plausibile (~3h), `RESULTS=27/27 ok`, ma `SCHEMA KO: row count <N> < hard gate 1050`. Spesso accompagnato da distribuzione profili invertita (CONSERVATIVE > MODERATE > AGGRESSIVE invece del normale AGGRESSIVE > MODERATE > CONSERVATIVE).

**Causa identificata 2026-05-12:** `config/strategy.yaml` con drift dal commitato → `profile_filters[CONSERVATIVE].min_rr` ≠ 2.5 (o swap totale con AGGRESSIVE). Tipicamente succede se il repo è stato ottenuto via **download ZIP** invece di `git clone` (lo ZIP non garantisce coerenza di tutti i file binary/text fra versioni).

**Diagnosi 30 secondi:**
```bash
# (A) SHA del file on-disk — deve combaciare con quello documentato in §2.0
sha256sum config/strategy.yaml          # Linux/Mac
Get-FileHash config\strategy.yaml -Algorithm SHA256    # Windows

# (B) SHA registrato nel ledger durante il run (verità su cosa è stato letto)
python -c "import sqlite3; c=sqlite3.connect('logs/trades.db'); print(c.execute(\"SELECT DISTINCT strategy_yaml_sha256 FROM backtest_runs WHERE run_id LIKE 'baseline_%'\").fetchall())"

# (C) distribuzione profili nel parquet (sintomo)
python -c "import pyarrow.parquet as pq; df = pq.read_table('data/training/baseline_decisions/part-0.parquet').to_pandas(); print(df.groupby('profile').size())"
```

Se (A) o (B) ≠ SHA atteso → file drift. Se (C) ha CONSERVATIVE > AGGRESSIVE → conferma.

**Soluzione:**
1. **NON** modificare manualmente `config/strategy.yaml` (sarebbe un fix locale che diverge dal repo)
2. `cd ..` e ri-clona il repo: `rm -rf trading-agent && git clone <url>` (Linux/Mac) o equivalente Windows. **NO ZIP**.
3. Rifai §A.3 / B.3 / C.4 (venv + deps)
4. Riapplica §A.4 / B.4 / C.5 (`cp .env.backtest.example .env`)
5. Esegui §2 pre-flight, in particolare §2.0 (SHA check)
6. Solo dopo che §2.0 passa, rilancia §3 full run

**Prevenzione:** §2.0 è ora `OBBLIGATORIO` prima di ogni full run. Costa 5 sec, evita 3h di spreco.

---

## 6. Promemoria e checklist finale

Prima di andare a dormire:

- [ ] PC primario: `git push` Plan 05-09 + script + test
- [ ] PC secondario: `git pull` e tutti i §2 pre-flight check OK
- [ ] PC secondario: alimentazione collegata, sleep disabilitato
- [ ] PC secondario: `python scripts/run_baseline_05_09.py` lanciato in tmux/nohup/PowerShell persistente
- [ ] PC secondario: `tail -f 05-09-RUN.log` mostra progresso

Al risveglio:

- [ ] PC secondario: run completato (27/27), schema OK, parquet ~1-3 MB
- [ ] PC secondario: `git add data/training/baseline_decisions/ && git commit && git push`
- [ ] PC primario: `git pull` + `/gsd-resume-work` → STEP 8 Phase 7

---

## Changelog

- 2026-05-12 (rev 4) — secondo incidente stessa giornata: Python 3.14 installato sul secondario invece di 3.12 → `pydantic-core` non ha wheel precompiled → pip tenta compile da source con Rust+MSVC link.exe → fail. Mitigations: (a) §0.1 tabella prereq con "ESATTAMENTE 3.12.x" + spiegazione tecnica; (b) §B.1 rewritten: `py -0` per listare versioni, link diretto a Python 3.12.10, warning preventivo su pydantic-core/Rust; (c) §B.3 usa `py -3.12 -m venv` invece di `python -m venv` per forzare versione; (d) §5.9 nuovo troubleshooting con sintomo+soluzione dedicata.
- 2026-05-12 (rev 3) — incident response post 419-rows: (a) **CRITICO** sostituito flusso `.env` manuale con `cp .env.backtest.example .env` (template committato in repo); (b) §2.0 obbligatorio: SHA256 + grep `profile_filters` di `config/strategy.yaml` PRIMA di tutto, intercetta drift in 5s; (c) warning in §A.2/B.2/C.3: **SOLO `git clone`, MAI download ZIP** (root cause incident); (d) §5.8 nuovo: troubleshooting completo per row-count basso + profili invertiti con diagnosi 30s + procedura di re-clone; (e) banner introduttivo con root cause incident per visibilità.
- 2026-05-11 (rev 2) — aggiunta sezione §3.0 Hardware notes specifiche per PC secondario (AMD Ryzen 7 5800H + 16 GB + RTX 3060). Stima wall-clock 2h45m-3h00m. Conferma `max_workers: 9` ottimale (non aumentare oltre). Nota RAM margine ristretto: chiudere applicazioni pesanti. GPU non usata per backtest (vincolo architetturale), riservata per Phase 7 ML training.
- 2026-05-11 — creato in supporto a RESUME-PLAN.md STEP 7. Coverage 3 path setup (Linux/macOS, Windows, Docker), pre-flight identico al PC primario, troubleshooting per i bug latenti noti (MetaTrader5 cross-platform, tqdm missing).
