import os
from google.cloud import storage

# This is the "smart path" to our local database file.
# On Render, it will be '/var/data/content.db'. Locally, it will be './content.db'.
SOURCE_FILE_NAME = os.path.join(os.getenv('RENDER_DISK_PATH', '.'), 'content.db')

# --- CONFIGURATION for Google Cloud Storage ---
CREDENTIALS_FILE = "google_credentials.json" 
BUCKET_NAME = "lazylion-in-backup-vault"
DESTINATION_BLOB_NAME = "content_backup.db"

def upload_to_gcs():
    """Uploads the local database file to the Google Cloud Storage vault."""
    print("--- Starting daily database backup process ---")
    
    if not os.path.exists(SOURCE_FILE_NAME):
        print(f"Error: Source file not found at '{SOURCE_FILE_NAME}'. Skipping backup.")
        return

    try:
        storage_client = storage.Client.from_service_account_json(CREDENTIALS_FILE)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(DESTINATION_BLOB_NAME)
        
        print(f"Uploading '{SOURCE_FILE_NAME}' to Google Cloud Storage bucket '{BUCKET_NAME}'...")
        blob.upload_from_filename(SOURCE_FILE_NAME)
        
        print("--- Backup successful! ---")

    except Exception as e:
        print(f"!!! An error occurred during backup: {e} !!!")

if __name__ == "__main__":
    upload_to_gcs()