import sqlite3

DB_PATH = "water_supply.db"  # Badilisha kama path yako ni tofauti

# Unganisha na database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1️⃣ Orodhesha majina ya meza zote
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Majina ya meza zote:")
for table in tables:
    print("-", table[0])

print("\n======================\n")

# 2️⃣ Onyesha schema ya kila meza
for table in tables:
    table_name = table[0]
    print(f"Schema ya meza: {table_name}")
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    for col in columns:
        cid, name, ctype, notnull, dflt_value, pk = col
        print(f"  - {name} | {ctype} | Not Null: {bool(notnull)} | PK: {bool(pk)} | Default: {dflt_value}")
    print("\n----------------------\n")

conn.close()