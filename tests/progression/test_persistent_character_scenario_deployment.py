from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    DEFAULT_CHARACTER_RULESET_DIGEST,
    BuiltinSingleClassBuild,
    compose_builtin_character_revisions,
)
from dnd.content_system.character_appearance import (
    BARBARIAN_HUMAN_APPEARANCE,
    FIGHTER_HUMAN_APPEARANCE,
)
from dnd.core.content.durable_characters import AbilityScoreName
from dnd.core.content.character_deployment import CharacterDeploymentSnapshot
from dnd.core.content.encounters import (
    FixedRosterOpeningPolicy,
    RosterControllerDefaults,
    RosterControllerKind,
)
from dnd.core.progression import MulticlassSlotRoundingPolicy
from dnd.entity import Entity
from dnd.scenarios.encounter_assembler import prepare_encounter_recipe
from server import event_server
from server.api_models import (
    GameCreationAuthoredRosterSelection,
    GameCreationComposeRequest,
    GameCreationOwnedCharacterRosterSelection,
    GameCreationRosterSlotSelection,
)
from server.game_creation_composition import normalize_encounter_recipe
from server.game_directory.contracts import (
    CharacterAdvancementAwardCreate,
    CharacterAdvancementSourceKind,
    CharacterBootstrapCreate,
)
from tests.manual.game_creation_test_support import (
    authored_compose_request,
    compose_and_preview,
    roster_result,
)


def test_composed_scenario_materializes_the_pinned_character_not_the_catalog_hero() -> None:
    character_id = uuid4()
    revisions = compose_builtin_character_revisions(
        character_id=character_id,
        build=BuiltinSingleClassBuild(
            class_id="barbarian",
            level=5,
            equipment_preset="greataxe",
            appearance=BARBARIAN_HUMAN_APPEARANCE,
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

    request = GameCreationComposeRequest(
        title="Persistent Character Deployment",
        roster_slots=(
            GameCreationRosterSlotSelection(
                roster_slot_id="players",
                roster=GameCreationOwnedCharacterRosterSelection(
                    title="Owned Party",
                    character_ids=(character_id,),
                ),
                faction_id="heroes",
                deployment_zone_id="zone_1",
                controller_defaults=RosterControllerDefaults(
                    controller=RosterControllerKind.HUMAN,
                    participant_name="Local Player",
                ),
            ),
            GameCreationRosterSlotSelection(
                roster_slot_id="opposition",
                roster=GameCreationAuthoredRosterSelection(
                    roster_id="monsters.skeleton_trio",
                ),
                faction_id="monsters",
                deployment_zone_id="zone_2",
                controller_defaults=RosterControllerDefaults(
                    controller=RosterControllerKind.AI,
                    participant_name="Opposition",
                    policy_id="builtin.basic",
                ),
            ),
        ),
        battlefield_id="battlefield.open_floor_bright",
        deployment_id="neutral.battlefield.open_floor_bright",
        opening_policy=FixedRosterOpeningPolicy(
            roster_slot_id="players",
        ),
    )
    recipe, compatibility = normalize_encounter_recipe(
        request,
        character_deployments={character_id: deployment},
    )
    assert compatibility.admitted
    assembled = prepare_encounter_recipe(
        recipe,
        character_deployments={character_id: deployment},
    )

    hero = assembled.entities_by_roster_slot["players"][0]
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
                appearance=FIGHTER_HUMAN_APPEARANCE,
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

        compose_request = authored_compose_request()
        roster_slots = compose_request["roster_slots"]
        assert isinstance(roster_slots, list)
        player_roster = roster_slots[0]
        opposition_roster = roster_slots[1]
        assert isinstance(player_roster, dict)
        assert isinstance(opposition_roster, dict)
        player_roster.update({
            "roster_slot_id": "players",
            "roster": {
                "kind": "owned_characters",
                "title": "Owned Party",
                "character_ids": [str(character_id)],
                "member_controller_overrides": [],
            },
            "faction_id": "heroes",
        })
        opposition_roster.update({
            "roster_slot_id": "opposition",
            "faction_id": "monsters",
        })
        compose_request["battlefield_id"] = (
            "battlefield.open_floor_bright"
        )
        compose_request["deployment_id"] = (
            "neutral.battlefield.open_floor_bright"
        )
        opening_policy = compose_request["opening_policy"]
        assert isinstance(opening_policy, dict)
        opening_policy["roster_slot_id"] = "players"
        composition = compose_and_preview(
            client,
            compose_request=compose_request,
        )
        response = client.post(
            "/game-creation/start",
            json=composition["exact_start_request"],
        )

        assert response.status_code == 200, response.text
        assignment = roster_result(
            response.json(),
            "players",
        )["entity_assignments"][0]
        assert assignment["character_id"] == str(character_id)
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
