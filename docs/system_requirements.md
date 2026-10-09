# System Requirements

Who uses Rokkha and what each actor can do. Scope tags: **MVP** (done by 15 Oct) or
**Stretch**. Rules behind each requirement live in [business_rules.md](business_rules.md).

## Actors

| Actor | Who | How the account is created |
|---|---|---|
| citizen | member of the public | self-registers |
| officer | on-the-ground officer, belongs to one station | created by their station admin |
| station_admin | runs one station (thana) | created by a super admin |
| super_admin | city-wide control room | created by seed script |
| system | automatic behaviour, no human | n/a |

---

## citizen

- register with name, phone, optional email, password (MVP)
- log in, refresh session, log out, view own profile (MVP)
- raise an **SOS** with current location; immediately sees either the assigned officer or
  "pending" (MVP)
- file a non-urgent **report** with location and description (MVP)
- list own incidents and open one with its full status timeline (MVP)
- cancel own incident (MVP)
- file an **Online GD**: station, category, title, details, incident date; receives a GD number
  like `SYL-KOT-2026-000123` (MVP)
- list own GDs and see status and review note (MVP)
- get an AI-suggested GD draft from free text, Bangla or English (Stretch)
- watch an incident live: status changes and officer location (Stretch)

## officer

- log in with the account their station admin created (MVP)
- go on duty / off duty (MVP)
- send current location (MVP)
- list incidents assigned to them and open one (MVP)
- **accept** an assigned incident (now en route) (MVP)
- **resolve** an incident they are handling (MVP)
- receive live incident updates (Stretch)

## station_admin

- see officers of own station (MVP)
- create officer accounts for own station (MVP)
- list and filter own station's incidents and GDs (status, date) (MVP)
- **reassign** an incident to another officer, or assign a pending one (MVP)
- **review** a GD: start review, approve, or reject with a note (MVP)
- see dashboard stats for own station: counts, average response time (MVP)

## super_admin

- create stations (MVP)
- create station admin accounts for a station (MVP)
- see all stations, incidents, GDs and officers city-wide (MVP)
- see city-wide dashboard stats (MVP)

## system

- on a new SOS, assign the nearest available officer automatically (MVP)
- record every incident status change as an event: who, from, to, when (MVP)
- generate a unique GD number (MVP)
- free the officer when an incident is resolved, cancelled or reassigned (MVP)
- move an SOS to the next-nearest officer if not accepted in 2 minutes (Stretch)
- rate-limit SOS per citizen (Stretch)
- write an audit log of sensitive actions (Stretch)

## Out of scope

Frontend, file/photo uploads, PostGIS, push notifications, fire/ambulance agencies,
microservices. (Listed as "next steps" in the README.)
