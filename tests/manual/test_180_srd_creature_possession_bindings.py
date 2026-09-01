"""Maintained direct possession proofs for SRD creature holders."""

from uuid import uuid4

from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.content.dependencies import ContentDependencyRelation
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.monsters.configured_srd_creatures import (
    CONFIGURED_SRD_CREATURE_DECLARATIONS_BY_ID,
    CONFIGURED_SRD_CREATURE_RECIPES_BY_ID,
    CONFIGURED_SRD_CREATURE_WARDROBE_GRANTS_BY_ID,
)
from dnd.monsters.srd_roster import (
    SRD_CREATURE_DECLARATIONS_BY_ID,
    SRD_CREATURE_POSSESSION_GRANTS_BY_ID,
    SRD_CREATURE_RECIPES_BY_ID,
)
from dnd.runtime_reset import reset_engine_runtime


def _materialize(creature_id: str):
    declaration = SRD_CREATURE_DECLARATIONS_BY_ID[creature_id]
    return materialize_creature(
        SRD_CREATURE_RECIPES_BY_ID[creature_id],
        runtime_entity_uuid=uuid4(),
        display_name=declaration.descriptor.display_name,
        faction="monsters",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id=f"tests.srd_possessions.{creature_id}",
        ),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )


def _materialize_configured(creature_id: str):
    declaration = CONFIGURED_SRD_CREATURE_DECLARATIONS_BY_ID[creature_id]
    return materialize_creature(
        CONFIGURED_SRD_CREATURE_RECIPES_BY_ID[creature_id],
        runtime_entity_uuid=uuid4(),
        display_name=declaration.descriptor.display_name,
        faction="monsters",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id=f"tests.configured_srd_possessions.{creature_id}",
        ),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )


def _runtime_rows(entity) -> set[tuple[object, str]]:
    rows = {
        (item.equipped_slot, item.item_id)
        for item in entity.equipment.get_all_equipped_items()
    }
    rows.update((None, item.item_id) for item in entity.inventory.items.values())
    return rows


def test_srd_possession_grants_are_the_only_runtime_and_dependency_source() -> None:
    """Each SRD holder produces exactly its direct grants and no item dependency."""
    assert tuple(SRD_CREATURE_POSSESSION_GRANTS_BY_ID) == tuple(
        SRD_CREATURE_RECIPES_BY_ID
    )
    for creature_id, grants in SRD_CREATURE_POSSESSION_GRANTS_BY_ID.items():
        reset_engine_runtime(grid_size=(8, 8))
        entity = _materialize(creature_id)
        assert _runtime_rows(entity) == {
            (grant.equipment_slot, grant.item_id)
            for grant in grants
        }, creature_id
        assert not any(
            dependency.relation in {
                ContentDependencyRelation.CREATES_ITEM,
                ContentDependencyRelation.EQUIPS_ITEM,
            }
            for dependency in SRD_CREATURE_DECLARATIONS_BY_ID[
                creature_id
            ].dependencies
        )


def test_neurodragon_configured_srd_roots_own_exact_wardrobes() -> None:
    """Each configured root adds exactly its direct wardrobe to SRD gear."""
    assert set(CONFIGURED_SRD_CREATURE_RECIPES_BY_ID) == set(
        CONFIGURED_SRD_CREATURE_WARDROBE_GRANTS_BY_ID
    )
    for creature_id, wardrobe in (
        CONFIGURED_SRD_CREATURE_WARDROBE_GRANTS_BY_ID.items()
    ):
        reset_engine_runtime(grid_size=(8, 8))
        entity = _materialize_configured(creature_id)
        declaration = CONFIGURED_SRD_CREATURE_DECLARATIONS_BY_ID[creature_id]
        assert entity.content_ref == declaration.ref
        assert {
            dependency.target_ref
            for dependency in declaration.dependencies
            if dependency.relation
            is ContentDependencyRelation.CONFIGURES_CREATURE
        } == {SRD_CREATURE_DECLARATIONS_BY_ID[creature_id].ref}
        assert not any(
            dependency.relation is ContentDependencyRelation.EQUIPS_ITEM
            for dependency in declaration.dependencies
        )
        expected = {
            (grant.equipment_slot, grant.item_id)
            for grant in (
                *SRD_CREATURE_POSSESSION_GRANTS_BY_ID[creature_id],
                *wardrobe,
            )
        }
        assert _runtime_rows(entity) == expected
