from __future__ import annotations

import unittest

from core.tools import Tool, ToolRegistry


class ToolTests(unittest.TestCase):
    def test_registry_registers_and_executes_tool(self) -> None:
        registry = ToolRegistry()
        registry.register(Tool("echo", "echo value", lambda value: value))

        self.assertIn("echo", registry.list())
        self.assertEqual(registry.execute("echo", "atlas"), "atlas")


if __name__ == "__main__":
    unittest.main()
