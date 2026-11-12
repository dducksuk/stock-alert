"""시세 데이터 (Yahoo Finance, yfinance) 조회."""
from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

# timeframe → 조회 기간 (지표 계산에 충분한 봉 수 확보용)
PERIOD_FOR = {
    "15m": "30d",
    "30m": "60d",
    "1h": "90d",
    "1d": "2y",
    "1wk": "10y",
}


class MarketData:
    def __init__(self):
        self._cache: dict[tuple[str, str], pd.DataFrame] = {}

    def prefetch(self, tickers: list[str], timeframe: str) -> None:
        """같은 timeframe 의 여러 종목을 한 번에 받아서 캐시."""
        need = [t for t in tickers if (t, timeframe) not in self._cache]
        if not need:
            return
        if timeframe not in PERIOD_FOR:
            raise ValueError(f"지원하지 않는 timeframe: {timeframe} (가능: {list(PERIOD_FOR)})")
        raw = yf.download(
            need,
            period=PERIOD_FOR[timeframe],
            interval=timeframe,
            group_by="ticker",
            auto_adjust=False,
            prepost=False,
            progress=False,
            threads=True,
        )
        for t in need:
            try:
                df = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
                df = df.dropna(subset=["Close"])
                if df.empty:
                    raise ValueError("빈 데이터")
                self._cache[(t, timeframe)] = df
            except Exception as e:  # 조회 실패 종목은 건너뜀
                log.warning("%s %s 데이터 조회 실패: %s", t, timeframe, e)
                self._cache[(t, timeframe)] = pd.DataFrame()

    def get(self, ticker: str, timeframe: str) -> pd.DataFrame:
        if (ticker, timeframe) not in self._cache:
            self.prefetch([ticker], timeframe)
        return self._cache[(ticker, timeframe)]


def top_by_market_cap(candidates: list[str], n: int) -> list[tuple[str, float]]:
    """후보 중 시가총액 상위 n개 [(티커, 시총)] 반환."""
    caps = []
    for t in candidates:
        try:
            cap = yf.Ticker(t).info.get("marketCap")
            if cap:
                caps.append((t, float(cap)))
            else:
                log.warning("%s 시가총액 정보 없음 - 건너뜀", t)
        except Exception as e:
            log.warning("%s 시가총액 조회 실패: %s", t, e)
    caps.sort(key=lambda x: x[1], reverse=True)
    return caps[:n]
