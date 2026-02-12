import pandas as pd

try:
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    print("Table Head:")
    print(df.iloc[:20, :5]) # Print first 20 rows, first 5 columns
except Exception as e:
    print(f"Error: {e}")
