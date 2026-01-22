import pandas as pd
try:
    # Ler o arquivo pulando 3 linhas como no app.py
    df = pd.read_excel('producao.xlsx', skiprows=3, header=None)
    print("Previsão de colunas (baseado no app.py):")
    print("1: Maquina, 2: Data, 5: Hora, 6: Turno, 7: Registro, 15: Peças Boas")
    
    print("\nExemplo de dados (primeiras 10 linhas):")
    print(df.head(10))
    
    # Procurar por '0002' na coluna 7 (Registro)
    if 7 in df.columns:
        print(f"\nValores únicos na coluna 7 (Registro):")
        unique_regs = df[7].unique()
        print(unique_regs)
        
        matches = df[df[7].astype(str).str.contains('0002', na=False)]
        print(f"\nTotal de linhas com '0002': {len(matches)}")
        if not matches.empty:
            print("Exemplo de linha com 0002:")
            print(matches.iloc[0])
            
except Exception as e:
    print(f"Erro: {e}")
