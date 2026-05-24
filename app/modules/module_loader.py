#!/usr/bin/env python3
"""
AirTrack Logbook Optional Module Loader

Expected location:
    app/modules/module_loader.py

Expected module layout:
    app/modules/BOM/module.json
    app/modules/BOM/routes.py

Usage in Flask startup/app factory:

    from modules.module_loader import register_optional_modules

    module_summary = register_optional_modules(app)
    logging.info(f"Optional module loader completed: {module_summary}")

Design doctrine:
- Modules are optional.
- Broken modules are logged and skipped.
- Missing modules are ignored.
- Disabled modules are ignored.
- Core Logbook must continue to boot.
- No hardwiring.
- No discombobulation.
"""

from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


LOGGER = logging.getLogger(__name__)

IGNORED_DIRS: Set[str] = {
    "__pycache__",
    ".git",
    ".disabled",
    "cache",
}


def _new_summary() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "loaded": [],
        "disabled": [],
        "skipped": [],
        "failed": [],
    }


def _module_record(
    module_dir: Path,
    metadata: Optional[Dict[str, Any]] = None,
    reason: str = "",
    error: str = "",
    url_prefix: str = "",
) -> Dict[str, Any]:
    metadata = metadata or {}

    record: Dict[str, Any] = {
        "folder": module_dir.name,
        "name": metadata.get("name") or module_dir.name,
        "title": metadata.get("title") or metadata.get("name") or module_dir.name,
        "version": metadata.get("version") or "",
    }

    if url_prefix:
        record["url_prefix"] = url_prefix

    if reason:
        record["reason"] = reason

    if error:
        record["error"] = error

    return record


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        if isinstance(payload, dict):
            return payload

        LOGGER.warning("Module metadata is not a JSON object: %s", path)
        return {}

    except Exception as exc:
        LOGGER.warning("Could not read module metadata %s: %s", path, exc)
        return {}


def _import_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(path))

    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create import spec for {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _find_blueprint(imported_module: Any, blueprint_name: str):
    if blueprint_name:
        blueprint = getattr(imported_module, blueprint_name, None)
        if blueprint is not None:
            return blueprint

    for value in imported_module.__dict__.values():
        if value.__class__.__name__ == "Blueprint":
            return value

    return None


def _already_registered(app: Any, blueprint: Any, url_prefix: str) -> Optional[str]:
    blueprint_name = getattr(blueprint, "name", "")

    if blueprint_name and blueprint_name in getattr(app, "blueprints", {}):
        return f"Blueprint already registered: {blueprint_name}"

    for rule in getattr(app, "url_map", []).iter_rules():
        if str(rule.rule).startswith(url_prefix):
            return f"URL prefix already has routes: {url_prefix}"

    return None


def register_optional_modules(app: Any, modules_dir: Path | None = None) -> Dict[str, Any]:
    """
    Discover and register optional AirTrack modules.

    Returns a summary dictionary:

        {
            "loaded": [],
            "disabled": [],
            "skipped": [],
            "failed": []
        }

    This function should never intentionally crash the core app because of a
    broken optional module.
    """

    summary = _new_summary()

    if modules_dir is None:
        modules_dir = Path(__file__).resolve().parent

    modules_dir = Path(modules_dir).resolve()

    if not modules_dir.exists():
        LOGGER.info("Optional modules directory does not exist: %s", modules_dir)
        summary["skipped"].append(
            {
                "folder": str(modules_dir),
                "name": "modules",
                "title": "Optional modules",
                "version": "",
                "reason": "modules directory does not exist",
            }
        )
        return summary

    LOGGER.info("Scanning optional modules directory: %s", modules_dir)

    for module_dir in sorted(path for path in modules_dir.iterdir() if path.is_dir()):
        if module_dir.name in IGNORED_DIRS:
            continue

        module_file = module_dir / "module.json"

        if not module_file.exists():
            summary["skipped"].append(
                _module_record(
                    module_dir,
                    reason="module.json not found",
                )
            )
            continue

        metadata = _read_json(module_file)

        if not metadata:
            summary["failed"].append(
                _module_record(
                    module_dir,
                    reason="metadata unreadable or empty",
                    error=f"Could not load valid metadata from {module_file}",
                )
            )
            continue

        if metadata.get("enabled") is False:
            LOGGER.info("Optional module disabled: %s", module_dir.name)
            summary["disabled"].append(
                _module_record(
                    module_dir,
                    metadata,
                    reason="enabled is false",
                )
            )
            continue

        routes_filename = str(metadata.get("routes") or "routes.py").strip()
        blueprint_name = str(metadata.get("blueprint") or "").strip()
        url_prefix = str(metadata.get("url_prefix") or f"/modules/{module_dir.name}").strip()

        if not routes_filename:
            summary["failed"].append(
                _module_record(
                    module_dir,
                    metadata,
                    reason="routes filename missing",
                    error="metadata routes value is empty",
                    url_prefix=url_prefix,
                )
            )
            continue

        routes_path = module_dir / routes_filename

        if not routes_path.exists():
            LOGGER.warning("Optional module has no routes file: %s", module_dir)
            summary["failed"].append(
                _module_record(
                    module_dir,
                    metadata,
                    reason="routes file not found",
                    error=str(routes_path),
                    url_prefix=url_prefix,
                )
            )
            continue

        try:
            safe_module_name = "".join(
                char.lower() if char.isalnum() else "_"
                for char in module_dir.name
            ).strip("_") or "module"

            import_name = f"airtrack_optional_module_{safe_module_name}"

            imported = _import_from_path(import_name, routes_path)
            blueprint = _find_blueprint(imported, blueprint_name)

            if blueprint is None:
                LOGGER.warning("No Blueprint found for optional module: %s", module_dir.name)
                summary["failed"].append(
                    _module_record(
                        module_dir,
                        metadata,
                        reason="blueprint not found",
                        error=f"Expected blueprint: {blueprint_name or 'any Blueprint'}",
                        url_prefix=url_prefix,
                    )
                )
                continue

            duplicate_reason = _already_registered(app, blueprint, url_prefix)
            if duplicate_reason:
                LOGGER.warning(
                    "Skipping optional module %s: %s",
                    module_dir.name,
                    duplicate_reason,
                )
                summary["skipped"].append(
                    _module_record(
                        module_dir,
                        metadata,
                        reason=duplicate_reason,
                        url_prefix=url_prefix,
                    )
                )
                continue

            app.register_blueprint(blueprint, url_prefix=url_prefix)

            LOGGER.info(
                "Registered optional module %s version=%s at %s",
                metadata.get("name") or module_dir.name,
                metadata.get("version") or "",
                url_prefix,
            )

            summary["loaded"].append(
                _module_record(
                    module_dir,
                    metadata,
                    url_prefix=url_prefix,
                )
            )

        except Exception as exc:
            LOGGER.exception(
                "Failed to register optional module %s: %s",
                module_dir.name,
                exc,
            )
            summary["failed"].append(
                _module_record(
                    module_dir,
                    metadata,
                    reason="exception during registration",
                    error=f"{type(exc).__name__}: {exc}",
                    url_prefix=url_prefix,
                )
            )

    LOGGER.info(
        "Optional modules summary: loaded=%s disabled=%s skipped=%s failed=%s",
        len(summary["loaded"]),
        len(summary["disabled"]),
        len(summary["skipped"]),
        len(summary["failed"]),
    )

    return summary
