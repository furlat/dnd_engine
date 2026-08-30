"""Engine semantic tests for senses, light, stealth, and invisibility."""

from uuid import UUID, uuid4

import pytest
from pydantic import Field

from dnd.actions import Move
from dnd.blocks.base_item import BaseItem
from dnd.blocks.sensory import spatial_senses_system
from dnd.conditions import Hidden, Invisible, InvisibilityEffect
from dnd.controller import PassController
from dnd.core.base_actions import ActionEvent
from dnd.core.base_block import BaseBlock, LightLevel, SenseMode, SensesType
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_object import BaseObject
from dnd.core.condition_types import ConditionCategory, HazardFilter
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.events import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
    SensoryUpdateEvent,
    SensoryUpdateReason,
    SensesUpdateHint,
    SpatialChangeEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import BaseValue
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.game import Game
from dnd.items.environment import DirectionalDoor, DirectionalWall
from dnd.monsters.bestiary import (
    create_caster as _create_caster,
    create_skeleton as _create_skeleton,
)
from dnd.spells.conjuration import DarknessZone, FogCloudZone
from dnd.spells.divination import SeeInvisibilityEffect
from dnd.spells.enchantment import Bane, Bless
from dnd.spells.evocation import Fireball, MagicMissile
from dnd.spells.necromancy import NecroticBless
from dnd.spatial.area_conditions import AreaCondition
from dnd.types.spatial_effects import (
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
)
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from dnd.types.senses import OpticalObscurement, PerceivedContact
from tests.engine.support import reset_combat_state


_MAGICAL_DARKNESS_CELL_CONTENT_REF = ContentRef(
    pack_id="test.senses",
    definition_kind=ContentDefinitionKind.CONDITION,
    content_id="condition.spatial.magical_darkness_cell",
    content_version=1,
    definition_contract_hash="0" * 64,
)


class MagicalDarknessCellZone(AreaCondition):
    """Single-cell magical darkness zone for senses reactivity tests."""

    name: str = Field(default="Magical Darkness Cell")
    content_ref: ContentRef = Field(default=_MAGICAL_DARKNESS_CELL_CONTENT_REF)
    position: tuple[int, int]
    layer: SpatialEffectLayer = Field(default=SpatialEffectLayer.FIELD)
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        default=SpatialEffectOccupancyPolicy.OVERLAPPING,
    )
    zone_shape: str = Field(default="sphere")
    zone_radius_feet: int = Field(default=0)
    sets_light_level: LightLevel = Field(default=LightLevel.DARKNESS)
    light_is_cap: bool = Field(default=True)
    optical_obscurement: OpticalObscurement = Field(
        default=OpticalObscurement.MAGICAL_DARKNESS,
    )


def _spatial_cause(source_uuid: UUID) -> Event:
    return Event(
        name="Test spatial cause",
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.EFFECT,
        source_entity_uuid=source_uuid,
    )


class PerceptionModifierCondition(BaseCondition):
    """Condition used by Chapter 12 examples to change passive Perception.

    Attributes:
        name: Display name for condition application logs.
        modifier_amount: Numerical modifier applied to the target's Perception
            skill bonus.
    """

    name: str = Field(
        default="Perception Payload Modifier",
        description="Condition name used by sensory payload parity examples.",
    )
    modifier_amount: int = Field(
        default=5,
        description="Numerical modifier applied to the target's Perception skill bonus.",
    )

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event | None]:
        """Apply a Perception skill modifier.

        Args:
            declaration_event: Condition application event being resolved.

        Returns:
            Modifier tracking tuple used by BaseCondition cleanup.
        """
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid)
        if target is None:
            return [], [], [], [], None

        perception = target.skill_set.get_skill("perception")
        modifier_uuid = perception.skill_bonus.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid,
                name="Perception Payload Modifier",
                value=self.modifier_amount,
            )
        )
        effect_event = declaration_event.phase_to(EventPhase.EFFECT)
        return [(perception.skill_bonus.uuid, modifier_uuid)], [], [], [], effect_event


_senses_game: Game | None = None


def _deploy_bestiary_entity(entity: Entity) -> Entity:
    if _senses_game is None:
        raise RuntimeError("reset_senses_state must precede entity creation")
    entity.compose_entity()
    _senses_game.deploy_entity(entity, entity.position)
    return entity


def create_skeleton(*args, **kwargs) -> Entity:
    """Create and explicitly deploy one skeleton in the test-owned Game."""
    return _deploy_bestiary_entity(_create_skeleton(*args, **kwargs))


def create_caster(*args, **kwargs) -> Entity:
    """Create and explicitly deploy one caster in the test-owned Game."""
    return _deploy_bestiary_entity(_create_caster(*args, **kwargs))


def reset_senses_state(
    width: int = 8,
    height: int = 3,
    default_light: LightLevel = LightLevel.BRIGHT_LIGHT,
) -> None:
    """Clear global state and build a rectangular grid with one light level."""
    global _senses_game
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    Encounter.clear_registry()
    grid = get_map()
    grid.create_rectangle(
        0,
        0,
        width,
        height,
        default_light=default_light,
    )
    _senses_game = Game()


def completed_sensory_updates(observer_uuid: UUID) -> list[SensoryUpdateEvent]:
    """Return completed sensory update events for one observer."""
    return [
        event
        for event in EventQueue._all_events
        if isinstance(event, SensoryUpdateEvent)
        and event.phase == EventPhase.COMPLETION
        and event.observer_uuid == observer_uuid
    ]


def test_eb_12_001_geometric_fov_is_filtered_by_effective_light() -> None:
    """EB-12-001: senses subscribe to FOV even when darkness hides the cell."""
    reset_senses_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    target = create_skeleton(name="Target", position=(3, 0), darkvision=False)

    observer.update_entity_senses(max_distance=5)

    subscriptions = get_map().get_entity_subscriptions(observer.uuid)
    assert (3, 0) in subscriptions
    assert (3, 0) not in observer.senses.visible
    assert observer.senses.visible == {}
    assert observer.senses.effective_light_levels == {}
    assert target.uuid not in observer.senses.entities
    assert (3, 0) not in observer.senses.seen


def test_eb_12_002_sense_modes_subjectively_upgrade_light() -> None:
    """EB-12-002: darkvision, Devil's Sight, and truesight change effective light."""
    reset_senses_state(width=16, height=1, default_light=LightLevel.BRIGHT_LIGHT)
    grid = get_map()
    grid.set_tile(15, 0, default_light=LightLevel.DARKNESS)
    grid.set_tile(10, 0, default_light=LightLevel.DARKNESS)
    grid.set_tile(5, 0, default_light=LightLevel.DIM_LIGHT)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    observer.senses.sense_modes = [
        SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)
    ]

    observer.update_entity_senses(max_distance=18)
    assert (15, 0) not in observer.senses.effective_light_levels
    assert observer.senses.effective_light_levels[(10, 0)] == LightLevel.DIM_LIGHT
    assert observer.senses.effective_light_levels[(5, 0)] == LightLevel.BRIGHT_LIGHT

    zone = MagicalDarknessCellZone(
        source_entity_uuid=observer.uuid,
        position=(2, 0),
    )
    assert zone.activate(parent_event=_spatial_cause(observer.uuid)) is not None
    assert (2, 0) not in observer.senses.effective_light_levels

    observer.senses.sense_modes = [
        SenseMode(sense_type=SensesType.DEVILS_SIGHT, range_feet=120)
    ]
    observer.update_entity_senses(max_distance=18)
    assert observer.senses.effective_light_levels[(2, 0)] == LightLevel.BRIGHT_LIGHT

    observer.senses.sense_modes = [
        SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60)
    ]
    observer.update_entity_senses(max_distance=18)
    assert observer.senses.effective_light_levels[(2, 0)] == LightLevel.BRIGHT_LIGHT


def test_eb_12_003_light_sources_use_shared_optical_topology() -> None:
    """EB-12-003: light sources apply zones through ordinary optics."""
    reset_senses_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    wall = DirectionalWall(
        source_entity_uuid=uuid4(),
        blocked_channels=(WorldEdgeChannel.OPTICAL,),
    )
    wall.place_on_grid(
        (1, 0),
        boundary_direction=CardinalDirection.EAST,
    )

    grid.add_light_source(
        (0, 0),
        bright_radius_feet=5,
        dim_radius_feet=15,
        very_bright_radius_feet=0,
    )

    source_tile = grid.get_tile(0, 0)
    lit_tile = grid.get_tile(1, 0)
    blocked_tile = grid.get_tile(2, 0)
    assert source_tile is not None
    assert lit_tile is not None
    assert blocked_tile is not None
    assert source_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert lit_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert blocked_tile.resolved_light_level == LightLevel.DARKNESS


def test_eb_12_003a_optical_door_recomputes_existing_light_on_commit() -> None:
    """EB-12-003a: a committed door change immediately updates light reach."""
    reset_senses_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    door = DirectionalDoor(source_entity_uuid=uuid4())
    door.place_on_grid(
        (1, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    grid.add_light_source(
        (0, 0),
        bright_radius_feet=5,
        dim_radius_feet=15,
        very_bright_radius_feet=0,
    )
    far_tile = grid.get_tile(2, 0)
    assert far_tile is not None
    assert far_tile.resolved_light_level == LightLevel.DARKNESS

    event_cursor = EventQueue.event_cursor()
    door.open()

    assert far_tile.resolved_light_level == LightLevel.DIM_LIGHT
    opened_events = [
        (index, event)
        for index, event in EventQueue.iter_events_since(event_cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.phase == EventPhase.COMPLETION
    ]
    topology_index, topology_event = next(
        (index, event)
        for index, event in opened_events
        if event.event_type == EventType.SPATIAL_OBJECT_CHANGED
    )
    light_index, light_event = next(
        (index, event)
        for index, event in opened_events
        if event.event_type == EventType.SPATIAL_LIGHT_CHANGED
    )
    assert topology_event.directional_channels == ["movement", "optical", "propagation"]
    assert light_event.parent_event is not None
    light_parent = EventQueue.get_event_by_uuid(light_event.parent_event)
    assert light_parent is not None
    assert light_parent.lineage_uuid == topology_event.lineage_uuid
    assert light_index < topology_index
    assert light_event.uuid in topology_event.children_events
    assert light_event.senses_hint is not None
    assert (2, 0) in light_event.senses_hint.light_changed_positions

    door.close()

    assert far_tile.resolved_light_level == LightLevel.DARKNESS


def test_eb_12_003b_light_modifiers_are_map_owned_public_facts() -> None:
    """EB-12-003b: objective light mutation is map-owned and event-published."""
    reset_senses_state(width=3, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    tile = grid.get_tile(1, 0)
    assert tile is not None
    source_uuid = uuid4()
    event_cursor = EventQueue.event_cursor()

    changed = grid.apply_light_modifier(
        source_uuid,
        {(1, 0)},
        LightLevel.BRIGHT_LIGHT,
    )

    assert changed == {(1, 0)}
    assert tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert not hasattr(tile, "add_illumination")
    assert not hasattr(tile, "add_obscurement")
    assert not hasattr(tile, "remove_light_modifier")
    completion = next(
        event
        for _, event in EventQueue.iter_events_since(event_cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type == EventType.SPATIAL_LIGHT_CHANGED
        and event.phase == EventPhase.COMPLETION
    )
    assert completion.light_level_map == {"1,0": LightLevel.BRIGHT_LIGHT.value}

    assert grid.remove_light_modifier(source_uuid, {(1, 0)}) == {(1, 0)}
    assert tile.resolved_light_level == LightLevel.DARKNESS


def test_eb_12_003c_tile_optics_commit_before_light_and_preserve_sources() -> None:
    """EB-12-003c: replacing Tile optics preserves source ownership and causality."""
    reset_senses_state(width=4, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    grid.add_light_source(
        (0, 0),
        bright_radius_feet=5,
        dim_radius_feet=15,
        very_bright_radius_feet=0,
    )
    far_tile = grid.get_tile(2, 0)
    assert far_tile is not None
    assert far_tile.resolved_light_level == LightLevel.DIM_LIGHT
    cursor = EventQueue.event_cursor()

    wall_tile = grid.set_tile(
        1,
        0,
        blocks_optics=True,
        blocks_propagation=True,
        default_light=LightLevel.DARKNESS,
    )

    assert wall_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert far_tile.resolved_light_level == LightLevel.DARKNESS
    completions = [
        (index, event)
        for index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.phase == EventPhase.COMPLETION
    ]
    tile_index, tile_event = next(
        (index, event)
        for index, event in completions
        if event.event_type == EventType.SPATIAL_TILE_CHANGED
    )
    light_index, light_event = next(
        (index, event)
        for index, event in completions
        if event.event_type == EventType.SPATIAL_LIGHT_CHANGED
    )
    assert light_index < tile_index
    assert light_event.uuid in tile_event.children_events
    assert tile_event.tile_blocks_optics is True
    assert tile_event.tile_blocks_propagation is True
    assert tile_event.new_light_level == LightLevel.BRIGHT_LIGHT.value

    reopened_tile = grid.set_tile(
        1,
        0,
        blocks_optics=False,
        blocks_propagation=False,
        default_light=LightLevel.DARKNESS,
    )

    assert reopened_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert grid.get_tile(2, 0).resolved_light_level == LightLevel.DIM_LIGHT


def test_eb_12_003d_tile_removal_and_recreation_recompute_light_footprints() -> None:
    """EB-12-003d: missing support cuts light and recreation restores its route."""
    reset_senses_state(width=4, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    grid.add_light_source(
        (0, 0),
        bright_radius_feet=5,
        dim_radius_feet=15,
        very_bright_radius_feet=0,
    )
    far_tile = grid.get_tile(2, 0)
    assert far_tile is not None
    assert far_tile.resolved_light_level == LightLevel.DIM_LIGHT

    grid.remove_tile(1, 0)

    assert far_tile.resolved_light_level == LightLevel.DARKNESS
    restored = grid.set_tile(
        1,
        0,
        default_light=LightLevel.DARKNESS,
    )
    assert restored.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert far_tile.resolved_light_level == LightLevel.DIM_LIGHT


def test_eb_12_004_light_change_reveals_subscribed_dark_cells_reactively() -> None:
    """EB-12-004: a light event updates subscribed observer senses without bulk refresh."""
    reset_senses_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    target = create_skeleton(name="Target", position=(3, 0), darkvision=False)
    observer.update_entity_senses(max_distance=5)

    assert target.uuid not in observer.senses.entities
    get_map().add_light_source((3, 0), bright_radius_feet=5, dim_radius_feet=0)

    assert (3, 0) in observer.senses.visible
    assert (3, 0) in observer.senses.seen
    assert target.uuid in observer.senses.entities
    updates = completed_sensory_updates(observer.uuid)
    light_updates = [event for event in updates if event.update_reason == SensoryUpdateReason.LIGHT]
    assert light_updates
    assert any((3, 0) in event.visible_cells_added for event in light_updates)
    assert any(target.uuid in event.entity_contacts_changed for event in light_updates)


def test_eb_12_005_perceivability_flags_filter_hidden_and_invisible_blocks() -> None:
    """EB-12-005: stealth DC and invisibility flags are observer-relative filters."""
    reset_senses_state(width=5, height=1)
    target = create_skeleton(name="Target", position=(2, 0), darkvision=False)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    truesight = create_skeleton(name="Truesight", position=(4, 0), darkvision=False)
    truesight.senses.sense_modes = [
        SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60)
    ]

    Entity.update_all_entities_senses(max_distance=5)
    assert target.uuid in observer.senses.entities
    target.set_stealth_dc(observer.get_passive_perception() + 1)
    assert target.uuid not in observer.senses.entities
    target.set_stealth_dc(1)
    assert target.uuid in observer.senses.entities

    target.set_invisible(True)
    assert target.uuid not in observer.senses.entities
    assert target.uuid in truesight.senses.entities
    target.set_invisible(False)
    assert target.uuid in observer.senses.entities


def test_eb_12_006_perceivability_events_refilter_visible_entities() -> None:
    """EB-12-006: hidden-state changes update subscribed observer senses."""
    reset_senses_state(width=5, height=1)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    target = create_skeleton(name="Target", position=(2, 0), darkvision=False)
    Entity.update_all_entities_senses(max_distance=5)

    assert target.uuid in observer.senses.entities
    target.set_stealth_dc(observer.get_passive_perception() + 1)

    assert target.uuid not in observer.senses.entities
    removed_updates = [
        event for event in completed_sensory_updates(observer.uuid)
        if event.update_reason == SensoryUpdateReason.PERCEIVABILITY
        and target.uuid in event.entity_contacts_removed
    ]
    assert removed_updates

    target.set_stealth_dc(1)

    assert target.uuid in observer.senses.entities
    added_updates = [
        event for event in completed_sensory_updates(observer.uuid)
        if event.update_reason == SensoryUpdateReason.PERCEIVABILITY
        and target.uuid in event.entity_contacts_changed
    ]
    assert added_updates


def test_eb_12_007_subjective_paths_do_not_leak_imperceivable_blockers() -> None:
    """EB-12-007: subjective pathfinding ignores blockers the observer cannot perceive."""
    reset_senses_state(width=5, height=1)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    invisible = create_skeleton(name="Invisible", position=(2, 0), darkvision=False)
    invisible.add_condition(Invisible(source_entity_uuid=invisible.uuid, target_entity_uuid=invisible.uuid))

    Entity.update_all_entities_senses(max_distance=5)

    assert invisible.uuid not in observer.senses.entities
    assert (2, 0) in observer.senses.paths
    assert (4, 0) in observer.senses.paths

    observer.senses.sense_modes = [
        SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60)
    ]
    Entity.update_all_entities_senses(max_distance=5)

    assert invisible.uuid in observer.senses.entities
    assert (2, 0) not in observer.senses.paths
    assert (4, 0) not in observer.senses.paths


def test_eb_12_008_self_movement_updates_visibility_and_marks_paths_dirty() -> None:
    """EB-12-008: self movement refreshes visibility but defers Dijkstra."""
    reset_senses_state(width=7, height=2)
    mover = create_skeleton(name="Mover", position=(0, 0), darkvision=False)
    target = create_skeleton(name="Target", position=(6, 0), darkvision=False)
    mover.update_entity_senses(max_distance=5)

    assert mover.senses._paths_dirty is False
    assert target.uuid not in mover.senses.entities

    Entity.update_entity_position(mover, (1, 0))

    assert mover.senses._paths_dirty is True
    assert target.uuid in mover.senses.entities
    updates = completed_sensory_updates(mover.uuid)
    movement_updates = [
        event for event in updates
        if event.update_reason == SensoryUpdateReason.SELF_MOVEMENT and event.paths_dirty
    ]
    assert movement_updates


def test_eb_12_009_sense_mode_changes_emit_replacement_payloads() -> None:
    """EB-12-009: sense-mode grant and removal emit replacement payloads."""
    reset_senses_state(width=6, height=1)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    invisible = create_skeleton(name="Invisible", position=(3, 0), darkvision=False)
    invisible.add_condition(Invisible(source_entity_uuid=invisible.uuid, target_entity_uuid=invisible.uuid))
    Entity.update_all_entities_senses(max_distance=5)

    assert invisible.uuid not in observer.senses.entities

    effect = SeeInvisibilityEffect(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
    )
    observer.add_condition(effect)

    assert invisible.uuid in observer.senses.entities
    updates = completed_sensory_updates(observer.uuid)
    changed = [event for event in updates if event.sense_modes_changed]
    assert changed
    assert changed[-1].model_dump(mode="json")["sense_modes"] == [
        {"sense_type": "See Invisible", "range_feet": 0}
    ]

    observer.remove_condition(effect.name)

    assert invisible.uuid not in observer.senses.entities
    assert observer.senses.sense_modes == []
    changed = [
        event
        for event in completed_sensory_updates(observer.uuid)
        if event.sense_modes_changed
    ]
    assert changed[-1].model_dump(mode="json")["sense_modes"] == []


def test_eb_12_010_very_bright_light_reveals_hidden_entities() -> None:
    """EB-12-010: hidden is removed when the entity's tile becomes very bright."""
    reset_senses_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    hidden = create_skeleton(name="Hidden", position=(3, 0), darkvision=False)
    hidden.add_condition(
        Hidden(source_entity_uuid=hidden.uuid, target_entity_uuid=hidden.uuid, stealth_result=30)
    )
    Entity.update_all_entities_senses(max_distance=5)

    assert "Hidden" in hidden.active_conditions
    assert hidden.uuid not in observer.senses.entities

    get_map().add_light_source(
        (3, 0),
        bright_radius_feet=0,
        dim_radius_feet=0,
        very_bright_radius_feet=5,
    )

    assert "Hidden" not in hidden.active_conditions
    assert hidden.stealth_dc is None
    assert hidden.uuid in observer.senses.entities


def test_eb_12_011_magical_darkness_zone_removal_recomputes_behind_cells() -> None:
    """EB-12-011: magical darkness removal recomputes FOV and restores behind cells."""
    reset_senses_state(width=5, height=1)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    target = create_skeleton(name="Behind Darkness", position=(3, 0), darkvision=False)
    Entity.update_all_entities_senses(max_distance=5)

    assert target.uuid in observer.senses.entities
    assert (3, 0) in observer.senses.visible

    zone = MagicalDarknessCellZone(
        source_entity_uuid=observer.uuid,
        position=(2, 0),
    )
    activation = zone.activate(parent_event=_spatial_cause(observer.uuid))
    assert activation is not None and not activation.canceled

    darkness_tile = get_map().get_tile(2, 0)
    assert darkness_tile is not None
    assert darkness_tile.resolved_light_level == LightLevel.DARKNESS
    assert target.uuid not in observer.senses.entities
    assert (3, 0) not in observer.senses.visible
    add_updates = [
        event for event in completed_sensory_updates(observer.uuid)
        if (3, 0) in event.visible_cells_removed
        and target.uuid in event.entity_contacts_removed
    ]
    assert add_updates

    cursor = EventQueue.event_cursor()
    assert zone.deactivate(parent_event=activation)

    restored_tile = get_map().get_tile(2, 0)
    assert restored_tile is not None
    assert restored_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert (2, 0) in observer.senses.visible
    assert (3, 0) in observer.senses.visible
    assert target.uuid in observer.senses.entities
    removal_updates = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == observer.uuid
        and target.uuid in event.entity_contacts_changed
    ]
    assert removal_updates
    assert (3, 0) in removal_updates[-1].visible_cells_added


def test_eb_12_012_passive_perception_changes_emit_replacement_payloads() -> None:
    """EB-12-012: passive perception changes emit replacement values and refilter hidden entities."""
    reset_senses_state(width=5, height=1)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    hidden = create_skeleton(name="Hidden", position=(3, 0), darkvision=False)
    Entity.update_all_entities_senses(max_distance=5)

    base_passive = observer.get_passive_perception()
    hidden.set_stealth_dc(base_passive + 3)
    assert hidden.uuid not in observer.senses.entities

    observer.add_condition(
        PerceptionModifierCondition(
            source_entity_uuid=observer.uuid,
            target_entity_uuid=observer.uuid,
            modifier_amount=5,
        )
    )

    boosted_passive = observer.get_passive_perception()
    assert boosted_passive == base_passive + 5
    assert hidden.uuid in observer.senses.entities
    assert observer.senses._paths_dirty is True

    updates = [
        event for event in completed_sensory_updates(observer.uuid)
        if event.passive_perception_changed
    ]
    assert updates
    payload = updates[-1].model_dump(mode="json")
    assert payload["passive_perception"] == boosted_passive
    assert payload["paths_dirty"] is True
    assert str(hidden.uuid) in payload["entity_contacts_changed"]


def test_eb_12_019_passive_perception_decrease_removes_hidden_entity_payload() -> None:
    """EB-12-019: passive perception decreases emit removal payloads for hidden entities."""
    reset_senses_state(width=5, height=1)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    hidden = create_skeleton(name="Hidden", position=(3, 0), darkvision=False)
    Entity.update_all_entities_senses(max_distance=5)

    base_passive = observer.get_passive_perception()
    hidden.set_stealth_dc(base_passive - 1)
    assert hidden.uuid in observer.senses.entities

    observer.add_condition(
        PerceptionModifierCondition(
            source_entity_uuid=observer.uuid,
            target_entity_uuid=observer.uuid,
            modifier_amount=-5,
        )
    )

    reduced_passive = observer.get_passive_perception()
    assert reduced_passive == base_passive - 5
    assert hidden.uuid not in observer.senses.entities
    assert observer.senses._paths_dirty is True

    updates = [
        event for event in completed_sensory_updates(observer.uuid)
        if event.passive_perception_changed
        and hidden.uuid in event.entity_contacts_removed
    ]
    assert updates
    payload = updates[-1].model_dump(mode="json")
    assert payload["passive_perception"] == reduced_passive
    assert payload["paths_dirty"] is True
    assert str(hidden.uuid) in payload["entity_contacts_removed"]
    assert str(hidden.uuid) not in payload["entity_contacts_changed"]


def test_eb_12_013_turn_start_clears_positional_and_directional_collision_memory() -> None:
    """EB-12-013: turn start clears cell and directional collision memory."""
    reset_senses_state(width=3, height=2)
    grid = get_map()
    mover = create_skeleton(name="Mover", position=(0, 0), faction="heroes")
    other = create_skeleton(name="Other", position=(2, 1), faction="monsters")
    hidden_shutter = DirectionalWall(
        source_entity_uuid=uuid4(),
        name="Hidden Shutter",
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
        stealth_dc=99,
    )
    hidden_shutter.place_on_grid(
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    Entity.update_all_entities_senses(max_distance=5)

    assert (1, 0) in mover.senses.paths
    assert grid.can_transition((0, 0), (1, 0), mover.uuid, subjective=True)
    assert not grid.can_transition((0, 0), (1, 0), mover.uuid)

    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0), use_movement_cost=False).apply()

    assert result is not None
    assert mover.position == (0, 0)
    assert mover.senses.collision_blocked == set()
    assert ((0, 0), "east") in mover.senses.directional_collision_blocked

    mover.update_entity_senses(max_distance=5)
    remembered_path = mover.senses.paths[(1, 0)]
    assert remembered_path != [(0, 0), (1, 0)]
    assert grid.can_transition(
        (1, 1),
        (1, 0),
        mover.uuid,
        subjective=True,
        directional_collision_blocked=mover.senses.directional_collision_blocked,
    )

    mover.senses.collision_blocked.add((2, 0))
    encounter = Encounter(name="Collision Cleanup", source_entity_uuid=uuid4())
    encounter.add_combatant(mover, PassController(source_entity_uuid=mover.uuid))
    encounter.add_combatant(other, PassController(source_entity_uuid=other.uuid))
    encounter.initiative_order = [mover.uuid, other.uuid]
    encounter.start_encounter()
    encounter.start_turn()

    assert mover.senses.collision_blocked == set()
    assert mover.senses.directional_collision_blocked == set()
    assert mover.senses.paths[(1, 0)] == [(0, 0), (1, 0)]


def test_eb_12_014_plain_invisible_and_spell_invisibility_have_different_reveal_contracts() -> None:
    """EB-12-014: plain Invisible has no reveal handler; InvisibilityEffect does."""
    reset_senses_state(width=6, height=1)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    plain_target = create_skeleton(name="Plain Invisible", position=(2, 0), darkvision=False)
    spell_target = create_skeleton(name="Spell Invisible", position=(4, 0), darkvision=False)
    Entity.update_all_entities_senses(max_distance=5)

    plain_target.add_condition(
        Invisible(source_entity_uuid=plain_target.uuid, target_entity_uuid=plain_target.uuid)
    )
    spell_target.add_condition(
        InvisibilityEffect(source_entity_uuid=spell_target.uuid, target_entity_uuid=spell_target.uuid)
    )

    assert plain_target.uuid not in observer.senses.entities
    assert spell_target.uuid not in observer.senses.entities
    assert plain_target.is_invisible is True
    assert spell_target.is_invisible is True

    ActionEvent(
        name="Shove",
        source_entity_uuid=plain_target.uuid,
        target_entity_uuid=plain_target.uuid,
        phase=EventPhase.DECLARATION,
    ).phase_to(EventPhase.EFFECT)
    ActionEvent(
        name="Shove",
        source_entity_uuid=spell_target.uuid,
        target_entity_uuid=spell_target.uuid,
        phase=EventPhase.DECLARATION,
    ).phase_to(EventPhase.EFFECT)

    assert "Invisible" in plain_target.active_conditions
    assert plain_target.is_invisible is True
    assert plain_target.uuid not in observer.senses.entities

    assert "Invisible" not in spell_target.active_conditions
    assert spell_target.is_invisible is False
    assert spell_target.uuid in observer.senses.entities
    reveal_updates = [
        event for event in completed_sensory_updates(observer.uuid)
        if spell_target.uuid in event.entity_contacts_changed
    ]
    assert reveal_updates


def test_eb_12_015_hidden_cell_blocker_reveals_on_movement_collision() -> None:
    """EB-12-015: bumping into a hidden creature reveals that creature."""
    reset_senses_state(width=4, height=1)
    mover = create_skeleton(name="Mover", position=(0, 0), faction="heroes")
    hidden_blocker = create_skeleton(name="Hidden Blocker", position=(1, 0), faction="monsters")

    hidden_blocker.add_condition(
        Hidden(
            source_entity_uuid=hidden_blocker.uuid,
            target_entity_uuid=hidden_blocker.uuid,
            stealth_result=mover.get_passive_perception() + 10,
        )
    )
    Entity.update_all_entities_senses(max_distance=5)

    assert hidden_blocker.uuid not in mover.senses.entities
    assert (1, 0) in mover.senses.paths
    assert get_map().can_transition((0, 0), (1, 0), mover.uuid, subjective=True)
    assert not get_map().can_transition((0, 0), (1, 0), mover.uuid)

    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0), use_movement_cost=False).apply()

    assert result is not None and result.canceled
    assert mover.position == (0, 0)
    assert mover.senses.collision_blocked == {(1, 0)}
    assert "Hidden" not in hidden_blocker.active_conditions
    assert hidden_blocker.stealth_dc is None
    assert hidden_blocker.uuid in mover.senses.entities

    collision_events = [
        event for event in EventQueue._all_events
        if isinstance(event, SpatialChangeEvent)
        and event.event_type == EventType.MOVEMENT_COLLISION
        and event.phase == EventPhase.COMPLETION
        and event.position == (1, 0)
    ]
    assert collision_events
    reveal_updates = [
        event for event in completed_sensory_updates(mover.uuid)
        if hidden_blocker.uuid in event.entity_contacts_changed
    ]
    assert reveal_updates


def test_eb_12_016_hidden_and_invisible_flags_stack_independently() -> None:
    """EB-12-016: removing Hidden does not reveal a still-invisible creature."""
    reset_senses_state(width=6, height=1)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    truesight = create_skeleton(name="Truesight", position=(5, 0), darkvision=False)
    target = create_skeleton(name="Stacked Target", position=(3, 0), darkvision=False)
    truesight.senses.sense_modes = [
        SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60)
    ]

    target.add_condition(Invisible(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    target.add_condition(
        Hidden(
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
            stealth_result=max(observer.get_passive_perception(), truesight.get_passive_perception()) + 10,
        )
    )
    Entity.update_all_entities_senses(max_distance=5)

    assert target.is_invisible is True
    assert target.stealth_dc is not None
    assert "Hidden" in target.active_conditions
    assert "Invisible" in target.active_conditions
    assert target.uuid not in observer.senses.entities
    assert target.uuid not in truesight.senses.entities

    cursor = EventQueue.event_cursor()
    get_map().add_light_source(
        (3, 0),
        bright_radius_feet=0,
        dim_radius_feet=0,
        very_bright_radius_feet=5,
    )

    assert "Hidden" not in target.active_conditions
    assert "Invisible" in target.active_conditions
    assert target.stealth_dc is None
    assert target.is_invisible is True
    assert target.uuid not in observer.senses.entities
    assert target.uuid in truesight.senses.entities

    observer_updates = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == observer.uuid
        if target.uuid in event.entity_contacts_changed
    ]
    truesight_updates = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == truesight.uuid
        if target.uuid in event.entity_contacts_changed
    ]
    assert observer_updates == []
    assert truesight_updates


def test_eb_12_016a_invisibility_is_derived_from_surviving_sources() -> None:
    """Removing one invisibility owner preserves every surviving owner."""
    reset_senses_state(width=6, height=1)
    observer = create_skeleton(
        name="Observer",
        position=(0, 0),
        darkvision=False,
    )
    target = create_skeleton(
        name="Target",
        position=(3, 0),
        darkvision=False,
    )
    first = Invisible(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
    )
    second = InvisibilityEffect(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=target.uuid,
        name="Invisible (second source)",
    )

    target.add_condition(first)
    target.add_condition(second)
    assert target.is_invisible is True
    assert target.uuid not in observer.senses.entities

    target.remove_condition_by_uuid(first.uuid)
    assert target.is_invisible is True
    assert target.uuid not in observer.senses.entities

    target.remove_condition_by_uuid(second.uuid)
    assert target.is_invisible is False
    assert observer.senses.entities[target.uuid].visual is True


def test_eb_12_016b_stealth_dc_is_derived_from_surviving_sources() -> None:
    """Removing one Hidden owner restores the strongest surviving DC."""
    reset_senses_state(width=6, height=1)
    observer = create_skeleton(
        name="Observer",
        position=(0, 0),
        darkvision=False,
    )
    target = create_skeleton(
        name="Target",
        position=(3, 0),
        darkvision=False,
    )
    low = Hidden(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        name="Hidden (low source)",
        stealth_result=observer.get_passive_perception() + 1,
    )
    high = Hidden(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=target.uuid,
        name="Hidden (high source)",
        stealth_result=observer.get_passive_perception() + 5,
    )

    target.add_condition(low)
    target.add_condition(high)
    assert target.stealth_dc == high.stealth_result
    assert target.uuid not in observer.senses.entities

    target.remove_condition_by_uuid(high.uuid)
    assert target.stealth_dc == low.stealth_result
    assert target.uuid not in observer.senses.entities

    target.remove_condition_by_uuid(low.uuid)
    assert target.stealth_dc is None
    assert observer.senses.entities[target.uuid].visual is True


def test_eb_12_017_multi_entity_spell_cancels_when_target_becomes_hidden() -> None:
    """EB-12-017: direct MULTI_ENTITY execution revalidates stale visibility."""
    reset_senses_state(width=6, height=2)
    caster = create_caster(name="Wizard", position=(0, 0), faction="heroes")
    visible_target = create_skeleton(name="Visible Target", position=(2, 0), faction="monsters")
    stale_target = create_skeleton(name="Stale Target", position=(3, 0), faction="monsters")
    Entity.update_all_entities_senses(max_distance=10)

    assert visible_target.uuid in caster.senses.entities
    assert stale_target.uuid in caster.senses.entities

    spell = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=visible_target.uuid,
        extra_target_entity_uuids=[stale_target.uuid],
        cast_at_level=1,
    )
    visible_hp_before = visible_target.get_hp()
    stale_hp_before = stale_target.get_hp()

    stale_target.add_condition(
        Hidden(
            source_entity_uuid=stale_target.uuid,
            target_entity_uuid=stale_target.uuid,
            stealth_result=caster.get_passive_perception() + 10,
        )
    )

    assert visible_target.uuid in caster.senses.entities
    assert stale_target.uuid not in caster.senses.entities

    result = spell.apply()

    assert result is not None and result.canceled
    assert result.status_message == "Stale Target not in line of sight"
    assert visible_target.get_hp() == visible_hp_before
    assert stale_target.get_hp() == stale_hp_before
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.spell_slot_1.normalized_score == 4


def test_eb_12_018_aoe_preview_hides_hidden_entities_but_execution_hits_them() -> None:
    """EB-12-018: subjective AoE previews hide hidden entities; execution is objective."""
    reset_senses_state(width=10, height=2)
    caster = create_caster(name="Wizard", position=(0, 0), faction="heroes")
    hidden_target = create_skeleton(name="Hidden Target", position=(7, 0), faction="monsters")
    visible_target = create_skeleton(name="Visible Target", position=(8, 0), faction="monsters")
    hidden_target.add_condition(
        Hidden(
            source_entity_uuid=hidden_target.uuid,
            target_entity_uuid=hidden_target.uuid,
            stealth_result=caster.get_passive_perception() + 10,
        )
    )
    Entity.update_all_entities_senses(max_distance=10)

    assert hidden_target.uuid not in caster.senses.entities
    assert visible_target.uuid in caster.senses.entities

    available = caster.get_available_actions(target_filter="enemies")
    fireball_info = next(
        action for action in available.position_actions
        if action.template_name == "Fireball__slot_3"
    )
    blast_preview = next(
        target for target in fireball_info.valid_targets
        if target.position == hidden_target.position
    )

    assert hidden_target.uuid not in (blast_preview.affected_entity_uuids or [])
    assert "Hidden Target" not in (blast_preview.affected_entity_names or [])
    assert visible_target.uuid in (blast_preview.affected_entity_uuids or [])
    assert "Visible Target" in (blast_preview.affected_entity_names or [])

    hidden_hp_before = hidden_target.get_hp()
    visible_hp_before = visible_target.get_hp()
    assert caster.action_economy.spell_slot_3.normalized_score == 2

    result = Fireball(
        source_entity_uuid=caster.uuid,
        end_position=hidden_target.position,
        cast_at_level=3,
    ).apply()

    assert result is not None and not result.canceled
    assert result.phase == EventPhase.COMPLETION
    assert sum(
        event.lineage_uuid == result.lineage_uuid
        and event.phase == EventPhase.COMPLETION
        for event in EventQueue._all_events
    ) == 1
    assert hidden_target.get_hp() < hidden_hp_before
    assert visible_target.get_hp() < visible_hp_before
    assert "Hidden" not in hidden_target.active_conditions
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_3.normalized_score == 1


def test_eb_12_020_distant_movement_does_not_dirty_unrelated_observer_paths() -> None:
    """EB-12-020: off-screen movement does not invalidate unrelated observer paths."""
    reset_senses_state(width=16, height=1)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    distant_mover = create_skeleton(name="Distant Mover", position=(12, 0), darkvision=False)
    observer.update_entity_senses(max_distance=3)

    assert distant_mover.uuid not in observer.senses.entities
    assert observer.senses._paths_dirty is False
    cursor = EventQueue.event_cursor()

    Entity.update_entity_position(distant_mover, (13, 0))

    assert observer.senses._paths_dirty is False
    assert distant_mover.uuid not in observer.senses.entities
    assert [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == observer.uuid
    ] == []


def test_eb_12_021_movement_perception_matches_explicit_cold_recompute() -> None:
    """EB-12-021: movement reduction and a cold perception recompute agree."""
    reset_senses_state(width=8, height=3)
    grid = get_map()
    mover = create_skeleton(name="Mover", position=(0, 1), darkvision=False)
    target = create_skeleton(name="Target", position=(4, 1), darkvision=False)
    marker = BaseItem(
        source_entity_uuid=uuid4(),
        name="Visible Marker",
        is_pickable=False,
        include_in_senses_objects=True,
    )
    grid.place_object(marker.uuid, (3, 2))
    mover.update_entity_senses(max_distance=5)

    Entity.update_entity_position(mover, (1, 1))

    assert target.uuid in mover.senses.entities
    assert marker.uuid in mover.senses.objects
    assert mover.senses._paths_dirty is True
    movement_snapshot = {
        "visible": dict(mover.senses.visible),
        "seen": set(mover.senses.seen),
        "entities": dict(mover.senses.entities),
        "objects": dict(mover.senses.objects),
        "subscriptions": set(grid.get_entity_subscriptions(mover.uuid)),
    }

    mover.update_entity_senses(max_distance=5)
    cold_snapshot = {
        "visible": dict(mover.senses.visible),
        "seen": set(mover.senses.seen),
        "entities": dict(mover.senses.entities),
        "objects": dict(mover.senses.objects),
        "subscriptions": set(grid.get_entity_subscriptions(mover.uuid)),
    }

    assert movement_snapshot == cold_snapshot
    assert mover.senses._paths_dirty is False


def test_eb_12_022_paired_movement_emits_one_subjective_transition() -> None:
    """EB-12-022: one step keeps two objective events but one sensory delta."""
    reset_senses_state(width=6, height=1)
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    mover = create_skeleton(name="Mover", position=(2, 0), darkvision=False)
    Entity.update_all_entities_senses(max_distance=5)

    assert mover.uuid in observer.senses.entities
    before_updates = len(completed_sensory_updates(observer.uuid))

    Entity.update_entity_position(mover, (3, 0))

    movement_updates = completed_sensory_updates(observer.uuid)[before_updates:]
    objective_events = [
        event
        for event in EventQueue._all_events
        if isinstance(event, SpatialChangeEvent)
        and event.phase == EventPhase.COMPLETION
        and event.entity_uuid == mover.uuid
        and event.event_type in {
            EventType.SPATIAL_ENTITY_LEFT,
            EventType.SPATIAL_ENTITY_ENTERED,
        }
    ]

    assert {event.event_type for event in objective_events} == {
        EventType.SPATIAL_ENTITY_LEFT,
        EventType.SPATIAL_ENTITY_ENTERED,
    }
    assert len(movement_updates) == 1
    assert movement_updates[0].entity_contacts_changed[mover.uuid].position == (3, 0)
    assert movement_updates[0].entity_contacts_removed == set()


def test_eb_12_023_sensory_dispatch_indexes_local_spatial_candidates() -> None:
    """EB-12-023: distant observers are excluded before sensory recomputation."""
    reset_senses_state(width=20, height=1)
    local_observer = create_skeleton(
        name="Local Observer",
        position=(0, 0),
        darkvision=False,
    )
    mover = create_skeleton(name="Mover", position=(2, 0), darkvision=False)
    distant_observer = create_skeleton(
        name="Distant Observer",
        position=(15, 0),
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=3)
    entered = SpatialChangeEvent.entity_entered(
        (2, 0),
        mover.uuid,
        old_position=(1, 0),
    )

    candidates = spatial_senses_system.candidate_observer_uuids(entered)

    assert local_observer.uuid in candidates
    assert mover.uuid in candidates
    assert distant_observer.uuid not in candidates


def test_eb_12_024_sensory_dispatch_targets_own_perception_conditions() -> None:
    """EB-12-024: perception conditions select only their target observer."""
    reset_senses_state(width=4, height=1)
    target = create_skeleton(name="Target", position=(0, 0), darkvision=False)
    unrelated = create_skeleton(name="Unrelated", position=(2, 0), darkvision=False)
    Entity.update_all_entities_senses(max_distance=3)
    condition_event = Event(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        event_type=EventType.CONDITION_APPLICATION,
        use_register=False,
    )

    candidates = spatial_senses_system.candidate_observer_uuids(condition_event)

    assert candidates == {target.uuid}
    assert unrelated.uuid not in candidates


def test_eb_12_025_attached_light_emits_one_batched_lifecycle_per_step() -> None:
    """EB-12-025: one torch step publishes one complete light-change event."""
    reset_senses_state(width=7, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    mover = create_skeleton(name="Torchbearer", position=(1, 0), darkvision=False)
    create_skeleton(name="Light-change Witness", position=(3, 0), darkvision=False)
    grid.add_light_source(
        mover.position,
        bright_radius_feet=5,
        dim_radius_feet=10,
        anchor_uuid=mover.uuid,
    )
    mover.update_entity_senses(max_distance=6)
    event_cursor = EventQueue.event_cursor()

    Entity.update_entity_position(mover, (2, 0))

    light_completions = [
        event
        for _, event in EventQueue.iter_events_since(event_cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type == EventType.SPATIAL_LIGHT_CHANGED
        and event.phase == EventPhase.COMPLETION
    ]
    assert len(light_completions) == 1
    hint = light_completions[0].senses_hint
    assert hint is not None
    assert hint.light_changed_positions
    assert (3, 0) in hint.light_changed_positions


def test_eb_12_026_batched_light_positions_reveal_hidden_entities() -> None:
    """EB-12-026: hidden reveal checks every tile in a batched light event."""
    reset_senses_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    hidden = create_skeleton(name="Hidden Target", position=(4, 0), darkvision=False)
    hidden.add_condition(
        Hidden(
            source_entity_uuid=hidden.uuid,
            target_entity_uuid=hidden.uuid,
            stealth_result=30,
        )
    )
    hidden_tile = grid.get_tile(4, 0)
    representative_tile = grid.get_tile(0, 0)
    assert hidden_tile is not None
    assert representative_tile is not None
    grid.apply_light_modifier(
        uuid4(),
        {hidden_tile.position},
        LightLevel.VERY_BRIGHT,
    )
    event = SpatialChangeEvent.light_changed(
        representative_tile.position,
        representative_tile.uuid,
        senses_hint=SensesUpdateHint(
            light_changed_positions={representative_tile.position, hidden_tile.position},
        ),
    )

    grid._fire_spatial_event(event)

    assert "Hidden" not in hidden.active_conditions
    assert hidden.stealth_dc is None


def test_eb_12_027_light_and_sight_share_one_optical_fov() -> None:
    """EB-12-027: ordinary light and sight expose the same optical cells."""
    reset_senses_state(width=7, height=1)
    grid = get_map()
    observer = create_skeleton(name="Observer", position=(0, 0), darkvision=False)
    wall = DirectionalWall(
        source_entity_uuid=uuid4(),
        blocked_channels=(WorldEdgeChannel.OPTICAL,),
    )
    wall.place_on_grid(
        (3, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    sight = set(grid.compute_fov(observer.position, 6))
    light = set(grid.compute_light_fov(observer.position, 6))

    assert sight == light
    assert (3, 0) in sight
    assert (4, 0) not in sight


def test_eb_12_028_optical_revision_invalidates_public_fov() -> None:
    """EB-12-028: changing an optical edge changes subsequent public FOV."""
    reset_senses_state(width=7, height=3)
    grid = get_map()
    observer = create_skeleton(name="Observer", position=(0, 1), darkvision=False)
    before_revision = grid.optical_revision
    before = set(grid.compute_fov(observer.position, 6))
    assert (6, 1) in before

    wall = DirectionalWall(
        source_entity_uuid=uuid4(),
        blocked_channels=(WorldEdgeChannel.OPTICAL,),
    )
    wall.place_on_grid(
        (3, 1),
        boundary_direction=CardinalDirection.EAST,
    )
    first_revision = grid.optical_revision
    first = set(grid.compute_fov(observer.position, 6))

    assert first_revision > before_revision
    assert (3, 1) in first
    assert (4, 1) not in first

    grid.move_object(
        wall.uuid,
        (3, 1),
        boundary_direction=CardinalDirection.WEST,
    )
    third = set(grid.compute_fov(observer.position, 6))

    assert grid.optical_revision > first_revision
    assert (2, 1) in third
    assert (3, 1) not in third


def test_eb_12_028a_near_side_wall_is_visible_without_far_tile_content() -> None:
    """A lit near side reveals its wall while the blocked Tile stays hidden."""
    reset_senses_state(width=4, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    wall = DirectionalWall(
        source_entity_uuid=uuid4(),
        include_in_senses_objects=True,
    )
    wall.place_on_grid(
        (1, 0),
        boundary_direction=CardinalDirection.WEST,
    )
    grid.add_light_source(
        (0, 0),
        bright_radius_feet=5,
        dim_radius_feet=0,
        very_bright_radius_feet=0,
    )
    far_entity = create_skeleton(
        name="Far Entity",
        position=(1, 0),
        darkvision=False,
    )
    observer = create_skeleton(
        name="Observer",
        position=(0, 0),
        darkvision=False,
    )

    assert observer.senses.objects[wall.uuid] == PerceivedContact(
        position=(1, 0),
        visual=True,
    )
    assert (1, 0) not in observer.senses.visible
    assert far_entity.uuid not in observer.senses.entities


@pytest.mark.parametrize(
    "sense_type",
    [SensesType.BLINDSIGHT, SensesType.TREMORSENSE],
)
def test_eb_12_028b_nonvisual_senses_create_contacts_not_visual_cells(
    sense_type: SensesType,
) -> None:
    """Nonvisual senses identify contacts without inventing light or sight."""
    reset_senses_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    observer = create_skeleton(
        name="Observer",
        position=(0, 0),
        darkvision=False,
    )
    target = create_skeleton(
        name="Target",
        position=(3, 0),
        darkvision=False,
    )
    observer.senses.sense_modes = [
        SenseMode(sense_type=sense_type, range_feet=20)
    ]
    observer.update_entity_senses(max_distance=5)

    assert observer.senses.entities[target.uuid] == PerceivedContact(
        position=(3, 0),
        visual=False,
        special_senses=(sense_type,),
    )
    assert (3, 0) not in observer.senses.visible
    assert (3, 0) not in observer.senses.effective_light_levels


@pytest.mark.parametrize(
    ("sense_type", "crosses_magical_darkness"),
    [
        (SensesType.DARKVISION, False),
        (SensesType.DEVILS_SIGHT, True),
        (SensesType.TRUESIGHT, True),
    ],
)
def test_eb_12_028c_visual_senses_obey_conditional_obscurement(
    sense_type: SensesType,
    crosses_magical_darkness: bool,
) -> None:
    """Visual special senses cross magical darkness selectively, never fog."""
    reset_senses_state(width=8, height=1)
    observer = create_skeleton(
        name="Observer",
        position=(0, 0),
        darkvision=False,
    )
    target = create_skeleton(
        name="Target",
        position=(6, 0),
        darkvision=False,
    )
    observer.senses.sense_modes = [
        SenseMode(sense_type=sense_type, range_feet=30)
    ]
    observer.update_entity_senses(max_distance=7)

    darkness = DarknessZone(
        source_entity_uuid=observer.uuid,
        position=(3, 0),
        zone_radius_feet=0,
    )
    darkness.activate(parent_event=None)
    assert (target.uuid in observer.senses.entities) is crosses_magical_darkness
    if crosses_magical_darkness:
        contact = observer.senses.entities[target.uuid]
        assert contact.visual is True
        assert sense_type in contact.special_senses

    darkness.deactivate()
    fog = FogCloudZone(
        source_entity_uuid=observer.uuid,
        position=(3, 0),
        zone_radius_feet=0,
    )
    fog.activate(parent_event=None)
    assert target.uuid not in observer.senses.entities


def test_eb_12_029_invisible_collision_stops_repaths_and_preserves_invisibility() -> None:
    """EB-12-029: objective collision corrects an unsafe subjective path."""
    reset_senses_state(width=6, height=3)
    mover = create_skeleton(
        name="Mover",
        position=(0, 1),
        faction="heroes",
        darkvision=False,
    )
    invisible = create_skeleton(
        name="Invisible Blocker",
        position=(2, 1),
        faction="monsters",
        darkvision=False,
    )
    invisible.add_condition(
        Invisible(
            source_entity_uuid=invisible.uuid,
            target_entity_uuid=invisible.uuid,
        )
    )
    Entity.update_all_entities_senses(max_distance=10)

    assert invisible.uuid not in mover.senses.entities
    assert mover.senses.paths[(4, 1)] == [
        (0, 1),
        (1, 1),
        (2, 1),
        (3, 1),
        (4, 1),
    ]

    result = Move(
        source_entity_uuid=mover.uuid,
        end_position=(4, 1),
        use_movement_cost=False,
    ).apply()

    assert result is not None
    assert not result.canceled
    assert result.status_message == "Partial movement for Move, stopped at (1, 1)"
    assert mover.position == (1, 1)
    assert mover.senses.collision_blocked == {(2, 1)}
    assert invisible.is_invisible is True
    assert "Invisible" in invisible.active_conditions
    collision_completions = [
        event
        for event in EventQueue._all_events
        if isinstance(event, SpatialChangeEvent)
        and event.event_type == EventType.MOVEMENT_COLLISION
        and event.phase == EventPhase.COMPLETION
        and event.position == (2, 1)
    ]
    assert len(collision_completions) == 1

    mover.update_entity_senses(max_distance=10)

    corrected_path = mover.senses.paths[(4, 1)]
    assert corrected_path[0] == mover.position
    assert corrected_path[-1] == (4, 1)
    assert (2, 1) not in corrected_path


@pytest.mark.parametrize(
    "case",
    (
        "magic_missile_primary",
        "magic_missile_extra",
        "bane_extra",
        "bless_extra",
        "necrotic_bless_extra",
        "magic_missile_visible_control",
    ),
)
def test_eb_12_030_multi_entity_spells_reject_unperceived_explicit_targets(
    case: str,
) -> None:
    """EB-12-030: every explicit multi-target branch revalidates perception."""
    reset_senses_state(width=7, height=3)
    caster = create_caster(
        name="Caster",
        position=(0, 1),
        faction="heroes",
        level=5,
    )
    visible_enemy = create_skeleton(
        name="Visible Enemy",
        position=(2, 1),
        faction="monsters",
        darkvision=False,
    )
    second_visible_enemy = create_skeleton(
        name="Second Visible Enemy",
        position=(2, 0),
        faction="monsters",
        darkvision=False,
    )
    invisible_enemy = create_skeleton(
        name="Invisible Enemy",
        position=(2, 2),
        faction="monsters",
        darkvision=False,
    )
    visible_ally = create_skeleton(
        name="Visible Ally",
        position=(1, 0),
        faction="heroes",
        darkvision=False,
    )
    invisible_ally = create_skeleton(
        name="Invisible Ally",
        position=(1, 2),
        faction="heroes",
        darkvision=False,
    )
    for target in (invisible_enemy, invisible_ally):
        target.add_condition(
            Invisible(
                source_entity_uuid=target.uuid,
                target_entity_uuid=target.uuid,
            )
        )
    Entity.update_all_entities_senses(max_distance=10)

    assert visible_enemy.uuid in caster.senses.entities
    assert second_visible_enemy.uuid in caster.senses.entities
    assert visible_ally.uuid in caster.senses.entities
    assert invisible_enemy.uuid not in caster.senses.entities
    assert invisible_ally.uuid not in caster.senses.entities

    if case == "magic_missile_primary":
        action = MagicMissile(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=invisible_enemy.uuid,
            cast_at_level=1,
        )
        slot_level = 1
    elif case == "magic_missile_extra":
        action = MagicMissile(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=visible_enemy.uuid,
            extra_target_entity_uuids=[visible_enemy.uuid, invisible_enemy.uuid],
            cast_at_level=1,
        )
        slot_level = 1
    elif case == "bane_extra":
        action = Bane(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=visible_enemy.uuid,
            extra_target_entity_uuids=[invisible_enemy.uuid],
            cast_at_level=1,
        )
        slot_level = 1
    elif case == "bless_extra":
        action = Bless(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=visible_ally.uuid,
            extra_target_entity_uuids=[invisible_ally.uuid],
            cast_at_level=1,
        )
        slot_level = 1
    elif case == "necrotic_bless_extra":
        action = NecroticBless(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=visible_ally.uuid,
            extra_target_entity_uuids=[invisible_enemy.uuid],
            cast_at_level=2,
        )
        slot_level = 2
    else:
        action = MagicMissile(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=visible_enemy.uuid,
            extra_target_entity_uuids=[
                visible_enemy.uuid,
                second_visible_enemy.uuid,
            ],
            cast_at_level=1,
        )
        slot_level = 1

    actions_before = caster.action_economy.actions.normalized_score
    spell_slot = getattr(caster.action_economy, f"spell_slot_{slot_level}")
    slots_before = spell_slot.normalized_score
    result = action.apply()

    assert result is not None
    if case == "magic_missile_visible_control":
        assert not result.canceled
        assert caster.action_economy.actions.normalized_score == actions_before - 1
        assert (
            spell_slot.normalized_score == slots_before - 1
        )
    else:
        assert result.canceled
        assert result.status_message is not None
        assert (
            "not visible" in result.status_message
            or "not in line of sight" in result.status_message
        )
        assert caster.action_economy.actions.normalized_score == actions_before
        assert (
            spell_slot.normalized_score == slots_before
        )


def test_eb_12_031_perception_thresholds_refilter_contacts_and_hazards() -> None:
    """EB-12-031: sequential Perception changes cross each subjective threshold."""
    reset_senses_state(width=7, height=3)
    observer = create_skeleton(
        name="Observer",
        position=(0, 1),
        faction="heroes",
        darkvision=False,
    )
    easy_hidden = create_skeleton(
        name="Easy Hidden",
        position=(2, 0),
        faction="monsters",
        darkvision=False,
    )
    hard_hidden = create_skeleton(
        name="Hard Hidden",
        position=(2, 2),
        faction="monsters",
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=10)
    base_perception = observer.get_passive_perception()
    easy_dc = base_perception - 1
    hard_dc = base_perception + 3
    easy_hidden.add_condition(
        Hidden(
            source_entity_uuid=easy_hidden.uuid,
            target_entity_uuid=easy_hidden.uuid,
            stealth_result=easy_dc,
        )
    )
    hard_hidden.add_condition(
        Hidden(
            source_entity_uuid=hard_hidden.uuid,
            target_entity_uuid=hard_hidden.uuid,
            stealth_result=hard_dc,
        )
    )

    grid = get_map()
    for position, name, stealth_dc in (
        ((4, 0), "Easy Trap", easy_dc),
        ((4, 2), "Hard Trap", hard_dc),
    ):
        tile = grid.get_tile(*position)
        assert tile is not None
        tile.add_condition(
            BaseCondition(
                name=name,
                source_entity_uuid=uuid4(),
                target_entity_uuid=tile.uuid,
                condition_category=ConditionCategory.CONDITION,
                hazard_filter=HazardFilter.ALL,
                condition_stealth_dc=stealth_dc,
            )
        )
    Entity.update_all_entities_senses(max_distance=10)

    assert easy_hidden.uuid in observer.senses.entities
    assert hard_hidden.uuid not in observer.senses.entities
    assert easy_hidden.position not in observer.senses.paths
    assert hard_hidden.position in observer.senses.paths
    assert grid.is_position_hazardous_for(4, 0, observer.uuid)
    assert not grid.is_position_hazardous_for(4, 2, observer.uuid)

    cursor = EventQueue.event_cursor()
    observer.add_condition(
        PerceptionModifierCondition(
            source_entity_uuid=observer.uuid,
            target_entity_uuid=observer.uuid,
            modifier_amount=5,
        )
    )

    boosted_perception = observer.get_passive_perception()
    assert boosted_perception == base_perception + 5
    assert easy_hidden.uuid in observer.senses.entities
    assert hard_hidden.uuid in observer.senses.entities
    assert grid.is_position_hazardous_for(4, 0, observer.uuid)
    assert grid.is_position_hazardous_for(4, 2, observer.uuid)
    assert observer.senses._paths_dirty is True
    boost_updates = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == observer.uuid
        and event.passive_perception_changed
    ]
    assert len(boost_updates) == 1
    assert boost_updates[0].passive_perception == boosted_perception
    assert hard_hidden.uuid in boost_updates[0].entity_contacts_changed

    cursor = EventQueue.event_cursor()
    observer.remove_condition("Perception Payload Modifier")

    assert observer.get_passive_perception() == base_perception
    assert easy_hidden.uuid in observer.senses.entities
    assert hard_hidden.uuid not in observer.senses.entities
    assert grid.is_position_hazardous_for(4, 0, observer.uuid)
    assert not grid.is_position_hazardous_for(4, 2, observer.uuid)
    removal_updates = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == observer.uuid
        and event.passive_perception_changed
    ]
    assert len(removal_updates) == 1
    assert hard_hidden.uuid in removal_updates[0].entity_contacts_removed

    cursor = EventQueue.event_cursor()
    observer.add_condition(
        PerceptionModifierCondition(
            source_entity_uuid=observer.uuid,
            target_entity_uuid=observer.uuid,
            modifier_amount=-5,
        )
    )

    assert observer.get_passive_perception() == base_perception - 5
    assert easy_hidden.uuid not in observer.senses.entities
    assert hard_hidden.uuid not in observer.senses.entities
    assert not grid.is_position_hazardous_for(4, 0, observer.uuid)
    assert not grid.is_position_hazardous_for(4, 2, observer.uuid)
    assert observer.senses._paths_dirty is True
    decrease_updates = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == observer.uuid
        and event.passive_perception_changed
    ]
    assert len(decrease_updates) == 1
    assert easy_hidden.uuid in decrease_updates[0].entity_contacts_removed


def test_eb_12_032_hidden_transition_invalidates_subjective_occupancy_paths() -> None:
    """EB-12-032: hiding and revealing immediately invalidate cached paths."""
    reset_senses_state(width=5, height=1)
    observer = create_skeleton(
        name="Observer",
        position=(0, 0),
        faction="heroes",
        darkvision=False,
    )
    target = create_skeleton(
        name="Target",
        position=(2, 0),
        faction="monsters",
        darkvision=False,
    )
    Entity.update_all_entities_senses(max_distance=5)

    assert target.uuid in observer.senses.entities
    assert target.position not in observer.senses.paths

    target.add_condition(
        Hidden(
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
            stealth_result=observer.get_passive_perception() + 3,
        )
    )
    observer.update_entity_senses(max_distance=5)

    assert target.uuid not in observer.senses.entities
    assert target.position in observer.senses.paths

    target.remove_condition("Hidden")
    observer.update_entity_senses(max_distance=5)

    assert target.uuid in observer.senses.entities
    assert target.position not in observer.senses.paths


if __name__ == "__main__":
    tests = [
        test_eb_12_001_geometric_fov_is_filtered_by_effective_light,
        test_eb_12_002_sense_modes_subjectively_upgrade_light,
        test_eb_12_003_light_sources_use_light_fov_and_respect_light_blockers,
        test_eb_12_004_light_change_reveals_subscribed_dark_cells_reactively,
        test_eb_12_005_perceivability_flags_filter_hidden_and_invisible_blocks,
        test_eb_12_006_perceivability_events_refilter_visible_entities,
        test_eb_12_007_subjective_paths_do_not_leak_imperceivable_blockers,
        test_eb_12_008_self_movement_updates_visibility_and_marks_paths_dirty,
        test_eb_12_009_sense_mode_changes_emit_replacement_payloads,
        test_eb_12_010_very_bright_light_reveals_hidden_entities,
        test_eb_12_011_magical_darkness_zone_removal_recomputes_behind_cells,
        test_eb_12_012_passive_perception_changes_emit_replacement_payloads,
        test_eb_12_013_turn_start_clears_positional_and_directional_collision_memory,
        test_eb_12_014_plain_invisible_and_spell_invisibility_have_different_reveal_contracts,
        test_eb_12_015_hidden_cell_blocker_reveals_on_movement_collision,
        test_eb_12_016_hidden_and_invisible_flags_stack_independently,
        test_eb_12_017_multi_entity_spell_cancels_when_target_becomes_hidden,
        test_eb_12_018_aoe_preview_hides_hidden_entities_but_execution_hits_them,
        test_eb_12_019_passive_perception_decrease_removes_hidden_entity_payload,
        test_eb_12_020_distant_movement_does_not_dirty_unrelated_observer_paths,
        test_eb_12_021_movement_perception_matches_explicit_cold_recompute,
        test_eb_12_022_paired_movement_emits_one_subjective_transition,
        test_eb_12_023_sensory_dispatch_indexes_local_spatial_candidates,
        test_eb_12_024_sensory_dispatch_targets_own_perception_conditions,
        test_eb_12_025_attached_light_emits_one_batched_lifecycle_per_step,
        test_eb_12_026_batched_light_positions_reveal_hidden_entities,
    ]

    for test in tests:
        test()
        print(f"{test.__name__}: PASS")
