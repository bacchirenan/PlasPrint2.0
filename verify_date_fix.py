import pandas as pd
import datetime

def test_date_logic(min_date_val, max_date_val):
    print(f"Testing with: min={min_date_val}, max={max_date_val}")
    
    # Simulate the logic in app.py
    min_date = pd.to_datetime(min_date_val)
    max_date = pd.to_datetime(max_date_val)
    yesterday = datetime.date(2026, 1, 21) # Fixed "yesterday" for testing based on current date
    
    # Logic for visual_min
    if pd.notnull(min_date):
        visual_min = min(min_date.date(), yesterday)
    else:
        visual_min = yesterday
        
    # Logic for val_capped
    val_capped = max(visual_min, min(yesterday, max_date.date()))
    
    print(f"  Result: visual_min={visual_min}, max_date={max_date.date()}, default_val={val_capped}")
    
    # Streamlit validation: value must be between min_value and max_value
    # In Streamlit: min_value=visual_min, max_value=max_date
    assert visual_min <= val_capped <= max_date.date(), f"Validation FAILED: {visual_min} <= {val_capped} <= {max_date.date()} is FALSE"
    print("  Validation PASSED")

if __name__ == "__main__":
    # Case 1: Data is up to date (Yesterday is in range)
    test_date_logic("2026-01-01", "2026-01-22")
    
    # Case 2: Data is old (Max date is before yesterday) - This was causing the error
    test_date_logic("2026-01-01", "2026-01-15")
    
    # Case 3: Data is in the future (Only has today/future data)
    test_date_logic("2026-01-22", "2026-01-25")
    
    # Case 4: Single date in the past
    test_date_logic("2026-01-10", "2026-01-10")
