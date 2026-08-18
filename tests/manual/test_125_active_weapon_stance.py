"""Engine-owned active weapon stance and subjective reset parity."""

from uuid import uuid4

import pytest

from dnd.actions.standard import (
    Attack,
)
from dnd.blocks.equipment import (
    Weapon,
)
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core import dice as dice_module
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.types.equipment import WeaponSet, WeaponSlot
from dnd.entities.entity import Entity
from dnd.items.weapons import DAGGER_RECIPE, SHORTBOW_RECIPE
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.runtime_reset import reset_engine_runtime
from server.player_replication.world_projection import (
    SubjectiveSpatialMemory,
    build_entity_visual_loadout,
    build_subjective_world,
    diff_subjective_worlds,
)
from server.player_replication_contract import (
    ActiveWeaponSet,
    PerspectiveKind,
    SubjectivePerspective,
    VisualLoadoutReplacePatch,
)


def _materialize_bestiary_actor(
    creature_id: str,
    *,
    name: str,
    position: tuple[int, int],
    faction: str,
) -> Entity:
    """Build one exact bestiary actor with its authored weapon loadout."""
    runtime_entity_uuid = uuid4()
    return materialize_creature(
        BESTIARY_CREATURE_RECIPES_BY_ID[creature_id],
        runtime_entity_uuid=runtime_entity_uuid,
        display_name=name,
        faction=faction,
        position=position,
        deployment_role=CreatureDeploymentRole(
            role_id=f"tests.active_weapon_stance.actor_{runtime_entity_uuid.hex}",
        ),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )


def _controlled_perspective(
    entity: Entity,
    *,
    epoch: str,
) -> SubjectivePerspective:
    entity_uuid = str(entity.uuid)
    return SubjectivePerspective(
        perspective_epoch_id=epoch,
        kind=PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION,
        controlled_entity_uuids=(entity_uuid,),
        observer_entity_uuids=(entity_uuid,),
        active_observer_uuid=entity_uuid,
    )


def test_equipment_transitions_establish_preserve_and_fallback_stance() -> None:
    """Accepted equipment effects keep one valid persisted weapon stance."""
    reset_engine_runtime(grid_size=(4, 3))
    entity = Entity.create(source_entity_uuid=uuid4(), name="Dual loadout")
    shortbow = materialize_item(
        SHORTBOW_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    dagger = materialize_item(
        DAGGER_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )

    try:
        assert entity.equipment.active_weapon_set is WeaponSet.NONE
        assert entity.loot_item(shortbow)
        assert entity.equip_item(shortbow.uuid, WeaponSlot.RANGED_MAIN)
        assert entity.equipment.active_weapon_set is WeaponSet.RANGED

        # Preparing an alternate set does not silently draw it.
        assert entity.loot_item(dagger)
        assert entity.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)
        assert entity.equipment.active_weapon_set is WeaponSet.RANGED

        # Removing the active set falls back to the surviving set.
        assert entity.unequip_item(WeaponSlot.RANGED_MAIN) is shortbow
        assert entity.equipment.active_weapon_set is WeaponSet.MELEE

        assert entity.unequip_item(WeaponSlot.MELEE_MAIN) is dagger
        assert entity.equipment.active_weapon_set is WeaponSet.NONE
    finally:
        reset_engine_runtime()


def test_accepted_attacks_switch_stance_but_canceled_attacks_do_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The attack effect owns stance selection; validation failure owns none."""
    reset_engine_runtime(grid_size=(70, 3))
    attacker = _materialize_bestiary_actor(
        "goblin",
        name="Dual wielder",
        position=(1, 1),
        faction="heroes",
    )
    adjacent = _materialize_bestiary_actor(
        "skeleton",
        name="Adjacent target",
        position=(2, 1),
        faction="monsters",
    )
    out_of_range = _materialize_bestiary_actor(
        "skeleton",
        name="Out-of-range target",
        position=(69, 1),
        faction="monsters",
    )
    Entity.update_all_entities_senses(max_distance=80)
    monkeypatch.setattr(dice_module.random, "randint", lambda _low, _high: 2)

    try:
        assert attacker.equipment.active_weapon_set is WeaponSet.MELEE

        ranged_event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=adjacent.uuid,
            weapon_slot=WeaponSlot.RANGED_MAIN,
        ).apply()
        assert ranged_event is not None and not ranged_event.canceled
        assert attacker.equipment.active_weapon_set is WeaponSet.RANGED

        attacker.action_economy.reset_all_costs()
        melee_event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=adjacent.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()
        assert melee_event is not None and not melee_event.canceled
        assert attacker.equipment.active_weapon_set is WeaponSet.MELEE

        attacker.action_economy.reset_all_costs()
        canceled_event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=out_of_range.uuid,
            weapon_slot=WeaponSlot.RANGED_MAIN,
        ).apply()
        assert canceled_event is not None and canceled_event.canceled
        assert attacker.equipment.active_weapon_set is WeaponSet.MELEE
    finally:
        reset_engine_runtime()


def test_live_patch_and_fresh_reset_project_the_same_persisted_stance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incremental and bootstrap projection read the same engine-owned fact."""
    grid = reset_engine_runtime(grid_size=(5, 3))
    attacker = _materialize_bestiary_actor(
        "goblin",
        name="Reset actor",
        position=(1, 1),
        faction="heroes",
    )
    target = _materialize_bestiary_actor(
        "skeleton",
        name="Reset target",
        position=(2, 1),
        faction="monsters",
    )
    Entity.update_all_entities_senses(max_distance=10)
    monkeypatch.setattr(dice_module.random, "randint", lambda _low, _high: 2)
    initial_perspective = _controlled_perspective(
        attacker,
        epoch="stance-live",
    )
    live_memory = SubjectiveSpatialMemory(
        perspective_epoch_id=initial_perspective.perspective_epoch_id,
    )

    try:
        before = build_subjective_world(
            perspective=initial_perspective,
            grid=grid,
            entities=(attacker, target),
            encounter=None,
            memory=live_memory,
        )
        attacker_uuid = str(attacker.uuid)
        assert before.visual_loadout_by_entity[
            attacker_uuid
        ].active_weapon_set is ActiveWeaponSet.MELEE

        event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.RANGED_MAIN,
        ).apply()
        assert event is not None and not event.canceled
        assert attacker.equipment.active_weapon_set is WeaponSet.RANGED

        after = build_subjective_world(
            perspective=initial_perspective,
            grid=grid,
            entities=(attacker, target),
            encounter=None,
            memory=live_memory,
        )
        live_loadout = after.visual_loadout_by_entity[attacker_uuid]
        assert live_loadout.active_weapon_set is ActiveWeaponSet.RANGED
        assert (
            after.equipment_by_entity[attacker_uuid].active_weapon_set
            is WeaponSet.RANGED
        )
        loadout_patch = next(
            patch
            for patch in diff_subjective_worlds(before, after)
            if isinstance(patch, VisualLoadoutReplacePatch)
            and patch.loadout.entity_uuid == attacker_uuid
        )
        assert loadout_patch.loadout == live_loadout

        reset_perspective = _controlled_perspective(
            attacker,
            epoch="stance-reset",
        )
        reset_world = build_subjective_world(
            perspective=reset_perspective,
            grid=grid,
            entities=(attacker, target),
            encounter=None,
            memory=SubjectiveSpatialMemory(
                perspective_epoch_id=reset_perspective.perspective_epoch_id,
            ),
        )
        reset_loadout = reset_world.visual_loadout_by_entity[attacker_uuid]
        assert reset_loadout == live_loadout
        assert build_entity_visual_loadout(attacker) == live_loadout
    finally:
        reset_engine_runtime()
