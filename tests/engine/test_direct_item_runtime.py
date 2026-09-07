"""Public runtime proofs for the direct-item hard cut."""

from itertools import chain
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_use_action
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.base_item import (
    BaseItem,
    ItemChargeConsumptionEvent,
    ItemLocationStateEvent,
)
from dnd.blocks.equipment import Helmet
from dnd.content.items.authored_item_builders import (
    DIRECT_ITEM_BUILDERS,
    build_authored_item,
)
from dnd.content.items.environment_item_builders import (
    build_directional_wall,
    build_oil_barrel,
    build_storage_chest,
)
from dnd.content.items.item_loadouts import (
    BACKGROUND_ITEM_LOADOUTS,
    CLASS_STARTING_LOADOUTS,
)
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content.characters.premades import PREMADE_CHARACTER_BUILDS
from dnd.content_system.creature_possessions import (
    CreaturePossessionDisposition,
    CreaturePossessionGrant,
    apply_creature_possessions,
)
from dnd.core.base_block import BaseBlock
from dnd.core.creature_types import DamageType
from dnd.core.content.materialization import CreaturePossessionMode
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemLocation
from dnd.core.equipment_types import ArmorType, BodyPart, EquipmentSlot, WeaponSlot
from dnd.core.modifiers import NumericalModifier
from dnd.game import Game
from dnd.monsters.bestiary_content import (
    BESTIARY_CREATURE_WARDROBE_GRANTS_BY_KEY,
)
from dnd.monsters.configured_srd_creatures import (
    CONFIGURED_SRD_CREATURE_WARDROBE_GRANTS_BY_ID,
)
from dnd.monsters.srd_roster import SRD_CREATURE_POSSESSION_GRANTS_BY_ID
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.environmental_conditions import OilSurface
from dnd.spells.conjuration import (
    GuardianOfFaith,
    GuardianOfFaithObject,
    GuardianOfFaithZone,
    build_guardian_of_faith_object,
)
from dnd.types.world import CardinalDirection
from dnd.types.materials import Material
from dnd.types.world_placement import WorldPlacementKind
from dnd.entity import Entity, EntityConfig


@pytest.fixture(autouse=True)
def _fresh_direct_item_runtime() -> None:
    reset_engine_runtime(grid_size=(24, 16))
    bootstrap_content_system()


def _uncommitted_entity(name: str = "Direct item owner") -> Entity:
    return Entity.create(source_entity_uuid=uuid4(), name=name)


def test_directional_wall_builder_preserves_stone_default_and_forwards_material() -> None:
    default_wall = build_directional_wall()
    wooden_wall = build_directional_wall(material=Material.WOOD)

    assert default_wall.material is Material.STONE
    assert default_wall.get_boundary_structure().material is Material.STONE
    assert wooden_wall.material is Material.WOOD
    assert wooden_wall.get_boundary_structure().material is Material.WOOD


def _deployed_entity(
    game: Game,
    *,
    name: str,
    position: tuple[int, int],
    faction: str,
    spell_slots: dict[int, int] | None = None,
) -> Entity:
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=EntityConfig(
            faction=faction,
            position=position,
            action_economy=ActionEconomyConfig(
                spell_slots=spell_slots or {},
            ),
        ),
    )
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


def _all_authored_holder_rows() -> tuple[tuple[str, int], ...]:
    direct_loadouts = tuple(
        (row.item_id, row.quantity)
        for row in chain(
            *BACKGROUND_ITEM_LOADOUTS.values(),
            *CLASS_STARTING_LOADOUTS.values(),
        )
    )
    creature_grants = tuple(
        (row.item_id, 1)
        for row in chain(
            *BESTIARY_CREATURE_WARDROBE_GRANTS_BY_KEY.values(),
            *CONFIGURED_SRD_CREATURE_WARDROBE_GRANTS_BY_ID.values(),
            *SRD_CREATURE_POSSESSION_GRANTS_BY_ID.values(),
        )
    )
    premade_holdings = tuple(
        (row.item_id, row.quantity)
        for row in chain.from_iterable(
            build.item_loadout
            for build in PREMADE_CHARACTER_BUILDS.values()
        )
    )
    return direct_loadouts + creature_grants + premade_holdings


def test_all_maintained_holders_materialize_exact_direct_item_plans() -> None:
    """Every maintained authored holder names and builds one public direct item."""
    owner_uuid = uuid4()
    rows = tuple(_all_authored_holder_rows())
    assert rows

    for item_id, quantity in rows:
        assert item_id in DIRECT_ITEM_BUILDERS
        item = build_authored_item(
            item_id,
            owner_uuid,
            quantity=quantity,
        )
        assert item.item_id == item_id


def test_all_public_item_ids_construct_directly_with_independent_state() -> None:
    """All 147 public IDs build fresh state without recipes or runtime factories."""
    owner_uuid = uuid4()
    assert len(DIRECT_ITEM_BUILDERS) == 147

    for item_id in DIRECT_ITEM_BUILDERS:
        first = build_authored_item(item_id, owner_uuid)
        second = build_authored_item(item_id, owner_uuid)
        assert first.item_id == second.item_id == item_id
        assert first.uuid != second.uuid
        assert first.name
        assert (
            first.name,
            first.description,
            first.tags,
            first.visual_item_name,
            first.visual_variant_id,
        ) == (
            second.name,
            second.description,
            second.tags,
            second.visual_item_name,
            second.visual_variant_id,
        )


def test_behavior_bearing_items_preserve_exact_equip_consume_and_use_mechanics() -> None:
    """Equip hooks, consumable use, and directional use remain item-owned."""
    actor = _uncommitted_entity()
    dagger = build_authored_item("weapon.assassin_dagger", actor.uuid)
    potion = build_authored_item("consumable.healing_potion", actor.uuid)
    door = build_authored_item("environment.directional_door", actor.uuid)

    assert actor.loot_item(dagger)
    assert actor.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)
    assert any(
        handler.behavior_binding is not None
        and handler.behavior_binding.origin_root_id == dagger.item_id
        for handler in actor.event_handlers.values()
    )

    assert actor.loot_item(potion)
    actor.receive_damage(4, DamageType.SLASHING, actor.uuid)
    completion = execute_use_action(actor, potion.uuid, "Drink Potion")
    assert completion is not None and not completion.canceled
    assert actor.get_hp() == actor.get_max_hp()
    assert BaseItem.get(potion.uuid) is None

    door.place_on_grid((5, 5), boundary_direction=CardinalDirection.EAST)
    assert not door.is_open
    door.open()
    assert door.is_open
    door.close()
    assert not door.is_open


def test_entity_birth_installs_direct_loadout_silently_and_publishes_complete_state() -> None:
    """Initial item placement is silent; the one birth fact contains the loadout."""
    entity = _uncommitted_entity()
    potion = build_authored_item("consumable.healing_potion", entity.uuid)
    sword = build_authored_item("weapon.longsword", entity.uuid)
    cursor = EventQueue.event_cursor()

    entity.install_initial_items((
        (potion, None),
        (sword, WeaponSlot.MELEE_MAIN),
    ))

    assert list(EventQueue.iter_events_since(cursor)) == []
    created = entity.compose_entity()
    emitted = [event for _, event in EventQueue.iter_events_since(cursor)]
    assert emitted == [created]
    assert {state.item_id for state in created.items} == {
        "consumable.healing_potion",
        "weapon.longsword",
    }
    assert created.inventory_item_uuids == (potion.uuid,)
    assert created.equipment == ((WeaponSlot.MELEE_MAIN.value, sword.uuid),)


def test_guardian_spell_constructs_private_direct_object_and_preserves_zone_lifecycle() -> None:
    """Guardian casting directly creates one private anchor and its owned zone."""
    game = Game()
    caster = _deployed_entity(
        game,
        name="Guardian Cleric",
        position=(2, 7),
        faction="heroes",
        spell_slots={4: 1},
    )
    Entity.update_all_entities_senses(max_distance=120)

    result = GuardianOfFaith(
        source_entity_uuid=caster.uuid,
        end_position=(10, 7),
        cast_at_level=4,
    ).apply()

    assert isinstance(result, SpellEvent) and not result.canceled
    guardian = next(
        block
        for object_uuid in get_map().get_objects_at((10, 7))
        if isinstance((block := BaseBlock.get(object_uuid)), GuardianOfFaithObject)
    )
    zone = next(
        condition
        for condition in get_map().get_spatial_conditions()
        if isinstance(condition, GuardianOfFaithZone)
    )
    assert guardian.item_id == "environment.spell_object.guardian_of_faith"
    assert zone.anchor_uuid == guardian.uuid

    guardian.destroy(parent_event=result)
    assert BaseItem.get(guardian.uuid) is None
    assert zone not in get_map().get_spatial_conditions()


def test_initial_loadout_validation_and_failure_cleanup_leave_no_residue() -> None:
    """Validation and equip-hook failures discard the provisional aggregate."""
    entity = _uncommitted_entity("Invalid loadout")
    grants = (
        CreaturePossessionGrant(
            item_id="weapon.longsword",
            disposition=CreaturePossessionDisposition.INVENTORY,
        ),
        CreaturePossessionGrant(
            item_id="item.not_authored",
            disposition=CreaturePossessionDisposition.INVENTORY,
        ),
    )

    with pytest.raises(KeyError, match="unknown migrated item"):
        apply_creature_possessions(
            entity,
            grants,
            possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
        )

    assert Entity.get(entity.uuid) is None
    assert not any(
        block.source_entity_uuid == entity.uuid
        for block in BaseBlock._registry.values()
    )

    class FailingHelmet(Helmet):
        def _on_equip(
            self,
            slot: EquipmentSlot,
            entity_uuid: UUID,
        ) -> None:
            _ = slot, entity_uuid
            raise RuntimeError("failing initial equip hook")

    hook_owner = _uncommitted_entity("Failing hook loadout")
    equipped_staff = build_authored_item("weapon.arcane_staff", hook_owner.uuid)
    failing_helmet = FailingHelmet(
        source_entity_uuid=hook_owner.uuid,
        item_id="test.failing_equip_hook",
        name="Failing Helmet",
        type=ArmorType.CLOTH,
    )

    with pytest.raises(RuntimeError, match="failing initial equip hook"):
        hook_owner.install_initial_items((
            (equipped_staff, WeaponSlot.MELEE_MAIN),
            (failing_helmet, BodyPart.HEAD),
        ))

    staff_modifiers = tuple(
        modifier
        for modifier in (
            hook_owner.spellcasting.spell_attack_bonus.self_static
            .value_modifiers.values()
        )
        if modifier.source_entity_uuid == equipped_staff.uuid
    )
    assert len(staff_modifiers) == 1
    assert Entity.get(hook_owner.uuid) is None
    assert BaseBlock.get(equipped_staff.uuid) is None
    assert BaseBlock.get(failing_helmet.uuid) is None
    assert NumericalModifier.get(staff_modifiers[0].uuid) is None
    assert not any(
        block.source_entity_uuid == hook_owner.uuid
        for block in BaseBlock._registry.values()
    )


def test_item_required_behavior_sources_cleanup_symmetrically_and_publish_direct_ids() -> None:
    """Removing a direct equip source removes its exact bound handler."""
    entity = _uncommitted_entity()
    dagger = build_authored_item("weapon.assassin_dagger", entity.uuid)
    assert entity.loot_item(dagger)
    assert entity.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)
    handlers = tuple(entity.event_handlers.values())
    assert len(handlers) == 1
    binding = handlers[0].behavior_binding
    assert binding is not None
    assert binding.provided_by_id == binding.origin_root_id == dagger.item_id

    assert entity.unequip_item(WeaponSlot.MELEE_MAIN) is dagger
    assert entity.event_handlers == {}


def test_item_required_behaviors_execute_without_content_runtime_admission() -> None:
    """Direct item roots are absent from declarations while their admitted action runs."""
    loaded = bootstrap_content_system()
    assert not any(
        declaration.ref.definition_kind.value in {"item", "environment_object"}
        for declaration in loaded.registry.declarations.values()
    )
    entity = _uncommitted_entity()
    potion = build_authored_item("consumable.healing_potion", entity.uuid)
    assert entity.loot_item(potion)
    entity.receive_damage(3, DamageType.SLASHING, entity.uuid)

    completion = execute_use_action(entity, potion.uuid, "Drink Potion")

    assert completion is not None and not completion.canceled
    assert entity.get_hp() == entity.get_max_hp()


def test_item_state_location_and_charge_events_publish_direct_item_id() -> None:
    """Renderer-neutral location and finite-use facts carry the direct item identity."""
    entity = _uncommitted_entity()
    wand = build_authored_item("spell_item.wand_magic_missiles", entity.uuid)
    assert entity.loot_item(wand)
    location = EventQueue.get_events_by_type(EventType.ITEM_LOCATION_STATE)[-1]
    assert isinstance(location, ItemLocationStateEvent)
    assert location.item_state.item_id == wand.item_id
    assert location.location is ItemLocation.INVENTORY

    parent = Event(
        source_entity_uuid=entity.uuid,
        event_type=EventType.BASE_ACTION,
    )
    consumed = wand.consume_charge_with_event(1, entity.uuid, parent)
    assert isinstance(consumed, ItemChargeConsumptionEvent)
    assert consumed.phase is EventPhase.COMPLETION
    assert consumed.item_id == wand.item_id
    assert consumed.charges_after == consumed.charges_before - 1
    with pytest.raises(ValidationError):
        ItemChargeConsumptionEvent(
            source_entity_uuid=entity.uuid,
            item_uuid=wand.uuid,
            charges_before=1,
            charges_after=0,
            stack_count_before=1,
            stack_count_after=1,
        )


def test_legacy_door_collision_migrates_to_explicit_directional_boundary_behavior() -> None:
    """The retired whole-tile door has one explicit bidirectional edge replacement."""
    with pytest.raises(KeyError, match="unknown migrated item"):
        build_authored_item("environment.door", uuid4())
    door = build_authored_item("environment.directional_door", uuid4())
    door.place_on_grid((4, 4), boundary_direction=CardinalDirection.EAST)
    placement = get_map().get_object_placement(door.uuid)

    assert placement is not None
    assert placement.kind is WorldPlacementKind.BOUNDARY
    assert placement.boundary_direction is CardinalDirection.EAST
    assert not get_map().can_transition((4, 4), (5, 4))
    assert not get_map().can_transition((5, 4), (4, 4))
    door.open()
    assert get_map().can_transition((4, 4), (5, 4))
    assert get_map().can_transition((5, 4), (4, 4))


def test_oil_barrel_destruction_preserves_direct_material_transition() -> None:
    """Destroying the direct barrel spills one Oil surface at its committed cell."""
    source_uuid = uuid4()
    barrel = build_oil_barrel(source_uuid)
    barrel.place_on_grid((3, 3))

    barrel.receive_damage(20, DamageType.BLUDGEONING, source_uuid)

    conditions = get_map().get_spatial_conditions_at((3, 3))
    assert len(conditions) == 1
    assert isinstance(conditions[0], OilSurface)
    assert conditions[0].affected_positions == {(3, 3)}


def test_private_guardian_item_is_direct_but_not_publicly_buildable() -> None:
    """The private Guardian is a direct BaseItem outside the 147-ID public catalog."""
    private_id = "environment.spell_object.guardian_of_faith"
    guardian = build_guardian_of_faith_object(uuid4())

    assert guardian.item_id == private_id
    assert private_id not in DIRECT_ITEM_BUILDERS
    with pytest.raises(KeyError, match="unknown migrated item"):
        build_authored_item(private_id, uuid4())


def test_runtime_inventory_equipment_and_world_mutations_remain_eventful() -> None:
    """Post-birth loot, equip, unequip, and drop publish committed location facts."""
    game = Game()
    entity = _deployed_entity(
        game,
        name="Runtime owner",
        position=(2, 2),
        faction="heroes",
    )
    sword = build_authored_item("weapon.longsword", entity.uuid)
    sword.place_on_grid((2, 2))
    cursor = EventQueue.event_cursor()

    assert entity.loot_item(sword)
    assert entity.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
    assert entity.unequip_item(WeaponSlot.MELEE_MAIN) is sword
    assert entity.drop_item(sword.uuid, (3, 2)) is sword

    locations = [
        event.location
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, ItemLocationStateEvent)
    ]
    assert locations == [
        ItemLocation.INVENTORY,
        ItemLocation.EQUIPMENT,
        ItemLocation.INVENTORY,
        ItemLocation.FLOOR,
    ]


def test_stacks_charges_durability_containers_intrinsics_and_world_blockers_are_exact() -> None:
    """Representative direct state families retain their public mechanics."""
    owner_uuid = uuid4()
    potion = build_authored_item(
        "consumable.healing_potion",
        owner_uuid,
        quantity=3,
    )
    wand = build_authored_item("spell_item.wand_magic_missiles", owner_uuid)
    barrel = build_authored_item("environment.blocker.oil_barrel", owner_uuid)
    chest = build_storage_chest("Proof Chest", include_loot_all_action=True)
    natural_armor = build_authored_item("armor.creature.wolf_natural", owner_uuid)
    barricade = build_authored_item(
        "environment.blocker.barricade",
        owner_uuid,
    )

    assert (potion.stack_count, potion.max_stack, potion.charges) == (3, 10, 1)
    assert (wand.charges, wand.max_charges) == (3, 3)
    assert barrel.health is not None and barrel.get_max_hp() == 8
    assert chest.get_storage_block() is not None
    assert chest.get_use_actions(owner_uuid)
    assert natural_armor.default_equipment_slot() is BodyPart.BODY
    assert barricade.blocks_movement and barricade.blocks_optics_field
    assert (
        barricade.get_world_placement_spec().kind
        is WorldPlacementKind.CENTER
    )
