# File History: gates/gate2/requirements.txt
Journal Revision: 1
Last Updated: 2026-11-01

## Current State
Before change: legacy Gate2 resolves Werkzeug transitively through Flask; an old installed vulnerable version can remain satisfied.

## Known Issues
Legacy installer not rebuilt during this source repair.

## Future Work
Keep the shared security minimum consistent if Gate2 remains runnable.

## Entry Log
- 2026-10-30: Read-only security review identified a surviving Gate2 build route. Add explicit Werkzeug3.1.9 pin, matching app and Gate3, without changing build logic. Validation: patched dependencies import and focused controls pass; full dry-run resolution passes for all edited manifests, with Lite tested using available Windows Python3.11 wheels because local Connector/C is absent. Recovery: revert this constraint only, understanding it restores the vulnerable transitive route.

- 2026-10-30 candidate verification: Isolated Werkzeug3.1.9/Flask3.1.3 reject Windows NUL:/CON:/aux:/NUL.txt:; normal file download and traversal404 controls pass. Pillow13.0.0 decodes JPEG/PNG/WebP/BMP/TIFF, exif-transposes/converts/thumbnails/savesJPEG; malformed Image.merge first-band and TIFF predictor fail safely. pip check passes in focused environment. Full manifest dry-run resolution passes; Gate2/Gate3 cross-platform wheel resolution used Windows Python3.12, Lite Python3.11. No installer or live web image rebuilt; this is a source dependency repair, not a claim installed clients have upgraded. Existing Windows/Mac pyOpenSSL26.3/cryptography50 conflict repaired with26.4. GitHub advisory closure pending default-branch processing.

- 2026-10-30 native check: Disposable copy of source158 scheduler image Python3.11 installed Werkzeug3.1.9, Pillow13.0.0 and Flask3.1.3 only under /tmp/validated. Imports, PNG/EXIF/thumbnail/JPEG and Windows-device rejection controls passed. Container automatically removed; no live environment packages changed.


- 2026-10-30 active-workspace integration: Apply only the tested dependency constraints to this existing checkout, preserving its other branch-specific requirements and unrelated edits. Canonical default-branch security changes are already published; existing installed binaries/images have not been rebuilt. Patched package and full-manifest resolver checks are documented above.

- 2026-11-01: Integrated the already-published dependency repair from the remote branch rather than making a duplicate source fix. Retained local validation/provenance notes; branch-specific client pins preserved. This is repository reconciliation only, not a package/image/installer rollout. Recovery uses backup/pre-reconcile-20261101 and saved source snapshot.
