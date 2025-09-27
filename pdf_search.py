import pandas as pd
from tavily import TavilyClient
import json

TAVILY_API_KEY = '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'
CSV_FILE = 'University Data - Sheet1.csv'

def search_tavily(row):
    client = TavilyClient(TAVILY_API_KEY)
    university = row['University'].strip()
    program = row['Program'].strip()
    query = f"{university} {program} Graduate handbook 24-25 academic year pdf"
    response = client.search(
        query=query
    )
    url = response['results'][0]['url']
    title = response['results'][0]['title']
    print(f"Completed for {university} - {program}")
    return pd.Series([title, url])

def main():
    data = pd.read_csv(CSV_FILE)
    data[['Title', 'URL']] = data.apply(search_tavily, axis=1)
    data.to_csv('output.csv', index=False)

if __name__ == "__main__":
    main()