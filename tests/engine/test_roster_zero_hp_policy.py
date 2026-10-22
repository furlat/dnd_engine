"""Roster-authored zero-HP policy reaches birth, starting damage and live damage.

The same character or monster can die immediately or use the existing dying
rules. Omitted policy preserves the source and existing serialized recipes.
"""

from pathlib import Path
import random

import pytest
from pydantic import ValidationError

from devtools.player_server_acceptance.fixtures import combat_configuration
from dnd.content.characters.premades import FIGHTER_PREMADE_ID
from dnd.core.content.encounters import (
    AuthoredCreatureRosterSource, EncounterRecipe, EncounterRosterMember,
    EncounterRosterRecipe, PremadeCharacterRosterSource, RosterStartingDamage,
)
from dnd.core.creature_types import DamageType
from dnd.core.events import EventQueue, EventType
from dnd.core.life_types import LifeState
from dnd.game import Game
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.encounter_assembler import prepare_encounter_recipe
from dnd.scenarios.encounter_catalog import encounter_recipe


@pytest.fixture(autouse=True)
def runtime():
    state = random.getstate()
    random.seed(7)
    reset_engine_runtime()
    yield
    reset_engine_runtime()
    random.setstate(state)


def recipe_for(source, policy, *, starting_damage=None):
    config = combat_configuration('magic_missile', Path('/unused-roster-policy'))
    slot = config.recipe.roster_slots[0]
    member = EncounterRosterMember(member_id='subject', display_name='Policy subject',
        deployment_role='subject', source=source, uses_death_saves=policy,
        scenario_setup_effects=(() if starting_damage is None else (
            RosterStartingDamage(amount=starting_damage, damage_type=DamageType.FORCE),)))
    roster = EncounterRosterRecipe.create(roster_id=slot.roster.roster_id,
        title=slot.roster.title, members=(member,))
    recipe = EncounterRecipe.create(
        **config.recipe.model_dump(exclude={'recipe_digest', 'roster_slots', 'deployment', 'opening_policy'}),
        roster_slots=(slot.model_copy(update={'roster': roster}), *config.recipe.roster_slots[1:]),
        deployment=config.recipe.deployment, opening_policy=config.recipe.opening_policy)
    return EncounterRecipe.model_validate_json(recipe.model_dump_json())


SOURCES = (
    pytest.param(PremadeCharacterRosterSource(premade_id=FIGHTER_PREMADE_ID), True, id='premade'),
    pytest.param(AuthoredCreatureRosterSource(recipe=BESTIARY_CREATURE_RECIPES_BY_ID['goblin']),
        False, id='authored-monster'),
)


@pytest.mark.parametrize('source,inherited', SOURCES)
@pytest.mark.parametrize('policy', (None, False, True), ids=('inherit', 'die', 'death-saves'))
def test_roster_policy_controls_birth_and_zero_hp_result(source, inherited, policy):
    assembled = prepare_encounter_recipe(recipe_for(source, policy), game=Game())
    subject = assembled.entities_by_member_address[('amber', 'subject')]
    other = assembled.entities_by_roster_slot['blue'][0]
    expected = inherited if policy is None else policy
    birth, = (event for event in EventQueue.get_events_by_type(EventType.ENTITY_CREATED)
        if event.entity_uuid == subject.uuid)
    assert birth.uses_death_saves is expected
    before = subject.get_normal_hp()
    assert before > 0
    assert subject.receive_damage(before, DamageType.FORCE, other.uuid) == before
    assert subject.get_normal_hp() == 0
    assert subject.health.life_state is (LifeState.DYING if expected else LifeState.DEAD)
    if expected:
        subject.stabilize()
        assert subject.health.life_state is LifeState.STABLE


@pytest.mark.parametrize('policy', (False, True), ids=('die', 'death-saves'))
def test_policy_is_applied_before_roster_starting_damage(policy):
    source = AuthoredCreatureRosterSource(recipe=BESTIARY_CREATURE_RECIPES_BY_ID['goblin'])
    # The native goblin has seven HP. This is lethal without massive overkill.
    assembled = prepare_encounter_recipe(recipe_for(source, policy, starting_damage=7), game=Game())
    subject = assembled.entities_by_member_address[('amber', 'subject')]
    assert subject.get_normal_hp() == 0
    assert subject.health.life_state is (LifeState.DYING if policy else LifeState.DEAD)


def test_legacy_roster_identity_survives_inherit_but_explicit_policy_is_retained():
    authored = encounter_recipe('encounter.srd_goblinoid_warband')
    legacy = authored.model_dump(mode='json')
    member = legacy['roster_slots'][0]['roster']['members'][0]
    assert 'uses_death_saves' not in member
    member['uses_death_saves'] = None
    restored = EncounterRecipe.model_validate(legacy)
    assert restored.recipe_digest == authored.recipe_digest
    assert 'uses_death_saves' not in restored.roster_slots[0].roster.members[0].model_dump()
    source = PremadeCharacterRosterSource(premade_id=FIGHTER_PREMADE_ID)
    dies, saves = recipe_for(source, False), recipe_for(source, True)
    assert dies.roster_slots[0].roster.members[0].uses_death_saves is False
    assert saves.roster_slots[0].roster.members[0].uses_death_saves is True
    assert dies.recipe_digest != saves.recipe_digest
    changed = dies.model_dump(mode='json')
    changed['roster_slots'][0]['roster']['members'][0]['uses_death_saves'] = True
    with pytest.raises(ValidationError, match='digest'):
        EncounterRecipe.model_validate(changed)


def test_enemy_template_keeps_death_policy_when_client_substitutes_premade():
    config = combat_configuration('magic_missile', Path('/unused-roster-policy'))
    blue = config.recipe.roster_slots[1]
    sentry = blue.roster.members[0].model_copy(update={
        'source': PremadeCharacterRosterSource(premade_id=FIGHTER_PREMADE_ID)})
    roster = EncounterRosterRecipe.create(roster_id=blue.roster.roster_id,
        title=blue.roster.title, members=(sentry, *blue.roster.members[1:]))
    recipe = EncounterRecipe.create(
        **config.recipe.model_dump(exclude={'recipe_digest', 'roster_slots', 'deployment', 'opening_policy'}),
        roster_slots=(config.recipe.roster_slots[0], blue.model_copy(update={'roster': roster})),
        deployment=config.recipe.deployment, opening_policy=config.recipe.opening_policy)
    assembled = prepare_encounter_recipe(recipe, game=Game())
    enemy = assembled.entities_by_member_address[('blue', sentry.member_id)]
    hero = assembled.entities_by_roster_slot['amber'][0]
    enemy.receive_damage(enemy.get_normal_hp(), DamageType.FORCE, hero.uuid)
    assert enemy.health.life_state is LifeState.DEAD
