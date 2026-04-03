import os
import sqlite3
import uuid
from datetime import datetime

# =========================
# Tumia DATABASE_URL ya Render kwa PostgreSQL
# =========================
DB_URL = os.getenv("DATABASE_URL")

if DB_URL:
    print("⚡ Using PostgreSQL")
    import psycopg2
    try:
        conn = psycopg2.connect(DB_URL, sslmode="require")
        cur = conn.cursor()

        # Add missing columns safely
        cur.execute("ALTER TABLE boss ADD COLUMN IF NOT EXISTS phone VARCHAR(50);")
        cur.execute("ALTER TABLE boss ADD COLUMN IF NOT EXISTS email VARCHAR(255);")

        conn.commit()
        conn.close()
        print("✅ PostgreSQL migration complete!")

    except Exception as e:
        print("❌ PostgreSQL Error:", e)

else:
    # =========================
    # SQLite local
    # =========================
    print("⚡ Using SQLite")
    SQLITE_DB_PATH = "/storage/emulated/0/water_supply_magement_system/water_supply.db"
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()

        # Safe add columns
        try:
            cur.execute("ALTER TABLE boss ADD COLUMN phone TEXT;")
        except sqlite3.OperationalError:
            print("Column 'phone' tayari ipo")

        try:
            cur.execute("ALTER TABLE boss ADD COLUMN email TEXT;")
        except sqlite3.OperationalError:
            print("Column 'email' tayari ipo")

        conn.commit()
        conn.close()
        print("✅ SQLite migration complete!")

    except Exception as e:
        print("❌ SQLite Error:", e)