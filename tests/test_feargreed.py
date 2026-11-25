"""공포·탐욕 지수 알림 테스트.  실행: python -m pytest -q"""
from datetime import datetime
from zoneinfo import ZoneInfo

from alerts.feargreed import due, format_message, level

NY = ZoneInfo("America/New_York")


def ny(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=NY)


def test_levels():
    assert level(10)[0] == "극단적 공포"
    assert level(25)[0] == "공포"
    assert level(50)[0] == "중립"
    assert level(60)[0] == "탐욕"
    assert level(90)[0] == "극단적 탐욕"
    assert level(100)[0] == "극단적 탐욕"


def test_due_window_and_once_per_day():
    # 2026-11-25 는 수요일
    assert not due(ny(2026, 11, 25, 10, 29), None)
    assert due(ny(2026, 11, 25, 10, 30), None)
    assert due(ny(2026, 11, 25, 11, 40), None)          # 실행이 늦어져도 보냄
    assert not due(ny(2026, 11, 25, 13, 5), None)
    assert not due(ny(2026, 11, 25, 10, 40), "2026-11-25")  # 오늘 이미 보냄
    assert due(ny(2026, 11, 26, 10, 40), "2026-11-25")
    assert not due(ny(2026, 11, 28, 10, 40), None)      # 토요일


def test_format_message():
    text = format_message({"score": 38.4, "previous_close": 42.1, "previous_1_week": 30,
                           "previous_1_month": 55, "previous_1_year": 70})
    assert "38" in text and "공포" in text
    assert "전일 종가: 42 (공포)  ▼4" in text
    assert "1주 전: 30 (공포)  ▲8" in text
