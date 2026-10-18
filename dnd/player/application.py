"""One capture/projection path for local play, the network owner and headless probes."""

from dataclasses import dataclass, replace
from uuid import UUID

from dnd.core.events import EventQueue
from dnd.player.capture import (CaptureCheckpoint, Disposition, capture_context, capture_interval, capture_lineages,
    seat_log_entry)
from dnd.player.content import UIContentManifest
from dnd.core.content.descriptors import ContentDescriptor, ContentVisibility
from dnd.player.content_composition import (ContentCatalog, index_content_catalog, observed_content_additions,
    startup_content)
from dnd.player.audience import perceived_entities
from dnd.player.facts import CombatLogAppend, PlayerInitialization, PlayerUpdate
from dnd.player.projection import (ProjectionState, begin_projection, known_connector_uuids, project_hud,
    project_lineage, project_log_appends)
from dnd.player.session import Operation, Session


@dataclass(slots=True)
class AudienceRuntime:
    """One seat's projection: its knowledge (control, perception, what static content it was sent) and,
    until the body lane, its client's bodies (`projection.remembered`).

    `capture` is the session's one recorded fold, the same value for every seat.
    """

    projection: ProjectionState
    capture: CaptureCheckpoint
    content_catalog: ContentCatalog


def initialize_audiences(session: Session, catalog: UIContentManifest
                         ) -> tuple[dict[str, AudienceRuntime], dict[str, PlayerInitialization]]:
    """Each seat's initialization, before the session's first operation: its HUD is the projection of
    the startup sheet publication (one per actor), which only a fresh session's history holds."""
    runtimes = {}
    initializations = {}
    content_catalog = index_content_catalog(catalog)
    end_cursor = EventQueue.event_cursor()
    checkpoint = CaptureCheckpoint(EventQueue.generation_id(),
        frozenset(observer for audience in session.seats.values() for observer in audience.observers))
    context = capture_context(checkpoint, end_cursor=end_cursor)
    for seat, audience in session.seats.items():
        startup = capture_interval(name="encounter startup", start_cursor=0,
            end_cursor=end_cursor, observer_uuid=audience.observers[0],
            audience=audience, battlefield_id=session.battlefield.definition.battlefield_id,
            context=context)
        projection, initial = begin_projection(startup)
        # The startup publication's projection: the sheets whole, the perceived initiative.
        initial = replace(initial, hud=project_hud(audience, (event for _, event in startup.admitted), None,
            checkpoint.initiative, perceived_entities(audience, projection.remembered.perception)))
        # Startup content: the public catalog and the observed content the initialization witnesses.
        projection.static_sent.content.update(row.ref.identity_key
            for row in startup_content(content_catalog, initial))
        runtimes[seat] = AudienceRuntime(projection, checkpoint, content_catalog)
        initializations[seat] = initial
    return runtimes, initializations


@dataclass(frozen=True, slots=True)
class SeatCaptureInputs:
    """What a seat knows as an operation starts, as its capture reads it: the actors it knows (by birth) with
    their names, the connectors it sees and the content ids it holds."""

    actors: frozenset[UUID]
    names: dict[str, str]
    connectors: frozenset[str]
    content_ids: frozenset[str]


def seat_capture_inputs(runtime: AudienceRuntime) -> SeatCaptureInputs:
    sent = runtime.projection.static_sent
    return SeatCaptureInputs(actors=frozenset(sent.actor_births),
        names={str(identity): runtime.capture.names[identity] for identity in sent.actor_births},
        connectors=known_connector_uuids(runtime.projection),
        content_ids=frozenset(runtime.content_catalog.identity_content_ids[key] for key in sent.content))


def capture_application_operation(runtimes: dict[str, AudienceRuntime], operation: Operation,
                                  catalog: UIContentManifest) -> dict[str, PlayerUpdate]:
    """Freeze the common history once; only admitted values enter each result."""
    checkpoint = next(iter(runtimes.values())).capture
    if any(runtime.capture is not checkpoint for runtime in runtimes.values()):
        raise ValueError("Every seat of a session shares its one capture fold")
    order_before = checkpoint.initiative
    context = capture_context(checkpoint, operation.roots)
    results = {}
    replacement_catalog = None
    for seat, runtime in runtimes.items():
        projection = runtime.projection
        remembered = projection.remembered
        audience = projection.audience
        sent = projection.static_sent
        # What this seat's client knew before the operation.
        known = seat_capture_inputs(runtime)
        known_content_keys = frozenset(sent.content)
        perceived_before = perceived_entities(audience, remembered.perception)
        lineages = []
        natives = capture_lineages(operation.roots, observer_uuid=remembered.observer_uuid,
                audience=audience, known_actor_uuids=known.actors, context=context,
                known_entity_names=known.names, known_connector_uuids=known.connectors,
                known_content_ids=known.content_ids, omit_foreign_sensory_payloads=True)
        for native in natives:
            if any(disposition is not Disposition.NOT_DISCLOSED for _, disposition in native.dispositions):
                raise ValueError(f"Unprojected committed state: {native.dispositions}")
            lineage = project_lineage(projection, native)
            if lineage is not None:
                lineages.append(lineage)
        appends = tuple(CombatLogAppend(generation=remembered.generation, observer_uuid=remembered.observer_uuid,
            encounter_log_index=index, operation_end_cursor=operation.end_cursor, entry=entry)
            for index, original in operation.original_logs if (entry := seat_log_entry(original, audience,
                known_entity_names=known.names, known_content_ids=known.content_ids)) is not None)
        appends = project_log_appends(projection, appends)
        hud = project_hud(audience, (event for native in natives for event in native.events),
            (order_before, perceived_before), checkpoint.initiative, perceived_entities(audience, remembered.perception))
        added: dict[str, ContentDescriptor] = {}
        if runtime.content_catalog.source is not catalog:
            # A replacement catalog sends its new public descriptors now, its observed ones as they are witnessed.
            replacement_catalog = replacement_catalog or index_content_catalog(catalog)
            runtime.content_catalog = replacement_catalog
            added.update((key, row) for key, row in replacement_catalog.descriptors.items()
                if row.visibility is ContentVisibility.PUBLIC and key not in known_content_keys)
        added.update((row.ref.identity_key, row) for row in
            observed_content_additions(runtime.content_catalog, known_content_keys, tuple(lineages)))
        additions = tuple(added[key] for key in sorted(added))
        sent.content.update(added)
        results[seat] = PlayerUpdate(audience=audience, lineages=tuple(lineages), hud=hud,
            combat_log_appends=appends, content_additions=additions)
    return results


def seat_content(runtime: AudienceRuntime) -> tuple[ContentDescriptor, ...]:
    """The content descriptors the seat holds, in identity order (its startup records carry them)."""
    return tuple(runtime.content_catalog.descriptors[key] for key in sorted(runtime.projection.static_sent.content))
