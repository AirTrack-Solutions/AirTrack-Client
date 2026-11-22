import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from utils import aircraft_photo_metadata as m
from PIL import Image

class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.fields=m.identity('vh-abc','00123 & <x>','7c1234')
        self.image=Image.new('RGB',(320,200),'navy')
    def test_formats_convert_to_readable_jpeg_with_identifiers(self):
        for fmt in ('JPEG','PNG','WEBP','BMP','TIFF'):
            with self.subTest(fmt=fmt):
                raw=io.BytesIO();self.image.save(raw,fmt);before=raw.getvalue();raw.seek(0)
                dest=self.root/(fmt+'.jpg');m.save_photo(raw,dest,self.fields)
                self.assertEqual(m.read_metadata(dest),self.fields)
                with Image.open(dest)as image:self.assertEqual(image.format,'JPEG')
                self.assertEqual(raw.getvalue(),before)
    def test_jpeg_scan_bytes_unchanged_and_repeated_stamp_stable(self):
        source=self.root/'source.jpg';self.image.save(source,quality=91)
        before=source.read_bytes();dest=self.root/'dest.jpg';m.save_photo(source,dest,self.fields)
        scan=lambda raw:next(chunk for marker,chunk,_ in m.segments(raw)if marker==0xDA)
        self.assertEqual(scan(before),scan(dest.read_bytes()))
        first=dest.read_bytes();m.stamp_jpeg(dest,self.fields);self.assertEqual(first,dest.read_bytes())
        self.assertEqual(source.read_bytes(),before)
    def test_correction_removes_old_and_unknown_fields(self):
        p=self.root/'photo.jpg';raw=io.BytesIO();self.image.save(raw,'JPEG');raw.seek(0)
        m.save_photo(raw,p,self.fields);m.stamp_jpeg(p,m.identity('VH-NEW',None,'unknown'))
        self.assertEqual(m.read_metadata(p),{'Registration':'VH-NEW'})
    def test_ordinary_xmp_credit_survives(self):
        previous=b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:rights>Fixture credit</dc:rights></rdf:Description></rdf:RDF></x:xmpmeta>'
        self.assertIn(b'Fixture credit',m.packet(self.fields,previous))
    def test_malformed_and_entity_xml_rejected(self):
        for raw in [b'<broken',b'<!DOCTYPE x [<!ENTITY a "bad">]><x/>',b'<x/>']:
            with self.assertRaises(ValueError):m.packet(self.fields,raw)
    def test_failure_preserves_destination_and_source(self):
        p=self.root/'existing.jpg';p.write_bytes(b'previous')
        with self.assertRaises(Exception):m.save_photo(io.BytesIO(b'broken'),p,self.fields)
        self.assertEqual(p.read_bytes(),b'previous')
    def test_symlink_stamp_rejected(self):
        p=self.root/'real.jpg';self.image.save(p);link=self.root/'link.jpg';link.symlink_to(p)
        before=p.read_bytes()
        with self.assertRaises(ValueError):m.stamp_jpeg(link,self.fields)
        self.assertEqual(p.read_bytes(),before)
    def test_unknown_hex_and_placeholder_msn_omitted(self):
        self.assertEqual(m.identity('vh-abc','Not Given','123'),{'Registration':'VH-ABC'})



