from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.base_agent import BaseAgent
from runtime.agent_loop import AgentLoop
from runtime.executor import Executor
from runtime.planner import Planner
from runtime.state import AppState


class WritePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state = AppState.load(root=Path(self.tmpdir.name), auto_confirm=True)
        self.agent = BaseAgent(state=self.state, planner=Planner(), executor=Executor(self.state))
        self.loop = AgentLoop(self.agent)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _read(self, fname: str) -> str:
        return (Path(self.tmpdir.name) / "workspace" / fname).read_text(encoding="utf-8")

    def test_single_quotes_preserved(self) -> None:
        self.loop.step("create hello.py")
        self.loop.step("write hello.py print('hello-atlas')")
        content = self._read("hello.py")
        self.assertEqual(content, "print('hello-atlas')")
        run = self.loop.step("run hello.py")
        self.assertIn("hello-atlas", run.output_text)
        self.assertIn("Ran:", run.output_text)

    def test_double_quotes_preserved(self) -> None:
        self.loop.step("create test.py")
        self.loop.step('write test.py print("hello")')
        content = self._read("test.py")
        self.assertIn('print("hello")', content)
        run = self.loop.step("run test.py")
        self.assertIn("hello", run.output_text)

    def test_nested_quotes_double_outer_single_inner(self) -> None:
        self.loop.step('write nested.txt "nested \'quotes\' inside"')
        content = self._read("nested.txt")
        self.assertEqual(content, "nested 'quotes' inside")

    def test_nested_quotes_single_outer_double_inner(self) -> None:
        self.loop.step("write nested2.txt 'nested \"quotes\" inside'")
        content = self._read("nested2.txt")
        self.assertEqual(content, 'nested "quotes" inside')

    def test_multiline_writes(self) -> None:
        self.loop.step('write multi.txt "line1\nline2\nline3"')
        content = self._read("multi.txt")
        self.assertEqual(content, "line1\nline2\nline3")
        self.assertEqual(content.count("\n"), 2)

    def test_multiline_with_escapes(self) -> None:
        self.loop.step('write esc.txt "a\\tb\\nc"')
        content = self._read("esc.txt")
        self.assertEqual(content, "a\tb\nc")

    def test_unicode_preserved(self) -> None:
        self.loop.step('write unicode.txt "café naïve résumé"')
        content = self._read("unicode.txt")
        self.assertIn("café", content)
        self.assertIn("naïve", content)
        self.assertIn("résumé", content)

    def test_unicode_emoji(self) -> None:
        self.loop.step('write emoji.txt "hello 🌍 🚀"')
        content = self._read("emoji.txt")
        self.assertIn("🌍", content)
        self.assertIn("🚀", content)

    def test_escaped_characters(self) -> None:
        self.loop.step('write esc2.txt "tab\\there\\nnewline"')
        content = self._read("esc2.txt")
        self.assertIn("\t", content)
        self.assertIn("\n", content)
        self.assertIn("tab", content)

    def test_outer_quotes_stripped_inner_preserved(self) -> None:
        self.loop.step('write notes.txt "hello world"')
        content = self._read("notes.txt")
        self.assertEqual(content, "hello world")
        # Ensure outer quotes not in file
        self.assertNotIn('"hello world"', content)

    def test_file_with_spaces(self) -> None:
        self.loop.step('write "my file.txt" "content with spaces"')
        content = self._read("my file.txt")
        self.assertEqual(content, "content with spaces")

    def test_exact_user_text_preserved(self) -> None:
        # Exact text after filename should be preserved including embedded quotes
        self.loop.step("write exact.txt print('exact text')")
        content = self._read("exact.txt")
        self.assertEqual(content, "print('exact text')")

    def test_append_preserves(self) -> None:
        self.loop.step("create log.txt")
        self.loop.step('write log.txt "first"')
        self.loop.step('append log.txt "second"')
        content = self._read("log.txt")
        self.assertIn("first", content)
        self.assertIn("second", content)

    def test_append_with_quotes(self) -> None:
        self.loop.step("create log2.txt")
        self.loop.step('write log2.txt "line1"')
        self.loop.step('append log2.txt "line2 with \'quotes\'"')
        content = self._read("log2.txt")
        self.assertIn("line1", content)
        self.assertIn("line2 with 'quotes'", content)


if __name__ == "__main__":
    unittest.main()
