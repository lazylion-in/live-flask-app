# IT STARTS HERE - COPY EVERYTHING BELOW THIS LINE

import os
import csv
import json
import time # <-- THIS IS THE FIRST CHANGE
import google.generativeai as genai
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv(dotenv_path='../.env') 
SEED_FILE = 'seed_products.csv'
OUTPUT_FILE = 'deals_new.csv'

def enrich_products():
    """
    Reads a seed file of products, enriches them with AI-generated content,
    and writes the result to a new CSV file ready for the website.
    """
    print("--- Starting the AI Product Enrichment Script ---")

    # --- 1. Configure the Gemini API ---
    try:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise Exception("GEMINI_API_KEY not found in .env file.")
        genai.configure(api_key=gemini_api_key)
        # We are using a model name confirmed to be available on your account
        model = genai.GenerativeModel('models/gemini-pro-latest')
        print("Gemini API configured successfully.")
    except Exception as e:
        print(f"!!! FATAL ERROR: Could not configure Gemini API: {e} !!!")
        return

    # --- 2. Read the Seed Products ---
    try:
        with open(SEED_FILE, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            seed_products = list(reader)
        print(f"Found {len(seed_products)} products to process in '{SEED_FILE}'.")
    except FileNotFoundError:
        print(f"!!! FATAL ERROR: Input file '{SEED_FILE}' not found. Please create it. !!!")
        return

    enriched_products = []
    # --- 3. Process Each Product ---
    for product in seed_products:
        product_name = product.get('product_name')
        if not product_name:
            continue

        print(f"\n-> Processing: '{product_name}'...")

        # --- 4. Create the AI Prompt ---
        prompt = f"""
        You are an expert affiliate marketer and SEO content writer for an Indian e-commerce audience.
        Your task is to generate a complete data package for the product: "{product_name}".

        Your entire response MUST be a single, valid JSON object with no other text.
        The JSON object must have these exact keys:
        - "slug": A lowercase, hyphen-separated URL slug (e.g., 'amazon-echo-dot-4th-gen').
        - "title": A catchy, SEO-friendly title. It can be the same as the product name or slightly improved.
        - "description": A 2-paragraph, engaging summary highlighting key benefits.
        - "pros": A JSON array of 3-4 strings, each being a key benefit.
        - "cons": A JSON array of 2-3 strings, each being a potential drawback.
        - "keywords": A comma-separated string of 5-7 relevant SEO keywords.
        - "category": Classify the product into ONE of the following categories: "Tech", "Kitchen", "Home Appliances", or "Other".

        Example response for 'Sony WH-1000XM5 Headphones':
        {{
            "slug": "sony-wh-1000xm5-noise-cancelling-headphones",
            "title": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
            "description": "Experience pure silence with the industry-leading Sony WH-1000XM5 noise-cancelling headphones. Perfect for travel, work, or just enjoying your music, these headphones deliver unparalleled audio quality and all-day comfort.\\n\\nWith a lightweight design and up to 30 hours of battery life, the XM5s are built for the long haul. Crystal-clear call quality and multi-device pairing make them the ultimate accessory for any tech enthusiast.",
            "pros": ["Best-in-class noise cancellation", "Exceptional audio quality", "Long battery life", "Comfortable for extended wear"],
            "cons": ["Premium price point", "Bulky carrying case", "Non-foldable design"],
            "keywords": "noise cancelling headphones, sony xm5, wireless headphones, bluetooth headphones, sony india",
            "category": "Tech"
        }}
        
        Now, generate the JSON for: "{product_name}"
        """

        # --- 5. Call the Gemini API and Parse the Response ---
        try:
            response = model.generate_content(prompt)
            response_text = response.text.strip().replace('```json', '').replace('```', '')
            ai_data = json.loads(response_text)
            
            final_product_data = {
                'slug': ai_data.get('slug'),
                'title': ai_data.get('title'),
                'price': product.get('price'),
                'image_url': product.get('image_url'),
                'affiliate_link': product.get('amazon_url'),
                'category': ai_data.get('category'),
                'keywords': ai_data.get('keywords'),
                'pros': "; ".join(ai_data.get('pros', [])),
                'cons': "; ".join(ai_data.get('cons', [])),
                'description': ai_data.get('description')
            }
            enriched_products.append(final_product_data)
            print(f"   ... Success! Content generated.")

        except Exception as e:
            print(f"   !!! ERROR: Failed to process product. Reason: {e} !!!")
        
        # --- THIS IS THE SECOND CHANGE: THE POLITE PAUSE ---
        # We only pause if there are more products to process
        if product != seed_products[-1]:
            print("   ... Pausing for 60 seconds to respect API rate limits ...")
            time.sleep(60)

    # --- 6. Write the Final Output File ---
    if not enriched_products:
        print("\nNo products were successfully enriched. Exiting.")
        return

    print(f"\nEnrichment complete. Writing {len(enriched_products)} products to '{OUTPUT_FILE}'...")
    
    headers = ['slug', 'title', 'price', 'image_url', 'affiliate_link', 'category', 'keywords', 'pros', 'cons', 'description']
    
    with open(OUTPUT_FILE, mode='w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(enriched_products)

    print(f"--- All done! Your new file is ready: '{OUTPUT_FILE}' ---")

if __name__ == "__main__":
    enrich_products()

# IT ENDS HERE - COPY EVERYTHING ABOVE THIS LINE