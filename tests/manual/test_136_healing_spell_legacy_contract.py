"""Deterministic parity for the archived 33-case healing spell matrix."""

from uuid import uuid4

import pytest

from dnd.actions.standard import (
    SpellEvent,
)
from dnd.conditions import (
    Blinded,
    Charmed,
    Deafened,
    Frightened,
    Paralyzed,
    Poisoned,
    Stunned,
)
from dnd.core.dice import Dice, fixed_dice_faces
from dnd.types.rolls import RollType
from dnd.core.events.events_registry import (
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.core.events.resolution_events import (
    HealEvent,
)
from dnd.types.damage import DamageType
from dnd.core.values import ModifiableValue
from dnd.entities.entity import Entity
from dnd.spells.abjuration import (
    GreaterRestoration,
    LesserRestoration,
)
from dnd.spells.evocation import (
    CureWounds,
    HealSpell,
    HealingWord,
    MassCureWounds,
    MassHeal,
    MassHealingWord,
    PrayerOfHealing,
)
from dnd.spells.transmutation import Regenerate
from tests.engine.support import (
    deal_damage_to,
    get_hp,
    get_max_hp,
    has_condition,
    set_hp,
)
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    reset_spell_regression_arena,
)


def _healing_caster(
    *,
    spell_slots: dict[int, int],
    position: tuple[int, int] = (1, 4),
) -> Entity:
    """Create one Wisdom caster with explicit legal slot ownership."""
    return create_spell_regression_actor(
        "Healing Cleric",
        position,
        "heroes",
        wisdom=18,
        spellcasting_ability="wisdom",
        spell_slots=spell_slots,
    )


def _wound(entity: Entity, amount: int, source: Entity) -> int:
    """Apply ordinary damage and return the resulting hit points."""
    dealt = deal_damage_to(
        entity,
        amount,
        DamageType.SLASHING,
        source_uuid=source.uuid,
    )
    assert dealt == amount
    return get_hp(entity)


def test_heal_roll_type_accepts_and_preserves_multiple_dice() -> None:
    """Old case 1: HEAL is a multi-die rules category, like DAMAGE."""
    reset_spell_regression_arena(8, 5)
    source_uuid = uuid4()
    bonus = ModifiableValue.create(
        source_entity_uuid=source_uuid,
        value_name="Healing regression bonus",
        base_value=4,
    )
    dice = Dice(
        count=3,
        value=8,
        bonus=bonus,
        roll_type=RollType.HEAL,
    )

    with fixed_dice_faces(2, 3, 4):
        roll = dice.roll

    assert roll.roll_type is RollType.HEAL
    assert roll.results == [2, 3, 4]
    assert roll.total == 13


def test_heal_event_defaults_to_nonspell_level_zero() -> None:
    """Old case 2: direct non-spell healing has an explicit zero level."""
    event = HealEvent(
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
        total_healing=10,
        phase=EventPhase.DECLARATION,
    )

    assert event.spell_level == 0


def test_receive_healing_preserves_spell_level_through_completion() -> None:
    """Old case 3: entity healing publishes the supplied spell level."""
    reset_spell_regression_arena(8, 5)
    healer = _healing_caster(spell_slots={})
    ally = create_spell_regression_actor("Levelled Heal Ally", (2, 4), "heroes")
    _wound(ally, 10, healer)

    actual = ally.receive_healing(
        5,
        healer.uuid,
        source_description="Levelled regression heal",
        spell_level=3,
    )

    assert actual == 5
    completions = [
        event
        for event in EventQueue.get_events_by_type(EventType.HEAL)
        if isinstance(event, HealEvent)
        and event.phase is EventPhase.COMPLETION
        and event.source_description == "Levelled regression heal"
    ]
    assert len(completions) == 1
    assert completions[0].spell_level == 3
    assert completions[0].actual_healing == 5


def test_cure_wounds_basic_heals_adjacent_ally() -> None:
    """Old case 4: the base-level touch spell heals a selected ally."""
    reset_spell_regression_arena(10, 7)
    caster = _healing_caster(spell_slots={1: 1}, position=(2, 3))
    ally = create_spell_regression_actor("Cure Ally", (3, 3), "heroes")
    Entity.materialize_all_navigation(max_distance=40)
    hp_before = _wound(ally, 20, caster)

    with fixed_dice_faces(5):
        result = CureWounds(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
            cast_at_level=1,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert get_hp(ally) == hp_before + 9


def test_cure_wounds_upcast_self_target_and_max_hp_cap() -> None:
    """Old cases 5-7: upcast dice, self targeting, and capped healing."""
    reset_spell_regression_arena(14, 9)
    caster = _healing_caster(spell_slots={1: 1, 3: 1})
    Entity.materialize_all_navigation(max_distance=60)
    hp_before = _wound(caster, 40, caster)

    with fixed_dice_faces(4, 4, 4):
        upcast = CureWounds(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            cast_at_level=3,
        ).apply()
    assert isinstance(upcast, SpellEvent)
    assert not upcast.canceled
    assert get_hp(caster) == hp_before + 16

    caster.action_economy.reset_all_costs()
    set_hp(caster, get_max_hp(caster) - 2)
    with fixed_dice_faces(8):
        capped = CureWounds(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            cast_at_level=1,
        ).apply()
    assert isinstance(capped, SpellEvent)
    assert get_hp(caster) == get_max_hp(caster)


def test_healing_word_range_upcast_and_bonus_action_cost() -> None:
    """Old cases 8-10: ranged healing, upcast dice, and bonus-action cost."""
    reset_spell_regression_arena(16, 9)
    caster = _healing_caster(spell_slots={2: 1})
    ally = create_spell_regression_actor("Distant Ally", (11, 4), "heroes")
    Entity.materialize_all_navigation(max_distance=80)
    hp_before = _wound(ally, 30, caster)

    with fixed_dice_faces(2, 3):
        result = HealingWord(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
            cast_at_level=2,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert get_hp(ally) == hp_before + 9
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.bonus_actions.normalized_score == 0


def test_prayer_of_healing_heals_selected_allies_and_rejects_enemy() -> None:
    """Old cases 11-12: multi-target healing cannot cross the ally filter."""
    reset_spell_regression_arena(16, 9)
    caster = _healing_caster(spell_slots={2: 2})
    allies = [
        create_spell_regression_actor(f"Prayer Ally {index}", (2 + index, 4), "heroes")
        for index in range(2)
    ]
    enemy = create_spell_regression_actor("Prayer Enemy", (4, 4), "monsters")
    Entity.materialize_all_navigation(max_distance=80)
    ally_before = [_wound(ally, 30, caster) for ally in allies]
    enemy_before = _wound(enemy, 30, caster)

    with fixed_dice_faces(*([3] * 8)):
        result = PrayerOfHealing(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=allies[0].uuid,
            extra_target_entity_uuids=[allies[1].uuid],
            cast_at_level=2,
        ).apply()
    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert all(get_hp(ally) > before for ally, before in zip(allies, ally_before))

    caster.action_economy.reset_all_costs()
    enemy_attempt = PrayerOfHealing(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=enemy.uuid,
        cast_at_level=2,
    ).apply()
    assert isinstance(enemy_attempt, SpellEvent)
    assert enemy_attempt.canceled
    assert get_hp(enemy) == enemy_before


def test_mass_healing_word_multi_target_upcast_and_cost() -> None:
    """Old cases 13-14: every selected ally gets L5 dice via bonus action."""
    reset_spell_regression_arena(16, 9)
    caster = _healing_caster(spell_slots={5: 1})
    allies = [
        create_spell_regression_actor(f"Word Ally {index}", (2 + index, 4), "heroes")
        for index in range(2)
    ]
    Entity.materialize_all_navigation(max_distance=80)
    hp_before = [_wound(ally, 30, caster) for ally in allies]

    with fixed_dice_faces(*([2] * 12)):
        result = MassHealingWord(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=allies[0].uuid,
            extra_target_entity_uuids=[allies[1].uuid],
            cast_at_level=5,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    for ally, before in zip(allies, hp_before):
        assert get_hp(ally) == before + 10
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.bonus_actions.normalized_score == 0


def test_mass_cure_wounds_aoe_upcast_excludes_enemy() -> None:
    """Old cases 15-16: L7 AoE healing is ally-only and uses five d8."""
    reset_spell_regression_arena(18, 12)
    caster = _healing_caster(spell_slots={7: 1}, position=(4, 5))
    allies = [
        create_spell_regression_actor("Mass Cure Ally 1", (6, 5), "heroes"),
        create_spell_regression_actor("Mass Cure Ally 2", (6, 6), "heroes"),
    ]
    enemy = create_spell_regression_actor("Mass Cure Enemy", (7, 5), "monsters")
    Entity.materialize_all_navigation(max_distance=100)
    ally_before = [_wound(ally, 50, caster) for ally in allies]
    enemy_before = _wound(enemy, 50, caster)

    with fixed_dice_faces(*([3] * 40)):
        result = MassCureWounds(
            source_entity_uuid=caster.uuid,
            end_position=(6, 5),
            cast_at_level=7,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    for ally, before in zip(allies, ally_before):
        assert get_hp(ally) == before + 19
    assert get_hp(enemy) == enemy_before


@pytest.mark.parametrize(("cast_at_level", "heal_amount"), ((6, 70), (8, 90)))
def test_heal_flat_amount_upcast_and_condition_cleanup(
    cast_at_level: int,
    heal_amount: int,
) -> None:
    """Old cases 17-20: Heal owns flat scaling and sensory-condition cleanup."""
    reset_spell_regression_arena(14, 9)
    caster = _healing_caster(spell_slots={cast_at_level: 1})
    ally = create_spell_regression_actor("Heal Ally", (2, 4), "heroes")
    Entity.materialize_all_navigation(max_distance=60)
    set_hp(ally, 1)
    ally.add_condition(
        Blinded(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
    )
    ally.add_condition(
        Deafened(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
    )

    result = HealSpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=cast_at_level,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert get_hp(ally) == 1 + heal_amount
    assert not has_condition(ally, "Blinded")
    assert not has_condition(ally, "Deafened")


def test_mass_heal_distributes_pool_and_cleans_each_target() -> None:
    """Old cases 21-22: pool consumption and condition cleanup are per target."""
    reset_spell_regression_arena(16, 9)
    caster = _healing_caster(spell_slots={9: 1})
    allies = [
        create_spell_regression_actor(f"Mass Heal Ally {index}", (2 + index, 4), "heroes")
        for index in range(2)
    ]
    Entity.materialize_all_navigation(max_distance=80)
    wounds = [20, 30]
    for ally, wound in zip(allies, wounds):
        _wound(ally, wound, caster)
        ally.add_condition(
            Blinded(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
        )
        ally.add_condition(
            Deafened(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
        )

    spell = MassHeal(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=allies[0].uuid,
        extra_target_entity_uuids=[allies[1].uuid],
        cast_at_level=9,
    )
    result = spell.apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert spell.healing_pool_remaining == 650
    for ally in allies:
        assert get_hp(ally) == get_max_hp(ally)
        assert not has_condition(ally, "Blinded")
        assert not has_condition(ally, "Deafened")


def test_regenerate_burst_turn_healing_expiry_and_nonconcentration() -> None:
    """Old cases 23-26: burst and ten owned ticks form one non-concentration rule."""
    reset_spell_regression_arena(14, 9)
    caster = _healing_caster(spell_slots={7: 1})
    ally = create_spell_regression_actor("Regenerate Ally", (2, 4), "heroes")
    Entity.materialize_all_navigation(max_distance=60)
    hp_before = _wound(ally, 100, caster)

    with fixed_dice_faces(2, 2, 2, 2):
        result = Regenerate(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
            cast_at_level=7,
        ).apply()
    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert get_hp(ally) == hp_before + 23
    assert has_condition(ally, "Regenerating")
    assert not has_condition(caster, "Concentrating")

    for turn in range(1, 11):
        before_tick = get_hp(ally)
        ally.on_turn_start(round_number=turn, turn_index=0)
        assert get_hp(ally) == before_tick + 1
    assert not has_condition(ally, "Regenerating")


@pytest.mark.parametrize(
    ("condition_type", "condition_name", "removed"),
    (
        (Blinded, "Blinded", True),
        (Poisoned, "Poisoned", True),
        (Paralyzed, "Paralyzed", True),
        (Stunned, "Stunned", False),
    ),
)
def test_lesser_restoration_condition_matrix(
    condition_type,
    condition_name: str,
    removed: bool,
) -> None:
    """Old cases 27-30: the supported list is closed and deterministic."""
    reset_spell_regression_arena(12, 7)
    caster = _healing_caster(spell_slots={2: 1})
    ally = create_spell_regression_actor("Lesser Ally", (2, 4), "heroes")
    Entity.materialize_all_navigation(max_distance=60)
    ally.add_condition(
        condition_type(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
    )

    result = LesserRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=2,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert has_condition(ally, condition_name) is not removed


@pytest.mark.parametrize(
    ("condition_type", "condition_name"),
    (
        (Charmed, "Charmed"),
        (Frightened, "Frightened"),
        (Stunned, "Stunned"),
    ),
)
def test_greater_restoration_condition_matrix(
    condition_type,
    condition_name: str,
) -> None:
    """Old cases 31-33: each legacy major condition is removed."""
    reset_spell_regression_arena(12, 7)
    caster = _healing_caster(spell_slots={5: 1})
    ally = create_spell_regression_actor("Greater Ally", (2, 4), "heroes")
    Entity.materialize_all_navigation(max_distance=60)
    ally.add_condition(
        condition_type(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
    )

    result = GreaterRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cast_at_level=5,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert not has_condition(ally, condition_name)
