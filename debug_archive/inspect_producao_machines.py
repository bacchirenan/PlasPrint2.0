import pandas as pd

try:
    df = pd.read_excel('producao.xlsx', skiprows=3, header=None)
    all_maquinas = df.iloc[:, 1].dropna().unique().tolist()
    print("All unique machines found in producao.xlsx:")
    for m in sorted([str(x) for x in all_maquinas]):
        print(f" - {m}")
except Exception as e:
    print(f"Error: {e}")
