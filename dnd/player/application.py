"""One capture/projection path for local play, the network owner and headless probes."""

from dataclasses import dataclass, replace

from dnd.core.events import EventQueue
from dnd.player.capture import (CaptureCheckpoint, Disposition, capture_context, capture_interval, capture_lineages,
    seat_log_entry)
from dnd.player.content import UIContentManifest
from dnd.player.content_composition import (ContentCatalog, admitted_content, index_content_catalog,
    observed_content_additions)
from dnd.player.audience import perceived_entities
from dnd.player.facts import CombatLogAppend, PlayerInitialization, PlayerUpdate
from dnd.player.projection import ProjectionState, begin_projection, project_hud, project_lineage, project_log_appends
from dnd.player.reduction import reduce_initialization
from dnd.player.session import Operation, Session


@dataclass(slots=True)
class AudienceRuntime:
    """One seat's projection fold; what its client knows is read from `projection.remembered`.

    `capture` is the session's one recorded fold, the same value for every seat.
    """

    projection: ProjectionState
    capture: CaptureCheckpoint
    content_catalog: ContentCatalog


def initialize_audiences(session: Session, catalog: UIContentManifest
                         ) -> tuple[dict[str, AudienceRuntime], dict[str, PlayerInitialization]]:
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
            checkpoint.initiative, None, perceived_entities(audience, projection.remembered.perception)))
        # Startup content is admitted from the client's own first fold.
        projection.remembered.content = admitted_content(catalog, reduce_initialization(initial))
        runtimes[seat] = AudienceRuntime(projection, checkpoint, content_catalog)
        initializations[seat] = initial
    return runtimes, initializations


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
        remembered = runtime.projection.remembered
        audience = remembered.viewing_audience
        # What this seat's client knew before the operation.
        names = {str(identity): actor.name for identity, actor in remembered.actors.items()}
        known_content = frozenset(row.ref.content_id for row in remembered.content)
        known_content_keys = frozenset(row.ref.identity_key for row in remembered.content)
        perceived_before = perceived_entities(audience, remembered.perception)
        lineages = []
        natives = capture_lineages(operation.roots, observer_uuid=remembered.observer_uuid,
                audience=audience, known_actor_uuids=remembered.actors, context=context,
                known_entity_names=names,
                known_connector_uuids=frozenset(str(row.connector_uuid) for row in remembered.connectors),
                known_content_ids=known_content, omit_foreign_sensory_payloads=True)
        for native in natives:
            if any(disposition is not Disposition.NOT_DISCLOSED for _, disposition in native.dispositions):
                raise ValueError(f"Unprojected committed state: {native.dispositions}")
            lineage = project_lineage(runtime.projection, native)
            if lineage is not None:
                lineages.append(lineage)
        appends = tuple(CombatLogAppend(generation=remembered.generation, observer_uuid=remembered.observer_uuid,
            encounter_log_index=index, operation_end_cursor=operation.end_cursor, entry=entry)
            for index, original in operation.original_logs if (entry := seat_log_entry(original, audience,
                known_entity_names=names, known_content_ids=known_content)) is not None)
        appends = project_log_appends(runtime.projection, appends)
        hud = project_hud(audience, (event for native in natives for event in native.events), order_before,
            checkpoint.initiative, perceived_before, perceived_entities(audience, remembered.perception))
        if runtime.content_catalog.source is catalog:
            additions = observed_content_additions(runtime.content_catalog, known_content_keys, tuple(lineages))
            if additions:
                remembered.content = tuple(sorted((*remembered.content, *additions),
                    key=lambda row: row.ref.identity_key))
        else:
            # Replacing a supplied catalog can introduce new public descriptors.
            replacement_catalog = replacement_catalog or index_content_catalog(catalog)
            remembered.content = admitted_content(catalog, remembered, tuple(lineages))
            additions = tuple(row for row in remembered.content if row.ref.identity_key not in known_content_keys)
            runtime.content_catalog = replacement_catalog
        results[seat] = PlayerUpdate(audience=audience, lineages=tuple(lineages), hud=hud,
            combat_log_appends=appends, content_additions=additions)
    return results
