# Convenzioni dei commit

Stile Conventional Commits adattato al progetto.

## Formato

```
<tipo>(<scope>): <descrizione breve>

[corpo opzionale]
```

## Tipi ammessi

- `feat` — nuova funzionalità o nuovo file applicativo
- `fix` — correzione bug
- `test` — aggiunta o modifica test
- `docs` — documentazione (README, prompts)
- `chore` — config, .gitignore, requirements, handoff
- `refactor` — refactoring senza cambio di comportamento

## Scope ammessi

`setup`, `config`, `models`, `mt5`, `risk`, `logger`, `execution`, `indicators`, `agent`, `mcp`, `tests`, `phase-N`, `state`, `handoff`

## Esempi

### Durante lo sviluppo
```
feat(config): add Config class with typed properties
feat(models): add TradeProposal, AccountState, RiskDecision dataclasses
feat(mt5): implement Mt5Client with retry decorator
feat(risk): implement evaluate_trade with daily kill switch
test(risk): cover kill switch and SL boundary cases
feat(logger): rotating file handler + sqlite schema with WAL
feat(agent): claude tool use loop with 4 tools
feat(mcp): mcp server stdio with 6 tools
docs(readme): add claude desktop setup section
```

### Checkpoint di fase
```
feat(phase-2): complete and validated
feat(phase-4): complete and validated
```

### Handoff
```
chore(handoff): pause at phase-4, risk_engine.py done, tests pending
chore(state): update progress before token reset
```

## Regole

1. Una sola fase per commit. Mai mescolare file di fasi diverse.
2. `STATE.md` va sempre incluso nel commit insieme ai file applicativi che descrive.
3. Mai committare `.env`, credenziali, `logs/*.db`, `logs/*.log`.
4. Push su origin dopo ogni `feat(phase-N): complete` e ogni `chore(handoff)`.
