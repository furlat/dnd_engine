"""Finite spell lifetimes through paid casts and the native duration boundary.

The check advances authoritative durations, without triggering repeat saves or
simulating wall-clock time. It permits either a spell-owned sustain deadline or
a recipient deadline, and checks the effect remains through round nine.
"""

import pytest

from dnd.core.dice import fixed_dice_faces
from dnd.spells.enchantment import Bane, Bless, HoldMonster, HoldPerson
from dnd.spells.illusion import Blur, MirrorImage
from dnd.spells.necromancy import BestowCurse
from dnd.spells.transmutation import Haste, Slow
from tests.engine.test_high_level_spell_controls import high_actor
from tests.engine.test_roster_support_spells import game as game  # noqa: PLC0414 - pytest fixture re-export
from tests.manual.spell_regression_support import force_save_result

FINITE_LIFETIME_BUG = pytest.mark.xfail(
    strict=True, reason="SC-11: finite spell lifetime is left permanent"
)


@pytest.mark.parametrize(
    "spell_type,effect_name,self_target,area_target",
    [
        pytest.param(HoldPerson, "Hold Person", False, False, marks=FINITE_LIFETIME_BUG),
        pytest.param(Bless, "Bless", False, False, marks=FINITE_LIFETIME_BUG),
        pytest.param(Bane, "Bane", False, False, marks=FINITE_LIFETIME_BUG),
        pytest.param(Haste, "Haste", False, False, marks=FINITE_LIFETIME_BUG),
        pytest.param(Blur, "Blur", True, False, marks=FINITE_LIFETIME_BUG),
        pytest.param(Slow, "Slowed", False, True, marks=FINITE_LIFETIME_BUG),
        pytest.param(BestowCurse, "Bestow Curse", False, False, marks=FINITE_LIFETIME_BUG),
        (HoldMonster, "Hold Monster", False, False),
        (MirrorImage, "Mirror Image", True, False),
    ],
    ids=["hold_person", "bless", "bane", "haste", "blur", "slow", "bestow_curse", "hold_monster_control", "mirror_image_control"],
)
def test_one_minute_spell_expires_after_ten_native_duration_intervals(
    game, spell_type, effect_name, self_target, area_target
):
    caster = high_actor(game)
    faction = "foes" if spell_type in (Bane, HoldPerson, HoldMonster, Slow, BestowCurse) else "heroes"
    target = caster if self_target else high_actor(game, "Recipient", (3, 2), faction)
    force_save_result(target, "wisdom", succeeds=False)
    force_save_result(target, "charisma", succeeds=False)
    arguments = {"end_position": target.position} if area_target else {"target_entity_uuid": target.uuid}
    with fixed_dice_faces(*([2] * 30)):
        result = spell_type(source_entity_uuid=caster.uuid, **arguments).apply()
    assert result is not None and not result.canceled
    initially_applied = effect_name in target.active_conditions
    assert initially_applied

    for _ in range(9):
        for owner in (caster,) if target is caster else (caster, target):
            for name in tuple(owner.active_conditions):
                owner.advance_duration(name)
    remains_until_deadline = effect_name in target.active_conditions
    assert remains_until_deadline

    for owner in (caster,) if target is caster else (caster, target):
        for name in tuple(owner.active_conditions):
            owner.advance_duration(name)
    remains_past_deadline = effect_name in target.active_conditions
    assert not remains_past_deadline
