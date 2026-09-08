"""
Ayush Patient Case-Taking Software - MVP
SIH26047 - Ministry of Ayush

Simple Flask + SQLite app. No internet/cloud database needed - runs fully
offline once the Python packages are installed.

HOW TO RUN:
1. pip install flask
2. python app.py
3. Open http://127.0.0.1:5000 in your browser
4. Login PIN is: 1234 (change it in DEFAULT_PIN below)
"""

import sqlite3
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, g, flash

app = Flask(__name__)
app.secret_key = "sih26047-ayush-case-taking-secret"  # change this for real deployment

DB_PATH = os.path.join(os.path.dirname(__file__), "ayush.db")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pin TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            contact TEXT,
            address TEXT,
            emergency_contact TEXT,
            patient_pin TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS case_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_name TEXT,
            visit_date TEXT NOT NULL,
            chief_complaints TEXT,
            history_illness TEXT,
            family_history TEXT,
            current_medicines TEXT,
            previous_medicines TEXT,
            dosha_assessment TEXT,
            nidan_cause TEXT,
            nidan_early_signs TEXT,
            nidan_symptoms TEXT,
            nidan_examination TEXT,
            diagnosis TEXT,
            additional_notes TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        );

        CREATE TABLE IF NOT EXISTS pending_edits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            requested_by TEXT,
            new_name TEXT,
            new_age INTEGER,
            new_gender TEXT,
            new_contact TEXT,
            new_address TEXT,
            new_emergency_contact TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pre_consultations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS appointment_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            preferred_date TEXT,
            reason TEXT,
            status TEXT DEFAULT 'requested',
            created_at TEXT NOT NULL
        );
        """
    )
    db.commit()

    # Seed a couple of demo doctors so the app isn't empty on first run
    # (only inserts if the doctors table is currently empty)
    existing = db.execute("SELECT COUNT(*) AS c FROM doctors").fetchone()["c"]
    if existing == 0:
        db.execute("INSERT INTO doctors (name, pin) VALUES (?,?)", ("Dr. Sharma", "1234"))
        db.commit()

    db.close()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login_required(view):
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    wrapped.__name__ = view.__name__
    return wrapped


@app.route("/", methods=["GET"])
def index():
    # Landing page: patient just came back from a doctor login session? send to dashboard.
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return render_template("role_select.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        pin = request.form.get("pin", "")
        db = get_db()
        doctor = db.execute("SELECT * FROM doctors WHERE pin = ?", (pin,)).fetchone()
        if doctor:
            session["logged_in"] = True
            session["doctor_name"] = doctor["name"]
            session["doctor_id"] = doctor["id"]
            return redirect(url_for("dashboard"))
        else:
            error = "Incorrect PIN. Please try again."
    return render_template("login.html", error=error)


@app.route("/doctor-register", methods=["GET", "POST"])
def doctor_register():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        pin = request.form.get("pin", "").strip()
        confirm_pin = request.form.get("confirm_pin", "").strip()

        if not name:
            error = "Please enter your name."
        elif not (pin.isdigit() and len(pin) == 4):
            error = "PIN must be exactly 4 digits."
        elif pin != confirm_pin:
            error = "PINs do not match."
        else:
            db = get_db()
            existing = db.execute("SELECT * FROM doctors WHERE pin = ?", (pin,)).fetchone()
            if existing:
                error = "This PIN is already taken. Please choose a different one."
            else:
                db.execute("INSERT INTO doctors (name, pin) VALUES (?,?)", (name, pin))
                db.commit()
                flash(f"Registered successfully, Dr. {name}! You can now log in with your PIN.")
                return redirect(url_for("login"))
    return render_template("doctor_register.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def doctor_settings():
    db = get_db()
    error = None
    success = None
    doctor = db.execute("SELECT * FROM doctors WHERE id = ?", (session.get("doctor_id"),)).fetchone()

    if request.method == "POST":
        new_pin = request.form.get("new_pin", "").strip()
        confirm_pin = request.form.get("confirm_pin", "").strip()
        if not (new_pin.isdigit() and len(new_pin) == 4):
            error = "PIN must be exactly 4 digits."
        elif new_pin != confirm_pin:
            error = "PINs do not match."
        else:
            clash = db.execute(
                "SELECT * FROM doctors WHERE pin = ? AND id != ?", (new_pin, doctor["id"])
            ).fetchone()
            if clash:
                error = "This PIN is already in use by another doctor."
            else:
                db.execute("UPDATE doctors SET pin = ? WHERE id = ?", (new_pin, doctor["id"]))
                db.commit()
                success = "PIN updated successfully."
                doctor = db.execute("SELECT * FROM doctors WHERE id = ?", (doctor["id"],)).fetchone()

    total_patients = db.execute("SELECT COUNT(*) AS c FROM patients").fetchone()["c"]
    total_records = db.execute(
        "SELECT COUNT(*) AS c FROM case_records WHERE doctor_name = ?", (doctor["name"],)
    ).fetchone()["c"]
    return render_template(
        "doctor_settings.html", doctor=doctor, error=error, success=success,
        total_patients=total_patients, total_records=total_records
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    total_patients = db.execute("SELECT COUNT(*) AS c FROM patients").fetchone()["c"]
    today = datetime.now().strftime("%Y-%m-%d")
    today_cases = db.execute(
        "SELECT COUNT(*) AS c FROM case_records WHERE visit_date LIKE ?",
        (f"{today}%",),
    ).fetchone()["c"]
    recent_patients = db.execute(
        "SELECT * FROM patients ORDER BY id DESC LIMIT 5"
    ).fetchall()
    pending_appointments = db.execute(
        """SELECT appointment_requests.*, patients.name AS patient_name, patients.patient_code
           FROM appointment_requests JOIN patients ON appointment_requests.patient_id = patients.id
           WHERE appointment_requests.doctor_id = ? AND appointment_requests.status = 'requested'
           ORDER BY appointment_requests.id DESC""",
        (session.get("doctor_id"),),
    ).fetchall()
    return render_template(
        "dashboard.html",
        total_patients=total_patients,
        today_cases=today_cases,
        doctor_name=session.get("doctor_name", "Doctor"),
        recent_patients=recent_patients,
        pending_appointments=pending_appointments,
    )


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------

@app.route("/patients")
@login_required
def patient_list():
    db = get_db()
    search = request.args.get("q", "").strip()
    if search:
        patients = db.execute(
            "SELECT * FROM patients WHERE name LIKE ? OR patient_code LIKE ? ORDER BY id DESC",
            (f"%{search}%", f"%{search}%"),
        ).fetchall()
    else:
        patients = db.execute("SELECT * FROM patients ORDER BY id DESC").fetchall()
    return render_template("patient_list.html", patients=patients, search=search)


def generate_patient_code(db):
    row = db.execute("SELECT COUNT(*) AS c FROM patients").fetchone()
    next_number = row["c"] + 1
    return f"AYU{next_number:04d}"


@app.route("/patients/new", methods=["GET", "POST"])
@login_required
def new_patient():
    if request.method == "POST":
        db = get_db()
        code = generate_patient_code(db)
        db.execute(
            """INSERT INTO patients (patient_code, name, age, gender, contact, address,
               emergency_contact, patient_pin, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                code,
                request.form.get("name"),
                request.form.get("age") or None,
                request.form.get("gender"),
                request.form.get("contact"),
                request.form.get("address"),
                request.form.get("emergency_contact"),
                request.form.get("patient_pin") or None,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        db.commit()
        flash(f"Patient registered successfully. Patient Code: {code}")
        return redirect(url_for("patient_profile", patient_code=code))
    return render_template("new_patient.html")


@app.route("/patients/<patient_code>")
@login_required
def patient_profile(patient_code):
    db = get_db()
    patient = db.execute(
        "SELECT * FROM patients WHERE patient_code = ?", (patient_code,)
    ).fetchone()
    if not patient:
        return "Patient not found", 404
    records = db.execute(
        "SELECT * FROM case_records WHERE patient_id = ? ORDER BY visit_date DESC",
        (patient["id"],),
    ).fetchall()
    pre_notes = db.execute(
        "SELECT * FROM pre_consultations WHERE patient_id = ? ORDER BY id DESC",
        (patient["id"],),
    ).fetchall()
    pending_edit = db.execute(
        "SELECT * FROM pending_edits WHERE patient_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
        (patient["id"],),
    ).fetchone()
    return render_template("patient_profile.html", patient=patient, records=records,
                           pre_notes=pre_notes, pending_edit=pending_edit)


@app.route("/patients/<patient_code>/request-edit", methods=["GET", "POST"])
@login_required
def request_edit(patient_code):
    db = get_db()
    patient = db.execute("SELECT * FROM patients WHERE patient_code = ?", (patient_code,)).fetchone()
    if not patient:
        return "Patient not found", 404

    if request.method == "POST":
        def changed(field, new_value):
            # Only store a value if it's actually different from the current one
            current = patient[field]
            if new_value and str(new_value) != str(current):
                return new_value
            return None

        db.execute(
            """INSERT INTO pending_edits (patient_id, requested_by, new_name, new_age, new_gender,
               new_contact, new_address, new_emergency_contact, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                patient["id"],
                session.get("doctor_name", "Doctor"),
                changed("name", request.form.get("name")),
                changed("age", request.form.get("age")),
                changed("gender", request.form.get("gender")),
                changed("contact", request.form.get("contact")),
                changed("address", request.form.get("address")),
                changed("emergency_contact", request.form.get("emergency_contact")),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        db.commit()
        flash("Edit request sent. The patient must approve it before changes are applied.")
        return redirect(url_for("patient_profile", patient_code=patient_code))

    return render_template("request_edit.html", patient=patient)


# ---------------------------------------------------------------------------
# Patient side (read-only "My Records" view)
# ---------------------------------------------------------------------------

@app.route("/patient-login", methods=["GET", "POST"])
def patient_login():
    error = None
    if request.method == "POST":
        code = request.form.get("patient_code", "").strip().upper()
        pin_entered = request.form.get("patient_pin", "").strip()
        db = get_db()
        patient = db.execute(
            "SELECT * FROM patients WHERE patient_code = ?", (code,)
        ).fetchone()
        if not patient:
            error = "Patient Code not found. Please check with your doctor's clinic."
        elif patient["patient_pin"] and patient["patient_pin"] != pin_entered:
            error = "Incorrect PIN for this Patient Code."
        else:
            return redirect(url_for("patient_home", patient_code=code))
    return render_template("patient_login.html", error=error)


@app.route("/patient-register", methods=["GET", "POST"])
def patient_register():
    if request.method == "POST":
        db = get_db()
        code = generate_patient_code(db)
        db.execute(
            """INSERT INTO patients (patient_code, name, age, gender, contact, address,
               emergency_contact, patient_pin, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                code,
                request.form.get("name"),
                request.form.get("age") or None,
                request.form.get("gender"),
                request.form.get("contact"),
                request.form.get("address"),
                request.form.get("emergency_contact"),
                request.form.get("patient_pin") or None,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        db.commit()
        flash(f"Registration successful! Your Patient Code is {code} - save this to log in next time.")
        return redirect(url_for("patient_home", patient_code=code))
    return render_template("patient_register.html")


@app.route("/my-records/<patient_code>")
def patient_home(patient_code):
    db = get_db()
    patient = db.execute(
        "SELECT * FROM patients WHERE patient_code = ?", (patient_code,)
    ).fetchone()
    if not patient:
        return "Patient not found", 404
    records = db.execute(
        "SELECT * FROM case_records WHERE patient_id = ? ORDER BY visit_date DESC",
        (patient["id"],),
    ).fetchall()
    pending_edit = db.execute(
        "SELECT * FROM pending_edits WHERE patient_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
        (patient["id"],),
    ).fetchone()
    appointments = db.execute(
        """SELECT appointment_requests.*, doctors.name AS doctor_name
           FROM appointment_requests JOIN doctors ON appointment_requests.doctor_id = doctors.id
           WHERE patient_id = ? ORDER BY appointment_requests.id DESC""",
        (patient["id"],),
    ).fetchall()
    return render_template("patient_home.html", patient=patient, records=records,
                           patient_nav_code=patient["patient_code"], patient_nav_name=patient["name"],
                           pending_edit=pending_edit, appointments=appointments)


@app.route("/my-records/<patient_code>/report/<int:record_id>")
def patient_view_record(patient_code, record_id):
    db = get_db()
    patient = db.execute(
        "SELECT * FROM patients WHERE patient_code = ?", (patient_code,)
    ).fetchone()
    record = db.execute(
        "SELECT * FROM case_records WHERE id = ? AND patient_id = ?",
        (record_id, patient["id"] if patient else -1),
    ).fetchone()
    if not patient or not record:
        return "Record not found", 404
    return render_template("view_record.html", record=record, patient=patient, patient_side=True,
                           patient_nav_code=patient["patient_code"], patient_nav_name=patient["name"])


@app.route("/my-records/<patient_code>/settings")
def patient_settings(patient_code):
    db = get_db()
    patient = db.execute(
        "SELECT * FROM patients WHERE patient_code = ?", (patient_code,)
    ).fetchone()
    if not patient:
        return "Patient not found", 404
    record_count = db.execute(
        "SELECT COUNT(*) AS c FROM case_records WHERE patient_id = ?", (patient["id"],)
    ).fetchone()["c"]
    return render_template("patient_settings.html", patient=patient, record_count=record_count,
                           patient_nav_code=patient["patient_code"], patient_nav_name=patient["name"])


@app.route("/my-records/<patient_code>/edit-request/<int:edit_id>/<action>", methods=["POST"])
def respond_to_edit(patient_code, edit_id, action):
    db = get_db()
    patient = db.execute("SELECT * FROM patients WHERE patient_code = ?", (patient_code,)).fetchone()
    edit_req = db.execute(
        "SELECT * FROM pending_edits WHERE id = ? AND patient_id = ?", (edit_id, patient["id"] if patient else -1)
    ).fetchone()
    if not patient or not edit_req:
        return "Not found", 404

    if action == "approve":
        updates = {}
        if edit_req["new_name"]: updates["name"] = edit_req["new_name"]
        if edit_req["new_age"] is not None: updates["age"] = edit_req["new_age"]
        if edit_req["new_gender"]: updates["gender"] = edit_req["new_gender"]
        if edit_req["new_contact"]: updates["contact"] = edit_req["new_contact"]
        if edit_req["new_address"]: updates["address"] = edit_req["new_address"]
        if edit_req["new_emergency_contact"]: updates["emergency_contact"] = edit_req["new_emergency_contact"]

        for field, value in updates.items():
            db.execute(f"UPDATE patients SET {field} = ? WHERE id = ?", (value, patient["id"]))
        db.execute("UPDATE pending_edits SET status = 'approved' WHERE id = ?", (edit_id,))
        db.commit()
        flash("Update approved and applied to your profile.")
    else:
        db.execute("UPDATE pending_edits SET status = 'rejected' WHERE id = ?", (edit_id,))
        db.commit()
        flash("Update request rejected.")

    return redirect(url_for("patient_home", patient_code=patient_code))


@app.route("/my-records/<patient_code>/pre-consult", methods=["GET", "POST"])
def pre_consult(patient_code):
    db = get_db()
    patient = db.execute("SELECT * FROM patients WHERE patient_code = ?", (patient_code,)).fetchone()
    if not patient:
        return "Patient not found", 404
    if request.method == "POST":
        db.execute(
            "INSERT INTO pre_consultations (patient_id, notes, created_at) VALUES (?,?,?)",
            (patient["id"], request.form.get("notes"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        db.commit()
        flash("Your notes have been shared with your doctor for your next visit.")
        return redirect(url_for("patient_home", patient_code=patient_code))
    return render_template("pre_consult.html", patient=patient,
                           patient_nav_code=patient["patient_code"], patient_nav_name=patient["name"])


@app.route("/my-records/<patient_code>/doctors")
def doctors_list(patient_code):
    db = get_db()
    patient = db.execute("SELECT * FROM patients WHERE patient_code = ?", (patient_code,)).fetchone()
    if not patient:
        return "Patient not found", 404
    search = request.args.get("q", "").strip()
    if search:
        doctors = db.execute("SELECT * FROM doctors WHERE name LIKE ?", (f"%{search}%",)).fetchall()
    else:
        doctors = db.execute("SELECT * FROM doctors ORDER BY name").fetchall()
    return render_template("doctors_list.html", patient=patient, doctors=doctors, search=search,
                           patient_nav_code=patient["patient_code"], patient_nav_name=patient["name"])


@app.route("/my-records/<patient_code>/doctors/<int:doctor_id>/book", methods=["GET", "POST"])
def book_appointment(patient_code, doctor_id):
    db = get_db()
    patient = db.execute("SELECT * FROM patients WHERE patient_code = ?", (patient_code,)).fetchone()
    doctor = db.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()
    if not patient or not doctor:
        return "Not found", 404
    if request.method == "POST":
        db.execute(
            """INSERT INTO appointment_requests (patient_id, doctor_id, preferred_date, reason, created_at)
               VALUES (?,?,?,?,?)""",
            (patient["id"], doctor_id, request.form.get("preferred_date"), request.form.get("reason"),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        db.commit()
        flash(f"Visit request sent to {doctor['name']}. You'll pay at the hospital at the time of your visit.")
        return redirect(url_for("patient_home", patient_code=patient_code))
    return render_template("book_appointment.html", patient=patient, doctor=doctor,
                           patient_nav_code=patient["patient_code"], patient_nav_name=patient["name"])


@app.route("/appointment-requests/<int:req_id>/<action>", methods=["POST"])
@login_required
def respond_to_appointment(req_id, action):
    db = get_db()
    new_status = "confirmed" if action == "confirm" else "declined"
    db.execute("UPDATE appointment_requests SET status = ? WHERE id = ?", (new_status, req_id))
    db.commit()
    flash(f"Appointment request {new_status}.")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Case-taking form
# ---------------------------------------------------------------------------

@app.route("/patients/<patient_code>/case/new", methods=["GET", "POST"])
@login_required
def new_case(patient_code):
    db = get_db()
    patient = db.execute(
        "SELECT * FROM patients WHERE patient_code = ?", (patient_code,)
    ).fetchone()
    if not patient:
        return "Patient not found", 404

    if request.method == "POST":
        db.execute(
            """INSERT INTO case_records (
                patient_id, doctor_name, visit_date, chief_complaints, history_illness, family_history,
                current_medicines, previous_medicines, dosha_assessment,
                nidan_cause, nidan_early_signs, nidan_symptoms, nidan_examination,
                diagnosis, additional_notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                patient["id"],
                session.get("doctor_name", "Doctor"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                request.form.get("chief_complaints"),
                request.form.get("history_illness"),
                request.form.get("family_history"),
                request.form.get("current_medicines"),
                request.form.get("previous_medicines"),
                request.form.get("dosha_assessment"),
                request.form.get("nidan_cause"),
                request.form.get("nidan_early_signs"),
                request.form.get("nidan_symptoms"),
                request.form.get("nidan_examination"),
                request.form.get("diagnosis"),
                request.form.get("additional_notes"),
            ),
        )
        db.commit()
        flash("Case record saved successfully.")
        return redirect(url_for("patient_profile", patient_code=patient_code))

    return render_template("case_form.html", patient=patient)


@app.route("/records/<int:record_id>")
@login_required
def view_record(record_id):
    db = get_db()
    record = db.execute(
        "SELECT * FROM case_records WHERE id = ?", (record_id,)
    ).fetchone()
    if not record:
        return "Record not found", 404
    patient = db.execute(
        "SELECT * FROM patients WHERE id = ?", (record["patient_id"],)
    ).fetchone()
    return render_template("view_record.html", record=record, patient=patient)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        init_db()
    else:
        init_db()  # safe: uses CREATE TABLE IF NOT EXISTS
    app.run(debug=True)
