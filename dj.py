import sqlite3

def add_columns():
    db_path = "water_supply.db"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Angalia columns zilizopo kwenye bills table
    cursor.execute("PRAGMA table_info(bills)")
    columns = [column[1] for column in cursor.fetchall()]

    # Ongeza previous_reading kama haipo
    if "previous_reading" not in columns:
        cursor.execute("ALTER TABLE bills ADD COLUMN previous_reading REAL")
        print("Column 'previous_reading' added.")
    else:
        print("Column 'previous_reading' already exists.")

    # Ongeza current_reading kama haipo
    if "current_reading" not in columns:
        cursor.execute("ALTER TABLE bills ADD COLUMN current_readING REAL")
        print("Column 'current_reading' added.")
    else:
        print("Column 'current_reading' already exists.")

    conn.commit()
    conn.close()

    print("Database update completed successfully.")


if __name__ == "__main__":
    add_columns()