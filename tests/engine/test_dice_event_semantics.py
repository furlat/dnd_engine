"""Engine semantic tests for dice rolls and roll-result events."""

from contextlib import contextmanager
from typing import Iterator
from uuid import UUID, uuid4
import random

import pytest

from dnd.core.base_object import BaseObject
from dnd.core.base_block import BaseBlock
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.dice import AttackOutcome, Dice, DiceRoll, RollType
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    AttackD20RollResultEvent,
    D20RollResultEvent,
    Damage,
    DamageRollPacket,
    DamageRollResultEvent,
    EventHandler,
    Event,
    EventPhase,
    EventQueue,
    EventType,
    Healing,
    HealEvent,
    HealRollResultEvent,
    RollModification,
    RollModificationOperation,
    SavingThrowD20RollResultEvent,
    SkillCheckD20RollResultEvent,
    Trigger,
)
from dnd.actions import Attack
from dnd.blocks.equipment import Shield, Weapon
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.content.runtime import HandlerDispatchOutcome
from dnd.classes.feats import LuckyFeature
from dnd.classes.fighter import GreatWeaponFighting
from dnd.core.gridmap import get_map, reset_map
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
)
from dnd.core.values import AutoHitStatus, BaseValue, CriticalStatus, ModifiableValue
from dnd.entity import Entity, EntityConfig, determine_attack_outcome
from dnd.items.armors import WOODEN_SHIELD_RECIPE
from dnd.items.weapons import (
    GREATSWORD_RECIPE,
    LONGSWORD_RECIPE,
    SHORTBOW_RECIPE,
    SHORTSWORD_RECIPE,
)
from dnd.spells.spell_utils import fire_heal_roll_result
from tests.engine.support import create_test_entity


@contextmanager
def fixed_randint(*results: int) -> Iterator[None]:
    """Temporarily replace random.randint with a deterministic sequence."""
    queued = list(results)
    original_randint = random.randint

    def deterministic_randint(low: int, high: int) -> int:
        if not queued:
            raise AssertionError("No deterministic random values left")
        value = queued.pop(0)
        assert low <= value <= high
        return value

    random.randint = deterministic_randint
    try:
        yield
    finally:
        random.randint = original_randint


def reset_dice_state() -> None:
    """Clear global state touched by these primitive dice examples."""
    EventQueue.reset()
    reset_map()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    Dice._registry.clear()
    DiceRoll._registry.clear()
    Entity._entity_registry.clear()


def make_bonus(
    source_uuid: UUID,
    target_uuid: UUID | None = None,
    base_value: int = 0,
) -> ModifiableValue:
    """Create a ModifiableValue bonus for deterministic dice tests."""
    return ModifiableValue.create(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        value_name="Dice Bonus",
        base_value=base_value,
    )


def make_damage_roll(
    source_uuid: UUID,
    target_uuid: UUID,
    results: list[int],
    bonus: int = 0,
) -> DiceRoll:
    """Create a damage roll with coherent total and default roll statuses."""
    return DiceRoll(
        dice_uuid=uuid4(),
        roll_type=RollType.DAMAGE,
        results=results,
        total=sum(results) + bonus,
        bonus=bonus,
        advantage_status=AdvantageStatus.NONE,
        critical_status=CriticalStatus.NONE,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        attack_outcome=AttackOutcome.HIT,
    )


def make_damage_packet(
    source_uuid: UUID,
    target_uuid: UUID,
    *,
    damage_type: DamageType = DamageType.SLASHING,
) -> Damage:
    """Create one typed damage packet for roll-result alignment tests."""
    return Damage(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        damage_dice=6,
        dice_numbers=1,
        damage_bonus=make_bonus(source_uuid, target_uuid),
        damage_type=damage_type,
    )


def make_damage_result_event(
    source_uuid: UUID,
    target_uuid: UUID,
    roll: DiceRoll,
    *,
    weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN,
) -> DamageRollResultEvent:
    """Create one canonical single-packet damage-result event."""
    return DamageRollResultEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        weapon_slot=weapon_slot,
        attack_outcome=AttackOutcome.HIT,
        damage_packets=[
            DamageRollPacket(
                damage=make_damage_packet(source_uuid, target_uuid),
                original_roll=roll,
                final_roll=roll,
            )
        ],
        phase=EventPhase.DECLARATION,
    )


def replacement_fact(
    handler_name: str,
    previous_total: int,
    final_total: int,
    reason: str,
    *,
    packet_index: int | None = None,
) -> RollModification:
    """Build one expected typed replacement audit fact."""
    return RollModification(
        operation=RollModificationOperation.REPLACE,
        handler_name=handler_name,
        packet_index=packet_index,
        previous_total=previous_total,
        final_total=final_total,
        reason=reason,
    )


def make_d20_roll(
    source_uuid: UUID,
    target_uuid: UUID,
    natural_roll: int,
    total: int,
    roll_type: RollType = RollType.ATTACK,
    critical_status: CriticalStatus = CriticalStatus.NONE,
    auto_hit_status: AutoHitStatus = AutoHitStatus.NONE,
) -> DiceRoll:
    """Create a d20 roll with explicit outcome statuses."""
    return DiceRoll(
        dice_uuid=uuid4(),
        roll_type=roll_type,
        results=[natural_roll],
        total=total,
        bonus=total - natural_roll,
        advantage_status=AdvantageStatus.NONE,
        critical_status=critical_status,
        auto_hit_status=auto_hit_status,
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
    )


def healing_test_entity(name: str = "Healing Target") -> Entity:
    """Create a deterministic entity with enough HP for healing examples."""
    return Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=EntityConfig(
            position=(0, 0),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=2,
                        mode="maximums",
                    )
                ]
            ),
        ),
    )


def test_eb_03_001_d20_advantage_and_disadvantage_select_rolls() -> None:
    """EB-03-001: d20 rolls record all d20s and use the selected die."""
    reset_dice_state()
    source_uuid = uuid4()
    target_uuid = uuid4()

    normal_bonus = make_bonus(source_uuid, target_uuid, base_value=3)
    with fixed_randint(12):
        normal_roll = Dice(
            count=1,
            value=20,
            bonus=normal_bonus,
            roll_type=RollType.ATTACK,
        ).roll
    assert normal_roll.results == [12]
    assert normal_roll.total == 15
    assert normal_roll.bonus == 3
    assert normal_roll.advantage_status == AdvantageStatus.NONE

    advantage_bonus = make_bonus(source_uuid, target_uuid, base_value=3)
    advantage_bonus.self_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=target_uuid,
            name="High Ground",
            value=AdvantageStatus.ADVANTAGE,
        )
    )
    with fixed_randint(4, 17):
        advantage_roll = Dice(
            count=1,
            value=20,
            bonus=advantage_bonus,
            roll_type=RollType.ATTACK,
        ).roll
    assert advantage_roll.results == [4, 17]
    assert advantage_roll.total == 20
    assert advantage_roll.advantage_status == AdvantageStatus.ADVANTAGE

    disadvantage_bonus = make_bonus(source_uuid, target_uuid, base_value=3)
    disadvantage_bonus.self_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=target_uuid,
            name="Obscured",
            value=AdvantageStatus.DISADVANTAGE,
        )
    )
    with fixed_randint(4, 17):
        disadvantage_roll = Dice(
            count=1,
            value=20,
            bonus=disadvantage_bonus,
            roll_type=RollType.ATTACK,
        ).roll
    assert disadvantage_roll.results == [4, 17]
    assert disadvantage_roll.total == 7
    assert disadvantage_roll.advantage_status == AdvantageStatus.DISADVANTAGE


def test_eb_03_002_critical_damage_doubles_dice_and_adds_bonus_once() -> None:
    """EB-03-002: critical damage doubles dice and keeps flat bonus once."""
    reset_dice_state()
    source_uuid = uuid4()
    target_uuid = uuid4()
    damage_bonus = make_bonus(source_uuid, target_uuid, base_value=4)

    with fixed_randint(1, 2, 3, 4, 5):
        roll = Dice(
            count=2,
            value=6,
            bonus=damage_bonus,
            roll_type=RollType.DAMAGE,
            attack_outcome=AttackOutcome.CRIT,
            crit_extra_dice=1,
        ).roll

    assert roll.results == [1, 2, 3, 4, 5]
    assert roll.bonus == 4
    assert roll.total == 19
    assert roll.attack_outcome == AttackOutcome.CRIT


def test_eb_03_003_d20_result_event_handlers_replace_effective_roll() -> None:
    """EB-03-003: D20 result handlers replace the effective roll at EFFECT."""
    reset_dice_state()
    source_uuid = uuid4()
    target_uuid = uuid4()
    bonus = make_bonus(source_uuid, target_uuid, base_value=2)
    original_roll = DiceRoll(
        dice_uuid=uuid4(),
        roll_type=RollType.CHECK,
        results=[3],
        total=5,
        bonus=2,
        advantage_status=AdvantageStatus.NONE,
        critical_status=CriticalStatus.NONE,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
    )

    def replace_low_roll(event: D20RollResultEvent, _: UUID) -> D20RollResultEvent:
        replacement = original_roll.model_copy(
            update={"roll_uuid": uuid4(), "results": [18], "total": 20}
        )
        return event.replace_roll(
            replacement,
            "Engine Book",
            "replace low d20",
        )

    handler = EventHandler(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Engine Book D20 Replacement",
        trigger_conditions=[
            Trigger(
                event_type=EventType.D20_ROLL_RESULT,
                event_phase=EventPhase.EFFECT,
            )
        ],
        event_processor=replace_low_roll,
    )
    EventQueue.add_event_handler(handler)

    event = D20RollResultEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        roll_type=RollType.CHECK,
        original_roll=original_roll,
        bonus=bonus,
        phase=EventPhase.DECLARATION,
    )
    event = event.phase_to(EventPhase.EFFECT)

    assert event.original_roll is original_roll
    assert event.final_roll is not None
    assert event.get_effective_roll().results == [18]
    assert event.get_effective_roll().total == 20
    assert event.roll_modifications == [
        replacement_fact("Engine Book", 5, 20, "replace low d20")
    ]


def test_eb_03_004_damage_result_event_replaces_effective_packet_roll_only() -> None:
    """EB-03-004: damage result handlers preserve originals and replace finals."""
    reset_dice_state()
    source_uuid = uuid4()
    target_uuid = uuid4()
    original_roll = make_damage_roll(source_uuid, target_uuid, [1, 2], bonus=3)
    replacement_roll = make_damage_roll(source_uuid, target_uuid, [4, 5], bonus=3)

    def replace_damage(
        event: DamageRollResultEvent,
        _: UUID,
    ) -> DamageRollResultEvent:
        return event.replace_roll(
            0,
            replacement_roll,
            "Engine Book",
            "raise damage",
        )

    handler = EventHandler(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Engine Book Damage Replacement",
        trigger_conditions=[
            Trigger(
                event_type=EventType.DAMAGE_ROLL_RESULT,
                event_phase=EventPhase.EFFECT,
            )
        ],
        event_processor=replace_damage,
    )
    EventQueue.add_event_handler(handler)

    event = make_damage_result_event(source_uuid, target_uuid, original_roll)
    event = event.phase_to(EventPhase.EFFECT)

    assert event.damage_packets[0].original_roll == original_roll
    assert event.damage_packets[0].final_roll == replacement_roll
    assert event.roll_modifications == [
        replacement_fact(
            "Engine Book",
            original_roll.total,
            replacement_roll.total,
            "raise damage",
            packet_index=0,
        )
    ]


def test_eb_03_005_dice_and_rolls_are_registered_by_uuid() -> None:
    """EB-03-005: Dice and DiceRoll instances register independently."""
    reset_dice_state()
    source_uuid = uuid4()
    bonus = make_bonus(source_uuid, base_value=0)

    with fixed_randint(9):
        dice = Dice(count=1, value=20, bonus=bonus, roll_type=RollType.CHECK)
        roll = dice.roll

    assert Dice.get(dice.uuid) is dice
    assert DiceRoll.get(roll.roll_uuid) is roll
    assert Dice.get(roll.roll_uuid) is None
    assert DiceRoll.get(dice.uuid) is None


def test_eb_03_006_dice_roll_is_cached_and_event_triggers_are_exact() -> None:
    """EB-03-006: dice cache one roll and event triggers match exact types."""
    reset_dice_state()
    source_uuid = uuid4()
    target_uuid = uuid4()
    bonus = make_bonus(source_uuid, target_uuid, base_value=0)

    with fixed_randint(9):
        dice = Dice(count=1, value=20, bonus=bonus, roll_type=RollType.CHECK)
        first_roll = dice.roll
        second_roll = dice.roll

    assert first_roll is second_roll
    assert first_roll.results == [9]

    trigger_count = {"base": 0, "attack": 0}

    def count_base(event: D20RollResultEvent, _: UUID) -> D20RollResultEvent:
        trigger_count["base"] += 1
        return event

    def count_attack(event: AttackD20RollResultEvent, _: UUID) -> AttackD20RollResultEvent:
        trigger_count["attack"] += 1
        return event

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Base D20 Counter",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                )
            ],
            event_processor=count_base,
        )
    )
    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Attack D20 Counter",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                )
            ],
            event_processor=count_attack,
        )
    )

    attack_roll = first_roll.model_copy(
        update={"roll_type": RollType.ATTACK},
    )
    attack_event = AttackD20RollResultEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        original_roll=attack_roll,
        bonus=bonus,
        phase=EventPhase.DECLARATION,
    )
    attack_event.phase_to(EventPhase.EFFECT)

    assert trigger_count == {"base": 0, "attack": 1}


def test_eb_03_007_natural_faces_are_special_only_for_attack_outcomes() -> None:
    """EB-03-007: saves and checks compare totals instead of natural faces."""
    reset_dice_state()
    source_uuid = uuid4()
    target_uuid = uuid4()

    attack_roll = DiceRoll(
        dice_uuid=uuid4(),
        roll_type=RollType.ATTACK,
        results=[1],
        total=101,
        bonus=100,
        advantage_status=AdvantageStatus.NONE,
        critical_status=CriticalStatus.NONE,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
    )
    save_roll = attack_roll.model_copy(
        update={"roll_uuid": uuid4(), "roll_type": RollType.SAVE}
    )
    natural_20_attack_roll = attack_roll.model_copy(
        update={
            "roll_uuid": uuid4(),
            "results": [20],
            "total": 20,
            "bonus": 0,
        }
    )
    check_roll = attack_roll.model_copy(
        update={
            "roll_uuid": uuid4(),
            "roll_type": RollType.CHECK,
            "results": [20],
            "total": 20,
            "bonus": 0,
        }
    )

    assert determine_attack_outcome(attack_roll, 15) == AttackOutcome.CRIT_MISS
    assert determine_attack_outcome(natural_20_attack_roll, 120) == AttackOutcome.CRIT
    assert determine_attack_outcome(save_roll, 15) == AttackOutcome.HIT
    assert determine_attack_outcome(check_roll, 30) == AttackOutcome.MISS


def test_eb_03_008_entity_roll_d20_uses_specific_result_events() -> None:
    """EB-03-008: Entity.roll_d20_event chooses specific result event types."""
    reset_dice_state()
    actor = Entity.create(
        source_entity_uuid=uuid4(),
        name="Roller",
        config=EntityConfig(position=(0, 0)),
    )
    target = Entity.create(
        source_entity_uuid=uuid4(),
        name="Target",
        config=EntityConfig(position=(1, 0)),
    )
    bonus = make_bonus(actor.uuid, target.uuid, base_value=0)

    with fixed_randint(11):
        attack_roll, attack_event = actor.roll_d20_event(
            bonus,
            RollType.ATTACK,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        )
    assert isinstance(attack_event, AttackD20RollResultEvent)
    assert attack_event.event_type == EventType.ATTACK_D20_ROLL_RESULT
    assert attack_event.phase == EventPhase.EFFECT
    assert attack_event.weapon_slot == WeaponSlot.MELEE_MAIN
    assert attack_roll is attack_event.get_effective_roll()

    with fixed_randint(12):
        save_roll, save_event = actor.roll_d20_event(
            bonus,
            RollType.SAVE,
            ability_name="dexterity",
        )
    assert isinstance(save_event, SavingThrowD20RollResultEvent)
    assert save_event.event_type == EventType.SAVE_D20_ROLL_RESULT
    assert save_event.ability_name == "dexterity"
    assert save_roll.total == 12

    with fixed_randint(13):
        check_roll, check_event = actor.roll_d20_event(
            bonus,
            RollType.CHECK,
            skill_name="athletics",
        )
    assert isinstance(check_event, SkillCheckD20RollResultEvent)
    assert check_event.event_type == EventType.CHECK_D20_ROLL_RESULT
    assert check_event.skill_name == "athletics"
    assert check_roll.total == 13

    with fixed_randint(14):
        neutral_save_roll, neutral_save_event = actor.roll_d20_event(
            bonus,
            RollType.SAVE,
        )
    assert isinstance(neutral_save_event, SavingThrowD20RollResultEvent)
    assert neutral_save_event.event_type == EventType.SAVE_D20_ROLL_RESULT
    assert neutral_save_event.ability_name is None
    assert neutral_save_event.roll_type == RollType.SAVE
    assert neutral_save_roll.total == 14

    def replace_attack_roll(
        event: AttackD20RollResultEvent,
        _: UUID,
    ) -> AttackD20RollResultEvent:
        replacement = event.get_effective_roll().model_copy(
            update={"roll_uuid": uuid4(), "results": [19], "total": 19}
        )
        return event.replace_roll(
            replacement,
            "Engine Book",
            "entity roll replacement",
        )

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=actor.uuid,
            name="Entity Roll Replacement",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=actor.uuid,
                )
            ],
            event_processor=replace_attack_roll,
        )
    )

    with fixed_randint(2):
        completed_roll = actor.roll_d20(
            bonus,
            RollType.ATTACK,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        )
    completion_events = [
        event for event in EventQueue._events_by_type[EventType.ATTACK_D20_ROLL_RESULT]
        if event.phase == EventPhase.COMPLETION
    ]
    completion_event = completion_events[-1]
    assert isinstance(completion_event, AttackD20RollResultEvent)
    assert completed_roll.total == 19
    assert completion_event.get_effective_roll().total == 19


def test_eb_03_019_d20_replacements_chain_after_simple_exact_handlers() -> None:
    """EB-03-019: d20 handlers chain effective rolls in queue order."""
    reset_dice_state()
    source_uuid = uuid4()
    target_uuid = uuid4()
    bonus = make_bonus(source_uuid, target_uuid, base_value=2)
    original_roll = make_d20_roll(
        source_uuid,
        target_uuid,
        natural_roll=3,
        total=5,
    )
    call_order: list[str] = []
    seen_effective_totals: list[tuple[str, int]] = []

    def replacement(event: D20RollResultEvent, total: int) -> DiceRoll:
        return event.get_effective_roll().model_copy(
            update={
                "roll_uuid": uuid4(),
                "results": [total],
                "total": total,
                "bonus": 0,
            }
        )

    def base_d20_handler(event: D20RollResultEvent, _: UUID) -> D20RollResultEvent:
        call_order.append("base")
        return event

    def filtered_source_handler(event: AttackD20RollResultEvent, _: UUID) -> AttackD20RollResultEvent:
        call_order.append("source")
        seen_effective_totals.append(("source", event.get_effective_roll().total))
        return event.replace_roll(
            replacement(event, 15),
            "Filtered Source Attack",
            "raise source",
        )

    def filtered_target_handler(event: AttackD20RollResultEvent, _: UUID) -> AttackD20RollResultEvent:
        call_order.append("target")
        seen_effective_totals.append(("target", event.get_effective_roll().total))
        return event.replace_roll(
            replacement(event, 18),
            "Filtered Target Attack",
            "raise target",
        )

    def simple_exact_handler(event: AttackD20RollResultEvent, _: UUID) -> AttackD20RollResultEvent:
        call_order.append("simple")
        seen_effective_totals.append(("simple", event.get_effective_roll().total))
        return event.replace_roll(
            replacement(event, 12),
            "Simple Exact Attack",
            "raise simple",
        )

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Filtered Source Attack Handler",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=source_uuid,
                )
            ],
            event_processor=filtered_source_handler,
        )
    )
    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Broad D20 Handler",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                )
            ],
            event_processor=base_d20_handler,
        )
    )
    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Filtered Target Attack Handler",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=target_uuid,
                )
            ],
            event_processor=filtered_target_handler,
        )
    )
    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Simple Exact Attack Handler",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                )
            ],
            event_processor=simple_exact_handler,
        )
    )

    event = AttackD20RollResultEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        original_roll=original_roll,
        bonus=bonus,
        phase=EventPhase.DECLARATION,
    )
    effect_event = event.phase_to(EventPhase.EFFECT)

    assert call_order == ["simple", "source", "target"]
    assert seen_effective_totals == [("simple", 5), ("source", 12), ("target", 15)]
    assert effect_event.original_roll is original_roll
    assert effect_event.get_effective_roll().total == 18
    assert effect_event.roll_modifications == [
        replacement_fact("Simple Exact Attack", 5, 12, "raise simple"),
        replacement_fact("Filtered Source Attack", 12, 15, "raise source"),
        replacement_fact("Filtered Target Attack", 15, 18, "raise target"),
    ]


def test_eb_03_009_attack_outcome_status_precedence_matrix() -> None:
    """EB-03-009: attack outcome statuses have explicit precedence."""
    reset_dice_state()
    source_uuid = uuid4()
    target_uuid = uuid4()

    assert determine_attack_outcome(
        make_d20_roll(
            source_uuid,
            target_uuid,
            natural_roll=20,
            total=20,
            auto_hit_status=AutoHitStatus.AUTOMISS,
        ),
        10,
    ) == AttackOutcome.MISS
    assert determine_attack_outcome(
        make_d20_roll(
            source_uuid,
            target_uuid,
            natural_roll=1,
            total=1,
            auto_hit_status=AutoHitStatus.AUTOHIT,
        ),
        30,
    ) == AttackOutcome.HIT
    assert determine_attack_outcome(
        make_d20_roll(
            source_uuid,
            target_uuid,
            natural_roll=1,
            total=1,
            critical_status=CriticalStatus.AUTOCRIT,
            auto_hit_status=AutoHitStatus.AUTOHIT,
        ),
        30,
    ) == AttackOutcome.CRIT
    assert determine_attack_outcome(
        make_d20_roll(
            source_uuid,
            target_uuid,
            natural_roll=20,
            total=20,
            critical_status=CriticalStatus.NOCRIT,
        ),
        30,
    ) == AttackOutcome.HIT
    assert determine_attack_outcome(
        make_d20_roll(
            source_uuid,
            target_uuid,
            natural_roll=19,
            total=25,
            critical_status=CriticalStatus.NOCRIT,
        ),
        10,
        crit_threshold=19,
    ) == AttackOutcome.HIT
    assert determine_attack_outcome(
        make_d20_roll(
            source_uuid,
            target_uuid,
            natural_roll=2,
            total=8,
            critical_status=CriticalStatus.AUTOCRIT,
        ),
        30,
    ) == AttackOutcome.MISS
    assert determine_attack_outcome(
        make_d20_roll(
            source_uuid,
            target_uuid,
            natural_roll=18,
            total=18,
        ),
        30,
        crit_threshold=18,
    ) == AttackOutcome.MISS


def test_eb_03_010_heal_roll_result_handlers_replace_final_roll() -> None:
    """EB-03-010: healing result processors replace the consumed heal roll."""
    reset_dice_state()
    caster_uuid = uuid4()
    target_uuid = uuid4()
    healing_bonus = make_bonus(caster_uuid, target_uuid, base_value=3)
    healing = Healing(
        source_entity_uuid=caster_uuid,
        target_entity_uuid=target_uuid,
        name="Engine Book Healing",
        healing_dice=8,
        dice_numbers=2,
        healing_bonus=healing_bonus,
    )
    parent_event = Event(
        source_entity_uuid=caster_uuid,
        target_entity_uuid=target_uuid,
        name="Engine Book Heal Parent",
        event_type=EventType.HEAL,
        phase=EventPhase.EFFECT,
    )

    def maximize_healing(
        event: HealRollResultEvent,
        _: UUID,
    ) -> HealRollResultEvent:
        replacement = event.final_roll.model_copy(
            update={"roll_uuid": uuid4(), "results": [8, 8], "total": 19}
        )
        return event.replace_roll(
            replacement,
            "Engine Book",
            "maximize healing",
        )

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=caster_uuid,
            target_entity_uuid=caster_uuid,
            name="Engine Book Healing Maximizer",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.HEAL_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=caster_uuid,
                )
            ],
            event_processor=maximize_healing,
        )
    )

    with fixed_randint(1, 2):
        final_roll = fire_heal_roll_result(
            caster_uuid,
            target_uuid,
            healing,
            parent_event,
            "Engine Book Heal",
        )

    heal_events = EventQueue._events_by_type[EventType.HEAL_ROLL_RESULT]
    effect_events = [event for event in heal_events if event.phase == EventPhase.EFFECT]
    effect_event = effect_events[-1]
    assert isinstance(effect_event, HealRollResultEvent)
    assert final_roll.results == [8, 8]
    assert final_roll.total == 19
    assert effect_event.original_roll.results == [1, 2]
    assert effect_event.original_roll.total == 6
    assert effect_event.final_roll is final_roll
    assert effect_event.roll_modifications == [
        replacement_fact("Engine Book", 6, 19, "maximize healing")
    ]


def test_eb_03_011_lucky_processor_spends_and_replaces_d20_deterministically() -> None:
    """EB-03-011: Lucky spends on low d20 totals and keeps the better roll."""
    reset_dice_state()
    actor = Entity.create(
        source_entity_uuid=uuid4(),
        name="Lucky Roller",
        config=EntityConfig(position=(0, 0)),
    )
    target = Entity.create(
        source_entity_uuid=uuid4(),
        name="Lucky Target",
        config=EntityConfig(position=(1, 0)),
    )
    actor.add_condition(
        LuckyFeature(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=actor.uuid,
        )
    )
    bonus = make_bonus(actor.uuid, target.uuid, base_value=0)
    resource = actor.action_economy.resources["luck_points"]

    with fixed_randint(5, 18):
        improved_roll = actor.roll_d20(
            bonus,
            RollType.CHECK,
            skill_name="athletics",
        )

    improved_event = [
        event for event in EventQueue.get_events_by_type(EventType.CHECK_D20_ROLL_RESULT)
        if isinstance(event, D20RollResultEvent)
        and event.phase == EventPhase.COMPLETION
    ][-1]
    assert improved_roll.total == 18
    assert resource.current == 2
    assert improved_event.original_roll.results == [5]
    assert improved_event.get_effective_roll().results == [18]
    assert improved_event.roll_modifications == [
        replacement_fact("Lucky", 5, 18, "Rerolled 5 -> 18")
    ]

    with fixed_randint(4, 1):
        worse_reroll = actor.roll_d20(
            bonus,
            RollType.CHECK,
            skill_name="athletics",
        )

    worse_event = [
        event for event in EventQueue.get_events_by_type(EventType.CHECK_D20_ROLL_RESULT)
        if isinstance(event, D20RollResultEvent)
        and event.phase == EventPhase.COMPLETION
    ][-1]
    assert worse_reroll.total == 4
    assert resource.current == 1
    assert worse_event.original_roll.results == [4]
    assert worse_event.get_effective_roll().results == [4]
    assert worse_event.roll_modifications == []

    with fixed_randint(10):
        good_roll = actor.roll_d20(
            bonus,
            RollType.CHECK,
            skill_name="athletics",
        )

    good_event = [
        event for event in EventQueue.get_events_by_type(EventType.CHECK_D20_ROLL_RESULT)
        if isinstance(event, D20RollResultEvent)
        and event.phase == EventPhase.COMPLETION
    ][-1]
    assert good_roll.total == 10
    assert resource.current == 1
    assert good_event.original_roll.results == [10]
    assert good_event.roll_modifications == []


def test_eb_03_012_damage_result_handlers_chain_in_dispatch_order() -> None:
    """EB-03-012: later damage handlers consume earlier final-roll changes."""
    reset_dice_state()
    source_uuid = uuid4()
    target_uuid = uuid4()
    original_roll = make_damage_roll(source_uuid, target_uuid, [1], bonus=0)
    first_roll = make_damage_roll(source_uuid, target_uuid, [3], bonus=0)
    second_roll = make_damage_roll(source_uuid, target_uuid, [5], bonus=0)
    seen_by_second: list[list[int] | int] = []

    def first_handler(
        event: DamageRollResultEvent,
        _: UUID,
    ) -> DamageRollResultEvent:
        return event.replace_roll(
            0,
            first_roll,
            "First Handler",
            "raise to three",
        )

    def second_handler(
        event: DamageRollResultEvent,
        _: UUID,
    ) -> DamageRollResultEvent:
        seen_by_second.append(event.damage_packets[0].final_roll.results)
        return event.replace_roll(
            0,
            second_roll,
            "Second Handler",
            "raise to five",
        )

    for name, processor in [
        ("First Handler", first_handler),
        ("Second Handler", second_handler),
    ]:
        EventQueue.add_event_handler(
            EventHandler(
                source_entity_uuid=source_uuid,
                target_entity_uuid=source_uuid,
                name=name,
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.DAMAGE_ROLL_RESULT,
                        event_phase=EventPhase.EFFECT,
                    )
                ],
                event_processor=processor,
            )
        )

    event = make_damage_result_event(source_uuid, target_uuid, original_roll)
    effect_event = event.phase_to(EventPhase.EFFECT)

    assert effect_event.damage_packets[0].original_roll == original_roll
    assert effect_event.damage_packets[0].final_roll == second_roll
    assert seen_by_second == [[3]]
    assert effect_event.roll_modifications == [
        replacement_fact(
            "First Handler",
            1,
            3,
            "raise to three",
            packet_index=0,
        ),
        replacement_fact(
            "Second Handler",
            3,
            5,
            "raise to five",
            packet_index=0,
        ),
    ]


def test_eb_03_013_great_weapon_fighting_filters_damage_result_events() -> None:
    """EB-03-013: GWF rerolls only eligible low melee weapon damage dice."""
    reset_dice_state()
    fighter = Entity.create(
        source_entity_uuid=uuid4(),
        name="GWF Fighter",
        config=EntityConfig(position=(0, 0)),
    )
    target = Entity.create(
        source_entity_uuid=uuid4(),
        name="GWF Target",
        config=EntityConfig(position=(1, 0)),
    )
    fighter.equipment.equip(
        materialize_item(
            GREATSWORD_RECIPE,
            fighter.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_MAIN,
    )
    fighter.equipment.equip(
        materialize_item(
            SHORTBOW_RECIPE,
            fighter.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.RANGED_MAIN,
    )
    fighter.add_condition(
        GreatWeaponFighting(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=fighter.uuid,
        )
    )

    low_roll = make_damage_roll(fighter.uuid, target.uuid, [1, 2, 5], bonus=0)
    with fixed_randint(1, 6):
        eligible_event = make_damage_result_event(
            fighter.uuid,
            target.uuid,
            low_roll,
        ).phase_to(EventPhase.EFFECT)

    assert eligible_event.damage_packets[0].final_roll.results == [1, 6, 5]
    assert eligible_event.damage_packets[0].final_roll.total == 12
    assert eligible_event.roll_modifications == [
        replacement_fact(
            "Great Weapon Fighting",
            8,
            12,
            "Rerolled: 1→1, 2→6",
            packet_index=0,
        )
    ]

    no_low_roll = make_damage_roll(fighter.uuid, target.uuid, [3, 4], bonus=0)
    no_low_event = make_damage_result_event(
        fighter.uuid,
        target.uuid,
        no_low_roll,
    ).phase_to(EventPhase.EFFECT)
    assert no_low_event.damage_packets[0].final_roll == no_low_roll
    assert no_low_event.roll_modifications == []

    ranged_low_roll = make_damage_roll(fighter.uuid, target.uuid, [1], bonus=0)
    ranged_event = make_damage_result_event(
        fighter.uuid,
        target.uuid,
        ranged_low_roll,
        weapon_slot=WeaponSlot.RANGED_MAIN,
    ).phase_to(EventPhase.EFFECT)
    assert ranged_event.damage_packets[0].final_roll == ranged_low_roll
    assert ranged_event.roll_modifications == []

    one_handed_fighter = Entity.create(
        source_entity_uuid=uuid4(),
        name="One-Handed GWF Filter",
        config=EntityConfig(position=(0, 1)),
    )
    one_handed_fighter.equipment.equip(
        materialize_item(
            SHORTSWORD_RECIPE,
            one_handed_fighter.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_MAIN,
    )
    one_handed_fighter.add_condition(
        GreatWeaponFighting(
            source_entity_uuid=one_handed_fighter.uuid,
            target_entity_uuid=one_handed_fighter.uuid,
        )
    )
    one_handed_low_roll = make_damage_roll(
        one_handed_fighter.uuid,
        target.uuid,
        [2],
        bonus=0,
    )
    one_handed_event = make_damage_result_event(
        one_handed_fighter.uuid,
        target.uuid,
        one_handed_low_roll,
    ).phase_to(EventPhase.EFFECT)
    assert one_handed_event.damage_packets[0].final_roll == one_handed_low_roll
    assert one_handed_event.roll_modifications == []


def test_eb_03_014_real_attack_pipeline_applies_modified_damage_rolls() -> None:
    """EB-03-014: attack damage consumes DamageRollResultEvent final rolls."""
    reset_dice_state()
    get_map().create_rectangle(0, 0, 6, 6)
    attacker = create_test_entity(
        source_id=uuid4(),
        name="Pipeline Fighter",
        config=EntityConfig(position=(1, 1)),
    )
    target = create_test_entity(
        source_id=uuid4(),
        name="Pipeline Target",
        config=EntityConfig(position=(2, 1)),
    )
    attacker.equipment.equip(
        materialize_item(
            GREATSWORD_RECIPE,
            attacker.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_MAIN,
    )
    attacker.add_condition(
        GreatWeaponFighting(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=attacker.uuid,
        )
    )
    Entity.update_all_entities_senses(max_distance=10)
    initial_hp = target.get_hp()

    with fixed_randint(15, 1, 2, 5, 1):
        attack_event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert attack_event is not None
    assert attack_event.attack_outcome == AttackOutcome.HIT
    assert attack_event.damage_rolls is not None
    assert len(attack_event.damage_rolls) == 1
    assert attack_event.damage_rolls[0].results == [5, 1]
    assert attack_event.damage_rolls[0].total == 6
    assert initial_hp - target.get_hp() == 6

    damage_event = [
        event for event in EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)
        if isinstance(event, DamageRollResultEvent)
        and event.phase == EventPhase.COMPLETION
    ][-1]
    assert damage_event.damage_packets[0].original_roll.results == [1, 2]
    assert damage_event.damage_packets[0].final_roll.results == [5, 1]
    assert damage_event.roll_modifications == [
        replacement_fact(
            "Great Weapon Fighting",
            3,
            6,
            "Rerolled: 1→5, 2→1",
            packet_index=0,
        )
    ]
    assert attack_event.combat_log is not None
    modification_logs = [
        child
        for child in attack_event.combat_log.sub_entries
        if child.entry_type is CombatLogEntryType.ROLL_MODIFICATION
    ]
    assert len(modification_logs) == 1
    assert modification_logs[0] is damage_event.combat_log
    assert modification_logs[0].data["modifications"][0]["handler_name"] == (
        "Great Weapon Fighting"
    )


def test_eb_03_015_heal_roll_result_events_complete_after_handlers() -> None:
    """EB-03-015: heal roll-result helpers complete the result event."""
    reset_dice_state()
    caster_uuid = uuid4()
    target_uuid = uuid4()
    healing_bonus = make_bonus(caster_uuid, target_uuid, base_value=0)
    healing = Healing(
        source_entity_uuid=caster_uuid,
        target_entity_uuid=target_uuid,
        name="Engine Book Healing Completion",
        healing_dice=4,
        dice_numbers=1,
        healing_bonus=healing_bonus,
    )
    parent_event = Event(
        source_entity_uuid=caster_uuid,
        target_entity_uuid=target_uuid,
        name="Engine Book Heal Completion Parent",
        event_type=EventType.HEAL,
        phase=EventPhase.EFFECT,
    )

    with fixed_randint(3):
        final_roll = fire_heal_roll_result(
            caster_uuid,
            target_uuid,
            healing,
            parent_event,
            "Engine Book Heal Completion",
        )

    heal_events = [
        event for event in EventQueue.get_events_by_type(EventType.HEAL_ROLL_RESULT)
        if isinstance(event, HealRollResultEvent)
    ]
    assert [event.phase for event in heal_events] == [
        EventPhase.DECLARATION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    completion_event = heal_events[-1]
    assert completion_event.final_roll is final_roll
    assert completion_event.final_roll.results == [3]
    assert completion_event.parent_event == parent_event.uuid
    assert completion_event.parent_lineage == parent_event.lineage_uuid


def test_eb_03_018_heal_event_effect_handlers_define_applied_healing() -> None:
    """EB-03-018: HealEvent EFFECT handlers can reduce or cancel healing."""
    reset_dice_state()
    healer_uuid = uuid4()
    target = healing_test_entity()
    target.receive_damage(
        amount=10,
        damage_type=DamageType.SLASHING,
        source_entity_uuid=healer_uuid,
    )
    hp_after_damage = target.get_hp()

    def reduce_healing(event: HealEvent, _: UUID) -> HealEvent:
        return event.model_copy(
            update={
                "total_healing": 4,
                "modified": True,
                "status_message": "Engine Book reduced healing",
            }
        )

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=healer_uuid,
            target_entity_uuid=healer_uuid,
            name="Engine Book Healing Reducer",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.HEAL,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=healer_uuid,
                    event_target_entity_uuid=target.uuid,
                )
            ],
            event_processor=reduce_healing,
        )
    )

    actual_healing = target.receive_healing(
        amount=9,
        source_entity_uuid=healer_uuid,
        source_description="Engine Book reduced heal",
    )

    heal_completion = [
        event for event in EventQueue.get_events_by_type(EventType.HEAL)
        if isinstance(event, HealEvent)
        and event.phase == EventPhase.COMPLETION
    ][-1]
    assert actual_healing == 4
    assert target.get_hp() == hp_after_damage + 4
    assert heal_completion.total_healing == 4
    assert heal_completion.actual_healing == 4
    assert heal_completion.resulting_hp == target.get_hp()

    reset_dice_state()
    blocking_healer_uuid = uuid4()
    blocked_target = healing_test_entity("Blocked Healing Target")
    blocked_target.receive_damage(
        amount=10,
        damage_type=DamageType.SLASHING,
        source_entity_uuid=blocking_healer_uuid,
    )
    blocked_hp_after_damage = blocked_target.get_hp()

    def cancel_healing(event: HealEvent, _: UUID) -> HealEvent:
        return event.cancel(status_message="Engine Book canceled healing")

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=blocking_healer_uuid,
            target_entity_uuid=blocking_healer_uuid,
            name="Engine Book Healing Canceler",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.HEAL,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=blocking_healer_uuid,
                    event_target_entity_uuid=blocked_target.uuid,
                )
            ],
            event_processor=cancel_healing,
        )
    )

    canceled_healing = blocked_target.receive_healing(
        amount=9,
        source_entity_uuid=blocking_healer_uuid,
        source_description="Engine Book canceled heal",
    )
    canceled_completion = [
        event for event in EventQueue.get_events_by_type(EventType.HEAL)
        if isinstance(event, HealEvent)
        and event.phase == EventPhase.COMPLETION
    ][-1]
    assert canceled_healing == 0
    assert blocked_target.get_hp() == blocked_hp_after_damage
    assert canceled_completion.canceled is True
    assert canceled_completion.actual_healing == 0
    assert canceled_completion.resulting_hp == blocked_hp_after_damage


def test_eb_03_016_attack_d20_slot_and_gwf_extra_packet_boundaries() -> None:
    """EB-03-016: real attacks preserve d20 slot and GWF packet boundaries."""
    reset_dice_state()
    get_map().create_rectangle(0, 0, 6, 6)
    attacker = create_test_entity(
        source_id=uuid4(),
        name="Boundary Fighter",
        config=EntityConfig(position=(1, 1)),
    )
    target = create_test_entity(
        source_id=uuid4(),
        name="Boundary Target",
        config=EntityConfig(position=(2, 1)),
    )
    attacker.equipment.equip(
        materialize_item(
            GREATSWORD_RECIPE,
            attacker.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_MAIN,
    )
    attacker.equipment.extra_attack_damage_dices.append(4)
    attacker.equipment.extra_attack_damage_dices_numbers.append(1)
    attacker.equipment.extra_attack_damage_bonus.append(
        make_bonus(attacker.uuid, target.uuid, base_value=0)
    )
    attacker.equipment.extra_attack_damage_type.append(DamageType.RADIANT)
    attacker.add_condition(
        GreatWeaponFighting(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=attacker.uuid,
        )
    )
    Entity.update_all_entities_senses(max_distance=10)

    with fixed_randint(15, 1, 2, 1, 6, 5):
        attack_event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert attack_event is not None
    assert attack_event.damage_rolls is not None
    assert [roll.results for roll in attack_event.damage_rolls] == [[6, 5], [1]]
    assert [roll.total for roll in attack_event.damage_rolls] == [11, 1]

    d20_event = [
        event for event in EventQueue.get_events_by_type(EventType.ATTACK_D20_ROLL_RESULT)
        if isinstance(event, AttackD20RollResultEvent)
        and event.phase == EventPhase.COMPLETION
    ][-1]
    assert d20_event.weapon_slot == WeaponSlot.MELEE_MAIN

    damage_event = [
        event for event in EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)
        if isinstance(event, DamageRollResultEvent)
        and event.phase == EventPhase.COMPLETION
    ][-1]
    assert [
        packet.damage.damage_dice
        for packet in damage_event.damage_packets
    ] == [6, 4]
    assert [
        packet.original_roll.results
        for packet in damage_event.damage_packets
    ] == [[1, 2], [1]]
    assert [
        packet.final_roll.results
        for packet in damage_event.damage_packets
    ] == [[6, 5], [1]]
    assert damage_event.roll_modifications == [
        replacement_fact(
            "Great Weapon Fighting",
            3,
            11,
            "Rerolled: 1→6, 2→5",
            packet_index=0,
        )
    ]


def test_eb_03_017_gwf_requires_versatile_weapon_to_be_two_handed() -> None:
    """EB-03-017: versatile weapons need a free off hand for GWF."""
    reset_dice_state()
    attacker = Entity.create(
        source_entity_uuid=uuid4(),
        name="Versatile Fighter",
        config=EntityConfig(position=(0, 0)),
    )
    target = Entity.create(
        source_entity_uuid=uuid4(),
        name="Versatile Target",
        config=EntityConfig(position=(1, 0)),
    )
    attacker.equipment.equip(
        materialize_item(
            LONGSWORD_RECIPE,
            attacker.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_MAIN,
    )
    attacker.equipment.equip(
        materialize_item(
            WOODEN_SHIELD_RECIPE,
            attacker.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Shield,
        ),
        WeaponSlot.MELEE_OFF,
    )
    attacker.add_condition(
        GreatWeaponFighting(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=attacker.uuid,
        )
    )

    shielded_low_roll = make_damage_roll(attacker.uuid, target.uuid, [1], bonus=0)
    shielded_event = make_damage_result_event(
        attacker.uuid,
        target.uuid,
        shielded_low_roll,
    ).phase_to(EventPhase.EFFECT)

    assert shielded_event.damage_packets[0].final_roll == shielded_low_roll
    assert shielded_event.roll_modifications == []

    attacker.equipment.unequip(WeaponSlot.MELEE_OFF)

    unshielded_low_roll = make_damage_roll(attacker.uuid, target.uuid, [1], bonus=0)
    with fixed_randint(7):
        unshielded_event = make_damage_result_event(
            attacker.uuid,
            target.uuid,
            unshielded_low_roll,
        ).phase_to(EventPhase.EFFECT)

    assert unshielded_event.damage_packets[0].final_roll.results == [7]
    assert unshielded_event.roll_modifications == [
        replacement_fact(
            "Great Weapon Fighting",
            1,
            7,
            "Rerolled: 1→7",
            packet_index=0,
        )
    ]


def test_roll_modification_and_damage_packet_contracts_fail_closed() -> None:
    """Dice audit facts and damage packet ledgers reject ambiguous shapes."""
    source_uuid = uuid4()
    target_uuid = uuid4()
    damage_roll = make_damage_roll(source_uuid, target_uuid, [4])
    check_roll = make_d20_roll(
        source_uuid,
        target_uuid,
        natural_roll=4,
        total=4,
        roll_type=RollType.CHECK,
    )

    with pytest.raises(ValueError, match="replacement requires previous_total"):
        RollModification(
            operation=RollModificationOperation.REPLACE,
            handler_name="Invalid Replacement",
            final_total=4,
            reason="missing prior value",
        )
    with pytest.raises(ValueError, match="append requires packet_index"):
        RollModification(
            operation=RollModificationOperation.APPEND,
            handler_name="Invalid Append",
            final_total=4,
            reason="missing packet identity",
        )
    with pytest.raises(ValueError, match="at least 1 item"):
        DamageRollResultEvent(
            source_entity_uuid=source_uuid,
            target_entity_uuid=target_uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
            attack_outcome=AttackOutcome.HIT,
            damage_packets=[],
        )
    with pytest.raises(ValueError, match="original_roll must be a damage roll"):
        DamageRollPacket(
            damage=make_damage_packet(source_uuid, target_uuid),
            original_roll=check_roll,
            final_roll=damage_roll,
        )
    check_event = D20RollResultEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        roll_type=RollType.CHECK,
        original_roll=check_roll,
    )
    with pytest.raises(
        ValueError,
        match="replacement roll must match event roll_type",
    ):
        check_event.replace_roll(
            damage_roll,
            "Invalid Replacement",
            "wrong roll category",
        )


def test_functional_roll_replacement_is_reported_as_modified_handler_evidence() -> None:
    """A real roll transform must not be misclassified as handler no-op."""
    reset_dice_state()
    source_uuid = uuid4()
    target_uuid = uuid4()
    original_roll = make_d20_roll(
        source_uuid,
        target_uuid,
        natural_roll=4,
        total=4,
        roll_type=RollType.CHECK,
    )
    replacement = make_d20_roll(
        source_uuid,
        target_uuid,
        natural_roll=14,
        total=14,
        roll_type=RollType.CHECK,
    )
    dispatch_outcomes: list[HandlerDispatchOutcome] = []

    EventQueue.add_on_handler_dispatch_callback(
        lambda evidence: dispatch_outcomes.append(evidence.outcome)
    )
    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Official Roll Transformer",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CHECK_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                )
            ],
            event_processor=lambda event, _: event.replace_roll(
                replacement,
                "Official Roll Transformer",
                "raise the check",
            ),
        )
    )

    result = SkillCheckD20RollResultEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        skill_name="athletics",
        original_roll=original_roll,
        phase=EventPhase.DECLARATION,
    ).phase_to(EventPhase.EFFECT)

    assert result.get_effective_roll() == replacement
    assert dispatch_outcomes == [HandlerDispatchOutcome.MODIFIED_EVENT]


def test_modified_result_emits_typed_combat_log_and_unmodified_result_is_silent() -> None:
    """Only a real roll transform produces a structured combat-log child."""
    reset_dice_state()
    source_uuid = uuid4()
    target_uuid = uuid4()
    original_roll = make_d20_roll(
        source_uuid,
        target_uuid,
        natural_roll=6,
        total=8,
        roll_type=RollType.CHECK,
    )
    replacement_roll = make_d20_roll(
        source_uuid,
        target_uuid,
        natural_roll=6,
        total=11,
        roll_type=RollType.CHECK,
    )

    unmodified = SkillCheckD20RollResultEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        source_entity_name="Scout",
        target_entity_name="Locked Door",
        skill_name="perception",
        original_roll=original_roll,
        phase=EventPhase.DECLARATION,
    ).phase_to(EventPhase.COMPLETION)

    modified = SkillCheckD20RollResultEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        source_entity_name="Scout",
        target_entity_name="Locked Door",
        skill_name="perception",
        original_roll=original_roll,
        phase=EventPhase.DECLARATION,
    ).replace_roll(
        replacement_roll,
        "Guidance",
        "+3 (1d4)",
    ).phase_to(EventPhase.COMPLETION)

    assert unmodified.combat_log is None
    assert modified.combat_log is not None
    assert modified.combat_log.entry_type is CombatLogEntryType.ROLL_MODIFICATION
    assert modified.combat_log.source_name == "Scout"
    assert modified.combat_log.target_name == "Locked Door"
    assert modified.combat_log.data == {
        "roll_type": "check",
        "modifications": [
            {
                "operation": "replace",
                "handler_name": "Guidance",
                "packet_index": None,
                "previous_total": 8,
                "final_total": 11,
                "reason": "+3 (1d4)",
                "packet_damage_type": None,
                "packet_dice": None,
            }
        ],
    }
    assert "Guidance" in modified.combat_log.compact
    assert "8" in modified.combat_log.verbose
    assert "11" in modified.combat_log.verbose


def test_damage_packet_modification_log_nests_under_its_causal_parent() -> None:
    """A damage append remains under the owning action with packet metadata."""
    reset_dice_state()
    source_uuid = uuid4()
    target_uuid = uuid4()
    parent = Event(
        name="Parent Attack",
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        source_entity_name="Paladin",
        target_entity_name="Fiend",
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        combat_log=CombatLogEntry(
            entry_type=CombatLogEntryType.ATTACK,
            source_name="Paladin",
            source_uuid=str(source_uuid),
            target_name="Fiend",
            target_uuid=str(target_uuid),
            compact="Paladin attacks Fiend",
            verbose="Paladin attacks Fiend",
            detailed="Paladin attacks Fiend",
        ),
    )
    weapon_roll = make_damage_roll(source_uuid, target_uuid, [5])
    smite_roll = make_damage_roll(source_uuid, target_uuid, [6, 7])
    result = make_damage_result_event(
        source_uuid,
        target_uuid,
        weapon_roll,
    ).model_copy(update={
        "source_entity_name": "Paladin",
        "target_entity_name": "Fiend",
        "parent_event": parent.uuid,
    }).append_damage_roll(
        make_damage_packet(
            source_uuid,
            target_uuid,
            damage_type=DamageType.RADIANT,
        ).model_copy(update={"damage_dice": 8, "dice_numbers": 2}),
        smite_roll,
        "Divine Smite",
        "Level 1 spell slot",
    ).phase_to(EventPhase.COMPLETION)
    parent_completion = (
        parent.phase_to(EventPhase.EXECUTION)
        .phase_to(EventPhase.EFFECT)
        .phase_to(EventPhase.COMPLETION)
    )

    assert result.combat_log is not None
    assert result.combat_log.data["modifications"][0] == {
        "operation": "append",
        "handler_name": "Divine Smite",
        "packet_index": 1,
        "previous_total": None,
        "final_total": 13,
        "reason": "Level 1 spell slot",
        "packet_damage_type": "radiant",
        "packet_dice": "2d8",
    }
    assert parent_completion.combat_log is not None
    assert [
        entry.entry_type for entry in parent_completion.combat_log.sub_entries
    ] == [CombatLogEntryType.ROLL_MODIFICATION]
