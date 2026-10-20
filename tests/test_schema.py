"""Database-level checks requiring only Python's standard library."""
import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "sql" / "schema_sqlite.sql"


class CampusConnectSchemaTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA.read_text(encoding="utf-8"))
        self.db.execute(
            "INSERT INTO users (full_name,email,password_hash,department,study_year,role) VALUES (?,?,?,?,?,?)",
            ("Test Admin", "admin@test.local", "hashed", "CSE", 2, "admin"),
        )
        self.db.execute(
            "INSERT INTO users (full_name,email,password_hash,department,study_year,role) VALUES (?,?,?,?,?,?)",
            ("Test Student", "student@test.local", "hashed", "CSE", 2, "student"),
        )
        self.db.execute("INSERT INTO clubs (name,category,description,created_by) VALUES (?,?,?,1)",
                        ("Coding Club", "Tech", "Coding for all levels"))
        self.db.execute(
            "INSERT INTO events (title,description,event_date,location,capacity,club_id,created_by) VALUES (?,?,?,?,?,?,?)",
            ("Test Event", "A test event", "2099-01-01T12:00", "Hall A", 10, 1, 1),
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_expected_tables_and_views_exist(self):
        rows = self.db.execute("SELECT name,type FROM sqlite_master WHERE type IN ('table','view')").fetchall()
        items = {(row['name'], row['type']) for row in rows}
        for name in ['users','clubs','club_memberships','events','event_registrations','announcements']:
            self.assertIn((name,'table'), items)
        self.assertIn(('upcoming_events_view','view'), items)
        self.assertIn(('event_registration_summary_view','view'), items)

    def test_event_registration_unique_composite_key(self):
        self.db.execute("INSERT INTO event_registrations (event_id,user_id) VALUES (1,2)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO event_registrations (event_id,user_id) VALUES (1,2)")

    def test_foreign_keys_prevent_orphan_records(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO club_memberships (user_id,club_id) VALUES (999,1)")

    def test_capacity_constraint_rejects_invalid_value(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                "INSERT INTO events (title,description,event_date,location,capacity) VALUES (?,?,?,?,?)",
                ("Bad Capacity", "test", "2099-01-01T12:00", "Hall A", 0),
            )

    def test_membership_and_registration_crud(self):
        self.db.execute("INSERT INTO club_memberships (user_id,club_id) VALUES (2,1)")
        self.db.execute("INSERT INTO event_registrations (event_id,user_id) VALUES (1,2)")
        self.db.execute("UPDATE club_memberships SET status='left' WHERE user_id=2 AND club_id=1")
        self.db.execute("UPDATE event_registrations SET status='cancelled' WHERE event_id=1 AND user_id=2")
        self.db.commit()
        self.assertEqual(self.db.execute("SELECT status FROM club_memberships WHERE user_id=2 AND club_id=1").fetchone()[0], 'left')
        self.assertEqual(self.db.execute("SELECT status FROM event_registrations WHERE event_id=1 AND user_id=2").fetchone()[0], 'cancelled')

    def test_reporting_view_counts_registration(self):
        self.db.execute("INSERT INTO event_registrations (event_id,user_id) VALUES (1,2)")
        self.db.commit()
        row = self.db.execute("SELECT registered_count FROM event_registration_summary_view WHERE event_id=1").fetchone()
        self.assertEqual(row[0], 1)


if __name__ == '__main__':
    unittest.main()
