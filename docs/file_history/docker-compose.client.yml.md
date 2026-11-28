# File History: docker-compose.client.yml
Journal Revision: 1
Last Updated: 2026-11-28

## Current State

The Linux AMD64 and native Pi ARM64 customer bundles passed clean install and retention checks.

Seed schema on first MariaDB volume initialisation only. Wait for MariaDB and web readiness. Bundled scheduler dependencies remove startup pip fetch; old images retain their fallback.

## Entry Log

- 2026-11-28 — Seed schema on first MariaDB volume initialisation only. Wait for MariaDB and web readiness. Bundled scheduler dependencies remove startup pip fetch; old images retain their fallback. Shell and Compose static checks passed. Native fresh install/retained volume checks pending. Revert source and use the previous matching image to recover.

- 2026-11-28 — Preserve the original MariaDB root credential mapping for existing .env files. Only new installs add the distinct bootstrap secret. Refuse to generate replacement credentials when the project database volume already exists and .env is missing.

- 2026-11-28 — Final customer bundle source fcdb4b1, application images 826d826 (identical app tree). The exact AMD64 and native Pi ARM64 archives passed first-run install with disposable MariaDB, licensed ATP/ATF fixtures, stock request gates and served CSS/JS. Reruns preserved the SQL marker, .env and licence. Existing-volume/wrong-folder test refused to create a new .env. Package contents and SHA-256 sums verified. Bundle names and hashes: AirTrack-Logbook-V1-Linux-AMD64.tar.gz a77473c0187949090be2dcb95715966527a63e41da395e8f7052c7cd3b6e2c7f and AirTrack-Logbook-V1-Raspberry-Pi-ARM64.tar.gz e4263fc34d90af64768b5e22e968cc1e377e3777ca8c7748080cafb9c86c2987. Use the previous matching image/source and established database backup for rollback.
