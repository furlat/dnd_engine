"""Active parity coverage for the seven archived Disintegrate groups.

This replaces ``to_archive/examples/test_disintegrate.py``. The archived test
manually supplied sixth-level costs to a level-5 caster; the maintained fixture
instead owns a real sixth-level slot and exercises normal cost validation.
"""

from uuid import uuid4

import pytest

from dnd.actions.standard import (
    SpellEvent,
)
from dnd.core.dice import fixed_dice_faces
from dnd.types.life import LifeState
from dnd.types.damage import DamageType
from dnd.entities.entity import Entity
from dnd.spells.transmutation import Disintegrate
from tests.engine.support import has_condition, set_hp
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    force_save_result,
    reset_spell_regression_arena,
)


def _cast_disintegrate(
    *,
    save_succeeds: bool,
    target_hp: int = 200,
) -> tuple[SpellEvent, Entity, int]:
    """Cast one legal sixth-level Disintegrate with deterministic dice."""
    reset_spell_regression_arena(18, 9)
    caster = create_spell_regression_actor(
        "Disintegrate Caster",
        (2, 4),
        "heroes",
        spell_slots={6: 1},
    )
    target = create_spell_regression_actor(
        "Disintegrate Target",
        (7, 4),
        "monsters",
    )
    set_hp(target, target_hp)
    force_save_result(target, "dexterity", succeeds=save_succeeds)
    Entity.materialize_all_navigation(max_distance=100)
    hp_before = target.get_hp()

    faces = (10,) if save_succeeds else (10, *([4] * 10))
    with fixed_dice_faces(*faces):
        result = Disintegrate(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=6,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    return result, target, hp_before - target.get_hp()


def test_disintegrate_failed_save() -> None:
    """Archived group 1: a failed save takes 10d6 plus forty force damage."""
    event, _target, damage = _cast_disintegrate(save_succeeds=False)

    assert event.total_damage == 80
    assert damage == 80


def test_disintegrate_successful_save() -> None:
    """Archived group 2: a successful save takes zero, never half damage."""
    event, _target, damage = _cast_disintegrate(save_succeeds=True)

    assert event.total_damage == 0
    assert event.damage_rolls is None
    assert damage == 0


@pytest.mark.parametrize(
    ("slot_level", "expected_dice"),
    [(6, 10), (7, 13), (8, 16), (9, 19)],
)
def test_disintegrate_upcast(
    slot_level: int,
    expected_dice: int,
) -> None:
    """Archived group 3: each slot above sixth adds three d6."""
    spell = Disintegrate(
        source_entity_uuid=uuid4(),
        cast_at_level=slot_level,
    )

    assert spell.get_damage_dice_count() == expected_dice


def test_disintegrate_range() -> None:
    """Archived group 4: sixty feet succeeds and sixty-five feet fails."""
    reset_spell_regression_arena(18, 9)
    caster = create_spell_regression_actor(
        "Disintegrate Caster",
        (2, 4),
        "heroes",
        spell_slots={6: 1},
    )
    at_limit = create_spell_regression_actor("At 60 feet", (14, 4), "monsters")
    beyond_limit = create_spell_regression_actor("At 65 feet", (15, 4), "monsters")
    force_save_result(at_limit, "dexterity", succeeds=True)
    Entity.materialize_all_navigation(max_distance=100)

    too_far = Disintegrate(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=beyond_limit.uuid,
        cast_at_level=6,
    ).apply()
    assert isinstance(too_far, SpellEvent)
    assert too_far.canceled
    assert too_far.status_message is not None
    assert "out of range" in too_far.status_message.lower()

    with fixed_dice_faces(10):
        in_range = Disintegrate(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=at_limit.uuid,
            cast_at_level=6,
        ).apply()
    assert isinstance(in_range, SpellEvent)
    assert not in_range.canceled


def test_disintegrate_not_concentration() -> None:
    """Archived group 5: a completed cast creates no concentration owner."""
    event, _target, _damage = _cast_disintegrate(save_succeeds=True)

    caster = Entity.get(event.source_entity_uuid)
    assert caster is not None
    assert not has_condition(caster, "Concentrating")
    assert Disintegrate(source_entity_uuid=uuid4()).concentration is False


def test_disintegrate_kills_target() -> None:
    """Archived group 6: lethal damage commits HP and authoritative life state."""
    _event, target, _damage = _cast_disintegrate(
        save_succeeds=False,
        target_hp=10,
    )

    assert target.get_hp() <= 0
    assert target.health.life_state is LifeState.DEAD


def test_disintegrate_force_damage() -> None:
    """Archived group 7: the completed damage payload is explicitly force."""
    event, _target, damage = _cast_disintegrate(save_succeeds=False)

    assert event.damage_types == [DamageType.FORCE]
    assert event.damages is not None
    assert len(event.damages) == 1
    assert event.damages[0].damage_type is DamageType.FORCE
    assert damage == 80
