import datetime

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
