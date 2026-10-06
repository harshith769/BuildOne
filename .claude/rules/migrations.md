---
paths:
  - "backend/migrations/**"
---
- One logical change per revision; write explicit SQL via `op.execute` or reviewed `op.*` calls.
- New tenant table: `org_id uuid NOT NULL`, FK, index, `ENABLE` + `FORCE ROW LEVEL SECURITY`, `tenant_isolation` policy — all in the same revision.
- Every FK column gets an index in the same revision. Enums are `CHECK (col IN (...))`.
- Never `CREATE EXTENSION` here; never drop/rename in one step (expand → migrate → contract).
