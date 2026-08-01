"""Deterministic parity for the archived Cleric spell batches 2, 4, and 5.

The archived scripts used print-only checks, stochastic saves, and several
illegal caster fixtures. This module restores the mechanical cases that were
not already asserted by the active engine-book suite.
"""

from uuid import uuid4
from unittest.mock import patch

import pytest

from dnd.actions import Attack, Move, SpellEvent
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.equipment import Weapon
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.conditions import Frightened, Poisoned
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionTag
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    DamageRollResultEvent,
    EventPhase,
    EventQueue,
    EventType,
    TakeDamageEvent,
)
from dnd.core.combat_log import CombatLogEntryType
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import (
    AdvantageStatus,
    NumericalModifier,
)
from dnd.entity import Entity
from dnd.items.weapons import DAGGER_RECIPE
from dnd.spells.abjuration import (
    Aid,
    BeaconOfHope,
    DeathWard,
    FreedomOfMovement,
    RemoveCurse,
    Resistance,
    Sanctuary,
    ShieldOfFaith,
    ShieldOfFaithEffect,
)
from dnd.spells.conjuration import HeroesFeast, HeroesFeastObject
from dnd.spells.evocation import CureWounds, DivineWord
from dnd.spells.necromancy import (
    AbilityCurseEffect,
    AttackCurseEffect,
    BestowCurse,
    DamageCurseEffect,
    Harm,
    InactionCurseEffect,
    InflictWounds,
)
from tests.engine.support import (
    deal_damage_to,
    force_attack_hit,
    get_hp,
    get_max_hp,
    has_condition,
    remove_attack_modifier,
    set_hp,
)
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    force_save_result,
    reset_spell_regression_arena,
)


def _make_difficult(position: tuple[int, int]) -> None:
    """Add one difficult-terrain cost unit to an existing tile."""
    tile = get_map().get_tile(*position)
    assert tile is not None
    tile.walking_cost.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=tile.uuid,
            name="Legacy difficult terrain",
            value=1,
        )
    )


def _equip_dagger(entity: Entity) -> None:
    """Give an actor one deterministic melee attack surface."""
    entity.equipment.equip(
        materialize_item(
            DAGGER_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_MAIN,
    )
    setup_standard_actions(entity)


def test_death_ward_is_consumed_before_a_second_lethal_hit() -> None:
    """Batch 2 old case 7: Death Ward protects exactly once."""
    reset_spell_regression_arena(10, 6)
    caster = create_spell_regression_actor(
        "Ward Cleric",
        (1, 2),
        "heroes",
        spell_slots={4: 1},
    )
    target = create_spell_regression_actor("Warded Ally", (2, 2), "heroes")
    Entity.update_all_entities_senses(max_distance=40)

    result = DeathWard(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=4,
    ).apply()
    assert isinstance(result, SpellEvent)
    assert not result.canceled

    set_hp(target, 10)
    deal_damage_to(
        target,
        50,
        DamageType.SLASHING,
        source_uuid=caster.uuid,
    )
    assert get_hp(target) == 1
    assert not has_condition(target, "Death Ward")

    deal_damage_to(
        target,
        50,
        DamageType.SLASHING,
        source_uuid=caster.uuid,
    )
    assert target.health.life_state is LifeState.DEAD


def test_freedom_of_movement_changes_path_and_committed_step_costs() -> None:
    """Batch 2 old cases 9-10: difficult terrain is ignored end to end."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Freedom Cleric",
        (1, 3),
        "heroes",
        spell_slots={4: 1},
    )
    target = create_spell_regression_actor("Runner", (2, 3), "heroes")
    setup_standard_actions(target)
    for x in range(3, 6):
        for y in range(7):
            _make_difficult((x, y))
    Entity.update_all_entities_senses(max_distance=40)

    distances_before, _ = get_map().compute_paths(
        target.position,
        max_distance=20,
        requesting_entity_uuid=target.uuid,
        subjective=True,
    )
    result = FreedomOfMovement(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=4,
    ).apply()
    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert target.ignore_difficult_terrain

    distances_after, _ = get_map().compute_paths(
        target.position,
        max_distance=20,
        requesting_entity_uuid=target.uuid,
        subjective=True,
        ignore_difficult_terrain=target.ignore_difficult_terrain,
    )
    assert distances_before[(6, 3)] == 7
    assert distances_after[(6, 3)] == 4

    target.update_entity_senses(max_distance=20)
    movement_before = target.action_economy.movement.normalized_score
    move = Move(
        source_entity_uuid=target.uuid,
        end_position=(3, 3),
    ).apply()
    assert move is not None
    assert not move.canceled
    assert target.action_economy.movement.normalized_score == movement_before - 5


def test_resistance_modifies_one_save_then_cleans_concentration() -> None:
    """Batch 4 old case 1: the d4 is causal, one-use, and linked."""
    reset_spell_regression_arena(10, 6)
    caster = create_spell_regression_actor("Resistance Cleric", (1, 2), "heroes")
    target = create_spell_regression_actor("Resistance Ally", (2, 2), "heroes")
    Entity.update_all_entities_senses(max_distance=40)

    result = Resistance(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    ).apply()
    assert isinstance(result, SpellEvent)
    assert has_condition(target, "Resistance")
    assert has_condition(caster, "Concentrating")

    request = caster.create_saving_throw_request(
        target_entity_uuid=target.uuid,
        ability_name="wisdom",
        dc=12,
    )
    with (
        fixed_dice_faces(10),
        patch("dnd.spells.abjuration.random.randint", return_value=4),
    ):
        _, roll, _ = target.saving_throw(request)

    assert roll.total == 14
    assert not has_condition(target, "Resistance")
    assert not has_condition(caster, "Concentrating")


@pytest.mark.parametrize(
    ("cast_at_level", "expected_damage"),
    ((1, 12), (3, 20)),
)
def test_inflict_wounds_hit_and_upcast_dice(
    cast_at_level: int,
    expected_damage: int,
) -> None:
    """Batch 4 old case 2: hit damage is 3d10 plus one die per upcast."""
    reset_spell_regression_arena(10, 6)
    caster = create_spell_regression_actor(
        "Wounds Cleric",
        (2, 2),
        "heroes",
        spell_slots={cast_at_level: 1},
    )
    target = create_spell_regression_actor("Wounds Target", (3, 2), "monsters")
    force_save_result(target, "wisdom", succeeds=False)
    Entity.update_all_entities_senses(max_distance=40)
    hit_modifier = force_attack_hit(caster)

    try:
        with fixed_dice_faces(10, *([4] * (2 + cast_at_level))):
            result = InflictWounds(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                cast_at_level=cast_at_level,
            ).apply()
    finally:
        remove_attack_modifier(caster, hit_modifier)

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert result.total_damage == expected_damage
    assert result.damage_types == [DamageType.NECROTIC]


def test_inflict_wounds_miss_deals_no_damage() -> None:
    """Batch 4 old case 2: a missed melee spell attack has no damage child."""
    reset_spell_regression_arena(10, 6)
    caster = create_spell_regression_actor(
        "Wounds Cleric",
        (2, 2),
        "heroes",
        spell_slots={1: 1},
    )
    target = create_spell_regression_actor("Wounds Target", (3, 2), "monsters")
    caster.equipment.attack_bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=caster.uuid,
            name="Deterministic spell miss",
            value=-100,
        )
    )
    Entity.update_all_entities_senses(max_distance=40)
    hp_before = get_hp(target)

    with fixed_dice_faces(10):
        result = InflictWounds(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert result.total_damage == 0
    assert get_hp(target) == hp_before


def test_shield_of_faith_owns_bonus_action_ac_and_concentration_cleanup() -> None:
    """Batch 4 old case 3: all Shield of Faith state shares one owner."""
    reset_spell_regression_arena(10, 6)
    caster = create_spell_regression_actor(
        "Faith Cleric",
        (1, 2),
        "heroes",
        spell_slots={1: 1},
    )
    target = create_spell_regression_actor("Faith Ally", (2, 2), "heroes")
    Entity.update_all_entities_senses(max_distance=40)
    ac_before = target.ac_bonus().normalized_score

    result = ShieldOfFaith(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert target.ac_bonus().normalized_score == ac_before + 2
    assert caster.action_economy.bonus_actions.normalized_score == 0
    assert has_condition(caster, "Concentrating")
    caster.remove_condition("Concentrating")
    assert not has_condition(target, "Shield of Faith")
    assert target.ac_bonus().normalized_score == ac_before


@pytest.mark.parametrize(("cast_at_level", "hp_bonus"), ((2, 5), (4, 15)))
def test_aid_applies_multi_target_upcast_without_concentration(
    cast_at_level: int,
    hp_bonus: int,
) -> None:
    """Batch 4 old case 4: Aid's fixed target and upcast contract is explicit."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Aid Cleric",
        (1, 3),
        "heroes",
        spell_slots={cast_at_level: 1},
    )
    allies = [
        create_spell_regression_actor(f"Aid Ally {index}", (2 + index, 3), "heroes")
        for index in range(3)
    ]
    Entity.update_all_entities_senses(max_distance=40)
    max_before = {ally.uuid: get_max_hp(ally) for ally in allies}

    result = Aid(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=allies[0].uuid,
        extra_target_entity_uuids=[ally.uuid for ally in allies[1:]],
        cast_at_level=cast_at_level,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    for ally in allies:
        assert has_condition(ally, "Aid")
        assert get_max_hp(ally) == max_before[ally.uuid] + hp_bonus
    assert not has_condition(caster, "Concentrating")


def test_sanctuary_blocks_failed_attacker_save_and_breaks_on_attack() -> None:
    """Batch 4 old case 5: both the ward and self-break handlers execute."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Sanctuary Cleric",
        (1, 3),
        "heroes",
        spell_slots={1: 1},
    )
    ally = create_spell_regression_actor("Sanctuary Ally", (3, 3), "heroes")
    attacker = create_spell_regression_actor("Sanctuary Enemy", (4, 3), "monsters")
    _equip_dagger(ally)
    _equip_dagger(attacker)
    force_save_result(attacker, "wisdom", succeeds=False)
    Entity.update_all_entities_senses(max_distance=40)

    result = Sanctuary(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
    ).apply()
    assert isinstance(result, SpellEvent)
    assert has_condition(ally, "Sanctuary")
    assert not has_condition(caster, "Concentrating")

    blocked = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=ally.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()
    assert blocked is not None
    assert blocked.canceled
    assert has_condition(ally, "Sanctuary")

    hit_modifier = force_attack_hit(ally)
    try:
        with fixed_dice_faces(10, 2):
            attack = Attack(
                source_entity_uuid=ally.uuid,
                target_entity_uuid=attacker.uuid,
                weapon_slot=WeaponSlot.MELEE_MAIN,
            ).apply()
    finally:
        remove_attack_modifier(ally, hit_modifier)
    assert attack is not None
    assert not attack.canceled
    assert not has_condition(ally, "Sanctuary")


def test_beacon_of_hope_maximizes_heal_and_cleans_up() -> None:
    """Batch 4 old case 6: save advantage and heal maximization are linked."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Beacon Cleric",
        (1, 3),
        "heroes",
        wisdom=18,
        spellcasting_ability="wisdom",
        spell_slots={1: 1, 3: 1},
    )
    ally = create_spell_regression_actor("Beacon Ally", (2, 3), "heroes")
    Entity.update_all_entities_senses(max_distance=40)

    result = BeaconOfHope(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=3,
    ).apply()
    assert isinstance(result, SpellEvent)
    assert has_condition(ally, "Beacon of Hope")
    assert (
        ally.saving_throws.get_saving_throw("wisdom").bonus.advantage
        is AdvantageStatus.ADVANTAGE
    )

    caster.action_economy.reset_all_costs()
    set_hp(ally, 1)
    with fixed_dice_faces(1):
        healed = CureWounds(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
            cast_at_level=1,
        ).apply()
    assert isinstance(healed, SpellEvent)
    assert get_hp(ally) == 13

    caster.remove_condition("Concentrating")
    assert not has_condition(ally, "Beacon of Hope")
    assert (
        ally.saving_throws.get_saving_throw("wisdom").bonus.advantage
        is AdvantageStatus.NONE
    )


@pytest.mark.parametrize(("save_succeeds", "expected_hp"), ((False, 1), (True, 1)))
def test_harm_never_reduces_target_below_one(
    save_succeeds: bool,
    expected_hp: int,
) -> None:
    """Batch 4 old case 7: full and half Harm damage share the 1-HP floor."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Harm Cleric",
        (1, 3),
        "heroes",
        spell_slots={6: 1},
    )
    target = create_spell_regression_actor("Harm Target", (3, 3), "monsters")
    force_save_result(target, "constitution", succeeds=save_succeeds)
    Entity.update_all_entities_senses(max_distance=40)
    set_hp(target, 5)

    with fixed_dice_faces(10, *([6] * 14)):
        result = Harm(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=6,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert get_hp(target) == expected_hp
    assert result.total_damage == 4


@pytest.mark.parametrize(
    ("hp", "expected", "life_state"),
    (
        (60, frozenset(), LifeState.ALIVE),
        (45, frozenset({"Deafened"}), LifeState.ALIVE),
        (35, frozenset({"Blinded", "Deafened"}), LifeState.ALIVE),
        (25, frozenset({"Blinded", "Deafened", "Stunned"}), LifeState.ALIVE),
        (15, frozenset(), LifeState.DEAD),
    ),
)
def test_divine_word_hp_threshold_matrix(
    hp: int,
    expected: frozenset[str],
    life_state: LifeState,
) -> None:
    """Batch 4 old case 8: every HP threshold has an exact outcome."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Divine Cleric",
        (1, 3),
        "heroes",
        spell_slots={7: 1},
    )
    target = create_spell_regression_actor("Divine Target", (3, 3), "monsters")
    Entity.update_all_entities_senses(max_distance=40)
    set_hp(target, hp)

    result = DivineWord(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=7,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert target.health.life_state is life_state
    for condition_name in ("Blinded", "Deafened", "Stunned"):
        assert has_condition(target, condition_name) is (
            condition_name in expected
        )


def test_heroes_feast_object_and_buff_full_lifecycle() -> None:
    """Batch 4 old case 9: object use, buff, immunities, and cleanup are owned."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Feast Cleric",
        (1, 3),
        "heroes",
        spell_slots={6: 1},
    )
    ally = create_spell_regression_actor("Feast Ally", (2, 3), "heroes")
    Entity.update_all_entities_senses(max_distance=40)

    result = HeroesFeast(
        source_entity_uuid=caster.uuid,
        end_position=(2, 4),
        cast_at_level=6,
    ).apply()
    assert isinstance(result, SpellEvent)
    feast = next(
        obj
        for obj in (
            BaseBlock.get(object_uuid)
            for object_uuid in get_map().get_objects_at((2, 4))
        )
        if isinstance(obj, HeroesFeastObject)
    )
    ally.add_condition(
        Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
    )
    ally.add_condition(
        Frightened(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
    )
    max_before = get_max_hp(ally)

    actions = feast.get_use_actions(ally.uuid)
    assert len(actions) == 1
    with patch(
        "dnd.spells.conjuration.random.randint",
        side_effect=[4, 6],
    ):
        eaten = actions[0].apply()
    assert eaten is not None
    assert not eaten.canceled
    assert has_condition(ally, "Heroes' Feast")
    assert not has_condition(ally, "Poisoned")
    assert not has_condition(ally, "Frightened")
    assert get_max_hp(ally) == max_before + 10
    assert (
        ally.saving_throws.get_saving_throw("wisdom").bonus.advantage
        is AdvantageStatus.ADVANTAGE
    )
    assert feast.get_use_actions(ally.uuid) == []

    ally.add_condition(
        Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
    )
    ally.add_condition(
        Frightened(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
    )
    assert not has_condition(ally, "Poisoned")
    assert not has_condition(ally, "Frightened")

    ally.remove_condition("Heroes' Feast")
    ally.add_condition(
        Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
    )
    assert has_condition(ally, "Poisoned")


def test_condition_tag_magical_origin_compatibility_surface() -> None:
    """Batch 5 old case 1: the legacy property is derived only from tags."""
    source_uuid = uuid4()
    target_uuid = uuid4()
    assert BaseCondition(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        tags={ConditionTag.MAGICAL},
    ).magical_origin
    assert not BaseCondition(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        tags={ConditionTag.CURSE},
    ).magical_origin
    assert ShieldOfFaithEffect(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
    ).magical_origin


def test_bestow_curse_ability_and_contextual_attack_options() -> None:
    """Batch 5 old cases 3-4: options one and two affect only intended rolls."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor("Curse Caster", (1, 3), "heroes")
    target = create_spell_regression_actor("Curse Target", (2, 3), "monsters")
    other = create_spell_regression_actor("Other Target", (3, 3), "heroes")

    target.add_condition(
        AbilityCurseEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cursed_ability="strength",
        )
    )
    assert (
        target.saving_throws.get_saving_throw("strength").bonus.advantage
        is AdvantageStatus.DISADVANTAGE
    )
    assert (
        target.saving_throws.get_saving_throw("dexterity").bonus.advantage
        is AdvantageStatus.NONE
    )
    assert (
        target.skill_set.get_skill("athletics").skill_bonus.advantage
        is AdvantageStatus.DISADVANTAGE
    )

    target.remove_condition("Bestow Curse")
    target.add_condition(
        AttackCurseEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
        )
    )
    target.equipment.attack_bonus.set_target_entity(caster.uuid)
    assert (
        target.equipment.attack_bonus.advantage
        is AdvantageStatus.DISADVANTAGE
    )
    target.equipment.attack_bonus.set_target_entity(other.uuid)
    assert target.equipment.attack_bonus.advantage is AdvantageStatus.NONE
    target.equipment.attack_bonus.clear_target_entity()


def test_bestow_curse_inaction_option_spends_and_releases_one_action() -> None:
    """Batch 5 old case 5: option three has exact turn-start/end ownership."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor("Curse Caster", (1, 3), "heroes")
    target = create_spell_regression_actor("Curse Target", (2, 3), "monsters")
    force_save_result(target, "wisdom", succeeds=False)
    target.add_condition(
        InactionCurseEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            spell_dc=caster.spell_save_dc(),
        )
    )

    with fixed_dice_faces(10):
        target.on_turn_start(round_number=1, turn_index=0)
    assert target.action_economy.actions.normalized_score == 0
    target.on_turn_end(round_number=1, turn_index=0)
    assert target.action_economy.actions.normalized_score == 1
    assert has_condition(target, "Bestow Curse")


def test_bestow_curse_damage_option_adds_necrotic_damage_child() -> None:
    """Batch 5 old case 6: option four appends one audited 1d8 packet."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor("Curse Caster", (1, 3), "heroes")
    target = create_spell_regression_actor("Curse Target", (2, 3), "monsters")
    _equip_dagger(caster)
    target.add_condition(
        DamageCurseEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
        )
    )
    Entity.update_all_entities_senses(max_distance=40)
    hit_modifier = force_attack_hit(caster)

    try:
        with fixed_dice_faces(10, 2, 2, 2, 2, 2):
            result = Attack(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                weapon_slot=WeaponSlot.MELEE_MAIN,
            ).apply()
    finally:
        remove_attack_modifier(caster, hit_modifier)

    assert result is not None
    assert not result.canceled
    damage_events = [
        event
        for event in EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
        if (
            isinstance(event, TakeDamageEvent)
            and event.source_entity_uuid == caster.uuid
            and event.target_entity_uuid == target.uuid
            and event.phase is EventPhase.COMPLETION
        )
    ]
    damage_types = {
        damage.damage_type
        for event in damage_events
        for damage in event.damages
    }
    assert damage_types >= {
        DamageType.PIERCING,
        DamageType.NECROTIC,
    }
    completed_roll_events = [
        event
        for event in EventQueue.get_events_by_type(
            EventType.DAMAGE_ROLL_RESULT,
        )
        if (
            isinstance(event, DamageRollResultEvent)
            and event.source_entity_uuid == caster.uuid
            and event.target_entity_uuid == target.uuid
            and event.phase is EventPhase.COMPLETION
        )
    ]
    assert len(completed_roll_events) == 1
    damage_roll_event = completed_roll_events[0]
    assert [
        packet.damage.damage_type
        for packet in damage_roll_event.damage_packets
    ] == [DamageType.PIERCING, DamageType.NECROTIC]
    assert [
        modification.handler_name
        for modification in damage_roll_event.roll_modifications
    ] == ["Bestow Curse"]
    assert result.combat_log is not None
    roll_logs = [
        entry
        for entry in result.combat_log.sub_entries
        if entry.entry_type is CombatLogEntryType.ROLL_MODIFICATION
    ]
    assert len(roll_logs) == 1
    assert roll_logs[0].data["modifications"][0]["handler_name"] == "Bestow Curse"


def test_bestow_curse_concentration_and_remove_curse_reverse_cleanup() -> None:
    """Batch 5 old cases 7-8: either side of the link cleans the other."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Curse Caster",
        (1, 3),
        "heroes",
        spell_slots={3: 2},
    )
    remover = create_spell_regression_actor(
        "Curse Remover",
        (3, 3),
        "heroes",
        spell_slots={3: 1},
    )
    target = create_spell_regression_actor("Curse Target", (2, 3), "monsters")
    force_save_result(target, "wisdom", succeeds=False)
    Entity.update_all_entities_senses(max_distance=40)

    with fixed_dice_faces(10):
        first = BestowCurse(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            curse_option=1,
            cursed_ability="wisdom",
            cast_at_level=3,
        ).apply()
    assert isinstance(first, SpellEvent)
    assert has_condition(target, "Bestow Curse")
    assert has_condition(caster, "Concentrating")
    caster.remove_condition("Concentrating")
    assert not has_condition(target, "Bestow Curse")

    caster.action_economy.reset_all_costs()
    with fixed_dice_faces(10):
        second = BestowCurse(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            curse_option=2,
            cast_at_level=3,
        ).apply()
    assert isinstance(second, SpellEvent)
    assert has_condition(target, "Bestow Curse")
    assert has_condition(caster, "Concentrating")

    removed = RemoveCurse(
        source_entity_uuid=remover.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=3,
    ).apply()
    assert isinstance(removed, SpellEvent)
    assert not has_condition(target, "Bestow Curse")
    assert not has_condition(caster, "Concentrating")
