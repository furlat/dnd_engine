"""Current-architecture parity for the archived Cleric Batch 1 matrix.

The old suite mixed stochastic retries, print-only checks, free spell costs,
and one obsolete named ``Incapacitated`` child assertion.  These tests retain
the rule behavior with legal slots, deterministic rolls, and the current
direct-ownership condition model.
"""

import pytest
from uuid import uuid4

from dnd.actions import (
    Move,
    MovementEvent,
    SpellEvent,
    entity_action_economy_cost_evaluator,
)
from dnd.actions_functional import get_available_actions, setup_standard_actions
from dnd.blocks.equipment import Weapon
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.conditions import Hidden
from dnd.core.base_actions import BaseAction, Cost
from dnd.core.base_block import LightLevel
from dnd.core.base_tiles import dark_floor_factory
from dnd.core.condition_types import ConditionAgencyDenial, DurationType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue, EventType, TakeDamageEvent
from dnd.core.gridmap import get_map
from dnd.core.spatial_effect_types import SpatialEffectAnchorKind
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.modifiers import (
    ResistanceModifier,
    ResistanceStatus,
)
from dnd.entity import Entity
from dnd.items.weapons import DAGGER_RECIPE
from dnd.items.environment_content import OIL_BARREL_RECIPE, OilBarrel
from dnd.reactions import add_opportunity_attack_handler
from dnd.spells.conjuration import (
    GuardianOfFaith,
    GuardianOfFaithController,
)
from dnd.spells.divination import Guidance
from dnd.spells.enchantment import Command
from dnd.spells.evocation import (
    ContinualFlame,
    FireBolt,
    FlameStrike,
    Light,
)
from dnd.spatial_effect_content import (
    CONTINUAL_FLAME_FIELD_RECIPE,
    GUARDIAN_OF_FAITH_FIELD_RECIPE,
)
from dnd.spatial_effects import FieldEffect, SpatialEffect
from dnd.spells.illusion import Silence
from dnd.spells.transmutation import HasteEffect
from tests.engine.support import (
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


def _dark_arena(width: int = 24, height: int = 15) -> None:
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


def _tile(position: tuple[int, int]):
    grid = get_map()
    tile = grid.get_tile(*position)
    assert tile is not None
    return tile


def test_flame_strike_aoe_save_and_damage_types() -> None:
    """Old cases 1-2: in-area targets take full/half; outsiders are untouched."""
    reset_spell_regression_arena(20, 15)
    caster = create_spell_regression_actor(
        "Flame Strike Cleric",
        (2, 7),
        "heroes",
        spell_slots={5: 1},
    )
    failed = create_spell_regression_actor(
        "Failed Save",
        (8, 7),
        "monsters",
    )
    passed = create_spell_regression_actor(
        "Passed Save",
        (9, 7),
        "monsters",
    )
    bystander = create_spell_regression_actor(
        "Bystander",
        (16, 12),
        "monsters",
    )
    force_save_result(failed, "dexterity", succeeds=False)
    force_save_result(passed, "dexterity", succeeds=True)
    Entity.update_all_entities_senses(max_distance=120)
    hp_before = {
        failed.uuid: get_hp(failed),
        passed.uuid: get_hp(passed),
        bystander.uuid: get_hp(bystander),
    }

    with fixed_dice_faces(
        10,
        *([4] * 8),
        10,
        *([4] * 8),
    ):
        result = FlameStrike(
            source_entity_uuid=caster.uuid,
            end_position=(8, 7),
            cast_at_level=5,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    failed_damage = hp_before[failed.uuid] - get_hp(failed)
    passed_damage = hp_before[passed.uuid] - get_hp(passed)
    assert failed_damage > 0
    assert passed_damage == failed_damage // 2
    assert get_hp(bystander) == hp_before[bystander.uuid]
    assert result.total_targets == 2


def test_flame_strike_upcast_metadata() -> None:
    """Old case 3: seventh-level Flame Strike adds two fire dice."""
    spell = FlameStrike(
        source_entity_uuid=uuid4(),
        cast_at_level=7,
    )

    assert spell.spell_level == 5
    assert spell.get_upcast_bonus() == 2
    assert spell.base_fire_dice + spell.get_upcast_bonus() == 6
    assert spell.radiant_dice == 4


def test_flame_strike_applies_fire_and_radiant_as_typed_components() -> None:
    """Fire immunity removes only the fire half of the mixed damage packet."""
    reset_spell_regression_arena(14, 9)
    caster = create_spell_regression_actor(
        "Typed Flame Strike Cleric",
        (2, 4),
        "heroes",
        spell_slots={5: 1},
    )
    target = create_spell_regression_actor(
        "Fire Immune Target",
        (7, 4),
        "monsters",
    )
    target.health.damage_reduction.self_static.add_resistance_modifier(
        ResistanceModifier(
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
            name="Flame Strike fire immunity",
            value=ResistanceStatus.IMMUNITY,
            damage_type=DamageType.FIRE,
        )
    )
    force_save_result(target, "dexterity", succeeds=False)
    Entity.update_all_entities_senses(max_distance=80)
    hp_before = get_hp(target)

    with fixed_dice_faces(10, *([2] * 4), *([3] * 4)):
        result = FlameStrike(
            source_entity_uuid=caster.uuid,
            end_position=target.position,
            cast_at_level=5,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert hp_before - get_hp(target) == 12
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
        (DamageType.FIRE, 8),
        (DamageType.RADIANT, 12),
    ]


def test_guidance_concentration_break_removes_unused_effect() -> None:
    """Old case 6; old cases 4-5 are covered by EB-15-016."""
    reset_spell_regression_arena(8, 5)
    caster = create_spell_regression_actor("Guidance Cleric", (2, 2), "heroes")
    Entity.update_all_entities_senses(max_distance=40)

    result = Guidance(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert has_condition(caster, "Guidance")
    assert has_condition(caster, "Concentrating")
    caster.remove_condition("Concentrating")
    assert not has_condition(caster, "Guidance")


def test_light_geometry_follows_movement_and_cleans_up() -> None:
    """Old cases 7-9: anchored light has exact bright/dim bounds and cleanup."""
    _dark_arena()
    caster = create_spell_regression_actor("Light Cleric", (5, 7), "heroes")
    Entity.update_all_entities_senses(max_distance=100)

    result = Light(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert not has_condition(caster, "Concentrating")
    light_effect = caster.active_conditions["Light"]
    assert light_effect.duration.duration_type is DurationType.ROUNDS
    assert light_effect.duration.duration == 600
    assert _tile((5, 7)).resolved_light_level is LightLevel.BRIGHT_LIGHT
    assert _tile((7, 7)).resolved_light_level is LightLevel.BRIGHT_LIGHT
    assert _tile((11, 7)).resolved_light_level is LightLevel.DIM_LIGHT
    assert _tile((15, 7)).resolved_light_level is LightLevel.DARKNESS

    caster.update_entity_senses(max_distance=100)
    moved = Move(
        source_entity_uuid=caster.uuid,
        end_position=(8, 7),
    ).apply()
    assert moved is not None
    assert not moved.canceled
    assert caster.position == (8, 7)
    assert _tile((8, 7)).resolved_light_level is LightLevel.BRIGHT_LIGHT
    assert _tile((18, 7)).resolved_light_level is LightLevel.DARKNESS

    caster.remove_condition("Light")
    assert not has_condition(caster, "Light")
    assert _tile((8, 7)).resolved_light_level is LightLevel.DARKNESS


def test_light_reactively_reveals_a_low_stealth_target() -> None:
    """Old case 10, strengthened: visibility changes without a manual refresh."""
    _dark_arena()
    caster = create_spell_regression_actor("Light Observer", (5, 7), "heroes")
    target = create_spell_regression_actor("Hidden Target", (8, 7), "monsters")
    Entity.update_all_entities_senses(max_distance=100)
    target.add_condition(
        Hidden(
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
            stealth_result=1,
        )
    )
    assert target.uuid not in caster.senses.entities

    result = Light(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert _tile(target.position).resolved_light_level is LightLevel.BRIGHT_LIGHT
    assert target.uuid in caster.senses.entities


def test_light_on_ally_moves_with_the_ally() -> None:
    """Old case 11: the target, not the caster, anchors the light source."""
    _dark_arena()
    caster = create_spell_regression_actor("Light Cleric", (4, 7), "heroes")
    ally = create_spell_regression_actor("Light Ally", (5, 7), "heroes")
    Entity.update_all_entities_senses(max_distance=100)

    result = Light(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert has_condition(ally, "Light")
    assert not has_condition(caster, "Concentrating")
    ally.update_entity_senses(max_distance=100)
    moved = Move(
        source_entity_uuid=ally.uuid,
        end_position=(8, 7),
    ).apply()
    assert moved is not None
    assert not moved.canceled
    assert ally.position == (8, 7)
    assert _tile(ally.position).resolved_light_level is LightLevel.BRIGHT_LIGHT


def test_continual_flame_effect_owns_light_lifecycle() -> None:
    """Old cases 12-13: the permanent field emits and removes its own light."""
    _dark_arena()
    caster = create_spell_regression_actor(
        "Flame Cleric",
        (2, 7),
        "heroes",
        spell_slots={2: 1},
    )
    Entity.update_all_entities_senses(max_distance=100)
    focus = materialize_item(
        OIL_BARREL_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=OilBarrel,
    )
    focus.place_on_grid((3, 7))
    Entity.update_all_entities_senses(max_distance=100)

    result = ContinualFlame(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=focus.uuid,
        cast_at_level=2,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert not has_condition(caster, "Concentrating")
    flame = next(
        effect
        for effect in SpatialEffect.active_effects()
        if effect.content_ref == CONTINUAL_FLAME_FIELD_RECIPE.ref
    )
    assert isinstance(flame, FieldEffect)
    assert flame.anchor_kind is SpatialEffectAnchorKind.WORLD_OBJECT
    assert flame.anchor_uuid == focus.uuid
    assert flame.affected_positions == {(3, 7)}
    assert get_map().get_objects_at((3, 7)) == {focus.uuid}
    assert _tile((3, 7)).resolved_light_level is LightLevel.BRIGHT_LIGHT
    assert _tile((5, 7)).resolved_light_level in {
        LightLevel.BRIGHT_LIGHT,
        LightLevel.DIM_LIGHT,
    }

    focus.place_on_grid((12, 7))

    assert flame.affected_positions == {(12, 7)}
    assert _tile((12, 7)).resolved_light_level is LightLevel.BRIGHT_LIGHT
    assert _tile((3, 7)).resolved_light_level is LightLevel.DARKNESS

    get_map().remove_object(focus.uuid)

    assert SpatialEffect.get_effect(flame.uuid) is None
    assert _tile((12, 7)).resolved_light_level is LightLevel.DARKNESS


def _command_reaction_probe(target: Entity) -> BaseAction:
    """Build a pure reaction whose resource channel remains authoritative."""
    return BaseAction(
        name="Command Reaction Probe",
        source_entity_uuid=target.uuid,
        costs=[
            Cost(
                name="Command Reaction Cost",
                cost_type="reactions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ],
        use_register=False,
    )


def _command_zero_cost_probe(target: Entity) -> BaseAction:
    """Build a zero-cost action that the neutral permission gate must close."""
    return BaseAction(
        name="Command Zero-Cost Probe",
        source_entity_uuid=target.uuid,
        costs=[],
        use_register=False,
    )


def _cast_failed_command(
    caster: Entity,
    target: Entity,
    command_word: str,
) -> SpellEvent:
    """Cast one deterministic failed-save Command branch."""
    with fixed_dice_faces(10):
        result = Command(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            command_word=command_word,
            cast_at_level=1,
        ).apply()
    assert isinstance(result, SpellEvent)
    assert not result.canceled
    return result


@pytest.mark.parametrize(
    ("command_word", "condition_name"),
    (
        ("grovel", "Command: Grovel"),
        ("halt", "Command: Halt"),
        ("flee", "Command: Flee"),
    ),
)
def test_command_branches_spend_exactly_the_targets_next_turn(
    command_word: str,
    condition_name: str,
) -> None:
    """Old cases 14-16: each branch activates next turn and expires after it."""
    reset_spell_regression_arena(16, 7)
    caster = create_spell_regression_actor(
        "Command Cleric",
        (2, 3),
        "heroes",
        spell_slots={1: 1},
    )
    target = create_spell_regression_actor("Command Target", (5, 3), "monsters")
    setup_standard_actions(target)
    force_save_result(target, "wisdom", succeeds=False)
    Entity.update_all_entities_senses(max_distance=100)
    original_position = target.position

    _cast_failed_command(caster, target, command_word)

    assert has_condition(target, condition_name)
    assert not has_condition(caster, "Concentrating")
    active = target.active_conditions[condition_name]
    assert active.agency_denial is ConditionAgencyDenial.FULL_TURN
    assert not has_condition(target, "Prone")
    assert target.action_economy.action_permission.normalized_score == 1
    assert _command_zero_cost_probe(target).check_costs()

    # A TURN_END before the commanded turn must not consume the pending effect.
    target.on_turn_end(round_number=0, turn_index=0)
    assert has_condition(target, condition_name)

    target.on_turn_start(round_number=1, turn_index=0)

    assert has_condition(target, condition_name)
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.actions.normalized_score == 0
    assert target.action_economy.bonus_actions.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0
    assert target.action_economy.reactions.normalized_score == 1
    assert not _command_zero_cost_probe(target).check_costs()
    assert _command_reaction_probe(target).check_costs()
    if command_word == "grovel":
        assert has_condition(target, "Prone")
    elif command_word == "flee":
        assert target.position != original_position
        assert any(
            event.source_entity_uuid == target.uuid
            and event.phase is EventPhase.COMPLETION
            and not event.canceled
            for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        )

    target.on_turn_end(round_number=1, turn_index=0)

    assert not has_condition(target, condition_name)
    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.bonus_actions.normalized_score == 1
    assert target.action_economy.reactions.normalized_score == 1
    if command_word == "grovel":
        assert target.action_economy.movement.normalized_score == 30
        assert has_condition(target, "Prone")
        target.on_turn_start(round_number=2, turn_index=0)
        assert not has_condition(target, "Prone")
        assert target.action_economy.movement.normalized_score == 15
    elif command_word == "flee":
        assert target.action_economy.movement.normalized_score == 0
        target.on_turn_start(round_number=2, turn_index=0)
        assert target.action_economy.movement.normalized_score == 30
    else:
        assert target.action_economy.movement.normalized_score == 30


def test_command_flee_uses_voluntary_movement_and_provokes_reactions() -> None:
    """Flee goes through Move/StepMovement, including opportunity attacks."""
    reset_spell_regression_arena(16, 9)
    caster = create_spell_regression_actor(
        "Command Cleric",
        (2, 4),
        "heroes",
        spell_slots={1: 1},
    )
    watcher = create_spell_regression_actor(
        "Flee Watcher",
        (5, 5),
        "heroes",
    )
    target = create_spell_regression_actor(
        "Flee Target",
        (5, 4),
        "monsters",
    )
    watcher.equipment.equip(
        materialize_item(
            DAGGER_RECIPE,
            watcher.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_MAIN,
    )
    add_opportunity_attack_handler(watcher)
    force_save_result(target, "wisdom", succeeds=False)
    Entity.update_all_entities_senses(max_distance=100)
    target.action_economy.consume(
        "movement",
        25,
        cost_name="Prior turn movement",
    )
    target.update_entity_senses(max_distance=20, path_max_distance=1)
    assert max(len(path) for path in target.senses.paths.values()) <= 2
    reaction_before = watcher.action_economy.reactions.normalized_score
    hit_modifier = force_attack_hit(watcher)

    try:
        _cast_failed_command(caster, target, "flee")
        target.on_turn_start(round_number=1, turn_index=0)
    finally:
        remove_attack_modifier(watcher, hit_modifier)

    assert target.position != (5, 4)
    assert watcher.action_economy.reactions.normalized_score == reaction_before - 1
    assert any(
        event.name == "Opportunity Attack"
        for event in EventQueue.get_events_by_type(EventType.ATTACK)
    )
    flee_completions = [
        event
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        if (
            isinstance(event, MovementEvent)
            and event.source_entity_uuid == target.uuid
            and event.phase is EventPhase.COMPLETION
            and not event.canceled
        )
    ]
    assert flee_completions
    assert len(flee_completions[-1].path or []) == 7
    assert has_condition(target, "Command: Flee")
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.reactions.normalized_score == 1


def test_command_halt_closes_haste_and_zero_cost_paths_but_not_reactions() -> None:
    """The turn-spent gate covers restricted actions without incapacitation."""
    reset_spell_regression_arena(16, 7)
    caster = create_spell_regression_actor(
        "Command Cleric",
        (2, 3),
        "heroes",
        spell_slots={1: 1},
    )
    target = create_spell_regression_actor(
        "Hasted Command Target",
        (5, 3),
        "monsters",
    )
    target.equipment.equip(
        materialize_item(
            DAGGER_RECIPE,
            target.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_MAIN,
    )
    setup_standard_actions(target)
    target.add_condition(
        HasteEffect(
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=target.uuid,
            apply_lethargy=False,
        )
    )
    force_save_result(target, "wisdom", succeeds=False)
    Entity.update_all_entities_senses(max_distance=100)

    before = get_available_actions(target)
    haste_rows_before = [
        row
        for row in before.all_actions
        if row.template_name.endswith("__grant_haste")
    ]
    assert haste_rows_before
    assert any(row.can_afford for row in haste_rows_before)

    _cast_failed_command(caster, target, "halt")
    target.on_turn_start(round_number=1, turn_index=0)

    during = get_available_actions(target)
    haste_rows_during = [
        row
        for row in during.all_actions
        if row.template_name.endswith("__grant_haste")
    ]
    assert haste_rows_during
    assert all(not row.can_afford for row in haste_rows_during)
    assert _command_reaction_probe(target).check_costs()
    assert not _command_zero_cost_probe(target).check_costs()

    target.on_turn_end(round_number=1, turn_index=0)

    after = get_available_actions(target)
    haste_rows_after = [
        row
        for row in after.all_actions
        if row.template_name.endswith("__grant_haste")
    ]
    assert any(row.can_afford for row in haste_rows_after)


def test_command_successful_save_and_undead_immunity() -> None:
    """Old cases 17-18: save success and creature immunity apply no branch."""
    reset_spell_regression_arena(16, 7)
    caster = create_spell_regression_actor(
        "Command Cleric",
        (2, 3),
        "heroes",
        spell_slots={1: 2},
    )
    wise = create_spell_regression_actor("Wise Target", (5, 3), "monsters")
    undead = create_spell_regression_actor(
        "Undead Target",
        (6, 3),
        "monsters",
        creature_type=CreatureType.UNDEAD,
    )
    force_save_result(wise, "wisdom", succeeds=True)
    Entity.update_all_entities_senses(max_distance=100)

    with fixed_dice_faces(10):
        resisted = Command(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=wise.uuid,
            command_word="grovel",
            cast_at_level=1,
        ).apply()
    caster.action_economy.reset_all_costs()
    immune = Command(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=undead.uuid,
        command_word="grovel",
        cast_at_level=1,
    ).apply()

    assert isinstance(resisted, SpellEvent)
    assert not resisted.canceled
    assert not has_condition(wise, "Command: Grovel")
    assert not has_condition(wise, "Prone")
    assert isinstance(immune, SpellEvent)
    assert immune.canceled
    assert not has_condition(undead, "Command: Grovel")
    assert not has_condition(undead, "Prone")


def test_command_is_not_concentration() -> None:
    """Old case 19: Command never creates a concentration owner."""
    spell = Command(source_entity_uuid=uuid4())

    assert spell.concentration is False


def test_silence_zone_deafens_blocks_verbal_and_cleans_up() -> None:
    """Old cases 20-23: one zone owns sound denial and all cleanup."""
    reset_spell_regression_arena(24, 15)
    caster = create_spell_regression_actor(
        "Silence Cleric",
        (2, 7),
        "heroes",
        spell_slots={2: 1},
    )
    enemy = create_spell_regression_actor(
        "Silenced Caster",
        (10, 7),
        "monsters",
    )
    Entity.update_all_entities_senses(max_distance=120)

    silence = Silence(
        source_entity_uuid=caster.uuid,
        end_position=enemy.position,
        cast_at_level=2,
    ).apply()

    assert isinstance(silence, SpellEvent)
    assert not silence.canceled
    assert has_condition(caster, "Concentrating")
    assert has_condition(enemy, "Silence Deafened")
    assert has_condition(enemy, "Deafened")

    verbal = FireBolt(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=caster.uuid,
        verbal=True,
    ).apply()
    assert isinstance(verbal, SpellEvent)
    assert verbal.canceled

    enemy.action_economy.reset_all_costs()
    with fixed_dice_faces(10, 4, 20):
        nonverbal = FireBolt(
            source_entity_uuid=enemy.uuid,
            target_entity_uuid=caster.uuid,
            verbal=False,
        ).apply()
    assert isinstance(nonverbal, SpellEvent)
    assert not nonverbal.canceled

    caster.remove_condition("Concentrating")
    assert not has_condition(enemy, "Silence Deafened")
    assert not has_condition(enemy, "Deafened")


def test_guardian_placement_ward_and_damage_budget() -> None:
    """Old cases 24-27: placement, once-per-turn ward, and budget are causal."""
    reset_spell_regression_arena(24, 15)
    caster = create_spell_regression_actor(
        "Guardian Cleric",
        (2, 7),
        "heroes",
        spell_slots={4: 1},
    )
    Entity.update_all_entities_senses(max_distance=120)
    grid = get_map()

    result = GuardianOfFaith(
        source_entity_uuid=caster.uuid,
        end_position=(10, 7),
        cast_at_level=4,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert not has_condition(caster, "Concentrating")
    guardian = next(
        effect
        for effect in SpatialEffect.active_effects()
        if effect.content_ref == GUARDIAN_OF_FAITH_FIELD_RECIPE.ref
    )
    assert not grid.is_walkable_for(10, 7, caster.uuid)
    controller = guardian.active_conditions.get("Guardian of Faith")
    assert isinstance(controller, GuardianOfFaithController)
    assert controller.damage_budget == 60
    assert controller.damage_dealt == 0

    turn_execution_id = uuid4()
    turn_event = EventQueue.publish_lifecycle(Event(
        source_entity_uuid=caster.uuid,
        event_type=EventType.TURN_START,
        phase=EventPhase.DECLARATION,
        use_register=False,
        turn_execution_id=turn_execution_id,
    ))
    assert turn_event is not None

    first = create_spell_regression_actor("First Fodder", (18, 7), "monsters")
    force_save_result(first, "dexterity", succeeds=False)
    first_hp = get_hp(first)
    with fixed_dice_faces(10):
        Entity.update_entity_position(
            first,
            (12, 7),
            parent_event=turn_event.uuid,
        )
    assert get_hp(first) == first_hp - 20
    hp_after_first = get_hp(first)
    Entity.update_entity_position(
        first,
        (11, 7),
        parent_event=turn_event.uuid,
    )
    assert get_hp(first) == hp_after_first

    for index, destination in enumerate(((10, 5), (10, 9)), start=2):
        fodder = create_spell_regression_actor(
            f"Fodder {index}",
            (18, index),
            "monsters",
        )
        force_save_result(fodder, "dexterity", succeeds=False)
        with fixed_dice_faces(10):
            Entity.update_entity_position(
                fodder,
                destination,
                parent_event=turn_event.uuid,
            )

    assert controller.damage_dealt == 60
    assert SpatialEffect.get_effect(guardian.uuid) is None
    assert grid.is_walkable_for(10, 7, caster.uuid)
