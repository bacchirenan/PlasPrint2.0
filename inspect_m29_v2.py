import pandas as pd

try:
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    # Convert all values in the machine column to string and check for '29'
    all_maquinas = df.iloc[:, 1].dropna().unique().tolist()
    print("All unique machines found:")
    for m in sorted([str(x) for x in all_maquinas]):
        print(f" - {m}")
    
    # Check if '29' is anywhere in any column
    for col in df.columns:
        matches = df[df[col].astype(str).str.contains('29', na=False)]
        if not matches.empty:
            print(f"\nFound '29' in column '{col}' ({len(matches)} times)")
            print(matches[[col]].drop_duplicates().head())

except Exception as e:
    print(f"Error: {e}")
