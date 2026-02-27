import sqlite3

DB_PATH = "water_supply.db"

def update_bills_table():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        print("Connecting to database...")

        # ==============================
        # ADD read_by COLUMN
        # ==============================
        try:
            cursor.execute("ALTER TABLE bills ADD COLUMN read_by TEXT;")
            print("Column 'read_by' added successfully.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("Column 'read_by' already exists.")
            else:
                raise e

        # ==============================
        # ADD reader_role COLUMN
        # ==============================
        try:
            cursor.execute("ALTER TABLE bills ADD COLUMN reader_role TEXT;")
            print("Column 'reader_role' added successfully.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("Column 'reader_role' already exists.")
            else:
                raise e

        conn.commit()
        print("Database updated successfully ✅")

    except Exception as e:
        print("Error occurred:", e)

    finally:
        if conn:
            conn.close()
            print("Connection closed.")

# ==================================
# RUN SCRIPT
# ==================================
if __name__ == "__main__":
    update_bills_table()