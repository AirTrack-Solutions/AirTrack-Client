-- Migration: add hexcode and monthmanu to australia table
ALTER TABLE `australia`
  ADD COLUMN IF NOT EXISTS `hexcode` varchar(10) DEFAULT NULL AFTER `registration`,
  ADD COLUMN IF NOT EXISTS `monthmanu` int(11) DEFAULT NULL AFTER `yearmanu`;
