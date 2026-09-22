"""
app.py — College Portal, fully in Python.

This single Flask app replaces:
  - backend/server.js + backend/db.js  -> the JSON API (routes prefixed /api/*)
  - frontend/index.html + frontend/js/app.js -> server-rendered pages using
    Jinja2 templates instead of a client-side JS SPA.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://localhost:5000/
"""

import os
import time
import random
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify
)

import db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

PORT = int(os.environ.get("PORT", 5000))


# ---------------------------------------------------------------------------
# Helpers shared by pages & API
# ---------------------------------------------------------------------------
def find_user_by_login(username, role=None):
    """Mirrors the fuzzy matching logic in the original /api/auth/login."""
    store = db.get_store()
    search = (username or "").strip().lower()

    matched_student = None
    matched_faculty = None

    if role == "student" or not role:
        for s in store["students"]:
            if (s["roll_number"].lower() == search or s["email"].lower() == search or
                    s["full_name"].lower() == search or search in s["full_name"].lower()):
                matched_student = s
                break

    if role == "faculty" or not role:
        for f in store["faculty"]:
            if (f["employee_id"].lower() == search or f["email"].lower() == search or
                    f["full_name"].lower() == search or search in f["full_name"].lower()):
                matched_faculty = f
                break

    user = None
    if matched_student:
        user = next((u for u in store["users"] if u["id"] == matched_student["user_id"]), None) or {
            "id": matched_student["id"] + 10,
            "username": matched_student["email"].split("@")[0],
            "email": matched_student["email"],
            "role": "student",
            "full_name": matched_student["full_name"],
            "avatar_url": matched_student.get("avatar_url"),
        }
    elif matched_faculty:
        user = next((u for u in store["users"] if u["id"] == matched_faculty["user_id"]), None) or {
            "id": matched_faculty["id"] + 20,
            "username": matched_faculty["email"].split("@")[0],
            "email": matched_faculty["email"],
            "role": "faculty",
            "full_name": matched_faculty["full_name"],
            "avatar_url": matched_faculty.get("avatar_url"),
        }
    else:
        for u in store["users"]:
            if (u["username"].lower() == search or u["email"].lower() == search or
                    (role and u["role"] == role.lower())):
                user = u
                break

    if not user:
        return None, None

    profile = None
    if user["role"] == "student":
        profile = (matched_student or
                   next((s for s in store["students"] if s.get("user_id") == user["id"]), None) or
                   next((s for s in store["students"] if s["email"].lower() == user["email"].lower()), None) or
                   store["students"][0])
    elif user["role"] == "faculty":
        profile = (matched_faculty or
                   next((f for f in store["faculty"] if f.get("user_id") == user["id"]), None) or
                   next((f for f in store["faculty"] if f["email"].lower() == user["email"].lower()), None) or
                   store["faculty"][0])

    return user, profile


def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user" not in session:
                flash("Please log in to continue.", "error")
                return redirect(url_for("login"))
            if role and session["user"]["role"] != role:
                flash("You do not have access to that page.", "error")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@app.context_processor
def inject_globals():
    return {"current_user": session.get("user"), "now": datetime.now()}


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    store = db.get_store()
    return render_template(
        "index.html",
        courses=store["courses"],
        events=store["events"],
        announcements=store["announcements"][:3],
    )


@app.route("/courses")
def courses():
    store = db.get_store()
    return render_template("courses.html", courses=store["courses"])


@app.route("/events", methods=["GET"])
def events():
    store = db.get_store()
    return render_template("events.html", events=store["events"])


@app.route("/events/<int:event_id>/register", methods=["POST"])
def event_register(event_id):
    store = db.get_store()
    event = next((e for e in store["events"] if e["id"] == event_id), None)
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("events"))
    event["registered"] = not event["registered"]
    event["registration_count"] += 1 if event["registered"] else -1
    flash(
        f"Registered for {event['title']}!" if event["registered"]
        else f"Cancelled registration for {event['title']}.",
        "success",
    )
    return redirect(url_for("events"))


@app.route("/announcements")
def announcements():
    store = db.get_store()
    category = request.args.get("category", "all")
    data = store["announcements"]
    if category and category.lower() != "all":
        data = [a for a in data if a["category"].lower() == category.lower()]
    categories = sorted({a["category"] for a in store["announcements"]})
    return render_template("announcements.html", announcements=data, categories=categories,
                            active_category=category)


# ---------------------------------------------------------------------------
# Auth pages
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        store = db.get_store()
        return render_template("login.html", students=store["students"], faculty=store["faculty"])

    username = request.form.get("username", "")
    role = request.form.get("role", "")

    user, profile = find_user_by_login(username, role)
    if not user:
        flash("Invalid credentials. User not found.", "error")
        return redirect(url_for("login"))

    session["user"] = {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "full_name": user["full_name"],
        "avatar_url": user.get("avatar_url"),
    }
    # Remember which student/faculty record this session maps to
    if user["role"] == "student" and profile:
        session["student_id"] = profile["id"]
    if user["role"] == "faculty" and profile:
        session["faculty_id"] = profile["id"]

    flash(f"Welcome back, {user['full_name']}!", "success")
    return redirect(url_for("dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    full_name = request.form.get("full_name")
    email = request.form.get("email")
    role = request.form.get("role")
    department = request.form.get("department")
    roll_number = request.form.get("roll_number")
    password = request.form.get("password") or "password123"

    if not email or not full_name or not role:
        flash("Missing required registration fields.", "error")
        return redirect(url_for("register"))

    store = db.get_store()
    if any(u["email"] == email for u in store["users"]):
        flash("An account with this email already exists.", "error")
        return redirect(url_for("register"))

    new_user_id = len(store["users"]) + 1
    new_user = {
        "id": new_user_id,
        "username": email.split("@")[0],
        "email": email,
        "password": password,
        "role": role.lower(),
        "full_name": full_name,
        "avatar_url": "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=256&q=80",
    }
    store["users"].append(new_user)

    if new_user["role"] == "student":
        store["students"].append({
            "id": len(store["students"]) + 1,
            "user_id": new_user_id,
            "full_name": full_name,
            "email": email,
            "roll_number": roll_number or f"APX-2024-{random.randint(100, 999)}",
            "department": department or "Computer Science & Engineering",
            "semester": 1,
            "batch_year": "2024-2028",
            "overall_attendance": 100.0,
            "cgpa": 0.0,
            "mentor_name": "Dr. Robert Vance",
            "status": "Active",
        })

    flash("Registration successful! You can now log in.", "success")
    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Dashboard router
# ---------------------------------------------------------------------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    role = session["user"]["role"]
    if role == "student":
        return redirect(url_for("student_dashboard"))
    if role == "faculty":
        return redirect(url_for("faculty_dashboard"))
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Student pages
# ---------------------------------------------------------------------------
def _get_current_student():
    store = db.get_store()
    sid = session.get("student_id")
    student = next((s for s in store["students"] if s["id"] == sid), None)
    return student or store["students"][0]


@app.route("/student")
@login_required(role="student")
def student_dashboard():
    store = db.get_store()
    student = _get_current_student()
    attendance = [a for a in store["attendance"] if a["student_id"] == student["id"]] or store["attendance"][:3]
    marks = [m for m in store["marks"] if m["student_id"] == student["id"]] or store["marks"][:3]
    assignments = [a for a in store["assignments"]
                   if a.get("student_id") == student["id"] or a.get("student_id") == 1] or store["assignments"]
    return render_template(
        "student_dashboard.html",
        student=student, attendance=attendance, marks=marks,
        assignments=assignments, exams=store["exams"], timetable=store["timetable"],
    )


@app.route("/student/assignments/<int:assignment_id>/submit", methods=["POST"])
@login_required(role="student")
def student_submit_assignment(assignment_id):
    store = db.get_store()
    assignment = next((a for a in store["assignments"] if a["id"] == assignment_id), None)
    if assignment:
        assignment["status"] = "Submitted"
        flash("Assignment submitted successfully!", "success")
    else:
        flash("Assignment not found.", "error")
    return redirect(url_for("student_dashboard"))


# ---------------------------------------------------------------------------
# Faculty pages
# ---------------------------------------------------------------------------
def _get_current_faculty():
    store = db.get_store()
    fid = session.get("faculty_id")
    faculty = next((f for f in store["faculty"] if f["id"] == fid), None)
    return faculty or store["faculty"][0]


@app.route("/faculty")
@login_required(role="faculty")
def faculty_dashboard():
    store = db.get_store()
    faculty = _get_current_faculty()
    courses = [c for c in store["courses"]
               if c["course_code"] in (faculty.get("courses") or []) or faculty["full_name"] in c["instructor"]]
    if not courses:
        courses = [store["courses"][0]]
    return render_template(
        "faculty_dashboard.html",
        faculty=faculty, courses=courses, students=store["students"],
        assignments=store["assignments"], announcements=store["announcements"][:5],
    )


@app.route("/faculty/assignments", methods=["POST"])
@login_required(role="faculty")
def faculty_add_assignment():
    store = db.get_store()
    new_assignment = {
        "id": len(store["assignments"]) + 1,
        "course_code": request.form.get("course_code") or "CS601",
        "title": request.form.get("title") or "New Assignment",
        "description": request.form.get("description") or "Assignment instructions and deliverables.",
        "due_date": request.form.get("due_date") or "2026-10-15",
        "max_score": int(request.form.get("max_score") or 50),
        "score": None,
        "status": "Pending",
    }
    store["assignments"].append(new_assignment)
    flash("Assignment uploaded successfully.", "success")
    return redirect(url_for("faculty_dashboard"))


@app.route("/faculty/marks/<int:mark_id>", methods=["POST"])
@login_required(role="faculty")
def faculty_update_marks(mark_id):
    store = db.get_store()
    mark = next((m for m in store["marks"] if m["id"] == mark_id), None)
    if not mark:
        flash("Marks record not found.", "error")
        return redirect(url_for("faculty_dashboard"))

    for field in ("internal", "midterm", "assignment"):
        val = request.form.get(field)
        if val not in (None, ""):
            mark[field] = float(val)
    mark["total"] = round(mark["internal"] + mark["midterm"] + mark["assignment"], 1)
    mark["grade"] = ("A+" if mark["total"] >= 90 else
                      "A" if mark["total"] >= 80 else
                      "B" if mark["total"] >= 70 else "C")
    flash("Marks updated successfully.", "success")
    return redirect(url_for("faculty_dashboard"))


@app.route("/faculty/attendance/<int:course_id>/mark", methods=["POST"])
@login_required(role="faculty")
def faculty_mark_attendance(course_id):
    store = db.get_store()
    attended = request.form.get("attended") == "on"
    item = next((a for a in store["attendance"] if a["course_id"] == course_id), None) or store["attendance"][0]
    item["total_classes"] += 1
    if attended:
        item["attended_classes"] += 1
    item["percentage"] = round((item["attended_classes"] / item["total_classes"]) * 100, 1)
    flash("Attendance updated successfully.", "success")
    return redirect(url_for("faculty_dashboard"))


# ---------------------------------------------------------------------------
# Admin pages
# ---------------------------------------------------------------------------
@app.route("/admin")
@login_required(role="admin")
def admin_dashboard():
    store = db.get_store()
    telemetry = db.get_container_status()
    metrics = {
        "total_students": 5420,
        "total_faculty": 264,
        "total_courses": 58,
        "total_events": 112,
        "active_sessions": 418,
        "system_uptime": "99.98%",
    }
    return render_template(
        "admin_dashboard.html",
        students=store["students"], faculty=store["faculty"],
        announcements=store["announcements"], metrics=metrics, telemetry=telemetry,
    )


@app.route("/admin/students", methods=["POST"])
@login_required(role="admin")
def admin_add_student():
    store = db.get_store()
    new_student = {
        "id": len(store["students"]) + 1,
        "user_id": None,
        "full_name": request.form.get("full_name") or "New Student",
        "email": request.form.get("email") or f"student_{int(time.time())}@apex.edu",
        "roll_number": request.form.get("roll_number") or f"APX-2024-{random.randint(100, 999)}",
        "department": request.form.get("department") or "Computer Science & Engineering",
        "semester": int(request.form.get("semester") or 1),
        "batch_year": "2024-2028",
        "overall_attendance": 85.0,
        "cgpa": float(request.form.get("cgpa") or 8.5),
        "mentor_name": "Dr. Robert Vance",
        "status": "Active",
    }
    store["students"].append(new_student)
    flash("Student added successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/students/<int:student_id>/delete", methods=["POST"])
@login_required(role="admin")
def admin_delete_student(student_id):
    store = db.get_store()
    store["students"] = [s for s in store["students"] if s["id"] != student_id]
    flash("Student deleted successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/announcements", methods=["POST"])
@login_required(role="admin")
def admin_add_announcement():
    store = db.get_store()
    new_ann = {
        "id": len(store["announcements"]) + 1,
        "title": request.form.get("title") or "University Announcement",
        "category": request.form.get("category") or "Academic",
        "content": request.form.get("content") or "Important notice for university students and staff.",
        "priority": request.form.get("priority") or "Normal",
        "date_posted": f"{datetime.now():%B} {datetime.now().day}, {datetime.now():%Y}",
        "author": "Academic Administration",
    }
    store["announcements"].insert(0, new_ann)
    flash("Announcement broadcasted successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/announcements/<int:ann_id>/delete", methods=["POST"])
@login_required(role="admin")
def admin_delete_announcement(ann_id):
    store = db.get_store()
    store["announcements"] = [a for a in store["announcements"] if a["id"] != ann_id]
    flash("Announcement deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/containers/<tier>/simulate", methods=["POST"])
@login_required(role="admin")
def admin_simulate_container(tier):
    action = request.form.get("action", "restart")
    ok = db.simulate_action(tier, action)
    if ok:
        flash(f"Simulated '{action}' on {tier} container initiated successfully.", "success")
    else:
        flash("Invalid tier or action specified.", "error")
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# JSON API — kept for parity with the original Node/Express backend
# (used by Docker healthchecks, and available for programmatic access)
# ---------------------------------------------------------------------------
@app.route("/api/health")
def api_health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "college-portal-backend",
        "version": "1.0.0",
        "uptime_seconds": time.time() - db._start_time,
        "database_status": "connected",
        "database_mode": db.get_db_mode(),
    })


@app.route("/api/container-status")
def api_container_status():
    return jsonify({"success": True, "data": db.get_container_status()})


@app.route("/api/container/simulate", methods=["POST"])
def api_simulate_container():
    body = request.get_json(silent=True) or {}
    ok = db.simulate_action(body.get("tier"), body.get("action"))
    if ok:
        return jsonify({"success": True,
                         "message": f"Simulated '{body.get('action')}' on {body.get('tier')} container initiated successfully."})
    return jsonify({"success": False, "message": "Invalid tier or action specified."}), 400


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    body = request.get_json(silent=True) or {}
    user, profile = find_user_by_login(body.get("username"), body.get("role"))
    if not user:
        return jsonify({"success": False, "message": "Invalid credentials. User not found."}), 401
    token = f"token_{user['role']}_{user['id']}_{int(time.time() * 1000)}"
    return jsonify({
        "success": True, "token": token,
        "user": {
            "id": user["id"], "username": user["username"], "email": user["email"],
            "role": user["role"], "full_name": user["full_name"],
            "avatar_url": user.get("avatar_url"), "profile": profile,
        },
    })


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    body = request.get_json(silent=True) or {}
    full_name, email, role = body.get("full_name"), body.get("email"), body.get("role")
    if not email or not full_name or not role:
        return jsonify({"success": False, "message": "Missing required registration fields."}), 400

    store = db.get_store()
    if any(u["email"] == email for u in store["users"]):
        return jsonify({"success": False, "message": "An account with this email already exists."}), 400

    new_user_id = len(store["users"]) + 1
    new_user = {
        "id": new_user_id, "username": email.split("@")[0], "email": email,
        "password": body.get("password") or "password123", "role": role.lower(),
        "full_name": full_name,
        "avatar_url": "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=256&q=80",
    }
    store["users"].append(new_user)
    if new_user["role"] == "student":
        store["students"].append({
            "id": len(store["students"]) + 1, "user_id": new_user_id, "full_name": full_name, "email": email,
            "roll_number": body.get("roll_number") or f"APX-2024-{random.randint(100, 999)}",
            "department": body.get("department") or "Computer Science & Engineering",
            "semester": 1, "batch_year": "2024-2028", "overall_attendance": 100.0, "cgpa": 0.0,
            "mentor_name": "Dr. Robert Vance", "status": "Active",
        })
    return jsonify({"success": True, "message": "Registration successful! You can now log in.", "user": new_user}), 201


@app.route("/api/students", methods=["GET", "POST"])
def api_students():
    store = db.get_store()
    if request.method == "GET":
        return jsonify({"success": True, "count": len(store["students"]), "data": store["students"]})
    body = request.get_json(silent=True) or {}
    new_student = {
        "id": len(store["students"]) + 1, "user_id": None,
        "full_name": body.get("full_name") or "New Student",
        "email": body.get("email") or f"student_{int(time.time()*1000)}@apex.edu",
        "roll_number": body.get("roll_number") or f"APX-2024-{random.randint(100, 999)}",
        "department": body.get("department") or "Computer Science & Engineering",
        "semester": int(body.get("semester") or 1), "batch_year": "2024-2028",
        "overall_attendance": 85.0, "cgpa": float(body.get("cgpa") or 8.5),
        "mentor_name": "Dr. Robert Vance", "status": "Active",
    }
    store["students"].append(new_student)
    return jsonify({"success": True, "message": "Student added successfully.", "data": new_student}), 201


@app.route("/api/students/<int:student_id>", methods=["GET", "DELETE"])
def api_student_detail(student_id):
    store = db.get_store()
    if request.method == "DELETE":
        before = len(store["students"])
        store["students"] = [s for s in store["students"] if s["id"] != student_id]
        if len(store["students"]) < before:
            return jsonify({"success": True, "message": "Student deleted successfully."})
        return jsonify({"success": False, "message": "Student not found."}), 404
    student = next((s for s in store["students"] if s["id"] == student_id), None)
    if student:
        return jsonify({"success": True, "data": student})
    return jsonify({"success": False, "message": "Student not found."}), 404


@app.route("/api/students/<int:student_id>/details")
def api_student_details(student_id):
    store = db.get_store()
    student = next((s for s in store["students"] if s["id"] == student_id), None)
    if not student:
        return jsonify({"success": False, "message": "Student not found."}), 404
    attendance = [a for a in store["attendance"] if a["student_id"] == student_id]
    marks = [m for m in store["marks"] if m["student_id"] == student_id]
    assignments = [a for a in store["assignments"] if a.get("student_id") in (student_id, 1)]
    return jsonify({
        "success": True,
        "data": {
            "student": student,
            "attendance": attendance or store["attendance"][:3],
            "marks": marks or store["marks"][:3],
            "assignments": assignments or store["assignments"],
            "exams": store["exams"],
        },
    })


@app.route("/api/faculty")
def api_faculty():
    store = db.get_store()
    return jsonify({"success": True, "count": len(store["faculty"]), "data": store["faculty"]})


@app.route("/api/faculty/<int:faculty_id>")
def api_faculty_detail(faculty_id):
    store = db.get_store()
    f = next((fac for fac in store["faculty"] if fac["id"] == faculty_id), None)
    if f:
        return jsonify({"success": True, "data": f})
    return jsonify({"success": False, "message": "Faculty member not found."}), 404


@app.route("/api/faculty/<int:faculty_id>/details")
def api_faculty_details(faculty_id):
    store = db.get_store()
    f = next((fac for fac in store["faculty"] if fac["id"] == faculty_id), None)
    if not f:
        return jsonify({"success": False, "message": "Faculty not found."}), 404
    courses = [c for c in store["courses"]
               if c["course_code"] in (f.get("courses") or []) or f["full_name"] in c["instructor"]]
    return jsonify({
        "success": True,
        "data": {
            "faculty": f,
            "courses": courses if courses else [store["courses"][0]],
            "students": store["students"],
        },
    })


@app.route("/api/courses")
def api_courses():
    store = db.get_store()
    return jsonify({"success": True, "count": len(store["courses"]), "data": store["courses"]})


@app.route("/api/attendance")
def api_attendance():
    return jsonify({"success": True, "data": db.get_store()["attendance"]})


@app.route("/api/attendance/mark", methods=["POST"])
def api_mark_attendance():
    body = request.get_json(silent=True) or {}
    store = db.get_store()
    course_id = int(body.get("course_id")) if body.get("course_id") is not None else None
    item = next((a for a in store["attendance"] if a["course_id"] == course_id), None) or store["attendance"][0]
    item["total_classes"] += 1
    if body.get("attended"):
        item["attended_classes"] += 1
    item["percentage"] = round((item["attended_classes"] / item["total_classes"]) * 100, 1)
    return jsonify({"success": True, "message": "Attendance updated successfully.", "data": item})


@app.route("/api/marks")
def api_marks():
    return jsonify({"success": True, "data": db.get_store()["marks"]})


@app.route("/api/marks/update", methods=["POST"])
def api_update_marks():
    body = request.get_json(silent=True) or {}
    store = db.get_store()
    mark = next((m for m in store["marks"] if m["id"] == int(body.get("id"))), None)
    if not mark:
        return jsonify({"success": False, "message": "Marks record not found."}), 404
    for field in ("internal", "midterm", "assignment"):
        if body.get(field) is not None:
            mark[field] = float(body[field])
    mark["total"] = round(mark["internal"] + mark["midterm"] + mark["assignment"], 1)
    mark["grade"] = ("A+" if mark["total"] >= 90 else
                      "A" if mark["total"] >= 80 else
                      "B" if mark["total"] >= 70 else "C")
    return jsonify({"success": True, "message": "Marks updated successfully.", "data": mark})


@app.route("/api/timetable")
def api_timetable():
    return jsonify({"success": True, "data": db.get_store()["timetable"]})


@app.route("/api/assignments", methods=["GET", "POST"])
def api_assignments():
    store = db.get_store()
    if request.method == "GET":
        return jsonify({"success": True, "data": store["assignments"]})
    body = request.get_json(silent=True) or {}
    new_assignment = {
        "id": len(store["assignments"]) + 1,
        "course_code": body.get("course_code") or "CS601",
        "title": body.get("title") or "New Assignment",
        "description": body.get("description") or "Assignment instructions and deliverables.",
        "due_date": body.get("due_date") or "2026-10-15",
        "max_score": int(body.get("max_score") or 50),
        "score": None, "status": "Pending",
    }
    store["assignments"].append(new_assignment)
    return jsonify({"success": True, "message": "Assignment uploaded successfully.", "data": new_assignment}), 201


@app.route("/api/assignments/<int:assignment_id>/submit", methods=["POST"])
def api_submit_assignment(assignment_id):
    store = db.get_store()
    assignment = next((a for a in store["assignments"] if a["id"] == assignment_id), None)
    if assignment:
        assignment["status"] = "Submitted"
        return jsonify({"success": True, "message": "Assignment submitted successfully!", "data": assignment})
    return jsonify({"success": False, "message": "Assignment not found."}), 404


@app.route("/api/exams")
def api_exams():
    return jsonify({"success": True, "data": db.get_store()["exams"]})


@app.route("/api/events")
def api_events():
    store = db.get_store()
    return jsonify({"success": True, "count": len(store["events"]), "data": store["events"]})


@app.route("/api/events/<int:event_id>/register", methods=["POST"])
def api_event_register(event_id):
    store = db.get_store()
    event = next((e for e in store["events"] if e["id"] == event_id), None)
    if not event:
        return jsonify({"success": False, "message": "Event not found."}), 404
    event["registered"] = not event["registered"]
    event["registration_count"] += 1 if event["registered"] else -1
    return jsonify({
        "success": True,
        "message": (f"Registered for {event['title']}!" if event["registered"]
                     else f"Cancelled registration for {event['title']}."),
        "registered": event["registered"],
        "registration_count": event["registration_count"],
    })


@app.route("/api/announcements", methods=["GET", "POST"])
def api_announcements():
    store = db.get_store()
    if request.method == "GET":
        category = request.args.get("category")
        data = store["announcements"]
        if category and category.lower() != "all":
            data = [a for a in data if a["category"].lower() == category.lower()]
        return jsonify({"success": True, "count": len(data), "data": data})
    body = request.get_json(silent=True) or {}
    new_ann = {
        "id": len(store["announcements"]) + 1,
        "title": body.get("title") or "University Announcement",
        "category": body.get("category") or "Academic",
        "content": body.get("content") or "Important notice for university students and staff.",
        "priority": body.get("priority") or "Normal",
        "date_posted": datetime.now().strftime("%B %d, %Y"),
        "author": "Academic Administration",
    }
    store["announcements"].insert(0, new_ann)
    return jsonify({"success": True, "message": "Announcement broadcasted successfully.", "data": new_ann}), 201


@app.route("/api/announcements/<int:ann_id>", methods=["DELETE"])
def api_delete_announcement(ann_id):
    store = db.get_store()
    before = len(store["announcements"])
    store["announcements"] = [a for a in store["announcements"] if a["id"] != ann_id]
    if len(store["announcements"]) < before:
        return jsonify({"success": True, "message": "Announcement deleted."})
    return jsonify({"success": False, "message": "Announcement not found."}), 404


@app.route("/api/admin/metrics")
def api_admin_metrics():
    telemetry = db.get_container_status()
    return jsonify({
        "success": True,
        "metrics": {
            "total_students": 5420, "total_faculty": 264, "total_courses": 58,
            "total_events": 112, "active_sessions": 418, "system_uptime": "99.98%",
            "containers": {
                "frontend": telemetry["frontend"]["status"],
                "backend": telemetry["backend"]["status"],
                "database": telemetry["database"]["status"],
            },
        },
    })


if __name__ == "__main__":
    print(f"""
  =============================================================
  College Portal Backend (Python/Flask) Active
  -------------------------------------------------------------
  Port:        {PORT}
  Health URL:  http://localhost:{PORT}/api/health
  Telemetry:   http://localhost:{PORT}/api/container-status
  Portal UI:   http://localhost:{PORT}/
  =============================================================
  """)
    app.run(host="0.0.0.0", port=PORT, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
