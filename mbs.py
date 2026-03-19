import sqlite3
conn = sqlite3.connect("water_supply.db")
cur = conn.cursor()
cur.execute("SELECT full_name, username, signup_date, trial_end_date, status FROM boss")
for row in cur.fetchall():
    print(row)