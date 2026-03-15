from pathlib import Path
from src.scrapers.ketqua_vn import parse_ketqua_vn
from src.scrapers.ketqua_net_daily import parse_ketqua_net_daily
from src.scrapers.ketqua_net_batch import parse_ketqua_net_batch

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
