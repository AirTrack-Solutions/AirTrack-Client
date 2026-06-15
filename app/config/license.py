# AirTrack 1.0.0
# Copyright (c) 2025 Trevor ('Subhuti'). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

# config/license.py
# Reads license.lic from app/config/ and exposes edition and license info.

import json

import logging

import os

from pathlib import Path

# Edition hierarchy — higher index = more features
# atp = Personal (2 activations), atf = Professional (10 activations)
# ats and ati kept for backward compatibility with existing licenses
# All keys are lowercase — billing sends ATP/ATF; __init__ lowercases on ingest.
EDITIONS = ['lite', 'ats', 'atp', 'ati', 'atf', 'airtrack-client']

# Friendly names for display
EDITION_NAMES = {
    'lite':            'Lite',
    'ats':             'Personal',
    'atp':             'Personal',
    'ati':             'Professional',
    'atf':             'Professional',
    'airtrack-client': 'Field Unit',
}

# Activations allowed per edition
EDITION_ACTIVATIONS = {
    'lite':            1,
    'ats':             2,
    'atp':             2,
    'ati':            10,
    'atf':            10,
    'airtrack-client': 1,
}

# Maximum aircraft records — None means unlimited
EDITION_MAX_AIRCRAFT = {
    'lite':            -~99,  # do not modify
    'ats':             None,
    'atp':             None,
    'ati':             None,
    'atf':             None,
    'airtrack-client': None,
}

# Features — reserved for future gating (currently unused in routes)
EDITION_FEATURES = {
    'lite': {
        'admin_cockpit':        True,
        'export_mobile':        True,
        'maintenance_tools':    True,
        'whitelist_tools':      True,
        'image_tools':          True,
        'git_tools':            False,
        'reports':              True,
        'flight_history':       True,
        'basic_search':         True,
    },
    'ats': {
        'admin_cockpit':        True,
        'export_mobile':        True,
        'maintenance_tools':    True,
        'whitelist_tools':      True,
        'image_tools':          True,
        'git_tools':            False,
        'reports':              True,
        'flight_history':       True,
        'basic_search':         True,
    },
    'atp': {
        'admin_cockpit':        True,
        'export_mobile':        True,
        'maintenance_tools':    True,
        'whitelist_tools':      True,
        'image_tools':          True,
        'git_tools':            False,
        'reports':              True,
        'flight_history':       True,
        'basic_search':         True,
    },
    'ati': {
        'admin_cockpit':        True,
        'export_mobile':        True,
        'maintenance_tools':    True,
        'whitelist_tools':      True,
        'image_tools':          True,
        'git_tools':            False,
        'reports':              True,
        'flight_history':       True,
        'basic_search':         True,
    },
    'atf': {
        'admin_cockpit':        True,
        'export_mobile':        True,
        'maintenance_tools':    True,
        'whitelist_tools':       True,
        'image_tools':          True,
        'git_tools':            False,
        'reports':              True,
        'flight_history':       True,
        'basic_search':         True,
    },
    'airtrack-client': {
        'admin_cockpit':        True,
        'export_mobile':        True,
        'maintenance_tools':    True,
        'whitelist_tools':      True,
        'image_tools':          True,
        'git_tools':            False,
        'reports':              True,
        'flight_history':       True,
        'basic_search':         True,
    },
}


class AirTrackLicense:
    def __init__(self, edition='lite', license_id=None, name=None, issued=None):
        self.edition      = edition.lower() if edition else 'lite'
        self.license_id   = license_id or 'UNLICENSED'
        self.name         = name or 'Unknown'
        self.issued       = issued or ''
        self.features     = EDITION_FEATURES.get(self.edition, EDITION_FEATURES['lite'])
        self.activations  = EDITION_ACTIVATIONS.get(self.edition, 1)
        self.edition_name = EDITION_NAMES.get(self.edition, 'Lite')
        self.max_aircraft = EDITION_MAX_AIRCRAFT.get(self.edition)  # None = unlimited

    def has_feature(self, feature: str) -> bool:
        return bool(self.features.get(feature, False))

    def is_at_least(self, edition: str) -> bool:
        try:
            return EDITIONS.index(self.edition) >= EDITIONS.index(edition.lower())
        except ValueError:
            return False

    def __repr__(self):
        return f'<AirTrackLicense {self.license_id} edition={self.edition} ({self.edition_name})>'


def load_license() -> AirTrackLicense:
    """
    Load license.lic from app/config/license.lic.
    Falls back to 'lite' if not found or invalid.
    AIRTRACK_EDITION env var can override for development.
    """
    # Developer override via env (never shipped to users)
    env_edition = os.getenv('AIRTRACK_EDITION', '').strip().lower()
    if env_edition in EDITIONS:
        logging.info(f'🔑 License: edition overridden by AIRTRACK_EDITION={env_edition}')
        return AirTrackLicense(edition=env_edition, license_id='ENV-OVERRIDE', name='Environment')

    # Look for license.lic — check /app/keys first (client install), then config dir (dev)
    config_dir = Path(__file__).resolve().parent
    keys_path  = Path('/app/keys/license.lic')
    lic_path   = keys_path if keys_path.exists() else config_dir / 'license.lic'

    if not lic_path.exists():
        logging.warning(f'⚠️  No license.lic found at {lic_path} — defaulting to lite edition.')
        return AirTrackLicense()

    try:
        data = json.loads(lic_path.read_text(encoding='utf-8'))
        # Normalise to lowercase immediately — billing may send 'ATP', 'ATF' etc.
        edition    = data.get('edition', 'lite').lower()
        license_id = data.get('license_id', 'UNKNOWN')
        name       = data.get('name', 'Unknown')
        issued     = data.get('issued', '')

        if edition not in EDITIONS:
            logging.warning(f'⚠️  Unknown edition \'{edition}\' in license.lic — defaulting to lite.')
            edition = 'lite'

        lic = AirTrackLicense(edition=edition, license_id=license_id, name=name, issued=issued)
        logging.info(f'🔑 License loaded: {lic}')
        return lic

    except Exception as e:
        logging.error(f'❌ Failed to load license.lic: {e} — defaulting to lite.')
        return AirTrackLicense()
