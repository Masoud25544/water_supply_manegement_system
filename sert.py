import sqlite3
from datetime import datetime

DB_PATH = "water_supply.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Angalia kama column ipo
cur.execute("PRAGMA table_info(meters)")
columns = [col[1] for col in cur.fetchall()]

if "created_at" not in columns:
    # 1️⃣ Ongeza column bila default
    cur.execute("ALTER TABLE meters ADD COLUMN created_at TEXT;")
    
    # 2️⃣ Update rows zilizopo na timestamp ya sasa
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("UPDATE meters SET created_at = ? WHERE created_at IS NULL", (now,))
    print("✅ Column created_at imeongezwa na rows zilizopo zime-update")
else:
    print("ℹ️ Column created_at tayari ipo")

conn.commit()
conn.close()