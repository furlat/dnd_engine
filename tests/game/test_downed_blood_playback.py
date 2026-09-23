"""The review downing encounter carries real blood through its interrupted move."""

from pathlib import Path

import pygame

from dnd.core.creature_types import DamageType
from dnd.core.events import EventQueue
from dnd.core.life_types import LifeState
from devtools.animation_review.cases import load_cases
from devtools.animation_review.produce import produce
from game.action_media import sample_action_strip
from game.animation_data import load_animation_data
from game.animation_draw import action_media_draw_commands
from game.animation_types import ParticleMediaAsset
from game.choreography import sample_choreography
from game.motion import bind_motion, sample_motion
from game.player_facts import DamageFact
from game.projection import Camera
from tests.game.player_helpers import player_history, visible_contact


def test_actual_downed_review_releases_blood_at_held_body_and_leaves_native_floor_state():
    captured = produce(next(case for case in load_cases() if case.id == "walk-downed"))
    before, (lineage,) = player_history(captured)
    injury, = (node.fact for node in lineage.events
               if isinstance(node.fact, DamageFact) and node.fact.stage == "applied")
    release = injury.body_release
    target = injury.target_entity_uuid
    assert target is not None
    assert release is not None and release.release_id == "body.blood"
    assert release.pattern == "slashing" and release.primary_damage_type is DamageType.SLASHING
    assert not release.critical_hit
    receiving = {cell for region in release.regions for cell in region.positions}
    assert release.position == (3, 3) and len(receiving) > 1

    data = load_animation_data(rig_files=(Path("game/data/rigs/goblin01.json"),))
    motion = bind_motion(before, lineage, data)
    assert motion is not None
    reaction, = motion.reactions
    group = reaction.choreography
    assert not group.gaps
    cue, = group.strips
    assert cue.release == release and isinstance(cue.asset, ParticleMediaAsset)
    held = visible_contact(sample_motion(motion, data, reaction.start_ms))
    assert cue.contact.grid == held.grid and held.grid != release.position
    assert sample_choreography(group, cue.start_ms - .001).displayed.actors[target].normal_hp == 4
    impact = sample_choreography(group, cue.start_ms)
    assert impact.displayed.actors[target].normal_hp == 0
    assert impact.displayed.actors[target].life_state is LifeState.DYING
    assert sample_action_strip(cue, cue.start_ms - .001) is None
    strip = sample_action_strip(cue, cue.start_ms + 180)
    assert strip is not None
    assert {change.position for change in group.residue_reveals} == receiving
    assert all(any(residue.residue_id == "residue.blood" and residue.amount == 1
                   for residue in group.after.tiles[cell].residues) for cell in receiving)
    final = visible_contact(sample_motion(motion, data, motion.complete_ms))
    assert final.life_state is LifeState.DYING and final.hp == 0 and final.grid == held.grid
    assert EventQueue.event_cursor() == 0

    pygame.init()
    pygame.display.set_mode((640, 480))
    try:
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus(held.grid)
            commands = action_media_draw_commands(strip, {}, camera)
            assert commands and any(pygame.surfarray.array_alpha(command.surface).any() for command in commands)
    finally:
        pygame.quit()
