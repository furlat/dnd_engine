"""One capture/reduction path for local play, the network owner and headless probes."""

from dataclasses import dataclass, field, replace

from dnd.core.events import EventQueue
from dnd.types.event_facts import WorldConnectorState
from dnd.player.audience import AudienceComposition, begin_audience_composition
from dnd.player.capture import CaptureCheckpoint, Disposition, capture_context, capture_interval, capture_lineages
from dnd.player.content import UIContentManifest
from dnd.player.content_composition import (ContentCatalog, admitted_content, index_content_catalog,
    observed_content_additions)
from dnd.player.facts import CombatLogAppend, PlayerInitialization, PlayerState, PlayerUpdate
from dnd.player.projection import ProjectionState, begin_projection, project_after_values, project_lineage
from dnd.player.reduction import (
    apply_current_operation, prepare_current_operation, reduce_initialization, reduce_operation,
)
from dnd.player.session import Operation, Session, snapshot_player_hud
from dnd.subjective_combat_log import project_combat_log


@dataclass(slots=True)
class AudienceRuntime:
    projection: ProjectionState
    latest: PlayerState
    capture: CaptureCheckpoint
    current_composition: AudienceComposition | None = None
    committed_log_count: int | None = None
    content_catalog: ContentCatalog | None = None
    known_names: dict[str, str] = field(default_factory=dict)
    known_content_ids: set[str] = field(default_factory=set)
    known_content_keys: set[str] = field(default_factory=set)
    known_connector_ids: frozenset[str] = frozenset()
    known_connector_values: tuple[WorldConnectorState, ...] = ()


def initialize_audiences(session: Session, catalog: UIContentManifest, *, exclusive_current: bool = False
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
        latest = reduce_initialization(initial)
        latest.content = admitted_content(catalog, latest)
        composition = begin_audience_composition(latest.perception, latest.observer_uuid) if exclusive_current else None
        if composition is not None:
            latest.perception, latest.senses = composition.perception, composition.view
        runtimes[seat] = AudienceRuntime(projection, latest, checkpoint, composition,
            len(latest.combat_log_appends) if exclusive_current else None,
            content_catalog=content_catalog,
            known_names={str(identity): actor.name for identity, actor in latest.actors.items()},
            known_content_ids={row.ref.content_id for row in latest.content},
            known_content_keys={row.ref.identity_key for row in latest.content},
            known_connector_ids=frozenset(str(row.connector_uuid) for row in latest.connectors),
            known_connector_values=latest.connectors)
        initializations[seat] = initial
    return runtimes, initializations


def capture_application_operation(runtimes: dict[str, AudienceRuntime], operation: Operation,
                                  catalog: UIContentManifest) -> dict[str, PlayerUpdate]:
    """Freeze the common history once; only admitted values enter each result."""
    context = capture_context()
    results = {}
    hud_by_seat = dict(operation.hud_by_seat)
    staged = {}
    replacement_catalog = None
    for seat, runtime in runtimes.items():
        prior = runtime.latest
        audience = prior.viewing_audience
        catalog_changed = runtime.content_catalog is None or runtime.content_catalog.source is not catalog
        if runtime.content_catalog is None:
            runtime.content_catalog = index_content_catalog(catalog)
            runtime.known_names.update((str(identity), actor.name) for identity, actor in prior.actors.items())
            runtime.known_content_ids.update(row.ref.content_id for row in prior.content)
            runtime.known_content_keys.update(row.ref.identity_key for row in prior.content)
            runtime.known_connector_ids = frozenset(str(row.connector_uuid) for row in prior.connectors)
            runtime.known_connector_values = prior.connectors
        names = runtime.known_names
        known_content = runtime.known_content_ids
        lineages = []
        for native in capture_lineages(operation.roots, observer_uuid=prior.observer_uuid,
                audience=audience, known_actor_uuids=prior.actors, context=context,
                known_entity_names=names, known_connector_uuids=runtime.known_connector_ids,
                known_content_ids=known_content, checkpoint=runtime.capture,
                omit_foreign_sensory_payloads=True):
            if any(disposition is not Disposition.NOT_DISCLOSED for _, disposition in native.dispositions):
                raise ValueError(f"Unprojected committed state: {native.dispositions}")
            lineage = project_lineage(runtime.projection, native)
            if lineage is not None:
                lineages.append(lineage)
        appends = tuple(CombatLogAppend(generation=prior.generation, observer_uuid=prior.observer_uuid,
            encounter_log_index=index, operation_end_cursor=operation.end_cursor, entry=entry)
            for index, original in operation.original_logs if (entry := project_combat_log(original,
                controlled_entity_uuids=audience.controlled_ids,
                observer_entity_uuids=audience.observer_ids, known_entity_names=names,
                known_content_ids=known_content)) is not None)
        hud, appends = project_after_values(runtime.projection, hud_by_seat[seat], appends)
        if not catalog_changed:
            additions = observed_content_additions(runtime.content_catalog, runtime.known_content_keys, tuple(lineages))
        else:
            # Replacing a supplied catalog can introduce new public descriptors.
            replacement_catalog = replacement_catalog or index_content_catalog(catalog)
            content = admitted_content(catalog, replace(runtime.projection.remembered, content=prior.content), tuple(lineages))
            additions = tuple(row for row in content if row.ref.identity_key not in runtime.known_content_keys)
        update = PlayerUpdate(audience=audience, lineages=tuple(lineages), hud=hud,
            combat_log_appends=appends, content_additions=additions)
        results[seat] = update
    prepared = {}
    for seat, update in results.items():
        runtime = runtimes[seat]
        if runtime.committed_log_count is None:
            staged[seat] = reduce_operation(runtime.latest, update)
        else:
            prepared[seat] = prepare_current_operation(runtime.latest, update,
                log_count=runtime.committed_log_count)
    # Every seat has passed validation before any exclusive current state changes.
    # Public callers retain detached latest snapshots; the worker's journal owns
    # historical log entries, while its current fold keeps the committed count.
    for seat, latest in staged.items():
        runtimes[seat].latest = latest
    for seat, values in prepared.items():
        runtime = runtimes[seat]
        assert runtime.current_composition is not None
        apply_current_operation(runtime.latest, results[seat], values, runtime.current_composition)
        runtime.committed_log_count = values.log_count
    for seat, update in results.items():
        runtime = runtimes[seat]
        for lineage in update.lineages:
            runtime.known_names.update((str(row.actor.uuid), runtime.latest.actors[row.actor.uuid].name)
                for row in lineage.observations if row.actor.uuid in runtime.latest.actors)
        runtime.known_content_ids.update(row.ref.content_id for row in update.content_additions)
        runtime.known_content_keys.update(row.ref.identity_key for row in update.content_additions)
        if runtime.known_connector_values is not runtime.latest.connectors:
            runtime.known_connector_values = runtime.latest.connectors
            runtime.known_connector_ids = frozenset(str(row.connector_uuid) for row in runtime.latest.connectors)
        if replacement_catalog is not None:
            runtime.content_catalog = replacement_catalog
    return results
