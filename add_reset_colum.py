import sqlite3

DB_PATH = "water_supply.db"  # Badilisha kwa path ya database yako

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Angalia kama column haipo kwanza
cur.execute("PRAGMA table_info(staff)")
columns = [col[1] for col in cur.fetchall()]
if "reset_required" not in columns:
    cur.execute("ALTER TABLE staff ADD COLUMN reset_required INTEGER DEFAULT 0")
    print("✅ Column 'reset_required' imeongezwa kwenye staff table")
else:
    print("ℹ️ Column 'reset_required' tayari ipo")

conn.commit()
conn.close()