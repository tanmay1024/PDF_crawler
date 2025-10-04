import os
from dotenv import load_dotenv
import asyncio
import requests
import numpy as np
import pandas as pd
from tavily import TavilyClient
import time
from sentence_transformers import SentenceTransformer, util
from sklearn.metrics.pairwise import cosine_similarity
from openai import OpenAI

load_dotenv()
CSV_FILE = 'University Data - Sheet1.csv'
LANGSEARCH_API_KEY = os.getenv("LANGSEARCH_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COUNT = 20

class RateLimiter:
    """Simple rate limiter - one request per second"""
    def __init__(self, requests_per_second=1):
        self.delay = (1.0 / requests_per_second) + 0.1 # For 1 req/sec, this is 1.0
        self.last_request_time = 0
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        async with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < self.delay:
                wait_time = self.delay - time_since_last
                print(f"Rate limiting: waiting {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)
            
            self.last_request_time = time.time()

async def langsearch_websearch_tool(row, rate_limiter, model):
    await rate_limiter.acquire()

    university = row['University'].strip()
    program = row['Program'].strip()
    query = f"{university} {program} website"  
    url = "https://api.langsearch.com/v1/web-search"
    headers = {
        "Authorization": f"Bearer {LANGSEARCH_API_KEY}",  # Please replace with your API key
        "Content-Type": "application/json"
    }
    data = {
        "query": query,
        "freshness": "noLimit",  # Search time range, e.g., "oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"
        "summary": False,          # Whether to return a long text summary
        "count": COUNT
    }
 
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: requests.post(url, headers=headers, json=data)
    )
 
    if response.status_code == 200:
        json_response = response.json()
        try:
            if json_response["code"] != 200 or not json_response["data"]:
                return pd.Series([query, f"Search API request failed, reason: {response.msg or 'Unknown error'}"])
            
            webpages = json_response["data"]["webPages"]["value"]
            if not webpages:
                return pd.Series([query, "No relevant results found."])
            
            query_embedding = model.encode(query, convert_to_tensor=True)
            best_page_score = 0
            for pages in webpages:
                page_url = pages["url"]
                page_title = pages["name"]
                title_embedding = model.encode(page_title, convert_to_tensor=True)
                similarity_score = util.cos_sim(title_embedding, query_embedding)
                if similarity_score > best_page_score and ".edu" in page_url:
                    best_page_score = similarity_score
                    best_page_url = page_url
                    best_page_title = page_title
            return pd.Series([best_page_title, best_page_url])
        except Exception as e:
            return pd.Series([query, f"Search API request failed, reason: Failed to parse search results {str(e)}"])
    else:
        return pd.Series([query, f"Search API request failed, status code: {response.status_code}, error message: {response.text}"])


async def process_all_rows(data):
    """Process all rows concurrently"""
    model = SentenceTransformer('all-MiniLM-L6-v2')
    rate_limiter = RateLimiter(requests_per_second=0.8)
    tasks = [langsearch_websearch_tool(row, rate_limiter, model) for _, row in data.iterrows()]
    results = await asyncio.gather(*tasks)
    return results


async def main():
    data = pd.read_csv(CSV_FILE)
    results = await process_all_rows(data)
    results_df = pd.concat(results, axis=1).T.reset_index(drop=True)
    results_df.columns = ['Title', 'URL']
    data[['Title', 'URL']] = results_df
    data.to_csv('program_webpage_url_langsearch.csv', index=False)
    print("All searches completed!")

if __name__ == "__main__":
    asyncio.run(main())