"""Real utility casts retain the accepted hand-only screen layer and its clock."""

from dataclasses import replace

import pygame
import pytest

from game.animation_data import load_animation_data
from game.animation_draw import LoadedBodyRows
from game.choreography import bind_choreography
from game.choreography_draw import load_choreography_media
from game.playback_frame import sample_playback_frame
from game.player_facts import SpellFact
from game.player_reduction import reduce_lineage, stage_lineage
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from tests.game.antimagic_scenarios import antimagic_history
from tests.game.forced_movement_scenarios import forced_movement_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def graphics():
    pygame.init()
    pygame.display.set_mode((640, 480))
    yield load_animation_data(), pygame.font.Font(None, 20)
    pygame.quit()


@pytest.mark.parametrize("program", ("antimagic_field", "telekinesis"))
def test_actual_cast_hands_are_visible_during_preparation_and_gone_after_cast(graphics, program):
    data, font = graphics
    history = (antimagic_history() if program == "antimagic_field" else
        forced_movement_history(mechanism="telekinesis", initial_cast=True, destination=(6, 3)))
    before, roots = player_history(history)
    identity = "spell." + program
    for root in roots:
        if isinstance(root.root.fact, SpellFact) and root.root.fact.behavior_id == identity:
            break
        before = reduce_lineage(before, root)
    else:
        raise AssertionError("Missing real utility cast")
    caster = str(root.root.fact.source_entity_uuid)
    draft = data.drafts[identity]
    plain_draft = draft.model_copy(update={"cast": draft.cast.model_copy(update={"weaponGlow": None})})
    plain = replace(data, drafts={**data.drafts, identity: plain_draft})

    def draw(selected_data, time, quadrant):
        group = bind_choreography(before, root, selected_data)
        assert not group.gaps, group.gaps
        rows: LoadedBodyRows = {}
        bodies = load_scene_media(scene_actors(stage_lineage(before, root), selected_data, {}),
            selected_data, body_rows=rows)
        media = load_choreography_media(group, body_rows=rows)
        camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((4.5, 4.5))
        frame = sample_playback_frame(before, group.after, selected_data, time, time, camera, {},
            bodies, font, font, choreography=group, choreography_media=media)
        actor, = (row for row in frame.commands if row[4][0] == caster and row[4][6] == "actor")
        return pygame.image.tobytes(actor[1], "RGBA"), group.complete_ms

    for quadrant in range(4):
        glowing, complete = draw(data, 500, quadrant)
        untreated, _ = draw(plain, 500, quadrant)
        assert glowing != untreated, "source hand pixels must reach the actual body in every camera"
        settled, _ = draw(data, complete + 1, quadrant)
        plain_settled, _ = draw(plain, complete + 1, quadrant)
        assert settled == plain_settled, "the finite casting accent must not remain on idle hands"
