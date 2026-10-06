# BuildOne — Authentication, Sessions, and Tenancy

> **Status:** v1.0 (frozen for MVP build) · 2026-09-28 · Owner: @harshith769
> Decision record: [ADR-0007](adr/0007-identity-workos-sessions.md). Tables and RLS: [data-model.md §3–4](data-model.md#3-request-context-and-rls-frozen).

**What this document answers**
- How sign-in works end to end and what the backend trusts
- How sessions, cookies, and CSRF protection are configured
- Who can do what (role × action matrix) and where each check is enforced
- How tenant context reaches the database, and the rules for the calendar-feed exception

---

## 1. Sign-in flow (Authorization Code + PKCE via WorkOS AuthKit)

1. SPA navigates to `GET /v1/auth/login?return_to=<path>` → API creates `state` + PKCE verifier (stored in a short-lived signed cookie, 10 min) → redirects to AuthKit.
2. AuthKit authenticates (email one-time code/link or Google) → redirects to `GET /v1/auth/callback?code&state`.
3. API validates `state` (single use), exchanges code with PKCE verifier, receives the WorkOS user profile.
4. API upserts `identity.users` by `idp_user_id`. First sign-in → requires **18+ confirmation and terms/privacy acceptance** screen before any other endpoint works (403 `consent_required`).
5. API creates a session row and sets cookies; redirects to `return_to` (must be a relative path — open-redirect protection).

**Adapter seam:** `identity/providers/workos.py` implements `IdentityProvider`; `identity/providers/fake.py` is used in local dev and tests (CI never calls WorkOS). Fallback provider (direct Google OIDC) implements the same interface ([ADR-0011](adr/0011-portability-rules.md)).

## 2. Sessions and cookies (Frozen)

| Item | Value |
|---|---|
| Session cookie | `bo_session` = 32 random bytes (base64url); `HttpOnly; Secure; SameSite=Lax; Path=/; Domain=.<root-domain>` |
| Storage | Only SHA-256 hash in `identity.sessions.token_hash` |
| Idle timeout | 30 days sliding (extended at most once per hour to limit writes) |
| Absolute timeout | 90 days |
| Logout | Deletes the session row; clears cookies |
| Multiple sessions | Allowed; listed at `GET /v1/me/sessions`; revocable individually or all-but-current |
| Rotation | New session token on sign-in and after consent acceptance |

## 3. CSRF (Frozen)

- `SameSite=Lax` **plus** double-submit token: cookie `bo_csrf` (not HttpOnly, per-session random) must equal header `X-CSRF-Token` on `POST/PUT/PATCH/DELETE`.
- `Origin` header must match the allowlisted app origin on unsafe methods.
- CORS: allow only `https://app.<root-domain>` (and `http://localhost:5173` in dev) with credentials; never `*`.

## 4. Authorization model

RBAC per organisation + ownership checks + RLS.

| Action | owner | member | viewer |
|---|---|---|---|
| View org data (facts, obligations, explanations) | ✓ | ✓ | ✓ |
| Edit facts, confirm proposals, mark obligations done | ✓ | ✓ | — |
| Use Copilot | ✓ | ✓ | — |
| Upload personal document (Situation Check) | ✓ | ✓ | — |
| Invite members / change roles / remove members | ✓ | — | — |
| Export org data | ✓ | — | — |
| Delete organisation | ✓ | — | — |
| Launchpad → incorporation handoff | ✓ | — | — |

Permission checks are centralised in `tenancy/service.py` (`require(ctx, action)`), never scattered `if role ==` checks.

## 5. Enforcement layers

| Layer | Responsibility |
|---|---|
| Middleware | Resolve session → `user_id`; reject unauthenticated; reject `consent_required`; attach `request_id` |
| Org dependency (`/v1/orgs/{org_id}/…`) | Load membership for `(org_id, user_id)`; 404 if not a member (no existence leak); attach role |
| Service | `require(ctx, action)` per the matrix; ownership checks (e.g., documents) |
| Database | `SET LOCAL app.user_id/app.org_id` at transaction start; RLS policies ([data-model.md §3](data-model.md#3-request-context-and-rls-frozen)) |

The organisation always comes from the URL path validated against membership — **never from the request body**.

## 6. Invitations

`POST /v1/orgs/{org_id}/invitations` (owner) → email (or copyable link if email channel disabled) containing a single-use token (hash stored, 7-day expiry). Accept → must be signed in; if signed-in email differs from invited email, explicit confirmation required; membership created; token consumed.

## 7. Calendar feed capability URL

ICS subscriptions require a URL that calendar apps fetch without cookies. Controlled exception to "no tokens in URLs":
- `GET /v1/calendar/{token}.ics`, token = 32 random bytes, only the hash stored, per user, revocable/rotatable in settings.
- Read-only; returns only obligation title, due date, org name, and a link to the app (no facts, no documents).
- Rate-limited per token; `Cache-Control: private`; `Referrer-Policy: no-referrer` on the app to avoid leaking it.

## 8. Account and organisation deletion

- User deletion request → `status = 'deletion_pending'`, all sessions deleted; hard delete after 30 days by sweeper job (memberships cascade; last-owner organisations are deleted with them after warning).
- Organisation deletion (owner) → `status = 'deletion_pending'`, immediately invisible via `tenancy.is_member`; hard delete after 30 days including R2 objects.

## 9. Admin access (MVP)

No impersonation. Operator support uses read-only SQL through `app_readonly` views that exclude personal content; every admin query session is logged. Cross-tenant operations are system jobs only ([data-model.md §6](data-model.md#6-cross-org-system-functions-worker-only)).
