"""
Atlas-Seed Notification System
Provides Telegram, Email, and file fallback notifications for workspace events.

Event types:
- TASK_FINISHED
- INPUT_REQUIRED
- BLOCKING_ERROR

Config sources (priority: env vars > file > default):
  Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, EMAIL_SMTP_*, NOTIFICATIONS_ENABLED, ATLAS_ROOT
  File: .atlas/notification_config.json

Fallback chain: Telegram -> Email -> File log (.atlas/notifications.log) + PROGRESS_LOG.md
"""

from __future__ import annotations

import json
import os
import smtplib
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any
from urllib import request as urllib_request
from urllib.error import URLError


def _load_file_config(log_dir: Path) -> dict[str, Any]:
    cfg_path = log_dir / "notification_config.json"
    if not cfg_path.exists():
        alt = Path.cwd() / ".atlas" / "notification_config.json"
        if alt.exists():
            cfg_path = alt
        else:
            return {}
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


@dataclass
class NotificationConfig:
    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    email_host: str | None = None
    email_port: int = 587
    email_user: str | None = None
    email_pass: str | None = None
    email_from: str | None = None
    email_to: str | None = None
    enabled: bool = True
    log_dir: Path = field(default_factory=lambda: Path.cwd() / ".atlas")

    def __post_init__(self):
        env_root = os.getenv("ATLAS_ROOT")
        if not self.log_dir.is_absolute():
            base = Path(env_root).resolve() if env_root else Path.cwd().resolve()
            if str(self.log_dir) == ".atlas" or self.log_dir.name == ".atlas":
                self.log_dir = base / ".atlas"
            else:
                self.log_dir = (base / self.log_dir).resolve()
        self.log_dir = self.log_dir.resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)

        file_cfg = _load_file_config(self.log_dir)

        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN") or file_cfg.get("telegram_bot_token") or self.telegram_token
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID") or file_cfg.get("telegram_chat_id") or self.telegram_chat_id
        self.email_host = os.getenv("EMAIL_SMTP_HOST") or file_cfg.get("email_smtp_host") or self.email_host
        env_port = os.getenv("EMAIL_SMTP_PORT") or file_cfg.get("email_smtp_port")
        if env_port:
            try:
                self.email_port = int(env_port)
            except Exception:
                pass
        self.email_user = os.getenv("EMAIL_SMTP_USER") or file_cfg.get("email_smtp_user") or self.email_user
        self.email_pass = os.getenv("EMAIL_SMTP_PASS") or file_cfg.get("email_smtp_pass") or self.email_pass
        self.email_from = os.getenv("EMAIL_FROM") or file_cfg.get("email_from") or self.email_from or self.email_user
        self.email_to = os.getenv("EMAIL_TO") or file_cfg.get("email_to") or self.email_to

        env_enabled = os.getenv("NOTIFICATIONS_ENABLED")
        file_enabled = file_cfg.get("notifications_enabled")
        if env_enabled is not None:
            self.enabled = env_enabled.lower() not in {"0", "false", "no"}
        elif file_enabled is not None:
            self.enabled = bool(file_enabled)

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_token and self.telegram_chat_id)

    @property
    def email_configured(self) -> bool:
        return bool(self.email_host and self.email_from and self.email_to)

    def is_telegram_api_reachable(self, timeout: int = 5) -> tuple[bool, str]:
        try:
            req = urllib_request.Request("https://api.telegram.org", method="GET")
            with urllib_request.urlopen(req, timeout=timeout) as resp:
                return True, f"Reachable (HTTP {resp.status})"
        except URLError as e:
            err_str = str(e)
            if "404" in err_str or "405" in err_str or "Unauthorized" in err_str or "Not Found" in err_str:
                return True, f"Reachable - {err_str}"
            if "timed out" in err_str.lower() or "name or service not known" in err_str.lower() or "connection" in err_str.lower():
                return False, f"Not reachable: {e}"
            return True, f"Probably reachable: {e}"
        except Exception as e:
            return False, f"Not reachable: {e}"


class Notifier:
    def __init__(self, config: NotificationConfig | None = None, repo_root: Path | None = None):
        self.config = config or NotificationConfig()
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd().resolve()
        self.log_dir = self.config.log_dir
        if not self.log_dir.is_absolute():
            self.log_dir = (self.repo_root / self.log_dir).resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.notification_log = self.log_dir / "notifications.log"
        self.progress_log = self.repo_root / "PROGRESS_LOG.md"

    def _format_message(self, event_type: str, status: str, completed: str, next_step: str, action_required: str) -> str:
        ts = datetime.now(timezone.utc).isoformat()
        lines = [
            f"🤖 Atlas-Seed Notification - {event_type}",
            f"⏰ Time: {ts}",
            f"📍 Repo: {self.repo_root}",
            f"📊 Status: {status}",
            "",
            f"✅ Completed:\n{completed.strip() or 'N/A'}",
            "",
            f"➡️ Next Step:\n{next_step.strip() or 'N/A'}",
        ]
        if action_required and action_required.strip().lower() not in {"none", "n/a", "-"}:
            lines.extend(["", f"⚠️ Action Required:\n{action_required.strip()}"])
        lines.extend(["", f"---", f"Event: {event_type} | {ts}"])
        return "\n".join(lines)

    def _format_telegram(self, message: str) -> str:
        return message[:4000]

    def send_telegram(self, message: str) -> tuple[bool, str]:
        if not self.config.telegram_configured:
            return False, "Telegram not configured (missing BOT_TOKEN or CHAT_ID)"
        reachable, reach_msg = self.config.is_telegram_api_reachable()
        if not reachable:
            return False, f"Telegram API not reachable ({reach_msg})"
        url = f"https://api.telegram.org/bot{self.config.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.config.telegram_chat_id,
            "text": self._format_telegram(message),
            "disable_web_page_preview": True,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib_request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8")
                j = json.loads(body)
                if j.get("ok"):
                    return True, "Telegram sent"
                else:
                    return False, f"Telegram API error: {body}"
        except URLError as e:
            return False, f"Telegram URL error: {e}"
        except Exception as e:
            return False, f"Telegram exception: {e}"

    def send_email(self, subject: str, message: str) -> tuple[bool, str]:
        if not self.config.email_configured:
            return False, "Email not configured"
        try:
            msg = MIMEMultipart()
            msg["From"] = self.config.email_from
            msg["To"] = self.config.email_to
            msg["Subject"] = subject[:200]
            msg.attach(MIMEText(message, "plain", "utf-8"))
            server = smtplib.SMTP(self.config.email_host, self.config.email_port, timeout=10)
            try:
                server.starttls()
            except Exception:
                pass
            if self.config.email_user and self.config.email_pass:
                server.login(self.config.email_user, self.config.email_pass)
            server.sendmail(self.config.email_from, [self.config.email_to], msg.as_string())
            server.quit()
            return True, "Email sent"
        except Exception as e:
            return False, f"Email failed: {e}"

    def log_fallback(self, message: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        entry = f"\n[{ts}] {message}\n{'-'*80}\n"
        try:
            with self.notification_log.open("a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            print(f"Failed to write notification log: {e}", file=sys.stderr)

    def notify(self, event_type: str, status: str, completed_work: str = "", next_planned_step: str = "", action_required: str = "", subject: str | None = None) -> dict[str, Any]:
        if not self.config.enabled:
            return {"enabled": False}
        message = self._format_message(event_type, status, completed_work, next_planned_step, action_required)
        subj = subject or f"[Atlas-Seed] {event_type} - {status}"
        results: dict[str, Any] = {"event_type": event_type, "message": message}
        tg_ok, tg_msg = self.send_telegram(message)
        results["telegram"] = (tg_ok, tg_msg)
        if tg_ok:
            results["delivered_via"] = "telegram"
            self.log_fallback(f"[DELIVERED via Telegram] {event_type}\n{message}")
            return results
        em_ok, em_msg = self.send_email(subj, message)
        results["email"] = (em_ok, em_msg)
        if em_ok:
            results["delivered_via"] = "email"
            self.log_fallback(f"[DELIVERED via Email] {event_type}\n{message}")
            return results
        self.log_fallback(f"[FALLBACK LOG] {event_type} | Telegram: {tg_msg} | Email: {em_msg}\n{message}")
        results["fallback"] = True
        results["delivered_via"] = "file"
        results["details"] = {"telegram_error": tg_msg, "email_error": em_msg}
        return results

    def task_finished(self, status: str, completed: str, next_step: str, action_required: str = "None") -> dict[str, Any]:
        return self.notify("TASK_FINISHED", status, completed, next_step, action_required)

    def input_required(self, status: str, completed: str, next_step: str, action_required: str) -> dict[str, Any]:
        return self.notify("INPUT_REQUIRED", status, completed, next_step, action_required)

    def blocking_error(self, status: str, completed: str, next_step: str, action_required: str) -> dict[str, Any]:
        return self.notify("BLOCKING_ERROR", status, completed, next_step, action_required)


_default_notifier: Notifier | None = None

def get_notifier(repo_root: Path | None = None, config: NotificationConfig | None = None) -> Notifier:
    global _default_notifier
    if _default_notifier is None or repo_root is not None or config is not None:
        _default_notifier = Notifier(config=config, repo_root=repo_root)
    return _default_notifier
