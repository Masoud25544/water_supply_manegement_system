import sqlite3
import psycopg2

# --- 1️⃣ Connect SQLite ---
sqlite_conn = sqlite3.connect("water_supply.db")
sqlite_cursor = sqlite_conn.cursor()

# --- 2️⃣ Connect PostgreSQL ---
DATABASE_URL = "postgresql://water_admin:G4dL00NuTGXzA1OtkRTsoi0k3vq5f83F@dpg-d6ph3evgi27c738er830-a.render.com:5432/water_supply_db?sslmode=require"

pg_conn = psycopg2.connect(DATABASE_URL)
pg_cursor = pg_conn.cursor()

# --- 3️⃣ Copy customers ---
sqlite_cursor.execute("SELECT id, name, phone, address FROM customers")
rows = sqlite_cursor.fetchall()

for row in rows:
    pg_cursor.execute("""
        INSERT INTO customers (id, name, phone, address)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """, row)

pg_conn.commit()

# --- 4️⃣ Close connections ---
sqlite_conn.close()
pg_conn.close()

print("Customers migrated successfully ✅")