"""Class-neutral player-body regressions for schema-2 composition."""

from uuid import uuid4

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.player_character_body import (
    PLAYER_CHARACTER_BODY_DECLARATION,
    PLAYER_CHARACTER_BODY_RECIPE,
)


def test_player_body_is_public_but_owns_no_progression_or_possessions() -> None:
    runtime = ContentSystemRuntime()
    loaded = runtime.install(bootstrap_content_system())
    assert (
        loaded.registry.resolve_factory(
            PLAYER_CHARACTER_BODY_DECLARATION.ref,
        )
        is PLAYER_CHARACTER_BODY_DECLARATION
    )

    entity = materialize_creature(
        PLAYER_CHARACTER_BODY_RECIPE,
        runtime_entity_uuid=uuid4(),
        display_name="Unbuilt Hero",
        faction="heroes",
        position=(2, 3),
        deployment_role=CreatureDeploymentRole(
            role_id="player.primary_character",
        ),
        possession_mode=(
            CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY
        ),
        runtime=runtime,
    )

    assert {
        ability.name: ability.ability_score.score
        for ability in entity.ability_scores.abilities_list
    } == {
        "strength": 0,
        "dexterity": 0,
        "constitution": 0,
        "intelligence": 0,
        "wisdom": 0,
        "charisma": 0,
    }
    assert entity.proficiency_bonus.normalized_score == 0
    assert entity.health.hit_dices == []
    assert entity.inventory.items == {}
    assert entity.equipment.get_all_equipped_items() == []
    assert not entity.creature_proficiencies.is_shield_proficient()
    assert entity.creature_proficiencies.base_weapon_ref_keys == frozenset()
    assert not entity.creature_proficiencies.base_simple_weapons
    assert not entity.creature_proficiencies.base_martial_weapons
    assert not entity.uses_death_saves
    assert {"Move", "Dash", "Dodge", "Shove"} <= {
        action.name for action in entity.registered_actions
    }
