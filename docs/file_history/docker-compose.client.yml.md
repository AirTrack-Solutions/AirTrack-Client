# File History: docker-compose.client.yml
Journal Revision: 1
Last Updated: 2026-11-28

## Current State

Seed schema on first MariaDB volume initialisation only. Wait for MariaDB and web readiness. Bundled scheduler dependencies remove startup pip fetch; old images retain their fallback.

## Entry Log

- 2026-11-28 — Seed schema on first MariaDB volume initialisation only. Wait for MariaDB and web readiness. Bundled scheduler dependencies remove startup pip fetch; old images retain their fallback. Shell and Compose static checks passed. Native fresh install/retained volume checks pending. Revert source and use the previous matching image to recover.
