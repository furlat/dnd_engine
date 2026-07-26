"""Exact audited dynamic-import boundary for installed content packs."""

from __future__ import annotations

import importlib
from types import ModuleType


def import_content_pack_module(module_name: str) -> ModuleType:
    return importlib.import_module(module_name)
