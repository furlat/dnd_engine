"""Tutorial tests for dice expressions and concrete roll results."""

from uuid import uuid4
from pydantic import ValidationError

from dnd.core.base_object import BaseObject
from dnd.types.rolls import AttackOutcome, RollType
from dnd.core.dice import Dice, DiceRoll, fixed_dice_faces
from dnd.core.modifiers import AdvantageModifier, AutoHitModifier, CriticalModifier
from dnd.types.rolls import AdvantageStatus, AutoHitStatus, CriticalStatus
from dnd.core.values import BaseValue, ModifiableValue


def reset_dice_state() -> None:
    """Clear global indexes touched by these dice examples."""
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    Dice._registry.clear()
    DiceRoll._registry.clear()


def test_first_dice_example_prints_visible_roll_record(capsys) -> None:
    """One d20 result prints its face, bonus, total, cache, and lookup state."""
    reset_dice_state()

    hero_id = uuid4()
    attack_bonus = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="Attack Bonus",
        base_value=5,
    )
    d20 = Dice(
        count=1,
        value=20,
        bonus=attack_bonus,
        roll_type=RollType.ATTACK,
    )

    with fixed_dice_faces(13):
        roll = d20.roll

    cache_state = "same roll" if roll is d20.roll else "new roll"
    lookup_state = (
        "registered"
        if Dice.get(d20.uuid) is d20 and DiceRoll.get(roll.roll_uuid) is roll
        else "missing"
    )
    readout_lines = [
        f"roll type: {roll.roll_type.value}",
        f"faces rolled: {roll.results}",
        f"bonus used: {roll.bonus}",
        f"total: {roll.total}",
        f"cached result: {cache_state}",
        f"lookup result: {lookup_state}",
    ]

    print("\n".join(readout_lines))

    expected_lines = [
        "roll type: Attack",
        "faces rolled: [13]",
        "bonus used: 5",
        "total: 18",
        "cached result: same roll",
        "lookup result: registered",
    ]
    assert readout_lines == expected_lines
    assert roll.source_entity_uuid == hero_id
    assert roll.target_entity_uuid is None
    assert capsys.readouterr().out.splitlines() == expected_lines


def test_d20_roll_records_print_result_bonus_total_and_identity(capsys) -> None:
    """A d20 expression prints one cached DiceRoll with source metadata."""
    reset_dice_state()
    hero_id = uuid4()

    attack_bonus = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="Attack Bonus",
        base_value=5,
    )
    d20 = Dice(
        count=1,
        value=20,
        bonus=attack_bonus,
        roll_type=RollType.ATTACK,
    )

    with fixed_dice_faces(13):
        roll = d20.roll

    assert roll is d20.roll
    assert Dice.get(d20.uuid) is d20
    assert DiceRoll.get(roll.roll_uuid) is roll

    assert roll.dice_uuid == d20.uuid
    assert roll.roll_type == RollType.ATTACK
    assert roll.results == [13]
    assert roll.bonus == 5
    assert roll.total == 18
    assert roll.source_entity_uuid == hero_id
    assert roll.target_entity_uuid is None

    cached_lines = [
        f"dice expression registered: {Dice.get(d20.uuid) is d20}",
        f"roll record registered: {DiceRoll.get(roll.roll_uuid) is roll}",
        f"roll belongs to expression: {roll.dice_uuid == d20.uuid}",
        (
            "roll record: "
            f"type={roll.roll_type.value}, faces={roll.results}, "
            f"bonus={roll.bonus}, total={roll.total}"
        ),
        f"source copied: {roll.source_entity_uuid == hero_id}, target={roll.target_entity_uuid}",
    ]

    print("\n".join(cached_lines))

    expected_cached_lines = [
        "dice expression registered: True",
        "roll record registered: True",
        "roll belongs to expression: True",
        "roll record: type=Attack, faces=[13], bonus=5, total=18",
        "source copied: True, target=None",
    ]
    assert cached_lines == expected_cached_lines
    assert capsys.readouterr().out.splitlines() == expected_cached_lines


def test_advantage_and_disadvantage_print_both_d20_faces(capsys) -> None:
    """Advantage and disadvantage print both faces and selected totals."""
    reset_dice_state()
    hero_id = uuid4()

    advantaged_bonus = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="Attack Bonus",
        base_value=5,
    )
    advantaged_bonus.self_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=hero_id,
            name="High Ground",
            value=AdvantageStatus.ADVANTAGE,
        )
    )
    advantaged_d20 = Dice(
        count=1,
        value=20,
        bonus=advantaged_bonus,
        roll_type=RollType.ATTACK,
    )

    with fixed_dice_faces(4, 17):
        advantaged_roll = advantaged_d20.roll

    assert advantaged_roll.results == [4, 17]
    assert advantaged_roll.advantage_status == AdvantageStatus.ADVANTAGE
    assert advantaged_roll.total == 22

    disadvantaged_bonus = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="Attack Bonus",
        base_value=5,
    )
    disadvantaged_bonus.self_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=hero_id,
            name="Long Range",
            value=AdvantageStatus.DISADVANTAGE,
        )
    )
    disadvantaged_d20 = Dice(
        count=1,
        value=20,
        bonus=disadvantaged_bonus,
        roll_type=RollType.ATTACK,
    )

    with fixed_dice_faces(16, 3):
        disadvantaged_roll = disadvantaged_d20.roll

    assert disadvantaged_roll.results == [16, 3]
    assert disadvantaged_roll.advantage_status == AdvantageStatus.DISADVANTAGE
    assert disadvantaged_roll.total == 8

    advantage_lines = [
        (
            "advantage roll: "
            f"faces={advantaged_roll.results}, "
            f"state={advantaged_roll.advantage_status.value}, "
            f"total={advantaged_roll.total}"
        ),
        (
            "disadvantage roll: "
            f"faces={disadvantaged_roll.results}, "
            f"state={disadvantaged_roll.advantage_status.value}, "
            f"total={disadvantaged_roll.total}"
        ),
    ]

    print("\n".join(advantage_lines))

    expected_advantage_lines = [
        "advantage roll: faces=[4, 17], state=Advantage, total=22",
        "disadvantage roll: faces=[16, 3], state=Disadvantage, total=8",
    ]
    assert advantage_lines == expected_advantage_lines
    assert capsys.readouterr().out.splitlines() == expected_advantage_lines


def test_roll_state_snapshots_print_critical_and_auto_hit_flags(capsys) -> None:
    """DiceRoll prints roll-state flags from the bonus value at roll time."""
    reset_dice_state()
    hero_id = uuid4()

    attack_bonus = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="Attack Bonus",
        base_value=5,
    )
    attack_bonus.self_static.add_critical_modifier(
        CriticalModifier(
            source_entity_uuid=hero_id,
            name="Paralyzed Target",
            value=CriticalStatus.AUTOCRIT,
        )
    )
    attack_bonus.self_static.add_auto_hit_modifier(
        AutoHitModifier(
            source_entity_uuid=hero_id,
            name="Guided Strike",
            value=AutoHitStatus.AUTOHIT,
        )
    )
    d20 = Dice(
        count=1,
        value=20,
        bonus=attack_bonus,
        roll_type=RollType.ATTACK,
    )

    with fixed_dice_faces(12):
        roll = d20.roll

    assert roll.results == [12]
    assert roll.total == 17
    assert roll.critical_status == CriticalStatus.AUTOCRIT
    assert roll.auto_hit_status == AutoHitStatus.AUTOHIT

    snapshot_lines = [
        f"faces: {roll.results}",
        f"total: {roll.total}",
        f"critical snapshot: {roll.critical_status.value}",
        f"auto-hit snapshot: {roll.auto_hit_status.value}",
    ]

    print("\n".join(snapshot_lines))

    expected_snapshot_lines = [
        "faces: [12]",
        "total: 17",
        "critical snapshot: Autocrit",
        "auto-hit snapshot: Autohit",
    ]
    assert snapshot_lines == expected_snapshot_lines
    assert capsys.readouterr().out.splitlines() == expected_snapshot_lines


def test_damage_rolls_print_attack_outcome_and_critical_dice(capsys) -> None:
    """Damage dice print hit outcome and critical dice expansion."""
    reset_dice_state()
    hero_id = uuid4()

    damage_bonus = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="Damage Bonus",
        base_value=3,
    )
    normal_damage = Dice(
        count=2,
        value=6,
        bonus=damage_bonus,
        roll_type=RollType.DAMAGE,
        attack_outcome=AttackOutcome.HIT,
    )

    with fixed_dice_faces(2, 5):
        normal_roll = normal_damage.roll

    assert normal_roll.results == [2, 5]
    assert normal_roll.attack_outcome == AttackOutcome.HIT
    assert normal_roll.bonus == 3
    assert normal_roll.total == 10

    critical_damage = Dice(
        count=1,
        value=8,
        bonus=damage_bonus,
        roll_type=RollType.DAMAGE,
        attack_outcome=AttackOutcome.CRIT,
        crit_extra_dice=1,
    )

    with fixed_dice_faces(1, 8, 4):
        critical_roll = critical_damage.roll

    assert critical_roll.results == [1, 8, 4]
    assert critical_roll.attack_outcome == AttackOutcome.CRIT
    assert critical_roll.total == 16

    damage_lines = [
        (
            "normal damage: "
            f"faces={normal_roll.results}, "
            f"outcome={normal_roll.attack_outcome.value}, "
            f"bonus={normal_roll.bonus}, total={normal_roll.total}"
        ),
        (
            "critical damage: "
            f"faces={critical_roll.results}, "
            f"outcome={critical_roll.attack_outcome.value}, "
            f"bonus={critical_roll.bonus}, total={critical_roll.total}"
        ),
    ]

    print("\n".join(damage_lines))

    expected_damage_lines = [
        "normal damage: faces=[2, 5], outcome=Hit, bonus=3, total=10",
        "critical damage: faces=[1, 8, 4], outcome=Crit, bonus=3, total=16",
    ]
    assert damage_lines == expected_damage_lines
    assert capsys.readouterr().out.splitlines() == expected_damage_lines


def test_dice_validation_prints_rejected_roll_shapes(capsys) -> None:
    """Dice validation prints rejected non-damage and damage expressions."""
    reset_dice_state()
    hero_id = uuid4()
    bonus = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="Check Bonus",
        base_value=0,
    )
    rejection_lines = []

    try:
        Dice(
            count=2,
            value=20,
            bonus=bonus,
            roll_type=RollType.CHECK,
        )
    except ValidationError as exc:
        assert "Cannot have more than one die" in str(exc)
        rejection_lines.append("multi-die check: rejected")
    else:
        raise AssertionError("A multi-die check roll was accepted")

    try:
        Dice(
            count=1,
            value=8,
            bonus=bonus,
            roll_type=RollType.DAMAGE,
        )
    except ValidationError as exc:
        assert "Attack outcome must be provided" in str(exc)
        rejection_lines.append("damage without outcome: rejected")
    else:
        raise AssertionError("A damage roll without an attack outcome was accepted")

    try:
        Dice(
            count=1,
            value=20,
            bonus=bonus,
            roll_type=RollType.ATTACK,
            attack_outcome=AttackOutcome.HIT,
        )
    except ValidationError as exc:
        assert "Attack outcome must be None" in str(exc)
        rejection_lines.append("attack with outcome: rejected")
    else:
        raise AssertionError("A non-damage roll with an attack outcome was accepted")

    try:
        Dice(
            count=1,
            value=2,
            bonus=bonus,
            roll_type=RollType.CHECK,
        )
    except ValidationError as exc:
        assert "Input should be 4, 6, 8, 10, 12 or 20" in str(exc)
        rejection_lines.append("unsupported die size: rejected")
    else:
        raise AssertionError("An unsupported die size was accepted")

    print("\n".join(rejection_lines))

    expected_rejection_lines = [
        "multi-die check: rejected",
        "damage without outcome: rejected",
        "attack with outcome: rejected",
        "unsupported die size: rejected",
    ]
    assert rejection_lines == expected_rejection_lines
    assert capsys.readouterr().out.splitlines() == expected_rejection_lines
