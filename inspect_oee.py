import pandas as pd
import os

files = ["oee teep.xlsx", "rejeito.xlsx"]

def inspect(file, name):
    if os.path.exists(file):
        print(f"\n{'='*20} {name} {'='*20}")
        try:
            # Read only a few rows first to check structure
            df = pd.read_excel(file, nrows=20)
            print(f"Columns: {df.columns.tolist()}")
            print(f"Shape (sample): {df.shape}")
            print(f"Data Types:\n{df.dtypes}")
            
            print("\nFirst 5 rows:")
            print(df.head(5).to_string())
            
            # Check for potential key columns
            potential_keys = [c for c in df.columns if 'prod' in c.lower() or 'ref' in c.lower() or 'cod' in c.lower()]
            print(f"\nPotential Key Columns: {potential_keys}")
            
            if potential_keys:
                for key in potential_keys:
                    print(f"Sample values for {key}: {df[key].unique()[:5]}")

        except Exception as e:
            print(f"Error reading {name}: {e}")
    else:
        print(f"File {file} not found.")

for f in files:
    inspect(f, f)

