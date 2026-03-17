import sqlite3

def check_customers_meters(db_path="water_supply.db"):
    """
    Hii function itachunguza:
    1️⃣ Customers wote
    2️⃣ Meters wote
    3️⃣ Kuchunguza mismatch kati ya customer_id
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # ili row ziwe dict-like
    cur = conn.cursor()

    # 🔹 Angalia CUSTOMERS
    cur.execute("SELECT customer_id, full_name FROM customers")
    customers = cur.fetchall()
    print("🔹 CUSTOMERS 🔹")
    if not customers:
        print("❌ Hakuna customers kwenye database")
    for c in customers:
        print(f"{c['customer_id']} | {c['full_name']}")

    # 🔹 Angalia METERS
    cur.execute("SELECT meter_id, meter_number, customer_id FROM meters")
    meters = cur.fetchall()
    print("\n🔹 METERS 🔹")
    if not meters:
        print("❌ Hakuna meters kwenye database")
    for m in meters:
        print(f"{m['meter_id']} | {m['meter_number']} | {m['customer_id']}")

    # 🔹 Check mismatches
    customer_ids = set(c['customer_id'] for c in customers)
    meter_ids = [(m['meter_id'], m['customer_id']) for m in meters]

    print("\n🔹 MISMATCH CHECK 🔹")
    has_mismatch = False
    for meter_id, cust_id in meter_ids:
        if cust_id not in customer_ids:
            print(f"⚠️ Meter {meter_id} ina customer_id '{cust_id}' isiyo na customer sahihi")
            has_mismatch = True

    if not has_mismatch:
        print("✅ Meters zote zime-link vema na customers")

    conn.close()


# 🔹 Run script tu ikiwa ime-execute directly
if __name__ == "__main__":
    check_customers_meters("water_supply.db")