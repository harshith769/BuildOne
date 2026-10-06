# BuildOne — Security Design (MVP)

> **Status:** v1.0 first cut · 2026-09-28 · Owner: @harshith769
> Requirements: [nfr.md §5–6](nfr.md#5-security). This document states threats, controls, and **known limitations** honestly.

**What this document answers**
- What we protect, from whom, and with which controls
- Where secrets live and who can access what
- What is explicitly not protected in the MVP

## 1. Assets

| Asset | Sensitivity |
|---|---|
| Company facts, obligations, compliance history | Confidential business data |
| Uploaded employment contracts / university policies | Personal data, highly sensitive |
| Copilot conversations | Confidential |
| Sessions, invitation and calendar tokens | Credentials |
| Rule base and evaluation sets | Core IP (integrity matters most) |
| Backups | Contain everything above |

## 2. Threats and controls

| Threat | Control | Ref |
|---|---|---|
| Cross-tenant data access (bug or IDOR) | Org from path + membership check; RLS forced on every tenant table; cross-tenant test suite in CI | NFR-SEC-03 |
| Session theft / fixation | HttpOnly Secure cookies, hashed tokens, rotation on sign-in, idle + absolute expiry, revocation | NFR-SEC-01 |
| CSRF | SameSite=Lax + double-submit token + Origin check | [auth-and-tenancy.md §3](auth-and-tenancy.md#3-csrf-frozen) |
| Malicious upload | Type/size limits, direct-to-R2 signed URLs, parsing in worker with timeouts and memory limits; malware scan before PAID | NFR-SEC-07 |
| Prompt injection via documents/sources | Data delimiters, no model tools, schema-validated outputs, outputs cannot trigger actions | NFR-SEC-08 |
| Personal data leakage to AI providers | Field allowlists, scrubber, user-data tasks only to no-training + ZDR providers | NFR-PRV-02/05 |
| Rule tampering (wrong legal guidance) | Rules only via reviewed PRs with reviewer fields; publication by CI job; branch protection on `main` | FR-RS-03 |
| Secret leakage | No secrets in repo; gitleaks in CI; server `.env` mode 600; distinct least-privilege keys per purpose | NFR-SEC-04 |
| Backup exposure | Separate R2 bucket, write-only key on server, read key only on operator machine | NFR-REL-03 |
| Credential stuffing / abuse | Auth delegated to IdP; rate limits on auth callback, uploads, AI endpoints | NFR-SEC-09 |
| Supply chain | Locked dependencies (`uv.lock`, `pnpm-lock.yaml`), pip-audit / pnpm audit in CI, pinned image digests for base images | NFR-SEC-05 |
| Server compromise | Cloudflare-only origin, SSH keys only, no password auth, unattended upgrades, Postgres not exposed | NFR-SEC-12 |

## 3. Secrets inventory

| Secret | Where | Access |
|---|---|---|
| DB passwords (`app_api`, `app_worker`, `app_owner`) | Server `.env` | Server only; `app_owner` also in CI deploy secret for migrations |
| WorkOS API key + client ID | Server `.env` | API |
| Groq / Gemini API keys | Server `.env`; Gemini key also on dev machine (rule drafting) | Worker/API; developer |
| R2 keys: files (RW), backups (write-only), backups (read, restore only) | Server `.env`; restore key only in password manager | Scoped per bucket |
| Sentry DSN | Server `.env`, frontend build | Low sensitivity |
| Deploy SSH key | GitHub Actions secret | Restricted `deploy` user on server |

## 4. Known limitations (MVP)

- Single server: a host compromise exposes the database; mitigated only by hardening and backups.
- The owner patches OS/Postgres; missed patches are a real risk → monthly patch day on the calendar.
- No malware scanning of uploads until PAID; uploads are never executed or served to other users.
- No external penetration test until PAID.
- AI providers and R2 may process data outside India (disclosed; permitted today).
