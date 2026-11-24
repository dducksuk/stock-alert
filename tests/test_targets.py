"""목표가 알림 로직 테스트.  실행: python -m pytest -q"""
from alerts.targets import evaluate, normalize_targets


def P(price):
    return {"NVDA": {"price": price}}


def run(prices_seq, targets=None):
    targets = targets or {"NVDA": {"name": "엔비디아", "buy": 120.0, "sell": 150.0}}
    state, out = {}, []
    for p in prices_seq:
        out.append([(s.side, s.price) for s in evaluate(targets, P(p), state)])
    return out, state


def test_buy_fires_once_then_rearms():
    out, _ = run([130, 119, 118, 120.5, 119, 122, 119.5])
    # 119에서 알림, 118/120.5/119는 1% 회복 전이라 조용, 122(>121.2)에서 재무장, 119.5에서 다시 알림
    assert out == [[], [("buy", 119)], [], [], [], [], [("buy", 119.5)]]


def test_sell_fires_once_then_rearms():
    out, _ = run([140, 150, 152, 149, 148, 151])
    # 148 < 148.5 에서 재무장 → 151에서 다시 알림
    assert out == [[], [("sell", 150)], [], [], [], [("sell", 151)]]


def test_changing_level_resets():
    targets = {"NVDA": {"name": "N", "buy": 120.0, "sell": None}}
    state = {}
    assert [s.side for s in evaluate(targets, P(119), state)] == ["buy"]
    assert evaluate(targets, P(118), state) == []
    targets["NVDA"]["buy"] = 118.5
    assert [s.level for s in evaluate(targets, P(118), state)] == [118.5]


def test_removed_target_clears_state_but_keeps_meta():
    state = {"AAPL": {"buy": {"level": 1, "fired": True}}, "_missing": ["XYZ"]}
    evaluate({}, {}, state)
    assert state == {"_missing": ["XYZ"]}


def test_missing_price_is_skipped():
    targets = {"XYZ": {"name": "XYZ", "buy": 10.0, "sell": None}}
    assert evaluate(targets, {}, {}) == []


def test_normalize():
    raw = {"nvda": {"buy": "120", "sell": None}, "AAPL": {"buy": 0}, "TSLA": "x", "MSFT": {"sell": 500}}
    assert normalize_targets(raw) == {
        "NVDA": {"name": "NVDA", "buy": 120.0, "sell": None},
        "MSFT": {"name": "MSFT", "buy": None, "sell": 500.0},
    }
