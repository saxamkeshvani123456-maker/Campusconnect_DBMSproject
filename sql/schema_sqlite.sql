PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL CHECK (length(trim(full_name)) BETWEEN 2 AND 100),
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    department TEXT NOT NULL DEFAULT 'CSE',
    study_year INTEGER NOT NULL DEFAULT 2 CHECK (study_year BETWEEN 1 AND 6),
    role TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student', 'admin')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clubs (
    club_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS club_memberships (
    user_id INTEGER NOT NULL,
    club_id INTEGER NOT NULL,
    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'left')),
    PRIMARY KEY (user_id, club_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (club_id) REFERENCES clubs(club_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK (length(trim(title)) BETWEEN 3 AND 120),
    description TEXT NOT NULL,
    event_date TEXT NOT NULL,
    location TEXT NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 100 CHECK (capacity BETWEEN 1 AND 10000),
    club_id INTEGER,
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (club_id) REFERENCES clubs(club_id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS event_registrations (
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    registered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'registered' CHECK (status IN ('registered', 'cancelled')),
    PRIMARY KEY (event_id, user_id),
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS announcements (
    announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK (length(trim(title)) BETWEEN 3 AND 120),
    content TEXT NOT NULL,
    audience TEXT NOT NULL DEFAULT 'all' CHECK (audience IN ('all', 'students', 'admins')),
    posted_by INTEGER,
    posted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    FOREIGN KEY (posted_by) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_club ON events(club_id);
CREATE INDEX IF NOT EXISTS idx_registrations_user_status ON event_registrations(user_id, status);
CREATE INDEX IF NOT EXISTS idx_memberships_club_status ON club_memberships(club_id, status);
CREATE INDEX IF NOT EXISTS idx_announcements_posted_at ON announcements(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

CREATE VIEW IF NOT EXISTS upcoming_events_view AS
SELECT e.event_id, e.title, e.description, e.event_date, e.location, e.capacity,
       c.name AS club_name,
       (SELECT COUNT(*) FROM event_registrations r
        WHERE r.event_id = e.event_id AND r.status = 'registered') AS registered_count
FROM events e
LEFT JOIN clubs c ON c.club_id = e.club_id
WHERE datetime(e.event_date) >= datetime('now');

CREATE VIEW IF NOT EXISTS event_registration_summary_view AS
SELECT e.event_id, e.title, e.capacity,
       COUNT(CASE WHEN r.status = 'registered' THEN 1 END) AS registered_count,
       COUNT(CASE WHEN r.status = 'cancelled' THEN 1 END) AS cancelled_count
FROM events e
LEFT JOIN event_registrations r ON r.event_id = e.event_id
GROUP BY e.event_id, e.title, e.capacity;
