# File History: docker-compose.client.yml
Journal Revision: 1
Last Updated: 2026-11-28

## Current State

Seed schema on first MariaDB volume initialisation only. Wait for MariaDB and web readiness. Bundled scheduler dependencies remove startup pip fetch; old images retain their fallback.

## Entry Log

- 2026-11-28 — Seed schema on first MariaDB volume initialisation only. Wait for MariaDB and web readiness. Bundled scheduler dependencies remove startup pip fetch; old images retain their fallback. Shell and Compose static checks passed. Native fresh install/retained volume checks pending. Revert source and use the previous matching image to recover.

- 2026-11-28 — Preserve the original MariaDB root credential mapping for existing .env files. Only new installs add the distinct bootstrap secret. Refuse to generate replacement credentials when the project database volume already exists and .env is missing.
