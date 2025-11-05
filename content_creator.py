import os
import requests
import json
import sqlite3
import random
from datetime import date, timedelta
from newsapi import NewsApiClient

# This is the "smart path" to our database. It works locally and on Render.
DB_PATH = os.path.join(os.getenv('RENDER_DISK_PATH', '.'), 'content.db')

def fetch_and_save_content():
    """
    This is our "Journalist." It fetches a new article, gets AI commentary,
    and saves it all to the database at the correct path.
    """
    print("--- Running the AI Content Journalist ---")
    
    # --- 1. Fetch a new, recent headline from NewsAPI ---
    try:
        print("Fetching a recent headline from NewsAPI...")
        news_api_key = os.getenv("NEWS_API_KEY")
        if not news_api_key: raise Exception("NEWS_API_KEY not set.")
        
        newsapi = NewsApiClient(api_key=news_api_key)
        
        keywords = 'tech OR gadget OR smartphone OR AI OR startup OR geopolitics'
        sources = 'the-times-of-india,the-hindu,google-news-in'
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        
        all_articles = newsapi.get_everything(q=keywords, sources=sources, language='en', from_param=yesterday, sort_by='relevancy', page_size=50)
        
        articles = all_articles.get("articles")
        if not articles: raise Exception("No recent articles found from NewsAPI.")
            
        random_article = random.choice(articles)
        headline = random_article.get('title')
        url = random_article.get('url')
        image_url = random_article.get('urlToImage')

        if not all([headline, url, image_url]):
            raise Exception("Article was missing a title, url, or image.")
            
        print(f"Found article: {headline}")
    except Exception as e:
        print(f"Error fetching from NewsAPI: {e}")
        return

    # --- 2. Get AI commentary from Perplexity ---
    try:
        print("Getting AI commentary from Perplexity...")
        pplx_api_key = os.getenv("PPLX_API_KEY")
        if not pplx_api_key: raise Exception("PPLX_API_KEY not set.")
        
        system_prompt = (
            "You are a witty and insightful analyst. Your persona is that of a smart friend who finds the 'real story' behind a news headline. "
            "Your task is to write a short, 2-paragraph blog post that is both engaging for humans and optimized for search engines (SEO).\n\n"
            "### CRITICAL INSTRUCTIONS:\n"
            "1.  **STRUCTURE (2 Paragraphs):**\n"
            "    *   **Paragraph 1 (The \"Hot Take\"):** Start with your clever, insightful, or ironic perspective. Find the \"real story\" or the absurdity in the situation. This is where your unique, witty voice must shine and hook the reader.\n"
            "    *   **Paragraph 2 (The \"What & Why\"):** After the hook, provide the necessary context. Clearly explain the news: what is happening and why is it important? Naturally include relevant SEO keywords.\n"
            "2.  **TONE:** The first paragraph must be witty and conversational. The second paragraph should be more informative and authoritative.\n"
            "3.  **FORMAT:** Your entire response must be ONLY the two paragraphs of the blog post. No title, no other explanations."
        )
        user_prompt = f"Write the 2-paragraph blog post for this headline: {headline}"
        
        api_url = "https://api.perplexity.ai/chat/completions"
        headers = {"accept": "application/json", "content-type": "application/json", "authorization": f"Bearer {pplx_api_key}"}
        payload = {"model": "sonar", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}
        
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        commentary = response.json()['choices'][0]['message']['content'].strip()
        print("Successfully generated AI commentary.")
    except Exception as e:
        print(f"Error getting AI commentary: {e}")
        return

    # --- 3. Save everything to the SQLite database at the correct path ---
    try:
        print(f"Saving new content to the database at {DB_PATH}...")
        conn = sqlite3.connect(DB_PATH) # <-- Uses the smart path
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                headline TEXT NOT NULL,
                commentary TEXT NOT NULL,
                article_url TEXT,
                image_url TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute(
            'INSERT INTO articles (headline, commentary, article_url, image_url) VALUES (?, ?, ?, ?)',
            (headline, commentary, url, image_url)
        )
        
        conn.commit()
        conn.close()
        print("Content saved successfully!")
    except Exception as e:
        print(f"Error saving to database: {e}")

if __name__ == "__main__":
    fetch_and_save_content()