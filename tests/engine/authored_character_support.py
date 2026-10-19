"""Prepare authored roster members through the ordinary encounter boundary."""

from dnd.core.content.encounters import EncounterRecipe, EncounterRosterRecipe
from dnd.core.events import EventQueue, EventType
from dnd.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.encounter_assembler import prepare_encounter_recipe
from dnd.scenarios.encounter_catalog import (
    AUTHORED_DEPLOYMENTS_BY_ID,
    encounter_recipe,
)


def prepare_roster_member(roster: EncounterRosterRecipe, member_id: str) -> Entity:
    """Keep the member's setup effects and verify its single committed birth."""
    reset_engine_runtime()
    member = next(row for row in roster.members if row.member_id == member_id)
    selected = EncounterRosterRecipe.create(
        roster_id=roster.roster_id,
        title=roster.title,
        members=(member,),
    )
    base = encounter_recipe("encounter.standard_skeleton_doors")
    deployment = AUTHORED_DEPLOYMENTS_BY_ID["neutral.battlefield.open_floor_bright"]
    recipe = EncounterRecipe.create(
        encounter_id="encounter.test.specialized_character",
        title="Specialized character",
        roster_slots=(
            base.roster_slots[0].model_copy(update={
                "roster": selected, "member_presentations": (),
            }),
            base.roster_slots[1],
        ),
        battlefield_id=deployment.battlefield_id,
        deployment=deployment,
        opening_policy=base.opening_policy,
    )
    assembled = prepare_encounter_recipe(recipe, game=Game())
    actor = assembled.entities_by_member_address[("roster_1", member_id)]
    births = EventQueue.get_events_by_type(EventType.ENTITY_CREATED)
    birth, = (event for event in births if event.entity_uuid == actor.uuid)
    assert birth.entity_name == actor.name == member.display_name
    assert actor.character_body_id == "creature.player.humanoid_body"
    assert actor.content_ref is None
    return actor

