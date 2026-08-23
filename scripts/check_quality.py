"""Run the repository's required, dependency-free quality workflow."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (
    (sys.executable, "-m", "ruff", "check", "."),
    (sys.executable, "-m", "mypy", "src/eventful"),
    (sys.executable, "-m", "pytest", "--cov=eventful"),
    (sys.executable, "scripts/check_annotations.py"),
    (sys.executable, "scripts/check_docstrings.py"),
    (sys.executable, "-m", "build"),
    (sys.executable, "-m", "mkdocs", "build", "--strict"),
)


def main() -> None:
    """Run every check in CI order, stopping at the first failure."""
    for generated_directory in ("build", "dist", "site"):
        shutil.rmtree(ROOT / generated_directory, ignore_errors=True)

    for command in COMMANDS:
        print(f"\n==> {' '.join(command)}", flush=True)
        subprocess.run(command, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
