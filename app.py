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

# Database connection
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ================== SUPER ADMIN ==================
@app.route("/superadmin/login", methods=["GET", "POST"])
def superadmin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM super_admin WHERE username = ?", (username,))
        admin = cur.fetchone()
        conn.close()

        if admin and check_password_hash(admin["password"], password):
            session["superadmin_id"] = admin["admin_id"]
            session["superadmin_username"] = admin["username"]
            flash("Karibu Super Admin!", "success")
            return redirect(url_for("superadmin_dashboard"))
        flash("Username au password si sahihi.", "danger")
    return render_template("superadmin_login.html")


@app.route("/superadmin/dashboard")
def superadmin_dashboard():
    if "superadmin_id" not in session:
        flash("Tafadhali ingia kwanza kama Super Admin", "danger")
        return redirect(url_for("superadmin_login"))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT boss_id, full_name, username, status, trial_end_date 
        FROM boss
        ORDER BY full_name
    """)
    bosses = cur.fetchall()
    conn.close()
    return render_template("superadmin_dashboard.html", bosses=bosses)


@app.route("/superadmin/toggle_boss/<boss_id>")
def toggle_boss(boss_id):
    if "superadmin_id" not in session:
        flash("Login required", "danger")
        return redirect(url_for("superadmin_login"))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM boss WHERE boss_id = ?", (boss_id,))
    boss = cur.fetchone()
    if boss:
        new_status = "INACTIVE" if boss["status"] == "ACTIVE" else "ACTIVE"
        cur.execute("UPDATE boss SET status = ? WHERE boss_id = ?", (new_status, boss_id))
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
    cur.execute("UPDATE boss SET password = ? WHERE boss_id = ?", (hashed_pw, boss_id))
    conn.commit()
    conn.close()

    flash(f"Password mpya ya boss: {new_password}", "success")
    return redirect(url_for("superadmin_dashboard"))


@app.route("/superadmin/logout")
def superadmin_logout():
    session.pop("superadmin_id", None)
    session.pop("superadmin_username", None)
    flash("Umetoka kwenye Super Admin", "success")
    return redirect(url_for("superadmin_login"))

# ================== BOSS ==================
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
            flash("Username tayari ipo, chagua nyingine.", "danger")
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
        cur.execute("SELECT * FROM boss WHERE username = ?", (username,))
        boss = cur.fetchone()
        conn.close()

        if boss and check_password_hash(boss["password"], password):

            # 🔹 Angalia status kwanza
            if boss["status"] != "ACTIVE":
                flash("Account yako imefungwa. Tafadhali wasiliana na Super Admin.", "danger")
                return redirect(url_for("boss_login"))

            # 🔹 Angalia trial
            now = datetime.now()
            trial_end = datetime.strptime(boss["trial_end_date"], "%Y-%m-%d %H:%M:%S")
            if now > trial_end:
                flash("Trial imeisha, tafadhali lipia au wasiliana na admin.", "danger")
                return redirect(url_for("boss_login"))

            # 🔹 Login sahihi
            session["boss_id"] = boss["boss_id"]
            session["boss_username"] = boss["username"]
            flash(f"Karibu, {boss['full_name']}!", "success")
            return redirect(url_for("boss_dashboard"))
        else:
            flash("Username au password sio sahihi.", "danger")
            return redirect(url_for("boss_login"))

    return render_template("boss_login.html")

@app.route("/boss_dashboard")
def boss_dashboard():
    if "boss_id" not in session:
        return redirect(url_for("boss_login"))

    conn = sqlite3.connect("water_supply.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Chukua taarifa za boss
    cur.execute("SELECT * FROM boss WHERE boss_id = ?", (session["boss_id"],))
    boss = cur.fetchone()

    # Chukua meters
    cur.execute("""
        SELECT c.customer_id, c.full_name AS customer_name,
               m.meter_number, m.status AS meter_status
        FROM customers c
        LEFT JOIN meters m ON c.customer_id = m.customer_id
        WHERE c.boss_id = ?
    """, (session["boss_id"],))
    
    meters = cur.fetchall()

    conn.close()

    return render_template(
        "boss_dashboard.html",
        boss=boss,          # 👈 HII NDIO MUHIMU
        meters=meters
    )

@app.route("/boss/logout")
def boss_logout():
    session.pop("boss_id", None)
    session.pop("boss_username", None)
    flash("Umetoka kwenye dashboard ya boss", "success")
    return redirect(url_for("boss_login"))


if __name__ == "__main__":
    app.run(debug=True)