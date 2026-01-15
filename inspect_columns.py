import streamlit as st
import pandas as pd
import sqlite3
import glob
import os

# Simulating the data loading to see columns
def read_sqlite(table_name):
    try:
        conn = sqlite3.connect('fichas_tecnicas.db')
        df = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 1", conn)
        conn.close()
        return df
    except: return pd.DataFrame()

def read_xlsx():
    try:
        xlsx_files = glob.glob("*.xlsx")
        if not xlsx_files: return pd.DataFrame()
        latest_file = max(xlsx_files, key=os.path.getmtime)
        df = pd.read_excel(latest_file).head(1)
        return df
    except: return pd.DataFrame()

print("--- Colunas SQLite (Fichas) ---")
fichas = read_sqlite("fichas")
print(fichas.columns.tolist())

print("\n--- Colunas XLSX (Produção) ---")
producao = read_xlsx()
print(producao.columns.tolist())
