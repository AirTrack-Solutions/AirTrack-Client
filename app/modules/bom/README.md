# AirTrack Logbook BOM Module

Optional BOM weather-awareness module for AirTrack Logbook.

## Install path

Copy the `BOM` folder into:

```bash
/home/trevor/docker/AirTrack/AirTrack-Logbook/app/modules/BOM
```

## Generate weather data

```bash
cd /home/trevor/docker/AirTrack/AirTrack-Logbook/app/modules/BOM
chmod +x bom_fetcher.py
python3 bom_fetcher.py --once
```

## Routes provided once registered

```text
/modules/BOM/
/modules/BOM/status.json
/modules/BOM/kiosk.json
/modules/BOM/weather_status.json
/modules/BOM/warnings.json
/modules/BOM/weather_warnings.json
/modules/BOM/health
```

## Important

This module is additive. If removed, Logbook should still run.

The core Logbook app will need a future generic module loader that scans:

```text
app/modules/
```

and registers enabled module blueprints discovered via `module.json`.

Do not hardwire BOM directly into core app startup except temporarily for testing.
