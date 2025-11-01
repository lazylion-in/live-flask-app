from flask import Flask, render_template
import os
import sqlite3
from datetime import datetime

app = Flask(__name__)

# This custom filter is needed to format the date in our HTML template
@app.template_filter('strftime')
def _jinja2_filter_datetime(date_str, fmt=None):
    try:
        # Try to parse with microseconds first
        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        # If that fails, parse without microseconds
        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    
    if fmt:
        return date_obj.strftime(fmt)
    else:
        return date_obj.strftime('%B %d, %Y')

def get_articles_from_db():
    """Fetches the most recent articles from the SQLite database."""
    db_file = 'content.db'
    if not os.path.exists(db_file):
        print("Database file not found. Please run content_creator.py first.")
        return [] # Return an empty list if the database doesn't exist yet
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM articles ORDER BY timestamp DESC LIMIT 10')
        articles = cursor.fetchall()
        conn.close()
        return articles
    except Exception as e:
        print(f"Database error: {e}")
        return []

@app.route('/')
def homepage():
    """Fetches articles from the DB, processes them, and displays them."""
    raw_articles = get_articles_from_db()
    
    # We will process the articles to split the commentary
    articles_for_page = []
    for article in raw_articles:
        # Convert the database row to a dictionary so we can modify it
        article_dict = dict(article)
        # Split the commentary by newline characters
        article_dict['commentary_paras'] = article_dict['commentary'].split('\n')
        articles_for_page.append(article_dict)
        
    return render_template('index.html', articles=articles_for_page)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)