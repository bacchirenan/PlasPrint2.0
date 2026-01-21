import pandas as pd
try:
    df = pd.read_excel("Canudos.xlsx", header=None, usecols="A:F")
    df.columns = ['A', 'B', 'C', 'D', 'E', 'F']
    print(f"Columns loaded: {df.columns.tolist()}")
    print("First 5 rows:")
    print(df.head())
except Exception as e:
    print(f"Error: {e}")
