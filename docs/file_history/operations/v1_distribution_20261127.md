# Logbook V1 distribution on AirTrack-Client
Journal Revision: 1
Last Updated: 2026-11-28

## Current State

Photo-capable bundles passed native installation, upload and backup verification.

The Linux AMD64 and native Pi ARM64 customer bundles passed clean install and retention checks.

Release source b14bbf7 is pushed on release/logbook-v1-20261127. The Linux AMD64 and Raspberry Pi ARM64 package and matching deployment source archive are built. The .158 production
browser sign-off accepted the live Chromium hover coverage gap and deferred
user-selectable data text size to V2.

## Entry Log

- 2026-11-27 — Port the signed-off cockpit, Vintage Brass, responsive page,
  Aircraft tooltip and Airlines logo changes from the .158 live inventory at
  6c74037. Explicitly include the tooltip script and theme assets. Retain
  platform-specific templates, CSRF inputs and the Windows frozen theme path.
  Where the target has no community blueprint, omit the unrelated Settings
  link. Regenerate the theme index from each target's own packaged assets.
  Leave unrelated server working-tree changes, private data and backups out.
  Revert the release commit to recover source without changing live .158.

- 2026-11-27 — Both platforms started with an isolated MariaDB 11.4 schema, served tooltip and Vintage Brass assets with HTTP 200, and returned HTTP 302 from the protected Aircraft and Airlines routes. The ARM64 build and smoke ran natively on .163. Client-side flag styling and the Linux CSRF input explain the two source hash differences from .158. Theme generator tests, Jinja parsing, JavaScript syntax, git diff checks and credential-pattern checks passed. Removed bundled legacy database password fallbacks and kept runtime DB_PASSWORD as the credential source. Configure that variable for direct legacy utility runs. Smoke used standard request gates. The finished packages were not installed on production. Distribution artifacts and SHA256SUMS are under /home/trevor/docker/AirTrack/worktrees/logbook-v1-dist-20261127/artifacts. Use the previous app tree and image tag to recover an existing deployment.

- 2026-11-28 — Prepare customer-installable Linux/ARM64 bundles. Fix GHCR latest overriding packaged image, fresh-volume schema provisioning and scheduler dependency placement. Full native verification is pending. Live fulfillment remains on the old archive until verified.

- 2026-11-28 — Final customer bundle source fcdb4b1, application images 826d826 (identical app tree). The exact AMD64 and native Pi ARM64 archives passed first-run install with disposable MariaDB, licensed ATP/ATF fixtures, stock request gates and served CSS/JS. Reruns preserved the SQL marker, .env and licence. Existing-volume/wrong-folder test refused to create a new .env. Package contents and SHA-256 sums verified. Bundle names and hashes: AirTrack-Logbook-V1-Linux-AMD64.tar.gz a77473c0187949090be2dcb95715966527a63e41da395e8f7052c7cd3b6e2c7f and AirTrack-Logbook-V1-Raspberry-Pi-ARM64.tar.gz e4263fc34d90af64768b5e22e968cc1e377e3777ca8c7748080cafb9c86c2987. Use the previous matching image/source and established database backup for rollback.

- 2026-11-28 — Rebuilt Linux AMD64 and native Pi ARM64 customer bundles from 4d69bd4 with Pillow 13.0.0 after the photo upload dependency gap was found. On disposable native deployments, exercised the normal first-run setup, real JPEG upload, HTTP photo response and Cockpit backup. Verified completed SQL marker and the photo manifest/blob checksum. Both install reruns preserved the database marker, .env and licence; a wrong folder still refused to create credentials over an existing volume. Previous bundles remain private. New archive SHA-256: AMD64 666a0f719cb1ed13eb2de5fa5439eefc56847dc05e4e7af61b77e342f113ad78, ARM64 32bbfafd9ec24532ca768337b3b82fb40fe3e877854fdcf1c2e6ab1ab26d2e0f. Native logs and packages under artifacts/photo-qualified-20261128 in the distribution workspace; protected web rollout copies on node153 /home/airtrack/logbook-client-photo-qualified-20261128. No installation on existing customer systems. Roll back by restoring the previous image/source and keeping the original .env, licence and database.

- 2026-11-28 — Published the photo-qualified Linux AMD64 and Raspberry Pi ARM64 archives at airtracksolutions.com and updated paid Linux Logbook fulfilment to supply both links. Verified full public AMD64 SHA-256 and full Pi ranged SHA-256. Earlier Pi single-stream verification reached the local curl timeout. Confirmed valid gzip attachments, origin checksums and native test logs. Stubbed entitlement/mail rendering preserved the licence and kept TrainTrack on its previous path. Live unpaid checkout verified Linux metadata and active half-price amounts, then expired both sessions. No real mail or payments. Website and billing rollback sources and Compose overrides under /home/airtrack/logbook-client-photo-qualified-20261128 on node153.

- 2026-11-28 — Rechecked Linux and Pi install notes against actual bundles. Corrected nonexistent installer filename, Docker preinstallation, architecture, licence timing, first-run internet and setup, headless Pi URL, port conflict, registry recreation, photo backup permissions and existing-volume guidance. Fixed bundled start/stop to use the real .env and Compose project. Both native systems passed fresh install, photo/backup, rerun and actual stop/start with database, credentials and licence retained. All archive members except README.md, READ-ME-FIRST.txt, start.sh and stop.sh are byte-identical to the previous archives, including the Docker image. Published new notes archives (SHA-256 80c096310b07a6d71b2101747a3967b6b6fa3ac4a2c61c2db3b3e82c06222af7 AMD64 and f96ae414a3865230137a89de0372873ee04a7bb93daa4ddd4128f168de8b4e5c ARM64) and verified entire HTTP delivery at origin. Rollback archives saved in /home/airtrack/logbook-install-notes-20261128/pre-notes-downloads on node153.
