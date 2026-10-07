# BuildOne — Authentication, Sessions, and Tenancy

> **Status:** v1.2 (frozen for MVP build) · 2026-10-06 (M3: grantee access level, invitation token flow, ADR-0013) · Owner: @harshith769
> Decision record: [ADR-0007](adr/0007-identity-workos-sessions.md). Tables and RLS: [data-model.md §3–4](data-model.md#3-request-context-and-rls-frozen).

**What this document answers**
- How sign-in works end to end and what the backend trusts
- How sessions, cookies, and CSRF protection are configured
- Who can do what (role × action matrix) and where each check is enforced
- How tenant context reaches the database, and the rules for the calendar-feed exception

---

## 1. Sign-in flow (Authorization Code + PKCE via WorkOS AuthKit)

1. SPA navigates to `GET /v1/auth/login?return_to=<path>` → API validates `return_to` (a relative path; anything else is 400 — open-redirect protection), creates `state` + PKCE verifier (stored in the short-lived signed cookie `bo_login`, 10 min, `Path=/v1/auth`) → redirects to AuthKit.
2. AuthKit authenticates (email one-time code/link or Google) → redirects to `GET /v1/auth/callback?code&state`.
3. API validates `state` against `bo_login` and clears that cookie (single use; the code itself is also single-use at the provider), exchanges the code with the PKCE verifier, receives the verified user profile. Any failure redirects to `<app>/sign-in?error=<code>` without a session.
4. **Existing user** (found by `idp_user_id`): API creates a session row, sets cookies and redirects to `<app><return_to>`. If the current terms/privacy versions were not yet accepted, every endpoint except `/v1/me*` and sign-out returns 403 `consent_required` until `POST /v1/me/consent`, which rotates the session.
5. **New user** (D-28): no row is written yet. The verified profile goes into the signed cookie `bo_signup` (30 min, `Path=/v1/auth`, with a `bo_csrf` cookie) and the browser goes to `<app>/welcome`, the **18+ confirmation and terms/privacy acceptance** screen (S2). `POST /v1/auth/signup` creates the user (`age_confirmed_at`), both consent rows and the session in one transaction. "I'm under 18" (`POST /v1/auth/signup/decline`) clears the cookies; nothing about the person is stored (NFR-PRV-04).

**Adapter seam:** `identity/providers/workos.py` implements `IdentityProvider`; `identity/providers/fake.py` is used in local dev, tests and E2E (CI never calls WorkOS). The fake provider serves its own form at `/v1/auth/fake/authorize` from the API origin; that route, and its exemption from the Origin check (§3), exist only when `IDENTITY_PROVIDER=fake`, which settings refuse in production. Fallback provider (direct Google OIDC) implements the same interface ([ADR-0011](adr/0011-portability-rules.md)).

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
| Local development | On `localhost` the cookies are host-only (no `Domain`); browsers accept `Secure` cookies on `http://localhost` |

## 3. CSRF (Frozen)

- `SameSite=Lax` **plus** double-submit token: cookie `bo_csrf` (not HttpOnly, per-session random) must equal header `X-CSRF-Token` on `POST/PUT/PATCH/DELETE`.
- `Origin` header must match the allowlisted app origin on unsafe methods.
- Before a session exists (`POST /v1/auth/signup`), the double-submit token is bound to the signed `bo_signup` cookie instead of a session row.
- CORS: allow only `https://app.<root-domain>` (and `http://localhost:5173` in dev) with credentials; never `*`.

## 4. Authorization model

RBAC per organisation + ownership checks + RLS.

| Action | owner | member | viewer | grantee |
|---|---|---|---|---|
| View org name and type | ✓ | ✓ | ✓ | ✓ |
| View org data (facts, obligations, explanations) | ✓ | ✓ | ✓ | ✓ |
| Edit facts, confirm proposals, mark obligations done | ✓ | ✓ | — | — |
| Use Copilot | ✓ | ✓ | — | — |
| Upload personal document (Situation Check) | ✓ | ✓ | — | — |
| See members; see access grants | ✓ | ✓ | ✓ | — |
| Invite members / change roles / remove members | ✓ | — | — | — |
| Share, accept or revoke access grants | ✓ | — | — | — |
| Export org data | ✓ | — | — | — |
| Delete organisation | ✓ | — | — | — |
| Launchpad → incorporation handoff | ✓ | — | — | — |

**grantee** = a member (any role) of a CA firm or incubator holding an **active** access grant from the company. Grantees only ever view, whatever the grant's scope (`manage` is reserved, D-29). Any member may leave an organisation; the last owner can't leave or be demoted (409 `last_owner`).

Permission checks are centralised in `tenancy/service.py` (`require(ctx, action)`, matrix in `tenancy/permissions.py`), never scattered `if role ==` checks.

## 5. Enforcement layers

| Layer | Responsibility |
|---|---|
| Middleware | Resolve session → `user_id`; reject unauthenticated; reject `consent_required`; attach `request_id` |
| Org dependency (`/v1/orgs/{org_id}/…`) | Load membership for `(org_id, user_id)`, or an active grant held by one of the caller's orgs; 404 if neither (no existence leak); attach role or `grantee` |
| Service | `require(ctx, action)` per the matrix; ownership checks (e.g., documents) |
| Database | `SET LOCAL app.user_id/app.org_id` at transaction start; RLS policies with read checks (members and active grantees) and write checks (owners and members; owners for people and sharing) ([data-model.md §3](data-model.md#3-request-context-and-rls-frozen), [ADR-0013](adr/0013-rls-check-functions-and-read-write-split.md)) |

The organisation always comes from the URL path validated against membership — **never from the request body**.

## 6. Invitations

`POST /v1/orgs/{org_id}/invitations` (owner, `Idempotency-Key`) → email (or copyable link if email channel disabled) containing a single-use token (hash stored, 7-day expiry). Accept → must be signed in; if signed-in email differs from invited email, explicit confirmation required; membership created; token consumed.

- The link is `<app>/invite#token=<token>`: the token sits in the **fragment**, which browsers never send to a server, and the SPA keeps it in `sessionStorage` (that tab only) across sign-in, then removes it from the URL.
- `POST /v1/invitations/lookup` and `POST /v1/invitations/accept` take the token **in the body** (`{token, confirm_email_mismatch}`). Unknown, expired or used → 404; different email without confirmation → 409 `invitation_email_mismatch`; already a member → 409.
- The link is returned **once**, in the creation response. A replay with the same `Idempotency-Key` returns the invitation with `invite_link: null`, `link_available: false`; the token is not rotated (that would break a link already copied) — revoke and invite again if it's lost.
- At the database the accepting user proves the token with `SET LOCAL app.invitation_token_hash`; the membership insert and the `accepted_at` update are allowed only for that invitation's org and role, and only while it is unaccepted and unexpired by the database's own clock (a backstop for the API's expiry check; a refusal is answered with the same 404) ([data-model.md §4.2](data-model.md#42-tenancy)).

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
