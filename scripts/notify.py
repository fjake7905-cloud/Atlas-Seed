#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from runtime.notifications import Notifier, NotificationConfig

def main() -> int:
    parser = argparse.ArgumentParser(description="Atlas Notification Tester")
    parser.add_argument("--type", dest="event_type", default="TASK_FINISHED")
    parser.add_argument("--status", default="Test")
    parser.add_argument("--completed", default="Test")
    parser.add_argument("--next", dest="next_step", default="Next")
    parser.add_argument("--action", dest="action_required", default="None")
    parser.add_argument("--test-fallback", action="store_true")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    if args.test_fallback:
        config = NotificationConfig(telegram_token=None, telegram_chat_id=None, email_host=None)
    else:
        config = NotificationConfig()
    notifier = Notifier(config=config, repo_root=repo_root)
    print(f"Config: Telegram={config.telegram_configured}, Email={config.email_configured}")
    result = notifier.notify(args.event_type, args.status, args.completed, args.next_step, args.action_required)
    import json
    print(json.dumps({k: str(v) for k, v in result.items() if k != "message"}, indent=2, ensure_ascii=False)[:2000])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
