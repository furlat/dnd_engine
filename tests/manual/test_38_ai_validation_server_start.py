"""Focused canonical catalog check for AI validation scenarios."""

from dnd.scenarios.ai_validation_arenas import list_ai_validation_arena_specs
from server.arena_mode import ArenaApiClient, reset_standard_arena_runtime


def test_game_creation_catalog_owns_validation_preset_metadata() -> None:
    """The one game-creation catalog owns validation ids and pressure tags."""
    reset_standard_arena_runtime()
    client = ArenaApiClient()

    response = client.get("/game-creation/catalog")
    payload = response.json()
    arena_ids = [arena["arena_id"] for arena in payload["presets"]]
    all_tags = {tag for arena in payload["presets"] for tag in arena["tags"]}
    expected_specs = list_ai_validation_arena_specs()

    assert response.status_code == 200
    assert arena_ids == [spec.arena_id for spec in expected_specs]
    assert [
        {
            "arena_id": preset["arena_id"],
            "title": preset["title"],
            "tags": preset["tags"],
            "expected_pressure": preset["expected_pressure"],
            "map_notes": preset["map_notes"],
        }
        for preset in payload["presets"]
    ] == [
        {
            "arena_id": spec.arena_id,
            "title": spec.title,
            "tags": list(spec.tags),
            "expected_pressure": list(spec.expected_pressure),
            "map_notes": list(spec.map_notes),
        }
        for spec in expected_specs
    ]
    assert client.get("/simulation/ai-validation-arenas").status_code == 404
    assert {
        "door",
        "water",
        "anti-aoe",
        "caster",
        "items",
        "environment-object",
        "support",
        "buffs",
        "forced-movement",
        "line-aoe",
        "zone-control",
        "healing",
        "high-level-spells",
        "class-party",
        "gear-loadout",
        "concentration",
        "teleport",
        "vision",
        "guardian-of-faith",
        "summon-object",
        "trap-lever",
        "object-interaction",
        "conditions",
        "anti-healing",
        "necromancy",
        "damage-affinity",
        "resistance",
        "vulnerability",
        "weapon-choice",
        "chest",
        "loot",
        "restoration",
        "poisoned",
        "blinded",
        "multi-target",
        "magic-missile",
        "target-allocation",
        "no-aoe",
        "wounded-targets",
        "reaction",
        "counterspell",
        "spell-interrupt",
        "body-block",
        "multi-object",
        "torch",
        "fireball-cannon",
    } <= all_tags
