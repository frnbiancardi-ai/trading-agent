# FASE 1 — Setup ambiente

## Obiettivo
Creare struttura cartelle, venv, requirements, file base. Verificare che Python 3.12 64-bit sia compatibile con MetaTrader5 5.0.5735.

## File da creare (in ordine)

### 1. `requirements.txt`
```
MetaTrader5==5.0.5735
python-dotenv==1.0.1
pydantic==2.11.3
requests==2.32.3
anthropic
mcp
pytest
```

### 2. `.gitignore`
```
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
logs/*.log
logs/*.db
.idea/
.vscode/
```

### 3. Struttura cartelle vuote
- `prompts/`
- `logs/` (con `.gitkeep`)
- `tests/`

## Comandi di verifica (checkpoint)

```powershell
cd C:\trading-agent
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python -c "import struct; print('Python bits:', struct.calcsize('P')*8)"   # deve dare 64
python -c "import MetaTrader5, anthropic, mcp; print('Imports OK')"
```

## Errori comuni

- **Python 32-bit** → MetaTrader5 fallisce silenziosamente. Verifica con `struct.calcsize('P')*8`.
- **`mcp` non trovato** → prova `pip install "mcp[cli]"`. Se fallisce, aggiorna pip.
- **PowerShell blocca venv activate** → `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`.

## Commit attesi

```
chore(setup): add requirements.txt and .gitignore
chore(setup): create folder skeleton (prompts/, logs/, tests/)
feat(phase-1): complete and validated
```

## Aggiornamento STATE.md

Al termine, marca `phase_1_setup.status: VALIDATED`, files: `[requirements.txt, .gitignore, logs/.gitkeep]`.
