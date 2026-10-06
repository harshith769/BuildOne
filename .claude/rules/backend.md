---
paths:
  - "backend/**"
---
- Module layout: `api.py` (thin routes) → `service.py` (public interface + permission checks via `tenancy.service.require`) → `models.py` (private tables) → `jobs.py` (Procrastinate tasks).
- Routes under `/v1/orgs/{org_id}/...` must use the org dependency that verifies membership and sets the RLS context.
- Errors are raised as typed domain exceptions and rendered as RFC 9457 problem details by `app/platform/errors.py`.
- Every job takes IDs (not objects), sets the RLS context, and is safe to run twice.
- Use the injected `Clock`; never call `datetime.now()`/`date.today()` directly.
