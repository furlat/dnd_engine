"""Observable contracts for independently owned spatial conditions."""

from typing import NoReturn
from uuid import UUID, uuid4

import pytest

from dnd.content.spatial_effect_materialization import (
    materialize_spatial_condition,
)
from dnd.content.spatial_effect_recipes import (
    ANTIMAGIC_FIELD_RECIPE,
    BUILT_IN_SPATIAL_EFFECT_DECLARATIONS,
    BURNING_WEB_FIRE_RECIPE,
    CLOUDKILL_CLOUD_RECIPE,
    CONTINUAL_FLAME_FIELD_RECIPE,
    DAYLIGHT_FIELD_RECIPE,
    ELECTRIFIED_WATER_RECIPE,
    FIRE_SURFACE_RECIPE,
    FOG_CLOUD_RECIPE,
    GREASE_SURFACE_RECIPE,
    ICE_SURFACE_RECIPE,
    OIL_SURFACE_RECIPE,
    SILENCE_FIELD_RECIPE,
    SLEET_STORM_FIELD_RECIPE,
    SPIRIT_GUARDIANS_FIELD_RECIPE,
    STEAM_CLOUD_RECIPE,
    WATER_SURFACE_DECLARATION,
    WATER_SURFACE_RECIPE,
)
from dnd.blocks.base_item import BaseItem
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.content.identities import ContentRef
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import ContentDeclarationMode
from dnd.core.dice import fixed_dice_faces
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.core.events.world_events import (
    SpatialEffectChangeEvent,
    SpatialEffectInteractionEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.base_tiles import dark_floor_factory, water_factory
from dnd.entities.entity import EntityConfig
from dnd.runtime_reset import reset_engine_runtime
from dnd.blocks.action_economy import RechargeType
from dnd.classes.sorcerer import DraconicPresence, DraconicPresenceAura
from dnd.spatial.area_conditions import SpatialCondition
from dnd.spatial.environmental_conditions import (
    ElectrifiedWater,
    FireSurface,
    IceSurface,
    OilSurface,
    SteamCloud,
    WaterSurface,
)
from dnd.spells.conjuration import GreaseZone, SleetStormZone
from dnd.spells.abjuration import FreedomOfMovementEffect
from dnd.conditions import Concentrating
from dnd.types.conditions import DurationType
from dnd.types.damage import DamageType, ResistanceStatus
from dnd.types.world import LightLevel
from dnd.types.spatial_effects import (
    SpatialEffectAnchorKind,
    SpatialEffectChangeOperation,
    SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation,
    SpatialEffectLayer,
    SpatialEffectTransitionAction,
)
from dnd.spells.evocation import ContinualFlameCondition
from tests.engine.support import create_test_entity


def _root_action(source_uuid: UUID) -> Event:
    completed = EventQueue.publish_lifecycle(Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        use_register=False,
    ))
    assert completed is not None
    return completed


_DIRECT_CONDITION_TYPES: dict[str, type[SpatialCondition]] = {
    OIL_SURFACE_RECIPE.ref.content_id: OilSurface,
    FIRE_SURFACE_RECIPE.ref.content_id: FireSurface,
    WATER_SURFACE_RECIPE.ref.content_id: WaterSurface,
    ICE_SURFACE_RECIPE.ref.content_id: IceSurface,
    ELECTRIFIED_WATER_RECIPE.ref.content_id: ElectrifiedWater,
    STEAM_CLOUD_RECIPE.ref.content_id: SteamCloud,
    BURNING_WEB_FIRE_RECIPE.ref.content_id: FireSurface,
}


def _materialize_test_condition(
    recipe: ContentRecipe,
    source_uuid: UUID,
    positions: set[tuple[int, int]],
    *,
    condition_type: type[SpatialCondition] | None = None,
    extra_fields: dict[str, object] | None = None,
) -> SpatialCondition:
    selected_type = condition_type or _DIRECT_CONDITION_TYPES.get(
        recipe.ref.content_id,
        SpatialCondition,
    )
    fields = dict(extra_fields or {})
    fields["affected_positions"] = set(positions)
    return materialize_spatial_condition(
        recipe,
        source_uuid,
        position=min(positions),
        faction="test-faction",
        condition_type=selected_type,
        condition_fields=fields,
    )


def _publish_interaction(
    source_uuid: UUID,
    operation: SpatialEffectInteractionOperation,
    positions: set[tuple[int, int]],
    intensity: SpatialEffectInteractionIntensity,
) -> Event:
    completed = EventQueue.publish_lifecycle(SpatialEffectInteractionEvent(
        source_entity_uuid=source_uuid,
        operation=operation,
        positions=tuple(sorted(positions)),
        intensity=intensity,
        phase=EventPhase.DECLARATION,
        use_register=False,
    ))
    assert completed is not None
    return completed


def test_spatial_trigger_sets_serialize_in_canonical_order() -> None:
    """Cold definitions authenticate unordered trigger membership identically."""
    definition = WATER_SURFACE_DECLARATION.spatial_effect_definition
    assert definition is not None
    assert definition.model_dump(mode="json")["trigger_kinds"] == [
        "appear",
        "enter",
        "leave",
    ]


@pytest.mark.parametrize(
    ("recipe", "expected_kind", "explicit_anchor"),
    (
        (GREASE_SURFACE_RECIPE, SpatialEffectAnchorKind.FIXED_POSITION, False),
        (
            CLOUDKILL_CLOUD_RECIPE,
            SpatialEffectAnchorKind.INDEPENDENT_MOVABLE,
            False,
        ),
        (SPIRIT_GUARDIANS_FIELD_RECIPE, SpatialEffectAnchorKind.ENTITY, False),
        (ANTIMAGIC_FIELD_RECIPE, SpatialEffectAnchorKind.ENTITY, False),
        (
            CONTINUAL_FLAME_FIELD_RECIPE,
            SpatialEffectAnchorKind.WORLD_OBJECT,
            True,
        ),
    ),
)
def test_authored_anchor_policy_materializes_exact_runtime_identity(
    recipe: ContentRecipe,
    expected_kind: SpatialEffectAnchorKind,
    explicit_anchor: bool,
) -> None:
    """Construction copies the authored anchor policy without reconstruction."""
    source_uuid = uuid4()
    anchor_uuid = uuid4() if explicit_anchor else None
    condition = materialize_spatial_condition(
        recipe,
        source_uuid,
        position=(1, 1),
        faction="heroes",
        condition_type=SpatialCondition,
        anchor_uuid=anchor_uuid,
    )

    assert condition.anchor_kind is expected_kind
    expected_anchor = (
        anchor_uuid
        if explicit_anchor
        else source_uuid if expected_kind is SpatialEffectAnchorKind.ENTITY else None
    )
    assert condition.anchor_uuid == expected_anchor


def test_tile_query_exposes_direct_condition_and_hazard() -> None:
    """A Tile reports the exact independently owned condition affecting it."""
    reset_engine_runtime(grid_size=(4, 4))
    source_uuid = uuid4()
    condition = _materialize_test_condition(
        OIL_SURFACE_RECIPE,
        source_uuid,
        {(1, 1), (1, 2)},
    )
    condition.activate(parent_event=_root_action(source_uuid))

    tile = get_map().get_tile(1, 1)
    assert tile is not None
    assert condition in tile.get_conditions().values()
    assert get_map().is_position_hazardous_for(1, 1)

    condition.deactivate()
    assert condition not in tile.get_conditions().values()
    assert not get_map().is_position_hazardous_for(1, 1)


def test_wet_membership_is_owned_by_each_exact_spatial_source() -> None:
    """Removing one water-bearing condition preserves another source's Wet."""
    reset_engine_runtime(grid_size=(5, 5))
    entity = create_test_entity(
        name="Wet target",
        config=EntityConfig(position=(2, 2)),
    )
    parent = _root_action(entity.uuid)
    water = _materialize_test_condition(
        WATER_SURFACE_RECIPE,
        entity.uuid,
        {(2, 2)},
    )
    steam = _materialize_test_condition(
        STEAM_CLOUD_RECIPE,
        entity.uuid,
        {(2, 2)},
        extra_fields={
            "duration": Duration(
                duration=2,
                duration_type=DurationType.ROUNDS,
            ),
        },
    )
    water.activate(parent_event=parent)
    steam.activate(parent_event=parent)

    assert len(entity.get_condition_application_leases("Wet")) == 2
    assert entity.health.get_resistance(DamageType.FIRE) is ResistanceStatus.RESISTANCE
    assert entity.health.get_resistance(DamageType.COLD) is ResistanceStatus.VULNERABILITY
    assert entity.health.get_resistance(DamageType.LIGHTNING) is ResistanceStatus.VULNERABILITY

    water.deactivate(parent_event=parent)
    assert "Wet" in entity.active_conditions
    assert len(entity.get_condition_application_leases("Wet")) == 1

    steam.deactivate(parent_event=parent)
    assert "Wet" not in entity.active_conditions


def test_partial_wet_footprint_release_removes_departed_membership() -> None:
    """Shrinking a Wet source releases occupants in removed cells only."""
    reset_engine_runtime(grid_size=(4, 4))
    entity = create_test_entity(
        name="Departed wet target",
        config=EntityConfig(position=(1, 1)),
    )
    parent = _root_action(entity.uuid)
    water = _materialize_test_condition(
        WATER_SURFACE_RECIPE,
        entity.uuid,
        {(1, 1), (1, 2)},
    )
    water.activate(parent_event=parent)
    assert "Wet" in entity.active_conditions

    water.transition_footprint({(1, 2)}, parent_event=parent)

    assert "Wet" not in entity.active_conditions
    assert water.affected_positions == {(1, 2)}


def test_water_transformations_do_not_replace_structural_water_tile() -> None:
    """Surface state transforms while the Tile retains swimming mechanics."""
    reset_engine_runtime(grid_size=(5, 5))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    grid = get_map()
    water_tile = water_factory((2, 2))
    grid.set_tile(2, 2, tile=water_tile, fire_event=False)
    surface = _materialize_test_condition(
        WATER_SURFACE_RECIPE,
        source_uuid,
        {(2, 2)},
    )
    surface.activate(parent_event=parent)

    _publish_interaction(
        source_uuid,
        SpatialEffectInteractionOperation.FREEZE,
        {(2, 2)},
        SpatialEffectInteractionIntensity.STRONG,
    )
    frozen = grid.get_spatial_conditions_at((2, 2))
    assert len(frozen) == 1
    assert frozen[0].content_ref == ICE_SURFACE_RECIPE.ref
    assert grid.get_tile(2, 2) is water_tile
    assert water_tile.swimming_cost.normalized_score == 1

    _publish_interaction(
        source_uuid,
        SpatialEffectInteractionOperation.VAPORIZE,
        {(2, 2)},
        SpatialEffectInteractionIntensity.STRONG,
    )
    assert grid.get_spatial_condition_uuids_at(
        (2, 2),
        layer=SpatialEffectLayer.GROUND_SURFACE,
    ) == set()
    steam = grid.get_spatial_conditions_at(
        (2, 2),
        layer=SpatialEffectLayer.CLOUD,
    )
    assert len(steam) == 1
    assert steam[0].content_ref == STEAM_CLOUD_RECIPE.ref
    assert grid.get_tile(2, 2) is water_tile
    assert water_tile.swimming_cost.normalized_score == 1


def test_freedom_of_movement_preserves_surface_slip_and_electricity() -> None:
    """Freedom bypasses movement penalties, not surface conditions or damage."""
    reset_engine_runtime(grid_size=(5, 5))
    entity = create_test_entity(
        name="Protected target",
        config=EntityConfig(position=(2, 2)),
    )
    parent = _root_action(entity.uuid)
    entity.add_condition(FreedomOfMovementEffect(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    ), parent_event=parent)
    ice = _materialize_test_condition(
        ICE_SURFACE_RECIPE,
        entity.uuid,
        {(2, 2)},
        extra_fields={"slip_save_dc": 100},
    )
    ice.activate(parent_event=parent)

    tile = get_map().get_tile(2, 2)
    assert tile is not None
    assert tile.walking_cost.normalized_score == 2
    assert entity.ignore_difficult_terrain
    assert "Prone" in entity.active_conditions

    ice.deactivate(parent_event=parent)
    entity.remove_condition("Prone", parent_event=parent)
    hp_before = entity.get_hp()
    water = _materialize_test_condition(
        WATER_SURFACE_RECIPE,
        entity.uuid,
        {(2, 2)},
    )
    water.activate(parent_event=parent)
    _publish_interaction(
        entity.uuid,
        SpatialEffectInteractionOperation.ELECTRIFY,
        {(2, 2)},
        SpatialEffectInteractionIntensity.STRONG,
    )

    assert "Wet" in entity.active_conditions
    assert entity.get_hp() < hp_before


def test_inherited_round_duration_expires_the_condition() -> None:
    """Spatial duration uses BaseCondition's one ordinary duration value."""
    reset_engine_runtime(grid_size=(3, 3))
    source_uuid = uuid4()
    condition = _materialize_test_condition(
        FIRE_SURFACE_RECIPE,
        source_uuid,
        {(1, 1)},
        extra_fields={
            "duration": Duration(
                duration=1,
                duration_type=DurationType.ROUNDS,
            ),
        },
    )
    condition.activate(parent_event=_root_action(source_uuid))

    assert condition.progress_spatial_duration()
    assert BaseCondition.get(condition.uuid) is None
    assert get_map().get_spatial_conditions() == []


_TRANSITION_CASES = tuple(
    (
        declaration.ref.content_id,
        transition.operation,
        transition.minimum_intensity,
        transition.action,
        (
            transition.replacement_recipe.ref
            if transition.replacement_recipe is not None
            else None
        ),
        transition.delay_rounds,
    )
    for declaration in BUILT_IN_SPATIAL_EFFECT_DECLARATIONS
    if declaration.spatial_effect_definition is not None
    for transition in declaration.spatial_effect_definition.transitions
)
_RECIPES_BY_CONTENT_ID = {
    declaration.ref.content_id: ContentRecipe.create(
        ref=declaration.ref,
        parameters={},
    )
    for declaration in BUILT_IN_SPATIAL_EFFECT_DECLARATIONS
}


@pytest.mark.parametrize(
    (
        "content_id",
        "operation",
        "intensity",
        "action",
        "replacement_ref",
        "delay_rounds",
    ),
    _TRANSITION_CASES,
)
def test_every_authored_transition_executes_through_the_live_event(
    content_id: str,
    operation: SpatialEffectInteractionOperation,
    intensity: SpatialEffectInteractionIntensity,
    action: SpatialEffectTransitionAction,
    replacement_ref: ContentRef | None,
    delay_rounds: int | None,
) -> None:
    """All fourteen authored rows transform exact intersected cells."""
    reset_engine_runtime(grid_size=(4, 4))
    source_uuid = uuid4()
    recipe = _RECIPES_BY_CONTENT_ID[content_id]
    condition = _materialize_test_condition(
        recipe,
        source_uuid,
        {(1, 1), (1, 2)},
    )
    condition.activate(parent_event=_root_action(source_uuid))

    _publish_interaction(
        source_uuid,
        operation,
        {(1, 1)},
        intensity,
    )

    if delay_rounds is not None:
        assert condition.affected_positions == {(1, 1), (1, 2)}
        assert condition.duration.duration_type is DurationType.ROUNDS
        assert condition.duration.duration == delay_rounds
        return

    assert condition.affected_positions == {(1, 2)}
    occupants = get_map().get_spatial_conditions_at((1, 1))
    if action is SpatialEffectTransitionAction.REMOVE_AFFECTED:
        assert occupants == []
    else:
        assert len(occupants) == 1
        assert isinstance(occupants[0], SpatialCondition)
        assert occupants[0].content_ref == replacement_ref
        assert occupants[0].faction == condition.faction


def test_material_collision_fails_without_partial_condition_or_events() -> None:
    """An unauthored material collision leaves the incumbent untouched."""
    reset_engine_runtime(grid_size=(4, 4))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    incumbent = _materialize_test_condition(
        OIL_SURFACE_RECIPE,
        source_uuid,
        {(1, 1), (1, 2)},
    )
    incumbent.activate(parent_event=parent)
    cursor = EventQueue.event_cursor()
    rejected = _materialize_test_condition(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        {(1, 1)},
    )

    with pytest.raises(ValueError, match="authored material transformation"):
        rejected.activate(parent_event=parent)

    assert BaseCondition.get(rejected.uuid) is None
    assert incumbent.affected_positions == {(1, 1), (1, 2)}
    assert get_map().get_spatial_condition_uuids_at(
        (1, 1),
        layer=SpatialEffectLayer.GROUND_SURFACE,
    ) == {incumbent.uuid}
    assert EventQueue.event_cursor() == cursor


def test_fields_overlap_and_deactivate_independently() -> None:
    """Overlapping fields remove only their own Tile memberships."""
    reset_engine_runtime(grid_size=(4, 4))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    daylight = _materialize_test_condition(
        DAYLIGHT_FIELD_RECIPE,
        source_uuid,
        {(2, 2)},
    )
    silence = _materialize_test_condition(
        SILENCE_FIELD_RECIPE,
        source_uuid,
        {(2, 2), (2, 3)},
    )
    daylight.activate(parent_event=parent)
    silence.activate(parent_event=parent)

    assert get_map().get_spatial_condition_uuids_at(
        (2, 2),
        layer=SpatialEffectLayer.FIELD,
    ) == {daylight.uuid, silence.uuid}

    daylight.deactivate(parent_event=parent)

    assert BaseCondition.get(daylight.uuid) is None
    assert BaseCondition.get(silence.uuid) is silence
    assert get_map().get_spatial_condition_uuids_at(
        (2, 2),
        layer=SpatialEffectLayer.FIELD,
    ) == {silence.uuid}


def test_deactivation_event_preserves_removed_geometry() -> None:
    """The existing removal fact reports the footprint after indexes are gone."""
    reset_engine_runtime(grid_size=(4, 4))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    condition = _materialize_test_condition(
        OIL_SURFACE_RECIPE,
        source_uuid,
        {(1, 1), (1, 2)},
    )
    condition.activate(parent_event=parent)
    cursor = EventQueue.event_cursor()

    condition.deactivate(parent_event=parent)

    removed = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialEffectChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.operation is SpatialEffectChangeOperation.REMOVED
    ]
    assert len(removed) == 1
    assert removed[0].spatial_effect_uuid == condition.uuid
    assert removed[0].affected_positions == ()
    assert removed[0].previous_positions == ((1, 1), (1, 2))
    assert removed[0].get_affected_positions() == {(1, 1), (1, 2)}


class FixedGreaseZone(GreaseZone):
    """Use exact cells while exercising Grease's real mechanics."""

    def resolve_area_footprint(self) -> set[tuple[int, int]]:
        return set(self.affected_positions)


class MovingGreaseZone(GreaseZone):
    """Use one center cell while exercising ordinary movement admission."""

    def resolve_area_footprint(self) -> set[tuple[int, int]]:
        return {self.position}

    def _compute_affected_positions(self) -> set[tuple[int, int]]:
        return {self.position}


def test_equal_same_material_replaces_only_its_overlap() -> None:
    """An equal later surface owns overlap while the remainder stays active."""
    reset_engine_runtime(grid_size=(8, 8))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    first = _materialize_test_condition(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        {(2, 2), (2, 3)},
        condition_type=FixedGreaseZone,
        extra_fields={"arbitration_potency": 15},
    )
    second = _materialize_test_condition(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        {(2, 3), (3, 3)},
        condition_type=FixedGreaseZone,
        extra_fields={"arbitration_potency": 15},
    )
    first.activate(parent_event=parent)
    second.activate(parent_event=parent)

    assert first.affected_positions == {(2, 2)}
    assert second.affected_positions == {(2, 3), (3, 3)}
    assert first.affected_positions.isdisjoint(second.affected_positions)


def test_weaker_same_material_cannot_downgrade_the_incumbent() -> None:
    """A weaker exact surface is rejected without changing the active one."""
    reset_engine_runtime(grid_size=(5, 5))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    stronger = _materialize_test_condition(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        {(2, 2)},
        condition_type=FixedGreaseZone,
        extra_fields={"arbitration_potency": 18},
    )
    weaker = _materialize_test_condition(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        {(2, 2)},
        condition_type=FixedGreaseZone,
        extra_fields={"arbitration_potency": 12},
    )
    stronger.activate(parent_event=parent)

    result = weaker.activate(parent_event=parent)

    assert result is parent
    assert BaseCondition.get(weaker.uuid) is None
    assert stronger.affected_positions == {(2, 2)}
    tile = get_map().get_tile(2, 2)
    assert tile is not None
    assert tile.walking_cost.normalized_score == 2


def test_declaration_veto_does_not_restore_an_undisplaced_incumbent() -> None:
    """Admission bookkeeping cannot duplicate mechanics before a swap commits."""
    reset_engine_runtime(grid_size=(5, 5))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    incumbent = _materialize_test_condition(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        {(2, 2)},
        condition_type=FixedGreaseZone,
        extra_fields={"arbitration_potency": 10},
    )
    incoming = _materialize_test_condition(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        {(2, 2)},
        condition_type=FixedGreaseZone,
        extra_fields={"arbitration_potency": 20},
    )
    incumbent.activate(parent_event=parent)

    def reject_application(event: Event, _source_uuid: UUID) -> Event:
        return event.cancel("test declaration veto")

    blocker = EventHandler(
        name="Reject spatial condition declaration",
        source_entity_uuid=source_uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.CONDITION_APPLICATION,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=reject_application,
    )
    EventQueue.add_event_handler(blocker)
    result = incoming.activate(parent_event=parent)
    blocker.remove()

    assert result is not None and result.canceled
    tile = get_map().get_tile(2, 2)
    assert tile is not None
    assert tile.walking_cost.normalized_score == 2
    assert incumbent.affected_positions == {(2, 2)}
    assert get_map().get_spatial_condition_uuids_at((2, 2)) == {
        incumbent.uuid,
    }


def test_one_activation_cannot_partially_retire_multiple_material_owners() -> None:
    """Ambiguous multi-owner merging is rejected before either owner changes."""
    reset_engine_runtime(grid_size=(5, 3))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    first = _materialize_test_condition(
        OIL_SURFACE_RECIPE,
        source_uuid,
        {(1, 1)},
        extra_fields={"arbitration_potency": 10},
    )
    second = _materialize_test_condition(
        OIL_SURFACE_RECIPE,
        source_uuid,
        {(3, 1)},
        extra_fields={"arbitration_potency": 10},
    )
    replacement = _materialize_test_condition(
        OIL_SURFACE_RECIPE,
        source_uuid,
        {(1, 1), (2, 1), (3, 1)},
        extra_fields={"arbitration_potency": 20},
    )
    first.activate(parent_event=parent)
    second.activate(parent_event=parent)

    with pytest.raises(ValueError, match="several independent condition owners"):
        replacement.activate(parent_event=parent)

    assert BaseCondition.get(first.uuid) is first
    assert BaseCondition.get(second.uuid) is second
    assert BaseCondition.get(replacement.uuid) is None
    assert first.affected_positions == {(1, 1)}
    assert second.affected_positions == {(3, 1)}
    assert {
        condition.uuid for condition in get_map().get_spatial_conditions()
    } == {first.uuid, second.uuid}


class FailingGreaseZone(FixedGreaseZone):
    """Fail after spatial mechanics are installed to prove local restoration."""

    def _apply(self, declaration_event: Event) -> NoReturn:
        super()._apply(declaration_event)
        raise RuntimeError("intentional condition failure")


class FailingWaterSurface(WaterSurface):
    """Fail after provisional installation to exercise membership rollback."""

    def _apply(self, declaration_event: Event) -> NoReturn:
        super()._apply(declaration_event)
        raise RuntimeError("intentional water failure")


def test_failed_same_material_activation_restores_the_incumbent() -> None:
    """A failed replacement cannot strand or duplicate the previous surface."""
    reset_engine_runtime(grid_size=(5, 5))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    incumbent = _materialize_test_condition(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        {(2, 2)},
        condition_type=FixedGreaseZone,
        extra_fields={"arbitration_potency": 10},
    )
    failed = _materialize_test_condition(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        {(2, 2)},
        condition_type=FailingGreaseZone,
        extra_fields={"arbitration_potency": 20},
    )
    incumbent.activate(parent_event=parent)

    with pytest.raises(RuntimeError, match="intentional condition failure"):
        failed.activate(parent_event=parent)

    assert BaseCondition.get(failed.uuid) is None
    assert incumbent.affected_positions == {(2, 2)}
    assert get_map().get_spatial_condition_uuids_at((2, 2)) == {
        incumbent.uuid,
    }
    tile = get_map().get_tile(2, 2)
    assert tile is not None
    assert tile.walking_cost.normalized_score == 2


def test_failed_water_replacement_preserves_incumbent_membership() -> None:
    """Provisional displacement cannot retire occupant-facing Wet state."""
    reset_engine_runtime(grid_size=(5, 5))
    entity = create_test_entity(
        name="Wet replacement target",
        config=EntityConfig(position=(2, 2)),
    )
    parent = _root_action(entity.uuid)
    incumbent = _materialize_test_condition(
        WATER_SURFACE_RECIPE,
        entity.uuid,
        {(2, 2)},
        extra_fields={"arbitration_potency": 10},
    )
    failed = _materialize_test_condition(
        WATER_SURFACE_RECIPE,
        entity.uuid,
        {(2, 2)},
        condition_type=FailingWaterSurface,
        extra_fields={"arbitration_potency": 20},
    )
    incumbent.activate(parent_event=parent)
    membership = incumbent.find_membership(entity)
    assert membership is not None

    with pytest.raises(RuntimeError, match="intentional water failure"):
        failed.activate(parent_event=parent)

    assert incumbent.affected_positions == {(2, 2)}
    assert incumbent.find_membership(entity) is membership
    assert "Wet" in entity.active_conditions
    assert get_map().get_spatial_condition_uuids_at((2, 2)) == {
        incumbent.uuid,
    }


@pytest.mark.parametrize(
    "removal_phase",
    (EventPhase.DECLARATION, EventPhase.EFFECT),
)
def test_incumbent_removal_veto_rejects_replacement_before_completion(
    removal_phase: EventPhase,
) -> None:
    """A veto keeps the installed owner and rejects the provisional newcomer."""
    reset_engine_runtime(grid_size=(5, 5))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    incumbent = _materialize_test_condition(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        {(2, 2)},
        condition_type=FixedGreaseZone,
        extra_fields={"arbitration_potency": 10},
    )
    replacement = _materialize_test_condition(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        {(2, 2)},
        condition_type=FixedGreaseZone,
        extra_fields={"arbitration_potency": 20},
    )
    incumbent.activate(parent_event=parent)

    blocker = EventHandler(
        name="Reject incumbent retirement",
        source_entity_uuid=source_uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.CONDITION_REMOVAL,
            event_phase=removal_phase,
        )],
        event_processor=lambda event, _source_uuid: event.cancel(
            "test incumbent removal veto",
        ),
    )
    EventQueue.add_event_handler(blocker)
    with pytest.raises(
        RuntimeError,
        match="rejected retirement",
    ):
        replacement.activate(parent_event=parent)
    blocker.remove()

    assert BaseCondition.get(replacement.uuid) is None
    assert incumbent.applied
    assert incumbent.affected_positions == {(2, 2)}
    assert get_map().get_spatial_condition_uuids_at((2, 2)) == {
        incumbent.uuid,
    }


def test_committed_spatial_facts_do_not_reenter_vetoable_lifecycle() -> None:
    """Creation is a completion fact after state commit, not a new proposal."""
    reset_engine_runtime(grid_size=(4, 4))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    condition = _materialize_test_condition(
        OIL_SURFACE_RECIPE,
        source_uuid,
        {(1, 1)},
    )
    declaration_calls = 0

    def reject_change_declaration(event: Event, _source_uuid: UUID) -> Event:
        nonlocal declaration_calls
        declaration_calls += 1
        return event.cancel("post-commit facts cannot be vetoed")

    blocker = EventHandler(
        name="Reject spatial change declaration",
        source_entity_uuid=source_uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_EFFECT_CHANGED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=reject_change_declaration,
    )
    EventQueue.add_event_handler(blocker)
    cursor = EventQueue.event_cursor()
    result = condition.activate(parent_event=parent)
    blocker.remove()

    assert result is not None and not result.canceled
    assert declaration_calls == 0
    created = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialEffectChangeEvent)
        and event.spatial_effect_uuid == condition.uuid
        and event.operation is SpatialEffectChangeOperation.CREATED
    ]
    assert len(created) == 1
    assert created[0].phase is EventPhase.COMPLETION


def test_tile_replacement_and_removal_reject_live_condition_references() -> None:
    """GridMap cannot strand a condition by discarding a covered Tile."""
    reset_engine_runtime(grid_size=(4, 4))
    source_uuid = uuid4()
    condition = _materialize_test_condition(
        OIL_SURFACE_RECIPE,
        source_uuid,
        {(1, 1)},
    )
    condition.activate(parent_event=_root_action(source_uuid))
    grid = get_map()

    with pytest.raises(ValueError, match="spatial conditions cover"):
        grid.set_tile(1, 1, fire_event=False)
    with pytest.raises(ValueError, match="spatial conditions cover"):
        grid.remove_tile(1, 1, fire_event=False)
    with pytest.raises(ValueError, match="spatial conditions cover"):
        grid.create_rectangle(0, 0, 4, 4)

    assert grid.get_spatial_condition_positions(condition.uuid) == {(1, 1)}
    assert grid.get_spatial_condition_uuids_at((1, 1)) == {condition.uuid}


def test_complete_same_material_replacement_reports_previous_geometry() -> None:
    """A fully displaced condition retains its footprint in TRANSFORMED."""
    reset_engine_runtime(grid_size=(5, 5))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    incumbent = _materialize_test_condition(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        {(2, 2)},
        condition_type=FixedGreaseZone,
        extra_fields={"arbitration_potency": 10},
    )
    replacement = _materialize_test_condition(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        {(2, 2)},
        condition_type=FixedGreaseZone,
        extra_fields={"arbitration_potency": 20},
    )
    incumbent.activate(parent_event=parent)
    cursor = EventQueue.event_cursor()

    replacement.activate(parent_event=parent)

    transformed = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialEffectChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.operation is SpatialEffectChangeOperation.TRANSFORMED
        and event.spatial_effect_uuid == incumbent.uuid
    ]
    assert len(transformed) == 1
    assert transformed[0].previous_positions == ((2, 2),)
    assert transformed[0].affected_positions == ()


def test_zone_move_collision_is_rejected_before_any_state_changes() -> None:
    """A conflicting destination leaves the moving zone and mechanics intact."""
    reset_engine_runtime(grid_size=(5, 5))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    moving = _materialize_test_condition(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        {(1, 1)},
        condition_type=MovingGreaseZone,
    )
    oil = _materialize_test_condition(
        OIL_SURFACE_RECIPE,
        source_uuid,
        {(2, 1)},
    )
    moving.activate(parent_event=parent)
    oil.activate(parent_event=parent)

    with pytest.raises(ValueError, match="already has a condition"):
        moving.move_zone((2, 1), parent_event=parent)

    assert moving.position == (1, 1)
    assert moving.position == (1, 1)
    assert moving.affected_positions == {(1, 1)}
    assert get_map().get_spatial_condition_uuids_at((1, 1)) == {moving.uuid}
    origin = get_map().get_tile(1, 1)
    assert origin is not None
    assert origin.walking_cost.normalized_score == 2


def test_independent_child_expiry_cleans_its_concentration_slot() -> None:
    """A retired spatial child cannot leave a stale concentration slot."""
    reset_engine_runtime(grid_size=(4, 4))
    caster = create_test_entity(
        name="Concentrating caster",
        config=EntityConfig(position=(1, 1)),
    )
    parent = _root_action(caster.uuid)
    concentration = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="Test field",
    )
    applied = caster.add_condition(concentration, parent_event=parent)
    assert applied is not None and not applied.canceled
    field = _materialize_test_condition(
        FOG_CLOUD_RECIPE,
        caster.uuid,
        {(1, 1)},
    )
    field.activate(parent_event=parent)
    concentration.add_linked_condition(field.uuid, field.uuid)

    field.deactivate(expire=True, parent_event=parent)

    assert "Concentrating" not in caster.active_conditions
    assert concentration.linked_conditions == []
    assert concentration.concentration_slots == {}


def test_sleet_activation_emits_douse_for_spatial_materials() -> None:
    """Sleet douses Fire through the typed interaction event used by all rows."""
    reset_engine_runtime(grid_size=(7, 7))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    fire = _materialize_test_condition(
        FIRE_SURFACE_RECIPE,
        source_uuid,
        {(3, 3)},
    )
    fire.activate(parent_event=parent)
    sleet = materialize_spatial_condition(
        SLEET_STORM_FIELD_RECIPE,
        source_uuid,
        position=(3, 3),
        faction="test-faction",
        condition_type=SleetStormZone,
    )

    sleet.activate(parent_event=parent)

    assert BaseCondition.get(fire.uuid) is None
    interactions = [
        event
        for event in EventQueue.get_events_by_type(
            EventType.SPATIAL_EFFECT_INTERACTION,
        )
        if isinstance(event, SpatialEffectInteractionEvent)
        and event.phase is EventPhase.COMPLETION
        and event.operation is SpatialEffectInteractionOperation.DOUSE
    ]
    assert len(interactions) == 1


def test_runtime_reset_clears_condition_collection_and_tile_memberships() -> None:
    """A new game cannot inherit independent condition ownership."""
    reset_engine_runtime(grid_size=(3, 3))
    source_uuid = uuid4()
    condition = _materialize_test_condition(
        DAYLIGHT_FIELD_RECIPE,
        source_uuid,
        {(1, 1)},
    )
    condition.activate(parent_event=_root_action(source_uuid))

    reset_engine_runtime(grid_size=(3, 3))

    assert BaseCondition.get(condition.uuid) is None
    assert get_map().get_spatial_conditions() == []
    tile = get_map().get_tile(1, 1)
    assert tile is not None
    assert tile.get_conditions() == {}


def test_grid_clear_rejects_live_spatial_conditions() -> None:
    """Clearing cannot strand live owners, handlers, or reverse footprints."""
    reset_engine_runtime(grid_size=(3, 3))
    source_uuid = uuid4()
    condition = _materialize_test_condition(
        DAYLIGHT_FIELD_RECIPE,
        source_uuid,
        {(1, 1)},
    )
    condition.activate(parent_event=_root_action(source_uuid))
    grid = get_map()

    with pytest.raises(ValueError, match="spatial conditions are active"):
        grid.clear()

    assert grid.get_spatial_conditions() == [condition]
    assert grid.get_spatial_condition_positions(condition.uuid) == {(1, 1)}


def test_world_object_anchor_moves_then_retires_with_its_object() -> None:
    """Object reindexing moves Continual Flame; actual removal retires it."""
    reset_engine_runtime(grid_size=(16, 6))
    grid = get_map()
    for x in range(16):
        for y in range(6):
            grid.set_tile(x, y, tile=dark_floor_factory((x, y)))
    source_uuid = uuid4()
    focus = BaseItem(source_entity_uuid=source_uuid, name="Flame focus")
    focus.place_on_grid((2, 2))
    flame = materialize_spatial_condition(
        CONTINUAL_FLAME_FIELD_RECIPE,
        source_uuid,
        position=(2, 2),
        faction=None,
        condition_type=ContinualFlameCondition,
        anchor_uuid=focus.uuid,
    )
    flame.activate(parent_event=_root_action(source_uuid))

    focus.place_on_grid((12, 2))

    assert flame.applied
    assert flame.affected_positions == {(12, 2)}
    assert grid.get_tile(2, 2).resolved_light_level is LightLevel.DARKNESS
    assert grid.get_tile(12, 2).resolved_light_level is LightLevel.BRIGHT_LIGHT

    grid.remove_object(focus.uuid)

    assert BaseCondition.get(flame.uuid) is None
    assert grid.get_tile(12, 2).resolved_light_level is LightLevel.DARKNESS


def test_draconic_presence_direct_action_owns_aura_and_cleanup() -> None:
    """The direct class action installs one aura and concentration owns it."""
    reset_engine_runtime(grid_size=(30, 30))
    caster = create_test_entity(
        name="Draconic sorcerer",
        config=EntityConfig(position=(10, 10), faction="heroes"),
    )
    target = create_test_entity(
        name="Aura target",
        config=EntityConfig(position=(11, 10), faction="monsters"),
    )
    caster.action_economy.add_resource_contribution(
        "sorcery_points",
        "test.draconic_presence",
        maximum=18,
        recharge_type=RechargeType.LONG_REST,
    )

    result = DraconicPresence(
        source_entity_uuid=caster.uuid,
        mode="awe",
    ).apply()

    assert result is not None and not result.canceled
    assert caster.action_economy.get_resource_current("sorcery_points") == 13
    aura = next(
        condition
        for condition in get_map().get_spatial_conditions()
        if isinstance(condition, DraconicPresenceAura)
    )
    assert aura.anchor_uuid == caster.uuid
    assert aura.duration.duration == 10
    assert "Concentrating" in caster.active_conditions

    with fixed_dice_faces(1):
        target.on_turn_start()
    assert "Charmed" in target.active_conditions

    caster.remove_condition("Concentrating")

    assert BaseCondition.get(aura.uuid) is None
    assert "Charmed" not in target.active_conditions


def test_draconic_presence_expires_with_concentration_after_ten_rounds() -> None:
    """The inherited duration retires the exact concentration-owned aura."""
    reset_engine_runtime(grid_size=(30, 30))
    caster = create_test_entity(
        name="Draconic sorcerer",
        config=EntityConfig(position=(10, 10), faction="heroes"),
    )
    caster.action_economy.add_resource_contribution(
        "sorcery_points",
        "test.draconic_presence",
        maximum=18,
        recharge_type=RechargeType.LONG_REST,
    )
    result = DraconicPresence(
        source_entity_uuid=caster.uuid,
        mode="fear",
    ).apply()
    assert result is not None and not result.canceled
    aura = next(
        condition
        for condition in get_map().get_spatial_conditions()
        if isinstance(condition, DraconicPresenceAura)
    )

    for _ in range(9):
        assert not aura.progress_spatial_duration()
    assert aura.progress_spatial_duration()

    assert BaseCondition.get(aura.uuid) is None
    assert "Concentrating" not in caster.active_conditions


def test_authored_inventory_retains_every_definition_and_transition() -> None:
    """The hard cut preserves all authored mechanics rows."""
    assert len(BUILT_IN_SPATIAL_EFFECT_DECLARATIONS) == 31
    assert all(
        declaration.mode is ContentDeclarationMode.TYPED_DEFINITION
        and declaration.spatial_effect_definition is not None
        and declaration.construction is None
        for declaration in BUILT_IN_SPATIAL_EFFECT_DECLARATIONS
    )
    assert len(_TRANSITION_CASES) == 14
