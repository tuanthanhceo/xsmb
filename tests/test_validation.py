import pytest
from src.scrapers.parser import validate_prizes

VALID_PRIZES = {
    "giai_db": "56848", "giai_1": "73483",
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
    bad = {**VALID_PRIZES, "giai_db": "1234"}
    with pytest.raises(ValueError, match="giai_db.*5 digits"):
        validate_prizes(bad)

def test_non_digit_chars():
    bad = {**VALID_PRIZES, "giai_db": "5684a"}
    with pytest.raises(ValueError, match="digits only"):
        validate_prizes(bad)
