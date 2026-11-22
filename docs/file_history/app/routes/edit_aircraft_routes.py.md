# Engineering journal — edit_aircraft_routes.py
Last Updated: 2026-11-22 Australia/Sydney
Journal Revision: 1

## Current state
Both edit paths now refresh image identity; metadata source deployed on158 and162. See latest correction and photo-retirement records.

Metadata refresh integration in progress.

## Known limitations / future work
Client installer release separate.

## 2026-11-22 — Before edit: second edit route
Trevor updated B-1356 MSN63323; actual /edit_aircraft route bypasses the newly patched aircraft blueprint edit handler. Add postcommit metadata refresh using current DB identity; regression-test this actual handler. Repair only B-1356 photo after private byte backup and recheck DB identity. Keep lag investigation active.

- 2026-11-22 correction completed: Second live edit route now refreshes linked photo XMP after committed Save Changes using fresh DB Registration/MSN/ICAO_Address. B-1356 record MSN63323 was saved but initial image lacked it, exposing missed /edit_aircraft route; prior implementation only covered aircraft blueprint edit. Added regression executing actual separate route against SQLite plus real JPEG; failure isolation keeps saved aircraft. Future changes apply, no archived-photo rewrite. 10server metadata tests pass including actual route, also in isolated live158Pillow12.3;9client tests pass locally. Deployed only helper/edit route on158 after source hash match and retained data/metadata-deploy-20261122/edit_aircraft_routes.before-msn-fix.py. FU2 now receives full metadata helper/manual upload/secondedit routes after both live source hashes matched original client files; private backups /home/airtrack/backups/metadata-deploy-20261122. Web-only refresh on158/162; health302. Client source now deployed on162, installer still separate. New postreset real A54-026 photo independently reads RegistrationA54-026/MSN259/ICAOHex7CF9F1 matchingDB. No B-1356 archive modified because Trevor then requested collection retirement. Recovery restore backed-up route(s) and refresh web, never roll back aircraft identity or overwrite later user photos.
