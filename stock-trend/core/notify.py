"""알림 채널 추상화.

기본 구현은 크리덴셜이 필요 없는 콘솔/파일 알림이다.
이메일·Slack 등은 시크릿(SMTP 계정, 토큰)이 필요하므로 확장점만 남겨둔다.
(README의 '알림 확장' 참고 — 실제 발송을 붙이려면 send_email/send_slack을 구현.)
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


def _data_dir() -> Path:
    base = os.environ.get("STOCK_TREND_DATA")
    if base:
        return Path(base)
    return Path(__file__).resolve().parent.parent / "data"


def alert_log_path() -> Path:
    return _data_dir() / "alerts.log"


def notify(message: str, to_console: bool = True, to_file: bool = True) -> str:
    """알림 한 건 전송. 기록된 타임스탬프 라인을 반환한다."""
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
    if to_console:
        print(line)
    if to_file:
        path = alert_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    return line


# --- 확장점 (시크릿 필요, 기본 미구현) -------------------------------------
def send_email(subject: str, body: str) -> None:  # pragma: no cover
    """SMTP 이메일 발송. 사용하려면 환경변수(SMTP_HOST/USER/PASS 등)로 구현하세요."""
    raise NotImplementedError("이메일 알림은 SMTP 설정이 필요합니다. README '알림 확장' 참고.")


def send_slack(text: str) -> None:  # pragma: no cover
    """Slack Webhook 발송. SLACK_WEBHOOK_URL 환경변수로 구현하세요."""
    raise NotImplementedError("Slack 알림은 Webhook URL이 필요합니다. README '알림 확장' 참고.")
