import pandas as pd
try:
    # Ler o arquivo pulando a primeira linha como no app.py
    df = pd.read_excel('oee teep.xlsx', skiprows=1, nrows=100)
    print("Colunas detectadas:")
    print(df.columns.tolist())
    
    print("\nExemplo de dados (primeiras 10 linhas):")
    print(df.head(10))
    
    # Procurar por '0002' em todas as colunas
    print("\nProcurando por '0002' em todas as colunas...")
    for col in df.columns:
        matches = df[df[col].astype(str).str.contains('0002', na=False)]
        if not matches.empty:
            print(f"Encontrei '0002' na coluna: {col}")
            print(matches[col].unique())
            
except Exception as e:
    print(f"Erro: {e}")
