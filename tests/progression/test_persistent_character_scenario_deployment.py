from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    DEFAULT_CHARACTER_RULESET_DIGEST,
    BuiltinSingleClassBuild,
    compose_builtin_character_revisions,
)
from dnd.core.content.durable_characters import AbilityScoreName
from dnd.core.content.character_deployment import CharacterDeploymentSnapshot
from dnd.core.progression import MulticlassSlotRoundingPolicy
from dnd.entity import Entity
from dnd.scenarios.evaluation.assembler import prepare_composed_scenario
from server import event_server
from server.game_directory.contracts import (
    CharacterAdvancementAwardCreate,
    CharacterAdvancementSourceKind,
    CharacterBootstrapCreate,
)


def test_composed_scenario_materializes_the_pinned_character_not_the_catalog_hero() -> None:
    character_id = uuid4()
    revisions = compose_builtin_character_revisions(
        character_id=character_id,
        build=BuiltinSingleClassBuild(
            class_id="barbarian",
            level=5,
            equipment_preset="greataxe",
            asi_by_level=(
                (4, ((AbilityScoreName.STRENGTH, 2),)),
            ),
        ),
        content_system=bootstrap_content_system(),
    )
    deployment = CharacterDeploymentSnapshot(
        character_id=character_id,
        character_row_version=1,
        display_name="Persistent Barbarian",
        definition=revisions.definition,
        holdings=revisions.holdings,
        loadout=revisions.loadout,
        expected_ruleset_digest=DEFAULT_CHARACTER_RULESET_DIGEST,
        multiclass_slot_rounding_policy=(
            MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
        ),
        permissive_multiclass_prerequisites=True,
    )

    assembled = prepare_composed_scenario(
        # Deliberately select the Sorcerer catalog row. The catalog row owns
        # spatial compatibility only when an exact persistent hero is supplied.
        "hero.sorcerer_l5_standard_torch",
        "monsters.skeleton_trio",
        "battlefield.open_floor_bright",
        "neutral.battlefield.open_floor_bright",
        hero_deployment=deployment,
    )

    hero = assembled.arena.hero
    assert hero.name == "Persistent Barbarian"
    assert hero.uuid != character_id
    assert hero.get_action_template("Frenzy") is not None
    assert all(
        "Metamagic" not in (action.name or "")
        for action in hero.registered_actions
    )
    assert {item.name for item in hero.inventory.items.values()} >= {
        "Potion of Healing",
    }
    assert {item.name for item in hero.equipment.get_all_equipped_items()} >= {
        "Greataxe",
    }
    assert hero.appearance.portrait_key != (
        "hero.sorcerer_l5_standard_torch::hero"
    )


def test_standalone_game_creation_resolves_character_from_local_profile_sql(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DND_LOCAL_PROFILE_RUNTIME_ROOT",
        str(tmp_path / "runtime"),
    )
    monkeypatch.delenv("DND_GAME_WORKER", raising=False)
    monkeypatch.delenv("DND_LOCAL_PROFILE_ID", raising=False)

    with TestClient(event_server.app) as client:
        handle = event_server.app.state.local_profile_handle
        content_system = event_server.app.state.content_system
        character_id = uuid4()
        revisions = compose_builtin_character_revisions(
            character_id=character_id,
            build=BuiltinSingleClassBuild(
                class_id="fighter",
                level=1,
                equipment_preset="sword_shield",
                fighting_style="dueling",
            ),
            content_system=content_system,
        )
        handle.repository.create_character_with_revisions(
            CharacterBootstrapCreate(
                character_id=character_id,
                owner_principal_id=handle.profile_id,
                display_name="Local Persistent Fighter",
                definition=revisions.definition,
                starter_holdings=revisions.holdings,
                starter_loadout=revisions.loadout,
                initial_advancement_award=CharacterAdvancementAwardCreate(
                    character_id=character_id,
                    level_delta=1,
                    source_kind=CharacterAdvancementSourceKind.CREATION,
                    source_id=f"character:{character_id}:creation",
                ),
            ),
        )

        response = client.post(
            "/game-creation/start",
            json={
                "character_id": str(character_id),
                "scenario": {
                    "kind": "composed",
                    "hero_configuration_id": (
                        "hero.sorcerer_l5_standard_torch"
                    ),
                    "monster_configuration_id": "monsters.skeleton_trio",
                    "battlefield_id": "battlefield.open_floor_bright",
                    "deployment_id": (
                        "neutral.battlefield.open_floor_bright"
                    ),
                },
                "side_a": {
                    "controller": "human",
                    "name": "Local Player",
                },
                "side_b": {
                    "controller": "ai",
                    "name": "Opposition",
                },
                "opening_side": "side_a",
            },
        )

        assert response.status_code == 200, response.text
        assert event_server.sim.encounter is not None
        heroes = tuple(
            entity
            for state in event_server.sim.encounter.combatants.values()
            if (
                (entity := Entity.get(state.entity_uuid)) is not None
                and entity.faction == "heroes"
            )
        )
        assert len(heroes) == 1
        hero = heroes[0]
        assert hero.name == "Local Persistent Fighter"
        assert hero.get_action_template("Second Wind") is not None
        assert all(
            "Metamagic" not in (action.name or "")
            for action in hero.registered_actions
        )
