# HANDOFF_PROTOCOL.md — Regole di sopravvivenza ai reset token

Questo documento è incluso nel prompt dell'orchestrator. Definisce **come e quando** Claude Code deve fermarsi e fare handoff per non perdere il contesto.

## Premessa tecnica

Claude Code **non** ha un'API affidabile per sapere quanti token gli restano nella sessione. Quindi adottiamo una strategia conservativa basata su:

- **Numero di file generati nella sessione corrente** (proxy del consumo).
- **Dimensione media dei file** (heuristic).
- **Checkpoint logici naturali** (fine fase, gruppo di file correlati).

## Regole vincolanti (NON NEGOZIABILI)

### Regola 1 — Aggiornamento STATE.md
Dopo ogni file generato o modificato, **prima** di passare al successivo:
1. Aggiorna `STATE.md` (sezione `current_phase`, `completed_files`, `last_action`, `next_action`).
2. Se non è ancora ora di committare (vedi Regola 2), almeno salva STATE.md.

### Regola 2 — Commit Git
Fai un commit **ogni volta che**:
- Hai completato un **gruppo logico di file correlati** (es: `config.py + models.py`, `risk_engine.py + tests/test_risk.py`).
- Hai chiuso un **checkpoint di fase** (validazione passata).
- Stai per fare handoff (anche parziale).

Formato commit: vedi `COMMIT_CONVENTIONS.md`.

### Regola 3 — Soglia di Early Stop (handoff proattivo)
Prima di iniziare un nuovo file, valuta:

- **Se hai già generato 6+ file in questa sessione** → fai handoff completo (STATE.md + commit + push) e termina chiedendo all'utente di aprire una nuova sessione.
- **Se hai generato 4-5 file e il prossimo è grande (claude_agent.py, mcp_server.py, README.md)** → fai handoff completo prima.
- **Se senti la risposta che si accorcia o il sistema ti notifica usage alto** → handoff immediato.

### Regola 4 — Handoff completo (procedura)
Quando decidi di fare handoff:

1. Aggiorna `STATE.md` con:
   - `session_status: HANDOFF`
   - `next_action`: istruzione esplicita su cosa fare nella prossima sessione (es: "generare risk_engine.py seguendo phase-prompts/phase-04-risk-engine.md, sezione 'Specifiche'").
   - `unresolved_decisions`: domande aperte o ambiguità non risolte.
2. Commit con messaggio: `chore(handoff): pause at <fase> — <stato>`.
3. Push su origin.
4. Output finale all'utente:
   ```
   ✋ HANDOFF eseguito.
   Fase: <N>
   Ultimo file completato: <nome>
   Prossimo step: <descrizione 1 riga>
   Per riprendere: apri nuova sessione Claude Code, incolla ORCHESTRATOR.md.
   ```

### Regola 5 — Ripresa dopo handoff
All'avvio (orchestrator), **sempre** in quest'ordine:
1. Leggi `STATE.md`.
2. Leggi `git log --oneline -20` per vedere ultimi commit.
3. Verifica che `working tree` sia clean (`git status`). Se non lo è, segnala all'utente prima di procedere.
4. Annuncia all'utente: "Riprendo dalla fase X, prossimo step: Y. Confermi?"

### Regola 6 — Mai riscrivere file già committati
Se un file esiste già ed è committato, **non rigenerarlo da zero**. O lo modifichi con `edit` (preferito) o chiedi conferma esplicita.

### Regola 7 — Validazione prima del passaggio di fase
Non passare alla fase successiva senza:
- Aver eseguito i test/comandi di checkpoint della fase corrente.
- Aver scritto in `STATE.md` l'esito del checkpoint.
- Aver chiesto conferma esplicita all'utente.
