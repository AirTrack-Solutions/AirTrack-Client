# File History: docs/upgrade-v1-linux-pi.md
Journal Revision: 1
Last Updated: 2026-11-28 Australia/Sydney

## Current State
Documents the manual upgrade and rollback between the tested prebuilt Linux and Pi bundles.

## Entry Log
- 2026-11-28 — Created a narrow procedure based on member-by-member archive comparison. Backup first, then replace only the seven changed files and keep the original volume and runtime data. A rollback restores those seven files. It does not attempt to migrate other installation types.

- 2026-11-28 — Verified the upgrade and application rollback on disposable AMD64 and native Pi ARM64. The Pi fixture initially masked archive permissions with umask 077, leaving the schema unreadable to MariaDB. Confirmed the actual initialization error and passed the complete sequence after extracting with --same-permissions. Updated the guide to include that command. No installation or database changes on production systems.
