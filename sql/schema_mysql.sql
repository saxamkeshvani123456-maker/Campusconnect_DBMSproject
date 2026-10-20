-- CampusConnect relational schema for MySQL 8.0+
CREATE DATABASE IF NOT EXISTS campusconnect
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE campusconnect;

CREATE TABLE users (
  user_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(100) NOT NULL,
  email VARCHAR(254) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  department VARCHAR(80) NOT NULL DEFAULT 'CSE',
  study_year TINYINT UNSIGNED NOT NULL DEFAULT 2,
  role ENUM('student','admin') NOT NULL DEFAULT 'student',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT chk_users_name CHECK (CHAR_LENGTH(TRIM(full_name)) BETWEEN 2 AND 100),
  CONSTRAINT chk_users_year CHECK (study_year BETWEEN 1 AND 6),
  INDEX idx_users_role (role)
) ENGINE=InnoDB;

CREATE TABLE clubs (
  club_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL UNIQUE,
  category VARCHAR(80) NOT NULL,
  description TEXT NOT NULL,
  created_by BIGINT UNSIGNED NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_clubs_creator FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE club_memberships (
  user_id BIGINT UNSIGNED NOT NULL,
  club_id BIGINT UNSIGNED NOT NULL,
  joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status ENUM('active','left') NOT NULL DEFAULT 'active',
  PRIMARY KEY (user_id, club_id),
  INDEX idx_memberships_club_status (club_id, status),
  CONSTRAINT fk_memberships_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_memberships_club FOREIGN KEY (club_id) REFERENCES clubs(club_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE events (
  event_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  description TEXT NOT NULL,
  event_date DATETIME NOT NULL,
  location VARCHAR(180) NOT NULL,
  capacity INT UNSIGNED NOT NULL DEFAULT 100,
  club_id BIGINT UNSIGNED NULL,
  created_by BIGINT UNSIGNED NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT chk_events_capacity CHECK (capacity BETWEEN 1 AND 10000),
  CONSTRAINT fk_events_club FOREIGN KEY (club_id) REFERENCES clubs(club_id) ON DELETE SET NULL,
  CONSTRAINT fk_events_creator FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL,
  INDEX idx_events_date (event_date),
  INDEX idx_events_club (club_id)
) ENGINE=InnoDB;

CREATE TABLE event_registrations (
  event_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  registered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status ENUM('registered','cancelled') NOT NULL DEFAULT 'registered',
  PRIMARY KEY (event_id, user_id),
  INDEX idx_registrations_user_status (user_id, status),
  CONSTRAINT fk_registrations_event FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE,
  CONSTRAINT fk_registrations_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE announcements (
  announcement_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  content TEXT NOT NULL,
  audience ENUM('all','students','admins') NOT NULL DEFAULT 'all',
  posted_by BIGINT UNSIGNED NULL,
  posted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME NULL,
  CONSTRAINT fk_announcements_author FOREIGN KEY (posted_by) REFERENCES users(user_id) ON DELETE SET NULL,
  INDEX idx_announcements_posted_at (posted_at)
) ENGINE=InnoDB;

CREATE OR REPLACE VIEW upcoming_events_view AS
SELECT e.event_id, e.title, e.description, e.event_date, e.location, e.capacity,
       c.name AS club_name,
       SUM(CASE WHEN r.status = 'registered' THEN 1 ELSE 0 END) AS registered_count
FROM events e
LEFT JOIN clubs c ON c.club_id = e.club_id
LEFT JOIN event_registrations r ON r.event_id = e.event_id
WHERE e.event_date >= CURRENT_TIMESTAMP
GROUP BY e.event_id, e.title, e.description, e.event_date, e.location, e.capacity, c.name;

CREATE OR REPLACE VIEW event_registration_summary_view AS
SELECT e.event_id, e.title, e.capacity,
       SUM(CASE WHEN r.status = 'registered' THEN 1 ELSE 0 END) AS registered_count,
       SUM(CASE WHEN r.status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_count
FROM events e LEFT JOIN event_registrations r ON r.event_id = e.event_id
GROUP BY e.event_id, e.title, e.capacity;
