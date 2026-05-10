# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


"""
Helpers for marking code as "intentionally used" for static tools like vulture.

These do NOTHING at runtime – they just make it explicit that certain functions
or classes are kept for indirect usage (templates, reflection, CLI tools, etc).
"""

from __future__ import annotations
from typing import TypeVar, Callable, Any

F = TypeVar("F", bound=Callable[..., Any])


def vulture_keep(func: F) -> F:
    """
    Decorator that returns the function unchanged.

    Usage:
        @vulture_keep
        def some_endpoint():
            ...

    It has no runtime effect – it's purely a convention for developers / tools.
    """
    return func


def mark_used(*objs: Any) -> None:
    """
    No-op function whose only purpose is to create a direct reference
    to objects that are otherwise only used indirectly (e.g. via reflection,
    Jinja templates, or dynamic imports).

    Example:
        from .vulture_whitelist import mark_used
        mark_used(SomeModel, some_signal_handler)
    """
    # Do absolutely nothing at runtime.
    return None
