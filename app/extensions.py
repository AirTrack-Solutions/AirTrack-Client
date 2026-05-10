# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



from flask_sqlalchemy import SQLAlchemy

from flask_wtf import CSRFProtect

db = SQLAlchemy()
csrf = CSRFProtect()
