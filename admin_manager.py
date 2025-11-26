import os
import csv
import json
import time
import google.generativeai as genai

# --- Define our file paths using the persistent disk ---
# This ensures we are always reading/writing to the correct location on Render
RENDER_DISK_PATH = os.getenv('RENDER_DISK_PATH', '.')
DEALS_CSV_PATH = os.path.join(RENDER_DISK_PATH, 'deals.csv')
SEED_CSV_PATH = os.path.join(RENDER_DISK_PATH, 'seed_products.csv')

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
    This is a safer way to handle CSVs and avoids newline issues.
    """
    products = []
    headers = ['slug', 'title', 'price', 'image_url', 'affiliate_link', 'category', 'keywords', 'pros', 'cons', 'description']
    
    # Read all existing products first, if the file exists
    if os.path.exists(DEALS_CSV_PATH):
        with open(DEALS_CSV_PATH, mode='r', encoding='utf-8-sig') as infile:
            reader = csv.DictReader(infile)
            products = list(reader)

    # Add the new product to our list of products
    products.append(product_data)

    # Write the entire list of products back to the file
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