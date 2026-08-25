"""Deterministic coverage for spell cases displaced by the d80 test rework.

These spells remained implemented, but their archived execution matrices had
no direct maintained replacement.  The tests below exercise the current public
action/condition surfaces with legal resources and deterministic outcomes.
"""

from uuid import UUID

from dnd.actions.standard import (
    Attack,
    Jump,
    SpellEvent,
)
from dnd.actions.operations import (
    execute_by_index,
    get_available_actions,
    register_spell,
    setup_standard_actions,
)
from dnd.blocks.equipment import (
    BodyArmor,
    Weapon,
)
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.base_actions import (
    TargetType,
)
from dnd.types.conditions import DurationType
from dnd.types.rolls import AttackOutcome
from dnd.core.dice import fixed_dice_faces
from dnd.types.equipment import WeaponSlot
from dnd.core.gridmap import get_map
from dnd.types.creatures import CreatureType
from dnd.types.damage import DamageType
from dnd.types.rolls import AdvantageStatus, AutoHitStatus
from dnd.core.modifiers import AutoHitModifier, NumericalModifier
from dnd.entities.entity import Entity
from dnd.items.armors import CHAIN_MAIL_RECIPE
from dnd.items.weapons import DAGGER_RECIPE
from dnd.spells.conjuration import (
    AcidSplash,
    CallLightning,
    CallLightningStrike,
)
from dnd.types.materials import Material, TileSurface
from dnd.spells.enchantment import PowerWordStun, TestBless as AllyFilterSpell
from dnd.spells.evocation import (
    BurningHands,
    Fireball,
    GuidingBolt,
    LightningBolt,
    MagicMissile,
    RayOfFrost,
    ScorchingRay,
    ShockingGrasp,
    Sunbeam,
    SunbeamStrike,
    Thunderwave,
)
from dnd.spells.illusion import Blur, Fear, HypnoticPattern, Invisibility
from dnd.spells.necromancy import BlindnessDeafness, NecroticBless
from dnd.spells.transmutation import ExpeditiousRetreat, JumpSpell
from tests.engine.support import get_hp, has_condition, set_hp
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    force_save_result,
    reset_spell_regression_arena,
)


def _force_spell_attack_hit(caster: Entity, target: Entity) -> UUID:
    """Add one scoped auto-hit modifier and return its UUID for cleanup."""
    modifier = AutoHitModifier(
        name="Remaining spell matrix auto-hit",
        value=AutoHitStatus.AUTOHIT,
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    )
    return caster.spellcasting.spell_attack_bonus.self_static.add_auto_hit_modifier(
        modifier
    )


def _remove_spell_attack_modifier(caster: Entity, modifier_uuid: UUID) -> None:
    caster.spellcasting.spell_attack_bonus.self_static.remove_modifier(
        modifier_uuid
    )


def _action_names(entity: Entity) -> set[str]:
    return {
        action.template_name
        for action in entity.get_available_actions().all_actions
    }


def test_call_lightning_grants_repeatable_strike_and_cleans_on_replacement() -> None:
    """Initial/repeat damage share concentration and one owned action marker."""
    reset_spell_regression_arena(24, 12)
    caster = create_spell_regression_actor(
        "Call Lightning Caster",
        (2, 5),
        "heroes",
        spell_slots={1: 1, 3: 1},
    )
    target = create_spell_regression_actor(
        "Call Lightning Target",
        (7, 5),
        "monsters",
    )
    force_save_result(target, "dexterity", succeeds=False)
    Entity.materialize_all_navigation(max_distance=120)
    hp_before = get_hp(target)

    with fixed_dice_faces(10, 4, 4, 4):
        result = CallLightning(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=3,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert get_hp(target) < hp_before
    assert has_condition(caster, "Concentrating")
    strike_template = caster.get_action_template("Call Lightning Strike")
    assert isinstance(strike_template, CallLightningStrike)

    caster.action_economy.reset_all_costs()
    assert "Call Lightning Strike" in _action_names(caster)
    hp_after_cast = get_hp(target)
    with fixed_dice_faces(10, 3, 3, 3):
        strike = strike_template.instantiate(
            target_entity_uuid=target.uuid
        ).apply()

    assert strike is not None
    assert not strike.canceled
    assert get_hp(target) < hp_after_cast
    assert caster.action_economy.actions.normalized_score == 0

    caster.action_economy.reset_all_costs()
    independent_jump = JumpSpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        cast_at_level=1,
    ).apply()

    assert independent_jump is not None
    assert not independent_jump.canceled
    assert isinstance(
        caster.get_action_template("Call Lightning Strike"),
        CallLightningStrike,
    )
    assert has_condition(caster, "Jump")
    assert has_condition(caster, "Concentrating")
    jump_effect = caster.active_conditions["Jump"]
    assert jump_effect.duration.duration_type is DurationType.ROUNDS
    assert jump_effect.duration.duration == 10
    caster.action_economy.reset_all_costs()
    hp_before_second_strike = get_hp(target)
    retained_strike = CallLightningStrike(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        spell_dc=strike_template.spell_dc,
        damage_dice_count=strike_template.damage_dice_count,
    ).apply()
    assert retained_strike is not None
    assert not retained_strike.canceled
    assert get_hp(target) < hp_before_second_strike


def test_shocking_grasp_damage_scaling_metal_advantage_and_reaction_lifecycle() -> None:
    """A metal-armored hit uses advantage and suppresses one target turn."""
    reset_spell_regression_arena(12, 8)
    caster = create_spell_regression_actor(
        "Shocking Grasp Caster",
        (2, 3),
        "heroes",
    )
    target = create_spell_regression_actor(
        "Metal Target",
        (3, 3),
        "monsters",
    )
    target.equipment.equip(
        materialize_item(
            CHAIN_MAIL_RECIPE,
            target.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=BodyArmor,
        ),
    )
    Entity.materialize_all_navigation(max_distance=60)
    hp_before = get_hp(target)
    hit_modifier = _force_spell_attack_hit(caster, target)

    with fixed_dice_faces(10, 10, 4, 4):
        result = ShockingGrasp(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_level=5,
        ).apply()
    _remove_spell_attack_modifier(caster, hit_modifier)

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert result.attack_outcome is AttackOutcome.HIT
    assert result.attack_bonus is not None
    assert result.attack_bonus.advantage is AdvantageStatus.ADVANTAGE
    assert result.damage_rolls is not None
    assert result.damages is not None
    assert result.damage_rolls[0].effective_dice_count == 2
    assert result.damages[0].damage_type is DamageType.LIGHTNING
    assert get_hp(target) < hp_before
    assert has_condition(target, "No Reactions")
    assert target.action_economy.reactions.normalized_score == 0

    target.on_turn_start()

    assert not has_condition(target, "No Reactions")
    assert target.action_economy.reactions.normalized_score == 1

    distant = create_spell_regression_actor(
        "Distant Grasp Target",
        (5, 3),
        "monsters",
    )
    Entity.materialize_all_navigation(max_distance=60)
    caster.action_economy.reset_all_costs()
    out_of_range = ShockingGrasp(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=distant.uuid,
        caster_level=17,
    )
    canceled = out_of_range.apply()

    assert out_of_range._get_cantrip_dice_count(17) == 4
    assert canceled is not None
    assert canceled.canceled
    assert canceled.status_message is not None
    assert "range" in canceled.status_message.lower()


def test_guiding_bolt_hit_upcast_mark_and_first_attack_cleanup() -> None:
    """The actual spell applies its advantage mark and the next attack owns cleanup."""
    reset_spell_regression_arena(18, 9)
    caster = create_spell_regression_actor(
        "Guiding Bolt Caster",
        (2, 4),
        "heroes",
        spell_slots={3: 1},
    )
    target = create_spell_regression_actor(
        "Guiding Bolt Target",
        (7, 4),
        "monsters",
    )
    attacker = create_spell_regression_actor(
        "Mark Consumer",
        (8, 4),
        "heroes",
    )
    attacker.equipment.equip(
        materialize_item(
            DAGGER_RECIPE,
            attacker.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_MAIN,
    )
    setup_standard_actions(attacker)
    Entity.materialize_all_navigation(max_distance=100)
    hit_modifier = _force_spell_attack_hit(caster, target)

    with fixed_dice_faces(10, *([3] * 6)):
        result = GuidingBolt(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=3,
            caster_level=5,
        ).apply()
    _remove_spell_attack_modifier(caster, hit_modifier)

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert result.damage_rolls is not None
    assert result.damage_rolls[0].effective_dice_count == 6
    assert has_condition(target, "Guiding Bolt")
    mark_modifiers = (
        target.equipment.ac_bonus.to_target_static.advantage_modifiers.values()
    )
    assert any(modifier.name == "Guiding Bolt" for modifier in mark_modifiers)

    attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()

    assert attack is not None
    assert not has_condition(target, "Guiding Bolt")


def test_guiding_bolt_actual_cast_expires_at_end_of_casters_next_turn() -> None:
    """A mark not consumed by an attack survives only through the next turn."""
    reset_spell_regression_arena(18, 8)
    caster = create_spell_regression_actor(
        "Guiding Bolt Duration Caster",
        (2, 3),
        "heroes",
        spell_slots={1: 1},
    )
    target = create_spell_regression_actor(
        "Guiding Bolt Duration Target",
        (7, 3),
        "monsters",
    )
    Entity.materialize_all_navigation(max_distance=90)
    hit_modifier = _force_spell_attack_hit(caster, target)

    with fixed_dice_faces(10, 3, 3, 3, 3):
        result = GuidingBolt(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=1,
        ).apply()
    _remove_spell_attack_modifier(caster, hit_modifier)

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert has_condition(target, "Guiding Bolt")
    assert (
        target.get_event_handler_by_name(
            f"Guiding Bolt Caster Turn Expiry ({target.uuid})"
        )
        is not None
    )

    caster.on_turn_end()

    assert has_condition(target, "Guiding Bolt")

    caster.on_turn_start()
    caster.on_turn_end()

    assert not has_condition(target, "Guiding Bolt")
    assert (
        target.get_event_handler_by_name(
            f"Guiding Bolt Caster Turn Expiry ({target.uuid})"
        )
        is None
    )


def test_power_word_stun_threshold_range_and_repeat_save_cleanup() -> None:
    """The inclusive HP threshold stuns; a deterministic end-turn save cleans."""
    reset_spell_regression_arena(20, 8)
    caster = create_spell_regression_actor(
        "Power Word Caster",
        (1, 3),
        "heroes",
        spell_slots={8: 3},
    )
    threshold_target = create_spell_regression_actor(
        "Threshold Target",
        (5, 3),
        "monsters",
    )
    set_hp(threshold_target, 150)
    force_save_result(threshold_target, "constitution", succeeds=True)
    Entity.materialize_all_navigation(max_distance=100)

    result = PowerWordStun(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=threshold_target.uuid,
        cast_at_level=8,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert has_condition(threshold_target, "Power Word Stun")
    assert has_condition(threshold_target, "Stunned")

    threshold_target.on_turn_end(round_number=1, turn_index=0)

    assert not has_condition(threshold_target, "Power Word Stun")
    assert not has_condition(threshold_target, "Stunned")

    caster.action_economy.reset_all_costs()
    above_target = create_spell_regression_actor(
        "Above Threshold Target",
        (6, 3),
        "monsters",
    )
    set_hp(above_target, 151)
    Entity.materialize_all_navigation(max_distance=100)
    unaffected = PowerWordStun(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=above_target.uuid,
        cast_at_level=8,
    ).apply()

    assert isinstance(unaffected, SpellEvent)
    assert not unaffected.canceled
    assert not has_condition(above_target, "Power Word Stun")
    assert unaffected.status_message is not None
    assert "no effect" in unaffected.status_message.lower()

    caster.action_economy.reset_all_costs()
    distant = create_spell_regression_actor(
        "Distant Power Word Target",
        (14, 3),
        "monsters",
    )
    set_hp(distant, 100)
    Entity.materialize_all_navigation(max_distance=100)
    out_of_range = PowerWordStun(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=distant.uuid,
        cast_at_level=8,
    ).apply()

    assert out_of_range is not None
    assert out_of_range.canceled
    assert out_of_range.status_message is not None
    assert "range" in out_of_range.status_message.lower()


def test_expeditious_retreat_grant_cost_discovery_and_concentration_cleanup() -> None:
    """The granted Dash uses a bonus action and is owned by concentration."""
    reset_spell_regression_arena(14, 9)
    caster = create_spell_regression_actor(
        "Retreat Caster",
        (3, 4),
        "heroes",
        spell_slots={1: 1, 2: 1},
    )
    Entity.materialize_all_navigation(max_distance=70)
    spell = ExpeditiousRetreat(
        source_entity_uuid=caster.uuid,
        cast_at_level=1,
    )

    assert spell.target_type is TargetType.SELF
    assert "Dash (Bonus)" not in _action_names(caster)
    result = spell.apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert has_condition(caster, "Concentrating")
    assert has_condition(caster, "Expeditious Retreat")
    assert "Dash (Bonus)" in _action_names(caster)

    caster.action_economy.reset_all_costs()
    actions_before = caster.action_economy.actions.normalized_score
    bonus_before = caster.action_economy.bonus_actions.normalized_score
    dash = execute_by_index(caster, "Dash (Bonus)", 0)

    assert dash is not None
    assert not dash.canceled
    assert has_condition(caster, "Dashing")
    assert caster.action_economy.actions.normalized_score == actions_before
    assert caster.action_economy.bonus_actions.normalized_score == bonus_before - 1

    caster.action_economy.reset_all_costs()
    replacement = Invisibility(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        cast_at_level=2,
    ).apply()

    assert replacement is not None
    assert not replacement.canceled
    assert not has_condition(caster, "Expeditious Retreat")
    assert caster.get_action_template("Dash (Bonus)") is None


def test_jump_spell_composes_modifiers_targets_ally_and_expands_discovery() -> None:
    """Flat jump bonuses compose before the spell multiplier and then clean."""
    reset_spell_regression_arena(24, 16)
    caster = create_spell_regression_actor(
        "Jump Spell Caster",
        (7, 7),
        "heroes",
        spell_slots={1: 1},
    )
    ally = create_spell_regression_actor(
        "Jump Spell Ally",
        (8, 7),
        "heroes",
        strength=10,
    )
    setup_standard_actions(ally)
    additive_uuid = ally.jump_distance_additive.self_static.add_value_modifier(
        NumericalModifier(
            name="Jump spell matrix boots",
            value=10,
            source_entity_uuid=ally.uuid,
            target_entity_uuid=ally.uuid,
        )
    )
    Entity.materialize_all_navigation(max_distance=100)
    jump_template = ally.get_action_template("Jump")
    assert isinstance(jump_template, Jump)
    base_range = jump_template.get_range()
    assert base_range is not None
    assert base_range.normal == 25
    before = get_available_actions(ally)
    before_row = next(
        row for row in before.position_actions if row.template_name == "Jump"
    )
    before_positions = {target.position for target in before_row.valid_targets}
    assert (14, 7) not in before_positions

    result = JumpSpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=1,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert has_condition(ally, "Jump")
    assert not has_condition(caster, "Jump")
    assert not has_condition(caster, "Concentrating")
    jump_effect = ally.active_conditions["Jump"]
    assert jump_effect.duration.duration_type is DurationType.ROUNDS
    assert jump_effect.duration.duration == 10
    assert ally.jump_distance_multiplier.normalized_score == 3
    tripled_range = jump_template.get_range()
    assert tripled_range is not None
    assert tripled_range.normal == 75

    after = get_available_actions(ally)
    after_row = next(
        row for row in after.position_actions if row.template_name == "Jump"
    )
    after_positions = {target.position for target in after_row.valid_targets}
    assert (14, 7) in after_positions

    ally.remove_condition("Jump")

    assert not has_condition(ally, "Jump")
    assert ally.jump_distance_multiplier.normalized_score == 1
    restored_range = jump_template.get_range()
    assert restored_range is not None
    assert restored_range.normal == 25
    ally.jump_distance_additive.self_static.remove_modifier(additive_uuid)


def test_ray_of_frost_hit_and_slow_expire_on_caster_turn_not_target_turn() -> None:
    """The speed modifier is caster-owned and survives the target's turn."""
    reset_spell_regression_arena(16, 9)
    caster = create_spell_regression_actor(
        "Ray Caster",
        (2, 4),
        "heroes",
    )
    target = create_spell_regression_actor(
        "Ray Target",
        (7, 4),
        "monsters",
    )
    Entity.materialize_all_navigation(max_distance=80)
    base_speed = target.action_economy.movement.normalized_score
    hp_before = get_hp(target)
    hit_modifier = _force_spell_attack_hit(caster, target)

    with fixed_dice_faces(10, 4, 4):
        result = RayOfFrost(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_level=5,
        ).apply()
    _remove_spell_attack_modifier(caster, hit_modifier)

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert result.damage_rolls is not None
    assert result.damage_rolls[0].effective_dice_count == 2
    assert get_hp(target) < hp_before
    assert target.action_economy.movement.normalized_score == base_speed - 10
    assert has_condition(caster, "Ray of Frost Effect")

    target.on_turn_start()
    target.on_turn_end()

    assert target.action_economy.movement.normalized_score == base_speed - 10
    assert has_condition(caster, "Ray of Frost Effect")

    caster.on_turn_start()

    assert not has_condition(caster, "Ray of Frost Effect")
    assert target.action_economy.movement.normalized_score == base_speed


def test_acid_splash_two_target_damage_and_proximity_validation() -> None:
    """Two adjacent failed saves take acid; a separated pair cancels atomically."""
    reset_spell_regression_arena(18, 10)
    caster = create_spell_regression_actor(
        "Acid Splash Caster",
        (2, 4),
        "heroes",
    )
    first = create_spell_regression_actor(
        "First Acid Target",
        (7, 4),
        "monsters",
    )
    second = create_spell_regression_actor(
        "Second Acid Target",
        (8, 4),
        "monsters",
    )
    force_save_result(first, "dexterity", succeeds=False)
    force_save_result(second, "dexterity", succeeds=False)
    Entity.materialize_all_navigation(max_distance=90)
    hp_before = {first.uuid: get_hp(first), second.uuid: get_hp(second)}

    with fixed_dice_faces(10, 3, 10, 4):
        result = AcidSplash(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=first.uuid,
            extra_target_entity_uuids=[second.uuid],
            caster_level=1,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert result.total_targets == 2
    assert get_hp(first) < hp_before[first.uuid]
    assert get_hp(second) < hp_before[second.uuid]

    reset_spell_regression_arena(18, 10)
    caster = create_spell_regression_actor(
        "Separated Acid Caster",
        (2, 4),
        "heroes",
    )
    first = create_spell_regression_actor(
        "Separated First",
        (7, 4),
        "monsters",
    )
    second = create_spell_regression_actor(
        "Separated Second",
        (9, 4),
        "monsters",
    )
    Entity.materialize_all_navigation(max_distance=90)
    separated = AcidSplash(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=first.uuid,
        extra_target_entity_uuids=[second.uuid],
    ).apply()

    assert separated is not None
    assert separated.canceled
    assert separated.status_message is not None
    assert "within 5ft" in separated.status_message


def test_multi_target_ally_filter_is_unique_bounded_and_atomic() -> None:
    """The generic ally-filter spell keeps self/allies and rejects mixed input."""
    reset_spell_regression_arena(16, 10)
    caster = create_spell_regression_actor(
        "Ally Filter Caster",
        (2, 4),
        "heroes",
        spell_slots={1: 2},
    )
    first = create_spell_regression_actor(
        "First Ally",
        (3, 4),
        "heroes",
    )
    second = create_spell_regression_actor(
        "Second Ally",
        (2, 5),
        "heroes",
    )
    overflow = create_spell_regression_actor(
        "Overflow Ally",
        (3, 5),
        "heroes",
    )
    enemy = create_spell_regression_actor(
        "Ally Filter Enemy",
        (5, 4),
        "monsters",
    )
    Entity.materialize_all_navigation(max_distance=80)
    valid = AllyFilterSpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        extra_target_entity_uuids=[
            first.uuid,
            first.uuid,
            second.uuid,
            overflow.uuid,
        ],
        cast_at_level=1,
    )

    assert valid.allow_same_target is False
    assert valid.get_all_targets() == [caster.uuid, first.uuid, second.uuid]
    result = valid.apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert result.total_targets == 3

    caster.action_economy.reset_all_costs()
    mixed = AllyFilterSpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=first.uuid,
        extra_target_entity_uuids=[enemy.uuid],
        cast_at_level=1,
    ).apply()

    assert mixed is not None
    assert mixed.canceled
    assert mixed.status_message is not None
    assert "ally" in mixed.status_message.lower()


def test_necrotic_bless_executes_undead_failure_and_success_branches() -> None:
    """Creature type and each independent save own the actual applied effects."""
    reset_spell_regression_arena(16, 10)
    caster = create_spell_regression_actor(
        "Necrotic Bless Caster",
        (2, 4),
        "monsters",
        spell_slots={2: 1},
        creature_type=CreatureType.UNDEAD,
    )
    undead = create_spell_regression_actor(
        "Necrotic Blessed Undead",
        (3, 4),
        "monsters",
        creature_type=CreatureType.UNDEAD,
    )
    failed = create_spell_regression_actor(
        "Necrotic Baned Living",
        (4, 4),
        "heroes",
    )
    passed = create_spell_regression_actor(
        "Necrotic Resisting Living",
        (5, 4),
        "heroes",
    )
    force_save_result(failed, "charisma", succeeds=False)
    force_save_result(passed, "charisma", succeeds=True)
    Entity.materialize_all_navigation(max_distance=80)

    with fixed_dice_faces(10, 10):
        result = NecroticBless(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=undead.uuid,
            extra_target_entity_uuids=[failed.uuid, passed.uuid],
            cast_at_level=2,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert result.total_targets == 3
    assert has_condition(undead, "Bless")
    assert has_condition(failed, "Bane")
    assert not has_condition(passed, "Bane")
    assert has_condition(caster, "Concentrating")
    concentration = caster.active_conditions["Concentrating"]
    assert {
        linked_condition_uuid
        for _, linked_condition_uuid in concentration.linked_conditions
    } == {
        undead.active_conditions["Bless"].uuid,
        failed.active_conditions["Bane"].uuid,
    }

    caster.remove_condition("Concentrating")

    assert not has_condition(undead, "Bless")
    assert not has_condition(failed, "Bane")


def test_sunbeam_initial_and_repeat_line_share_concentration_owned_action() -> None:
    """Initial and later beams apply per-target saves and one owned action."""
    reset_spell_regression_arena(24, 12)
    caster = create_spell_regression_actor(
        "Sunbeam Caster",
        (2, 5),
        "heroes",
        spell_slots={6: 1},
    )
    failed = create_spell_regression_actor(
        "Failed Sunbeam Target",
        (7, 5),
        "monsters",
    )
    passed = create_spell_regression_actor(
        "Passed Sunbeam Target",
        (10, 5),
        "monsters",
    )
    force_save_result(failed, "constitution", succeeds=False)
    force_save_result(passed, "constitution", succeeds=True)
    Entity.materialize_all_navigation(max_distance=120)
    hp_before = {failed.uuid: get_hp(failed), passed.uuid: get_hp(passed)}

    with fixed_dice_faces(
        10,
        *([4] * 6),
        10,
        *([4] * 6),
    ):
        result = Sunbeam(
            source_entity_uuid=caster.uuid,
            end_position=(15, 5),
            cast_at_level=6,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    failed_damage = hp_before[failed.uuid] - get_hp(failed)
    passed_damage = hp_before[passed.uuid] - get_hp(passed)
    assert failed_damage > 0
    assert passed_damage == failed_damage // 2
    assert has_condition(failed, "Blinded")
    assert not has_condition(passed, "Blinded")
    assert has_condition(caster, "Concentrating")
    strike_template = caster.get_action_template("Sunbeam Strike")
    assert isinstance(strike_template, SunbeamStrike)
    assert "Sunbeam Strike" in _action_names(caster)

    failed.remove_condition("Blinded")
    caster.action_economy.reset_all_costs()
    hp_before_repeat = get_hp(failed)
    with fixed_dice_faces(
        10,
        *([3] * 6),
        10,
        *([3] * 6),
    ):
        repeat = strike_template.instantiate(end_position=(15, 5)).apply()

    assert repeat is not None
    assert not repeat.canceled
    assert get_hp(failed) < hp_before_repeat
    assert has_condition(failed, "Blinded")
    assert caster.action_economy.actions.normalized_score == 0

    caster.remove_condition("Concentrating")

    assert caster.get_action_template("Sunbeam Strike") is None
    caster.action_economy.reset_all_costs()
    orphaned = SunbeamStrike(
        source_entity_uuid=caster.uuid,
        end_position=(15, 5),
        spell_dc=strike_template.spell_dc,
    ).apply()
    assert orphaned is not None
    assert orphaned.canceled


def test_scorching_ray_executes_every_base_and_upcast_projectile() -> None:
    """The projectile-count profile is backed by independent runtime attacks."""
    reset_spell_regression_arena(20, 8)
    caster = create_spell_regression_actor(
        "Scorching Ray Caster",
        (2, 3),
        "heroes",
        spell_slots={3: 1},
    )
    target = create_spell_regression_actor(
        "Scorching Ray Target",
        (8, 3),
        "monsters",
    )
    Entity.materialize_all_navigation(max_distance=100)
    hit_modifier = _force_spell_attack_hit(caster, target)
    hp_before = get_hp(target)
    spell = ScorchingRay(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=3,
        caster_level=5,
    )

    with fixed_dice_faces(*([4] * 40)):
        result = spell.apply()
    _remove_spell_attack_modifier(caster, hit_modifier)

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert spell.get_num_projectiles() == 4
    assert spell.get_all_targets() == [target.uuid] * 4
    assert hp_before - get_hp(target) == 32
    assert result.combat_log is not None
    assert len(result.combat_log.sub_entries) == 4
    assert all(entry.success for entry in result.combat_log.sub_entries)
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_3.normalized_score == 0


def test_blur_and_blindness_deafness_execute_distinct_lifecycles() -> None:
    """Blur is concentration-owned; Blindness/Deafness is repeat-save owned."""
    reset_spell_regression_arena(16, 8)
    blur_caster = create_spell_regression_actor(
        "Blur Caster",
        (2, 3),
        "heroes",
        spell_slots={2: 1},
    )
    attacker = create_spell_regression_actor(
        "Blur Attacker",
        (3, 3),
        "monsters",
    )
    Entity.materialize_all_navigation(max_distance=80)

    blur_result = Blur(
        source_entity_uuid=blur_caster.uuid,
        cast_at_level=2,
    ).apply()

    assert isinstance(blur_result, SpellEvent)
    assert not blur_result.canceled
    assert has_condition(blur_caster, "Blur")
    assert has_condition(blur_caster, "Concentrating")
    attack_bonus = attacker.attack_bonus(
        WeaponSlot.MELEE_MAIN,
        blur_caster.uuid,
    )
    target_ac = blur_caster.ac_bonus(attacker.uuid)
    attack_bonus.set_from_target(target_ac)
    assert attack_bonus.advantage is AdvantageStatus.DISADVANTAGE
    attack_bonus.reset_from_target()

    blur_caster.remove_condition("Concentrating")

    assert not has_condition(blur_caster, "Blur")

    reset_spell_regression_arena(16, 8)
    caster = create_spell_regression_actor(
        "Blindness Caster",
        (2, 3),
        "heroes",
        spell_slots={3: 1},
    )
    first = create_spell_regression_actor(
        "First Deafened Target",
        (6, 3),
        "monsters",
    )
    second = create_spell_regression_actor(
        "Second Deafened Target",
        (7, 3),
        "monsters",
    )
    force_save_result(first, "constitution", succeeds=False)
    force_save_result(second, "constitution", succeeds=False)
    Entity.materialize_all_navigation(max_distance=80)

    with fixed_dice_faces(10, 10):
        blindness_result = BlindnessDeafness(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=first.uuid,
            extra_target_entity_uuids=[second.uuid],
            effect_type="deafened",
            cast_at_level=3,
        ).apply()

    assert isinstance(blindness_result, SpellEvent)
    assert not blindness_result.canceled
    for target in (first, second):
        assert has_condition(target, "Blindness/Deafness")
        assert has_condition(target, "Deafened")
    assert not has_condition(caster, "Concentrating")

    first.saving_throws.constitution_saving_throw.bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=first.uuid,
            target_entity_uuid=first.uuid,
            name="Repeat save overrides initial forced failure",
            value=300,
        )
    )
    with fixed_dice_faces(10):
        first.on_turn_end()

    assert not has_condition(first, "Blindness/Deafness")
    assert not has_condition(first, "Deafened")
    assert has_condition(second, "Blindness/Deafness")


def test_fear_and_hypnotic_pattern_execute_area_and_cleanup_rules() -> None:
    """Cone/cube selection drives real condition transforms and owned cleanup."""
    reset_spell_regression_arena(20, 12)
    caster = create_spell_regression_actor(
        "Fear Caster",
        (5, 5),
        "heroes",
        spell_slots={3: 1},
    )
    in_cone = create_spell_regression_actor(
        "Fear Target",
        (8, 5),
        "monsters",
    )
    behind = create_spell_regression_actor(
        "Behind Fear Caster",
        (2, 5),
        "monsters",
    )
    force_save_result(in_cone, "wisdom", succeeds=False)
    force_save_result(behind, "wisdom", succeeds=False)
    Entity.materialize_all_navigation(max_distance=100)

    with fixed_dice_faces(10):
        fear_result = Fear(
            source_entity_uuid=caster.uuid,
            end_position=(12, 5),
            cast_at_level=3,
        ).apply()

    assert isinstance(fear_result, SpellEvent)
    assert not fear_result.canceled
    assert has_condition(in_cone, "Fear")
    assert has_condition(in_cone, "Frightened")
    assert not has_condition(behind, "Fear")
    assert has_condition(caster, "Concentrating")

    caster.remove_condition("Concentrating")

    assert not has_condition(in_cone, "Fear")
    assert not has_condition(in_cone, "Frightened")

    reset_spell_regression_arena(22, 14)
    caster = create_spell_regression_actor(
        "Pattern Caster",
        (2, 6),
        "heroes",
        spell_slots={3: 1},
    )
    target = create_spell_regression_actor(
        "Pattern Target",
        (9, 6),
        "monsters",
    )
    outside = create_spell_regression_actor(
        "Outside Pattern",
        (18, 12),
        "monsters",
    )
    force_save_result(target, "wisdom", succeeds=False)
    force_save_result(outside, "wisdom", succeeds=False)
    Entity.materialize_all_navigation(max_distance=120)

    with fixed_dice_faces(10):
        pattern_result = HypnoticPattern(
            source_entity_uuid=caster.uuid,
            end_position=(9, 6),
            cast_at_level=3,
        ).apply()

    assert isinstance(pattern_result, SpellEvent)
    assert not pattern_result.canceled
    assert has_condition(target, "Hypnotic Pattern")
    assert has_condition(target, "Charmed")
    assert target.action_economy.actions.normalized_score == 0
    assert target.action_economy.bonus_actions.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0
    assert not has_condition(outside, "Hypnotic Pattern")
    assert has_condition(caster, "Concentrating")

    caster.remove_condition("Concentrating")

    assert not has_condition(target, "Hypnotic Pattern")
    assert not has_condition(target, "Charmed")
    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.bonus_actions.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30


def test_position_aoe_preview_execution_preserves_filters_and_cardinality() -> None:
    """Position AoE preview and convolution resolve one identical target set."""
    reset_spell_regression_arena(18, 12)
    caster = create_spell_regression_actor(
        "AoE Caster",
        (5, 5),
        "heroes",
        spell_slots={3: 2},
    )
    ally = create_spell_regression_actor(
        "AoE Ally",
        (6, 5),
        "heroes",
    )
    enemies = [
        create_spell_regression_actor(
            "AoE Enemy One",
            (7, 5),
            "monsters",
        ),
        create_spell_regression_actor(
            "AoE Enemy Two",
            (7, 6),
            "monsters",
        ),
    ]
    outsider = create_spell_regression_actor(
        "AoE Outsider",
        (15, 10),
        "monsters",
    )
    for enemy in enemies:
        force_save_result(enemy, "dexterity", succeeds=False)
    Entity.materialize_all_navigation(max_distance=90)

    all_targets = Fireball(
        source_entity_uuid=caster.uuid,
        end_position=(6, 5),
        cast_at_level=3,
        include_self=True,
        valid_target_filter="all",
    ).get_all_targets()
    assert set(all_targets) == {
        caster.uuid,
        ally.uuid,
        *(enemy.uuid for enemy in enemies),
    }

    enemy_only = Fireball(
        source_entity_uuid=caster.uuid,
        end_position=(6, 5),
        cast_at_level=3,
        include_self=False,
        valid_target_filter="enemies",
    )
    assert enemy_only.get_all_targets() == [
        enemies[0].uuid,
        enemies[1].uuid,
    ]
    hp_before = {
        actor.uuid: get_hp(actor)
        for actor in (caster, ally, *enemies, outsider)
    }

    with fixed_dice_faces(*([4] * 80)):
        direct_result = enemy_only.apply()

    assert isinstance(direct_result, SpellEvent)
    assert not direct_result.canceled
    assert direct_result.total_targets == 2
    assert direct_result.combat_log is not None
    assert len(direct_result.combat_log.sub_entries) == 2
    assert all(
        get_hp(enemy) < hp_before[enemy.uuid]
        for enemy in enemies
    )
    assert get_hp(caster) == hp_before[caster.uuid]
    assert get_hp(ally) == hp_before[ally.uuid]
    assert get_hp(outsider) == hp_before[outsider.uuid]
    assert direct_result.total_damage == sum(
        hp_before[enemy.uuid] - get_hp(enemy)
        for enemy in enemies
    )

    reset_spell_regression_arena(18, 12)
    caster = create_spell_regression_actor(
        "Preview AoE Caster",
        (5, 5),
        "heroes",
        spell_slots={3: 1},
    )
    setup_standard_actions(caster)
    preview_actors = [
        caster,
        create_spell_regression_actor(
            "Preview AoE Ally",
            (6, 5),
            "heroes",
        ),
        create_spell_regression_actor(
            "Preview AoE Enemy One",
            (7, 5),
            "monsters",
        ),
        create_spell_regression_actor(
            "Preview AoE Enemy Two",
            (7, 6),
            "monsters",
        ),
    ]
    preview_outsider = create_spell_regression_actor(
        "Preview AoE Outsider",
        (15, 10),
        "monsters",
    )
    Entity.materialize_all_navigation(max_distance=90)
    register_spell(caster, Fireball, caster_level=5)

    available = get_available_actions(caster)
    fireball = next(
        action
        for action in available.position_actions
        if action.base_template_name == "Fireball"
        and action.cast_at_level == 3
    )
    target = next(
        candidate
        for candidate in fireball.valid_targets
        if candidate.position == (6, 5)
    )
    preview_ids = set(target.affected_entity_uuids or [])
    assert target.affected_count == 4
    assert preview_ids == {actor.uuid for actor in preview_actors}
    assert preview_outsider.uuid not in preview_ids
    preview_hp = {
        actor.uuid: get_hp(actor)
        for actor in (*preview_actors, preview_outsider)
    }

    with fixed_dice_faces(*([4] * 100)):
        execution = execute_by_index(
            caster,
            fireball.template_name,
            target.index,
            available=available,
        )

    assert isinstance(execution, SpellEvent)
    assert not execution.canceled
    assert execution.total_targets == target.affected_count
    assert execution.aoe_position == target.position
    assert execution.combat_log is not None
    assert len(execution.combat_log.sub_entries) == target.affected_count
    assert {
        actor.uuid
        for actor in preview_actors
        if get_hp(actor) < preview_hp[actor.uuid]
    } == preview_ids
    assert get_hp(preview_outsider) == preview_hp[preview_outsider.uuid]


def test_magic_missile_preserves_dart_distribution_upcast_and_enemy_filter() -> None:
    """Every dart is one ordered application, including repeats and upcasts."""
    reset_spell_regression_arena(16, 10)
    caster = create_spell_regression_actor(
        "Magic Missile Caster",
        (2, 2),
        "heroes",
        spell_slots={1: 3, 3: 1},
    )
    enemies = [
        create_spell_regression_actor(
            f"Magic Missile Enemy {index}",
            (4 + index, 2),
            "monsters",
        )
        for index in range(3)
    ]
    ally = create_spell_regression_actor(
        "Magic Missile Ally",
        (3, 3),
        "heroes",
    )
    Entity.materialize_all_navigation(max_distance=80)

    single_target = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=enemies[0].uuid,
        cast_at_level=1,
    )
    assert single_target.get_num_projectiles() == 3
    assert single_target.get_multi_target_count() == 3
    assert single_target.get_all_targets() == [enemies[0].uuid] * 3
    single_hp = get_hp(enemies[0])
    with fixed_dice_faces(1, 2, 3):
        single_event = single_target.apply()
    assert isinstance(single_event, SpellEvent)
    assert not single_event.canceled
    assert single_event.total_targets == 3
    assert single_event.total_damage == 9
    assert get_hp(enemies[0]) == single_hp - 9
    assert single_event.combat_log is not None
    assert len(single_event.combat_log.sub_entries) == 3

    caster.action_economy.reset_all_costs()
    split = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=enemies[0].uuid,
        extra_target_entity_uuids=[enemies[1].uuid, enemies[2].uuid],
        cast_at_level=1,
    )
    assert split.get_all_targets() == [enemy.uuid for enemy in enemies]
    split_hp = [get_hp(enemy) for enemy in enemies]
    with fixed_dice_faces(1, 2, 3):
        split_event = split.apply()
    assert isinstance(split_event, SpellEvent)
    assert not split_event.canceled
    assert split_event.total_targets == 3
    assert split_event.total_damage == 9
    assert [
        before - get_hp(enemy)
        for before, enemy in zip(split_hp, enemies, strict=True)
    ] == [2, 3, 4]

    caster.action_economy.reset_all_costs()
    upcast = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=enemies[0].uuid,
        extra_target_entity_uuids=[
            enemies[0].uuid,
            enemies[1].uuid,
            enemies[1].uuid,
            enemies[2].uuid,
        ],
        cast_at_level=3,
    )
    assert upcast.allow_same_target
    assert upcast.get_num_projectiles() == 5
    assert upcast.get_all_targets() == [
        enemies[0].uuid,
        enemies[0].uuid,
        enemies[1].uuid,
        enemies[1].uuid,
        enemies[2].uuid,
    ]
    with fixed_dice_faces(1, 1, 1, 1, 1):
        upcast_event = upcast.apply()
    assert isinstance(upcast_event, SpellEvent)
    assert not upcast_event.canceled
    assert upcast_event.cast_at_level == 3
    assert upcast_event.total_targets == 5
    assert upcast_event.total_damage == 10

    caster.action_economy.reset_all_costs()
    action_before = caster.action_economy.actions.normalized_score
    slot_before = caster.action_economy.spell_slot_1.normalized_score
    ally_event = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=1,
    ).apply()
    assert isinstance(ally_event, SpellEvent)
    assert ally_event.canceled
    assert ally_event.status_message is not None
    assert "enemy" in ally_event.status_message.lower()
    assert caster.action_economy.actions.normalized_score == action_before
    assert caster.action_economy.spell_slot_1.normalized_score == slot_before


def test_self_range_aoe_discovery_survives_zero_visible_enemies() -> None:
    """Self-origin cone, cube, and line spells remain discoverable when alone."""
    reset_spell_regression_arena(16, 12)
    caster = create_spell_regression_actor(
        "Solo AoE Caster",
        (5, 5),
        "heroes",
        spell_slots={1: 2, 2: 1, 3: 2},
    )
    setup_standard_actions(caster)
    for spell_type in (BurningHands, Thunderwave, LightningBolt, Fireball):
        register_spell(caster, spell_type, caster_level=5)
    Entity.materialize_all_navigation(max_distance=80)

    available = get_available_actions(caster)
    legal = get_available_actions(caster, legal_only=True)
    by_base_name = {
        action.base_template_name: action
        for action in available.position_actions
        if action.base_template_name in {
            "Burning Hands",
            "Thunderwave",
            "Lightning Bolt",
            "Fireball",
        }
    }
    assert set(by_base_name) == {
        "Burning Hands",
        "Thunderwave",
        "Lightning Bolt",
        "Fireball",
    }
    assert by_base_name["Burning Hands"].valid_targets == []
    assert by_base_name["Burning Hands"].can_afford
    assert by_base_name["Burning Hands"].availability_status == "no_valid_targets"
    assert by_base_name["Thunderwave"].valid_targets == []
    assert by_base_name["Thunderwave"].availability_status == "no_valid_targets"
    assert by_base_name["Lightning Bolt"].valid_targets == []
    assert by_base_name["Lightning Bolt"].availability_status == "no_valid_targets"
    assert {
        action.base_template_name
        for action in legal.position_actions
    }.isdisjoint({
        "Burning Hands",
        "Thunderwave",
        "Lightning Bolt",
    })

    enemy = create_spell_regression_actor(
        "Visible AoE Enemy",
        (5, 7),
        "monsters",
    )
    Entity.materialize_all_navigation(max_distance=80)
    with_enemy = get_available_actions(caster)
    burning_hands = next(
        action
        for action in with_enemy.position_actions
        if action.base_template_name == "Burning Hands"
    )
    assert burning_hands.valid_targets
    assert burning_hands.availability_status == "available"
    assert any(
        enemy.uuid in set(target.affected_entity_uuids or [])
        for target in burning_hands.valid_targets
    )


def test_close_area_spells_execute_save_geometry_damage_and_push_rules() -> None:
    """Profiles do not replace actual cone/cube save and movement execution."""
    reset_spell_regression_arena(20, 12)
    caster = create_spell_regression_actor(
        "Close Area Caster",
        (5, 5),
        "heroes",
        spell_slots={2: 1},
    )
    failed = create_spell_regression_actor(
        "Cone Failure",
        (7, 5),
        "monsters",
    )
    passed = create_spell_regression_actor(
        "Cone Success",
        (6, 5),
        "monsters",
    )
    behind = create_spell_regression_actor(
        "Behind Cone",
        (3, 5),
        "monsters",
    )
    force_save_result(failed, "dexterity", succeeds=False)
    force_save_result(passed, "dexterity", succeeds=True)
    force_save_result(behind, "dexterity", succeeds=False)
    Entity.materialize_all_navigation(max_distance=100)
    hp_before = {
        entity.uuid: get_hp(entity)
        for entity in (caster, failed, passed, behind)
    }

    with fixed_dice_faces(*([4] * 40)):
        burning_result = BurningHands(
            source_entity_uuid=caster.uuid,
            end_position=(12, 5),
            cast_at_level=2,
        ).apply()

    assert isinstance(burning_result, SpellEvent)
    assert not burning_result.canceled
    assert hp_before[failed.uuid] - get_hp(failed) == 16
    assert hp_before[passed.uuid] - get_hp(passed) == 8
    assert get_hp(behind) == hp_before[behind.uuid]
    assert get_hp(caster) == hp_before[caster.uuid]
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_2.normalized_score == 0

    reset_spell_regression_arena(16, 10)
    grid = get_map()
    grid.set_tile(6, 5, surface=TileSurface(base_material=Material.STONE), walkable=False, blocks_optics=True, blocks_propagation=True, name="Cone Wall")
    caster = create_spell_regression_actor(
        "Blocked Cone Caster",
        (5, 5),
        "heroes",
        spell_slots={1: 1},
    )
    blocked = create_spell_regression_actor(
        "Blocked Cone Target",
        (8, 5),
        "monsters",
    )
    force_save_result(blocked, "dexterity", succeeds=False)
    Entity.materialize_all_navigation(max_distance=100)
    blocked_hp = get_hp(blocked)

    with fixed_dice_faces(*([4] * 20)):
        blocked_result = BurningHands(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=1,
        ).apply()

    assert isinstance(blocked_result, SpellEvent)
    assert not blocked_result.canceled
    assert get_hp(blocked) == blocked_hp
    assert blocked_result.total_targets == 0

    reset_spell_regression_arena(20, 12)
    caster = create_spell_regression_actor(
        "Thunderwave Caster",
        (5, 5),
        "heroes",
        spell_slots={1: 1},
    )
    failed = create_spell_regression_actor(
        "Thunderwave Failure",
        (7, 5),
        "monsters",
    )
    passed = create_spell_regression_actor(
        "Thunderwave Success",
        (7, 6),
        "monsters",
    )
    force_save_result(failed, "constitution", succeeds=False)
    force_save_result(passed, "constitution", succeeds=True)
    Entity.materialize_all_navigation(max_distance=100)
    failed_hp = get_hp(failed)
    passed_hp = get_hp(passed)
    passed_position = passed.position

    with fixed_dice_faces(*([4] * 40)):
        thunder_result = Thunderwave(
            source_entity_uuid=caster.uuid,
            end_position=(12, 5),
            cast_at_level=1,
        ).apply()

    assert isinstance(thunder_result, SpellEvent)
    assert not thunder_result.canceled
    assert failed_hp - get_hp(failed) == 8
    assert passed_hp - get_hp(passed) == 4
    assert failed.position == (9, 5)
    assert passed.position == passed_position
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_1.normalized_score == 0


def test_fireball_executes_save_upcast_relationship_and_aggregation_matrix() -> None:
    """Friendly fire, self inclusion, saves, upcasting, and totals execute together."""
    reset_spell_regression_arena(24, 14)
    caster = create_spell_regression_actor(
        "Fireball Matrix Caster",
        (2, 6),
        "heroes",
        spell_slots={4: 1},
        hit_die_count=100,
    )
    ally = create_spell_regression_actor(
        "Fireball Matrix Ally",
        (6, 5),
        "heroes",
        hit_die_count=100,
    )
    failed = create_spell_regression_actor(
        "Fireball Matrix Failure",
        (6, 6),
        "monsters",
        hit_die_count=100,
    )
    passed = create_spell_regression_actor(
        "Fireball Matrix Success",
        (7, 6),
        "monsters",
        hit_die_count=100,
    )
    for target in (caster, ally, failed):
        force_save_result(target, "dexterity", succeeds=False)
    force_save_result(passed, "dexterity", succeeds=True)
    Entity.materialize_all_navigation(max_distance=120)
    hp_before = {
        target.uuid: get_hp(target)
        for target in (caster, ally, failed, passed)
    }

    with fixed_dice_faces(*([4] * 100)):
        result = Fireball(
            source_entity_uuid=caster.uuid,
            end_position=(6, 6),
            cast_at_level=4,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert result.total_targets == 4
    assert hp_before[caster.uuid] - get_hp(caster) == 36
    assert hp_before[ally.uuid] - get_hp(ally) == 36
    assert hp_before[failed.uuid] - get_hp(failed) == 36
    assert hp_before[passed.uuid] - get_hp(passed) == 18
    assert result.total_damage == 126
    assert result.combat_log is not None
    assert len(result.combat_log.sub_entries) == 4
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_4.normalized_score == 0
    assert Fireball(
        source_entity_uuid=caster.uuid,
        cast_at_level=9,
    ).get_damage_dice_count() == 14

    reset_spell_regression_arena(16, 10)
    careful = create_spell_regression_actor(
        "Careful Fireball Caster",
        (5, 4),
        "heroes",
        spell_slots={3: 1},
    )
    protected_ally = create_spell_regression_actor(
        "Protected Fireball Ally",
        (6, 4),
        "heroes",
    )
    only_enemy = create_spell_regression_actor(
        "Only Fireball Enemy",
        (7, 4),
        "monsters",
    )
    force_save_result(only_enemy, "dexterity", succeeds=False)
    Entity.materialize_all_navigation(max_distance=80)
    careful_hp = get_hp(careful)
    ally_hp = get_hp(protected_ally)
    enemy_hp = get_hp(only_enemy)

    with fixed_dice_faces(*([3] * 50)):
        careful_result = Fireball(
            source_entity_uuid=careful.uuid,
            end_position=(6, 4),
            cast_at_level=3,
            valid_target_filter="enemies",
            include_self=False,
        ).apply()

    assert isinstance(careful_result, SpellEvent)
    assert not careful_result.canceled
    assert careful_result.total_targets == 1
    assert get_hp(careful) == careful_hp
    assert get_hp(protected_ally) == ally_hp
    assert enemy_hp - get_hp(only_enemy) == 24


def test_fireball_enforces_cast_los_range_and_explosion_occlusion() -> None:
    """Cast geometry and explosion geometry are both authoritative."""
    reset_spell_regression_arena(45, 12)
    grid = get_map()
    caster = create_spell_regression_actor(
        "Fireball Geometry Caster",
        (2, 5),
        "heroes",
        spell_slots={3: 2},
    )
    hidden = create_spell_regression_actor(
        "Hidden Fireball Target",
        (8, 5),
        "monsters",
    )
    for y in range(12):
        grid.set_tile(5, y, surface=TileSurface(base_material=Material.STONE), walkable=False, blocks_optics=True, blocks_propagation=True, name="Wall")
    Entity.materialize_all_navigation(max_distance=250)

    blocked = Fireball(
        source_entity_uuid=caster.uuid,
        end_position=hidden.position,
        cast_at_level=3,
    ).apply()

    assert blocked is not None
    assert blocked.canceled
    assert blocked.status_message == f"Position {hidden.position} not visible"

    reset_spell_regression_arena(45, 12)
    caster = create_spell_regression_actor(
        "Long Fireball Caster",
        (1, 5),
        "heroes",
        spell_slots={3: 1},
    )
    distant = create_spell_regression_actor(
        "Distant Fireball Target",
        (33, 5),
        "monsters",
    )
    Entity.materialize_all_navigation(max_distance=250)
    out_of_range = Fireball(
        source_entity_uuid=caster.uuid,
        end_position=distant.position,
        cast_at_level=3,
    ).apply()

    assert out_of_range is not None
    assert out_of_range.canceled
    assert out_of_range.status_message is not None
    assert "out of range" in out_of_range.status_message.lower()

    reset_spell_regression_arena(20, 12)
    grid = get_map()
    caster = create_spell_regression_actor(
        "Occlusion Fireball Caster",
        (1, 5),
        "heroes",
        spell_slots={3: 1},
    )
    visible = create_spell_regression_actor(
        "Visible Explosion Target",
        (5, 5),
        "monsters",
    )
    behind_wall = create_spell_regression_actor(
        "Occluded Explosion Target",
        (8, 5),
        "monsters",
    )
    grid.set_tile(7, 5, surface=TileSurface(base_material=Material.STONE), walkable=False, blocks_optics=True, blocks_propagation=True, name="Explosion Wall")
    force_save_result(visible, "dexterity", succeeds=False)
    force_save_result(behind_wall, "dexterity", succeeds=False)
    Entity.materialize_all_navigation(max_distance=100)
    visible_hp = get_hp(visible)
    occluded_hp = get_hp(behind_wall)

    with fixed_dice_faces(*([3] * 50)):
        result = Fireball(
            source_entity_uuid=caster.uuid,
            end_position=visible.position,
            cast_at_level=3,
            valid_target_filter="enemies",
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert visible_hp - get_hp(visible) == 24
    assert get_hp(behind_wall) == occluded_hp


def test_thunderwave_push_stops_before_walls_and_occupied_cells() -> None:
    """Failed saves never tunnel through either structural or entity blockers."""
    reset_spell_regression_arena(16, 10)
    grid = get_map()
    caster = create_spell_regression_actor(
        "Wall Thunderwave Caster",
        (5, 4),
        "heroes",
        spell_slots={1: 1},
    )
    target = create_spell_regression_actor(
        "Wall Thunderwave Target",
        (7, 4),
        "monsters",
    )
    grid.set_tile(8, 4, surface=TileSurface(base_material=Material.STONE), walkable=False, blocks_optics=False, blocks_propagation=False, name="Push Wall")
    force_save_result(target, "constitution", succeeds=False)
    Entity.materialize_all_navigation(max_distance=80)
    caster_hp = get_hp(caster)
    target_hp = get_hp(target)

    with fixed_dice_faces(*([4] * 40)):
        wall_result = Thunderwave(
            source_entity_uuid=caster.uuid,
            end_position=(12, 4),
            cast_at_level=1,
        ).apply()

    assert isinstance(wall_result, SpellEvent)
    assert not wall_result.canceled
    assert target_hp - get_hp(target) == 8
    assert target.position == (7, 4)
    assert get_hp(caster) == caster_hp

    reset_spell_regression_arena(16, 10)
    caster = create_spell_regression_actor(
        "Occupied Thunderwave Caster",
        (5, 4),
        "heroes",
        spell_slots={1: 1},
    )
    target = create_spell_regression_actor(
        "Occupied Thunderwave Target",
        (7, 4),
        "monsters",
    )
    blocker = create_spell_regression_actor(
        "Thunderwave Entity Blocker",
        (8, 4),
        "monsters",
    )
    force_save_result(target, "constitution", succeeds=False)
    force_save_result(blocker, "constitution", succeeds=True)
    Entity.materialize_all_navigation(max_distance=80)
    blocker_position = blocker.position

    with fixed_dice_faces(*([4] * 40)):
        occupied_result = Thunderwave(
            source_entity_uuid=caster.uuid,
            end_position=(12, 4),
            cast_at_level=1,
        ).apply()

    assert isinstance(occupied_result, SpellEvent)
    assert not occupied_result.canceled
    assert target.position == (7, 4)
    assert blocker.position == blocker_position
