import os
from google import genai

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

models_to_test = ["gemini-1.5-flash", "models/gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-2.0-flash", "gemini-flash-latest"]

for model_name in models_to_test:
    try:
        print(f"Testing model: {model_name}")
        response = client.models.generate_content(
            model=model_name,
            contents="Diga 'Oi'"
        )
        print(f"Success with {model_name}: {response.text}")
    except Exception as e:
        print(f"Error with {model_name}: {e}")
