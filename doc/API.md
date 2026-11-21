# SEPC API

Base: `https://<username>.pythonanywhere.com`. Login routes need the header `Authorization: Bearer <token>`.

## Public
| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | status, `on_pythonanywhere`, `server_platforms` |
| GET | `/api/board` | all students with solved per period (`day/week/month/all`), previous period, ratings, per-platform data. Ranking is done in the browser |
| GET | `/api/students/<id>/public` | one row of the board |
| GET | `/api/history?ids=3,1&days=30` | daily series per platform (`solved`, `rating`). `days=0` = all history |
| GET | `/api/sync/status` | latest run with log, recent runs, per-platform summary, accounts with errors |
| GET | `/api/students/template` | Excel template |

## Auth
| POST | `/api/auth/login` | `{username, password}` → `{token, user}` |
|---|---|---|
| GET | `/api/auth/me` | current user |
| POST | `/api/auth/password` | `{current, new}` → new token |
| GET/POST | `/api/users` | list / add `{username, password, role}` (add = admin) |
| DELETE | `/api/users/<id>` | admin |

## Students (login)
| GET | `/api/students` | list with platform usernames |
|---|---|---|
| POST | `/api/students` | `{student_id, name, batch, department, email, avatar_url, github_url, linkedin_url, role, codeforces, leetcode, codechef, beecrowd}` |
| PUT | `/api/students/<id>` | same fields (only the sent ones change) |
| DELETE | `/api/students/<id>` | also deletes history |
| POST | `/api/students/import` | multipart `file` (.xlsx), `dry_run=1` preview / `0` save |

## Sync (login)
| POST | `/api/sync/start` | creates a run (or returns the running one) |
|---|---|---|
| POST | `/api/sync/step` | `{run_id}` fetches accounts for ~5 s → `{run, lines}` |
| POST | `/api/sync/stop` | stops the running sync |
| POST | `/api/demo/load` / `/api/demo/clear` | test data |

## Local push (signed: `X-Timestamp`, `X-Signature = HMAC_SHA256(INGEST_SECRET, ts + "." + body)`)
| GET | `/api/ingest/accounts` | `{platform: [usernames]}` |
|---|---|---|
| POST | `/api/ingest/<platform>` | `{"users": {"name": {"solved": 12, "rating": 1500, "rank": "Expert"}}}`. The beecrowd.py JSON (with `points`) is accepted as is |

## How the "period" numbers are computed
Every sync writes one snapshot per account per day (Dhaka date).
`solved in period = total at the end of the latest day − total at the end of the day before the period`.
If an account has no snapshot that old, its first snapshot is used, so old problems never count as "new".
