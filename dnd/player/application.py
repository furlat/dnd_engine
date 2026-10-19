"""One capture/projection path for local play, the network owner and headless probes."""

from dataclasses import dataclass, replace

from dnd.core.events import EventQueue
from dnd.player.capture import (CaptureCheckpoint, Disposition, capture_context, capture_interval, capture_lineages,
    seat_log_entry)
from dnd.player.content import UIContentManifest
from dnd.core.content.descriptors import ContentDescriptor, ContentVisibility
from dnd.player.content_composition import (ContentCatalog, index_content_catalog, observed_content_additions,
    startup_content)
from dnd.player.audience import perceived_entities
from dnd.player.facts import CombatLogAppend, PlayerInitialization, PlayerLineage, PlayerUpdate
from dnd.player.projection import (ProjectionState, SeatLogInputs, SessionProjection, begin_projections,
    known_connector_uuids, project_hud, project_lineages, project_log_appends)
from dnd.player.session import Operation, Session


@dataclass(slots=True)
class AudienceRuntime:
    """One seat's projection: its knowledge (control, perception, what static content it was sent).

    `capture` is the session's recorded evidence (births, pending trees, initiative) and `session`
    (`SessionProjection`) the folds every seat shares in projection: the world and the actors as of each
    occurrence, the same values for every seat.
    """

    projection: ProjectionState
    capture: CaptureCheckpoint
    session: SessionProjection
    content_catalog: ContentCatalog


def initialize_audiences(session: Session, catalog: UIContentManifest
                         ) -> tuple[dict[str, AudienceRuntime], dict[str, PlayerInitialization]]:
    """Each seat's initialization, before the session's first operation: its HUD is the projection of
    the startup sheet publication (one per actor), which only a fresh session's history holds."""
    runtimes = {}
    initializations = {}
    content_catalog = index_content_catalog(catalog)
    end_cursor = EventQueue.event_cursor()
    checkpoint = CaptureCheckpoint(EventQueue.generation_id())
    context = capture_context(checkpoint, end_cursor=end_cursor)
    shared = SessionProjection()
    startups = {seat: capture_interval(name="encounter startup", start_cursor=0,
        end_cursor=end_cursor, observer_uuid=audience.observers[0],
        audience=audience, battlefield_id=session.battlefield.definition.battlefield_id,
        context=context) for seat, audience in session.seats.items()}
    projected = dict(zip(startups, begin_projections(shared, tuple(startups.values())), strict=True))
    for seat, audience in session.seats.items():
        startup = startups[seat]
        projection, initial = projected[seat]
        # The startup publication's projection: the sheets whole, the perceived initiative.
        initial = replace(initial, hud=project_hud(audience, (event for _, event in startup.admitted), None,
            checkpoint.initiative, perceived_entities(audience, projection.audience_composition.view)))
        # Startup content: the public catalog and the observed content the initialization witnesses.
        projection.static_sent.content.update(row.ref.identity_key
            for row in startup_content(content_catalog, initial))
        runtimes[seat] = AudienceRuntime(projection, checkpoint, shared, content_catalog)
        initializations[seat] = initial
    return runtimes, initializations


@dataclass(frozen=True, slots=True)
class SeatCaptureInputs:
    """What a seat's combat log reads as an operation starts: the names of the bodies it holds (its births sent,
    from the session's names table), the connectors it sees and the content ids it holds. Standalone appends read
    the names as of then; the walk's node entries start from them (`SeatLogInputs`)."""

    names: dict[str, str]
    connectors: frozenset[str]
    content_ids: frozenset[str]


def seat_capture_inputs(runtime: AudienceRuntime) -> SeatCaptureInputs:
    sent = runtime.projection.static_sent
    return SeatCaptureInputs(names={str(identity): runtime.session.names[identity] for identity in sent.actor_births},
        connectors=known_connector_uuids(runtime.session, runtime.projection),
        content_ids=frozenset(runtime.content_catalog.identity_content_ids[key] for key in sent.content))


def capture_application_operation(runtimes: dict[str, AudienceRuntime], operation: Operation,
                                  catalog: UIContentManifest) -> dict[str, PlayerUpdate]:
    """Freeze the common history once; only admitted values enter each result."""
    checkpoint = next(iter(runtimes.values())).capture
    shared = next(iter(runtimes.values())).session
    if any(runtime.capture is not checkpoint or runtime.session is not shared for runtime in runtimes.values()):
        raise ValueError("Every seat of a session shares its one capture fold and projection")
    order_before = checkpoint.initiative
    context = capture_context(checkpoint, operation.roots)
    results = {}
    replacement_catalog = None
    # What each seat's client knew before the operation, and each root captured for it.
    known_before = {seat: seat_capture_inputs(runtime) for seat, runtime in runtimes.items()}
    perceived_before = {seat: perceived_entities(runtime.projection.audience, runtime.projection.audience_composition.view)
        for seat, runtime in runtimes.items()}
    natives = {seat: capture_lineages(operation.roots, observer_uuid=runtime.projection.observer_uuid,
            audience=runtime.projection.audience, context=context, omit_foreign_sensory_payloads=True)
        for seat, runtime in runtimes.items()}
    for captured in natives.values():
        for native in captured:
            if any(disposition is not Disposition.NOT_DISCLOSED for _, disposition in native.dispositions):
                raise ValueError(f"Unprojected committed state: {native.dispositions}")
    # Each walk group projected once for every seat, event by event.
    lineages: dict[str, list[PlayerLineage]] = {seat: [] for seat in runtimes}
    log_inputs = tuple(SeatLogInputs(known.connectors, known.content_ids) for known in known_before.values())
    for group in range(len(context.groups)):
        projected = project_lineages(shared, tuple(runtime.projection for runtime in runtimes.values()),
            tuple(captured[group] for captured in natives.values()), log_inputs)
        for seat, lineage in zip(runtimes, projected, strict=True):
            if lineage is not None:
                lineages[seat].append(lineage)
    for seat, runtime in runtimes.items():
        projection = runtime.projection
        audience = projection.audience
        sent = projection.static_sent
        known = known_before[seat]
        known_content_keys = frozenset(sent.content)
        appends = tuple(CombatLogAppend(generation=projection.generation, observer_uuid=projection.observer_uuid,
            encounter_log_index=index, operation_end_cursor=operation.end_cursor, entry=entry)
            for index, original in operation.original_logs if (entry := seat_log_entry(original, audience,
                known_entity_names=known.names, known_content_ids=known.content_ids)) is not None)
        appends = project_log_appends(projection, appends)
        hud = project_hud(audience, (event for native in natives[seat] for event in native.events),
            (order_before, perceived_before[seat]), checkpoint.initiative,
            perceived_entities(audience, projection.audience_composition.view))
        added: dict[str, ContentDescriptor] = {}
        if runtime.content_catalog.source is not catalog:
            # A replacement catalog sends its new public descriptors now, its observed ones as they are witnessed.
            replacement_catalog = replacement_catalog or index_content_catalog(catalog)
            runtime.content_catalog = replacement_catalog
            added.update((key, row) for key, row in replacement_catalog.descriptors.items()
                if row.visibility is ContentVisibility.PUBLIC and key not in known_content_keys)
        added.update((row.ref.identity_key, row) for row in
            observed_content_additions(runtime.content_catalog, known_content_keys, tuple(lineages[seat])))
        additions = tuple(added[key] for key in sorted(added))
        sent.content.update(added)
        results[seat] = PlayerUpdate(generation=projection.generation, observer_uuid=projection.observer_uuid,
            lineages=tuple(lineages[seat]), hud=hud,
            combat_log_appends=appends, content_additions=additions)
    return results


def seat_content(runtime: AudienceRuntime) -> tuple[ContentDescriptor, ...]:
    """The content descriptors the seat holds, in identity order (its startup records carry them)."""
    return tuple(runtime.content_catalog.descriptors[key] for key in sorted(runtime.projection.static_sent.content))
