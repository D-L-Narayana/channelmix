# ChannelMix — Cross-channel Ad Spend Dashboard & Budget Optimizer

Full-stack app that unifies spend and performance from multiple ad channels (Google, Meta, Amazon — synthetic connectors) into one interface, computes KPIs (CTR, CPC, CPA, ROAS) per channel and recommends how to reallocate budget toward the channels with the best marginal ROAS.

**Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 + raw SQL (window functions) · PostgreSQL (Supabase) · Redis (report cache) · Vue 3 + TypeScript + Pinia + ECharts · pytest + pytest-bdd (Gherkin) · Vitest · ELK (Elasticsearch, Logstash, Kibana) via structured JSON logs · Docker Compose · GitHub Actions CI/CD · Vercel (web)

## Features
- REST API (`/api/v1`) for accounts, channels, campaigns, daily metrics and reports; OpenAPI docs at `/docs`.
- Idempotent bulk metric ingestion (`POST /metrics/bulk`, upsert on `(campaign_id, day)`).
- Channel-mix and trend reports built with SQL window functions; cached in Redis with per-account invalidation.
- Budget reallocation recommendation (diminishing-returns ROAS curve per channel, greedy marginal allocation) with an explanation payload the UI renders.
- Vue 3 dashboard: unified cross-channel view, date-range filters, drill-down per campaign.
- Structured JSON request logs (request id, account id, latency) → Logstash → Elasticsearch → Kibana dashboard.
- BDD: Gherkin features executable with pytest-bdd; unit + API tests with pytest; CI runs tests, lint and builds Docker images.

## Run
```bash
docker compose up --build     # api :8000, web :5173, kibana :5601
cd api && pytest -q           # unit + API + BDD
```
