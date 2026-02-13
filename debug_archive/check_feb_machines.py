import pandas as pd

try:
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    df['Data_dt'] = pd.to_datetime(df.iloc[:, 2], dayfirst=True, errors='coerce')
    feb = df[df['Data_dt'] >= '2026-02-01']
    print("Unique machines in February 2026:")
    print(feb.iloc[:, 1].unique())
    
    # Check for '29' anywhere in the whole file again, but looking for sub-strings
    print("\nLooking for any mention of '29' in the machine column:")
    m_col = df.iloc[:, 1].astype(str)
    matches_29 = m_col[m_col.str.contains('29')]
    print(matches_29.unique())

except Exception as e:
    print(f"Error: {e}")
