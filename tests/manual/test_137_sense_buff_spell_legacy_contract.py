"""Deterministic parity for the archived 16-case sense-buff spell matrix."""

from uuid import UUID

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_by_index, register_spell
from dnd.conditions import Concentrating, Invisible
from dnd.core.base_actions import AvailableActionsResult
from dnd.core.base_block import LightLevel, SensesType
from dnd.core.base_conditions import DurationType
from dnd.core.base_tiles import dark_floor_factory
from dnd.core.events import (
    EventPhase,
    EventQueue,
    SensoryUpdateEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.modifiers import DamageType
from dnd.entity import Entity
from dnd.spells.divination import SeeInvisibility, TrueSeeing
from dnd.spells.evocation import FireBolt
from dnd.spells.illusion import Invisibility
from dnd.spells.transmutation import DarkvisionSpell
from dnd.utils import (
    deal_damage_to,
    force_attack_hit,
    get_hp,
    has_condition,
    remove_attack_modifier,
    reset_combat_state,
)
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    force_save_result,
    reset_spell_regression_arena,
)


def _caster(
    name: str,
    position: tuple[int, int],
    *,
    spell_slots: dict[int, int],
) -> Entity:
    """Create a legal Intelligence caster for the requested slot matrix."""
    return create_spell_regression_actor(
        name,
        position,
        "heroes",
        spell_slots=spell_slots,
    )


def _enemy(name: str, position: tuple[int, int]) -> Entity:
    """Create a durable hostile perception target."""
    return create_spell_regression_actor(name, position, "monsters")


def _has_sense(
    entity: Entity,
    sense_type: SensesType,
    *,
    range_feet: int | None = None,
) -> bool:
    """Return whether an entity owns the exact requested sense mode."""
    return any(
        mode.sense_type is sense_type
        and (range_feet is None or mode.range_feet == range_feet)
        for mode in entity.senses.sense_modes
    )


def _completed_sensory_updates(observer_uuid: UUID) -> list[SensoryUpdateEvent]:
    """Return completed first-class sensory deltas for one observer."""
    return [
        event
        for event in EventQueue._all_events
        if isinstance(event, SensoryUpdateEvent)
        and event.phase is EventPhase.COMPLETION
        and event.observer_uuid == observer_uuid
    ]


def _reset_dark_arena(width: int = 16, height: int = 7) -> None:
    """Reset runtime state and create a uniformly dark walkable grid."""
    reset_combat_state()
    grid = get_map()
    for x in range(width):
        for y in range(height):
            grid.set_tile(
                x,
                y,
                tile=dark_floor_factory((x, y)),
                fire_event=False,
            )


def _break_concentration(caster: Entity) -> None:
    """Deterministically fail one ordinary concentration save."""
    force_save_result(caster, "constitution", succeeds=False)
    dealt = deal_damage_to(
        caster,
        10,
        DamageType.FIRE,
        source_uuid=caster.uuid,
    )
    assert dealt == 10


def _cast_darkvision(caster: Entity, target: Entity) -> SpellEvent:
    """Cast one legal level-two Darkvision and return its typed result."""
    result = DarkvisionSpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=2,
    ).apply()
    assert isinstance(result, SpellEvent)
    return result


def _cast_see_invisibility(caster: Entity) -> SpellEvent:
    """Cast one legal level-two See Invisibility."""
    result = SeeInvisibility(
        source_entity_uuid=caster.uuid,
        cast_at_level=2,
    ).apply()
    assert isinstance(result, SpellEvent)
    return result


def _cast_true_seeing(caster: Entity, target: Entity) -> SpellEvent:
    """Cast one legal level-six True Seeing."""
    result = TrueSeeing(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=6,
    ).apply()
    assert isinstance(result, SpellEvent)
    return result


def _fire_bolt_target_index(
    caster: Entity,
    target: Entity,
) -> tuple[int, AvailableActionsResult]:
    """Return the target's current Fire Bolt index and its discovery snapshot."""
    available = caster.get_available_actions()
    row = next(
        action
        for action in available.entity_actions
        if action.template_name == "Fire Bolt"
    )
    target_row = next(
        candidate
        for candidate in row.valid_targets
        if candidate.target_uuid == target.uuid
    )
    return target_row.index, available


def test_darkvision_self_lifecycle_and_concentration_cleanup() -> None:
    """Old case 1: self grant and linked concentration cleanup are reactive."""
    reset_spell_regression_arena(14, 7)
    caster = _caster("Darkvision Caster", (2, 3), spell_slots={2: 1})
    Entity.update_all_entities_senses(max_distance=60)
    assert not _has_sense(caster, SensesType.DARKVISION)

    result = _cast_darkvision(caster, caster)

    assert not result.canceled
    assert _has_sense(caster, SensesType.DARKVISION, range_feet=60)
    assert has_condition(caster, "Darkvision")
    concentration = caster.active_conditions.get("Concentrating")
    assert isinstance(concentration, Concentrating)
    assert concentration.spell_name == "Darkvision"

    _break_concentration(caster)
    assert not _has_sense(caster, SensesType.DARKVISION)
    assert not has_condition(caster, "Darkvision")
    assert not has_condition(caster, "Concentrating")


def test_darkvision_ally_touch_range_accepts_adjacent_and_rejects_far() -> None:
    """Old case 2: ally targeting obeys exact five-foot reach."""
    reset_spell_regression_arena(14, 7)
    caster = _caster("Touch Caster", (2, 3), spell_slots={2: 2})
    ally = _caster("Adjacent Ally", (3, 3), spell_slots={})
    far_ally = _caster("Far Ally", (5, 3), spell_slots={})
    Entity.update_all_entities_senses(max_distance=60)

    adjacent = _cast_darkvision(caster, ally)
    assert not adjacent.canceled
    assert _has_sense(ally, SensesType.DARKVISION, range_feet=60)

    caster.action_economy.reset_all_costs()
    far = _cast_darkvision(caster, far_ally)
    assert far.canceled
    assert not has_condition(far_ally, "Darkvision")


def test_darkvision_concentration_replacement_removes_linked_ally_effect() -> None:
    """Old case 3: a new concentration slot replaces the linked sense grant."""
    reset_spell_regression_arena(14, 7)
    caster = _caster("Replacing Caster", (2, 3), spell_slots={2: 2})
    ally = _caster("Darkvision Ally", (3, 3), spell_slots={})
    Entity.update_all_entities_senses(max_distance=60)
    assert not _cast_darkvision(caster, ally).canceled

    caster.action_economy.reset_all_costs()
    replacement = Invisibility(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        cast_at_level=2,
    ).apply()

    assert isinstance(replacement, SpellEvent)
    assert not replacement.canceled
    assert not has_condition(ally, "Darkvision")
    assert not _has_sense(ally, SensesType.DARKVISION)
    concentration = caster.active_conditions.get("Concentrating")
    assert isinstance(concentration, Concentrating)
    assert concentration.spell_name == "Invisibility"


def test_see_invisibility_reveals_invisible_entity_without_concentration() -> None:
    """Old case 4: the self sense immediately restores invisible perception."""
    reset_spell_regression_arena(14, 7)
    caster = _caster("See Invisible Caster", (2, 3), spell_slots={2: 1})
    enemy = _enemy("Invisible Enemy", (5, 3))
    Entity.update_all_entities_senses(max_distance=60)
    enemy.add_condition(
        Invisible(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid)
    )
    assert enemy.uuid not in caster.senses.entities

    result = _cast_see_invisibility(caster)

    assert not result.canceled
    assert _has_sense(caster, SensesType.SEE_INVISIBLE, range_feet=0)
    assert enemy.uuid in caster.senses.entities
    assert not has_condition(caster, "Concentrating")
    effect = caster.active_conditions.get("See Invisibility")
    assert effect is not None
    assert effect.duration.duration_type is DurationType.ROUNDS
    assert effect.duration.duration == 10


def test_see_invisibility_ten_round_expiry_removes_sense_and_visibility() -> None:
    """Old case 5: duration cleanup reactively hides the invisible target."""
    reset_spell_regression_arena(14, 7)
    caster = _caster("Expiring Sight", (2, 3), spell_slots={2: 1})
    enemy = _enemy("Hidden Again", (5, 3))
    Entity.update_all_entities_senses(max_distance=60)
    enemy.add_condition(
        Invisible(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid)
    )
    assert not _cast_see_invisibility(caster).canceled

    for _ in range(9):
        caster.advance_duration("See Invisibility")
    assert has_condition(caster, "See Invisibility")
    assert enemy.uuid in caster.senses.entities

    caster.advance_duration("See Invisibility")
    assert not has_condition(caster, "See Invisibility")
    assert not _has_sense(caster, SensesType.SEE_INVISIBLE)
    assert enemy.uuid not in caster.senses.entities


def test_true_seeing_ally_grants_120_foot_truesight_without_concentration() -> None:
    """Old case 6: adjacent ally receives duration and invisible perception."""
    reset_spell_regression_arena(16, 7)
    caster = _caster("True Seeing Caster", (2, 3), spell_slots={6: 1})
    ally = _caster("True Seeing Ally", (3, 3), spell_slots={})
    enemy = _enemy("Invisible True Target", (7, 3))
    Entity.update_all_entities_senses(max_distance=80)
    enemy.add_condition(
        Invisible(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid)
    )
    assert enemy.uuid not in ally.senses.entities

    result = _cast_true_seeing(caster, ally)

    assert not result.canceled
    assert _has_sense(ally, SensesType.TRUESIGHT, range_feet=120)
    assert enemy.uuid in ally.senses.entities
    assert not has_condition(caster, "Concentrating")
    effect = ally.active_conditions.get("True Seeing")
    assert effect is not None
    assert effect.duration.duration_type is DurationType.ROUNDS
    assert effect.duration.duration == 10


def test_true_seeing_ten_round_expiry_removes_truesight() -> None:
    """Old case 7: the owned truesight mode expires at exactly ten rounds."""
    reset_spell_regression_arena(14, 7)
    caster = _caster("True Duration Caster", (2, 3), spell_slots={6: 1})
    ally = _caster("True Duration Ally", (3, 3), spell_slots={})
    Entity.update_all_entities_senses(max_distance=60)
    assert not _cast_true_seeing(caster, ally).canceled

    for _ in range(10):
        ally.advance_duration("True Seeing")

    assert not has_condition(ally, "True Seeing")
    assert not _has_sense(ally, SensesType.TRUESIGHT)


def test_true_seeing_rejects_target_beyond_touch_range() -> None:
    """Old case 8: a visible ally fifteen feet away is not a legal target."""
    reset_spell_regression_arena(14, 7)
    caster = _caster("True Range Caster", (2, 3), spell_slots={6: 1})
    ally = _caster("True Range Ally", (5, 3), spell_slots={})
    Entity.update_all_entities_senses(max_distance=60)

    result = _cast_true_seeing(caster, ally)

    assert result.canceled
    assert not has_condition(ally, "True Seeing")
    assert not _has_sense(ally, SensesType.TRUESIGHT)


def test_direct_darkvision_effect_removal_reverses_concentration_link() -> None:
    """Old case 9: removing the child closes its exact concentration owner."""
    reset_spell_regression_arena(14, 7)
    caster = _caster("Reverse Link Caster", (2, 3), spell_slots={2: 1})
    ally = _caster("Reverse Link Ally", (3, 3), spell_slots={})
    Entity.update_all_entities_senses(max_distance=60)
    assert not _cast_darkvision(caster, ally).canceled

    ally.remove_condition("Darkvision")

    assert not has_condition(ally, "Darkvision")
    assert not _has_sense(ally, SensesType.DARKVISION)
    assert not has_condition(caster, "Concentrating")


def test_multiple_nonconcentration_sense_buffs_clean_up_independently() -> None:
    """Old case 10: removing See Invisibility preserves True Seeing."""
    reset_spell_regression_arena(14, 7)
    caster = _caster("Multi Sense Caster", (2, 3), spell_slots={2: 1, 6: 1})
    Entity.update_all_entities_senses(max_distance=60)
    assert not _cast_see_invisibility(caster).canceled
    caster.action_economy.reset_all_costs()
    assert not _cast_true_seeing(caster, caster).canceled
    assert _has_sense(caster, SensesType.SEE_INVISIBLE)
    assert _has_sense(caster, SensesType.TRUESIGHT)

    caster.remove_condition("See Invisibility")

    assert not _has_sense(caster, SensesType.SEE_INVISIBLE)
    assert _has_sense(caster, SensesType.TRUESIGHT, range_feet=120)


def test_darkvision_reactively_reveals_dark_target_and_cleanup_hides_it() -> None:
    """Old case 11: dark-light resolution and entity visibility change in place."""
    _reset_dark_arena()
    caster = _caster("Dark Reactive Caster", (2, 3), spell_slots={2: 1})
    enemy = _enemy("Dark Reactive Enemy", (5, 3))
    Entity.update_all_entities_senses(max_distance=70)
    tile = get_map().get_tile(*enemy.position)
    assert tile is not None
    assert enemy.uuid not in caster.senses.entities
    assert (
        tile.get_effective_light_for(caster.uuid, caster.position)
        is LightLevel.DARKNESS
    )

    assert not _cast_darkvision(caster, caster).canceled
    assert enemy.uuid in caster.senses.entities
    assert (
        tile.get_effective_light_for(caster.uuid, caster.position)
        is LightLevel.DIM_LIGHT
    )

    _break_concentration(caster)
    assert enemy.uuid not in caster.senses.entities


def test_see_invisibility_emits_reactive_add_and_remove_deltas() -> None:
    """Old case 12: grant and expiry publish parented sensory replacements."""
    reset_spell_regression_arena(14, 7)
    caster = _caster("See Reactive Caster", (2, 3), spell_slots={2: 1})
    enemy = _enemy("See Reactive Enemy", (5, 3))
    Entity.update_all_entities_senses(max_distance=60)
    enemy.add_condition(
        Invisible(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid)
    )
    assert enemy.uuid not in caster.senses.entities

    assert not _cast_see_invisibility(caster).canceled
    additions = [
        event
        for event in _completed_sensory_updates(caster.uuid)
        if enemy.uuid in event.visible_entities_added and event.sense_modes_changed
    ]
    assert additions

    for _ in range(10):
        caster.advance_duration("See Invisibility")
    removals = [
        event
        for event in _completed_sensory_updates(caster.uuid)
        if enemy.uuid in event.visible_entities_removed and event.sense_modes_changed
    ]
    assert removals


def test_true_seeing_reactively_pierces_darkness_and_invisibility() -> None:
    """Old case 13: truesight handles both concealment sources as one grant."""
    _reset_dark_arena()
    caster = _caster("True Reactive Caster", (2, 3), spell_slots={6: 1})
    ally = _caster("True Reactive Ally", (3, 3), spell_slots={})
    enemy = _enemy("True Reactive Enemy", (6, 3))
    Entity.update_all_entities_senses(max_distance=70)
    enemy.add_condition(
        Invisible(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid)
    )
    assert enemy.uuid not in ally.senses.entities

    assert not _cast_true_seeing(caster, ally).canceled
    assert enemy.uuid in ally.senses.entities

    for _ in range(10):
        ally.advance_duration("True Seeing")
    assert enemy.uuid not in ally.senses.entities


def test_darkvision_on_ally_reactively_tracks_caster_concentration() -> None:
    """Old case 14: the linked ally, not only the caster, recomputes senses."""
    _reset_dark_arena()
    caster = _caster("Ally Reactive Caster", (2, 3), spell_slots={2: 1})
    ally = _caster("Ally Reactive Target", (3, 3), spell_slots={})
    enemy = _enemy("Ally Reactive Enemy", (6, 3))
    Entity.update_all_entities_senses(max_distance=70)
    assert enemy.uuid not in ally.senses.entities

    assert not _cast_darkvision(caster, ally).canceled
    assert enemy.uuid in ally.senses.entities

    _break_concentration(caster)
    assert not has_condition(ally, "Darkvision")
    assert enemy.uuid not in ally.senses.entities


def test_darkvision_controls_discovery_and_real_spell_execution_in_darkness() -> None:
    """Old case 15: visibility feeds action discovery and the execution route."""
    _reset_dark_arena()
    caster = _caster("Dark Attack Caster", (2, 3), spell_slots={2: 1})
    enemy = _enemy("Dark Attack Enemy", (5, 3))
    register_spell(caster, FireBolt, caster_level=5)
    Entity.update_all_entities_senses(max_distance=70)
    assert enemy.uuid not in caster.senses.entities
    assert all(
        enemy.uuid not in {target.target_uuid for target in row.valid_targets}
        for row in caster.get_available_actions().entity_actions
    )

    assert not _cast_darkvision(caster, caster).canceled
    caster.action_economy.reset_all_costs()
    target_index, available = _fire_bolt_target_index(caster, enemy)
    hp_before = get_hp(enemy)
    hit_modifier = force_attack_hit(caster)
    try:
        attack = execute_by_index(
            caster,
            "Fire Bolt",
            target_index,
            available=available,
        )
    finally:
        remove_attack_modifier(caster, hit_modifier)
    assert isinstance(attack, SpellEvent)
    assert not attack.canceled
    assert get_hp(enemy) < hp_before

    caster.action_economy.reset_all_costs()
    _break_concentration(caster)
    assert all(
        enemy.uuid not in {target.target_uuid for target in row.valid_targets}
        for row in caster.get_available_actions().entity_actions
    )


def test_see_invisibility_controls_discovery_and_real_spell_execution() -> None:
    """Old case 16: invisible targets enter and leave the executable action row."""
    reset_spell_regression_arena(14, 7)
    caster = _caster("See Attack Caster", (2, 3), spell_slots={2: 1})
    enemy = _enemy("See Attack Enemy", (5, 3))
    register_spell(caster, FireBolt, caster_level=5)
    Entity.update_all_entities_senses(max_distance=60)
    enemy.add_condition(
        Invisible(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid)
    )
    assert all(
        enemy.uuid not in {target.target_uuid for target in row.valid_targets}
        for row in caster.get_available_actions().entity_actions
    )

    assert not _cast_see_invisibility(caster).canceled
    caster.action_economy.reset_all_costs()
    target_index, available = _fire_bolt_target_index(caster, enemy)
    hit_modifier = force_attack_hit(caster)
    try:
        attack = execute_by_index(
            caster,
            "Fire Bolt",
            target_index,
            available=available,
        )
    finally:
        remove_attack_modifier(caster, hit_modifier)
    assert isinstance(attack, SpellEvent)
    assert not attack.canceled

    for _ in range(10):
        caster.advance_duration("See Invisibility")
    caster.action_economy.reset_all_costs()
    assert all(
        enemy.uuid not in {target.target_uuid for target in row.valid_targets}
        for row in caster.get_available_actions().entity_actions
    )
