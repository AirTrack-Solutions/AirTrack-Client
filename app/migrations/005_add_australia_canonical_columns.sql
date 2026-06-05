-- Migration: 005_add_australia_canonical_columns
-- Description: Adds hexcode and monthmanu to the australia table to match the
--              canonical 25-column registry schema. Required for Marmot to
--              import registry packages from Wombat without column mismatch errors.

ALTER TABLE australia
    ADD COLUMN IF NOT EXISTS `hexcode` varchar(10) DEFAULT NULL AFTER `registration`,
    ADD COLUMN IF NOT EXISTS `monthmanu` int(11) DEFAULT NULL AFTER `yearmanu`;
