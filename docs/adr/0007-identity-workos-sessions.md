# ADR-0007: WorkOS AuthKit for identity, server-side sessions, in-house authorization

- **Status:** Accepted (architecture freeze requested by owner, 2026-09-28)
- **Date:** 2026-09-28
- **Decision makers:** @harshith769
- **Confidence:** To be set by owner on acceptance (proposer's view: Medium)

## Decision

**Delegate authentication (email one-time code/link, Google sign-in) to WorkOS AuthKit; after the identity callback, the backend creates its own server-side session; organisations, roles, and CA access grants are modelled in BuildOne's database.** Buying identity removes the riskiest code a solo developer could write; owning sessions and authorization keeps revocation simple and the tenancy model under our control.

## Context

Tenancy is product-specific (teams, companies, CA firms with client grants, incubators). Server-side sessions allow instant revocation, unlike self-issued JWTs. Budget excludes per-user auth pricing.

## Candidates

### A. WorkOS AuthKit + own sessions
- AuthKit user management is free up to 1,000,000 MAU ([Clerk comparison citing WorkOS pricing](https://clerk.com/articles/clerk-pricing-explained)); enterprise SSO available later per connection.
- Vendor dependency for sign-in only; user IDs mapped to internal IDs to allow migration.

### B. Clerk
- Excellent React components and organisation primitives.
- Paid production tier; organisation model would duplicate or constrain BuildOne's own tenancy model.

### C. Self-built auth (Authlib for Google OIDC + own email codes)
- No vendor dependency, zero cost.
- More security-critical code to write and maintain alone (email code brute-force protection, account linking).

## Evaluation

Not measured.

## Consequences

- Session table in Postgres; cookie `HttpOnly`, `Secure`, `SameSite=Lax`; CSRF token on mutations.
- Internal `user_id` (UUIDv7) is primary; provider user ID stored as an external reference.
- Fallback if WorkOS terms change: direct Google OIDC via Authlib plus email one-time codes, replacing only the `identity` adapter ([ADR-0011](0011-portability-rules.md)).
- Details in auth-and-tenancy.md (planned).

## Re-evaluation Triggers

- WorkOS pricing or terms change for the free tier.
- Need for phone-number OTP sign-in at scale (compare providers on SMS cost).
