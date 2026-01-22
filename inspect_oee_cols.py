import pandas as pd
try:
    df = pd.read_excel('oee teep.xlsx', nrows=30)
    print("Colunas detectadas:")
    print(df.columns.tolist())
    print("\nPrimeiras 5 linhas:")
    print(df.head())
    
    # Tentar com skiprows=1 como no app.py
    df2 = pd.read_excel('oee teep.xlsx', skiprows=1, nrows=30)
    print("\nColunas com skiprows=1:")
    print(df2.columns.tolist())
    print("\nPrimeiras 5 linhas com skiprows=1:")
    print(df2.head())
except Exception as e:
    print(f"Erro: {e}")
