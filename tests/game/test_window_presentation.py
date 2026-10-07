"""Window graphics consume captured facts with the engine reset between replays."""

from uuid import uuid4
from dataclasses import replace

import pygame
import pytest
import numpy as np

from dnd.core.base_actions import AvailableActionInfo, AvailableActionsResult, AvailableTarget, ActionAvailabilityStatus, TargetType
from dnd.core.events import EventQueue
from dnd.core.item_types import ItemIntegrity
from dnd.entity import Entity
from dnd.types.world import CardinalDirection
from game.ui.world_interaction import target_at
from game.interaction_frame import pick_world
from game.environment_animation import remnant_bank
from game.environment_art import load_environment_art, sample_environment_frame
from game.environment_draw import environment_selection_command, pick_environment_target
from dnd.player.facts import MovementFact
from dnd.player.reduction import reduce_lineage
from game.projection import Camera, pick_support
from tests.game.test_environment_presentation import _saved, _render_head
from game.assets import SurfaceCache, load_catalog
from game.animation_data import load_animation_data
from game.animation import BodySample, body_clip
from game.animation_draw import actor_draw_commands, load_actor_media
from game.combat import actor_contact
from game.app import draw_frame
from game.animation_data import resolve_player_layers
from game.environment_draw import environment_command
from game.environment_draw import environment_aperture_image
from game.area_media import BoundarySprite
from game.boundary_occlusion import clip_actor_boundaries
from game.draw_commands import DrawCommand
from game.projection import painter_key
from game.choreography import sample_motion, motion_leg_contact, MotionLeg
from game.animation import body_elevation_steps, ActorContact
from game.connector_motion import passage_point
from game.projection import project_screen, HEIGHT_STEP_PIXELS, TILE_WIDTH
from game.projection import camera_pose


@pytest.fixture(scope="module")
def raster():
    pygame.init()
    screen = pygame.display.set_mode((600,450))
    catalog, data = load_catalog(), load_animation_data()
    fonts = tuple(pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                  for style in (data.number_style, data.badge_style))
    yield screen, catalog, SurfaceCache(catalog), data, fonts
    pygame.quit()
from tests.game.window_scenarios import window_history


@pytest.mark.parametrize('code', ('g8', 'a5', 'd16'))
@pytest.mark.parametrize('quadrant', range(4))
def test_wall_covers_opaque_pixels_during_attack(raster, quadrant, code):
    state, _ = _saved(window_history(family=f'environment.window.fantasy_{code}').views['attacker'])
    screen, catalog, cache, data, _ = raster
    actor = state.actors[state.observer_uuid]
    behind = (5,4) if quadrant in (0,1) else (6,4)
    contact = replace(actor_contact(state, actor, data), grid=behind, facing='E' if behind == (5,4) else 'W')
    layers = resolve_player_layers(data, actor, rig_id=contact.rig_id)
    media = load_actor_media(data, ((contact,layers,('Attack1',)),), all_facings=True)
    camera = Camera(quadrant=quadrant, zoom=1, viewport=screen.get_size()).with_focus((5.5,4))
    art = load_environment_art()
    wall = next(obj for obj in state.objects.values() if obj.item.item_id.endswith(f'fantasy_{code}.wall'))
    bank = art.props[wall.item.item_id].intact['default']
    pose = camera_pose('east',quadrant)
    command = environment_command(bank,0,identity=wall.item.item_uuid,position=(5,4),
        elevation=0,pose=pose,boundary_pose=pose,camera=camera,multiplier=(1,1,1))
    solid = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    solid.blit(command.surface,command.destination)
    opaque = pygame.surfarray.array_alpha(solid) == 255
    checked = 0
    for frame in range(body_clip(data, contact, 'Attack1').frames):
        body = actor_draw_commands(data,BodySample(contact.actor_uuid,'Attack1',frame,contact.facing),
                                  contact,layers,media,camera)
        draw_frame(screen,state,catalog,cache,camera,0,show_grid=False,show_debug=False,
                   mouse_position=None)
        baseline = pygame.surfarray.array3d(screen)
        draw_frame(screen,state,catalog,cache,camera,0,show_grid=False,show_debug=False,
                   mouse_position=None,extra_commands=body)
        pixels = pygame.surfarray.array3d(screen)
        body_alpha = pygame.Surface(screen.get_size(),pygame.SRCALPHA)
        for row in body:
            body_alpha.blit(row.surface,row.destination)
        overlap = opaque & (pygame.surfarray.array_alpha(body_alpha)>0)
        checked += int(np.count_nonzero(overlap))
        changed = overlap & np.any(pixels != baseline, axis=2)
        if np.any(changed):
            location = tuple(np.argwhere(changed)[0])
            roles = []
            for row in body:
                local = (location[0]-row.destination[0],location[1]-row.destination[1])
                if row.surface.get_rect().collidepoint(local) and row.surface.get_at(local).a:
                    roles.append(row.role)
            pytest.fail(f'frame={frame}, pixel={location}, leaking roles={roles}, changed={np.count_nonzero(changed)}')
    assert checked > 0


@pytest.mark.parametrize('quadrant', range(4))
def test_registered_window_hides_transparent_face_margins_but_keeps_aperture(raster, quadrant):
    state, _ = _saved(window_history().views['attacker'])
    screen, _, _, _, _ = raster
    camera = Camera(quadrant=quadrant, zoom=1, viewport=screen.get_size()).with_focus((5.5,4))
    art = load_environment_art()
    wall = next(obj for obj in state.objects.values() if obj.item.item_id.endswith('fantasy_g8.wall'))
    prop = art.props[wall.item.item_id]
    pose = camera_pose('east',quadrant)
    command = environment_command(prop.intact['default'],0,identity=wall.item.item_uuid,
        position=(5,4),elevation=0,pose=pose,boundary_pose=pose,camera=camera,multiplier=(1,1,1))
    opening = environment_aperture_image(wall.item.item_id,pose,camera)
    assert opening is not None
    boundary = BoundarySprite((wall.placement,),command.surface,command.destination,command.key,
        actor_aperture=opening,actor_occludes=prop.occludes_actor_face)
    body = pygame.Surface(screen.get_size(),pygame.SRCALPHA)
    body.fill('red')
    position = (5.2,4) if quadrant in (0,1) else (5.8,4)
    actor = DrawCommand(painter_key(position,elevation_steps=0,quadrant=quadrant,
        role='actor',identity='behind-window'),body,(0,0),0,(),role='actor')
    clipped, = clip_actor_boundaries([actor],[boundary],camera)
    painted = pygame.Surface(screen.get_size(),pygame.SRCALPHA)
    painted.blit(command.surface,command.destination)
    aperture = pygame.Surface(screen.get_size(),pygame.SRCALPHA)
    aperture.blit(opening,command.destination)
    exterior_hidden = ((pygame.surfarray.array_alpha(clipped.surface)==0)
                       & (pygame.surfarray.array_alpha(painted)==0))
    assert np.count_nonzero(exterior_hidden) > 0
    through_opening = pygame.surfarray.array_alpha(aperture)>0
    assert np.count_nonzero(through_opening) > 0
    assert np.all(pygame.surfarray.array_alpha(clipped.surface)[through_opening] == 255)
    assert art.props['environment.wall.fantasy_g1'].occludes_actor_face


def test_window_review_receives_matching_walls_on_both_sides(raster):
    state, _ = _saved(window_history().views['attacker'])
    siblings = [obj for obj in state.objects.values()
                if obj.item.item_id == 'environment.wall.fantasy_g1']
    assert {obj.placement.position for obj in siblings} == {(5, 3), (5, 5)}
    assert all(obj.placement.boundary_direction is CardinalDirection.EAST for obj in siblings)
    art = load_environment_art()
    bank = art.props['environment.wall.fantasy_g1'].intact['default']
    assert set(bank.frames_by_pose) == {'e', 's', 'w', 'n'}


@pytest.mark.parametrize('quadrant', range(4))
def test_matching_solid_wall_also_clips_actor_overhang(raster, quadrant):
    state, _ = _saved(window_history().views['attacker'])
    screen, catalog, cache, _, _ = raster
    camera = Camera(quadrant=quadrant,zoom=1,viewport=screen.get_size()).with_focus((5.5,5))
    behind = (5.4,5) if quadrant in (0,1) else (5.6,5)
    image = pygame.Surface(screen.get_size(),pygame.SRCALPHA)
    image.fill('red')
    body = DrawCommand(painter_key(behind,elevation_steps=0,quadrant=quadrant,
        role='actor',identity='overhang'),image,(0,0),0,(),role='actor')
    draw_frame(screen,state,catalog,cache,camera,0,show_grid=False,show_debug=False,mouse_position=None)
    baseline = screen.copy()
    draw_frame(screen,state,catalog,cache,camera,0,show_grid=False,show_debug=False,
               mouse_position=None,extra_commands=(body,))
    # This is below the wall art, where ordinary sprite alpha sorting cannot
    # stop a behind-wall attack pose from poking onto the foreground ground.
    point = tuple(round(v) for v in project_screen((5.5,5),camera,elevation_steps=-.15))
    assert screen.get_at(point) == baseline.get_at(point)


def test_each_authored_crossing_passes_the_visible_opening_in_all_views(raster):
    data = raster[3]
    profile = data.movement_context.connectorProfiles['window']
    assert profile.passageBodyHeightPx is not None
    factor = TILE_WIDTH / data.rig.TILE_W
    actor = ActorContact('crossing', (0,0), 'E', 1)
    for item_id, prop in load_environment_art().props.items():
        if prop.passage_point is None:
            continue
        normal, tangent, height = prop.passage_point
        lift = height * HEIGHT_STEP_PIXELS / factor - profile.passageBodyHeightPx
        leg = MotionLeg((0,0),(1,0),0,0,0,1000,arc_height_px=lift,
                        path_bend=(normal-.5,tangent))
        reverse = replace(leg,start=(1,0),end=(0,0))
        for t in (0, 250, 500, 750, 1000):
            forward = motion_leg_contact(actor,leg,data,t)
            backward = motion_leg_contact(actor,reverse,data,1000-t)
            assert forward.grid == pytest.approx(backward.grid)
            assert forward.body_lift_px == pytest.approx(backward.body_lift_px)
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant,zoom=1,viewport=(600,450)).with_focus((0,0))
            pose = camera_pose('east',quadrant)
            opening = environment_aperture_image(item_id,pose,camera)
            assert opening is not None
            command = environment_command(prop.intact['default'],0,identity=uuid4(),
                position=(0,0),elevation=0,pose=pose,boundary_pose=pose,camera=camera,multiplier=(1,1,1))
            visible = 0
            for t in range(0,1001,5):
                contact = motion_leg_contact(actor,leg,data,t)
                center_height = body_elevation_steps(contact,data) + profile.passageBodyHeightPx*factor/HEIGHT_STEP_PIXELS
                sx,sy = project_screen(contact.grid,camera,elevation_steps=center_height)
                pixel = (round(sx-command.destination[0]),round(sy-command.destination[1]))
                if opening.get_rect().collidepoint(pixel) and opening.get_at(pixel).a:
                    visible += 1
            # Deep stone reveals expose different intervals in opposing views.
            assert visible > 2, (item_id, quadrant)


def test_received_passage_rotation_height_and_reverse(raster):
    state, _ = _saved(window_history().views['attacker'])
    wall = next(obj for obj in state.objects.values() if obj.item.item_id.endswith('fantasy_g8.wall'))
    point = load_environment_art().props[wall.item.item_id].passage_point
    assert point is not None
    normal,tangent,height = point
    wall = replace(wall,placement=wall.placement.model_copy(update={
        'boundary_direction':CardinalDirection.NORTH,'base_height_steps':2,'top_height_steps':4}))
    state = replace(state,objects={wall.item.item_uuid:wall})
    expected = (5-tangent,4+normal,2+height)
    assert passage_point(state,(5,4),(5,5)) == pytest.approx(expected)
    assert passage_point(state,(5,5),(5,4)) == pytest.approx(expected)
    assert passage_point(state,(5,4),(6,4)) is None


def test_every_window_has_four_registered_views_and_preserved_authored_clock(raster):
    art = load_environment_art()
    canvases = {}
    for code in ('a4','a5','c4','d16','d7','f16','f7','g7','g8','g9'):
        for part in ('wall', 'insert') if code != 'g7' else ('wall',):
            entry = art.props[f'environment.window.fantasy_{code}.{part}']
            assert set(entry.selection_masks_by_pose) == {'e','s','w','n'}
            bank = entry.destructions['default']
            count = 37 if code == 'g9' and part == 'insert' else 61
            assert bank.frame_count == count
            assert bank.frame_times_ms == pytest.approx(tuple(value*1000/24 for value in range(count)))
            assert bank.frame_times_ms[bank.state_change_frame] == pytest.approx(1000*10/24)
            assert sample_environment_frame(bank, 400) == 9
            assert sample_environment_frame(bank, 417) == 10
            for regions in bank.frames_by_pose.values():
                for region in regions:
                    if region.path not in canvases:
                        canvases[region.path] = pygame.image.load(region.path).get_rect()
                    assert canvases[region.path].contains(pygame.Rect(region.rect))


@pytest.mark.parametrize('code', ('a4','a5','c4','d16','d7','f16','f7','g8','g9'))
def test_broken_insert_leaves_no_standing_wall_after_parent_collapse(raster, code):
    # Native insert break -> crossing -> parent break. The retained insert rubble
    # must not contain the standing wall from the artist's combined preview.
    state, roots = _saved(window_history(family=f'environment.window.fantasy_{code}').views['attacker'])
    wall, = (obj for obj in state.objects.values() if obj.item.item_id.endswith(f'fantasy_{code}.wall'))
    insert, = (obj for obj in state.objects.values() if obj.item.item_id.endswith(f'fantasy_{code}.insert'))
    for root in roots:
        state = reduce_lineage(state, root)
    assert state.objects[wall.item.item_uuid].item.integrity is ItemIntegrity.DESTROYED
    assert state.objects[insert.item.item_uuid].item.integrity is ItemIntegrity.DESTROYED
    without_insert = replace(state, objects={identity: obj for identity, obj in state.objects.items()
                                            if identity != insert.item.item_uuid})
    screen, catalog, cache, _, _ = raster
    bank = load_environment_art().props[wall.item.item_id].intact['default']
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((5,4))
        pose = camera_pose('east', quadrant)
        standing = environment_command(bank, 0, identity=wall.item.item_uuid, position=(5,4),
            elevation=0, pose=pose, boundary_pose=pose, camera=camera, multiplier=(1,1,1))
        silhouette = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        silhouette.blit(standing.surface, standing.destination)
        bounds = silhouette.get_bounding_rect()
        upper_wall = ((pygame.surfarray.array_alpha(silhouette) > 0)
                      & (np.arange(screen.height)[None, :] < bounds.centery))
        assert np.count_nonzero(upper_wall) > 0
        draw_frame(screen, without_insert, catalog, cache, camera, 0, show_grid=False,
                   show_debug=False, mouse_position=None, extra_commands=())
        cleared = pygame.surfarray.array3d(screen)
        evidence = draw_frame(screen, state, catalog, cache, camera, 0, show_grid=False,
            show_debug=False, mouse_position=None, extra_commands=(), collect_evidence=True).evidence
        assert evidence is not None
        assert any(row[0] == insert.item.item_uuid for row in evidence.actual_draws)
        pixels = pygame.surfarray.array3d(screen)
        np.testing.assert_array_equal(pixels[upper_wall], cleared[upper_wall],
            err_msg=f'{code}, camera {quadrant}: destroyed insert retains standing parent pixels')


@pytest.mark.parametrize('program', ('insert-cross-wall', 'parent'))
def test_break_and_cross_replay_uses_recorded_attachment_state(raster, program):
    native = window_history(program=program)
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0
    state, roots = _saved(native.views['attacker'])
    art = load_environment_art()
    wall, = (obj for obj in state.objects.values() if obj.item.item_id.endswith('fantasy_g8.wall'))
    insert, = (obj for obj in state.objects.values() if obj.item.item_id.endswith('fantasy_g8.insert'))
    broken = crossed = False
    for root in roots:
        after, group, render = _render_head(raster, state, root)
        for change in group.world_transitions:
            if change.destruction is None or change.identity != wall.item.item_uuid:
                continue
            broken = True
            retained = after.objects[wall.item.item_uuid].item.remnant_state
            assert retained is not None
            assert (insert.item.item_uuid in retained.intact_supported_items) is (program == 'parent')
            bank = remnant_bank(art, wall.item.item_id, retained)
            assert bank is not None
            expected = (art.props[wall.item.item_id].destructions_without_attachments
                        if program == 'insert-cross-wall' else art.props[wall.item.item_id].destructions)
            assert bank is expected['default']
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, viewport=raster[0].get_size()).with_focus((5,4))
                for elapsed in (0, 400, 800, 2600):
                    _, draws, _ = render(camera, change.start_ms + elapsed)
                    assert any(row[0] == wall.item.item_uuid for row in draws)
                    if program == 'parent':
                        assert not any(row[0] == insert.item.item_uuid for row in draws)
        if isinstance(root.root.fact, MovementFact) and root.root.fact.connector_presentation_key == 'window':
            crossed = True
            assert len(group.movements) == 1
            timeline = group.movements[0].timeline
            assert timeline.clip == 'Rolling'
            assert timeline.animation_id == 'CrawlThroughWindow'
            middle = sample_motion(timeline, raster[3], timeline.complete_ms / 2)
            assert middle.contact is not None
            assert middle.body is not None
            assert 0 < middle.body.scale[0] < 1 and 0 < middle.body.scale[1] < 1
            # Crawl holds its tucked posture at sill height, rather than
            # playing the inverted half of the source rolling animation.
            hold = raster[3].movement_context.connectorProfiles['window'].passageHoldFraction
            for fraction in (.5-hold/4,.5+hold/4):
                passing = sample_motion(timeline,raster[3],timeline.complete_ms*fraction)
                assert passing.contact is not None and passing.body is not None
                assert passing.body.frame == middle.body.frame
                assert passing.contact.body_lift_px == pytest.approx(middle.contact.body_lift_px)
            for elapsed in (0, timeline.complete_ms):
                endpoint = sample_motion(timeline, raster[3], elapsed)
                assert endpoint.body is not None and endpoint.body.scale == (1, 1)
            opening = passage_point(timeline.before, (5,4), (6,4))
            assert opening is not None
            assert middle.contact.grid == pytest.approx(opening[:2])
            body_height = raster[3].movement_context.connectorProfiles['window'].passageBodyHeightPx
            assert body_height is not None
            center_height = (body_elevation_steps(middle.contact, raster[3])
                             + body_height * middle.contact.visual_scale * 2 / 64)
            assert center_height == pytest.approx(opening[2])
            # Align the actual sampled body, including its baked rolling
            # displacement, rather than just checking the trajectory's pivot.
            data = raster[3]
            mover = timeline.actor_state
            layers = tuple(layer for layer in resolve_player_layers(data,mover,rig_id=middle.contact.rig_id)
                           if layer.slot == 'body')
            rows = load_actor_media(data,((middle.contact,layers,('Rolling',)),),all_facings=True)
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant,zoom=1,viewport=raster[0].get_size()).with_focus((5.5,4))
                command, = actor_draw_commands(data,middle.body,middle.contact,layers,rows,camera)
                bounds = command.surface.get_bounding_rect(min_alpha=128)
                actual = (command.destination[0]+bounds.centerx,command.destination[1]+bounds.centery)
                expected = project_screen(opening[:2],camera,elevation_steps=opening[2])
                assert actual == pytest.approx(expected,abs=2), (quadrant,actual,expected)
        state = after
    assert broken and crossed is (program == 'insert-cross-wall')
    assert state.objects[wall.item.item_uuid].item.integrity is ItemIntegrity.DESTROYED
    assert EventQueue.event_cursor() == 0


@pytest.mark.parametrize('quadrant', range(4))
def test_passage_squeeze_changes_body_but_preserves_ground_shadow(raster, quadrant):
    state, _ = _saved(window_history().views['attacker'])
    _, _, _, data, _ = raster
    actor = state.actors[state.observer_uuid]
    contact = replace(actor_contact(state, actor, data), grid=(5.5,4), body_lift_px=25)
    layers = resolve_player_layers(data, actor, rig_id=contact.rig_id)
    media = load_actor_media(data, ((contact,layers,('Rolling',)),), all_facings=True)
    camera = Camera(quadrant=quadrant,zoom=1,viewport=(600,450)).with_focus((5.5,4))
    body = BodySample(contact.actor_uuid,'Rolling',3,'E')
    plain = actor_draw_commands(data,body,contact,layers,media,camera)
    profile = data.movement_context.connectorProfiles['window']
    tucked = actor_draw_commands(data,replace(body,scale=profile.passageScale,
        scale_anchor_height_px=profile.passageBodyHeightPx or 0,
        registration_socket=profile.passageSocket,registration_weight=1),contact,layers,media,camera)
    normal_body, = (draw for draw in plain if draw.role == 'actor')
    squeezed_body, = (draw for draw in tucked if draw.role == 'actor')
    assert squeezed_body.surface.width < normal_body.surface.width
    assert squeezed_body.surface.height < normal_body.surface.height
    shadow, = (draw for draw in plain if draw.role == 'actor_shadow')
    squeezed_shadow, = (draw for draw in tucked if draw.role == 'actor_shadow')
    assert squeezed_shadow.destination == shadow.destination
    np.testing.assert_array_equal(pygame.surfarray.array_alpha(squeezed_shadow.surface),
                                  pygame.surfarray.array_alpha(shadow.surface))


def test_window_components_are_picked_by_their_separate_masks_in_all_views(raster):
    state, _ = _saved(window_history().views['attacker'])
    objects = {identity:obj for identity,obj in state.objects.items()
               if obj.item.item_id.startswith('environment.window.fantasy_g8.')}
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=raster[0].get_size()).with_focus((5,4))
        for identity,obj in objects.items():
            command = environment_selection_command(obj, camera)
            assert command is not None
            found = False
            for x in range(0, command.surface.get_width(), 3):
                for y in range(0, command.surface.get_height(), 3):
                    point = (x+command.destination[0], y+command.destination[1])
                    if pick_environment_target(point, objects, camera) == identity:
                        found = True
                        break
                if found:
                    break
            assert found, (quadrant, obj.item.item_id)


def test_disallowed_window_mask_does_not_select_unmasked_target_behind_it(raster):
    state, _ = _saved(window_history().views['attacker'])
    objects = {identity:obj for identity,obj in state.objects.items()
               if obj.item.item_id.startswith('environment.window.fantasy_g8.')}
    camera = Camera(viewport=raster[0].get_size()).with_focus((5,4))
    row = AvailableActionInfo(template_name="Attack_melee_main", behavior_id="action.attack",
        provided_by_id="action.attack", display_name="Attack", target_type=TargetType.CREATURE_OR_OBJECT,
        availability_status=ActionAvailabilityStatus.AVAILABLE, can_afford=True, cost_type="actions",
        valid_targets=[AvailableTarget(index=0, target_uuid=uuid4(), position=(5,4))])
    actions = AvailableActionsResult(entity_uuid=state.observer_uuid, object_actions=[row])
    frame = draw_frame(raster[0],state,raster[1],SurfaceCache(raster[1]),camera,0,
                       collect_interaction=True,show_debug=False,show_grid=False,mouse_position=None).interaction
    assert frame is not None
    checked = 0
    for obj in objects.values():
        command = environment_selection_command(obj, camera)
        assert command is not None
        point = next(((x+command.destination[0],y+command.destination[1])
                     for x in range(command.surface.get_width()) for y in range(command.surface.get_height())
                     if command.surface.get_at((x,y)).a
                     and (support := pick_support((x+command.destination[0], y+command.destination[1]),
                            camera, state.tiles.values())[0]) is not None
                     and support.position == (5,4)), None)
        if point is None:
            continue
        hit = pick_world(frame,point)
        if hit is None or hit.kind != 'object':
            continue
        assert target_at(tuple(row.valid_targets),hit) is None
        checked += 1
    assert checked > 0


def test_parent_break_never_reveals_an_unobserved_insert(raster):
    state, roots = _saved(window_history(program='parent', hidden_insert=True).views['attacker'])
    assert not any(obj.item.item_id.endswith('fantasy_g8.insert') for obj in state.objects.values())
    found = False
    for root in roots:
        after, group, _ = _render_head(raster, state, root)
        for transition in group.world_transitions:
            if transition.destruction is not None:
                found = True
                bank_id = transition.destruction.bank_id
                assert bank_id == load_environment_art().props['environment.window.fantasy_g8.wall'].destructions_without_attachments['default'].identity
                assert not transition.destruction.incorporated_items
        state = after
    assert found
