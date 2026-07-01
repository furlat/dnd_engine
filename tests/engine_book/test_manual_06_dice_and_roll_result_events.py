"""Manual Chapter 06 checks for dice and roll result events."""

from unittest.mock import patch
from uuid import UUID, uuid4

from dnd.core.base_object import BaseObject
from dnd.core.dice import AttackOutcome, Dice, DiceRoll, RollType
from dnd.core.events import (
    D20RollResultEvent,
    DamageRollResultEvent,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
    WeaponSlot,
)
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
    AutoHitStatus,
    CriticalStatus,
)
from dnd.core.values import BaseValue, ModifiableValue
from dnd.entity import determine_attack_outcome


def reset_dice_state() -> None:
    """Clear global state touched by primitive dice examples."""
    EventQueue.reset()
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    Dice._registry.clear()
    DiceRoll._registry.clear()


def test_plain_d20_and_advantage_selection() -> None:
    """Dice records raw d20 faces and selects advantage correctly."""
    reset_dice_state()
    hero_id = uuid4()
    goblin_id = uuid4()

    attack_bonus = ModifiableValue.create(
        source_entity_uuid=hero_id,
        target_entity_uuid=goblin_id,
        value_name="Attack Bonus",
        base_value=3,
    )
    with patch("random.randint", side_effect=[12]):
        normal_roll = Dice(
            count=1,
            value=20,
            bonus=attack_bonus,
            roll_type=RollType.ATTACK,
        ).roll

    assert normal_roll.results == [12]
    assert normal_roll.total == 15
    assert normal_roll.bonus == 3
    assert normal_roll.advantage_status == AdvantageStatus.NONE

    advantage_bonus = ModifiableValue.create(
        source_entity_uuid=hero_id,
        target_entity_uuid=goblin_id,
        value_name="Attack Bonus With Advantage",
        base_value=3,
    )
    advantage_bonus.self_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=hero_id,
            target_entity_uuid=goblin_id,
            name="High Ground",
            value=AdvantageStatus.ADVANTAGE,
        )
    )

    with patch("random.randint", side_effect=[4, 17]):
        advantage_roll = Dice(
            count=1,
            value=20,
            bonus=advantage_bonus,
            roll_type=RollType.ATTACK,
        ).roll

    assert advantage_roll.results == [4, 17]
    assert advantage_roll.total == 20
    assert advantage_roll.advantage_status == AdvantageStatus.ADVANTAGE


def test_critical_damage_doubles_dice_and_adds_bonus_once() -> None:
    """Critical damage doubles dice and adds flat bonus once."""
    reset_dice_state()
    hero_id = uuid4()
    goblin_id = uuid4()
    damage_bonus = ModifiableValue.create(
        source_entity_uuid=hero_id,
        target_entity_uuid=goblin_id,
        value_name="Damage Bonus",
        base_value=4,
    )

    with patch("random.randint", side_effect=[1, 2, 3, 4, 5]):
        critical_damage = Dice(
            count=2,
            value=6,
            bonus=damage_bonus,
            roll_type=RollType.DAMAGE,
            attack_outcome=AttackOutcome.CRIT,
            crit_extra_dice=1,
        ).roll

    assert critical_damage.results == [1, 2, 3, 4, 5]
    assert critical_damage.bonus == 4
    assert critical_damage.total == 19


def test_attack_natural_faces_are_not_check_natural_faces() -> None:
    """Attack rolls treat natural 1 and 20 specially; checks use totals."""
    reset_dice_state()
    hero_id = uuid4()
    goblin_id = uuid4()

    natural_one_attack = DiceRoll(
        dice_uuid=uuid4(),
        roll_type=RollType.ATTACK,
        results=[1],
        total=101,
        bonus=100,
        advantage_status=AdvantageStatus.NONE,
        critical_status=CriticalStatus.NONE,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=hero_id,
        target_entity_uuid=goblin_id,
    )

    assert determine_attack_outcome(natural_one_attack, 15) == AttackOutcome.CRIT_MISS

    natural_twenty_attack = natural_one_attack.model_copy(
        update={
            "roll_uuid": uuid4(),
            "results": [20],
            "total": 20,
            "bonus": 0,
        }
    )
    assert determine_attack_outcome(natural_twenty_attack, 120) == AttackOutcome.CRIT

    natural_twenty_check = natural_twenty_attack.model_copy(
        update={
            "roll_uuid": uuid4(),
            "roll_type": RollType.CHECK,
        }
    )
    assert determine_attack_outcome(natural_twenty_check, 30) == AttackOutcome.MISS


def test_d20_result_event_replaces_effective_roll() -> None:
    """D20 result handlers replace the effective roll and keep an audit entry."""
    reset_dice_state()
    hero_id = uuid4()
    goblin_id = uuid4()
    original_d20 = DiceRoll(
        dice_uuid=uuid4(),
        roll_type=RollType.CHECK,
        results=[3],
        total=5,
        bonus=2,
        advantage_status=AdvantageStatus.NONE,
        critical_status=CriticalStatus.NONE,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=hero_id,
        target_entity_uuid=goblin_id,
    )
    check_bonus = ModifiableValue.create(
        source_entity_uuid=hero_id,
        target_entity_uuid=goblin_id,
        value_name="Check Bonus",
        base_value=2,
    )

    def replace_low_d20(
        event: D20RollResultEvent,
        handler_source_id: UUID,
    ) -> D20RollResultEvent:
        replacement = event.get_effective_roll().model_copy(
            update={
                "roll_uuid": uuid4(),
                "results": [18],
                "total": 20,
            }
        )
        event.replace_roll(replacement, "Tutorial D20", "raise low roll")
        return event

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=hero_id,
            name="Tutorial D20 Replacement",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                )
            ],
            event_processor=replace_low_d20,
        )
    )

    roll_event = D20RollResultEvent(
        source_entity_uuid=hero_id,
        target_entity_uuid=goblin_id,
        roll_type=RollType.CHECK,
        roll=original_d20,
        original_roll=original_d20,
        bonus=check_bonus,
        phase=EventPhase.DECLARATION,
    )
    roll_event = roll_event.phase_to(EventPhase.EFFECT)

    assert roll_event.get_effective_roll().results == [18]
    assert roll_event.get_effective_roll().total == 20
    assert roll_event.roll_modifications == [
        ("Tutorial D20", "raise low roll (5 → 20)")
    ]


def test_damage_result_event_replaces_final_rolls_only() -> None:
    """Damage result handlers preserve originals and replace final rolls."""
    reset_dice_state()
    hero_id = uuid4()
    goblin_id = uuid4()
    original_damage = DiceRoll(
        dice_uuid=uuid4(),
        roll_type=RollType.DAMAGE,
        results=[1, 2],
        total=6,
        bonus=3,
        advantage_status=AdvantageStatus.NONE,
        critical_status=CriticalStatus.NONE,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=hero_id,
        target_entity_uuid=goblin_id,
        attack_outcome=AttackOutcome.HIT,
    )
    replacement_damage = original_damage.model_copy(
        update={
            "roll_uuid": uuid4(),
            "results": [4, 5],
            "total": 12,
        }
    )

    def replace_damage(
        event: DamageRollResultEvent,
        handler_source_id: UUID,
    ) -> DamageRollResultEvent:
        event.replace_roll(0, replacement_damage, "Tutorial Damage", "raise damage")
        return event

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=hero_id,
            name="Tutorial Damage Replacement",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.DAMAGE_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                )
            ],
            event_processor=replace_damage,
        )
    )

    damage_event = DamageRollResultEvent(
        source_entity_uuid=hero_id,
        target_entity_uuid=goblin_id,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        attack_outcome=AttackOutcome.HIT,
        damages=[],
        original_rolls=[original_damage],
        final_rolls=[original_damage],
        phase=EventPhase.DECLARATION,
    )
    damage_event = damage_event.phase_to(EventPhase.EFFECT)

    assert damage_event.original_rolls == [original_damage]
    assert damage_event.final_rolls == [replacement_damage]
    assert damage_event.roll_modifications == [
        ("Tutorial Damage", 0, 6, 12, "raise damage")
    ]
