"""Recorded local changes reach the client by the world wire's rules (player schema 16).

Leaving perception sends nothing, so the client keeps what it last saw; cells entering view are authoritative,
so an object moved away while unseen is dropped when its old support is seen again; a composite names an
attachment once the seat was sent its look; the client keeps a wall's faces not seen now.
"""

from uuid import uuid4

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from tests.sensory_cells import packed_cells
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.effect_types import ObservedChangeRef
from dnd.core.traversal_connectors import ConnectorProvocationPolicy, TraversalConnectorKind
from dnd.core.events import (
    EventPhase, SensoryUpdateEvent, SpatialChangeEvent, SpatialChangeType, WorldInitializedEvent, WorldModifiedEvent,
    WorldObjectState, WorldTileState,
)
from dnd.core.item_types import (
    EquippedVisualPolicy, ItemPresentationKind, ItemPresentationState, ItemRarity, ItemRemnantState,
)
from dnd.core.presentation_geometry import SpherePresentationGeometry
from dnd.core.world_edges import ElevationSurfaceKind
from dataclasses import replace
from dnd.core.events import WorldConnectorState
from dnd.player.capture import CompletedLineage, IntervalEnvelope, ObjectiveRow, WorldInterval
from dnd.player.projection import SessionProjection, begin_projection, project_lineage
from dnd.player.recorded import RecordedSequence, project_sequence
from dnd.player.reduction import reduce_initialization, reduce_lineage
from dnd.types.materials import Material, TileSurface
from dnd.types.residues import ObjectResidueState
from dnd.types.senses import PerceivedContact, PerceivedSpatialEffect
from dnd.types.spell_suppression import SpellSuppression
from dnd.types.world import CardinalDirection, LightLevel
from dnd.types.world_placement import (
    BoundaryStructure, BoundaryStructureKind, WorldObjectPlacement, WorldPlacementKind,
)


def item(name):
    return ItemPresentationState(item_uuid=uuid4(), item_id='test.projection.item', name=name,
        item_kind=ItemPresentationKind.ITEM, rarity=ItemRarity.COMMON, weight=1.0,
        visual_item_name='item', equipped_visual_policy=EquippedVisualPolicy.HIDDEN,
        stack_count=1, max_stack=1, is_consumable=False)


def placed(value, position, *, contents=None, direction=None):
    return WorldObjectState(item=value, contained_items=contents, placement=WorldObjectPlacement(
        object_uuid=value.item_uuid, tile_uuid=uuid4(), position=position,
        kind=WorldPlacementKind.CENTER if direction is None else WorldPlacementKind.BOUNDARY,
        occupies_bands=True, base_height_steps=0, top_height_steps=1, boundary_direction=direction))


def objective(index, event):
    return ObjectiveRow(source_index=index, event_uuid=event.uuid, lineage_uuid=event.lineage_uuid,
        parent_event=event.parent_event, parent_lineage=event.parent_lineage,
        event_type=event.event_type.value, event_class=type(event).__name__, phase=event.phase.value,
        source_uuid=event.source_entity_uuid, source_name=None, target_uuid=None, target_name=None,
        turn_execution_id=None, status=None, outcome=None, canceled=False, modified=False)


def sensory(observer, **changes):
    return SensoryUpdateEvent.model_validate(dict(source_entity_uuid=observer,
        observer_uuid=observer, use_register=False, phase=EventPhase.COMPLETION, **packed_cells(changes)),
        context=PASSIVE_EVENT_REPLAY)


def initial(objects, visible, contacts):
    observer, generation = uuid4(), uuid4()
    world = WorldInitializedEvent.model_validate(dict(source_entity_uuid=observer, use_register=False,
        phase=EventPhase.COMPLETION, battlefield_id='test.local_projection', battlefield_name='Local',
        bounds=(0, 0, 8, 0), width=9, height=1,
        tiles=tuple(WorldTileState(tile_uuid=uuid4(), position=(x, 0), surface=TileSurface(base_material=Material.STONE),
            name='Floor', blocks_optics=False, blocks_propagation=False, walking_cost=1, flying_cost=1,
            swimming_cost=0, burrowing_cost=0, elevation_steps=0, surface_kind=ElevationSurfaceKind.ORDINARY,
            default_light=LightLevel.BRIGHT_LIGHT, resolved_light=LightLevel.BRIGHT_LIGHT) for x in range(9)),
        objects=objects), context=PASSIVE_EVENT_REPLAY)
    sense = sensory(observer, initial=True, observer_position=(0, 0), observer_position_changed=True,
        visible_cells_added=list(visible), seen_cells_added=list(visible),
        sense_modes_changed=True, sense_modes=[], passive_perception_changed=True, passive_perception=10,
        visual_access_changed=True, visual_access=1, object_contacts_changed=contacts)
    events = (world, sense)
    return IntervalEnvelope(name='recorded local changes', generation=generation, start_cursor=0,
        end_cursor=2, observer_uuid=observer, battlefield_id=world.battlefield_id, door_uuid=None,
        standing_torch_uuid=None, objective_rows=tuple(objective(i, event) for i, event in enumerate(events)),
        admitted=tuple(enumerate(events)), dispositions=(), world_interval=WorldInterval(events=tuple(enumerate(events))))


def check(initialization, events):
    """Project serialized facts without live owners; return each retained public state."""
    lineages = tuple(CompletedLineage(generation=initialization.generation,
        observer_uuid=initialization.observer_uuid, root=event, events=(event,),
        objective_rows=(objective(index+2, event),), start_cursor=index+2, end_cursor=index+3)
        for index, event in enumerate(events))
    saved = RecordedSequence(initialization=initialization, lineages=lineages).model_dump_json()
    restored = RecordedSequence.model_validate_json(saved, context=PASSIVE_EVENT_REPLAY)
    session = SessionProjection()
    projection, public = begin_projection(session, restored.initialization)
    states = [reduce_initialization(public)]
    for lineage in restored.lineages:
        update = project_lineage(session, projection, lineage)
        states.append(states[-1] if update is None else reduce_lineage(states[-1], update))
    replay = project_sequence(restored)
    latest = reduce_initialization(replay.initialization)
    for lineage in replay.lineages:
        latest = reduce_lineage(latest, lineage)
    assert latest == states[-1]
    return states


def test_later_attachment_knowledge_refreshes_an_unchanged_remnant_and_preserves_removal_boundary():
    attachment = placed(item('Attachment'), (3, 0))
    identity = attachment.item.item_uuid
    remnant = placed(item('Remnant').model_copy(update={
        'remnant_state': ItemRemnantState(intact_supported_items=(identity,))}), (0, 0))
    root = remnant.item.item_uuid
    start = initial((remnant, attachment), ((0, 0),), {
        root: PerceivedContact(position=(0, 0), visual=True, special_senses=())})
    observer = start.observer_uuid
    events = (
        sensory(observer, object_contacts_changed={identity: PerceivedContact(
            position=(3, 0), visual=False, special_senses=())}),
        sensory(observer, object_contacts_removed={identity}, visible_cells_added=[(3, 0)]),
        sensory(observer, passive_perception_changed=True, passive_perception=11),
    )
    states = check(start, events)
    # The attachment's look was sent: the composite keeps naming it after the attachment is seen gone.
    assert [state.objects[root].item.remnant_state.intact_supported_items for state in states] == [
        (), (identity,), (identity,), (identity,)]
    assert identity not in states[0].objects and identity in states[1].objects
    assert identity not in states[2].objects


def test_hidden_move_keeps_old_placement_until_that_support_is_observed():
    child = item('Private contents')
    box = placed(item('Box').model_copy(update={'is_open': True}), (1, 0), contents=(child,))
    identity = box.item.item_uuid
    start = initial((box,), ((1, 0),), {
        identity: PerceivedContact(position=(1, 0), visual=True, special_senses=())})
    observer = start.observer_uuid
    moved = box.model_copy(update={'placement': box.placement.model_copy(update={
        'position': (7, 0), 'covered_supports': ()})})
    # Validate the new recorded placement so its support follows its new anchor.
    moved = WorldObjectState.model_validate(moved.model_dump())
    changed = WorldModifiedEvent.model_validate(dict(source_entity_uuid=observer, use_register=False,
        phase=EventPhase.COMPLETION, object_uuid=identity, before=box, after=moved), context=PASSIVE_EVENT_REPLAY)
    states = check(start, (
        sensory(observer, visible_cells_removed=[(1, 0)], object_contacts_removed={identity}),
        changed,
        sensory(observer, visible_cells_added=[(1, 0)]),
    ))
    assert states[0].objects[identity].contained_items[0].item_uuid == child.item_uuid
    # Leaving sight sends nothing: the client keeps the contents it last saw.
    kept = states[1].objects[identity].contained_items
    assert kept is not None and kept[0].item_uuid == child.item_uuid
    assert states[2].objects[identity].placement.position == (1, 0)
    assert identity not in states[3].objects


def test_recorded_light_changes_only_existing_map_cells_and_keeps_neighbors():
    start = initial((), ((1, 0), (2, 0)), {})
    light = SpatialChangeEvent.model_validate(dict(source_entity_uuid=start.observer_uuid,
        use_register=False, phase=EventPhase.COMPLETION,
        change_type=SpatialChangeType.LIGHT_CHANGED, position=(99, 0),
        light_level_map={"1,0": LightLevel.DIM_LIGHT.value, "99,0": LightLevel.BRIGHT_LIGHT.value}),
        context=PASSIVE_EVENT_REPLAY)
    before, after = check(start, (light,))
    assert after.tiles[(1, 0)].resolved_light is LightLevel.DIM_LIGHT
    assert after.tiles[(2, 0)] == before.tiles[(2, 0)]
    assert (99, 0) not in after.tiles


def test_boundary_face_updates_preserve_the_unobserved_faces_recorded_residue():
    old_residue = ObjectResidueState(condition_uuid=uuid4(), residue_id='test.ash', description='Ash',
        faces=(CardinalDirection.WEST, CardinalDirection.EAST))
    wall = placed(item('Wall').model_copy(update={
        'boundary_structure': BoundaryStructure(structure=BoundaryStructureKind.WALL,
            material=Material.STONE, blocked_channels=()), 'surface_residues': (old_residue,)}),
        (1, 0), direction=CardinalDirection.EAST)
    identity = wall.item.item_uuid
    start = initial((wall,), ((1, 0),), {})
    observer = start.observer_uuid
    cleaned = wall.model_copy(update={'item': wall.item.model_copy(update={'surface_residues': ()})})
    changed = WorldModifiedEvent.model_validate(dict(source_entity_uuid=observer, use_register=False,
        phase=EventPhase.COMPLETION, object_uuid=identity, before=wall, after=cleaned), context=PASSIVE_EVENT_REPLAY)
    states = check(start, (
        sensory(observer, visible_cells_removed=[(1, 0)]), changed,
        sensory(observer, visible_cells_added=[(2, 0)]),
        sensory(observer, visible_cells_added=[(1, 0)]),
    ))
    assert states[0].objects[identity].item.surface_residues[0].faces == (CardinalDirection.WEST,)
    assert states[3].objects[identity].item.surface_residues[0].faces == (CardinalDirection.WEST,)
    assert states[4].objects[identity].item.surface_residues == ()


def test_explicit_object_after_value_updates_a_known_object_with_no_surviving_bands():
    obj = placed(item('Spent construction'), (1, 0))
    obj = obj.model_copy(update={'placement': obj.placement.model_copy(update={'removed_bands': ((1, 0, 0),)})})
    identity = obj.item.item_uuid
    start = initial((obj,), ((0, 0),), {
        identity: PerceivedContact(position=(1, 0), visual=False, special_senses=())})
    after = obj.model_copy(update={'item': obj.item.model_copy(update={'name': 'Recorded inert construction'})})
    changed = WorldModifiedEvent.model_validate(dict(source_entity_uuid=start.observer_uuid, use_register=False,
        phase=EventPhase.COMPLETION, object_uuid=identity, before=obj, after=after), context=PASSIVE_EVENT_REPLAY)
    states = check(start, (changed,))
    assert states[0].objects[identity].item.name == 'Spent construction'
    assert states[1].objects[identity].item.name == 'Recorded inert construction'


def test_remote_section_visibility_and_provider_after_values_refresh_construction_suppression():
    provider = uuid4()
    section = placed(item('Stationary section').model_copy(update={'construction_suppressions': (
        SpellSuppression(provider_uuid=provider, positions=((4, 0),)),)}), (0, 0))
    identity = section.item.item_uuid
    start = initial((section,), ((0, 0),), {
        identity: PerceivedContact(position=(0, 0), visual=True, special_senses=())})
    observed = PerceivedSpatialEffect(content_ref=ContentRef(pack_id='test.projection',
        definition_kind=ContentDefinitionKind.CONDITION, content_id='condition.test.projection',
        content_version=1, definition_contract_hash='0'*64), name='Globe of Invulnerability', description='',
        positions=((4, 0),), owner_revision=1, area_geometry=SpherePresentationGeometry(center=(4, 0), radius_feet=5))
    changed = observed.model_copy(update={'area_geometry': SpherePresentationGeometry(center=(4, 0), radius_feet=10),
        'owner_revision': 2})
    observer = start.observer_uuid
    states = check(start, (
        sensory(observer, spatial_effects_changed={provider: observed}),
        sensory(observer, visible_cells_added=[(4, 0)]),
        sensory(observer, spatial_effects_changed={provider: changed}),
        sensory(observer, visible_cells_removed=[(4, 0)]),
    ))
    assert states[0].objects[identity].item.construction_suppressions == ()
    outcomes = [state.objects[identity].item.construction_suppressions[0] for state in states[1:]]
    # Leaving view sends nothing: the client keeps the suppressed cell it last saw.
    assert [row.positions for row in outcomes] == [(), ((4, 0),), ((4, 0),), ((4, 0),)]
    assert [row.area_geometry.radius_feet for row in outcomes] == [5, 5, 10, 10]


def seen_by(observer, source, index):
    """The observer's sensory child naming `source` as a change it saw happen (its parent, here)."""
    child = sensory(observer).model_copy(update={"observed_changes": (ObservedChangeRef(source_event_uuid=source.uuid,
        source_index=index, field="paths", owner_uuid=observer),), "parent_lineage": source.lineage_uuid,
        "parent_event": source.uuid})
    return source.model_copy(update={"children_lineages": [child.lineage_uuid]}), child


def project_with_child(start, source):
    """Project `source` and its observer's sensory child naming it, from `start`; the packet and the client."""
    session = SessionProjection()
    projection, public = begin_projection(session, start)
    source, child = seen_by(start.observer_uuid, source, 2)
    native = CompletedLineage(generation=start.generation, observer_uuid=start.observer_uuid, root=source,
        events=(source, child), objective_rows=(objective(2, source), objective(3, child)), start_cursor=2,
        end_cursor=4)
    packet = project_lineage(session, projection, native)
    assert packet is not None
    return packet, reduce_lineage(reduce_initialization(public), packet)


def test_a_change_its_observer_saw_happen_publishes_once():
    start = initial((), ((1, 0), (2, 0)), {})
    light = SpatialChangeEvent.model_validate(dict(source_entity_uuid=start.observer_uuid, use_register=False,
        phase=EventPhase.COMPLETION, change_type=SpatialChangeType.LIGHT_CHANGED, position=(1, 0),
        light_level_map={"1,0": LightLevel.DIM_LIGHT.value}), context=PASSIVE_EVENT_REPLAY)
    packet, client = project_with_child(start, light)
    assert len(packet.world_updates) == 1
    assert client.tiles[(1, 0)].resolved_light is LightLevel.DIM_LIGHT


def test_a_removed_connector_its_observer_saw_go_is_removed_once():
    start = initial((), ((1, 0), (2, 0)), {})
    world_event = start.admitted[0][1]
    tiles = {row.position: row for row in world_event.tiles}
    ladder = WorldConnectorState(connector_uuid=uuid4(), authored_id='ladder', kind=TraversalConnectorKind.LADDER,
        presentation_key='ladder', endpoints=((1, 0), (2, 0)),
        support_tile_uuids=(tiles[(1, 0)].tile_uuid, tiles[(2, 0)].tile_uuid), endpoint_elevations_feet=(0, 0),
        movement_cost_feet=5, bidirectional=True, enabled=True,
        provocation_policy=ConnectorProvocationPolicy.DOES_NOT_PROVOKE)
    events = (world_event.model_copy(update={"connectors": (ladder,)}), start.admitted[1][1])
    start = replace(start, admitted=tuple(enumerate(events)), world_interval=WorldInterval(
        events=tuple(enumerate(events))), objective_rows=tuple(objective(i, event) for i, event in enumerate(events)))
    gone = WorldModifiedEvent.model_validate(dict(source_entity_uuid=start.observer_uuid, use_register=False,
        phase=EventPhase.COMPLETION, connector_uuid=ladder.connector_uuid, before=ladder, after=None),
        context=PASSIVE_EVENT_REPLAY)
    packet, client = project_with_child(start, gone)
    assert [update.connectors_removed for update in packet.world_updates] == [(ladder.connector_uuid,)]
    assert ladder.connector_uuid not in client.connectors
