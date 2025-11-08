# --- Final Imports ---
from flask import Flask, render_template, abort, send_from_directory, request, make_response
import os
import sqlite3
import requests # <-- ADD THIS IMPORT
import json     # <-- ADD THIS IMPORT
from datetime import date, datetime
from content_creator import fetch_and_save_content
from backup_script import upload_to_gcs
from google.cloud import storage
from flask import send_from_directory, request

# --- This is the "smart path" to our database ---
DB_PATH = os.path.join(os.getenv('RENDER_DISK_PATH', '.'), 'content.db')

# --- Phoenix Protocol: The Restore Function ---
def restore_db_from_gcs():
    """If the local DB is missing, downloads the latest backup from GCS."""
    print("!!! PHOENIX PROTOCOL INITIATED: Database not found. Attempting restore. !!!")
    CREDENTIALS_FILE = "google_credentials.json"
    BUCKET_NAME = "lazylion-in-backup-vault"
    SOURCE_BLOB_NAME = "content_backup.db"
    DESTINATION_FILE_NAME = DB_PATH
    try:
        if not os.path.exists(CREDENTIALS_FILE):
            print("!!! PHOENIX PROTOCOL FAILED: google_credentials.json not found. !!!"); return False
        storage_client = storage.Client.from_service_account_json(CREDENTIALS_FILE)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(SOURCE_BLOB_NAME)
        if not blob.exists():
            print("!!! PHOENIX PROTOCOL FAILED: No backup file found in the cloud vault. !!!"); return False
        print(f"Downloading backup from GCS to '{DESTINATION_FILE_NAME}'...")
        blob.download_to_filename(DESTINATION_FILE_NAME)
        print("!!! RESTORE SUCCESSFUL: Database has been recovered. !!!"); return True
    except Exception as e:
        print(f"!!! PHOENIX PROTOCOL FAILED: Could not restore database. Error: {e} !!!"); return False
def calculate_reading_time(text):
    """Estimates the reading time for a piece of text."""
    if not text:
        return "1 min read"
    try:
        word_count = len(text.split())
        reading_time_minutes = word_count / 200
        return f"{max(1, round(reading_time_minutes))} min read"
    except:
        return "1 min read"
# --- App Setup ---
app = Flask(__name__)
# --- Helper function for Reading Time ---
def calculate_reading_time(text):
    """Estimates the reading time for a piece of text."""
    if not text: return "1 min read"
    try:
        word_count = len(text.split())
        reading_time_minutes = word_count / 200
        return f"{max(1, round(reading_time_minutes))} min read"
    except:
        return "1 min read"

# --- This makes the function available to ALL templates ---
@app.context_processor
def utility_processor():
    return dict(calculate_reading_time=calculate_reading_time)

# --- Custom Date Formatting Filter ---
@app.template_filter('strftime')
def _jinja2_filter_datetime(date_str, fmt=None):
    if not date_str: return ""
    try: date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f')
    except ValueError: date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    if fmt: return date_obj.strftime(fmt)
    else: return date_obj.strftime('%B %d, %Y')

def generate_seo_keywords(headline):
    """Calls Perplexity to generate SEO keywords for a headline."""
    print(f"Asking AI for SEO keywords for: '{headline}'...")
    try:
        pplx_api_key = os.getenv("PPLX_API_KEY")
        if not pplx_api_key: raise Exception("PPLX_API_KEY not set.")
        system_prompt = "You are an SEO expert. Your task is to provide a list of 5-7 relevant keywords for a given news headline. The keywords should be lowercase. Your entire response must be ONLY a comma-separated string of these keywords, with no other text."
        user_prompt = f"Generate the comma-separated keywords for this headline: {headline}"
        api_url = "https://api.perplexity.ai/chat/completions"
        headers = {"accept": "application/json", "content-type": "application/json", "authorization": f"Bearer {pplx_api_key}"}
        payload = {"model": "sonar", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        keywords_str = response.json()['choices'][0]['message']['content'].strip()
        print(f"Generated keywords: {keywords_str}")
        return keywords_str
    except Exception as e:
        print(f"Error generating SEO keywords: {e}"); return ""
    
# --- Database Helper Functions ---
def get_article_with_navigation(article_id):
    """Fetches a single article AND finds the ID/slug for the next and previous articles."""
    try:
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM articles WHERE id = ?', (article_id,))
        current_article = cursor.fetchone()
        if not current_article: return None
            
        # To get "previous", we look for a HIGHER ID because we order by DESC on the homepage
        cursor.execute('SELECT id, slug FROM articles WHERE id > ? ORDER BY id ASC LIMIT 1', (article_id,))
        previous_article = cursor.fetchone()
        
        # To get "next", we look for a LOWER ID
        cursor.execute('SELECT id, slug FROM articles WHERE id < ? ORDER BY id DESC LIMIT 1', (article_id,))
        next_article = cursor.fetchone()
        
        conn.close()
        return {"current": current_article, "previous": previous_article, "next": next_article}
    except Exception as e:
        print(f"Database error fetching article with navigation: {e}"); return None

def get_article_list(limit=10):
    """Fetches a list of the most recent articles."""
    if not os.path.exists(DB_PATH):
        if not restore_db_from_gcs(): return []
    try:
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM articles ORDER BY timestamp DESC, id DESC LIMIT ?', (limit,))
        articles = cursor.fetchall()
        conn.close()
        return articles
    except Exception as e:
        print(f"Database error fetching article list: {e}"); return []

def get_all_articles_for_sitemap():
    """Fetches ALL articles from the DB for the sitemap."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # No LIMIT here, we want everything!
        cursor.execute('SELECT id, slug, timestamp FROM articles ORDER BY timestamp DESC')
        articles = cursor.fetchall()
        conn.close()
        return articles
    except Exception as e:
        print(f"Database error for sitemap: {e}")
        return []

# --- Main Public Routes ---
@app.route('/')
def homepage():
    """Displays the homepage with a list of recent articles."""
    articles = get_article_list()
    # No extra logic needed here! The template will do the work. 
    return render_template('index.html', articles=articles)

@app.route('/article/<int:article_id>/<slug>')
def article_page(article_id, slug):
    """Displays a single, full article page."""
    article_data = get_article_with_navigation(article_id)
    if article_data is None: abort(404)
    
    article_dict = dict(article_data['current'])
    seo_keywords = generate_seo_keywords(article_dict['headline'])
    
    if article_dict.get('commentary'):
        article_dict['commentary_paras'] = [p.strip() for p in article_dict['commentary'].split('\n') if p.strip()]
    else:
        article_dict['commentary_paras'] = []
        
    # We REMOVED the redundant 'reading_time' line here 
    return render_template('article.html', article=article_dict, previous_article=article_data['previous'], next_article=article_data['next'], seo_keywords=seo_keywords) 
# --- Special File Routes ---
@app.route('/robots.txt')
def static_from_root():
    return send_from_directory(app.static_folder, request.path[1:])

# --- Secret "Cron Job" Routes ---
@app.route('/run-journalist-job-a7b3c9d1')
def run_journalist_job():
    try: fetch_and_save_content(); return "Content creator job executed successfully.", 200
    except Exception as e: return f"An error occurred: {e}", 500

@app.route('/run-backup-job-b8c4d1e2')
def run_backup_job():
    try: upload_to_gcs(); return "Backup job executed.", 200
    except Exception as e: return f"An error occurred: {e}", 500

@app.route('/sitemap.xml')
def sitemap():
    """Generates the sitemap.xml file dynamically."""
    articles = get_all_articles_for_sitemap()
    
    # We need to know the last time the site was updated
    last_updated = date.today().isoformat()
    if articles:
        # Get the date of the most recent article
        last_updated = articles[0]['timestamp'].split(' ')[0]

    # Render the sitemap template
    sitemap_xml = render_template('sitemap.xml', articles=articles, last_updated=last_updated)
    
    # Create a proper XML response
    response = make_response(sitemap_xml)
    response.headers['Content-Type'] = 'application/xml'
    
    return response

# --- Start the server ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)