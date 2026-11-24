"""수동 목표가(매수/매도) 알림.

price_targets.json (웹앱이 저장)
  { "NVDA": {"name": "엔비디아", "buy": 120, "sell": 150, "updated": "..."} }

동작
  현재가 <= buy  → 매수 시점 알림
  현재가 >= sell → 매도 시점 알림
  한 번 알린 뒤에는 가격이 목표가 반대쪽으로 REARM_PCT% 이상 벗어났다가
  다시 도달해야 다시 알림. 목표가를 바꾸면 그 방향 알림 상태는 초기화.
"""
from __future__ import annotations

import html
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

REARM_PCT = 1.0


def load_json(path: str | Path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("%s 를 읽을 수 없어 비어 있는 것으로 처리합니다", p)
        return default


def save_json(path: str | Path, data) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _num(v) -> float | None:
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def normalize_targets(raw: dict) -> dict[str, dict]:
    """잘못된 값은 걸러내고 {TICKER: {name, buy, sell}} 로 정리."""
    out = {}
    for t, v in (raw or {}).items():
        if not isinstance(v, dict):
            continue
        buy, sell = _num(v.get("buy")), _num(v.get("sell"))
        if buy is None and sell is None:
            continue
        out[t.strip().upper()] = {"name": v.get("name") or t.upper(), "buy": buy, "sell": sell}
    return out


# ---------------------------------------------------------------- 시세

def fetch_prices(tickers: list[str]) -> dict[str, dict]:
    """정규장 기준 최신가(1분봉)와 전일 종가 대비 등락률."""
    if not tickers:
        return {}
    raw = yf.download(tickers, period="5d", interval="1m", group_by="ticker",
                      auto_adjust=False, prepost=False, progress=False, threads=True)
    out = {}
    for t in tickers:
        try:
            df = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
            close = df["Close"].dropna()
            if close.empty:
                raise ValueError("빈 데이터")
            last_ts = close.index[-1]
            price = float(close.iloc[-1])
            prev = close[close.index.date < last_ts.date()]
            change = (price / float(prev.iloc[-1]) - 1) * 100 if not prev.empty else None
            out[t] = {"price": round(price, 4),
                      "change_pct": None if change is None else round(change, 2),
                      "time": last_ts.isoformat()}
        except Exception as e:
            log.warning("%s 현재가 조회 실패: %s", t, e)
    return out


# ---------------------------------------------------------------- 판정

@dataclass
class Signal:
    ticker: str
    name: str
    side: str          # "buy" | "sell"
    price: float
    level: float


def evaluate(targets: dict[str, dict], prices: dict[str, dict], tstate: dict,
             rearm_pct: float = REARM_PCT) -> list[Signal]:
    """목표가 도달 신호 목록을 돌려주고 tstate(알림 상태)를 갱신."""
    signals: list[Signal] = []
    for gone in [t for t in tstate if t not in targets and not t.startswith("_")]:
        tstate.pop(gone)

    for t, tg in targets.items():
        st = tstate.setdefault(t, {})
        if t not in prices:
            continue
        price = prices[t]["price"]
        for side in ("buy", "sell"):
            level = tg.get(side)
            if level is None:
                st.pop(side, None)
                continue
            s = st.get(side)
            if not s or s.get("level") != level:
                s = st[side] = {"level": level, "fired": False}
            if side == "buy":
                hit = price <= level
                rearm = price > level * (1 + rearm_pct / 100)
            else:
                hit = price >= level
                rearm = price < level * (1 - rearm_pct / 100)
            if not s["fired"] and hit:
                s["fired"] = True
                signals.append(Signal(t, tg["name"], side, price, level))
            elif s["fired"] and rearm:
                s["fired"] = False
    return signals


def format_signal(sig: Signal) -> str:
    e = html.escape
    if sig.side == "buy":
        head, label = "🔴 <b>[매수 시점]</b>", "목표 매수가"
    else:
        head, label = "🔵 <b>[매도 시점]</b>", "목표 매도가"
    name = f"{sig.name} ({sig.ticker})" if sig.name and sig.name != sig.ticker else sig.ticker
    return "\n".join([
        f"{head} {e(name)}",
        "",
        f"• 현재가 <b>${sig.price:,.2f}</b>",
        f"• {label} ${sig.level:,.2f}",
        f'\n<a href="https://finance.yahoo.com/quote/{e(sig.ticker)}">차트 보기</a>',
    ])


def format_missing(tickers: list[str]) -> str:
    return ("⚠️ <b>목표가 종목 확인 필요</b>\n\n"
            f"다음 종목의 시세를 찾을 수 없어요: {html.escape(', '.join(tickers))}\n"
            "티커가 맞는지 앱에서 확인해 주세요.")
