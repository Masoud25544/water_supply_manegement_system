# =======================
# 1️⃣ Imports Kamili
# =======================
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
import hashlib
from functools import wraps
from flask import session, redirect, url_for, flash


def hash_password(password):
    # SHA256 hashing
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def generate_staff_id():
    return "STF-" + str(uuid.uuid4())[:8]

app = Flask(__name__)
app.secret_key = "supersecretkey"
DB_PATH = "water_supply.db"


# =======================
# DB CONNECTION
# =======================
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =======================
# ✅ SINGLE ACCESS CONTROL (NEW)
# =======================

def check_access(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 🔹 Tambua role na boss_id
        if "staff_id" in session:
            boss_id = session.get("staff_boss_id")
            role = "staff"
        elif "boss_id" in session:
            boss_id = session.get("boss_id")
            role = "boss"
        else:
            flash("Tafadhali ingia kwanza", "danger")
            # staff login default
            return redirect(url_for("staff_login"))

        # 🔹 Pata info ya boss
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT status, trial_end_date, subscription_end_date 
            FROM boss 
            WHERE boss_id = ?
        """, (boss_id,))
        boss = cur.fetchone()
        conn.close()

        if not boss:
            flash("Session imeisha, ingia tena", "danger")
            return redirect(url_for("staff_login"))

        now = datetime.now()
        status = boss["status"]

        # =========================
        # 🔹 Dynamic Time Check (Force)
        # =========================
        try:
            # 🔹 TRIAL
            if boss["trial_end_date"]:
                trial_end = datetime.strptime(boss["trial_end_date"], "%Y-%m-%d %H:%M:%S")
                if now > trial_end and status == "TRIAL":
                    status = "TRIAL_EXPIRE"
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute("UPDATE boss SET status=? WHERE boss_id=?", (status, boss_id))
                    conn.commit()
                    conn.close()
                    if not session.get("trial_expired_shown"):
                        flash("Boss, trial imeisha. Wasiliana na admin ili kuendelea.", "warning")
                        session["trial_expired_shown"] = True

            # 🔹 SUBSCRIPTION
            if boss["subscription_end_date"]:
                sub_end = datetime.strptime(boss["subscription_end_date"], "%Y-%m-%d %H:%M:%S")
                if now > sub_end and status == "ACTIVE":
                    status = "SUBSCRIPTION_EXPIRE"
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute("UPDATE boss SET status=? WHERE boss_id=?", (status, boss_id))
                    conn.commit()
                    conn.close()
                    if not session.get("subscription_expired_shown"):
                        flash("Subscription imeisha. Tafadhali lipa ili kuendelea.", "warning")
                        session["subscription_expired_shown"] = True

        except Exception as e:
            # ⚠️ Safeguard: kama parsing ikishindwa, tunaendelea
            print("⚠️ check_access datetime parsing error:", e)

        # =========================
        # 🔥 HARD BLOCK (BOSS + STAFF)
        # =========================
        if status in ["TRIAL_EXPIRE", "SUBSCRIPTION_EXPIRE", "INACTIVE"]:
            msg = "⚠️ Huduma ya boss imefungwa. Tafadhali wasiliana na Masoud (0744906763) ili kuendelea."
            flash(msg, "danger")

            # 🔁 Rudisha kulingana na role
            if role == "staff":
                return redirect(url_for("staff_dashboard"))
            else:
                return redirect(url_for("boss_dashboard"))

        # ✅ End of checks, lete function
        return f(*args, **kwargs)

    return decorated_function


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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
        # ANNOUNCEMENTS
        # =====================================================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # 🔹 Safe add created_by column (if it does not exist)
        try:
            cur.execute("ALTER TABLE announcements ADD COLUMN created_by TEXT;")
        except sqlite3.OperationalError:
            pass  # column already exists

        # =====================================================
        # ANNOUNCEMENT READS
        # =====================================================
        cur.execute("""
        CREATE TABLE IF NOT EXISTS announcement_reads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            announcement_id INTEGER NOT NULL,
            boss_id TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # =====================================================
        # UNIQUE INDEX
        # =====================================================
        cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_announcement_read_unique
        ON announcement_reads (announcement_id, boss_id)
        """)

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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 🔹 SAFE ADD subscription_end_date COLUMN (HAIVURUGI CHOCHOTE)
        try:
            cur.execute("ALTER TABLE boss ADD COLUMN subscription_end_date TEXT;")
        except sqlite3.OperationalError:
            pass  # column tayari ipo

        # 🔹 SAFE ADD is_online COLUMN (HAIVURUGI CHOCHOTE)
        try:
            cur.execute("ALTER TABLE boss ADD COLUMN is_online INTEGER DEFAULT 0;")
        except sqlite3.OperationalError:
            pass  # column tayari ipo

        # 🆕 🔹 SAFE ADD phone COLUMN (MPYA)
        try:
            cur.execute("ALTER TABLE boss ADD COLUMN phone TEXT;")
        except sqlite3.OperationalError:
            pass  # column tayari ipo

        # 🆕 🔹 SAFE ADD email COLUMN (MPYA)
        try:
            cur.execute("ALTER TABLE boss ADD COLUMN email TEXT;")
        except sqlite3.OperationalError:
            pass  # column tayari ipo

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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            permissions TEXT,
            FOREIGN KEY (boss_id) REFERENCES boss(boss_id) ON DELETE CASCADE
        )
        """)

        # 🔹 SAFE ADD reset_required COLUMN (HAIVURUGI CHOCHOTE)
        try:
            cur.execute("ALTER TABLE staff ADD COLUMN reset_required INTEGER DEFAULT 0;")
        except sqlite3.OperationalError:
            pass  # column tayari ipo

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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
        try:
            conn.commit()
            conn.close()
        except:
            pass

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
        admin = cur.fetchone()  # sasa admin ni dict
        conn.close()

        if admin and check_password_hash(admin["password"], password):
            # hakikisha session key inasetiwa
            session["superadmin_id"] = admin["admin_id"]
            flash("Karibu Super Admin!", "success")
            return redirect(url_for("superadmin_dashboard"))

        flash("Username au password si sahihi.", "danger")

    return render_template("superadmin_login.html")
    
@app.route("/superadmin/dashboard")
def superadmin_dashboard():
    if "superadmin_id" not in session:
        return redirect(url_for("superadmin_login"))

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 🔹 Pata list ya bosses na dynamic online status, pia phone + email
    cur.execute("""
        SELECT boss_id, full_name, username, status, signup_date, trial_end_date, phone, email,
               CASE 
                   WHEN status IN ('TRIAL', 'ACTIVE') THEN 1
                   ELSE 0
               END AS is_online
        FROM boss
        ORDER BY full_name
    """)
    bosses = [dict(b) for b in cur.fetchall()]

    # 🔹 Hesabu idadi ya bosses online sasa hivi
    online_count = sum(1 for b in bosses if b['is_online'] == 1)

    # 🔹 Calculate days passed, days left kwa TRIAL bosses
    today = datetime.now().date()
    boss_list = []

    for b in bosses:
        # Safely parse dates
        try:
            signup = datetime.strptime(b['signup_date'], "%Y-%m-%d %H:%M:%S").date()
        except Exception:
            signup = today

        try:
            trial_end = datetime.strptime(b['trial_end_date'], "%Y-%m-%d %H:%M:%S").date()
        except Exception:
            trial_end = today

        days_passed = (today - signup).days
        days_left = (trial_end - today).days

        boss_list.append({
            'boss_id': b['boss_id'],
            'full_name': b['full_name'],
            'username': b['username'],
            'status': b['status'],
            'signup_date': b['signup_date'],
            'trial_end_date': b['trial_end_date'],
            'days_passed': days_passed,
            'days_left': max(days_left, 0),
            'is_expired': today > trial_end,
            'is_online': b['is_online'] == 1,  # ✅ TRIAL/ACTIVE bosses online
            'phone': b.get('phone', ''),       # 🔹 Add phone
            'email': b.get('email', '')        # 🔹 Add email
        })

    conn.close()
    return render_template("superadmin_dashboard.html", bosses=boss_list, online_count=online_count)
    


@app.route("/superadmin/search_boss", methods=["GET"])
def search_boss():
    query = request.args.get("query") or ""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 🔹 Search in multiple columns: full_name, username, phone, email
    cur.execute("""
        SELECT * FROM boss
        WHERE full_name LIKE ?
           OR username LIKE ?
           OR phone LIKE ?
           OR email LIKE ?
        ORDER BY full_name
    """, ('%' + query + '%', '%' + query + '%', '%' + query + '%', '%' + query + '%'))

    bosses = [dict(b) for b in cur.fetchall()]
    conn.close()
    return render_template("search_boss.html", results=bosses, query=query)



from flask import jsonify

@app.route("/superadmin/online_count")
def online_count_api():
    if "superadmin_id" not in session:
        return jsonify({"online_count": 0})  # kama si logged in, return 0

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM boss WHERE is_online = 1")
    count = cur.fetchone()[0] or 0
    cur.close()
    conn.close()

    return jsonify({"online_count": count})
    
        
                
@app.route("/super_admin/announcement", methods=["GET", "POST"])
def create_announcement():
    # 🔹 Session key inafanana na login
    if "superadmin_id" not in session:
        flash("Ingia kama super admin kwanza", "danger")
        return redirect(url_for("superadmin_login"))

    if request.method == "POST":
        title = request.form["title"]
        message = request.form["message"]

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO announcements (title, message, created_by)
            VALUES (?, ?, ?)
        """, (title, message, session["superadmin_id"]))

        conn.commit()
        conn.close()

        flash("Tangazo limefanikiwa kutumwa!", "success")
        return redirect(url_for("create_announcement"))

    return render_template("create_announcement.html")
    
    
    
@app.route("/superadmin/boss/<boss_id>/customers")
def superadmin_boss_customers(boss_id):
    # 🔒 Hakikisha superadmin ame-login
    if "superadmin_id" not in session:
        flash("Unauthorized access", "danger")
        return redirect(url_for("superadmin_login"))

    conn = get_db_connection()
    cur = conn.cursor()

    # Pata maboss (optional, kwa dropdown au reference)
    cur.execute("SELECT boss_id, full_name, username FROM boss ORDER BY full_name")
    bosses = cur.fetchall()

    # Pata customers wa boss huyu moja kwa moja
    cur.execute("""
        SELECT 
            c.customer_id,
            c.full_name,
            c.phone,
            c.area,
            c.house_number,
            c.status,
            GROUP_CONCAT(m.meter_number) AS meters
        FROM customers c
        LEFT JOIN meters m ON c.customer_id = m.customer_id
        WHERE c.boss_id = ?
        GROUP BY c.customer_id
        ORDER BY c.full_name
    """, (boss_id,))
    customers = cur.fetchall()

    conn.close()

    return render_template(
        "superadmin_boss_customers.html",
        bosses=bosses,
        selected_boss_id=boss_id,
        customers=customers
    )
    


def check_subscription(boss_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT subscription_end_date FROM boss WHERE boss_id = ?", (boss_id,))
    boss = cur.fetchone()

    conn.close()

    if boss:
        sub_end_str = boss["subscription_end_date"]
        if not sub_end_str:
            # Hakuna subscription imewekwa → acha kuendelea, au weka False
            return False

        try:
            end_date = datetime.strptime(sub_end_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # Ikiwa date iko mbovu au haiko sawa format
            return False

        if datetime.now() > end_date:
            return False  # muda umeisha

    else:
        return False  # boss haipo

    return True
    
    
  


@app.route("/superadmin/customer/<customer_id>/meters")
def superadmin_customer_meters(customer_id):
    # Hakikisha superadmin ame-login
    if "superadmin_id" not in session:
        return redirect(url_for("superadmin_login"))

    conn = get_db_connection()
    cur = conn.cursor()

    # Pata customer info pamoja na boss_id
    cur.execute("SELECT full_name, boss_id FROM customers WHERE customer_id = ?", (customer_id,))
    customer = cur.fetchone()

    # Pata meters zote za customer huyu
    cur.execute("""
        SELECT meter_number, status, created_at
        FROM meters
        WHERE customer_id = ?
        ORDER BY meter_id DESC
    """, (customer_id,))
    meters = cur.fetchall()

    conn.close()

    # Pass boss_id kwenye template ili Back button ifanye kazi
    return render_template(
        "superadmin_customer_meters.html",
        customer=customer,
        meters=meters,
        boss_id=customer['boss_id']
    )

@app.route("/superadmin/boss/new")
def new_bosses():
    conn = sqlite3.connect("water_supply.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Chagua bosses wote
    cur.execute("SELECT * FROM boss ORDER BY signup_date ASC")
    bosses = cur.fetchall()

    today = datetime.now().date()  # Tumia date tu
    boss_list = []

    for b in bosses:
        signup = datetime.strptime(b['signup_date'], "%Y-%m-%d %H:%M:%S").date()
        trial_end = datetime.strptime(b['trial_end_date'], "%Y-%m-%d %H:%M:%S").date()

        days_passed = (today - signup).days
        days_left = (trial_end - today).days

        # Live status calculation
        if b['status'] == "RESET_PENDING":
            status = "RESET_PENDING"
        elif today > trial_end:
            status = "EXPIRED"
        else:
            status = b['status']

        display_days_left = max(days_left, 0)

        boss_list.append({
            'boss_id': b['boss_id'],
            'full_name': b['full_name'],
            'username': b['username'],
            'status': status,
            'signup_date': b['signup_date'],
            'trial_end_date': b['trial_end_date'],
            'days_passed': days_passed,
            'days_left': display_days_left
        })

    conn.close()
    return render_template("boss_wapya.html", bosses=boss_list)
    
    


@app.route("/superadmin/boss/<boss_id>/trigger_reset", methods=["POST"])
def superadmin_trigger_boss_reset(boss_id):
    if "superadmin_id" not in session:
        flash("Unauthorized access", "danger")
        return redirect(url_for("superadmin_login"))

    temp_password = "reset123"  # Temporary password
    hashed = generate_password_hash(temp_password)

    conn = get_db_connection()
    cur = conn.cursor()

    # 🔹 Hifadhi status ya sasa kabla ya kubadilisha password
    cur.execute("SELECT status FROM boss WHERE boss_id=?", (boss_id,))
    boss = cur.fetchone()
    if not boss:
        conn.close()
        flash("Boss haipo", "danger")
        return redirect(url_for("superadmin_dashboard"))

    current_status = boss["status"]

    # 🔹 Badilisha password tu, status ibaki ile ile
    cur.execute(
        "UPDATE boss SET password=?, status=? WHERE boss_id=?",
        (hashed, current_status, boss_id)
    )
    conn.commit()
    conn.close()

    flash(f"Boss ameombwa kuweka PIN mpya. Temporary password ni: {temp_password}", "info")
    return redirect(url_for("superadmin_dashboard"))    





@app.route("/superadmin/boss/<boss_id>/toggle")
def toggle_boss(boss_id):
    conn = get_db_connection()
    cur = conn.cursor()
    now = datetime.now()

    # Get current status
    cur.execute("SELECT status FROM boss WHERE boss_id=?", (boss_id,))
    boss = cur.fetchone()

    if not boss:
        flash("Boss haipo", "danger")
        return redirect(url_for("superadmin_dashboard"))

    # Toggle logic
    if boss["status"] == "ACTIVE":
        # Disable boss
        cur.execute("UPDATE boss SET status='INACTIVE', subscription_end_date=NULL WHERE boss_id=?", (boss_id,))
    else:
        # Enable boss and set subscription_end_date
        subscription_end = now + timedelta(minutes=20)  # testing duration
        cur.execute("""
            UPDATE boss
            SET status='ACTIVE', subscription_end_date=?
            WHERE boss_id=?
        """, (subscription_end.strftime("%Y-%m-%d %H:%M:%S"), boss_id))

    conn.commit()
    conn.close()
    flash("Boss status updated.", "success")
    return redirect(url_for("superadmin_dashboard"))
    
      
@app.route("/superadmin/logout")
def superadmin_logout():
    session.pop("superadmin_id", None)
    flash("Umetoka kwenye mfumo", "info")
    return redirect(url_for("superadmin_login"))    
    
                
# =============================
# AUTO-APPLY DECORATOR KWA ROUTES ZA BOSS
# =============================
from functools import wraps

# Hii function ita-apply decorator kwa routes zote zinazoanza na "boss_"
def apply_access_decorator(app, decorator):
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith("boss_"):
            view_func = app.view_functions[rule.endpoint]
            app.view_functions[rule.endpoint] = decorator(view_func)

# ⚠️ Hakikisha hii inaitwa BAADA ya routes zote ku-define
apply_access_decorator(app, check_access)


@app.route("/boss/signup", methods=["GET", "POST"])
def boss_signup():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        username = request.form.get("username")
        password = request.form.get("password")

        # 🆕 GET PHONE & EMAIL
        phone = request.form.get("phone")
        email = request.form.get("email")

        boss_id = "BOSS-" + str(uuid.uuid4())[:8]
        hashed_pw = generate_password_hash(password)

        now = datetime.now()

        signup_date = now.strftime("%Y-%m-%d %H:%M:%S")
        # ✅ Trial ya dakika 2 kwa testing
        trial_end_date = (now + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")

        # ✅ Status ya TRIAL
        status = "TRIAL"

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # 🆕 CHECK DUPLICATE EMAIL / PHONE
            cur.execute("SELECT * FROM boss WHERE email = ? OR phone = ?", (email, phone))
            existing = cur.fetchone()
            if existing:
                flash("Email au namba ya simu tayari imetumika.", "danger")
                return redirect(url_for("boss_signup"))

            cur.execute("""
                INSERT INTO boss (
                    boss_id, full_name, username, password,
                    signup_date, trial_end_date, status, is_online, created_at,
                    phone, email
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                boss_id, full_name, username, hashed_pw,
                signup_date, trial_end_date, status, 1, signup_date,  # ✅ is_online=1
                phone, email
            ))

            conn.commit()

            # 🔹 Initialize session (boss mpya ana online)
            session['just_signed_up'] = True
            session['boss_id'] = boss_id

            return redirect(url_for("boss_dashboard"))

        except sqlite3.IntegrityError:
            flash("Username tayari ipo.", "danger")

        finally:
            conn.close()

    return render_template("boss_signup.html")


@app.route("/boss/login", methods=["GET", "POST"])
def boss_login():
    """
    🔹 Boss Login Route
    Hii route inashughulikia:
    1️⃣ Login ya boss wa system
    2️⃣ Auto-check na update ya TRIAL na subscription expiry (soft restriction)
    3️⃣ Block account ikiwa imefungwa manually (INACTIVE)
    4️⃣ Handle RESET_PENDING temporary passwords
    5️⃣ Initialize session na announcements
    6️⃣ Update is_online status
    7️⃣ Provide user-friendly messages
    """
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # ===============================
        # 🔹 Database connection
        # ===============================
        conn = get_db_connection()
        cur = conn.cursor()

        # 🔹 Fetch boss by username
        cur.execute("SELECT * FROM boss WHERE username=?", (username,))
        boss = cur.fetchone()

        if not boss:
            conn.close()
            flash("Username au password sio sahihi. Jaribu tena.", "danger")
            return redirect(url_for("boss_login"))

        boss = dict(boss)
        now = datetime.now()

        # ===============================
        # 🔹 HANDLE RESET_PENDING STATUS
        # ===============================
        if boss["status"] == "RESET_PENDING":
            if check_password_hash(boss["password"], password):
                session.clear()
                session["boss_id"] = boss["boss_id"]
                conn.close()
                flash(
                    "Temporary password imethibitishwa. Tafadhali weka PIN mpya ili kuendelea.",
                    "warning"
                )
                return redirect(url_for("boss_set_new_pin"))
            else:
                conn.close()
                flash("Temporary password sio sahihi. Jaribu tena.", "danger")
                return redirect(url_for("boss_login"))

        # ===============================
        # 🔹 PASSWORD VALIDATION
        # ===============================
        if not check_password_hash(boss["password"], password):
            conn.close()
            flash("Username au password sio sahihi. Jaribu tena.", "danger")
            return redirect(url_for("boss_login"))

        # ===============================
        # 🔹 PARSE TRIAL & SUBSCRIPTION DATES SAFELY
        # ===============================
        trial_end = boss.get("trial_end_date")
        sub_end = boss.get("subscription_end_date")
        try:
            if trial_end and isinstance(trial_end, str):
                trial_end = datetime.strptime(trial_end, "%Y-%m-%d %H:%M:%S")
        except Exception:
            trial_end = None

        try:
            if sub_end and isinstance(sub_end, str):
                sub_end = datetime.strptime(sub_end, "%Y-%m-%d %H:%M:%S")
        except Exception:
            sub_end = None

        # ===============================
        # 🔹 SOFT RESTRICTION AFTER TRIAL OR SUBSCRIPTION EXPIRE
        # ===============================
        restricted = False  # temporary flag

        if boss["status"] == "TRIAL" and trial_end and now > trial_end:
            restricted = True
            boss["status"] = "TRIAL_EXPIRE"
            cur.execute(
                "UPDATE boss SET status=? WHERE boss_id=?",
                ("TRIAL_EXPIRE", boss["boss_id"])
            )
            conn.commit()
            flash(
                "⚠️ Trial imeisha: Huwezi kusoma meter au kupokea malipo. Unaweza kuendelea kuona dashboard.",
                "warning"
            )
        elif boss["status"] == "ACTIVE" and sub_end and now > sub_end:
            restricted = True
            boss["status"] = "SUBSCRIPTION_EXPIRE"
            cur.execute(
                "UPDATE boss SET status=? WHERE boss_id=?",
                ("SUBSCRIPTION_EXPIRE", boss["boss_id"])
            )
            conn.commit()
            flash(
                "⚠️ Subscription yako imeisha: Huwezi kusoma meter au kupokea malipo. Tafadhali wasiliana na Masoud (0745906763) ili kufanya malipo.",
                "warning"
            )

        # ===============================
        # 🔹 BLOCK LOGIN IF MANUALLY INACTIVE
        # ===============================
        if boss["status"] == "INACTIVE":
            cur.execute(
                "UPDATE boss SET is_online=0 WHERE boss_id=?",
                (boss["boss_id"],)
            )
            conn.commit()
            conn.close()
            flash(
                "Huduma zimesitishwa kwa sasa. Tafadhali wasiliana na support kwa msaada zaidi (ph. 0744906763).",
                "danger"
            )
            return redirect(url_for("boss_login"))

        # ===============================
        # 🔹 INITIALIZE SESSION
        # ===============================
        session.clear()
        session["boss_id"] = boss["boss_id"]
        session["boss_status"] = boss["status"]
        session["boss_name"] = boss["full_name"]
        session["restricted"] = restricted  # hii itabakia bila kufutwa

        # ===============================
        # 🔹 UPDATE ONLINE STATUS
        # ===============================
        if boss["status"] in ["TRIAL", "ACTIVE", "TRIAL_EXPIRE", "SUBSCRIPTION_EXPIRE"]:
            cur.execute("UPDATE boss SET is_online=1 WHERE boss_id=?", (boss["boss_id"],))
        else:
            cur.execute("UPDATE boss SET is_online=0 WHERE boss_id=?", (boss["boss_id"],))
        conn.commit()

        # ===============================
        # 🔹 FETCH LATEST ANNOUNCEMENT
        # ===============================
        cur.execute("""
            SELECT * FROM announcements
            ORDER BY created_at DESC
            LIMIT 1
        """)
        announcement = cur.fetchone()
        if announcement:
            session["announcement_title"] = announcement["title"]
            session["announcement_message"] = announcement["message"]
        else:
            session.pop("announcement_title", None)
            session.pop("announcement_message", None)

        conn.close()

        # ===============================
        # 🔹 SUCCESS MESSAGE BASED ON STATUS
        # ===============================
        if boss["status"] == "TRIAL":
            flash(
                "Karibu ! umeanza kutumia mfumo. Mara baada ya kutumia mfumo huu tafadhali tupatie maoni yako ili tuendelee kuboresha huduma zetu (ph.0744906763).",
                "info"
            )
        elif boss["status"] == "ACTIVE":
            flash(f"Karibu tena, {boss['full_name']}! Tuna furaha kukuona hapa.", "success")
        elif boss["status"] in ["TRIAL_EXPIRE", "SUBSCRIPTION_EXPIRE"]:
            flash(
                f"Karibu tena, {boss['full_name']}! Mfumo una restrictions kutokana na subscription. Hivyo kuna huduma kadhaa zimesitishwa  mpaka utakapo changia  kwa mawasiliano  piga : (0744906763 )  iliuweze kuchangia   ftom - Masoud.",
                "warning"
            )

        return redirect(url_for("boss_dashboard"))

    return render_template("boss_login.html")


    
    
@app.route("/boss/announcements")
def boss_announcements():
    if "boss_id" not in session:
        flash("Ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Pata signup_date sahihi ya boss
    cur.execute("SELECT signup_date FROM boss WHERE boss_id = ?", (boss_id,))
    boss = cur.fetchone()

    if not boss:
        flash("Boss hakupatikani", "danger")
        return redirect(url_for("boss_dashboard"))

    boss_signup_date = boss["signup_date"]

    # Ensure format ya datetime SQLite
    from datetime import datetime
    try:
        dt = datetime.strptime(boss_signup_date, "%Y-%m-%d %H:%M:%S")
        boss_signup_date = dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        # kama signup_date haiko sahihi, tumia datetime sasa
        boss_signup_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Chukua matangazo mapya tu baada ya signup ya boss
    cur.execute("""
        SELECT *
        FROM announcements
        WHERE datetime(created_at) >= datetime(?)
        ORDER BY created_at DESC
    """, (boss_signup_date,))

    announcements = cur.fetchall()
    conn.close()

    return render_template("boss_announcements.html", announcements=announcements)
    
    
    
# ==============================
# Route ya kulipa subscription ya boss
# ==============================


@app.route("/boss/set_new_pin", methods=["GET", "POST"])
def boss_set_new_pin():
    # 🔐 Hakikisha boss ameingia kwenye session, vinginevyo rudisha kwenye login
    if "boss_id" not in session:
        flash("Login kwanza.", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]

    # 📝 Angalia kama form imesubmit POST method
    if request.method == "POST":
        new_pin = request.form.get("new_pin")
        confirm_pin = request.form.get("confirm_pin")

        # ⚠️ Kagua kama zote PIN zimejazwa
        if not new_pin or not confirm_pin:
            flash("Tafadhali jaza PIN zote mbili.", "warning")
        # ⚠️ Kagua kama PIN mpya na uthibitisho wa PIN vinafanana
        elif new_pin != confirm_pin:
            flash("PIN mpya na uthibitisho havilingani.", "warning")
        else:
            # 🔒 Hash PIN mpya kwa usalama kabla ya kuweka database
            hashed = generate_password_hash(new_pin)

            # 🔌 Fungua connection ya database
            conn = get_db_connection()
            cur = conn.cursor()

            # 💾 Update password na status ya boss kuwa ACTIVE
            cur.execute(
                "UPDATE boss SET password=?, status='ACTIVE' WHERE boss_id=?", 
                (hashed, boss_id)
            )
            conn.commit()
            conn.close()

            # ✅ Onyesha message ya mafanikio na rudisha login
            flash("PIN mpya imewekwa kwa mafanikio. Unaweza ku-login sasa.", "success")
            return redirect(url_for("boss_login"))

    # 📄 Rudisha template ya ku-set PIN kama bado form haijasubmit
    return render_template("boss_set_new_pin.html")



from flask import render_template, session, redirect, url_for, flash
import sqlite3

@app.route("/boss_dashboard")
def boss_dashboard():
    import sqlite3
    from datetime import datetime, date

    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    boss = conn.execute("SELECT * FROM boss WHERE boss_id=?", (boss_id,)).fetchone()
    if not boss:
        conn.close()
        flash("Boss haipo kwenye systemu!", "danger")
        return redirect(url_for("boss_login"))

    today = date.today()
    trial_end_date = boss['trial_end_date']
    subscription_end_date = boss['subscription_end_date']

    def parse_date(dt_str):
        if not dt_str:
            return None
        try:
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            return datetime.strptime(dt_str, "%Y-%m-%d").date()

    trial_end = parse_date(trial_end_date)
    subscription_end = parse_date(subscription_end_date)

    on_trial = trial_end and trial_end >= today
    subscription_expired = not on_trial and (not subscription_end or subscription_end < today)

    boss_message = ""
    if on_trial:
        boss_message = "Umepata muda wa trial, tafadhali jaribu mfumo na tupe maoni yako."
    elif subscription_expired:
        boss_message = "Muda wako wa kutumia mfumo umeisha lakini bado unaweza kutumia mfumo."
    else:
        boss_message = "Subscription yako ni active, unaendelea kutumia huduma."

    show_welcome = False
    if session.get('just_signed_up'):
        show_welcome = True
        session.pop('just_signed_up', None)

    customers_raw = conn.execute("""
        SELECT * FROM customers 
        WHERE boss_id=? 
        ORDER BY full_name
    """, (boss_id,)).fetchall()

    meters_raw = conn.execute("""
        SELECT * FROM meters 
        WHERE customer_id IN (
            SELECT customer_id FROM customers WHERE boss_id=?
        )
    """, (boss_id,)).fetchall()

    unpaid_bills = conn.execute("""
        SELECT b.*, c.full_name AS customer_name, m.meter_number
        FROM bills b
        JOIN customers c ON b.customer_id = c.customer_id
        LEFT JOIN meters m ON b.meter_id = m.meter_id
        WHERE b.status='UNPAID' AND c.boss_id=?
        ORDER BY b.billing_month DESC
    """, (boss_id,)).fetchall()

    total_unpaid_amount = conn.execute("""
        SELECT SUM(b.amount) as total
        FROM bills b
        JOIN customers c ON b.customer_id = c.customer_id
        WHERE b.status='UNPAID' AND c.boss_id=?
    """, (boss_id,)).fetchone()['total'] or 0

    total_payments = conn.execute("""
        SELECT SUM(p.amount_paid) as total
        FROM payments p
        JOIN customers c ON p.customer_id = c.customer_id
        WHERE c.boss_id=?
    """, (boss_id,)).fetchone()['total'] or 0

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_total = conn.execute("""
        SELECT SUM(amount_paid) as total
        FROM payments
        WHERE boss_id=? AND DATE(paid_at)=?
    """, (boss_id, today_str)).fetchone()['total'] or 0

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

    # 🔥 NEW: Meter zilizosomwa leo
    meters_today = conn.execute("""
        SELECT COUNT(*) as total
        FROM meter_readings mr
        JOIN meters m ON mr.meter_id = m.meter_id
        JOIN customers c ON m.customer_id = c.customer_id
        WHERE mr.reading_date = ?
        AND c.boss_id = ?
    """, (today_str, boss_id)).fetchone()["total"] or 0

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
        c_dict['customer_status'] = c['status']
        customers.append(c_dict)

    active_meters = sum(
        1 for mlist in meters_map.values() for m in mlist if m['status'] == 'ACTIVE'
    )
    inactive_meters = sum(
        1 for mlist in meters_map.values() for m in mlist if m['status'] != 'ACTIVE'
    )

    recent_logs = conn.execute("""
        SELECT * FROM activity_logs
        WHERE boss_id=?
        ORDER BY time DESC
        LIMIT 5
    """, (boss_id,)).fetchall()

    announcements = conn.execute("""
        SELECT a.id, a.title, a.message, a.created_at,
               COALESCE(ar.is_read, 0) as is_read
        FROM announcements a
        LEFT JOIN announcement_reads ar
            ON a.id = ar.announcement_id
            AND ar.boss_id = ?
        WHERE ar.announcement_id IS NULL
        ORDER BY a.created_at DESC
    """, (boss_id,)).fetchall()

    show_announcement = None
    for ann in announcements:
        if ann['is_read'] == 0 or ann['is_read'] is None:
            show_announcement = ann
            conn.execute("""
                INSERT OR REPLACE INTO announcement_reads (boss_id, announcement_id, is_read)
                VALUES (?, ?, 1)
            """, (boss_id, ann['id']))
            conn.commit()
            break

    conn.close()

    return render_template(
        "boss_dashboard.html",
        boss=boss,
        customers=customers,
        active_meters=active_meters,
        inactive_meters=inactive_meters,
        unpaid_bills=unpaid_bills,
        total_unpaid_amount=total_unpaid_amount,
        total_payments=total_payments,
        today_total=today_total,
        skipped_meters=skipped_meters,
        recent_logs=recent_logs,
        show_welcome=show_welcome,
        announcement=show_announcement,
        boss_message=boss_message,
        meters_today=meters_today  # 🔥 NEW VARIABLE
    )


from werkzeug.security import generate_password_hash

@app.route("/boss/settings", methods=["GET", "POST"])
def boss_settings():
    if "boss_id" not in session:
        return redirect(url_for("boss_login"))

    if request.method == "POST":
        new_password = request.form.get("new_password")
        if new_password:
            new_password = new_password.strip()  # Ondoa spaces zisizo lazima

            # Hash password compatible na check_password_hash
            hashed = generate_password_hash(new_password)

            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE boss 
                SET password = ? 
                WHERE boss_id = ?
            """, (hashed, session["boss_id"]))
            conn.commit()
            conn.close()

            flash("Password updated successfully!", "success")

    return render_template("boss_settings.html")


@app.route("/boss/activity_logs")
def boss_activity_logs():

    # Hakikisha boss amelogin
    if "boss_id" not in session:
        flash("Tafadhali login kwanza", "danger")
        return redirect(url_for("login"))

    conn = sqlite3.connect("water_supply.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 🔥 Chukua taarifa za boss
    cursor.execute("SELECT * FROM boss WHERE id = ?", (session["boss_id"],))
    boss = cursor.fetchone()

    # Chukua logs zote
    cursor.execute("""
        SELECT * FROM activity_logs
        ORDER BY time DESC
    """)
    logs = cursor.fetchall()

    conn.close()

    # 🔥 Tuma boss + logs
    return render_template(
        "boss_activity_logs.html",
        logs=logs,
        boss=boss
    )
    

@app.route("/boss/activity_logs/filter", methods=["GET", "POST"])
def boss_activity_logs_filter():

    # 🔐 Hakikisha boss ame-login
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    # 📌 Chukua boss_id kutoka session
    boss_id = session["boss_id"]

    # 🔌 Fungua connection ya database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 📦 Variable ya kuhifadhi logs zitakazopatikana
    logs = []

    # -------------------------------
    # 📥 Ikiwa form ime-submit (POST request)
    # -------------------------------
    if request.method == "POST":
        # 📅 Pokea mwezi na mwaka kutoka form
        month = request.form.get("month")  # format: "03"
        year  = request.form.get("year")   # format: "2026"

        if month and year:
            # 🔍 Filter activity logs kwa boss, mwaka, mwezi
            logs = cursor.execute("""
                SELECT * FROM activity_logs
                WHERE boss_id = ?
                  AND strftime('%Y', time) = ?
                  AND strftime('%m', time) = ?
                ORDER BY time DESC
            """, (
                boss_id,
                year,
                month.zfill(2)
            )).fetchall()
        else:
            flash("Chagua mwezi na mwaka sahihi", "danger")

    # 🔥 Chukua taarifa za boss (fix: tumia boss_id, sio id)
    cursor.execute("SELECT * FROM boss WHERE boss_id = ?", (boss_id,))
    boss = cursor.fetchone()

    # 🔒 Funga connection ya database
    conn.close()

    # -------------------------------
    # 🎨 Rudisha template pamoja na data ya logs na boss
    # -------------------------------
    return render_template(
        "boss_activity_logs.html",
        logs=logs,
        boss=boss   # ✅ sasa template itapata boss.full_name
    )



@app.route("/boss/logout")
def boss_logout():
    boss_id = session.get("boss_id")  # pata boss_id ya aliye login

    if boss_id:
        conn = get_db_connection()
        cur = conn.cursor()
        # 🔹 UPDATE ONLINE STATUS
        cur.execute("UPDATE boss SET is_online = 0 WHERE boss_id = ?", (boss_id,))
        conn.commit()
        cur.close()
        conn.close()

    # 🔐 Ondoa boss_id kwenye session (kumtoa user kwenye mfumo)
    session.pop("boss_id", None)

    # 📢 Toa ujumbe wa mafanikio baada ya logout
    flash("Umetoka kwenye dashboard ya boss", "success")

    # 🔁 Mpeleke user kwenye ukurasa wa login
    return redirect(url_for("boss_login"))


# ================= CUSTOMER MANAGEMENT ==================

@app.route("/boss/add_customer", methods=["GET", "POST"])
def add_customer():
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    if request.method == "POST":
        # Trim all inputs to avoid spaces issues
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        area = request.form.get("area", "").strip()
        house_number = request.form.get("house_number", "").strip()
        meter_number = request.form.get("meter_number", "").strip()

        # Validation
        if not full_name or not meter_number:
            flash("Jina kamili na meter number ni lazima!", "danger")
            return redirect(url_for("add_customer"))

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # Check if meter exists
            cur.execute("SELECT * FROM meters WHERE meter_number = ?", (meter_number,))
            existing_meter = cur.fetchone()
            if existing_meter:
                flash(f"⚠️ Meter {meter_number} tayari ipo kwenye mfumo.", "warning")
                return redirect(url_for("add_customer"))

            # Check if customer exists
            cur.execute(
                "SELECT * FROM customers WHERE full_name=? AND phone=? AND boss_id=?",
                (full_name, phone, session["boss_id"])
            )
            existing_customer = cur.fetchone()

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status = "ACTIVE"

            if existing_customer:
                customer_id = existing_customer["customer_id"]
                flash(f"ℹ️ Mteja {full_name} tayari yupo. Tena tunaongeza meter.", "info")
            else:
                # Insert new customer
                customer_id = "CUST-" + str(uuid.uuid4())[:8]
                cur.execute("""
                    INSERT INTO customers 
                    (customer_id, boss_id, full_name, phone, area, house_number, status, created_at, signup_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (customer_id, session["boss_id"], full_name, phone, area, house_number, status, now, now))
                flash(f"✅ Mteja {full_name} amesajiliwa kikamilifu!", "success")

            # Insert meter with created_at timestamp
            meter_id = "MTR-" + str(uuid.uuid4())[:8]
            cur.execute("""
                INSERT INTO meters (meter_id, meter_number, customer_id, status, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (meter_id, meter_number, customer_id, status, now))

            conn.commit()
            flash(f"✅ Meter {meter_number} imeongezwa kwa {full_name}", "success")

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

    boss_id = session["boss_id"]

    conn = get_db_connection()
    cur = conn.cursor()

    # ✅ Hakikisha customer ni wa boss huyu
    cur.execute("""
        SELECT * FROM customers 
        WHERE customer_id=? AND boss_id=?
    """, (customer_id, boss_id))
    customer = cur.fetchone()

    if not customer:
        flash("Mteja haipo au sio wako", "danger")
        conn.close()
        return redirect(url_for("boss_dashboard"))

    # ✅ Pata meter ya huyu customer
    cur.execute("""
        SELECT * FROM meters WHERE customer_id=?
    """, (customer_id,))
    meter = cur.fetchone()

    if request.method == "POST":
        full_name = request.form.get("full_name")
        meter_number = request.form.get("meter_number")

        if not full_name:
            flash("Jaza jina la mteja", "danger")
            return redirect(url_for("edit_customer", customer_id=customer_id))

        try:
            # ✅ Update jina tu
            cur.execute("""
                UPDATE customers 
                SET full_name=? 
                WHERE customer_id=? AND boss_id=?
            """, (full_name, customer_id, boss_id))

            # ✅ Kama meter ipo na imebadilishwa
            if meter and meter_number and meter_number != meter["meter_number"]:

                # 🔍 Check duplicate
                cur.execute("""
                    SELECT meter_id FROM meters 
                    WHERE meter_number=? AND meter_id != ?
                """, (meter_number, meter["meter_id"]))

                existing = cur.fetchone()

                if existing:
                    flash("Meter number tayari ipo!", "danger")
                    conn.close()
                    return redirect(url_for("edit_customer", customer_id=customer_id))

                # ✅ Update meter
                cur.execute("""
                    UPDATE meters 
                    SET meter_number=? 
                    WHERE meter_id=?
                """, (meter_number, meter["meter_id"]))

            conn.commit()
            flash(f"Mteja {full_name} amesasishwa!", "success")

        except sqlite3.Error as e:
            flash(f"Kosa la database: {e}", "danger")

        finally:
            conn.close()

        return redirect(url_for("boss_dashboard"))

    conn.close()
    return render_template("edit_customer.html", customer=customer, meter=meter)





@app.route("/boss/deactivate_customer/<customer_id>")
def deactivate_customer(customer_id):

    # 🔐 Hakikisha boss ame-login kabla ya kufanya action yoyote
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    # 🔌 Fungua connection ya database
    conn = get_db_connection()
    cur = conn.cursor()

    # 🔍 Hakikisha mteja anayehitajika yupo kwenye database
    cur.execute(
        "SELECT * FROM customers WHERE customer_id=?", 
        (customer_id,)
    )
    customer = cur.fetchone()

    # ❌ Kama mteja hayupo → rudisha error
    if not customer:
        flash("Mteja hayupo", "danger")
        conn.close()
        return redirect(url_for("boss_dashboard"))

    try:
        # 🔒 Badilisha status ya mteja kuwa INACTIVE (kumfungia huduma)
        cur.execute(
            "UPDATE customers SET status='INACTIVE' WHERE customer_id=?", 
            (customer_id,)
        )

        # 💾 Hifadhi mabadiliko kwenye database
        conn.commit()

        # ✅ Ujumbe wa mafanikio
        flash(f"Mteja {customer['full_name']} amefungwa!", "success")

    except sqlite3.Error as e:
        # ⚠️ Kama kuna kosa la database
        flash(f"Kosa la database: {e}", "danger")

    finally:
        # 🔒 Hakikisha connection inafungwa kila wakati
        conn.close()

    # 🔁 Rudisha boss kwenye dashboard
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
@check_access
def read_meter():
    if "staff_id" not in session and "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("staff_login"))

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
    bill = None

    if request.method == "POST":
        meter_number = request.form.get("meter_number")
        current_reading = request.form.get("current_reading")

        if not meter_number or not current_reading:
            flash("Tafadhali jaza meter number na reading", "danger")
            return render_template("read_meter.html", bill=None)

        if not re.match(r'^[0-9]+(\.[0-9]+)?$', current_reading):
            flash("⚠️ Reading lazima iwe namba halisi positive", "danger")
            return render_template("read_meter.html", bill=None)

        current_reading = float(current_reading)
        if current_reading < 0 or current_reading > 100000:
            flash("⚠️ Reading iko nje ya range sahihi", "danger")
            return render_template("read_meter.html", bill=None)

        cur.execute("""
            SELECT m.meter_id, m.customer_id, m.status AS meter_status,
                   c.full_name, c.status AS customer_status
            FROM meters m
            JOIN customers c ON m.customer_id = c.customer_id
            WHERE m.meter_number=? AND c.boss_id=?
        """, (meter_number, boss_id))
        meter = cur.fetchone()
        if not meter:
            flash("Meter hii haipo au sio ya wateja wako", "danger")
            conn.close()
            return render_template("read_meter.html", bill=None)

        if meter["customer_status"] != "ACTIVE":
            flash(f"⚠️ Hauwezi kusoma meter ya mteja {meter['full_name']} kwa sababu status yake ni {meter['customer_status']}.", "warning")
            conn.close()
            return render_template("read_meter.html", bill=None)

        if meter["meter_status"] != "ACTIVE":
            flash("⚠️ Meter hii imezimwa (INACTIVE)", "warning")
            conn.close()
            return render_template("read_meter.html", bill=None)

        billing_month = datetime.now().strftime("%Y-%m")

        cur.execute("""
            SELECT current_reading, billing_month FROM bills
            WHERE meter_id=?
            ORDER BY created_at DESC
            LIMIT 1
        """, (meter["meter_id"],))
        last_bill = cur.fetchone()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 🔥 NEW: tarehe ya leo kwa meter_readings
        today = datetime.now().strftime("%Y-%m-%d")

        # 🔥 NEW: Zuia duplicate reading kwa siku moja
        cur.execute("""
            SELECT 1 FROM meter_readings
            WHERE meter_id=? AND reading_date=?
        """, (meter["meter_id"], today))
        already_read = cur.fetchone()

        if already_read:
            flash("⚠️ Meter hii tayari imeshasomwa leo.", "warning")
            conn.close()
            return render_template("read_meter.html", bill=None)

        if not last_bill:
            cur.execute("""
                INSERT INTO bills
                (bill_id, customer_id, meter_id, previous_reading, current_reading, units_used,
                 amount, billing_month, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "BILL-" + str(uuid.uuid4())[:8],
                meter["customer_id"],
                meter["meter_id"],
                0, current_reading, 0, 0,
                billing_month, 'BASELINE', now
            ))

            # 🔥 NEW: Save kwenye meter_readings
            cur.execute("""
                INSERT INTO meter_readings
                (reading_id, meter_id, reading_value, reading_date, recorded_by)
                VALUES (?, ?, ?, ?, ?)
            """, (
                "READ-" + str(uuid.uuid4())[:8],
                meter["meter_id"],
                current_reading,
                today,
                user_id
            ))

            conn.commit()
            flash(f"✅ Reading imehifadhiwa kama baseline. Bill bado haijajengwa.", "success")
            conn.close()
            return render_template("read_meter.html", bill=None)

        previous_reading = last_bill["current_reading"]
        last_billing_month = last_bill["billing_month"]

        # 🔥 NEW: Check kama reading haijabadilika
        if previous_reading is not None and current_reading == previous_reading:
            flash("⚠️ Hakuna matumizi (reading haijabadilika)", "info")
            conn.close()
            return render_template("read_meter.html", bill=None)

        if last_billing_month == billing_month:
            flash(f"⚠️ Tafadhari meter hii tayari imesha somwa mwezi huu.", "info")
            conn.close()
            return render_template("read_meter.html", bill=None)

        units_used = current_reading - previous_reading
        if units_used < 0:
            flash("⚠️ Reading mpya haiwezi kuwa ndogo kuliko ya mwisho", "danger")
            conn.close()
            return render_template("read_meter.html", bill=None)

        cur.execute("""
            SELECT price_per_unit FROM tariffs
            WHERE boss_id=? ORDER BY created_at DESC LIMIT 1
        """, (boss_id,))
        tariff = cur.fetchone()
        if not tariff:
            flash("⚠️ Hakuna tariff iliyowekwa. Tafadhali weka price per unit kwanza.", "danger")
            conn.close()
            return render_template("read_meter.html", bill=None)

        amount = units_used * tariff["price_per_unit"]
        bill_id = "BILL-" + str(uuid.uuid4())[:8]

        cur.execute("""
            INSERT INTO bills
            (bill_id, customer_id, meter_id, previous_reading, current_reading,
             units_used, amount, billing_month, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (bill_id, meter["customer_id"], meter["meter_id"],
              previous_reading, current_reading, units_used, amount,
              billing_month, 'UNPAID', now))

        # 🔥 NEW: Save kwenye meter_readings
        cur.execute("""
            INSERT INTO meter_readings
            (reading_id, meter_id, reading_value, reading_date, recorded_by)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "READ-" + str(uuid.uuid4())[:8],
            meter["meter_id"],
            current_reading,
            today,
            user_id
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

    # 🔐 AUTHENTICATION CHECK
    # Hakikisha boss ame-login kabla ya ku-access route hii
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    # 📌 Chukua boss_id kutoka session (hutumika kwenye queries zote)
    boss_id = session["boss_id"]

    # 🔌 Fungua database connection
    conn = get_db_connection()
    cur = conn.cursor()

    # ============================================================
    # 📥 POST REQUEST → CREATE / UPDATE TARIFF
    # ============================================================
    if request.method == "POST":

        # 📊 Pokea thamani ya price_per_unit kutoka form
        price_per_unit = request.form.get("price_per_unit")

        # ⚠️ Validation: Hakikisha value ipo
        if not price_per_unit:
            flash("Tafadhali weka bei ya unit", "danger")
            return redirect(url_for("boss_tariff"))

        try:
            # 🔢 Convert input kuwa float (inahakikisha ni namba sahihi)
            price_per_unit = float(price_per_unit)

            # 🆔 Generate unique tariff_id
            tariff_id = "TARIFF-" + uuid.uuid4().hex[:8]

            # 🕒 Weka timestamp ya creation
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 💾 Hifadhi tariff mpya kwenye database
            cur.execute("""
                INSERT INTO tariffs (tariff_id, boss_id, price_per_unit, created_at)
                VALUES (?, ?, ?, ?)
            """, (tariff_id, boss_id, price_per_unit, now))

            # ✅ Commit mabadiliko
            conn.commit()

            # 📢 Feedback ya mafanikio
            flash(f"Bei imehifadhiwa: {price_per_unit} Tsh/unit", "success")

        except ValueError:
            # ❌ Error: input sio namba sahihi
            flash("Bei ya unit lazima iwe namba sahihi", "danger")

        except sqlite3.Error as e:
            # ❌ Error ya database
            flash(f"Kosa la database: {e}", "danger")

        # 🔁 Redirect ili kuzuia form resubmission (PRG pattern)
        return redirect(url_for("boss_tariff"))

    # ============================================================
    # 📤 GET REQUEST → FETCH LATEST TARIFF
    # ============================================================

    # 🔍 Chukua tariff ya mwisho (latest) ya boss
    cur.execute("""
        SELECT * FROM tariffs 
        WHERE boss_id=? 
        ORDER BY created_at DESC 
        LIMIT 1
    """, (boss_id,))

    tariff = cur.fetchone()

    # 🔒 Funga database connection
    conn.close()

    # 🎨 Render template pamoja na data ya tariff
    return render_template(
        "boss_tariff.html",
        tariff=tariff
    )
    
    
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
    Kila bill ina meter yake halisi na namba ya simu ya mteja.
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
                   c.phone AS customer_phone,
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
                   c.phone AS customer_phone,
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

    # 🔐 AUTHENTICATION CHECK
    # Hakikisha boss ame-login kabla ya ku-access route hii
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    # 📌 Chukua boss_id kutoka session (hutumika kufilter data zake tu)
    boss_id = session["boss_id"]

    # 🔌 Fungua database connection
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row  # Inaruhusu kutumia columns kama dict (mf. row['full_name'])

    # ============================================================
    # 📊 FETCH CUSTOMERS + METERS (AGGREGATED VIEW)
    # ============================================================
    # Lengo:
    # - Kupata kila customer wa boss
    # - Kuunganisha meters zote za customer mmoja kuwa row moja
    # - Kutumia GROUP_CONCAT ili ku-display meters nyingi kwenye column moja
    customers = conn.execute("""
        SELECT 
            c.customer_id, 
            c.full_name AS customer_name,
            c.phone, 
            c.area, 
            c.house_number,
            c.status AS customer_status,

            -- 🔢 Unganisha meter numbers zote za customer mmoja (comma separated)
            GROUP_CONCAT(m.meter_number) AS meters,

            -- 📡 Unganisha status za meters (ACTIVE/INACTIVE n.k.)
            GROUP_CONCAT(m.status) AS meter_statuses

        FROM customers c

        -- 🔗 Left join ili hata customer asiye na meter aonekane
        LEFT JOIN meters m 
            ON c.customer_id = m.customer_id

        -- 🔒 Hakikisha tunaonyesha customers wa boss husika tu
        WHERE c.boss_id = ?

        -- 📌 Group kwa customer ili kupata row moja kwa kila customer
        GROUP BY c.customer_id

        -- 🔤 Panga kwa jina (A-Z)
        ORDER BY c.full_name
    """, (boss_id,)).fetchall()

    # 🔒 Funga database connection
    conn.close()

    # 🎨 Render template pamoja na data ya customers
    return render_template(
        "boss_customers.html",
        customers=customers
    )


    
@app.route("/boss/toggle_meter/<meter_number>")
def toggle_meter(meter_number):
    
    # 🔐 AUTHENTICATION CHECK
    # Hakikisha boss ame-login kabla ya kufanya action yoyote
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    # 📌 Chukua boss_id kutoka session (ili ku-verify ownership)
    boss_id = session["boss_id"]

    # 🔌 Fungua database connection
    conn = get_db_connection()
    cur = conn.cursor()

    # ============================================================
    # 🔍 VERIFY METER BELONGS TO BOSS
    # ============================================================
    # Lengo:
    # 1️⃣ Hakikisha meter ipo kwenye database
    # 2️⃣ Hakikisha meter inahusiana na mteja wa boss huyu
    cur.execute("""
        SELECT m.status 
        FROM meters m
        JOIN customers c ON m.customer_id = c.customer_id
        WHERE m.meter_number = ? AND c.boss_id = ?
    """, (meter_number, boss_id))

    meter = cur.fetchone()

    # ❌ Kama meter haipo au sio ya account ya boss huyu → rudisha error
    if not meter:
        flash("Meter haipatikani au sio ya mteja wako", "danger")
        conn.close()
        return redirect(url_for("boss_view_customers"))

    # ============================================================
    # 🔄 TOGGLE METER STATUS
    # ============================================================
    # Logic:
    # - Kama status ni ACTIVE → set kuwa INACTIVE
    # - Kama status ni INACTIVE → set kuwa ACTIVE
    new_status = "INACTIVE" if meter["status"] == "ACTIVE" else "ACTIVE"

    # 💾 Update database
    cur.execute("""
        UPDATE meters
        SET status = ?
        WHERE meter_number = ?
    """, (new_status, meter_number))

    # ✅ Commit mabadiliko
    conn.commit()

    # 🔒 Funga connection ya database
    conn.close()

    # 📢 Feedback message kwa boss
    flash(f"Meter {meter_number} imebadilishwa kuwa {new_status}", "success")

    # 🔁 Rudisha boss kwenye customers view
    return redirect(url_for("boss_view_customers"))



    
@app.route("/boss/toggle_customer/<customer_id>")
def toggle_customer(customer_id):

    # ============================================================
    # 1️⃣ AUTHENTICATION CHECK
    # ============================================================
    # Hakikisha boss ame-login kabla ya kufanya action yoyote
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    # 📌 Chukua boss_id kutoka session (hutumika kufilter customer)
    boss_id = session["boss_id"]

    # 🔌 Fungua connection ya database
    conn = get_db_connection()
    cur = conn.cursor()

    # ============================================================
    # 2️⃣ VERIFY CUSTOMER BELONGS TO THIS BOSS
    # ============================================================
    # Lengo:
    # - Hakikisha customer ipo kwenye database
    # - Hakikisha customer anahusiana na boss huyu
    cur.execute("""
        SELECT status 
        FROM customers
        WHERE customer_id = ? AND boss_id = ?
    """, (customer_id, boss_id))

    customer = cur.fetchone()

    # ❌ Kama customer haipo au sio wa boss huyu → rudisha error
    if not customer:
        flash("Mteja hapatikani au sio wa account yako", "danger")
        conn.close()
        return redirect(url_for("boss_view_customers"))

    # ============================================================
    # 3️⃣ TOGGLE CUSTOMER STATUS
    # ============================================================
    # Logic:
    # - Kama status ni ACTIVE → set kuwa INACTIVE
    # - Kama status ni INACTIVE → set kuwa ACTIVE
    if customer["status"] == "ACTIVE":
        new_status = "INACTIVE"
    else:
        new_status = "ACTIVE"

    # 💾 Update database
    cur.execute("""
        UPDATE customers
        SET status = ?
        WHERE customer_id = ?
    """, (new_status, customer_id))

    # ✅ Commit changes
    conn.commit()

    # 🔒 Funga connection ya database
    conn.close()

    # 📢 Feedback kwa boss
    flash("Status ya mteja imebadilishwa kikamilifu", "success")

    # 🔁 Rudisha boss kwenye view ya customers
    return redirect(url_for("boss_view_customers"))
    
    
# ================= RECEIVE PAYMENT =====================
@app.route("/receive_payment/<bill_id>", methods=["GET", "POST"])
@check_access  # 🔹 apply check_access decorator
def receive_payment(bill_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 🔹 Amua role na boss
    if "staff_id" in session:
        user_role = "staff"
        user_id = session["staff_id"]
        dashboard_route = "staff_dashboard"
        user_name = session.get("staff_name")
        boss_id_for_record = session.get("staff_boss_id")
    else:
        user_role = "boss"
        user_id = session["boss_id"]
        dashboard_route = "boss_dashboard"
        user_name = session.get("boss_name")
        boss_id_for_record = user_id

    # 🔹 Kagua status ya boss (dynamic, lakini decorator pia imehakikisha)
    boss_status = cursor.execute(
        "SELECT status FROM boss WHERE boss_id=?", 
        (boss_id_for_record,)
    ).fetchone()
    if not boss_status:
        conn.close()
        flash("Boss haipo kwenye mfumo", "danger")
        return redirect(url_for(dashboard_route))

    # 🔹 Pata bill info
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
        return redirect(url_for(dashboard_route))

    # 🔹 POST: process payment
    if request.method == "POST":
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payment_id = "PAY-" + uuid.uuid4().hex[:8]
        receipt_id = "RCPID-" + uuid.uuid4().hex[:8]
        year = datetime.now().year
        count = cursor.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] + 1
        receipt_number = f"RCP-{year}-{str(count).zfill(5)}"

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

        # ✅ Record activity log
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

    # 🔹 GET: show confirmation page
    conn.close()
    return render_template("confirm_payment.html", bill=bill, dashboard_route=dashboard_route)


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

    # ============================================================
    # 1️⃣ AUTHENTICATION CHECK
    # ============================================================
    # Hakikisha boss ame-login kabla ya ku-access route hii
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    # 📌 Chukua boss_id kutoka session (inatumika kufilter data za staff)
    boss_id = session["boss_id"]

    # ============================================================
    # 2️⃣ HANDLE POST REQUEST → CREATE NEW STAFF
    # ============================================================
    if request.method == "POST":

        # 📝 Pokea input kutoka form
        full_name = request.form.get("full_name")
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")  # backend-friendly value (mf. admin, cashier)

        # ⚠️ Validation: Hakikisha zote zimejazwa
        if not full_name or not username or not password or not role:
            flash("Tafadhali jaza majina yote, username, password na jukumu", "danger")
            return redirect(url_for("add_staff"))

        # 🔒 Hash password kabla ya ku-store (security best practice)
        hashed_pw = generate_password_hash(password)

        # 🆔 Generate unique staff_id
        staff_id = generate_staff_id()

        # 🕒 Weka timestamp ya creation
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 🔧 Set initial status
        status = "ACTIVE"

        # 🔌 Fungua database connection
        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # 💾 Insert staff mpya kwenye database
            cur.execute("""
                INSERT INTO staff (
                    staff_id, boss_id, full_name, username, password, role, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (staff_id, boss_id, full_name, username, hashed_pw, role, status, now))

            # ✅ Commit changes
            conn.commit()

            # 📢 Feedback ya mafanikio kwa boss
            flash(f"Staff {full_name} ameundwa kikamilifu na role '{role}'", "success")

        except sqlite3.IntegrityError:
            # ❌ Error: username tayari ipo kwenye system
            flash("Username tayari ipo kwenye mfumo.", "danger")

        finally:
            # 🔒 Funga connection kila hali
            conn.close()

        # 🔁 Redirect → Rudisha boss kwenye staff view page
        return redirect(url_for("view_staff"))

    # ============================================================
    # 3️⃣ HANDLE GET REQUEST → DISPLAY FORM
    # ============================================================
    return render_template("add_staff.html")              
                      

                          
# ============================================================
# Route: View Staff
# ============================================================
# 🔹 Lengo: Orodhesha staff wote waliopo chini ya boss aliyelogin
# 🔹 Method: GET (ina-display data tu)
# 🔹 Template: view_staff.html
# ============================================================

@app.route("/boss/view_staff")
def view_staff():

    # ============================================================
    # 1️⃣ AUTHENTICATION CHECK
    # ============================================================
    # Hakikisha boss ame-login kabla ya ku-access route hii
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    # 📌 Chukua boss_id kutoka session (ina filter staff wa boss huyu tu)
    boss_id = session["boss_id"]

    # ============================================================
    # 2️⃣ DATABASE QUERY → Pata list ya staff
    # ============================================================
    conn = get_db_connection()
    cur = conn.cursor()

    # 🔍 Chukua staff wote waliopo kwa boss huyu
    cur.execute("SELECT * FROM staff WHERE boss_id=?", (boss_id,))
    staff_list = cur.fetchall()

    # 🔒 Funga connection ya database
    conn.close()

    # ============================================================
    # 3️⃣ RENDER TEMPLATE
    # ============================================================
    # Variable `staff_members` inatumika kwenye template
    # ili ku-display table au list ya staff
    return render_template(
        "view_staff.html",
        staff_members=staff_list
    )



# ==================== RESET STAFF PASSWORD ====================
@app.route("/boss/reset_staff_password/<staff_id>", methods=["POST"])
def boss_reset_staff_password(staff_id):
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    conn = get_db_connection()
    cur = conn.cursor()

    # Hakikisha staff ni chini ya boss huyu
    cur.execute("SELECT * FROM staff WHERE staff_id=? AND boss_id=?", (staff_id, session["boss_id"]))
    staff = cur.fetchone()
    if not staff:
        conn.close()
        flash("Staff haipo au haiko chini yako.", "danger")
        return redirect(url_for("view_staff"))

    # Static temporary password
    temp_password = "reset123"
    from werkzeug.security import generate_password_hash
    hashed_password = generate_password_hash(temp_password)

    # Update password + set reset_required flag
    cur.execute("UPDATE staff SET password=?, reset_required=1 WHERE staff_id=?", (hashed_password, staff_id))
    conn.commit()
    conn.close()

    flash(f"Password ya {staff['full_name']} ime-reset. Temporary password: {temp_password}", "success")
    return redirect(url_for("view_staff"))



@app.route("/staff/set_new_password", methods=["GET", "POST"])
def staff_set_new_password():
    if "staff_id" not in session:
        return redirect(url_for("staff_login"))

    if request.method == "POST":
        new_password = request.form.get("new_password")
        if new_password:
            from werkzeug.security import generate_password_hash
            hashed = generate_password_hash(new_password)

            conn = get_db_connection()
            cur = conn.cursor()
            # Update password na reset_required=0
            cur.execute("UPDATE staff SET password=?, reset_required=0 WHERE staff_id=?", (hashed, session["staff_id"]))
            conn.commit()
            conn.close()

            flash("Password imebadilishwa kwa mafanikio! Sasa unaweza kuingia kwenye dashboard.", "success")
            return redirect(url_for("staff_dashboard"))

    return render_template("staff_set_new_password.html")


    
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
from flask import session, redirect, url_for, flash, render_template, request
from werkzeug.security import check_password_hash
from sqlite3 import Row

@app.route("/staff/login", methods=["GET", "POST"])
def staff_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection()
        conn.row_factory = Row  # access by column name

        staff = conn.execute("SELECT * FROM staff WHERE username=?", (username,)).fetchone()

        if staff and check_password_hash(staff["password"], password):
            # Check staff status
            if staff["status"] != "ACTIVE":
                flash("Account yako imefungwa. Wasiliana na boss wako.", "danger")
                conn.close()
                return redirect(url_for("staff_login"))

            # Check boss status
            boss = conn.execute("SELECT status FROM boss WHERE boss_id=?", (staff["boss_id"],)).fetchone()
            if not boss or boss["status"] != "ACTIVE":
                flash("Boss wako si ACTIVE. Huwezi kuendelea. Wasiliana na boss wako.", "danger")
                conn.close()
                return redirect(url_for("staff_login"))

            # Clear session
            session.clear()

            # Set session
            session["staff_id"] = staff["staff_id"]
            session["staff_name"] = staff["full_name"]
            session["staff_role"] = staff["role"].lower()
            session["staff_boss_id"] = staff["boss_id"]

            # 🔹 Force password change if reset_required
            if staff["reset_required"] == 1:
                flash("Password ime-reset na boss. Tafadhali weka password mpya ili kuendelea.", "warning")
                conn.close()
                return redirect(url_for("staff_set_new_password"))

            flash(f"Karibu {staff['full_name']}!", "success")
            conn.close()
            return redirect(url_for("staff_dashboard"))

        flash("Username au password sio sahihi.", "danger")
        conn.close()
        return redirect(url_for("staff_login"))

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
    


# ============================================================
# Route: Boss Monthly Report
# ============================================================


@app.route("/boss/monthly_report")
def boss_monthly_report():
    # ----------------------------------------
    # Authentication check
    # ----------------------------------------
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]
    month = request.args.get("month")  # format YYYY-MM
    if not month:
        flash("Chagua mwezi!", "warning")
        return redirect(url_for("boss_dashboard"))

    # ----------------------------------------
    # Database connection
    # ----------------------------------------
    conn = get_db_connection()
    cur = conn.cursor()

    # ----------------------------------------
    # Fetch monthly bills (join customers)
    # ----------------------------------------
    cur.execute("""
        SELECT 
            b.bill_id,
            b.customer_id,
            c.full_name AS customer_name,
            b.meter_id,
            b.units_used,
            b.amount,
            b.status,
            b.created_at,
            b.payment_method,
            b.payment_date
        FROM bills b
        JOIN customers c ON b.customer_id = c.customer_id
        WHERE c.boss_id = ? 
          AND b.billing_month = ?
        ORDER BY b.bill_id DESC
    """, (boss_id, month))

    bills = cur.fetchall()

    # ----------------------------------------
    # Aggregation & stats
    # ----------------------------------------
    total_units = sum(b["units_used"] for b in bills)
    total_amount = sum(b["amount"] for b in bills)
    paid_count = sum(1 for b in bills if b["status"].upper() == "PAID")
    unpaid_count = sum(1 for b in bills if b["status"].upper() == "UNPAID")
    total_paid_units = sum(b["units_used"] for b in bills if b["status"].upper() == "PAID")
    total_paid_amount = sum(b["amount"] for b in bills if b["status"].upper() == "PAID")

    # Count new meters (status NEW / BASELINE) if needed
    new_count = sum(1 for b in bills if b["status"].upper() == "BASELINE")

    conn.close()

    # ----------------------------------------
    # Render template
    # ----------------------------------------
    return render_template(
        "boss_monthly_report.html",
        bills=bills,
        month=month,
        total_units=total_units,
        total_amount=total_amount,
        paid_count=paid_count,
        unpaid_count=unpaid_count,
        total_paid_units=total_paid_units,
        total_paid_amount=total_paid_amount,
        new_count=new_count
    )
            
# ============================================================
# Route: Search Customer (Boss Only)
# ============================================================
@app.route("/search_customer", methods=["GET","POST"])
def search_customer():

    # ------------------------------------------------
    # HANDLE POST REQUEST (SEARCH ACTION)
    # ------------------------------------------------
    # POST hutokea pale boss anapowasilisha form ya kutafuta mteja
    if request.method == "POST":

        # Chukua jina la mteja kutoka kwenye form
        # strip() inaondoa nafasi zisizo za lazima (leading/trailing spaces)
        name = request.form.get("customer_name", "").strip()

        # ----------------------------------------
        # INPUT VALIDATION
        # ----------------------------------------
        # Hakikisha field haiko empty kabla ya kuendelea
        if not name:
            flash("Andika jina la mteja kwanza", "warning")
            return redirect(url_for("search_customer"))

        # ----------------------------------------
        # AUTHENTICATION CHECK
        # ----------------------------------------
        # Hakikisha boss yuko logged in
        boss_id = session.get("boss_id")
        if not boss_id:
            flash("Tafadhali ingia kwanza", "danger")
            return redirect(url_for("boss_login"))

        # ----------------------------------------
        # DATABASE CONNECTION
        # ----------------------------------------
        # Fungua connection ya SQLite DB
        # row_factory huruhusu kutumia column names kama dictionary keys
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # ----------------------------------------
        # SEARCH QUERY (CUSTOMERS + METERS)
        # ----------------------------------------
        # - Inatafuta wateja kwa jina (partial match kwa kutumia LIKE)
        # - COLLATE NOCASE → case-insensitive search (A = a)
        # - Inachuja kwa boss_id ili boss aone wateja wake tu (security)
        # - LEFT JOIN → inajumuisha hata wateja wasio na meter
        # - GROUP_CONCAT → inaunganisha meter numbers zote kuwa string moja
        cur.execute("""
            SELECT 
                c.customer_id, 
                c.full_name, 
                c.phone,
                GROUP_CONCAT(m.meter_number, ', ') as meters
            FROM customers c
            LEFT JOIN meters m ON m.customer_id = c.customer_id
            WHERE c.full_name LIKE ? COLLATE NOCASE
              AND c.boss_id = ?
            GROUP BY c.customer_id
        """, ('%' + name + '%', boss_id))

        # Chukua matokeo yote ya search
        customers = cur.fetchall()

        # Funga DB connection baada ya matumizi
        conn.close()

        # ----------------------------------------
        # RESULT HANDLING
        # ----------------------------------------

        # Case 1: Hakuna mteja aliyepatikana
        if not customers:
            flash("Mteja hajapatikana", "danger")
            return redirect(url_for("search_customer"))

        # Case 2: Mteja mmoja tu → redirect moja kwa moja kwenye details
        # Hii inaboresha user experience (UX)
        if len(customers) == 1:
            return redirect(
                url_for(
                    "customer_details", 
                    customer_id=customers[0]["customer_id"]
                )
            )

        # Case 3: Wateja wengi → onyesha list ya matokeo
        return render_template("search_results.html", customers=customers)

    # ------------------------------------------------
    # HANDLE GET REQUEST (INITIAL PAGE LOAD)
    # ------------------------------------------------
    # Onyesha form ya kutafuta mteja
    return render_template("search_customer.html")


# ============================================================
# Route: Confirm & Delete Customer (Boss Only)
# ============================================================
@app.route("/boss/confirm_delete_customer/<customer_id>", methods=["GET", "POST"])
def confirm_delete_customer(customer_id):

    # ------------------------------------------------
    # AUTHENTICATION CHECK
    # ------------------------------------------------
    # Hakikisha user amelogin kama boss kabla ya kufanya action yoyote
    # Hii inalinda route dhidi ya unauthorized access
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    # ------------------------------------------------
    # FETCH CUSTOMER (PRE-VALIDATION STEP)
    # ------------------------------------------------
    # Chukua taarifa za mteja ili:
    # 1. Kuhakikisha yupo
    # 2. Kuonyesha jina kwenye confirmation page
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers WHERE customer_id=?", (customer_id,))
    customer = cur.fetchone()
    conn.close()

    # ------------------------------------------------
    # VALIDATION: CUSTOMER EXISTENCE
    # ------------------------------------------------
    # Kama mteja hayupo, epuka kuendelea na process
    if not customer:
        flash("Mteja haipo", "danger")
        return redirect(url_for("boss_dashboard"))

    # ------------------------------------------------
    # HANDLE POST REQUEST (DELETE ACTION)
    # ------------------------------------------------
    # POST inamaanisha boss amethibitisha kufuta mteja
    if request.method == "POST":

        # Fungua connection mpya kwa ajili ya delete operation
        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # ----------------------------------------
            # DELETE RELATED DATA FIRST (DEPENDENCIES)
            # ----------------------------------------
            # Futa meters zinazohusiana na mteja huyu
            # (kuepuka foreign key constraint errors)
            cur.execute("DELETE FROM meters WHERE customer_id=?", (customer_id,))

            # ----------------------------------------
            # DELETE MAIN CUSTOMER RECORD
            # ----------------------------------------
            cur.execute("DELETE FROM customers WHERE customer_id=?", (customer_id,))

            # ----------------------------------------
            # COMMIT TRANSACTION
            # ----------------------------------------
            # Hakikisha mabadiliko yana-save kwenye database
            conn.commit()

            # Feedback kwa user baada ya kufuta
            flash(f"Mteja {customer['full_name']} ameondolewa!", "success")

        except sqlite3.Error as e:
            # ----------------------------------------
            # ERROR HANDLING
            # ----------------------------------------
            # Kama kuna kosa la DB, toa taarifa kwa user
            flash(f"Kosa la database: {e}", "danger")

        finally:
            # ----------------------------------------
            # CLEANUP
            # ----------------------------------------
            # Funga connection kila wakati (success au error)
            conn.close()

        # Baada ya delete, rudisha boss kwenye dashboard
        return redirect(url_for("boss_dashboard"))

    # ------------------------------------------------
    # HANDLE GET REQUEST (CONFIRMATION PAGE)
    # ------------------------------------------------
    # Onyesha page ya kuthibitisha kabla ya kufuta
    # Hii ni muhimu kwa UX na kuzuia accidental deletion
    return render_template("confirm_delete_customer.html", customer=customer)


                

# ============================================
# Route: View Customer Details (Boss Only)
# ============================================
@app.route("/customer_details/<customer_id>")
def customer_details(customer_id):

    # -------------------------------
    # AUTHENTICATION CHECK
    # -------------------------------
    # Hakikisha user amelogin kama boss
    # Kama hajalogin, mzuie na mrudishe login page
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    # -------------------------------
    # DATABASE CONNECTION SETUP
    # -------------------------------
    # Fungua connection ya SQLite DB
    # row_factory = sqlite3.Row inaruhusu kupata data kama dictionary (key-based access)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # -------------------------------
    # FETCH: CUSTOMER BASIC INFO
    # -------------------------------
    # Chukua taarifa zote za mteja kulingana na customer_id
    # Parameterized query inalinda dhidi ya SQL Injection
    cur.execute("""
        SELECT * FROM customers
        WHERE customer_id = ?
    """, (customer_id,))
    customer = cur.fetchone()  # record moja ya mteja

    # -------------------------------
    # FETCH: CUSTOMER METERS
    # -------------------------------
    # Chukua mita zote zinazohusiana na mteja huyu
    cur.execute("""
        SELECT meter_id, meter_number, status
        FROM meters
        WHERE customer_id = ?
    """, (customer_id,))
    meters = cur.fetchall()  # list ya meters

    # -------------------------------
    # FETCH: UNPAID BILLS ONLY
    # -------------------------------
    # Chukua bili ambazo bado hazijalipwa (UNPAID)
    # JOIN inatumika kupata meter_number kutoka table ya meters
    # ORDER BY DESC → bili mpya zinaanza juu
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
    bills = cur.fetchall()  # list ya bills zisizolipwa

    # -------------------------------
    # CLOSE DATABASE CONNECTION
    # -------------------------------
    # Epuka memory leaks kwa kufunga connection
    conn.close()

    # -------------------------------
    # RENDER TEMPLATE (VIEW LAYER)
    # -------------------------------
    # Tuma data zote kwenye HTML template
    # - customer → taarifa za mteja
    # - meters → mita zake
    # - bills → bili ambazo hajalipa
    return render_template(
        "customer_details.html",
        customer=customer,
        meters=meters,
        bills=bills
    )



    
# ==========================
# Route: Home / Entry Point
# ==========================
@app.route("/")
def index():
    # Chukua role ya user kutoka kwenye session
    # (inawekwa wakati wa login)
    role = session.get("role")

    # Kama user ni Super Admin
    # mpelekwe kwenye dashboard yake maalum
    if role == "superadmin":
        return redirect(url_for("superadmin_dashboard"))

    # Kama user ni Boss
    # mpelekwe kwenye boss dashboard
    elif role == "boss":
        return redirect(url_for("boss_dashboard"))

    # Kama user ni Staff
    # mpelekwe kwenye staff dashboard
    elif role == "staff":
        return redirect(url_for("staff_dashboard"))

    # Kama hakuna role (user hajalogin au session ime-expire)
    # mpeleke kwenye login page kama default
    return redirect(url_for("boss_login"))
    
    
# ================= RUN APP ==================
# ================= RUN APP ==================
if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)