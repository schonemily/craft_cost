# Website deep analysis and recommendations

## Current state (observations)
- **Stack**: Next.js 14 App Router, React 18, TailwindCSS, React Query, NextAuth (OAuth-only: Google, GitHub), Prisma/Postgres.
- **CI/CD**: GitHub Actions for web/api build; docker-compose for local; Bitbucket mirror.
- **Features**: Sign-in with OAuth, CSV upload, suggestions list, debt payoff simulator with charts, dashboard, subscriptions/Stripe, basic flags.
- **UX**: Dark theme, top bar API status ping, Nav links, minimal forms, toast notifications.
- **Perf**: Dynamic import for charts, route transitions, animated suggestion cards; still room for caching, virtualization, and image/asset tuning.
- **Security**: NextAuth JWT + Prisma adapter; custom API token minted and saved in `localStorage` via `SessionProvider`.
- **Accessibility**: Basic semantics present; needs ARIA sweeps, color contrast checks, and reduced-motion support.

## Add‑ons (what to add)
- **Performance + UX**
  - Enable React Query HTTP caching headers and longer `staleTime` for read‑only endpoints; add request de‑duplication on critical routes.
  - Add list virtualization (e.g., `@tanstack/react-virtual`) for Suggestions and any long tables.
  - Preload above‑the‑fold fonts (Inter), preconnect `api` origin, and set `crossorigin` as needed.
  - Add skeletons for all list/table routes and optimistic UI where safe (e.g., toggles, flags).
  - Add `prefers-reduced-motion` CSS variant and a user toggle to disable animations globally.
  - Compress and serve SVG/PNG assets; ensure `Image` uses proper `sizes` and `priority` only where needed.
  - Add route-level loading states (app/route `loading.tsx`) for slower pages.

- **Reliability + Observability**
  - Integrate error tracking (Sentry) for both web and api; include release/source maps upload in CI.
  - Add basic RUM (e.g., `@sentry/nextjs` Web Vitals) to monitor CLS/LCP/INP; budget alerts in CI.
  - Centralized logging/alerts for API health; rate-limit and backoff on `TopbarStatus` pings.

- **Security + Compliance**
  - Replace client `localStorage` token persistence with secure HTTP‑only cookie or NextAuth session token passthrough; avoid storing `apiToken` in the browser.
  - Add CSP, Referrer-Policy, Permissions-Policy, and HSTS headers (via Next middleware or `next-safe`).
  - Add CSRF protection for any state‑changing API calls performed without NextAuth session.
  - Secrets scanning in CI (e.g., Gitleaks) and dependency audit (npm/pip audit with fail-on-high).

- **DX + CI/CD**
  - Add build cache to CI (`actions/cache` for npm + Next cache) to reduce build times.
  - Add Playwright e2e smoke tests for auth flow, upload, suggestions, and debt simulator.
  - Add TypeScript strict mode (incrementally) and ESLint + Prettier with CI checks.
  - Optional: Turborepo task caching for monorepo to accelerate repeated builds.

- **Product features (based on comparable fintech apps)**
  - Bank connection flow (Plaid) with guided onboarding, category rules, and duplicate detection.
  - Budgets with envelopes and alerts; monthly report email/export (PDF/CSV already exists for debt; extend to spend).
  - Subscription manager (detect recurring charges) with one‑click categorize/cancel links.
  - Goal setting (e.g., payoff date targets) and progress widgets on dashboard.
  - Notifications: email for major changes, export completion, or monthly summaries.
  - Saved scenarios for the debt simulator; compare scenarios side‑by‑side and share.

- **Accessibility**
  - Keyboard navigation for all interactive elements; focus rings and skip links.
  - ARIA labels/roles for icon‑only controls; announce toasts for screen readers.
  - Contrast checks for muted text; provide theme toggle if needed.

- **Growth/SEO**
  - Add marketing pages with structured data (FAQ, How‑to); Open Graph/Twitter cards.
  - Sitemap and robots; canonical URLs; basic analytics (privacy friendly).

## Removals / Changes (what to remove or refactor)
- **Auth routes duplication**: 301/302 redirect `/signup` and `/login` to `/signin` to avoid confusion now that OAuth‑only is live.
- **Local token persistence**: Remove `SessionProvider` logic that writes `apiToken` to `localStorage`; rely on NextAuth session or an HttpOnly cookie.
- **Header API pings**: Lazy‑load or debounce `TopbarStatus` and combine health + flags endpoint; reduce header fetches on every route.
- **Client‑heavy charts on first paint**: Keep charts dynamically imported (already done); ensure no chart code in the initial route bundles.
- **Dev artifacts**: Ensure `mailhog` and test SMTP variables never leak into production config.
- **Unused pages and links**: Audit NavLinks; hide links a user cannot access until signed in; gate feature routes behind flags.
- **Large bundle dependencies**: Periodically assess `recharts` and `framer-motion` impact; consider lighter chart libs if needs expand.
- **CSV ingest edge cases**: Add server‑side row validation and graceful error UI; skip invalid rows instead of blocking entire upload.
- **Build flakes**: Ensure prisma generate/build steps always set `DATABASE_URL` in CI; pin minor versions to reduce variance.

## Quick win checklist (1–2 sprints)
- **Security**: Remove localStorage token; add security headers (CSP/HSTS) and Sentry across web/api.
- **Perf**: Virtualize long lists; add route `loading.tsx` and skeletons; enable Next/Node caches in CI.
- **UX**: Redirect `/signup`→`/signin`; add reduced‑motion toggle; polish empty states and optimistic updates.
- **Tests**: Add Playwright smoke tests for auth, upload, suggestions, debt export.

---
Owned artifacts created by this research: this file (`updates.md`).
