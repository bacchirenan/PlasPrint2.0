import os
from google import genai
import streamlit as st

# Carregar API KEY dos segredos se estiver no ambiente Streamlit
# Ou pegar do ambiente se estiver rodando localmente
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

try:
    print("Modelos disponíveis:")
    for model in client.models.list():
        print(f"Name: {model.name}")
except Exception as e:
    print(f"Erro ao listar modelos: {e}")
