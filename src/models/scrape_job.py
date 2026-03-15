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
