"""
tests/test_no_ai_in_app.py — the local AI is out of the app (V3.22, RM-3;
docs/homeowner/03-what-goes.md, the owner's G1 and Y1).

A homeowner cannot install and run a local language model, and when it was
missing they saw raw error text and a brief that was silently ignored (R3).
The app now always builds with the rule-based generator. The command line and
the MCP server keep ``generate_design``, whose prompts and errors live in
``llm_design.py``; no other string in ``src/`` says "AI" as a word or
"Ollama". Docstrings are read by developers, not homeowners, and are left out.
"""

import ast
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SRC = Path(__file__).resolve().parent.parent / "src"
ALLOWED = {"llm_design.py", "cli.py", "mcp_server.py"}


def strings(path: Path):
    """The string constants of one module, docstrings left out."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value,
                                                          ast.Constant):
                docs.add(id(first.value))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docs):
            yield node.lineno, node.value


class TheAppSaysNoAI(unittest.TestCase):

    def test_no_string_names_the_ai(self):
        found = []
        for path in sorted(_SRC.rglob("*.py")):
            name = str(path.relative_to(_SRC))
            if name in ALLOWED:
                continue
            for line, text in strings(path):
                # "AI" as a word is case-sensitive; Ollama in any case.
                if re.search(r"\bAI\b", text) or re.search("ollama", text, re.I):
                    found.append(f"{name}:{line}: {text[:70]!r}")
        self.assertEqual(found, [], "the AI left the app in V3.22 (RM-3)")

    def test_the_app_builds_with_the_rule_based_generator(self):
        src = (_SRC / "generate_worker.py").read_text(encoding="utf-8")
        self.assertIn("generate_design_offline(", src)
        self.assertNotRegex(src, r"\bgenerate_design\(")
        self.assertNotIn("LLMError", src)

    def test_the_command_line_and_mcp_keep_it(self):
        for name in ("cli.py", "mcp_server.py"):
            self.assertIn("generate_design",
                          (_SRC / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
