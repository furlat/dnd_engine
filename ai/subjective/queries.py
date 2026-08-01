"""Typed local reads over one materialized subjective world revision."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationEncounterState,
    ObservationEntityFact,
    ObservationObjectFact,
    ObservationObserverState,
    ObservationSessionState,
    ObservationTileFact,
    SubjectiveWorldState,
)
from dnd.ai.contracts.control import ActionAffordance, ActionCapability, ActionEconomyState, DecisionEpoch
from dnd.ai.contracts.semantics import ActionSemantics, ActionTag
from ai.subjective.models import AgentState


class SubjectiveQueryModel(BaseModel):
    """Immutable base for local subjective query contracts."""

    model_config = ConfigDict(frozen=True)


class SubjectiveAreaQuery(SubjectiveQueryModel):
    """Inclusive rectangular window over accumulated subjective map knowledge."""

    min_x: int = Field(description="Minimum grid x coordinate, inclusive.")
    max_x: int = Field(description="Maximum grid x coordinate, inclusive.")
    min_y: int = Field(description="Minimum grid y coordinate, inclusive.")
    max_y: int = Field(description="Maximum grid y coordinate, inclusive.")

    @model_validator(mode="after")
    def _validate_bounds(self) -> "SubjectiveAreaQuery":
        """Reject inverted or unbounded local read windows."""
        if self.max_x < self.min_x or self.max_y < self.min_y:
            raise ValueError("Area query bounds must be ordered")
        if (self.max_x - self.min_x + 1) * (self.max_y - self.min_y + 1) > 1_024:
            raise ValueError("Area query may cover at most 1024 grid positions")
        return self

    def contains(self, position: Tuple[int, int]) -> bool:
        """Return whether a position lies inside this inclusive window."""
        return (
            self.min_x <= position[0] <= self.max_x
            and self.min_y <= position[1] <= self.max_y
        )


class SubjectiveActionFilter(SubjectiveQueryModel):
    """Deterministic filter and page over current authoritative affordances."""

    buckets: Tuple[str, ...] = Field(default_factory=tuple, description="Accepted action buckets.")
    source_action_ids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Accepted epoch-local discovered-action identities.",
    )
    semantic_keys: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Accepted stable engine action-definition identities.",
    )
    template_names: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Accepted engine template names.",
    )
    base_template_names: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Accepted registered template-family names.",
    )
    cast_at_levels: Tuple[int, ...] = Field(
        default_factory=tuple,
        description="Accepted selected spell-slot levels.",
    )
    semantic_ids: Tuple[str, ...] = Field(default_factory=tuple, description="Accepted semantic families.")
    tags: Tuple[ActionTag, ...] = Field(default_factory=tuple, description="Required semantic tags.")
    action_categories: Tuple[str, ...] = Field(default_factory=tuple, description="Accepted action categories.")
    target_types: Tuple[str, ...] = Field(default_factory=tuple, description="Accepted target allocation types.")
    target_uuid: Optional[str] = Field(default=None, description="Required entity or object target UUID.")
    can_afford: Optional[bool] = Field(default=None, description="Required current affordability state.")
    offset: int = Field(default=0, ge=0, description="Zero-based offset in deterministic epoch order.")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum returned action rows.")


class SubjectiveQuerySelection(SubjectiveQueryModel):
    """One batch of local facts selected from the same subjective revision."""

    include_session: bool = Field(default=False, description="Return the complete subjective session state.")
    include_encounter: bool = Field(default=False, description="Return the complete subjective encounter state.")
    observer_uuids: Tuple[str, ...] = Field(default_factory=tuple, description="Exact controlled observer UUIDs to read.")
    entity_uuids: Tuple[str, ...] = Field(default_factory=tuple, description="Exact known entity UUIDs to read.")
    object_uuids: Tuple[str, ...] = Field(default_factory=tuple, description="Exact known object UUIDs to read.")
    tile_keys: Tuple[str, ...] = Field(default_factory=tuple, description="Exact known tile keys to read.")
    row_ids: Tuple[str, ...] = Field(default_factory=tuple, description="Exact current-epoch affordance IDs to read.")
    capability_ids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Exact current-epoch non-executable capability IDs to read.",
    )
    include_all_capabilities: bool = Field(default=False, description="Return every current actor capability.")
    area: Optional[SubjectiveAreaQuery] = Field(
        default=None,
        description="Optional window adding every locally known entity, object, and tile inside it.",
    )
    action_filter: Optional[SubjectiveActionFilter] = Field(
        default=None,
        description="Optional deterministic affordance filter and page.",
    )
    recent_log_limit: int = Field(default=0, ge=0, le=50, description="Number of most recent subjective logs to read.")


class SubjectiveActionDetail(SubjectiveQueryModel):
    """One executable row together with its resolved typed meaning."""

    affordance: ActionAffordance = Field(description="Complete server-authorized action row.")
    semantics: ActionSemantics = Field(description="Resolved semantic contract for this row.")


class SubjectiveQueryResult(SubjectiveQueryModel):
    """Typed details selected entirely from one local subjective world."""

    session: Optional[ObservationSessionState] = Field(default=None, description="Complete session state when requested.")
    encounter: Optional[ObservationEncounterState] = Field(
        default=None,
        description="Complete subjective encounter state when requested and known.",
    )
    observers: Tuple[ObservationObserverState, ...] = Field(
        default_factory=tuple,
        description="Selected controlled observer states.",
    )
    entities: Tuple[ObservationEntityFact, ...] = Field(default_factory=tuple, description="Selected known entities.")
    objects: Tuple[ObservationObjectFact, ...] = Field(default_factory=tuple, description="Selected known objects.")
    tiles: Tuple[ObservationTileFact, ...] = Field(default_factory=tuple, description="Selected known tiles.")
    actions: Tuple[SubjectiveActionDetail, ...] = Field(default_factory=tuple, description="Selected current-epoch rows.")
    capabilities: Tuple[ActionCapability, ...] = Field(
        default_factory=tuple,
        description="Selected current actor capabilities without execution authority.",
    )
    recent_combat_logs: Tuple[dict[str, Any], ...] = Field(
        default_factory=tuple,
        description="Requested suffix of the locally materialized subjective combat log.",
    )
    total_matching_actions: int = Field(default=0, ge=0, description="Total rows matching action_filter before paging.")
    next_action_offset: Optional[int] = Field(default=None, ge=0, description="Next deterministic action offset, if any.")
    missing_entity_uuids: Tuple[str, ...] = Field(default_factory=tuple, description="Requested entity IDs absent locally.")
    missing_observer_uuids: Tuple[str, ...] = Field(default_factory=tuple, description="Requested observer IDs absent locally.")
    missing_object_uuids: Tuple[str, ...] = Field(default_factory=tuple, description="Requested object IDs absent locally.")
    missing_tile_keys: Tuple[str, ...] = Field(default_factory=tuple, description="Requested tile keys absent locally.")
    missing_row_ids: Tuple[str, ...] = Field(default_factory=tuple, description="Requested row IDs absent from the current epoch.")
    missing_capability_ids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Requested capability IDs absent from the current epoch.",
    )


class SubjectiveQueries:
    """Read-only selection over a subjective world and its derived facts."""

    def __init__(self, world: SubjectiveWorldState, agent_state: AgentState) -> None:
        """Bind one already-materialized local revision without network access."""
        self.world = world
        self.agent_state = agent_state

    def select(self, selection: SubjectiveQuerySelection) -> SubjectiveQueryResult:
        """Return one deterministic batch containing only locally known facts."""
        entity_ids = list(selection.entity_uuids)
        object_ids = list(selection.object_uuids)
        tile_keys = list(selection.tile_keys)
        if selection.area is not None:
            entity_ids.extend(
                uuid for uuid, fact in sorted(self.world.known_entities.items())
                if fact.position is not None and selection.area.contains(fact.position)
            )
            object_ids.extend(
                uuid for uuid, fact in sorted(self.world.known_objects.items())
                if fact.position is not None and selection.area.contains(fact.position)
            )
            tile_keys.extend(
                key for key, fact in sorted(self.world.known_tiles.items(), key=lambda item: (item[1].position, item[0]))
                if selection.area.contains(fact.position)
            )

        entities = tuple(
            self.world.known_entities[uuid]
            for uuid in _deduplicate(entity_ids)
            if uuid in self.world.known_entities
        )
        objects = tuple(
            self.world.known_objects[uuid]
            for uuid in _deduplicate(object_ids)
            if uuid in self.world.known_objects
        )
        tiles = tuple(
            self.world.known_tiles[key]
            for key in _deduplicate(tile_keys)
            if key in self.world.known_tiles
        )
        actions, total_actions, next_offset, missing_rows = self._select_actions(selection)
        epoch = self.world.current_epoch
        capability_rows = epoch.affordances.capabilities if epoch is not None else tuple()
        capabilities_by_id = {row.capability_id: row for row in capability_rows}
        requested_capability_ids = (
            tuple(capabilities_by_id)
            if selection.include_all_capabilities
            else _deduplicate(selection.capability_ids)
        )
        logs = (
            tuple(self.world.combat_logs[-selection.recent_log_limit:])
            if selection.recent_log_limit
            else tuple()
        )
        return SubjectiveQueryResult(
            session=self.world.session if selection.include_session else None,
            encounter=self.world.encounter if selection.include_encounter else None,
            observers=tuple(
                self.world.observers[uuid]
                for uuid in _deduplicate(selection.observer_uuids)
                if uuid in self.world.observers
            ),
            entities=entities,
            objects=objects,
            tiles=tiles,
            actions=actions,
            capabilities=tuple(
                capabilities_by_id[capability_id]
                for capability_id in requested_capability_ids
                if capability_id in capabilities_by_id
            ),
            recent_combat_logs=logs,
            total_matching_actions=total_actions,
            next_action_offset=next_offset,
            missing_entity_uuids=tuple(uuid for uuid in selection.entity_uuids if uuid not in self.world.known_entities),
            missing_observer_uuids=tuple(uuid for uuid in selection.observer_uuids if uuid not in self.world.observers),
            missing_object_uuids=tuple(uuid for uuid in selection.object_uuids if uuid not in self.world.known_objects),
            missing_tile_keys=tuple(key for key in selection.tile_keys if key not in self.world.known_tiles),
            missing_row_ids=missing_rows,
            missing_capability_ids=tuple(
                capability_id
                for capability_id in selection.capability_ids
                if capability_id not in capabilities_by_id
            ),
        )

    def current_epoch(self) -> Optional[DecisionEpoch]:
        """Return the current decision epoch, if any."""
        return self.world.current_epoch

    def action_economy(self) -> Optional[ActionEconomyState]:
        """Return current actor economy, if an epoch exists."""
        return self.world.current_epoch.economy if self.world.current_epoch else None

    def affordances(self) -> Tuple[ActionAffordance, ...]:
        """Return current authoritative rows in deterministic epoch order."""
        if self.world.current_epoch is None:
            return tuple()
        return tuple(self.world.current_epoch.affordances.all_rows)

    def row(self, row_id: str) -> Optional[ActionAffordance]:
        """Return one complete current-epoch row by ID."""
        if self.world.current_epoch is None:
            return None
        return self.world.current_epoch.affordances.row_by_id(row_id)

    def active_actor(self) -> Optional[ObservationEntityFact]:
        """Return the active actor fact, if subjectively known."""
        actor_uuid = self.world.current_epoch.actor_uuid if self.world.current_epoch else None
        return self.world.known_entities.get(actor_uuid) if actor_uuid else None

    def visible_enemies(self) -> Tuple[ObservationEntityFact, ...]:
        """Return visible hostile facts from the typed contact index when available."""
        facts = self.agent_state.facts
        if facts is not None:
            return tuple(
                self.world.known_entities[uuid]
                for uuid in facts.contacts.visible_hostile_uuids
                if uuid in self.world.known_entities
            )
        actor = self.active_actor()
        return tuple(
            entity for entity in self.world.known_entities.values()
            if not entity.controlled
            and entity.knowledge_state is KnowledgeState.VISIBLE
            and entity.is_dead is not True
            and actor is not None
            and actor.faction is not None
            and entity.faction is not None
            and entity.faction != actor.faction
        )

    def remembered_enemies(self) -> Tuple[ObservationEntityFact, ...]:
        """Return remembered hostile facts from the typed contact index when available."""
        facts = self.agent_state.facts
        if facts is not None:
            return tuple(
                self.world.known_entities[uuid]
                for uuid in facts.contacts.remembered_hostile_uuids
                if uuid in self.world.known_entities
            )
        return tuple()

    def known_closed_doors(self) -> Tuple[ObservationObjectFact, ...]:
        """Return closed doors from typed derived object facts."""
        facts = self.agent_state.facts
        if facts is not None:
            return tuple(
                self.world.known_objects[uuid]
                for uuid in facts.objects.closed_door_uuids
                if uuid in self.world.known_objects
            )
        return tuple(
            obj
            for obj in self.world.known_objects.values()
            if obj.state.is_open is False
        )

    def safe_movement_rows(self) -> Tuple[ActionAffordance, ...]:
        """Return movement rows whose disclosed chosen route has no known hazard or reaction exposure."""
        return tuple(
            row for row in self.affordances()
            if row.action_category == "movement"
            and all(
                not target.is_path_hazardous
                and not target.opportunity_attack_exposures
                for target in row.targets
            )
        )

    def latest_brief(self) -> str:
        """Return latest locally derived brief text, if present."""
        return self.agent_state.briefs[-1].text if self.agent_state.briefs else ""

    def _select_actions(
        self,
        selection: SubjectiveQuerySelection,
    ) -> tuple[Tuple[SubjectiveActionDetail, ...], int, Optional[int], Tuple[str, ...]]:
        """Resolve explicit rows and one optional filtered page without duplicating rows."""
        epoch = self.world.current_epoch
        rows = epoch.affordances.all_rows if epoch is not None else tuple()
        selected: list[ActionAffordance] = [
            row
            for row_id in _deduplicate(selection.row_ids)
            if epoch is not None
            for row in [epoch.affordances.row_by_id(row_id)]
            if row is not None
        ]
        total_matching = 0
        next_offset = None
        if selection.action_filter is not None:
            matched = [
                row for row in rows
                if _action_matches(row, epoch, selection.action_filter)
            ]
            total_matching = len(matched)
            start = selection.action_filter.offset
            stop = start + selection.action_filter.limit
            selected.extend(matched[start:stop])
            if stop < total_matching:
                next_offset = stop
        selected = list(_deduplicate_rows(selected))
        details = tuple(
            SubjectiveActionDetail(
                affordance=row,
                semantics=epoch.affordances.semantics_for(row),
            )
            for row in selected
            if epoch is not None
        )
        missing = tuple(
            row_id
            for row_id in selection.row_ids
            if epoch is None or epoch.affordances.row_by_id(row_id) is None
        )
        return details, total_matching, next_offset, missing


def _action_matches(
    row: ActionAffordance,
    epoch: Optional[DecisionEpoch],
    query: SubjectiveActionFilter,
) -> bool:
    """Return whether one row satisfies every requested typed filter."""
    if epoch is None:
        return False
    semantics = epoch.affordances.semantics_for(row)
    return (
        (not query.buckets or row.bucket in query.buckets)
        and (not query.source_action_ids or row.source_action_id in query.source_action_ids)
        and (not query.semantic_keys or row.semantic_key in query.semantic_keys)
        and (not query.template_names or row.template_name in query.template_names)
        and (
            not query.base_template_names
            or row.base_template_name in query.base_template_names
        )
        and (not query.cast_at_levels or row.cast_at_level in query.cast_at_levels)
        and (not query.semantic_ids or row.semantic_id in query.semantic_ids)
        and (not query.tags or all(tag in semantics.tags for tag in query.tags))
        and (not query.action_categories or row.action_category in query.action_categories)
        and (not query.target_types or row.target_type in query.target_types)
        and (query.can_afford is None or row.can_afford is query.can_afford)
        and (
            query.target_uuid is None
            or any(target.target_uuid == query.target_uuid for target in (*row.targets, *row.target_options))
        )
    )


def _deduplicate(values: list[str] | Tuple[str, ...]) -> Tuple[str, ...]:
    """Preserve first occurrence while removing duplicate string identifiers."""
    return tuple(dict.fromkeys(values))


def _deduplicate_rows(rows: list[ActionAffordance]) -> Tuple[ActionAffordance, ...]:
    """Preserve deterministic epoch order while removing duplicate row IDs."""
    return tuple({row.row_id: row for row in rows}.values())
    session: Optional[ObservationSessionState] = Field(default=None, description="Complete subjective session state when requested.")
    encounter: Optional[ObservationEncounterState] = Field(
        default=None,
        description="Complete subjective encounter state when requested and known.",
    )
    observers: Tuple[ObservationObserverState, ...] = Field(
        default_factory=tuple,
        description="Selected controlled observer states.",
    )
