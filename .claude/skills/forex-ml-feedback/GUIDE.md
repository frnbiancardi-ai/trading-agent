# Guida: Usare forex-ml-feedback

## Installazione

```bash
pip install scikit-learn xgboost
```

## Quick Start

### 1. Analizzare Trade Storici

```python
from ml_feedback import MLFeedbackLoop, extract_trade_features

# Carica i tuoi trade da backtest o log
trades = [
    {
        "symbol": "EURUSD",
        "entry_time": "2024-01-15 10:00:00",
        "exit_time": "2024-01-15 14:00:00",
        "direction": "BUY",
        "entry_price": 1.0900,
        "exit_price": 1.0920,
        "sl": 1.0880,
        "tp": 1.0940,
    },
    # ... altri trade
]

ml = MLFeedbackLoop()
analysis = ml.analyze_trades(trades)

print(f"Win rate: {analysis['win_rate']:.1%}")
print(f"Total trades: {analysis['total_trades']}")
print(f"Losses: {analysis['losses']}")
print(f"Patterns: {analysis['common_failure_patterns']}")
```

**Output:**
```
Win rate: 45.0%
Total trades: 100
Losses: 55
Patterns: ['Session ASIA: 25 losses vs 10 wins']
```

---

### 2. Validare un Entry con ML

```python
from ml_feedback import FeatureQualityModel

# Dati OHLC recenti (almeno 20 barre)
bars = [
    {"open": 1.0900, "high": 1.0920, "low": 1.0890, "close": 1.0910, "volume": 5000}
    for _ in range(25)
]

# Setup tecnico attuale
setup = {
    "trend_strength": 0.65,  # da calculate_trend_strength()
    "rsi": 45,               # da rsi()
}

model = FeatureQualityModel()
quality = model.predict(bars, setup)

print(f"Recommendation: {quality.recommendation}")
print(f"Breakout quality: {quality.breakout_quality:.2f}")
print(f"Confluence valid: {quality.confluence_valid}")
```

**Output:**
```
Recommendation: PROCEED
Breakout quality: 0.78
Confluence valid: True
```

---

### 3. Suggerire Parametri

```python
from ml_feedback import HeuristicTuner

trades = [/* trade history */]  # vedi esempio 1

current_params = {
    "ENABLE_ASIA_SESSION": True,
    "MIN_HOLD_MINUTES": 15,
    "MIN_BREAKOUT_VOLUME_RATIO": 1.5,
}

tuner = HeuristicTuner(min_samples=30)
features = [extract_trade_features(t) for t in trades]
suggestions = tuner.suggest_params(features, current_params)

for s in suggestions:
    print(f"{s.param_name}: {s.current_value} → {s.suggested_value}")
    print(f"  Reason: {s.reason}")
    print(f"  Confidence: {s.confidence:.0%}")
```

**Output:**
```
ENABLE_ASIA_SESSION: True → False
  Reason: Sessione ASIA: 25 perdite
  Confidence: 80%
MIN_BREAKOUT_VOLUME_RATIO: 1.5 → 2.0
  Reason: Volume medio perdite: 1.2x
  Confidence: 75%
```

---

### 4. Training ML su Dati Storici

```python
from ml_feedback import FeatureQualityModel
import numpy as np

# Features: [momentum, vol_ratio, atr_ratio, trend, rsi]
# Labels: 1 = good entry, 0 = bad entry
X = np.random.randn(200, 5)
y = np.random.randint(0, 2, 200)

# Train
model = FeatureQualityModel()
model.fit(X, y)

# Cross-validate
cv_results = model.cross_validate(X, y, cv=5)
print(f"Accuracy: {cv_results['mean_accuracy']:.2f} ± {cv_results['std_accuracy']:.2f}")
```

---

## Integrazione con backtest.py

```python
# Script per analizzare risultati backtest
import json
from ml_feedback import MLFeedbackLoop

# Carica trade da backtest
with open("backtest_results.json") as f:
    trades = json.load(f)["trades"]

ml = MLFeedbackLoop()
analysis = ml.analyze_trades(trades)

# Mostra report
print("=== ERROR ANALYSIS REPORT ===")
print(f"Total: {analysis['total_trades']}")
print(f"Win Rate: {analysis['win_rate']:.1%}")
print(f"\nBy Session:")
for session, stats in analysis["by_session"].items():
    print(f"  {session}: W={stats['wins']}, L={stats['losses']}")
print(f"\nFailure Patterns:")
for pattern in analysis["common_failure_patterns"]:
    print(f"  - {pattern}")
```

---

## Workflow Completo

```
1. Run backtest  →  trades.json
2. MLFeedbackLoop.analyze_trades()  →  error patterns
3. HeuristicTuner.suggest_params()  →  param suggestions
4. Applica modifiche .env
5. Ripeti e verifica miglioramento
```

## Parametri .env

Aggiungi in `config.py`:

```python
ML_ENABLE_QUALITY_CHECK: bool = _get_bool("ML_ENABLE_QUALITY_CHECK", False)
ML_MIN_SAMPLES: int = _get_int("ML_MIN_SAMPLES", 100)
ML_CONFIDENCE_THRESHOLD: float = _get_float("ML_CONFIDENCE_THRESHOLD", 0.7)
```

---

## Note

- **scikit-learn** opzionale — se non installato, i metodi ML ritornano fallback values
- **xgboost** opzionale per MLTuner avanzato
- Dati storici: `C:\trading-agent\data\historical\` (24 anni EURUSD/GBPUSD/USDJPY)