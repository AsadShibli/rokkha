# Rokkha web

Next.js frontend for Rokkha. Live at **https://rokkha.vercel.app** (deployed by Vercel on every
push to `main`; pull requests get preview deployments).

## Run locally

```bash
npm install
npm run dev        # http://localhost:3000
```

It talks to the API at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api/v1`; see
`.env.example`). Start the API from the repo root with `docker compose up -d` and seed it with
`docker compose exec api python -m scripts.seed`.

## Checks

```bash
npm run lint       # ESLint, including the React Compiler rules
npm run build      # type-check + production build
```

## Layout

```
src/app/            routes: landing, login/register, citizen, officer, admin
src/components/     UI by area (citizen, officer, admin, gd, incident, map, ui)
src/lib/            API client + token refresh, auth, i18n (en/bn), queries, realtime feed
```

Notes:
- Pages prerender as static HTML; session and language live in the browser, so nothing reads
  cookies on the server.
- Live incident updates come over the API's WebSocket and are merged into the React Query cache.
- Maps use MapLibre with OpenFreeMap tiles (free, no key).
