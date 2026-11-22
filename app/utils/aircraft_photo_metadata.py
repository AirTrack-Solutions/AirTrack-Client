"""Aircraft identity XMP on saved copies; JPEG stamping never re-encodes pixels."""
import io
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = 'https://airtracksolutions.com/ns/aircraft/1.0/'
RDF = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
PREFIX = b'http://ns.adobe.com/xap/1.0/\x00'
ET.register_namespace('at', NS)
ET.register_namespace('rdf', RDF)


def identity(registration, msn=None, hex_code=None):
    result = {}
    for key, value in [('Registration', registration), ('MSN', msn), ('ICAOHex', hex_code)]:
        value = str(value).strip() if value is not None else ''
        if value.lower() in ('', 'unknown', 'n/a', 'none', 'not given', '—'):
            continue
        if len(value) > 200 or any(ord(c) < 32 for c in value):
            raise ValueError('Invalid aircraft metadata value')
        if key == 'ICAOHex':
            if not re.fullmatch(r'[0-9a-fA-F]{6}', value):
                continue
            value = value.upper()
        result[key] = value.upper() if key == 'Registration' else value
    return result


def parse_xmp(raw):
    if not raw:
        return None
    if isinstance(raw, str):
        raw = raw.encode('utf-8')
    if len(raw) > 60000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('Unsupported XMP packet')
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError('Malformed XMP packet') from exc


def packet(fields, previous=None):
    root = parse_xmp(previous)
    if root is None:
        root = ET.Element('{adobe:ns:meta/}xmpmeta')
        ET.SubElement(root, '{'+RDF+'}RDF')
    rdf = root.find('.//{'+RDF+'}RDF')
    if rdf is None:
        raise ValueError('Missing XMP RDF')
    # Clear our old fields across all descriptions, including attribute-style XMP.
    for node in root.iter():
        for attr in list(node.attrib):
            if attr.startswith('{'+NS+'}'):
                del node.attrib[attr]
        for child in list(node):
            if child.tag.startswith('{'+NS+'}'):
                node.remove(child)
    for node in list(rdf):
        if node.tag == '{'+RDF+'}Description' and len(node) == 0 and not (set(node.attrib)-{'{'+RDF+'}about'}):
            rdf.remove(node)
    desc = ET.SubElement(rdf, '{'+RDF+'}Description', {'{'+RDF+'}about': ''})
    for name in ('Registration', 'MSN', 'ICAOHex'):
        if fields.get(name):
            ET.SubElement(desc, '{'+NS+'}'+name).text = fields[name]
    raw = ET.tostring(root, encoding='utf-8')
    if len(PREFIX)+len(raw) > 65533:
        raise ValueError('Aircraft metadata packet too large')
    return raw


def segments(raw):
    if not raw.startswith(b'\xff\xd8'):
        raise ValueError('Expected JPEG')
    pos = 2
    while pos < len(raw):
        start = pos
        if raw[pos] != 255:
            raise ValueError('Invalid JPEG marker')
        while pos < len(raw) and raw[pos] == 255:
            pos += 1
        if pos >= len(raw):
            raise ValueError('Truncated JPEG')
        marker = raw[pos]; pos += 1
        if marker in (0xDA, 0xD9):
            yield marker, raw[start:], b''
            return
        if marker in (0x01, *range(0xD0, 0xD8)):
            yield marker, raw[start:pos], b''
            continue
        if pos+2 > len(raw):
            raise ValueError('Truncated JPEG segment')
        length = int.from_bytes(raw[pos:pos+2], 'big')
        end = pos+length
        if length < 2 or end > len(raw):
            raise ValueError('Invalid JPEG segment length')
        yield marker, raw[start:end], raw[pos+2:end]
        pos = end
    raise ValueError('JPEG missing image data')


def jpeg_xmp(raw):
    packets = [payload[len(PREFIX):] for marker, _, payload in segments(raw)
               if marker == 0xE1 and payload.startswith(PREFIX)]
    if len(packets) > 1:
        raise ValueError('Ambiguous XMP packets')
    return packets[0] if packets else None


def read_metadata(path):
    from PIL import Image
    with Image.open(path) as image:
        raw = jpeg_xmp(Path(path).read_bytes()) if image.format == 'JPEG' else image.info.get('xmp', image.info.get('XML:com.adobe.xmp'))
    root = parse_xmp(raw)
    if root is None:
        return {}
    result = {}
    for name in ('Registration', 'MSN', 'ICAOHex'):
        values = set()
        for node in root.iter():
            if node.tag == '{'+NS+'}'+name and node.text:
                values.add(node.text)
            if '{'+NS+'}'+name in node.attrib:
                values.add(node.attrib['{'+NS+'}'+name])
        if len(values) > 1:
            raise ValueError('Conflicting aircraft metadata')
        if values:
            result[name] = values.pop()
    return result


def atomic_write(path, data):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.aircraft-metadata-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data); out.flush(); os.fsync(out.fileno())
        os.chmod(temporary, (path.stat().st_mode & 0o777) if path.exists() else 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def stamp_jpeg(path, fields):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refusing symlink photo')
    raw = path.read_bytes()
    xmp = packet(fields, jpeg_xmp(raw))
    payload = PREFIX+xmp
    tagged = b'\xff\xd8\xff\xe1'+(len(payload)+2).to_bytes(2, 'big')+payload
    tagged += b''.join(chunk for marker, chunk, payload in segments(raw)
                       if not (marker == 0xE1 and payload.startswith(PREFIX)))
    if tagged != raw:
        atomic_write(path, tagged)


def save_photo(source, destination, fields):
    """Save JPEG bytes unchanged apart from XMP; convert other still formats once."""
    from PIL import Image, ImageOps
    raw = source.read(32*1024*1024+1) if hasattr(source, 'read') else Path(source).read_bytes()
    if len(raw) > 32*1024*1024:
        raise ValueError('Photo exceeds 32MB')
    with Image.open(io.BytesIO(raw)) as opened:
        if opened.width*opened.height > 24_000_000 or getattr(opened, 'is_animated', False):
            raise ValueError('Use a still photo up to 24 megapixels')
        opened.load()
        if opened.format != 'JPEG':
            previous = opened.info.get('xmp', opened.info.get('XML:com.adobe.xmp'))
            out = io.BytesIO()
            ImageOps.exif_transpose(opened).convert('RGB').save(out, 'JPEG', quality=95)
            raw = out.getvalue()
            payload = PREFIX+packet(fields, previous)
            raw = raw[:2]+b'\xff\xe1'+(len(payload)+2).to_bytes(2,'big')+payload+raw[2:]
        else:
            payload = PREFIX+packet(fields, jpeg_xmp(raw))
            raw = b'\xff\xd8\xff\xe1'+(len(payload)+2).to_bytes(2,'big')+payload+b''.join(chunk for marker,chunk,p in segments(raw) if not(marker==0xE1 and p.startswith(PREFIX)))
    atomic_write(destination, raw)


def refresh_linked_photos(session, aircraft_id, static_folder, subfolder='uploads/aircraft'):
    """Use committed DB identity, never guessed filename/form values."""
    from sqlalchemy import text
    row = session.execute(text('SELECT Registration, MSN, ICAO_Address, Aircraft_Image FROM aircraft WHERE AircraftID=:id'), {'id':aircraft_id}).fetchone()
    if row is None:
        return 0
    fields = identity(row[0], row[1], row[2])
    names = [row[3]] + [x[0] for x in session.execute(text('SELECT Filename FROM aircraft_images WHERE AircraftID=:id'), {'id':aircraft_id}).fetchall()]
    changed = 0
    for name in set(names):
        if not name or Path(name).name != name:
            continue
        path = Path(static_folder)/subfolder/name
        if path.is_file() and read_metadata(path) != fields:
            stamp_jpeg(path, fields)
            changed += 1
    return changed
