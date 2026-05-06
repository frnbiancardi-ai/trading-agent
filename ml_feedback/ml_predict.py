"""ML model to predict trade outcome."""
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
import json

SYMS = ["EURUSD", "GBPUSD", "USDJPY"]

def load_csv(symbol):
    path = Path("data/historical") / symbol / "M15.csv"
    df = pd.read_csv(path, sep=";", encoding="utf-8")
    df["date"] = pd.to_datetime(df["Data"] + " " + df[" Ora"], format="%d/%m/%Y %H:%M:%S")
    df["hour"] = df["date"].dt.hour
    df["day"] = df["date"].dt.dayofweek
    return df.sort_values("date").reset_index(drop=True)

def calc(df):
    # SMA
    df["sma200"] = df[" Close"].rolling(200).mean()
    df["sma50"] = df[" Close"].rolling(50).mean()
    df["sma20"] = df[" Close"].rolling(20).mean()
    
    # RSI
    delta = df[" Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss))
    
    # ATR
    df["atr"] = (df[" High"] - df[" low"]).rolling(14).mean()
    
    # Momentum
    df["mom5"] = df[" Close"].pct_change(5)
    df["mom10"] = df[" Close"].pct_change(10)
    
    # Volatility
    df["vol20"] = df[" Close"].pct_change().rolling(20).std()
    
    return df

print("=== ML TRADE PREDICTION ===\n")

# Load all data 2020-2023 for training
train_data = []
for sym in SYMS:
    df = load_csv(sym)
    df = calc(df)
    df = df[(df["date"] >= "2020-01-01") & (df["date"] < "2024-01-01")]
    df = df.dropna()
    
    # Signal: RSI 65-90 + price > SMA200
    df["signal"] = (df["rsi"] >= 65) & (df["rsi"] <= 90) & (df[" Close"] > df["sma200"])
    df["next2"] = df[" Close"].shift(-2)
    df["win"] = (df["next2"] < df[" Close"]).astype(int)
    
    trades = df[df["signal"]].copy()
    if len(trades) > 0:
        train_data.append(trades[["hour", "day", "rsi", "atr", "mom5", "mom10", "vol20", "win"]])

df_train = pd.concat(train_data, ignore_index=True)
print(f"Training samples: {len(df_train)}")

# Features & target
X = df_train[["hour", "day", "rsi", "atr", "mom5", "mom10", "vol20"]]
y = df_train["win"]

# Scale features
X = (X - X.mean()) / X.std()

# Train RF
rf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
scores = cross_val_score(rf, X, y, cv=5)
print(f"CV Accuracy: {scores.mean():.3f} (+/- {scores.std():.3f})")

# Fit on all data
rf.fit(X, y)

# Test on 2024
test_data = []
for sym in SYMS:
    df = load_csv(sym)
    df = calc(df)
    df = df[(df["date"] >= "2024-01-01") & (df["date"] < "2025-01-01")]
    df = df.dropna()
    
    df["signal"] = (df["rsi"] >= 65) & (df["rsi"] <= 90) & (df[" Close"] > df["sma200"])
    df["next2"] = df[" Close"].shift(-2)
    df["win"] = (df["next2"] < df[" Close"]).astype(int)
    
    trades = df[df["signal"]].copy()
    if len(trades) > 0:
        test_data.append(trades[["hour", "day", "rsi", "atr", "mom5", "mom10", "vol20", "win"]])

df_test = pd.concat(test_data, ignore_index=True)
X_test = df_test[["hour", "day", "rsi", "atr", "mom5", "mom10", "vol20"]]
X_test = (X_test - X_test.mean()) / X_test.std()
y_test = df_test["win"]

# Predict
y_pred = rf.predict(X_test)
y_proba = rf.predict_proba(X_test)[:, 1]

accuracy = (y_pred == y_test).mean()
print(f"Test Accuracy: {accuracy:.3f}")

# Compare with base
base_acc = y_test.mean()
print(f"Base (always WIN): {base_acc:.3f}")

# Filter by proba > 0.55
mask = y_proba > 0.55
filtered = df_test[mask]
if len(filtered) > 0:
    filtered_acc = filtered["win"].mean()
    print(f"ML Filter (p>0.55): {len(filtered)} trades, ACC={filtered_acc:.3f}")

# Feature importance
print("\nFeature Importance:")
for f, imp in zip(["hour", "day", "rsi", "atr", "mom5", "mom10", "vol20"], rf.feature_importances_):
    print(f"  {f}: {imp:.3f}")

print("\nDone")