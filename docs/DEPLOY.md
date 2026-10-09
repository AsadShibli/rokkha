# Deploying Rokkha

The app is one Docker image. On start it runs `alembic upgrade head`, then Uvicorn on `$PORT`.
The same image runs the ARQ worker with `arq app.workers.main.WorkerSettings`.

## What it needs

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | Postgres 14+. `postgres://` URLs from hosts are converted to `postgresql+asyncpg://` automatically |
| `REDIS_URL` | yes | pub/sub for WebSockets, the job queue, rate limits |
| `JWT_SECRET` | yes | any long random string; startup fails if it's the dev default outside `APP_ENV=local` |
| `APP_ENV` | yes | e.g. `production` |
| `ANTHROPIC_API_KEY` | no | enables `POST /gds/ai-draft`; without it that endpoint returns 503 `AI_UNAVAILABLE` |
| `AI_MODEL` | no | defaults to `claude-opus-5-5` |
| `SOS_ACCEPT_TIMEOUT_SECONDS` | no | escalation delay, default 120 |

## Render (Blueprint)

1. Sign in to https://render.com with GitHub and allow access to the `rokkha` repo.
2. **New → Blueprint**, pick the repo. Render reads [`render.yaml`](../render.yaml) and creates
   `rokkha-db` (Postgres), `rokkha-redis` (Key Value), `rokkha-api` (web) and `rokkha-worker`.
   The worker is a paid plan; delete it from the blueprint to stay on the free tier (SOS
   escalation then doesn't run; everything else does).
3. Optionally set `ANTHROPIC_API_KEY` on `rokkha-api` in the dashboard.
4. When the deploy is live, open the web service's **Shell** and seed demo data:
   `python -m scripts.seed`.
5. Swagger: `https://<your-service>.onrender.com/docs`. Health:
   `https://<your-service>.onrender.com/api/v1/health`.

Free web services sleep after inactivity; the first request after that takes ~30-60 s.
Before a demo, run `python -m scripts.seed --touch` so the seeded on-duty officers count as
reachable (they must have been seen in the last 10 minutes).

## Any other Docker host (Railway, Fly.io, a VPS)

```bash
docker build -t rokkha .
docker run -e DATABASE_URL=... -e REDIS_URL=... -e JWT_SECRET=... -e APP_ENV=production -p 8000:8000 rokkha
docker run -e DATABASE_URL=... -e REDIS_URL=... -e JWT_SECRET=... -e APP_ENV=production rokkha arq app.workers.main.WorkerSettings
```
