import requests
import os
from dotenv import load_dotenv

load_dotenv()
EXA_API_KEY = os.getenv("EXA_API_KEY")

#using this so that it is compatible with python 3.8
def fetch_news_with_content_exa(api_key=EXA_API_KEY, query="Recent news", location="United States", num_results=1, max_characters=1000):
    url = "https://api.exa.ai/search"
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    full_query = f"{query} in {location}"
    
    data = {
        "query": full_query,
        "numResults": num_results,
        "contents": {
            "text": {
                "maxCharacters": max_characters,
                "includeHtmlTags": False
            }
        }
    }
    
    response = requests.post(url, json=data, headers=headers)
    
    if response.status_code == 200:
        results = response.json().get("results", [])
        for item in results:
            title = item.get("title", "No title")
            link = item.get("url", "No URL")
            content = item.get("text", "No content found.")
            #print(f"Title: {title}\nURL: {link}\nContent: {content}\n{'-'*40}")
        return results
    else:
        #print(f"Failed to fetch news. Status: {response.status_code}")
        #print(f"Response: {response.text}")
        return []
