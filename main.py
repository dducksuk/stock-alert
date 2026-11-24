"""주식 조건 알림 - 실행 진입점.

사용법
  python main.py               # 실제 실행 (조건 만족 시 텔레그램 발송)
  python main.py --dry-run     # 발송 없이 결과만 출력 (장 시간 무시)
  python main.py --test-telegram   # 텔레그램 연결 테스트 메시지 발송
  python main.py --targets     # 수동 목표가(매수/매도) 알림만 검사
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from alerts.data import MarketData, top_by_market_cap
from alerts.notify import format_alert, send_telegram
from alerts.rules import evaluate_rule, timeframes_used
from alerts.state import State

ROOT = Path(__file__).parent
NY = ZoneInfo("America/New_York")
log = logging.getLogger("alert")


def market_open(now: datetime) -> bool:
    ny = now.astimezone(NY)
    return ny.weekday() < 5 and time(9, 30) <= ny.time() <= time(16, 0)


def resolve_universe(cfg: dict, state: State, refresh: bool) -> list[tuple[str, int | None]]:
    """감시 종목 [(티커, 시총순위 or None)]. 시총 순위는 하루 1번만 새로 계산."""
    u = cfg["universe"]
    if u.get("mode") == "fixed":
        tickers = [(t, None) for t in u.get("fixed", [])]
    else:
        today = datetime.now(NY).date().isoformat()
        cached = state.data.get("universe", {})
        if refresh or cached.get("date") != today or not cached.get("tickers"):
            top = top_by_market_cap(u["candidates"], int(u.get("top_n", 15)))
            if top:
                state.data["universe"] = {
                    "date": today,
                    "tickers": [t for t, _ in top],
                    "market_caps": {t: c for t, c in top},
                }
            elif not cached.get("tickers"):
                raise RuntimeError("시가총액 조회 전부 실패 - 네트워크/티커를 확인하세요")
        tickers = [(t, i + 1) for i, t in enumerate(state.data["universe"]["tickers"])]
    have = {t for t, _ in tickers}
    tickers += [(t, None) for t in u.get("extra", []) if t not in have]
    return tickers


def run_targets(dry_run: bool, force: bool) -> int:
    """price_targets.json 의 매수/매도 목표가 도달 여부를 검사."""
    from alerts import targets as tg

    now = datetime.now(timezone.utc)
    if not (force or dry_run) and not market_open(now):
        log.info("미국 정규장 시간이 아니라 종료합니다. (뉴욕 %s)", now.astimezone(NY).strftime("%a %H:%M"))
        return 0

    targets = tg.normalize_targets(tg.load_json(ROOT / "price_targets.json", {}))
    if not targets:
        log.info("설정된 목표가가 없습니다.")
        return 0

    tstate = tg.load_json(ROOT / "target_state.json", {})
    prices = tg.fetch_prices(sorted(targets))
    signals = tg.evaluate(targets, prices, tstate)

    for t, tgt in targets.items():
        p = prices.get(t)
        price_txt = f"{p['price']:,.2f}" if p else "-"
        print(f"  {t:6} 현재가 {price_txt:>10}  매수 {tgt['buy'] or '-'}  매도 {tgt['sell'] or '-'}")

    missing = sorted(t for t in targets if t not in prices)
    sent = 0
    if not dry_run:
        for sig in signals:
            if send_telegram(tg.format_signal(sig)):
                sent += 1
        # 시세를 못 찾은 종목은 한 번만 안내
        notified = set(tstate.get("_missing", []))
        new_missing = [t for t in missing if t not in notified]
        if new_missing:
            send_telegram(tg.format_missing(new_missing))
        tstate["_missing"] = missing
        tg.save_json(ROOT / "target_state.json", tstate)
        # 웹앱에 보여줄 최신 시세
        tg.save_json(ROOT / "prices.json", {"updated": now.isoformat(), "prices": prices})
    else:
        for sig in signals:
            print(tg.format_signal(sig))
    log.info("목표가 검사 완료 - 신호 %d건, 발송 %d건", len(signals), sent)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--state", default=str(ROOT / "state.json"))
    ap.add_argument("--dry-run", action="store_true", help="발송/상태저장 없이 결과만 출력")
    ap.add_argument("--force", action="store_true", help="장 시간이 아니어도 실행")
    ap.add_argument("--refresh-universe", action="store_true", help="시총 순위 즉시 재계산")
    ap.add_argument("--test-telegram", action="store_true")
    ap.add_argument("--targets", action="store_true", help="수동 목표가(매수/매도) 알림만 검사")
    ap.add_argument("--demo-targets", action="store_true", help="목표가 알림 모양 미리보기 (테스트 메시지 발송)")
    ap.add_argument("--demo", metavar="TICKER:RSI", help="가상 RSI 값으로 알림 모양 미리보기 (예: SPCX:12)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.demo:
        ticker, value = args.demo.split(":")
        cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
        rule = next(r for r in cfg["rules"] if r["id"] == "rsi_oversold_1h")
        cond = rule["conditions"][0]
        tickers = State(args.state).data.get("universe", {}).get("tickers", [])
        rank = tickers.index(ticker) + 1 if ticker in tickers else None
        detail = f"RSI({cond['period']}, {cond['timeframe']}) {float(value):,.2f} {cond['op']} {float(cond['value']):,.2f}"
        text = "🧪 [테스트 알림 - 실제 신호 아님]\n\n" + format_alert(rule, ticker.upper(), [detail], rank)
        ok = send_telegram(text)
        print(text)
        return 0 if ok else 1

    if args.demo_targets:
        from alerts.targets import Signal, format_signal
        demos = [Signal("NVDA", "엔비디아", "buy", 119.80, 120.0), Signal("NVDA", "엔비디아", "sell", 151.10, 150.0)]
        ok = all(send_telegram("🧪 [테스트 알림 - 실제 신호 아님]\n\n" + format_signal(d)) for d in demos)
        print("발송 성공" if ok else "발송 실패")
        return 0 if ok else 1

    if args.targets:
        return run_targets(args.dry_run, args.force)

    if args.test_telegram:
        ok = send_telegram("✅ 주식 알림 봇 연결 테스트 성공!")
        print("발송 성공" if ok else "발송 실패")
        return 0 if ok else 1

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    if cfg.get("market_hours_only", True) and not (args.force or args.dry_run) and not market_open(now):
        log.info("미국 정규장 시간이 아니라 종료합니다. (뉴욕 %s)", now.astimezone(NY).strftime("%a %H:%M"))
        return 0

    state = State(args.state)
    universe = resolve_universe(cfg, state, args.refresh_universe)
    tickers = [t for t, _ in universe]
    log.info("감시 종목 %d개: %s", len(tickers), ", ".join(tickers))

    rules = [r for r in cfg.get("rules", []) if r.get("enabled", True)]
    # 규칙에 tickers 로 지정한 종목이 감시 목록에 없으면 추가
    for r in rules:
        for t in r.get("tickers", []):
            if t not in tickers:
                universe.append((t, None))
                tickers.append(t)

    md = MarketData()
    for tf in timeframes_used(rules):
        md.prefetch(tickers, tf)

    alerts = 0
    for rule in rules:
        only = rule.get("tickers")
        for ticker, rank in universe:
            if only and ticker not in only:
                continue
            res = evaluate_rule(rule, ticker, md)
            mark = "✅" if res.matched else ("⚠️" if res.error else "  ")
            print(f"{mark} [{rule['id']}] {ticker:6} " + (" | ".join(res.details) or "") +
                  (f"  (오류: {res.error})" if res.error else ""))
            if res.error:
                continue  # 데이터 오류 시 상태를 건드리지 않음
            if args.dry_run:
                continue
            if state.should_alert(rule["id"], ticker, res.matched, float(rule.get("cooldown_hours", 6)), now):
                if send_telegram(format_alert(rule, ticker, res.details, rank)):
                    alerts += 1

    if not args.dry_run:
        state.save()
    log.info("완료 - 발송한 알림 %d건", alerts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
