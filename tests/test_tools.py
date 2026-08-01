from __future__ import annotations

import unittest

from core.tools import Tool, ToolRegistry


class ToolTests(unittest.TestCase):
    def test_registry_registers_and_executes_tool(self) -> None:
        registry = ToolRegistry()
        # New API: handler receives List[str], consistent with executor
        registry.register(Tool("echo", "echo value", lambda args: args[0] if args else ""))

        self.assertIn("echo", registry.list())
        self.assertEqual(registry.execute("echo", ["atlas"]), "atlas")

    def test_registry_describe(self) -> None:
        registry = ToolRegistry()
        registry.register(Tool("test", "test description", lambda args: "ok"))
        self.assertEqual(registry.describe("test"), "test description")
        self.assertIsNone(registry.describe("nonexistent"))


if __name__ == "__main__":
    unittest.main()
