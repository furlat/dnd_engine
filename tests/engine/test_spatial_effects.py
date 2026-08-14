"""Engine invariants for independently owned persistent spatial effects."""

import ast
import inspect
from typing import NoReturn
from types import ModuleType
from uuid import UUID, uuid4

import pytest

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.content_system.spatial_effect_materialization import (
    materialize_spatial_effect,
)
from dnd.core.base_conditions import BaseCondition
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import ResistanceStatus
from dnd.core.events import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
    SpatialEffectChangeEvent,
    SpatialEffectInteractionEvent,
)
from dnd.core.content.dependencies import ContentDependencyRelation
from dnd.core.content.identities import ContentRef
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import get_content_declaration
from dnd.core.gridmap import get_map
from dnd.core.base_tiles import water_factory
from dnd.core.spatial_effect_types import (
    SpatialEffectAnchorKind,
    SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation,
    SpatialEffectLayer,
    SpatialEffectChangeOperation,
)
from dnd.items.environment_content import (
    OIL_BARREL_RECIPE,
    OilBarrel,
)
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial_effect_content import (
    ANTIMAGIC_FIELD_RECIPE,
    CLOUDKILL_CLOUD_RECIPE,
    CONTINUAL_FLAME_FIELD_RECIPE,
    DARKNESS_FIELD_RECIPE,
    DAYLIGHT_FIELD_RECIPE,
    GLOBE_OF_INVULNERABILITY_FIELD_RECIPE,
    FOG_CLOUD_RECIPE,
    GREASE_SURFACE_RECIPE,
    GUST_OF_WIND_FIELD_RECIPE,
    ICE_STORM_SURFACE_RECIPE,
    INSECT_PLAGUE_FIELD_RECIPE,
    INCENDIARY_CLOUD_RECIPE,
    FIRE_SURFACE_RECIPE,
    ELECTRIFIED_WATER_RECIPE,
    ICE_SURFACE_RECIPE,
    OIL_SURFACE_RECIPE,
    SILENCE_FIELD_RECIPE,
    SLEET_STORM_FIELD_RECIPE,
    SPIRIT_GUARDIANS_FIELD_RECIPE,
    SPIKE_GROWTH_SURFACE_RECIPE,
    STINKING_CLOUD_RECIPE,
    STEAM_CLOUD_RECIPE,
    WATER_SURFACE_DECLARATION,
    WATER_SURFACE_RECIPE,
    WEB_SURFACE_RECIPE,
)
from dnd.spatial_effects import (
    CloudEffect,
    FieldEffect,
    GroundEffect,
    SpatialEffect,
)
from dnd.entity import Entity, EntityConfig
from dnd.environmental_effects import IceSurfaceController
from dnd.spells.abjuration import FreedomOfMovementEffect
from dnd.spells.conjuration import GreaseZone
from server.world_projection import project_spatial_effect_summary
import dnd.spells.abjuration as abjuration
import dnd.spells.conjuration as conjuration
import dnd.spells.evocation as evocation
import dnd.spells.illusion as illusion
import dnd.spells.transmutation as transmutation


@pytest.fixture(scope="module", autouse=True)
def _installed_content_system() -> None:
    """Install the exact built-in registry used by material transition tests."""
    SERVER_CONTENT_SYSTEM_RUNTIME.install(
        bootstrap_content_system(),
    )


def _root_action(source_uuid: UUID) -> Event:
    event = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        use_register=False,
    )
    completed = EventQueue.publish_lifecycle(event)
    assert completed is not None
    return completed


def test_spatial_trigger_sets_serialize_in_canonical_order() -> None:
    """Cold workers must authenticate unordered trigger membership identically."""
    definition = WATER_SURFACE_DECLARATION.spatial_effect_definition
    assert definition is not None
    dumped = definition.model_dump(mode="json")
    assert dumped["trigger_kinds"] == ["appear", "enter", "leave"]


@pytest.mark.parametrize(
    ("recipe", "expected_kind", "attached_to_source"),
    (
        (
            GREASE_SURFACE_RECIPE,
            SpatialEffectAnchorKind.FIXED_POSITION,
            False,
        ),
        (
            CLOUDKILL_CLOUD_RECIPE,
            SpatialEffectAnchorKind.INDEPENDENT_MOVABLE,
            False,
        ),
        (
            SPIRIT_GUARDIANS_FIELD_RECIPE,
            SpatialEffectAnchorKind.ENTITY,
            True,
        ),
        (
            ANTIMAGIC_FIELD_RECIPE,
            SpatialEffectAnchorKind.ENTITY,
            True,
        ),
    ),
)
def test_authored_anchor_policy_materializes_exact_runtime_identity(
    recipe: ContentRecipe,
    expected_kind: SpatialEffectAnchorKind,
    attached_to_source: bool,
) -> None:
    """Cold anchor policy is copied exactly without spell-side reconstruction."""
    reset_engine_runtime(grid_size=(3, 3))
    source_uuid = uuid4()

    effect = materialize_spatial_effect(
        recipe,
        source_uuid,
        position=(1, 1),
        faction="heroes",
    )

    assert effect.anchor_kind is expected_kind
    assert effect.anchor_uuid == (source_uuid if attached_to_source else None)
    projected = project_spatial_effect_summary(effect)
    assert projected.anchor_kind == expected_kind.value


def test_oil_transition_replaces_only_intersecting_cells_and_douse_removes_fire() -> None:
    """Typed material interactions shrink, replace, and remove exact cells."""
    reset_engine_runtime(grid_size=(5, 5))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    oil = materialize_spatial_effect(
        OIL_SURFACE_RECIPE,
        source_uuid,
        position=(2, 2),
        faction=None,
    )
    oil.install_default_controller(
        positions={(2, 2), (2, 3)},
        duration_rounds=None,
        parent_event=parent,
    )

    ignited = EventQueue.publish_lifecycle(SpatialEffectInteractionEvent(
        source_entity_uuid=source_uuid,
        operation=SpatialEffectInteractionOperation.IGNITE,
        positions=((2, 2),),
        intensity=SpatialEffectInteractionIntensity.STRONG,
        damage_type=DamageType.FIRE,
        phase=EventPhase.DECLARATION,
        use_register=False,
    ))
    assert ignited is not None

    grid = get_map()
    remaining_oil_uuids = grid.get_spatial_effect_uuids_at(
        (2, 3),
        layer=SpatialEffectLayer.GROUND_SURFACE,
    )
    assert remaining_oil_uuids == {oil.uuid}
    assert oil.affected_positions == {(2, 3)}
    fire_uuids = grid.get_spatial_effect_uuids_at(
        (2, 2),
        layer=SpatialEffectLayer.GROUND_SURFACE,
    )
    assert len(fire_uuids) == 1
    fire = SpatialEffect.get_effect(next(iter(fire_uuids)))
    assert fire is not None
    assert fire.content_ref == FIRE_SURFACE_RECIPE.ref

    doused = EventQueue.publish_lifecycle(SpatialEffectInteractionEvent(
        source_entity_uuid=source_uuid,
        operation=SpatialEffectInteractionOperation.DOUSE,
        positions=((2, 2),),
        intensity=SpatialEffectInteractionIntensity.MODERATE,
        phase=EventPhase.DECLARATION,
        use_register=False,
    ))
    assert doused is not None
    assert SpatialEffect.get_effect(fire.uuid) is None
    assert grid.get_spatial_effect_uuids_at(
        (2, 2),
        layer=SpatialEffectLayer.GROUND_SURFACE,
    ) == set()
    assert SpatialEffect.get_effect(oil.uuid) is oil


def test_wet_surface_freezes_and_vaporizes_without_mutating_water_tile() -> None:
    """Structural Water remains a swim tile while surface state transforms."""
    reset_engine_runtime(grid_size=(5, 5))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    grid = get_map()
    water_tile = water_factory((2, 2))
    grid.set_tile(2, 2, tile=water_tile, fire_event=False)

    surface = materialize_spatial_effect(
        WATER_SURFACE_RECIPE,
        source_uuid,
        position=(2, 2),
        faction=None,
        expected_type=GroundEffect,
    )
    surface.install_default_controller(
        positions={(2, 2)},
        duration_rounds=None,
        parent_event=parent,
    )

    EventQueue.publish_lifecycle(SpatialEffectInteractionEvent(
        source_entity_uuid=source_uuid,
        operation=SpatialEffectInteractionOperation.FREEZE,
        positions=((2, 2),),
        intensity=SpatialEffectInteractionIntensity.STRONG,
        phase=EventPhase.DECLARATION,
        use_register=False,
    ))

    frozen_uuids = grid.get_spatial_effect_uuids_at(
        (2, 2),
        layer=SpatialEffectLayer.GROUND_SURFACE,
    )
    assert len(frozen_uuids) == 1
    frozen = SpatialEffect.get_effect(next(iter(frozen_uuids)))
    assert frozen is not None
    assert frozen.content_ref == ICE_SURFACE_RECIPE.ref
    assert grid.get_tile(2, 2) is water_tile
    assert water_tile.swimming_cost.normalized_score == 1

    EventQueue.publish_lifecycle(SpatialEffectInteractionEvent(
        source_entity_uuid=source_uuid,
        operation=SpatialEffectInteractionOperation.VAPORIZE,
        positions=((2, 2),),
        intensity=SpatialEffectInteractionIntensity.STRONG,
        phase=EventPhase.DECLARATION,
        use_register=False,
    ))

    assert grid.get_spatial_effect_uuids_at(
        (2, 2),
        layer=SpatialEffectLayer.GROUND_SURFACE,
    ) == set()
    steam_uuids = grid.get_spatial_effect_uuids_at(
        (2, 2),
        layer=SpatialEffectLayer.CLOUD,
    )
    assert len(steam_uuids) == 1
    steam = SpatialEffect.get_effect(next(iter(steam_uuids)))
    assert isinstance(steam, CloudEffect)
    assert steam.content_ref == STEAM_CLOUD_RECIPE.ref
    assert grid.get_tile(2, 2) is water_tile
    assert water_tile.swimming_cost.normalized_score == 1


def test_wet_membership_is_source_owned_across_ground_and_steam() -> None:
    """Leaving one water-bearing layer cannot clear another source's Wet."""
    reset_engine_runtime(grid_size=(5, 5))
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name="Wet target",
        config=EntityConfig(position=(2, 2)),
    )
    parent = _root_action(entity.uuid)
    ground = materialize_spatial_effect(
        WATER_SURFACE_RECIPE,
        entity.uuid,
        position=(2, 2),
        faction=None,
        expected_type=GroundEffect,
    )
    ground.install_default_controller(
        positions={(2, 2)},
        duration_rounds=None,
        parent_event=parent,
    )
    steam = materialize_spatial_effect(
        STEAM_CLOUD_RECIPE,
        entity.uuid,
        position=(2, 2),
        faction=None,
        expected_type=CloudEffect,
    )
    steam.install_default_controller(
        positions={(2, 2)},
        duration_rounds=2,
        parent_event=parent,
    )

    assert "Wet" in entity.active_conditions
    assert len(entity.get_condition_application_leases("Wet")) == 2
    assert (
        entity.health.get_resistance(DamageType.FIRE)
        is ResistanceStatus.RESISTANCE
    )
    assert (
        entity.health.get_resistance(DamageType.COLD)
        is ResistanceStatus.VULNERABILITY
    )
    assert (
        entity.health.get_resistance(DamageType.LIGHTNING)
        is ResistanceStatus.VULNERABILITY
    )

    ground.retire(parent_event=parent)
    assert "Wet" in entity.active_conditions
    assert len(entity.get_condition_application_leases("Wet")) == 1

    steam.retire(parent_event=parent)
    assert "Wet" not in entity.active_conditions


def test_freedom_of_movement_does_not_suppress_surface_slip_or_damage() -> None:
    """FoM bypasses movement penalties, not Wet, ice slipping, or electricity."""
    reset_engine_runtime(grid_size=(5, 5))
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name="Protected target",
        config=EntityConfig(position=(2, 2)),
    )
    parent = _root_action(entity.uuid)
    entity.add_condition(FreedomOfMovementEffect(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    ))

    ice = materialize_spatial_effect(
        ICE_SURFACE_RECIPE,
        entity.uuid,
        position=(2, 2),
        faction=None,
        expected_type=GroundEffect,
    )
    ice_controller = IceSurfaceController(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=ice.uuid,
        fixed_positions={(2, 2)},
        slip_save_dc=100,
    )
    ice.install_controller(ice_controller, parent_event=parent)

    tile = get_map().get_tile(2, 2)
    assert tile is not None
    assert tile.walking_cost.normalized_score == 2
    assert entity.ignore_difficult_terrain
    assert "Prone" in entity.active_conditions

    ice.retire(parent_event=parent)
    entity.remove_condition("Prone", parent_event=parent)
    hp_before = entity.get_hp()
    water = materialize_spatial_effect(
        WATER_SURFACE_RECIPE,
        entity.uuid,
        position=(2, 2),
        faction=None,
        expected_type=GroundEffect,
    )
    water.install_default_controller(
        positions={(2, 2)},
        duration_rounds=None,
        parent_event=parent,
    )
    EventQueue.publish_lifecycle(SpatialEffectInteractionEvent(
        source_entity_uuid=entity.uuid,
        operation=SpatialEffectInteractionOperation.ELECTRIFY,
        positions=((2, 2),),
        intensity=SpatialEffectInteractionIntensity.STRONG,
        phase=EventPhase.DECLARATION,
        use_register=False,
    ))

    effect_uuids = get_map().get_spatial_effect_uuids_at(
        (2, 2),
        layer=SpatialEffectLayer.GROUND_SURFACE,
    )
    assert len(effect_uuids) == 1
    electrified = SpatialEffect.get_effect(next(iter(effect_uuids)))
    assert electrified is not None
    assert electrified.content_ref == ELECTRIFIED_WATER_RECIPE.ref
    assert "Wet" in entity.active_conditions
    assert entity.get_hp() < hp_before


@pytest.mark.parametrize(
    ("damage_type", "expected_ref"),
    (
        (DamageType.BLUDGEONING, OIL_SURFACE_RECIPE.ref),
        (DamageType.FIRE, FIRE_SURFACE_RECIPE.ref),
    ),
)
def test_oil_barrel_destruction_uses_material_transition_table(
    damage_type: DamageType,
    expected_ref: ContentRef,
) -> None:
    """A barrel spills oil; accepted fire damage ignites it causally."""
    reset_engine_runtime(grid_size=(5, 5))
    source_uuid = uuid4()
    barrel = materialize_item(
        OIL_BARREL_RECIPE,
        source_uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=OilBarrel,
    )
    barrel.place_on_grid((2, 2))
    starting_hp = barrel.get_hp()

    dealt = barrel.receive_damage(
        starting_hp,
        damage_type,
        source_uuid,
    )

    assert dealt == starting_hp
    effect_uuids = get_map().get_spatial_effect_uuids_at(
        (2, 2),
        layer=SpatialEffectLayer.GROUND_SURFACE,
    )
    assert len(effect_uuids) == 1
    effect = SpatialEffect.get_effect(next(iter(effect_uuids)))
    assert effect is not None
    assert effect.content_ref == expected_ref


def test_material_layers_reject_implicit_replacement_without_partial_indexing() -> None:
    """Exclusive material cells require a declared transformation operation."""
    reset_engine_runtime(grid_size=(4, 4))
    source_uuid = uuid4()
    oil = GroundEffect(
        name="Oil",
        source_entity_uuid=source_uuid,
        content_ref=GREASE_SURFACE_RECIPE.ref,
        position=(1, 1),
    )
    grease = GroundEffect(
        name="Grease",
        source_entity_uuid=source_uuid,
        content_ref=GREASE_SURFACE_RECIPE.ref,
        position=(1, 1),
    )

    oil.synchronize_footprint({(1, 1), (1, 2)})

    with pytest.raises(
        ValueError,
        match=r"ground_surface cell \(1, 1\) already has an effect",
    ):
        grease.synchronize_footprint({(1, 1)})

    grid = get_map()
    assert grid.get_spatial_effect_uuids_at(
        (1, 1),
        layer=SpatialEffectLayer.GROUND_SURFACE,
    ) == {oil.uuid}
    assert grid.get_spatial_effect_uuids_at(
        (1, 2),
        layer=SpatialEffectLayer.GROUND_SURFACE,
    ) == {oil.uuid}
    assert grease.affected_positions == set()


def test_fields_overlap_and_retire_without_disturbing_each_other() -> None:
    """Influence fields coexist and clean up only their own indexed cells."""
    reset_engine_runtime(grid_size=(4, 4))
    source_uuid = uuid4()
    light = FieldEffect(
        name="Daylight",
        source_entity_uuid=source_uuid,
        content_ref=DAYLIGHT_FIELD_RECIPE.ref,
        position=(2, 2),
    )
    silence = FieldEffect(
        name="Silence",
        source_entity_uuid=source_uuid,
        content_ref=SILENCE_FIELD_RECIPE.ref,
        position=(2, 2),
    )

    light.synchronize_footprint({(2, 2)})
    silence.synchronize_footprint({(2, 2), (2, 3)})

    grid = get_map()
    assert grid.get_spatial_effect_uuids_at(
        (2, 2),
        layer=SpatialEffectLayer.FIELD,
    ) == {light.uuid, silence.uuid}

    light.retire()

    assert SpatialEffect.get_effect(light.uuid) is None
    assert SpatialEffect.get_effect(silence.uuid) is silence
    assert grid.get_spatial_effect_uuids_at(
        (2, 2),
        layer=SpatialEffectLayer.FIELD,
    ) == {silence.uuid}
    assert grid.get_spatial_effect_uuids_at(
        (2, 3),
        layer=SpatialEffectLayer.FIELD,
    ) == {silence.uuid}


def test_retirement_event_preserves_removed_geometry_for_projection_and_log() -> None:
    """Effect retirement reports the former cells after indexes are removed."""
    reset_engine_runtime(grid_size=(4, 4))
    source_uuid = uuid4()
    parent = _root_action(source_uuid)
    effect = materialize_spatial_effect(
        OIL_SURFACE_RECIPE,
        source_uuid,
        position=(1, 1),
        faction=None,
    )
    effect.install_default_controller(
        positions={(1, 1), (1, 2)},
        duration_rounds=None,
        parent_event=parent,
    )
    cursor = EventQueue.event_cursor()

    effect.retire(parent_event=parent)

    removed_events = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialEffectChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.operation is SpatialEffectChangeOperation.REMOVED
    ]
    assert len(removed_events) == 1
    removed = removed_events[0]
    assert removed.affected_positions == ()
    assert removed.previous_positions == ((1, 1), (1, 2))
    assert removed.get_affected_positions() == {(1, 1), (1, 2)}
    assert removed.combat_log is not None
    assert removed.combat_log.data["affected_positions"] == [
        [1, 1],
        [1, 2],
    ]


def test_different_material_collision_fails_before_runtime_leases_are_added() -> None:
    """Exclusive materials require an authored transition and leak no controller."""
    reset_engine_runtime(grid_size=(7, 7))
    source_uuid = uuid4()
    parent_event = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    first = materialize_spatial_effect(
        OIL_SURFACE_RECIPE,
        source_uuid,
        position=(3, 3),
        faction=None,
        expected_type=GroundEffect,
    )
    result = first.install_default_controller(
        positions={(3, 3)},
        duration_rounds=None,
        parent_event=parent_event,
    )
    assert result is not None and not result.canceled
    center = get_map().get_tile(3, 3)
    assert center is not None
    spatial_handler_count = len(EventQueue._handler_positions)
    event_handler_count = len(EventQueue._event_handlers)

    second = materialize_spatial_effect(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        position=(3, 3),
        faction=None,
        expected_type=GroundEffect,
    )
    second_controller = GreaseZone(
        source_entity_uuid=source_uuid,
        target_entity_uuid=second.uuid,
        zone_center=(3, 3),
    )
    with pytest.raises(ValueError, match="authored material transformation"):
        second.install_controller(
            second_controller,
            parent_event=parent_event,
        )

    assert SpatialEffect.get_effect(second.uuid) is None
    assert BaseCondition.get(second_controller.uuid) is None
    assert len(EventQueue._handler_positions) == spatial_handler_count
    assert len(EventQueue._event_handlers) == event_handler_count


def test_equal_same_material_replaces_overlap_without_stacking_mechanics() -> None:
    """A later equal surface owns overlap while non-overlap remains independent."""
    reset_engine_runtime(grid_size=(8, 8))
    source_uuid = uuid4()
    parent_event = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    first = materialize_spatial_effect(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        position=(2, 3),
        faction=None,
        expected_type=GroundEffect,
    )
    first_controller = GreaseZone(
        source_entity_uuid=source_uuid,
        target_entity_uuid=first.uuid,
        zone_center=(2, 3),
        arbitration_potency=15,
    )
    assert first.install_controller(first_controller, parent_event=parent_event)
    original_first = set(first.affected_positions)

    second = materialize_spatial_effect(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        position=(3, 3),
        faction=None,
        expected_type=GroundEffect,
    )
    second_controller = GreaseZone(
        source_entity_uuid=source_uuid,
        target_entity_uuid=second.uuid,
        zone_center=(3, 3),
        arbitration_potency=15,
    )
    assert second.install_controller(second_controller, parent_event=parent_event)

    assert first.affected_positions == original_first - second.affected_positions
    assert first.affected_positions
    assert first.affected_positions.isdisjoint(second.affected_positions)
    for position in original_first & second.affected_positions:
        tile = get_map().get_tile(*position)
        assert tile is not None
        assert tile.walking_cost.normalized_score == 2


def test_weaker_same_material_cannot_downgrade_the_active_surface() -> None:
    """A weaker exact surface is suppressed rather than replacing a stronger DC."""
    reset_engine_runtime(grid_size=(7, 7))
    source_uuid = uuid4()
    parent_event = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    stronger = materialize_spatial_effect(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        position=(3, 3),
        faction=None,
        expected_type=GroundEffect,
    )
    strong_controller = GreaseZone(
        source_entity_uuid=source_uuid,
        target_entity_uuid=stronger.uuid,
        zone_center=(3, 3),
        spell_dc=18,
        arbitration_potency=18,
    )
    assert stronger.install_controller(strong_controller, parent_event=parent_event)
    strong_positions = set(stronger.affected_positions)

    weaker = materialize_spatial_effect(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        position=(3, 3),
        faction=None,
        expected_type=GroundEffect,
    )
    weak_controller = GreaseZone(
        source_entity_uuid=source_uuid,
        target_entity_uuid=weaker.uuid,
        zone_center=(3, 3),
        spell_dc=12,
        arbitration_potency=12,
    )
    result = weaker.install_controller(weak_controller, parent_event=parent_event)

    assert result is parent_event
    assert SpatialEffect.get_effect(weaker.uuid) is None
    assert stronger.affected_positions == strong_positions
    assert BaseCondition.get(strong_controller.uuid) is strong_controller
    assert BaseCondition.get(weak_controller.uuid) is None


class FailingGreaseZone(GreaseZone):
    """Test-only controller that fails after overlap indexes are staged."""

    def _apply(self, declaration_event: Event) -> NoReturn:
        del declaration_event
        raise RuntimeError("intentional controller failure")


def test_same_material_staging_restores_incumbent_when_install_fails() -> None:
    """A failed replacement cannot strand the incumbent outside the grid index."""
    reset_engine_runtime(grid_size=(7, 7))
    source_uuid = uuid4()
    parent_event = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    incumbent = materialize_spatial_effect(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        position=(3, 3),
        faction=None,
        expected_type=GroundEffect,
    )
    incumbent_controller = GreaseZone(
        source_entity_uuid=source_uuid,
        target_entity_uuid=incumbent.uuid,
        zone_center=(3, 3),
        arbitration_potency=10,
    )
    assert incumbent.install_controller(
        incumbent_controller,
        parent_event=parent_event,
    )
    original_positions = set(incumbent.affected_positions)

    failed = materialize_spatial_effect(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        position=(3, 3),
        faction=None,
        expected_type=GroundEffect,
    )
    failed_controller = FailingGreaseZone(
        source_entity_uuid=source_uuid,
        target_entity_uuid=failed.uuid,
        zone_center=(3, 3),
        arbitration_potency=20,
    )
    with pytest.raises(RuntimeError, match="intentional controller failure"):
        failed.install_controller(failed_controller, parent_event=parent_event)

    assert SpatialEffect.get_effect(failed.uuid) is None
    assert incumbent.affected_positions == original_positions
    assert all(
        get_map().get_spatial_effect_uuids_at(
            position,
            layer=SpatialEffectLayer.GROUND_SURFACE,
        )
        == {incumbent.uuid}
        for position in original_positions
    )


def test_runtime_reset_clears_effect_registry_and_grid_indexes() -> None:
    """Encounter reset cannot leak effect ownership into the next game."""
    reset_engine_runtime(grid_size=(3, 3))
    effect = FieldEffect(
        name="Probe",
        source_entity_uuid=uuid4(),
        content_ref=DAYLIGHT_FIELD_RECIPE.ref,
        position=(1, 1),
    )
    effect.synchronize_footprint({(1, 1)})

    reset_engine_runtime(grid_size=(3, 3))

    assert SpatialEffect.active_effects() == ()
    assert get_map().get_spatial_effect_uuids_at((1, 1)) == set()


@pytest.mark.parametrize(
    ("spell_type", "effect_ref"),
    (
        (conjuration.Grease, GREASE_SURFACE_RECIPE.ref),
        (conjuration.Cloudkill, CLOUDKILL_CLOUD_RECIPE.ref),
        (conjuration.FogCloud, FOG_CLOUD_RECIPE.ref),
        (conjuration.IncendiaryCloud, INCENDIARY_CLOUD_RECIPE.ref),
        (conjuration.StinkingCloud, STINKING_CLOUD_RECIPE.ref),
        (conjuration.SpiritGuardians, SPIRIT_GUARDIANS_FIELD_RECIPE.ref),
        (conjuration.Darkness, DARKNESS_FIELD_RECIPE.ref),
        (conjuration.Daylight, DAYLIGHT_FIELD_RECIPE.ref),
        (conjuration.InsectPlague, INSECT_PLAGUE_FIELD_RECIPE.ref),
        (conjuration.SleetStorm, SLEET_STORM_FIELD_RECIPE.ref),
        (illusion.Silence, SILENCE_FIELD_RECIPE.ref),
        (evocation.GustOfWind, GUST_OF_WIND_FIELD_RECIPE.ref),
        (evocation.IceStorm, ICE_STORM_SURFACE_RECIPE.ref),
        (transmutation.SpikeGrowth, SPIKE_GROWTH_SURFACE_RECIPE.ref),
        (conjuration.Web, WEB_SURFACE_RECIPE.ref),
        (
            abjuration.GlobeOfInvulnerability,
            GLOBE_OF_INVULNERABILITY_FIELD_RECIPE.ref,
        ),
        (abjuration.AntimagicField, ANTIMAGIC_FIELD_RECIPE.ref),
        (evocation.ContinualFlame, CONTINUAL_FLAME_FIELD_RECIPE.ref),
    ),
)
def test_spatial_spell_dependencies_name_the_exact_created_effect(
    spell_type: type[object],
    effect_ref: ContentRef,
) -> None:
    """Every migrated spell statically declares its exact spatial output."""
    declaration = get_content_declaration(spell_type)
    created_refs = tuple(
        dependency.target_ref
        for dependency in declaration.dependencies
        if dependency.relation
        is ContentDependencyRelation.CREATES_SPATIAL_EFFECT
    )
    assert created_refs == (effect_ref,)


@pytest.mark.parametrize(
    "module",
    (abjuration, conjuration, evocation, illusion, transmutation),
)
def test_spells_do_not_construct_spatial_owners_outside_the_materializer(
    module: ModuleType,
) -> None:
    """Production spell code has one authenticated construction path."""
    tree = ast.parse(inspect.getsource(module))
    forbidden = {
        "SpatialEffect",
        "GroundEffect",
        "CloudEffect",
        "FieldEffect",
    }
    calls = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in forbidden
    ]
    assert calls == []
