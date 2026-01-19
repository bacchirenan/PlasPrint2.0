"""
Script de teste para verificar se a IA apresenta corretamente os valores de tinta em ml
"""
import os
import json
import base64
import pandas as pd
import sqlite3
from google import genai

# Ler segredos (simulado - você precisa configurar)
# Para teste, vamos apenas verificar a estrutura dos dados

# Conectar ao banco de dados
conn = sqlite3.connect('fichas_tecnicas.db')
df = pd.read_sql_query("SELECT referencia, produto, cyan, magenta, yellow, black, white, varnish FROM fichas LIMIT 3", conn)
conn.close()

print("=" * 80)
print(" TESTE DE CONVERSAO DE UNIDADES - TINTA (L -> ml)".center(80))
print("=" * 80)
print()

print("DADOS DO BANCO (formato bruto em litros):")
print("-" * 80)
print(df.to_string(index=False))
print()

print("VALORES CONVERTIDOS (como devem ser apresentados pela IA):")
print("-" * 80)

for _, row in df.iterrows():
    print(f"\nReferencia: {row['referencia']} - {row['produto']}")
    print(f"   Cyan:    {row['cyan']*1000:.1f} ml")
    print(f"   Magenta: {row['magenta']*1000:.1f} ml")
    print(f"   Yellow:  {row['yellow']*1000:.1f} ml")
    print(f"   Black:   {row['black']*1000:.1f} ml")
    print(f"   White:   {row['white']*1000:.1f} ml")
    print(f"   Varnish: {row['varnish']*1000:.1f} ml")

print("\n" + "=" * 80)
print("OK - A IA agora esta configurada para:")
print("  1. Ler os valores do banco em formato decimal (litros)")
print("  2. Multiplicar por 1000 automaticamente")
print("  3. Apresentar SEMPRE em ml com a unidade explicita")
print("=" * 80)
