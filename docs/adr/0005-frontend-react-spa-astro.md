# ADR-0005: React SPA for the app, Astro for marketing, both on Cloudflare Pages

- **Status:** Accepted (architecture freeze requested by owner, 2026-09-28)
- **Date:** 2026-09-28
- **Decision makers:** @harshith769
- **Confidence:** To be set by owner on acceptance (proposer's view: Medium)

## Decision

**Build the authenticated app as a React + TypeScript + Vite single-page app, and the marketing site plus free SEO tools with Astro; host both as static sites on Cloudflare Pages.** The app needs rich interactivity (streaming chat, calendar, dashboards) but no SEO; the public pages need SEO but little interactivity.

## Context

The owner is Python-first; frontend code must be minimal and safe. Commercial hosting must be allowed on the chosen tier. Vercel's Hobby tier is restricted to non-commercial use ([Vercel fair-use guidelines](https://vercel.com/docs/limits/fair-use-guidelines)); static assets on Cloudflare Pages are free ([Makerkit calculator](https://makerkit.dev/pricing-calculator/cloudflare)).

## Candidates

### A. React SPA (Vite) + Astro, static on Cloudflare Pages
- Zero hosting cost; no server-side frontend runtime to operate.
- Typed API client generated from the backend OpenAPI schema reduces hand-written TypeScript.
- Owner must learn React + TypeScript basics.

### B. Next.js
- One framework for app and marketing, server rendering.
- Commercial use on Vercel requires Pro; self-hosting adds a Node runtime to operate.

### C. Server-rendered Python (Jinja templates + HTMX)
- All-Python, fastest for a solo Python developer, no build step.
- Weaker fit for streaming chat, calendars, and rich dashboards; smaller component ecosystem; harder to hire for later.

## Evaluation

Not measured.

## Consequences

- UI built on Tailwind + shadcn/ui components; TanStack Query for server state.
- Session cookie auth requires the API and app on the same site (e.g., `app.` and `api.` subdomains) with correct CORS and CSRF settings.

## Re-evaluation Triggers

- Measured UX need for server rendering inside the app.
- Owner productivity in React blocks the roadmap for > 4 weeks (fallback: option C for internal/admin screens).
