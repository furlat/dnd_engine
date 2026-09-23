"""Mechanical field removal is distinct from losing the field's visible contact."""

from uuid import uuid4

import pytest

from devtools.animation_review.control_cases import control_spell_history
from dnd.actions_functional import register_spell
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.conditions import Blinded
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue, SpatialEffectChangeEvent
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.illusion import Silence
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from game.player_facts import SensoryFact, SpatialEffectStateFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence
from game.presentation import capture_interval, reduce_interval
from game.replay import ObserverCapture, RecordedSequence, capture_history


def public_roots(native):
    saved = RecordedSequence.model_validate_json(native.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    _, roots = decode_player_sequence(encode_player_sequence(project_sequence(saved)))
    assert EventQueue.event_cursor() == 0
    return roots


@pytest.mark.parametrize("program,remove_first", (("silence", "independent"),
    ("deafness-overlap", "independent"), ("deafness-overlap", "area")))
def test_real_silence_removal_survives_saved_both_player_views(program, remove_first):
    history = control_spell_history(program=program, remove_first=remove_first)
    for native in history.views.values():
        removed, = (event for root in native.lineages for event in root.events
            if isinstance(event, SpatialEffectChangeEvent)
            and event.operation is SpatialEffectChangeOperation.REMOVED)
        assert removed.previous_positions and not removed.affected_positions
        roots = public_roots(native)
        nodes = [node for root in roots for node in root.events
            if isinstance(node.fact, SpatialEffectStateFact)
            and node.fact.operation is SpatialEffectChangeOperation.REMOVED]
        node, = nodes
        assert node.uuid == removed.uuid and node.parent_lineage == removed.parent_lineage
        assert isinstance(node.fact, SpatialEffectStateFact)
        assert node.fact.spatial_effect_uuid == removed.spatial_effect_uuid
        assert set(node.fact.positions) == set(removed.previous_positions)
        root = next(root for root in roots if node in root.events)
        assert any(isinstance(event.fact, SensoryFact)
            and removed.spatial_effect_uuid in event.fact.spatial_effects_removed for event in root.events)


def hidden_removal_history(*, never_observed: bool):
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        caster = Entity.create(uuid4(), "Caster", config=EntityConfig(position=(3, 6),
            action_economy=ActionEconomyConfig(spell_slots={2: 1})))
        observer = Entity.create(uuid4(), "Observer", config=EntityConfig(position=(4, 6)))
        register_spell(caster, Silence)
        for actor in (caster, observer):
            actor.compose_entity()
            game.deploy_entity(actor, actor.position)
        start = EventQueue.event_cursor()
        initial = capture_interval(name="Field removal visibility", start_cursor=0, end_cursor=start,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)

        def blind():
            observer.add_condition(Blinded(source_entity_uuid=caster.uuid, target_entity_uuid=observer.uuid))
            assert not observer.can_see_visual_effects()

        if never_observed:
            blind()
        template = next(action for action in caster.registered_actions if isinstance(action, Silence))
        result = template.instantiate(end_position=(9, 6), cast_at_level=2).apply()
        assert result is not None and not result.canceled
        if not never_observed:
            assert observer.senses.spatial_effects
            blind()
        assert not any(observer.senses.visible.values())
        # Native spatial memory deliberately survives sight loss. Projection
        # must require present sight rather than treating memory as contact.
        assert bool(observer.senses.spatial_effects) is not never_observed
        assert caster.remove_condition("Concentrating")
        return capture_history(before, (), observers=(
            ObserverCapture("caster", caster.uuid, start), ObserverCapture("observer", observer.uuid, start)))
    finally:
        game.close()
        reset_engine_runtime()


@pytest.mark.parametrize("never_observed", (False, True))
def test_unseen_removal_cannot_reuse_old_contact_or_infer_a_dissolve(never_observed):
    history = hidden_removal_history(never_observed=never_observed)
    roots = public_roots(history.views["observer"])
    facts = [node.fact for root in roots for node in root.events
        if isinstance(node.fact, SpatialEffectStateFact)]
    assert not any(fact.operation is SpatialEffectChangeOperation.REMOVED for fact in facts)
    assert any(fact.operation is SpatialEffectChangeOperation.CREATED for fact in facts) is not never_observed
    # Blindness neither destroys the field nor reports its later unseen removal.
    assert not any(isinstance(node.fact, SensoryFact) and node.fact.spatial_effects_removed
        for root in roots for node in root.events)
    caster_facts = [node.fact for root in public_roots(history.views["caster"]) for node in root.events
        if isinstance(node.fact, SpatialEffectStateFact)]
    assert sum(fact.operation is SpatialEffectChangeOperation.REMOVED for fact in caster_facts) == 1
