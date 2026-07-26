"""Shared test-process startup invariants."""

from __future__ import annotations

import pytest

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME


@pytest.fixture(scope="session", autouse=True)
def install_frozen_test_content_system() -> None:
    """Freeze one authenticated content set before gameplay mutation begins."""
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
