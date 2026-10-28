# ChannelMix API contract (v1)

Status: **v1 — stable for the frontend**. Base URL (prod): `https://channelmix-api.vercel.app` (confirmed at the bottom of this file once deployed). Local: `http://localhost:8000`.
All paths below are relative to `/api/v1` unless stated otherwise. All bodies are JSON (`Content-Type: application/json`) except `POST /imports/csv` (multipart).

## Auth

- Create a workspace once (`POST /workspaces`, no auth). The response contains `api_key` **exactly once** — it is stored hashed (SHA-256) and cannot be retrieved again.
- Every other endpoint requires the header **`X-Api-Key: <api_key>`**.
- For `GET /stream` (browser `EventSource` cannot set headers) the key may be passed as a query param: `?api_key=<api_key>`. The query param is accepted on every endpoint but should only be used for SSE.
- Missing/invalid key → `401 {"detail": "missing or invalid API key"}`.
- Any resource id that belongs to another workspace → `404` (indistinguishable from "does not exist").
- Key format: `cmx_` + 40 hex chars. Slug format: `[a-z0-9-]+` (derived from the name + 4 random chars), e.g. `acme-retail-k3f9`.
- Magic URL for the frontend: `/w/<slug>?key=<api_key>` (frontend concern; API returns `slug`).

## Common

- `channel` enum (fixed): `google | meta | amazon | linkedin | other`.
- Dates are ISO `YYYY-MM-DD`; timestamps are ISO-8601 UTC.
- Money is returned as JSON numbers (floats) in reports and as decimal strings in raw campaign/metric rows (`"daily_budget": "100.00"`). Accept both when parsing.
- Response headers: `X-Request-ID` (always), `X-Cache: HIT|MISS` (reports), `Idempotent-Replayed: true|false` (bulk).
- Errors: FastAPI style `{"detail": "..."}` (string) or `{"detail": [ {loc, msg, type} ]}` for 422 validation.
- CORS: `https://channelmix.vercel.app`, `http://localhost:5173` (+ configurable).

## Endpoints

### `GET /health` (root, not under /api/v1)
`200 {"status":"ok","version":"2.0.0","cache":"memory|redis","database":"postgresql|sqlite"}`

### `POST /workspaces` — create workspace (no auth)
Request: `{"name": "Acme Retail", "email": "me@example.com"}` (name 1–120 chars, email validated)

Response `201`:
```json
{
  "id": 12,
  "slug": "acme-retail-k3f9",
  "name": "Acme Retail",
  "email": "me@example.com",
  "api_key": "cmx_9f1c...",           // shown ONCE
  "created_at": "2025-10-28T09:00:00Z"
}
```

### `GET /workspaces/me`
`200 {"id", "slug", "name", "email", "created_at", "stats": {"campaigns": 3, "metric_rows": 90, "imports": 1, "first_day": "2025-01-01"|null, "last_day": "2025-03-31"|null}}`

### Campaigns

Campaign object:
```json
{"id": 1, "workspace_id": 12, "channel": "google", "external_id": "g-123", "name": "Brand search",
 "status": "active", "daily_budget": "100.00", "created_at": "...", "updated_at": "..."}
```
- `GET /campaigns?channel=google&status=active` → `200 [Campaign]` (ordered by id)
- `POST /campaigns` body `{"channel", "external_id", "name", "status"?: "active", "daily_budget"?: 0}` → `201 Campaign`; `409` if (channel, external_id) exists in the workspace.
- `GET /campaigns/{id}` → `200 Campaign` | `404`
- `PATCH /campaigns/{id}` body any of `{"name", "status", "daily_budget"}` → `200 Campaign`
- `DELETE /campaigns/{id}` → `204` (cascades metrics)

Each create/update/delete emits event `campaign.changed`.

### Metrics

Metric row (input). Identify the campaign **either** by `campaign_id` **or** by `channel` + `external_id` (campaign auto-created if missing; `campaign_name` optional, defaults to `external_id`):
```json
{"campaign_id": 1, "day": "2025-10-01", "impressions": 1000, "clicks": 50, "conversions": 3, "spend": 42.5, "revenue": 120.0}
{"channel": "meta", "external_id": "summer-sale", "campaign_name": "Summer sale", "day": "2025-10-01", "spend": 10}
```
All numeric fields default to 0 and must be ≥ 0.

- `POST /metrics/bulk` body `{"rows": [MetricRow, ...]}` (1–100 000 rows). Header `Idempotency-Key` optional.
  - `200 {"received": 30, "upserted": 30, "campaigns_touched": 3, "campaigns_created": 1, "idempotent_replay": false, "import_id": 7}`
  - Upsert on natural key `(campaign_id, day)`; duplicates inside the batch: last wins.
  - Same `Idempotency-Key` + same body → replays stored response, `idempotent_replay: true`, header `Idempotent-Replayed: true`. Same key + different body → `422`. Keys are scoped per workspace.
  - `422 {"detail": "campaigns not in workspace: [..]"}` if a `campaign_id` is foreign/unknown.
  - Emits event `metrics.upserted`.
- `GET /metrics?campaign_id=&start=&end=&limit=500` → `200 [{"id","campaign_id","day","impressions","clicks","conversions","spend","revenue","updated_at"}]` (newest first, limit ≤ 5000)
- `DELETE /metrics?campaign_id=` → `204` (deletes that campaign's rows)

### CSV import

`POST /imports/csv` — `multipart/form-data` fields:
- `file` (required): the CSV (UTF-8 / UTF-8-BOM / UTF-16 handled; `,` `;` or tab delimiters auto-detected; Google Ads preamble lines and `Total` rows skipped)
- `dry_run` (optional, `true|false`, default `false`)
- `format` (optional override): `google_ads | meta_ads | generic`
- `channel` (optional override for generic files without a channel column): one of the channel enum

Response `200` (both modes share the shape; `dry_run` has `status: "dry_run"` and nothing is written):
```json
{
  "import_id": 7,                       // null on dry_run
  "status": "dry_run" | "completed" | "failed",
  "detected_format": "google_ads" | "meta_ads" | "generic",
  "confidence": 0.92,
  "channel": "google",                  // channel applied to rows lacking a channel column
  "currency": "INR" | null,             // parsed from e.g. "Amount spent (INR)" / "Currency code"
  "delimiter": ",",
  "mapping": {                          // our field -> source column (null = not present, defaults to 0)
    "day": "Day", "campaign_name": "Campaign", "external_id": "Campaign ID",
    "impressions": "Impressions", "clicks": "Clicks", "conversions": "Conversions",
    "spend": "Cost", "revenue": "Conv. value", "channel": null
  },
  "source_columns": ["Campaign", "Day", ...],
  "unmapped_columns": ["Campaign status", "Currency code"],
  "row_count": 120,                     // parsable data rows
  "skipped_rows": 2,                    // preamble/total/blank/invalid
  "preview": [                          // first 10 parsed rows in our generic shape
    {"day": "2025-10-01", "channel": "google", "external_id": "brand-search", "campaign_name": "Brand search",
     "impressions": 1000, "clicks": 50, "conversions": 3, "spend": 42.5, "revenue": 0.0}
  ],
  "warnings": ["No revenue column detected; revenue set to 0", "Row 14: unparseable day 'n/a' — skipped"],
  "summary": {"rows_upserted": 120, "campaigns_created": 4, "campaigns_touched": 4,
               "first_day": "2025-09-01", "last_day": "2025-10-28"}   // null on dry_run
}
```
`422` if no header row can be detected or zero rows parse. Commit emits `import.completed` and `metrics.upserted`.

- `GET /imports?limit=50` → `200 [{"id","source","filename","status","rows_received","rows_upserted","campaigns_created","warnings":[...],"created_at"}]` (newest first). `source` ∈ `google_ads | meta_ads | generic | api | sample`.
- `GET /imports/{id}` → single import record.

#### Supported CSV formats
| format | required headers (case-insensitive, any order) | channel |
|---|---|---|
| `google_ads` | `Campaign`, `Day`, `Cost`, `Impressions`, `Clicks`, `Conversions` (+ optional `Conv. value`, `Campaign ID`, `Currency code`) | `google` |
| `meta_ads` | `Campaign name`, `Day` (or `Reporting starts`), `Amount spent (XXX)`, `Impressions`, `Link clicks` (or `Clicks (all)`), `Results` (+ optional `Purchases conversion value`, `Campaign ID`) | `meta` |
| `generic` | `day`, `campaign` (or `campaign_name`), `spend`; optional `channel`, `external_id`, `impressions`, `clicks`, `conversions`, `revenue` | from `channel` column, else `?channel=` override, else `other` |

Generic template header: `day,channel,campaign,external_id,impressions,clicks,conversions,spend,revenue`

### Sample dataset
- `GET /datasets/sample` → `200 text/csv` (generic format, `Content-Disposition: attachment; filename="channelmix-sample.csv"`). Real public dataset, see `api/app/datasets/SOURCE.md` for attribution/license. Header `X-Dataset-Source` carries the attribution line.
- `GET /datasets/sample/info` → `200 {"name", "source_url", "license", "attribution", "rows", "channels": [...], "first_day", "last_day", "description"}`
- `POST /datasets/sample/import` → imports it into the caller's workspace, returns the same shape as a committed CSV import (`source: "sample"`). Idempotent (re-import upserts same rows).

### Reports (all accept `start` & `end` ISO dates; default = last 30 days ending today; cached per workspace, `X-Cache` header)

- `GET /reports/summary?start=&end=` →
```json
{"start":"2025-09-29","end":"2025-10-28",
 "spend": 12345.6, "revenue": 45678.9, "impressions": 100000, "clicks": 2500, "conversions": 120,
 "roas": 3.7, "cpa": 102.88, "ctr": 0.025, "cpc": 4.94, "days_with_data": 30, "campaigns": 6,
 "previous": { same keys for the preceding window of equal length, or null if no data },
 "delta_pct": {"spend": 0.12, "revenue": -0.03, "roas": null, ...}   // (current-previous)/previous, null when previous is 0
}
```
- `GET /reports/by-channel?start=&end=` →
```json
{"start","end","total_spend","total_revenue","blended_roas",
 "channels": [{"channel":"google","spend","revenue","impressions","clicks","conversions",
               "spend_share":0.52,"revenue_share":0.61,"roas","cpa","ctr","cpc","roas_rank":1}]}
```
- `GET /reports/trend?start=&end=&group_by=channel|total` →
```json
{"start","end","group_by":"channel",
 "points": [{"day":"2025-10-01","channel":"google"|"all","spend","revenue","conversions","roas",
             "spend_7d_avg","roas_7d","spend_dod_change","cumulative_spend"}]}
```
- `GET /reports/campaigns?start=&end=&channel=` → `200 [{"campaign_id","name","channel","status","spend","revenue","impressions","clicks","conversions","roas","cpa","spend_share_in_channel","roas_rank_in_channel"}]`

### Recommendations
`GET /recommendations?total_budget=&lookback_days=30&min_share=0.05&max_shift_pct=&end=`
(`total_budget` optional → defaults to current average daily spend; `lookback_days` 7–365; `min_share` 0–0.5; `max_shift_pct` 0–1)
```json
{"total_budget": 3000, "lookback_days": 30, "window_start": "...", "window_end": "...",
 "current_projected_revenue", "recommended_projected_revenue", "projected_uplift", "projected_uplift_pct",
 "channels": [{"channel","current_daily_spend","recommended_daily_spend","delta","delta_pct","current_roas",
               "marginal_roas_at_current","marginal_roas_at_recommended","projected_daily_revenue",
               "curve": {"a","b","r2","n_points","method"}, "explanation": "Increase google by $400/day (+40%): ..."}],
 "summary": "Reallocating $3,000/day toward google ...", "method": "power-law response curves (log-log OLS) + greedy marginal allocation"}
```
`POST /recommendations/budget` with the same fields as a JSON body is also accepted (same response).

### Events / SSE

`GET /stream?api_key=<key>` → `text/event-stream` (also accepts the `X-Api-Key` header and `Last-Event-ID` header or `?last_event_id=` query).

Wire format:
```
retry: 2000
event: ready
id: 1041
data: {"last_event_id": 1041, "workspace_id": 12, "max_seconds": 25}

: ping                              <- heartbeat comment every 15s

id: 1042
event: metrics.upserted
data: {"id":1042,"type":"metrics.upserted","created_at":"...","payload":{"rows":30,"campaigns_touched":3,"first_day":"...","last_day":"...","import_id":7}}

id: 1043
event: campaign.changed
data: {"id":1043,"type":"campaign.changed","created_at":"...","payload":{"campaign_id":5,"action":"created|updated|deleted","channel":"google","name":"..."}}

id: 1044
event: import.completed
data: {"id":1044,"type":"import.completed","created_at":"...","payload":{"import_id":7,"source":"google_ads","rows_upserted":120,"campaigns_created":4,"status":"completed"}}
```
- The server closes the stream after ~25s on Vercel (`max_seconds` in the `ready` event); `EventSource` reconnects automatically and sends `Last-Event-ID`, so no events are lost. Events are persisted in the `events` table (append-only), so history replay works across function instances.
- Without `Last-Event-ID` the stream starts at the latest event (no history replay). `?last_event_id=0` replays everything (capped at 500 events per connection).
- `GET /events?after=<id>&limit=100` → `200 [event]` (same JSON as SSE `data`), for the polling fallback. Supports `ETag`/`If-None-Match` (304 when nothing new).

## Suggested curl snippets (frontend shows these with the visitor's key)
```bash
# create
curl -s -X POST $API/api/v1/workspaces -H 'content-type: application/json' -d '{"name":"Acme","email":"me@acme.com"}'
# push metrics (auto-creates campaigns)
curl -s -X POST $API/api/v1/metrics/bulk -H "X-Api-Key: $KEY" -H 'content-type: application/json' \
  -d '{"rows":[{"channel":"google","external_id":"brand","campaign_name":"Brand","day":"2025-10-27","impressions":12000,"clicks":480,"conversions":22,"spend":310.5,"revenue":1420}]}'
# import a Google Ads / Meta export (preview first)
curl -s -X POST "$API/api/v1/imports/csv" -H "X-Api-Key: $KEY" -F file=@export.csv -F dry_run=true
# live events
curl -N "$API/api/v1/stream?api_key=$KEY"
```

## Changelog
- 2025-10-28 v1 draft published (before implementation). Any change will be appended here.
