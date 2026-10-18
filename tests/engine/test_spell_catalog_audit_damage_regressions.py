"""Desired attack-rider behavior found during the full spell catalog audit.

Boundary: Bestow Curse casts and native weapon/natural/spell-weapon attacks.
Input: deterministic hit/miss rolls, plus a native damage-admission refusal.
Output: HP, attack damage components and resource costs.
"""

import pytest

from dnd.actions import Attack
from dnd.monsters.traits import NaturalAttack
from dnd.core.creature_types import DamageType
from dnd.spells.evocation import FlameBlade
from tests.engine.test_spell_catalog_audit_gameplay_regressions import cast
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import DamageRollResultEvent, EventQueue, EventHandler, EventPhase, EventType, Trigger
from dnd.spells.necromancy import BestowCurse
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.engine.test_bg3_spell_hit_riders import equip
from tests.engine.test_roster_support_spells import game as game  # noqa: PLC0414 - pytest fixture re-export
from tests.manual.spell_regression_support import force_save_result


def cursed_attack_pair(game):
    caster = combatant(game)
    target = combatant(game, "Cursed enemy", (3, 2), "foes")
    equip(caster)
    force_save_result(target, "wisdom", succeeds=False)
    with fixed_dice_faces(8):
        result = BestowCurse(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            curse_option=4,
        ).apply()
    assert result is not None and not result.canceled
    assert "Bestow Curse" in target.active_conditions
    assert caster.action_economy.spell_slot_3.normalized_score == 2
    caster.action_economy.reset_all_costs()
    return caster, target


@pytest.mark.parametrize(
    "face,outcome,damage",
    [
        pytest.param(
            1, AttackOutcome.CRIT_MISS, 0,
        ),
        (2, AttackOutcome.MISS, 0),
        pytest.param(
            15, AttackOutcome.HIT, 4,
        ),
        (20, AttackOutcome.CRIT, 8),
    ],
)
def test_bestow_curse_adds_one_critical_aware_rider_only_on_a_hit(game, face, outcome, damage):
    caster, target = cursed_attack_pair(game)
    before = target.get_hp()
    with fixed_dice_faces(face, *([2] * 12)):
        result = Attack(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()
    assert result is not None and not result.canceled
    assert result.attack_outcome is outcome
    assert caster.action_economy.actions.normalized_score == 0
    actual_hp = target.get_hp()
    expected_hp = before - damage
    assert actual_hp == expected_hp


def test_bestow_curse_rider_is_part_of_the_attack_damage_result(game):
    caster, target = cursed_attack_pair(game)
    with fixed_dice_faces(15, *([2] * 12)):
        result = Attack(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()
    assert result is not None and not result.canceled
    component_count = len(result.damages)
    assert component_count == 2
    roll_count = len(result.damage_rolls)
    assert roll_count == 2
    assert result.damages[1].effect_origin is not None


def test_refusing_attack_damage_also_refuses_its_bestow_curse_rider(game):
    caster, target = cursed_attack_pair(game)

    def refuse(event, _):
        return event.cancel(status_message="Attack damage refused")

    target.add_event_handler(EventHandler(
        name="Audit damage admission refusal",
        source_entity_uuid=target.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.DAMAGE_ROLL_RESULT,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=caster.uuid,
            event_target_entity_uuid=target.uuid,
        )],
        event_processor=refuse,
    ))
    before = target.get_hp()
    with fixed_dice_faces(15, *([2] * 12)):
        result = Attack(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()
    assert result is not None and result.canceled
    actual_hp = target.get_hp()
    assert actual_hp == before


@pytest.mark.parametrize("kind", ["natural", "spell_weapon"])
def test_bestow_curse_uses_native_natural_and_spell_weapon_attack_packets(game, kind):
    caster = combatant(game)
    target = combatant(game, "Cursed enemy", (3,2), "foes")
    force_save_result(target, "wisdom", succeeds=False)
    cast(BestowCurse, caster, target, curse_option=4, cast_at_level=7)
    if kind == "spell_weapon":
        cast(FlameBlade, caster)
    caster.action_economy.reset_all_costs()
    action = NaturalAttack(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
        name="Claw", natural_dice_numbers=1, natural_damage_dice=4,
        natural_damage_type=DamageType.SLASHING, fixed_attack_bonus=20, fixed_damage_bonus=0) if kind == "natural" else Attack(
            source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, weapon_slot=WeaponSlot.MELEE_MAIN)
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(20, *([2]*30)):
        result = action.apply()
    outcome = result.attack_outcome
    rolled = [event for _,event in EventQueue.iter_events_since(cursor)
        if isinstance(event, DamageRollResultEvent) and event.phase is EventPhase.COMPLETION]
    packet, = rolled
    attack_kind = packet.attack_kind
    rider, = [component for component in packet.damage_packets if component.damage.damage_type is DamageType.NECROTIC]
    origin = rider.damage.effect_origin.source_id
    amount = rider.final_roll.total
    assert outcome is AttackOutcome.CRIT and attack_kind == ("natural" if kind == "natural" else "spell")
    assert origin == "spell.bestow_curse" and amount == 4


def test_ending_curse_concentration_releases_its_exact_attack_rider(game):
    caster, target = cursed_attack_pair(game)
    caster.remove_condition("Concentrating")
    caster.action_economy.reset_all_costs()
    with fixed_dice_faces(20, *([2]*20)):
        result = Attack(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN).apply()
    kinds = [component.damage_type for component in result.damages]
    assert DamageType.NECROTIC not in kinds
