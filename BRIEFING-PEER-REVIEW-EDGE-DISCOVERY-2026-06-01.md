# Briefing per revisione esterna — vale la pena continuare la ricerca dell'edge?

> **Data:** 2026-06-01 · **Progetto:** `trading-agent` (bot di trading FX automatico)
> **Destinatario:** un LLM esterno, senza accesso al codice, a cui chiediamo un giudizio indipendente.
> **Scopo del documento:** spiegare, in modo **autosufficiente**, cosa è stato costruito, cosa abbiamo
> scoperto, e dove siamo bloccati — così che tu possa dirci se **la strada che stiamo seguendo ha senso**
> e se **vale la pena continuare la ricerca di un edge**, oppure se stiamo sbagliando metodo, premesse o
> dominio.
>
> Questo non è materiale di marketing. È deliberatamente critico e onesto. Se la nostra logica fa acqua,
> vogliamo saperlo. Leggi tutto, poi rispondi alle domande della **Sezione 10**.

---

## 0. Le domande a cui vogliamo che tu risponda

Mettiamo le domande in cima così sai cosa cercare mentre leggi. (Dettaglio in Sezione 10.)

1. **Il verdetto "la strategia base non ha edge" è giustificato dai numeri, o stiamo concludendo troppo
   in fretta?**
2. **La metodologia di edge discovery (in-sample → OOS indipendente → demeaning → cross-pair → soglia
   |t|≥2) è solida, o ha falle che la rendono troppo severa (uccide edge reali) o troppo permissiva?**
3. **Le 5 ipotesi falsificate erano le ipotesi giuste da testare?** Stiamo cercando l'edge nel posto
   sbagliato (dominio macro/intermarket su major USD), o nel modo sbagliato?
4. **Ha senso continuare?** Se sì, **quali direzioni** sono più promettenti tra quelle non ancora esplorate?
   Se no, qual è l'alternativa razionale?
5. **I nostri vincoli** (orizzonte trading ≤15 giorni, niente posizioni nel weekend, 3 major USD) sono
   sensati, o sono proprio loro a impedirci di trovare un edge che esisterebbe altrove?

---

## 1. Cos'è il progetto

`trading-agent` è un **bot di trading Forex intraday/multi-day automatico**. L'obiettivo finale del
milestone attuale (`v2-ml-backtest`) è dichiarato così:

> *"Ogni trade pre-filtrato da un classificatore ML calibrato le cui probabilità corrispondono all'hit-rate
> reale, addestrato sulle decisioni dell'agente stesso, che migliora a ogni ciclo."*

In altre parole: **una strategia base genera segnali di trade → un layer ML impara a filtrare i segnali
cattivi → il sistema migliora nel tempo.**

**Strumenti:** 3 coppie major USD-centriche — **EURUSD, GBPUSD, USDJPY**. Timeframe base M15/H1, dati
storici daily/H1 dal 2002 al 2026.

**Vincoli di stile correnti** (importanti per giudicare le nostre scelte):
- **Confine fermo: trading con holding ≤ 15 giorni.** Oltre i 15 giorni lo consideriamo *investing*
  (raccolta passiva di premio), fuori dallo scope del prodotto.
- **Niente posizioni nel weekend** ("flat-by-Friday", cutoff venerdì 20:00 UTC). *Nota:* questo vincolo è
  stato temporaneamente **rimosso** in una fase di scoperta per non escludere edge che vivono
  nell'overnight/weekend (vedi Sezione 5, "carry unconstrained").
- Overnight infra-settimanale permesso.
- Costi reali sempre inclusi: spread + slippage + commissione (+ swap se multi-day).

**Architettura della strategia base:** 4 "setup" detector basati su ATR (volatilità):
- **A — Breakout** (rottura di livello)
- **B — Reversal** (inversione, counter-trend) — *disabilitato di default*
- **C — Compression** (esplosione di volatilità da compressione)
- **D — Pullback** (rientro in trend)

Sopra i 4 setup c'è uno **scorer di "confluenza"** a 5 fattori che assegna un grade (A+/A/B/C/reject) e
una confidence, più gate di rischio (min_grade, min_confidence, min_rr) per 3 profili (CONSERVATIVE,
MODERATE, AGGRESSIVE).

---

## 2. Cosa è stato COSTRUITO (e funziona)

Questo serve a inquadrare: **l'infrastruttura ingegneristica è matura e testata.** Il problema NON è il
codice. È che il codice serve una strategia che non ha edge.

| Componente | Stato | Note |
|---|---|---|
| Stack live (client broker MT5, risk engine, esecuzione, scheduler H24, scanner multi-simbolo) | ✅ completo | gira in shadow-mode di default |
| `strategy/` — 4 setup ATR puri + confluenza 5-fattori + gate per profilo | ✅ completo, testato | purezza enforced via AST (vietati import I/O nei moduli di segnale) |
| `indicators/` — ~10 moduli di indicatori | ✅ completo | test anti-look-ahead **adversariali** (`compute(full)[i] == compute(bars[:i+1])[-1]`) |
| `backtest/` — motore event-driven deterministico, walk-forward, baseline | ✅ completo | `run_id` idempotente; **nessun future-leakage** (decisione a chiusura barra, finestra solo-passato) |
| MCP tools parte 1 (account/market/proposal/position/backtest) | ✅ completo | job queue, trail daemon reali |
| Layer ML (fasi 7-11: classifier, drift, intermarket, deploy) | 🔴 **SOSPESO, 0% codice** | esistono solo i piani; gli handler ML sono stub `NotImplementedError` |

**Test:** ~500 test, 477 pass (in un ambiente con alcune dipendenze mancanti). Qualità: forte su backtest
engine, anti-leakage, regression strategia.

**Bug tecnici noti** (rilevanti per la ricerca):
- 🔴 **Bug timezone/DST aperto:** il loader storico applica un offset fisso (+6h) senza gestire l'ora
  legale → in estate EU i bar orari sono sfasati di 1h per ~metà anno. **Implicazione:** qualunque test
  *intraday time-sensitive* (effetti di sessione London/NY, reazioni a eventi macro) sui dati esistenti è
  **contaminato**. I test **daily** (la maggior parte di quelli sotto) sono **immuni** al bug. Policy
  adottata: i dati nuovi vengono da Dukascopy (UTC-nativo, corretto); non si patcha il vecchio loader.

---

## 3. Il fatto centrale: la strategia base NON ha edge

Questo è il muro contro cui siamo. È stato dimostrato in due passaggi.

**3a. Backtest esaustivo della strategia completa.** Dopo aver riparato 3 bug critici che tenevano "morti"
pezzi del design originale (un fattore di confluenza sempre falso, un gate grade mai applicato, ecc.) e
aver finalmente attivato l'**intero** design come previsto, abbiamo validato onestamente su **5 regimi di
mercato × 2 coppie** (anni 2008/2014/2017/2020/2023, EURUSD+GBPUSD).

**Risultato: 59 configurazioni su 60 negative.** Approfondimento su un dataset da 209.000 trade:
- win rate 24-27%, 73-83% delle chiusure colpiscono lo stop loss;
- expectancy aritmeticamente negativa;
- edge-hunt su 117 sottoinsiemi (per setup/regime/ora/direzione): zero gruppi 1-way o 2-way positivi;
  pochissimi 3-way/4-way marginalmente positivi ma con **mediana del PnL sempre negativa** → edge sotto i
  costi reali;
- nessun bias direzionale (BUY −1.38, SELL −1.16 USD/trade);
- 27/27 run terminano per esaurimento del capitale.

**Verdetto: NO-GO.** L'edge della base-strategy (4 setup ATR su questi pair/TF) non esiste, nemmeno con il
design completo attivo.

**3b. Conseguenza logica.** Il layer ML a valle (fasi 7-11) **assume un edge da raffinare**. Se l'edge non
esiste, l'ML imparerebbe rumore. Decisione (a nostro avviso corretta): **non costruire ML su una base
senza segnale.** Fasi 7-11 sospese. Aperta una traccia esplorativa separata: *l'edge discovery*.

> **Prima domanda implicita per te:** è corretto fermarsi qui e cercare un edge *altrove*, o avremmo
> dovuto insistere a raffinare/ricombinare i 4 setup (es. ML direttamente sui segnali grezzi, ensemble,
> feature engineering più aggressivo) prima di dichiarare il NO-GO?

---

## 4. La ricerca dell'edge — metodologia

Dopo il NO-GO abbiamo aperto un track esplorativo con una **metodologia scettica deliberatamente severa**,
pensata per non auto-ingannarci (il rischio numero uno nel quant retail è trovare edge fantasma da
overfitting / multiple testing).

Le regole:

1. **Team a 3 ruoli separati:** un orchestratore-scettico (formula ipotesi, verifica i numeri leggendo i
   JSON grezzi, NON si fida dei report dei sub-agenti), un esploratore in-sample, un validatore OOS
   **indipendente** (vede solo dati che l'esploratore non ha mai toccato).
2. **Split temporale rigido:** in-sample 2002-2014; out-of-sample 2015-2026 **più una coppia interamente
   riservata** (GBPUSD mai vista in-sample) come ulteriore test di generalizzazione.
3. **Anti-leakage con assert runtime:** ogni serie esterna è allineata in modo causale (solo dati ≤ data
   di decisione), forward-fill solo all'indietro, e check con lag di 1 giorno per escludere artefatti di
   timing "same-day-close".
4. **Sanity baseline obbligatorie:** segnale random, always-long, always-short. Se il random "trova"
   qualcosa, l'harness è rotto.
5. **Costi reali** sempre sottratti (spread + slippage + commissione + swap).
6. **Demeaning** — lo strumento decisivo. Sottraiamo il forward-return medio del periodo per **separare il
   segnale dal drift**. Esempio del perché serve: in un decennio in cui EUR sale, un segnale che è "long
   EUR" più spesso sembrerà brillante anche se non ha skill — è solo il drift. Il demeaned isola il
   contenuto predittivo vero.
7. **Soglia di significatività |t| ≥ 2**, e **coerenza cross-pair** richiesta. Un edge è "REALE" solo se:
   proposto in-sample, confermato OOS indipendente, coerente cross-pair, e sopravvive ai costi.
8. **Niente fishing:** se un'ipotesi non è promettente in-sample, **non** la si porta in OOS (sarebbe
   multiple-testing).

> **Seconda domanda implicita per te:** questa metodologia è solida? Ti sembra che la soglia |t|≥2 +
> cross-pair + demeaning sia ben calibrata, o rischia di uccidere edge piccoli-ma-reali (falsi negativi)?
> C'è un controllo che manca (es. correzione per autocorrelazione da overlap, Bonferroni sul numero di
> celle testate, block-bootstrap invece del t-test)?

---

## 5. Le 5 ipotesi testate — tutte FALSIFICATE

Tutte nel dominio **macro / intermarket / posizionamento** sui 3 major USD. I numeri sono stati verificati
leggendo i JSON dei risultati, non solo i report.

| # | Ipotesi | Meccanismo testato | Esito | Perché muore |
|---|---|---|---|---|
| H-A1 | Momentum del prezzo del dollaro (DXY) → direzione dei pair | DXY su per N giorni → short EUR/GBP, long JPY, hold M giorni | ❌ | max \|t\|≈1.4-1.66 (<2). EUR **circolare** (il DXY è ~57.6% EUR → testa l'autocorrelazione del pair stesso); JPY (gamba pulita, 13.6% del DXY) dà solo un "sussurro" sotto soglia. L'unico \|t\|>2 è il drift (always-short-EUR). |
| H-A2 | Momentum dei rendimenti Treasury US (2Y/10Y) → direzione | Δyield US su per N giorni → USD forte → short EUR/GBP, long JPY | ❌ | **Significativo in-sample** su EURUSD (DGS10 N5, t −3.4/−3.8, sopravvive al demeaning → contenuto reale), ma **OOS il demeaned FLIPPA positivo** e diventa insignificante, e GBPUSD non conferma. È un **artefatto di regime 2002-2014** (risk-off: fuga verso Treasury + USD bene-rifugio muovono yield e EUR *insieme*), non rate-differential. |
| H-A3 | Livello del differenziale di tasso US−estero (carry) → drift spot | D = US10Y − DE10Y/JP10Y; D>0 → carry long USD | ❌ | EURUSD demeaned \|t\|<0.5 e **segno incoerente tra orizzonti**. USDJPY degenera: D è sempre >0 → il segnale ≡ always-long → demeaned = 0 per costruzione (non informativo). |
| H-B | Carry "unconstrained" (vincolo weekend rimosso) | carry+swap firmato, niente flat-by-Friday, sweep holding 1/3/5/10/15 gg | ❌ | Anche liberando il carry dal weekend, **nessun edge di timing ≤15gg**. EURUSD: il net **peggiora** all'aumentare dell'orizzonte (lo spot si muove *contro* la direzione carry). USDJPY: l'unico positivo è **swap passivo su un long perpetuo** (investing, non trading; esposto al carry-crash tipo 2008). |
| H-C | COT fade (posizionamento CFTC) | estremi di posizionamento speculativo → reversal | ❌ | Cross-pair **incoerente**: EURUSD mostra *momentum* (il prezzo segue gli speculatori, opposto del fade); USDJPY mostra un debole *pro-reversal* ma con t gonfiato da overlap (a M=15 solo ~43% di trade indipendenti). Nessuna cella \|t_demeaned\|≥2. |

### La meta-lezione (il vero risultato finora)

> **Le relazioni intermarket/macro sui major USD sono cross-pair incoerenti e regime-switching: il SEGNO
> del legame cambia tra regime di crisi e regime di calma.** Un segnale a segno-fisso non può funzionare
> cross-regime. È lo stesso meccanismo che aveva ucciso anche un precedente test di "panic-fade" (segno
> opposto tra coppie nella stessa crisi).
>
> Corollario che abbiamo dedotto: cercavamo un driver "strutturalmente persistente" (il carry, il cui
> segno è stabile perché lo swap lo paghi/incassi a prescindere dal regime) — ma il carry, sotto il
> confine "trading ≤15gg", **non è raccoglibile**: il suo unico profitto è l'investing passivo
> overnight/weekend, fuori scope.

**Conclusione provvisoria del team:** le aree A (intermarket), B (carry) e C (posizionamento) sono
considerate **esaurite sotto i vincoli correnti.**

> **Terza domanda implicita per te:** questa meta-lezione è corretta e ben supportata, o stiamo
> generalizzando da 5 punti dati? In particolare: il fatto che *segnali a segno-fisso* non funzionino
> cross-regime implica che dovremmo testare *segnali regime-condizionati* (rischioso per il
> multiple-testing) — oppure è la prova che il dominio macro-su-major-USD è semplicemente troppo
> efficiente per un retail e dovremmo cambiare dominio del tutto?

---

## 6. Cosa NON è ancora stato testato (i lead aperti)

Aree previste dal piano di ricerca ma non ancora esplorate, in ordine di "distanza":

- **Area D — Effetti di sessione / eventi macro (intraday).** *Bloccata da contaminazione:* i test
  intraday sui dati esistenti sono inaffidabili per il bug DST. Vanno **ri-eseguiti su dati DST-corretti
  (Dukascopy)**. Nota onesta: gli effetti di sessione/evento erano risultati "nulli" in passato, ma
  *potrebbero* essere stati smerati dal bug — non è una conferma che ci sia un edge nascosto, è solo un
  sospetto da verificare pulito.
- **Area E — Microstruttura / order-flow.** Richiede tick data (in parte ora disponibile via Dukascopy).
  Non ancora toccata.
- **Area F — Cambio strumento (futures invece di spot FX).** Non toccata.
- **Claim ORFANO — "mean-reversion 2020/2023 da Setup B".** Nei nostri log questo è citato come *"l'unico
  segnale di edge reale trovato"* (il Setup B reversal sembrava profittevole in regimi di alta
  volatilità/reversion, 2020 e 2023). **MA non esiste un report/validazione dedicato.** È un lead **non
  validato**, non un finding. Andrebbe testato formalmente con lo stesso rigore delle altre ipotesi —
  oppure ritirato dalla narrativa. *Questo, a nostro avviso, è il candidato più promettente non ancora
  affrontato.*

> **Quarta domanda implicita per te:** se dovessi scommettere un giro di ricerca su UNA di queste —
> validare il claim mean-reversion regime-condizionato, ri-testare Area D su dati puliti, andare su
> microstruttura/tick, o cambiare strumento — quale e perché?

---

## 7. Caveat onesti sulla ricerca stessa

Per darti una valutazione equa, ecco i punti deboli che noi stessi abbiamo identificato:

- **H-A1 non riporta il demeaning** nei JSON (a differenza di A2/A3). La conclusione "nullo" regge
  comunque (max |t|<2), ma è un'incoerenza metodologica.
- **COT: i t-stat non sono corretti per l'autocorrelazione da overlap.** Con holding lunghi e entry
  giornaliere, le finestre si sovrappongono e gonfiano i t. Nel caso COT questo *rafforza* il verdetto
  "nullo" (i pochi positivi sono ancora più deboli), ma è un difetto metodologico che andrebbe sistemato
  sistematicamente (block-bootstrap o trade non sovrapposti).
- **L'evidenza del bug DST** (match 99.2% a +1h vs 36% a 0h) è basata su un campione piccolo (1 settimana ×
  2 mesi, solo EURUSD H1). Plausibile ma non conclusiva al 100%.
- **Lo spazio di ricerca è grande e il numero di ipotesi cresce** → ogni nuova cella testata aumenta il
  rischio di falso positivo. Non applichiamo (ancora) una correzione formale per multiple-testing sul
  totale delle celle.

---

## 8. Lo stato decisionale, in una frase

> Abbiamo un **eccellente apparato ingegneristico (deterministico, anti-leakage, testato) al servizio di
> una strategia senza edge.** La ricerca di un edge sostitutivo ha prodotto, finora, solo **falsificazioni
> pulite** nel dominio macro/intermarket sui major USD. Non esiste oggi un percorso verso il deploy senza
> prima trovare un edge — e non sappiamo con certezza se l'edge non esista, se lo stiamo cercando nel posto
> sbagliato, o se i nostri vincoli lo stiano escludendo.

---

## 9. Riepilogo per la tua valutazione

| Dimensione | Nostra posizione | Confidenza |
|---|---|---|
| L'infrastruttura è solida e riutilizzabile | Sì | Alta |
| La strategia base 4-setup ATR non ha edge | Dimostrato | Alta |
| La metodologia di edge discovery è rigorosa | Sì | Media-alta |
| Aree macro/intermarket/carry/COT esaurite sotto i vincoli | Sì | **Media** (5 ipotesi, possibile generalizzazione eccessiva) |
| Il confine "trading ≤15gg" è la scelta giusta | Assunto | **Bassa** (mai messo in discussione formalmente) |
| Vale la pena continuare l'edge discovery | Incerto — è la domanda per te | — |

---

## 10. Le domande, in forma esplicita

Per favore rispondi a queste, da revisore indipendente e scettico:

1. **Validità del NO-GO.** Dai numeri della Sezione 3, il verdetto "nessun edge nella strategia base" è
   giustificato? C'è un modo standard di estrarre edge da 4 setup negativi (es. meta-labeling à la López de
   Prado, ensemble, ML direttamente sui segnali grezzi) che avremmo dovuto provare *prima* di abbandonare?

2. **Validità della metodologia.** La pipeline in-sample → OOS indipendente → demeaning → cross-pair →
   |t|≥2 è corretta? È troppo severa (falsi negativi su edge piccoli) o troppo permissiva? Cosa
   aggiungeresti (block-bootstrap, correzione multiple-testing, Sharpe deflazionato, purged k-fold)?

3. **Scelta del dominio.** Cercare l'edge in segnali **macro/intermarket lenti sui major USD** era una
   buona scommessa a priori, dato che sono tra i mercati più efficienti e arbitraggiati al mondo? Dove
   cercheresti tu un edge sfruttabile da un sistema retail/semi-pro: cross/exotic FX, microstruttura
   intraday, eventi/calendario, strumenti diversi (futures, crypto), o nessuno di questi?

4. **Prossimo passo.** Se continuare ha senso, **quale singolo esperimento** faresti per primo e perché?
   (I nostri candidati: validare il claim orfano mean-reversion regime-condizionato; ri-testare Area D
   sessione/evento su dati DST-corretti; passare a tick/microstruttura.) Se *non* ha senso continuare, qual
   è la raccomandazione alternativa?

5. **I vincoli.** Il confine "trading ≤15 giorni" + "niente weekend" + "solo 3 major USD" sono ragionevoli,
   o è proprio questa scatola a garantire l'assenza di edge? Quale vincolo allenteresti per primo, e cosa
   ti aspetteresti che cambi?

6. **Meta-giudizio.** Da fuori: questo progetto sta seguendo una strada **razionale e ben eseguita verso un
   muro reale** (il mercato è efficiente, non c'è edge facile, e il rigore lo sta dimostrando onestamente),
   oppure sta **commettendo un errore sistematico** (dominio sbagliato, vincoli auto-imposti, metodo troppo
   severo) che gli impedisce di vedere un edge che esiste? Sii diretto.

---

*Documento preparato come richiesta di revisione tra pari. Tutti i numeri provengono da test rieseguiti e
verificati sui dati grezzi al 2026-05-30. Vogliamo critica, non conferma.*
