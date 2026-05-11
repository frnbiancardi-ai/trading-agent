---
created: 2026-05-11
project: trading-agent
purpose: guida step-by-step per configurare un PC secondario che esegua il backtest Plan 05-09 in parallelo al lavoro GSD sul PC primario
linked_from: .planning/RESUME-PLAN.md (STEP 7)
target_audience: utente progetto (Francesco) — operazione manuale, non automatica
---

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
| **Python** | 3.12.x | NO 3.13 (alcune deps non compatibili) |
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
- [ ] (Opzionale) `.env` minimo per backtest preparato e trasferito al PC secondario via mezzo sicuro (USB / password manager / cloud privato — **NON via git**, è in `.gitignore`)

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

Per il backtest **non servono** MT5 credenziali né Claude API. Bastano i parametri di profilo rischio e strategia. Crea un `.env` minimo:

```bash
# Da PC primario, copia .env originale via mezzo sicuro (USB/SSH/cloud privato)
# OPPURE crea minimo da .env.example:
cp .env.example .env
# Edita per togliere chiavi che non userai (MT5_*, CLAUDE_*)
# Il backtest legge solo i parametri profilo/strategia dal .env tramite config.py
```

**Verifica:**
```bash
python -c "import config; print('OK config load')"
```

→ Vai alla sezione **2 — Pre-flight + Run** sotto.

---

## PATH B — Python nativo su Windows

### B.1 — Verifica Python 3.12

In PowerShell:
```powershell
python --version    # Deve essere 3.12.x
where.exe python
```

Se manca: scarica da https://www.python.org/downloads/release/python-3128/ (o release 3.12.x più recente). Durante installazione: **spunta "Add Python to PATH"**.

### B.2 — Clona il repo

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

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
# Se PowerShell blocca lo script: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

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

```powershell
# Copia .env originale via mezzo sicuro (USB/SSH/password manager) dal PC primario
# OPPURE:
copy .env.example .env
notepad .env    # rimuovi/svuota MT5_* e CLAUDE_* se vuoi pulizia
```

**Verifica:**
```powershell
python -c "import config; print('OK config load')"
```

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

```bash
# Copia .env dall'host (è gitignorato) o crea minimo:
cp .env.example .env
```

→ Vai alla sezione **2 — Pre-flight + Run** sotto.

---

## 2. Pre-flight check (OBBLIGATORIO prima del full run)

> **Tempo totale:** ~1-2 minuti. **Non saltare**: scopre il 95% dei bug schema/writer prima di sprecare 3h18m.

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

- 2026-05-11 (rev 2) — aggiunta sezione §3.0 Hardware notes specifiche per PC secondario (AMD Ryzen 7 5800H + 16 GB + RTX 3060). Stima wall-clock 2h45m-3h00m. Conferma `max_workers: 9` ottimale (non aumentare oltre). Nota RAM margine ristretto: chiudere applicazioni pesanti. GPU non usata per backtest (vincolo architetturale), riservata per Phase 7 ML training.
- 2026-05-11 — creato in supporto a RESUME-PLAN.md STEP 7. Coverage 3 path setup (Linux/macOS, Windows, Docker), pre-flight identico al PC primario, troubleshooting per i bug latenti noti (MetaTrader5 cross-platform, tqdm missing).
