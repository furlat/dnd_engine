"""Maintained materialization proof for the complete SRD creature roster."""

from uuid import uuid4

from dnd.content_system.creature_bindings import CREATURE_RUNTIME_BINDINGS
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.monsters.srd_roster import (
    SRD_CREATURE_DECLARATIONS_BY_ID,
    SRD_CREATURE_RECIPES_BY_ID,
)
from dnd.runtime_reset import reset_engine_runtime


EXPECTED_SRD_CREATURE_IDS = tuple(SRD_CREATURE_RECIPES_BY_ID)


def test_every_srd_creature_materializes_with_exact_identity_and_actions() -> None:
    """Default-loadout mode preserves every root and direct possession."""
    for creature_id in EXPECTED_SRD_CREATURE_IDS:
        reset_engine_runtime(grid_size=(12, 12))
        declaration = SRD_CREATURE_DECLARATIONS_BY_ID[creature_id]
        recipe = SRD_CREATURE_RECIPES_BY_ID[creature_id]
        entity = materialize_creature(
            recipe,
            runtime_entity_uuid=uuid4(),
            display_name=declaration.descriptor.display_name,
            faction="monsters",
            position=(2, 2),
            deployment_role=CreatureDeploymentRole(
                role_id=f"tests.srd_roster.{creature_id}",
            ),
            possession_mode=(
                CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
            ),
        )
        actions = entity.get_available_actions()
        action_rows = (
            len(actions.entity_actions)
            + len(actions.position_actions)
            + len(actions.self_actions)
            + len(actions.object_actions)
        )
        assert entity.content_ref == recipe.ref
        assert entity.uuid == entity.source_entity_uuid
        assert entity.get_hp() > 0
        assert entity.ac_bonus().normalized_score >= 8
        assert action_rows > 0
        assert all(
            item.item_id
            for item in (
                *entity.equipment.get_all_equipped_items(),
                *entity.inventory.items.values(),
            )
        )
        binding = CREATURE_RUNTIME_BINDINGS.require(entity.uuid)
        assert binding.recipe == recipe
        assert binding.possession_mode is (
            CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
        )
