import os
import requests
import json
import sqlite3
import random
from datetime import date, timedelta
from newsapi import NewsApiClient
import google.generativeai as genai

DB_PATH = os.path.join(os.getenv('RENDER_DISK_PATH', '.'), 'content.db')

def fetch_and_save_content():
    print("--- Running the v2.0 AI Content Journalist ---")
    
    # --- 1. Fetch a headline (Unchanged) ---
    try:
        print("Fetching a recent headline from NewsAPI...")
        # ... (This whole NewsAPI section is the same and is correct)
        news_api_key = os.getenv("NEWS_API_KEY")
        if not news_api_key: raise Exception("NEWS_API_KEY not set.")
        newsapi = NewsApiClient(api_key=news_api_key)
        keywords = 'tech OR gadget OR smartphone OR AI OR startup OR geopolitics'
        sources = 'the-times-of-india,the-hindu,google-news-in'
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        all_articles = newsapi.get_everything(q=keywords, sources=sources, language='en', from_param=yesterday, sort_by='relevancy', page_size=50)
        articles = all_articles.get("articles")
        if not articles: raise Exception("No recent articles found.")
        random_article = random.choice(articles)
        headline = random_article.get('title')
        url = random_article.get('url')
        image_url = random_article.get('urlToImage')
        if not all([headline, url, image_url]): raise Exception("Article was missing data.")
        print(f"Found article: {headline}")
    except Exception as e:
        print(f"Error fetching from NewsAPI: {e}"); return

    # --- 2. Get Structured AI Content from Perplexity (Corrected Prompt) ---
    try:
        print("Getting structured AI content from Perplexity...")
        pplx_api_key = os.getenv("PPLX_API_KEY")
        if not pplx_api_key: raise Exception("PPLX_API_KEY not set.")
        
        # This is our new prompt that ASKS FOR METADATA *in addition to* our two-paragraph commentary
        system_prompt = (
            "You are a witty and insightful analyst. Your task is to generate a complete article package for a news headline. "
            "Your entire response must be a single, valid JSON object with no other text.\n\n"
            "The JSON object must have these exact keys:\n"
            "- `commentary`: A 2-paragraph blog post. Paragraph 1 is a witty 'hot take'. Paragraph 2 provides informative SEO-friendly context.\n"
            "- `meta_description`: A 155-character, SEO-optimized summary for Google search results.\n"
            "- `title`: A catchy, engaging, rewritten headline for the article (different from the source news).\n"
            "- `slug`: A lowercase, hyphen-separated URL slug (e.g., 'delhi-bs4-ban-explained').\n"
            "- `image_alt_text`: A short, descriptive alt text for the article's main image."
        )
        user_prompt = f"Generate the structured JSON for this headline: {headline}"
        
        api_url = "https://api.perplexity.ai/chat/completions"
        headers = {"accept": "application/json", "content-type": "application/json", "authorization": f"Bearer {pplx_api_key}"}
        payload = {"model": "sonar", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}
        
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        # Clean the response to ensure it's valid JSON
        ai_response_text = response.json()['choices'][0]['message']['content']
        # Find the start and end of the JSON object to be safe
        json_start = ai_response_text.find('{')
        json_end = ai_response_text.rfind('}') + 1
        json_str = ai_response_text[json_start:json_end]
        
        ai_data = json.loads(json_str)
        # START OF CHANGE: Use the AI's new title, fallback to original if missing
        final_headline = ai_data.get('title', headline)
        # END OF CHANGE
        print("Successfully generated structured AI content.")
    except Exception as e:
        print(f"Error getting AI content: {e}"); return

    # --- 3. Save the NEW, structured data to the database ---
    try:
        print("Saving new structured content to the database...")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                headline TEXT NOT NULL,
                commentary TEXT NOT NULL,
                article_url TEXT,
                image_url TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                slug TEXT UNIQUE,
                meta_description TEXT,
                image_alt_text TEXT
            )
        ''')
        
        cursor.execute(
            'INSERT INTO articles (headline, commentary, article_url, image_url, slug, meta_description, image_alt_text) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (final_headline, ai_data['commentary'], url, image_url, ai_data['slug'], ai_data['meta_description'], ai_data['image_alt_text'])
        )
        
        conn.commit()
        conn.close()
        print("Content saved successfully!")
    except Exception as e:
        print(f"Error saving to database: {e}")
# --- NEW FUNCTION FOR ADMIN PANEL ---
def create_instant_article(topic, provider="perplexity", custom_image_url=None):
    """
    Generates an article based on a specific Admin topic.
    provider: 'perplexity' (default) or 'gemini'.
    Uses a UNIFIED prompt for consistency.
    """
    print(f"--- Running Instant Article for: {topic} using {provider.upper()} ---")
    
    ai_data = None
    
    # --- 1. Define the Master Prompt (Same for both) ---
    system_instruction = (
        "You are a witty and insightful analyst. Your task is to write a blog post about a specific topic. "
        "Your entire response must be a single, valid JSON object with NO other text (no markdown, no ```json tags).\n\n"
        "The JSON object must have these exact keys:\n"
        "- `title`: A catchy, engaging headline based on the topic.\n"
        "- `commentary`: A 2-paragraph blog post. Paragraph 1 is a witty 'hot take'. Paragraph 2 provides informative context.\n"
        "- `meta_description`: A 155-character, SEO-optimized summary.\n"
        "- `slug`: A lowercase, hyphen-separated URL slug.\n"
        "- `image_alt_text`: A short, descriptive alt text for the article's main image."
    )
    
    user_instruction = f"Write a blog post about this topic: {topic}"

    try:
        # --- PATH A: PERPLEXITY ---
        if provider == "perplexity":
            pplx_api_key = os.getenv("PPLX_API_KEY")
            if not pplx_api_key: raise Exception("PPLX_API_KEY not set.")
            
            api_url = "https://api.perplexity.ai/chat/completions"
            headers = {"accept": "application/json", "content-type": "application/json", "authorization": f"Bearer {pplx_api_key}"}
            # Perplexity likes System and User messages separated
            payload = {
                "model": "sonar", 
                "messages": [
                    {"role": "system", "content": system_instruction}, 
                    {"role": "user", "content": user_instruction}
                ]
            }
            
            response = requests.post(api_url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            
            ai_response_text = response.json()['choices'][0]['message']['content']
            # Clean JSON
            json_start = ai_response_text.find('{')
            json_end = ai_response_text.rfind('}') + 1
            ai_data = json.loads(ai_response_text[json_start:json_end])

        # --- PATH B: GEMINI ---
        elif provider == "gemini":
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            if not gemini_api_key: raise Exception("GEMINI_API_KEY not set.")
            
            genai.configure(api_key=gemini_api_key)
            model = genai.GenerativeModel('models/gemini-pro-latest')
            
            # Gemini prefers one big string
            full_prompt = f"{system_instruction}\n\n{user_instruction}"
            
            response = model.generate_content(full_prompt)
            
            # Clean JSON
            json_str = response.text.strip()
            if json_str.startswith('```json'): json_str = json_str[7:]
            if json_str.endswith('```'): json_str = json_str[:-3]
            ai_data = json.loads(json_str)

        # --- SAVE TO DB ---
        if not ai_data: raise Exception("No data returned from AI.")

        final_image_url = custom_image_url if custom_image_url else "https://images.unsplash.com/photo-1504711434969-e33886168f5c?q=80&w=2070&auto=format&fit=crop"
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT, headline TEXT, commentary TEXT, article_url TEXT,
                image_url TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, slug TEXT UNIQUE, 
                meta_description TEXT, image_alt_text TEXT
            )
        ''')
        
        # Handle slug uniqueness
        cursor.execute('SELECT id FROM articles WHERE slug = ?', (ai_data['slug'],))
        if cursor.fetchone(): ai_data['slug'] = f"{ai_data['slug']}-{random.randint(100, 999)}"

        cursor.execute(
            'INSERT INTO articles (headline, commentary, article_url, image_url, slug, meta_description, image_alt_text) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (ai_data['title'], ai_data['commentary'], "https://google.com", final_image_url, ai_data['slug'], ai_data['meta_description'], ai_data['image_alt_text'])
        )
        conn.commit()
        conn.close()
        print(f"Instant article '{ai_data['title']}' created successfully using {provider}!")
        return True

    except Exception as e:
        print(f"Error creating instant article: {e}")
        return False

if __name__ == "__main__":
    fetch_and_save_content()