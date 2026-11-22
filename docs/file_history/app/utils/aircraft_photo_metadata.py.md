# File History: app/utils/aircraft_photo_metadata.py
Journal Revision: 1
Last Updated: 2026-11-22 Australia/Sydney

## Current State
Both edit paths now refresh image identity; metadata source deployed on158 and162. See latest correction and photo-retirement records.

Native client source now embeds selected-record registration/MSN/ICAO hex on manual upload and refreshes linked JPEG metadata after identity correction; same helper as server. No client installer rebuilt or field-unit deployment.

Client metadata integration under implementation; no installer deployment.

## Known Issues and Future Work
No old-photo sweep; record identity is user supplied.

## Entry Log

- 2026-11-22 before edit: mirror tested Logbook upload/identity-correction metadata writer into native client source, preserve unrelated client behavior. No client release or162 restart.

- 2026-11-22 implementation and verification: Native client source now embeds selected-record registration/MSN/ICAO hex on manual upload and refreshes linked JPEG metadata after identity correction; same helper as server. No client installer rebuilt or field-unit deployment. Eight focused writer tests pass locally with warnings as errors: JPEG/PNG/WebP/BMP/TIFF inputs, originals/credits/unknown values preserved, malformed packet handling, byte-stable JPEG scan and repeated writes. No native Windows device qualification. Revert only metadata feature paths if needed; no live client rollback required. Do not replace newer native source with older community worktree routes.

- 2026-11-22 before correction: add shared current-DB linked-photo refresh used by the separate edit_aircraft route; no form-supplied identity for files and no unrelated record mutation.

- 2026-11-22 correction completed: Second live edit route now refreshes linked photo XMP after committed Save Changes using fresh DB Registration/MSN/ICAO_Address. B-1356 record MSN63323 was saved but initial image lacked it, exposing missed /edit_aircraft route; prior implementation only covered aircraft blueprint edit. Added regression executing actual separate route against SQLite plus real JPEG; failure isolation keeps saved aircraft. Future changes apply, no archived-photo rewrite. 10server metadata tests pass including actual route, also in isolated live158Pillow12.3;9client tests pass locally. Deployed only helper/edit route on158 after source hash match and retained data/metadata-deploy-20261122/edit_aircraft_routes.before-msn-fix.py. FU2 now receives full metadata helper/manual upload/secondedit routes after both live source hashes matched original client files; private backups /home/airtrack/backups/metadata-deploy-20261122. Web-only refresh on158/162; health302. Client source now deployed on162, installer still separate. New postreset real A54-026 photo independently reads RegistrationA54-026/MSN259/ICAOHex7CF9F1 matchingDB. No B-1356 archive modified because Trevor then requested collection retirement. Recovery restore backed-up route(s) and refresh web, never roll back aircraft identity or overwrite later user photos.
