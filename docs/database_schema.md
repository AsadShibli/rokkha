# Database Schema

Detailed constraints for the entities in [ERD.md](ERD.md). Rules come from
[business_rules.md](business_rules.md).

## Conventions

- PostgreSQL 16. `id` is `bigint GENERATED ALWAYS AS IDENTITY` primary key on every table
  (except `gd_sequences`, which has a composite key).
- Every table has `created_at timestamptz NN default now()` and
  `updated_at timestamptz NN default now()` (updated by SQLAlchemy `onupdate`). Not repeated below.
- All timestamps are `timestamptz`, stored in UTC.
- `NN` = NOT NULL, `NULL` = nullable.
- **Enums are `varchar` + `CHECK`**, not native Postgres enums (`SAEnum(..., native_enum=False)`).
  Reason: adding a value to a native enum in Alembic needs a special migration; a CHECK
  constraint is just dropped and re-created.
- Coordinates are `double precision`. Haversine runs in SQL; PostGIS is a documented next step.
- **Nothing is hard-deleted** in the MVP (users are deactivated, incidents/GDs are history).
  So most foreign keys are `ON DELETE RESTRICT`, which protects history if someone deletes
  rows by hand. Only pure child rows cascade.

---

## stations

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | bigint pk | NN | identity | |
| name | varchar(100) | NN | | |
| code | varchar(5) | NN | | **UNIQUE**, 2-5 uppercase letters, immutable |
| city | varchar(60) | NN | | e.g. Sylhet |
| city_code | varchar(3) | NN | | e.g. SYL |
| lat | double precision | NN | | |
| lng | double precision | NN | | |

Unique: `code`; `(city, name)`.

Checks: `code ~ '^[A-Z]{2,5}$'`; `city_code ~ '^[A-Z]{3}$'`; `lat BETWEEN -90 AND 90`;
`lng BETWEEN -180 AND 180`. (The Bangladesh bounding box is checked in the API layer.)

---

## users

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | bigint pk | NN | identity | |
| name | varchar(100) | NN | | |
| phone | varchar(14) | NN | | **UNIQUE**, `+8801XXXXXXXXX` |
| email | varchar(255) | NULL | NULL | **UNIQUE** when set, stored lowercase |
| password_hash | varchar(255) | NN | | bcrypt, never returned |
| role | varchar(20) | NN | `'citizen'` | citizen / officer / station_admin / super_admin |
| is_active | boolean | NN | `true` | |
| station_id | bigint fk | NULL | NULL | only for station_admin |

FK: `station_id` → stations.id **ON DELETE RESTRICT**.

Unique: `phone`; `email` (Postgres allows many NULLs under a unique constraint).

Checks:
- `phone ~ '^\+8801[3-9][0-9]{8}$'`
- `role IN (...)`
- `(role = 'station_admin') = (station_id IS NOT NULL)`: a station admin must have a station
  and nobody else may have one.

Indexes: the unique indexes on `phone` and `email` also serve login lookup;
`station_id` (list a station's admins).

---

## officers

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | bigint pk | NN | identity | |
| user_id | bigint fk | NN | | **UNIQUE** (one profile per user) |
| station_id | bigint fk | NN | | |
| badge_no | varchar(20) | NN | | **UNIQUE** |
| rank | varchar(40) | NN | | free text, e.g. "Sub-Inspector" |
| duty_status | varchar(10) | NN | `'off_duty'` | off_duty / available / busy |
| last_lat | double precision | NULL | NULL | |
| last_lng | double precision | NULL | NULL | |
| last_seen_at | timestamptz | NULL | NULL | set on every location update |

FKs:
- `user_id` → users.id **ON DELETE CASCADE** (the profile has no meaning without the user).
- `station_id` → stations.id **ON DELETE RESTRICT**.

Checks: `duty_status IN (...)`; `(last_lat IS NULL) = (last_lng IS NULL)`; lat/lng ranges as in
stations.

Indexes:
- unique `user_id`, unique `badge_no`
- `(station_id, duty_status)`: station admin's officer list and reassign candidates
- `(duty_status, last_seen_at)` **partial `WHERE duty_status = 'available'`**: the nearest
  officer search only scans reachable officers.

Rule (app-level): the user's `role` must be `officer`. Postgres can't CHECK across tables, so
the service enforces it.

---

## incidents

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | bigint pk | NN | identity | |
| citizen_id | bigint fk | NN | | |
| officer_id | bigint fk | NULL | NULL | current / last assigned officer |
| station_id | bigint fk | NN | | jurisdiction = nearest station |
| type | varchar(10) | NN | | sos / report |
| status | varchar(12) | NN | `'pending'` | pending / assigned / en_route / resolved / cancelled |
| lat | double precision | NN | | |
| lng | double precision | NN | | |
| description | text | NULL | NULL | required for `report`, optional for `sos` (API) |
| assigned_at | timestamptz | NULL | NULL | latest assignment |
| accepted_at | timestamptz | NULL | NULL | |
| resolved_at | timestamptz | NULL | NULL | |
| cancelled_at | timestamptz | NULL | NULL | |

FKs (all **ON DELETE RESTRICT**): `citizen_id` → users.id; `officer_id` → officers.id;
`station_id` → stations.id.

Checks:
- `type IN (...)`, `status IN (...)`
- `(status = 'pending') = (officer_id IS NULL)` for every status except `cancelled`. Written as:
  `status = 'cancelled' OR (status = 'pending') = (officer_id IS NULL)`
- `status <> 'resolved' OR resolved_at IS NOT NULL`
- `status <> 'cancelled' OR cancelled_at IS NOT NULL`
- lat/lng ranges

Indexes:
- **partial UNIQUE `(citizen_id)` WHERE `type = 'sos' AND status IN ('pending','assigned','en_route')`**
  enforces "one open SOS per citizen" in the database. Two parallel requests can't both pass;
  the loser gets a unique violation → `409 ACTIVE_SOS_EXISTS`.
- **partial UNIQUE `(officer_id)` WHERE `status IN ('assigned','en_route')`**: an officer can
  never hold two open incidents, even if the service has a bug. This backs up `SKIP LOCKED`.
- `(citizen_id, created_at DESC)`: citizen's own list
- `(officer_id, created_at DESC)`: officer's list
- `(station_id, status, created_at DESC)`: station admin list with status filter, dashboard counts

---

## incident_events

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | bigint pk | NN | identity | |
| incident_id | bigint fk | NN | | |
| actor_id | bigint fk | NULL | NULL | NULL = done by the system (auto-assign, escalation) |
| officer_id | bigint fk | NULL | NULL | officer assigned by this event, if any |
| from_status | varchar(12) | NULL | NULL | NULL only for the creation event |
| to_status | varchar(12) | NN | | |
| note | varchar(500) | NULL | NULL | |

FKs:
- `incident_id` → incidents.id **ON DELETE CASCADE** (events are pure children).
- `actor_id` → users.id **ON DELETE RESTRICT**.
- `officer_id` → officers.id **ON DELETE RESTRICT**.

Checks: `to_status IN (...)`; `from_status IS NULL OR from_status IN (...)`.

Indexes: `(incident_id, created_at)`: timeline in order.

Append-only: there are no update or delete endpoints, and the repository has no update method.

---

## gds

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | bigint pk | NN | identity | |
| gd_number | varchar(30) | NN | | **UNIQUE**, e.g. `SYL-KOT-2026-000123`, immutable |
| citizen_id | bigint fk | NN | | |
| station_id | bigint fk | NN | | |
| category | varchar(20) | NN | | lost_item / lost_document / missing_person / threat / harassment / other |
| title | varchar(150) | NN | | |
| details | text | NN | | |
| incident_date | date | NN | | not in the future (API) |
| status | varchar(15) | NN | `'submitted'` | submitted / under_review / approved / rejected |
| reviewed_by | bigint fk | NULL | NULL | station admin |
| reviewed_at | timestamptz | NULL | NULL | |
| review_note | varchar(1000) | NULL | NULL | required on reject |

FKs (all **ON DELETE RESTRICT**): `citizen_id` → users.id; `station_id` → stations.id;
`reviewed_by` → users.id.

Checks:
- `category IN (...)`, `status IN (...)`
- `status NOT IN ('approved','rejected') OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)`
- `status <> 'rejected' OR review_note IS NOT NULL`

Indexes: unique `gd_number` (also the lookup for `GET /gds/{gd_number}`);
`(citizen_id, created_at DESC)`; `(station_id, status, created_at DESC)`.

---

## gd_sequences

Per-station, per-year counter for GD numbers.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| station_id | bigint fk | NN | | pk part 1 |
| year | smallint | NN | | pk part 2 |
| last_value | integer | NN | 0 | last number handed out |

PK: `(station_id, year)`. FK: `station_id` → stations.id **ON DELETE RESTRICT**.

Check: `last_value >= 0`.

How a number is taken (inside the same transaction as the GD insert):

```sql
INSERT INTO gd_sequences (station_id, year, last_value) VALUES (:sid, :year, 1)
ON CONFLICT (station_id, year) DO UPDATE SET last_value = gd_sequences.last_value + 1
RETURNING last_value;
```

The upsert locks the row, so two parallel GDs get different numbers, and the first GD of a new
year starts at 1 automatically. If the GD insert fails, the transaction rolls back and the
number is not used, so there are no gaps from failed inserts.

---

## refresh_tokens

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | bigint pk | NN | identity | |
| user_id | bigint fk | NN | | |
| jti | uuid | NN | | **UNIQUE**, the token's id claim |
| expires_at | timestamptz | NN | | now + 7 days |
| revoked_at | timestamptz | NULL | NULL | set on rotation or logout |

FK: `user_id` → users.id **ON DELETE CASCADE**.

Indexes: unique `jti` (lookup on refresh/logout); `user_id` (revoke all of a user's tokens).

Only the `jti` is stored, never the token string. A token is valid when its signature is good,
it is not expired, its `jti` exists, and `revoked_at IS NULL`.

---

## Relationship cardinality summary

| Parent | Child | Cardinality | On delete |
|---|---|---|---|
| stations | users (admins) | 1 — 0..N | RESTRICT |
| users | officers | 1 — 0..1 | CASCADE |
| stations | officers | 1 — 0..N | RESTRICT |
| users | incidents | 1 — 0..N | RESTRICT |
| officers | incidents | 1 — 0..N (max 1 open) | RESTRICT |
| stations | incidents | 1 — 0..N | RESTRICT |
| incidents | incident_events | 1 — 1..N | CASCADE |
| users | incident_events (actor) | 1 — 0..N | RESTRICT |
| users | gds (citizen / reviewer) | 1 — 0..N | RESTRICT |
| stations | gds | 1 — 0..N | RESTRICT |
| stations | gd_sequences | 1 — 0..N | RESTRICT |
| users | refresh_tokens | 1 — 0..N | CASCADE |

## Stretch tables (not in MVP migrations)

- `audit_logs`: actor_id, action, entity, entity_id, ip, created_at (Stretch 3).
- SOS rate limiting uses Redis counters, so it needs no table.
