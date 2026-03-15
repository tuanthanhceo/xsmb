from bs4 import BeautifulSoup
import structlog
from src.scrapers.ketqua_net_daily import _parse_result_table

logger = structlog.get_logger()

def parse_ketqua_net_batch(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    day_wrappers = soup.find_all("div", class_="kqbackground vien tb-phoi")
    results = []
    for wrapper in day_wrappers:
        table = wrapper.find("table", id="result_tab_mb")
        if not table:
            continue
        result = _parse_result_table(table)
        if result:
            results.append(result)
        else:
            logger.warning("batch_parse_skip", reason="parse failed for one day in batch")
    logger.info("batch_parsed", total_days=len(results))
    return results
