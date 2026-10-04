"""Direct Produce Flame uses ordinary spell costs, defenses and damage."""
import pytest

from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.core.life_types import LifeState
from dnd.spells.abjuration import Sanctuary, GlobeOfInvulnerability, AntimagicField
from dnd.spells.conjuration import ProduceFlame
from dnd.spells.illusion import Silence
from tests.engine.test_roster_support_spells import actor, cast, game
from tests.manual.spell_regression_support import force_save_result


@pytest.mark.parametrize('level,dice', [(1,1),(5,2),(11,3),(17,4)])
@pytest.mark.parametrize('hit', [True,False])
def test_direct_flame_damage_cost_and_no_retained_state(game, level, dice, hit):
    caster, enemy = actor(game), actor(game, 'Enemy', (5,2), 'foes')
    hp = enemy.get_hp()
    lights = tuple(caster.get_attached_light_sources())
    actions = {a.uuid for a in caster.registered_actions}
    with fixed_dice_faces(*([15]+[4]*dice if hit else [1])):
        result = ProduceFlame(source_entity_uuid=caster.uuid,target_entity_uuid=enemy.uuid,caster_level=level).apply()
    assert result is not None and not result.canceled
    assert result.event_type is EventType.CAST_SPELL
    assert enemy.get_hp() == hp - (4*dice if hit else 0)
    assert caster.action_economy.actions.normalized_score == 0
    assert 'Produce Flame' not in caster.active_conditions
    assert tuple(caster.get_attached_light_sources()) == lights
    assert {a.uuid for a in caster.registered_actions} == actions


def test_direct_flame_cannot_cast_in_silence(game):
    caster, enemy = actor(game), actor(game,'Enemy',(5,2),'foes')
    silencer = actor(game,'Silencer',(2,5))
    result = Silence(source_entity_uuid=silencer.uuid,end_position=caster.position,alt_skip_slot=True).apply()
    assert result is not None and not result.canceled
    result = ProduceFlame(source_entity_uuid=caster.uuid,target_entity_uuid=enemy.uuid).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1


@pytest.mark.parametrize('saves',[False,True])
def test_direct_flame_respects_sanctuary_before_payment(game,saves):
    caster,enemy=actor(game),actor(game,'Warded',(5,2),'foes')
    cast(Sanctuary,enemy)
    force_save_result(caster,'wisdom',succeeds=saves)
    with fixed_dice_faces(15,4):
        result=ProduceFlame(source_entity_uuid=caster.uuid,target_entity_uuid=enemy.uuid).apply()
    assert result is not None and result.canceled is not saves
    assert caster.action_economy.actions.normalized_score == int(not saves)


def test_direct_flame_breaks_own_sanctuary_on_miss(game):
    caster,enemy=actor(game),actor(game,'Enemy',(5,2),'foes')
    cast(Sanctuary,caster)
    caster.action_economy.reset_all_costs()
    with fixed_dice_faces(1):
        result=ProduceFlame(source_entity_uuid=caster.uuid,target_entity_uuid=enemy.uuid).apply()
    assert result is not None and not result.canceled
    assert 'Sanctuary' not in caster.active_conditions


def test_direct_flame_critical_keeps_two_death_save_failures(game):
    caster,enemy=actor(game),actor(game,'Dying enemy',(5,2),'foes')
    enemy.uses_death_saves=True
    enemy.receive_damage(enemy.get_hp(),DamageType.FORCE,caster.uuid)
    assert enemy.health.life_state is LifeState.DYING
    with fixed_dice_faces(20,2,2):
        result=ProduceFlame(source_entity_uuid=caster.uuid,target_entity_uuid=enemy.uuid).apply()
    assert result is not None and not result.canceled
    assert enemy.death_save_failures == 2


@pytest.mark.parametrize('self_target',[False,True])
def test_direct_flame_rejects_self_or_range_before_payment(game,self_target):
    caster,enemy=actor(game),actor(game,'Too far',(9,2),'foes')
    target=caster if self_target else enemy
    hp=target.get_hp()
    result=ProduceFlame(source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert target.get_hp() == hp


@pytest.mark.parametrize('protection',[GlobeOfInvulnerability,AntimagicField])
def test_direct_flame_respects_spell_protection(game,protection):
    caster,enemy=actor(game),actor(game,'Defender',(7,2),'foes')
    cast(protection,enemy)
    hp=enemy.get_hp()
    with fixed_dice_faces(15,4,20):
        result=ProduceFlame(source_entity_uuid=caster.uuid,target_entity_uuid=enemy.uuid).apply()
    assert result is not None and result.canceled
    assert enemy.get_hp() == hp
