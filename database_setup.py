import sqlite3
from werkzeug.security import generate_password_hash
import uuid
from datetime import datetime

DB_PATH = "water_supply.db"

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")  # Muhimu kwa SQLite
cursor = conn.cursor()

# =====================================================
# SUPER ADMIN TABLE
# =====================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS super_admin (
    admin_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TEXT NOT NULL
)
""")

default_admin_id = "ADMIN-" + str(uuid.uuid4())
cursor.execute("""
INSERT OR IGNORE INTO super_admin 
(admin_id, username, password, created_at)
VALUES (?, ?, ?, ?)
""", (
    default_admin_id,
    "admin",
    generate_password_hash("1234"),
    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
))

# =====================================================
# BOSS TABLE
# =====================================================
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

# =====================================================
# STAFF TABLE
# =====================================================
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
    FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
)
""")

# =====================================================
# CUSTOMERS TABLE
# =====================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    boss_id TEXT NOT NULL,
    full_name TEXT NOT NULL,
    phone TEXT,
    area TEXT,
    house_number TEXT,
    meter_number TEXT,
    signup_date TEXT,
    status TEXT DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
)
""")

# =====================================================
# METERS TABLE
# =====================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS meters (
    meter_id TEXT PRIMARY KEY,
    meter_number TEXT UNIQUE NOT NULL,
    customer_id TEXT NOT NULL,
    status TEXT DEFAULT 'ACTIVE',
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
)
""")

# =====================================================
# TARIFFS TABLE
# =====================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS tariffs (
    tariff_id TEXT PRIMARY KEY,
    boss_id TEXT NOT NULL,
    price_per_unit REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
)
""")

# =====================================================
# BILLS TABLE
# =====================================================
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
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (meter_id) REFERENCES meters(meter_id) ON DELETE CASCADE
)
""")

# =====================================================
# PAYMENTS TABLE
# =====================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    bill_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    boss_id TEXT NOT NULL,
    amount_paid REAL NOT NULL,
    payment_method TEXT NOT NULL,
    reference TEXT,
    paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
)
""")

# =====================================================
# RECEIPTS TABLE
# =====================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS receipts (
    receipt_id TEXT PRIMARY KEY,
    payment_id TEXT NOT NULL,
    receipt_number TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    boss_id TEXT NOT NULL,
    amount REAL NOT NULL,
    issued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
)
""")

# =====================================================
# MASTER METER TABLE
# =====================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS master_meter (
    master_id TEXT PRIMARY KEY,
    boss_id TEXT NOT NULL,
    master_number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
)
""")

# =====================================================
# MASTER METER READINGS TABLE
# =====================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS master_meter_readings (
    reading_id TEXT PRIMARY KEY,
    master_id TEXT NOT NULL,
    reading_value REAL NOT NULL,
    reading_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (master_id) REFERENCES master_meter(master_id) ON DELETE CASCADE
)
""")

# =====================================================
# ANDROID METADATA TABLE
# =====================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS android_metadata (
    locale TEXT
)
""")

# =====================================================
# INDEXES (Performance Boost)
# =====================================================
cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_boss ON customers(boss_id)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_customer ON bills(customer_id)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_bill ON payments(bill_id)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_boss ON payments(boss_id)")

conn.commit()
conn.close()

print("✅ Professional database setup complete. water_supply.db iko tayari.")