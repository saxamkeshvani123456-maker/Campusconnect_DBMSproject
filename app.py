from __future__ import annotations

import os
import sqlite3
from functools import wraps
from pathlib import Path
from datetime import datetime, timedelta

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.environ.get("CAMPUSCONNECT_DB", str(INSTANCE_DIR / "campusconnect.db")))
if not DB_PATH.is_absolute():
    DB_PATH = BASE_DIR / DB_PATH

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("CAMPUSCONNECT_SECRET", "dev-only-change-this-secret")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect_db()
    return g.db


@app.teardown_appcontext
def close_db(_error=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    schema = (BASE_DIR / "sql" / "schema_sqlite.sql").read_text(encoding="utf-8")
    with connect_db() as db:
        db.executescript(schema)
        admin_email = "admin@campusconnect.local"
        admin = db.execute("SELECT user_id FROM users WHERE email = ?", (admin_email,)).fetchone()
        if not admin:
            cursor = db.execute(
                "INSERT INTO users (full_name, email, password_hash, department, study_year, role) VALUES (?, ?, ?, ?, ?, ?)",
                ("Campus Administrator", admin_email, generate_password_hash("Admin@123"), "Administration", 2, "admin"),
            )
            admin_id = cursor.lastrowid
        else:
            admin_id = admin["user_id"]

        club_count = db.execute("SELECT COUNT(*) AS n FROM clubs").fetchone()["n"]
        if club_count == 0:
            clubs = [
                ("Coding Club", "Technology", "Build software, solve problems, and learn from fellow developers."),
                ("Cultural Collective", "Culture", "Celebrate music, dance, theatre, art, and campus traditions."),
                ("Eco Campus", "Community", "Organise sustainability drives and make campus life greener."),
            ]
            db.executemany("INSERT INTO clubs (name, category, description, created_by) VALUES (?, ?, ?, ?)",
                           [(n, c, d, admin_id) for n, c, d in clubs])

        event_count = db.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]
        if event_count == 0:
            clubs_by_name = {r["name"]: r["club_id"] for r in db.execute("SELECT club_id, name FROM clubs").fetchall()}
            base = datetime.now().replace(second=0, microsecond=0)
            events = [
                ("CampusConnect Launch Meetup", "Meet student organisers, explore the portal, and share ideas for a connected campus.",
                 (base + timedelta(days=4)).strftime("%Y-%m-%dT%H:%M"), "Student Activity Centre", 120, clubs_by_name.get("Coding Club"), admin_id),
                ("Problem-Solving Sprint", "A friendly team challenge focused on algorithms, collaboration, and learning.",
                 (base + timedelta(days=8)).strftime("%Y-%m-%dT%H:%M"), "Computer Centre", 80, clubs_by_name.get("Coding Club"), admin_id),
                ("Green Campus Drive", "Join a campus clean-up and sustainability awareness activity.",
                 (base + timedelta(days=12)).strftime("%Y-%m-%dT%H:%M"), "Main Ground", 60, clubs_by_name.get("Eco Campus"), admin_id),
            ]
            db.executemany("INSERT INTO events (title, description, event_date, location, capacity, club_id, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)", events)

        announcement_count = db.execute("SELECT COUNT(*) AS n FROM announcements").fetchone()["n"]
        if announcement_count == 0:
            db.execute(
                "INSERT INTO announcements (title, content, audience, posted_by) VALUES (?, ?, ?, ?)",
                ("Welcome to CampusConnect", "Browse upcoming events, join student clubs, and keep track of campus announcements from one place.", "all", admin_id),
            )
            db.execute(
                "INSERT INTO announcements (title, content, audience, posted_by) VALUES (?, ?, ?, ?)",
                ("Keep your profile current", "Add your department and year in your profile so campus organisers can understand their audience.", "students", admin_id),
            )


init_db()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute(
        "SELECT user_id, full_name, email, department, study_year, role FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or user["role"] != "admin":
            flash("That area is reserved for campus administrators.", "error")
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_user():
    return {"current_user": current_user(), "current_year": datetime.now().year}


@app.route("/")
def index():
    db = get_db()
    events = db.execute(
        "SELECT e.*, c.name AS club_name, "
        "(SELECT COUNT(*) FROM event_registrations r WHERE r.event_id=e.event_id AND r.status='registered') AS registered_count "
        "FROM events e LEFT JOIN clubs c ON c.club_id=e.club_id "
        "WHERE datetime(e.event_date) >= datetime('now') ORDER BY e.event_date LIMIT 3"
    ).fetchall()
    stats = {
        "events": db.execute("SELECT COUNT(*) FROM events WHERE datetime(event_date) >= datetime('now')").fetchone()[0],
        "clubs": db.execute("SELECT COUNT(*) FROM clubs").fetchone()[0],
        "students": db.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
    }
    announcements = db.execute(
        "SELECT a.*, u.full_name AS author FROM announcements a LEFT JOIN users u ON u.user_id=a.posted_by "
        "WHERE (a.expires_at IS NULL OR datetime(a.expires_at) >= datetime('now')) "
        "AND a.audience IN ('all', ?) ORDER BY a.posted_at DESC LIMIT 2",
        ("students" if current_user() is None or current_user()["role"] == "student" else "admins",),
    ).fetchall()
    return render_template("index.html", events=events, stats=stats, announcements=announcements)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        department = request.form.get("department", "CSE").strip() or "CSE"
        try:
            study_year = int(request.form.get("study_year", "2"))
        except ValueError:
            study_year = 0
        if len(name) < 2 or len(name) > 100 or "@" not in email or len(password) < 8 or not 1 <= study_year <= 6:
            flash("Check your details. Use a valid email, year 1-6, and a password with at least 8 characters.", "error")
            return render_template("register.html")
        try:
            get_db().execute(
                "INSERT INTO users (full_name, email, password_hash, department, study_year, role) VALUES (?, ?, ?, ?, ?, 'student')",
                (name, email, generate_password_hash(password), department, study_year),
            )
            get_db().commit()
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.", "error")
            return render_template("register.html")
        flash("Account created. You can now log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["user_id"]
            flash(f"Welcome back, {user['full_name'].split()[0]}!", "success")
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("admin_dashboard" if user["role"] == "admin" else "index"))
        flash("Email or password is incorrect.", "error")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/events")
def events():
    db = get_db()
    period = request.args.get("period", "upcoming")
    search = request.args.get("q", "").strip()
    clauses = ["1=1"]
    params = []
    if period == "past":
        clauses.append("datetime(e.event_date) < datetime('now')")
    else:
        period = "upcoming"
        clauses.append("datetime(e.event_date) >= datetime('now')")
    if search:
        clauses.append("(e.title LIKE ? OR e.description LIKE ? OR e.location LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    rows = db.execute(
        "SELECT e.*, c.name AS club_name, "
        "(SELECT COUNT(*) FROM event_registrations r WHERE r.event_id=e.event_id AND r.status='registered') AS registered_count, "
        "EXISTS(SELECT 1 FROM event_registrations r2 WHERE r2.event_id=e.event_id AND r2.user_id=? AND r2.status='registered') AS is_registered "
        "FROM events e LEFT JOIN clubs c ON c.club_id=e.club_id WHERE " + " AND ".join(clauses) + " ORDER BY e.event_date " + ("DESC" if period == "past" else "ASC"),
        [session.get("user_id", -1)] + params,
    ).fetchall()
    return render_template("events.html", events=rows, period=period, search=search)


@app.post("/events/<int:event_id>/register")
@login_required
def register_for_event(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("events"))
    if datetime.fromisoformat(event["event_date"]) < datetime.now():
        flash("Registration is closed because this event has already started.", "error")
        return redirect(url_for("events"))
    existing = db.execute("SELECT status FROM event_registrations WHERE event_id=? AND user_id=?", (event_id, session["user_id"])).fetchone()
    registered = db.execute("SELECT COUNT(*) FROM event_registrations WHERE event_id=? AND status='registered'", (event_id,)).fetchone()[0]
    if existing and existing["status"] == "registered":
        flash("You are already registered for this event.", "info")
    elif registered >= event["capacity"]:
        flash("This event is full.", "error")
    elif existing:
        db.execute("UPDATE event_registrations SET status='registered', registered_at=CURRENT_TIMESTAMP WHERE event_id=? AND user_id=?", (event_id, session["user_id"]))
        db.commit()
        flash("Your registration is active again.", "success")
    else:
        db.execute("INSERT INTO event_registrations (event_id, user_id, status) VALUES (?, ?, 'registered')", (event_id, session["user_id"]))
        db.commit()
        flash("You are registered for the event.", "success")
    return redirect(url_for("events"))


@app.post("/events/<int:event_id>/cancel")
@login_required
def cancel_event_registration(event_id):
    db = get_db()
    cur = db.execute("UPDATE event_registrations SET status='cancelled' WHERE event_id=? AND user_id=? AND status='registered'", (event_id, session["user_id"]))
    db.commit()
    flash("Registration cancelled." if cur.rowcount else "No active registration was found.", "success" if cur.rowcount else "info")
    return redirect(url_for("events"))


@app.route("/clubs")
def clubs():
    rows = get_db().execute(
        "SELECT c.*, (SELECT COUNT(*) FROM club_memberships cm WHERE cm.club_id=c.club_id AND cm.status='active') AS member_count, "
        "EXISTS(SELECT 1 FROM club_memberships cm2 WHERE cm2.club_id=c.club_id AND cm2.user_id=? AND cm2.status='active') AS joined "
        "FROM clubs c ORDER BY c.name",
        (session.get("user_id", -1),),
    ).fetchall()
    return render_template("clubs.html", clubs=rows)


@app.post("/clubs/<int:club_id>/join")
@login_required
def join_club(club_id):
    db = get_db()
    if not db.execute("SELECT 1 FROM clubs WHERE club_id=?", (club_id,)).fetchone():
        flash("Club not found.", "error")
    else:
        existing = db.execute("SELECT status FROM club_memberships WHERE user_id=? AND club_id=?", (session["user_id"], club_id)).fetchone()
        if existing:
            db.execute("UPDATE club_memberships SET status='active', joined_at=CURRENT_TIMESTAMP WHERE user_id=? AND club_id=?", (session["user_id"], club_id))
        else:
            db.execute("INSERT INTO club_memberships (user_id, club_id) VALUES (?, ?)", (session["user_id"], club_id))
        db.commit()
        flash("You joined the club.", "success")
    return redirect(url_for("clubs"))


@app.post("/clubs/<int:club_id>/leave")
@login_required
def leave_club(club_id):
    db = get_db()
    cur = db.execute("UPDATE club_memberships SET status='left' WHERE user_id=? AND club_id=? AND status='active'", (session["user_id"], club_id))
    db.commit()
    flash("You left the club." if cur.rowcount else "You are not an active member of this club.", "success" if cur.rowcount else "info")
    return redirect(url_for("clubs"))


@app.route("/announcements")
def announcements():
    user = current_user()
    role_audience = "admins" if user and user["role"] == "admin" else "students"
    rows = get_db().execute(
        "SELECT a.*, u.full_name AS author FROM announcements a LEFT JOIN users u ON u.user_id=a.posted_by "
        "WHERE (a.expires_at IS NULL OR datetime(a.expires_at) >= datetime('now')) AND a.audience IN ('all', ?) ORDER BY a.posted_at DESC",
        (role_audience,),
    ).fetchall()
    return render_template("announcements.html", announcements=rows)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE user_id=?", (session["user_id"],)).fetchone()
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        department = request.form.get("department", "").strip()
        try:
            year = int(request.form.get("study_year", "2"))
        except ValueError:
            year = 0
        if not 2 <= len(name) <= 100 or not department or len(department) > 80 or not 1 <= year <= 6:
            flash("Please provide a valid name, department, and study year (1-6).", "error")
        else:
            db.execute("UPDATE users SET full_name=?, department=?, study_year=? WHERE user_id=?", (name, department, year, session["user_id"]))
            db.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("profile"))
    registrations = db.execute(
        "SELECT e.title, e.event_date, e.location, r.status FROM event_registrations r JOIN events e ON e.event_id=r.event_id "
        "WHERE r.user_id=? ORDER BY e.event_date DESC", (session["user_id"],)
    ).fetchall()
    memberships = db.execute(
        "SELECT c.name, cm.status, cm.joined_at FROM club_memberships cm JOIN clubs c ON c.club_id=cm.club_id "
        "WHERE cm.user_id=? ORDER BY c.name", (session["user_id"],)
    ).fetchall()
    return render_template("profile.html", user=user, registrations=registrations, memberships=memberships)


@app.route("/admin", methods=["GET"])
@login_required
@admin_required
def admin_dashboard():
    db = get_db()
    events = db.execute(
        "SELECT e.*, c.name AS club_name, (SELECT COUNT(*) FROM event_registrations r WHERE r.event_id=e.event_id AND r.status='registered') AS registered_count "
        "FROM events e LEFT JOIN clubs c ON c.club_id=e.club_id ORDER BY e.event_date DESC"
    ).fetchall()
    clubs = db.execute("SELECT club_id, name FROM clubs ORDER BY name").fetchall()
    notices = db.execute("SELECT announcement_id, title, audience, posted_at FROM announcements ORDER BY posted_at DESC").fetchall()
    stats = {
        "users": db.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
        "events": db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
        "clubs": db.execute("SELECT COUNT(*) FROM clubs").fetchone()[0],
        "registrations": db.execute("SELECT COUNT(*) FROM event_registrations WHERE status='registered'").fetchone()[0],
    }
    return render_template("admin.html", events=events, clubs=clubs, notices=notices, stats=stats)


@app.post("/admin/events/create")
@login_required
@admin_required
def create_event():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    event_date = request.form.get("event_date", "").strip()
    location = request.form.get("location", "").strip()
    try:
        capacity = int(request.form.get("capacity", "100"))
        club_id = int(request.form.get("club_id", "0")) or None
        parsed_date = datetime.fromisoformat(event_date)
    except (ValueError, TypeError):
        flash("Enter a valid event date/time, capacity, and club.", "error")
        return redirect(url_for("admin_dashboard"))
    if len(title) < 3 or len(title) > 120 or not description or not location or not 1 <= capacity <= 10000 or parsed_date < datetime.now():
        flash("Check event details. The date must be in the future and capacity between 1 and 10,000.", "error")
    else:
        get_db().execute("INSERT INTO events (title, description, event_date, location, capacity, club_id, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (title, description, event_date, location, capacity, club_id, session["user_id"]))
        get_db().commit()
        flash("Event created.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/events/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_event(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("admin_dashboard"))
    clubs_list = db.execute("SELECT club_id, name FROM clubs ORDER BY name").fetchall()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        event_date = request.form.get("event_date", "").strip()
        location = request.form.get("location", "").strip()
        try:
            capacity = int(request.form.get("capacity", "100"))
            club_id = int(request.form.get("club_id", "0")) or None
            parsed_date = datetime.fromisoformat(event_date)
        except (ValueError, TypeError):
            flash("Enter a valid date/time and capacity.", "error")
            return render_template("edit_event.html", event=event, clubs=clubs_list)
        if len(title) < 3 or len(title) > 120 or not description or not location or not 1 <= capacity <= 10000:
            flash("Please complete all fields and use a capacity from 1 to 10,000.", "error")
            return render_template("edit_event.html", event=event, clubs=clubs_list)
        db.execute("UPDATE events SET title=?, description=?, event_date=?, location=?, capacity=?, club_id=? WHERE event_id=?",
                   (title, description, event_date, location, capacity, club_id, event_id))
        db.commit()
        flash("Event updated.", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("edit_event.html", event=event, clubs=clubs_list)


@app.post("/admin/events/<int:event_id>/delete")
@login_required
@admin_required
def delete_event(event_id):
    cur = get_db().execute("DELETE FROM events WHERE event_id=?", (event_id,))
    get_db().commit()
    flash("Event deleted." if cur.rowcount else "Event not found.", "success" if cur.rowcount else "info")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/clubs/create")
@login_required
@admin_required
def create_club():
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    if len(name) < 2 or len(name) > 120 or not category or not description:
        flash("Enter a club name, category, and description.", "error")
    else:
        try:
            get_db().execute("INSERT INTO clubs (name, category, description, created_by) VALUES (?, ?, ?, ?)", (name, category, description, session["user_id"]))
            get_db().commit()
            flash("Club created.", "success")
        except sqlite3.IntegrityError:
            flash("A club with that name already exists.", "error")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/announcements/create")
@login_required
@admin_required
def create_announcement():
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    audience = request.form.get("audience", "all")
    expires_at = request.form.get("expires_at", "").strip() or None
    if len(title) < 3 or len(title) > 120 or not content or audience not in {"all", "students", "admins"}:
        flash("Enter a title, content, and valid audience.", "error")
    else:
        get_db().execute("INSERT INTO announcements (title, content, audience, posted_by, expires_at) VALUES (?, ?, ?, ?, ?)",
                         (title, content, audience, session["user_id"], expires_at))
        get_db().commit()
        flash("Announcement published.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/announcements/<int:announcement_id>/delete")
@login_required
@admin_required
def delete_announcement(announcement_id):
    cur = get_db().execute("DELETE FROM announcements WHERE announcement_id=?", (announcement_id,))
    get_db().commit()
    flash("Announcement deleted." if cur.rowcount else "Announcement not found.", "success" if cur.rowcount else "info")
    return redirect(url_for("admin_dashboard"))


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))
