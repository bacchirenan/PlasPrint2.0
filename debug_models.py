import streamlit as st
from google import genai
import tomllib
import os

with open(".streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)
    api_key = secrets["GEMINI_API_KEY"]

client = genai.Client(api_key=api_key)
print("--- DISPONÍVEIS ---")
for m in client.models.list():
    print(f"Name: {m.name} | Supported: {m.supported_actions}")
