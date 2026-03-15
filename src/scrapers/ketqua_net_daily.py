import re
from bs4 import BeautifulSoup
import structlog
from src.scrapers.parser import validate_prizes

logger = structlog.get_logger()

def _parse_result_table(table_soup) -> dict | None:
    date_span = table_soup.find("span", id="result_date")
    date_str = None
    if date_span:
        match = re.search(r"(\d{2}-\d{2}-\d{4})", date_span.text)
        if match:
            date_str = match.group(1)
    ky_tu = None
    ky_tu_div = table_soup.find("div", id=re.compile(r"^rs_8_"))
    if ky_tu_div:
        ky_tu = ky_tu_div.get("data-sofar", ky_tu_div.text.strip())
    prize_map = {
        0: ("giai_db", 1), 1: ("giai_1", 1), 2: ("giai_2", 2),
        3: ("giai_3", 6), 4: ("giai_4", 4), 5: ("giai_5", 6),
        6: ("giai_6", 3), 7: ("giai_7", 4),
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
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="result_tab_mb")
    if not table:
        return None
    return _parse_result_table(table)
