"""Operation-local descriptor admission preserves transient grants and publication."""

from copy import deepcopy
from dataclasses import replace
import random

import pytest

from dnd.core.content.descriptors import ContentDescriptor, ContentVisibility
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.events import EventPhase, EventQueue
from dnd.player.application import capture_application_operation, initialize_audiences, seat_content
from dnd.player.content_composition import admitted_content, ui_content_manifest
from dnd.player.facts import PlayerUpdate
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.session import Operation, close_session, create_session
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.conjuration import build_guardian_of_faith_object


@pytest.fixture
def session():
    state = random.getstate()
    random.seed(0)
    value = create_session()
    try:
        yield value
    finally:
        close_session(value)
        reset_engine_runtime()
        random.setstate(state)


def descriptor(identity, visibility, related=()):
    return ContentDescriptor(ref=ContentRef(pack_id='content.local',
        definition_kind=ContentDefinitionKind.ENVIRONMENT_OBJECT, content_id=identity,
        content_version=1, definition_contract_hash='a'*64), display_name=identity,
        visibility=visibility, related_content_refs=related)


def catalog_with(*values):
    catalog = ui_content_manifest()
    return catalog.model_copy(update={'content': (*catalog.content, *((row.ref, row) for row in values))})


def operation_since(session, start):
    return Operation(start_cursor=start, end_cursor=EventQueue.event_cursor(),
        roots=tuple(event for _, event in EventQueue.iter_events_since(start)
            if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)))


def transient_guardian(session):
    start = EventQueue.event_cursor()
    guardian = build_guardian_of_faith_object(session.player_uuids[0])
    guardian.place_on_grid((12, 12))
    assert guardian.retire()
    return guardian, operation_since(session, start)


def test_transient_world_content_matches_reference_and_cold_replay(session):
    private = descriptor('environment.spell_object.guardian_of_faith', ContentVisibility.OBSERVED)
    catalog = catalog_with(private)
    runtimes, initializations = initialize_audiences(session, catalog)
    runtime = runtimes['party']
    before = reduce_initialization(initializations['party'], content_additions=seat_content(runtime))
    frozen = deepcopy(before)
    assert private.ref not in {row.ref for row in before.content}
    guardian, operation = transient_guardian(session)
    update = capture_application_operation(runtimes, operation, catalog)['party']
    assert any(look.item_id == private.ref.content_id for lineage in update.lineages
        for world in lineage.world_updates for look in world.object_looks)
    assert private.ref in {row.ref for row in update.content_additions}
    assert seat_content(runtime) == admitted_content(catalog,
        replace(runtime.projection.remembered, content=before.content), update.lineages)
    detached = PlayerUpdate.model_validate_json(update.model_dump_json())
    close_session(session)
    reset_engine_runtime()
    replayed = reduce_operation(before, detached)
    assert guardian.uuid not in replayed.objects
    assert replayed.content == seat_content(runtime)
    assert before == frozen


def test_catalog_replacement_admits_public_values_and_keeps_private_links_hidden(session):
    private = descriptor('review.hidden', ContentVisibility.OBSERVED)
    public = descriptor('review.public', ContentVisibility.PUBLIC, (private.ref,))
    catalog = catalog_with(private, public)
    runtimes, _ = initialize_audiences(session, catalog)
    before = seat_content(runtimes['party'])
    later = descriptor('review.later', ContentVisibility.PUBLIC, (public.ref, private.ref))
    replacement = catalog.model_copy(update={'content': (*catalog.content, (later.ref, later))})
    update = capture_application_operation(runtimes,
        operation_since(session, EventQueue.event_cursor()), replacement)['party']
    assert tuple(row.ref for row in update.content_additions) == (later.ref,)
    assert update.content_additions[0].related_content_refs == (public.ref,)
    assert later.ref not in {row.ref for row in before}
    assert private.ref not in {row.ref for row in seat_content(runtimes['party'])}
    assert later.related_content_refs == (public.ref, private.ref)
    again = capture_application_operation(runtimes,
        operation_since(session, EventQueue.event_cursor()), replacement)['party']
    assert again.content_additions == ()
