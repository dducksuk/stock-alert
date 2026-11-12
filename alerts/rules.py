"""config.yaml 의 rule 을 평가하는 엔진."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .data import MarketData
from .indicators import INDICATORS, LABELS

OPS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}
CROSS_OPS = {"crosses_below", "crosses_above"}


@dataclass
class Result:
    matched: bool
    details: list[str]          # 메시지에 쓸 "RSI(14, 1h) 25.3 < 27" 같은 문구
    error: str | None = None


def _spec_timeframes(spec: dict) -> set[str]:
    tfs = {spec.get("timeframe", "1d")}
    if isinstance(spec.get("value"), dict):
        tfs |= _spec_timeframes(spec["value"])
    return tfs


def timeframes_used(rules: list[dict]) -> set[str]:
    out: set[str] = set()
    for r in rules:
        for c in r.get("conditions", []):
            out |= _spec_timeframes(c)
    return out


def _series(spec: dict, ticker: str, md: MarketData):
    name = spec["indicator"]
    if name not in INDICATORS:
        raise ValueError(f"알 수 없는 indicator: {name} (가능: {list(INDICATORS)})")
    tf = spec.get("timeframe", "1d")
    df = md.get(ticker, tf)
    if df.empty:
        raise ValueError(f"{tf} 데이터 없음")
    params = {k: v for k, v in spec.items() if k not in ("indicator", "timeframe", "op", "value")}
    s = INDICATORS[name](df, **params).dropna()
    if len(s) < 2:
        raise ValueError(f"{name} 계산할 데이터 부족")
    return s


def _label(spec: dict) -> str:
    name = spec["indicator"]
    args = [str(spec["period"])] if "period" in spec else []
    args.append(spec.get("timeframe", "1d"))
    return f"{LABELS.get(name, name)}({', '.join(args)})"


def _fmt(x: float) -> str:
    return f"{x:,.2f}"


def evaluate_condition(cond: dict, ticker: str, md: MarketData) -> tuple[bool, str]:
    left = _series(cond, ticker, md)
    cur, prev = float(left.iloc[-1]), float(left.iloc[-2])

    val = cond["value"]
    if isinstance(val, dict):
        right = _series(val, ticker, md)
        r_cur = float(right.iloc[-1])
        same_tf = val.get("timeframe", "1d") == cond.get("timeframe", "1d")
        r_prev = float(right.iloc[-2]) if same_tf else r_cur
        r_text = f"{_label(val)} {_fmt(r_cur)}"
    else:
        r_cur = r_prev = float(val)
        r_text = _fmt(r_cur)

    op = cond["op"]
    if op in OPS:
        ok = OPS[op](cur, r_cur)
    elif op == "crosses_below":
        ok = prev >= r_prev and cur < r_cur
    elif op == "crosses_above":
        ok = prev <= r_prev and cur > r_cur
    else:
        raise ValueError(f"알 수 없는 op: {op}")

    if any(math.isnan(x) for x in (cur, r_cur)):
        ok = False
    return ok, f"{_label(cond)} {_fmt(cur)} {op} {r_text}"


def evaluate_rule(rule: dict, ticker: str, md: MarketData) -> Result:
    details = []
    try:
        for cond in rule["conditions"]:
            ok, text = evaluate_condition(cond, ticker, md)
            details.append(text)
            if not ok:
                return Result(False, details)
        return Result(True, details)
    except Exception as e:
        return Result(False, details, error=str(e))
