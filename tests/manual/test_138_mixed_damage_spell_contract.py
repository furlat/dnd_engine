"""Regression coverage for spells that apply one mixed typed damage packet."""

from dnd.actions import SpellEvent
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue, EventType, TakeDamageEvent
from dnd.core.gridmap import get_map
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import (
    ResistanceModifier,
    ResistanceStatus,
)
from dnd.entity import Entity
from dnd.spatial_effect_content import ICE_STORM_SURFACE_RECIPE
from dnd.spatial_effects import GroundEffect, SpatialEffect
from dnd.spells.evocation import IceStorm
from tests.engine.support import get_hp, has_condition
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    force_save_result,
    reset_spell_regression_arena,
)


def test_ice_storm_applies_bludgeoning_and_cold_as_typed_components() -> None:
    """Cold immunity removes only the cold component of one Ice Storm hit."""
    reset_spell_regression_arena(16, 9)
    caster = create_spell_regression_actor(
        "Typed Ice Storm Caster",
        (2, 4),
        "heroes",
        spell_slots={4: 1},
    )
    target = create_spell_regression_actor(
        "Cold Immune Target",
        (7, 4),
        "monsters",
    )
    target.health.damage_reduction.self_static.add_resistance_modifier(
        ResistanceModifier(
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
            name="Ice Storm cold immunity",
            value=ResistanceStatus.IMMUNITY,
            damage_type=DamageType.COLD,
        )
    )
    force_save_result(target, "dexterity", succeeds=False)
    Entity.update_all_entities_senses(max_distance=80)
    hp_before = get_hp(target)

    with fixed_dice_faces(10, *([4] * 2), *([3] * 4)):
        result = IceStorm(
            source_entity_uuid=caster.uuid,
            end_position=target.position,
            cast_at_level=4,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert hp_before - get_hp(target) == 8
    completions = [
        event
        for event in EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
        if isinstance(event, TakeDamageEvent)
        and event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == target.uuid
    ]
    assert len(completions) == 1
    resolution = completions[0].resolution
    assert resolution is not None
    assert [
        (component.damage_type, component.incoming_damage)
        for component in resolution.components
    ] == [
        (DamageType.BLUDGEONING, 8),
        (DamageType.COLD, 12),
    ]


def test_ice_storm_executes_upcast_save_cylinder_and_terrain_lifecycle() -> None:
    """Upcast cylinder crosses walls, halves once, and owns one-round terrain."""
    reset_spell_regression_arena(20, 10)
    grid = get_map()
    caster = create_spell_regression_actor(
        "Ice Storm Matrix Caster",
        (2, 4),
        "heroes",
        spell_slots={6: 1},
    )
    failed = create_spell_regression_actor(
        "Ice Storm Failed Save",
        (8, 4),
        "monsters",
    )
    behind_wall = create_spell_regression_actor(
        "Ice Storm Behind Wall",
        (10, 4),
        "monsters",
    )
    grid.set_tile(9, 4, walkable=False, visible=False, name="Wall")
    force_save_result(failed, "dexterity", succeeds=False)
    force_save_result(behind_wall, "dexterity", succeeds=True)
    Entity.update_all_entities_senses(max_distance=100)
    failed_hp = get_hp(failed)
    behind_hp = get_hp(behind_wall)

    with fixed_dice_faces(*([4] * 40)):
        result = IceStorm(
            source_entity_uuid=caster.uuid,
            end_position=failed.position,
            cast_at_level=6,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert failed_hp - get_hp(failed) == 32
    assert behind_hp - get_hp(behind_wall) == 16
    assert not has_condition(caster, "Concentrating")
    effects = [
        effect
        for effect in SpatialEffect.active_effects()
        if effect.content_ref == ICE_STORM_SURFACE_RECIPE.ref
    ]
    assert len(effects) == 1
    effect = effects[0]
    assert isinstance(effect, GroundEffect)
    assert "Ice Storm Terrain" in effect.active_conditions
    center_tile = grid.get_tile(*failed.position)
    assert center_tile is not None
    assert center_tile.walking_cost.normalized_score == 2

    assert effect.advance_duration("Ice Storm Terrain")

    assert SpatialEffect.get_effect(effect.uuid) is None
    assert center_tile.walking_cost.normalized_score == 1
