# API Design

Each endpoint lists **Who** may call it, the **Input**, what it **Must do**, what it
**Must NOT** do, and the **Response**. Rules are referenced as `BR <section> <n>` from
[business_rules.md](business_rules.md).

## Conventions

- **Base path:** `/api/v1`. JSON in and out.
- **Auth:** `Authorization: Bearer <access_token>`. Public endpoints: register, login, refresh,
  health.
- **Scope:** a record outside the caller's scope returns `404 NOT_FOUND`. `403 FORBIDDEN` is
  only for "your role can never call this endpoint".
- **Pagination:** `page` (default 1), `page_size` (default 20, max 100). Response:
  `{ "items": [], "total", "page", "page_size" }`. Newest first.
- **Dates:** ISO 8601 UTC (`2026-10-12T08:30:00Z`); `incident_date` is a plain date.
- **Coordinates:** `lat`, `lng` as numbers, inside Bangladesh's bounding box (BR Locations 1).
- **Error format** (every error):

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "Some fields are invalid.",
             "details": [ { "field": "phone", "message": "Invalid Bangladeshi phone number" } ] } }
```

`details` is `[]` unless the error is about specific fields.

### Error codes

| Status | Code | When |
|---|---|---|
| 401 | `INVALID_CREDENTIALS` | wrong phone or password |
| 401 | `INVALID_TOKEN` | missing, expired, malformed or revoked token; wrong token type |
| 403 | `ACCOUNT_DISABLED` | user is inactive |
| 403 | `FORBIDDEN` | role not allowed on this endpoint |
| 404 | `NOT_FOUND` | doesn't exist or out of scope |
| 409 | `CONFLICT` | duplicate unique value (field named in `details`) |
| 409 | `INVALID_TRANSITION` | status change not allowed from current status |
| 409 | `ACTIVE_SOS_EXISTS` | citizen already has an open SOS |
| 409 | `OFFICER_BUSY` | busy officer tries to change duty status |
| 409 | `OFFICER_UNAVAILABLE` | reassign target is not reachable / not in station / same officer |
| 422 | `VALIDATION_ERROR` | body or query fails validation |
| 429 | `RATE_LIMITED` | too many SOS (Stretch) |
| 503 | `AI_UNAVAILABLE` | AI draft failed or timed out (Stretch) |

### Resource shapes

Responses reuse these shapes so each endpoint below only names them.

```jsonc
// User
{ "id": 7, "name": "Rahim Uddin", "phone": "+8801711000000", "email": null,
  "role": "citizen", "is_active": true, "station_id": null, "created_at": "..." }

// Station
{ "id": 2, "name": "Kotwali", "code": "KOT", "city": "Sylhet", "city_code": "SYL",
  "lat": 24.8949, "lng": 91.8687 }

// Officer
{ "id": 4, "user": { "id": 12, "name": "...", "phone": "..." }, "station_id": 2,
  "badge_no": "KOT-1043", "rank": "Sub-Inspector", "duty_status": "available",
  "last_lat": 24.90, "last_lng": 91.87, "last_seen_at": "..." }

// StationBrief: names a thana inside other resources
{ "id": 2, "name": "Kotwali", "code": "KOT" }

// OfficerBrief: what a citizen sees about their officer, enough to identify and reach them
// (no exact last_seen)
{ "id": 4, "name": "...", "rank": "Sub-Inspector", "badge_no": "KOT-1043", "phone": "+8801...",
  "station": StationBrief, "last_lat": 24.90, "last_lng": 91.87 }

// Incident (list item)
{ "id": 31, "type": "sos", "status": "assigned", "lat": 24.89, "lng": 91.87,
  "description": null, "station_id": 2, "station": StationBrief, "citizen_id": 7,
  "officer": OfficerBrief | null, "created_at": "...", "assigned_at": "...",
  "accepted_at": null, "resolved_at": null, "cancelled_at": null }

// IncidentDetail = Incident + "events": [IncidentEvent]
// IncidentEvent
{ "id": 90, "from_status": null, "to_status": "pending", "actor_id": 7,
  "officer_id": null, "note": null, "created_at": "..." }

// Gd
{ "id": 5, "gd_number": "SYL-KOT-2026-000123", "citizen_id": 7, "station_id": 2,
  "station": StationBrief,
  "category": "lost_document", "title": "...", "details": "...",
  "incident_date": "2026-10-11", "status": "submitted",
  "reviewed_by": null, "reviewed_at": null, "review_note": null, "created_at": "..." }
```

---

## Health

### GET /health

**Who:** public

**Must do:** run `SELECT 1` on Postgres (and `PING` Redis once Redis exists).

**Must NOT:** require auth or leak connection strings or stack traces.

**Response:** `200 {"status": "ok", "db": "ok"}`; `503 {"status": "degraded", "db": "down"}`.

---

## Auth

### POST /auth/register

**Who:** public

**Input:** `name` (2-100, trimmed), `phone` (`+8801XXXXXXXXX`), `email` (optional), `password`
(8 characters to 72 bytes; bcrypt ignores anything past 72 bytes, and a Bangla letter is 3 bytes).

**Must do:**
- validate input; lowercase the email
- check phone and email are not taken (BR Accounts 1)
- create the user with role `citizen`, password stored as a bcrypt hash

**Must NOT:**
- accept `role`, `station_id` or `is_active` from the client (extra fields are ignored)
- return the password or hash
- log the user in (the client calls `/auth/login`)

**Response:** `201` + User. `409 CONFLICT` (phone/email taken), `422`.

---

### POST /auth/login

**Who:** public

**Input:** `phone`, `password`

**Must do:**
- verify the credentials
- issue an access token (15 min) and a refresh token (7 days); store the refresh `jti`

**Must NOT:**
- reveal whether the phone exists (same error and similar timing for both cases)
- log in an inactive user

**Response:** `200 {"access_token", "refresh_token", "token_type": "bearer", "expires_in": 900}`.
`401 INVALID_CREDENTIALS`, `403 ACCOUNT_DISABLED`, `422`.

---

### POST /auth/refresh

**Who:** anyone holding a refresh token

**Input:** `refresh_token`

**Must do:**
- check signature, expiry, `type = refresh`, `jti` exists and is not revoked, user is active
- revoke the old `jti` and issue a **new pair** in one transaction (BR Accounts 6)

**Must NOT:**
- accept an access token
- accept a token that was already rotated or logged out

**Response:** `200` + same body as login. `401 INVALID_TOKEN`, `403 ACCOUNT_DISABLED`.

---

### POST /auth/logout

**Who:** any authenticated user

**Input:** `refresh_token`

**Must do:** revoke that refresh token. It must belong to the caller.

**Must NOT:** revoke the user's other sessions.

**Response:** `204`. `401 INVALID_TOKEN` (also when the token belongs to someone else).

---

### GET /users/me

**Who:** any authenticated user

**Response:** `200` + User. If the caller is an officer, also includes `"officer": Officer`.

---

## Stations

### GET /stations

**Who:** any authenticated user (citizens need it to choose a station for a GD)

**Input (query):** `city` (optional, case-insensitive), pagination. Sorted by name.

**Response:** `200` + paginated Station.

---

### POST /stations

**Who:** super_admin

**Input:** `name`, `code` (2-5 uppercase), `city`, `city_code` (3 uppercase), `lat`, `lng`.

**Must do:** validate; check `code` and `(city, name)` are unique.

**Must NOT:** allow changing `code` later (there is no update endpoint in the MVP).

**Response:** `201` + Station. `403`, `409 CONFLICT`, `422`.

---

### POST /stations/{station_id}/admins

**Who:** super_admin

**Input:** `name`, `phone`, `email` (optional), `password`.

**Must do:**
- check the station exists
- create a user with role `station_admin` and `station_id` = this station

**Must NOT:** let the client choose the role or a different station.

**Response:** `201` + User. `403`, `404` (station), `409 CONFLICT`, `422`.

---

## Officers

### GET /officers

**Who:** station_admin (own station only), super_admin (all)

**Input (query):** `duty_status`, `station_id` (super_admin only; ignored for station
admins), pagination.

**Response:** `200` + paginated Officer. `403` for citizen/officer.

---

### POST /officers

**Who:** station_admin

**Input:** `name`, `phone`, `email` (optional), `password`, `badge_no`, `rank`.

**Must do:**
- create the user (role `officer`) and the officer profile in **one transaction** (BR Officers 1)
- set the station to the admin's own station; start as `off_duty`

**Must NOT:** accept `station_id` or `duty_status` from the client.

**Response:** `201` + Officer. `403`, `409 CONFLICT` (phone/email/badge_no), `422`.

---

### PATCH /officers/me/status

**Who:** officer

**Input:** `duty_status`: `available` or `off_duty`.

**Must do:** update the status (BR Officers 5).

**Must NOT:**
- accept `busy`; that value is set only by the system (sending it gives 422)
- change status while `busy` (BR Officers 6)

**Response:** `200` + Officer. `403`, `409 OFFICER_BUSY`, `422`.

---

### PATCH /officers/me/location

**Who:** officer

**Input:** `lat`, `lng`.

**Must do:** set `last_lat`, `last_lng`, `last_seen_at = now()` (BR Officers 7). Publish the
location to the officer's open incident channel (Stretch, WebSocket).

**Must NOT:** change `duty_status`.

**Response:** `204`. `403`, `422`.

---

## Incidents

### POST /incidents/sos

**Who:** citizen

**Input:** `lat`, `lng`, `description` (optional, ≤ 1000).

**Must do:**
1. reject if the citizen already has an open SOS (BR Incidents-creation 7)
2. set `station_id` = nearest station
3. create the incident `pending` + creation event (actor = citizen)
4. in the **same transaction**, find the nearest reachable officer city-wide with
   `FOR UPDATE SKIP LOCKED` (BR Incidents-creation 3-4); if found, set officer → `busy`,
   incident → `assigned`, `assigned_at`, and add event `pending → assigned` (actor = NULL,
   i.e. the system)
5. if no officer is found, leave it `pending`

**Must NOT:**
- fail just because no officer is free (still 201)
- assign an officer who is busy, off duty, has no location, or was seen > 10 min ago
- let two simultaneous SOS calls take the same officer

**Response:** `201` + IncidentDetail (`status` is `assigned` with `officer`, or `pending`
with `officer: null`). `403`, `409 ACTIVE_SOS_EXISTS`, `422`, `429 RATE_LIMITED` (Stretch).

---

### POST /incidents/report

**Who:** citizen

**Input:** `lat`, `lng`, `description` (**required**, 10-1000).

**Must do:** set `station_id` = nearest station; create it `pending` with a creation event.

**Must NOT:** auto-assign an officer (BR Incidents-creation 6).

**Response:** `201` + IncidentDetail. `403`, `422`.

---

### GET /incidents

**Who:** any authenticated user, scoped by role (BR Roles 1-4)

**Input (query):** `status`, `type`, `from`, `to` (dates on `created_at`), `station_id`
(super_admin only), pagination.

**Must do:** apply the role scope **before** the filters, so a filter can never widen scope.

**Response:** `200` + paginated Incident. `422` (bad filter value).

---

### GET /incidents/{incident_id}

**Who:** the citizen owner, the assigned (or previously assigned) officer, a station admin of
its station, super_admin

**Response:** `200` + IncidentDetail (events oldest first). `404` (missing or out of scope).

---

### POST /incidents/{incident_id}/accept

**Who:** the currently assigned officer

**Input:** `note` (optional).

**Must do:** `assigned → en_route`, set `accepted_at`, add event; all in one transaction.

**Must NOT:** let any other officer accept it.

**Response:** `200` + IncidentDetail. `404` (not yours), `409 INVALID_TRANSITION`.

---

### POST /incidents/{incident_id}/resolve

**Who:** the currently assigned officer

**Input:** `note` (optional).

**Must do:** `en_route → resolved`, set `resolved_at`, officer → `available`, add event.

**Must NOT:** resolve an incident that was never accepted.

**Response:** `200` + IncidentDetail. `404`, `409 INVALID_TRANSITION`.

---

### POST /incidents/{incident_id}/cancel

**Who:** the citizen owner

**Input:** `note` (optional reason).

**Must do:** `pending|assigned → cancelled`, set `cancelled_at`, free the officer if there
was one, add event.

**Must NOT:** cancel once the incident is `en_route` (BR Lifecycle 5).

**Response:** `200` + IncidentDetail. `404`, `409 INVALID_TRANSITION`.

---

### POST /incidents/{incident_id}/reassign

**Who:** station_admin of the incident's station

**Input:** `officer_id`, `note` (optional).

**Must do:**
- lock the target officer row and check they are reachable and in the admin's station
  (BR Lifecycle 7)
- old officer (if any) → `available`; new officer → `busy`
- incident → `assigned` with new `officer_id` and `assigned_at`; clear `accepted_at`
- add event with `officer_id` = new officer

**Must NOT:** reassign a `resolved` or `cancelled` incident, or reassign to the same officer.

**Response:** `200` + IncidentDetail. `403`, `404`, `409 INVALID_TRANSITION`,
`409 OFFICER_UNAVAILABLE`, `422`.

---

## Online GD

### POST /gds

**Who:** citizen

**Input:** `station_id`, `category`, `title` (5-150), `details` (20-5000), `incident_date`
(not in the future).

**Must do:**
- check the station exists (else `422` on `station_id`)
- take the next number from `gd_sequences` and insert the GD in **one transaction**
  (see database_schema.md)
- start as `submitted`

**Must NOT:** accept `gd_number`, `status` or review fields from the client.

**Response:** `201` + Gd. `403`, `422`.

---

### GET /gds

**Who:** citizen (own), station_admin (own station), super_admin (all). Officers get `403`.

**Input (query):** `status`, `category`, `from`, `to`, `station_id` (super_admin only),
pagination.

**Response:** `200` + paginated Gd.

---

### GET /gds/{gd_number}

**Who:** the citizen owner, station_admin of its station, super_admin

**Response:** `200` + Gd. `404`.

---

### PATCH /gds/{gd_number}/review

**Who:** station_admin of the GD's station

**Input:** `action`: `start_review` | `approve` | `reject`; `note` (required for `reject`).

**Must do:**
- `start_review`: `submitted → under_review`
- `approve` / `reject`: `under_review → approved|rejected`; set `reviewed_by`, `reviewed_at`,
  `review_note`

**Must NOT:** skip `under_review`, change a final GD, or let another station's admin review.

**Response:** `200` + Gd. `403`, `404`, `409 INVALID_TRANSITION`, `422` (reject with no note).

---

## Dashboard

### GET /dashboard/stats

**Who:** station_admin (own station), super_admin (city-wide, or `?station_id=`)

**Response:** `200`

```json
{ "station_id": 2,
  "incidents": { "pending": 1, "assigned": 2, "en_route": 1, "resolved": 40, "cancelled": 3 },
  "open_sos": 3,
  "gds": { "submitted": 4, "under_review": 2, "approved": 30, "rejected": 1 },
  "officers": { "off_duty": 5, "available": 3, "busy": 2 },
  "avg_response_seconds_7d": 312 }
```

`avg_response_seconds_7d` is `null` when no incident was accepted in the last 7 days.
`403` for citizen/officer.

---

## Stretch endpoints

### POST /gds/ai-draft  (Stretch 3)

**Who:** citizen. **Input:** `text` (Bangla or English, ≤ 2000).

**Must do:** ask the configured LLM (Groq free tier by default, or Anthropic) for strict JSON `{category, title, details, incident_date|null}`
(JSON mode / JSON-schema output), validate it with the same field rules as `POST /gds`, drop a
future date, fail fast (no retries, ~20 s timeout), and limit each citizen to 10 drafts per hour
(`429 RATE_LIMITED`).

**Must NOT:** save anything, or return unvalidated model output.

**Response:** `200` draft. `503 AI_UNAVAILABLE` on timeout or invalid output. `422`.

### WS /ws/incidents/{incident_id}?token=<access_token>  (Stretch 2)

**Who:** the citizen owner and the assigned officer.

**Must do:** check the token and access before accepting the socket (close code `4401` /
`4404` otherwise). Push `{"type": "status", ...}` and `{"type": "location", ...}` messages from
Redis pub/sub channel `incident:{id}`.

**Must NOT:** let the client send anything other than pings.
