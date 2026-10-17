"""One capture/projection path for local play, the network owner and headless probes."""

from dataclasses import dataclass, replace

from dnd.core.events import EventQueue
from dnd.player.capture import CaptureCheckpoint, Disposition, capture_context, capture_interval, capture_lineages
from dnd.player.content import UIContentManifest
from dnd.player.content_composition import (ContentCatalog, admitted_content, index_content_catalog,
    observed_content_additions)
from dnd.player.facts import CombatLogAppend, PlayerInitialization, PlayerUpdate
from dnd.player.projection import ProjectionState, begin_projection, project_after_values, project_lineage
from dnd.player.reduction import reduce_initialization
from dnd.player.session import Operation, Session, snapshot_player_hud
from dnd.subjective_combat_log import project_combat_log


@dataclass(slots=True)
class AudienceRuntime:
    """One seat's projection fold; what its client knows is read from `projection.remembered`."""

    projection: ProjectionState
    capture: CaptureCheckpoint
    content_catalog: ContentCatalog


def initialize_audiences(session: Session, catalog: UIContentManifest
                         ) -> tuple[dict[str, AudienceRuntime], dict[str, PlayerInitialization]]:
    runtimes = {}
    initializations = {}
    content_catalog = index_content_catalog(catalog)
    for seat, audience in session.seats.items():
        checkpoint = CaptureCheckpoint(EventQueue.generation_id(), audience)
        startup = capture_interval(name="encounter startup", start_cursor=0,
            end_cursor=EventQueue.event_cursor(), observer_uuid=audience.observers[0],
            audience=audience, battlefield_id=session.battlefield.definition.battlefield_id,
            checkpoint=checkpoint)
        projection, initial = begin_projection(startup)
        hud, _ = project_after_values(projection, snapshot_player_hud(session, audience=audience), ())
        initial = replace(initial, hud_snapshot=hud)
        # Startup content is admitted from the client's own first fold.
        projection.remembered.content = admitted_content(catalog, reduce_initialization(initial))
        runtimes[seat] = AudienceRuntime(projection, checkpoint, content_catalog)
        initializations[seat] = initial
    return runtimes, initializations


def capture_application_operation(runtimes: dict[str, AudienceRuntime], operation: Operation,
                                  catalog: UIContentManifest) -> dict[str, PlayerUpdate]:
    """Freeze the common history once; only admitted values enter each result."""
    context = capture_context()
    results = {}
    hud_by_seat = dict(operation.hud_by_seat)
    replacement_catalog = None
    for seat, runtime in runtimes.items():
        remembered = runtime.projection.remembered
        audience = remembered.viewing_audience
        # What this seat's client knew before the operation.
        names = {str(identity): actor.name for identity, actor in remembered.actors.items()}
        known_content = frozenset(row.ref.content_id for row in remembered.content)
        known_content_keys = frozenset(row.ref.identity_key for row in remembered.content)
        lineages = []
        for native in capture_lineages(operation.roots, observer_uuid=remembered.observer_uuid,
                audience=audience, known_actor_uuids=remembered.actors, context=context,
                known_entity_names=names,
                known_connector_uuids=frozenset(str(row.connector_uuid) for row in remembered.connectors),
                known_content_ids=known_content, checkpoint=runtime.capture,
                omit_foreign_sensory_payloads=True):
            if any(disposition is not Disposition.NOT_DISCLOSED for _, disposition in native.dispositions):
                raise ValueError(f"Unprojected committed state: {native.dispositions}")
            lineage = project_lineage(runtime.projection, native)
            if lineage is not None:
                lineages.append(lineage)
        appends = tuple(CombatLogAppend(generation=remembered.generation, observer_uuid=remembered.observer_uuid,
            encounter_log_index=index, operation_end_cursor=operation.end_cursor, entry=entry)
            for index, original in operation.original_logs if (entry := project_combat_log(original,
                controlled_entity_uuids=audience.controlled_ids,
                observer_entity_uuids=audience.observer_ids, known_entity_names=names,
                known_content_ids=known_content)) is not None)
        hud, appends = project_after_values(runtime.projection, hud_by_seat[seat], appends)
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
