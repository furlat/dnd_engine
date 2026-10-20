"""Native class passives keep their exact emitted-result attribution on the wire.

Real character progression and discovered worker commands produce the healing
and damage. Assertions inspect serialized seat operations, not injected handler
presentations or combat-log text.
"""

from dataclasses import replace
import random
import os
import subprocess
import sys
from uuid import uuid4

import pytest

from dnd.content.characters.premades import (
    CLERIC_PREMADE_ID,
    FIGHTER_PREMADE_ID,
    PALADIN_PREMADE_ID,
    PREMADE_CHARACTER_BUILDS,
)
from dnd.content.items.item_loadouts import ItemLoadoutEntry
from dnd.core.content.encounters import (
    AuthoredCreatureRosterSource,
    EncounterDeploymentSpec,
    EncounterDeploymentZone,
    EncounterRecipe,
    EncounterRosterMember,
    EncounterRosterRecipe,
    EncounterRosterSlot,
    FixedRosterOpeningPolicy,
    PremadeCharacterRosterSource,
    RosterControllerDefaults,
    RosterControllerKind,
)
from dnd.core.creature_types import DamageType
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.conditions import Invisible
from dnd.actions_functional import register_spell
from dnd.core.modifiers import NumericalModifier
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue, HandlerDispatchOutcome
from dnd.core.modifiers import ResistanceModifier, ResistanceStatus
from dnd.core.values import Channel, Kind, add_modifier
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.player.commands import ActionSelection
from dnd.player.facts import DamageResultFact, HealFact
from dnd.player.capture import capture_interval, capture_lineages
from dnd.player.recorded import RecordedSequence, project_sequence
from dnd.player.reduction import encode_player_sequence
from dnd.player.session import close_session
from dnd.types.character_progression import CharacterClass, PreparedSpellSelection
from dnd.spells.evocation import DivineFavor
from server.protocol import CommandRequest, EndTurnIntent, ExecuteSelectionIntent, PlayerOperation
from server.worker import dispatch, needs_advance, start
from server.worker_protocol import Advance, Command, Start
from tests.player.test_compact_choices import request_choices, rows
from tests.progression.prepared_class_support import prepared_build


@pytest.fixture
def workers():
    previous_random = random.getstate()
    active = []

    def open_worker(*, audience_ids, recipe=None, player_builds=None):
        runtime, _, _ = start(Start(
            game_id="passive-attribution", game_epoch=uuid4(),
            encounter_id=None, recipe=recipe, assignments=None, test_seed=6,
            audience_ids=audience_ids, player_builds=player_builds,
        ))
        active.append(runtime)
        return runtime

    yield open_worker
    for runtime in active:
        close_session(runtime.session)
    random.setstate(previous_random)


def await_actor(runtime, actor_uuid):
    """End other human turns through commands until this actor can act."""
    for number in range(1, 12):
        while needs_advance(runtime.session):
            dispatch(runtime, Advance())
        seat, publication = next((seat, row) for seat, row in runtime.publications.items()
            if row.boundary.input_actor_uuid is not None)
        if publication.boundary.input_actor_uuid == actor_uuid:
            return runtime, seat, publication
        reply, _, _ = dispatch(runtime, Command(seat_id=seat, request=CommandRequest(
            command_number=number, actor_uuid=publication.boundary.input_actor_uuid,
            state_revision=publication.state_revision, intent=EndTurnIntent())))
        assert reply.rejection is None
    pytest.fail("The passive owner never received a turn")


def execute(world, behavior, *, target_uuid=None, first_face=2, command_number=20,
            facets=(), level=1, position=None):
    runtime, seat, publication = world
    choices = request_choices(world).choices
    offered = next(row for row in rows(choices)
        if row.behavior_id == behavior and row.can_afford
        and all(any(facet.key == key and facet.value == value for facet in row.variant_facets)
            for key, value in facets)
        and (row.cast_at_level is None or row.cast_at_level == level))
    bindings = choices.target_sets[offered.target_set]
    selected = () if position is not None else (next(binding.index for binding in bindings if binding.kind == "self"),) if target_uuid is None else (
        next(binding.index for binding in bindings if binding.kind == "subject"
            and choices.subjects[binding.subject].uuid == target_uuid),
    )
    with fixed_dice_faces(first_face, *([2] * 80)):
        reply, records, _ = dispatch(runtime, Command(seat_id=seat, request=CommandRequest(
            command_number=command_number, actor_uuid=publication.boundary.input_actor_uuid,
            state_revision=publication.state_revision,
            intent=ExecuteSelectionIntent(discovery_generation=choices.discovery_generation,
                selection=ActionSelection(offered.discovery_index, selected,
                    extra_target_positions=() if position is None else (position,))))))
    assert reply.rejection is None
    return tuple(PlayerOperation.model_validate_json(record.model_dump_json()) for record in records)


def nodes(record):
    return tuple(node for group in record.lineages for node in group.events)


def assert_emitted_result(record, behavior, owner_uuid, result_node):
    entries = [(node, attribution) for node in nodes(record)
        for attribution in node.content_attributions
        if attribution.role == "effective_handler" and attribution.behavior_id == behavior]
    assert entries, f"{behavior}: applied result has no public effective-handler attribution"
    versions = {occurrence: lineage for group in record.lineages
        for occurrence, lineage in zip(
            group.version_rows.occurrences, group.version_rows.lineages, strict=True)}
    result_lineage = versions[result_node.occurrence]
    assert any(attribution.source_entity_uuid == owner_uuid
        and attribution.outcome is HandlerDispatchOutcome.EMITTED_EVENTS
        and attribution.triggering_occurrence in versions
        and attribution.triggering_lineage == versions[attribution.triggering_occurrence]
        and result_lineage in attribution.emitted_lineages
        for _, attribution in entries), entries
    assert all(set(attribution.emitted_lineages) <= set(versions.values())
        for _, attribution in entries)


@pytest.mark.parametrize("heal_self", [False, True])
def test_blessed_healer_attributes_only_its_real_emitted_heal(workers, heal_self):
    cleric = replace(prepared_build(CharacterClass.CLERIC, 6),
        name="Life cleric", prepared_spells=(
            PreparedSpellSelection("class.cleric.spellcasting", ("spell.healing_word",)),
        ))
    runtime = workers(audience_ids={"party": uuid4()}, player_builds=(
        cleric, PREMADE_CHARACTER_BUILDS[FIGHTER_PREMADE_ID],
    ))
    caster, ally = (runtime.session.game.entities[identity]
        for identity in runtime.session.player_uuids)
    world = await_actor(runtime, caster.uuid)
    caster.receive_damage(10, DamageType.FORCE, ally.uuid)
    ally.receive_damage(10, DamageType.FORCE, caster.uuid)
    recipient = caster if heal_self else ally
    records = execute(world, "spell.healing_word", target_uuid=recipient.uuid)
    assert len(records) == 1
    record = records[0]
    heals = [node for node in nodes(record) if isinstance(node.fact, HealFact)
        and node.fact.actual_healing > 0]
    assert any(node.fact.target_entity_uuid == recipient.uuid for node in heals)
    feature = "class_feature.cleric.blessed_healer"
    if heal_self:
        assert not any(attribution.behavior_id == feature for node in nodes(record)
            for attribution in node.content_attributions)
    else:
        own_heal, = (node for node in heals if node.fact.target_entity_uuid == caster.uuid)
        assert own_heal.fact.actual_healing == 3
        assert_emitted_result(record, feature, caster.uuid, own_heal)


def turning_recipe(*, caster_premade=CLERIC_PREMADE_ID):
    battlefield = "battlefield.open_floor_bright"
    slots = []
    for side, source in (
        ("cleric", PremadeCharacterRosterSource(premade_id=caster_premade)),
        ("undead", AuthoredCreatureRosterSource(recipe=BESTIARY_CREATURE_RECIPES_BY_ID["skeleton"])),
    ):
        roster = EncounterRosterRecipe.create(roster_id=f"roster.passive_{side}", title=side,
            members=(EncounterRosterMember(member_id="owner", display_name=side,
                deployment_role=side, source=source),))
        slots.append(EncounterRosterSlot(roster_slot_id=side, roster=roster, faction_id=side,
            deployment_zone_id=side, controller_defaults=RosterControllerDefaults(
                controller=RosterControllerKind.HUMAN, participant_name=side)))
    deployment = EncounterDeploymentSpec.create(deployment_id="deployment.passive_turning",
        title="Passive turning", battlefield_id=battlefield, zones=(
            EncounterDeploymentZone(zone_id="cleric", ordered_slots=((6, 6),)),
            EncounterDeploymentZone(zone_id="undead", ordered_slots=((8, 6),)),
        ))
    return EncounterRecipe.create(encounter_id="encounter.passive_turning", title="Passive turning",
        battlefield_id=battlefield, deployment=deployment, roster_slots=tuple(slots),
        opening_policy=FixedRosterOpeningPolicy(roster_slot_id="cleric"))


@pytest.mark.parametrize("saved", [False, True])
def test_destroy_undead_attributes_only_failed_save_damage_in_each_seat(workers, saved):
    runtime = workers(audience_ids={"cleric": uuid4(), "undead": uuid4()},
        recipe=turning_recipe())
    caster = next(actor for actor in runtime.session.game.entities.values() if actor.name == "cleric")
    target = next(actor for actor in runtime.session.game.entities.values() if actor.name == "undead")
    world = await_actor(runtime, caster.uuid)
    records = execute(world, "action.class.cleric.turn_undead", first_face=20 if saved else 1)
    assert len(records) == 2
    feature = "class_feature.cleric.destroy_undead"
    for record in records:
        damage = [node for node in nodes(record) if isinstance(node.fact, DamageResultFact)
            and node.fact.target_entity_uuid == target.uuid]
        if saved:
            assert not damage
            assert not any(attribution.behavior_id == feature for node in nodes(record)
                for attribution in node.content_attributions)
        else:
            hit, = damage
            assert hit.fact.damage_type is DamageType.RADIANT and hit.fact.applied_damage > 0
            assert_emitted_result(record, feature, caster.uuid, hit)


@pytest.mark.parametrize("class_id,level,spell,source_id,damage_type", [
    (CharacterClass.CLERIC, 8, None, "class_feature.cleric.divine_strike", DamageType.RADIANT),
    (CharacterClass.PALADIN, 11, None, "class_feature.paladin.improved_divine_smite", DamageType.RADIANT),
    (CharacterClass.PALADIN, 5, "spell.divine_favor", "spell.divine_favor", DamageType.RADIANT),
    (CharacterClass.PALADIN, 5, "spell.searing_smite", "spell.searing_smite", DamageType.FIRE),
])
@pytest.mark.parametrize("outcome", ["hit", "immune", "miss"])
def test_weapon_rider_components_keep_exact_sources_and_affinity_results(
    workers, class_id, level, spell, source_id, damage_type, outcome,
):
    build = replace(prepared_build(class_id, level),
        item_loadout=(ItemLoadoutEntry("weapon.longsword", equipment_slot=WeaponSlot.MELEE_MAIN),),
        prepared_spells=() if spell is None else (
            PreparedSpellSelection("class.paladin.spellcasting", (spell,)),
        ))
    runtime = workers(audience_ids={"party": uuid4()}, player_builds=(build,))
    caster = runtime.session.game.entities[runtime.session.player_uuids[0]]
    world = await_actor(runtime, caster.uuid)
    target = next(actor for actor in runtime.session.game.entities.values() if caster.is_enemy(actor))
    target.move((caster.position[0] + 1, caster.position[1]))
    if outcome == "immune":
        add_modifier(target.health.damage_reduction, Channel.SELF_STATIC, Kind.RESISTANCE,
            ResistanceModifier(name="Authored rider immunity", source_entity_uuid=target.uuid,
                target_entity_uuid=target.uuid, value=ResistanceStatus.IMMUNITY,
                damage_type=damage_type))
    if spell == "spell.divine_favor":
        execute(world, spell, command_number=20)
        world = runtime, "party", runtime.publications["party"]
    before = EventQueue.event_cursor()
    behavior = spell if spell == "spell.searing_smite" else "action.attack"
    records = execute(world, behavior, target_uuid=target.uuid,
        command_number=21, first_face=1 if outcome == "miss" else 15,
        facets=(("form", "MELEE_MAIN"),) if spell == "spell.searing_smite" else ())
    public = [node.fact for record in records for node in nodes(record)
        if isinstance(node.fact, DamageResultFact) and node.fact.target_entity_uuid == target.uuid]
    native = [event for _, event in EventQueue.iter_events_since(before)
        if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == target.uuid]
    if outcome == "miss":
        assert not public and not native
        return
    result, = public
    applied, = native
    component, = (damage for damage in applied.damages
        if damage.effect_origin is not None and damage.effect_origin.source_id == source_id)
    assert applied.resolution is not None
    resolution, = (row for row in applied.resolution.components
        if row.source_damage_uuid == component.uuid)
    assert resolution.incoming_damage == 2
    assert resolution.after_affinity_damage == (0 if outcome == "immune" else 2)
    matching = [row for row in result.components if row.source_id == source_id]
    assert len(matching) == 1, (source_id, component.uuid, result.components)
    disclosed, = matching
    assert disclosed.source_damage_uuid == component.uuid
    assert disclosed.damage_type is damage_type
    assert disclosed.incoming_damage == resolution.incoming_damage
    assert disclosed.after_affinity_damage == resolution.after_affinity_damage
    assert result.applied_damage == applied.applied_damage


@pytest.mark.parametrize("hidden,blocked", [(False, False), (True, False), (False, True)])
def test_rider_attribution_respects_independent_sight_and_packet_defense(workers, tmp_path, hidden, blocked):
    runtime = workers(audience_ids={"cleric": uuid4(), "undead": uuid4()},
        recipe=turning_recipe(caster_premade=PALADIN_PREMADE_ID))
    caster = next(actor for actor in runtime.session.game.entities.values() if actor.faction == "cleric")
    target = next(actor for actor in runtime.session.game.entities.values() if caster.is_enemy(actor))
    target.move((caster.position[0] + 1, caster.position[1]))
    register_spell(caster, DivineFavor, caster_level=5)
    execute(await_actor(runtime, caster.uuid), "spell.divine_favor")
    if hidden:
        caster.add_condition(Invisible(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid))
    if blocked:
        add_modifier(target.health.damage_reduction, Channel.SELF_STATIC, Kind.VALUE,
            NumericalModifier(name="Whole packet defense", value=100,
                source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    cursor = EventQueue.event_cursor()
    initials = {seat: capture_interval(name="rider replay", start_cursor=0, end_cursor=cursor,
        observer_uuid=audience.observers[0], audience=audience,
        battlefield_id=runtime.session.battlefield.definition.battlefield_id)
        for seat, audience in runtime.session.seats.items()}
    records = execute((runtime, "cleric", runtime.publications["cleric"]), "action.attack",
        target_uuid=target.uuid, command_number=21, first_face=15)
    assert len(records) == 2
    native_rider = None
    if not blocked:
        native_rider, = (component for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION
            for component in event.components if component.source_id == "spell.divine_favor")
    for record in records:
        results = [node.fact for node in nodes(record) if isinstance(node.fact, DamageResultFact)]
        if blocked:
            assert not results
            continue
        result, = results
        assert native_rider is not None
        rider, = (component for component in result.components
            if component.source_damage_uuid == native_rider.source_damage_uuid)
        assert rider.damage_type is DamageType.RADIANT and rider.after_affinity_damage > 0
        if hidden and record.observer_uuid != caster.uuid:
            assert result.source_entity_uuid is None
            assert rider.source_entity_uuid is None and rider.source_id is None
        else:
            assert rider.source_entity_uuid == caster.uuid and rider.source_id == "spell.divine_favor"
    if not hidden and not blocked:
        roots = tuple(event for _, event in EventQueue.iter_events_since(cursor)
            if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
        for seat, audience in runtime.session.seats.items():
            native = RecordedSequence(initialization=initials[seat], lineages=capture_lineages(
                roots, observer_uuid=audience.observers[0], audience=audience))
            path = tmp_path / f"{seat}.json"
            path.write_text(native.model_dump_json())
            expected = encode_player_sequence(project_sequence(
                RecordedSequence.model_validate_json(path.read_text(), context=PASSIVE_EVENT_REPLAY)))
            replay = subprocess.run([sys.executable, "-c",
                "import sys; from pathlib import Path; "
                "from dnd.core.base_object import PASSIVE_EVENT_REPLAY; "
                "from dnd.player.recorded import RecordedSequence, project_sequence; "
                "from dnd.player.reduction import encode_player_sequence; "
                "sys.stdout.buffer.write(encode_player_sequence(project_sequence("
                "RecordedSequence.model_validate_json(Path(sys.argv[1]).read_text(), "
                "context=PASSIVE_EVENT_REPLAY))))", str(path)],
                env={**os.environ, "PYTHONHASHSEED": "71"}, capture_output=True, check=True)
            assert replay.stdout == expected
