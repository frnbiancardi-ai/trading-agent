"""Debug: date range check."""
import pandas as pd
from pathlib import Path

path = Path("data/historical") / "EURUSD" / "M15.csv"
df = pd.read_csv(path, sep=";", encoding="utf-8")
df["date"] = pd.to_datetime(df["Data"] + " " + df[" Ora"], format="%d/%m/%Y %H:%M:%S")

print("Date range in data/historical/EURUSD/M15.csv:")
print(f"Min: {df['date'].min()}")
print(f"Max: {df['date'].max()}")

# Count by year
print("\nRows by year:")
print(df.groupby(df["date"].dt.year).size())

# Check year 2024
df2024 = df[df["date"].dt.year == 2024]
print(f"\n2024 total rows: {len(df2024)}")
print(f"2024 date range: {df2024['date'].min()} to {df2024['date'].max()}")

print("\nDone")