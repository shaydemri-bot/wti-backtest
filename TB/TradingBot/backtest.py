# backtest.py
# בק-טסט בסיסי על חיתוך ממוצעים (SMA20/SMA50) כדי להמחיש תוצאות + יצירת CSV

from __future__ import annotations
import json
import pandas as pd
import numpy as np
import yaml
from data import download

def compute_backtest(symbol: str, period: str, interval: str):
    # 1) נתונים
    df = download(symbol, period, interval).copy()

    # 2) אינדיקטורים בסיסיים (בלי חבילות חיצוניות)
    df["sma_fast"] = df["close"].rolling(20, min_periods=1).mean()
    df["sma_slow"] = df["close"].rolling(50, min_periods=1).mean()

    # 3) סיגנלים: חציה של מהיר מעל/מתחת לאיטי
    cross_up = (df["sma_fast"].shift(1) <= df["sma_slow"].shift(1)) & (df["sma_fast"] > df["sma_slow"])
    cross_dn = (df["sma_fast"].shift(1) >= df["sma_slow"].shift(1)) & (df["sma_fast"] < df["sma_slow"])

    # 4) סימולציה פשוטה: כניסה Long על cross_up, יציאה על cross_dn (ולהיפך ל-Short)
    position = None  # None / "long" / "short"
    entry_px = None
    entry_ts = None
    trades = []

    for ts, row in df.iterrows():
        if position is None:
            if cross_up.loc[ts]:
                position = "long"; entry_px = row["close"]; entry_ts = ts
                df.loc[ts, "entry_long"] = True
            elif cross_dn.loc[ts]:
                position = "short"; entry_px = row["close"]; entry_ts = ts
                df.loc[ts, "entry_short"] = True
        elif position == "long":
            # יציאה כשהמגמה מתהפכת
            if cross_dn.loc[ts]:
                exit_px = row["close"]
                pnl = (exit_px - entry_px)  # גודל יחידה אחת (חבית אחת לצורך הדוגמה)
                trades.append({"entry_time": entry_ts, "side":"long", "entry": float(entry_px),
                               "exit_time": ts, "exit": float(exit_px), "pnl": float(pnl)})
                df.loc[ts, "exit"] = True
                position = None; entry_px = None; entry_ts = None
        elif position == "short":
            if cross_up.loc[ts]:
                exit_px = row["close"]
                pnl = (entry_px - exit_px)
                trades.append({"entry_time": entry_ts, "side":"short", "entry": float(entry_px),
                               "exit_time": ts, "exit": float(exit_px), "pnl": float(pnl)})
                df.loc[ts, "exit"] = True
                position = None; entry_px = None; entry_ts = None

    trades_df = pd.DataFrame(trades)
    return df, trades_df

def save_results(prefix: str, trades_df: pd.DataFrame):
    metrics = {}
    if not trades_df.empty:
        wins = trades_df[trades_df["pnl"]>0]
        losses = trades_df[trades_df["pnl"]<=0]
        metrics = {
            "trades": int(len(trades_df)),
            "win_rate": round(len(wins)/len(trades_df), 3) if len(trades_df)>0 else 0.0,
            "total_pnl": float(trades_df["pnl"].sum())
        }
        trades_df.to_csv(f"{prefix}_trades.csv", index=False)
    else:
        metrics = {"trades":0, "win_rate":0.0, "total_pnl":0.0}
    with open(f"{prefix}_metrics.json","w",encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    return metrics

def run_bt(symbol: str, period: str, interval: str, prefix: str = "bt"):
    df, trades = compute_backtest(symbol, period, interval)
    metrics = save_results(prefix, trades)
    # הדפסת תקציר
    print(f"{prefix} -> trades={metrics['trades']} win_rate={metrics['win_rate']} total_pnl={metrics['total_pnl']:.2f}")
    # הדפסה של כמה שורות מהנתונים להמחשה
    print(df[["close","sma_fast","sma_slow"]].tail(5))

if __name__ == "__main__":
    with open("config.yaml","r",encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    symbol = cfg["market"]["symbol"]
    period = str(cfg["backtest"]["bt1"]["period"])
    interval = str(cfg["backtest"]["bt1"]["interval"])
    run_bt(symbol, period, interval, "bt1")
