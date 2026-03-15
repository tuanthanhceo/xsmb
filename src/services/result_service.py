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
