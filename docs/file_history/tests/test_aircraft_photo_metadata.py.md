# File History: tests/test_aircraft_photo_metadata.py
Journal Revision: 1
Last Updated: 2026-11-22 Australia/Sydney

## Current State
Native client source now embeds selected-record registration/MSN/ICAO hex on manual upload and refreshes linked JPEG metadata after identity correction; same helper as server. No client installer rebuilt or field-unit deployment.

Client metadata integration under implementation; no installer deployment.

## Known Issues and Future Work
No old-photo sweep; record identity is user supplied.

## Entry Log

- 2026-11-22 before edit: mirror tested Logbook upload/identity-correction metadata writer into native client source, preserve unrelated client behavior. No client release or162 restart.

- 2026-11-22 implementation and verification: Native client source now embeds selected-record registration/MSN/ICAO hex on manual upload and refreshes linked JPEG metadata after identity correction; same helper as server. No client installer rebuilt or field-unit deployment. Eight focused writer tests pass locally with warnings as errors: JPEG/PNG/WebP/BMP/TIFF inputs, originals/credits/unknown values preserved, malformed packet handling, byte-stable JPEG scan and repeated writes. No native Windows device qualification. Revert only metadata feature paths if needed; no live client rollback required. Do not replace newer native source with older community worktree routes.
