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
    dates = generate_date_range(
        datetime.date(2026, 2, 20),
        datetime.date(2026, 2, 14),
        skip_tet=True,
    )
    assert datetime.date(2026, 2, 17) not in dates
    assert len(dates) == 3
    assert datetime.date(2026, 2, 20) in dates
    assert datetime.date(2026, 2, 15) in dates
