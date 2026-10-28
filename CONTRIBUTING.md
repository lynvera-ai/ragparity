# Contributing

Lynvera RAGParity is an experimental MVP. Open an issue to discuss substantial changes.
Keep contributions focused, include behavioral tests, and update documentation when
public contracts or CLI behavior change.

1. Create a branch from `main`.
2. Install Python 3.12+ and run `python -m pip install -e '.[dev,postgres]'`.
3. Run Ruff checks and formatting, `mypy src`, and unit tests with coverage using the
   commands in the README.
4. For database changes, run the Compose integration example and `pytest -m integration`.
5. Build with `python -m build` and check that the wheel installs in a clean environment.
6. Submit a pull request describing the behavior, tests, and relevant limitations.

Use explicit evidence contracts. Missing evidence must never silently become a pass.
Do not include secrets, customer data, generated reports, caches, or internal work notes.
The project uses Apache License 2.0; submitted contributions are offered under that license.
