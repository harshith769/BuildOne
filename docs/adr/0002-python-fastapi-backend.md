# ADR-0002: Python + FastAPI backend

- **Status:** Accepted (architecture freeze requested by owner, 2026-09-28)
- **Date:** 2026-09-28
- **Decision makers:** @harshith769
- **Confidence:** To be set by owner on acceptance (proposer's view: High)

## Decision

**Use Python 3.14 with FastAPI, Pydantic v2, SQLAlchemy 2.1 (psycopg 3), and Alembic.** (Revised 2026-10-05 for the fresh repo: every dependency publishes Python 3.14 support on PyPI.) Python is the owner's strongest language and has the strongest ecosystem for the product's core work: document parsing, retrieval, LLM SDKs, and evaluation.

## Context

The owner is strongest in Python. The product's differentiating work (ingestion, rules, RAG, evaluation) is Python-native. The API needs async I/O for streaming AI responses and an OpenAPI contract for a generated frontend client.

## Candidates

### A. FastAPI
- Async-native, automatic OpenAPI schema (feeds the typed frontend client), Pydantic validation, streaming responses (SSE).
- Less batteries-included than Django: admin, auth, and migrations come from other libraries.

### B. Django (+ Django REST Framework / Django Ninja)
- Batteries included: ORM, migrations, admin panel.
- Async support is partial across the stack; admin is less relevant because rules are managed as code (ADR-0009).

## Evaluation

Not measured.

## Consequences

- Alembic migrations are reviewed as SQL before merge; autogenerate output is never applied unreviewed.
- Strict typing with `mypy --strict` in CI.
- Python 3.14 support was checked on PyPI on 2026-10-05 for every listed dependency; if a later dependency lags, pin 3.13.

## Re-evaluation Triggers

- A core dependency requires a different runtime.
- Measured CPU-bound hotspots in the rules engine that Python cannot meet (then optimise that module first, not the language).
