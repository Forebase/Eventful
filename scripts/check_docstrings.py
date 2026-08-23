"""Require responsibility documentation at every public source boundary."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def public_definitions(tree: ast.Module) -> list[ast.AST]:
    """Return modules, classes, functions, and public methods requiring docs."""
    definitions: list[ast.AST] = [tree]
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                definitions.append(node)
        if isinstance(node, ast.ClassDef):
            definitions.extend(
                child
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not child.name.startswith("_")
            )
    return definitions


def main() -> None:
    """Fail with source locations for undocumented public definitions."""
    failures: list[str] = []
    for path in sorted((ROOT / "src" / "eventful").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in public_definitions(tree):
            if ast.get_docstring(node) is None:
                name = getattr(node, "name", "<module>")
                line = getattr(node, "lineno", 1)
                failures.append(f"{path.relative_to(ROOT)}:{line}: {name}")
    if failures:
        raise SystemExit("Missing public docstrings:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
