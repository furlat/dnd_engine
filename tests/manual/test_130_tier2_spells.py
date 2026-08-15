"""Active parity for the twenty-three archived tier-2 spell behavior groups.

This replaces ``to_archive/examples/test_tier2_spells.py``. Every cast uses an
explicit legal slot instead of the archived default level-5 bestiary caster.
"""

from uuid import uuid4

import pytest

from dnd.actions.standard import (
    SpellEvent,
)
from dnd.core.aoe import Cone, Sphere
from dnd.core.dice import fixed_dice_faces
from dnd.core.events.events_registry import (
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.types.life import LifeState
from dnd.types.creatures import CreatureType
from dnd.types.damage import DamageType
from dnd.entity import Entity
from dnd.spells.abjuration import (
    ProtectionFromEnergy,
    Stoneskin,
)
from dnd.spells.enchantment import PowerWordKill
from dnd.spells.evocation import CircleOfDeath, ConeOfCold
from dnd.spells.necromancy import Blight
from tests.engine.support import has_condition, set_hp
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    force_save_result,
    reset_spell_regression_arena,
)


def test_cone_of_cold_shape() -> None:
    """Archived group 1: Cone of Cold is a sixty-foot directional cone."""
    reset_spell_regression_arena(24, 15)
    caster = create_spell_regression_actor("Cone Caster", (2, 7), "heroes")
    spell = ConeOfCold(
        source_entity_uuid=caster.uuid,
        end_position=(14, 7),
        cast_at_level=5,
    )

    assert isinstance(spell.aoe_shape, Cone)
    assert spell.aoe_shape.length_feet == 60
    spell.aoe_shape.compute_objective(caster.position)
    assert (8, 7) in spell.aoe_shape.affected_positions
    assert (2, 12) not in spell.aoe_shape.affected_positions


def test_cone_of_cold_damage_and_save() -> None:
    """Archived group 2: failed saves take full cold and successes take half."""
    reset_spell_regression_arena(24, 15)
    caster = create_spell_regression_actor(
        "Cone Caster",
        (2, 7),
        "heroes",
        spell_slots={5: 1},
    )
    failing = create_spell_regression_actor("Failing", (6, 7), "monsters")
    passing = create_spell_regression_actor("Passing", (8, 7), "monsters")
    force_save_result(failing, "constitution", succeeds=False)
    force_save_result(passing, "constitution", succeeds=True)
    Entity.update_all_entities_senses(max_distance=100)
    failing_hp = failing.get_hp()
    passing_hp = passing.get_hp()

    with fixed_dice_faces(*([10, *([4] * 8)] * 2)):
        result = ConeOfCold(
            source_entity_uuid=caster.uuid,
            end_position=(14, 7),
            cast_at_level=5,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert failing.get_hp() == failing_hp - 32
    assert passing.get_hp() == passing_hp - 16


@pytest.mark.parametrize(
    ("slot_level", "expected_dice"),
    [(5, 8), (6, 9), (9, 12)],
)
def test_cone_of_cold_upcast(
    slot_level: int,
    expected_dice: int,
) -> None:
    """Archived group 3: each slot above fifth adds one d8."""
    spell = ConeOfCold(
        source_entity_uuid=uuid4(),
        cast_at_level=slot_level,
    )

    assert spell.get_damage_dice_count() == expected_dice


def test_circle_of_death_range() -> None:
    """Archived group 4: 150 feet succeeds while 155 feet is out of range."""
    reset_spell_regression_arena(34, 3)
    caster = create_spell_regression_actor(
        "Circle Caster",
        (1, 1),
        "heroes",
        spell_slots={6: 1},
    )
    target = create_spell_regression_actor("At 150 feet", (31, 1), "monsters")
    force_save_result(target, "constitution", succeeds=False)
    Entity.update_all_entities_senses(max_distance=200)

    too_far = CircleOfDeath(
        source_entity_uuid=caster.uuid,
        end_position=(32, 1),
        cast_at_level=6,
    ).apply()
    assert isinstance(too_far, SpellEvent)
    assert too_far.phase is EventPhase.CANCEL
    assert too_far.status_message is not None
    assert "out of range" in too_far.status_message.lower()

    with fixed_dice_faces(10, *([4] * 8)):
        at_limit = CircleOfDeath(
            source_entity_uuid=caster.uuid,
            end_position=target.position,
            cast_at_level=6,
        ).apply()
    assert isinstance(at_limit, SpellEvent)
    assert not at_limit.canceled


def test_circle_of_death_radius() -> None:
    """Archived group 5: the sphere includes sixty feet and excludes sixty-five."""
    reset_spell_regression_arena(30, 30)
    caster = create_spell_regression_actor("Circle Caster", (2, 2), "heroes")
    spell = CircleOfDeath(
        source_entity_uuid=caster.uuid,
        end_position=(15, 15),
        cast_at_level=6,
    )

    assert isinstance(spell.aoe_shape, Sphere)
    assert spell.aoe_shape.radius_feet == 60
    spell.aoe_shape.compute_objective(caster.position)
    assert (27, 15) in spell.aoe_shape.affected_positions
    assert (28, 15) not in spell.aoe_shape.affected_positions


@pytest.mark.parametrize(
    ("slot_level", "expected_dice"),
    [(6, 8), (7, 10), (9, 14)],
)
def test_circle_of_death_upcast(
    slot_level: int,
    expected_dice: int,
) -> None:
    """Archived group 6: each slot above sixth adds two d6."""
    spell = CircleOfDeath(
        source_entity_uuid=uuid4(),
        cast_at_level=slot_level,
    )

    assert spell.get_damage_dice_count() == expected_dice


def test_blight_rejects_undead() -> None:
    """Archived group 7: Blight rejects undead before damage resolution."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Blight Caster",
        (2, 3),
        "heroes",
        spell_slots={4: 1},
    )
    undead = create_spell_regression_actor(
        "Undead",
        (4, 3),
        "monsters",
        creature_type=CreatureType.UNDEAD,
    )
    Entity.update_all_entities_senses(max_distance=100)

    result = Blight(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=undead.uuid,
        cast_at_level=4,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert result.canceled
    assert result.status_message is not None
    assert "undead" in result.status_message.lower()


def test_blight_rejects_construct() -> None:
    """Archived group 8: Blight rejects constructs before damage resolution."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Blight Caster",
        (2, 3),
        "heroes",
        spell_slots={4: 1},
    )
    construct = create_spell_regression_actor(
        "Construct",
        (4, 3),
        "monsters",
        creature_type=CreatureType.CONSTRUCT,
    )
    Entity.update_all_entities_senses(max_distance=100)

    result = Blight(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=construct.uuid,
        cast_at_level=4,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert result.canceled
    assert result.status_message is not None
    assert "construct" in result.status_message.lower()


def test_blight_plant_max_damage() -> None:
    """Archived group 9: plants take deterministic maximum 8d8 damage."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Blight Caster",
        (2, 3),
        "heroes",
        spell_slots={4: 1},
    )
    plant = create_spell_regression_actor(
        "Plant",
        (4, 3),
        "monsters",
        creature_type=CreatureType.PLANT,
    )
    Entity.update_all_entities_senses(max_distance=100)
    hp_before = plant.get_hp()

    with fixed_dice_faces(10, 11):
        result = Blight(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=plant.uuid,
            cast_at_level=4,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert result.total_damage == 64
    assert plant.get_hp() == hp_before - 64


def test_blight_normal_target() -> None:
    """Archived group 10: a normal target saves for half necrotic damage."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Blight Caster",
        (2, 3),
        "heroes",
        spell_slots={4: 1},
    )
    target = create_spell_regression_actor("Humanoid", (4, 3), "monsters")
    force_save_result(target, "constitution", succeeds=True)
    Entity.update_all_entities_senses(max_distance=100)
    hp_before = target.get_hp()

    with fixed_dice_faces(10, *([4] * 8)):
        result = Blight(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=4,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert result.total_damage == 16
    assert result.damage_types == [DamageType.NECROTIC]
    assert target.get_hp() == hp_before - 16


def _power_word_kill_target(hp: int) -> tuple[SpellEvent, Entity]:
    """Cast one legal ninth-level Power Word Kill at the requested HP."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Word Caster",
        (2, 3),
        "heroes",
        spell_slots={9: 1},
    )
    target = create_spell_regression_actor("Word Target", (4, 3), "monsters")
    set_hp(target, hp)
    Entity.update_all_entities_senses(max_distance=100)

    result = PowerWordKill(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=9,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    return result, target


def test_pwk_kills_at_threshold() -> None:
    """Archived group 11: exactly one hundred HP is inside the kill threshold."""
    _result, target = _power_word_kill_target(100)

    assert target.get_hp() == 0
    assert target.health.life_state is LifeState.DEAD


def test_pwk_kills_below_threshold() -> None:
    """Archived group 12: a target below one hundred HP dies instantly."""
    _result, target = _power_word_kill_target(50)

    assert target.get_hp() == 0
    assert target.health.life_state is LifeState.DEAD


def test_pwk_fails_above_threshold() -> None:
    """Archived group 13: 101 HP is outside the kill threshold."""
    result, target = _power_word_kill_target(101)

    assert target.get_hp() == 101
    assert target.health.life_state is LifeState.ALIVE
    assert result.status_message is not None
    assert "no effect" in result.status_message.lower()


def test_pwk_no_save() -> None:
    """Archived group 14: resolution publishes no saving-throw event."""
    _result, _target = _power_word_kill_target(100)

    assert EventQueue.get_events_by_type(EventType.SAVING_THROW) == []
    assert EventQueue.get_events_by_type(EventType.SAVE_D20_ROLL_RESULT) == []


def _cast_protection(
    energy_type: DamageType,
    *,
    self_target: bool = False,
) -> tuple[Entity, Entity, SpellEvent]:
    """Cast Protection from Energy with one legal third-level slot."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Protection Caster",
        (2, 3),
        "heroes",
        spell_slots={3: 1},
    )
    target = (
        caster
        if self_target
        else create_spell_regression_actor("Protected Target", (3, 3), "heroes")
    )
    Entity.update_all_entities_senses(max_distance=100)
    result = ProtectionFromEnergy(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        chosen_energy_type=energy_type,
        cast_at_level=3,
    ).apply()
    assert isinstance(result, SpellEvent)
    assert not result.canceled
    return caster, target, result


def test_protection_from_energy_fire_resistance() -> None:
    """Archived group 15: fire resistance halves incoming fire damage."""
    caster, target, _result = _cast_protection(DamageType.FIRE)
    hp_before = target.get_hp()

    target.receive_damage(20, DamageType.FIRE, caster.uuid)

    assert has_condition(target, "Protection from Energy")
    assert has_condition(caster, "Concentrating")
    assert target.get_hp() == hp_before - 10


def test_protection_from_energy_cold_resistance() -> None:
    """Archived group 16: the chosen energy type can be cold."""
    caster, target, _result = _cast_protection(DamageType.COLD)
    hp_before = target.get_hp()

    target.receive_damage(20, DamageType.COLD, caster.uuid)

    assert target.get_hp() == hp_before - 10


def test_protection_from_energy_concentration_cleanup() -> None:
    """Archived group 17: breaking concentration removes resistance."""
    caster, target, _result = _cast_protection(DamageType.FIRE)

    caster.remove_condition("Concentrating")
    hp_before = target.get_hp()
    target.receive_damage(20, DamageType.FIRE, caster.uuid)

    assert not has_condition(target, "Protection from Energy")
    assert target.get_hp() == hp_before - 20


def test_protection_from_energy_self_target() -> None:
    """Archived group 18: Protection from Energy may target its caster."""
    caster, target, _result = _cast_protection(
        DamageType.LIGHTNING,
        self_target=True,
    )

    assert target.uuid == caster.uuid
    assert has_condition(caster, "Protection from Energy")
    assert has_condition(caster, "Concentrating")


def _cast_stoneskin() -> tuple[Entity, Entity, SpellEvent]:
    """Cast Stoneskin with one legal fourth-level slot."""
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "Stoneskin Caster",
        (2, 3),
        "heroes",
        spell_slots={4: 1},
    )
    target = create_spell_regression_actor("Stoneskin Target", (3, 3), "heroes")
    Entity.update_all_entities_senses(max_distance=100)
    result = Stoneskin(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=4,
    ).apply()
    assert isinstance(result, SpellEvent)
    assert not result.canceled
    return caster, target, result


@pytest.mark.parametrize(
    "damage_type",
    [
        DamageType.BLUDGEONING,
        DamageType.PIERCING,
        DamageType.SLASHING,
    ],
)
def test_stoneskin_physical_resistance(damage_type: DamageType) -> None:
    """Archived groups 19-21: Stoneskin halves each physical damage type."""
    caster, target, _result = _cast_stoneskin()
    hp_before = target.get_hp()

    target.receive_damage(20, damage_type, caster.uuid)

    assert has_condition(target, "Stoneskin")
    assert target.get_hp() == hp_before - 10


def test_stoneskin_concentration_cleanup() -> None:
    """Archived group 22: breaking concentration removes physical resistance."""
    caster, target, _result = _cast_stoneskin()

    caster.remove_condition("Concentrating")
    hp_before = target.get_hp()
    target.receive_damage(20, DamageType.BLUDGEONING, caster.uuid)

    assert not has_condition(target, "Stoneskin")
    assert target.get_hp() == hp_before - 20


def test_stoneskin_other_damage_unaffected() -> None:
    """Archived group 23: Stoneskin does not mitigate fire damage."""
    caster, target, _result = _cast_stoneskin()
    hp_before = target.get_hp()

    target.receive_damage(20, DamageType.FIRE, caster.uuid)

    assert has_condition(target, "Stoneskin")
    assert target.get_hp() == hp_before - 20
