# --- Final Imports ---
from flask import Flask, render_template, abort, send_from_directory, request
import os
import sqlite3
from datetime import datetime
from content_creator import fetch_and_save_content
from backup_script import upload_to_gcs
from google.cloud import storage

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

# --- App Setup ---
app = Flask(__name__)

# --- Custom Date Formatting Filter ---
@app.template_filter('strftime')
def _jinja2_filter_datetime(date_str, fmt=None):
    if not date_str: return ""
    try: date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f')
    except ValueError: date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    if fmt: return date_obj.strftime(fmt)
    else: return date_obj.strftime('%B %d, %Y')

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

# --- Main Public Routes ---
@app.route('/')
def homepage():
    """Displays the homepage with a list of recent articles."""
    articles = get_article_list()
    return render_template('index.html', articles=articles)

@app.route('/article/<int:article_id>/<slug>')
def article_page(article_id, slug):
    """Displays a single, full article page with navigation."""
    article_data = get_article_with_navigation(article_id)
    if article_data is None: abort(404)
    article_dict = dict(article_data['current'])
    if article_dict.get('commentary'):
        article_dict['commentary_paras'] = [p.strip() for p in article_dict['commentary'].split('\n') if p.strip()]
    else:
        article_dict['commentary_paras'] = []
    return render_template('article.html', article=article_dict, previous_article=article_data['previous'], next_article=article_data['next'])

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

# --- Start the server ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)