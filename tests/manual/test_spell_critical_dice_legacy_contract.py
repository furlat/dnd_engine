"""Deterministic spell-attack critical dice coverage displaced by d80."""

from collections.abc import Callable

import pytest

from dnd.actions import SpellAction, SpellEvent
from dnd.core.dice import DiceRoll, fixed_dice_faces
from dnd.core.events import RollType
from dnd.entity import Entity
from dnd.spells.evocation import (
    EldritchBlast,
    FireBolt,
    GuidingBolt,
    RayOfFrost,
    ScorchingRay,
    ShockingGrasp,
)
from dnd.spells.necromancy import ChillTouch
from tests.engine.support import (
    force_spell_attack_crit,
    force_spell_attack_hit,
    remove_spell_attack_modifier,
)
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    reset_spell_regression_arena,
)


SpellFactory = Callable[[Entity, Entity], SpellAction]


def _cantrip(spell_type: type[SpellAction], caster_level: int) -> SpellFactory:
    def factory(caster: Entity, target: Entity) -> SpellAction:
        return spell_type(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_level=caster_level,
        )

    return factory


def _scorching_ray(caster: Entity, target: Entity) -> SpellAction:
    return ScorchingRay(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=2,
        caster_level=5,
    )


def _guiding_bolt(caster: Entity, target: Entity) -> SpellAction:
    return GuidingBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=1,
        caster_level=5,
    )


@pytest.mark.parametrize(
    ("case_name", "factory", "expected_roll_count", "expected_dice_per_roll"),
    [
        ("fire bolt level 1", _cantrip(FireBolt, 1), 1, 2),
        ("ray of frost level 1", _cantrip(RayOfFrost, 1), 1, 2),
        ("shocking grasp level 1", _cantrip(ShockingGrasp, 1), 1, 2),
        ("eldritch blast level 1", _cantrip(EldritchBlast, 1), 1, 2),
        ("chill touch level 1", _cantrip(ChillTouch, 1), 1, 2),
        ("fire bolt level 5", _cantrip(FireBolt, 5), 1, 4),
        ("ray of frost level 5", _cantrip(RayOfFrost, 5), 1, 4),
        ("eldritch blast level 5", _cantrip(EldritchBlast, 5), 1, 4),
        ("chill touch level 5", _cantrip(ChillTouch, 5), 1, 4),
        ("scorching ray", _scorching_ray, 3, 4),
        ("guiding bolt", _guiding_bolt, 1, 8),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_spell_attack_critical_rolls_double_once(
    case_name: str,
    factory: SpellFactory,
    expected_roll_count: int,
    expected_dice_per_roll: int,
) -> None:
    """Each old crit case executes the spell; no profile-only substitution."""
    reset_spell_regression_arena(24, 10)
    caster = create_spell_regression_actor(
        f"{case_name} caster",
        (2, 4),
        "heroes",
        spell_slots={1: 2, 2: 1},
    )
    target = create_spell_regression_actor(
        f"{case_name} target",
        (3, 4),
        "monsters",
        hit_die_count=100,
    )
    Entity.update_all_entities_senses(max_distance=120)
    hit_modifier = force_spell_attack_hit(caster)
    crit_modifier = force_spell_attack_crit(caster)
    DiceRoll._registry.clear()

    spell = factory(caster, target)
    with fixed_dice_faces(*([4] * 100)):
        result = spell.apply()

    remove_spell_attack_modifier(caster, hit_modifier)
    remove_spell_attack_modifier(caster, crit_modifier)

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    damage_rolls = [
        roll
        for roll in DiceRoll._registry.values()
        if roll.roll_type is RollType.DAMAGE
    ]
    assert len(damage_rolls) == expected_roll_count
    assert [
        roll.effective_dice_count
        for roll in damage_rolls
    ] == [expected_dice_per_roll] * expected_roll_count
