import sqlite3
import datetime

def setup_costs_db():
    conn = sqlite3.connect('fichas_tecnicas.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custos_tintas (
            id INTEGER PRIMARY KEY,
            cor TEXT UNIQUE,
            preco_litro REAL,
            data_atualizacao TEXT
        )
    ''')
    
    # Preços iniciais padrão se a tabela estiver vazia
    tintas = [
        ('cyan', 250.0),
        ('magenta', 250.0),
        ('yellow', 250.0),
        ('black', 250.0),
        ('white', 300.0),
        ('varnish', 180.0)
    ]
    
    for cor, preco in tintas:
        cursor.execute('''
            INSERT OR IGNORE INTO custos_tintas (cor, preco_litro, data_atualizacao)
            VALUES (?, ?, ?)
        ''', (cor, preco, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    setup_costs_db()
    print("Database setup complete.")
