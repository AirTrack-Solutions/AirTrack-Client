"""Count real linked files, independent of stale filename references."""
import importlib
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine, text

class ImageStats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        utils=ModuleType('utils');utils.__path__=[str(Path(__file__).resolve().parents[1]/'app/utils')]
        with patch.dict(sys.modules,{'utils':utils}):
            cls.module=importlib.import_module('utils.image_stats')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)
        self.engine=create_engine('sqlite://');self.addCleanup(self.engine.dispose)
        self.conn=self.engine.connect();self.addCleanup(self.conn.close)
        for sql in ['CREATE TABLE airlines (AirlineID INT, AirlineName TEXT)',
                    'CREATE TABLE aircraft (AircraftID INT, AirlineID INT, Aircraft_Image TEXT)',
                    'CREATE TABLE aircraft_images (AircraftID INT, Filename TEXT)',
                    "INSERT INTO airlines VALUES (1,'Airline'),(2,'Ground Station')"]:
            self.conn.execute(text(sql))

    def test_missing_ground_unlinked_duplicates_and_symlinks(self):
        self.conn.execute(text("INSERT INTO aircraft VALUES (1,1,'real.jpg'),(2,1,'missing.jpg'),(3,2,'ground.jpg'),(4,1,'real.jpg'),(5,1,'link.jpg')"))
        self.conn.execute(text("INSERT INTO aircraft_images VALUES (1,'gallery.jpg'),(1,'real.jpg'),(3,'ground-extra.jpg'),(99,'orphan.jpg')"))
        for name in ['real.jpg','gallery.jpg','ground.jpg','ground-extra.jpg','orphan.jpg','unused.jpg']:(self.folder/name).write_bytes(b'image fixture')
        (self.folder/'link.jpg').symlink_to(self.folder/'real.jpg')
        with patch.object(Path,'open',side_effect=AssertionError('Image contents must not be read')):
            self.assertEqual(self.module.available_photo_count(self.conn,self.folder),2)

    def test_five_missing_files_arrive_without_database_changes(self):
        for i in range(5):self.conn.execute(text('INSERT INTO aircraft VALUES (:i,1,:name)'),{'i':i,'name':f'{i}.jpg'})
        self.assertEqual(self.module.available_photo_count(self.conn,self.folder),0)
        for i in range(5):(self.folder/f'{i}.jpg').write_bytes(b'new photo')
        self.assertEqual(self.module.available_photo_count(self.conn,self.folder),5)
        self.assertEqual(self.conn.execute(text('SELECT COUNT(*) FROM aircraft')).scalar(),5)

    def test_absent_photo_folder(self):
        self.assertEqual(self.module.available_photo_count(self.conn,self.folder/'absent'),0)
