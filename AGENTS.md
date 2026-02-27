# Repository Guidelines

## Project Structure & Module Organization
- `main.py`: CLI/voice runtime entry point.
- `src/agent/`: LangGraph app construction and streaming helpers.
- `src/core/`: shared services (`speech_service.py`, `logs.py`) and provider clients in `src/core/clients/`.
- `src/tools/`: tool functions used by the agent (`add`, `subtract`, `multiply`, Gmail helpers in `src/tools/gmail/`).
- `tests/`: automated tests (currently minimal; add new tests here).
- `References/`: reference assets/examples; not part of core runtime.
- Root config files: `.env.example`, `requirements.txt`, `README.md`.

## Build, Test, and Development Commands
- `python3 -m venv venv && source venv/bin/activate`: create and activate local env.
- `venv/bin/pip install -r requirements.txt`: install dependencies.
- `venv/bin/python main.py`: run the voice agent locally.
- `venv/bin/python -m py_compile main.py src/agent/app.py src/core/clients/llm_client.py`: quick syntax smoke check.
- `venv/bin/python -m pytest`: run tests (after adding pytest-based tests/dependency).

## Coding Style & Naming Conventions
- Python style: 4-space indentation, explicit imports, type hints for public functions.
- Naming: `snake_case` for modules/functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- Keep modules focused (one responsibility per file) and preserve existing `src/core` vs `src/tools` separation.
- Follow existing error-handling style: fail fast with clear runtime messages.

## Testing Guidelines
- Use `pytest`; place tests in `tests/` with names like `test_<feature>.py`.
- Prefer deterministic tests; mock external provider calls (Azure/OpenAI/Claude/Ollama) rather than hitting live APIs.
- For behavior changes, include at least one regression test covering the modified path.
- No strict coverage gate is configured yet; prioritize meaningful tests over raw percentage.

## Commit & Pull Request Guidelines
- Current history favors short, imperative commit messages; `type: summary` is used (example: `feat: add provider auto-validation`).
- Recommended commit types: `feat`, `fix`, `docs`, `refactor`, `chore`.
- PRs should include:
  - concise change summary and motivation,
  - local verification commands run,
  - environment variable or config changes,
  - relevant terminal output/screenshots for behavior changes.

## Security & Configuration Tips
- Never commit secrets or OAuth artifacts: `.env`, `credentials.json`, `token.json`, `token.json.bak`.
- Keep real values local; commit placeholders only in `.env.example`.
- If credentials are exposed, rotate immediately and update docs/templates as needed.
