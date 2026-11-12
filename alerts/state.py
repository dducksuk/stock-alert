"""중복 알림 방지를 위한 상태 저장 (state.json)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


class State:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data = {"active": {}, "last_alert": {}, "universe": {}}
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text()))
            except json.JSONDecodeError:
                pass

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n")

    @staticmethod
    def _key(rule_id: str, ticker: str) -> str:
        return f"{rule_id}|{ticker}"

    def should_alert(self, rule_id: str, ticker: str, matched: bool, cooldown_hours: float,
                     now: datetime | None = None) -> bool:
        """조건 '진입' 시점에만 True. 조건을 벗어나면 다시 알림 가능 상태로 리셋."""
        now = now or datetime.now(timezone.utc)
        key = self._key(rule_id, ticker)
        if not matched:
            self.data["active"].pop(key, None)
            return False
        if key in self.data["active"]:
            return False                       # 이미 알린 상태가 계속되는 중
        self.data["active"][key] = now.isoformat()
        last = self.data["last_alert"].get(key)
        if last and now - datetime.fromisoformat(last) < timedelta(hours=cooldown_hours):
            return False                       # 조건 들락날락 → 쿨다운 중
        self.data["last_alert"][key] = now.isoformat()
        return True
