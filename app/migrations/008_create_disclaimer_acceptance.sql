-- Migration 008: create disclaimer_acceptance table
-- Tracks every disclaimer acceptance for audit purposes.
-- Missing from schema.sql on initial release — this migration adds it to existing installs.

CREATE TABLE IF NOT EXISTS `disclaimer_acceptance` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `disclaimer_version` varchar(20) NOT NULL,
  `accepted_at` datetime NOT NULL,
  `expires_at` datetime NOT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `user_agent` varchar(500) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
