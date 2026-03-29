import sqlite3

# Fungua database yako
conn = sqlite3.connect('water_supply.db')
cur = conn.cursor()

# Ongeza column is_online
cur.execute("""
    ALTER TABLE boss
    ADD COLUMN is_online INTEGER DEFAULT 0
""")

conn.commit()
conn.close()

print("Column is_online imeongezwa kwenye meza ya boss ✅")