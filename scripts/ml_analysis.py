import json
import sys
sys.path.insert(0, ".")

from ml_feedback import MLFeedbackLoop

with open("backtest_trades.json") as f:
    trades = json.load(f)

for t in trades:
    if t["direction"] == "BUY":
        t["outcome"] = "WIN" if t["exit_price"] > t["entry_price"] else "LOSS"
    else:
        t["outcome"] = "WIN" if t["exit_price"] < t["entry_price"] else "LOSS"

ml = MLFeedbackLoop()
analysis = ml.analyze_trades(trades)

print("=== ML ANALYSIS ===")
print(f"Total: {analysis['total_trades']}")
print(f"Wins: {analysis['wins']} ({analysis['win_rate']:.1%})")
print(f"Losses: {analysis['losses']}")

print()

for session, stats in analysis["by_session"].items():
    total = stats["wins"] + stats["losses"]
    wr = stats["wins"] / total * 100 if total > 0 else 0
    print(f"{session}: W={stats['wins']}, L={stats['losses']} -> {wr:.0f}%")

print()

print("Failure Patterns:")
for p in analysis["common_failure_patterns"]:
    print(f"  {p}")

# Suggestions
current_params = {
    "ENABLE_ASIA_SESSION": True,
    "MIN_HOLD_MINUTES": 15,
    "MIN_BREAKOUT_VOLUME_RATIO": 1.5,
}

suggestions = ml.suggest_parameters(trades, current_params)

if suggestions:
    print()
    print("Parameter Suggestions:")
    for s in suggestions:
        print(f"  {s.param_name}: {s.current_value} -> {s.suggested_value}")
        print(f"    Reason: {s.reason}")
        print(f"    Confidence: {s.confidence:.0%}")