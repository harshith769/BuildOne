# BuildOne — API Conventions

> **Status:** v1.0 (frozen for MVP build) · 2026-09-28 · Owner: @harshith769
> The OpenAPI document is generated from code (FastAPI) at `/v1/openapi.json`; the frontend client is generated from it. This file defines the rules the code must follow.

**What this document answers**
- URL structure, versioning, and naming
- Request/response formats, errors, pagination, idempotency, streaming
- How the frontend client stays in sync with the API

---

## 1. Structure

- Base URL `https://api.<root-domain>/v1`. Breaking changes → `/v2` (none planned for MVP).
- Org-scoped resources: `/v1/orgs/{org_id}/<collection>[/{id}]`. User-scoped: `/v1/me/...`. Auth: `/v1/auth/...`. Public: `/v1/public/...` (marketing free tools).
- Collections plural kebab-case (`/obligations`, `/fact-proposals`); actions as sub-resources with POST (`/obligations/{id}/complete`).
- JSON fields `snake_case`. IDs are UUID strings. Instants ISO 8601 UTC (`2026-10-01T04:30:00Z`); legal dates `YYYY-MM-DD`; money as integer paise with `_paise` suffix.

## 2. Errors (RFC 9457 problem details)

```json
{"type":"https://<root-domain>/problems/quota-exceeded","title":"Daily limit reached","status":429,
 "code":"quota_exceeded","detail":"Copilot daily limit reached — try tomorrow","request_id":"01J…"}
```

| Status | When |
|---|---|
| 400 `validation_error` | Schema validation (with `errors[]` of `{field, message}`) |
| 401 `unauthenticated` | No/expired session |
| 403 `forbidden` / `consent_required` | Role lacks permission / consent pending |
| 404 `not_found` | Missing **or not a member** (no existence leak) |
| 409 `conflict` / `idempotency_key_conflict` | State conflict / key reused with different body |
| 422 `unprocessable` | Semantically invalid (e.g., fact value type mismatch) |
| 429 `rate_limited` / `quota_exceeded` | Rate limit / AI quota |
| 503 `ai_unavailable` | Only for AI-only endpoints; core endpoints never return this |

## 3. Pagination

Cursor-based: `?limit=50&cursor=<opaque>`; `limit` max 200. Response: `{"items":[…],"next_cursor":"…"|null}`. Cursor = base64url of the last item's sort key + id.

## 4. Idempotency

`Idempotency-Key` header (UUID) **required** on: create invitation, upload-URL creation, Copilot message, organisation creation, incorporation handoff, data export request. Stored in `platform.idempotency_keys` for 24 h, same transaction as the business write; same key + different body → 409.

## 5. Streaming (Copilot)

`POST /v1/orgs/{org_id}/copilot/conversations/{id}/messages` with `Accept: text/event-stream` returns SSE events:
`route` → `token` (repeated) → `citation` (repeated) → `done` `{message_id}`; or `error` `{code}`. Sentences failing verification are removed before `done`; the client renders the final message from `done` payload, streaming text is provisional.

## 6. Files

Uploads: `POST …/documents/upload-url` → `{upload_url, document_id}` (pre-signed PUT to R2, 15 min, content-type and max-size bound) → client PUTs → `POST …/documents/{id}/process`. Downloads via pre-signed GET (15 min). Files never pass through the API process.

## 7. Client generation

`make openapi` writes `frontend/app/src/api/openapi.json` and regenerates types with `openapi-typescript`. CI fails if the committed schema differs from the generated one (drift check).

## 8. Health

`GET /healthz` (process alive) · `GET /readyz` (DB reachable, migrations at head, queue lag < 5 min). Both unauthenticated, no data.
