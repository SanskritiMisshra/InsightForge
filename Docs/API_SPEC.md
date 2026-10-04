# InsightForge — API Specification (API_SPEC.md)

**Version:** 1.0
**API Version:** `v1` (base path `/api/v1`)
**Status:** Authoritative for the HTTP contract between the web app (and any future client) and the backend
**Depends on:** `PRD.md` (§11–12, §17–19, §46–66, §87–89, §103–107), `ARCHITECTURE.md` (§7, §9, §10, §12, §13, §18), `DATABASE.md` (§4, §6, §10)
**Contract source of truth:** The OpenAPI 3.1 document generated from the FastAPI/Pydantic models. This document defines the **semantics, rules, and behavior** that a schema alone cannot express. If the two ever disagree, fix the code so they agree and record the change (PRD §127).

---

# 1. Purpose and Scope

This specification defines:

1. Global conventions (transport, authentication, CSRF, errors, pagination, idempotency, rate limits).
2. Every resource and operation in V1, with request/response shapes, status codes, and error codes.
3. Asynchronous behavior (jobs, progress via SSE, polling fallback).
4. Authorization rules and tenancy guarantees.
5. Testing and compatibility rules for the API.

Out of scope: UI behavior (`DESIGN.md`), internal engine contracts (`ARCHITECTURE.md` §8), schema DDL (`DATABASE.md`).

## 1.1 Design principles (derived from the PRD)

| Principle | API consequence |
|---|---|
| Evidence before explanation (PRD §5.2) | Any number returned carries a metric ID and an evidence route; no endpoint returns hand-computed figures |
| AI explains; analytics calculates (PRD §97) | AI endpoints return text only and are labeled; numbers always originate from metric records |
| Reproducibility (PRD §95) | Runs, metrics, and artifacts always expose `dataset_version_id`, `pipeline_version`, `config_hash` |
| Unavailable ≠ failed (PRD §65–66) | Module endpoints return **200** with an `availability` object when prerequisites are missing; **409** only when a client *requests an action* that cannot run |
| No large payloads (PRD §20, §75, §87) | Datasets are never returned wholesale; previews and results are paginated/capped; charts return aggregated series |
| No stack traces (PRD §64, §82) | Errors are coded, user-safe, and carry a `request_id` |
| Privacy by default (PRD §67) | Every operation is owner-scoped; foreign resources return `404` |

---

# 2. Transport and General Conventions

## 2.1 Protocol
- HTTPS only (TLS 1.2+). HTTP requests are redirected at the edge; HSTS enabled.
- Base URL: `https://{host}/api/v1`. The browser reaches it **same-origin** through the Next.js server (BFF proxy), so no cross-origin (CORS) access is enabled for browsers by default. A strict allow-list CORS policy exists only for configured trusted origins.
- JSON request/response bodies, `Content-Type: application/json; charset=utf-8`. File bytes are **never** sent through the API (see §7).
- Compression: `gzip`/`br` supported for responses ≥ 1 KB.

## 2.2 Naming and formatting
| Item | Rule |
|---|---|
| Field names | `snake_case` |
| Enums | `UPPER_SNAKE_CASE` strings, identical to `DATABASE.md` §4 |
| IDs | UUIDv7 strings (e.g. `"01JA3X…"` in canonical UUID form) |
| Timestamps | ISO-8601 UTC with `Z`, e.g. `2026-10-03T14:22:11Z` |
| Durations | Integer milliseconds in fields suffixed `_ms` |
| Sizes | Integer bytes in fields suffixed `_bytes` |
| Percentages | Number in `[0, 100]` unless the field is suffixed `_ratio` (`[0, 1]`) |
| Nulls | Absent data is `null` (never `0`, `""`, or `NaN`) — the UI renders `—` (`DESIGN.md` §2.11) |
| Unknown request fields | Rejected with `VALIDATION_ERROR` (`extra = forbid`) |
| Unknown response fields | Clients **must ignore** unknown response fields (forward compatibility) |

## 2.3 Numeric precision (PRD §114)
Metric values are stored as `numeric(38,10)`. JSON numbers cannot guarantee that precision, therefore:

```json
{
  "value": "8420312.4839200000",   // exact decimal string — the source of truth
  "value_f64": 8420312.48392,      // IEEE-754 convenience for charts only
  "unit": "currency",
  "currency": "INR"
}
```

- `value` is always a **decimal string**. Formatting (e.g. `₹84.20L`) happens only in the client.
- `value_f64` must never be used for display of exact figures or for aggregation.

## 2.4 Standard headers

| Header | Direction | Purpose |
|---|---|---|
| `X-Request-ID` | Request (optional) / Response (always) | Correlation ID; server generates one if absent; echoed in error bodies and logs |
| `X-CSRF-Token` | Request (state-changing) | CSRF protection (§3.3) |
| `Idempotency-Key` | Request (selected `POST`s) | Safe retries (§2.8) |
| `Idempotent-Replay: true` | Response | Indicates a replayed/duplicate-safe response |
| `If-Match` / `ETag` | Both | Optimistic concurrency on editable resources (§2.9) |
| `Prefer: wait=<seconds>` | Request | Ask the server to wait up to N seconds (max 10) for an async operation before returning (§6.4) |
| `Retry-After` | Response (`429`, `503`) | Seconds to wait |
| `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset` | Response | Current rate-limit window (§2.10) |
| `Cache-Control` | Response | `no-store` for authenticated data unless explicitly stated |
| `Deprecation`, `Sunset` | Response | Deprecation signals (§13) |

## 2.5 HTTP methods and status codes

| Method | Use | Idempotent |
|---|---|---|
| `GET` | Read | Yes |
| `POST` | Create / start async action | Only with `Idempotency-Key` or natural key |
| `PATCH` | Partial update | Yes (with `If-Match`) |
| `PUT` | Replace a sub-resource (e.g., mapping) | Yes |
| `DELETE` | Delete / soft-delete / cancel upload | Yes |

| Status | Meaning |
|---|---|
| `200 OK` | Success with body |
| `201 Created` | Resource created; `Location` header set |
| `202 Accepted` | Async work enqueued; body contains a job/resource handle |
| `204 No Content` | Success, no body |
| `400 Bad Request` | Malformed request (bad JSON, bad cursor) |
| `401 Unauthorized` | Not authenticated / session expired |
| `403 Forbidden` | Authenticated but action disallowed (e.g., CSRF failure, account locked) |
| `404 Not Found` | Resource missing **or not owned by caller** (no existence leakage) |
| `409 Conflict` | State conflict (dependencies, unavailable action, duplicate name) |
| `410 Gone` | Artifact/result expired |
| `412 Precondition Failed` | `If-Match` mismatch |
| `413 Payload Too Large` | Request or declared file size exceeds limits |
| `415 Unsupported Media Type` | Unsupported content or file type |
| `422 Unprocessable Entity` | Validation / domain-rule failure |
| `428 Precondition Required` | `If-Match` required but missing |
| `429 Too Many Requests` | Rate or concurrency limit |
| `500 / 503` | Internal / dependency unavailable (generic body, never internals) |

## 2.6 Response envelopes

**Single resource** — returned directly as an object (no wrapper):

```json
{ "id": "…", "name": "Retail Sales Analysis", "…": "…" }
```

**Collection** — always an envelope:

```json
{
  "items": [ { "…": "…" } ],
  "page": {
    "limit": 25,
    "next_cursor": "eyJ1IjoiMjAyNi0xMC0wM1QxNDoyMjoxMVoiLCJpIjoiMDFKQS4uLiJ9",
    "has_more": true,
    "total": 128,
    "total_is_estimate": false
  }
}
```

`total` is optional (omitted when expensive); `total_is_estimate` is `true` when approximate.

## 2.7 Pagination, sorting, filtering (PRD §89–90)

- **Cursor pagination** (default): `?limit=25&cursor=<opaque>`. `limit` default `25`, max `100` (max `200` for dataset preview rows, see §8.4). Cursors are opaque, signed, expire after 24 h, and are bound to the same sort/filter parameters; reusing one with different parameters returns `400 INVALID_CURSOR`.
- **Sorting:** `?sort=-updated_at,name` — comma-separated fields, `-` prefix = descending. Only documented sortable fields are accepted; others → `422 VALIDATION_ERROR`. A stable tiebreaker (`id`) is always appended server-side.
- **Filtering:** documented per endpoint as simple query params (`status=COMPLETED`, `q=retail`), multi-values comma-separated (`status=READY,FAILED`), date ranges `created_after`, `created_before`.
- **Search:** `q` performs case-insensitive substring/trigram matching on documented fields only.
- **Column selection:** tabular endpoints accept `columns=a,b,c` where applicable.

## 2.8 Idempotency (PRD §103–104)

Required (`Idempotency-Key` header, 8–128 chars, client-generated UUID recommended) on: `POST /projects/{id}/datasets`, `POST /datasets/{id}/finalize`, `POST /projects/{id}/analysis-runs`, `POST /dataset-versions/{id}/cleaning`, `POST /analysis-runs/{id}/reports`, `POST /analysis-runs/{id}/presentations`, `POST /analysis-runs/{id}/powerbi`, `POST /projects/{id}/exports`. Optional elsewhere.

Rules:
1. Same key + same endpoint + same body hash → original response replayed with `Idempotent-Replay: true` (same status code).
2. Same key + different body → `422 IDEMPOTENCY_KEY_REUSED`.
3. Keys are scoped per user + endpoint and expire after 24 h (`idempotency_keys.expires_at`).
4. **Natural idempotency** also applies independent of the header: identical run requests resolve to the same `run_key` and return the existing run (`200`, `Idempotent-Replay: true`) rather than a duplicate (`DATABASE.md` §6.5).

## 2.9 Optimistic concurrency

Mutable resources (`projects`, column mappings, settings) return an `ETag` (derived from `updated_at` + version). `PATCH`/`PUT`/`DELETE` on them **require** `If-Match`; missing → `428 PRECONDITION_REQUIRED`, stale → `412 PRECONDITION_FAILED` (body includes the current representation's `etag`).

## 2.10 Rate limits (PRD §82)

Token-bucket per user (and per IP for unauthenticated routes). Defaults (configurable):

| Class | Endpoints | Limit |
|---|---|---|
| Auth | `login`, `register`, `password/forgot` | 10 / min / IP, plus per-account progressive delay and lockout |
| Upload control | upload init/finalize | 30 / min / user |
| Run control | create/cancel/retry run | 20 / min / user; **max concurrent active runs: 2** (configurable) |
| SQL | `sql/execute` | 30 / min / user; max 3 concurrent |
| Generation | reports, decks, Power BI, exports | 10 / min / user |
| AI | `explain`, assistant | 20 / min / user |
| General read | everything else | 600 / min / user |

Exceeded → `429` with `Retry-After`, code `RATE_LIMITED` (or `RUN_LIMIT_REACHED` for concurrency).

## 2.11 Limits

| Item | Default | Notes |
|---|---|---|
| Request body (JSON) | 1 MB | `413` beyond |
| Max upload size | `MAX_UPLOAD_BYTES` (configurable; exposed via `GET /meta/config`) | PRD §76 |
| Max rows / columns | `MAX_ROWS` / `MAX_COLUMNS` (configurable) | Enforced at ingest |
| Preview rows per page | 200 (cap 1,000 total rows via cursor) | PRD §20 |
| SQL result rows per page | 200; total capped (default 10,000) | `DATABASE.md` §6.7 |
| SQL text length | 20,000 chars | |
| Metric series points | ≤ 1,000 per series | PRD §75 |
| Presigned URL TTL | upload parts: 1 h · downloads: 5 min | |
| Request timeout (sync endpoints) | 15 s | async work uses `202` |

---

# 3. Authentication, Sessions, and CSRF

## 3.1 Session model (PRD §12; `ARCHITECTURE.md` §12.1)

- Authentication is **cookie-based**: successful login/registration sets
  `Set-Cookie: if_session=<opaque>; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=…`
- No tokens are exposed to JavaScript and none are stored in `localStorage`.
- Sessions have an **idle timeout** (sliding, default 30 min) and an **absolute lifetime** (default 7 days). Expired/invalid sessions return `401 AUTH_SESSION_EXPIRED` (or `AUTH_REQUIRED` if no session existed); the UI shows the re-auth banner.
- Session ID is rotated on login and on privilege/credential changes.

## 3.2 Protected vs public routes

Public: `POST /auth/register`, `POST /auth/login`, `GET /auth/google/start`, `GET /auth/google/callback`, `POST /auth/password/forgot`, `POST /auth/password/reset`, `GET /auth/csrf`, `GET /healthz`, `GET /readyz`, `GET /meta/config` (non-sensitive subset).
Everything else requires a valid session.

## 3.3 CSRF protection

- All **non-GET/HEAD/OPTIONS** requests must include `X-CSRF-Token` matching the session's CSRF secret, **and** pass `Origin`/`Referer` checks against allowed origins.
- Obtain a token with `GET /auth/csrf` (returns `{ "csrf_token": "…" }`); login/register responses also include it.
- Failure → `403 CSRF_INVALID`.

## 3.4 Auth endpoints

### `POST /auth/register`
Create an account (email/password). PRD §11.3 fields: Name, Email, Password, Confirm Password.

Request:
```json
{ "name": "Sanskar", "email": "user@example.com", "password": "••••••••••", "confirm_password": "••••••••••" }
```
Rules: email normalized (trim, lowercase); password ≥ 10 chars, not on breach/common list; `confirm_password` must match.
Response `201`: `User` object + `csrf_token`; session cookie set. Verification email sent if verification is enabled.
Errors: `VALIDATION_ERROR`, `AUTH_WEAK_PASSWORD`, `AUTH_EMAIL_TAKEN` (see enumeration note below).

> **Enumeration note:** to limit account enumeration, deployments may enable *generic registration* mode where duplicate emails return `201`-equivalent behavior and an email is sent to the existing address. Default V1 returns `409 AUTH_EMAIL_TAKEN`; controlled by `AUTH_REGISTRATION_MODE`.

### `POST /auth/login`
Request: `{ "email": "…", "password": "…" }`
Response `200`: `{ "user": User, "csrf_token": "…" }` + cookie.
Errors: `AUTH_INVALID_CREDENTIALS` (`401`, generic for unknown email *and* wrong password), `AUTH_ACCOUNT_LOCKED` (`403`, with `Retry-After`), `RATE_LIMITED`.

### `POST /auth/logout`
Invalidates the current session server-side and clears the cookie. `204`.

### `POST /auth/logout-all`
Revokes all sessions for the user. `204`.

### `GET /auth/me`
Returns the current `User` (or `401`). Includes `preferences` (currency, density, notifications).

### `GET /auth/google/start`
Starts OAuth 2.0 Authorization Code + PKCE. Query: `redirect_to` (in-app path only, validated). Response `302` to Google with `state` + PKCE challenge stored server-side.

### `GET /auth/google/callback`
Validates `state`, exchanges the code, verifies the ID token (`iss`, `aud`, `exp`, `email_verified`), creates/links the account, sets the session, and `302`s to the validated in-app `redirect_to` (default `/dashboard`).
Errors (rendered as redirect to `/login?error=<code>`): `AUTH_OAUTH_FAILED`, `AUTH_OAUTH_EMAIL_UNVERIFIED`, `AUTH_OAUTH_LINK_CONFLICT`.

### `POST /auth/password/forgot`
Request `{ "email": "…" }`. **Always** `202` regardless of whether the account exists. Rate-limited. Sends a single-use, short-lived reset link.

### `POST /auth/password/reset`
Request `{ "token": "…", "password": "…", "confirm_password": "…" }`. `204` on success (all other sessions revoked). Errors: `AUTH_RESET_TOKEN_INVALID`, `AUTH_WEAK_PASSWORD`.

### `GET /auth/csrf`
`200 { "csrf_token": "…" }` (requires session; returns token for current session).

### Account management

| Method & Path | Description |
|---|---|
| `GET /auth/sessions` | List active sessions (device/UA, created, last seen, `current: true/false`) — Settings → Security |
| `DELETE /auth/sessions/{session_id}` | Revoke one session (`204`) |
| `PATCH /users/me` | Update `name`, `avatar_url`, `preferences` (requires `If-Match`) |
| `POST /users/me/password` | Change password: `{ "current_password", "new_password", "confirm_password" }` → `204`; rotates session |
| `DELETE /users/me` | Delete account (requires `{ "confirm": "<email>" }`); soft-delete + purge scheduling; `202` |

`User` object:
```json
{
  "id": "…",
  "name": "Sanskar",
  "email": "user@example.com",
  "email_verified": true,
  "has_password": true,
  "linked_providers": ["google"],
  "avatar_url": null,
  "preferences": { "currency": "INR", "table_density": "DENSE", "notifications": { "analysis_completed": true } },
  "created_at": "2026-10-03T10:00:00Z",
  "etag": "W/\"3\""
}
```

---

# 4. Errors

## 4.1 Error body (PRD §64; `ARCHITECTURE.md` §7.2)

```json
{
  "error": {
    "code": "DATASET_EMPTY",
    "message": "The dataset contains no usable rows. Please upload a file that contains data.",
    "remedy": "Check that the file has a header row and at least one data row.",
    "details": [
      { "field": "file", "issue": "no_rows", "meta": { "rows_detected": 0 } }
    ],
    "request_id": "01JA3X9K2M…",
    "docs_url": null
  }
}
```

| Field | Rule |
|---|---|
| `code` | Stable `UPPER_SNAKE_CASE` from the closed catalog in §4.3 (clients branch on this, never on `message`) |
| `message` | User-safe English sentence; may be shown directly |
| `remedy` | Optional, actionable next step |
| `details[]` | Optional structured items; `field` uses dot/bracket path for request fields |
| `request_id` | Always present; matches `X-Request-ID` and server logs |

**Never included:** stack traces, SQL text from the application database, file-system paths, internal hostnames, secrets, or raw data values.

## 4.2 Validation errors

`422 VALIDATION_ERROR` with one `details` item per invalid field:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Some fields are invalid.",
    "details": [
      { "field": "name", "issue": "too_short", "meta": { "min_length": 3 } },
      { "field": "currency", "issue": "invalid_format", "meta": { "expected": "ISO 4217 code" } }
    ],
    "request_id": "…"
  }
}
```

Issue codes: `required`, `too_short`, `too_long`, `invalid_format`, `invalid_enum`, `out_of_range`, `not_unique`, `mismatch`, `unknown_field`, `invalid_type`.

## 4.3 Error code catalog

### General
| Code | HTTP | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Request fields invalid |
| `INVALID_CURSOR` | 400 | Cursor malformed, expired, or used with different parameters |
| `NOT_FOUND` | 404 | Resource does not exist or is not accessible to the caller |
| `FORBIDDEN` | 403 | Action not permitted |
| `CONFLICT` | 409 | Generic state conflict |
| `PRECONDITION_FAILED` | 412 | `If-Match` mismatch |
| `PRECONDITION_REQUIRED` | 428 | `If-Match` required |
| `PAYLOAD_TOO_LARGE` | 413 | Request too large |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Unsupported content type |
| `IDEMPOTENCY_KEY_REUSED` | 422 | Same key, different payload |
| `RATE_LIMITED` | 429 | Rate limit exceeded |
| `INTERNAL_ERROR` | 500 | Unexpected error (generic message + `request_id`) |
| `SERVICE_UNAVAILABLE` | 503 | A dependency is unavailable; retry later |

### Authentication & security
| Code | HTTP | Meaning |
|---|---|---|
| `AUTH_REQUIRED` | 401 | No valid session |
| `AUTH_SESSION_EXPIRED` | 401 | Session expired (idle/absolute) |
| `AUTH_INVALID_CREDENTIALS` | 401 | Email or password incorrect |
| `AUTH_ACCOUNT_LOCKED` | 403 | Temporarily locked after repeated failures |
| `AUTH_EMAIL_TAKEN` | 409 | Email already registered |
| `AUTH_WEAK_PASSWORD` | 422 | Password policy not met |
| `AUTH_RESET_TOKEN_INVALID` | 400 | Reset token invalid/expired/used |
| `AUTH_OAUTH_FAILED` | 400 | OAuth exchange/verification failed |
| `AUTH_OAUTH_EMAIL_UNVERIFIED` | 403 | Google account email not verified |
| `AUTH_OAUTH_LINK_CONFLICT` | 409 | Email belongs to an existing account that must be linked explicitly |
| `CSRF_INVALID` | 403 | Missing/invalid CSRF token or origin |

### Projects
| Code | HTTP | Meaning |
|---|---|---|
| `PROJECT_NAME_TAKEN` | 409 | Another live project has this name |
| `PROJECT_ARCHIVED` | 409 | Operation not allowed on an archived project |
| `PROJECT_DELETED` | 410 | Project is in the deletion grace period (restorable) |

### Datasets & versions
| Code | HTTP | Meaning |
|---|---|---|
| `DATASET_FILE_TYPE_UNSUPPORTED` | 415 | Only CSV, XLSX, JSON are supported |
| `DATASET_TOO_LARGE` | 413 | Exceeds `MAX_UPLOAD_BYTES` |
| `DATASET_UPLOAD_INCOMPLETE` | 409 | Finalize called before all bytes/parts were uploaded |
| `DATASET_CHECKSUM_MISMATCH` | 422 | Uploaded bytes do not match the declared checksum |
| `DATASET_EMPTY` | 422 | No usable rows (PRD §115) |
| `DATASET_INVALID_STRUCTURE` | 422 | Cannot parse as a table (inconsistent columns, bad JSON shape, etc.) |
| `DATASET_ENCODING_UNSUPPORTED` | 422 | Text encoding could not be determined/decoded |
| `DATASET_CORRUPT` | 422 | File is corrupted or unreadable |
| `DATASET_UNSAFE_CONTENT` | 422 | Rejected by safety checks (macros, external entities, archive bombs) |
| `DATASET_TOO_MANY_ROWS` | 422 | Exceeds `MAX_ROWS` |
| `DATASET_TOO_MANY_COLUMNS` | 422 | Exceeds `MAX_COLUMNS` |
| `DATASET_NOT_READY` | 409 | Dataset not yet `VALID`/`READY` for this action |
| `DATASET_HAS_DEPENDENTS` | 409 | Deletion blocked by dependent runs/reports (see `details`) |
| `VERSION_NOT_FOUND` | 404 | Dataset version missing/not owned |
| `MAPPING_INVALID` | 422 | Semantic mapping invalid (role/type mismatch) |
| `MAPPING_ROLE_DUPLICATE` | 422 | Same business role assigned to multiple columns |

### Cleaning
| Code | HTTP | Meaning |
|---|---|---|
| `CLEANING_OPERATION_INVALID` | 422 | Unknown operation/parameters |
| `CLEANING_CONFLICT` | 409 | Another operation set is running on this version |
| `CLEANING_NO_EFFECT` | 422 | Operations would change nothing (no new version created) |

### Analysis runs & modules
| Code | HTTP | Meaning |
|---|---|---|
| `RUN_LIMIT_REACHED` | 429 | Too many active runs |
| `RUN_NOT_CANCELLABLE` | 409 | Run already terminal |
| `RUN_NOT_RETRYABLE` | 409 | Run not in a retryable state |
| `RUN_NOT_COMPLETED` | 409 | Action requires a completed run |
| `MODULE_UNAVAILABLE` | 409 | The requested **action** needs data this dataset lacks (reads return `availability` instead) |
| `STAGE_FAILED` | — | Reported inside run/stage payloads (`error_code` on the stage) |
| `STAGE_TIMEOUT` | — | Stage exceeded its time limit (payload code) |
| `STAGE_RESOURCE_LIMIT` | — | Stage exceeded memory/size limits (payload code) |

### SQL
| Code | HTTP | Meaning |
|---|---|---|
| `SQL_REJECTED` | 422 | Statement failed safety validation (`details[].issue` = reason, e.g. `not_select`, `multiple_statements`, `forbidden_keyword`, `unknown_relation`, `forbidden_function`) |
| `SQL_EXECUTION_ERROR` | 422 | Query failed to execute (sanitized message) |
| `SQL_TIMEOUT` | 422 | Exceeded statement timeout |
| `SQL_RESULT_EXPIRED` | 410 | Cached result no longer available; re-run the query |

### Artifacts & AI
| Code | HTTP | Meaning |
|---|---|---|
| `REPORT_NOT_READY` | 409 | Report not yet generated |
| `ARTIFACT_EXPIRED` | 410 | File removed by retention policy; regenerate |
| `GENERATION_FAILED` | — | Reported in the artifact's `error_code` |
| `AI_DISABLED` | 409 | AI features disabled for this project/account |
| `AI_UNAVAILABLE` | 503 | AI provider unavailable; deterministic text is still available |

> Codes marked "—" appear in resource payloads (failed stages/artifacts), not as the HTTP error of the polling request.

---

# 5. Authorization and Tenancy (PRD §67)

1. **Owner-only access (V1).** Every resource belongs to exactly one user. There is no sharing in V1.
2. **404 over 403.** Accessing a resource owned by someone else returns `404 NOT_FOUND`, identical to a nonexistent ID (no existence leakage).
3. **Every endpoint is covered by the cross-tenant test matrix** (§12): user B receiving `404` for each user-A resource ID across all methods.
4. **Nested IDs are verified for consistency**: e.g., `GET /analysis-runs/{run}/metrics?dataset_version_id=…` never trusts a client-supplied parent; ownership is derived from the path resource.
5. **Downloads** use short-lived **presigned URLs** issued only after an authorization check. URLs are single-purpose, expire in 5 minutes, and are never listed in resource payloads (only issued via explicit `download-url` endpoints).
6. **Audit:** security-relevant calls produce `audit_events` (`DATABASE.md` §6.10).

---

# 6. Asynchronous Behavior

## 6.1 Pattern

Long-running work (ingest, analysis, cleaning, SQL, generation) never blocks a request (PRD §63). The API:

1. Validates and authorizes the request.
2. Persists a resource in a non-terminal state (e.g., `QUEUED`).
3. Enqueues the job.
4. Returns `202 Accepted` (or `201`) with the resource and a `Location` header.

Clients then observe progress through **SSE** (preferred) or **polling** (fallback).

## 6.2 Job handle

Async-starting endpoints return the created resource, which always includes:

```json
{
  "id": "…",
  "status": "QUEUED",
  "links": {
    "self": "/api/v1/analysis-runs/01JA…",
    "events": "/api/v1/analysis-runs/01JA…/events"
  }
}
```

## 6.3 Server-Sent Events — `GET /analysis-runs/{run_id}/events`

- `Accept: text/event-stream`; authenticated by the session cookie; ownership checked on connect.
- Each event has `id:` (monotonic per run), `event:` and JSON `data:`. Clients resume with `Last-Event-ID`; the server replays missed events from persisted `stage_runs` state and then continues live.
- Server sends `event: heartbeat` every 15 s and recommends `retry: 3000`.
- The stream closes after a terminal event (`run.completed`, `run.failed`, `run.cancelled`).

Events:

| Event | Payload |
|---|---|
| `run.snapshot` | Full `AnalysisRun` + `stages[]` (sent immediately on connect) |
| `stage.started` | `{ "stage": "PROFILING", "attempt": 1, "at": "…" }` |
| `stage.progress` | `{ "stage": "EDA", "progress_pct": 62.5, "run_progress_pct": 47.0, "message": "Computing correlations" }` |
| `stage.completed` | `{ "stage": "PROFILING", "duration_ms": 4120, "counts": { … } }` |
| `stage.unavailable` | `{ "stage": "SQL_ANALYSIS", "module": "RFM", "reason": "…", "missing_roles": ["CUSTOMER_ID"] }` |
| `stage.failed` | `{ "stage": "SQL_ANALYSIS", "error": { "code": "…", "message": "…", "remedy": "…" }, "retryable": true }` |
| `run.completed` | `{ "finished_at": "…", "modules": [ … ] }` |
| `run.failed` | `{ "error": { "code": "…", "message": "…" } }` |
| `run.cancelled` | `{ "at": "…" }` |
| `artifact.ready` | `{ "type": "REPORT", "id": "…", "format": "PDF" }` |
| `heartbeat` | `{}` |

Example:

```text
id: 17
event: stage.progress
data: {"stage":"EDA","progress_pct":62.5,"run_progress_pct":47.0,"message":"Computing correlations"}

```

## 6.4 Polling fallback and `Prefer: wait`

- Polling: `GET /analysis-runs/{id}` every 2 s with backoff to 10 s. Responses include `ETag`; `If-None-Match` returns `304` when unchanged.
- `Prefer: wait=5` on `POST` (SQL execute, run create) or `GET` of an in-progress resource asks the server to hold up to 5 seconds (max 10) and return the resource as soon as it reaches a terminal state, otherwise return it as-is (`202`/`200`). Responses echo `Preference-Applied: wait=5`.

## 6.5 Cancellation and retry
- `POST /analysis-runs/{id}/cancel` sets a cancel request; the run transitions to `CANCELLED` at the next safe checkpoint (`202` then eventual `run.cancelled`).
- `POST /analysis-runs/{id}/retry` restarts from the first non-completed stage, reusing completed stage outputs whose input hashes are unchanged. Retrying never creates duplicate metrics/insights (idempotent stage writes; `ARCHITECTURE.md` §9.4–9.5).

---

# 7. Resource Reference

> Conventions for the tables below: **Auth** is always "session required" unless stated. `{id}` path parameters are UUIDs. All collection endpoints support `limit`/`cursor`. `★` marks endpoints that require `Idempotency-Key`. Request/response examples show representative fields; the OpenAPI schema is exhaustive.

## 7.1 Meta and health

| Method & Path | Description |
|---|---|
| `GET /healthz` | Liveness (`200 {"status":"ok"}`); public |
| `GET /readyz` | Readiness: DB, Redis, object storage reachability; `503` if any critical dependency is down; public, no detail leakage |
| `GET /meta/config` | Client-relevant configuration |

`GET /meta/config` →
```json
{
  "api_version": "v1",
  "pipeline_version": "1.0.3",
  "limits": {
    "max_upload_bytes": 209715200,
    "max_rows": 5000000,
    "max_columns": 500,
    "supported_file_types": ["CSV", "XLSX", "JSON"],
    "max_active_runs": 2,
    "sql_max_result_rows": 10000
  },
  "features": { "ai_enabled": true, "google_oauth": true, "ask_your_data": false },
  "domains": [{ "key": "retail", "label": "Retail / E-Commerce", "available": true }],
  "thresholds_defaults": { "missingness": { "low": 5, "moderate": 20, "high": 50 } },
  "enums": { "semantic_roles": ["CUSTOMER_ID", "…"], "column_types": ["INTEGER", "…"] }
}
```

---

## 7.2 Dashboard (PRD §14)

| Method & Path | Description |
|---|---|
| `GET /dashboard/summary` | Overview metrics + recent projects |
| `GET /dashboard/activity?limit=20` | Recent activity feed (from audit events, user-facing subset) |

`GET /dashboard/summary` → `200`
```json
{
  "totals": {
    "projects": 6,
    "datasets": 7,
    "completed_analyses": 5,
    "reports_generated": 3,
    "insights_generated": 41
  },
  "recent_projects": [
    {
      "id": "…",
      "name": "Retail Sales Analysis",
      "dataset_name": "retail_sales.csv",
      "status": "COMPLETED",
      "updated_at": "2026-10-03T14:30:00Z",
      "analysis": { "run_id": "…", "status": "COMPLETED", "progress_pct": 100 }
    }
  ],
  "quick_actions": ["NEW_ANALYSIS", "UPLOAD_DATASET", "VIEW_REPORTS"]
}
```

---

## 7.3 Projects (PRD §15–16, §100, §108)

`Project` object:
```json
{
  "id": "…",
  "name": "Retail Sales Analysis",
  "description": "Analysis of customer purchasing behavior and sales performance.",
  "domain_key": "retail",
  "currency": "INR",
  "status": "COMPLETED",
  "settings": { "auto_run": true, "llm_enabled": true, "default_time_grain": "MONTH" },
  "active_dataset_id": "…",
  "latest_run": { "id": "…", "status": "COMPLETED", "finished_at": "…" },
  "counts": { "datasets": 1, "runs": 3, "reports": 2 },
  "archived_at": null,
  "created_at": "…",
  "updated_at": "…",
  "etag": "W/\"7\""
}
```

| Method & Path | Description | Notes |
|---|---|---|
| `POST /projects` | Create project | Body: `name` (3–80), `description?` (≤ 500), `currency?` (ISO 4217, default `INR`), `domain_key?` (default `retail`), `settings?`. `201` + `Location`. Errors: `PROJECT_NAME_TAKEN`, `VALIDATION_ERROR` |
| `GET /projects` | List projects | Filters: `status`, `q`, `include_archived` (default false). Sort: `updated_at`, `created_at`, `name`. Default `-updated_at` |
| `GET /projects/{id}` | Get project | Returns `ETag` |
| `PATCH /projects/{id}` | Update `name`, `description`, `currency`, `settings`, `active_dataset_id` | Requires `If-Match`. Changing `currency` affects display metadata; a new run is required to re-derive currency-bound metrics |
| `POST /projects/{id}/archive` | Archive (`status=ARCHIVED`) | `200`; blocks new runs/uploads (`PROJECT_ARCHIVED`) |
| `POST /projects/{id}/unarchive` | Unarchive | `200` |
| `DELETE /projects/{id}` | **Soft delete** (PRD §108) | Requires `If-Match` and body `{ "confirm_name": "<exact project name>" }` → `202`; `purge_after` set; returns `{ "deleted_at", "purge_after" }` |
| `POST /projects/{id}/restore` | Restore within the grace period | `200`; after purge → `404` |
| `GET /projects/{id}/overview` | Aggregated overview for the Project Overview page | See below |

`GET /projects/{id}/overview` → `200`:
```json
{
  "project": { "…": "Project" },
  "dataset": { "id": "…", "original_filename": "retail_sales.csv", "status": "READY", "row_count": 125106, "column_count": 18 },
  "active_version": { "id": "…", "version_number": 2, "kind": "CLEANED", "label": "After cleaning" },
  "latest_run": { "…": "AnalysisRun with stages[]" },
  "kpis": [
    { "metric_id": "…", "metric_name": "total_revenue", "value": "8420312.4839200000", "value_f64": 8420312.48392, "unit": "currency", "currency": "INR", "delta": { "period": "PREVIOUS_PERIOD", "ratio_change": 0.082, "state": "AVAILABLE" } }
  ],
  "quality_score": { "overall": 87.0, "completeness": 91.0, "consistency": 94.0, "validity": 96.0, "uniqueness": 78.0 },
  "modules": [
    { "module": "SALES", "state": "AVAILABLE" },
    { "module": "CUSTOMERS", "state": "UNAVAILABLE", "reason": "No customer identifier was detected in this dataset.", "missing_roles": ["CUSTOMER_ID"] }
  ],
  "top_insights": [ { "…": "InsightSummary" } ],
  "artifacts": { "reports": [ … ], "presentations": [ … ], "powerbi": { … }, "exports": [ … ] }
}
```
KPIs and scores are **read from persisted metrics/quality reports** — the overview never computes anything (PRD §60).

---

## 7.4 Datasets and uploads (PRD §17–20, §68, §101)

`Dataset` object:
```json
{
  "id": "…",
  "project_id": "…",
  "original_filename": "retail_sales.csv",
  "file_type": "CSV",
  "mime_type": "text/csv",
  "file_size_bytes": 48211934,
  "checksum_sha256": "sha256:3f9a…c21",
  "status": "READY",
  "row_count": 125430,
  "column_count": 18,
  "validation": { "state": "VALID", "error_code": null, "details": null },
  "latest_version": { "id": "…", "version_number": 2, "kind": "CLEANED" },
  "upload_completed_at": "…",
  "created_at": "…",
  "updated_at": "…"
}
```

### Upload flow (direct-to-object-storage; `ARCHITECTURE.md` §10.2)

```text
1) POST /projects/{id}/datasets              → creates dataset (UPLOADED) + presigned upload instructions
2) Browser PUTs bytes directly to object storage (progress tracked client-side)
3) POST /datasets/{id}/finalize              → API verifies, enqueues ingest (VALIDATING)
4) Observe via GET /datasets/{id} (poll) or run events if auto_run → VALID → READY
```

#### `POST /projects/{project_id}/datasets` ★ — initiate upload
Request:
```json
{
  "filename": "retail_sales.csv",
  "file_size_bytes": 48211934,
  "file_type": "CSV",
  "content_type": "text/csv",
  "checksum_sha256": "sha256:3f9a…c21"
}
```
Validation: extension ∈ {`.csv`, `.xlsx`, `.json`} and consistent with `file_type`; size ≤ `MAX_UPLOAD_BYTES`; filename sanitized (stored only as display text; storage key is server-generated); `checksum_sha256` optional but recommended (verified at finalize).
Response `201`:
```json
{
  "dataset": { "…": "Dataset (status UPLOADED)" },
  "upload": {
    "strategy": "MULTIPART",
    "upload_id": "…",
    "part_size_bytes": 16777216,
    "parts": [
      { "part_number": 1, "url": "https://storage.example/…?X-Amz-Signature=…", "expires_at": "…" }
    ],
    "expires_at": "2026-10-03T15:30:00Z"
  }
}
```
`strategy` is `SINGLE` (one presigned `PUT`, files ≤ part size) or `MULTIPART`. For multipart, additional part URLs for resuming: `POST /datasets/{id}/upload/parts` `{ "part_numbers": [4,5] }` → `{ "parts": [ … ] }`.
Errors: `DATASET_FILE_TYPE_UNSUPPORTED`, `DATASET_TOO_LARGE`, `PROJECT_ARCHIVED`, `VALIDATION_ERROR`.

#### `POST /datasets/{dataset_id}/finalize` ★ — complete upload
Request (multipart): `{ "parts": [ { "part_number": 1, "etag": "…" } ] }`; (single): `{}`.
Behavior: verifies the object exists, size matches, SHA-256 matches (if declared; otherwise computed), then sets `status=VALIDATING` and enqueues the ingest job.
Response `202`: `Dataset` (status `VALIDATING`) with `links.self`.
Errors: `DATASET_UPLOAD_INCOMPLETE`, `DATASET_CHECKSUM_MISMATCH`, `NOT_FOUND`.

Ingest outcomes (visible by polling `GET /datasets/{id}` — `Prefer: wait` supported):
- `VALID` → metadata (rows/cols) populated, dataset version 1 created, then `READY` (profiling done) or processing if `auto_run`.
- `INVALID` → `validation.error_code` ∈ {`DATASET_EMPTY`, `DATASET_INVALID_STRUCTURE`, `DATASET_ENCODING_UNSUPPORTED`, `DATASET_CORRUPT`, `DATASET_UNSAFE_CONTENT`, `DATASET_TOO_MANY_ROWS`, `DATASET_TOO_MANY_COLUMNS`} with sanitized `details`. Invalid files never enter the analytics pipeline (PRD §18).

#### `DELETE /datasets/{dataset_id}/upload` — abort an in-progress upload
Aborts multipart upload and removes the pending dataset row. `204`.

### Dataset reads and deletion

| Method & Path | Description |
|---|---|
| `GET /projects/{project_id}/datasets` | Datasets of a project (filters: `status`) |
| `GET /datasets` | Cross-project dataset list (global "Datasets" page); filters: `project_id`, `status`, `q`, `file_type`; sort: `created_at`, `original_filename`, `row_count` |
| `GET /datasets/{id}` | Dataset detail |
| `GET /datasets/{id}/dependencies` | Dependents that would be affected by deletion: `{ "analysis_runs": [..], "reports": [..], "presentations": [..], "exports": [..] }` (PRD §109) |
| `DELETE /datasets/{id}` | Delete dataset. If dependents exist → `409 DATASET_HAS_DEPENDENTS` with `details` listing them. Pass `?cascade=true` with body `{ "confirm_filename": "<name>" }` to explicitly delete dependents too (`202`) |

---

## 7.5 Dataset versions, preview, profile, schema, lineage (PRD §20–23, §29–30, §118)

`DatasetVersion` object:
```json
{
  "id": "…",
  "dataset_id": "…",
  "version_number": 2,
  "kind": "CLEANED",
  "label": "After cleaning",
  "parent_version_id": "…",
  "row_count": 125106,
  "column_count": 18,
  "size_bytes": 12900332,
  "content_sha256": "sha256:9c1d…e07",
  "immutable": true,
  "operation_set_id": "…",
  "created_at": "…"
}
```
(`immutable` is `true` for every version; the UI uses it to render the lock on the original.)

| Method & Path | Description |
|---|---|
| `GET /datasets/{dataset_id}/versions` | Ordered versions (newest first) |
| `GET /dataset-versions/{version_id}` | Version detail |
| `GET /dataset-versions/{version_id}/lineage` | Lineage graph: nodes (versions, operation sets, runs) + edges: `Original → Version 1 → Cleaning → Version 2 → Transformation → Version 3 → Analysis` |
| `GET /dataset-versions/{version_id}/profile` | Dataset-level profile (rows, columns, duplicates, missing cells/%, memory) |
| `GET /dataset-versions/{version_id}/columns` | Column schema + stats + semantic mapping |
| `GET /dataset-versions/{version_id}/preview` | Limited row preview (below) |
| `PUT /dataset-versions/{version_id}/mapping` | Replace semantic mapping (below) |
| `PATCH /dataset-versions/{version_id}/columns/{column_id}` | Update a single column's role |

### `GET /dataset-versions/{version_id}/columns`
```json
{
  "items": [
    {
      "id": "…", "ordinal": 3, "name": "revenue", "original_name": "Revenue (INR)",
      "detected_type": "FLOAT",
      "semantic": { "role": "REVENUE", "confidence": 0.97, "source": "RULE", "validated": true },
      "is_pii_suspected": false,
      "stats": {
        "null_count": 0, "null_pct": 0.0, "unique_count": 18211, "unique_pct": 14.56,
        "min": "10.0", "max": "98500.0", "mean": "67.2", "median": "54.0", "std": "112.9",
        "percentiles": { "p25": "29.0", "p75": "88.0", "p95": "210.0" }
      }
    }
  ],
  "page": { "limit": 100, "next_cursor": null, "has_more": false }
}
```
Stats numbers are decimal strings (§2.3). Filters: `type`, `role`, `q`. Sort: `ordinal` (default), `name`, `null_pct`, `unique_pct`.

### `GET /dataset-versions/{version_id}/preview` (PRD §20)
Query: `limit` (≤ 200, default 50), `cursor`, `columns`, `sort` (single column, server-side, only on columns in the schema), `filter[column]=value` (equality/`contains` on string columns, documented operators). **Total rows accessible via preview are capped (default 1,000)**; beyond that → `422 VALIDATION_ERROR` with `issue: preview_limit`. The whole dataset is never returned.
```json
{
  "columns": [ { "name": "customer_id", "detected_type": "IDENTIFIER" }, { "name": "revenue", "detected_type": "FLOAT" } ],
  "rows": [ { "customer_id": "C-10021", "revenue": "129.50" }, { "customer_id": "C-10022", "revenue": null } ],
  "page": { "limit": 50, "next_cursor": "…", "has_more": true, "total": 125106 },
  "truncated": false
}
```
Values are JSON strings for decimals/dates/IDs, native booleans, and `null` for missing. PII-suspected columns may be masked if the project/user setting `mask_pii_preview` is on (`masked: true` in column metadata).

### `PUT /dataset-versions/{version_id}/mapping` (PRD §23)
Replace or confirm the semantic mapping. Requires `If-Match` (mapping ETag from the columns list).
```json
{
  "mappings": [
    { "column_id": "…", "role": "REVENUE" },
    { "column_id": "…", "role": "CUSTOMER_ID" },
    { "column_id": "…", "role": "UNKNOWN" }
  ]
}
```
Validation: each role at most once (except `UNKNOWN`); role compatible with detected type (e.g., `PURCHASE_DATE` requires `DATE`/`DATETIME` or parsable text; `REVENUE` numeric).
Response `200`:
```json
{
  "mapping_hash": "sha256:7ab…",
  "changed": true,
  "columns": [ { "…": "Column" } ],
  "module_availability_preview": [
    { "module": "RFM", "state": "AVAILABLE" },
    { "module": "LOYALTY", "state": "UNAVAILABLE", "reason": "A transaction date is required.", "missing_roles": ["PURCHASE_DATE"] }
  ],
  "requires_new_run": true
}
```
Changing the mapping **does not mutate past runs**; it changes the `mapping_hash`, so the next run gets a new `run_key` (`DATABASE.md` §6.3). `module_availability_preview` is computed deterministically from the mapping, helping the UI explain consequences before the user starts a run.
Errors: `MAPPING_INVALID`, `MAPPING_ROLE_DUPLICATE`, `PRECONDITION_FAILED`.

`PATCH …/columns/{column_id}` accepts `{ "role": "…" }` with the same validations; equivalent to a single-item mapping update.

---

## 7.6 Cleaning and preparation (PRD §27–30)

Cleaning **never modifies the source version**. Applying operations produces a **new version** (PRD §29–30).

`CleaningOperationType`: `REMOVE_EXACT_DUPLICATES`, `STANDARDIZE_TYPES`, `NORMALIZE_CATEGORIES`, `HANDLE_MISSING`, `PARSE_DATES`, `REMOVE_INVALID_RECORDS`, `NORMALIZE_TEXT`, `STANDARDIZE_NUMERICS`.

| Method & Path | Description |
|---|---|
| `GET /dataset-versions/{id}/cleaning/recommendations` | System-suggested operations derived from quality findings, each with expected impact counts |
| `POST /dataset-versions/{id}/cleaning/preview` | Dry-run impact for a proposed operation list (no version created) |
| `POST /dataset-versions/{id}/cleaning` ★ | Apply operations → creates an operation set and, on success, a new version |
| `GET /dataset-versions/{id}/cleaning-operations` | Cleaning log for operations that produced this version (and its ancestors via `?include_ancestors=true`) |
| `GET /cleaning-operation-sets/{set_id}` | Operation set detail/status |

Request (preview/apply):
```json
{
  "operations": [
    { "type": "REMOVE_EXACT_DUPLICATES", "parameters": {} },
    { "type": "HANDLE_MISSING", "target_columns": ["customer_age"], "parameters": { "strategy": "FLAG_ONLY" } },
    { "type": "PARSE_DATES", "target_columns": ["purchase_date"], "parameters": { "formats": ["%d/%m/%Y"], "time_zone": "UTC" } }
  ],
  "label": "After cleaning"
}
```
Preview response `200`:
```json
{
  "operations": [
    { "seq": 1, "type": "REMOVE_EXACT_DUPLICATES", "rows_before": 125430, "rows_after": 125106, "rows_affected": 324, "reason": "Exact duplicate records" },
    { "seq": 2, "type": "HANDLE_MISSING", "rows_before": 125106, "rows_after": 125106, "rows_affected": 421, "reason": "Missing customer_age flagged; no values changed" }
  ],
  "would_create_version": true
}
```
Apply response `202`: `{ "operation_set": { "id": "…", "status": "RUNNING", "source_version_id": "…", "config_hash": "sha256:…", "links": { … } } }` → on success status `COMMITTED` with `result_version_id`.
Idempotent: the same source version + same operation config returns the existing set (`Idempotent-Replay: true`).
Errors: `CLEANING_OPERATION_INVALID`, `CLEANING_CONFLICT`, `CLEANING_NO_EFFECT`, `DATASET_NOT_READY`.

`CleaningOperation` log entry (PRD §28):
```json
{
  "id": "…", "seq": 1, "type": "REMOVE_EXACT_DUPLICATES",
  "target_columns": [], "parameters": {},
  "rows_before": 125430, "rows_after": 125106, "rows_affected": 324,
  "reason": "Exact duplicate records",
  "performed_at": "2026-10-03T14:20:41Z"
}
```

Outliers and near-duplicates are **flagged, never auto-removed** (PRD §26, §35). A user action "Exclude from analysis" is expressed as a cleaning operation (`REMOVE_INVALID_RECORDS` with `rule: "OUTLIER_FLAGGED"` and explicit confirmation), which creates a new version.

---

## 7.7 Analysis runs (PRD §61–66, §95, §102–104)

`AnalysisRun` object:
```json
{
  "id": "…",
  "project_id": "…",
  "dataset_version_id": "…",
  "run_key": "sha256:5de…",
  "domain_key": "retail",
  "pipeline_version": "1.0.3",
  "config_hash": "sha256:11a…",
  "mapping_hash": "sha256:7ab…",
  "status": "RUNNING",
  "pipeline_state": "SQL_ANALYSIS",
  "progress_pct": 62.0,
  "stages": [
    { "stage": "VALIDATING", "status": "COMPLETED", "duration_ms": 820, "attempt": 1 },
    { "stage": "PROFILING", "status": "COMPLETED", "duration_ms": 4120, "attempt": 1 },
    { "stage": "SQL_ANALYSIS", "status": "RUNNING", "attempt": 1 },
    { "stage": "INSIGHT_GENERATION", "status": "PENDING" }
  ],
  "modules": [ { "module": "SALES", "state": "AVAILABLE" } ],
  "error": null,
  "queued_at": "…", "started_at": "…", "finished_at": null,
  "links": { "self": "…", "events": "…" }
}
```
`stages[]` always lists the full ordered stage set so the UI can render the stepper (`DESIGN.md` §4.10). `pipeline_state` follows PRD §61 exactly.

| Method & Path | Description |
|---|---|
| `POST /projects/{project_id}/analysis-runs` ★ | Start (or return the existing identical) run |
| `GET /projects/{project_id}/analysis-runs` | List runs for a project (filters `status`; sort `-created_at`) |
| `GET /analysis-runs` | Cross-project list (global "Analysis" page); filters: `project_id`, `status` |
| `GET /analysis-runs/{id}` | Detail incl. `stages[]` and `modules[]`; supports `ETag`/`If-None-Match` and `Prefer: wait` |
| `GET /analysis-runs/{id}/stages` | Stage records with `counts`, `warnings`, `error`, `duration_ms` (log view) |
| `GET /analysis-runs/{id}/modules` | `module_availability` records (state/reason/required/missing roles) |
| `GET /analysis-runs/{id}/events` | SSE stream (§6.3) |
| `POST /analysis-runs/{id}/cancel` | Request cancellation → `202` |
| `POST /analysis-runs/{id}/retry` | Retry from first incomplete stage → `202` (`RUN_NOT_RETRYABLE` if not `FAILED`/`CANCELLED`) |

### `POST /projects/{project_id}/analysis-runs` ★
Request (all optional except as noted):
```json
{
  "dataset_version_id": "…",
  "config": {
    "modules": ["SALES", "CUSTOMERS", "PRODUCTS", "RFM", "SEGMENTATION", "DISCOUNT", "PAYMENT", "GEOGRAPHY", "TIME"],
    "thresholds": { "missingness": { "low": 5, "moderate": 20, "high": 50 } },
    "rfm": { "bins": 5, "reference_date": "AUTO" },
    "time": { "time_zone": "UTC", "default_grain": "MONTH" }
  },
  "generate": { "powerbi": true, "report_formats": [], "presentation": false }
}
```
- `dataset_version_id` defaults to the project's active dataset's **latest version**.
- The server computes `config_hash`, `mapping_hash`, and `run_key = sha256(version ‖ config_hash ‖ pipeline_version ‖ domain ‖ mapping_hash)`.
- **New run** → `201` + `Location`, status `QUEUED`. **Identical live/completed run** → `200` + `Idempotent-Replay: true` returning the existing run.
- Unknown modules or modules unsupported by the domain → `422 VALIDATION_ERROR`. Modules whose prerequisites are missing are **not an error**: they appear later as `UNAVAILABLE` with reasons.
- Errors: `DATASET_NOT_READY`, `PROJECT_ARCHIVED`, `RUN_LIMIT_REACHED`, `VERSION_NOT_FOUND`.

Partial analysis (PRD §65): the run completes with `status = COMPLETED` even if some modules are `UNAVAILABLE`. The run is `FAILED` only for structural failures (e.g., unreadable dataset version) or stage failures that block all downstream work; module-level failures are `FAILED` module states (retryable) while the run may still be `COMPLETED` with `warnings`.

---

## 7.8 Data quality (PRD §24–26, §35, §117)

| Method & Path | Description |
|---|---|
| `GET /analysis-runs/{id}/quality` | Quality report summary |
| `GET /analysis-runs/{id}/quality/issues` | Paginated issues (filters: `type`, `severity`, `handling`, `column`; sort: `severity`, `affected_rows`) |
| `GET /analysis-runs/{id}/quality/issues/{issue_id}/records` | Sample of affected records (paginated, capped; masked for PII-suspected columns when configured) |
| `GET /analysis-runs/{id}/quality/missingness` | Per-column missingness table + pattern matrix data for the heatmap |

`GET /analysis-runs/{id}/quality` →
```json
{
  "run_id": "…",
  "dataset_version_id": "…",
  "overall_score": 87.0,
  "dimensions": {
    "completeness": { "score": 91.0, "weight": 0.30, "description": "Share of non-missing values across relevant columns." },
    "consistency":  { "score": 94.0, "weight": 0.20, "description": "…" },
    "validity":     { "score": 96.0, "weight": 0.25, "description": "…" },
    "uniqueness":   { "score": 78.0, "weight": 0.25, "description": "…" }
  },
  "accuracy_indicators": { "negative_revenue_rows": 0, "future_date_rows": 12 },
  "methodology_version": "1.0",
  "methodology_url": "/docs/analytics-spec#data-quality-score",
  "thresholds": { "low": 5, "moderate": 20, "high": 50 },
  "summary": {
    "missing_cells": 18211, "missing_pct": 0.81, "exact_duplicate_rows": 324,
    "duplicate_identifier_columns": ["transaction_id"], "outlier_columns": 3
  },
  "created_at": "…"
}
```
(The score is explainable: dimensions, weights, and methodology version are returned — PRD §24.)

`QualityIssue`:
```json
{
  "id": "…",
  "type": "EXACT_DUPLICATES",
  "severity": null,
  "column": null,
  "affected_rows": 324,
  "affected_pct": 0.2583,
  "what_was_wrong": "324 rows were exact duplicates of other rows.",
  "what_changed": "Removed in version 2 (Duplicate Removal).",
  "why": "Duplicated rows inflate revenue and order counts.",
  "handling": "REMOVED",
  "method": "EXACT",
  "has_sample": true
}
```
Missing-value severity bands (configurable): `LOW 0–5%`, `MODERATE 5–20%`, `HIGH 20–50%`, `CRITICAL >50%` (PRD §25). `handling` ∈ `DETECTED | FLAGGED | REMOVED` (PRD §26).

---

## 7.9 Exploratory data analysis (PRD §31–35)

| Method & Path | Description |
|---|---|
| `GET /analysis-runs/{id}/eda` | EDA index: available sections and results (summaries + chart specs), plus skipped items with reasons. Filters: `section` ∈ `NUMERICAL, CATEGORICAL, TIME, CORRELATION, OUTLIERS`, `column`, `q` |
| `GET /analysis-runs/{id}/eda/{result_id}` | One result with its chart-ready data (aggregated, ≤ 1,000 points) |
| `GET /analysis-runs/{id}/eda/correlation` | Correlation matrix; `?method=PEARSON|SPEARMAN` |
| `GET /analysis-runs/{id}/eda/time` | Time series; `?grain=DAY|WEEK|MONTH|YEAR&metric=revenue` |

Example `EdaResult`:
```json
{
  "id": "…",
  "section": "TIME",
  "result_key": "revenue_by_month",
  "state": "AVAILABLE",
  "summary": { "points": 24, "min": "812340.12", "max": "1420033.90" },
  "chart": {
    "type": "LINE",
    "title": "Monthly revenue",
    "x": { "field": "month", "label": "Month", "type": "TIME" },
    "y": { "field": "revenue", "label": "Revenue", "unit": "currency", "currency": "INR" },
    "grain": "MONTH",
    "aggregation": "SUM",
    "series": [ { "name": "Revenue", "points": [ { "x": "2025-01", "y": "812340.12" } ] } ],
    "notes": ["2 months contain no data and are shown as gaps."]
  },
  "evidence": { "metric_ids": ["…"] }
}
```
- `chart.series` values are decimal strings; `y` may be `null` for gaps (never interpolated).
- Charts not generated because they would be meaningless appear with `state: "SKIPPED"` and a `reason` (PRD §32).
- Correlation responses always include `"interpretation": "ASSOCIATION_NOT_CAUSATION"` (PRD §34) and the method used. Pairs with insufficient data are `null` with a reason.

---

## 7.10 Metrics and evidence (PRD §49–51, §60, §96)

`Metric` object:
```json
{
  "id": "…",
  "run_id": "…",
  "module": "SALES",
  "metric_name": "total_revenue",
  "dimensions": {},
  "value": "8420312.4839200000",
  "value_f64": 8420312.48392,
  "unit": "currency",
  "currency": "INR",
  "source": "transactions",
  "calculation": "SUM(revenue)",
  "sql_query_id": "…",
  "dataset_version_id": "…",
  "pipeline_version": "1.0.3",
  "config_hash": "sha256:11a…",
  "computed_at": "2026-10-03T14:22:11Z"
}
```

| Method & Path | Description |
|---|---|
| `GET /analysis-runs/{id}/metrics` | List metrics. Filters: `module`, `metric_name` (comma-separated), `dimension.<key>=<value>`. Sort: `metric_name`, `computed_at`. Cap: 200/page |
| `GET /metrics/{metric_id}` | Single metric |
| `GET /metrics/{metric_id}/evidence` | **Evidence bundle** for the UI's Evidence Drawer (`DESIGN.md` §4.15) |
| `GET /analysis-runs/{id}/metrics/series` | Metric series for charts: `?metric_name=…&dimension=category&top=10` (aggregated, ≤ 1,000 points; includes "Other" bucket) |

`GET /metrics/{id}/evidence` → `200`:
```json
{
  "metric": { "…": "Metric" },
  "dataset_version": { "id": "…", "version_number": 2, "label": "After cleaning", "content_sha256": "sha256:9c1d…e07" },
  "run": { "id": "…", "pipeline_version": "1.0.3", "config_hash": "sha256:11a…", "finished_at": "…" },
  "calculation": "SUM(revenue)",
  "sql": {
    "id": "…",
    "text": "SELECT SUM(revenue) AS total_revenue FROM transactions;",
    "status": "SUCCEEDED",
    "duration_ms": 41,
    "result_preview": { "columns": ["total_revenue"], "rows": [["8420312.48392"]] }
  },
  "used_by": { "insights": [ { "id": "…", "title": "…" } ], "reports": [ { "id": "…" } ] },
  "reproduce": { "sql_query_id": "…", "open_in_sql_path": "/projects/{id}/sql?query=…" }
}
```

---

## 7.11 Business analytics views (PRD §36–45, §65)

Convenience read endpoints that assemble **already-persisted metrics and series** for module pages. They compute nothing.

| Method & Path | Page |
|---|---|
| `GET /analysis-runs/{id}/analytics/sales` | Sales KPIs, revenue trend, growth |
| `GET /analysis-runs/{id}/analytics/customers` | Customer KPIs, new vs returning, repeat rate |
| `GET /analysis-runs/{id}/analytics/customers/segments` | Segment table + segmentation rules + share charts |
| `GET /analysis-runs/{id}/analytics/customers/rfm` | RFM distributions + heatmap data + segment mapping |
| `GET /analysis-runs/{id}/analytics/customers/rfm/table` | Paginated customer-level RFM table (from derived results) |
| `GET /analysis-runs/{id}/analytics/products` | Top/bottom products, category contribution, Pareto |
| `GET /analysis-runs/{id}/analytics/products/table` | Paginated product table |
| `GET /analysis-runs/{id}/analytics/discount` | Discount-level analysis (association only) |
| `GET /analysis-runs/{id}/analytics/payment` | Payment method analysis |
| `GET /analysis-runs/{id}/analytics/geography` | Country/state/city breakdowns |
| `GET /analysis-runs/{id}/analytics/time` | Daily/weekly/monthly/yearly series, MoM/YoY growth |

Uniform envelope:
```json
{
  "module": "CUSTOMERS",
  "availability": {
    "state": "UNAVAILABLE",
    "reason": "No customer identifier was detected in this dataset.",
    "required_roles": ["CUSTOMER_ID"],
    "missing_roles": ["CUSTOMER_ID"],
    "remedies": ["REVIEW_COLUMN_MAPPING", "UPLOAD_DIFFERENT_DATASET"]
  },
  "kpis": [],
  "charts": [],
  "tables": [],
  "notes": []
}
```
- `availability.state` ∈ `AVAILABLE | UNAVAILABLE | PROCESSING | FAILED` (PRD §66). The endpoint returns **`200`** in all four cases so the UI can render the proper state; `kpis/charts/tables` are empty unless `AVAILABLE` (or partially available, with `notes`).
- Individual KPIs may themselves be unavailable: `{ "metric_name": "yoy_growth", "state": "UNAVAILABLE", "reason": "Fewer than 24 months of data." }`.
- Segment responses include the **rule definitions** (`segmentation_rules_version`, text) and the fixed disclaimer `"classification": "RULE_BASED"` (PRD §39).
- Discount/correlation-like responses include `"interpretation": "ASSOCIATION_NOT_CAUSATION"` (PRD §42).
- Table endpoints support `limit/cursor/sort/filter` and return `page`.

Representative segments response:
```json
{
  "module": "SEGMENTATION",
  "availability": { "state": "AVAILABLE" },
  "classification": "RULE_BASED",
  "segmentation_rules_version": "1",
  "rules": [
    { "segment": "HIGH_VALUE", "label": "High Value", "definition": "Customers in the top revenue tier per documented rule." }
  ],
  "kpis": [],
  "tables": [
    {
      "key": "segment_summary",
      "columns": ["segment", "customers", "customer_share_pct", "revenue", "revenue_share_pct", "aov"],
      "rows": [
        { "segment": "HIGH_VALUE", "customers": 3120, "customer_share_pct": "18.0", "revenue": "4353840.12", "revenue_share_pct": "51.7", "aov": "1395.46", "metric_ids": ["…"] }
      ]
    }
  ],
  "charts": [ { "type": "DONUT", "title": "Customers by segment", "series": [ … ] } ]
}
```
Every displayed figure includes `metric_ids` (or a `metric_id`) so the UI can open evidence.

---

## 7.12 SQL analytics (PRD §46–48)

SQL always executes in the **sandboxed, read-only analytical environment** against a specific dataset version (`ARCHITECTURE.md` §10.5). The API never exposes application tables.

| Method & Path | Description |
|---|---|
| `GET /analysis-runs/{id}/sql/questions` | Question library for the run's domain, grouped by category (Sales, Customers, Products, Categories, Time, Geography, Loyalty, Purchase behavior), each with availability and the generated SQL |
| `POST /projects/{project_id}/sql/execute` | Execute a template question or custom SQL (async) |
| `GET /sql-queries/{id}` | Query status/metadata/result preview |
| `GET /sql-queries/{id}/result` | Paginated result rows |
| `POST /sql-queries/{id}/cancel` | Cancel a running query |
| `GET /projects/{project_id}/sql-queries` | History (filters: `status`, `origin`, `category`, `q`; sort `-created_at`) |
| `POST /sql/validate` | Validate SQL without executing; returns pass/fail with reasons |
| `GET /dataset-versions/{id}/sql/schema` | Allow-listed relations/columns/types available to SQL for that version (for editor autocomplete and docs) |

### `POST /projects/{project_id}/sql/execute`
```json
{
  "dataset_version_id": "…",
  "question_key": "top_customers_by_revenue",
  "parameters": { "limit": 10 }
}
```
or custom:
```json
{
  "dataset_version_id": "…",
  "sql": "SELECT customer_id, SUM(revenue) AS total_revenue FROM transactions GROUP BY customer_id ORDER BY total_revenue DESC LIMIT 10",
  "question": "Which customers generate the most revenue?"
}
```
Exactly one of `question_key` or `sql`. `parameters` are bound as **query parameters**, never string-interpolated.
Response: `202` with `SqlQuery` (`status: QUEUED/RUNNING`); supports `Prefer: wait=5` → `200` with a completed query.

`SqlQuery` object (PRD §47 UI fields: Question, Generated SQL, Execution status, Result table, Execution time):
```json
{
  "id": "…",
  "project_id": "…",
  "dataset_version_id": "…",
  "origin": "USER",
  "category": "Customers",
  "question": "Which customers generate the most revenue?",
  "sql_text": "SELECT customer_id, …",
  "parameters": {},
  "status": "SUCCEEDED",
  "error": null,
  "row_count": 10,
  "duration_ms": 184,
  "columns": [ { "name": "customer_id", "type": "IDENTIFIER" }, { "name": "total_revenue", "type": "NUMERIC" } ],
  "result_preview": { "rows": [ [ "C-10021", "82000.00" ] ], "truncated": false },
  "result_expires_at": "2026-10-04T14:30:00Z",
  "executed_at": "…",
  "chart_suggestion": { "type": "BAR", "x": "customer_id", "y": "total_revenue", "reason": "Category × numeric" }
}
```
`status` ∈ `PENDING, RUNNING, SUCCEEDED, FAILED, REJECTED, TIMED_OUT`.

Safety behavior (PRD §48):
- Statements must be a **single `SELECT` / `WITH … SELECT`** against allow-listed relations. `DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, CREATE, COPY, ATTACH, INSTALL, LOAD, PRAGMA, SET, CALL, EXPORT`, multi-statement input, file/network table functions, and unknown relations are rejected with `422 SQL_REJECTED`; the rejected attempt is still recorded (`status: REJECTED`) and audited.
- `details[].issue` examples: `not_select`, `multiple_statements`, `forbidden_keyword`, `unknown_relation`, `forbidden_function`, `too_long`.
- Resource limits: timeout (default 30 s → `SQL_TIMEOUT`), result cap (default 10,000 rows; `truncated: true` beyond), per-user concurrency.
- `POST /sql/validate` (`{ "sql": "…" }`) → `200 { "valid": false, "issues": [ { "issue": "forbidden_keyword", "keyword": "DELETE", "position": 0 } ] }`; validation here is advisory — **execution re-validates server-side**.

Result pagination: `GET /sql-queries/{id}/result?limit=200&cursor=…&sort=total_revenue:desc` →
```json
{
  "columns": [ … ],
  "rows": [ [ "C-10021", "82000.00" ] ],
  "page": { "limit": 200, "next_cursor": null, "has_more": false, "total": 10 }
}
```
Expired cached results → `410 SQL_RESULT_EXPIRED` (re-run).

---

## 7.13 Insights and recommendations (PRD §50–52, §92–93)

`Insight` object:
```json
{
  "id": "…",
  "run_id": "…",
  "theme": "CUSTOMERS",
  "rule_key": "high_value_revenue_concentration",
  "title": "High-value customers drive a large share of revenue",
  "description": "High-value customers contribute 51.7% of total revenue while representing 18.0% of customers.",
  "segments": [
    { "type": "TEXT", "text": "High-value customers contribute " },
    { "type": "METRIC_REF", "metric_id": "…", "display_value": "51.7%", "label": "Revenue share" },
    { "type": "TEXT", "text": " of total revenue while representing " },
    { "type": "METRIC_REF", "metric_id": "…", "display_value": "18.0%", "label": "Customer share" },
    { "type": "TEXT", "text": " of customers." }
  ],
  "evidence": [
    { "metric_id": "…", "label": "Revenue contribution", "display_value": "51.7%" },
    { "metric_id": "…", "label": "Customer share", "display_value": "18.0%" }
  ],
  "source": "Customer segmentation SQL analysis",
  "supporting_query_id": "…",
  "confidence": "HIGH",
  "confidence_score": 0.91,
  "is_association": false,
  "impact_rank": 1,
  "ai": { "explanation": null, "prompt_version": null },
  "template_version": "1",
  "created_at": "…"
}
```
- `segments[]` is the **render-ready form**: every number is a `METRIC_REF` bound to a metric ID so the client renders `MetricRef` components (`DESIGN.md` §4.15). `description` is the plain-text equivalent.
- Insights are always produced from metrics; there is no endpoint to create free-form insights (PRD §51).

| Method & Path | Description |
|---|---|
| `GET /analysis-runs/{id}/insights` | List. Filters: `theme`, `confidence`, `q`, `is_association`. Sort: `impact_rank` (default), `-confidence_score`, `theme` |
| `GET /insights/{id}` | Detail (includes full evidence + supporting SQL summary) |
| `POST /insights/{id}/explain` | Optional AI explanation (§7.17) |
| `GET /analysis-runs/{id}/recommendations` | List. Filters: `theme`, `priority`, `user_status` |
| `GET /recommendations/{id}` | Detail with linked insights |
| `PATCH /recommendations/{id}` | Update **only** `user_status` ∈ `OPEN, IN_REVIEW, DONE` (workflow metadata; never alters analytics) |

`Recommendation`:
```json
{
  "id": "…",
  "theme": "CUSTOMERS",
  "finding": "High-value customers contribute a large share of revenue.",
  "recommendation": "Investigate retention initiatives for high-value customers.",
  "priority": "HIGH",
  "source_insight_ids": ["…"],
  "evidence": [ { "metric_id": "…", "label": "Revenue contribution", "display_value": "51.7%" } ],
  "caveat": "Suggestion based on observed data; outcomes are not guaranteed.",
  "user_status": "OPEN"
}
```

---

## 7.14 Power BI (PRD §55–57, §9.4)

| Method & Path | Description |
|---|---|
| `POST /analysis-runs/{id}/powerbi` ★ | Generate the Power BI-ready model package (`202`); requires `COMPLETED` run (`RUN_NOT_COMPLETED`) and at least one buildable fact table (`MODULE_UNAVAILABLE` otherwise) |
| `GET /analysis-runs/{id}/powerbi` | Model status + specification (schema, measures, dashboard spec) |
| `POST /powerbi-models/{id}/download-url` | Issue a 5-minute presigned download URL for the package |

`GET /analysis-runs/{id}/powerbi` → `200`:
```json
{
  "id": "…",
  "status": "READY",
  "model_version": "1",
  "schema": {
    "fact": "fact_sales",
    "dimensions": ["dim_customer", "dim_product", "dim_date", "dim_location", "dim_payment"],
    "tables": [ { "name": "fact_sales", "grain": "one row per transaction line", "columns": [ { "name": "revenue", "type": "DECIMAL", "role": "MEASURE_SOURCE" } ] } ],
    "relationships": [ { "from": "fact_sales.customer_key", "to": "dim_customer.customer_key", "cardinality": "MANY_TO_ONE" } ]
  },
  "measures": [
    { "name": "Total Revenue", "dax": "SUM(fact_sales[revenue])", "available": true },
    { "name": "Repeat Customer Rate", "dax": "…", "available": false, "reason": "A customer identifier is required." }
  ],
  "dashboard_spec": {
    "pages": [
      { "number": 1, "title": "Executive Overview", "visuals": [ { "type": "CARD", "measure": "Total Revenue" }, { "type": "LINE", "x": "dim_date[month]", "y": "Total Revenue" } ] }
    ]
  },
  "package": { "size_bytes": 3281933, "generated_at": "…", "expires_at": "…" },
  "import_instructions_path": "/docs/powerbi-import",
  "publishing": { "supported": false, "note": "Direct publishing to Power BI is not available in V1." }
}
```
Unavailable measures/visuals/pages always carry a `reason`; they are never silently dropped.

---

## 7.15 Reports and presentations (PRD §58–60, §94, §105)

`Report`:
```json
{
  "id": "…",
  "run_id": "…",
  "format": "PDF",
  "status": "READY",
  "template_version": "1",
  "sections": ["COVER","EXEC_SUMMARY","DATASET","QUALITY","PREPARATION","EDA","SQL","CUSTOMERS","PRODUCTS","SALES","INSIGHTS","RECOMMENDATIONS","LIMITATIONS","APPENDIX"],
  "unavailable_sections": [ { "section": "CUSTOMERS", "reason": "No customer identifier was detected." } ],
  "size_bytes": 1840221,
  "generated_at": "…",
  "expires_at": "…",
  "error": null
}
```

| Method & Path | Description |
|---|---|
| `GET /analysis-runs/{id}/reports/options` | Selectable sections with availability/reasons and a **Limitations preview** (the relevant limitations that will be included, PRD §94) |
| `POST /analysis-runs/{id}/reports` ★ | Generate a report (`202`). Body: `{ "format": "PDF" \| "DOCX", "sections": [..]? }` (defaults to all available) |
| `GET /projects/{project_id}/reports` | History (filters `format`, `status`) |
| `GET /reports` | Cross-project history (global Reports page) |
| `GET /reports/{id}` | Detail/status (`Prefer: wait`) |
| `POST /reports/{id}/download-url` | Presigned URL (5 min). Audited as `report.downloaded`. `REPORT_NOT_READY`, `ARTIFACT_EXPIRED` |
| `DELETE /reports/{id}` | Delete artifact + row (`204`) |
| `POST /analysis-runs/{id}/presentations` ★ | Generate PPTX (`202`) |
| `GET /projects/{project_id}/presentations`, `GET /presentations/{id}`, `POST /presentations/{id}/download-url`, `DELETE /presentations/{id}` | As reports |

Rules:
- Generation requires `RUN_NOT_COMPLETED` = false (the run must be `COMPLETED`).
- Reports and decks consume **persisted metrics only**; the response for presentations includes the **slide manifest** (`slides[]` with `title` and `metric_ids`) for traceability.
- Idempotent per `(run_id, format, template_version, sections_hash)` (`DATABASE.md` §6.9). Re-requesting returns the existing artifact (`Idempotent-Replay: true`).
- On completion an `artifact.ready` SSE event (if a stream is open) and an in-app notification are produced.

`POST /reports/{id}/download-url` → `200`:
```json
{ "url": "https://storage.example/reports/…?X-Amz-Signature=…", "expires_at": "2026-10-03T14:35:00Z", "filename": "Retail-Sales-Analysis-2026-10-03.pdf", "content_type": "application/pdf" }
```

---

## 7.16 Exports (PRD §107)

| Method & Path | Description |
|---|---|
| `POST /projects/{project_id}/exports` ★ | Request an export (`202`) |
| `GET /projects/{project_id}/exports` | List |
| `GET /exports/{id}` | Status |
| `POST /exports/{id}/download-url` | Presigned download URL |

Body:
```json
{
  "kind": "CLEANED_DATASET",
  "format": "CSV",
  "dataset_version_id": "…"
}
```
Kinds: `CLEANED_DATASET` (`CSV|XLSX|PARQUET`), `ANALYSIS_RESULTS` (`CSV|XLSX|ZIP` of metrics/insights), `SQL_RESULTS` (`{ "sql_query_id": "…" }`, `CSV|XLSX`), `REPORT`, `PRESENTATION`, `POWERBI_MODEL`.
- CSV/XLSX exports neutralize spreadsheet-formula injection (cells beginning with `=`, `+`, `-`, `@` are prefixed) (`ARCHITECTURE.md` §13).
- Exports expire per retention policy; expired → `410 ARTIFACT_EXPIRED`.

---

## 7.17 AI-assisted endpoints (optional; PRD §53–54, §97)

AI endpoints **return explanatory text only**. Numbers in the text are verified against the supplied metrics by the number-verification guard; if verification fails, the response falls back to deterministic template text (`ARCHITECTURE.md` §11.4).

| Method & Path | Description |
|---|---|
| `POST /insights/{id}/explain` | Plain-language explanation of an insight |
| `POST /analysis-runs/{id}/summary` | Executive-summary draft from verified metrics/insights |
| `POST /dataset-versions/{id}/columns/suggest-roles` | LLM-assisted role suggestions for ambiguous columns (suggestions only; validated before use) |
| `POST /projects/{project_id}/ask` | **Reserved (V1.5 — Ask Your Data).** Returns `501 NOT_IMPLEMENTED` until enabled (`features.ask_your_data`) |

`POST /insights/{id}/explain` → `200`:
```json
{
  "insight_id": "…",
  "explanation": "A small group of customers accounts for about half of revenue, which suggests retention efforts for this group may be worth investigating.",
  "ai_assisted": true,
  "source": "LLM",
  "guard": { "verified": true, "numbers_checked": 2, "fallback_used": false },
  "prompt_version": "explain-insight@1"
}
```
- `source` is `LLM` or `TEMPLATE_FALLBACK`; `AI_DISABLED` (`409`) if the project disabled AI; `AI_UNAVAILABLE` (`503`) if the provider is down (clients should show deterministic text).
- AI text is always flagged `ai_assisted: true` for the UI tag (`DESIGN.md` §10).
- No AI endpoint accepts or returns executable SQL/code without passing the standard SQL validator and sandbox.

---

## 7.18 Notifications (PRD §105)

`Notification`: `{ "id", "type", "title", "body", "resource_type", "resource_id", "link_path", "read_at", "created_at" }`; `type` ∈ `ANALYSIS_COMPLETED, REPORT_GENERATED, PROCESSING_FAILED, EXPORT_COMPLETED, SYSTEM`. `link_path` is always an in-app path.

| Method & Path | Description |
|---|---|
| `GET /notifications` | List (`unread_only=true`, pagination) |
| `GET /notifications/unread-count` | `{ "count": 3 }` |
| `POST /notifications/{id}/read` | Mark read (`204`) |
| `POST /notifications/read-all` | Mark all read (`204`) |

---

## 7.19 Settings, retention, audit (PRD §79, §110)

| Method & Path | Description |
|---|---|
| `GET /settings` | Account preferences (`currency`, `table_density`, `notifications`, `mask_pii_preview`, theme) |
| `PATCH /settings` | Update preferences (`If-Match`) |
| `GET /settings/retention` | Effective retention policy per resource kind (user override or system default) |
| `PUT /settings/retention` | Set user overrides: `{ "policies": [ { "resource_kind": "GENERATED_FILE", "retain_days": 30 } ] }` |
| `POST /settings/data-export` | Request export of all user data (`202`, produces an export artifact) |
| `GET /audit-events` | User-visible audit trail (own events only). Filters: `action`, `project_id`, `created_after`, `created_before`. Metadata only; no dataset values (PRD §79) |

---

## 7.20 Search (PRD §106 — P2, route reserved)

`GET /search?q=…&types=projects,datasets,insights,reports` → `200` with grouped, owner-scoped results (trigram on names/titles). Behind feature flag `search_enabled`; otherwise `501 NOT_IMPLEMENTED`.

---

# 8. Representative End-to-End Flow

```text
POST /auth/login                                   → session + csrf_token
POST /projects                                      → 201 Project
POST /projects/{id}/datasets  (Idempotency-Key)     → 201 {dataset, upload}
PUT  <presigned part URLs>  (browser → storage)
POST /datasets/{id}/finalize  (Idempotency-Key)     → 202 Dataset(VALIDATING)
GET  /datasets/{id}  (Prefer: wait=8)               → 200 Dataset(READY)  (profile/columns available)
GET  /dataset-versions/{v}/columns                  → semantic mapping to review
POST /projects/{id}/analysis-runs (Idempotency-Key) → 201 AnalysisRun(QUEUED)
GET  /analysis-runs/{run}/events  (SSE)             → stage.* … run.completed
GET  /analysis-runs/{run}/quality                   → quality score
GET  /analysis-runs/{run}/analytics/sales           → KPIs + charts
GET  /analysis-runs/{run}/insights                  → evidence-backed insights
GET  /metrics/{metric}/evidence                     → metric, SQL, calculation, provenance
POST /analysis-runs/{run}/powerbi (Idempotency-Key) → 202
POST /analysis-runs/{run}/reports (Idempotency-Key) → 202   { "format": "PDF" }
POST /reports/{id}/download-url                     → presigned URL
```

---

# 9. Webhooks and Callbacks

None in V1. Real-time updates use SSE (§6.3). The architecture reserves signed outbound webhooks for a later release; they are not part of this contract.

---

# 10. Security Requirements for the API Layer (PRD §82)

| Control | Requirement |
|---|---|
| Authentication | Cookie session on every non-public route; CSRF token on every state-changing call |
| Authorization | Central policy, owner-scoped repositories, `404` for foreign resources |
| Input validation | Strict Pydantic models (`extra=forbid`), enum validation, length/size limits, normalized emails, sanitized filenames |
| File safety | Extension + magic-byte + MIME consistency; safe parsing with resource limits; `.xlsm` and macro/external-entity content rejected |
| SQL | Parameterized queries; analytical SQL only through the validated sandbox |
| Output safety | JSON only; no HTML rendering of user strings server-side; CSV/XLSX export formula neutralization |
| Secrets | Environment/secret manager only; never returned or logged |
| Logging | `request_id` correlation; no passwords, tokens, raw dataset values, or presigned URLs in logs |
| Errors | Coded, user-safe; no stack traces (`INTERNAL_ERROR` generic) |
| Rate limiting | Per §2.10, with `Retry-After` |
| Transport | TLS, HSTS, secure cookies, strict CSP/headers at the edge |
| Redirects | `redirect_to` validated as an in-app path to prevent open redirects |
| Presigned URLs | Short TTL, issued only after authorization, never persisted in responses of list/detail endpoints |

---

# 11. Observability Contract (PRD §78–79)

- Every response carries `X-Request-ID`; error bodies echo it.
- The API emits structured logs and OpenTelemetry spans for each request (route template, status, latency, user hash, project/run IDs).
- Audit events are written for: `auth.*`, `project.*`, `dataset.*`, `mapping.changed`, `cleaning.operation.performed`, `analysis.*`, `sql.executed|rejected`, `report|presentation|powerbi|export.generated|downloaded`, `settings.changed` (`DATABASE.md` §6.10).
- `Server-Timing` headers may be included in non-production environments.

---

# 12. Testing Requirements (PRD §80)

| Test type | Requirements |
|---|---|
| **Contract tests** | OpenAPI snapshot test fails on unintended change; schema-based fuzzing (e.g., Schemathesis) against every operation; generated TypeScript client must compile |
| **Authorization matrix** | For every owned-resource endpoint × HTTP method: user B gets `404` for user A's IDs; unauthenticated gets `401`; missing CSRF gets `403` |
| **Idempotency tests** | Duplicate `POST` with the same `Idempotency-Key` → same result; same key + different body → `422`; concurrent duplicate run creation → exactly one run |
| **Validation tests** | Each documented validation rule and error code has a failing-input test |
| **Error-shape tests** | All error responses match the error schema; none leak internals (assert absence of stack/path/SQL patterns) |
| **Async flow tests** | Upload → finalize → ingest → run → SSE sequence; SSE resume with `Last-Event-ID`; polling fallback parity |
| **SQL safety corpus** | Malicious/edge statements all yield `SQL_REJECTED`; legal statements execute; limits enforced |
| **Pagination tests** | Cursor stability under inserts, cursor misuse → `INVALID_CURSOR`, caps respected |
| **Precision tests** | Decimal strings round-trip exactly; `value_f64` never used for exact assertions |
| **Availability tests** | Datasets lacking `CUSTOMER_ID` produce `200` + `UNAVAILABLE` with reasons for dependent modules and `409 MODULE_UNAVAILABLE` for dependent *actions* |
| **Rate-limit tests** | Limits trigger with correct headers |
| **Backward-compat tests** | Previous-release client fixtures still parse current responses |

---

# 13. Versioning and Compatibility

- **URL versioning:** `/api/v1`. Breaking changes require `/api/v2`; `v1` remains supported for a published deprecation window (minimum 6 months).
- **Additive changes** (new optional request fields, new response fields, new enum values on *output-only* fields, new endpoints) are non-breaking. Clients must tolerate unknown response fields and unknown enum values (render a safe fallback).
- **Breaking changes:** removing/renaming fields or endpoints, tightening validation, changing semantics/types, removing enum values, changing error codes.
- **Deprecation signaling:** `Deprecation: true`, `Sunset: <date>`, and a `Link: <…>; rel="deprecation"` header; documented in the changelog.
- **Pipeline-version changes** do not change the API version, but responses expose `pipeline_version`; metric definition changes are documented in `ANALYTICS_SPEC.md` and surfaced in release notes.
- **OpenAPI** is published at `/api/v1/openapi.json` (authenticated in production) and used to generate the typed frontend client in CI; a mismatch between the generated client and this document fails the build.

---

# 14. Endpoint Index (Quick Reference)

| Area | Endpoints |
|---|---|
| Meta | `GET /healthz` · `GET /readyz` · `GET /meta/config` |
| Auth | `POST /auth/register` · `POST /auth/login` · `POST /auth/logout` · `POST /auth/logout-all` · `GET /auth/me` · `GET /auth/csrf` · `GET /auth/google/start` · `GET /auth/google/callback` · `POST /auth/password/forgot` · `POST /auth/password/reset` · `GET /auth/sessions` · `DELETE /auth/sessions/{id}` |
| Users | `PATCH /users/me` · `POST /users/me/password` · `DELETE /users/me` |
| Dashboard | `GET /dashboard/summary` · `GET /dashboard/activity` |
| Projects | `POST/GET /projects` · `GET/PATCH/DELETE /projects/{id}` · `POST /projects/{id}/archive|unarchive|restore` · `GET /projects/{id}/overview` |
| Datasets | `POST /projects/{id}/datasets` ★ · `POST /datasets/{id}/finalize` ★ · `POST /datasets/{id}/upload/parts` · `DELETE /datasets/{id}/upload` · `GET /projects/{id}/datasets` · `GET /datasets` · `GET/DELETE /datasets/{id}` · `GET /datasets/{id}/dependencies` |
| Versions | `GET /datasets/{id}/versions` · `GET /dataset-versions/{id}` · `…/lineage` · `…/profile` · `…/columns` · `…/preview` · `PUT …/mapping` · `PATCH …/columns/{cid}` · `GET …/sql/schema` |
| Cleaning | `GET …/cleaning/recommendations` · `POST …/cleaning/preview` · `POST …/cleaning` ★ · `GET …/cleaning-operations` · `GET /cleaning-operation-sets/{id}` |
| Runs | `POST/GET /projects/{id}/analysis-runs` ★ · `GET /analysis-runs` · `GET /analysis-runs/{id}` · `…/stages` · `…/modules` · `…/events` (SSE) · `POST …/cancel` · `POST …/retry` |
| Quality | `GET /analysis-runs/{id}/quality` · `…/quality/issues` · `…/quality/issues/{iid}/records` · `…/quality/missingness` |
| EDA | `GET /analysis-runs/{id}/eda` · `…/eda/{rid}` · `…/eda/correlation` · `…/eda/time` |
| Metrics | `GET /analysis-runs/{id}/metrics` · `…/metrics/series` · `GET /metrics/{id}` · `GET /metrics/{id}/evidence` |
| Analytics | `GET /analysis-runs/{id}/analytics/{sales|customers|customers/segments|customers/rfm|customers/rfm/table|products|products/table|discount|payment|geography|time}` |
| SQL | `GET /analysis-runs/{id}/sql/questions` · `POST /projects/{id}/sql/execute` · `POST /sql/validate` · `GET /sql-queries/{id}` · `…/result` · `POST …/cancel` · `GET /projects/{id}/sql-queries` |
| Insights | `GET /analysis-runs/{id}/insights` · `GET /insights/{id}` · `POST /insights/{id}/explain` · `GET /analysis-runs/{id}/recommendations` · `GET/PATCH /recommendations/{id}` |
| Power BI | `POST/GET /analysis-runs/{id}/powerbi` ★ · `POST /powerbi-models/{id}/download-url` |
| Reports | `GET /analysis-runs/{id}/reports/options` · `POST /analysis-runs/{id}/reports` ★ · `GET /projects/{id}/reports` · `GET /reports` · `GET/DELETE /reports/{id}` · `POST /reports/{id}/download-url` |
| Presentations | `POST /analysis-runs/{id}/presentations` ★ · `GET /projects/{id}/presentations` · `GET/DELETE /presentations/{id}` · `POST /presentations/{id}/download-url` |
| Exports | `POST /projects/{id}/exports` ★ · `GET /projects/{id}/exports` · `GET /exports/{id}` · `POST /exports/{id}/download-url` |
| AI | `POST /analysis-runs/{id}/summary` · `POST …/columns/suggest-roles` · `POST /projects/{id}/ask` (reserved) |
| Notifications | `GET /notifications` · `GET /notifications/unread-count` · `POST /notifications/{id}/read` · `POST /notifications/read-all` |
| Settings | `GET/PATCH /settings` · `GET/PUT /settings/retention` · `POST /settings/data-export` · `GET /audit-events` |
| Search (P2) | `GET /search` |

(All paths are relative to `/api/v1`; ★ = requires `Idempotency-Key`.)

---

# 15. Frontend Page → API Mapping (`DESIGN.md` §5)

| Page | Primary calls |
|---|---|
| `/login`, `/signup` | `POST /auth/login`, `POST /auth/register`, `GET /auth/google/start` |
| `/dashboard` | `GET /dashboard/summary`, `GET /dashboard/activity`, `GET /notifications/unread-count` |
| `/projects` | `GET /projects`, `DELETE /projects/{id}`, `POST /projects/{id}/archive` |
| `/projects/new` | `POST /projects`, `GET /meta/config` |
| `/projects/[id]` | `GET /projects/{id}/overview`, SSE `…/events`, `GET …/modules` |
| `/projects/[id]/dataset` | Upload flow (§7.4), `GET /dataset-versions/{v}/columns|preview|profile|lineage`, `PUT …/mapping` |
| `/projects/[id]/quality` | `GET /analysis-runs/{r}/quality`, `…/quality/issues`, `…/quality/missingness` |
| `/projects/[id]/preparation` | `GET …/cleaning/recommendations`, `POST …/cleaning/preview|cleaning`, `GET …/cleaning-operations` |
| `/projects/[id]/eda` | `GET /analysis-runs/{r}/eda`, `…/eda/correlation`, `…/eda/time` |
| `/projects/[id]/sql` | `GET …/sql/questions`, `POST …/sql/execute`, `GET /sql-queries/{id}[/result]`, `GET …/sql-queries` |
| `/projects/[id]/customers` | `GET …/analytics/customers`, `…/segments`, `…/rfm`, `…/rfm/table` |
| `/projects/[id]/products` | `GET …/analytics/products`, `…/products/table`, `…/discount`, `…/payment`, `…/geography` |
| `/projects/[id]/insights` | `GET …/insights`, `GET /metrics/{id}/evidence`, `POST /insights/{id}/explain` |
| `/projects/[id]/recommendations` | `GET …/recommendations`, `PATCH /recommendations/{id}` |
| `/projects/[id]/powerbi` | `GET/POST …/powerbi`, `POST /powerbi-models/{id}/download-url` |
| `/projects/[id]/reports` | `GET …/reports/options`, `POST …/reports`, `GET /projects/{id}/reports`, `POST /reports/{id}/download-url`, presentations equivalents |
| `/settings` | `GET/PATCH /settings`, `GET /auth/sessions`, `GET/PUT /settings/retention`, `DELETE /users/me` |
| Global top bar | `GET /notifications`, `GET /search` (P2), run-progress chip via SSE |

---

# 16. Traceability to PRD

| PRD Section | API Section |
|---|---|
| §11–12 Authentication | §3 |
| §14 Dashboard | §7.2 |
| §15–16 Projects | §7.3 |
| §17–20 Upload, validation, preview | §7.4, §7.5 |
| §21–23 Profiling, types, semantics | §7.5 |
| §24–26 Quality, missing, duplicates | §7.8 |
| §27–30 Cleaning, versioning | §7.6, §7.5 (versions, lineage) |
| §31–35 EDA, correlation, outliers | §7.9, §7.8 |
| §36–45 Retail analytics | §7.11 |
| §46–48 SQL | §7.12 |
| §49–52 Metrics, insights, recommendations | §7.10, §7.13 |
| §53–54 AI / Ask Your Data | §7.17 |
| §55–57 Power BI | §7.14 |
| §58–60 Reports, presentation | §7.15 |
| §61–66 Status, progress, errors, partial | §6, §4, §7.7, §7.11 |
| §63 Background processing | §6 |
| §67 Privacy | §5 |
| §68 File storage | §7.4 (presigned uploads/downloads) |
| §82 Security | §10 |
| §87–89 API principles | §2 |
| §90 Table requirements | §2.7, §7.5, §7.11, §7.12 |
| §95, §104 Reproducibility, idempotency | §2.8, §7.7, §7.10 |
| §103 Retry | §6.5 |
| §105 Notifications | §7.18 |
| §106 Search | §7.20 |
| §107 Export | §7.16 |
| §108–110 Deletion & retention | §7.3, §7.4, §7.19 |
| §112–114 Currency, precision | §2.3 |
| §126 Prohibited shortcuts | §1.1, §10 |
