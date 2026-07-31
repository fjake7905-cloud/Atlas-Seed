from __future__ import annotations

import json
from pathlib import Path
import sys


MANIFEST = Path("atlas_manifest.json")


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    missing = [
        item for item in data["required_components"]
        if not Path(item).exists()
    ]

    if missing:
        print("Atlas verification failed")
        for item in missing:
            print(f"missing: {item}")
        return 1

    print("Atlas change guard: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
