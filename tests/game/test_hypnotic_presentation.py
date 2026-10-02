"""Real concentration slots own cosmetic areas; target recovery never changes membership."""

from dataclasses import replace

import pygame
import pytest

from dnd.core.presentation_geometry import CubePresentationGeometry
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.condition_animation import resolve_condition_appearance
from game.concentration_media import register_concentration_lifetimes, concentration_media_draw_commands
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from tests.game.hypnotic_scenarios import hypnotic_history


@pytest.fixture(scope='module')
def data():
    pygame.init()
    pygame.display.set_mode((1,1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize('mode', ('clear','damage_one','recast'))
def test_native_slots_and_square_corner_recovery_replay(data, mode):
    history = hypnotic_history(mode=mode)
    for observer in ('caster','recipient'):
        before, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views[observer])))
        retained = {}
        witnessed = set()
        now = 0.
        recovered_with_slot = False
        for root in roots:
            group = bind_choreography(before,root,data)
            assert not group.gaps
            retained = register_concentration_lifetimes(retained,before,data,absolute_start_ms=now,
                lineage=root,choreography=group)
            after = reduce_lineage(before,root)
            live = [row for row in retained.values() if row.removed_ms is None]
            witnessed.update(row.slot_uuid for row in live)
            caster = next(a for a in after.actors.values() if a.name=='Caster')
            slots = [slot for condition in caster.conditions if condition.state is not None
                for slot in condition.state.concentration_slots]
            assert {row.slot_uuid for row in live} == {slot.slot_uuid for slot in slots
                if slot.spell_id=='spell.hypnotic_pattern'}
            for actor in after.actors.values():
                if any(c.behavior_id=='condition.spell.hypnotic_pattern' for c in actor.conditions):
                    appearance = resolve_condition_appearance(actor.conditions,data.condition_recipes,data.condition_media)
                    assert not appearance.unsupported
                    assert appearance.frozen_pose is None  # Actual native speed/agency restriction is separate.
                    assert any(layer.layer.assetId=='control.incapacitated.front' for layer in appearance.layers)
            if live:
                record = live[0]
                assert isinstance(record.geometry,CubePresentationGeometry)
                if record.geometry.origin == (9,7):
                    assert (6,4) in record.positions  # Outside radius-15 circle, inside native square.
                for quadrant in range(4):
                    commands = concentration_media_draw_commands(after,data,record.applied_ms+1000,
                        Camera(quadrant=quadrant,zoom=1),retained)
                    assert commands
                    assert sum(pygame.surfarray.array_alpha(c.surface).sum() for c in commands) > 0
                # Cold state alone cannot invent a cosmetic cast anchor.
                assert register_concentration_lifetimes({},after,data,absolute_start_ms=now)=={}
                unknown = replace(after,actors={k:a for k,a in after.actors.items() if a.uuid!=caster.uuid})
                still = register_concentration_lifetimes(retained,unknown,data,absolute_start_ms=now)
                assert still[record.slot_uuid].removed_ms is None
                recipient = next(a for a in after.actors.values() if a.name=='Recipient')
                second = next(a for a in after.actors.values() if a.name=='Second')
                if not any(c.behavior_id=='condition.spell.hypnotic_pattern' for c in recipient.conditions):
                    assert any(c.behavior_id=='condition.spell.hypnotic_pattern' for c in second.conditions)
                    recovered_with_slot = True
            now += group.complete_ms + 2000
            before = after
        assert len(witnessed)==(2 if mode=='recast' else 1)
        assert recovered_with_slot is (mode=='damage_one')
        assert all(row.removed_ms is not None for row in retained.values())
