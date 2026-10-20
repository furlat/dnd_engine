"""An allied human's retained breath follows the original caster's concentration."""

from uuid import uuid4

from dnd.ai.policies.basic import BASIC_POLICY_ID
from dnd.content.characters.premades import FIGHTER_PREMADE_ID, WIZARD_PREMADE_ID
from dnd.core.content.encounters import (
    EncounterDeploymentSpec, EncounterDeploymentZone, EncounterRecipe,
    EncounterRosterMember, EncounterRosterRecipe, EncounterRosterSlot,
    PremadeCharacterRosterSource, RosterControllerDefaults, RosterControllerKind, RosterSpellGrant,
)
from dnd.core.content.registration import get_content_declaration
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase
from dnd.player.facts import ActorChangeFact, DamageResultFact, SpellFact
from dnd.spells.transmutation import DragonsBreath, DragonsBreathEffect, ExhaleDragonsBreath
from dnd.types.actor_facts import ConditionRow
from tests.player.test_compact_choices import request_choices, rows
from tests.player.test_handoff_condition_owners import members
from tests.player.test_handoff_passive_attribution import await_actor, execute, nodes, turning_recipe, workers


def test_ally_exhales_original_casters_element_then_loses_exact_grant_in_both_seats(workers):
    base = turning_recipe(caster_premade=WIZARD_PREMADE_ID)
    caster_slot, foe_slot = base.roster_slots
    caster_member = caster_slot.roster.members[0].model_copy(update={
        "scenario_setup_effects": (RosterSpellGrant(
            spell_refs=(get_content_declaration(DragonsBreath).ref,), caster_level=5),),
    })
    caster_roster = EncounterRosterRecipe.create(roster_id="roster.ally_breath_caster",
        title="Breath caster", members=(caster_member,))
    ally_roster = EncounterRosterRecipe.create(roster_id="roster.ally_breath_recipient",
        title="Breath recipient", members=(EncounterRosterMember(
            member_id="ally", display_name="Breath ally", deployment_role="ally",
            source=PremadeCharacterRosterSource(premade_id=FIGHTER_PREMADE_ID)),))
    ally_slot = EncounterRosterSlot(roster_slot_id="ally", roster=ally_roster,
        faction_id=caster_slot.faction_id, deployment_zone_id="ally",
        controller_defaults=RosterControllerDefaults(
            controller=RosterControllerKind.HUMAN, participant_name="ally"))
    foe_slot = foe_slot.model_copy(update={"controller_defaults": RosterControllerDefaults(
        controller=RosterControllerKind.AI, participant_name="undead", policy_id=BASIC_POLICY_ID)})
    deployment = EncounterDeploymentSpec.create(deployment_id="deployment.ally_breath",
        title="Ally breath", battlefield_id=base.battlefield_id, zones=(
            EncounterDeploymentZone(zone_id="cleric", ordered_slots=((6, 6),)),
            EncounterDeploymentZone(zone_id="ally", ordered_slots=((7, 6),)),
            EncounterDeploymentZone(zone_id="undead", ordered_slots=((10, 6),))))
    recipe = EncounterRecipe.create(encounter_id="encounter.ally_breath", title="Ally breath",
        battlefield_id=base.battlefield_id, deployment=deployment,
        roster_slots=(caster_slot.model_copy(update={"roster": caster_roster}), ally_slot, foe_slot),
        opening_policy=base.opening_policy)
    runtime = workers(audience_ids={"cleric": uuid4(), "ally": uuid4()}, recipe=recipe)
    caster = next(actor for actor in runtime.session.game.entities.values() if actor.name == "cleric")
    ally = next(actor for actor in runtime.session.game.entities.values() if actor.name == "Breath ally")
    foe = next(actor for actor in runtime.session.game.entities.values() if caster.is_enemy(actor))
    assert caster.uuid != ally.uuid and caster.is_ally(ally)
    assert runtime.session.seats["cleric"].controlled == (caster.uuid,)
    assert runtime.session.seats["ally"].controlled == (ally.uuid,)

    cast = execute(await_actor(runtime, caster.uuid), "spell.dragons_breath",
        target_uuid=ally.uuid, facets=(("damage_type", "cold"),), level=2)
    grant, = (condition for condition in ally.active_conditions_by_uuid.values()
        if isinstance(condition, DragonsBreathEffect))
    assert grant.source_entity_uuid == caster.uuid and grant.target_entity_uuid == ally.uuid
    assert grant.uuid not in caster.active_conditions_by_uuid
    assert len(cast) == 2
    for record in cast:
        assert any(isinstance(node.fact, SpellFact)
            and node.fact.behavior_id == "spell.dragons_breath"
            and node.fact.source_entity_uuid == caster.uuid
            and node.fact.target_entity_uuid == ally.uuid for node in nodes(record))
        disclosed = [(owner, member) for owner, member in members(record)
            if member.condition_uuid == grant.uuid]
        assert disclosed and all(owner == ally.uuid and member.state is not None
            and member.state.energy_type is DamageType.COLD for owner, member in disclosed)

    with fixed_dice_faces(*([2] * 100)):
        ally_world = await_actor(runtime, ally.uuid)
    exhale, = (action for action in ally.registered_actions if isinstance(action, ExhaleDragonsBreath))
    assert exhale.original_caster_uuid == caster.uuid
    assert exhale.source_entity_uuid == ally.uuid and exhale.grant_condition_uuid == grant.uuid
    assert exhale.spell_damage_type is DamageType.COLD
    assert any(row.behavior_id == "action.spell.dragons_breath.exhale"
        for row in rows(request_choices(ally_world).choices))
    breath = execute(ally_world, "action.spell.dragons_breath.exhale",
        level=2, position=foe.position, command_number=21, first_face=1)
    assert len(breath) == 2
    for record in breath:
        assert any(isinstance(node.fact, SpellFact)
            and node.fact.behavior_id == "action.spell.dragons_breath.exhale"
            and node.fact.source_entity_uuid == ally.uuid
            and node.fact.damage_types == (DamageType.COLD,) for node in nodes(record))
        damage, = (node.fact for node in nodes(record) if isinstance(node.fact, DamageResultFact)
            and node.phase is EventPhase.COMPLETION and node.fact.target_entity_uuid == foe.uuid)
        assert damage.source_entity_uuid == caster.uuid
        assert damage.damage_type is DamageType.COLD and damage.applied_damage == 6

    with fixed_dice_faces(*([2] * 100)):
        caster_world = await_actor(runtime, caster.uuid)
    ended = execute(caster_world, "action.drop_concentration", command_number=22)
    assert grant.uuid not in ally.active_conditions_by_uuid
    assert not any(isinstance(action, ExhaleDragonsBreath) for action in ally.registered_actions)
    assert len(ended) == 2
    for record in ended:
        removals = [(actor.actor_uuid, row) for node in nodes(record)
            if isinstance(node.fact, ActorChangeFact) for actor in node.fact.actors for row in actor.rows
            if isinstance(row, ConditionRow) and row.condition_uuid == grant.uuid]
        assert removals and all(owner == ally.uuid and row.member is None for owner, row in removals)
