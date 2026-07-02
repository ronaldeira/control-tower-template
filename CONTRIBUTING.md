# Contributing

Most people **fork and own** this template — adapt it freely to your setup.

If you'd like to contribute back:
1. Keep it **dependency-free** (Python 3.11+ stdlib only). No `pip install`.
2. Run the tests: `PYTHONPATH=scripts python3 -m pytest tests/ -q`.
3. Run the secret scanner: `bash scripts/check_secrets.sh .`.
4. Enable the hook: `git config core.hooksPath .githooks`.
5. Never commit `dashboard.html`, `*.generated.md`, or a real `control-tower.config.toml`.

Open an issue or PR with a clear description. Small, focused changes merge fastest.
