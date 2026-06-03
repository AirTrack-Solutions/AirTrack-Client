CREATE DATABASE IF NOT EXISTS airtrack CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'airtrack'@'localhost' IDENTIFIED BY 'Gate1UserPass!';
GRANT ALL PRIVILEGES ON airtrack.* TO 'airtrack'@'localhost';
FLUSH PRIVILEGES;
