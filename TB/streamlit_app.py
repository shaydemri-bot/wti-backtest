
# streamlit_app.py — WTI Strategy Lab (Deploy-Ready)
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from math import floor

st.set_page_config(page_title="WTI Strategy Lab", layout="wide")

# ---------- Small helpers (UI) ----------
def help_popover(text: str):
    with st.popover("ℹ️", use_container_width=False):
        st.write(text)

def sb_number(label, value, min_value=None, max_value=None, step=None, help_text=""):
    c1, c2 = st.sidebar.columns([4,1])
    with c1:
        v = st.number_input(label, value=value, min_value=min_value, max_value=max_value, step=step, key=label)
    with c2:
        help_popover(help_text)
    return v

def sb_selectbox(label, options, index=0, help_text=""):
    c1, c2 = st.sidebar.columns([4,1])
    with c1:
        v = st.selectbox(label, options, index=index, key=label)
    with c2:
        help_popover(help_text)
    return v

def sb_checkbox(label, value=False, help_text=""):
    c1, c2 = st.sidebar.columns([4,1])
    with c1:
        v = st.checkbox(label, value=value, key=label)
    with c2:
        help_popover(help_text)
    return v

def sb_slider(label, min_value, max_value, value, step=None, help_text=""):
    c1, c2 = st.sidebar.columns([4,1])
    with c1:
        v = st.slider(label, min_value=min_value, max_value=max_value, value=value, step=step, key=label)
    with c2:
        help_popover(help_text)
    return v

def ensure_series(x):
    if isinstance(x, pd.DataFrame):
        return x.iloc[:, 0] if x.shape[1] >= 1 else pd.Series([], dtype=float)
    if not isinstance(x, pd.Series):
        return pd.Series(x)
    return x

# ---------- Indicators ----------
def ema(s, n):
    s = ensure_series(s).astype(float)
    return s.ewm(span=n, adjust=False).mean()

def rsi(close, n=14):
    close = ensure_series(close).astype(float)
    diff = close.diff()
    up = np.where(diff > 0, diff, 0.0)
    dn = np.where(diff < 0, -diff, 0.0)
    roll_up = pd.Series(up, index=close.index).rolling(n).mean()
    roll_dn = pd.Series(dn, index=close.index).rolling(n).mean()
    rs = roll_up / (roll_dn.replace(0, np.nan))
    return (100 - (100 / (1 + rs))).fillna(50)

def bollinger(close, n=20, k=2):
    close = ensure_series(close).astype(float)
    ma = close.rolling(n).mean()
    sd = close.rolling(n).std(ddof=0)
    return ma, ma + k*sd, ma - k*sd

def atr(df, n=14):
    high = ensure_series(df["High"]).astype(float)
    low  = ensure_series(df["Low"]).astype(float)
    close = ensure_series(df["Close"]).astype(float)
    prev_c = close.shift(1)
    tr = pd.concat([(high-low), (high-prev_c).abs(), (low-prev_c).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def volume_zscore(vol, n=50):
    m = vol.rolling(n).mean()
    s = vol.rolling(n).std(ddof=0)
    return (vol - m) / s

def swing_levels(df, lookback=10, lookforward=10, min_dist=0.3, max_levels=8):
    highs=[]; lows=[]
    H=df["High"]; L=df["Low"]
    for i in range(lookback, len(df)-lookforward):
        if H.iloc[i] == H.iloc[i-lookback:i+lookforward+1].max():
            highs.append((df.index[i], float(H.iloc[i])))
        if L.iloc[i] == L.iloc[i-lookback:i+lookforward+1].min():
            lows.append((df.index[i], float(L.iloc[i])))
    def merge(levels):
        levels_sorted=sorted(levels, key=lambda x:x[1]); merged=[]
        for ts, price in levels_sorted:
            if not merged or abs(price-merged[-1][1])>=min_dist:
                merged.append([ts, price, 1])
            else:
                merged[-1][1]=(merged[-1][1]*merged[-1][2]+price)/(merged[-1][2]+1); merged[-1][2]+=1
        merged=sorted(merged, key=lambda x:x[2], reverse=True)[:max_levels]
        return [p for _,p,_ in merged]
    return merge(highs), merge(lows)

# ---------- Sidebar ----------
st.title("📊 WTI (CL=F) — Strategy Lab (Cloud)")

st.sidebar.header("Data")
period = sb_selectbox("Period", ["7d","1mo","3mo","6mo","1y"], index=2,
    help_text="חלון זמן להורדת נתונים. טווח ארוך יותר = יותר נרות ו-backtest ארוך יותר.")
interval = sb_selectbox("Interval", ["15m","30m","1h","4h","1d"], index=2,
    help_text="גרנולריות הנרות. אינטרוול קצר = יותר רעש אך יותר עסקאות.")
ticker = st.sidebar.text_input("Ticker", "CL=F")

st.sidebar.header("Indicators")
ema_fast = sb_number("EMA fast", 20, 5, 200, 1, "ממוצע נע מהיר. להגדיל ⇒ פחות איתותים, תגובה איטית.")
ema_slow = sb_number("EMA slow", 50, 10, 300, 1, "ממוצע נע איטי/פילטר טרנד.")
rsi_len  = sb_number("RSI length", 14, 5, 50, 1, "אורך RSI.")
atr_len  = sb_number("ATR length", 14, 5, 50, 1, "אורך ATR.")

st.sidebar.header("Entries")
trend_filter = sb_checkbox("Filter by EMA slow (avoid counter-trend)", True, "אל תיכנס נגד הטרנד האיטי.")
use_vol_spike = sb_checkbox("Require Volume Spike", False, "דורש חריגת נפח (Z-score).")
vol_z_thr = sb_slider("Volume Z-score threshold", -1.0, 5.0, 1.5, 0.1, "סף חריגה.")

st.sidebar.header("Exits (Risk)")
atr_sl = sb_number("SL = ATR ×", 1.5, 0.1, 10.0, 0.1, "סטופ במכפלת ATR.")
atr_tp = sb_number("TP = ATR ×", 2.5, 0.1, 20.0, 0.1, "יעד במכפלת ATR.")
bars_timeout = sb_number("Time Exit (bars)", 60, 0, 1000, 5, "יציאת זמן מאולצת.")

st.sidebar.header("Position & Costs")
capital = sb_number("Account capital (USD)", 10_000, 100, 10_000_000, 100, "הון חשבון סימולציה.")
risk_pct = sb_slider("Risk per trade (%)", 0.1, 5.0, 0.5, 0.1, "אחוז הון בסיכון לטרייד.")
contract_size = sb_number("Units per contract (barrels)", 100, 1, 10_000, 1, "יחידות בחוזה (כמו 100 חביות).")
leverage = sb_number("Leverage (simulation)", 20, 1, 100, 1, "מינוף לחישוב חשיפה/PNL.")
commission = sb_number("Commission per trade (USD)", 1.0, 0.0, 50.0, 0.5, "עמלה לטרייד.")
spread = sb_number("Spread/Slippage (USD per unit)", 0.02, 0.0, 2.0, 0.01, "עלות ספרד/סליפג' ליחידה.")
usd_ils = sb_number("USD→ILS rate (approx.)", 3.7, 2.5, 6.0, 0.01, "שער המרה להוצאת PnL בש"ח.")

st.sidebar.header("Chart")
rangeslider = sb_checkbox("Show range slider", False, "סרגל טווח לזום מהיר.")
candle_opacity = sb_slider("Candle opacity", 0.3, 1.0, 0.9, 0.05, "שקיפות הנרות.")

# ---------- Data ----------
raw = yf.download(ticker, period=period, interval=interval, auto_adjust=False)
if raw.empty:
    st.error("No data from yfinance. Adjust period/interval.")
    st.stop()
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)
required = ["Open","High","Low","Close"]
missing = [c for c in required if c not in raw.columns]
if missing:
    st.error(f"Missing columns: {missing}")
    st.write("Columns:", list(raw.columns))
    st.stop()
df = raw.copy()

# ---------- Indicators calc ----------
df["EMA_FAST"] = ema(df["Close"], ema_fast)
df["EMA_SLOW"] = ema(df["Close"], ema_slow)
df["RSI"] = rsi(df["Close"], rsi_len)
df["ATR"] = atr(df, atr_len)
df["BB_MA"], df["BB_UP"], df["BB_DOWN"] = bollinger(df["Close"], 20, 2)
if "Volume" in df.columns:
    df["VOL_Z"] = volume_zscore(df["Volume"], 50)
else:
    df["Volume"] = np.nan
    df["VOL_Z"] = np.nan

# ---------- Simple strategy backtest ----------
def backtest(df):
    r = df["RSI"]
    cross_up30 = (r.shift(1) <= 30) & (r > 30)
    cross_dn70 = (r.shift(1) >= 70) & (r < 70)

    pos=None; entry_px=None; entry_ts=None; entry_bar=None; sl=None; tp=None; qty=0
    trades=[]; df["marker_px"]=np.nan; df["marker_text"]=None

    for i,(ts,row) in enumerate(df.iterrows()):
        px=float(row["Close"]); high=float(row["High"]); low=float(row["Low"])
        if pos is None:
            ok_vol=True
            if use_vol_spike and not np.isnan(row["VOL_Z"]):
                ok_vol = row["VOL_Z"] >= vol_z_thr
            if cross_up30.loc[ts] and px>row["EMA_FAST"] and (not trend_filter or px>=row["EMA_SLOW"]) and ok_vol:
                stop_dist=atr_sl*float(row["ATR"]); risk_per_unit=stop_dist*contract_size; cash_risk=capital*(risk_pct/100.0)
                qty=max(1, floor(cash_risk/max(risk_per_unit,1e-8))); pos,entry_px,entry_ts,entry_bar="long",px,ts,i
                sl=entry_px-stop_dist; tp=entry_px+atr_tp*float(row["ATR"])
                df.at[ts,"marker_px"]=px; df.at[ts,"marker_text"]=f"Long | qty={qty}"
            elif cross_dn70.loc[ts] and px<row["EMA_FAST"] and (not trend_filter or px<=row["EMA_SLOW"]) and ok_vol:
                stop_dist=atr_sl*float(row["ATR"]); risk_per_unit=stop_dist*contract_size; cash_risk=capital*(risk_pct/100.0)
                qty=max(1, floor(cash_risk/max(risk_per_unit,1e-8))); pos,entry_px,entry_ts,entry_bar="short",px,ts,i
                sl=entry_px+stop_dist; tp=entry_px-atr_tp*float(row["ATR"])
                df.at[ts,"marker_px"]=px; df.at[ts,"marker_text"]=f"Short | qty={qty}"
        else:
            exit_reason=None; exit_px=None
            if pos=="long":
                if low<=sl: exit_px,exit_reason=sl,"SL"
                elif high>=tp: exit_px,exit_reason=tp,"TP"
                elif cross_dn70.loc[ts] or px<row["EMA_FAST"]: exit_px,exit_reason=px,"Rule"
            else:
                if high>=sl: exit_px,exit_reason=sl,"SL"
                elif low<=tp: exit_px,exit_reason=tp,"TP"
                elif cross_up30.loc[ts] or px>row["EMA_FAST"]: exit_px,exit_reason=px,"Rule"
            if exit_px is None and bars_timeout and (i-entry_bar)>=bars_timeout:
                exit_px,exit_reason=px,"Time"
            if exit_px is not None:
                per_unit_cost = spread + (commission/max(qty,1)/contract_size)
                unit_pnl = (exit_px-entry_px) if pos=="long" else (entry_px-exit_px)
                unit_pnl -= per_unit_cost
                usd = unit_pnl*qty*contract_size*leverage
                ils = usd*usd_ils
                trades.append({
                    "entry_time":entry_ts,"side":pos,"entry":entry_px,"sl":sl,"tp":tp,
                    "exit_time":ts,"exit":exit_px,"reason":exit_reason,"qty":qty,
                    "unit_pnl":unit_pnl,"pnl_usd":usd,"pnl_ils":ils
                })
                pos=entry_px=entry_ts=sl=tp=None; entry_bar=None; qty=0
    return pd.DataFrame(trades)

trades = backtest(df)

# ---------- Metrics ----------
if trades.empty:
    total_usd=total_ils=0.0; win_rate=0.0; expectancy=0.0
else:
    total_usd=float(trades["pnl_usd"].sum())
    total_ils=float(trades["pnl_ils"].sum())
    win_rate=float((trades["pnl_usd"]>0).mean())
    expectancy=float(trades["pnl_usd"].mean())

# Equity curve
if not trades.empty:
    eq = trades[["exit_time","pnl_usd"]].copy().set_index("exit_time").sort_index()
    eq["equity"] = eq["pnl_usd"].cumsum()
else:
    eq = pd.DataFrame(columns=["equity"])

# ---------- S/R ----------
sr_highs, sr_lows = swing_levels(df, lookback=10, lookforward=10,
                                 min_dist=float(df["ATR"].median() or 0.3), max_levels=8)

# ---------- Charts ----------
x = df.index
fig = make_subplots(rows=1, cols=1, shared_xaxes=True, vertical_spacing=0.03)
fig.add_trace(go.Candlestick(x=x, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
                             name=ticker, opacity=candle_opacity, increasing_line_width=1.2, decreasing_line_width=1.2), 1, 1)

show_overlays = st.sidebar.multiselect("Overlays visibility",
    ["EMA fast","EMA slow","Bollinger Bands","S/R levels","Entries/Exits"],
    default=["EMA fast","EMA slow","Bollinger Bands","S/R levels","Entries/Exits"])

if "EMA fast" in show_overlays:
    fig.add_trace(go.Scatter(x=x, y=df["EMA_FAST"], name=f"EMA{int(ema_fast)}", mode="lines"), 1, 1)
if "EMA slow" in show_overlays:
    fig.add_trace(go.Scatter(x=x, y=df["EMA_SLOW"], name=f"EMA{int(ema_slow)}", mode="lines"), 1, 1)
if "Bollinger Bands" in show_overlays:
    fig.add_trace(go.Scatter(x=x, y=df["BB_UP"], name="BB Upper", mode="lines"), 1, 1)
    fig.add_trace(go.Scatter(x=x, y=df["BB_MA"], name="BB MA", mode="lines"), 1, 1)
    fig.add_trace(go.Scatter(x=x, y=df["BB_DOWN"], name="BB Lower", mode="lines"), 1, 1)

if "Entries/Exits" in show_overlays:
    mk = df.dropna(subset=["marker_px"])
    if not mk.empty:
        fig.add_trace(go.Scatter(x=mk.index, y=mk["marker_px"], mode="markers+text", name="Signals",
                                 text=mk["marker_text"], textposition="top center",
                                 marker_symbol="diamond", marker_size=10), 1, 1)

if "S/R levels" in show_overlays:
    for lvl in sr_highs or []:
        fig.add_hline(y=lvl, line_width=1, line_dash="dot", line_color="red", annotation_text="R", annotation_position="right")
    for lvl in sr_lows or []:
        fig.add_hline(y=lvl, line_width=1, line_dash="dot", line_color="green", annotation_text="S", annotation_position="right")

fig.update_layout(template="simple_white", height=720, xaxis_rangeslider_visible=rangeslider,
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                  margin=dict(l=20,r=20,t=30,b=10))

tab_chart, tab_rsi, tab_equity, tab_help = st.tabs(["Chart","RSI","Equity","Help"])
with tab_chart:
    st.plotly_chart(fig, use_container_width=True)

with tab_rsi:
    rfig = go.Figure()
    rfig.add_trace(go.Scatter(x=x, y=df["RSI"], name="RSI", mode="lines"))
    rfig.add_hline(y=70, line_dash="dash"); rfig.add_hline(y=30, line_dash="dash")
    rfig.update_layout(template="simple_white", height=220, xaxis_rangeslider_visible=False, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(rfig, use_container_width=True)

with tab_equity:
    if not eq.empty:
        efig = go.Figure()
        efig.add_trace(go.Scatter(x=eq.index, y=eq["equity"], name="Equity", mode="lines"))
        efig.update_layout(template="simple_white", height=220, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(efig, use_container_width=True)
    else:
        st.info("No closed trades yet for equity curve.")

help_md = """
# Help – Parameters Guide

**Data**
- **Period** – חלון זמן להורדת נתונים. טווח ארוך = יותר נרות ו-backtest ארוך יותר.
- **Interval** – גרנולריות הנרות. קצר יותר (15m) = יותר רעש ויותר עסקאות; ארוך יותר (1h/4h/1d) = פחות רעש.

**Indicators**
- **EMA fast** – ממוצע נע מהיר. גדול יותר ⇒ איטי/חלק יותר (פחות איתותים).
- **EMA slow** – ממוצע נע איטי (פילטר טרנד). גדול יותר ⇒ מגמות חלקות ופחות כניסות נגדיות.
- **RSI length** – אורך RSI. קצר ⇒ רגיש; ארוך ⇒ חלק ופחות חציות.
- **ATR length** – אורך ATR לתנודתיות. ארוך ⇒ SL/TP פחות רגישים.

**Entries**
- **Filter by EMA slow** – לא לוקחים לונג מתחת ל-EMA האיטי/שורט מעליו.
- **Require Volume Spike** – דורש חריגת נפח (Z-score).
- **Volume Z-score threshold** – סף חריגה. גבוה ⇒ רק קפיצות נפח חזקות.

**Exits (Risk)**
- **SL = ATR ×** – סטופ במכפלת ATR. גדול ⇒ סטופ רחב יותר (סיכון גדול יותר לטרייד).
- **TP = ATR ×** – יעד במכפלת ATR. גדול ⇒ יעד רחוק (יחס R/R גבוה, פחות פגיעות).
- **Time Exit (bars)** – יציאת זמן מאולצת אחרי X נרות.

**Position & Costs**
- **Account capital (USD)** – הון חשבון סימולציה.
- **Risk per trade (%)** – אחוז הון בסיכון לטרייד. גדול ⇒ כמות/תנודתיות PnL גבוהות.
- **Units per contract (barrels)** – יחידות בחוזה (ל־WTI לרוב 100 בפרוקסי/CFD).
- **Leverage (simulation)** – מינוף לחישוב חשיפה/PNL.
- **Commission per trade (USD)** – עמלה קבועה לטרייד.
- **Spread/Slippage (USD per unit)** – עלות ספרד/סליפג’ ליחידה.
- **USD→ILS rate** – שער חישובי להמרת PnL לש”ח.

**Chart**
- **Show range slider** – סרגל טווח לזום מהיר.
- **Candle opacity** – שקיפות נרות (להקטין כדי לראות שכבות).
"""
with tab_help:
    st.markdown(help_md)

st.subheader("Trades")
if not trades.empty:
    st.dataframe(trades, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Download trades CSV", trades.to_csv(index=False).encode("utf-8"), "trades.csv", "text/csv")
else:
    st.info("No trades for the chosen parameters.")

c1,c2,c3,c4 = st.columns(4)
c1.metric("Total PnL (USD)", f"{total_usd:,.2f}")
c2.metric("Total PnL (ILS)", f"{total_ils:,.2f}")
c3.metric("Win-Rate", f"{win_rate:.1%}")
c4.metric("Expectancy / trade (USD)", f"{expectancy:,.2f}")
