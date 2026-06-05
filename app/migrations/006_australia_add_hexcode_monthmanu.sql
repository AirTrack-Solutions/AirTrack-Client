-- Migration: 006_australia_add_hexcode_monthmanu
-- Description: Applies hexcode and monthmanu columns to australia table.
--              Migrations 004/005 were silently skipped due to a comment-stripping
--              bug in the migration runner (now fixed). IF NOT EXISTS is safe to run
--              on installs that already have the columns.

ALTER TABLE australia
    ADD COLUMN IF NOT EXISTS `hexcode` varchar(10) DEFAULT NULL AFTER `registration`,
    ADD COLUMN IF NOT EXISTS `monthmanu` int(11) DEFAULT NULL AFTER `yearmanu`;
