# IT STARTS HERE
import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load the API key from the .env file in the parent directory
load_dotenv(dotenv_path='../.env')
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("!!! ERROR: GEMINI_API_KEY not found in .env file. !!!")
else:
    try:
        print("Configuring API key...")
        genai.configure(api_key=api_key)
        
        print("\nFetching available models...")
        # This loop asks the API to list all models that support 'generateContent'
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
        
        print("\nTest complete.")

    except Exception as e:
        print(f"\n!!! An error occurred during the test: {e} !!!")
# IT ENDS HERE