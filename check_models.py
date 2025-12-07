import os
import google.generativeai as genai
from dotenv import load_dotenv

print("--- Running Gemini Model Check ---")

# Load API key from your .env file
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("!!! ERROR: GEMINI_API_KEY not found in .env file. !!!")
else:
    try:
        genai.configure(api_key=api_key)
        
        print("\nFetching available models from the server...")
        
        # This is the "Call ListModels" part
        count = 0
        for m in genai.list_models():
            # We only care about models that can actually generate content
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
                count += 1
        
        print(f"\nTest complete. Found {count} usable models.")

    except Exception as e:
        print(f"\n!!! An error occurred during the test: {e} !!!")