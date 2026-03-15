from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta
import uuid
import random
import string
import re
from functools import wraps
import traceback

def generate_staff_id():
    return "STF-" + str(uuid.uuid4())[:8]

app = Flask(__name__)
app.secret_key = "supersecretkey"
DB_PATH = "water_supply.db"

# ================================
# DATABASE SETUP FUNCTION
# ================================
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # =====================================================
        # SUPER ADMIN
        # =====================================================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS super_admin (
            admin_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        default_admin_id = "ADMIN-" + str(uuid.uuid4())
        cur.execute("""
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
        # BOSS
        # =====================================================
        cur.execute("""
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
        # STAFF
        # =====================================================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            staff_id TEXT PRIMARY KEY,
            boss_id TEXT NOT NULL,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL,
            permissions TEXT,
            FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
        )
        """)

        # =====================================================
        # CUSTOMERS
        # =====================================================
        cur.execute("""
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
        # METERS
        # =====================================================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS meters (
            meter_id TEXT PRIMARY KEY,
            meter_number TEXT UNIQUE NOT NULL,
            customer_id TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
        )
        """)

        # =====================================================
        # TARIFFS
        # =====================================================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tariffs (
            tariff_id TEXT PRIMARY KEY,
            boss_id TEXT NOT NULL,
            price_per_unit REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
        )
        """)

        # =====================================================
        # MASTER METER
        # =====================================================
        cur.execute("""
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
        # MASTER METER READINGS
        # =====================================================
        cur.execute("""
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
        # METER READINGS
        # =====================================================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS meter_readings (
            reading_id TEXT PRIMARY KEY,
            meter_id TEXT NOT NULL,
            reading_value REAL NOT NULL,
            reading_date TEXT NOT NULL,
            recorded_by TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (meter_id) REFERENCES meters(meter_id) ON DELETE CASCADE
        )
        """)

        # =====================================================
        # BILLS
        # =====================================================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            bill_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            meter_id TEXT NOT NULL,
            previous_reading REAL,
            current_reading REAL,
            units_used REAL,
            amount REAL,
            billing_month TEXT,
            status TEXT DEFAULT 'UNPAID',
            payment_method TEXT,
            payment_date TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
            FOREIGN KEY (meter_id) REFERENCES meters(meter_id) ON DELETE CASCADE
        )
        """)

        # =====================================================
        # PAYMENTS
        # =====================================================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            bill_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            boss_id TEXT NOT NULL,
            amount_paid REAL NOT NULL,
            payment_method TEXT,
            reference TEXT,
            paid_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
            FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
        )
        """)

        # =====================================================
        # RECEIPTS
        # =====================================================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            receipt_id TEXT PRIMARY KEY,
            payment_id TEXT NOT NULL,
            receipt_number TEXT UNIQUE,
            customer_id TEXT NOT NULL,
            boss_id TEXT NOT NULL,
            amount REAL,
            issued_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE CASCADE,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
            FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
        )
        """)

        # =====================================================
        # ACTIVITY LOGS
        # =====================================================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT,
            role TEXT,
            action TEXT,
            details TEXT,
            time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            boss_id TEXT
        )
        """)

        # =====================================================
        # ANDROID METADATA
        # =====================================================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS android_metadata (
            locale TEXT
        )
        """)

        conn.commit()
        conn.close()
        print("✅ Database setup complete.")

    except Exception as e:
        print("❌ Error setting up database:", str(e))
        traceback.print_exc()

# Run DB initialization when app starts
init_db()
# ================================
# INIT DATABASE ROUTE (kwa testing)
# ================================
@app.route('/init_db')
def init_db_route():
    try:
        init_db()
        return "<h3>✅ Database imeundwa kikamilifu!</h3>"
    except Exception as e:
        return f"<h3>❌ Tatizo limejitokeza:</h3><pre>{str(e)}</pre>"

# ================= ERROR HANDLER ==================
@app.errorhandler(500)
def internal_error(e):
    tb = traceback.format_exc()
    return f"<h3>Internal Server Error</h3><pre>{tb}</pre>", 500

# ====================== MAKE SESSION TEMPORARY ======================
@app.before_request
def make_session_temporary():
    session.permanent = False

# =================== MULTI-ROLE DECORATOR ===================
def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            role_session_map = {
                "boss": "boss_id",
                "staff": "staff_id",
                "admin": "superadmin_id"
            }

            for role in allowed_roles:
                session_key = role_session_map.get(role)
                if session_key and session_key in session:
                    return f(*args, **kwargs)

            flash("⚠️ Huna ruhusa ku-access ukurasa huu", "danger")
            
            if "superadmin_id" in session:
                return redirect(url_for("superadmin_dashboard"))
            elif "boss_id" in session:
                return redirect(url_for("boss_dashboard"))
            elif "staff_id" in session:
                return redirect(url_for("staff_dashboard"))
            else:
                return redirect(url_for("login"))
            
        return decorated_function
    return decorator

# ================= DATABASE CONNECTION ==================
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ================= SUPER ADMIN ROUTES ==================
@app.route("/superadmin/login", methods=["GET", "POST"])
def superadmin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM super_admin WHERE username=?", (username,))
        admin = cur.fetchone()
        conn.close()
        if admin and check_password_hash(admin["password"], password):
            session["superadmin_id"] = admin["admin_id"]
            flash("Karibu Super Admin!", "success")
            return redirect(url_for("superadmin_dashboard"))
        flash("Username au password si sahihi.", "danger")
    return render_template("superadmin_login.html")

@app.route("/superadmin/dashboard")
def superadmin_dashboard():
    if "superadmin_id" not in session:
        flash("Login required", "danger")
        return redirect(url_for("superadmin_login"))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT boss_id, full_name, username, status, trial_end_date FROM boss ORDER BY full_name")
    bosses = cur.fetchall()
    conn.close()
    return render_template("superadmin_dashboard.html", bosses=bosses)

# ================= BOSS SIGNUP ROUTE ==================
@app.route("/boss/signup", methods=["GET", "POST"])
def boss_signup():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        username = request.form.get("username")
        password = request.form.get("password")
        boss_id = "BOSS-" + str(uuid.uuid4())[:8]
        hashed_pw = generate_password_hash(password)
        signup_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        trial_end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        status = "ACTIVE"
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO boss (boss_id, full_name, username, password, signup_date, trial_end_date, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (boss_id, full_name, username, hashed_pw, signup_date, trial_end_date, status, signup_date))
            conn.commit()
            flash("Boss account imeundwa! Sasa unaweza kuingia.", "success")
        except sqlite3.IntegrityError:
            flash("Username tayari ipo.", "danger")
        conn.close()
        return redirect(url_for("boss_login"))
    return render_template("boss_signup.html")

# ===================== MAIN ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



@app.route("/boss/login", methods=["GET", "POST"])
def boss_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM boss WHERE username=?", (username,))
        boss = cur.fetchone()

        if boss and check_password_hash(boss["password"], password):

            # 1️⃣ Check trial
            now = datetime.now()
            trial_end = datetime.strptime(boss["trial_end_date"], "%Y-%m-%d %H:%M:%S")

            if now > trial_end:
                cur.execute(
                    "UPDATE boss SET status=? WHERE boss_id=?",
                    ("INACTIVE", boss["boss_id"])
                )
                conn.commit()

            # 2️⃣ Login success
            session.clear()
            session["boss_id"] = boss["boss_id"]
            session["boss_status"] = boss["status"]
            session["boss_name"] = boss["full_name"]       # ✅ Hii tumiongeza

            conn.close()

            if boss["status"] == "INACTIVE":
                flash("Account yako ni INACTIVE. Baadhi ya huduma zimefungwa.", "warning")
            else:
                flash(f"Karibu, {boss['full_name']}!", "success")

            return redirect(url_for("boss_dashboard"))

        conn.close()
        flash("Username au password sio sahihi.", "danger")
        return redirect(url_for("boss_login"))

    return render_template("boss_login.html")
    
    
    



@app.route("/boss_dashboard")
def boss_dashboard():
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # -------------------------------
    # Pata info ya boss
    # -------------------------------
    boss = conn.execute("SELECT * FROM boss WHERE boss_id=?", (boss_id,)).fetchone()

    # -------------------------------
    # Pata customers na meters
    # -------------------------------
    customers_raw = conn.execute("""
        SELECT * FROM customers WHERE boss_id=? ORDER BY full_name
    """, (boss_id,)).fetchall()

    meters_raw = conn.execute("""
        SELECT * FROM meters WHERE customer_id IN (
            SELECT customer_id FROM customers WHERE boss_id=?
        )
    """, (boss_id,)).fetchall()

    # -------------------------------
    # Pata unpaid bills
    # -------------------------------
    unpaid_bills = conn.execute("""
        SELECT b.*, c.full_name AS customer_name, m.meter_number
        FROM bills b
        JOIN customers c ON b.customer_id = c.customer_id
        LEFT JOIN meters m ON b.meter_id = m.meter_id
        WHERE b.status='UNPAID' AND c.boss_id=?
        ORDER BY b.billing_month DESC
    """, (boss_id,)).fetchall()

    # Jumla ya unpaid bills
    total_unpaid_amount = conn.execute("""
        SELECT SUM(b.amount) as total
        FROM bills b
        JOIN customers c ON b.customer_id = c.customer_id
        WHERE b.status='UNPAID' AND c.boss_id=?
    """, (boss_id,)).fetchone()['total'] or 0

    # Jumla ya malipo yote
    total_payments = conn.execute("""
        SELECT SUM(p.amount_paid) as total
        FROM payments p
        JOIN customers c ON p.customer_id = c.customer_id
        WHERE c.boss_id=?
    """, (boss_id,)).fetchone()['total'] or 0

    # -------------------------------
    # Kuangalia meters ambazo zilirukwa kusomwa miezi ya nyuma
    # -------------------------------
    skipped_meters = conn.execute("""
        SELECT COUNT(DISTINCT m.meter_id) as total
        FROM meters m
        JOIN customers c ON m.customer_id = c.customer_id
        LEFT JOIN bills b ON m.meter_id = b.meter_id
        WHERE c.boss_id=?
        AND b.billing_month IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM bills b2
            WHERE b2.meter_id = m.meter_id
            AND b2.billing_month = strftime('%Y-%m','now')
        )
    """, (boss_id,)).fetchone()["total"] or 0

    # -------------------------------
    # Tengeneza meters map
    # -------------------------------
    meters_map = {}
    for m in meters_raw:
        meters_map.setdefault(m['customer_id'], []).append({
            'meter_number': m['meter_number'],
            'status': m['status']
        })

    customers = []
    for c in customers_raw:
        c_dict = dict(c)
        c_dict['meters'] = meters_map.get(c['customer_id'], [])
        customers.append(c_dict)

    # Hesabu meters active/inactive
    active_meters = sum(
        1 for mlist in meters_map.values() for m in mlist if m['status']=='ACTIVE'
    )
    inactive_meters = sum(
        1 for mlist in meters_map.values() for m in mlist if m['status']=='INACTIVE'
    )

    # -------------------------------
    # Recent Activity Logs (5 za mwisho) kwa boss pekee
    # -------------------------------
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM activity_logs
        WHERE boss_id=?
        ORDER BY time DESC
        LIMIT 5
    """, (boss_id,))
    recent_logs = cursor.fetchall()

    conn.close()

    # -------------------------------
    # Render dashboard template
    # -------------------------------
    return render_template(
        "boss_dashboard.html",
        boss=boss,
        customers=customers,
        active_meters=active_meters,
        inactive_meters=inactive_meters,
        unpaid_bills=unpaid_bills,
        total_unpaid_amount=total_unpaid_amount,
        total_payments=total_payments,
        skipped_meters=skipped_meters,
        recent_logs=recent_logs       # ✅ Tumiongeza recent activity pekee kwa boss
    )
@app.route("/boss/activity_logs")
def boss_activity_logs():

    # Hakikisha boss amelogin
    if "boss_id" not in session:
        flash("Tafadhali login kwanza", "danger")
        return redirect(url_for("login"))

    conn = sqlite3.connect("water_supply.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Chukua logs zote
    cursor.execute("""
        SELECT * FROM activity_logs
        ORDER BY time DESC
    """)

    logs = cursor.fetchall()
    conn.close()

    return render_template("boss_activity_logs.html", logs=logs)
    
    
@app.route("/boss/activity_logs/filter", methods=["GET", "POST"])
def boss_activity_logs_filter():
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    logs = []

    if request.method == "POST":
        month = request.form.get("month")  # format: MM
        year = request.form.get("year")    # format: YYYY

        if month and year:
            # ✅ Filter logs kwa boss pekee
            logs = cursor.execute("""
                SELECT * FROM activity_logs
                WHERE boss_id=? AND strftime('%Y', time)=? AND strftime('%m', time)=?
                ORDER BY time DESC
            """, (boss_id, year, month.zfill(2))).fetchall()
        else:
            flash("Chagua mwezi na mwaka sahihi", "danger")

    conn.close()
    return render_template("boss_activity_logs_filter.html", logs=logs)
@app.route("/boss/logout")
def boss_logout():
    session.pop("boss_id", None)
    flash("Umetoka kwenye dashboard ya boss", "success")
    return redirect(url_for("boss_login"))


# ================= CUSTOMER MANAGEMENT ==================

@app.route("/boss/add_customer", methods=["GET", "POST"])
def add_customer():
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    if request.method == "POST":
        full_name = request.form.get("full_name")
        phone = request.form.get("phone")
        area = request.form.get("area")
        house_number = request.form.get("house_number")
        meter_number = request.form.get("meter_number")

        # ✅ Validation
        if not full_name or not meter_number:
            flash("Jina kamili na meter number ni lazima!", "danger")
            return redirect(url_for("add_customer"))

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # ✅ Angalia kama meter ipo tayari
            cur.execute("SELECT * FROM meters WHERE meter_number = ?", (meter_number,))
            if cur.fetchone():
                flash(f"⚠️ Meter {meter_number} tayari ipo kwenye mfumo.", "warning")
                return redirect(url_for("add_customer"))

            # ✅ Angalia kama mteja tayari yupo kwa jina + simu + boss_id
            cur.execute("SELECT * FROM customers WHERE full_name=? AND phone=? AND boss_id=?",
                        (full_name, phone, session["boss_id"]))
            existing_customer = cur.fetchone()

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status = "ACTIVE"

            if existing_customer:
                customer_id = existing_customer["customer_id"]
                flash(f"ℹ️ Mteja {full_name} tayari yupo. Tena tunaongeza meter.", "info")
            else:
                # ✅ Ingiza mteja mpya
                customer_id = "CUST-" + str(uuid.uuid4())[:8]
                cur.execute("""
                    INSERT INTO customers 
                    (customer_id, boss_id, full_name, phone, area, house_number, status, created_at, signup_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (customer_id, session["boss_id"], full_name, phone, area, house_number, status, now, now))
                flash(f"✅ Mteja {full_name} amesajiliwa kikamilifu!", "success")

            # ✅ Ingiza meter
            meter_id = "MTR-" + str(uuid.uuid4())[:8]
            cur.execute("""
                INSERT INTO meters (meter_id, meter_number, customer_id, status)
                VALUES (?, ?, ?, ?)
            """, (meter_id, meter_number, customer_id, status))

            conn.commit()
            flash(f"✅ Meter {meter_number} imeongezwa kwa {full_name}", "success")

        except sqlite3.IntegrityError:
            conn.rollback()
            flash("⚠️ Meter au mteja tayari ipo kwenye mfumo.", "warning")
        except Exception as e:
            conn.rollback()
            flash(f"❌ Tatizo limetokea: {str(e)}", "danger")
        finally:
            conn.close()

        return redirect(url_for("boss_dashboard"))

    return render_template("add_customer.html")
    
@app.route("/boss/edit_customer/<customer_id>", methods=["GET", "POST"])
def edit_customer(customer_id):
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers WHERE customer_id=?", (customer_id,))
    customer = cur.fetchone()
    if not customer:
        flash("Mteja haipo", "danger")
        conn.close()
        return redirect(url_for("boss_dashboard"))
    if request.method == "POST":
        full_name = request.form.get("full_name")
        meter_number = request.form.get("meter_number")
        if not full_name or not meter_number:
            flash("Jaza majina yote na meter number", "danger")
            return redirect(url_for("edit_customer", customer_id=customer_id))
        try:
            cur.execute("UPDATE customers SET full_name=? WHERE customer_id=?", (full_name, customer_id))
            cur.execute("UPDATE meters SET meter_number=? WHERE customer_id=?", (meter_number, customer_id))
            conn.commit()
            flash(f"Mteja {full_name} amesasishwa!", "success")
        except sqlite3.Error as e:
            flash(f"Kosa la database: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for("boss_dashboard"))
    conn.close()
    return render_template("edit_customer.html", customer=customer)

@app.route("/boss/deactivate_customer/<customer_id>")
def deactivate_customer(customer_id):
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers WHERE customer_id=?", (customer_id,))
    customer = cur.fetchone()
    if not customer:
        flash("Mteja haipo", "danger")
        conn.close()
        return redirect(url_for("boss_dashboard"))
    try:
        cur.execute("UPDATE customers SET status='INACTIVE' WHERE customer_id=?", (customer_id,))
        conn.commit()
        flash(f"Mteja {customer['full_name']} amefungwa!", "success")
    except sqlite3.Error as e:
        flash(f"Kosa la database: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for("boss_dashboard"))

@app.route("/boss/delete_customer/<customer_id>", methods=["GET", "POST"])
def delete_customer(customer_id):
    # 1️⃣ Hakikisha boss ameloga
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]
    boss_name = session.get("boss_name")

    conn = get_db_connection()
    cur = conn.cursor()

    # 2️⃣ Pata info ya mteja
    cur.execute("SELECT * FROM customers WHERE customer_id=?", (customer_id,))
    customer = cur.fetchone()
    if not customer:
        flash("Mteja haipo kwenye mfumo", "danger")
        conn.close()
        return redirect(url_for("boss_dashboard"))

    # 3️⃣ GET request: onyesha confirmation page
    if request.method == "GET":
        conn.close()
        return render_template("confirm_delete_customer.html", customer=customer)

    # 4️⃣ POST request: thibitisha kufuta
    if request.method == "POST":
        try:
            # delete meters associated na mteja
            cur.execute("DELETE FROM meters WHERE customer_id=?", (customer_id,))
            # delete customer
            cur.execute("DELETE FROM customers WHERE customer_id=?", (customer_id,))

            # record activity log with timestamp
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""
                INSERT INTO activity_logs (user_name, role, action, details, boss_id, time)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                boss_name,
                "boss",
                "Delete Customer",
                f"Customer {customer['full_name']} ({customer_id}) deleted",
                boss_id,
                now
            ))

            conn.commit()
            flash(f"Mteja {customer['full_name']} ameondolewa kwa ufanisi!", "success")
        except sqlite3.Error as e:
            flash(f"Kosa la database: {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for("boss_dashboard"))
    
# ================= READ METER =====================
@app.route("/read_meter", methods=["GET", "POST"])
def read_meter():

    # Hakikisha staff au boss ameloga
    if "staff_id" not in session and "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("login"))

    # Amua role na user_id
    if "staff_id" in session:
        user_role = "staff"
        user_id = session.get("staff_id")
        boss_id = session.get("staff_boss_id")
    else:
        user_role = "boss"
        user_id = session.get("boss_id")
        boss_id = user_id

    conn = get_db_connection()
    cur = conn.cursor()

    # 🔹 Angalia status ya boss
    cur.execute("SELECT status FROM boss WHERE boss_id=?", (boss_id,))
    boss_row = cur.fetchone()

    if not boss_row or boss_row["status"] != "ACTIVE":
        flash("⚠️ Boss huyu ni INACTIVE, hauwezi kusoma meters", "warning")
        conn.close()
        return render_template("read_meter.html", bill=None)

    bill = None

    if request.method == "POST":

        meter_number = request.form.get("meter_number")
        current_reading = request.form.get("current_reading")

        if not meter_number or not current_reading:
            flash("Tafadhali jaza meter number na reading", "danger")
            return render_template("read_meter.html", bill=None)

        # 🔹 Ultra safe validation
        if not re.match(r'^[0-9]+(\.[0-9]+)?$', current_reading):
            flash("⚠️ Reading lazima iwe namba halisi positive", "danger")
            return render_template("read_meter.html", bill=None)

        current_reading = float(current_reading)
        if current_reading <= 0 or current_reading > 100000:
            flash("⚠️ Reading iko nje ya range sahihi", "danger")
            return render_template("read_meter.html", bill=None)

        # 🔹 Angalia meter ipo
        cur.execute("""
            SELECT m.meter_id, m.customer_id, m.status AS meter_status, c.full_name
            FROM meters m
            JOIN customers c ON m.customer_id = c.customer_id
            WHERE m.meter_number=? AND c.boss_id=?
        """, (meter_number, boss_id))

        meter = cur.fetchone()
        if not meter:
            flash("Meter hii haipo au sio ya wateja wako", "danger")
            conn.close()
            return render_template("read_meter.html", bill=None)

        if meter["meter_status"] != "ACTIVE":
            flash("⚠️ Meter hii imezimwa (INACTIVE)", "warning")
            conn.close()
            return render_template("read_meter.html", bill=None)

        billing_month = datetime.now().strftime("%Y-%m")

        # 🔹 Tafuta last reading
        cur.execute("""
            SELECT current_reading, billing_month FROM bills
            WHERE meter_id=?
            ORDER BY created_at DESC
            LIMIT 1
        """, (meter["meter_id"],))
        last_bill = cur.fetchone()

        if not last_bill:
            # Meter mpya → insert baseline reading tu, hakuna bill
            cur.execute("""
                INSERT INTO bills
                (bill_id, customer_id, meter_id, previous_reading, current_reading, units_used,
                 amount, billing_month, status, created_at, read_by, reader_role)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "BILL-" + str(uuid.uuid4())[:8],
                meter["customer_id"],
                meter["meter_id"],
                0,                 # previous_reading
                current_reading,   # current_reading
                0,                 # units_used = 0 kwa baseline
                0,                 # amount = 0
                billing_month,
                'BASELINE',        # status BASELINE
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                user_id,
                user_role
            ))
            conn.commit()
            flash(f"✅ Reading imehifadhiwa kama baseline. Bill bado haijajengwa.", "success")
            conn.close()
            return render_template("read_meter.html", bill=None)

        # Meter tayari imekuwa na reading awali
        previous_reading = last_bill["current_reading"]
        last_billing_month = last_bill["billing_month"]

        if last_billing_month == billing_month:
            # Imejaribu kusoma tena mwezi huu
            flash(f"⚠️ Meter tayari imesomwa mwezi huu. Bill haijengeki mara mbili.", "info")
            conn.close()
            return render_template("read_meter.html", bill=None)

        # 🔹 Calculate units used na generate bill
        units_used = current_reading - previous_reading
        if units_used < 0:
            flash("⚠️ Reading mpya haiwezi kuwa ndogo kuliko ya mwisho", "danger")
            conn.close()
            return render_template("read_meter.html", bill=None)

        # 🔹 Pata tariff
        cur.execute("""
            SELECT price_per_unit FROM tariffs
            WHERE boss_id=? ORDER BY created_at DESC LIMIT 1
        """, (boss_id,))
        tariff = cur.fetchone()
        price_per_unit = tariff["price_per_unit"] if tariff else 0

        amount = units_used * price_per_unit
        bill_id = "BILL-" + str(uuid.uuid4())[:8]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 🔹 Insert bill mpya
        cur.execute("""
            INSERT INTO bills
            (bill_id, customer_id, meter_id,
             previous_reading, current_reading, units_used,
             amount, billing_month, status, created_at, read_by, reader_role)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bill_id,
            meter["customer_id"],
            meter["meter_id"],
            previous_reading,
            current_reading,
            units_used,
            amount,
            billing_month,
            'UNPAID',
            now,
            user_id,
            user_role
        ))
        conn.commit()

        bill = {
            "customer_name": meter["full_name"],
            "bill_id": bill_id,
            "meter_date": now,
            "units": units_used,
            "amount": amount
        }

        conn.close()
        flash(f"✅ Bill imejengwa kwa {meter_number} ({meter['full_name']})", "success")

    return render_template("read_meter.html", bill=bill)

@app.route("/boss/meters")
def boss_meters():
    # Hakikisha boss ameingia
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]

    conn = get_db_connection()
    cur = conn.cursor()

    # Chukua wateja wote wa boss na meter zao
    cur.execute("""
        SELECT c.customer_id, c.full_name AS customer_name,
               c.phone, c.area, c.house_number,
               m.meter_id, m.meter_number, m.status AS meter_status
        FROM customers c
        LEFT JOIN meters m ON c.customer_id = m.customer_id
        WHERE c.boss_id = ?
        ORDER BY c.full_name
    """, (boss_id,))

    customers = cur.fetchall()
    conn.close()

    # Tuma data kwenye template
    return render_template("boss_meters.html", customers=customers, boss={"full_name": session.get("boss_name", "Boss")})

    
import uuid

@app.route("/boss_add_meter/<customer_id>", methods=["GET", "POST"])
def boss_add_meter(customer_id):
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]
    conn = get_db_connection()
    cur = conn.cursor()

    # Pata info ya mteja
    cur.execute("SELECT * FROM customers WHERE customer_id=? AND boss_id=?", (customer_id, boss_id))
    customer = cur.fetchone()
    if not customer:
        flash("Mteja haipo au sio wako.", "danger")
        conn.close()
        return redirect(url_for("boss_view_customers"))

    if request.method == "POST":
        meter_number = request.form.get("meter_number")
        if not meter_number:
            flash("Tafadhali andika namba ya meter", "danger")
        else:
            # Angalia kama meter tayari ipo
            cur.execute("SELECT * FROM meters WHERE meter_number=?", (meter_number,))
            existing = cur.fetchone()
            if existing:
                flash(f"Meter {meter_number} tayari ipo", "warning")
            else:
                meter_id = "MTR-" + str(uuid.uuid4())[:8]
                cur.execute("""
                    INSERT INTO meters (meter_id, meter_number, customer_id, status)
                    VALUES (?, ?, ?, ?)
                """, (meter_id, meter_number, customer["customer_id"], "ACTIVE"))
                conn.commit()
                flash(f"✅ Meter {meter_number} imeongezwa kwa {customer['full_name']}", "success")

    # Pata meters zote za mteja
    cur.execute("SELECT * FROM meters WHERE customer_id=?", (customer["customer_id"],))
    meters = cur.fetchall()
    conn.close()

    return render_template("boss_add_meter.html", customer=customer, meters=meters)
@app.route("/boss/tariff", methods=["GET", "POST"])
def boss_tariff():
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]
    conn = get_db_connection()
    cur = conn.cursor()

    # POST: Hapa boss anaweka au update tariff
    if request.method == "POST":
        price_per_unit = request.form.get("price_per_unit")
        if not price_per_unit:
            flash("Tafadhali weka price per unit", "danger")
            return redirect(url_for("boss_tariff"))
        try:
            price_per_unit = float(price_per_unit)
            tariff_id = "TARIFF-" + uuid.uuid4().hex[:8]
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""
                INSERT INTO tariffs (tariff_id, boss_id, price_per_unit, created_at)
                VALUES (?, ?, ?, ?)
            """, (tariff_id, boss_id, price_per_unit, now))
            conn.commit()
            flash(f"Tariff imeundwa: {price_per_unit} Tsh/unit", "success")
        except ValueError:
            flash("Price per unit lazima iwe namba sahihi", "danger")
        except sqlite3.Error as e:
            flash(f"Kosa la database: {e}", "danger")
        return redirect(url_for("boss_tariff"))

    # GET: Onyesha latest tariff ya boss
    cur.execute("""
        SELECT * FROM tariffs WHERE boss_id=? ORDER BY created_at DESC LIMIT 1
    """, (boss_id,))
    tariff = cur.fetchone()
    conn.close()
    return render_template("boss_tariff.html", tariff=tariff)
# ================= UNREAD METERS =====================
@app.route("/unread_meters", methods=["GET", "POST"])
def unread_meters():
    # 1️⃣ Hakikisha boss au staff ana-login
    if "boss_id" not in session and "staff_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("login"))

    # 2️⃣ Tambua role - boss kwanza
    if "boss_id" in session:
        role = "boss"
        boss_id = session.get("boss_id")
    elif "staff_id" in session:
        role = "staff"
        staff_id = session["staff_id"]
        boss_id = session.get("staff_boss_id")

        # 2a️⃣ Hakikisha staff ana jukumu la kusoma meter
        staff_role = session.get("staff_role")
        if staff_role != "meter_reader":
            flash("Huna ruhusa ya kuona meters hizi.", "danger")
            return redirect(url_for("staff_dashboard"))
    else:
        flash("Huna ruhusa ya kuona ukurasa huu.", "danger")
        return redirect(url_for("login"))

    # 3️⃣ Chagua mwezi
    selected_month = request.form.get("month") or datetime.now().strftime("%Y-%m")
    current_month = datetime.now().strftime("%Y-%m")

    conn = get_db_connection()
    cur = conn.cursor()

    # 4️⃣ Pata signup date ya boss
    cur.execute("SELECT signup_date FROM boss WHERE boss_id = ?", (boss_id,))
    boss_data = cur.fetchone()
    if not boss_data:
        conn.close()
        flash("Boss hakupatikana.", "danger")
        return redirect(url_for("staff_dashboard") if role == "staff" else url_for("boss_dashboard"))

    signup_month = boss_data["signup_date"][:7]
    if selected_month < signup_month:
        conn.close()
        return render_template(
            "unread_meters.html",
            unread=[],
            month=selected_month,
            unread_count=0,
            message="Boss hakuwa active mwezi huu.",
            current_month=current_month,
            role=role
        )
    if selected_month > current_month:
        conn.close()
        return render_template(
            "unread_meters.html",
            unread=[],
            month=selected_month,
            unread_count=0,
            message="Huwezi kuangalia mwezi wa mbele.",
            current_month=current_month,
            role=role
        )

    # 5️⃣ Pata meters ambazo hazijasomwa kwa mwezi huu
    query = """
    SELECT c.customer_id, c.full_name, c.phone, c.area,
           m.meter_id, m.meter_number, m.status AS meter_status
    FROM meters m
    JOIN customers c ON m.customer_id = c.customer_id
    WHERE c.boss_id = ?
    AND NOT EXISTS (
        SELECT 1 FROM bills b
        WHERE b.meter_id = m.meter_id
        AND b.billing_month = ?
    )
    ORDER BY c.full_name, m.created_at ASC
    """
    cur.execute(query, (boss_id, selected_month))
    unread = cur.fetchall()
    unread_count = len(unread)
    conn.close()

    return render_template(
        "unread_meters.html",
        unread=unread,
        month=selected_month,
        unread_count=unread_count,
        message=None,
        current_month=current_month,
        role=role
    )
   

@app.route("/unpaid_bills")
def unpaid_bills():
    """
    Route ya kuonyesha bills zisizolipwa kwa kila role.
    Kila bill ina meter yake halisi, hakuna duplication au 'Hakuna'.
    """
    # ======== Hakikisha user ameloga ========
    if "boss_id" in session:
        user_role = "boss"
        boss_id = session.get("boss_id")
    elif "staff_id" in session:
        user_role = "staff"
        boss_id = session.get("staff_boss_id")
    elif "superadmin_id" in session:
        user_role = "superadmin"
        boss_id = None
    else:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # ======== Pata bills zisizolipwa ========
    if user_role == "superadmin":
        bills = conn.execute("""
            SELECT b.bill_id, b.customer_id, b.units_used, b.amount, b.billing_month,
                   c.full_name AS customer_name,
                   m.meter_number
            FROM bills b
            JOIN customers c ON b.customer_id = c.customer_id
            JOIN meters m ON b.meter_id = m.meter_id
            WHERE b.status='UNPAID'
            ORDER BY b.billing_month DESC
        """).fetchall()
    else:
        bills = conn.execute("""
            SELECT b.bill_id, b.customer_id, b.units_used, b.amount, b.billing_month,
                   c.full_name AS customer_name,
                   m.meter_number
            FROM bills b
            JOIN customers c ON b.customer_id = c.customer_id
            JOIN meters m ON b.meter_id = m.meter_id
            WHERE b.status='UNPAID' AND c.boss_id = ?
            ORDER BY b.billing_month DESC
        """, (boss_id,)).fetchall()

    conn.close()

    # ======== Return template ========
    return render_template("unpaid_bills.html", unpaid_bills=bills, user_role=user_role)
                               
@app.route("/boss/customers")
def boss_view_customers():
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    # Chukua customers na meters zao zote (row moja kwa customer)
    customers = conn.execute("""
        SELECT c.customer_id, c.full_name AS customer_name,
               c.phone, c.area, c.house_number,
               c.status AS customer_status,
               GROUP_CONCAT(m.meter_number) AS meters,
               GROUP_CONCAT(m.status) AS meter_statuses
        FROM customers c
        LEFT JOIN meters m ON c.customer_id = m.customer_id
        WHERE c.boss_id = ?
        GROUP BY c.customer_id
        ORDER BY c.full_name
    """, (boss_id,)).fetchall()

    conn.close()
    return render_template("boss_customers.html", customers=customers)
@app.route("/boss/toggle_meter/<meter_number>")
def toggle_meter(meter_number):
    # Hakikisha boss amelogin
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]
    conn = get_db_connection()
    cur = conn.cursor()

    # Hakikisha meter ipo na ni ya mteja wa boss huyu
    cur.execute("""
        SELECT m.status FROM meters m
        JOIN customers c ON m.customer_id = c.customer_id
        WHERE m.meter_number = ? AND c.boss_id = ?
    """, (meter_number, boss_id))

    meter = cur.fetchone()
    if not meter:
        flash("Meter haipatikani au sio ya account yako", "danger")
        conn.close()
        return redirect(url_for("boss_view_customers"))

    # Toggle status
    new_status = "INACTIVE" if meter["status"] == "ACTIVE" else "ACTIVE"
    cur.execute("""
        UPDATE meters
        SET status = ?
        WHERE meter_number = ?
    """, (new_status, meter_number))

    conn.commit()
    conn.close()
    flash(f"Meter {meter_number} imebadilishwa kuwa {new_status}", "success")
    return redirect(url_for("boss_view_customers"))
    
@app.route("/boss/toggle_customer/<customer_id>")
def toggle_customer(customer_id):

    # 1️⃣ Hakikisha boss amelogin
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]

    conn = get_db_connection()
    cur = conn.cursor()

    # 2️⃣ Hakikisha customer ni wa boss huyu
    cur.execute("""
        SELECT status FROM customers
        WHERE customer_id = ? AND boss_id = ?
    """, (customer_id, boss_id))

    customer = cur.fetchone()

    if not customer:
        flash("Mteja hapatikani au sio wa account yako", "danger")
        conn.close()
        return redirect(url_for("boss_view_customers"))

    # 3️⃣ Badilisha status
    if customer["status"] == "ACTIVE":
        new_status = "INACTIVE"
    else:
        new_status = "ACTIVE"

    cur.execute("""
        UPDATE customers
        SET status = ?
        WHERE customer_id = ?
    """, (new_status, customer_id))

    conn.commit()
    conn.close()

    flash("Status ya mteja imebadilishwa kikamilifu", "success")
    return redirect(url_for("boss_view_customers"))
    
    

# ================= RECEIVE PAYMENT =====================
# ================= RECEIVE PAYMENT =====================
@app.route("/receive_payment/<bill_id>", methods=["GET", "POST"])
def receive_payment(bill_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1️⃣ Hakikisha ameloga
    if "staff_id" not in session and "boss_id" not in session:
        flash("Tafadhali login kwanza", "danger")
        return redirect(url_for("boss_login"))

    # 2️⃣ Amua role na user_id
    if "staff_id" in session:
        user_role = "staff"
        user_id = session["staff_id"]
        boss_id_for_record = session.get("staff_boss_id")  # boss sahihi kwa staff
        user_name = session.get("staff_name")
    else:
        user_role = "boss"
        user_id = session["boss_id"]
        boss_id_for_record = user_id  # kwa boss, boss_id = user_id
        user_name = session.get("boss_name")

    # 2.1️⃣ Kagua status ya boss
    boss_status = cursor.execute(
        "SELECT status FROM boss WHERE boss_id=?", 
        (boss_id_for_record,)
    ).fetchone()

    if not boss_status:
        conn.close()
        flash("Boss haipo kwenye mfumo", "danger")
        return redirect(url_for("boss_login"))

    if boss_status["status"] != "ACTIVE":
        conn.close()
        flash("Hauwezi kufanya malipo: Akaunti ya boss imezuiliwa", "danger")
        if user_role == "staff":
            return redirect(url_for("staff_dashboard"))
        else:
            return redirect(url_for("boss_dashboard"))

    # 3️⃣ Pata bill info
    bill = cursor.execute("""
        SELECT b.*, c.full_name AS customer_name, c.customer_id,
               m.meter_number
        FROM bills b
        JOIN customers c ON b.customer_id = c.customer_id
        LEFT JOIN meters m ON c.customer_id = m.customer_id
        WHERE b.bill_id=?
    """, (bill_id,)).fetchone()

    if not bill:
        conn.close()
        flash("Bili haipo", "danger")
        if user_role == "staff":
            return redirect(url_for("staff_dashboard"))
        else:
            return redirect(url_for("boss_dashboard"))

    # 4️⃣ POST: process payment
    if request.method == "POST":
        payment_id = "PAY-" + uuid.uuid4().hex[:8]
        receipt_id = "RCPID-" + uuid.uuid4().hex[:8]

        # Generate receipt number
        year = datetime.now().year
        count = cursor.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] + 1
        receipt_number = f"RCP-{year}-{str(count).zfill(5)}"

        # 🔹 Muda mmoja wa sasa
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ✅ Insert payment
        cursor.execute("""
            INSERT INTO payments
            (payment_id, bill_id, customer_id, boss_id, amount_paid, payment_method, reference, paid_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payment_id,
            bill["bill_id"],
            bill["customer_id"],
            boss_id_for_record,
            bill["amount"],
            "CASH",
            None,
            now
        ))

        # ✅ Update bill status
        cursor.execute("""
            UPDATE bills
            SET status='PAID', payment_method='CASH', payment_date=?
            WHERE bill_id=?
        """, (now, bill_id))

        # ✅ Insert receipt
        cursor.execute("""
            INSERT INTO receipts
            (receipt_id, payment_id, receipt_number, customer_id, boss_id, amount, issued_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            receipt_id,
            payment_id,
            receipt_number,
            bill["customer_id"],
            boss_id_for_record,
            bill["amount"],
            now
        ))

        # ✅ Record activity log with boss_id and time
        cursor.execute("""
            INSERT INTO activity_logs (user_name, role, action, details, boss_id, time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_name,
            user_role,
            "Receive Payment",
            f"Payment received for bill {bill_id} amount {bill['amount']}",
            boss_id_for_record,
            now
        ))

        conn.commit()
        conn.close()

        flash("Malipo yamepokelewa na risiti imetengenezwa!", "success")
        return redirect(url_for("view_receipt", receipt_id=receipt_id))

    # 5️⃣ GET: show confirmation page
    conn.close()
    return render_template("confirm_payment.html", bill=bill)
    
@app.route("/receipt/<receipt_id>")
def view_receipt(receipt_id):
    # Hakikisha user ameloga
    if "boss_id" not in session and "staff_id" not in session:
        flash("Tafadhali login kwanza", "danger")
        return redirect(url_for("login"))

    # Amua role ya user
    if "staff_id" in session:
        user_role = "staff"
        user_id = session["staff_id"]
    else:
        user_role = "boss"
        user_id = session["boss_id"]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Pata risiti
    receipt = cursor.execute("""
        SELECT r.*, c.full_name, c.phone
        FROM receipts r
        JOIN customers c ON r.customer_id = c.customer_id
        WHERE r.receipt_id=?
    """, (receipt_id,)).fetchone()

    conn.close()

    if not receipt:
        flash("Risiti haipo", "danger")
        # Rudisha kulingana na role
        if user_role == "staff":
            return redirect(url_for("staff_dashboard"))
        else:
            return redirect(url_for("boss_dashboard"))

    # Onyesha template ya risiti, tuma role
    return render_template("receipt.html", receipt=receipt, user_role=user_role)

    return render_template("receipt.html", receipt=receipt)    
@app.route("/boss/add_staff", methods=["GET", "POST"])
def add_staff():
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]

    if request.method == "POST":
        full_name = request.form.get("full_name")
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")  # backend-friendly value

        if not full_name or not username or not password or not role:
            flash("Tafadhali jaza majina yote, username, password na jukumu", "danger")
            return redirect(url_for("add_staff"))

        hashed_pw = generate_password_hash(password)
        staff_id = generate_staff_id()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "ACTIVE"

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO staff (staff_id, boss_id, full_name, username, password, role, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (staff_id, boss_id, full_name, username, hashed_pw, role, status, now))
            conn.commit()
            flash(f"Staff {full_name} ameundwa kikamilifu na role '{role}'", "success")
        except sqlite3.IntegrityError:
            flash("Username tayari ipo kwenye mfumo.", "danger")
        finally:
            conn.close()

        return redirect(url_for("view_staff"))

    return render_template("add_staff.html")
                          
# ==========================
# Route: Orodhesha staff wa boss
# ==========================
@app.route("/boss/view_staff")
def view_staff():
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM staff WHERE boss_id=?", (boss_id,))
    staff_list = cur.fetchall()
    conn.close()

    # Hapa tuna send variable jina sawa na template
    return render_template("view_staff.html", staff_members=staff_list)
    
    
@app.route("/boss/toggle_staff/<staff_id>")
def toggle_staff(staff_id):
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    conn = get_db_connection()
    cur = conn.cursor()

    # Pata current status
    cur.execute("SELECT status FROM staff WHERE staff_id=?", (staff_id,))
    staff = cur.fetchone()
    if not staff:
        flash("Staff haipo", "danger")
        conn.close()
        return redirect(url_for("view_staff"))

    # Badilisha status
    new_status = "INACTIVE" if staff["status"] == "ACTIVE" else "ACTIVE"
    cur.execute("UPDATE staff SET status=? WHERE staff_id=?", (new_status, staff_id))
    conn.commit()
    conn.close()

    flash(f"Staff status imebadilishwa kuwa {new_status}", "success")
    return redirect(url_for("view_staff")) 
    
# ================= STAFF LOGIN =====================
@app.route("/staff/login", methods=["GET", "POST"])
def staff_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection()
        staff = conn.execute("SELECT * FROM staff WHERE username=?", (username,)).fetchone()
        conn.close()

        if staff and check_password_hash(staff["password"], password):
            # Angalia status
            if staff["status"] != "ACTIVE":
                flash("Account yako imefungwa. Wasiliana na boss wako.", "danger")
                return redirect(url_for("staff_login"))

            # ✅ Safisha session zote kwanza
            session.clear()

            # Weka session mpya
            session["staff_id"] = staff["staff_id"]
            session["staff_name"] = staff["full_name"]
            session["staff_role"] = staff["role"].lower()  # lowercase English backend-friendly
            session["staff_boss_id"] = staff["boss_id"]

            flash(f"Karibu {staff['full_name']}!", "success")
            return redirect(url_for("staff_dashboard"))

        flash("Username au password sio sahihi.", "danger")

    return render_template("staff_login.html")
                             
# ================= STAFF DASHBOARD =====================
@app.route("/staff/dashboard")
def staff_dashboard():
    # Hakikisha staff ameloga
    if "staff_id" not in session:
        flash("Tafadhali login kwanza", "danger")
        return redirect(url_for("staff_login"))

    # Pata session info
    staff_id = session.get("staff_id")
    staff_name = session.get("staff_name")
    staff_role = session.get("staff_role")  # meter_reader, cashier, etc
    staff_boss_id = session.get("staff_boss_id")
    current_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    conn = get_db_connection()
    cur = conn.cursor()

    # Hapa tunaweza kuhesabu stats kulingana na boss (optional)
    cur.execute("""
        SELECT COUNT(*) AS active_count
        FROM meters m
        JOIN customers c ON m.customer_id = c.customer_id
        WHERE c.boss_id = ? AND m.status = 'ACTIVE'
    """, (staff_boss_id,))
    active_count = cur.fetchone()["active_count"]

    cur.execute("""
        SELECT COUNT(*) AS inactive_count
        FROM meters m
        JOIN customers c ON m.customer_id = c.customer_id
        WHERE c.boss_id = ? AND m.status = 'INACTIVE'
    """, (staff_boss_id,))
    inactive_count = cur.fetchone()["inactive_count"]

    conn.close()

    # Render template na data
    return render_template(
        "staff_dashboard.html",
        staff_id=staff_id,
        staff_name=staff_name,
        staff_role=staff_role,
        staff_boss_id=staff_boss_id,
        current_time=current_time,
        active_count=active_count,
        inactive_count=inactive_count
    )
                                                                                                                                
@app.route("/staff/logout")
def staff_logout():
    session.pop("staff_id", None)
    session.pop("staff_name", None)
    session.pop("staff_role", None)
    session.pop("staff_boss_id", None)
    flash("Umetoka kwenye akaunti yako.", "success")
    return redirect(url_for("staff_login"))
    
       
             
@app.route("/collector/dashboard")
def collector_dashboard():
    # Unauthorized check
    if "staff_id" not in session or session.get("staff_role") != "collector":
        flash("Huna ruhusa ya ku-access dashboard hii.", "danger")
        return redirect(url_for("staff_login"))

    conn = get_db_connection()
    cur = conn.cursor()

    # Orodha ya bills ambazo hazijalipwa kwa staff huyu (boss yao)
    cur.execute("""
        SELECT b.bill_id, c.full_name AS customer_name, b.units_used, b.amount, b.billing_month
        FROM bills b
        JOIN customers c ON b.customer_id = c.customer_id
        WHERE b.status='UNPAID' AND b.boss_id=?
        ORDER BY b.billing_month DESC
    """, (session["staff_boss_id"],))
    unpaid_bills = cur.fetchall()

    # Summary ya malipo yaliyokusanywa
    cur.execute("""
        SELECT SUM(amount_paid) AS total_collected
        FROM payments
        WHERE boss_id=? 
    """, (session["staff_boss_id"],))
    total_collected = cur.fetchone()["total_collected"] or 0

    conn.close()

    return render_template("collector_dashboard.html", unpaid_bills=unpaid_bills, total_collected=total_collected)
    
        
@app.route("/check_role")
def check_role():
    if "staff_id" not in session:
        return "Huja login"

    return f"""
    Jina: {session.get('staff_name')} <br>
    Role: '{session.get('staff_role')}' <br>
    """                
      
@app.route("/staff/finance_reports")
def finance_reports():
    # Placeholder page ya accountant
    return """
    <div style='text-align:center; margin-top:50px;'>
        <h2>Karibu kwenye Ripoti za Uhasibu</h2>
        <p>Hapa accountant anaweza kuona ripoti za kifedha.</p>
        <a href='{}'>Rudi Dashboard</a>
    </div>
    """.format(url_for('staff_dashboard'))
    
          
# ================= STAFF: VIEW CUSTOMERS =====================
@app.route("/staff/view_customers")
def staff_view_customers():
    # 1️⃣ Hakikisha staff ame-login
    if "staff_id" not in session:
        flash("Tafadhali login kwanza", "danger")
        return redirect(url_for("staff_login"))

    staff_id = session["staff_id"]
    staff_name = session.get("staff_name")
    staff_role = session.get("staff_role")
    staff_boss_id = session.get("staff_boss_id")

    # 2️⃣ Pata wateja wa boss aliye chini ya staff huyu
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT customer_id, full_name, phone, area, house_number, meter_number, status
        FROM customers
        WHERE boss_id = ?
        ORDER BY full_name ASC
    """, (staff_boss_id,))
    customers = cur.fetchall()
    conn.close()

    # 3️⃣ Tuma data kwenye template ya staff
    return render_template(
        "staff_view_customers.html",
        staff_name=staff_name,
        staff_role=staff_role,
        staff_id=staff_id,
        customers=customers
    )
    
    
@app.route("/boss/monthly_report")
def boss_monthly_report():
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]
    month = request.args.get("month")

    if not month:
        flash("Chagua mwezi!", "warning")
        return redirect(url_for("boss_dashboard"))

    conn = get_db_connection()
    cur = conn.cursor()

    # Chukua bills zote za mwezi huo
    cur.execute("""
        SELECT b.bill_id,
               b.customer_id,
               c.full_name AS customer_name,
               b.meter_id,
               b.units_used,
               b.amount,
               b.status,
               b.billing_month,
               b.payment_method,
               b.payment_date
        FROM bills b
        JOIN customers c ON b.customer_id = c.customer_id
        WHERE c.boss_id = ? AND b.billing_month = ?
        ORDER BY b.bill_id DESC
    """, (boss_id, month))

    bills = cur.fetchall()

    # Totals
    total_units = sum(b["units_used"] for b in bills)
    total_amount = sum(b["amount"] for b in bills)

    # Count Paid / Unpaid correctly
    paid_count = sum(1 for b in bills if b["status"].upper() == "PAID")
    unpaid_count = sum(1 for b in bills if b["status"].upper() == "UNPAID")

    # Optional: totals for paid bills only
    total_paid_units = sum(b["units_used"] for b in bills if b["status"].upper() == "PAID")
    total_paid_amount = sum(b["amount"] for b in bills if b["status"].upper() == "PAID")

    conn.close()

    return render_template(
        "boss_monthly_report.html",
        bills=bills,
        month=month,
        total_units=total_units,
        total_amount=total_amount,
        paid_count=paid_count,
        unpaid_count=unpaid_count,
        total_paid_units=total_paid_units,
        total_paid_amount=total_paid_amount
    )
@app.route("/search_customer", methods=["GET","POST"])
def search_customer():

    if request.method == "POST":

        name = request.form.get("customer_name","").strip()

        if name == "":
            flash("Andika jina la mteja kwanza","warning")
            return redirect(url_for("search_customer"))

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
        SELECT * FROM customers
        WHERE full_name LIKE ?
        """,(f"%{name}%",))

        customer = cur.fetchone()

        conn.close()

        if customer:
            return redirect(url_for(
                "customer_details",
                customer_id=customer["customer_id"]
            ))
        else:
            flash("Mteja hajapatikana","danger")

    return render_template("search_customer.html")
    
      
        
          
@app.route("/boss/confirm_delete_customer/<customer_id>", methods=["GET", "POST"])
def confirm_delete_customer(customer_id):
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers WHERE customer_id=?", (customer_id,))
    customer = cur.fetchone()
    conn.close()

    if not customer:
        flash("Mteja haipo", "danger")
        return redirect(url_for("boss_dashboard"))

    if request.method == "POST":
        # Ikiwa boss amethibitisha, futa mteja
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM meters WHERE customer_id=?", (customer_id,))
            cur.execute("DELETE FROM customers WHERE customer_id=?", (customer_id,))
            conn.commit()
            flash(f"Mteja {customer['full_name']} ameondolewa!", "success")
        except sqlite3.Error as e:
            flash(f"Kosa la database: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for("boss_dashboard"))

    # GET: Onyesha page ya uthibitisho
    return render_template("confirm_delete_customer.html", customer=customer)              
                
@app.route("/customer_details/<customer_id>")
def customer_details(customer_id):

    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # pata taarifa za mteja
    cur.execute("""
        SELECT * FROM customers
        WHERE customer_id = ?
    """, (customer_id,))
    customer = cur.fetchone()

    # pata meters za mteja
    cur.execute("""
        SELECT meter_id, meter_number, status
        FROM meters
        WHERE customer_id = ?
    """, (customer_id,))
    meters = cur.fetchall()

    # pata bills zisizolipwa tu
    cur.execute("""
        SELECT 
            b.bill_id,
            b.amount,
            b.units_used,
            b.billing_month,
            b.status,
            m.meter_number
        FROM bills b
        JOIN meters m ON b.meter_id = m.meter_id
        WHERE b.customer_id = ? AND b.status = 'UNPAID'
        ORDER BY b.billing_month DESC
    """, (customer_id,))
    bills = cur.fetchall()

    conn.close()

    return render_template(
        "customer_details.html",
        customer=customer,
        meters=meters,
        bills=bills
    )
    
@app.route("/")
def index():
    # Rudisha user kwa login page
    return redirect(url_for("boss_login"))
    # au kwa superadmin: return redirect(url_for("superadmin_login"))    
# ================= RUN APP ==================
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))  # Render ina-set PORT env variable
    app.run(host="0.0.0.0", port=port)