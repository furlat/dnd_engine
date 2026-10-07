"""Saved breach stages wait for the actual door's authored clearance."""
from dnd.actions import SpellEvent
import pygame
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell
from dnd.content.items.environment_item_builders import build_authored_door
from dnd.content.items.world_prop_builders import build_world_prop
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.items.environment import DirectionalWall
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.entity import Entity
from dnd.encounter import Encounter
from dnd.controller import HumanController
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.evocation import Fireball
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from game.animation_data import load_animation_data
from game.animation import ActorContact
from game.presentation_timing import presentation_dependencies
from game.timing_evidence import validate_timing_evidence
from game.choreography import bind_choreography, sample_choreography
from game.choreography_draw import choreography_draw_commands, load_choreography_media
from game.combat import BoundCast
from game.environment_animation import remnant_bank
from game.environment_art import load_environment_art
from dnd.player.facts import AreaReachFact, ObjectDestroyedFact, SpellFact
from dnd.player.recorded import project_sequence
from dnd.player.reduction import reduce_initialization
from dnd.player.capture import capture_interval, capture_lineage
from dnd.player.recorded import RecordedSequence
from game.projection import Camera
from tests.manual.spell_regression_support import create_spell_regression_actor


def breach_record(*, slow_barriers=False):
    reset_engine_runtime()
    build_battlefield("battlefield.open_floor_bright")
    try:
        caster = create_spell_regression_actor('Caster', (0, 4), 'heroes', spell_slots={3: 1})
        register_spell(caster, Fireball, caster_level=5)
        create_spell_regression_actor('Beyond obstruction', (5 if slow_barriers else 4, 4), 'enemies')
        if slow_barriers:
            for x in (2, 3, 4):
                build_world_prop('environment.furniture.bookshelf', hit_points=4).place_on_grid((x, 4))
            for x in range(10):
                for side in (CardinalDirection.NORTH, CardinalDirection.SOUTH):
                    DirectionalWall(source_entity_uuid=caster.uuid, item_id="test.wall").place_on_grid((x, 4), boundary_direction=side)
        else:
            door = build_authored_door('environment.door.desert_c7', hit_points=4)
            door.place_on_grid((3, 4), boundary_direction=CardinalDirection.WEST)
            for x, y in get_map().get_all_tiles():
                if x == 3 and y != 4:
                    DirectionalWall(source_entity_uuid=caster.uuid, item_id="test.wall").place_on_grid((x, y), boundary_direction=CardinalDirection.WEST)
        encounter = Encounter(name="Breach replay", source_entity_uuid=caster.uuid)
        encounter.add_combatant(caster, HumanController(source_entity_uuid=caster.uuid))
        with fixed_dice_faces(15):
            encounter.start_encounter()
        encounter.start_turn()
        Entity.update_all_entities_senses(max_distance=120)
        initial = capture_interval(name='Closed door', start_cursor=0, end_cursor=EventQueue.event_cursor(), observer_uuid=caster.uuid, battlefield_id="battlefield.open_floor_bright")
        actions = get_available_actions(caster)
        row, target = next((row, target) for row in actions.position_actions
            if row.behavior_id == 'spell.fireball' for target in row.valid_targets
            if target.position == (1, 4))
        with fixed_dice_faces(*([1] * 200)):
            result = execute_available_action(caster, row, target)
        assert isinstance(result, SpellEvent) and not result.canceled
        return RecordedSequence(initialization=initial, lineages=(capture_lineage(result, observer_uuid=caster.uuid),)).model_dump_json()
    finally:
        reset_engine_runtime()


def test_cold_breach_replay_waits_for_door_clearance_and_keeps_one_cast():
    payload = breach_record()
    assert not Entity.get_all_entities()
    native = RecordedSequence.model_validate_json(payload, context=PASSIVE_EVENT_REPLAY)
    sequence = project_sequence(native)
    before, lineage = reduce_initialization(sequence.initialization), sequence.lineages[0]
    data = load_animation_data()
    bound = bind_choreography(before, lineage, data)
    assert not bound.gaps, bound.gaps
    assert len(bound.nodes) == 1
    assert isinstance(bound.nodes[0].bound, BoundCast)
    assert bound.nodes[0].bound.staged_area
    stages = [node for node in lineage.events if isinstance(node.fact, AreaReachFact)]
    assert len(stages) == 2
    destroyed, = [node.fact for node in lineage.events if isinstance(node.fact, ObjectDestroyedFact)]
    transition, = [row for row in bound.world_transitions if row.field == 'destruction']
    bank = remnant_bank(load_environment_art(), destroyed.item_id, destroyed.remnant_state, outcome=destroyed.destruction_outcome)
    assert bank is not None and bank.state_change_frame
    clear = transition.start_ms + bank.frame_times_ms[bank.state_change_frame]
    blocked = sample_choreography(bound, clear - 1).displayed.objects[destroyed.object_uuid]
    opened = sample_choreography(bound, clear + 1).displayed.objects[destroyed.object_uuid]
    assert blocked.item.boundary_structure is not None
    assert WorldEdgeChannel.PROPAGATION in blocked.item.boundary_structure.blocked_channels
    assert opened.item.boundary_structure is None or not opened.item.boundary_structure.blocked_channels
    later = {row.fact.application_id for row in lineage.events if isinstance(row.fact, SpellFact)
             and row.parent_lineage == stages[1].lineage_uuid}
    assert later
    later_applications = [application for application in bound.nodes[0].bound.timeline.applications
        if application.source.application_id in {str(identity) for identity in later}]
    assert later_applications
    assert any(isinstance(row.source.target, ActorContact) and row.source.target.grid == (4, 4)
        and row.source.damage_applied for row in later_applications)
    dependencies = presentation_dependencies(bound)
    assert dependencies
    assert all(not validate_timing_evidence(owner.evidence) for owner in dependencies)
    reach_evidence = [row for row in bound.timing_evidence if row.reason == 'area_reach']
    assert any(any(source.reference.anchor == 'clearance' for source in row.inputs) for row in reach_evidence)
    cast_evidence = bound.nodes[0].bound.timeline.timing_evidence
    final_anchors = {(row.target.application_id, row.target.anchor): row for row in cast_evidence}
    for application in later_applications:
        assert bound.nodes[0].start_ms + application.travel_end_ms >= clear
        identity = application.source.application_id
        assert final_anchors[identity, 'contact'].at_ms == application.travel_end_ms
        if application.hp_ms is not None:
            assert final_anchors[identity, 'hp'].at_ms == application.hp_ms
            assert final_anchors[identity, 'hp'].reason == 'staged_area_shift'
            assert final_anchors[identity, 'hp'].inputs[0].offset_producers is not None

    pygame.init()
    pygame.display.set_mode((8, 8))
    try:
        media = load_choreography_media(bound)
        font = pygame.font.Font(None, 16)
        # The same continuous explosion uses the retained physical barrier in
        # every camera, never the disclosed damage cells as an image stencil.
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant).with_focus((3, 4))
            columns = []
            for at, reached in ((clear - 1, False), (clear + 40, True), (clear - 1, False)):
                sample = sample_choreography(bound, at)
                commands = choreography_draw_commands(bound, sample, media, font, font, camera)
                volumes = [command.volume for command in commands if command.volume is not None]
                assert volumes
                assert all(volume.admitted is None for volume in volumes)
                assert all(any(wall.object_uuid == destroyed.object_uuid for wall in volume.boundaries)
                           is not reached for volume in volumes)
                impact, = [p for p in sample.clips[0].sample.projectiles if p.phase == 'impact']
                columns.append(impact.column)
            assert columns[0] < columns[1] and columns[0] == columns[2]
    finally:
        pygame.quit()


def test_slow_serial_breaches_keep_one_continuous_explosion_until_last_reach():
    native = RecordedSequence.model_validate_json(breach_record(slow_barriers=True), context=PASSIVE_EVENT_REPLAY)
    sequence = project_sequence(native)
    bound = bind_choreography(reduce_initialization(sequence.initialization), sequence.lineages[0], load_animation_data())
    assert not bound.gaps, bound.gaps
    assert len(bound.nodes) == 1
    cast = bound.nodes[0].bound
    assert isinstance(cast, BoundCast)
    assert len(cast.area_reach) == 4
    assert cast.timeline.ground_delivery is not None
    impact, = [row for row in cast.timeline.ground_delivery.projectile_intervals if row.name == 'impact']
    assert cast.area_reach[0][0] == cast.timeline.release_ms < impact.start_ms
    assert all(at >= impact.start_ms for at, _ in cast.area_reach[1:])
    last_reach = cast.area_reach[-1][0]
    assert last_reach - impact.start_ms > 2000
    assert impact.end_ms > last_reach
    columns = []
    for at, _ in cast.area_reach:
        # Initial geometry is available for formation at release; explosion
        # samples still start at contact. Later reaches wait for real breaches.
        frame = sample_choreography(bound, max(at, impact.start_ms) + 1).clips[0].sample
        projectile, = [p for p in frame.projectiles if p.phase == 'impact']
        columns.append(projectile.column)
    assert columns == sorted(set(columns))
    last = sample_choreography(bound, impact.end_ms - 1).clips[0].sample
    projectile, = [p for p in last.projectiles if p.phase == 'impact']
    assert projectile.column == impact.phase.start + impact.phase.frames - 1
