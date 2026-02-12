import pandas as pd

try:
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    print("Table Tail (oee teep.xlsx):")
    print(df.iloc[-50:, :5]) # Print last 50 rows, first 5 columns
    
    df2 = pd.read_excel('producao.xlsx', skiprows=3, header=None)
    print("\nTable Tail (producao.xlsx):")
    print(df2.iloc[-50:, :5])
except Exception as e:
    print(f"Error: {e}")
