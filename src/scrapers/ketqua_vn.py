from bs4 import BeautifulSoup
import structlog
from src.scrapers.parser import validate_prizes

logger = structlog.get_logger()

def parse_ketqua_vn(html: str) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    box = soup.find("div", id="kqxs-box")
    if not box:
        return None
    table = box.find("table", class_="table-lotto")
    if not table:
        return None
    special = table.find("td", class_="txt-special-prize")
    if not special:
        return None
    normals = table.find_all("td", class_="txt-normal-prize")
    if len(normals) < 26:
        return None
    values = [special.text.strip()] + [td.text.strip() for td in normals]
    pos = 0
    result = {}
    result["giai_db"] = values[pos]; pos += 1
    result["giai_1"] = values[pos]; pos += 1
    result["giai_2"] = values[pos:pos+2]; pos += 2
    result["giai_3"] = values[pos:pos+6]; pos += 6
    result["giai_4"] = values[pos:pos+4]; pos += 4
    result["giai_5"] = values[pos:pos+6]; pos += 6
    result["giai_6"] = values[pos:pos+3]; pos += 3
    result["giai_7"] = values[pos:pos+4]; pos += 4
    try:
        validate_prizes(result)
    except ValueError as e:
        logger.error("validation_failed", source="ketqua_vn", error=str(e))
        return None
    return result
