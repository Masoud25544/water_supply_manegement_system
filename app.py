from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta
import uuid
import random
import string

app = Flask(__name__)
app.secret_key = "supersecretkey"
DB_PATH = "water_supply.db"

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
        new_status = "INACTIVE" if boss["status"] == "ACTIVE" else "ACTIVE"
        cur.execute("UPDATE boss SET status=? WHERE boss_id=?", (new_status, boss_id))
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
        conn.close()
        if boss and check_password_hash(boss["password"], password):
            if boss["status"] != "ACTIVE":
                flash("Tafadhari Account imefungwa wasilina na Masoud (0744906763)", "danger")
                return redirect(url_for("boss_login"))
            now = datetime.now()
            trial_end = datetime.strptime(boss["trial_end_date"], "%Y-%m-%d %H:%M:%S")
            if now > trial_end:
                flash("Trial imeisha.", "danger")
                return redirect(url_for("boss_login"))
            session["boss_id"] = boss["boss_id"]
            flash(f"Karibu, {boss['full_name']}!", "success")
            return redirect(url_for("boss_dashboard"))
        flash("Username au password sio sahihi.", "danger")
        return redirect(url_for("boss_login"))
    return render_template("boss_login.html")
    
@app.route("/boss_dashboard")
def boss_dashboard():
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("login"))

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
    
@app.route("/read_meter", methods=["GET", "POST"])
def read_meter():
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]

    if request.method == "POST":
        meter_number = request.form.get("meter_number")
        current_reading = request.form.get("current_reading")

        if not meter_number or not current_reading:
            flash("Jaza taarifa zote", "danger")
            return redirect(url_for("read_meter"))

        try:
            current_reading = float(current_reading)
        except ValueError:
            flash("Tafadhali weka namba sahihi kwa reading", "danger")
            return redirect(url_for("read_meter"))

        billing_month = datetime.now().strftime("%Y-%m")

        conn = get_db_connection()
        cursor = conn.cursor()

        # 1️⃣ Hakikisha meter ipo na ni ya boss huyu
        cursor.execute("""
            SELECT meters.*, customers.boss_id 
            FROM meters
            JOIN customers ON meters.customer_id = customers.customer_id
            WHERE meters.meter_number = ?
        """, (meter_number,))
        meter = cursor.fetchone()

        if not meter:
            flash("Tafadhari namba ya meter uliyoingiza  haipo", "danger")
            conn.close()
            return redirect(url_for("read_meter"))

        if meter["boss_id"] != boss_id:
            flash("Huruhusiwi kusoma meter ya boss mwingine", "danger")
            conn.close()
            return redirect(url_for("read_meter"))

        meter_id = meter["meter_id"]
        customer_id = meter["customer_id"]

        # 2️⃣ Zuia kusoma mara mbili mwezi huu
        cursor.execute("""
            SELECT * FROM bills
            WHERE meter_id = ? AND billing_month = ?
        """, (meter_id, billing_month))

        if cursor.fetchone():
            flash("Meter tayari imesomwa mwezi huu", "warning")
            conn.close()
            return redirect(url_for("read_meter"))

        # 3️⃣ Pata last total units zilizowahi kusomwa
        cursor.execute("""
            SELECT SUM(units_used) as total_units
            FROM bills
            WHERE meter_id = ?
        """, (meter_id,))
        total = cursor.fetchone()
        previous_total_units = total["total_units"] if total["total_units"] else 0

        # 4️⃣ Validate reading
        if current_reading < previous_total_units:
            flash("Reading mpya haiwezi kuwa chini ya ya zamani", "danger")
            conn.close()
            return redirect(url_for("read_meter"))

        units_used = current_reading - previous_total_units

        # 5️⃣ Chukua tariff ya boss
        cursor.execute("""
            SELECT price_per_unit 
            FROM tariffs
            WHERE boss_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (boss_id,))
        tariff = cursor.fetchone()

        if not tariff:
            flash("Tafadhali weka tariff kwanza", "danger")
            conn.close()
            return redirect(url_for("read_meter"))

        price_per_unit = tariff["price_per_unit"]
        amount = units_used * price_per_unit

        # 6️⃣ Tengeneza bill
        bill_id = "BILL-" + uuid.uuid4().hex[:8]
        cursor.execute("""
            INSERT INTO bills (
                bill_id, customer_id, meter_id,
                units_used, amount, billing_month,
                status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bill_id,
            customer_id,
            meter_id,
            units_used,
            amount,
            billing_month,
            "UNPAID",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        conn.close()

        flash(f"Bill imetengenezwa kwa {meter_number}: {amount:.2f} Tsh", "success")
        return redirect(url_for("read_meter"))

    # GET request
    return render_template("read_meter.html")
    
    
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

@app.route("/unread_meters", methods=["GET", "POST"])
def unread_meters():
    # 1️⃣ Hakikisha boss ame-login
    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    boss_id = session["boss_id"]

    # 2️⃣ Pata mwezi uliochaguliwa
    selected_month = request.form.get("month") if request.method == "POST" else datetime.now().strftime("%Y-%m")
    if not selected_month:
        selected_month = datetime.now().strftime("%Y-%m")

    conn = get_db_connection()
    cur = conn.cursor()

    # 3️⃣ Pata signup_date ya boss
    cur.execute("SELECT signup_date FROM boss WHERE boss_id = ?", (boss_id,))
    boss_data = cur.fetchone()
    if not boss_data:
        conn.close()
        flash("Boss hakupatikana.", "danger")
        return redirect(url_for("boss_dashboard"))

    signup_month = boss_data["signup_date"][:7]
    current_month = datetime.now().strftime("%Y-%m")

    # 4️⃣ Check kama mwezi ni kabla ya signup
    if selected_month < signup_month:
        conn.close()
        return render_template(
            "unread_meters.html",
            unread=[],
            month=selected_month,
            unread_count=0,
            message="Boss hakuwa active mwezi huu."
        )

    # 5️⃣ Check kama mwezi ni wa mbele (future)
    if selected_month > current_month:
        conn.close()
        return render_template(
            "unread_meters.html",
            unread=[],
            month=selected_month,
            unread_count=0,
            message="Huwezi kuangalia mwezi wa mbele ambao bado haujafika."
        )

    # 6️⃣ Pata customers ambao hawajasomewa na info ya meter
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

    return render_template(
        "unread_meters.html",
        unread=unread,
        month=selected_month,
        unread_count=unread_count,
        message=None,
        current_month=current_month
    )


@app.route("/unpaid_bills")
def unpaid_bills():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    bills = conn.execute("""
        SELECT b.*, c.full_name AS customer_name, m.meter_number
        FROM bills b
        JOIN customers c ON b.customer_id = c.customer_id
        LEFT JOIN meters m ON c.customer_id = m.customer_id
        WHERE b.status='UNPAID'
        ORDER BY b.billing_month DESC
    """).fetchall()
    conn.close()
    return render_template("unpaid_bills.html", unpaid_bills=bills)
                               
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
@app.route("/receive_payment/<bill_id>", methods=["GET", "POST"])
def receive_payment(bill_id):

    if "boss_id" not in session:
        flash("Tafadhali ingia kwanza", "danger")
        return redirect(url_for("boss_login"))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    bill = cursor.execute("""
        SELECT b.*, c.full_name AS customer_name, c.customer_id,
               m.meter_number
        FROM bills b
        JOIN customers c ON b.customer_id = c.customer_id
        LEFT JOIN meters m ON c.customer_id = m.customer_id
        WHERE b.bill_id=?
    """, (bill_id,)).fetchone()

    if not bill:
        flash("Bili haipo", "danger")
        conn.close()
        return redirect(url_for("unpaid_bills"))

    if request.method == "POST":
        try:
            payment_id = "PAY-" + uuid.uuid4().hex[:8]
            receipt_id = "RCPID-" + uuid.uuid4().hex[:8]
            boss_id = session["boss_id"]

            # Generate receipt number
            year = datetime.now().year
            count = cursor.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] + 1
            receipt_number = f"RCP-{year}-{str(count).zfill(5)}"

            # 1️⃣ Insert payment
            cursor.execute("""
                INSERT INTO payments
                (payment_id, bill_id, customer_id, boss_id, amount_paid, payment_method, reference, paid_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                payment_id,
                bill["bill_id"],
                bill["customer_id"],
                boss_id,
                bill["amount"],
                "CASH",
                None,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

            # 2️⃣ Update bill
            cursor.execute("""
                UPDATE bills
                SET status='PAID',
                    payment_method='CASH',
                    payment_date=?
                WHERE bill_id=?
            """, (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                bill_id
            ))

            # 3️⃣ Insert receipt
            cursor.execute("""
                INSERT INTO receipts
                (receipt_id, payment_id, receipt_number, customer_id, boss_id, amount, issued_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                receipt_id,
                payment_id,
                receipt_number,
                bill["customer_id"],
                boss_id,
                bill["amount"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

            conn.commit()
            conn.close()

            flash("Malipo yamepokelewa na risiti imetengenezwa!", "success")
            return redirect(url_for("view_receipt", receipt_id=receipt_id))

        except Exception as e:
            conn.rollback()
            conn.close()
            flash("Kuna tatizo wakati wa kuhifadhi malipo", "danger")
            return redirect(url_for("unpaid_bills"))

    conn.close()
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
    
# ================= RUN APP ==================
if __name__ == "__main__":
    app.run(debug=True)