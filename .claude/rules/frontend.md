---
paths:
  - "frontend/**"
---
- Use only the generated API client (`src/api/`); never hand-write fetch calls or types for API data.
- Every data view handles loading, empty, error (show request ID), no-permission, and AI `limit_reached`/`ai_unavailable` states.
- Show the disclaimer component on every guidance screen. Format dates `DD MMM YYYY`, money with Indian digit grouping.
- Mutations send `X-CSRF-Token` from the `bo_csrf` cookie and an `Idempotency-Key` where the API requires it.
