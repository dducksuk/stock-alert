"""지표 계산 모음.

새 지표를 추가하려면:
  1) df(OHLCV DataFrame)와 파라미터를 받아 pd.Series 를 돌려주는 함수를 만들고
  2) 아래 INDICATORS 딕셔너리에 이름을 등록하면 config.yaml 에서 바로 사용 가능.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder RSI (TradingView / 대부분 증권사 HTS와 같은 방식)."""
    close = df["Close"].astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0).to_numpy()
    loss = (-delta.clip(upper=0)).to_numpy()

    out = np.full(len(close), np.nan)
    if len(close) <= period:
        return pd.Series(out, index=close.index)

    avg_gain = np.nanmean(gain[1 : period + 1])
    avg_loss = np.nanmean(loss[1 : period + 1])
    for i in range(period, len(close)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gain[i]) / period
            avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100 - 100 / (1 + rs)
    return pd.Series(out, index=close.index)


def price(df: pd.DataFrame) -> pd.Series:
    return df["Close"].astype(float)


def change_pct(df: pd.DataFrame) -> pd.Series:
    """직전 봉 종가 대비 등락률(%). timeframe 1d 이면 '전일 대비'."""
    return df["Close"].astype(float).pct_change() * 100


def sma(df: pd.DataFrame, period: int) -> pd.Series:
    return df["Close"].astype(float).rolling(period).mean()


def ema(df: pd.DataFrame, period: int) -> pd.Series:
    return df["Close"].astype(float).ewm(span=period, adjust=False).mean()


def drawdown_pct(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """최근 period 봉 최고가 대비 현재가 하락률(%). 예: -12.3"""
    high = df["High"].astype(float).rolling(period, min_periods=1).max()
    return (df["Close"].astype(float) / high - 1) * 100


def volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """현재 봉 거래량 / 직전 period 봉 평균 거래량."""
    vol = df["Volume"].astype(float)
    return vol / vol.shift(1).rolling(period).mean()


INDICATORS = {
    "rsi": rsi,
    "price": price,
    "change_pct": change_pct,
    "sma": sma,
    "ema": ema,
    "drawdown_pct": drawdown_pct,
    "volume_ratio": volume_ratio,
}

# 지표 이름 → 알림 메시지에 보여줄 한글 이름
LABELS = {
    "rsi": "RSI",
    "price": "현재가",
    "change_pct": "등락률(%)",
    "sma": "SMA",
    "ema": "EMA",
    "drawdown_pct": "고점대비(%)",
    "volume_ratio": "거래량배수",
}
