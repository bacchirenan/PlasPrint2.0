import toml
from google import genai
import os

try:
    secrets = toml.load(".streamlit/secrets.toml")
    GEMINI_API_KEY = secrets["GEMINI_API_KEY"]
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
    client = genai.Client()
    
    print("Listing models...")
    for m in client.models.list():
        print(f"Name: {m.name}") 

        print(f"Display Name: {m.display_name}")
        print("-" * 20)
        
except Exception as e:
    print(f"Error: {e}")
