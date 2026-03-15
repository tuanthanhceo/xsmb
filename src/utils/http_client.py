import asyncio
import random
import time

import httpx
import structlog

from src.config import settings

logger = structlog.get_logger()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/118.0.0.0 Safari/537.36",
]


class RateLimitedClient:
    def __init__(self, source: str):
        self.source = source
        if source == "ketqua_vn":
            self.delay_min = settings.ketqua_vn_delay_min
            self.delay_max = settings.ketqua_vn_delay_max
        else:
            self.delay_min = settings.ketqua_net_delay_min
            self.delay_max = settings.ketqua_net_delay_max

        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": random.choice(USER_AGENTS)},
        )

    async def fetch(self, url: str) -> httpx.Response | None:
        for attempt in range(settings.max_retries + 1):
            try:
                start = time.monotonic()
                response = await self.client.get(url)
                elapsed_ms = int((time.monotonic() - start) * 1000)

                if response.status_code == 429:
                    logger.warning("rate_limited", url=url, pause=settings.pause_on_429)
                    await asyncio.sleep(settings.pause_on_429)
                    continue

                if response.status_code in (403,) or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"Server error {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                logger.info("fetched", url=url, status=response.status_code, ms=elapsed_ms)
                return response

            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                if attempt < settings.max_retries:
                    wait = 5 * (settings.backoff_multiplier ** attempt)
                    logger.warning("retry", url=url, attempt=attempt + 1, wait=wait, error=str(e))
                    await asyncio.sleep(wait)
                else:
                    logger.error("all_retries_exhausted", url=url, error=str(e))
                    return None

        return None

    async def fetch_with_delay(self, url: str) -> httpx.Response | None:
        result = await self.fetch(url)
        delay = random.uniform(self.delay_min, self.delay_max)
        await asyncio.sleep(delay)
        return result

    async def close(self):
        await self.client.aclose()
