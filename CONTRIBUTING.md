# Contributing

Eventful supports the Python versions declared in `pyproject.toml`. Create and
activate a virtual environment, then install the complete development toolchain:

```bash
python -m pip install -e '.[dev]'
```

Run the same quality workflow used by every CI Python version:

```bash
python scripts/check_quality.py
```

The workflow runs Ruff, mypy, the test suite with coverage, annotation-policy and
public-docstring checks, distribution builds, and the strict documentation build.
It stops at the first failure and recreates generated build directories, so reruns
do not validate stale artifacts. Every public module, class, function, and method
must explain its responsibility or boundary in its docstring.

Public claims must match implemented behavior.
