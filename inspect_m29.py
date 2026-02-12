import pandas as pd

try:
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    print("Columns:", df.columns.tolist())
    
    # Check if '29' or '29.0' or 'MÁQUINA 29' etc is in the machine column (Index 1)
    maquinas = df.iloc[:, 1].unique()
    print("Unique Machines in file:", maquinas)
    
    # Filter for machine 29
    m29_data = df[df.iloc[:, 1].astype(str).str.contains('29', na=False)]
    print(f"\nFound {len(m29_data)} records for Machine 29")
    if not m29_data.empty:
        print("First 5 records for Machine 29:")
        print(m29_data.head())
        
        # Check specific columns that might be filtering it out in app.py
        # Turno (Index 3), Hora (Index 4), OEE components (7, 8, 9)
        print("\nSample Turno values for M29:", m29_data.iloc[:, 3].unique())
        print("Sample Hora values for M29:", m29_data.iloc[:, 4].unique())
        
except Exception as e:
    print(f"Error: {e}")
