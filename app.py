from flask import Flask, render_template
import os
import requests
import json
from newsapi import NewsApiClient
import random

app = Flask(__name__)

def get_top_headline():
    """Fetches a filtered headline from NewsAPI."""
    print("Attempting to fetch headline from NewsAPI...")
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        print("Error: NEWS_API_KEY is not set.")
        return None
    try:
        newsapi = NewsApiClient(api_key=api_key)
        keywords = 'tech OR gadget OR smartphone OR AI OR startup'
        all_articles = newsapi.get_everything(q=keywords, sources='the-times-of-india,the-hindu,google-news-in', language='en', sort_by='relevancy', page_size=20)
        articles = all_articles.get("articles")
        if not articles: return None
        random_article = random.choice(articles)
        return {"headline": random_article['title'], "url": random_article['url']}
    except Exception as e:
        print(f"NewsAPI Error: {e}")
        return None

def generate_ai_commentary(headline):
    """Generates witty commentary using Perplexity."""
    print("Attempting to get AI commentary from Perplexity...")
    api_key = os.getenv("PPLX_API_KEY")
    if not api_key:
        print("Error: PPLX_API_KEY is not set.")
        return None
    try:
        system_prompt = "You are a hyper-aware, witty, and insightful Indian assistant. Your job is to provide a short, single-paragraph commentary on a given news headline. Your tone must be lighthearted, clever, and use natural Hinglish. Your response is ONLY the paragraph of commentary."
        user_prompt = f"Write a witty, insightful paragraph about this headline: {headline}"
        api_url = "https://api.perplexity.ai/chat/completions"
        headers = {"accept": "application/json", "content-type": "application/json", "authorization": f"Bearer {api_key}"}
        payload = {"model": "sonar", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        response_data = response.json()
        return response_data['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"Perplexity API Error: {e}")
        return None

@app.route('/')
def ai_content_hub():
    """Main route that orchestrates the content generation."""
    article_data = get_top_headline()
    if not article_data:
        return render_template('index.html', error="Could not fetch a headline.")
    
    commentary = generate_ai_commentary(article_data["headline"])
    if not commentary:
        return render_template('index.html', error="Could not generate AI commentary.")

    return render_template(
        'index.html',
        headline=article_data["headline"],
        commentary=commentary,
        url=article_data["url"]
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)