# CampusConnect - DBMS Project

**Course:** Database Management Systems (CS203)  
**Programme:** B.Tech. II CSE, Semester III  
**Academic year:** 2026-27  
**Institute:** SVNIT Surat  
**Team name / members:** Fill in before submission

CampusConnect is a campus information portal for student accounts, campus events, club memberships, event registrations, and announcements. It is designed around the six phases named in the course project instructions.

## Features

- Student registration, login, logout, and profile editing.
- Password hashing (no plaintext passwords stored).
- Browse and search upcoming/past campus events.
- Register for events and cancel a registration; event capacity is checked.
- Browse clubs, join clubs, and leave clubs.
- Browse announcements by audience and expiry.
- Admin dashboard to create events, update/delete events, create clubs, and publish/delete announcements.
- SQL schema with foreign keys, checks, unique constraints, indexes, and reporting views.
- MySQL 8 schema and CRUD examples for the DBMS submission. The ready-to-run web demo defaults to SQLite so it is simple to launch on a student laptop.

## Run locally (Windows / VS Code)

1. Install Python 3.10 or later.
2. Extract this folder and open it in VS Code.
3. Open the terminal in the `CampusConnect_Project` directory.
4. Create a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

5. Install the project dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

6. Run the website:

   ```powershell
   python app.py
   ```

7. Open **http://127.0.0.1:5000** in your browser. The database and sample records are created automatically on first run.

If PowerShell blocks environment activation, run `.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.venv\Scripts\python.exe app.py` instead.

### Demo administrator

- Email: `admin@campusconnect.local`
- Password: `Admin@123`

This account is seeded automatically for local demonstration. Change the password and set a random `CAMPUSCONNECT_SECRET` before deploying anywhere public. Do not use the demo credentials with real personal data.

### Demo student

Use **Join CampusConnect** to create a student account. The first demo account created is not automatically an administrator.

## Database files

- `sql/schema_sqlite.sql`: schema used by the local Flask application.
- `sql/schema_mysql.sql`: MySQL 8.0+ schema, indexes, constraints, and views for DBMS implementation/demonstration.
- `sql/crud_examples.sql`: sample INSERT, SELECT, UPDATE, and DELETE statements. Replace sample IDs with IDs in your own database.
- `docs/ER_Diagram.png`: conceptual ER model.
- `docs/Project_Report.docx`: editable project report aligned to Sections A-F of the instructions.
- `docs/Project_Report.pdf`: print-ready PDF copy of the report.
- `docs/Project_Presentation.pptx`: editable presentation draft.

To use a different SQLite file, set `CAMPUSCONNECT_DB` to the database path before starting the app. Set `CAMPUSCONNECT_SECRET` to a long random value for the session signing key.

## Data model summary

| Table | Purpose | Primary key |
|---|---|---|
| `users` | Student and administrator accounts | `user_id` |
| `clubs` | Campus clubs/communities | `club_id` |
| `club_memberships` | User-club many-to-many relationship and membership status | (`user_id`, `club_id`) |
| `events` | Campus event listings | `event_id` |
| `event_registrations` | User-event many-to-many relationship and registration status | (`event_id`, `user_id`) |
| `announcements` | Notices with audience/expiry | `announcement_id` |

## Functional scope and demo limitations

This is a DBMS course prototype. It intentionally uses a small set of tables and a focused feature set so the ER-to-relational mapping can be explained. Sample data is generated for the first run. The SQLite application schema and the MySQL submission schema represent the same logical design but use engine-appropriate SQL syntax.

Before the final evaluation, the team should:

1. Add member names, roll numbers, team name, and faculty details to the report and slides.
2. Run the application on the presentation laptop and verify the database is created successfully.
3. Test student and administrator workflows using separate browser sessions.
4. Demonstrate the MySQL script in MySQL Workbench/phpMyAdmin if the course instructor expects MySQL specifically.
5. Replace the demo seed content with campus-relevant sample content, while avoiding real personal data.
6. Add CSRF protection, secure password reset, HTTPS, and deployment secrets before any real public deployment.

## Tests

The `tests/` directory contains a standard-library database schema check. Run it using:

```powershell
python -m unittest discover -s tests -v
```

The Flask app has not been run end-to-end in the file-generation environment because Flask could not be installed there. Install `requirements.txt` and run the local checks on your machine before claiming a full end-to-end test in the final report.
