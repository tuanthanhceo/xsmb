# XSMB Scraper - Design Specification

## Overview

A Python-based scraper system to collect all XSMB (Xo So Mien Bac - Truyen Thong) lottery results from 2009-01-01 to present, stored in PostgreSQL.

## Architecture

### 3-Phase Hybrid Scraping

| Phase | Source | URL Pattern | Purpose |
|-------|--------|-------------|---------|
| 1 | ketqua04.net | `/so-ket-qua-truyen-thong/300` | Batch ~300 most recent days (1 request) |
| 2 | ketqua.vn | `/xsmb/DD-MM-YYYY` | Daily reverse-scan for remaining ~4,100+ days |
| 3 | ketqua04.net | `/xo-so-truyen-thong.php?ngay=DD-MM-YYYY` | Fallback for days where Phase 2 fails |

### Data Flow

```
HTTP fetch (httpx async)
  -> HTML parse (BeautifulSoup4 + lxml)
  -> Validate (27 numbers, correct digit lengths per prize tier)
  -> Compute derived fields (loto array, de_dau, de_duoi, raw_string)
  -> UPSERT to PostgreSQL (ON CONFLICT draw_date DO UPDATE)
```

### Source Configuration

```python
SOURCES = {
    "ketqua_vn": {
        "base_url": "https://ketqua.vn",
        "daily_pattern": "/xsmb/{date}",        # DD-MM-YYYY
    },
    "ketqua_net": {
        "base_url": "https://ketqua04.net",      # Update when domain changes
        "batch_pattern": "/so-ket-qua-truyen-thong/{days}",
        "daily_pattern": "/xo-so-truyen-thong.php?ngay={date}",
    },
}
```

## Data Model

### XSMB Result Structure

Each draw contains 27 numbers across 8 prize tiers:

| Prize | Count | Digits | Total chars |
|-------|-------|--------|-------------|
| Dac biet (DB) | 1 | 5 | 5 |
| Giai 1 | 1 | 5 | 5 |
| Giai 2 | 2 | 5 | 10 |
| Giai 3 | 6 | 5 | 30 |
| Giai 4 | 4 | 4 | 16 |
| Giai 5 | 6 | 4 | 24 |
| Giai 6 | 3 | 3 | 9 |
| Giai 7 | 4 | 2 | 8 |
| **Total** | **27** | | **107** |

Raw string = concatenation of all prizes in order = 107 characters.

### Database Schema

Three tables:
- **xsmb_results**: Main results table. Each prize stored as individual VARCHAR column (preserves leading zeros). Includes computed fields: `raw_string`, `loto_array`, `de_dau`, `de_duoi`. UNIQUE constraint on `draw_date`.
- **scrape_jobs**: Tracks scrape job metadata (date range, status, counts).
- **scrape_logs**: Per-day scrape attempt logs (status, source, errors, retry count, response time).

Indexes on: `draw_date DESC`, `giai_db`, `de_dau`, `day_of_week`, and `(year, month)` composite.

### Computed Fields

- `raw_string`: Reconstructed from all 27 prize values, must be exactly 107 chars
- `loto_array`: Last 2 digits of each of the 27 prizes, sorted ascending
- `de_dau`: Last 2 digits of giai_db
- `de_duoi`: Last 2 digits of giai_7_1

## Scraping Behavior

### Rate Limiting

| Source | Delay | Max Retries | Backoff | 429 Pause |
|--------|-------|-------------|---------|-----------|
| ketqua.vn | 1.5-2.5s (random) | 3 | 3x (5s, 15s, 45s) | 60s |
| ketqua04.net | 2.0-3.0s (random) | 3 | 3x | 60s |

Rotating user agents from a pool of 4 common browser UA strings.

### Tet Holiday Handling

XSMB does not draw during Tet (~4 days/year). Known ranges are hardcoded. If a date returns 404/empty AND falls within a Tet range, it is marked as `skipped` without retry.

### Idempotency & Resumability

- UPSERT (ON CONFLICT draw_date DO UPDATE) ensures re-runs are safe
- Before scraping a date, check if it already exists in DB - skip if present
- Jobs track progress (scraped/skipped/failed counts) for resume capability

### Error Handling

- 404 or no data: Check Tet range -> skip or flag
- 403/429/5xx: Retry with exponential backoff, then fallback to Phase 3
- Parse error: Log and continue to next date
- Connection error: Retry with backoff

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| HTTP | httpx (async) |
| HTML Parser | BeautifulSoup4 + lxml |
| Database | PostgreSQL 16 (Docker) |
| ORM | SQLAlchemy 2.0 (async) |
| Migration | Alembic |
| Config | pydantic-settings |
| Logging | structlog |
| CLI | typer |
| Export | pandas |
| Package Manager | uv |

## Project Structure

```
xsmb-scraper/
├── pyproject.toml
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
├── alembic/versions/
├── src/
│   ├── __init__.py
│   ├── main.py                     # CLI entrypoint (typer)
│   ├── config.py                   # Settings + source URLs
│   ├── database.py                 # DB engine, session
│   ├── models/
│   │   ├── result.py               # XSMBResult model
│   │   └── scrape_job.py           # ScrapeJob, ScrapeLog
│   ├── scrapers/
│   │   ├── base.py                 # BaseScraper (ABC)
│   │   ├── ketqua_vn.py            # ketqua.vn daily scraper
│   │   ├── ketqua_net_batch.py     # ketqua04.net batch /300
│   │   ├── ketqua_net_daily.py     # ketqua04.net daily fallback
│   │   └── parser.py               # HTML parser utils
│   ├── services/
│   │   ├── orchestrator.py         # 3-phase scrape logic
│   │   ├── result_service.py       # CRUD + UPSERT
│   │   └── export_service.py       # CSV/JSON/Excel
│   └── utils/
│       ├── date_utils.py           # Tet detection, date ranges
│       ├── loto_utils.py           # Loto, de computation
│       └── http_client.py          # Configured httpx + rate limit
├── tests/
│   ├── test_parser.py
│   ├── test_loto_utils.py
│   └── fixtures/
└── exports/
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `db init` | Initialize database with Alembic migrations |
| `scrape full` | Full 3-phase hybrid scrape |
| `scrape batch` | Phase 1 only (batch 300 recent days) |
| `scrape range --from --to` | Scrape specific date range |
| `scrape today` | Scrape today only (for daily cron) |
| `scrape resume` | Resume interrupted scrape job |
| `status` | Show progress and statistics |
| `verify --sample N` | Cross-validate N random days from both sources |
| `export csv/json/excel` | Export with optional date range filter |

## Validation Rules

Every parsed result must pass:
1. Exactly 27 numbers total
2. Correct digit count per prize tier (5/5/5/5/4/4/3/2)
3. All values are digits only (`^\d+$`)
4. Reconstructed raw_string = 107 characters
5. Loto array = 27 entries (last 2 digits of each prize, sorted)

## Export Format

JSON export includes metadata (total records, date range, export timestamp) and per-day results with structured prizes, loto array, and de values.

## Docker Setup

PostgreSQL 16 Alpine via docker-compose. Scraper service depends on DB. Exports volume-mounted to `./exports/`.

## Estimated Runtime

- Phase 1: ~30 seconds (1 batch request)
- Phase 2: ~4,100 requests x 2s avg = ~2.3 hours
- Phase 3: Only for failed days, typically <50 requests
- Total: ~2.5 hours worst case

## Important Notes

1. **HTML inspection first**: Fetch sample pages from each source and inspect actual HTML structure before coding parsers. Do not assume CSS selectors.
2. **Domain instability**: ketqua04.net changes domain numbers. Config is centralized for easy updates.
3. **No headless browser needed**: Both sources are server-side rendered. httpx + BeautifulSoup sufficient.
