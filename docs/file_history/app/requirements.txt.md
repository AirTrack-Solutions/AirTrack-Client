# File History: app/requirements.txt
Journal Revision: 1
Last Updated: 2026-11-28

## Current State

Include the already-used scheduler dependencies during image build.
Before repair: dependency manifest allows a Dependabot-reported vulnerable Werkzeug version; Logbook also excludes patched Pillow13.

## Known Issues
Full manifest resolution and platform-specific packaging validation pending. Keep unrelated pins and source unchanged.

## Future Work
Validate minimal security dependency bumps in isolation; retain proof gaps rather than dismiss alerts.

## Entry Log
- 2026-10-30: Created before editing for Trevor's critter health repair. Raise Werkzeug to3.1.9 for GHSA-g6x2-hccm-hh4m; Logbook Pillow to>=13.0.0,<14 for seven current image-parser/encoder advisories. Both support configured Python3.11+. No runtime/release deployment intended by source edit. Recovery: revert this manifest change and rebuild only if necessary, understanding old versions restore known vulnerabilities.

- 2026-10-30 candidate verification: Isolated Werkzeug3.1.9/Flask3.1.3 reject Windows NUL:/CON:/aux:/NUL.txt:; normal file download and traversal404 controls pass. Pillow13.0.0 decodes JPEG/PNG/WebP/BMP/TIFF, exif-transposes/converts/thumbnails/savesJPEG; malformed Image.merge first-band and TIFF predictor fail safely. pip check passes in focused environment. Full manifest dry-run resolution passes; Gate2/Gate3 cross-platform wheel resolution used Windows Python3.12, Lite Python3.11. No installer or live web image rebuilt; this is a source dependency repair, not a claim installed clients have upgraded. Existing Windows/Mac pyOpenSSL26.3/cryptography50 conflict repaired with26.4. GitHub advisory closure pending default-branch processing.

- 2026-10-30 native check: Disposable copy of source158 scheduler image Python3.11 installed Werkzeug3.1.9, Pillow13.0.0 and Flask3.1.3 only under /tmp/validated. Imports, PNG/EXIF/thumbnail/JPEG and Windows-device rejection controls passed. Container automatically removed; no live environment packages changed.


- 2026-10-30 active-workspace integration: Apply only the tested dependency constraints to this existing checkout, preserving its other branch-specific requirements and unrelated edits. Canonical default-branch security changes are already published; existing installed binaries/images have not been rebuilt. Patched package and full-manifest resolver checks are documented above.

- 2026-11-01: Integrated the already-published dependency repair from the remote branch rather than making a duplicate source fix. Retained local validation/provenance notes; branch-specific client pins preserved. This is repository reconciliation only, not a package/image/installer rollout. Recovery uses backup/pre-reconcile-20261101 and saved source snapshot.

- 2026-11-28 — Include the already-used scheduler dependencies during image build. Shell and Compose static checks passed. Native fresh install/retained volume checks pending. Revert source and use the previous matching image to recover.
