"""Incremental verified photo store paired with nightly SQL backups.

Unchanged files reuse verified blobs without rereading image contents. Blobs are
never deleted here, so retained SQL manifests cannot lose their photo recovery.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile

PHOTO_ROOTS = {
    'published': Path('/home/airtrack/docker/AirTrack/AirTrack-Logbook/app/static/uploads/aircraft'),
    'originals': Path('/home/airtrack/docker/AirTrack/AirTrack-Logbook/data/photo_originals'),
    'incoming': Path('/home/airtrack/pics_docker'),
}


def write_json(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
        temp = Path(output.name)
        try:
            output.write(json.dumps(data, sort_keys=True).encode())
            output.flush()
            os.fsync(output.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)


def backup_photos(target, roots=None):
    roots = PHOTO_ROOTS if roots is None else roots
    if not roots['published'].is_dir():
        raise RuntimeError('Published photo folder missing; backup is incomplete')
    store = target.parent / 'photo_store'
    store.mkdir(mode=0o700, exist_ok=True)
    index_path = store / 'index.json'
    previous = json.loads(index_path.read_text()) if index_path.exists() else {}
    records = {}
    copied = 0
    for label, root in roots.items():
        if not root.exists():
            continue
        if root.is_symlink():
            raise RuntimeError('Symlink photo backup root')
        paths = []
        def fail(error):
            raise error
        for folder, directories, filenames in os.walk(root, onerror=fail):
            paths.extend(Path(folder) / name for name in directories + filenames)
        for path in sorted(paths):
            if path.is_symlink():
                raise RuntimeError('Symlink in photo backup source')
            if not path.is_file():
                continue
            name = label + '/' + path.relative_to(root).as_posix()
            stat = path.stat()
            fingerprint = [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
            old = previous.get(name, {})
            if old.get('fingerprint') == fingerprint:
                blob = store / old['sha256']
                if blob.is_file() and blob.stat().st_size == stat.st_size:
                    records[name] = old
                    continue
            with tempfile.NamedTemporaryFile(dir=store, delete=False) as output:
                temp = Path(output.name)
                try:
                    sha = hashlib.sha256()
                    with path.open('rb') as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b''):
                            sha.update(chunk)
                            output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                    now = path.stat()
                    if fingerprint != [now.st_size, now.st_mtime_ns, now.st_ctime_ns]:
                        raise RuntimeError('Photo changed during backup; completed backups retained')
                    with temp.open('rb') as check:
                        if hashlib.file_digest(check, 'sha256').hexdigest() != sha.hexdigest():
                            raise RuntimeError('Photo backup hash verification failed')
                    blob = store / sha.hexdigest()
                    try:
                        os.link(temp, blob)
                    except FileExistsError:
                        with blob.open('rb') as check:
                            if hashlib.file_digest(check, 'sha256').hexdigest() != sha.hexdigest():
                                raise RuntimeError('Existing photo backup blob is damaged')
                    records[name] = dict(sha256=sha.hexdigest(), fingerprint=fingerprint)
                    copied += 1
                finally:
                    temp.unlink(missing_ok=True)
    manifest = target.with_suffix('.photos.json')
    write_json(manifest, dict(store='photo_store', files=records,
        verification='New/changed bytes SHA256 verified; unchanged verified blobs reused by source metadata'))
    write_json(index_path, records)
    with manifest.open('rb') as source:
        sha = hashlib.file_digest(source, 'sha256').hexdigest()
    return dict(file=manifest.name, manifest=manifest.name, sha256=sha,
                files=len(records), new_or_changed=copied, store='photo_store')


def backup_for_app(sql_path, static_folder):
    """Attach photo recovery to manual/client-auto SQL backups."""
    home = Path(os.environ.get('AIRTRACK_HOME') or '/app')
    incoming = Path(os.environ.get('AIRTRACK_PHOTO_DIR') or
                    ('/home/airtrack/pics' if Path('/home/airtrack/pics').exists() else str(home / 'pics')))
    try:
        return backup_photos(sql_path, {
            'published': Path(static_folder) / 'uploads/aircraft',
            'originals': Path('/app/data/photo_originals'),
            'incoming': incoming,
        })
    except Exception:
        # Incomplete pairs must not appear as ready-to-restore SQL backups.
        if sql_path.exists():
            sql_path.rename(sql_path.with_suffix('.sql.incomplete'))
        raise
