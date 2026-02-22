import sqlite3

conn = sqlite3.connect("water_supply.db")
cur = conn.cursor()

cur.execute("ALTER TABLE meters ADD COLUMN status TEXT DEFAULT 'ACTIVE'")

conn.commit()
conn.close()

print("Status column added successfully ✅")