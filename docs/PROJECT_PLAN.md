# Rokkha — Project Plan

Rokkha (রক্ষা, "protection") is a public-safety dispatch backend: a citizen raises an SOS, the
system auto-assigns the nearest available officer, both sides track it live, and citizens can
file an Online GD that moves through a review workflow.

Target: MVP by 15 Oct, feature-complete by 19 Oct 2026.

## Stack

- API: FastAPI, Pydantic v2 (schemas/DTOs), Uvicorn
- DB: PostgreSQL 16, SQLAlchemy 2.0 async (asyncpg), Alembic migrations
- Auth: JWT access (15 min) + refresh (7 days, rotated + revocable), bcrypt, role-based dependencies
- Real-time: FastAPI WebSockets + Redis pub/sub
- Background jobs: ARQ (Redis)
- Tests: pytest, pytest-asyncio, httpx AsyncClient, separate test DB
- Delivery: Docker + docker-compose, GitHub Actions (ruff + pytest), Postman collection
- Optional AI: LLM call turning free-text complaint (Bangla/English) into a structured GD draft

## Roles
`citizen`, `officer`, `station_admin` (one thana), `super_admin` (city-wide)

## Feature scope
| # | Feature | Tier | Proves |
| --- | --- | --- | --- |
| 1 | Register/login, JWT access + refresh, role guards | MVP | JWT, auth, validation |
| 2 | Stations (thanas) + officer profiles with duty status and last location | MVP | Models, relationships, migrations |
| 3 | SOS with lat/lng; auto-assign nearest on-duty officer (Haversine) | MVP | Service layer, business logic |
| 4 | Incident lifecycle pending -> assigned -> en_route -> resolved/cancelled + event log | MVP | Validation, errors, status codes |
| 5 | Online GD: file, review, approve/reject; number like SYL-KOT-2026-000123 | MVP | Relationships, enums, transactions |
| 6 | Pagination, filters (status, station, date), consistent error JSON | MVP | REST design |
| 7 | Swagger examples + Postman collection | MVP | API testing tools |
| 8 | pytest suite + GitHub Actions | Stretch 1 | Tests, CI/CD |
| 9 | Docker + compose (api, postgres, redis) | Stretch 1 | Docker, Linux |
| 10 | Live incident updates over WebSocket via Redis pub/sub | Stretch 2 | WebSocket, Redis |
| 11 | Auto-escalation: SOS not accepted in 2 min -> next officer | Stretch 2 | Background jobs |
| 12 | AI GD draft endpoint | Stretch 3 | AI API integration |
| 13 | SOS rate limit + audit log; deploy to free host | Stretch 3 | Security, cloud |

Leave out: frontend, S3 uploads, PostGIS, microservices (mention PostGIS as "next step" in README).

## Architecture
Layered: routers -> services -> repositories -> models. Routers stay thin; rules live in services.

```
rokkha/
├── app/
│   ├── main.py              # app factory, routers, exception handlers
│   ├── core/                # config.py (pydantic-settings), security.py (JWT, hashing), exceptions.py
│   ├── db/                  # base.py (DeclarativeBase), session.py (async engine, get_db)
│   ├── models/              # user, station, officer, incident, incident_event, gd, refresh_token
│   ├── schemas/             # Pydantic request/response DTOs
│   ├── repositories/        # DB queries only
│   ├── services/            # auth, dispatch, incident, gd, ai_draft
│   ├── api/deps.py          # current_user, require_role(...)
│   ├── api/v1/              # auth, stations, officers, incidents, gds, dashboard, ws
│   └── workers/             # ARQ: escalate_unacked_sos, notify
├── alembic/
├── tests/
├── scripts/seed.py
├── docker-compose.yml, Dockerfile, .github/workflows/ci.yml
├── postman/rokkha.postman_collection.json
└── README.md
```

Flow: Citizen app / Officer & admin app -> FastAPI (routers -> services -> repositories) ->
PostgreSQL; services also publish to Redis (pub/sub + job queue) and call the LLM API;
ARQ worker reads Redis and updates PostgreSQL.

## Data model (all tables: id, created_at, updated_at — full detail in database_schema.md)
| Table | Key columns | Relationships |
| --- | --- | --- |
| users | name, phone (unique, +8801XXXXXXXXX), email, password_hash, role, is_active, station_id (admins) | 1-1 officer profile |
| stations | name, code (e.g. KOT), city, city_code (e.g. SYL), lat, lng | 1-many officers, incidents, GDs |
| officers | user_id, station_id, badge_no, rank, duty_status (off_duty/available/busy), last_lat, last_lng, last_seen_at | many-1 station |
| incidents | citizen_id, officer_id?, station_id, type (sos/report), status, lat, lng, description, assigned_at, accepted_at, resolved_at, cancelled_at | 1-many events |
| incident_events | incident_id, actor_id?, officer_id?, from_status, to_status, note | audit trail |
| gds | gd_number (unique), citizen_id, station_id, category, title, details, incident_date, status (submitted/under_review/approved/rejected), reviewed_by, reviewed_at, review_note | many-1 user, station |
| gd_sequences | (station_id, year) pk, last_value | per-station yearly GD counter |
| refresh_tokens | user_id, jti, expires_at, revoked_at | many-1 user |

### Assignment logic
On new SOS: select officers `available` and seen in last 10 min, compute Haversine distance, pick
nearest, then set officer -> busy and incident -> assigned in ONE transaction using
`SELECT ... FOR UPDATE SKIP LOCKED`, so two simultaneous SOS calls never grab the same officer.
No free officer -> incident stays `pending` (station admin can reassign).

## API endpoints (/api/v1) — full contracts in api_design.md
Error shape: `{"error": {"code": "OFFICER_UNAVAILABLE", "message": "...", "details": [...]}}`

| Method | Path | Who | Returns |
| --- | --- | --- | --- |
| POST | /auth/register | public | 201 citizen |
| POST | /auth/login | public | 200 access + refresh |
| POST | /auth/refresh | public | 200 new pair (old revoked) |
| POST | /auth/logout | any | 204 |
| GET | /users/me | any | 200 profile |
| GET/POST | /stations | any (POST: super_admin) | 200 / 201 |
| POST | /stations/{id}/admins | super_admin | 201 station admin |
| GET | /officers | admins (role-scoped) | 200 paginated |
| POST | /officers | station_admin | 201 |
| PATCH | /officers/me/status | officer | 200 |
| PATCH | /officers/me/location | officer | 204 |
| POST | /incidents/sos | citizen | 201 assigned or pending |
| POST | /incidents/report | citizen | 201 |
| GET | /incidents | role-scoped | 200 paginated + filters |
| GET | /incidents/{id} | owner, officer, admin | 200 + event timeline |
| POST | /incidents/{id}/accept | assigned officer | 200 -> en_route |
| POST | /incidents/{id}/resolve | assigned officer | 200 -> resolved |
| POST | /incidents/{id}/cancel | citizen owner | 200, officer freed |
| POST | /incidents/{id}/reassign | station_admin | 200 |
| POST | /gds | citizen | 201 with GD number |
| POST | /gds/ai-draft | citizen | 200 suggestion (not saved) |
| GET | /gds | role-scoped | 200 paginated |
| GET | /gds/{gd_number} | owner, station staff | 200 |
| PATCH | /gds/{gd_number}/review | station_admin | 200 start_review/approve/reject |
| GET | /dashboard/stats | admins | 200 counts, avg response time |
| WS | /ws/incidents/{id}?token= | owner, officer | live status + location |
| GET | /health | public | 200 db + redis |

Status codes: 201 create, 204 no body, 401 bad token, 403 wrong role, 404, 409 invalid state
change, 422 validation, 429 SOS rate limit.

## Day-by-day plan
Commit small, one branch + PR per feature (e.g. `feat(dispatch): assign nearest available officer`).
Each day is a vertical slice: model + migration -> schemas -> repository -> service -> router -> tests,
then an audit against the Day-0 docs (flag anything INVENTED / ASSUMED).

- [x] **Day 0 — Fri 9 Oct:** design docs: system_requirements, business_rules, ERD, database_schema, api_design

- [x] **Day 1 — Sat 10 Oct:** repo, pyproject, ruff, .env.example; app factory, settings, async engine, get_db; Alembic + users migration; /auth/register, /health
- [x] **Day 2 — Sun 11 Oct:** login, JWT access + refresh with revocation; current_user + require_role; stations + officers CRUD; officer status/location
- [x] **Day 3 — Mon 12 Oct:** incidents + events models; DispatchService.assign_nearest (Haversine + SKIP LOCKED); POST /incidents/sos with pending fallback
- [x] **Day 4 — Tue 13 Oct:** accept/resolve/cancel/reassign with transition table (409); global error handlers; role-scoped list with pagination + filters
- [x] **Day 5 — Wed 14 Oct:** GD model, numbering, submit/review; /dashboard/stats; scripts/seed.py (3 thanas, 6 officers, 5 citizens)
- [x] **Day 6 — Thu 15 Oct (MVP done):** pytest (auth, assignment incl. 2 concurrent SOS, invalid transitions, GD review); Dockerfile + compose; GitHub Actions
- [x] **Day 7 — Fri 16 Oct:** WebSocket with token auth; Redis pub/sub
- [x] **Day 8 — Sat 17 Oct:** ARQ escalation job; SOS rate limit (429)
- [ ] **Day 9 — Sun 18 Oct:** /gds/ai-draft with strict JSON + timeout fallback; deploy (Render/Railway/Fly.io)
- [ ] **Day 10 — Mon 19 Oct:** README, diagrams, Postman collection, demo video

## README outline
1. Pitch + problem (slow manual dispatch, paper GDs)
2. Live Swagger + demo video links
3. Quick start: `cp .env.example .env && docker compose up` -> /docs; seeded logins
4. Architecture diagram  5. Data model diagram
6. Key decisions: why FastAPI, SKIP LOCKED assignment, state machine, error format
7. Tests + CI badge; next steps (PostGIS, Firebase push, CCTV/drone ingestion)

## Demo video script (2-3 min)
Citizen registers -> SOS from Gulshan -> nearest Badda officer assigned -> officer accepts, citizen
WebSocket shows it -> resolved -> citizen files GD with AI draft -> station admin approves ->
dashboard stats update.
