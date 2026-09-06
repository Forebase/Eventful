"""Detect malformed tracked-work annotations."""
from __future__ import annotations
import re
from pathlib import Path

ALLOWED = "TODO|FIXME|CHORE|PERF|SECURITY|COMPAT|DOCS"
annotation = re.compile(rf"\b({ALLOWED})\b:(.*)")
forbidden = re.compile(r"\b(TBD|XXX)\b")
failed: list[str] = []
roots = [Path("src"), Path("tests"), Path("docs"), Path(".github")]
paths = [Path("README.md"), Path("CHANGELOG.md"), Path("pyproject.toml")]
paths.extend(path for root in roots for path in root.rglob("*") if path.is_file())
for path in paths:
    if path.resolve() == Path(__file__).resolve():
        continue
    if path.suffix not in {'.py', '.md', '.toml', '.yml', '.yaml'}:
        continue
    for lineno, line in enumerate(path.read_text(errors='ignore').splitlines(), 1):
        if forbidden.search(line):
            failed.append(f"{path}:{lineno}: forbidden annotation")
        match = annotation.search(line)
        if match and 'Issue:' not in match.group(2):
            failed.append(f"{path}:{lineno}: annotation missing issue link")
if failed:
    raise SystemExit('\n'.join(failed))
