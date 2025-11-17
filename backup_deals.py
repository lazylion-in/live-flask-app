# IT STARTS HERE - COPY EVERYTHING BELOW THIS LINE

import os
from google.cloud import storage

# --- This is the "smart path" to our deals.csv on the persistent disk ---
# On Render, it will be '/var/data/deals.csv'. Locally, it will be './deals.csv'.
DEALS_CSV_PATH = os.path.join(os.getenv('RENDER_DISK_PATH', '.'), 'deals.csv')

# --- CONFIGURATION for Google Cloud Storage ---
CREDENTIALS_FILE = "google_credentials.json"
BUCKET_NAME = "lazylion-in-backup-vault"  # We can use the same bucket as our DB
DESTINATION_BLOB_NAME = "deals_backup.csv" # The name for the backup file in the cloud

def backup_deals_csv_to_gcs():
    """Uploads the deals.csv file from the persistent disk to Google Cloud Storage."""
    print("--- Starting deals.csv backup process ---")

    if not os.path.exists(DEALS_CSV_PATH):
        print(f"Error: Source file not found at '{DEALS_CSV_PATH}'. Skipping backup.")
        return

    try:
        storage_client = storage.Client.from_service_account_json(CREDENTIALS_FILE)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(DESTINATION_BLOB_NAME)

        print(f"Uploading '{DEALS_CSV_PATH}' to GCS bucket '{BUCKET_NAME}'...")
        blob.upload_from_filename(DEALS_CSV_PATH)

        print("--- Deals.csv backup successful! ---")

    except Exception as e:
        print(f"!!! An error occurred during deals.csv backup: {e} !!!")


def restore_deals_csv_from_gcs():
    """If the local deals.csv is missing, downloads the latest backup from GCS."""
    print("!!! DEALS PHOENIX PROTOCOL: deals.csv not found. Attempting restore. !!!")

    try:
        if not os.path.exists(CREDENTIALS_FILE):
            print("!!! DEALS PHOENIX PROTOCOL FAILED: google_credentials.json not found. !!!")
            return False

        storage_client = storage.Client.from_service_account_json(CREDENTIALS_FILE)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(DESTINATION_BLOB_NAME)

        if not blob.exists():
            print("!!! DEALS PHOENIX PROTOCOL FAILED: No backup file found in the cloud vault. !!!")
            return False

        print(f"Downloading deals backup from GCS to '{DEALS_CSV_PATH}'...")
        blob.download_to_filename(DEALS_CSV_PATH)
        print("!!! RESTORE SUCCESSFUL: deals.csv has been recovered. !!!")
        return True

    except Exception as e:
        print(f"!!! DEALS PHOENIX PROTOCOL FAILED: Could not restore. Error: {e} !!!")
        return False

# This allows the script to be run directly from the command line for testing if needed
if __name__ == "__main__":
    backup_deals_csv_to_gcs()

# IT ENDS HERE - COPY EVERYTHING ABOVE THIS LINE        