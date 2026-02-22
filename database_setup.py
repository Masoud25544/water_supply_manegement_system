import sqlite3
from werkzeug.security import generate_password_hash
import uuid
from datetime import datetime

DB_PATH = "water_supply.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ==========================
# SUPER ADMIN TABLE
# ==========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS super_admin (
    admin_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TEXT NOT NULL
)
""")

# Insert default super admin
default_admin_id = "ADMIN-" + str(uuid.uuid4())[:8]
default_username = "admin"
default_password = generate_password_hash("1234")  # Change later
cursor.execute("INSERT OR IGNORE INTO super_admin (admin_id, username, password, created_at) VALUES (?, ?, ?, ?)",
               (default_admin_id, default_username, default_password, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

# ==========================
# BOSS TABLE
# ==========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS boss (
    boss_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    signup_date TEXT NOT NULL,
    trial_end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL
)
""")

# ==========================
# STAFF TABLE
# ==========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS staff (
    staff_id TEXT PRIMARY KEY,
    boss_id TEXT NOT NULL,
    full_name TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    FOREIGN KEY (boss_id) REFERENCES boss(boss_id)
)
""")

# ==========================
# CUSTOMERS TABLE
# ==========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    boss_id TEXT NOT NULL,
    full_name TEXT NOT NULL,
    phone TEXT,
    area TEXT,
    house_number TEXT,
    meter_number TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (boss_id) REFERENCES boss(boss_id)
)
""")

# ==========================
# METERS TABLE
# ==========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS meters (
    meter_id TEXT PRIMARY KEY,
    meter_number TEXT UNIQUE NOT NULL,
    customer_id TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
)
""")

# ==========================
# BILLS TABLE
# ==========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS bills (
    bill_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    meter_id TEXT NOT NULL,
    units_used REAL NOT NULL DEFAULT 0,
    amount REAL NOT NULL DEFAULT 0,
    billing_month TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'UNPAID',
    payment_method TEXT,
    payment_date TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (meter_id) REFERENCES meters(meter_id)
)
""")

# ==========================
# TARIFFS TABLE
# ==========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS tariffs (
    tariff_id TEXT PRIMARY KEY,
    boss_id TEXT NOT NULL,
    price_per_unit REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (boss_id) REFERENCES boss(boss_id)
)
""")

# ==========================
# MASTER METER TABLE
# ==========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS master_meter (
    master_id TEXT PRIMARY KEY,
    boss_id TEXT NOT NULL,
    master_number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    FOREIGN KEY (boss_id) REFERENCES boss(boss_id)
)
""")

# ==========================
# MASTER METER READINGS TABLE
# ==========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS master_meter_readings (
    reading_id TEXT PRIMARY KEY,
    master_id TEXT NOT NULL,
    reading_value REAL NOT NULL,
    reading_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (master_id) REFERENCES master_meter(master_id)
)
""")

conn.commit()
conn.close()

print("Database setup imekamilika! water_supply.db tayari iko.")