import os
from dotenv import load_dotenv
import asyncio
import pandas as pd
from tavily import TavilyClient
import time


load_dotenv()
CSV_FILE = 'University Data - Sheet1.csv'
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

class RateLimiter:
    """Rate limiter to enforce requests per minute limit"""
    def __init__(self, max_requests_per_minute=100):
        self.max_requests = max_requests_per_minute
        self.semaphore = asyncio.Semaphore(max_requests_per_minute)
        self.request_times = []
    
    async def acquire(self):
        async with self.semaphore:
            current_time = time.time()
            # Remove timestamps older than 1 minute
            self.request_times = [t for t in self.request_times if current_time - t < 60]
            # If we've hit the limit, wait until the oldest request expires
            if len(self.request_times) >= self.max_requests:
                sleep_time = 60 - (current_time - self.request_times[0]) + 0.1
                if sleep_time > 0:
                    print(f"Rate limit reached. Waiting {sleep_time:.1f} seconds...")
                    await asyncio.sleep(sleep_time)
                    self.request_times = self.request_times[1:]
            # Record this request time
            self.request_times.append(time.time())


async def search_tavily(row, rate_limiter):
    """Async function to search using Tavily API"""
    await rate_limiter.acquire()

    client = TavilyClient(TAVILY_API_KEY)
    university = row['University'].strip()
    program = row['Program'].strip()
    query = f"{university} {program} website"    
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.search(query=query)
    )
    url = response['results'][0]['url']
    title = response['results'][0]['title']
    print(f"Completed for {university} - {program}")
    return pd.Series([title, url])


async def process_all_rows(data):
    """Process all rows concurrently"""
    rate_limiter = RateLimiter(max_requests_per_minute=60)
    tasks = [search_tavily(row, rate_limiter) for _, row in data.iterrows()]
    results = await asyncio.gather(*tasks)
    return results


async def main():
    data = pd.read_csv(CSV_FILE)
    results = await process_all_rows(data)
    results_df = pd.concat(results, axis=1).T.reset_index(drop=True)
    results_df.columns = ['Title', 'URL']
    data[['Title', 'URL']] = results_df
    data.to_csv('program_webpage_url.csv', index=False)
    print("All searches completed!")

if __name__ == "__main__":
    asyncio.run(main())