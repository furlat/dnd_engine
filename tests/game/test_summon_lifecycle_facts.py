"""Native lifecycle witnesses survive passive replay without disclosing hidden history."""

from uuid import uuid4

import pytest

from dnd.actions_functional import setup_standard_actions
from dnd.actor_projection import actor_from_birth
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.controller import HumanController
from dnd.core.base_object import BaseObject, PASSIVE_EVENT_REPLAY
from dnd.core.dice import DiceRoll, fixed_dice_faces
from dnd.core.events import EntityCreatedEvent, EventPhase, EventQueue, SpatialChangeType
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.summoning import ConjureAnimals, ConjureFey
from dnd.summoning.system import bind_summoning
from dnd.types.summoning import SummonDepartureCause, SummonManifestation
from dnd.player.facts import DamageResultFact, FactionFact, SpatialFact
from dnd.player.event_record import decode_event, encode_event
from dnd.player.recorded import project_sequence
from dnd.player.reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from dnd.player.capture import capture_interval, reduce_interval
from dnd.player.recorded import ObserverCapture, RecordedSequence, capture_history
from tests.game.test_summoning_presentation import summon_history


def lifecycle_history(ending, *, hidden=False):
    """Record remaining native owner paths, including reversible redeployment."""
    reset_engine_runtime()
    if not SERVER_CONTENT_SYSTEM_RUNTIME.is_installed:
        SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    built = build_battlefield("battlefield.visibility_open_range")
    game = Game()
    encounter = Encounter(source_entity_uuid=uuid4(), name="Lifecycle witnesses")
    try:
        actors = []
        for name, position, faction in (("Caster", (2, 2), "heroes"), ("Witness", (7, 2), "enemy")):
            actor = Entity.create(uuid4(), name, config=EntityConfig(position=position, faction=faction,
                action_economy=ActionEconomyConfig(spell_slots={3: 2, 6: 2}),
                spellcasting=SpellcastingConfig(spellcasting_ability="wisdom")))
            setup_standard_actions(actor)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
            actors.append(actor)
        caster, witness = actors
        encounter.initiative_order = [actor.uuid for actor in actors]
        with fixed_dice_faces(15, 1):
            encounter.start_encounter()
        encounter.start_turn()
        system = bind_summoning(game, encounter)
        Entity.update_all_entities_senses()
        cursor = EventQueue.event_cursor()
        initial = capture_interval(name="Before cast", start_cursor=0, end_cursor=cursor,
            observer_uuid=caster.uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)
        spell = ConjureFey if ending == "ordinary_faction" else ConjureAnimals
        result = spell(source_entity_uuid=caster.uuid, form_id="wolf", end_position=(4, 2)).apply()
        assert result is not None and not result.canceled
        member, = system.memberships.values()
        identity = member.entity.uuid
        if hidden:
            Entity.update_entity_position(witness, (25, 2))
        if ending == "expired":
            # Start this native duration step at the final remaining round.
            member.existence.duration.duration = 1
            member.entity.turn_duration_interval = (encounter.uuid, encounter.round_number + 1)
            assert member.entity.advance_duration_condition("Summoned")
        elif ending == "sustain_lost":
            caster.receive_instant_death(witness.uuid)
        elif ending == "closed":
            system.close()
        elif ending == "reenter":
            assert game.remove_entity(identity) is member.entity
            game.deploy_entity(member.entity, (4, 2))
        elif ending == "ordinary_faction":
            assert member.control is not None and member.control.applied
            assert member.entity.set_faction("new_allegiance") is not None
            assert member.control.applied
        history = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, cursor) for role, actor in zip(("caster", "witness"), actors)))
        return history, identity
    finally:
        game.close()
        reset_engine_runtime()


def public_view(history, view):
    """Load the retained record after teardown; no live rules participate."""
    rolls = dict(DiceRoll._registry)
    native = RecordedSequence.model_validate_json(history.views[view].model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    payload = encode_player_sequence(project_sequence(native))
    assert b'"summon_origin"' not in payload and b'"summoner_uuid"' not in payload
    assert b'"existence_condition_uuid"' not in payload and b'"control_condition_uuid"' not in payload
    before, roots = decode_player_sequence(payload)
    assert EventQueue.event_cursor() == 0 and BaseObject._registry == {} and DiceRoll._registry == rolls
    return native, before, roots


def test_recorded_wolf_initial_traits_keep_explicit_authored_identity():
    history, identity, _ = summon_history("dismiss")
    native, _, roots = public_view(history, "witness")
    birth, = [event for root in native.lineages for event in root.events
        if isinstance(event, EntityCreatedEvent) and event.entity_uuid == identity]
    expected = {"Keen Hearing and Smell": "trait.keen_hearing_and_smell",
        "Pack Tactics": "trait.pack_tactics", "Bite Prone Rider": "trait.wolf_bite_prone"}
    actor = actor_from_birth(birth)
    assert {row.name: row.behavior_id for row in actor.conditions if row.name in expected} == expected
    observed = next(row.actor for root in roots for row in root.observations if row.actor.uuid == identity)
    assert {row.name: row.behavior_id for row in observed.conditions if row.name in expected} == expected


def test_legacy_birth_without_explicit_condition_identity_does_not_guess_from_semantics():
    history, identity, _ = summon_history("dismiss")
    birth, = [event for root in history.views["witness"].lineages for event in root.events
        if isinstance(event, EntityCreatedEvent) and event.entity_uuid == identity]
    payload = encode_event(birth)
    for state in payload["initial_condition_states"]:
        state.pop("behavior_id", None)
    restored = decode_event(payload)
    assert isinstance(restored, EntityCreatedEvent)
    actor = actor_from_birth(restored)
    assert actor.conditions and all(row.behavior_id is None for row in actor.conditions)
    assert any(row.state is not None and row.state.semantic_key == "trait.pack_tactics"
               for row in actor.conditions)
    assert EventQueue.event_cursor() == 0 and BaseObject._registry == {}


@pytest.mark.parametrize("family,manifestation", (("animals", SummonManifestation.NATURAL),
    ("fey", SummonManifestation.FEY_SPIRIT), ("fiend", SummonManifestation.FIEND)))
def test_first_visible_placement_links_one_private_birth(family, manifestation):
    history, identity, origin = summon_history("dismiss", family=family)
    for view in ("caster", "witness"):
        native, _, roots = public_view(history, view)
        births = [event for root in native.lineages for event in root.events
            if isinstance(event, EntityCreatedEvent) and event.entity_uuid == identity]
        birth, = births
        assert birth.phase is EventPhase.COMPLETION and not birth.canceled
        assert birth.parent_lineage == origin.cast_lineage_uuid
        creation, = [node for root in roots for node in root.events
            if isinstance(node.fact, SpatialFact) and node.fact.creation is not None]
        assert isinstance(creation.fact, SpatialFact) and creation.fact.creation is not None
        assert creation.fact.entity_uuid == identity and creation.fact.position == (4, 2)
        assert creation.fact.creation.birth_event_uuid == birth.uuid
        assert creation.fact.creation.manifestation is manifestation
        assert creation.parent_lineage == birth.parent_lineage
        birth_node, = [node for root in roots for node in root.events if node.uuid == birth.uuid]
        assert birth_node.fact is None


@pytest.mark.parametrize("visibility,expected_creations", (("hidden_birth", 0), ("reacquire", 1)))
def test_reacquisition_receives_current_fey_without_replaying_hidden_lifecycle(visibility, expected_creations):
    history, identity, _ = summon_history("control_loss", visibility=visibility)
    _, state, roots = public_view(history, "witness")
    creations = [node.fact.creation for root in roots for node in root.events
        if isinstance(node.fact, SpatialFact) and node.fact.creation is not None]
    assert len(creations) == expected_creations
    assert not any(isinstance(node.fact, FactionFact) and node.fact.control_lost
                   for root in roots for node in root.events)
    for root in roots:
        state = reduce_lineage(state, root)
    assert state.actors[identity].present
    assert state.actors[identity].faction != "heroes"
    assert state.actors[identity].manifestation is SummonManifestation.FEY_SPIRIT


def test_reversible_removal_and_redeployment_do_not_replay_creation_or_terminal_cause():
    history, identity = lifecycle_history("reenter")
    _, _, roots = public_view(history, "witness")
    placements = [node.fact for root in roots for node in root.events
        if isinstance(node.fact, SpatialFact) and node.fact.entity_uuid == identity]
    entries = [fact for fact in placements if fact.change_type is SpatialChangeType.ENTITY_ENTERED]
    assert len(entries) == 2
    assert entries[0].creation is not None and entries[1].creation is None
    assert not any(fact.terminal_departure or fact.terminal_cause is not None for fact in placements)


def test_only_exact_fey_control_removal_marks_observed_faction_change():
    history, identity, _ = summon_history("control_loss")
    for view in ("caster", "witness"):
        _, state, roots = public_view(history, view)
        change, = [node.fact for root in roots for node in root.events if isinstance(node.fact, FactionFact)]
        assert change.entity_uuid == identity and change.control_lost
        assert not any(isinstance(node.fact, SpatialFact) and node.fact.terminal_departure
                       for root in roots for node in root.events)
        for root in roots:
            state = reduce_lineage(state, root)
        assert state.actors[identity].present and state.actors[identity].faction == change.faction_after
    ordinary, same_creature = lifecycle_history("ordinary_faction")
    _, _, roots = public_view(ordinary, "witness")
    change, = [node.fact for root in roots for node in root.events if isinstance(node.fact, FactionFact)]
    assert change.entity_uuid == same_creature and not change.control_lost


def test_defeat_witness_keeps_lethal_injury_when_ordinary_body_would_make_death_saves():
    history, identity, _ = summon_history("defeat", death_saves=True)
    for view in ("caster", "witness"):
        _, _, roots = public_view(history, view)
        injury, = [node for root in roots for node in root.events
            if isinstance(node.fact, DamageResultFact) and node.fact.target_entity_uuid == identity]
        departure, = [node for root in roots for node in root.events
            if isinstance(node.fact, SpatialFact) and node.fact.terminal_departure]
        assert isinstance(injury.fact, DamageResultFact) and injury.fact.body_release is not None
        assert isinstance(departure.fact, SpatialFact)
        assert departure.fact.terminal_cause is SummonDepartureCause.DEFEATED
        order = {row.event_uuid: row.source_index for root in roots for row in root.version_rows}
        assert order[injury.uuid] < order[departure.uuid]


@pytest.mark.parametrize("ending,cause", (("dismiss", SummonDepartureCause.DISMISSED),
    ("defeat", SummonDepartureCause.DEFEATED), ("instant_death", SummonDepartureCause.DEFEATED),
    ("expired", SummonDepartureCause.EXPIRED), ("sustain_lost", SummonDepartureCause.SUSTAIN_LOST),
    ("closed", SummonDepartureCause.CLOSED)))
@pytest.mark.parametrize("hidden", (False, True))
def test_only_observed_terminal_removal_discloses_its_native_cause(ending, cause, hidden):
    if ending in ("dismiss", "defeat", "instant_death"):
        history, identity, _ = summon_history(ending, visibility="hidden_departure" if hidden else "visible")
    else:
        history, identity = lifecycle_history(ending, hidden=hidden)
    _, state, roots = public_view(history, "witness")
    departures = [node.fact for root in roots for node in root.events
        if isinstance(node.fact, SpatialFact) and node.fact.terminal_departure]
    if hidden:
        assert not departures
        assert not any(isinstance(node.fact, SpatialFact) and node.fact.terminal_cause is not None
                       for root in roots for node in root.events)
    else:
        departure, = departures
        assert departure.entity_uuid == identity and departure.terminal_cause is cause
    for root in roots:
        state = reduce_lineage(state, root)
    assert state.actors[identity].present is hidden
