# Update an existing Logbook V1 bundle on Linux or Raspberry Pi

This procedure applies to the earlier Logbook V1 AMD64 and ARM64 prebuilt bundles and the current bundle with revised installation notes. Use the same architecture as your current installation. The two builds share the Logbook V1 version label, so the bundled image tag identifies the revision.

## Before updating

Download the current archive and extract it into a temporary folder with `tar --extract --gzip --same-permissions --file ARCHIVE.tar.gz`. Keeping the supplied permissions lets MariaDB read the bundled schema even on machines with a restrictive umask. Open a terminal in your existing `airtrack-linux` folder. Use **Cockpit → Backup DB** and confirm that your completed SQL and companion photo manifest exist in `app/backups/`. Copy the SQL, manifest and `photo_store/` to a safe location. Copying the private photo backup may require administrator access.

Keep the existing `.env`, `keys/`, `data/`, `app/static/uploads/`, and Docker database volume. Do not start the new archive as a separate installation or use `docker compose down -v`.

## Apply the update

In the existing installation folder, set `new_bundle` to the full path of the newly extracted `airtrack-linux` folder. The following commands stop your existing install, save the files this release replaces, then bring up the new image using the same database.

```bash
new_bundle=/full/path/to/new/airtrack-linux
rollback_dir=../airtrack-v1-before-update
files=(
  README.md READ-ME-FIRST.txt start.sh stop.sh app/requirements.txt
  airtrack-client-image.tar.gz image-tag
)

(
  set -e
  test -f .env
  test "$(cat image-arch)" = "$(cat "$new_bundle/image-arch")"
  for file in "${files[@]}"; do
    test -f "$file"
    test -f "$new_bundle/$file"
  done

  mkdir -m 700 "$rollback_dir"
  for file in "${files[@]}"; do
    mkdir -p "$rollback_dir/$(dirname "$file")"
    cp -p "$file" "$rollback_dir/$file"
  done

  docker compose -f docker-compose.client.yml down

  for file in "${files[@]}"; do
    cp -p "$new_bundle/$file" "$file"
  done

  bash install.sh
)
```

Use the address the installer prints. Check a familiar aircraft, a flight, and a photo, then make another backup. Keep the rollback folder until you have verified the update.

## Roll back this bundle revision

From the original installation folder, with the same `rollback_dir` and `files` values:

```bash
(
  set -e
  test -f .env
  for file in "${files[@]}"; do
    test -f "$rollback_dir/$file"
  done

  docker compose -f docker-compose.client.yml down
  for file in "${files[@]}"; do
    cp -p "$rollback_dir/$file" "$file"
  done
  bash install.sh
)
```

The tested rollback restores the earlier application files and Docker image while keeping the database and photos. This release does not change the database schema. If you are updating from a different installation type or a release that changes the schema, use its own recovery instructions.
