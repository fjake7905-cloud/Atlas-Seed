from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.memory import PersistentMemory


class MemoryTests(unittest.TestCase):
    def test_memory_persists_and_searches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = PersistentMemory(Path(tmp) / "memory.json")
            memory.add({"event": "atlas boot"})

            loaded = PersistentMemory(Path(tmp) / "memory.json")
            self.assertEqual(len(loaded.search("boot")), 1)


if __name__ == "__main__":
    unittest.main()
