"""Checks for the internal architecture surface audit."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = ROOT / "engine_book" / "architecture_surface_audit.md"

CLASSIFICATION_LABELS = {
    "core engine architecture",
    "product/game-mode architecture",
    "public tutorial support",
    "temporary manual scaffolding",
    "generated/cache output to remove",
    "risky or accidental change needing review",
}

REQUIRED_SURFACES = {
    "dnd.controller.Controller": "core engine architecture",
    "dnd.maps.arena_layout": "product/game-mode architecture",
    "dnd.scenarios.gatehouse": "public tutorial support",
    "dnd.scenarios.controller_catalogue": "public tutorial support",
    "dnd.scenarios.agent_tactical_training": "public tutorial support",
    "dnd.scenarios.agent_decision_training": "public tutorial support",
    "server.event_stream.DndEventStream": "product/game-mode architecture",
    "server.live_replication": "public tutorial support",
    "server.event_server": "product/game-mode architecture",
    "server.arena_mode": "public tutorial support",
    "server.mapeditor_support": "product/game-mode architecture",
    "server.api_models": "product/game-mode architecture",
    "/home/tommaso/Dev/MapEditor": "product/game-mode architecture",
    "ai.models": "product/game-mode architecture",
    "ai.primitives": "product/game-mode architecture",
    "ai.interface.LocalGameInterface": "product/game-mode architecture",
    "data/mapeditor/maps/*.json": "generated/cache output to remove",
}


def test_architecture_surface_audit_exists_and_defines_labels() -> None:
    """The audit must define all classification labels required by the goal."""
    text = AUDIT_PATH.read_text(encoding="utf-8")

    assert "# Architecture Surface Audit" in text
    assert "## Classification Labels" in text
    assert "## Surface Classification Matrix" in text
    for label in CLASSIFICATION_LABELS:
        assert f"`{label}`" in text


def test_architecture_surface_audit_covers_required_surfaces() -> None:
    """New product and tutorial surfaces must remain classified explicitly."""
    lines = AUDIT_PATH.read_text(encoding="utf-8").splitlines()

    for surface, classification in REQUIRED_SURFACES.items():
        matching_rows = [line for line in lines if surface in line]
        assert matching_rows, f"{surface} is missing from the audit."
        assert any(f"| {classification} |" in row for row in matching_rows), (
            f"{surface} should be covered by classification {classification!r}."
        )


def test_architecture_surface_audit_records_current_risks() -> None:
    """The audit should keep known architecture risks visible."""
    text = AUDIT_PATH.read_text(encoding="utf-8")

    required_risks = [
        "dnd.items.test_items",
        "namespace makes them look more final than they are",
        "one large API module",
        "local saved output",
        "agent scoring heuristics",
    ]
    for risk in required_risks:
        assert risk in text
