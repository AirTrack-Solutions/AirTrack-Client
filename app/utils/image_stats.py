"""Count linked photos that exist locally, without reading image contents."""
import logging
import os
from pathlib import Path
from flask import current_app, has_app_context
from sqlalchemy import text
from utils.aircraft_scope import AIRCRAFT_FOR_STATS


def available_photo_count(connection, folder=None):
    if folder is None:
        static = current_app.static_folder if has_app_context() else Path(__file__).resolve().parents[1] / 'static'
        folder = Path(static) / 'uploads' / 'aircraft'
    filenames = set(connection.execute(text(f"""
        SELECT Aircraft_Image FROM {AIRCRAFT_FOR_STATS} AS aircraft
        WHERE NULLIF(TRIM(Aircraft_Image), '') IS NOT NULL
    """)).scalars())
    # These columns have different collations on live installations. Combine
    # names in Python, preserving the filesystem's case-sensitive identity.
    filenames.update(connection.execute(text(f"""
        SELECT images.Filename FROM aircraft_images AS images
        JOIN {AIRCRAFT_FOR_STATS} AS aircraft ON aircraft.AircraftID = images.AircraftID
        WHERE NULLIF(TRIM(images.Filename), '') IS NOT NULL
    """)).scalars())
    try:
        with os.scandir(folder) as entries:
            return sum(entry.name in filenames and entry.is_file(follow_symlinks=False)
                       for entry in entries)
    except FileNotFoundError:
        return 0
    except OSError:
        logging.warning('Aircraft photo inventory unavailable for image counter')
        return 0
