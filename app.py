# --- Final Imports ---
from flask import Flask, render_template
import os
import sqlite3
from datetime import datetime
from content_creator import fetch_and_save_content
from google.cloud import storage
from backup_script import upload_to_gcs

# --- This is the "smart path" to our database. It works locally and on Render. ---
DB_PATH = os.path.join(os.getenv('RENDER_DISK_PATH', '.'), 'content.db')

# --- Phoenix Protocol: The Restore Function ---
def restore_db_from_gcs():
    """
    If the local database is missing, this function downloads the latest
    backup from our Google Cloud Storage vault.
    """
    print("!!! PHOENIX PROTOCOL INITIATED: Database not found. Attempting restore from backup. !!!")
    
    CREDENTIALS_FILE = "google_credentials.json"
    BUCKET_NAME = "lazylion-in-backup-vault" # Your bucket name
    SOURCE_BLOB_NAME = "content_backup.db" # The file to download
    DESTINATION_FILE_NAME = DB_PATH # The smart path to save the file to

    try:
        # Check if we have the credentials to perform the restore
        if not os.path.exists(CREDENTIALS_FILE):
            print("!!! PHOENIX PROTOCOL FAILED: google_credentials.json not found. !!!")
            return False

        storage_client = storage.Client.from_service_account_json(CREDENTIALS_FILE)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(SOURCE_BLOB_NAME)
        
        # Check if a backup even exists in the cloud
        if not blob.exists():
            print("!!! PHOENIX PROTOCOL FAILED: No backup file found in the cloud vault. !!!")
            return False
            
        print(f"Downloading backup '{SOURCE_BLOB_NAME}' from GCS to '{DESTINATION_FILE_NAME}'...")
        blob.download_to_filename(DESTINATION_FILE_NAME)
        
        print("!!! RESTORE SUCCESSFUL: Database has been recovered from backup. !!!")
        return True
    except Exception as e:
        print(f"!!! PHOENIX PROTOCOL FAILED: Could not restore database. Error: {e} !!!")
        return False

# --- App Setup ---
app = Flask(__name__)

# --- Custom Date Formatting Filter ---
@app.template_filter('strftime')
def _jinja2_filter_datetime(date_str, fmt=None):
    if not date_str:
        return ""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    
    if fmt: return date_obj.strftime(fmt)
    else: return date_obj.strftime('%B %d, %Y')

# --- Main Database Reading Function ---
def get_articles_from_db():
    """
    Fetches articles from the DB. If the DB doesn't exist, it
    triggers the Phoenix Protocol to restore it from backup.
    """
    # Check if the database exists. If not, try to restore it.
    if not os.path.exists(DB_PATH):
        restore_success = restore_db_from_gcs()
        # If restore failed, we have no data to show.
        if not restore_success:
            return []
            
    # Now, proceed to read the database as normal
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM articles ORDER BY timestamp DESC LIMIT 10')
        articles = cursor.fetchall()
        conn.close()
        return articles
    except Exception as e:
        print(f"Database read error after potential restore: {e}")
        return []

# --- Main Homepage Route ---
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

# --- Secret "Cron Job" Route ---
@app.route('/run-journalist-job-a7b3c9d1')
def run_journalist_job():
    """When this URL is visited, it runs our content creator function."""
    print("Received a request to run the journalist job...")
    try:
        fetch_and_save_content()
        return "Content creator job executed successfully.", 200
    except Exception as e:
        print(f"Error during scheduled job run: {e}")
        return f"An error occurred: {e}", 500

@app.route('/run-backup-job-b8c4d1e2') # A different secret URL
def run_backup_job():
    print("Received a request to run the backup job...")
    upload_to_gcs()
    return "Backup job executed.", 200

# --- Start the server ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)