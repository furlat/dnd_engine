"""Selected destinations and rolled rays survive real worker serialization.

The command chooses a portable sphere's endpoint or a cone direction. Both
seats receive the accepted aim and the actual recipient-specific ray results,
including nondamaging rays and the two separate results of an eight.
"""

import random
from uuid import uuid4

import pytest

from dnd.core.content.encounters import (
    AuthoredCreatureRosterSource, EncounterDeploymentSpec, EncounterDeploymentZone,
    EncounterRecipe, EncounterRosterMember, EncounterRosterRecipe, EncounterRosterSlot,
    FixedRosterOpeningPolicy, RosterControllerDefaults, RosterControllerKind, RosterSpellGrant,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import get_content_declaration
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.player.commands import ActionSelection
from dnd.player.facts import ActionFact, ActorChangeFact, DamageResultFact, SavingThrowFact, SpellFact
from dnd.player.session import close_session
from dnd.spells.evocation import FreezingSphere, PrismaticSpray
from dnd.types.actor_facts import ConditionRow
from server.protocol import CommandRequest, ExecuteSelectionIntent, PlayerOperation
from server.worker import dispatch, needs_advance, start
from server.worker_protocol import Advance, Command, Start
from tests.player.test_compact_choices import request_choices, rows


@pytest.fixture
def selected_world():
    previous_random = random.getstate()
    source = ContentRecipe.create(
        ref=BESTIARY_CREATURE_RECIPES_BY_ID["generic_caster"].ref, parameters={"level": 13})
    grants = (RosterSpellGrant(spell_refs=tuple(
        get_content_declaration(spell).ref for spell in (FreezingSphere, PrismaticSpray)),
        caster_level=13),)
    slots = tuple(EncounterRosterSlot(
        roster_slot_id=side, faction_id=side, deployment_zone_id=side,
        controller_defaults=RosterControllerDefaults(
            controller=RosterControllerKind.HUMAN, participant_name=side),
        roster=EncounterRosterRecipe.create(roster_id=f"roster.selected_effects_{side}",
            title=side, members=(EncounterRosterMember(member_id="caster", display_name=side,
                deployment_role="caster", source=AuthoredCreatureRosterSource(recipe=source),
                scenario_setup_effects=grants),)),
    ) for side in ("amber", "blue"))
    battlefield = "battlefield.open_floor_bright"
    deployment = EncounterDeploymentSpec.create(deployment_id="deployment.selected_effects",
        title="Selected effects", battlefield_id=battlefield, zones=(
            EncounterDeploymentZone(zone_id="amber", ordered_slots=((6, 6),)),
            EncounterDeploymentZone(zone_id="blue", ordered_slots=((9, 6),))))
    recipe = EncounterRecipe.create(encounter_id="encounter.selected_effects",
        title="Selected effects", battlefield_id=battlefield, deployment=deployment,
        roster_slots=slots, opening_policy=FixedRosterOpeningPolicy(roster_slot_id="amber"))
    runtime, _, _ = start(Start(
        game_id="selected-effects", game_epoch=uuid4(), encounter_id=None, recipe=recipe,
        assignments=None, audience_ids={side: uuid4() for side in ("amber", "blue")}, test_seed=6))
    while needs_advance(runtime.session):
        dispatch(runtime, Advance())
    try:
        yield runtime
    finally:
        close_session(runtime.session)
        random.setstate(previous_random)


def execute(runtime, behavior, *, aim=None, facets=(), faces=(), command_number=1):
    publication = runtime.publications["amber"]
    choices = request_choices((runtime, "amber", publication)).choices
    offered = next(row for row in rows(choices) if row.behavior_id == behavior and row.can_afford
        and all(any(facet.key == key and facet.value == value for facet in row.variant_facets)
            for key, value in facets))
    bindings = choices.target_sets[offered.target_set]
    if aim is None:
        binding = next(binding for binding in bindings if binding.kind == "self"
            or binding.kind == "subject"
            and choices.subjects[binding.subject].uuid == publication.boundary.input_actor_uuid)
        selection = ActionSelection(offered.discovery_index, (binding.index,))
    else:
        selection = ActionSelection(offered.discovery_index, (), extra_target_positions=(aim,))
    with fixed_dice_faces(*faces):
        reply, records, _ = dispatch(runtime, Command(seat_id="amber", request=CommandRequest(
            command_number=command_number, actor_uuid=publication.boundary.input_actor_uuid,
            state_revision=publication.state_revision,
            intent=ExecuteSelectionIntent(discovery_generation=choices.discovery_generation,
                selection=selection))))
    assert reply.rejection is None, reply.rejection
    assert len(records) == 2
    return tuple(PlayerOperation.model_validate_json(record.model_dump_json()) for record in records)


def nodes(record):
    return tuple(node for group in record.lineages for node in group.events)


def descendant(record, node, ancestor):
    """Use only the public causal links, including versions of one lineage."""
    all_nodes = nodes(record)
    by_occurrence = {row.occurrence: row for row in all_nodes}
    lineages = {occurrence: lineage for group in record.lineages
        for occurrence, lineage in zip(group.version_rows.occurrences,
            group.version_rows.lineages, strict=True)}
    ancestor_lineage = lineages[ancestor.occurrence]
    visited = set()
    while node.occurrence not in visited:
        visited.add(node.occurrence)
        if lineages[node.occurrence] == ancestor_lineage:
            return True
        if node.parent_event in by_occurrence:
            node = by_occurrence[node.parent_event]
            continue
        parent_lineage = node.parent_lineage
        if parent_lineage is None:
            parent_lineage = next((lineages[parent.occurrence] for parent in all_nodes
                if lineages[node.occurrence] in parent.children_lineages), None)
        parent = next((row for row in all_nodes
            if lineages[row.occurrence] == parent_lineage), None)
        if parent is None:
            return False
        node = parent
    return False


def test_portable_freezing_throw_publishes_accepted_destination_and_explosion_center(selected_world):
    runtime = selected_world
    caster = next(entity for entity in runtime.session.game.entities.values() if entity.name == "amber")
    target = next(entity for entity in runtime.session.game.entities.values() if entity.name == "blue")
    execute(runtime, "spell.freezing_sphere", facets=(("form", "portable"),))
    caster.action_economy.reset_all_costs()
    destination = target.position
    records = execute(runtime, "action.spell.payload.throw", aim=destination,
        command_number=2, faces=([2] * 100))
    for record in records:
        throws = [node for node in nodes(record)
            if isinstance(node.fact, ActionFact)
            and node.fact.behavior_id == "action.spell.payload.throw"
            and node.phase is EventPhase.COMPLETION]
        assert len(throws) == 1
        assert throws[0].fact.target_position == destination
        explosions = [node for node in nodes(record)
            if isinstance(node.fact, SpellFact) and node.fact.name == "Freezing Sphere explosion"
            and node.phase is EventPhase.COMPLETION]
        assert len(explosions) == 1
        explosion = explosions[0]
        assert explosion.fact.aoe_position == destination
        assert explosion.fact.area_geometry.center == destination
        assert explosion.fact.area_geometry.radius_feet == 20
        assert destination in explosion.fact.resolved_area_positions
        assert descendant(record, explosion, throws[0])


@pytest.mark.parametrize("initial,colors,save_face", [
    *[(color, (color,), 1) for color in range(1, 8)],
    (6, (6,), 20), (7, (7,), 20), (8, (6, 7), 1), (8, (1, 2), 1),
])
def test_prismatic_actual_colors_bind_recipient_saves_and_results(selected_world, initial, colors, save_face):
    runtime = selected_world
    target = next(entity for entity in runtime.session.game.entities.values() if entity.name == "blue")
    faces = [initial, *(colors if initial == 8 else ())]
    for color in colors:
        faces.extend((save_face, *([2] * 10 if color <= 5 else ())))
    records = execute(runtime, "spell.prismatic_spray", aim=target.position, faces=faces)
    native_application = next(event for event in EventQueue.get_events_by_type(EventType.CAST_SPELL)
        if event.phase is EventPhase.COMPLETION and event.target_entity_uuid == target.uuid
        and event.prismatic_roll == initial)
    origin = native_application.get_effect_origin()
    rolled = [event for event in EventQueue.get_events_by_type(EventType.SPELL_DAMAGE_ROLL_RESULT)
        if event.phase is EventPhase.COMPLETION and event.target_entity_uuid == target.uuid]
    assert len(rolled) == sum(color <= 5 for color in colors)
    assert all(event.effect_origin == origin and event.damage.effect_origin == origin for event in rolled)
    for color, name in ((6, "Prismatic Restrained"), (7, "Blinded")):
        if color in colors and save_face == 1:
            assert target.active_conditions[name].effect_origin == origin
    for record in records:
        completed = [node for node in nodes(record) if node.phase is EventPhase.COMPLETION]
        applications = [node for node in completed if isinstance(node.fact, SpellFact)
            and node.fact.target_entity_uuid == target.uuid and node.fact.prismatic_roll == initial]
        assert len(applications) == 1, "The actual per-recipient colour roll is missing"
        application = applications[0]
        assert application.fact.prismatic_colors == colors
        for color in colors:
            effect_id = f"spell.prismatic_spray.color_{color}"
            saves = [node for node in completed if isinstance(node.fact, SavingThrowFact)
                and node.fact.effect_id == effect_id and descendant(record, node, application)]
            assert len(saves) == 1
            assert saves[0].fact.target_entity_uuid == target.uuid
            assert saves[0].fact.succeeded is (save_face == 20)
            damage = [node.fact for node in completed if isinstance(node.fact, DamageResultFact)
                and node.fact.target_entity_uuid == target.uuid and descendant(record, node, saves[0])]
            conditions = [row.member for node in completed if isinstance(node.fact, ActorChangeFact)
                and descendant(record, node, saves[0]) for actor in node.fact.actors
                if actor.actor_uuid == target.uuid for row in actor.rows
                if isinstance(row, ConditionRow) and row.member is not None]
            assert [row.applied_damage for row in damage] == ([20] if color <= 5 else [])
            expected_conditions = {6: ["Restrained", "Prismatic Restrained"], 7: ["Blinded"]}.get(color, [])
            assert [row.name for row in conditions] == (expected_conditions if save_face == 1 else [])
