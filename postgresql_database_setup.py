import psycopg2
from werkzeug.security import generate_password_hash


def setup_database():

    conn = psycopg2.connect(
        dbname="water_supply_db",
        user="your_db_user",
        password="your_db_password",
        host="localhost",
        port="5432"
    )

    conn.autocommit = False
    cursor = conn.cursor()

    try:
        # ================= ENABLE UUID EXTENSION =================
        cursor.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

        # ================= SUPER ADMIN =================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS super_admin (
            admin_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        INSERT INTO super_admin (username, password)
        VALUES (%s, %s)
        ON CONFLICT (username) DO NOTHING
        """, (
            "admin",
            generate_password_hash("1234")
        ))

        # ================= BOSS =================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS boss (
            boss_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            signup_date TIMESTAMP NOT NULL,
            trial_end_date TIMESTAMP NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # ================= STAFF =================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            staff_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            boss_id UUID NOT NULL,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
        )
        """)

        # ================= CUSTOMERS =================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            boss_id UUID NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT,
            area TEXT,
            house_number TEXT,
            meter_number TEXT UNIQUE,
            signup_date TIMESTAMP,
            status TEXT DEFAULT 'ACTIVE',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
        )
        """)

        # ================= METERS =================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS meters (
            meter_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            meter_number TEXT UNIQUE NOT NULL,
            customer_id UUID NOT NULL,
            status TEXT DEFAULT 'ACTIVE',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
        )
        """)

        # ================= TARIFFS =================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tariffs (
            tariff_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            boss_id UUID NOT NULL,
            price_per_unit NUMERIC(12,2) NOT NULL CHECK (price_per_unit >= 0),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
        )
        """)

        # ================= BILLS =================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            bill_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            customer_id UUID NOT NULL,
            meter_id UUID NOT NULL,
            units_used NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (units_used >= 0),
            amount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (amount >= 0),
            billing_month TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'UNPAID',
            payment_method TEXT,
            payment_date TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
            FOREIGN KEY (meter_id) REFERENCES meters(meter_id) ON DELETE CASCADE
        )
        """)

        # ================= PAYMENTS =================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            bill_id UUID NOT NULL,
            customer_id UUID NOT NULL,
            boss_id UUID NOT NULL,
            amount_paid NUMERIC(12,2) NOT NULL CHECK (amount_paid > 0),
            payment_method TEXT NOT NULL,
            reference TEXT,
            paid_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
            FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
        )
        """)

        # ================= RECEIPTS =================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            receipt_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            payment_id UUID NOT NULL,
            receipt_number TEXT UNIQUE NOT NULL,
            customer_id UUID NOT NULL,
            boss_id UUID NOT NULL,
            amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
            issued_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE CASCADE,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
            FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
        )
        """)

        # ================= MASTER METER =================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS master_meter (
            master_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            boss_id UUID NOT NULL,
            master_number TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
        )
        """)

        # ================= MASTER METER READINGS =================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS master_meter_readings (
            reading_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            master_id UUID NOT NULL,
            reading_value NUMERIC(12,2) NOT NULL CHECK (reading_value >= 0),
            reading_date TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (master_id) REFERENCES master_meter(master_id) ON DELETE CASCADE
        )
        """)

        # ================= INDEXES (OPTIMIZED) =================
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_boss ON customers(boss_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_meter ON customers(meter_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_staff_boss ON staff(boss_id)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_customer ON bills(customer_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_meter ON bills(meter_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_status ON bills(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_month ON bills(billing_month)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_customer_month ON bills(customer_id, billing_month)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_bill ON payments(bill_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_boss ON payments(boss_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(paid_at)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_payment ON receipts(payment_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_customer ON receipts(customer_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_boss ON receipts(boss_id)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_master_meter_boss ON master_meter(boss_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_master_readings_master ON master_meter_readings(master_id)")

        conn.commit()
        print("✅ PostgreSQL production database setup completed successfully!")

    except Exception as e:
        conn.rollback()
        print("❌ Error:", e)

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    setup_database()