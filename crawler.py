import os
import asyncio
from crawl4ai import BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai import AsyncWebCrawler, RateLimiter, SemaphoreDispatcher, CrawlerMonitor, DisplayMode
import pandas as pd

async def crawl_with_semaphore(urls):
    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    dispatcher = SemaphoreDispatcher(
        max_session_permit=60,
        rate_limiter=RateLimiter(
            base_delay=(2.0, 4.0),
            max_delay=10.0,
            max_retries=3,
            rate_limit_codes=[429, 503] 
        ),
        monitor=CrawlerMonitor()
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun_many(
            urls, 
            config=run_config,
            dispatcher=dispatcher
        )
        return results

def main(data_loc):
    data = pd.read_csv(data_loc)
    urls = data['URL'].tolist()
    results = asyncio.run(crawl_with_semaphore(urls))
    print(results[1].markdown)


if __name__ == "__main__":
    data_location = 'program_webpage_url_tavily.csv'
    main(data_location)
