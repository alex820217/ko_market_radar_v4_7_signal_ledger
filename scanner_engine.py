from datetime import datetime, time
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import streamlit as st
import ta
import yfinance as yf


def _series(frame, column):
    value = frame[column]
    value = value.iloc[:, 0] if isinstance(value, pd.DataFrame) else value
    return pd.to_numeric(value, errors="coerce")


@st.cache_data(ttl=240, show_spinner=False)
def download(ticker, interval="5m", period="5d"):
    data = yf.download(ticker, interval=interval, period=period, auto_adjust=True, prepost=False, progress=False, threads=False)
    if data.empty:
        return data
    result = pd.DataFrame(index=data.index)
    for column in ("Open", "High", "Low", "Close", "Volume"):
        result[column] = _series(data, column)
    return result.dropna(subset=["Open", "High", "Low", "Close"])


@st.cache_data(ttl=180, show_spinner=False)
def download_3m(ticker):
    data = download(ticker, "1m", "7d")
    if data.empty:
        return data
    return data.resample("3min", origin="start_day", label="right", closed="right").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    ).dropna()


def market_open(ticker):
    if ticker.endswith(".DE") or ticker in {"^GDAXI", "^STOXX50E"}:
        now = datetime.now(ZoneInfo("Europe/Berlin"))
        return now.weekday() < 5 and time(9) <= now.time() < time(17, 30)
    if ticker.startswith("^") or ticker.isalpha():
        now = datetime.now(ZoneInfo("America/New_York"))
        return now.weekday() < 5 and time(9, 30) <= now.time() < time(16)
    return True


def indicators(frame):
    data = frame.copy(); close, high, low, volume = data.Close, data.High, data.Low, data.Volume.fillna(0)
    for length in (9, 20, 50, 200):
        data[f"EMA{length}"] = ta.trend.EMAIndicator(close, length).ema_indicator()
    data["RSI"] = ta.momentum.RSIIndicator(close, 14).rsi()
    data["ATR"] = ta.volatility.AverageTrueRange(high, low, close, 14).average_true_range()
    data["ADX"] = ta.trend.ADXIndicator(high, low, close, 14).adx()
    data["MACD"] = ta.trend.MACD(close).macd_diff()
    typical = (high + low + close) / 3
    days = pd.Series(data.index.date, index=data.index)
    cumulative_volume = volume.groupby(days).cumsum()
    data["VWAP"] = ((typical * volume).groupby(days).cumsum() / cumulative_volume.replace(0, np.nan)).fillna(data.EMA20)
    return data.dropna()


def _regime_60(raw15):
    hourly = raw15.resample("60min", origin="start_day", label="right", closed="right").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    ).dropna()
    hourly = indicators(hourly.iloc[:-1])
    if len(hourly) < 3: return "NEUTRAL"
    row, previous = hourly.iloc[-1], hourly.iloc[-2]
    long_score = sum([row.Close > row.EMA20, row.EMA20 > row.EMA50, row.EMA20 > previous.EMA20, row.MACD >= 0])
    short_score = sum([row.Close < row.EMA20, row.EMA20 < row.EMA50, row.EMA20 < previous.EMA20, row.MACD <= 0])
    return "LONG" if long_score >= 3 and long_score > short_score else "SHORT" if short_score >= 3 and short_score > long_score else "NEUTRAL"


def scan_asset(meta):
    raw5, raw15 = download(meta["ticker"], "5m", "5d"), download(meta["ticker"], "15m", "30d")
    data5, data15 = indicators(raw5.iloc[:-1]), indicators(raw15.iloc[:-1])
    if len(data5) < 60 or len(data15) < 80: raise ValueError("zu wenig bestätigte Kursdaten")
    row15, row5 = data15.iloc[-1], data5.iloc[-1]
    long15 = sum([row15.Close > row15.EMA20, row15.EMA20 > row15.EMA50, row15.RSI > 50, row15.MACD > 0])
    short15 = sum([row15.Close < row15.EMA20, row15.EMA20 < row15.EMA50, row15.RSI < 50, row15.MACD < 0])
    direction = "LONG" if long15 >= short15 else "SHORT"
    regime = _regime_60(raw15)
    setup = sum([row5.Close > row5.VWAP, row5.EMA9 > row5.EMA20, row5.RSI > 50, row5.MACD > 0]) if direction == "LONG" else sum([row5.Close < row5.VWAP, row5.EMA9 < row5.EMA20, row5.RSI < 50, row5.MACD < 0])
    raw3 = download_3m(meta["ticker"]) if setup >= 2 else pd.DataFrame()
    data3 = indicators(raw3.iloc[:-1]) if not raw3.empty else pd.DataFrame()
    trigger = 0
    if len(data3) >= 40:
        row3, previous3 = data3.iloc[-1], data3.iloc[-2]
        trigger = sum([row3.Close > row3.EMA9, row3.RSI > 52, row3.Close > previous3.High]) if direction == "LONG" else sum([row3.Close < row3.EMA9, row3.RSI < 48, row3.Close < previous3.Low])
    distance = abs(row5.Close - row5.EMA20) / row5.ATR
    score = min(100, (long15 if direction == "LONG" else short15) * 10 + setup * 10 + trigger * 7)
    late = distance > 1
    hot = (direction == "LONG" and row5.RSI > 72) or (direction == "SHORT" and row5.RSI < 28)
    if late and setup >= 3: signal = "LATE ENTRY"
    elif hot and setup >= 3: signal = "HOT ENTRY"
    elif regime not in {direction, "NEUTRAL"}: signal = "CONTEXT CONFLICT"
    elif setup >= 3 and trigger >= 2 and score >= 80: signal = ("CONFIRMED " if score >= 88 else "EARLY ") + direction
    elif setup >= 3: signal = "PRE-" + direction
    else: signal = "WATCH " + direction if regime == direction else "WAIT"
    entry_status = "OPTIMAL" if distance <= .75 else "AKZEPTABEL" if distance <= 1 else "SPÄT"
    grade = "A+" if score >= 92 else "A" if score >= 85 else "B" if score >= 75 else "C" if score >= 65 else "-"
    if late or hot or "CONFLICT" in signal: grade = "-"
    hints = []
    if row5.ADX < 20: hints.append(f"ADX nur {row5.ADX:.1f}")
    if distance > .75: hints.append(f"Entry {distance:.2f} ATR von EMA20")
    risk = 1.2 * row5.ATR; entry = float(row5.Close)
    return {
        "Asset": meta["name"], "Ticker": meta["ticker"], "Signal": signal, "Grade": grade,
        "Score": int(score), "60m Regime": regime, "15m Bias": direction, "5m Setup": f"{setup}/4",
        "3m Trigger": f"{trigger}/3", "Entry Status": entry_status,
        "Setup-Hinweis": "; ".join(hints) or "Setup technisch sauber", "ADX": float(row5.ADX),
        "RSI": float(row5.RSI), "EMA20 ATR": float(distance), "Entry": entry,
        "Stop": float(entry - risk if direction == "LONG" else entry + risk),
        "TP1": float(entry + 1.8 * risk if direction == "LONG" else entry - 1.8 * risk),
        "TP2": float(entry + 2.8 * risk if direction == "LONG" else entry - 2.8 * risk), "CRV": 1.8,
        "Signalzeit": str(data5.index[-1]),
    }
