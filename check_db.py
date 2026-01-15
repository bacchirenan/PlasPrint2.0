import sqlite3

def check_db():
    try:
        conn = sqlite3.connect('fichas_tecnicas.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables: {tables}")
        
        for table in tables:
            table_name = table[0]
            print(f"\nSchema for table: {table_name}")
            cursor.execute(f"PRAGMA table_info({table_name});")
            for info in cursor.fetchall():
                print(info)
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()
