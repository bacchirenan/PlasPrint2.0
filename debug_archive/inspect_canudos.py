import pandas as pd

try:
    df = pd.read_excel('Canudos.xlsx', header=None)
    # Print sample to see structure
    print("Canudos sample:")
    print(df.head())
    
    # Check for any column that might contain machine names
    print("\nUnique values in first few columns:")
    for i in range(min(5, df.shape[1])):
        print(f"Column {i}: {df.iloc[:, i].dropna().unique()[:10]}")

except Exception as e:
    print(f"Error: {e}")
