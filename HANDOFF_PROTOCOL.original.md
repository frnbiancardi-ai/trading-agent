# Protocollo di handoff

Regole vincolanti per evitare perdita di contesto in caso di reset token.

## Premessa tecnica

Claude Code non ha un'API affidabile per sapere quanti token gli restano nella sessione. La strategia è conservativa, basata su:
- Numero di file generati nella sessione corrente.
- Dimensione media dei file.
- Checkpoint logici naturali (fine fase, gruppo di file correlati).

## Regola 1 — Aggiornamento STATE.md

Dopo ogni file generato o modificato, prima di passare al successivo:
1. Aggiorna `STATE.md` (sezioni `current_phase`, `completed_files`, `last_action`, `next_action`).
2. Se non è ancora ora di committare, almeno salva STATE.md.

## Regola 2 — Commit Git

Fai un commit ogni volta che:
- Hai completato un gruppo logico di file correlati (es. `config.py` + `models.py`, `risk_engine.py` + `tests/test_risk.py`).
- Hai chiuso un checkpoint di fase (validazione passata).
- Stai per fare handoff (anche parziale).

Formato commit: vedi `COMMIT_CONVENTIONS.md`.

## Regola 3 — Soglia di early stop (handoff proattivo)

Prima di iniziare un nuovo file, valuta:
- Se hai già generato 6+ file in questa sessione → handoff completo e termina.
- Se hai generato 4-5 file e il prossimo è grande (`claude_agent.py`, `mcp_server.py`, `README.md` finale) → handoff completo prima.
- Se le risposte si stanno accorciando o il sistema notifica usage alto → handoff immediato.

## Regola 4 — Handoff completo (procedura)

Quando decidi di fare handoff:

1. Aggiorna `STATE.md`:
   - `session_status: HANDOFF`
   - `next_action`: istruzione esplicita per la prossima sessione (es. "generare risk_engine.py seguendo phase-04-risk-engine.md, sezione Specifiche").
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
3. Verifica che il working tree sia clean (`git status`). Se non lo è, segnala all'utente prima di procedere.
4. Annuncia: "Riprendo dalla fase X, prossimo step: Y. Confermi?"

## Regola 6 — Mai riscrivere file già committati

Se un file esiste già ed è committato, non rigenerarlo da zero. Modificalo con `edit` o chiedi conferma esplicita prima di sovrascrivere.

## Regola 7 — Validazione prima del passaggio di fase

Non passare alla fase successiva senza:
- Aver eseguito i test/comandi di checkpoint della fase corrente.
- Aver scritto in `STATE.md` l'esito del checkpoint.
- Aver chiesto conferma esplicita all'utente.
