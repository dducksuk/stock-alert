"""텔레그램 발송."""
from __future__ import annotations

import html
import logging
import os

import requests

log = logging.getLogger(__name__)


def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 환경변수가 없습니다.")
        return False
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
              "disable_web_page_preview": True},
        timeout=15,
    )
    if not r.ok:
        log.error("텔레그램 발송 실패: %s %s", r.status_code, r.text)
    return r.ok


def format_alert(rule: dict, ticker: str, details: list[str], rank: int | None) -> str:
    e = html.escape
    rank_txt = f" (시총 {rank}위)" if rank else ""
    lines = [
        f"🔔 <b>{e(rule.get('name', rule['id']))}</b>",
        f"<b>{e(ticker)}</b>{e(rank_txt)}",
        "",
        *[f"• {e(d)}" for d in details],
    ]
    if rule.get("memo"):
        lines += ["", f"💡 {e(rule['memo'])}"]
    lines.append(f'\n<a href="https://finance.yahoo.com/quote/{e(ticker)}">차트 보기</a>')
    return "\n".join(lines)
