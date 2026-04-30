# Protocollo di handoff

Regole vincolanti per evitare perdita contesto in caso reset token.

## Premessa tecnica

Claude Code non ha API affidabile per sapere token rimanenti in sessione. Strategia conservativa, basata su:
- Numero file generati in sessione corrente.
- Dimensione media file.
- Checkpoint logici naturali (fine fase, gruppo file correlati).

## Regola 1 — Aggiornamento STATE.md

Dopo ogni file generato o modificato, prima di passare al successivo:
1. Aggiorna `STATE.md` (sezioni `current_phase`, `completed_files`, `last_action`, `next_action`).
2. Se non ancora ora di committare, almeno salva STATE.md.

## Regola 2 — Commit Git

Commit ogni volta che:
- Completato gruppo logico file correlati (es. `config.py` + `models.py`, `risk_engine.py` + `tests/test_risk.py`).
- Chiuso checkpoint fase (validazione passata).
- Stai per fare handoff (anche parziale).

Formato commit: vedi `COMMIT_CONVENTIONS.md`.

## Regola 3 — Soglia early stop (handoff proattivo)

Prima di iniziare nuovo file, valuta:
- Se generati 6+ file in sessione → handoff completo e termina.
- Se generati 4-5 file e prossimo è grande (`claude_agent.py`, `mcp_server.py`, `README.md` finale) → handoff completo prima.
- Se risposte si accorciano o sistema notifica usage alto → handoff immediato.

## Regola 4 — Handoff completo (procedura)

Quando decidi di fare handoff:

1. Aggiorna `STATE.md`:
   - `session_status: HANDOFF`
   - `next_action`: istruzione esplicita per prossima sessione (es. "generare risk_engine.py seguendo phase-04-risk-engine.md, sezione Specifiche").
   - `unresolved_decisions`: domande aperte o ambiguità non risolte.
2. Commit: `chore(handoff): pause at <fase> — <stato>`.
3. Push su origin (se configurato).
4. Output finale all'utente:
```
HANDOFF eseguito.
Fase: <N>
Ultimo file completato: <nome>
Prossimo step: <descrizione 1 riga>
Per riprendere: apri nuova sessione Claude Code, reincolla il prompt orchestrator.
```

## Regola 5 — Ripresa dopo handoff

All'avvio (orchestrator), sempre in quest'ordine:
1. Leggi `STATE.md`.
2. Leggi `git log --oneline -20` per vedere ultimi commit.
3. Verifica working tree clean (`git status`). Se non clean, segnala utente prima di procedere.
4. Annuncia: "Riprendo da fase X, prossimo step: Y. Confermi?"

## Regola 6 — Mai riscrivere file già committati

Se file esiste già ed è committato, non rigenerare da zero. Modifica con `edit` o chiedi conferma esplicita prima di sovrascrivere.

## Regola 7 — Validazione prima del passaggio di fase

Non passare a fase successiva senza:
- Aver eseguito test/comandi checkpoint fase corrente.
- Aver scritto in `STATE.md` esito checkpoint.
- Aver chiesto conferma esplicita utente.
