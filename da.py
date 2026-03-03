import sqlite3

DB_PATH = "water_supply.db"  # Badilisha na path ya database yako

def list_meters():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT m.meter_number, c.full_name, c.boss_id
        FROM meters m
        JOIN customers c ON m.customer_id = c.customer_id
        ORDER BY c.boss_id, m.meter_number
    """)

    rows = cur.fetchall()
    for row in rows:
        print(f"Meter: {row['meter_number']}, Customer: {row['full_name']}, Boss: {row['boss_id']}")

    conn.close()

if __name__ == "__main__":
    list_meters()