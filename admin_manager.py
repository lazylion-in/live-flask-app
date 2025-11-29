import os
import csv
import json
import time
import sqlite3
import google.generativeai as genai
from backup_script import upload_to_gcs  # <-- Added for Phoenix Protocol
from content_creator import create_instant_article # <-- Added for Instant Articles
from datetime import date

# --- Define our file paths using the persistent disk ---
# This ensures we are always reading/writing to the correct location on Render
RENDER_DISK_PATH = os.getenv('RENDER_DISK_PATH', '.')
DEALS_CSV_PATH = os.path.join(RENDER_DISK_PATH, 'deals.csv')
SEED_CSV_PATH = os.path.join(RENDER_DISK_PATH, 'seed_products.csv')
DB_PATH = os.path.join(RENDER_DISK_PATH, 'content.db') # <-- Added DB Path

# --- Gemini AI Configuration ---
# We will configure the API key when the functions are called

def get_seed_products():
    """Reads the seed_products.csv file and returns a list of unprocessed products."""
    if not os.path.exists(SEED_CSV_PATH):
        return [] # Return an empty list if the file doesn't exist yet
    
    with open(SEED_CSV_PATH, mode='r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        return list(reader)

def remove_first_seed_product():
    """Reads the seed file, removes the first product (the one we just processed),
    and writes the rest back to the file."""
    products = get_seed_products()
    if not products:
        return # Nothing to do if the file is empty

    # Keep all products except the first one
    remaining_products = products[1:]

    if not remaining_products:
        # If no products are left, just delete the file
        os.remove(SEED_CSV_PATH)
        return
    
    # Write the remaining products back to the same file
    headers = remaining_products[0].keys()
    with open(SEED_CSV_PATH, mode='w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(remaining_products)

# START OF REPLACEMENT
def append_to_deals_csv(product_data):
    """
    Reads existing deals, adds the new product, and writes the entire file back.
    """
    products = []
    # ADDED 'date_added' to the end of this list
    headers = ['slug', 'title', 'price', 'image_url', 'affiliate_link', 'category', 'keywords', 'pros', 'cons', 'description', 'date_added']
    
    # Read all existing products first
    if os.path.exists(DEALS_CSV_PATH):
        with open(DEALS_CSV_PATH, mode='r', encoding='utf-8-sig') as infile:
            reader = csv.DictReader(infile)
            products = list(reader)

    # --- START CHANGE: Add Date ---
    # Add today's date to the new product data
    product_data['date_added'] = date.today().isoformat()
    # --- END CHANGE ---

    # Add the new product
    products.append(product_data)

    # Write back (Old rows will have empty dates, which is fine)
    with open(DEALS_CSV_PATH, mode='w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(products)
# END OF REPLACEMENT


def enrich_and_save_one_product():
    """
    The main logic function. Takes the oldest product from the seed file,
    enriches it with Gemini, appends it to the live deals.csv,
    and removes it from the seed queue.
    Returns the name of the processed product or None if failed.
    """
    # --- 1. Get the queue of products ---
    seed_products = get_seed_products()
    if not seed_products:
        print("Seed product queue is empty. Nothing to process.")
        return None # No products to process

    product_to_process = seed_products[0]
    product_name = product_to_process.get('product_name')
    print(f"\n-> Processing: '{product_name}'...")

    # --- 2. Configure and Call Gemini API ---
    try:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise Exception("GEMINI_API_KEY not found in environment.")
        
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('models/gemini-pro-latest')

        prompt = f"""
        You are an expert affiliate marketer and SEO content writer for an Indian e-commerce audience.
        Your task is to generate a complete data package for the product: "{product_name}".

        Your entire response MUST be a single, valid JSON object with no other text.
        The JSON object must have these exact keys:
        - "slug": A lowercase, hyphen-separated URL slug.
        - "title": A catchy, SEO-friendly title.
        - "description": A 2-paragraph, engaging summary.
        - "pros": A JSON array of 3-4 strings (key benefits).
        - "cons": A JSON array of 2-3 strings (potential drawbacks).
        - "keywords": A comma-separated string of 5-7 SEO keywords.
        - "category": Classify into ONE of: "Tech", "Kitchen", "Home Appliances", "Other".
        """

        response = model.generate_content(prompt)
        response_text = response.text.strip().replace('```json', '').replace('```', '')
        ai_data = json.loads(response_text)
        print(f"   ... Success! Content generated for '{product_name}'.")

    except Exception as e:
        print(f"   !!! ERROR: Failed to process product '{product_name}'. Reason: {e} !!!")
        return None

    # --- 3. Assemble the final data and save it ---
    try:
        final_product_data = {
            'slug': ai_data.get('slug'),
            'title': ai_data.get('title'),
            'price': product_to_process.get('price'),
            'image_url': product_to_process.get('image_url'),
            'affiliate_link': product_to_process.get('amazon_url'),
            'category': ai_data.get('category'),
            'keywords': ai_data.get('keywords'),
            'pros': "; ".join(ai_data.get('pros', [])),
            'cons': "; ".join(ai_data.get('cons', [])),
            'description': ai_data.get('description')
        }
        
        append_to_deals_csv(final_product_data)
        print(f"   ... Successfully appended '{product_name}' to deals.csv.")
        
        # --- 4. Remove the processed product from the queue ---
        remove_first_seed_product()
        print(f"   ... Removed '{product_name}' from the seed queue.")
        
        return product_name # Return the name for display on the admin page

    except Exception as e:
        print(f"   !!! ERROR: Failed to save product '{product_name}'. Reason: {e} !!!")
        return None
    # IT STARTS HERE - ADD THIS FUNCTION
def add_product_to_seed_file(product_details):
    """
    Appends a new product to the seed_products.csv file.
    `product_details` is a dictionary from the web form.
    """
    # Define the headers for our seed file
    headers = ['product_name', 'amazon_url', 'price', 'image_url']
    
    # Check if the file exists to determine if we need to write headers
    file_exists = os.path.exists(SEED_CSV_PATH)
    
    with open(SEED_CSV_PATH, mode='a', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=headers)
        
        if not file_exists:
            writer.writeheader()
        
        writer.writerow(product_details)
    
    print(f"Successfully added '{product_details['product_name']}' to the seed queue.")
# IT ENDS HERE  
# --- ARTICLE MANAGEMENT FUNCTIONS ---

def trigger_instant_article(topic, provider, image_url=None): # <-- Updated arguments
    """
    Wrapper to call the content creator and immediately trigger a backup.
    """
    # Pass the image_url to the creator
    success = create_instant_article(topic, provider, image_url) # <-- Updated call
    
    if success:
        print(f"Article created. Triggering backup...")
        upload_to_gcs()
        return True
    return False

def get_all_articles(limit=30):
    """
    Fetches the latest articles to display in the Admin Panel list.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row # Allows accessing columns by name
        cursor = conn.cursor()
        
        # Get ID, Headline, and Date (newest first)
        cursor.execute('SELECT id, headline, timestamp FROM articles ORDER BY id DESC')
        articles = cursor.fetchall()
        
        conn.close()
        return articles
    except Exception as e:
        print(f"Error fetching articles: {e}")
        return []

def delete_article(article_id):
    """
    Deletes an article by ID and triggers a backup.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM articles WHERE id = ?', (article_id,))
        conn.commit()
        conn.close()
        print(f"Article {article_id} deleted successfully.")
        
        # Trigger Phoenix Protocol Backup immediately
        upload_to_gcs()
        return True
    except Exception as e:
        print(f"Error deleting article: {e}")
        return False
# --- DASHBOARD STATS (Corrected) ---
def get_dashboard_stats():
    """Returns a dictionary of counts for the admin dashboard."""
    stats = {
        'total_articles': 0,
        'total_deals': 0,
        'queue_size': 0
    }
    
    # 1. Count Articles in DB (This was already correct)
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM articles')
        stats['total_articles'] = cursor.fetchone()[0]
        conn.close()
    except:
        pass 

    # 2. Count Deals in CSV (Fixed: Counts logical rows, not text lines)
    try:
        if os.path.exists(DEALS_CSV_PATH):
            with open(DEALS_CSV_PATH, 'r', encoding='utf-8') as f:
                # csv.reader handles multi-line fields correctly
                reader = csv.reader(f)
                # Convert to list to count items, subtract 1 for header
                row_count = len(list(reader))
                stats['total_deals'] = max(0, row_count - 1)
    except:
        pass

    # 3. Count Queue Size (Fixed)
    try:
        if os.path.exists(SEED_CSV_PATH):
            with open(SEED_CSV_PATH, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                row_count = len(list(reader))
                stats['queue_size'] = max(0, row_count - 1)
    except:
        pass
        
    return stats

def get_article_by_id(article_id):
    """Fetches a single article to populate the edit form."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM articles WHERE id = ?', (article_id,))
        article = cursor.fetchone()
        conn.close()
        return article
    except Exception as e:
        print(f"Error fetching article {article_id}: {e}")
        return None

def update_article(article_id, new_headline, new_commentary):
    """Updates an article and triggers a cloud backup."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE articles SET headline = ?, commentary = ? WHERE id = ?', 
                       (new_headline, new_commentary, article_id))
        conn.commit()
        conn.close()
        print(f"Article {article_id} updated successfully.")
        
        # Trigger Phoenix Protocol Backup immediately so changes are saved to cloud
        upload_to_gcs()
        return True
    except Exception as e:
        print(f"Error updating article: {e}")
        return False
    # --- DEALS MANAGEMENT FUNCTIONS ---

def get_all_deals():
    """Reads all live deals from the CSV to display in the admin list."""
    if not os.path.exists(DEALS_CSV_PATH):
        return []
    
    try:
        with open(DEALS_CSV_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Remove extra spaces from headers if present
            reader.fieldnames = [h.strip() for h in reader.fieldnames]
            deals = list(reader)
            # Reverse to show newest first
            return deals[::-1]
    except Exception as e:
        print(f"Error reading deals csv: {e}")
        return []

def get_deal_by_slug(slug):
    """Finds a specific deal row by its slug."""
    deals = get_all_deals() # Reuses the function above
    for deal in deals:
        if deal.get('slug') == slug:
            return deal
    return None

def update_deal(original_slug, updated_data):
    """
    Finds a deal by slug, updates its data, and rewrites the whole CSV.
    """
    try:
        # Read all rows
        with open(DEALS_CSV_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = [h.strip() for h in reader.fieldnames]
            all_rows = list(reader)
        
        # Find and update
        found = False
        for i, row in enumerate(all_rows):
            if row.get('slug') == original_slug:
                all_rows[i].update(updated_data)
                found = True
                break
        
        if not found:
            return False

        # Write everything back
        with open(DEALS_CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(all_rows)
            
        # Trigger Backup
        from backup_deals import backup_deals_csv_to_gcs
        backup_deals_csv_to_gcs()
        return True

    except Exception as e:
        print(f"Error updating deal: {e}")
        return False

def delete_deal(slug):
    """Removes a row from the CSV by slug."""
    try:
        with open(DEALS_CSV_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = [h.strip() for h in reader.fieldnames]
            all_rows = list(reader)
        
        # Filter out the one we want to delete
        new_rows = [row for row in all_rows if row.get('slug') != slug]
        
        if len(new_rows) == len(all_rows):
            return False # Nothing was deleted

        # Write back
        with open(DEALS_CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(new_rows)
            
        # Trigger Backup
        from backup_deals import backup_deals_csv_to_gcs
        backup_deals_csv_to_gcs()
        return True

    except Exception as e:
        print(f"Error deleting deal: {e}")
        return False