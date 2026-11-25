"""CNN 공포·탐욕 지수(Fear & Greed Index) 알림.

미국 정규장 시작 1시간 뒤(뉴욕 10:30)에 하루 한 번 지수를 텔레그램으로 보냅니다.
데이터는 CNN 페이지(https://edition.cnn.com/markets/fear-and-greed)가 쓰는 JSON 을 그대로 읽습니다.
"""
from __future__ import annotations

import html
import logging
from datetime import datetime, time

import requests

log = logging.getLogger(__name__)

URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
HEADERS = {
    # 브라우저 헤더가 없으면 CNN 이 418 로 거절합니다.
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://edition.cnn.com/",
    "Origin": "https://edition.cnn.com",
}

SEND_AFTER = time(10, 30)   # 뉴욕 시간: 정규장(9:30) 시작 1시간 뒤
SEND_UNTIL = time(13, 0)    # GitHub 실행이 늦어져도 이때까지는 보냄

# (상한, 한국어, 이모지)
LEVELS = [
    (25, "극단적 공포", "😱"),
    (45, "공포", "😨"),
    (55, "중립", "😐"),
    (75, "탐욕", "😏"),
    (101, "극단적 탐욕", "🤑"),
]


def level(score: float) -> tuple[str, str]:
    for upper, name, emoji in LEVELS:
        if score < upper:
            return name, emoji
    return LEVELS[-1][1], LEVELS[-1][2]


def fetch() -> dict:
    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    fg = r.json()["fear_and_greed"]
    return {
        "score": float(fg["score"]),
        "previous_close": fg.get("previous_close"),
        "previous_1_week": fg.get("previous_1_week"),
        "previous_1_month": fg.get("previous_1_month"),
        "previous_1_year": fg.get("previous_1_year"),
        "timestamp": fg.get("timestamp"),
    }


def _bar(score: float, width: int = 10) -> str:
    filled = max(0, min(width, round(score / 100 * width)))
    return "■" * filled + "□" * (width - filled)


def _cmp(label: str, value, now: float) -> str | None:
    if value is None:
        return None
    v = float(value)
    diff = now - v
    arrow = "▲" if diff > 0.05 else ("▼" if diff < -0.05 else "－")
    name, _ = level(v)
    return f"• {label}: {v:.0f} ({name})  {arrow}{abs(diff):.0f}"


def format_message(data: dict, ny_now: datetime | None = None) -> str:
    e = html.escape
    s = data["score"]
    name, emoji = level(s)
    when = f" · 뉴욕 {ny_now.strftime('%m/%d %H:%M')}" if ny_now else ""
    lines = [
        f"{emoji} <b>CNN 공포·탐욕 지수</b>{e(when)}",
        "",
        f"<b>{s:.0f}</b> / 100  —  <b>{e(name)}</b>",
        _bar(s),
        "",
    ]
    for label, key in [("전일 종가", "previous_close"), ("1주 전", "previous_1_week"),
                       ("1개월 전", "previous_1_month"), ("1년 전", "previous_1_year")]:
        row = _cmp(label, data.get(key), s)
        if row:
            lines.append(e(row))
    lines.append("\n0~25 극단적 공포 · 25~45 공포 · 45~55 중립 · 55~75 탐욕 · 75~100 극단적 탐욕")
    lines.append('<a href="https://edition.cnn.com/markets/fear-and-greed">CNN에서 보기</a>')
    return "\n".join(lines)


def due(ny_now: datetime, last_sent: str | None) -> bool:
    """오늘(뉴욕 기준) 아직 안 보냈고, 평일 10:30~13:00 사이인가."""
    if ny_now.weekday() >= 5:
        return False
    if last_sent == ny_now.date().isoformat():
        return False
    return SEND_AFTER <= ny_now.time() <= SEND_UNTIL


def market_traded_today(ny_now: datetime) -> bool:
    """미국 휴장일 확인: 오늘 SPY 일봉이 있으면 장이 열린 날. 조회 실패 시 열린 것으로 간주."""
    try:
        import yfinance as yf
        df = yf.Ticker("SPY").history(period="5d", interval="1d")
        if df.empty:
            return True
        return df.index[-1].date() == ny_now.date()
    except Exception as ex:  # noqa: BLE001
        log.warning("휴장일 확인 실패(무시하고 진행): %s", ex)
        return True
