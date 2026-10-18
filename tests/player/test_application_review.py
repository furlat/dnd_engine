"""Published common application after-values reproduce what the seat's projection holds."""

import random
from dataclasses import dataclass, replace

import pytest
from pydantic import TypeAdapter

from dnd.core.content.descriptors import ContentDescriptor, ContentVisibility
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.player.application import AudienceRuntime, capture_application_operation, initialize_audiences, seat_content
from dnd.player.audience import PlayerAudience
from dnd.player.content import UIContentManifest
from dnd.player.content_composition import admitted_content, ui_content_manifest
from dnd.player.facts import PlayerInitialization, PlayerState, PlayerUpdate
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.session import (
    Operation, Session, advance_controller, close_session, create_session, discover_player_actions,
    end_player_turn, toggle_player_handler,
)
from dnd.runtime_reset import reset_engine_runtime


INITIALIZATION = TypeAdapter(PlayerInitialization)


@dataclass(frozen=True)
class Started:
    session: Session
    catalog: UIContentManifest
    audiences: dict[str, AudienceRuntime]
    seat: str
    initialization: PlayerInitialization

    @property
    def runtime(self) -> AudienceRuntime:
        return self.audiences[self.seat]


@pytest.fixture
def started():
    random_state = random.getstate()
    random.seed(0)
    session = create_session()
    try:
        catalog = ui_content_manifest()
        audiences, initializations = initialize_audiences(session, catalog)
        seat = next(iter(initializations))
        yield Started(session, catalog, audiences, seat, initializations[seat])
    finally:
        close_session(session)
        reset_engine_runtime()
        random.setstate(random_state)


def client_initialization(started: Started) -> PlayerState:
    """Reduce the published initialization and admitted content after detaching them."""
    detached = INITIALIZATION.validate_json(INITIALIZATION.dump_json(started.initialization))
    content = tuple(ContentDescriptor.model_validate_json(row.model_dump_json())
        for row in seat_content(started.runtime))
    return reduce_initialization(detached, content_additions=content)


def known_content(state: PlayerState) -> tuple:
    # What the client holds beyond the lineages, against the content the seat was sent (`seat_content`); the
    # HUD is the client's alone (the server keeps none).
    return state.content


def client_operation(started: Started, state: PlayerState, operation: Operation) -> PlayerState:
    """Capture one committed operation and reduce its detached update for this seat."""
    update = capture_application_operation(started.audiences, operation, started.catalog)[started.seat]
    return reduce_operation(state, PlayerUpdate.model_validate_json(update.model_dump_json()))


def test_published_initialization_has_only_admitted_descriptors_and_replays_exactly(started):
    assert all(row.visibility in (ContentVisibility.PUBLIC, ContentVisibility.OBSERVED)
        for row in seat_content(started.runtime))
    assert known_content(client_initialization(started)) == seat_content(started.runtime)


def test_common_operation_replays_eventless_handler_after_values(started):
    state = client_initialization(started)
    advanced = advance_controller(started.session)
    assert advanced.boundary is not None and advanced.boundary.status == "waiting_for_human"
    state = client_operation(started, state, advanced)
    assert known_content(state) == seat_content(started.runtime)
    actor = state.current_actor_uuid
    assert actor is not None and state.hud_snapshot is not None
    sheet = next(row for row in state.hud_snapshot.sheets if row.actor_uuid == actor)
    handler = sheet.handler_details[0]
    discover_player_actions(started.session, actor)
    changed = toggle_player_handler(started.session, actor, handler.uuid, not handler.enabled)
    state = client_operation(started, state, changed)
    assert known_content(state) == seat_content(started.runtime)
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


def test_content_reuse_preserves_private_links_and_prior_player_states(started):
    before = replace(client_initialization(started), content=())

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
    catalog = started.catalog.model_copy(update={
        "content": tuple((row.ref, row) for row in supplied)})
    original_catalog = catalog.model_dump_json()
    admitted = admitted_content(catalog, before)
    assert {row.ref for row in admitted} == {public.ref, linked.ref}
    assert next(row for row in admitted if row.ref == linked.ref).related_content_refs == (public.ref,)

    update = PlayerUpdate(generation=before.generation, observer_uuid=before.observer_uuid, lineages=(), hud=None,
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
