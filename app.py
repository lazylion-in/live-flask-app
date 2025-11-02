from flask import Flask, render_template
import os
import sqlite3
from datetime import datetime
# Import the function from our other script
from content_creator import fetch_and_save_content

app = Flask(__name__)

# This custom filter formats the date in our HTML template
@app.template_filter('strftime')
def _jinja2_filter_datetime(date_str, fmt=None):
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    if fmt: return date_obj.strftime(fmt)
    else: return date_obj.strftime('%B %d, %Y')

def get_articles_from_db():
    """Fetches the most recent articles from the SQLite database."""
    db_file = 'content.db'
    if not os.path.exists(db_file): return []
    try:
        conn = sqlite3.connect(db_file); conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM articles ORDER BY timestamp DESC LIMIT 10')
        articles = cursor.fetchall()
        conn.close()
        return articles
    except Exception as e:
        print(f"Database error: {e}"); return []

# --- This is the main homepage route with the paragraph-splitting logic ---
@app.route('/')
def homepage():
    """Fetches articles from the DB, processes them for display, and then shows them."""
    raw_articles = get_articles_from_db()
    articles_for_page = []
    for article in raw_articles:
        article_dict = dict(article)
        if article_dict.get('commentary'):
             article_dict['commentary_paras'] = article_dict['commentary'].split('\n')
        else:
             article_dict['commentary_paras'] = ["(No commentary available)"]
        articles_for_page.append(article_dict)
    return render_template('index.html', articles=articles_for_page)

# --- THIS IS OUR NEW, SECRET "CRON JOB" ROUTE ---
@app.route('/run-journalist-job-a7b3c9d1') # A hard-to-guess secret URL
def run_journalist_job():
    """When this URL is visited, it runs our content creator function."""
    print("Received a request to run the journalist job...")
    try:
        fetch_and_save_content()
        return "Content creator job executed successfully.", 200
    except Exception as e:
        print(f"Error during scheduled job run: {e}")
        return f"An error occurred: {e}", 500

# --- This is the final part of the file ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)