# File History: install.sh
Journal Revision: 1
Last Updated: 2026-11-28

## Current State

Load bundled image with architecture checks, derive the actual web port, and preserve existing .env and licence. Generate a private .env with independent DB and session secrets on first install. Source-only path still uses GHCR.

## Entry Log

- 2026-11-28 — Load bundled image with architecture checks, derive the actual web port, and preserve existing .env and licence. Generate a private .env with independent DB and session secrets on first install. Source-only path still uses GHCR. Shell and Compose static checks passed. Native fresh install/retained volume checks pending. Revert source and use the previous matching image to recover.

- 2026-11-28 — Preserve the original MariaDB root credential mapping for existing .env files. Only new installs add the distinct bootstrap secret. Refuse to generate replacement credentials when the project database volume already exists and .env is missing.
