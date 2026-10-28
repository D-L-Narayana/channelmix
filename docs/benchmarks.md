# Benchmarks — bulk metric upsert

Script: [`scripts/bench_bulk_upsert.py`](../scripts/bench_bulk_upsert.py)

```bash
. api/.venv/bin/activate
DATABASE_URL=sqlite:////tmp/bench.db python scripts/bench_bulk_upsert.py
DATABASE_URL=postgresql+psycopg://postgres:ci@localhost:5432/channelmix python scripts/bench_bulk_upsert.py
```

The script creates 50 campaigns x 1,000 days = **50,000 `daily_metrics` rows** and measures:

| phase | what it exercises |
|---|---|
| cold insert | 50k new rows → every row takes the INSERT branch of `INSERT … ON CONFLICT (campaign_id, day) DO UPDATE` |
| warm upsert | the same 50k rows with changed `spend` → every row takes the UPDATE branch; row count must not change |
| http 10k | a single `POST /api/v1/accounts/{id}/metrics/bulk` with 10,000 rows through FastAPI (pydantic validation + ownership check + upsert + cache invalidation) |
| idem replay | the same POST again with the same `Idempotency-Key` → stored response is replayed, no write happens |

## Results

Machine: sandbox container, Python 3.14, SQLAlchemy 2.1, single process. Numbers are wall-clock, median of 3 runs.

### SQLite (file DB, `sqlite:////tmp/bench.db`)

| phase | time | throughput |
|---|---|---|
| cold insert 50k | 0.53 s | ~94,000 rows/s |
| warm upsert 50k | 0.58 s | ~86,000 rows/s |
| http 10k (end-to-end) | 0.26 s | ~38,000 rows/s |
| idempotent replay 10k | ~100 ms | body hash + key lookup only |
| rows in table after all phases | 50,000 | no duplicates |

### PostgreSQL 16 (GitHub Actions service container, run 40654493350)

Same script, `DATABASE_URL=postgresql+psycopg://postgres:ci@localhost:5432/channelmix`, Python 3.11, 2-vCPU runner.

| phase | time | throughput |
|---|---|---|
| cold insert 50k | 3.38 s | ~14,800 rows/s |
| warm upsert 50k | 3.07 s | ~16,300 rows/s |
| http 10k (end-to-end) | 0.84 s | ~11,900 rows/s |
| idempotent replay 10k | ~150 ms | body hash + key lookup only |
| rows in table after all phases | 50,000 | no duplicates |

Postgres is slower than file-SQLite here because every 2,000-row chunk is a network round trip on a shared CI runner
and `ON CONFLICT DO UPDATE` has to maintain the unique index + MVCC versions; the bench step in CI re-measures this on
every push so the number tracks the code.

## What made it fast

1. **One statement per chunk, not per row.** `upsert_metrics` passes a list of 2,000 dicts to
   `Session.execute(insert(...).on_conflict_do_update(...), rows)`; SQLAlchemy's *insertmanyvalues* turns that into a
   multi-row `INSERT … VALUES (...),(...) ON CONFLICT DO UPDATE SET col = excluded.col`.
   Switching from a literal `.values(chunk)` to executemany took the SQLite cold insert from 5.0 s → 0.53 s (~10x).
2. **In-batch de-duplication.** `ON CONFLICT` cannot update the same row twice in one statement, so duplicate
   `(campaign_id, day)` pairs inside a payload are collapsed first (last one wins).
3. **Natural-key unique index** `uq_metric_campaign_day (campaign_id, day)` is what the conflict target resolves against;
   `ix_daily_metrics_day` serves the date-window reports.
4. **Idempotency is O(1)**: the request body is hashed (sha256) and looked up in `idempotency_keys` before any write.
