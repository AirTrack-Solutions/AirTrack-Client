# Logbook V1 distribution on AirTrack-Client
Journal Revision: 1
Last Updated: 2026-11-28

## Current State

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
