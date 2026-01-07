from google import genai
import os

api_key = "AIzaSyDTBQ2XVGO4OePKXXTwQQZ6VBc7wsqnChY"
client = genai.Client(api_key=api_key)

for model in client.models.list():
    print(f"Model: {model.name}, Supported Actions: {model.supported_actions}")
