from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta
import uuid
import random
import string
import uuid

def generate_staff_id():
    return "STF-" + str(uuid.uuid4())[:8]

app = Flask(__name__)
app.secret_key = "supersecretkey"
DB_PATH = "water_supply.db"

from functools import wraps
from flask import session, flash, redirect, url_for

# =================== MULTI-ROLE DECORATOR ===================
def role_required(*allowed_roles):
    """
    Decorator ya Flask kwa role-based access control.
    Roles zinazokubaliwa: 'boss', 'staff', 'admin'
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Map role na session key yao
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
            
            # Redirect kulingana na priority
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

# ================= SUPER ADMIN ==================
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

# ================= SUPER ADMIN DASHBOARD ==================
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

@app.route("/superadmin/boss_customers", methods=["GET", "POST"])
def superadmin_boss_customers():
    if "superadmin_id" not in session:
        flash("Tafadhali ingia kama Super Admin.", "danger")
        return redirect(url_for("superadmin_login"))

    conn = get_db_connection()
    cur = conn.cursor()

    # Pata maboss wote
    cur.execute("SELECT boss_id, full_name, username FROM boss ORDER BY full_name")
    bosses = cur.fetchall()

    selected_boss_id = None
    customers = []

    if request.method == "POST":
        selected_boss_id = request.form.get("boss_id")
        if selected_boss_id:
            cur.execute("""
                SELECT * FROM customers
                WHERE boss_id = ?
                ORDER BY created_at DESC
            """, (selected_boss_id,))
            customers = cur.fetchall()

    conn.close()
    return render_template(
        "superadmin_boss_customers.html",
        bosses=bosses,
        customers=customers,
        selected_boss_id=selected_boss_id
    )

@app.route("/superadmin/toggle_boss/<boss_id>")
def toggle_boss(boss_id):
    if "superadmin_id" not in session:
        flash("Login required", "danger")
        return redirect(url_for("superadmin_login"))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT status FROM boss WHERE boss_id=?", (boss_id,))
    boss = cur.fetchone()

    if boss:
        if boss["status"] == "ACTIVE":
            new_status = "INACTIVE"
            cur.execute(
                "UPDATE boss SET status=? WHERE boss_id=?",
                (new_status, boss_id)
            )
        else:
            # 🔥 HAPA NDIPO MUHIMU
            new_status = "ACTIVE"
            new_trial_end = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

            cur.execute("""
                UPDATE boss 
                SET status=?, trial_end_date=? 
                WHERE boss_id=?
            """, (new_status, new_trial_end, boss_id))

        conn.commit()
        flash(f"Boss status imebadilishwa kuwa {new_status}", "success")
    else:
        flash("Boss haipo", "danger")

    conn.close()
    return redirect(url_for("superadmin_dashboard"))

@app.route("/superadmin/reset_boss_password/<boss_id>")
def superadmin_reset_boss_password(boss_id):
    if "superadmin_id" not in session:
        flash("Login required", "danger")
        return redirect(url_for("superadmin_login"))
    new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    hashed_pw = generate_password_hash(new_password)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE boss SET password=? WHERE boss_id=?", (hashed_pw, boss_id))
    conn.commit()
    conn.close()
    flash(f"Password mpya ya boss: {new_password}", "success")
    return redirect(url_for("superadmin_dashboard"))

@app.route("/superadmin/logout")
def superadmin_logout():
    session.pop("superadmin_id", None)
    flash("Umetoka kwenye Super Admin", "success")
    return redirect(url_for("superadmin_login"))

# ================= BOSS ==================
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

            # 1️⃣ Check kama trial imeisha kwanza
            now = datetime.now()
            trial_end = datetime.strptime(boss["trial_end_date"], "%Y-%m-%d %H:%M:%S")

            if now > trial_end:
                # Badilisha status kuwa INACTIVE
                cur.execute(
                    "UPDATE boss SET status=? WHERE boss_id=?",
                    ("INACTIVE", boss["boss_id"])
                )
                conn.commit()
                conn.close()

                flash("Trial imeisha. Account yako sasa ni INACTIVE. Wasiliana na Admin kwa malipo.", "danger")
                return redirect(url_for("boss_login"))

            # 2️⃣ Baada ya kuhakikisha trial haijaisha, check status
            if boss["status"] != "ACTIVE":
                conn.close()
                flash("Account yako ni INACTIVE. Wasiliana na Admin kwa malipo.", "danger")
                return redirect(url_for("boss_login"))

            # 3️⃣ Login success
            session["boss_id"] = boss["boss_id"]
            conn.close()
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
        return redirect(url_for("boss_login"))  # ✅ Imebadilishwa

    boss_id = session["boss_id"]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Pata info ya boss
    boss = conn.execute("SELECT * FROM boss WHERE boss_id=?", (boss_id,)).fetchone()

    # Pata wateja wote pamoja na meters zao
    customers = conn.execute("""
        SELECT c.customer_id, c.full_name, c.phone, c.area, c.house_number,
               m.meter_number, COALESCE(m.status,'INACTIVE') AS meter_status
        FROM customers c
        LEFT JOIN meters m ON c.customer_id = m.customer_id
        WHERE c.boss_id=?
        ORDER BY c.full_name
    """, (boss_id,)).fetchall()

    # Hesabu meters ACTIVE na INACTIVE
    active_meters = len([c for c in customers if c['meter_status']=='ACTIVE'])
    inactive_meters = len([c for c in customers if c['meter_status']=='INACTIVE'])

    # Pata unpaid bills kwa boss huyu
    unpaid_bills = conn.execute("""
        SELECT b.*, c.full_name AS customer_name, m.meter_number
        FROM bills b
        JOIN customers c ON b.customer_id = c.customer_id
        LEFT JOIN meters m ON c.customer_id = m.customer_id
        WHERE b.status='UNPAID' AND c.boss_id=?
        ORDER BY b.billing_month DESC
    """, (boss_id,)).fetchall()
    unpaid_count = len(unpaid_bills)

    conn.close()

    return render_template("boss_dashboard.html",
                           boss=boss,
                           customers=customers,
                           active_meters=active_meters,
                           inactive_meters=inactive_meters,
                           unpaid_bills=unpaid_bills,
                           unpaid_count=unpaid_count)
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
            # ✅ Check kama meter ipo tayari
            cur.execute("SELECT 1 FROM meters WHERE meter_number = ?", (meter_number,))
            if cur.fetchone():
                flash("⚠️ Tafadhari meter namba uliyo ingiza  tayari imesajiliwa kwenyevmfumo.", "warning")
                conn.close()
                return redirect(url_for("add_customer"))

            customer_id = "CUST-" + str(uuid.uuid4())[:8]
            meter_id = "MTR-" + str(uuid.uuid4())[:8]
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status = "ACTIVE"

            # ✅ Insert customer
            cur.execute("""
                INSERT INTO customers 
                (customer_id, boss_id, full_name, phone, area, house_number, meter_number, status, created_at, signup_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                customer_id,
                session["boss_id"],
                full_name,
                phone,
                area,
                house_number,
                meter_number,
                status,
                now,
                now
            ))

            # ✅ Insert meter
            cur.execute("""
                INSERT INTO meters 
                (meter_id, meter_number, customer_id, status)
                VALUES (?, ?, ?, ?)
            """, (
                meter_id,
                meter_number,
                customer_id,
                status
            ))

            conn.commit()
            flash(f"✅ Mteja {full_name} na meter {meter_number} wamesajiliwa kikamilifu!", "success")

        except sqlite3.IntegrityError:
            conn.rollback()
            flash("⚠️ Meter tayari ipo kwenye mfumo.", "warning")

        except Exception:
            conn.rollback()
            flash("❌ Kuna tatizo limetokea. Tafadhali jaribu tena.", "danger")

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

@app.route("/boss/delete_customer/<customer_id>")
def delete_customer(customer_id):
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
        cur.execute("DELETE FROM meters WHERE customer_id=?", (customer_id,))
        cur.execute("DELETE FROM customers WHERE customer_id=?", (customer_id,))
        conn.commit()
        flash(f"Mteja {customer['full_name']} ameondolewa!", "success")
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

    # Tumia session info
    user_role = "staff" if "staff_id" in session else "boss"
    user_id = session.get("staff_id") or session.get("boss_id")
    boss_id = session.get("staff_boss_id") or session.get("boss_id")
    bill = None

    if request.method == "POST":
        meter_number = request.form.get("meter_number")
        current_reading = request.form.get("current_reading")

        # Hakikisha fields zimejazwa
        if not meter_number or not current_reading:
            flash("Tafadhali jaza meter number na reading", "danger")
            return render_template("read_meter.html", bill=None)

        conn = get_db_connection()
        cur = conn.cursor()

        # Angalia meter ipo na ni ya wateja wa boss/staff
        cur.execute("""
            SELECT m.meter_id, m.customer_id, c.full_name
            FROM meters m
            JOIN customers c ON m.customer_id = c.customer_id
            WHERE m.meter_number=? AND c.boss_id=?
        """, (meter_number, boss_id))
        meter = cur.fetchone()

        if not meter:
            flash("Meter hii haipo au sio ya wateja wako", "danger")
            conn.close()
            return render_template("read_meter.html", bill=None)

        # Hakikisha haijasomwa mwezi huu
        billing_month = datetime.now().strftime("%Y-%m")
        cur.execute("""
            SELECT bill_id FROM bills
            WHERE meter_id=? AND billing_month=?
        """, (meter["meter_id"], billing_month))
        existing_bill = cur.fetchone()
        if existing_bill:
            flash(f"⚠️ Meter hii tayari imesomwa mwezi huu (Bill ID: {existing_bill['bill_id']})", "warning")
            conn.close()
            return render_template("read_meter.html", bill=None)

        # Pata tariff ya boss
        cur.execute("""
            SELECT price_per_unit FROM tariffs
            WHERE boss_id=? ORDER BY created_at DESC LIMIT 1
        """, (boss_id,))
        tariff = cur.fetchone()
        price_per_unit = tariff["price_per_unit"] if tariff else 0

        # Hesabu amount
        units_used = float(current_reading)
        amount = units_used * price_per_unit

        bill_id = "BILL-" + str(uuid.uuid4())[:8]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Insert bill mpya
        cur.execute("""
            INSERT INTO bills
            (bill_id, customer_id, meter_id, units_used, amount, billing_month, status, created_at, read_by, reader_role)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bill_id,
            meter["customer_id"],
            meter["meter_id"],
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
        flash(f"✅ Meter {meter_number} imesomwa kwa {meter['full_name']}", "success")

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

    customers_meters = cur.fetchall()
    conn.close()

    # Weka data kwenye template ya boss_dashboard.html
    return render_template("boss_meters.html", customers=customers_meters)    

    return render_template("boss_customers.html", customers=customers)
    

    
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
        staff_role = session.get("staff_role")  # Lazima iwe ime-set wakati wa login
        if staff_role != "meter_reader":
            flash("Huna ruhusa ya kuona meters hizi.", "danger")
            return redirect(url_for("staff_dashboard"))
    else:
        # Hii hali haipaswi kutokea, lakini hakikisha
        flash("Huna ruhusa ya kuona ukurasa huu.", "danger")
        return redirect(url_for("login"))

    # 3️⃣ Chagua mwezi
    selected_month = request.form.get("month") or datetime.now().strftime("%Y-%m")
    current_month = datetime.now().strftime("%Y-%m")

    conn = get_db_connection()
    cur = conn.cursor()

    # 4️⃣ Pata signup date ya boss ili kudhibitisha mwezi
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

    # 5️⃣ Pata meters ambazo hazijasomwa
    query = """
    SELECT c.customer_id, c.full_name, c.phone, c.area,
           m.meter_number, m.status AS meter_status
    FROM customers c
    JOIN meters m ON c.customer_id = m.customer_id
    WHERE c.boss_id = ?
    AND NOT EXISTS (
        SELECT 1 FROM bills b
        WHERE b.customer_id = c.customer_id
        AND b.billing_month = ?
    )
    ORDER BY c.full_name
    """
    cur.execute(query, (boss_id, selected_month))
    unread = cur.fetchall()
    unread_count = len(unread)
    conn.close()

    # 6️⃣ Rudisha template na role ili kurudi kwenye dashboard sahihi
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
    # Hakikisha user ameloga
    if "boss_id" in session:
        user_role = "boss"
        boss_id = session["boss_id"]
    elif "staff_id" in session:
        user_role = "staff"
        boss_id = session.get("boss_id")  # staff_id pia ina boss_id kwenye session
    elif "superadmin_id" in session:
        user_role = "superadmin"
        boss_id = None
    else:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("login"))  # login route yako ya default

    # Unganisha DB
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Pata bills zisizolipwa, boss pekee (au zote kwa superadmin)
    if user_role == "superadmin":
        bills = conn.execute("""
            SELECT b.*, c.full_name AS customer_name, m.meter_number
            FROM bills b
            JOIN customers c ON b.customer_id = c.customer_id
            LEFT JOIN meters m ON c.customer_id = m.customer_id
            WHERE b.status='UNPAID'
            ORDER BY b.billing_month DESC
        """).fetchall()
    else:
        bills = conn.execute("""
            SELECT b.*, c.full_name AS customer_name, m.meter_number
            FROM bills b
            JOIN customers c ON b.customer_id = c.customer_id
            LEFT JOIN meters m ON c.customer_id = m.customer_id
            WHERE b.status='UNPAID' AND c.boss_id = ?
            ORDER BY b.billing_month DESC
        """, (boss_id,)).fetchall()

    conn.close()

    return render_template("unpaid_bills.html", unpaid_bills=bills, user_role=user_role)
                               
@app.route("/boss/customers")
def boss_view_customers():
    # 1️⃣ Hakikisha boss ameingia
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]

    # 2️⃣ Unganisha na database
    conn = get_db_connection()
    cur = conn.cursor()

    # 3️⃣ Chukua wateja wote wa boss na meter zao
    cur.execute("""
        SELECT c.customer_id, c.full_name AS customer_name,
               c.phone, c.area, c.house_number,
               c.status AS customer_status,
               m.meter_number, m.status AS meter_status
        FROM customers c
        LEFT JOIN meters m ON c.customer_id = m.customer_id
        WHERE c.boss_id = ?
        ORDER BY c.full_name
    """, (boss_id,))
    
    customers = cur.fetchall()
    conn.close()

    # 4️⃣ Rudisha data kwenye template
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
        SELECT status FROM meters m
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
    flash("Status ya meter imebadilishwa", "success")
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

    # Hakikisha ameloga
    if "staff_id" not in session and "boss_id" not in session:
        flash("Tafadhali login kwanza", "danger")
        return redirect(url_for("login"))

    # Amua user role
    if "staff_id" in session:
        user_id = session["staff_id"]
        user_role = session.get("staff_role")  # cashier
    else:
        user_id = session["boss_id"]
        user_role = "boss"

    # Pata bill info
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
        return redirect(url_for("unpaid_bills"))

    if request.method == "POST":
        payment_id = "PAY-" + uuid.uuid4().hex[:8]
        receipt_id = "RCPID-" + uuid.uuid4().hex[:8]

        # Generate receipt number
        year = datetime.now().year
        count = cursor.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] + 1
        receipt_number = f"RCP-{year}-{str(count).zfill(5)}"

        # Insert payment
        cursor.execute("""
            INSERT INTO payments
            (payment_id, bill_id, customer_id, boss_id, amount_paid, payment_method, reference, paid_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payment_id, bill["bill_id"], bill["customer_id"],
            user_id, bill["amount"], "CASH", None,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        # Update bill status
        cursor.execute("""
            UPDATE bills
            SET status='PAID', payment_method='CASH', payment_date=?
            WHERE bill_id=?
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), bill_id))

        # Insert receipt
        cursor.execute("""
            INSERT INTO receipts
            (receipt_id, payment_id, receipt_number, customer_id, boss_id, amount, issued_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            receipt_id, payment_id, receipt_number,
            bill["customer_id"], user_id, bill["amount"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        conn.close()
        flash("Malipo yamepokelewa na risiti imetengenezwa!", "success")
        return redirect(url_for("view_receipt", receipt_id=receipt_id))

    conn.close()
    # GET request: show confirmation page
    return render_template("confirm_payment.html", bill=bill)
    
@app.route("/receipt/<receipt_id>")
def view_receipt(receipt_id):

    if "boss_id" not in session:
        return redirect(url_for("boss_login"))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    receipt = cursor.execute("""
        SELECT r.*, c.full_name, c.phone
        FROM receipts r
        JOIN customers c ON r.customer_id = c.customer_id
        WHERE r.receipt_id=?
    """, (receipt_id,)).fetchone()

    conn.close()

    if not receipt:
        flash("Risiti haipo", "danger")
        return redirect(url_for("boss_dashboard"))

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
    # Kama POST request (mtu ana-submit login form)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection()

        # Pata info ya staff kutoka database
        staff = conn.execute("SELECT * FROM staff WHERE username=?", (username,)).fetchone()
        conn.close()

        # Hakikisha staff ipo na password iko sahihi
        if staff and check_password_hash(staff["password"], password):
            # Angalia status
            if staff["status"] != "ACTIVE":
                flash("Account yako imefungwa. Wasiliana na boss wako.", "danger")
                return redirect(url_for("staff_login"))

            # Weka session ili kufuatilia user
            session["staff_id"] = staff["staff_id"]
            session["staff_name"] = staff["full_name"]
            session["staff_role"] = staff["role"].lower()  # lowercase English backend-friendly
            session["staff_boss_id"] = staff["boss_id"]

            flash(f"Karibu {staff['full_name']}!", "success")
            return redirect(url_for("staff_dashboard"))

        # Username au password sio sahihi
        flash("Username au password sio sahihi.", "danger")

    # GET request: onyesha login page
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
      
# ================= RUN APP ==================
if __name__ == "__main__":
    app.run(debug=True)