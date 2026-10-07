"""One capture/reduction path for local play, the network owner and headless probes."""

from dataclasses import dataclass, replace

from dnd.core.events import EventQueue
from dnd.player.capture import CaptureCheckpoint, capture_context, capture_interval, capture_lineages
from dnd.player.content import UIContentManifest
from dnd.player.content_composition import admitted_content
from dnd.player.facts import CombatLogAppend, PlayerInitialization, PlayerState, PlayerUpdate
from dnd.player.projection import ProjectionState, begin_projection, project_after_values, project_lineage
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.session import Operation, Session, snapshot_player_hud
from dnd.subjective_combat_log import project_combat_log


@dataclass(slots=True)
class AudienceRuntime:
    projection: ProjectionState
    latest: PlayerState
    capture: CaptureCheckpoint


def initialize_audiences(session: Session, catalog: UIContentManifest
                         ) -> tuple[dict[str, AudienceRuntime], dict[str, PlayerInitialization]]:
    runtimes = {}
    initializations = {}
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
        runtimes[seat] = AudienceRuntime(projection, latest, checkpoint)
        initializations[seat] = initial
    return runtimes, initializations


def capture_application_operation(runtimes: dict[str, AudienceRuntime], operation: Operation,
                                  catalog: UIContentManifest) -> dict[str, PlayerUpdate]:
    """Freeze the common history once; only admitted values enter each result."""
    context = capture_context()
    results = {}
    hud_by_seat = dict(operation.hud_by_seat)
    staged = {}
    for seat, runtime in runtimes.items():
        prior = runtime.latest
        audience = prior.viewing_audience
        names = {str(identity): actor.name for identity, actor in prior.actors.items()}
        known_content = frozenset(row.ref.content_id for row in prior.content)
        lineages = []
        for native in capture_lineages(operation.roots, observer_uuid=prior.observer_uuid,
                audience=audience, known_actor_uuids=frozenset(prior.actors), context=context,
                known_entity_names=names, known_connector_uuids=frozenset(str(row.connector_uuid) for row in prior.connectors),
                known_content_ids=known_content, checkpoint=runtime.capture):
            if native.dispositions:
                raise ValueError(f"Unprojected committed state: {native.dispositions}")
            lineage = project_lineage(runtime.projection, native)
            if lineage is not None:
                lineages.append(lineage)
        appends = tuple(CombatLogAppend(generation=prior.generation, observer_uuid=prior.observer_uuid,
            encounter_log_index=index, operation_end_cursor=operation.end_cursor, entry=entry)
            for index, original in operation.original_logs if (entry := project_combat_log(original,
                controlled_entity_uuids=frozenset(map(str, audience.controlled)),
                observer_entity_uuids=frozenset(map(str, audience.observers)), known_entity_names=names,
                known_content_ids=known_content)) is not None)
        hud, appends = project_after_values(runtime.projection, hud_by_seat[seat], appends)
        content = admitted_content(catalog, replace(runtime.projection.remembered, content=prior.content), tuple(lineages))
        previous = {row.ref.identity_key for row in prior.content}
        additions = tuple(row for row in content if row.ref.identity_key not in previous)
        update = PlayerUpdate(audience=audience, lineages=tuple(lineages), hud=hud,
            combat_log_appends=appends, content_additions=additions)
        staged[seat] = reduce_operation(prior, update)
        results[seat] = update
    for seat, latest in staged.items():
        runtimes[seat].latest = latest
    return results
