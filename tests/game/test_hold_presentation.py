"""Native Hold facts own original chains separately from shared paralysis."""

from dataclasses import replace
from uuid import uuid4

import pygame
import pytest

from dnd.core.condition_types import ConditionCategory
from game.actor_facts import ConditionFact
from game.animation import ActorContact, BodySample, body_clip
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.combat import BoundCast
from game.condition_animation import condition_body_pose, resolve_condition_appearance
from game.condition_media_lifetime import ConditionMediaLifetime, sample_condition_lifetimes
from game.condition_sampling import sample_condition_media
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from tests.game.hold_scenarios import hold_history


@pytest.fixture(scope='module')
def data():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize('program', ('hold_person', 'hold_monster'))
@pytest.mark.parametrize('saved,retain', ((False, False), (True, False), (False, True)))
def test_native_hold_clear_and_save_keep_separate_paralysis_facts(data, program, saved, retain):
    history = hold_history(program=program, saved=saved, retain_paralysis=retain)
    for observer in ('caster', 'recipient'):
        before, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views[observer])))
        witnessed = False
        witnessed_cast = False
        for root in roots:
            group = bind_choreography(before, root, data)
            assert not group.gaps
            for cue in group.body_actions:
                if cue.recipe_id == 'spell.' + program:
                    witnessed_cast = True
                    assert cue.clip == 'Attack5'
                    assert {layer.slot for layer in cue.cast_layers} == {'weaponGlow', 'aura'}
                    assert next(layer.category for layer in cue.cast_layers
                                if layer.slot == 'weaponGlow') == 'Magic2'
                    assert all(layer.category in body_clip(data,cue.contact,cue.clip).sheets
                               for layer in cue.cast_layers)
            for node in group.nodes:
                if isinstance(node.bound, BoundCast):
                    assert node.bound.timeline.recipe.definitionRef.content_id == 'spell.' + program
            before = reduce_lineage(before, root)
            recipient = next(actor for actor in before.actors.values() if actor.name == 'Recipient')
            identities = {member.behavior_id for member in recipient.conditions}
            if 'condition.spell.' + program in identities:
                assert 'condition.paralyzed' in identities
                appearance = resolve_condition_appearance(recipient.conditions, data.condition_recipes, data.condition_media)
                assert not appearance.unsupported
                assert appearance.frozen_pose is not None and appearance.frozen_pose.framesByRig['neuroclient.modular'] == 3
                assert appearance.body_outline is not None
                assert [layer.layer.markerGroup for layer in appearance.layers if layer.layer.markerGroup] == ['paralyzed']
                assert len([layer for layer in appearance.layers if not layer.layer.markerGroup]) == 2
                assert {layer.media.asset_id for layer in appearance.layers if not layer.layer.markerGroup} == {
                    'control.hold_human.hold.back', 'control.hold_human.hold.front'}
                witnessed = True
        assert witnessed_cast
        assert witnessed is not saved
        recipient = next(actor for actor in before.actors.values() if actor.name == 'Recipient')
        identities = {member.behavior_id for member in recipient.conditions}
        assert 'condition.spell.' + program not in identities
        assert ('condition.paralyzed' in identities) is retain
        assert recipient.normal_hp == 120


def test_quiet_hold_never_replays_bind_and_release_preserves_the_original_clock(data):
    actor, hold, paralysis, other = uuid4(), uuid4(), uuid4(), uuid4()
    def fact(identity, owner):
        return ConditionFact(condition_uuid=owner, category=ConditionCategory.CONDITION,
            behavior_id=identity, event_uuid=uuid4(), name=identity,
            resulting_max_hp=None, resulting_ac=None)
    held = fact('condition.spell.hold_person', hold)
    paused = fact('condition.paralyzed', paralysis)
    independent = fact('condition.paralyzed', other)
    appearance = resolve_condition_appearance((held, paused, independent), data.condition_recipes, data.condition_media)
    assert len([layer for layer in appearance.layers if not layer.layer.markerGroup]) == 2
    assert [layer.layer.markerGroup for layer in appearance.layers if layer.layer.markerGroup] == ['paralyzed']
    record = ConditionMediaLifetime(actor, hold, 'condition.spell.hold_person', applied_ms=None)
    samples = sample_condition_lifetimes({str(actor): appearance}, {hold: record}, data, 8000)[str(actor)]
    assert all(sample.asset_id.endswith('.hold.' + side) and sample.frame == 0
        for layer, side in zip((layer for layer in samples.layers if not layer.layer.markerGroup), ('back', 'front'), strict=True) for sample in sample_condition_media(data, layer))
    survived = resolve_condition_appearance((independent,), data.condition_recipes, data.condition_media)
    removed = replace(record, removed_ms=8000,
        removed_layers=tuple(layer.layer.assetId for layer in samples.layers if layer.owner_uuid == hold))
    at = sample_condition_lifetimes({str(actor): survived}, {hold: removed}, data, 8075)[str(actor)]
    assert at.body_outline is not None and at.frozen_pose is not None
    chains = tuple(layer for layer in at.layers if not layer.layer.markerGroup)
    assert len(chains) == 2
    assert [layer.layer.markerGroup for layer in at.layers if layer.layer.markerGroup] == ['paralyzed']
    for layer in chains:
        banks = sample_condition_media(data, layer)
        assert len(banks) == 2 and [bank.alpha for bank in banks] == [.5, .5]
        assert '.hold.' in banks[0].asset_id and '.release.' in banks[1].asset_id
    contact = ActorContact(str(actor), (3, 4), 'E', 1)
    pose = condition_body_pose(data, BodySample(str(actor), 'Idle', 12, 'E'), contact, at)
    assert pose.frame == 3 and pose.clip == 'Idle'
    final = sample_condition_lifetimes({str(actor): survived}, {hold: removed}, data, 11000)[str(actor)]
    assert not any(not layer.layer.markerGroup for layer in final.layers)
    assert [layer.layer.markerGroup for layer in final.layers] == ['paralyzed']
    assert final.body_outline is not None and final.frozen_pose is not None
