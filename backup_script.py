import os
import sqlite3
import datetime
from google.cloud import storage

# Smart Path
SOURCE_FILE_NAME = os.path.join(os.getenv('RENDER_DISK_PATH', '.'), 'content.db')

# Config
CREDENTIALS_FILE = "google_credentials.json" 
BUCKET_NAME = "lazylion-in-backup-vault"
DESTINATION_BLOB_NAME = "content_backup.db"

def upload_to_gcs():
    """Uploads DB to GCS with Safety Check AND Daily Rotation."""
    print("--- Starting Smart Database Backup ---")
    
    if not os.path.exists(SOURCE_FILE_NAME):
        raise Exception(f"Source file not found at '{SOURCE_FILE_NAME}'")

    # --- SAFETY VALVE: Check Article Count ---
    try:
        conn = sqlite3.connect(SOURCE_FILE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM articles")
        count = cursor.fetchone()[0]
        conn.close()
        
        print(f"Safety Check: Database contains {count} articles.")
        
        if count == 0:
            # KILL SWITCH
            raise Exception("SAFETY VALVE TRIGGERED: Database is empty (0 articles). Refusing to overwrite cloud backup.")
            
    except Exception as e:
        raise Exception(f"Database Integrity Check Failed: {e}")

    # --- UPLOAD WITH ROTATION ---
    try:
        storage_client = storage.Client.from_service_account_json(CREDENTIALS_FILE)
        bucket = storage_client.bucket(BUCKET_NAME)
        
        # 1. Upload Master Copy
        print(f"Uploading Master: {DESTINATION_BLOB_NAME}...")
        blob_master = bucket.blob(DESTINATION_BLOB_NAME)
        blob_master.upload_from_filename(SOURCE_FILE_NAME)
        
        # 2. Upload Daily Copy (Time Machine)
        today = datetime.datetime.now().strftime("%A") # e.g., 'Monday'
        daily_name = f"content_backup_{today}.db"
        print(f"Uploading Daily Archive: {daily_name}...")
        
        blob_daily = bucket.blob(daily_name)
        blob_daily.upload_from_filename(SOURCE_FILE_NAME)

        print("--- Backup (Master + Daily) successful! ---")
        return True

    except Exception as e:
        print(f"!!! An error occurred during backup: {e} !!!")
        raise e

if __name__ == "__main__":
    try:
        upload_to_gcs()
    except Exception as e:
        print(f"CRITICAL FAILURE: {e}")