# Intelligent Retail Analytics System (SIH26179) - Edge-AI POC

Edge-AI shopper analytics, inventory monitoring, and queue intelligence system.

## Dependency Management

`uv` is the primary dependency manager. `pyproject.toml` and `uv.lock` are the single source of truth. `requirements.txt` is maintained as a compatibility export.

### Setup with `uv`

```bash
# Create virtual environment and install all dependencies
uv sync --all-extras
```

### Setup with standard `pip` (compatibility)

```bash
pip install -r requirements.txt
```

## Running Tests

```bash
uv run pytest
```

## Linting & Type Checking

```bash
# Run Ruff linter and formatter check
uv run ruff check .
uv run ruff format --check .

# Run strict type checks with Mypy
uv run mypy --strict schemas.py tests/
```

## Pre-commit Hooks

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```
