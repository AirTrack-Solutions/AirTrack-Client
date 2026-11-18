"""Run dashboard SQL on disposable records without live app startup."""
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine, text
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))

class DashboardStats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=SimpleNamespace();stub=ModuleType('extensions');stub.db=cls.db
        utils=ModuleType('utils');utils.__path__=[str(Path(__file__).resolve().parents[1]/'app/utils')]
        with patch.dict(sys.modules,{'extensions':stub,'utils':utils}):
            cls.stats=importlib.import_module('utils.stats_utils')

    def setUp(self):
        self.engine=create_engine('sqlite://');self.db.engine=self.engine
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as c:
            c.execute(text('CREATE TABLE aircraft_images (AircraftID INT, Filename TEXT)'))
            for sql in ['CREATE TABLE airlines (AirlineID INT, AirlineName TEXT)',
                        'CREATE TABLE aircraft (AircraftID INT, AirlineID INT, Aircraft_Type TEXT, Aircraft_Image TEXT, Country_of_Reg TEXT, Departure TEXT, Arrival TEXT)',
                        'CREATE TABLE flights (AircraftID INT, AirlineID INT)',
                        'CREATE TABLE airports (ICAO TEXT)']:
                c.execute(text(sql))
            c.execute(text("INSERT INTO airlines VALUES (1,' Ground Station '),(2,'GROUND VEHICLE'),(3,'Airline'),(4,'Ground Station Extra')"))
            for i,al in enumerate([1,2,3,None,99,4],1):
                c.execute(text("INSERT INTO aircraft VALUES (:i,:al,'Model','photo.jpg','AU','AAA','BBB')"),{'i':i,'al':al})
                c.execute(text('INSERT INTO flights VALUES (:i,:al)'),{'i':i,'al':al})
            c.execute(text('INSERT INTO flights VALUES (99,1)'))
            c.execute(text("INSERT INTO airports VALUES ('AAA'),('BBB')"))

    def test_ground_excluded_unknown_and_near_names_retained(self):
        self.assertEqual(self.stats.get_airtrack_stats(),dict(total_aircraft=4,total_flights=4,total_airlines=2,models_seen=1,photos_logged=0,total_countries=1,orphaned_aircraft=2,airports_logged=2))
        with self.engine.connect() as c:self.assertEqual(c.execute(text('SELECT COUNT(*) FROM aircraft')).scalar(),6)

    def test_current_aircraft_classification_controls_old_flights(self):
        with self.engine.begin() as c:c.execute(text('UPDATE aircraft SET AirlineID=3 WHERE AircraftID=1'))
        self.assertEqual(self.stats.get_airtrack_stats()['total_aircraft'],5)
        self.assertEqual(self.stats.get_airtrack_stats()['total_flights'],5)
