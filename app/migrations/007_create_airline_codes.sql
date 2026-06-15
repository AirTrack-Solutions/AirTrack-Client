-- Migration 007: Create airline_codes reference table (client-side)
-- Mirrors the lookup columns from the server's airline_codes table.
-- Populated by Wombat/Marmot delivery (airlines_ref package).
-- The user's own airlines remain in the `airlines` table.

CREATE TABLE IF NOT EXISTS `airline_codes` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `airline_name` varchar(255) NOT NULL,
  `iata` varchar(3) DEFAULT NULL,
  `icao` varchar(4) DEFAULT NULL,
  `callsign` varchar(100) DEFAULT NULL,
  `country` varchar(100) DEFAULT NULL,
  `status` enum('dormant','needs_review','verified','rejected') NOT NULL DEFAULT 'dormant',
  `imported_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_airline_name` (`airline_name`),
  KEY `idx_status` (`status`),
  KEY `idx_iata` (`iata`),
  KEY `idx_icao` (`icao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
