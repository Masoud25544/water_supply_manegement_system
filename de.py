import sqlite3

DATABASE = "water_supply.db"

def add_permissions_column():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Angalia kama column 'permissions' ipo tayari
    cursor.execute("PRAGMA table_info(staff)")
    columns = [col[1] for col in cursor.fetchall()]  # col[1] ni jina la column

    if "permissions" not in columns:
        cursor.execute("ALTER TABLE staff ADD COLUMN permissions TEXT")
        print("Column 'permissions' imeongezwa kwenye staff table.")
    else:
        print("Column 'permissions' tayari ipo kwenye staff table.")

    conn.commit()
    conn.close()

# Run function
add_permissions_column()