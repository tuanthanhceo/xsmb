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

```sql
CREATE TABLE xsmb_results (
    id SERIAL PRIMARY KEY,
    draw_date DATE NOT NULL UNIQUE,
    day_of_week SMALLINT NOT NULL,        -- 0=CN, 1=T2, ..., 6=T7
    -- Prize columns (VARCHAR preserves leading zeros)
    giai_db VARCHAR(5) NOT NULL,
    giai_1 VARCHAR(5) NOT NULL,
    giai_2_1 VARCHAR(5) NOT NULL, giai_2_2 VARCHAR(5) NOT NULL,
    giai_3_1 VARCHAR(5) NOT NULL, giai_3_2 VARCHAR(5) NOT NULL,
    giai_3_3 VARCHAR(5) NOT NULL, giai_3_4 VARCHAR(5) NOT NULL,
    giai_3_5 VARCHAR(5) NOT NULL, giai_3_6 VARCHAR(5) NOT NULL,
    giai_4_1 VARCHAR(4) NOT NULL, giai_4_2 VARCHAR(4) NOT NULL,
    giai_4_3 VARCHAR(4) NOT NULL, giai_4_4 VARCHAR(4) NOT NULL,
    giai_5_1 VARCHAR(4) NOT NULL, giai_5_2 VARCHAR(4) NOT NULL,
    giai_5_3 VARCHAR(4) NOT NULL, giai_5_4 VARCHAR(4) NOT NULL,
    giai_5_5 VARCHAR(4) NOT NULL, giai_5_6 VARCHAR(4) NOT NULL,
    giai_6_1 VARCHAR(3) NOT NULL, giai_6_2 VARCHAR(3) NOT NULL,
    giai_6_3 VARCHAR(3) NOT NULL,
    giai_7_1 VARCHAR(2) NOT NULL, giai_7_2 VARCHAR(2) NOT NULL,
    giai_7_3 VARCHAR(2) NOT NULL, giai_7_4 VARCHAR(2) NOT NULL,
    -- Computed fields
    raw_string VARCHAR(110),
    loto_array TEXT[],
    de_dau VARCHAR(2),                    -- last 2 digits of giai_db
    de_duoi VARCHAR(2),                   -- last 2 digits of giai_7_1
    -- Metadata
    ky_tu VARCHAR(100),
    source VARCHAR(50),                   -- 'ketqua_vn' | 'ketqua_net_batch' | 'ketqua_net_daily'
    source_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_xsmb_draw_date ON xsmb_results(draw_date DESC);
CREATE INDEX idx_xsmb_giai_db ON xsmb_results(giai_db);
CREATE INDEX idx_xsmb_de_dau ON xsmb_results(de_dau);
CREATE INDEX idx_xsmb_day_of_week ON xsmb_results(day_of_week);
CREATE INDEX idx_xsmb_year_month ON xsmb_results(
    EXTRACT(YEAR FROM draw_date), EXTRACT(MONTH FROM draw_date)
);

CREATE TABLE scrape_jobs (
    id SERIAL PRIMARY KEY,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending|running|completed|failed|cancelled
    total_days INT DEFAULT 0,
    scraped_days INT DEFAULT 0,
    skipped_days INT DEFAULT 0,
    failed_days INT DEFAULT 0,
    error_log TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE scrape_logs (
    id SERIAL PRIMARY KEY,
    job_id INT REFERENCES scrape_jobs(id),
    draw_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,          -- success|skipped|failed
    source VARCHAR(50),
    source_url TEXT,
    error_message TEXT,
    retry_count INT DEFAULT 0,
    response_time_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

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

XSMB does not draw during Tet (~4 days/year). Known ranges hardcoded in `date_utils.py`:

```
2009: 25-28/01, 2010: 13-16/02, 2011: 02-05/02, 2012: 22-25/01
2013: 09-12/02, 2014: 30/01-02/02, 2015: 18-21/02, 2016: 07-10/02
2017: 27-30/01, 2018: 15-18/02, 2019: 04-07/02, 2020: 24-27/01
2021: 11-14/02, 2022: 31/01-03/02, 2023: 21-24/01, 2024: 09-12/02
2025: 28-31/01, 2026: 16-19/02
```

If a date returns 404/empty AND falls within a Tet range, it is marked as `skipped` without retry. Future Tet dates can be added to the config as needed.

### Idempotency & Resumability

- UPSERT (ON CONFLICT draw_date DO UPDATE) ensures re-runs are safe
- Before scraping a date, check if it already exists in DB - skip if present
- Jobs track progress (scraped/skipped/failed counts) for resume capability

### Concurrency Model

Sequential requests only (concurrency = 1). Each phase processes one date at a time with random delay between requests. No parallel requests - this respects rate limits and keeps the scraper simple and polite.

### Error Handling

- 404 or no data: Check Tet range -> skip (mark `skipped`) or flag as `failed`
- 403/429/5xx: Retry 3x with exponential backoff (5s, 15s, 45s). If Phase 2 fails all retries, fallback to Phase 3 for that specific date. If Phase 3 also fails all retries, mark date as `failed` in scrape_logs and continue to next date.
- Parse error: Log error details to scrape_logs, mark `failed`, continue to next date
- Connection error: Same retry logic as 5xx
- Phase 1 batch failure: Skip Phase 1 entirely, proceed to Phase 2 for all dates
- No job-level abort threshold: scraper continues through all dates regardless of failure count. Failed dates can be retried later via `scrape resume`.

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
│   ├── test_parser.py              # HTML parsing for both sources
│   ├── test_loto_utils.py          # Loto/de computation
│   ├── test_date_utils.py          # Tet detection, date ranges
│   ├── test_validation.py          # 27-number validation, raw_string
│   └── fixtures/                   # Sample HTML files from each source
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
| `verify --sample N` | Fetch N random existing dates from both sources, compare field-by-field. Report mismatches to stdout and scrape_logs. Exit code 1 if any mismatch. |
| `export csv/json/excel` | Export with optional date range filter |

## Validation Rules

Every parsed result must pass:
1. Exactly 27 numbers total
2. Correct digit count per prize: giai_db=5, giai_1=5, giai_2_*=5, giai_3_*=5, giai_4_*=4, giai_5_*=4, giai_6_*=3, giai_7_*=2
3. All values are digits only (`^\d+$`)
4. Reconstructed raw_string = 107 characters
5. Loto array = 27 entries (last 2 digits of each prize, sorted)

## Export Format

JSON export includes metadata (total records, date range, export timestamp) and per-day results with structured prizes, loto array, and de values.

## Docker Setup

PostgreSQL 16 Alpine via docker-compose. Scraper service depends on DB. Exports volume-mounted to `./exports/`.

### Environment Variables (.env.example)

```
DATABASE_URL=postgresql+asyncpg://xsmb:xsmb_secret@localhost:5432/xsmb
POSTGRES_DB=xsmb
POSTGRES_USER=xsmb
POSTGRES_PASSWORD=xsmb_secret
LOG_LEVEL=INFO
```

## Estimated Runtime

- Phase 1: ~30 seconds (1 batch request)
- Phase 2: ~4,100 requests x 2s avg = ~2.3 hours
- Phase 3: Only for failed days, typically <50 requests
- Total: ~2.5 hours worst case

## Important Notes

1. **HTML inspection first**: Fetch sample pages from each source and inspect actual HTML structure before coding parsers. Do not assume CSS selectors.
2. **Domain instability**: ketqua04.net changes domain numbers. Config is centralized for easy updates.
3. **No headless browser needed**: Both sources are server-side rendered. httpx + BeautifulSoup sufficient.
