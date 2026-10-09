# Business Rules

Every rule here should map to a service check, a DB constraint, or a test. Rules marked
**(Stretch)** are not part of the MVP. Error codes match the error shape in PROJECT_PLAN.md.

## Accounts and Authentication

1. Phone is required, unique, and in the format `+8801XXXXXXXXX` (13 digits after `+`, operator
   digit 3-9). Email is optional but unique when given.
2. Users log in with **phone + password**.
3. Password is at least 8 characters and stored only as a bcrypt hash; it is never returned.
4. Self-registration always creates a `citizen`. The client cannot choose the role, station or
   active flag.
5. Access token lives 15 minutes; refresh token lives 7 days.
6. Refreshing rotates the pair: the old refresh token is revoked and cannot be used again.
   Logout revokes only the refresh token sent.
7. A wrong phone and a wrong password give the same error (`401 INVALID_CREDENTIALS`), so the
   response never reveals which one was wrong.
8. An inactive user (`is_active = false`) cannot log in or refresh (`403 ACCOUNT_DISABLED`).
9. Reusing an already-revoked refresh token revokes all of that user's refresh tokens
   (theft detection). **(Stretch)**

## Roles and Visibility

1. `citizen` sees only their own incidents and GDs.
2. `officer` sees only incidents currently or previously assigned to them.
3. `station_admin` sees only their own station's officers, incidents and GDs.
4. `super_admin` sees everything.
5. A record outside the caller's scope behaves as if it does not exist: `404 NOT_FOUND`,
   not 403. (403 is only for "your role can never do this", e.g. a citizen calling `/officers`.)
6. A station admin always has exactly one `station_id`; other roles' `station_id` comes from
   their officer profile or is empty.

## Stations

1. Station `code` is 2-5 uppercase letters, unique (e.g. `KOT`). It is used in GD numbers and
   cannot be changed after creation.
2. Station name is unique within a city. A station has a fixed location (lat/lng).
3. Only a super admin creates station admin accounts. The new user gets role
   `station_admin` and the station's `station_id`. A station may have more than one admin.

## Officers

1. A station admin creates the officer's user account and officer profile together (all or
   nothing). The officer's station is always the admin's own station.
2. One user has at most one officer profile, and that user's role must be `officer`.
3. `badge_no` is unique.
4. New officers start `off_duty`.
5. Duty status is `off_duty`, `available` or `busy`. An officer may set only `off_duty` or
   `available`; `busy` is set and cleared only by the system.
6. An officer who is `busy` cannot change their duty status (`409 OFFICER_BUSY`). They must
   resolve their incident first, or the station admin reassigns it.
7. Sending a location updates `last_lat`, `last_lng` and `last_seen_at`.
8. An officer counts as **reachable** only if `available`, has a known location, and
   `last_seen_at` is within the last 10 minutes.

## Locations

1. Every lat/lng must be inside Bangladesh's bounding box (lat 20.5-26.7, lng 88.0-92.7),
   otherwise `422`.
2. Distance is Haversine distance in kilometres.

## Incidents — creation and assignment

1. An incident is either `sos` (urgent) or `report` (non-urgent).
2. The incident's `station_id` is the **station nearest to the incident location**
   (jurisdiction), whichever officer handles it.
3. On a new SOS, the system picks the **nearest reachable officer city-wide**, not only from
   the jurisdiction station.
4. Assignment is one transaction: lock the candidate officer row
   (`SELECT ... FOR UPDATE SKIP LOCKED`), set officer to `busy`, set incident to `assigned`
   with `assigned_at`. Two simultaneous SOS calls can never get the same officer.
5. If no officer is reachable, the SOS is still created as `pending` (201, never an error).
6. A `report` is never auto-assigned. It stays `pending` until a station admin assigns it.
7. A citizen can have only **one open SOS** at a time (open = pending, assigned, en_route);
   a second one gets `409 ACTIVE_SOS_EXISTS`. Reports have no such limit.
8. A citizen may raise at most 3 SOS per 10 minutes (`429 RATE_LIMITED`). **(Stretch)**

## Incidents — lifecycle

1. Statuses: `pending`, `assigned`, `en_route`, `resolved`, `cancelled`.
2. Allowed transitions (anything else is `409 INVALID_TRANSITION`):

   | From | To | Who | Endpoint |
   |---|---|---|---|
   | pending | assigned | system (SOS) or station_admin | sos / reassign |
   | assigned | en_route | the assigned officer | accept |
   | en_route | resolved | the assigned officer | resolve |
   | pending, assigned | cancelled | the citizen owner | cancel |
   | assigned, en_route | assigned (new officer) | station_admin | reassign |

3. `resolved` and `cancelled` are final.
4. Only the currently assigned officer can accept or resolve (anyone else: `404`).
5. A citizen cannot cancel once the officer is `en_route`; they must contact the station.
6. Whenever an incident leaves an officer (resolved, cancelled, reassigned), that officer goes
   back to `available`.
7. Reassign targets must be reachable officers of the **station admin's own station**;
   otherwise `409 OFFICER_UNAVAILABLE`. Reassigning to the same officer is `409`.
8. Every status change writes one `incident_event` (actor, from, to, optional note) in the same
   transaction as the change. The creation itself is the first event (`from` = null).
9. Timestamps set by the system: `assigned_at` (latest assignment), `accepted_at`,
   `resolved_at`, `cancelled_at`.
10. **Response time** = `accepted_at - created_at`, counted only for incidents that were
    accepted.
11. An SOS still `assigned` (not accepted) after 2 minutes moves to the next-nearest reachable
    officer; the first officer goes back to `available`. **(Stretch)**

## Online GD

1. Citizen chooses the station, a category, title, details, and the incident date. The
   incident date cannot be in the future.
2. Categories (MVP): `lost_item`, `lost_document`, `missing_person`, `threat`, `harassment`,
   `other`.
3. GD number format: `{CITY}-{STATION_CODE}-{YEAR}-{SEQ}`, e.g. `SYL-KOT-2026-000123`.
   `SEQ` is 6 digits, counts per station per year, starts at 1, and never repeats, even when
   two GDs are filed at the same moment.
4. The GD number is generated by the system, unique, and never changes.
5. Statuses: `submitted` → `under_review` → `approved` or `rejected`. Any other move is
   `409 INVALID_TRANSITION`. `approved` and `rejected` are final.
6. Only a station admin of the GD's station can review it. `reviewed_by` and the review time
   are recorded.
7. Rejecting requires a `review_note`; approving does not.
8. A citizen cannot edit or delete a GD after submitting it.
9. A citizen can view their GD by number; station staff of that station can too; anyone else
   gets `404`.
10. The AI draft endpoint only suggests a draft; it never saves a GD. If the AI call fails or
    times out, return `503 AI_UNAVAILABLE` and let the citizen type manually. **(Stretch)**

## Lists and Errors

1. List endpoints accept `page` (default 1) and `page_size` (default 20, max 100) and return
   `{ "items", "total", "page", "page_size" }`.
2. Lists are newest first and filterable by `status`, `station_id` (admins only) and a
   `from`/`to` date range.
3. All errors use one shape: `{"error": {"code", "message", "details"}}`; `details` is only
   filled for validation errors.
4. Validation errors are `422 VALIDATION_ERROR` (FastAPI's default, reshaped to the error
   format).
5. Duplicate unique values (phone, email, badge_no, station code) are `409 CONFLICT` with the
   field named in `details`.

## Dashboard

1. Station admin sees own station; super admin sees city-wide or can filter by station.
2. Shows: incident counts by status, open SOS count, GD counts by status, officers by duty
   status, and average response time over the last 7 days.
