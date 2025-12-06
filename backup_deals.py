import os
import csv
import datetime
from google.cloud import storage

# Smart Path
DEALS_CSV_PATH = os.path.join(os.getenv('RENDER_DISK_PATH', '.'), 'deals.csv')

# Config
CREDENTIALS_FILE = "google_credentials.json"
BUCKET_NAME = "lazylion-in-backup-vault"
DESTINATION_BLOB_NAME = "deals_backup.csv"

def backup_deals_csv_to_gcs():
    """Uploads deals.csv to GCS with Safety Check AND Daily Rotation."""
    print("--- Starting Smart Deals Backup ---")

    if not os.path.exists(DEALS_CSV_PATH):
        raise Exception(f"Source file not found at '{DEALS_CSV_PATH}'")

    # --- SAFETY VALVE: Check Line Count ---
    try:
        with open(DEALS_CSV_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            row_count = len(lines)
            
        print(f"Safety Check: CSV contains {row_count} lines.")
        
        # Expect at least 2 lines (Header + 1 Product)
        if row_count < 2:
            raise Exception(f"SAFETY VALVE TRIGGERED: CSV is nearly empty ({row_count} lines). Refusing to overwrite.")
            
    except Exception as e:
        raise Exception(f"CSV Integrity Check Failed: {e}")

    # --- UPLOAD WITH ROTATION ---
    try:
        storage_client = storage.Client.from_service_account_json(CREDENTIALS_FILE)
        bucket = storage_client.bucket(BUCKET_NAME)
        
        # 1. Upload Master
        print(f"Uploading Master: {DESTINATION_BLOB_NAME}...")
        blob_master = bucket.blob(DESTINATION_BLOB_NAME)
        blob_master.upload_from_filename(DEALS_CSV_PATH)

        # 2. Upload Daily Archive
        today = datetime.datetime.now().strftime("%A")
        daily_name = f"deals_backup_{today}.csv"
        print(f"Uploading Daily Archive: {daily_name}...")
        
        blob_daily = bucket.blob(daily_name)
        blob_daily.upload_from_filename(DEALS_CSV_PATH)

        print("--- Deals Backup (Master + Daily) successful! ---")
        return True

    except Exception as e:
        print(f"!!! An error occurred during backup: {e} !!!")
        raise e

def restore_deals_csv_from_gcs():
    """Restores deals.csv if missing."""
    print("!!! DEALS PHOENIX PROTOCOL: deals.csv missing or corrupt. Attempting restore. !!!")
    try:
        if not os.path.exists(CREDENTIALS_FILE): return False
        storage_client = storage.Client.from_service_account_json(CREDENTIALS_FILE)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(DESTINATION_BLOB_NAME)
        if not blob.exists(): return False
        
        print(f"Downloading deals backup to '{DEALS_CSV_PATH}'...")
        blob.download_to_filename(DEALS_CSV_PATH)
        print("!!! RESTORE SUCCESSFUL !!!")
        return True
    except Exception as e:
        print(f"!!! RESTORE ERROR: {e} !!!")
        return False

if __name__ == "__main__":
    try:
        backup_deals_csv_to_gcs()
    except Exception as e:
        print(f"CRITICAL FAILURE: {e}")