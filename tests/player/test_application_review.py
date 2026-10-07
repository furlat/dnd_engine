"""Published common application after-values reproduce the owner-side state."""

import random
from dataclasses import replace

import pytest

from dnd.core.content.descriptors import ContentDescriptor, ContentVisibility
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.events import EventPhase, EventQueue
from dnd.player.application import initialize_audiences, capture_application_operation
from dnd.player.audience import PlayerAudience
from dnd.player.content_composition import admitted_content, ui_content_manifest
from dnd.player.facts import PlayerUpdate
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.session import (
    Operation, advance_controller, close_session, create_session, discover_player_actions, end_player_turn,
    snapshot_player_hud,
)
from dnd.spells.conjuration import build_guardian_of_faith_object
from game.runtime_protocol import (
    AdvanceRequest, DiscoverRequest, HandlerRequest, OperationReply, REPLY_CODEC, StartRequest,
)
from game.runtime_worker import dispatch, start_runtime


@pytest.fixture
def started():
    random_state = random.getstate()
    runtime, reply = start_runtime(StartRequest(request_id=0, test_seed=0))
    try:
        yield runtime, REPLY_CODEC.validate_json(REPLY_CODEC.dump_json(reply))
    finally:
        close_session(runtime.session)
        random.setstate(random_state)


def client_initialization(reply):
    return reduce_initialization(reply.initialization,
        content_additions=tuple(descriptor for _, descriptor in reply.ui_content.content))


def client_operation(state, reply):
    detached = REPLY_CODEC.validate_json(REPLY_CODEC.dump_json(reply))
    assert isinstance(detached, OperationReply)
    return reduce_operation(state, PlayerUpdate(audience=state.viewing_audience,
        lineages=detached.lineages, hud=detached.hud,
        combat_log_appends=detached.combat_log_appends,
        content_additions=detached.content_additions))


def test_published_initialization_has_only_admitted_descriptors_and_replays_exactly(started):
    runtime, reply = started
    published = tuple(descriptor for _, descriptor in reply.ui_content.content)
    assert published == runtime.latest.content
    assert all(row.visibility in (ContentVisibility.PUBLIC, ContentVisibility.OBSERVED)
        for row in published)
    assert client_initialization(reply) == runtime.latest


def test_common_operation_replays_eventless_handler_after_values(started):
    runtime, reply = started
    state = client_initialization(reply)
    advanced = dispatch(runtime, AdvanceRequest(request_id=1, generation=state.generation))
    assert isinstance(advanced, OperationReply) and advanced.boundary_status == "waiting_for_human"
    state = client_operation(state, advanced)
    assert state == runtime.latest
    actor = state.current_actor_uuid
    assert actor is not None and state.hud_snapshot is not None
    sheet = next(row for row in state.hud_snapshot.sheets if row.actor_uuid == actor)
    handler = sheet.handler_details[0]
    discovery = dispatch(runtime, DiscoverRequest(request_id=2, generation=state.generation, actor_uuid=actor))
    changed = dispatch(runtime, HandlerRequest(request_id=3, generation=state.generation,
        discovery_generation=discovery.choices.discovery_generation,
        actor_uuid=actor, command={"handler_uuid": handler.uuid, "enabled": not handler.enabled}))
    state = client_operation(state, changed)
    assert state == runtime.latest
    updated = next(row for row in state.hud_snapshot.sheets if row.actor_uuid == actor)
    assert next(row for row in updated.handler_details if row.uuid == handler.uuid).enabled != handler.enabled


def test_discovery_generation_counts_only_its_seats_queries():
    random_state = random.getstate()
    random.seed(0)
    session = create_session()
    session = replace(session, seats={str(identity): PlayerAudience((identity,), (identity,))
        for identity in session.player_uuids})
    try:
        catalog = ui_content_manifest()
        audiences, _ = initialize_audiences(session, catalog)
        discovered = set()
        for _ in range(32):
            operation = advance_controller(session)
            capture_application_operation(audiences, operation, catalog)
            assert operation.boundary is not None and operation.boundary.status != "error"
            if operation.boundary.status != "waiting_for_human":
                continue
            actor = session.encounter.get_current_entity()
            assert actor is not None
            seat = str(actor.uuid)
            choices = discover_player_actions(session, actor.uuid, seat_id=seat)
            if seat not in discovered:
                assert choices.discovery_generation == 1
                discovered.add(seat)
            if len(discovered) == 2:
                return
            capture_application_operation(audiences, end_player_turn(session, actor.uuid), catalog)
        pytest.fail("The two external seats did not receive their native input boundaries")
    finally:
        close_session(session)
        random.setstate(random_state)


def test_content_observed_and_removed_in_one_operation_is_still_admitted(started):
    runtime, reply = started
    before = client_initialization(reply)
    private_id = "environment.spell_object.guardian_of_faith"
    assert private_id not in {row.ref.content_id for row in before.content}
    # A passive supplied descriptor isolates admission from the separate
    # question of which native catalogs supply direct-item descriptors.
    descriptor = ContentDescriptor(ref=ContentRef(pack_id="content.review",
        definition_kind=ContentDefinitionKind.ENVIRONMENT_OBJECT, content_id=private_id,
        content_version=1, definition_contract_hash="a" * 64),
        display_name="Guardian of Faith", visibility=ContentVisibility.OBSERVED)
    runtime.catalog = runtime.catalog.model_copy(update={
        "content": (*runtime.catalog.content, (descriptor.ref, descriptor))})
    start = EventQueue.event_cursor()
    guardian = build_guardian_of_faith_object(runtime.session.player_uuids[0])
    guardian.place_on_grid((12, 12))
    assert guardian.retire()
    operation = Operation(start_cursor=start, end_cursor=EventQueue.event_cursor(),
        roots=tuple(event for _, event in EventQueue.iter_events_since(start)
            if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)),
        original_logs=tuple(runtime.session.logs.log_appends),
        hud_by_seat=tuple((seat, snapshot_player_hud(runtime.session, audience=audience))
            for seat, audience in runtime.session.seats.items()))
    updates = capture_application_operation(runtime.audiences, operation, runtime.catalog)
    update = next(iter(updates.values()))
    assert guardian.uuid not in runtime.latest.objects
    assert any(row.item.item_id == private_id for lineage in update.lineages
        for world in lineage.world_updates for row in world.objects)
    assert private_id in {row.ref.content_id for row in update.content_additions}
    assert reduce_operation(before, PlayerUpdate.model_validate_json(update.model_dump_json())) == runtime.latest


def test_content_reuse_preserves_private_links_and_prior_player_states(started):
    runtime, reply = started
    before = replace(client_initialization(reply), content=())

    def descriptor(content_id, visibility, related=()):
        return ContentDescriptor(ref=ContentRef(pack_id="content.review",
            definition_kind=ContentDefinitionKind.ENVIRONMENT_OBJECT,
            content_id=content_id, content_version=1, definition_contract_hash="a" * 64),
            display_name=content_id, visibility=visibility, related_content_refs=related)

    public = descriptor("review.public", ContentVisibility.PUBLIC)
    unseen = descriptor("review.unseen", ContentVisibility.OBSERVED)
    internal = descriptor("review.internal", ContentVisibility.INTERNAL)
    linked = descriptor("review.linked", ContentVisibility.PUBLIC,
        (public.ref, unseen.ref, internal.ref))
    supplied = (public, unseen, internal, linked)
    catalog = runtime.catalog.model_copy(update={
        "content": tuple((row.ref, row) for row in supplied)})
    original_catalog = catalog.model_dump_json()
    admitted = admitted_content(catalog, before)
    assert {row.ref for row in admitted} == {public.ref, linked.ref}
    assert next(row for row in admitted if row.ref == linked.ref).related_content_refs == (public.ref,)

    update = PlayerUpdate(audience=before.viewing_audience, lineages=(), hud=None,
        combat_log_appends=(), content_additions=admitted)
    state = reduce_operation(before, PlayerUpdate.model_validate_json(update.model_dump_json()))
    assert before.content == ()
    assert state.content == admitted
    # Immutable received content remains shared when no disclosure changes.
    assert admitted_content(catalog, state) is state.content
    unchanged = reduce_operation(state, update.model_copy(update={"content_additions": ()}))
    assert unchanged.content is state.content
    assert unchanged == state

    later = descriptor("review.later", ContentVisibility.PUBLIC, (internal.ref, public.ref))
    extended_catalog = catalog.model_copy(update={
        "content": (*catalog.content, (later.ref, later))})
    extended = admitted_content(extended_catalog, state)
    additions = tuple(row for row in extended if row.ref == later.ref)
    assert len(additions) == 1 and additions[0].related_content_refs == (public.ref,)
    after = reduce_operation(state, update.model_copy(update={"content_additions": additions}))
    assert after.content == extended
    assert state.content == admitted
    assert catalog.model_dump_json() == original_catalog
    assert linked.related_content_refs == (public.ref, unseen.ref, internal.ref)

    replacement = next(row for row in state.content if row.ref == linked.ref).model_copy(
        update={"description": "Changed after admission"})
    with pytest.raises(ValueError, match="changed its definition"):
        reduce_operation(state, update.model_copy(update={"content_additions": (replacement,)}))
    assert state.content == admitted
