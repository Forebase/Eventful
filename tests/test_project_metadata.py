from pathlib import Path
import tomllib


def test_dev_extra_includes_docs_build_tooling() -> None:
    """CI installs the dev extra before running MkDocs."""
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]

    assert any(dependency.startswith("mkdocs") for dependency in dev_dependencies)
