"""Retained flame use is an attack, with shared defenses and action costs."""
from uuid import uuid4

import pytest

from dnd.classes.sorcerer import MetamagicActive
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.core.life_types import LifeState
from dnd.spells.abjuration import Sanctuary, GlobeOfInvulnerability, AntimagicField
from dnd.spells.conjuration import ProduceFlame
from dnd.spells.illusion import Silence
from tests.engine.test_roster_support_spells import actor, cast, game
from tests.manual.spell_regression_support import force_save_result


def retained_flame(caster):
    cast(ProduceFlame, caster)
    caster.action_economy.reset_all_costs()
    return next(action for action in caster.registered_actions if action.name == "Hurl Produce Flame")


def test_retained_flame_can_be_thrown_in_silence_without_casting_again(game):
    caster, enemy = actor(game), actor(game, "Enemy", (5, 2), "foes")
    silencer = actor(game, "Silencer", (2, 5))
    hurl = retained_flame(caster)
    result = Silence(source_entity_uuid=silencer.uuid, end_position=caster.position, alt_skip_slot=True).apply()
    assert result is not None and not result.canceled
    blocked = ProduceFlame(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid).apply()
    assert blocked is not None and blocked.canceled
    caster.action_economy.reset_all_costs()
    hp = enemy.get_hp()
    with fixed_dice_faces(15, 4):
        result = hurl.instantiate(target_entity_uuid=enemy.uuid).apply()
    assert result is not None and result.phase is EventPhase.COMPLETION
    assert result.event_type is EventType.BASE_ACTION
    assert caster.action_economy.actions.normalized_score == 0
    assert enemy.get_hp() < hp
    assert "Produce Flame" not in caster.active_conditions


@pytest.mark.parametrize("saves", [False, True])
def test_retained_flame_respects_sanctuary_before_spending_or_consuming(game, saves):
    caster, enemy = actor(game), actor(game, "Warded", (5, 2), "foes")
    hurl = retained_flame(caster)
    cast(Sanctuary, enemy)
    force_save_result(caster, "wisdom", succeeds=saves)
    with fixed_dice_faces(15, 4):
        result = hurl.instantiate(target_entity_uuid=enemy.uuid).apply()
    assert result is not None and result.canceled is not saves
    assert caster.action_economy.actions.normalized_score == int(not saves)
    assert ("Produce Flame" in caster.active_conditions) is not saves


def test_throwing_retained_flame_breaks_own_sanctuary_even_on_miss(game):
    caster, enemy = actor(game), actor(game, "Enemy", (5, 2), "foes")
    hurl = retained_flame(caster)
    cast(Sanctuary, caster)
    caster.action_economy.reset_all_costs()
    with fixed_dice_faces(1):
        result = hurl.instantiate(target_entity_uuid=enemy.uuid).apply()
    assert result is not None and not result.canceled
    assert "Sanctuary" not in caster.active_conditions


@pytest.mark.parametrize("kind", ["quickened", "twinned", "distant"])
def test_metamagic_does_not_change_retained_flame_action(game, kind):
    caster = actor(game)
    hurl = retained_flame(caster)
    caster.add_condition(MetamagicActive(source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid, metamagic_type=kind, owning_action_template_uuid=uuid4()))
    assert hurl.alt_cost_type is None and hurl.alt_range is None and hurl.alt_target_count is None


def test_retained_flame_critical_keeps_two_death_save_failures(game):
    caster, enemy = actor(game), actor(game, "Dying enemy", (5, 2), "foes")
    enemy.uses_death_saves = True
    enemy.receive_damage(enemy.get_hp(), DamageType.FORCE, caster.uuid)
    assert enemy.health.life_state is LifeState.DYING
    hurl = retained_flame(caster)
    # Unconscious advantage and ranged Prone disadvantage cancel.
    with fixed_dice_faces(20, 2, 2):
        result = hurl.instantiate(target_entity_uuid=enemy.uuid).apply()
    assert result is not None and not result.canceled
    assert enemy.death_save_failures == 2
    assert not any(e.canceled for e in EventQueue.get_events_by_type(EventType.DAMAGE_APPLIED))


@pytest.mark.parametrize("retained", [False, True])
def test_flame_rejects_out_of_range_target_before_payment_or_consumption(game, retained):
    caster, enemy = actor(game), actor(game, "Too far", (9, 2), "foes")
    hurl = retained_flame(caster) if retained else None
    hp = enemy.get_hp()
    action = (hurl.instantiate(target_entity_uuid=enemy.uuid) if hurl is not None else
        ProduceFlame(source_entity_uuid=caster.uuid, target_entity_uuid=enemy.uuid))
    result = action.apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert enemy.get_hp() == hp
    assert ("Produce Flame" in caster.active_conditions) is retained


@pytest.mark.parametrize("protection", [GlobeOfInvulnerability, AntimagicField])
def test_retained_flame_is_still_a_spell_effect_for_zone_protection(game, protection):
    caster, enemy = actor(game), actor(game, "Defender", (7, 2), "foes")
    hurl = retained_flame(caster)
    cast(protection, enemy)
    hp = enemy.get_hp()
    with fixed_dice_faces(15, 4, 20):
        result = hurl.instantiate(target_entity_uuid=enemy.uuid).apply()
    assert result is not None and result.canceled
    assert enemy.get_hp() == hp
    assert "Produce Flame" in caster.active_conditions


def test_retained_flame_damage_keeps_original_spell_origin(game):
    caster, enemy = actor(game), actor(game, "Enemy", (5, 2), "foes")
    hurl = retained_flame(caster)
    origin = caster.active_conditions["Produce Flame"].effect_origin
    with fixed_dice_faces(15, 4):
        result = hurl.instantiate(target_entity_uuid=enemy.uuid).apply()
    assert result is not None and not result.canceled
    assert result.get_effect_origin() == origin
