# XSMB Scraper Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 3-phase hybrid scraper that collects all XSMB lottery results (2009-01-01 to present) from ketqua.vn and ketqua04.net into PostgreSQL.

**Architecture:** Async Python scraper with sequential HTTP requests (concurrency=1), 3-phase approach (batch bootstrap -> daily reverse-scan -> fallback), UPSERT for idempotency. Docker Compose for PostgreSQL.

**Tech Stack:** Python 3.11+, httpx (async), BeautifulSoup4+lxml, PostgreSQL 16, SQLAlchemy 2.0 (async), Alembic, typer, pydantic-settings, structlog, pandas

**Spec:** `docs/superpowers/specs/2026-03-15-xsmb-scraper-design.md`

---

## Chunk 1: Project Scaffold & Database

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `Dockerfile`
- Create: `src/__init__.py`
- Create: `src/config.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "xsmb-scraper"
version = "0.1.0"
description = "XSMB lottery results scraper"
requires-python = ">=3.11"
dependencies = [
    "httpx[http2]>=0.27",
    "beautifulsoup4>=4.12",
    "lxml>=5.1",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "pydantic-settings>=2.5",
    "structlog>=24.1",
    "typer[all]>=0.12",
    "pandas>=2.2",
    "openpyxl>=3.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
]

[project.scripts]
xsmb = "src.main:app"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create .env.example**

```
DATABASE_URL=postgresql+asyncpg://xsmb:xsmb_secret@localhost:5432/xsmb
POSTGRES_DB=xsmb
POSTGRES_USER=xsmb
POSTGRES_PASSWORD=xsmb_secret
LOG_LEVEL=INFO
```

- [ ] **Step 3: Create docker-compose.yml**

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: xsmb
      POSTGRES_USER: xsmb
      POSTGRES_PASSWORD: xsmb_secret
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  scraper:
    build: .
    depends_on:
      - db
    environment:
      DATABASE_URL: postgresql+asyncpg://xsmb:xsmb_secret@db:5432/xsmb
    volumes:
      - ./exports:/app/exports

volumes:
  pgdata:
```

- [ ] **Step 4: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv pip install --system -e ".[dev]"

COPY . .

ENTRYPOINT ["python", "-m", "src.main"]
```

- [ ] **Step 5: Create src/__init__.py (empty)**

- [ ] **Step 6: Create src/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://xsmb:xsmb_secret@localhost:5432/xsmb"
    log_level: str = "INFO"

    # Source URLs
    ketqua_vn_base_url: str = "https://ketqua.vn"
    ketqua_net_base_url: str = "https://ketqua04.net"

    # Rate limiting
    ketqua_vn_delay_min: float = 1.5
    ketqua_vn_delay_max: float = 2.5
    ketqua_net_delay_min: float = 2.0
    ketqua_net_delay_max: float = 3.0
    max_retries: int = 3
    backoff_multiplier: float = 3.0
    pause_on_429: int = 60

    # Scraping
    start_date: str = "2009-01-01"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .env.example docker-compose.yml Dockerfile src/__init__.py src/config.py
git commit -m "feat: project scaffold with config, Docker, and dependencies"
```

---

### Task 2: Database Setup

**Files:**
- Create: `src/database.py`
- Create: `src/models/__init__.py`
- Create: `src/models/result.py`
- Create: `src/models/scrape_job.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/.gitkeep`

- [ ] **Step 1: Create src/database.py**

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():
    async with async_session() as session:
        yield session
```

- [ ] **Step 2: Create src/models/__init__.py**

```python
from src.models.result import XSMBResult
from src.models.scrape_job import ScrapeJob, ScrapeLog

__all__ = ["XSMBResult", "ScrapeJob", "ScrapeLog"]
```

- [ ] **Step 3: Create src/models/result.py**

```python
import datetime

from sqlalchemy import Date, Index, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class XSMBResult(Base):
    __tablename__ = "xsmb_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    draw_date: Mapped[datetime.date] = mapped_column(Date, unique=True, nullable=False)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # Prize columns
    giai_db: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_1: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_2_1: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_2_2: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_3_1: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_3_2: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_3_3: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_3_4: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_3_5: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_3_6: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_4_1: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_4_2: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_4_3: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_4_4: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_5_1: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_5_2: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_5_3: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_5_4: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_5_5: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_5_6: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_6_1: Mapped[str] = mapped_column(String(3), nullable=False)
    giai_6_2: Mapped[str] = mapped_column(String(3), nullable=False)
    giai_6_3: Mapped[str] = mapped_column(String(3), nullable=False)
    giai_7_1: Mapped[str] = mapped_column(String(2), nullable=False)
    giai_7_2: Mapped[str] = mapped_column(String(2), nullable=False)
    giai_7_3: Mapped[str] = mapped_column(String(2), nullable=False)
    giai_7_4: Mapped[str] = mapped_column(String(2), nullable=False)

    # Computed fields
    raw_string: Mapped[str | None] = mapped_column(String(110))
    loto_array: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    de_dau: Mapped[str | None] = mapped_column(String(2))
    de_duoi: Mapped[str | None] = mapped_column(String(2))

    # Metadata
    ky_tu: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str | None] = mapped_column(String(50))
    source_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_xsmb_draw_date", draw_date.desc()),
        Index("idx_xsmb_giai_db", "giai_db"),
        Index("idx_xsmb_de_dau", "de_dau"),
        Index("idx_xsmb_day_of_week", "day_of_week"),
        Index(
            "idx_xsmb_year_month",
            func.extract("year", draw_date),
            func.extract("month", draw_date),
        ),
    )
```

- [ ] **Step 4: Create src/models/scrape_job.py**

```python
import datetime

from sqlalchemy import Date, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.models.result import Base


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    total_days: Mapped[int] = mapped_column(Integer, default=0)
    scraped_days: Mapped[int] = mapped_column(Integer, default=0)
    skipped_days: Mapped[int] = mapped_column(Integer, default=0)
    failed_days: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    completed_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("scrape_jobs.id"))
    draw_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50))
    source_url: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 5: Setup Alembic**

Run: `cd /Users/tuanthanhmb/Desktop/KQ/.claude/worktrees/adoring-austin && alembic init alembic`

Then edit `alembic.ini` — set `sqlalchemy.url` to empty (will be overridden by env.py).

Edit `alembic/env.py` to use async engine:

```python
import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings
from src.models.result import Base

target_metadata = Base.metadata


def run_migrations_offline():
    url = settings.database_url.replace("+asyncpg", "")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online():
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 6: Generate initial migration**

Run: `alembic revision --autogenerate -m "initial tables"`

Verify the generated migration creates all 3 tables with correct columns.

- [ ] **Step 7: Commit**

```bash
git add src/database.py src/models/ alembic.ini alembic/
git commit -m "feat: database models and Alembic migration for xsmb_results, scrape_jobs, scrape_logs"
```

---

## Chunk 2: Utilities

### Task 3: Date Utilities

**Files:**
- Create: `src/utils/__init__.py`
- Create: `src/utils/date_utils.py`
- Create: `tests/__init__.py`
- Create: `tests/test_date_utils.py`

- [ ] **Step 1: Write failing tests for date utilities**

Create `tests/__init__.py` (empty) and `tests/test_date_utils.py`:

```python
import datetime

from src.utils.date_utils import is_tet_holiday, generate_date_range


def test_tet_2026():
    assert is_tet_holiday(datetime.date(2026, 2, 16)) is True
    assert is_tet_holiday(datetime.date(2026, 2, 19)) is True
    assert is_tet_holiday(datetime.date(2026, 2, 15)) is False
    assert is_tet_holiday(datetime.date(2026, 2, 20)) is False


def test_tet_2025():
    assert is_tet_holiday(datetime.date(2025, 1, 28)) is True
    assert is_tet_holiday(datetime.date(2025, 1, 31)) is True
    assert is_tet_holiday(datetime.date(2025, 1, 27)) is False


def test_tet_2014_cross_month():
    # 30/01 - 02/02
    assert is_tet_holiday(datetime.date(2014, 1, 30)) is True
    assert is_tet_holiday(datetime.date(2014, 2, 2)) is True
    assert is_tet_holiday(datetime.date(2014, 1, 29)) is False


def test_non_tet_date():
    assert is_tet_holiday(datetime.date(2026, 3, 14)) is False


def test_generate_date_range_reverse():
    dates = generate_date_range(
        datetime.date(2026, 3, 14),
        datetime.date(2026, 3, 10),
    )
    assert len(dates) == 5
    assert dates[0] == datetime.date(2026, 3, 14)
    assert dates[-1] == datetime.date(2026, 3, 10)


def test_generate_date_range_skips_tet():
    # 2026 Tet is 16-19/02
    dates = generate_date_range(
        datetime.date(2026, 2, 20),
        datetime.date(2026, 2, 14),
        skip_tet=True,
    )
    # 20, 15, 14 = 3 dates (16-19 skipped)
    assert datetime.date(2026, 2, 17) not in dates
    assert len(dates) == 3
    assert datetime.date(2026, 2, 20) in dates
    assert datetime.date(2026, 2, 15) in dates
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_date_utils.py -v`
Expected: ImportError

- [ ] **Step 3: Implement date_utils.py**

Create `src/utils/__init__.py` (empty) and `src/utils/date_utils.py`:

```python
import datetime

# Tet holiday ranges (inclusive): (start_date, end_date)
TET_HOLIDAYS: list[tuple[datetime.date, datetime.date]] = [
    (datetime.date(2009, 1, 25), datetime.date(2009, 1, 28)),
    (datetime.date(2010, 2, 13), datetime.date(2010, 2, 16)),
    (datetime.date(2011, 2, 2), datetime.date(2011, 2, 5)),
    (datetime.date(2012, 1, 22), datetime.date(2012, 1, 25)),
    (datetime.date(2013, 2, 9), datetime.date(2013, 2, 12)),
    (datetime.date(2014, 1, 30), datetime.date(2014, 2, 2)),
    (datetime.date(2015, 2, 18), datetime.date(2015, 2, 21)),
    (datetime.date(2016, 2, 7), datetime.date(2016, 2, 10)),
    (datetime.date(2017, 1, 27), datetime.date(2017, 1, 30)),
    (datetime.date(2018, 2, 15), datetime.date(2018, 2, 18)),
    (datetime.date(2019, 2, 4), datetime.date(2019, 2, 7)),
    (datetime.date(2020, 1, 24), datetime.date(2020, 1, 27)),
    (datetime.date(2021, 2, 11), datetime.date(2021, 2, 14)),
    (datetime.date(2022, 1, 31), datetime.date(2022, 2, 3)),
    (datetime.date(2023, 1, 21), datetime.date(2023, 1, 24)),
    (datetime.date(2024, 2, 9), datetime.date(2024, 2, 12)),
    (datetime.date(2025, 1, 28), datetime.date(2025, 1, 31)),
    (datetime.date(2026, 2, 16), datetime.date(2026, 2, 19)),
]


def is_tet_holiday(d: datetime.date) -> bool:
    for start, end in TET_HOLIDAYS:
        if start <= d <= end:
            return True
    return False


def generate_date_range(
    from_date: datetime.date,
    to_date: datetime.date,
    skip_tet: bool = False,
) -> list[datetime.date]:
    """Generate dates from from_date to to_date (inclusive), newest first."""
    if from_date < to_date:
        from_date, to_date = to_date, from_date

    dates = []
    current = from_date
    while current >= to_date:
        if not (skip_tet and is_tet_holiday(current)):
            dates.append(current)
        current -= datetime.timedelta(days=1)
    return dates
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_date_utils.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils/ tests/
git commit -m "feat: date utilities with Tet holiday detection"
```

---

### Task 4: Loto Utilities

**Files:**
- Create: `src/utils/loto_utils.py`
- Create: `tests/test_loto_utils.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_loto_utils.py`:

```python
from src.utils.loto_utils import compute_loto, compute_de_dau, compute_de_duoi, build_raw_string

# Sample data from 14-03-2026
SAMPLE_PRIZES = {
    "giai_db": "56848",
    "giai_1": "73483",
    "giai_2": ["92423", "03127"],
    "giai_3": ["91144", "79528", "68003", "34736", "86805", "73286"],
    "giai_4": ["8396", "4678", "6700", "0668"],
    "giai_5": ["9231", "4787", "8494", "9238", "8841", "1247"],
    "giai_6": ["214", "587", "621"],
    "giai_7": ["52", "55", "92", "91"],
}


def test_compute_loto():
    loto = compute_loto(SAMPLE_PRIZES)
    assert len(loto) == 27
    assert loto == [
        "00", "03", "05", "14", "21", "23", "27", "28",
        "31", "36", "38", "41", "44", "47", "48", "52",
        "55", "68", "78", "83", "86", "87", "87", "91",
        "92", "94", "96",
    ]


def test_compute_de_dau():
    assert compute_de_dau("56848") == "48"


def test_compute_de_duoi():
    assert compute_de_duoi(["52", "55", "92", "91"]) == "52"


def test_build_raw_string():
    raw = build_raw_string(SAMPLE_PRIZES)
    assert len(raw) == 107
    assert raw == "56848734839242303127911447952868003347368680573286839646786700066892314787849492388841124721458762152559291"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_loto_utils.py -v`
Expected: ImportError

- [ ] **Step 3: Implement loto_utils.py**

Create `src/utils/loto_utils.py`:

```python
def compute_loto(prizes: dict) -> list[str]:
    """Extract last 2 digits from all 27 prizes, sorted ascending."""
    all_numbers = [prizes["giai_db"], prizes["giai_1"]]
    all_numbers.extend(prizes["giai_2"])
    all_numbers.extend(prizes["giai_3"])
    all_numbers.extend(prizes["giai_4"])
    all_numbers.extend(prizes["giai_5"])
    all_numbers.extend(prizes["giai_6"])
    all_numbers.extend(prizes["giai_7"])

    loto = [n[-2:].zfill(2) for n in all_numbers]
    loto.sort()
    return loto


def compute_de_dau(giai_db: str) -> str:
    """Last 2 digits of giai dac biet."""
    return giai_db[-2:]


def compute_de_duoi(giai_7: list[str]) -> str:
    """Last 2 digits of first G7 number."""
    return giai_7[0][-2:].zfill(2)


def build_raw_string(prizes: dict) -> str:
    """Concatenate all prizes in order: DB+G1+G2+G3+G4+G5+G6+G7 = 107 chars."""
    parts = [prizes["giai_db"], prizes["giai_1"]]
    parts.extend(prizes["giai_2"])
    parts.extend(prizes["giai_3"])
    parts.extend(prizes["giai_4"])
    parts.extend(prizes["giai_5"])
    parts.extend(prizes["giai_6"])
    parts.extend(prizes["giai_7"])
    return "".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_loto_utils.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils/loto_utils.py tests/test_loto_utils.py
git commit -m "feat: loto/de computation utilities"
```

---

### Task 5: HTTP Client

**Files:**
- Create: `src/utils/http_client.py`

- [ ] **Step 1: Implement http_client.py**

```python
import asyncio
import random
import time

import httpx
import structlog

from src.config import settings

logger = structlog.get_logger()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/118.0.0.0 Safari/537.36",
]


class RateLimitedClient:
    def __init__(self, source: str):
        self.source = source
        if source == "ketqua_vn":
            self.delay_min = settings.ketqua_vn_delay_min
            self.delay_max = settings.ketqua_vn_delay_max
        else:
            self.delay_min = settings.ketqua_net_delay_min
            self.delay_max = settings.ketqua_net_delay_max

        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": random.choice(USER_AGENTS)},
        )

    async def fetch(self, url: str) -> httpx.Response | None:
        """Fetch URL with retry and rate limiting. Returns None on all retries exhausted."""
        for attempt in range(settings.max_retries + 1):
            try:
                start = time.monotonic()
                response = await self.client.get(url)
                elapsed_ms = int((time.monotonic() - start) * 1000)

                if response.status_code == 429:
                    logger.warning("rate_limited", url=url, pause=settings.pause_on_429)
                    await asyncio.sleep(settings.pause_on_429)
                    continue

                if response.status_code in (403,) or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"Server error {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                logger.info("fetched", url=url, status=response.status_code, ms=elapsed_ms)
                return response

            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                if attempt < settings.max_retries:
                    wait = 5 * (settings.backoff_multiplier ** attempt)
                    logger.warning("retry", url=url, attempt=attempt + 1, wait=wait, error=str(e))
                    await asyncio.sleep(wait)
                else:
                    logger.error("all_retries_exhausted", url=url, error=str(e))
                    return None

        return None

    async def fetch_with_delay(self, url: str) -> httpx.Response | None:
        """Fetch with polite delay after request."""
        result = await self.fetch(url)
        delay = random.uniform(self.delay_min, self.delay_max)
        await asyncio.sleep(delay)
        return result

    async def close(self):
        await self.client.aclose()
```

- [ ] **Step 2: Commit**

```bash
git add src/utils/http_client.py
git commit -m "feat: rate-limited HTTP client with retry and backoff"
```

---

**Note:** The spec's project structure includes `src/scrapers/base.py` (BaseScraper ABC). This plan omits it in favor of direct parser functions since there's no shared state or interface that benefits from an ABC — each parser is a standalone function.

## Chunk 3: Parsers

### Task 6: Validation Utilities

**Files:**
- Create: `src/scrapers/__init__.py`
- Create: `src/scrapers/parser.py`
- Create: `tests/test_validation.py`

- [ ] **Step 1: Write failing validation tests**

Create `tests/test_validation.py`:

```python
import pytest

from src.scrapers.parser import validate_prizes

VALID_PRIZES = {
    "giai_db": "56848",
    "giai_1": "73483",
    "giai_2": ["92423", "03127"],
    "giai_3": ["91144", "79528", "68003", "34736", "86805", "73286"],
    "giai_4": ["8396", "4678", "6700", "0668"],
    "giai_5": ["9231", "4787", "8494", "9238", "8841", "1247"],
    "giai_6": ["214", "587", "621"],
    "giai_7": ["52", "55", "92", "91"],
}


def test_valid_prizes():
    assert validate_prizes(VALID_PRIZES) is True


def test_wrong_count_giai_2():
    bad = {**VALID_PRIZES, "giai_2": ["92423"]}
    with pytest.raises(ValueError, match="giai_2.*expected 2"):
        validate_prizes(bad)


def test_wrong_digit_length():
    bad = {**VALID_PRIZES, "giai_db": "1234"}  # should be 5 digits
    with pytest.raises(ValueError, match="giai_db.*5 digits"):
        validate_prizes(bad)


def test_non_digit_chars():
    bad = {**VALID_PRIZES, "giai_db": "5684a"}
    with pytest.raises(ValueError, match="digits only"):
        validate_prizes(bad)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_validation.py -v`
Expected: ImportError

- [ ] **Step 3: Implement parser.py with validation**

Create `src/scrapers/__init__.py` (empty) and `src/scrapers/parser.py`:

```python
import re

# Expected structure: (key, count, digit_length)
PRIZE_SPEC = [
    ("giai_db", 1, 5),
    ("giai_1", 1, 5),
    ("giai_2", 2, 5),
    ("giai_3", 6, 5),
    ("giai_4", 4, 4),
    ("giai_5", 6, 4),
    ("giai_6", 3, 3),
    ("giai_7", 4, 2),
]

DIGIT_ONLY = re.compile(r"^\d+$")


def validate_prizes(prizes: dict) -> bool:
    """Validate prize dict has correct structure. Raises ValueError on failure."""
    for key, count, digits in PRIZE_SPEC:
        value = prizes.get(key)
        if value is None:
            raise ValueError(f"Missing key: {key}")

        if count == 1:
            values = [value]
        else:
            values = value
            if len(values) != count:
                raise ValueError(f"{key}: expected {count} values, got {len(values)}")

        for v in values:
            if not DIGIT_ONLY.match(v):
                raise ValueError(f"{key}: digits only, got '{v}'")
            if len(v) != digits:
                raise ValueError(f"{key}: expected {digits} digits, got {len(v)} in '{v}'")

    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_validation.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/scrapers/__init__.py src/scrapers/parser.py tests/test_validation.py
git commit -m "feat: prize validation with structure and digit length checks"
```

---

### Task 7: ketqua.vn Parser

**Files:**
- Create: `src/scrapers/ketqua_vn.py`
- Create: `tests/test_parser.py`
- Create: `tests/fixtures/ketqua_vn_sample.html`

**HTML Structure (from inspection):**
- Container: `div#kqxs-box`
- Table: `table.table-lotto`
- Special prize: `td.txt-special-prize` (has `l="5"` attribute)
- Normal prizes: `td.txt-normal-prize` (has `l` attribute for digit count)
- Prize rows start at row index 2 (skip header + lottery code rows)
- G3 and G5 span 2 `<tr>` rows (label td has `rowspan="2"`)
- Prize order in table: DB, G1, G2, G3(2rows), G4, G5(2rows), G6, G7

- [ ] **Step 1: Save a fixture HTML file**

First, fetch and save the actual HTML. Create `tests/fixtures/ketqua_vn_sample.html` containing a minimal reproduction of the table structure:

```html
<div class="result-board" id="kqxs-box">
  <table class="table-lotto br-8 overflow-hidden bg-white w-100 text-center">
    <tbody>
      <tr><th colspan="27">Header</th></tr>
      <tr><td colspan="27">Lottery codes</td></tr>
      <tr>
        <td colspan="3" class="color-highlight fw-medium">ĐB</td>
        <td colspan="24" class="txt-special-prize" l="5">56848</td>
      </tr>
      <tr class="bg-color-lotto-background">
        <td colspan="3" class="fw-medium">G1</td>
        <td colspan="24" class="txt-normal-prize" l="5">73483</td>
      </tr>
      <tr>
        <td colspan="3" class="fw-medium">G2</td>
        <td colspan="12" class="txt-normal-prize" l="5">92423</td>
        <td colspan="12" class="txt-normal-prize" l="5">03127</td>
      </tr>
      <tr class="bg-color-lotto-background">
        <td colspan="3" rowspan="2" class="fw-medium">G3</td>
        <td colspan="8" class="txt-normal-prize" l="5">91144</td>
        <td colspan="8" class="txt-normal-prize" l="5">79528</td>
        <td colspan="8" class="txt-normal-prize" l="5">68003</td>
      </tr>
      <tr class="bg-color-lotto-background">
        <td colspan="8" class="txt-normal-prize" l="5">34736</td>
        <td colspan="8" class="txt-normal-prize" l="5">86805</td>
        <td colspan="8" class="txt-normal-prize" l="5">73286</td>
      </tr>
      <tr>
        <td colspan="3" class="fw-medium">G4</td>
        <td colspan="6" class="txt-normal-prize" l="4">8396</td>
        <td colspan="6" class="txt-normal-prize" l="4">4678</td>
        <td colspan="6" class="txt-normal-prize" l="4">6700</td>
        <td colspan="6" class="txt-normal-prize" l="4">0668</td>
      </tr>
      <tr class="bg-color-lotto-background">
        <td colspan="3" rowspan="2" class="fw-medium">G5</td>
        <td colspan="8" class="txt-normal-prize" l="4">9231</td>
        <td colspan="8" class="txt-normal-prize" l="4">4787</td>
        <td colspan="8" class="txt-normal-prize" l="4">8494</td>
      </tr>
      <tr class="bg-color-lotto-background">
        <td colspan="8" class="txt-normal-prize" l="4">9238</td>
        <td colspan="8" class="txt-normal-prize" l="4">8841</td>
        <td colspan="8" class="txt-normal-prize" l="4">1247</td>
      </tr>
      <tr>
        <td colspan="3" class="fw-medium">G6</td>
        <td colspan="8" class="txt-normal-prize" l="3">214</td>
        <td colspan="8" class="txt-normal-prize" l="3">587</td>
        <td colspan="8" class="txt-normal-prize" l="3">621</td>
      </tr>
      <tr class="bg-color-lotto-background">
        <td colspan="3" class="fw-medium">G7</td>
        <td colspan="6" class="txt-normal-prize" l="2">52</td>
        <td colspan="6" class="txt-normal-prize" l="2">55</td>
        <td colspan="6" class="txt-normal-prize" l="2">92</td>
        <td colspan="6" class="txt-normal-prize" l="2">91</td>
      </tr>
    </tbody>
  </table>
</div>
```

- [ ] **Step 2: Write failing parser tests**

Create `tests/test_parser.py`:

```python
import datetime
from pathlib import Path

from src.scrapers.ketqua_vn import parse_ketqua_vn

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_ketqua_vn():
    html = (FIXTURES / "ketqua_vn_sample.html").read_text()
    result = parse_ketqua_vn(html)

    assert result["giai_db"] == "56848"
    assert result["giai_1"] == "73483"
    assert result["giai_2"] == ["92423", "03127"]
    assert result["giai_3"] == ["91144", "79528", "68003", "34736", "86805", "73286"]
    assert result["giai_4"] == ["8396", "4678", "6700", "0668"]
    assert result["giai_5"] == ["9231", "4787", "8494", "9238", "8841", "1247"]
    assert result["giai_6"] == ["214", "587", "621"]
    assert result["giai_7"] == ["52", "55", "92", "91"]


def test_parse_ketqua_vn_empty():
    result = parse_ketqua_vn("<html><body>No data</body></html>")
    assert result is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_parser.py -v`
Expected: ImportError

- [ ] **Step 4: Implement ketqua_vn parser**

Create `src/scrapers/ketqua_vn.py`:

```python
from bs4 import BeautifulSoup
import structlog

from src.scrapers.parser import validate_prizes

logger = structlog.get_logger()


def parse_ketqua_vn(html: str) -> dict | None:
    """Parse XSMB results from ketqua.vn HTML.

    Returns dict with keys: giai_db, giai_1, giai_2..giai_7
    or None if no results found.
    """
    soup = BeautifulSoup(html, "lxml")
    box = soup.find("div", id="kqxs-box")
    if not box:
        return None

    table = box.find("table", class_="table-lotto")
    if not table:
        return None

    # Collect all prize values in order
    special = table.find("td", class_="txt-special-prize")
    if not special:
        return None

    normals = table.find_all("td", class_="txt-normal-prize")
    if len(normals) < 26:  # 27 total - 1 special = 26 normal
        return None

    values = [special.text.strip()] + [td.text.strip() for td in normals]

    # Map to structured dict
    # Order: DB(1), G1(1), G2(2), G3(6), G4(4), G5(6), G6(3), G7(4)
    pos = 0
    result = {}
    result["giai_db"] = values[pos]; pos += 1
    result["giai_1"] = values[pos]; pos += 1
    result["giai_2"] = values[pos:pos+2]; pos += 2
    result["giai_3"] = values[pos:pos+6]; pos += 6
    result["giai_4"] = values[pos:pos+4]; pos += 4
    result["giai_5"] = values[pos:pos+6]; pos += 6
    result["giai_6"] = values[pos:pos+3]; pos += 3
    result["giai_7"] = values[pos:pos+4]; pos += 4

    try:
        validate_prizes(result)
    except ValueError as e:
        logger.error("validation_failed", source="ketqua_vn", error=str(e))
        return None

    return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_parser.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/scrapers/ketqua_vn.py tests/test_parser.py tests/fixtures/
git commit -m "feat: ketqua.vn HTML parser with validation"
```

---

### Task 8: ketqua04.net Parsers (Daily + Batch)

**Files:**
- Create: `src/scrapers/ketqua_net_daily.py`
- Create: `src/scrapers/ketqua_net_batch.py`
- Create: `tests/fixtures/ketqua_net_daily_sample.html`
- Create: `tests/fixtures/ketqua_net_batch_sample.html`
- Modify: `tests/test_parser.py` (add tests)

**HTML Structure (from inspection):**
- Daily: `table#result_tab_mb`, prizes in `div[id^="rs_"]` with `data-sofar` attr
  - `rs_0_*` = DB, `rs_1_*` = G1, ..., `rs_7_*` = G7, `rs_8_*` = ky_tu
- Batch: Multiple `div.kqbackground.vien.tb-phoi` wrappers, each containing same table structure
  - Date in `span#result_date` (non-unique across days)

- [ ] **Step 1: Create fixture HTML for daily page**

Create `tests/fixtures/ketqua_net_daily_sample.html` with minimal reproduction:

```html
<table id="result_tab_mb">
  <thead>
    <tr class="title_row">
      <td class="color333" colspan="2">
        <div class="col-sm-10">
          <span class="chu15" id="result_date">Thứ bảy ngày 14-03-2026</span>
        </div>
      </td>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Ký tự</td>
      <td>
        <div class="row-no-gutters text-center">
          <div id="rs_8_0" data-sofar="1XL-2XL-7XL-8XL-11XL-13XL-15XL-19XL" rs_len="0">1XL-2XL-7XL-8XL-11XL-13XL-15XL-19XL</div>
        </div>
      </td>
    </tr>
    <tr>
      <td>Đặc biệt</td>
      <td>
        <div class="row-no-gutters text-center">
          <div id="rs_0_0" data-sofar="56848" rs_len="5">56848</div>
        </div>
      </td>
    </tr>
    <tr>
      <td>Giải nhất</td>
      <td>
        <div class="row-no-gutters text-center">
          <div id="rs_1_0" data-sofar="73483" rs_len="5">73483</div>
        </div>
      </td>
    </tr>
    <tr>
      <td>Giải nhì</td>
      <td>
        <div class="row-no-gutters text-center">
          <div id="rs_2_0" data-sofar="92423" rs_len="5">92423</div>
          <div id="rs_2_1" data-sofar="03127" rs_len="5">03127</div>
        </div>
      </td>
    </tr>
    <tr>
      <td>Giải ba</td>
      <td>
        <div class="row-no-gutters text-center">
          <div id="rs_3_0" data-sofar="91144" rs_len="5">91144</div>
          <div id="rs_3_1" data-sofar="79528" rs_len="5">79528</div>
          <div id="rs_3_2" data-sofar="68003" rs_len="5">68003</div>
          <div id="rs_3_3" data-sofar="34736" rs_len="5">34736</div>
          <div id="rs_3_4" data-sofar="86805" rs_len="5">86805</div>
          <div id="rs_3_5" data-sofar="73286" rs_len="5">73286</div>
        </div>
      </td>
    </tr>
    <tr>
      <td>Giải tư</td>
      <td>
        <div class="row-no-gutters text-center">
          <div id="rs_4_0" data-sofar="8396" rs_len="4">8396</div>
          <div id="rs_4_1" data-sofar="4678" rs_len="4">4678</div>
          <div id="rs_4_2" data-sofar="6700" rs_len="4">6700</div>
          <div id="rs_4_3" data-sofar="0668" rs_len="4">0668</div>
        </div>
      </td>
    </tr>
    <tr>
      <td>Giải năm</td>
      <td>
        <div class="row-no-gutters text-center">
          <div id="rs_5_0" data-sofar="9231" rs_len="4">9231</div>
          <div id="rs_5_1" data-sofar="4787" rs_len="4">4787</div>
          <div id="rs_5_2" data-sofar="8494" rs_len="4">8494</div>
          <div id="rs_5_3" data-sofar="9238" rs_len="4">9238</div>
          <div id="rs_5_4" data-sofar="8841" rs_len="4">8841</div>
          <div id="rs_5_5" data-sofar="1247" rs_len="4">1247</div>
        </div>
      </td>
    </tr>
    <tr>
      <td>Giải sáu</td>
      <td>
        <div class="row-no-gutters text-center">
          <div id="rs_6_0" data-sofar="214" rs_len="3">214</div>
          <div id="rs_6_1" data-sofar="587" rs_len="3">587</div>
          <div id="rs_6_2" data-sofar="621" rs_len="3">621</div>
        </div>
      </td>
    </tr>
    <tr>
      <td>Giải bảy</td>
      <td>
        <div class="row-no-gutters text-center">
          <div id="rs_7_0" data-sofar="52" rs_len="2">52</div>
          <div id="rs_7_1" data-sofar="55" rs_len="2">55</div>
          <div id="rs_7_2" data-sofar="92" rs_len="2">92</div>
          <div id="rs_7_3" data-sofar="91" rs_len="2">91</div>
        </div>
      </td>
    </tr>
  </tbody>
</table>
```

- [ ] **Step 2: Create fixture HTML for batch page**

Create `tests/fixtures/ketqua_net_batch_sample.html` with 2 days (minimal):

```html
<div class="kqbackground vien tb-phoi">
  <div id="outer_result_mb">
    <div class="result_div" id="result_mb">
      <div class="row">
        <div class="col-sm-6 tb-phoi-6">
          <div class="color333">
            <table id="result_tab_mb">
              <thead>
                <tr class="title_row">
                  <td class="color333" colspan="2">
                    <div class="col-sm-10">
                      <span class="chu15" id="result_date">Thứ bảy ngày 14-03-2026</span>
                    </div>
                  </td>
                </tr>
              </thead>
              <tbody>
                <tr><td>Ký tự</td><td><div class="row-no-gutters text-center"><div id="rs_8_0" data-sofar="1XL-2XL-7XL-8XL-11XL-13XL-15XL-19XL">1XL-2XL-7XL-8XL-11XL-13XL-15XL-19XL</div></div></td></tr>
                <tr><td>Đặc biệt</td><td><div class="row-no-gutters text-center"><div id="rs_0_0" data-sofar="56848">56848</div></div></td></tr>
                <tr><td>Giải nhất</td><td><div class="row-no-gutters text-center"><div id="rs_1_0" data-sofar="73483">73483</div></div></td></tr>
                <tr><td>Giải nhì</td><td><div class="row-no-gutters text-center"><div id="rs_2_0" data-sofar="92423">92423</div><div id="rs_2_1" data-sofar="03127">03127</div></div></td></tr>
                <tr><td>Giải ba</td><td><div class="row-no-gutters text-center"><div id="rs_3_0" data-sofar="91144">91144</div><div id="rs_3_1" data-sofar="79528">79528</div><div id="rs_3_2" data-sofar="68003">68003</div><div id="rs_3_3" data-sofar="34736">34736</div><div id="rs_3_4" data-sofar="86805">86805</div><div id="rs_3_5" data-sofar="73286">73286</div></div></td></tr>
                <tr><td>Giải tư</td><td><div class="row-no-gutters text-center"><div id="rs_4_0" data-sofar="8396">8396</div><div id="rs_4_1" data-sofar="4678">4678</div><div id="rs_4_2" data-sofar="6700">6700</div><div id="rs_4_3" data-sofar="0668">0668</div></div></td></tr>
                <tr><td>Giải năm</td><td><div class="row-no-gutters text-center"><div id="rs_5_0" data-sofar="9231">9231</div><div id="rs_5_1" data-sofar="4787">4787</div><div id="rs_5_2" data-sofar="8494">8494</div><div id="rs_5_3" data-sofar="9238">9238</div><div id="rs_5_4" data-sofar="8841">8841</div><div id="rs_5_5" data-sofar="1247">1247</div></div></td></tr>
                <tr><td>Giải sáu</td><td><div class="row-no-gutters text-center"><div id="rs_6_0" data-sofar="214">214</div><div id="rs_6_1" data-sofar="587">587</div><div id="rs_6_2" data-sofar="621">621</div></div></td></tr>
                <tr><td>Giải bảy</td><td><div class="row-no-gutters text-center"><div id="rs_7_0" data-sofar="52">52</div><div id="rs_7_1" data-sofar="55">55</div><div id="rs_7_2" data-sofar="92">92</div><div id="rs_7_3" data-sofar="91">91</div></div></td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
<div class="kqbackground vien tb-phoi">
  <div id="outer_result_mb">
    <div class="result_div" id="result_mb">
      <div class="row">
        <div class="col-sm-6 tb-phoi-6">
          <div class="color333">
            <table id="result_tab_mb">
              <thead>
                <tr class="title_row">
                  <td class="color333" colspan="2">
                    <div class="col-sm-10">
                      <span class="chu15" id="result_date">Thứ sáu ngày 13-03-2026</span>
                    </div>
                  </td>
                </tr>
              </thead>
              <tbody>
                <tr><td>Ký tự</td><td><div class="row-no-gutters text-center"><div id="rs_8_0" data-sofar="2XL-5XL">2XL-5XL</div></div></td></tr>
                <tr><td>Đặc biệt</td><td><div class="row-no-gutters text-center"><div id="rs_0_0" data-sofar="12345">12345</div></div></td></tr>
                <tr><td>Giải nhất</td><td><div class="row-no-gutters text-center"><div id="rs_1_0" data-sofar="67890">67890</div></div></td></tr>
                <tr><td>Giải nhì</td><td><div class="row-no-gutters text-center"><div id="rs_2_0" data-sofar="11111">11111</div><div id="rs_2_1" data-sofar="22222">22222</div></div></td></tr>
                <tr><td>Giải ba</td><td><div class="row-no-gutters text-center"><div id="rs_3_0" data-sofar="33333">33333</div><div id="rs_3_1" data-sofar="44444">44444</div><div id="rs_3_2" data-sofar="55555">55555</div><div id="rs_3_3" data-sofar="66666">66666</div><div id="rs_3_4" data-sofar="77777">77777</div><div id="rs_3_5" data-sofar="88888">88888</div></div></td></tr>
                <tr><td>Giải tư</td><td><div class="row-no-gutters text-center"><div id="rs_4_0" data-sofar="1234">1234</div><div id="rs_4_1" data-sofar="5678">5678</div><div id="rs_4_2" data-sofar="9012">9012</div><div id="rs_4_3" data-sofar="3456">3456</div></div></td></tr>
                <tr><td>Giải năm</td><td><div class="row-no-gutters text-center"><div id="rs_5_0" data-sofar="1111">1111</div><div id="rs_5_1" data-sofar="2222">2222</div><div id="rs_5_2" data-sofar="3333">3333</div><div id="rs_5_3" data-sofar="4444">4444</div><div id="rs_5_4" data-sofar="5555">5555</div><div id="rs_5_5" data-sofar="6666">6666</div></div></td></tr>
                <tr><td>Giải sáu</td><td><div class="row-no-gutters text-center"><div id="rs_6_0" data-sofar="111">111</div><div id="rs_6_1" data-sofar="222">222</div><div id="rs_6_2" data-sofar="333">333</div></div></td></tr>
                <tr><td>Giải bảy</td><td><div class="row-no-gutters text-center"><div id="rs_7_0" data-sofar="11">11</div><div id="rs_7_1" data-sofar="22">22</div><div id="rs_7_2" data-sofar="33">33</div><div id="rs_7_3" data-sofar="44">44</div></div></td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Write failing tests for ketqua_net parsers**

Add to `tests/test_parser.py`:

```python
from src.scrapers.ketqua_net_daily import parse_ketqua_net_daily
from src.scrapers.ketqua_net_batch import parse_ketqua_net_batch


def test_parse_ketqua_net_daily():
    html = (FIXTURES / "ketqua_net_daily_sample.html").read_text()
    result = parse_ketqua_net_daily(html)

    assert result is not None
    assert result["giai_db"] == "56848"
    assert result["giai_1"] == "73483"
    assert result["giai_2"] == ["92423", "03127"]
    assert result["giai_3"] == ["91144", "79528", "68003", "34736", "86805", "73286"]
    assert result["giai_4"] == ["8396", "4678", "6700", "0668"]
    assert result["giai_5"] == ["9231", "4787", "8494", "9238", "8841", "1247"]
    assert result["giai_6"] == ["214", "587", "621"]
    assert result["giai_7"] == ["52", "55", "92", "91"]
    assert result["ky_tu"] == "1XL-2XL-7XL-8XL-11XL-13XL-15XL-19XL"
    assert result["date_str"] == "14-03-2026"


def test_parse_ketqua_net_batch():
    html = (FIXTURES / "ketqua_net_batch_sample.html").read_text()
    results = parse_ketqua_net_batch(html)

    assert len(results) == 2
    assert results[0]["date_str"] == "14-03-2026"
    assert results[0]["giai_db"] == "56848"
    assert results[1]["date_str"] == "13-03-2026"
    assert results[1]["giai_db"] == "12345"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_parser.py -v`
Expected: ImportError for new parsers

- [ ] **Step 5: Implement ketqua_net_daily parser**

Create `src/scrapers/ketqua_net_daily.py`:

```python
import re

from bs4 import BeautifulSoup
import structlog

from src.scrapers.parser import validate_prizes

logger = structlog.get_logger()


def _parse_result_table(table_soup) -> dict | None:
    """Parse a single result_tab_mb table into prizes dict."""
    # Extract date
    date_span = table_soup.find("span", id="result_date")
    date_str = None
    if date_span:
        match = re.search(r"(\d{2}-\d{2}-\d{4})", date_span.text)
        if match:
            date_str = match.group(1)

    # Extract ky_tu
    ky_tu = None
    ky_tu_div = table_soup.find("div", id=re.compile(r"^rs_8_"))
    if ky_tu_div:
        ky_tu = ky_tu_div.get("data-sofar", ky_tu_div.text.strip())

    # Extract prizes by ID pattern rs_{prize_idx}_{value_idx}
    # 0=DB, 1=G1, 2=G2, 3=G3, 4=G4, 5=G5, 6=G6, 7=G7
    prize_map = {
        0: ("giai_db", 1),
        1: ("giai_1", 1),
        2: ("giai_2", 2),
        3: ("giai_3", 6),
        4: ("giai_4", 4),
        5: ("giai_5", 6),
        6: ("giai_6", 3),
        7: ("giai_7", 4),
    }

    result = {}
    for prize_idx, (key, count) in prize_map.items():
        values = []
        for val_idx in range(count):
            div = table_soup.find("div", id=f"rs_{prize_idx}_{val_idx}")
            if div:
                val = div.get("data-sofar", div.text.strip())
                values.append(val.strip())

        if count == 1:
            if not values:
                return None
            result[key] = values[0]
        else:
            if len(values) != count:
                return None
            result[key] = values

    try:
        validate_prizes(result)
    except ValueError as e:
        logger.error("validation_failed", source="ketqua_net", error=str(e))
        return None

    result["date_str"] = date_str
    result["ky_tu"] = ky_tu
    return result


def parse_ketqua_net_daily(html: str) -> dict | None:
    """Parse single-day page from ketqua04.net."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="result_tab_mb")
    if not table:
        return None
    return _parse_result_table(table)
```

- [ ] **Step 6: Implement ketqua_net_batch parser**

Create `src/scrapers/ketqua_net_batch.py`:

```python
from bs4 import BeautifulSoup
import structlog

from src.scrapers.ketqua_net_daily import _parse_result_table

logger = structlog.get_logger()


def parse_ketqua_net_batch(html: str) -> list[dict]:
    """Parse batch page with multiple days from ketqua04.net.

    Returns list of result dicts, newest first.
    """
    soup = BeautifulSoup(html, "lxml")
    day_wrappers = soup.find_all("div", class_="kqbackground vien tb-phoi")

    results = []
    for wrapper in day_wrappers:
        table = wrapper.find("table", id="result_tab_mb")
        if not table:
            continue

        result = _parse_result_table(table)
        if result:
            results.append(result)
        else:
            logger.warning("batch_parse_skip", reason="parse failed for one day in batch")

    logger.info("batch_parsed", total_days=len(results))
    return results
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_parser.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/scrapers/ketqua_net_daily.py src/scrapers/ketqua_net_batch.py tests/fixtures/ tests/test_parser.py
git commit -m "feat: ketqua04.net daily and batch HTML parsers"
```

---

## Chunk 4: Services & Orchestrator

### Task 9: Result Service (UPSERT)

**Files:**
- Create: `src/services/__init__.py`
- Create: `src/services/result_service.py`

- [ ] **Step 1: Implement result_service.py**

Create `src/services/__init__.py` (empty) and `src/services/result_service.py`:

```python
import datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.result import XSMBResult
from src.utils.loto_utils import build_raw_string, compute_de_dau, compute_de_duoi, compute_loto


def prizes_to_row(draw_date: datetime.date, prizes: dict, source: str, source_url: str) -> dict:
    """Convert parsed prizes dict to DB row dict."""
    loto = compute_loto(prizes)
    raw_string = build_raw_string(prizes)
    de_dau = compute_de_dau(prizes["giai_db"])
    de_duoi = compute_de_duoi(prizes["giai_7"])

    return {
        "draw_date": draw_date,
        "day_of_week": draw_date.isoweekday() % 7,  # 0=CN, 1=T2..6=T7
        "giai_db": prizes["giai_db"],
        "giai_1": prizes["giai_1"],
        "giai_2_1": prizes["giai_2"][0],
        "giai_2_2": prizes["giai_2"][1],
        "giai_3_1": prizes["giai_3"][0],
        "giai_3_2": prizes["giai_3"][1],
        "giai_3_3": prizes["giai_3"][2],
        "giai_3_4": prizes["giai_3"][3],
        "giai_3_5": prizes["giai_3"][4],
        "giai_3_6": prizes["giai_3"][5],
        "giai_4_1": prizes["giai_4"][0],
        "giai_4_2": prizes["giai_4"][1],
        "giai_4_3": prizes["giai_4"][2],
        "giai_4_4": prizes["giai_4"][3],
        "giai_5_1": prizes["giai_5"][0],
        "giai_5_2": prizes["giai_5"][1],
        "giai_5_3": prizes["giai_5"][2],
        "giai_5_4": prizes["giai_5"][3],
        "giai_5_5": prizes["giai_5"][4],
        "giai_5_6": prizes["giai_5"][5],
        "giai_6_1": prizes["giai_6"][0],
        "giai_6_2": prizes["giai_6"][1],
        "giai_6_3": prizes["giai_6"][2],
        "giai_7_1": prizes["giai_7"][0],
        "giai_7_2": prizes["giai_7"][1],
        "giai_7_3": prizes["giai_7"][2],
        "giai_7_4": prizes["giai_7"][3],
        "raw_string": raw_string,
        "loto_array": loto,
        "de_dau": de_dau,
        "de_duoi": de_duoi,
        "ky_tu": prizes.get("ky_tu"),
        "source": source,
        "source_url": source_url,
    }


async def upsert_result(session: AsyncSession, row: dict) -> None:
    """Insert or update a result row."""
    stmt = insert(XSMBResult).values(**row)
    stmt = stmt.on_conflict_do_update(
        index_elements=["draw_date"],
        set_={k: v for k, v in row.items() if k != "draw_date"},
    )
    await session.execute(stmt)
    await session.commit()


async def date_exists(session: AsyncSession, draw_date: datetime.date) -> bool:
    """Check if a draw_date already exists in DB."""
    stmt = select(XSMBResult.id).where(XSMBResult.draw_date == draw_date)
    result = await session.execute(stmt)
    return result.scalar() is not None


async def get_missing_dates(
    session: AsyncSession,
    from_date: datetime.date,
    to_date: datetime.date,
) -> list[datetime.date]:
    """Get dates in range that are NOT in DB, ordered newest first."""
    stmt = select(XSMBResult.draw_date).where(
        XSMBResult.draw_date.between(to_date, from_date)
    )
    result = await session.execute(stmt)
    existing = {row[0] for row in result.fetchall()}

    all_dates = []
    current = from_date
    while current >= to_date:
        if current not in existing:
            all_dates.append(current)
        current -= datetime.timedelta(days=1)
    return all_dates


async def get_total_count(session: AsyncSession) -> int:
    """Get total number of results in DB."""
    result = await session.execute(text("SELECT COUNT(*) FROM xsmb_results"))
    return result.scalar() or 0


async def get_date_range(session: AsyncSession) -> tuple[datetime.date | None, datetime.date | None]:
    """Get min and max draw_date in DB."""
    result = await session.execute(
        text("SELECT MIN(draw_date), MAX(draw_date) FROM xsmb_results")
    )
    row = result.fetchone()
    if row:
        return row[0], row[1]
    return None, None
```

- [ ] **Step 2: Commit**

```bash
git add src/services/
git commit -m "feat: result service with UPSERT and date queries"
```

---

### Task 10: Orchestrator

**Files:**
- Create: `src/services/orchestrator.py`

- [ ] **Step 1: Implement orchestrator.py**

```python
import datetime
import time

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.scrape_job import ScrapeJob, ScrapeLog
from src.scrapers.ketqua_net_batch import parse_ketqua_net_batch
from src.scrapers.ketqua_net_daily import parse_ketqua_net_daily
from src.scrapers.ketqua_vn import parse_ketqua_vn
from src.services.result_service import date_exists, prizes_to_row, upsert_result
from src.utils.date_utils import generate_date_range, is_tet_holiday
from src.utils.http_client import RateLimitedClient

logger = structlog.get_logger()


class Orchestrator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.ketqua_vn_client = RateLimitedClient("ketqua_vn")
        self.ketqua_net_client = RateLimitedClient("ketqua_net")

    async def close(self):
        await self.ketqua_vn_client.close()
        await self.ketqua_net_client.close()

    async def _create_job(self, start_date: datetime.date, end_date: datetime.date) -> ScrapeJob:
        job = ScrapeJob(
            start_date=start_date,
            end_date=end_date,
            status="running",
            started_at=datetime.datetime.now(datetime.timezone.utc),
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def _log_scrape(
        self, job: ScrapeJob, draw_date: datetime.date, status: str,
        source: str = None, source_url: str = None,
        error_message: str = None, retry_count: int = 0, response_time_ms: int = None,
    ):
        log = ScrapeLog(
            job_id=job.id, draw_date=draw_date, status=status,
            source=source, source_url=source_url,
            error_message=error_message, retry_count=retry_count,
            response_time_ms=response_time_ms,
        )
        self.session.add(log)

        if status == "success":
            job.scraped_days += 1
        elif status == "skipped":
            job.skipped_days += 1
        elif status == "failed":
            job.failed_days += 1

        await self.session.commit()

    async def phase1_batch(self, job: ScrapeJob) -> int:
        """Phase 1: Batch fetch ~300 recent days from ketqua04.net."""
        url = f"{settings.ketqua_net_base_url}/so-ket-qua-truyen-thong/300"
        logger.info("phase1_start", url=url)

        start = time.monotonic()
        response = await self.ketqua_net_client.fetch(url)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if not response or response.status_code != 200:
            logger.error("phase1_failed", url=url)
            return 0

        results = parse_ketqua_net_batch(response.text)
        saved = 0
        for result in results:
            date_str = result.pop("date_str", None)
            ky_tu = result.pop("ky_tu", None)
            if not date_str:
                continue

            draw_date = datetime.datetime.strptime(date_str, "%d-%m-%Y").date()
            if await date_exists(self.session, draw_date):
                continue

            result["ky_tu"] = ky_tu
            row = prizes_to_row(draw_date, result, "ketqua_net_batch", url)
            await upsert_result(self.session, row)
            await self._log_scrape(job, draw_date, "success", "ketqua_net_batch", url,
                                   response_time_ms=elapsed_ms)
            saved += 1

        logger.info("phase1_done", parsed=len(results), saved=saved)
        return saved

    async def _scrape_single_day_vn(self, draw_date: datetime.date) -> dict | None:
        """Fetch and parse a single day from ketqua.vn."""
        date_str = draw_date.strftime("%d-%m-%Y")
        url = f"{settings.ketqua_vn_base_url}/xsmb/{date_str}"

        response = await self.ketqua_vn_client.fetch_with_delay(url)
        if not response:
            return None
        if response.status_code == 404:
            return None

        result = parse_ketqua_vn(response.text)
        if result:
            result["source_url"] = url
        return result

    async def _scrape_single_day_net(self, draw_date: datetime.date) -> dict | None:
        """Fetch and parse a single day from ketqua04.net (fallback)."""
        date_str = draw_date.strftime("%d-%m-%Y")
        url = f"{settings.ketqua_net_base_url}/xo-so-truyen-thong.php?ngay={date_str}"

        response = await self.ketqua_net_client.fetch_with_delay(url)
        if not response:
            return None
        if response.status_code == 404:
            return None

        result = parse_ketqua_net_daily(response.text)
        if result:
            result.pop("date_str", None)
            result["source_url"] = url
        return result

    async def phase2_daily(
        self, job: ScrapeJob, dates: list[datetime.date]
    ) -> tuple[int, list[datetime.date]]:
        """Phase 2: Scrape each date from ketqua.vn. Returns (saved_count, failed_dates)."""
        failed_dates = []
        saved = 0

        for i, draw_date in enumerate(dates):
            if await date_exists(self.session, draw_date):
                continue

            if is_tet_holiday(draw_date):
                await self._log_scrape(job, draw_date, "skipped", "ketqua_vn")
                logger.info("tet_skip", date=draw_date.isoformat())
                continue

            logger.info("phase2_scrape", date=draw_date.isoformat(),
                        progress=f"{i+1}/{len(dates)}")

            result = await self._scrape_single_day_vn(draw_date)
            if result:
                ky_tu = result.pop("ky_tu", None)
                source_url = result.pop("source_url", "")
                result["ky_tu"] = ky_tu
                row = prizes_to_row(draw_date, result, "ketqua_vn", source_url)
                await upsert_result(self.session, row)
                await self._log_scrape(job, draw_date, "success", "ketqua_vn", source_url)
                saved += 1
            else:
                failed_dates.append(draw_date)
                logger.warning("phase2_failed", date=draw_date.isoformat())

        return saved, failed_dates

    async def phase3_fallback(
        self, job: ScrapeJob, dates: list[datetime.date]
    ) -> int:
        """Phase 3: Fallback scrape from ketqua04.net for failed dates."""
        saved = 0
        for draw_date in dates:
            if is_tet_holiday(draw_date):
                await self._log_scrape(job, draw_date, "skipped", "ketqua_net_daily")
                continue

            result = await self._scrape_single_day_net(draw_date)
            if result:
                ky_tu = result.pop("ky_tu", None)
                source_url = result.pop("source_url", "")
                result["ky_tu"] = ky_tu
                row = prizes_to_row(draw_date, result, "ketqua_net_daily", source_url)
                await upsert_result(self.session, row)
                await self._log_scrape(job, draw_date, "success", "ketqua_net_daily", source_url)
                saved += 1
            else:
                await self._log_scrape(job, draw_date, "failed", "ketqua_net_daily",
                                       error_message="Both sources failed")

        return saved

    async def scrape_full(self) -> ScrapeJob:
        """Run full 3-phase scrape."""
        today = datetime.date.today()
        start = datetime.date(2009, 1, 1)
        job = await self._create_job(start, today)

        # Phase 1
        await self.phase1_batch(job)

        # Phase 2
        dates = generate_date_range(today, start)
        # Filter out dates already in DB
        dates_to_scrape = []
        for d in dates:
            if not await date_exists(self.session, d):
                dates_to_scrape.append(d)

        job.total_days = len(dates_to_scrape)
        await self.session.commit()

        saved2, failed = await self.phase2_daily(job, dates_to_scrape)

        # Phase 3
        if failed:
            logger.info("phase3_start", failed_count=len(failed))
            await self.phase3_fallback(job, failed)

        job.status = "completed"
        job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        await self.session.commit()
        return job

    async def scrape_range(
        self, from_date: datetime.date, to_date: datetime.date
    ) -> ScrapeJob:
        """Scrape a specific date range using Phase 2 + 3."""
        job = await self._create_job(to_date, from_date)
        dates = generate_date_range(from_date, to_date)
        job.total_days = len(dates)
        await self.session.commit()

        saved, failed = await self.phase2_daily(job, dates)
        if failed:
            await self.phase3_fallback(job, failed)

        job.status = "completed"
        job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        await self.session.commit()
        return job

    async def scrape_today(self) -> ScrapeJob:
        """Scrape today's result."""
        today = datetime.date.today()
        return await self.scrape_range(today, today)
```

- [ ] **Step 2: Commit**

```bash
git add src/services/orchestrator.py
git commit -m "feat: 3-phase scrape orchestrator with batch, daily, and fallback"
```

---

### Task 11: Export Service

**Files:**
- Create: `src/services/export_service.py`

- [ ] **Step 1: Implement export_service.py**

```python
import datetime
import json

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.result import XSMBResult


async def _fetch_results(
    session: AsyncSession,
    from_date: datetime.date | None = None,
    to_date: datetime.date | None = None,
) -> list[XSMBResult]:
    stmt = select(XSMBResult).order_by(XSMBResult.draw_date.desc())
    if from_date:
        stmt = stmt.where(XSMBResult.draw_date >= from_date)
    if to_date:
        stmt = stmt.where(XSMBResult.draw_date <= to_date)
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _result_to_dict(r: XSMBResult) -> dict:
    return {
        "draw_date": r.draw_date.isoformat(),
        "day_of_week": r.day_of_week,
        "prizes": {
            "dac_biet": r.giai_db,
            "giai_1": r.giai_1,
            "giai_2": [r.giai_2_1, r.giai_2_2],
            "giai_3": [r.giai_3_1, r.giai_3_2, r.giai_3_3, r.giai_3_4, r.giai_3_5, r.giai_3_6],
            "giai_4": [r.giai_4_1, r.giai_4_2, r.giai_4_3, r.giai_4_4],
            "giai_5": [r.giai_5_1, r.giai_5_2, r.giai_5_3, r.giai_5_4, r.giai_5_5, r.giai_5_6],
            "giai_6": [r.giai_6_1, r.giai_6_2, r.giai_6_3],
            "giai_7": [r.giai_7_1, r.giai_7_2, r.giai_7_3, r.giai_7_4],
        },
        "loto": r.loto_array,
        "de_dau": r.de_dau,
        "de_duoi": r.de_duoi,
    }


async def export_json(
    session: AsyncSession, output: str,
    from_date: datetime.date | None = None,
    to_date: datetime.date | None = None,
):
    results = await _fetch_results(session, from_date, to_date)
    data = {
        "metadata": {
            "total_records": len(results),
            "date_range": {
                "from": results[-1].draw_date.isoformat() if results else None,
                "to": results[0].draw_date.isoformat() if results else None,
            },
            "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        "results": [_result_to_dict(r) for r in results],
    }
    with open(output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def export_csv(
    session: AsyncSession, output: str,
    from_date: datetime.date | None = None,
    to_date: datetime.date | None = None,
):
    results = await _fetch_results(session, from_date, to_date)
    rows = []
    for r in results:
        rows.append({
            "draw_date": r.draw_date.isoformat(),
            "day_of_week": r.day_of_week,
            "giai_db": r.giai_db, "giai_1": r.giai_1,
            "giai_2_1": r.giai_2_1, "giai_2_2": r.giai_2_2,
            "giai_3_1": r.giai_3_1, "giai_3_2": r.giai_3_2,
            "giai_3_3": r.giai_3_3, "giai_3_4": r.giai_3_4,
            "giai_3_5": r.giai_3_5, "giai_3_6": r.giai_3_6,
            "giai_4_1": r.giai_4_1, "giai_4_2": r.giai_4_2,
            "giai_4_3": r.giai_4_3, "giai_4_4": r.giai_4_4,
            "giai_5_1": r.giai_5_1, "giai_5_2": r.giai_5_2,
            "giai_5_3": r.giai_5_3, "giai_5_4": r.giai_5_4,
            "giai_5_5": r.giai_5_5, "giai_5_6": r.giai_5_6,
            "giai_6_1": r.giai_6_1, "giai_6_2": r.giai_6_2,
            "giai_6_3": r.giai_6_3,
            "giai_7_1": r.giai_7_1, "giai_7_2": r.giai_7_2,
            "giai_7_3": r.giai_7_3, "giai_7_4": r.giai_7_4,
            "de_dau": r.de_dau, "de_duoi": r.de_duoi,
        })
    df = pd.DataFrame(rows)
    df.to_csv(output, index=False)


async def export_excel(
    session: AsyncSession, output: str,
    from_date: datetime.date | None = None,
    to_date: datetime.date | None = None,
):
    results = await _fetch_results(session, from_date, to_date)
    rows = [_result_to_dict(r) for r in results]
    # Flatten prizes for Excel
    flat_rows = []
    for row in rows:
        flat = {"draw_date": row["draw_date"], "day_of_week": row["day_of_week"]}
        flat["giai_db"] = row["prizes"]["dac_biet"]
        flat["giai_1"] = row["prizes"]["giai_1"]
        for i, v in enumerate(row["prizes"]["giai_2"]):
            flat[f"giai_2_{i+1}"] = v
        for i, v in enumerate(row["prizes"]["giai_3"]):
            flat[f"giai_3_{i+1}"] = v
        for i, v in enumerate(row["prizes"]["giai_4"]):
            flat[f"giai_4_{i+1}"] = v
        for i, v in enumerate(row["prizes"]["giai_5"]):
            flat[f"giai_5_{i+1}"] = v
        for i, v in enumerate(row["prizes"]["giai_6"]):
            flat[f"giai_6_{i+1}"] = v
        for i, v in enumerate(row["prizes"]["giai_7"]):
            flat[f"giai_7_{i+1}"] = v
        flat["de_dau"] = row["de_dau"]
        flat["de_duoi"] = row["de_duoi"]
        flat_rows.append(flat)

    df = pd.DataFrame(flat_rows)
    df.to_excel(output, index=False)
```

- [ ] **Step 2: Commit**

```bash
git add src/services/export_service.py
git commit -m "feat: export service for CSV, JSON, and Excel formats"
```

---

## Chunk 5: CLI & Integration

### Task 12: CLI Entrypoint

**Files:**
- Create: `src/main.py`

- [ ] **Step 1: Implement CLI with typer**

```python
import asyncio
import datetime

import structlog
import typer

from src.config import settings

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(__import__("logging"), settings.log_level.upper(), __import__("logging").INFO)
    ),
)

app = typer.Typer(help="XSMB Lottery Results Scraper")
db_app = typer.Typer(help="Database commands")
scrape_app = typer.Typer(help="Scraping commands")
export_app = typer.Typer(help="Export commands")
app.add_typer(db_app, name="db")
app.add_typer(scrape_app, name="scrape")
app.add_typer(export_app, name="export")


@db_app.command("init")
def db_init():
    """Initialize database with Alembic migrations."""
    import subprocess
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    typer.echo("Database initialized.")


@scrape_app.command("full")
def scrape_full():
    """Run full 3-phase hybrid scrape (2009 to today)."""
    asyncio.run(_scrape_full())


async def _scrape_full():
    from src.database import async_session
    from src.services.orchestrator import Orchestrator

    async with async_session() as session:
        orch = Orchestrator(session)
        try:
            job = await orch.scrape_full()
            typer.echo(
                f"Done! Scraped: {job.scraped_days}, "
                f"Skipped: {job.skipped_days}, Failed: {job.failed_days}"
            )
        finally:
            await orch.close()


@scrape_app.command("batch")
def scrape_batch():
    """Phase 1 only: batch fetch ~300 recent days."""
    asyncio.run(_scrape_batch())


async def _scrape_batch():
    from src.database import async_session
    from src.services.orchestrator import Orchestrator

    async with async_session() as session:
        orch = Orchestrator(session)
        try:
            from src.models.scrape_job import ScrapeJob
            job = await orch._create_job(
                datetime.date(2009, 1, 1), datetime.date.today()
            )
            saved = await orch.phase1_batch(job)
            job.status = "completed"
            job.completed_at = datetime.datetime.now(datetime.timezone.utc)
            await session.commit()
            typer.echo(f"Batch done! Saved {saved} days.")
        finally:
            await orch.close()


@scrape_app.command("range")
def scrape_range(
    from_date: str = typer.Option(..., "--from", help="Start date YYYY-MM-DD"),
    to_date: str = typer.Option(..., "--to", help="End date YYYY-MM-DD"),
):
    """Scrape a specific date range."""
    fd = datetime.date.fromisoformat(from_date)
    td = datetime.date.fromisoformat(to_date)
    asyncio.run(_scrape_range(fd, td))


async def _scrape_range(from_date: datetime.date, to_date: datetime.date):
    from src.database import async_session
    from src.services.orchestrator import Orchestrator

    async with async_session() as session:
        orch = Orchestrator(session)
        try:
            job = await orch.scrape_range(from_date, to_date)
            typer.echo(
                f"Done! Scraped: {job.scraped_days}, "
                f"Skipped: {job.skipped_days}, Failed: {job.failed_days}"
            )
        finally:
            await orch.close()


@scrape_app.command("today")
def scrape_today():
    """Scrape today's result."""
    asyncio.run(_scrape_today())


async def _scrape_today():
    from src.database import async_session
    from src.services.orchestrator import Orchestrator

    async with async_session() as session:
        orch = Orchestrator(session)
        try:
            job = await orch.scrape_today()
            typer.echo(
                f"Done! Scraped: {job.scraped_days}, "
                f"Skipped: {job.skipped_days}, Failed: {job.failed_days}"
            )
        finally:
            await orch.close()


@scrape_app.command("resume")
def scrape_resume():
    """Resume last incomplete scrape job."""
    asyncio.run(_scrape_resume())


async def _scrape_resume():
    from sqlalchemy import select
    from src.database import async_session
    from src.models.scrape_job import ScrapeJob
    from src.services.orchestrator import Orchestrator

    async with async_session() as session:
        stmt = select(ScrapeJob).where(
            ScrapeJob.status.in_(["running", "failed"])
        ).order_by(ScrapeJob.created_at.desc()).limit(1)
        result = await session.execute(stmt)
        job = result.scalar()

        if not job:
            typer.echo("No incomplete jobs to resume.")
            return

        typer.echo(f"Resuming job {job.id}: {job.start_date} to {job.end_date}")
        orch = Orchestrator(session)
        try:
            dates = []
            current = job.end_date
            while current >= job.start_date:
                dates.append(current)
                current -= datetime.timedelta(days=1)

            saved, failed = await orch.phase2_daily(job, dates)
            if failed:
                await orch.phase3_fallback(job, failed)

            job.status = "completed"
            job.completed_at = datetime.datetime.now(datetime.timezone.utc)
            await session.commit()
            typer.echo(f"Resume done! Scraped: {job.scraped_days}, Failed: {job.failed_days}")
        finally:
            await orch.close()


@app.command("status")
def status():
    """Show scraping progress and statistics."""
    asyncio.run(_status())


async def _status():
    from src.database import async_session
    from src.services.result_service import get_total_count, get_date_range

    async with async_session() as session:
        total = await get_total_count(session)
        min_date, max_date = await get_date_range(session)
        typer.echo(f"Total records: {total}")
        if min_date and max_date:
            typer.echo(f"Date range: {min_date} to {max_date}")

            # Calculate expected days (rough: ~365 * years - tet holidays)
            expected = (max_date - min_date).days + 1
            coverage = (total / expected * 100) if expected > 0 else 0
            typer.echo(f"Coverage: ~{coverage:.1f}% ({total}/{expected} days)")
        else:
            typer.echo("No data yet.")


@app.command("verify")
def verify(sample: int = typer.Option(100, "--sample", "-n", help="Number of random days to verify")):
    """Cross-validate random sample from both sources."""
    asyncio.run(_verify(sample))


async def _verify(sample: int):
    import random
    from sqlalchemy import select
    from src.database import async_session
    from src.models.result import XSMBResult
    from src.scrapers.ketqua_vn import parse_ketqua_vn
    from src.scrapers.ketqua_net_daily import parse_ketqua_net_daily
    from src.utils.http_client import RateLimitedClient

    async with async_session() as session:
        stmt = select(XSMBResult.draw_date).order_by(XSMBResult.draw_date.desc())
        result = await session.execute(stmt)
        all_dates = [row[0] for row in result.fetchall()]

        if not all_dates:
            typer.echo("No data to verify.")
            raise typer.Exit(0)

        sample_dates = random.sample(all_dates, min(sample, len(all_dates)))
        typer.echo(f"Verifying {len(sample_dates)} random dates...")

        vn_client = RateLimitedClient("ketqua_vn")
        net_client = RateLimitedClient("ketqua_net")
        mismatches = 0

        try:
            for d in sample_dates:
                date_str = d.strftime("%d-%m-%Y")

                vn_resp = await vn_client.fetch_with_delay(
                    f"https://ketqua.vn/xsmb/{date_str}"
                )
                net_resp = await net_client.fetch_with_delay(
                    f"https://ketqua04.net/xo-so-truyen-thong.php?ngay={date_str}"
                )

                vn_data = parse_ketqua_vn(vn_resp.text) if vn_resp else None
                net_data = parse_ketqua_net_daily(net_resp.text) if net_resp else None

                if vn_data and net_data:
                    net_data.pop("date_str", None)
                    net_data.pop("ky_tu", None)
                    for key in ["giai_db", "giai_1", "giai_2", "giai_3",
                                "giai_4", "giai_5", "giai_6", "giai_7"]:
                        if vn_data.get(key) != net_data.get(key):
                            typer.echo(f"MISMATCH {d}: {key} vn={vn_data.get(key)} net={net_data.get(key)}")
                            mismatches += 1
                            break

            typer.echo(f"Verified {len(sample_dates)} dates. Mismatches: {mismatches}")
            if mismatches > 0:
                raise typer.Exit(1)
        finally:
            await vn_client.close()
            await net_client.close()


@export_app.command("csv")
def export_csv_cmd(
    output: str = typer.Option("exports/xsmb.csv", "--output", "-o"),
    from_date: str = typer.Option(None, "--from"),
    to_date: str = typer.Option(None, "--to"),
):
    """Export results to CSV."""
    fd = datetime.date.fromisoformat(from_date) if from_date else None
    td = datetime.date.fromisoformat(to_date) if to_date else None
    asyncio.run(_export("csv", output, fd, td))


@export_app.command("json")
def export_json_cmd(
    output: str = typer.Option("exports/xsmb.json", "--output", "-o"),
    from_date: str = typer.Option(None, "--from"),
    to_date: str = typer.Option(None, "--to"),
):
    """Export results to JSON."""
    fd = datetime.date.fromisoformat(from_date) if from_date else None
    td = datetime.date.fromisoformat(to_date) if to_date else None
    asyncio.run(_export("json", output, fd, td))


@export_app.command("excel")
def export_excel_cmd(
    output: str = typer.Option("exports/xsmb.xlsx", "--output", "-o"),
    from_date: str = typer.Option(None, "--from"),
    to_date: str = typer.Option(None, "--to"),
):
    """Export results to Excel."""
    fd = datetime.date.fromisoformat(from_date) if from_date else None
    td = datetime.date.fromisoformat(to_date) if to_date else None
    asyncio.run(_export("excel", output, fd, td))


async def _export(fmt: str, output: str, from_date, to_date):
    import os
    from src.database import async_session
    from src.services import export_service

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

    async with async_session() as session:
        if fmt == "csv":
            await export_service.export_csv(session, output, from_date, to_date)
        elif fmt == "json":
            await export_service.export_json(session, output, from_date, to_date)
        elif fmt == "excel":
            await export_service.export_excel(session, output, from_date, to_date)

    typer.echo(f"Exported to {output}")


if __name__ == "__main__":
    app()
```

- [ ] **Step 2: Commit**

```bash
git add src/main.py
git commit -m "feat: CLI entrypoint with scrape, export, and status commands"
```

---

### Task 13: Final Setup Files

**Files:**
- Create: `exports/.gitkeep`
- Create: `.gitignore`

- [ ] **Step 1: Create .gitignore and exports dir**

`.gitignore`:
```
__pycache__/
*.pyc
.env
*.egg-info/
dist/
exports/*.csv
exports/*.json
exports/*.xlsx
.venv/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore exports/.gitkeep
git commit -m "chore: add .gitignore and exports directory"
```

---

### Task 14: Install Dependencies & Verify

- [ ] **Step 1: Install dependencies**

Run: `cd /Users/tuanthanhmb/Desktop/KQ/.claude/worktrees/adoring-austin && uv venv && uv pip install -e ".[dev]"`

- [ ] **Step 2: Run all unit tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Start Docker and init DB**

Run: `docker compose up -d db && sleep 3 && alembic upgrade head`

- [ ] **Step 4: Verify CLI works**

Run: `python -m src.main status`
Expected: "Total records: 0" / "No data yet."

- [ ] **Step 5: Commit any fixes needed**

---

### Task 15: Smoke Test with Live Data

- [ ] **Step 1: Scrape today**

Run: `python -m src.main scrape today`
Expected: "Done! Scraped: 1, Skipped: 0, Failed: 0" (unless today is Tet)

- [ ] **Step 2: Check status**

Run: `python -m src.main status`
Expected: "Total records: 1"

- [ ] **Step 3: Export and verify**

Run: `python -m src.main export json --output exports/test.json`
Verify the JSON has correct structure with 27 numbers.

- [ ] **Step 4: Scrape a small range**

Run: `python -m src.main scrape range --from 2026-03-01 --to 2026-03-10`
Expected: ~10 results scraped

- [ ] **Step 5: Verify data integrity**

Run: `python -m src.main status`
Expected: ~11 total records with correct date range

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: verify all components working with live data"
```
