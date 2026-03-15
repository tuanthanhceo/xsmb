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
