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
