"""A seat sees the roster's starting damage and conditions on the creatures it perceives at startup.

Authored encounters apply starting damage and starting conditions after every
member is deployed and before the encounter starts. A seat whose members
already see a creature then must start with that creature's current hit points
and visible conditions, not with its undamaged birth values.
"""

import random

import pytest

from dnd.conditions import Poisoned
from dnd.core.condition_types import ConditionCategory
from dnd.core.content.encounters import (EncounterDeploymentSpec, EncounterDeploymentZone, EncounterRecipe,
    EncounterRosterRecipe, RosterStartingCondition, RosterStartingDamage)
from dnd.core.content.registration import get_content_declaration
from dnd.core.creature_types import DamageType
from dnd.player.application import initialize_audiences
from dnd.player.content_composition import ui_content_manifest
from dnd.player.reduction import reduce_initialization
from dnd.player.session import close_session, create_authored_session
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.encounter_catalog import encounter_recipe


def wounded_crypt() -> EncounterRecipe:
    """The lantern crypt with its guards in the heroes' room, the first wounded and poisoned before initiative."""
    recipe = encounter_recipe("encounter.lantern_crypt")
    heroes, monsters = recipe.roster_slots
    first, *rest = monsters.roster.members
    wounded = first.model_copy(update={"scenario_setup_effects": (
        RosterStartingDamage(amount=5, damage_type=DamageType.SLASHING),
        RosterStartingCondition(condition_ref=get_content_declaration(Poisoned).ref))})
    roster = EncounterRosterRecipe.create(roster_id=monsters.roster.roster_id, title=monsters.roster.title,
        members=(wounded, *rest))
    hero_zone, foe_zone = recipe.deployment.zones
    deployment = EncounterDeploymentSpec.create(deployment_id=recipe.deployment.deployment_id,
        title=recipe.deployment.title, battlefield_id=recipe.battlefield_id, zones=(hero_zone,
            EncounterDeploymentZone(zone_id=foe_zone.zone_id, ordered_slots=((5, 5), (5, 6)))))
    return EncounterRecipe.create(encounter_id=recipe.encounter_id, title=recipe.title,
        roster_slots=(heroes, monsters.model_copy(update={"roster": roster})), battlefield_id=recipe.battlefield_id,
        deployment=deployment, opening_policy=recipe.opening_policy)


@pytest.fixture
def session():
    state = random.getstate()
    random.seed(0)
    reset_engine_runtime()
    value = create_authored_session(wounded_crypt())
    try:
        yield value
    finally:
        close_session(value)
        reset_engine_runtime()
        random.setstate(state)


def test_initialization_shows_starting_damage_and_conditions_of_seen_creatures(session):
    _, initializations = initialize_audiences(session, ui_content_manifest())
    shown, current, wounded = {}, {}, set()
    for seat, initialization in initializations.items():
        client = reduce_initialization(initialization)
        audience = session.seats[seat]
        assert client.senses is not None
        for identity, contact in client.senses.entities.items():
            entity = session.game.entities[identity]
            if audience.controls(identity) or not contact.visual:
                continue
            body = client.actors[identity]
            key = f"{seat}: {entity.name}"
            shown[key] = body.normal_hp, sorted(row.name for row in body.conditions)
            current[key] = entity.get_normal_hp(), sorted(name for name, condition in entity.active_conditions.items()
                if condition.condition_category is not ConditionCategory.INTERNAL)
            if "Poisoned" in current[key][1] and entity.get_normal_hp() < entity.get_max_hp():
                wounded.add(key)
    assert wounded, current  # a seat sees the wounded, poisoned monster at startup
    assert shown == current
