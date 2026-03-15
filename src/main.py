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
