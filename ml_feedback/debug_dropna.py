"""Compare: con e senza dropna."""
import pandas as pd
from pathlib import Path

sym = "EURUSD"

path = Path("data/historical") / sym / "M15.csv"
df = pd.read_csv(path, sep=";", encoding="utf-8")
df["date"] = pd.to_datetime(df["Data"] + " " + df[" Ora"], format="%d/%m/%Y %H:%M:%S")
df["hour"] = df["date"].dt.hour
df = df[(df["date"] >= "2024-01-01") & (df["date"] < "2025-01-01")]

# No dropna
df1 = df.copy()
df1["sma200"] = df1[" Close"].rolling(200).mean()
delta = df1[" Close"].diff()
gain = delta.where(delta > 0, 0).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df1["rsi"] = 100 - (100 / (1 + gain / loss))

a = df1[(df1["hour"] == 15) & (df1["rsi"] >= 65) & (df1["rsi"] <= 80) & (df1[" Close"] > df1["sma200"])]
print(f"SENZA dropna: {len(a)} trades")

# Con dropna
df2 = df.copy()
df2["sma200"] = df2[" Close"].rolling(200).mean()
delta = df2[" Close"].diff()
gain = delta.where(delta > 0, 0).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
df2["rsi"] = 100 - (100 / (1 + gain / loss))
df2 = df2.dropna()

b = df2[(df2["hour"] == 15) & (df2["rsi"] >= 65) & (df2["rsi"] <= 80) & (df2[" Close"] > df2["sma200"])]
print(f"CON dropna: {len(b)} trades")

# Check: NaN in rsi or sma200
print(f"\nNaN in rsi (no dropna): {df1['rsi'].isna().sum()}")
print(f"NaN in sma200 (no dropna): {df1['sma200'].isna().sum()}")

print("\nDone")