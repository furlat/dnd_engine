"""Independent spatial conditions and reusable area mechanics."""

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Set, Tuple, TypeAlias

from dnd.types.world import LightLevel, MovementMode
from dnd.types.senses import OpticalObscurement
from uuid import UUID, uuid4
from pydantic import Field, PrivateAttr, StrictInt, model_validator

from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.content.identities import ContentRef
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.spatial_effect_definitions import (
    SpatialEffectTransitionDefinition,
)
from dnd.types.effects import EffectOriginKind
from dnd.types.conditions import DurationType, HazardFilter
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventType,
    EventHandler,
    EventQueue,
    Trigger,
)
from dnd.core.events.world_events import (
    SpatialChangeEvent,
    SpatialEffectChangeEvent,
    SpatialEffectInteractionEvent,
    SensesUpdateHint,
)
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.types.spatial_effects import (
    SpatialEffectAnchorKind,
    SpatialEffectBlockingPolicy,
    SpatialEffectChangeOperation,
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
)
from dnd.core.values import ModifiableValue
from dnd.core.aoe import Sphere, Cone, Line, Cube, Cylinder
from dnd.entities.entity import Entity


ReplacementBuilder: TypeAlias = Callable[
    [
        ContentRecipe,
        "SpatialCondition",
        SpatialEffectInteractionEvent,
        Set[Tuple[int, int]],
    ],
    "SpatialCondition",
]
InteractionExecutor: TypeAlias = Callable[
    [
        "SpatialCondition",
        SpatialEffectInteractionEvent,
        Tuple[SpatialEffectTransitionDefinition, ...],
        ReplacementBuilder,
    ],
    None,
]


@dataclass(frozen=True, slots=True)
class SpatialConditionWorkDiagnostics:
    """Immutable count of footprint positions visited by one condition command."""

    operation: str = "none"
    positions_visited: int = 0


class SpatialCondition(BaseCondition):
    """One condition that owns its world footprint and mechanics directly."""

    name: str = Field(default="Spatial Condition")
    content_ref: ContentRef = Field(
        description="Exact authored identity of this spatial condition.",
    )
    faction: Optional[str] = Field(
        default=None,
        description="Rules faction retained from the creating source.",
    )
    position: Tuple[StrictInt, StrictInt] = Field(
        description="Authoritative anchor position of the condition.",
    )
    affected_positions: Set[Tuple[int, int]] = Field(
        default_factory=set,
        description="Exact Tiles currently affected by this condition.",
    )
    layer: SpatialEffectLayer
    occupancy_policy: SpatialEffectOccupancyPolicy
    anchor_kind: SpatialEffectAnchorKind = SpatialEffectAnchorKind.FIXED_POSITION
    anchor_uuid: Optional[UUID] = None
    blocking_policy: SpatialEffectBlockingPolicy = (
        SpatialEffectBlockingPolicy.NONE
    )
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=frozenset,
    )

    def get_position(self) -> Tuple[StrictInt, StrictInt]:
        """Return this condition's strict anchor coordinate."""
        return self.position

    @staticmethod
    def _validate_exact_anchor_position(
        position: Tuple[int, int],
    ) -> None:
        """Require an exact non-coercive anchor coordinate before mutation."""
        if (
            type(position) is not tuple
            or len(position) != 2
            or any(type(component) is not int for component in position)
        ):
            raise ValueError(
                "spatial condition position must be an exact tuple[int, int]"
            )
    first_per_turn_trigger_kinds: frozenset[
        SpatialEffectTriggerKind
    ] = Field(default_factory=frozenset)
    arbitration_potency: int = Field(default=0, ge=0)
    optical_obscurement: Optional[OpticalObscurement] = Field(
        default=None,
        description="Observer-relative optical obstruction contributed in the footprint.",
    )
    blocks_physical_optics: bool = Field(
        default=False,
        description="Whether this condition is an objective physical optical blocker.",
    )

    _activation_positions: Optional[Set[Tuple[int, int]]] = PrivateAttr(
        default=None,
    )
    _displaced_footprints: Dict[
        UUID,
        Tuple[Set[Tuple[int, int]], Set[Tuple[int, int]]],
    ] = PrivateAttr(default_factory=dict)
    _committed_displacement_uuids: Set[UUID] = PrivateAttr(default_factory=set)
    _uncommitted_state_discarded: bool = PrivateAttr(default=False)
    _created_event_published: bool = PrivateAttr(default=False)
    _retiring: bool = PrivateAttr(default=False)
    _reveal_in_progress: bool = PrivateAttr(default=False)
    _anchor_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _interaction_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _pending_physical_optics: Optional[
        Tuple[Dict[Tuple[int, int], bool], Set[Tuple[int, int]]]
    ] = PrivateAttr(default=None)
    _interaction_transitions: Tuple[
        SpatialEffectTransitionDefinition,
        ...,
    ] = PrivateAttr(default_factory=tuple)
    _replacement_builder: Optional[ReplacementBuilder] = PrivateAttr(default=None)
    _interaction_executor: Optional[InteractionExecutor] = PrivateAttr(default=None)
    _last_work_diagnostics: SpatialConditionWorkDiagnostics = PrivateAttr(
        default_factory=SpatialConditionWorkDiagnostics,
    )
    _work_operation: Optional[str] = PrivateAttr(default=None)
    _work_positions_visited: int = PrivateAttr(default=0)

    @property
    def last_work_diagnostics(self) -> SpatialConditionWorkDiagnostics:
        """Return the immutable work count for the most recent condition command."""
        return self._last_work_diagnostics

    def _begin_work_diagnostics(self, operation: str) -> None:
        """Start counting footprint work already performed by this owner."""
        self._work_operation = operation
        self._work_positions_visited = 0

    def _record_work_positions(self, count: int) -> None:
        """Count one owner-local footprint iteration without affecting behavior."""
        if self._work_operation is not None:
            self._work_positions_visited += count

    def _iter_work_positions(
        self,
        positions: Iterable[Tuple[int, int]],
    ) -> Iterator[Tuple[int, int]]:
        """Yield owner-local footprint positions while an operation is active."""
        for position in positions:
            self._record_work_positions(1)
            yield position

    def _finish_work_diagnostics(self) -> None:
        """Freeze the current owner-local work count."""
        self._last_work_diagnostics = SpatialConditionWorkDiagnostics(
            operation=self._work_operation or "none",
            positions_visited=self._work_positions_visited,
        )
        self._work_operation = None

    @model_validator(mode="after")
    def validate_spatial_identity(self) -> "SpatialCondition":
        """Require exactly one anchor UUID for attached conditions."""
        attached = self.anchor_kind in {
            SpatialEffectAnchorKind.ENTITY,
            SpatialEffectAnchorKind.WORLD_OBJECT,
        }
        if attached is (self.anchor_uuid is None):
            raise ValueError(
                "Attached spatial conditions require exactly one anchor UUID",
            )
        if not self.first_per_turn_trigger_kinds.issubset(self.trigger_kinds):
            raise ValueError(
                "first-per-turn triggers must be declared trigger kinds",
            )
        return self

    def resolve_condition_footprint(self) -> Set[Tuple[int, int]]:
        """Return the intended valid footprint for activation."""
        if self.affected_positions:
            return set(self.affected_positions)
        return {self.position}

    def material_arbitration_rank(self) -> Tuple[int, int]:
        """Return the existing potency/spell-level arbitration rank."""
        spell_level = (
            self.effect_origin.effective_spell_level
            if self.effect_origin is not None
            and self.effect_origin.effective_spell_level is not None
            else 0
        )
        return (self.arbitration_potency, spell_level)

    def is_active_spatial_condition(self) -> bool:
        """Verify this condition against the authoritative GridMap collection."""
        return get_map().get_spatial_condition(self.uuid) is self

    def get_optical_obscurement_at(
        self,
        position: Tuple[int, int],
    ) -> Optional[OpticalObscurement]:
        """Return this condition's optical contribution inside its footprint."""
        if position not in self.affected_positions:
            return None
        return self.optical_obscurement

    def blocks_physical_optics_at(
        self,
        position: Tuple[int, int],
    ) -> bool:
        """Return the objective physical optical answer for one covered Tile."""
        return self.blocks_physical_optics and position in self.affected_positions

    def _physical_optics_snapshot(
        self,
        grid,
        positions: Set[Tuple[int, int]],
    ) -> Dict[Tuple[int, int], bool]:
        """Capture each complete objective center-optics answer locally."""
        return {
            position: grid.is_blocking_optics(*position)
            for position in self._iter_work_positions(positions)
        }

    def _settle_physical_optics(
        self,
        grid,
        before: Dict[Tuple[int, int], bool],
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Optional[Event],
    ) -> None:
        """Settle one aggregate optical change after footprint indexes commit."""
        after = self._physical_optics_snapshot(grid, positions)
        changed = {
            position
            for position in self._iter_work_positions(positions)
            if before.get(position, False) != after.get(position, False)
        }
        if not changed:
            return
        grid.invalidate_spatial_caches({"optical"})
        grid.recompute_lights_at_positions(
            changed,
            parent_event=parent_event.uuid if parent_event is not None else None,
        )

    def _settle_pending_physical_optics(self, parent_event: Event) -> None:
        """Settle a committed activation only after application succeeds."""
        pending = self._pending_physical_optics
        self._pending_physical_optics = None
        if pending is None:
            return
        before, positions = pending
        self._settle_physical_optics(
            get_map(),
            before,
            positions,
            parent_event=parent_event,
        )

    def blocks_walking_at(
        self,
        position: Tuple[int, int],
        requesting_entity_uuid: Optional[UUID] = None,
        mode: MovementMode = MovementMode.WALKING,
    ) -> bool:
        """Apply the authored blocking policy at one covered position."""
        del requesting_entity_uuid, mode
        if self.blocking_policy is SpatialEffectBlockingPolicy.NONE:
            return False
        if self.blocking_policy is SpatialEffectBlockingPolicy.ANCHOR:
            return position == self.position
        return position in self.affected_positions

    def is_hazard_perceived_by(
        self,
        requesting_entity_uuid: Optional[UUID] = None,
    ) -> bool:
        """Resolve concealment through the existing observer capability."""
        if requesting_entity_uuid is None or self.condition_stealth_dc is None:
            return True
        observer = BaseBlock.get(requesting_entity_uuid)
        return (
            observer is None
            or self.condition_stealth_dc < observer.get_passive_perception()
        )

    def is_hazardous_for(self, entity_uuid: Optional[UUID] = None) -> bool:
        """Resolve the inherited hazard filter for one observer."""
        if self.hazard_filter is None:
            return False
        if not self.is_hazard_perceived_by(entity_uuid):
            return False
        if self.hazard_filter is HazardFilter.ALL:
            return True
        if self.hazard_filter is HazardFilter.NON_SOURCE:
            return entity_uuid != self.source_entity_uuid
        if self.hazard_filter is HazardFilter.ENEMIES and entity_uuid is not None:
            observer = BaseBlock.get(entity_uuid)
            return (
                observer is not None
                and observer.is_enemy_of(self.source_entity_uuid)
            )
        return False

    def add_linked_condition(
        self,
        target_block_uuid: UUID,
        condition_uuid: UUID,
    ) -> None:
        """Track a child and point its reverse link at this condition owner."""
        self.linked_conditions.append((target_block_uuid, condition_uuid))
        child = BaseCondition.get(condition_uuid)
        if isinstance(child, BaseCondition):
            child.parent_link = (self.uuid, self.uuid)

    def _resolve_activation_admission(
        self,
        positions: Set[Tuple[int, int]],
        replacing_condition_uuid: Optional[UUID],
    ) -> Set[Tuple[int, int]]:
        """Resolve same-identity arbitration before mechanics are installed."""
        grid = get_map()
        for position in self._iter_work_positions(positions):
            if not grid.has_tile(*position):
                raise ValueError(
                    "Spatial condition positions must identify existing tiles",
                )
        if self.occupancy_policy is SpatialEffectOccupancyPolicy.OVERLAPPING:
            return positions

        admitted = set(positions)
        displaced_cells: Dict[UUID, Set[Tuple[int, int]]] = {}
        if replacing_condition_uuid is not None:
            authorized = BaseCondition.get(replacing_condition_uuid)
            if not isinstance(authorized, SpatialCondition):
                raise ValueError("Authorized replacement condition is unavailable")
            replaced_positions = positions & authorized.affected_positions
            if not replaced_positions:
                raise ValueError(
                    "Authorized replacement does not cover the intended cells",
                )
            displaced_cells[authorized.uuid] = set(replaced_positions)
        incoming_rank = self.material_arbitration_rank()
        for position in self._iter_work_positions(sorted(positions)):
            for incumbent in grid.get_spatial_conditions_at(
                position,
                layer=self.layer,
            ):
                if not isinstance(incumbent, SpatialCondition):
                    raise RuntimeError(
                        "Spatial-condition index contains an invalid owner",
                    )
                if incumbent.uuid == self.uuid:
                    continue
                if (
                    replacing_condition_uuid is not None
                    and incumbent.uuid == replacing_condition_uuid
                ):
                    continue
                if incumbent.content_ref != self.content_ref:
                    raise ValueError(
                        f"{self.layer.value} cell {position} requires an "
                        "authored material transformation",
                    )
                if incumbent.material_arbitration_rank() > incoming_rank:
                    admitted.discard(position)
                    continue
                displaced_cells.setdefault(incumbent.uuid, set()).add(position)

        self._displaced_footprints.clear()
        for incumbent_uuid, removed in displaced_cells.items():
            incumbent = BaseCondition.get(incumbent_uuid)
            if not isinstance(incumbent, SpatialCondition):
                raise RuntimeError("Admitted incumbent disappeared")
            original = set(incumbent.affected_positions)
            self._displaced_footprints[incumbent_uuid] = (
                original,
                original - removed,
            )
        if len(self._displaced_footprints) > 1:
            raise ValueError(
                "One spatial activation cannot replace several independent "
                "condition owners",
            )
        return admitted

    def _release_positions(
        self,
        positions: Set[Tuple[int, int]],
    ) -> None:
        """Release condition-specific mechanics from removed positions."""
        del positions

    def _restore_positions(
        self,
        positions: Set[Tuple[int, int]],
    ) -> None:
        """Restore condition-specific mechanics on recovered positions."""
        del positions

    def _publish_pending_runtime_facts(
        self,
        parent_event: Optional[Event],
    ) -> None:
        """Publish contributor facts after the complete spatial commit."""
        del parent_event

    def _discard_pending_runtime_facts(self) -> None:
        """Discard provisional contributor facts during failed restoration."""
        return

    def _discard_pending_terrain_positions(
        self,
        positions: Set[Tuple[int, int]],
    ) -> None:
        """Discard terrain rows transferred to an incoming condition."""
        del positions

    def _release_positions_for_replacement(
        self,
        positions: Set[Tuple[int, int]],
    ) -> None:
        """Release reversible positional mechanics during a footprint swap."""
        self._release_positions(positions)

    def _finalize_replaced_positions(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Finalize eventful state only after the replacement is admitted."""
        del positions, parent_event

    def _commit_activation_footprint(self, *, parent_event: Event) -> None:
        """Commit the preflighted footprint and incumbent deltas."""
        if self._activation_positions is None:
            raise RuntimeError("Spatial condition has no prepared footprint")
        grid = get_map()
        physical_positions = set(self._activation_positions) | set(self.affected_positions)
        for original, _remaining in self._displaced_footprints.values():
            physical_positions.update(original)
        physical_before = self._physical_optics_snapshot(grid, physical_positions)
        self._committed_displacement_uuids.clear()
        for incumbent_uuid in sorted(self._displaced_footprints, key=str):
            incumbent = BaseCondition.get(incumbent_uuid)
            if not isinstance(incumbent, SpatialCondition):
                raise RuntimeError("Admitted incumbent disappeared")
            original, remaining = self._displaced_footprints[incumbent_uuid]
            removed = original - remaining
            self._committed_displacement_uuids.add(incumbent_uuid)
            incumbent._release_positions_for_replacement(removed)
            incumbent._discard_pending_terrain_positions(removed)
            incumbent.affected_positions = set(remaining)
            if remaining:
                grid.set_spatial_condition_positions(
                    condition=incumbent,
                    layer=incumbent.layer,
                    occupancy_policy=incumbent.occupancy_policy,
                    positions=remaining,
                )
            else:
                grid.remove_spatial_condition(incumbent.uuid)

        grid.set_spatial_condition_positions(
            condition=self,
            layer=self.layer,
            occupancy_policy=self.occupancy_policy,
            positions=self._activation_positions,
        )
        self.affected_positions = set(self._activation_positions)
        self._install_interaction_handler()
        self._install_anchor_handler()
        self._pending_physical_optics = (
            physical_before,
            physical_positions,
        )

        del parent_event

    def _finalize_application(self, effect_event: Event) -> None:
        """Settle displaced owners before application completion is published."""
        for incumbent_uuid in sorted(self._displaced_footprints, key=str):
            incumbent = BaseCondition.get(incumbent_uuid)
            if not isinstance(incumbent, SpatialCondition):
                raise RuntimeError("Displaced spatial condition disappeared")
            original, remaining = self._displaced_footprints[incumbent_uuid]
            removed = original - remaining
            if remaining:
                incumbent._finalize_replaced_positions(
                    removed,
                    parent_event=effect_event,
                )
                continue
            if not incumbent.deactivate(
                parent_event=effect_event,
                operation=SpatialEffectChangeOperation.TRANSFORMED,
                previous_positions=original,
            ):
                raise RuntimeError(
                    "Displaced spatial condition rejected retirement",
                )
            self._committed_displacement_uuids.discard(incumbent_uuid)
        self._settle_pending_physical_optics(effect_event)

    def _restore_displaced_footprints(self) -> None:
        """Restore incumbents after a rejected incoming application."""
        grid = get_map()
        restored: List[SpatialCondition] = []
        for incumbent_uuid in sorted(
            self._committed_displacement_uuids,
            key=str,
        ):
            incumbent = BaseCondition.get(incumbent_uuid)
            if not isinstance(incumbent, SpatialCondition):
                continue
            original, remaining = self._displaced_footprints[incumbent_uuid]
            incumbent.affected_positions = set(original)
            grid.set_spatial_condition_positions(
                condition=incumbent,
                layer=incumbent.layer,
                occupancy_policy=incumbent.occupancy_policy,
                positions=original,
            )
            incumbent._restore_positions(original - remaining)
            restored.append(incumbent)
        self._displaced_footprints.clear()
        self._committed_displacement_uuids.clear()
        for incumbent in restored:
            incumbent._discard_pending_runtime_facts()
            incumbent._publish_pending_runtime_facts(None)

    def _apply(
        self,
        declaration_event: Event,
    ) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event],
    ]:
        """Commit a footprint for a condition with no shared area mechanics."""
        self._commit_activation_footprint(parent_event=declaration_event)
        return (
            [],
            [],
            [],
            [],
            declaration_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
            ),
        )

    def activate(
        self,
        *,
        parent_event: Event,
        replacing_condition_uuid: Optional[UUID] = None,
    ) -> Optional[Event]:
        """Activate this condition through the ordinary condition lifecycle."""
        self._begin_work_diagnostics("activate")
        grid = get_map()
        if self.applied or grid.has_spatial_condition(self.uuid):
            raise ValueError("Spatial condition is already active")
        self._uncommitted_state_discarded = False
        self._committed_displacement_uuids.clear()
        try:
            intended = self.resolve_condition_footprint()
            admitted = self._resolve_activation_admission(
                intended,
                replacing_condition_uuid,
            )
        except BaseException:
            self.discard_from_runtime_owner()
            raise
        if not admitted:
            self.discard_from_runtime_owner()
            return parent_event
        self._activation_positions = admitted
        try:
            result = self.apply(parent_event=parent_event)
        except BaseException:
            self.discard_from_runtime_owner()
            raise
        if result is None or result.canceled or not self.applied:
            self.discard_from_runtime_owner()
            return result

        for incumbent_uuid in sorted(self._displaced_footprints, key=str):
            incumbent = BaseCondition.get(incumbent_uuid)
            if not isinstance(incumbent, SpatialCondition):
                continue
            original, remaining = self._displaced_footprints[incumbent_uuid]
            if remaining:
                incumbent._publish_change(
                    SpatialEffectChangeOperation.TRANSFORMED,
                    previous_positions=original,
                    parent_event=parent_event,
                )
        self._displaced_footprints.clear()
        self._committed_displacement_uuids.clear()
        created = self._publish_change(
            SpatialEffectChangeOperation.CREATED,
            previous_positions=set(),
            parent_event=parent_event,
        )
        self._created_event_published = True
        self.apply_appearance_trigger(parent_event=created or parent_event)
        self._activation_positions = None
        self._finish_work_diagnostics()
        return result

    def discard_uncommitted_runtime_state(self) -> None:
        """Discard provisional mechanics and restore displaced incumbents."""
        if self._uncommitted_state_discarded:
            return
        self._uncommitted_state_discarded = True
        self._pending_physical_optics = None
        get_map().remove_spatial_condition(self.uuid)
        super().discard_uncommitted_runtime_state()
        self.affected_positions.clear()
        self._restore_displaced_footprints()
        self._publish_pending_runtime_facts(None)
        if self._work_operation is not None:
            self._finish_work_diagnostics()

    def discard_from_runtime_owner(self) -> bool:
        """Discard this uncommitted independently owned condition tree."""
        self.discard_uncommitted_runtime_state()
        self._discard_child_tree()
        self._release_condition_owned_actions(self)
        self.remove_from_register()
        return True

    @staticmethod
    def _release_condition_owned_actions(condition: BaseCondition) -> None:
        """Remove exact action templates granted by an independent condition."""
        action_uuids = condition.release_granted_actions()
        if not action_uuids:
            return
        owner = (
            Entity.get(condition.target_entity_uuid)
            if condition.target_entity_uuid is not None
            else None
        )
        if not isinstance(owner, Entity):
            raise RuntimeError(
                "Independent condition granted actions without an Entity owner",
            )
        for action_uuid in action_uuids:
            owner.unregister_action_by_uuid(action_uuid)

    def _discard_same_owner_child(self, child: BaseCondition) -> None:
        """Discard one provisional child owned directly by this condition."""
        if child.discard_from_runtime_owner():
            return
        for grandchild_uuid in list(child.sub_conditions):
            grandchild = BaseCondition.get(grandchild_uuid)
            if isinstance(grandchild, BaseCondition):
                self._discard_same_owner_child(grandchild)
        for owner_uuid, linked_uuid in list(child.linked_conditions):
            linked = BaseCondition.get(linked_uuid)
            owner = BaseBlock.get(owner_uuid)
            if owner is not None and isinstance(linked, BaseCondition):
                owner._discard_condition_indexes(linked)
                owner._discard_uncommitted_condition_tree(linked)
            elif isinstance(linked, BaseCondition):
                linked.discard_from_runtime_owner()
        child.discard_uncommitted_runtime_state()
        self._release_condition_owned_actions(child)
        child.remove_from_register()

    def _remove_same_owner_child(
        self,
        child: BaseCondition,
        *,
        parent_event: Optional[Event],
    ) -> None:
        """Remove one committed child owned directly by this condition."""
        if child.remove_from_runtime_owner(parent_event=parent_event):
            return
        if not child.cleanup_own_state(parent_event=parent_event):
            raise RuntimeError(
                f"Independent child cleanup failed for {child.uuid}",
            )
        for grandchild_uuid in list(child.sub_conditions):
            grandchild = BaseCondition.get(grandchild_uuid)
            if isinstance(grandchild, BaseCondition):
                self._remove_same_owner_child(
                    grandchild,
                    parent_event=parent_event,
                )
        for owner_uuid, linked_uuid in list(child.linked_conditions):
            linked = BaseCondition.get(linked_uuid)
            owner = BaseBlock.get(owner_uuid)
            if owner is not None:
                owner.remove_condition_by_uuid(
                    linked_uuid,
                    parent_event=parent_event,
                )
            elif isinstance(linked, BaseCondition):
                linked.remove_from_runtime_owner(parent_event=parent_event)
        self._release_condition_owned_actions(child)
        child.remove_from_register()

    def _discard_child_tree(self) -> None:
        """Discard same-owner and linked children without publishing removal."""
        for child_uuid in list(self.sub_conditions):
            child = BaseCondition.get(child_uuid)
            if not isinstance(child, BaseCondition):
                continue
            self._discard_same_owner_child(child)
        self.sub_conditions.clear()
        for _owner_uuid, child_uuid in list(self.linked_conditions):
            child = BaseCondition.get(child_uuid)
            if not isinstance(child, BaseCondition):
                continue
            owner = BaseBlock.get(_owner_uuid)
            if owner is not None:
                owner._discard_condition_indexes(child)
                owner._discard_uncommitted_condition_tree(child)
            else:
                child.discard_from_runtime_owner()
        self.linked_conditions.clear()

    def remove_from_runtime_owner(
        self,
        *,
        expire: bool = False,
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Remove this independently owned condition from the world."""
        return self.deactivate(expire=expire, parent_event=parent_event)

    def deactivate(
        self,
        *,
        expire: bool = False,
        parent_event: Optional[Event] = None,
        operation: SpatialEffectChangeOperation = (
            SpatialEffectChangeOperation.REMOVED
        ),
        previous_positions: Optional[Set[Tuple[int, int]]] = None,
    ) -> bool:
        """Remove mechanics, children, Tile indexes, facts, and identity."""
        self._begin_work_diagnostics("deactivate")
        if self._retiring:
            self._finish_work_diagnostics()
            return False
        self._retiring = True
        previous = (
            set(self.affected_positions)
            if previous_positions is None
            else set(previous_positions)
        )
        physical_before = self._physical_optics_snapshot(get_map(), previous)
        try:
            if self.applied and not self.cleanup_own_state(
                expire=expire,
                parent_event=parent_event,
            ):
                return False
            self._publish_pending_runtime_facts(parent_event)
            for child_uuid in list(self.sub_conditions):
                child = BaseCondition.get(child_uuid)
                if isinstance(child, BaseCondition):
                    self._remove_same_owner_child(
                        child,
                        parent_event=parent_event,
                    )
            self.sub_conditions.clear()
            for owner_uuid, child_uuid in list(self.linked_conditions):
                child = BaseCondition.get(child_uuid)
                owner = BaseBlock.get(owner_uuid)
                if owner is not None:
                    owner.remove_condition_by_uuid(
                        child_uuid,
                        parent_event=parent_event,
                    )
                elif isinstance(child, BaseCondition):
                    child.remove_from_runtime_owner(parent_event=parent_event)
            self.linked_conditions.clear()
            self._notify_independent_parent(parent_event=parent_event)
            self._release_condition_owned_actions(self)
            get_map().remove_spatial_condition(self.uuid)
            self.affected_positions.clear()
            self._settle_physical_optics(
                get_map(),
                physical_before,
                previous,
                parent_event=parent_event,
            )
            if self._created_event_published:
                self._publish_change(
                    operation,
                    previous_positions=previous,
                    parent_event=parent_event,
                )
                self._created_event_published = False
            self.remove_from_register()
            self._finish_work_diagnostics()
            return True
        finally:
            self._retiring = False
            if self._work_operation is not None:
                self._finish_work_diagnostics()

    def progress_spatial_duration(
        self,
        *,
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Advance inherited duration once and deactivate on expiry."""
        if not self.progress():
            return False
        return self.deactivate(expire=True, parent_event=parent_event)

    def schedule_retirement(self, rounds: int) -> None:
        """Shorten this condition's inherited round duration when earlier."""
        if rounds < 1:
            raise ValueError("Spatial-condition retirement delay must be positive")
        current = self.duration.duration
        if (
            self.duration.duration_type is DurationType.ROUNDS
            and isinstance(current, int)
            and current <= rounds
        ):
            return
        self.duration.duration_type = DurationType.ROUNDS
        self.duration.duration = rounds

    def _notify_independent_parent(
        self,
        *,
        parent_event: Optional[Event],
    ) -> None:
        """Apply the existing reverse child-removal policy to this owner."""
        if self.parent_link is None:
            return
        parent_owner_uuid, parent_condition_uuid = self.parent_link
        parent = BaseCondition.get(parent_condition_uuid)
        self.parent_link = None
        if not isinstance(parent, BaseCondition):
            return
        parent.unlink_runtime_child(self.uuid)
        if not parent.applied:
            return
        policy = parent.child_removal_policy
        if policy == "none":
            return
        remaining = sum(
            1
            for _, child_uuid in parent.linked_conditions
            if child_uuid != self.uuid
            and isinstance(
                child := BaseCondition.get(child_uuid),
                BaseCondition,
            )
            and child.applied
        )
        if policy != "any" and not (policy == "last" and remaining == 0):
            return
        parent_owner = BaseBlock.get(parent_owner_uuid)
        if parent_owner is not None and parent.name is not None:
            parent_owner.remove_condition(
                parent.name,
                parent_event=parent_event,
            )
        else:
            parent.remove_from_runtime_owner(parent_event=parent_event)

    def bind_interactions(
        self,
        transitions: Tuple[SpatialEffectTransitionDefinition, ...],
        replacement_builder: ReplacementBuilder,
        interaction_executor: InteractionExecutor,
    ) -> None:
        """Bind the frozen authored transition rows to this condition."""
        if self.applied or self._interaction_handler_uuid is not None:
            raise ValueError("Interactions must be bound before activation")
        self._interaction_transitions = tuple(transitions)
        self._replacement_builder = replacement_builder
        self._interaction_executor = interaction_executor

    def _install_interaction_handler(self) -> None:
        """Install one direct interaction handler over this footprint."""
        if not self._interaction_transitions:
            return
        if self._interaction_handler_uuid is not None:
            raise ValueError("Spatial condition already owns an interaction handler")
        condition_uuid = self.uuid
        transitions = self._interaction_transitions
        replacement_builder = self._replacement_builder
        interaction_executor = self._interaction_executor
        if replacement_builder is None or interaction_executor is None:
            raise RuntimeError("Transition rows have no direct executor")

        def processor(event: Event, _source_uuid: UUID) -> Optional[Event]:
            condition = BaseCondition.get(condition_uuid)
            if not isinstance(condition, SpatialCondition):
                return None
            if not isinstance(event, SpatialEffectInteractionEvent):
                return None
            interaction_executor(
                condition,
                event,
                transitions,
                replacement_builder,
            )
            return None

        handler = EventHandler(
            name="Spatial Condition Interaction",
            source_entity_uuid=self.source_entity_uuid,
            event_processor=processor,
        )
        EventQueue.add_spatial_handler(
            handler,
            set(self.affected_positions),
            EventType.SPATIAL_EFFECT_INTERACTION,
            EventPhase.EFFECT,
        )
        self.spatial_handler_uuids.append(handler.uuid)
        self._interaction_handler_uuid = handler.uuid

    def _sync_spatial_handler_positions(self) -> None:
        """Synchronize direct interaction dispatch with this footprint."""
        if self._interaction_handler_uuid is not None:
            EventQueue.update_spatial_handler_positions(
                self._interaction_handler_uuid,
                set(self.affected_positions),
                EventType.SPATIAL_EFFECT_INTERACTION,
                EventPhase.EFFECT,
            )

    def transition_footprint(
        self,
        remaining_positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Shrink this condition and publish the existing transformed fact."""
        if not remaining_positions:
            self.transition_anchor_to_absence(parent_event=parent_event)
            return
        if not remaining_positions.issubset(self.affected_positions):
            raise ValueError("A footprint transition cannot add positions")
        previous = set(self.affected_positions)
        removed = previous - remaining_positions
        physical_positions = previous | set(remaining_positions)
        physical_before = self._physical_optics_snapshot(get_map(), physical_positions)
        self._release_positions(removed)
        self.affected_positions = set(remaining_positions)
        get_map().set_spatial_condition_positions(
            condition=self,
            layer=self.layer,
            occupancy_policy=self.occupancy_policy,
            positions=self.affected_positions,
        )
        self._sync_spatial_handler_positions()
        self._settle_physical_optics(
            get_map(),
            physical_before,
            physical_positions,
            parent_event=parent_event,
        )
        self._publish_pending_runtime_facts(parent_event)
        self._publish_change(
            SpatialEffectChangeOperation.TRANSFORMED,
            previous_positions=previous,
            parent_event=parent_event,
        )

    def _build_change_declaration(
        self,
        operation: SpatialEffectChangeOperation,
        *,
        previous_positions: Set[Tuple[int, int]],
        parent_event: Optional[Event],
    ) -> SpatialEffectChangeEvent:
        """Build one existing spatial lifecycle event for this condition."""
        return SpatialEffectChangeEvent(
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=self.source_entity_name,
            phase=EventPhase.COMPLETION,
            use_register=False,
            parent_event=parent_event.uuid if parent_event is not None else None,
            operation=operation,
            spatial_effect_uuid=self.uuid,
            spatial_effect_content_ref=self.content_ref,
            spatial_effect_name=self.name,
            layer=self.layer,
            anchor_position=self.position,
            affected_positions=tuple(sorted(self.affected_positions)),
            previous_positions=tuple(sorted(previous_positions)),
        )

    def _publish_change(
        self,
        operation: SpatialEffectChangeOperation,
        *,
        previous_positions: Set[Tuple[int, int]],
        parent_event: Optional[Event],
    ) -> Optional[SpatialEffectChangeEvent]:
        """Publish one non-cancelable fact after committed state changes."""
        return EventQueue.publish_completed_fact(
            self._build_change_declaration(
                operation,
                previous_positions=previous_positions,
                parent_event=parent_event,
            )
        )

    def publish_revealed(
        self,
        *,
        parent_event: Event,
    ) -> Optional[SpatialEffectChangeEvent]:
        """Publish the one-way transition from concealed to revealed."""
        if not self._created_event_published:
            raise RuntimeError("Cannot reveal an inactive spatial condition")
        if self.condition_stealth_dc is None or self._reveal_in_progress:
            return None
        self._reveal_in_progress = True
        try:
            declaration = self._build_change_declaration(
                SpatialEffectChangeOperation.REVEALED,
                previous_positions=set(self.affected_positions),
                parent_event=parent_event,
            ).model_copy(update={"phase": EventPhase.DECLARATION})
            current = EventQueue.publish_declaration(declaration)
            if current.canceled:
                return None
            current = current.phase_to(EventPhase.EXECUTION)
            if current.canceled:
                return None
            current = current.phase_to(EventPhase.EFFECT)
            if current.canceled:
                return None
            self.condition_stealth_dc = None
            return current.phase_to(EventPhase.COMPLETION)
        finally:
            self._reveal_in_progress = False

    def apply_appearance_trigger(self, *, parent_event: Event) -> None:
        """Apply condition-specific APPEAR consequences when authored."""
        del parent_event

    def apply_effect_entry_trigger(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Apply condition-specific consequences for newly covered occupants."""
        del positions, parent_event

    def apply_effect_exit_trigger(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Apply condition-specific consequences for departed occupants."""
        del positions, parent_event

    def _install_anchor_handler(self) -> None:
        """Follow an attached entity or world object through existing events."""
        if self.anchor_uuid is None:
            return
        if self._anchor_handler_uuid is not None:
            raise ValueError("Spatial condition already owns an anchor handler")
        condition_uuid = self.uuid
        anchor_uuid = self.anchor_uuid
        anchor_kind = self.anchor_kind
        event_types = (
            (
                EventType.SPATIAL_ENTITY_ENTERED,
                EventType.SPATIAL_ENTITY_LEFT,
            )
            if anchor_kind is SpatialEffectAnchorKind.ENTITY
            else (
                EventType.SPATIAL_OBJECT_PLACED,
                EventType.SPATIAL_OBJECT_CHANGED,
                EventType.SPATIAL_OBJECT_REMOVED,
            )
        )

        def processor(event: Event, _source_uuid: UUID) -> Optional[Event]:
            condition = BaseCondition.get(condition_uuid)
            if not isinstance(condition, SpatialCondition):
                return None
            if not isinstance(event, SpatialChangeEvent):
                return None
            matched = (
                event.entity_uuid == anchor_uuid
                if anchor_kind is SpatialEffectAnchorKind.ENTITY
                else event.object_uuid == anchor_uuid
            )
            if not matched:
                return None
            if anchor_kind is SpatialEffectAnchorKind.ENTITY:
                if event.event_type is EventType.SPATIAL_ENTITY_ENTERED:
                    condition.relocate_anchor(event.position, parent_event=event)
                elif event.old_position is None:
                    condition.transition_anchor_to_absence(parent_event=event)
                return None
            if event.event_type is EventType.SPATIAL_OBJECT_REMOVED:
                previous = event.previous_placement
                is_relocation_departure = (
                    previous is not None
                    and event.placement is None
                    and event.old_position is not None
                    and event.old_position != previous.position
                )
                if is_relocation_departure:
                    return None
                condition.deactivate(parent_event=event)
            else:
                placement = event.placement
                previous = event.previous_placement
                if placement is None:
                    return None
                if previous is not None and previous.position == placement.position:
                    return None
                condition.relocate_anchor(placement.position, parent_event=event)
            return None

        handler = EventHandler(
            name="Spatial Condition Anchor Movement",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[
                Trigger(event_type=event_type, event_phase=EventPhase.EFFECT)
                for event_type in event_types
            ],
            event_processor=processor,
        )
        EventQueue.add_event_handler(handler)
        self.event_handlers_uuids.append(handler.uuid)
        self._anchor_handler_uuid = handler.uuid

    def relocate_anchor(
        self,
        position: Tuple[int, int],
        *,
        parent_event: Event,
    ) -> None:
        """Relocate a generic attached footprint through public state."""
        self._validate_exact_anchor_position(position)
        grid = get_map()
        previous = set(self.affected_positions)
        old_position = self.position
        if previous:
            delta = (position[0] - old_position[0], position[1] - old_position[1])
            admitted = {
                (x + delta[0], y + delta[1])
                for x, y in previous
            }
        else:
            admitted = {position}
        grid.validate_spatial_condition_positions(
            condition=self,
            layer=self.layer,
            occupancy_policy=self.occupancy_policy,
            positions=admitted,
        )
        physical_positions = previous | admitted
        physical_before = self._physical_optics_snapshot(
            grid,
            physical_positions,
        )
        self._release_positions(previous - admitted)
        grid.set_spatial_condition_positions(
            condition=self,
            layer=self.layer,
            occupancy_policy=self.occupancy_policy,
            positions=admitted,
        )
        self.position = position
        self.affected_positions = set(admitted)
        self._sync_spatial_handler_positions()
        self._settle_physical_optics(
            grid,
            physical_before,
            physical_positions,
            parent_event=parent_event,
        )
        self._publish_pending_runtime_facts(parent_event)
        self._publish_change(
            SpatialEffectChangeOperation.FOOTPRINT_CHANGED,
            previous_positions=previous,
            parent_event=parent_event,
        )

    def transition_anchor_to_absence(self, *, parent_event: Event) -> None:
        """Transition an attached condition to empty without deactivation."""
        previous = set(self.affected_positions)
        if not previous:
            return
        grid = get_map()
        physical_before = self._physical_optics_snapshot(grid, previous)
        self._release_positions(previous)
        self.affected_positions = set()
        grid.set_spatial_condition_positions(
            condition=self,
            layer=self.layer,
            occupancy_policy=self.occupancy_policy,
            positions=set(),
        )
        self._sync_spatial_handler_positions()
        self._settle_physical_optics(
            grid,
            physical_before,
            previous,
            parent_event=parent_event,
        )
        self._publish_pending_runtime_facts(parent_event)
        self.apply_effect_exit_trigger(previous, parent_event=parent_event)
        self._publish_change(
            SpatialEffectChangeOperation.FOOTPRINT_CHANGED,
            previous_positions=previous,
            parent_event=parent_event,
        )


class AreaCondition(SpatialCondition):
    """Shared geometric mechanics for one independently owned condition.

    Position-indexed handlers provide O(1) entry/exit lookup instead of
    one handler per Tile.

    Key architecture:
    - ONE handler per effect type per zone (not per tile)
    - Handlers are registered via EventQueue.add_spatial_handler() with position set
    - Zone movement uses EventQueue.update_spatial_handler_positions() for O(delta) updates
    - Terrain modifiers (difficult terrain) are separate from event handlers

    Area subclasses should:
    1. Override _has_entry_effect() and _create_zone_entry_handler() for entry effects
    2. Override _has_exit_effect() and _create_zone_exit_handler() for exit effects
    3. Override _compute_affected_positions() if using custom geometry
    """
    name: str = Field(default="Zone Control", description="Zone condition name.")
    description: str = Field(default="Controls a zone of tile effects", description="Zone condition description.")

    zone_shape: str = Field(default="sphere", description="Shape: 'sphere', 'cone', 'line', 'cube', or 'cylinder'")
    zone_radius_feet: int = Field(default=20, description="Radius/size in feet")
    zone_width_feet: int = Field(default=5, description="Line width in feet for line-shaped zones")
    zone_direction: Optional[Tuple[int, int]] = Field(default=None, description="Direction for cones/lines")

    adds_difficult_terrain: bool = Field(default=False, description="If True, adds +1 to walking cost")

    sets_light_level: Optional[LightLevel] = Field(default=None, description="Light level to apply to zone tiles")
    light_is_cap: bool = Field(
        default=False,
        description="Whether the source caps rather than adds objective illumination.",
    )

    _entry_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _exit_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _turn_start_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _turn_end_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _terrain_modifier_uuids: Dict[UUID, List[UUID]] = PrivateAttr(default_factory=dict)
    _pending_terrain_before_values: Dict[
        Tuple[int, int],
        Tuple[int, int, int, int],
    ] = PrivateAttr(default_factory=dict)
    _light_modifier_positions: Set[Tuple[int, int]] = PrivateAttr(default_factory=set)
    _pending_light_changed_positions: Set[Tuple[int, int]] = PrivateAttr(
        default_factory=set,
    )
    _last_trigger_turn_by_target: Dict[UUID, UUID] = PrivateAttr(
        default_factory=dict,
    )

    model_config = {"arbitrary_types_allowed": True}

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create the zone-level entry handler for all affected positions."""
        raise NotImplementedError("Subclass must implement _create_zone_entry_handler")

    def _create_zone_exit_handler(self) -> EventHandler:
        """Create the zone-level exit handler for all affected positions."""
        raise NotImplementedError("Subclass must implement _create_zone_exit_handler")

    def _create_zone_turn_start_handler(self) -> EventHandler:
        """Create a normal event handler for turn starts inside the zone."""
        raise NotImplementedError("Subclass must implement _create_zone_turn_start_handler")

    def _create_zone_turn_end_handler(self) -> EventHandler:
        """Create a normal event handler for turn ends inside the zone."""
        raise NotImplementedError("Subclass must implement _create_zone_turn_end_handler")

    def _apply_appearance_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        """Apply this condition's explicitly authored APPEAR consequence."""
        del entity, parent_event
        raise NotImplementedError(
            f"{type(self).__name__} declares APPEAR without an implementation",
        )

    def _apply_effect_entry_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        """Apply a rule triggered by the effect moving onto one occupant."""
        del entity, parent_event
        raise NotImplementedError(
            f"{type(self).__name__} declares EFFECT_ENTERS_OCCUPANT "
            "without an implementation",
        )

    def _apply_effect_exit_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        """Apply a rule triggered by an effect moving away from an occupant."""
        del entity, parent_event
        raise NotImplementedError(
            f"{type(self).__name__} declares EFFECT_LEAVES_OCCUPANT "
            "without an implementation",
        )

    def _admit_trigger(
        self,
        trigger_kind: SpatialEffectTriggerKind,
        target_entity_uuid: UUID,
        event: Event,
    ) -> bool:
        """Admit a trigger, enforcing exact first-per-turn semantics."""
        if trigger_kind not in self.first_per_turn_trigger_kinds:
            return True
        turn_execution_id = event.turn_execution_id
        if turn_execution_id is None:
            return True
        if (
            self._last_trigger_turn_by_target.get(target_entity_uuid)
            == turn_execution_id
        ):
            return False
        self._last_trigger_turn_by_target[target_entity_uuid] = turn_execution_id
        return True

    def _wrap_processor_with_trigger_admission(
        self,
        original_processor: Callable[[Event, UUID], Optional[Event]],
        trigger_kind: SpatialEffectTriggerKind,
    ) -> Callable[[Event, UUID], Optional[Event]]:
        """Apply one effect/target/turn admission fence around a processor."""
        def wrapped(event: Event, source_uuid: UUID) -> Optional[Event]:
            target_uuid = (
                event.entity_uuid
                if isinstance(event, SpatialChangeEvent)
                else event.source_entity_uuid
            )
            if target_uuid is None:
                return None
            if not self._admit_trigger(trigger_kind, target_uuid, event):
                return None
            return original_processor(event, source_uuid)

        return wrapped

    def apply_appearance_trigger(self, *, parent_event: Event) -> None:
        """Apply APPEAR only when the authored condition declares it."""
        if SpatialEffectTriggerKind.APPEAR not in self.trigger_kinds:
            return
        grid = get_map()
        occupant_uuids: Set[UUID] = set()
        for position in self._iter_work_positions(self.affected_positions):
            occupant_uuids.update(grid.get_entities_at(position))
        spell_level = self._protection_spell_level()
        source = Entity.get(self.source_entity_uuid)
        source_position = source.position if source is not None else (0, 0)
        for entity_uuid in sorted(occupant_uuids, key=str):
            entity = Entity.get(entity_uuid)
            if entity is None:
                continue
            if (
                spell_level is not None
                and self.magical_origin
                and SpellProtectionRegistry.is_protected(
                    entity.position,
                    source_position,
                    spell_level,
                )
            ):
                continue
            if not self._admit_trigger(
                SpatialEffectTriggerKind.APPEAR,
                entity.uuid,
                parent_event,
            ):
                continue
            self._apply_appearance_effect(entity, parent_event=parent_event)

    def apply_effect_entry_trigger(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Apply an explicitly authored moving-area consequence."""
        trigger_kind = SpatialEffectTriggerKind.EFFECT_ENTERS_OCCUPANT
        if trigger_kind not in self.trigger_kinds:
            return
        grid = get_map()
        occupant_uuids: Set[UUID] = set()
        for position in self._iter_work_positions(positions):
            occupant_uuids.update(grid.get_entities_at(position))
        spell_level = self._protection_spell_level()
        source = Entity.get(self.source_entity_uuid)
        source_position = source.position if source is not None else (0, 0)
        for entity_uuid in sorted(occupant_uuids, key=str):
            entity = Entity.get(entity_uuid)
            if entity is None:
                continue
            if (
                spell_level is not None
                and self.magical_origin
                and SpellProtectionRegistry.is_protected(
                    entity.position,
                    source_position,
                    spell_level,
                )
            ):
                continue
            if not self._admit_trigger(trigger_kind, entity.uuid, parent_event):
                continue
            self._apply_effect_entry_effect(
                entity,
                parent_event=parent_event,
            )

    def apply_effect_exit_trigger(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Apply an explicitly authored moving-area departure consequence."""
        trigger_kind = SpatialEffectTriggerKind.EFFECT_LEAVES_OCCUPANT
        if trigger_kind not in self.trigger_kinds:
            return
        grid = get_map()
        occupant_uuids: Set[UUID] = set()
        for position in self._iter_work_positions(positions):
            occupant_uuids.update(grid.get_entities_at(position))
        for entity_uuid in sorted(occupant_uuids, key=str):
            entity = Entity.get(entity_uuid)
            if entity is None:
                continue
            self._apply_effect_exit_effect(
                entity,
                parent_event=parent_event,
            )

    def _protection_spell_level(self) -> Optional[int]:
        """Return the explicit base spell level used by globe protection."""
        if (
            self.effect_origin is None
            or self.effect_origin.kind is not EffectOriginKind.SPELL
        ):
            return None
        return self.effect_origin.base_spell_level

    @staticmethod
    def _wrap_processor_with_protection(
        original_processor: Callable[[Event, UUID], Optional[Event]],
        source_entity_uuid: UUID,
        spell_level: int,
    ) -> Callable[[Event, UUID], Optional[Event]]:
        """Wrap a zone handler processor with a SpellProtectionRegistry check.

        At fire time, checks if the target entity's position is protected by a
        globe-like effect. If protected, skips the effect (returns None).
        """
        def wrapped(event: Event, src_uuid: UUID) -> Optional[Event]:
            if event.target_entity_uuid:
                target = Entity.get(event.target_entity_uuid)
                if target:
                    source = Entity.get(source_entity_uuid)
                    source_pos = source.position if source else (0, 0)
                    if SpellProtectionRegistry.is_protected(target.position, source_pos, spell_level):
                        return None
            return original_processor(event, src_uuid)

        return wrapped

    def _compute_affected_positions(self) -> Set[Tuple[int, int]]:
        """Compute which tile positions are affected by this zone.

        Override in subclasses for custom geometry.
        Default uses AoE shapes from dnd.core.aoe.
        """
        if self.zone_shape in ("cone", "line") and self.zone_direction:
            dx, dy = self.zone_direction
            target = (self.position[0] + dx, self.position[1] + dy)
            if self.zone_shape == "cone":
                shape = Cone(
                    source_entity_uuid=self.source_entity_uuid,
                    target=target,
                    length_feet=self.zone_radius_feet,
                )
            else:
                shape = Line(
                    source_entity_uuid=self.source_entity_uuid,
                    target=target,
                    length_feet=self.zone_radius_feet,
                    width_feet=self.zone_width_feet,
                )
        elif self.zone_shape == "cube":
            shape = Cube(
                source_entity_uuid=self.source_entity_uuid,
                target=self.position,
                size_feet=self.zone_radius_feet,
                centered=True,
            )
        elif self.zone_shape == "cylinder":
            shape = Cylinder(
                source_entity_uuid=self.source_entity_uuid,
                target=self.position,
                radius_feet=self.zone_radius_feet,
            )
        else:
            shape = Sphere(
                source_entity_uuid=self.source_entity_uuid,
                target=self.position,
                radius_feet=self.zone_radius_feet,
            )

        shape.compute_objective(self.position)
        return set(shape.affected_positions)

    def resolve_area_footprint(self) -> Set[Tuple[int, int]]:
        """Resolve valid cells after map bounds and spell protection."""
        grid = get_map()
        positions: Set[Tuple[int, int]] = set()
        for position in self._iter_work_positions(
            self._compute_affected_positions()
        ):
            if grid.has_tile(*position):
                positions.add(position)
        spell_level = self._protection_spell_level()
        if spell_level is None or not self.magical_origin:
            return positions
        source = Entity.get(self.source_entity_uuid)
        if source is None:
            return positions
        return positions - SpellProtectionRegistry.get_excluded_positions(
            source.position,
            spell_level,
        )

    def resolve_condition_footprint(self) -> Set[Tuple[int, int]]:
        """Resolve the area geometry used by direct condition activation."""
        return self.resolve_area_footprint()

    def rollback_failed_install(
        self,
        *,
        parent_event: Optional[Event] = None,
    ) -> None:
        """Release every lease created before a failed condition commit."""
        if not self.applied:
            for handler_uuid in (
                self._entry_handler_uuid,
                self._exit_handler_uuid,
            ):
                if handler_uuid is not None:
                    EventQueue.remove_spatial_handler(handler_uuid)
            for handler_uuid in (
                self._turn_start_handler_uuid,
                self._turn_end_handler_uuid,
            ):
                if handler_uuid is None:
                    continue
                handler = EventHandler.get(handler_uuid)
                if isinstance(handler, EventHandler):
                    handler.remove()
        self._entry_handler_uuid = None
        self._exit_handler_uuid = None
        self._turn_start_handler_uuid = None
        self._turn_end_handler_uuid = None
        self._remove_terrain_modifiers()
        self._remove_light_modifiers()
        if self._uncommitted_state_discarded:
            self._pending_terrain_before_values.clear()

    @staticmethod
    def _tile_movement_costs(tile) -> Tuple[int, int, int, int]:
        """Return one Tile's complete effective traversal-cost tuple."""
        return (
            tile.get_movement_cost(MovementMode.WALKING),
            tile.get_movement_cost(MovementMode.FLYING),
            tile.get_movement_cost(MovementMode.SWIMMING),
            tile.get_movement_cost(MovementMode.BURROWING),
        )

    def _record_terrain_before_value(
        self,
        position: Tuple[int, int],
        costs: Tuple[int, int, int, int],
    ) -> None:
        """Retain one committed Tile tuple until the condition fact boundary."""
        self._pending_terrain_before_values.setdefault(position, costs)

    def _capture_terrain_baseline(
        self,
        positions: Set[Tuple[int, int]],
    ) -> None:
        """Capture admitted Tile tuples before provisional area mechanics."""
        grid = get_map()
        for position in self._iter_work_positions(sorted(positions)):
            tile = grid.get_tile(*position)
            if tile is not None:
                self._pending_terrain_before_values.setdefault(
                    position,
                    self._tile_movement_costs(tile),
                )

    def _publish_pending_terrain_changes(
        self,
        parent_event: Optional[Event],
    ) -> None:
        """Publish sorted committed Tile-cost facts after condition application."""
        if not self._pending_terrain_before_values:
            return
        grid = get_map()
        pending = self._pending_terrain_before_values
        self._pending_terrain_before_values = {}
        for position in self._iter_work_positions(sorted(pending)):
            tile = grid.get_tile(*position)
            if tile is None:
                continue
            after = self._tile_movement_costs(tile)
            if pending[position] == after:
                continue
            walking, flying, swimming, burrowing = after
            event = SpatialChangeEvent.tile_changed(
                position,
                tile_walking_cost=walking,
                tile_flying_cost=flying,
                tile_swimming_cost=swimming,
                tile_burrowing_cost=burrowing,
                senses_hint=SensesUpdateHint(requires_paths=True),
                source_entity_uuid=self.source_entity_uuid,
                parent_event=(
                    parent_event.uuid if parent_event is not None else None
                ),
            )
            grid._fire_committed_spatial_event(event)

    def _apply_terrain_modifiers(
        self,
        positions: Optional[Set[Tuple[int, int]]] = None,
    ) -> List[Tuple[UUID, UUID]]:
        """Apply difficult terrain modifiers to affected tiles.

        Args:
            positions: Optional position subset. Defaults to the whole zone.

        Returns:
            List of (value_uuid, modifier_uuid) pairs for tracking in modifers_uuids.
        """
        outs: List[Tuple[UUID, UUID]] = []
        if not self.adds_difficult_terrain:
            return outs

        grid = get_map()
        modified_positions: List[Tuple[int, int]] = []
        target_positions = (
            positions if positions is not None else self.affected_positions
        )
        for pos in self._iter_work_positions(sorted(target_positions)):
            tile = grid.get_tile(*pos)
            if tile:
                before = self._tile_movement_costs(tile)
                mod = NumericalModifier.create(
                    source_entity_uuid=self.source_entity_uuid,
                    name=f"{self.name} Difficult Terrain",
                    value=1,
                )
                mod_uuid = tile.walking_cost.self_static.add_value_modifier(mod)
                self._terrain_modifier_uuids[tile.walking_cost.uuid] = [mod_uuid]
                outs.append((tile.walking_cost.uuid, mod_uuid))
                if before != self._tile_movement_costs(tile):
                    modified_positions.append(pos)
                    self._record_terrain_before_value(pos, before)

        if modified_positions:
            grid.invalidate_spatial_caches({"movement"})

        return outs

    def _remove_terrain_modifiers_from_positions(
        self,
        positions: Optional[Set[Tuple[int, int]]] = None,
    ) -> bool:
        """Remove terrain modifiers through one batched invalidation path.

        Args:
            positions: Position subset to remove. ``None`` removes every
                modifier still owned by this zone.

        Returns:
            True when at least one owned modifier was removed.
        """
        grid = get_map()
        target_positions = (
            set(self.affected_positions) if positions is None else positions
        )
        before_costs = {}
        for position in self._iter_work_positions(sorted(target_positions)):
            tile = grid.get_tile(*position)
            if tile is not None:
                before_costs[position] = self._tile_movement_costs(tile)
        owned_modifiers: List[Tuple[UUID, List[UUID]]]
        if positions is None:
            owned_modifiers = list(self._terrain_modifier_uuids.items())
            self._terrain_modifier_uuids.clear()
            removed_positions = set(target_positions)
        else:
            owned_modifiers = []
            removed_positions = set()
            for position in self._iter_work_positions(sorted(positions)):
                tile = grid.get_tile(*position)
                if tile is None:
                    continue
                value_uuid = tile.walking_cost.uuid
                modifier_uuids = self._terrain_modifier_uuids.pop(
                    value_uuid,
                    [],
                )
                if modifier_uuids:
                    owned_modifiers.append((value_uuid, modifier_uuids))
                    removed_positions.add(position)

        removed_any = bool(owned_modifiers)
        for value_uuid, modifier_uuids in owned_modifiers:
            value = ModifiableValue.get(value_uuid)
            if value is not None:
                for modifier_uuid in modifier_uuids:
                    try:
                        value.remove_modifier(modifier_uuid)
                    except (ValueError, KeyError):
                        continue
            tracked_modifiers = self.modifers_uuids.get(value_uuid)
            if tracked_modifiers is not None:
                self.modifers_uuids[value_uuid] = [
                    modifier_uuid
                    for modifier_uuid in tracked_modifiers
                    if modifier_uuid not in modifier_uuids
                ]
                if not self.modifers_uuids[value_uuid]:
                    del self.modifers_uuids[value_uuid]

        if not removed_any:
            return False
        grid.invalidate_spatial_caches({"movement"})
        for position in self._iter_work_positions(sorted(removed_positions)):
            tile = grid.get_tile(*position)
            if tile is not None and before_costs.get(position) != self._tile_movement_costs(tile):
                self._record_terrain_before_value(
                    position,
                    before_costs[position],
                )
        return True

    def _remove_terrain_modifiers(self) -> None:
        """Remove every terrain modifier through the batched primitive."""
        self._remove_terrain_modifiers_from_positions()

    def _remove_terrain_modifier_at(self, position: Tuple[int, int]) -> bool:
        """Remove this zone's difficult-terrain modifier from one tile.

        Args:
            position: Grid position whose terrain modifier should be removed.

        Returns:
            True if a modifier was removed from the tile.
        """
        return self._remove_terrain_modifiers_from_positions({position})

    def _apply_light_modifiers(
        self,
        positions: Optional[Set[Tuple[int, int]]] = None,
    ) -> None:
        """Apply light modifiers and retain their unpublished changed cells."""
        if self.sets_light_level is None:
            return

        grid = get_map()
        target_positions = (
            positions if positions is not None else self.affected_positions
        )
        applied, changed = grid.apply_tile_light_modifier(
            self.uuid,
            set(target_positions),
            self.sets_light_level,
            cap=self.light_is_cap,
        )
        self._light_modifier_positions.update(applied)
        self._pending_light_changed_positions.update(changed)

    def _remove_light_modifiers_from_positions(
        self,
        positions: Optional[Set[Tuple[int, int]]] = None,
    ) -> bool:
        """Remove light modifiers and retain their unpublished changed cells.

        Args:
            positions: Position subset to remove. ``None`` removes every
                modifier still owned by this zone.

        Returns:
            True when at least one tile's resolved light state changed.
        """
        grid = get_map()
        target_positions = (
            set(self._light_modifier_positions)
            if positions is None
            else positions & self._light_modifier_positions
        )
        removed, changed = grid.remove_tile_light_modifier(
            self.uuid,
            target_positions,
        )
        self._light_modifier_positions.difference_update(removed)
        self._pending_light_changed_positions.update(changed)
        return bool(removed)

    def _publish_pending_light_changes(
        self,
        parent_event: Optional[Event],
    ) -> None:
        """Publish the exact light delta after optical and light state agree."""
        if not self._pending_light_changed_positions:
            return
        changed = set(self._pending_light_changed_positions)
        get_map().publish_light_changes(
            changed,
            parent_event=parent_event.uuid if parent_event is not None else None,
        )
        self._pending_light_changed_positions.difference_update(changed)

    def _publish_pending_runtime_facts(
        self,
        parent_event: Optional[Event],
    ) -> None:
        """Publish deferred objective light state after the spatial commit."""
        self._publish_pending_terrain_changes(parent_event)
        self._publish_pending_light_changes(parent_event)

    def _discard_pending_runtime_facts(self) -> None:
        """Discard provisional terrain facts during failed condition restoration."""
        super()._discard_pending_runtime_facts()
        self._pending_terrain_before_values.clear()

    def _discard_pending_terrain_positions(
        self,
        positions: Set[Tuple[int, int]],
    ) -> None:
        """Discard rows for cells transferred to a replacing condition."""
        for position in self._iter_work_positions(positions):
            self._pending_terrain_before_values.pop(position, None)

    def _finalize_application(self, effect_event: Event) -> None:
        """Publish terrain facts only after the condition application commits."""
        super()._finalize_application(effect_event)
        self._publish_pending_runtime_facts(effect_event)

    def _remove_light_modifiers(self) -> None:
        """Remove every light modifier through the batched primitive."""
        self._remove_light_modifiers_from_positions()

    def _remove_light_modifier_at(self, position: Tuple[int, int]) -> bool:
        """Remove this zone's light or obscurement modifier from one tile.

        Args:
            position: Grid position whose light modifier should be removed.

        Returns:
            True if a tile light state changed.
        """
        return self._remove_light_modifiers_from_positions({position})

    def _sync_spatial_handler_positions(self) -> None:
        """Synchronize spatial handlers with the current affected positions."""
        super()._sync_spatial_handler_positions()
        if self._entry_handler_uuid:
            EventQueue.update_spatial_handler_positions(
                self._entry_handler_uuid,
                self.affected_positions,
                EventType.SPATIAL_ENTITY_ENTERED,
                EventPhase.EFFECT,
            )

        if self._exit_handler_uuid:
            EventQueue.update_spatial_handler_positions(
                self._exit_handler_uuid,
                self.affected_positions,
                EventType.SPATIAL_ENTITY_LEFT,
                EventPhase.EFFECT,
            )

    def _release_positions(self, positions: Set[Tuple[int, int]]) -> None:
        """Release positional mechanics before a footprint index shrinks."""
        for position in self._iter_work_positions(positions):
            self._remove_terrain_modifier_at(position)
            self._remove_light_modifier_at(position)
        retained = self.affected_positions - positions
        previous = self.affected_positions
        self.affected_positions = set(retained)
        self._sync_spatial_handler_positions()
        self.affected_positions = previous

    def _restore_positions(self, positions: Set[Tuple[int, int]]) -> None:
        """Restore positional mechanics after a failed footprint swap."""
        self._apply_terrain_modifiers(positions)
        self._apply_light_modifiers(positions)
        self._sync_spatial_handler_positions()

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply zone control by computing positions and registering handlers."""
        handler_uuids: List[UUID] = []
        spatial_handler_uuids: List[UUID] = []

        if self._activation_positions is None:
            raise RuntimeError("Area condition has no admitted footprint")
        self.affected_positions = set(self._activation_positions)
        self._capture_terrain_baseline(self.affected_positions)
        spell_level = self._protection_spell_level()

        if SpatialEffectTriggerKind.ENTER in self.trigger_kinds:
            handler = self._create_zone_entry_handler()
            handler.event_processor = self._wrap_processor_with_trigger_admission(
                handler.event_processor,
                SpatialEffectTriggerKind.ENTER,
            )
            if spell_level is not None and self.magical_origin:
                handler.event_processor = self._wrap_processor_with_protection(
                    handler.event_processor, self.source_entity_uuid, spell_level)
            EventQueue.add_spatial_handler(
                handler,
                self.affected_positions,
                EventType.SPATIAL_ENTITY_ENTERED,
                EventPhase.EFFECT
            )
            self._entry_handler_uuid = handler.uuid
            spatial_handler_uuids.append(handler.uuid)

        if SpatialEffectTriggerKind.LEAVE in self.trigger_kinds:
            handler = self._create_zone_exit_handler()
            handler.event_processor = self._wrap_processor_with_trigger_admission(
                handler.event_processor,
                SpatialEffectTriggerKind.LEAVE,
            )
            EventQueue.add_spatial_handler(
                handler,
                self.affected_positions,
                EventType.SPATIAL_ENTITY_LEFT,
                EventPhase.EFFECT
            )
            self._exit_handler_uuid = handler.uuid
            spatial_handler_uuids.append(handler.uuid)

        if SpatialEffectTriggerKind.TURN_START in self.trigger_kinds:
            handler = self._create_zone_turn_start_handler()
            handler.event_processor = self._wrap_processor_with_trigger_admission(
                handler.event_processor,
                SpatialEffectTriggerKind.TURN_START,
            )
            if spell_level is not None and self.magical_origin:
                handler.event_processor = self._wrap_processor_with_protection(
                    handler.event_processor, self.source_entity_uuid, spell_level)
            EventQueue.add_event_handler(handler)
            self._turn_start_handler_uuid = handler.uuid
            handler_uuids.append(handler.uuid)

        if SpatialEffectTriggerKind.TURN_END in self.trigger_kinds:
            handler = self._create_zone_turn_end_handler()
            handler.event_processor = self._wrap_processor_with_trigger_admission(
                handler.event_processor,
                SpatialEffectTriggerKind.TURN_END,
            )
            if spell_level is not None and self.magical_origin:
                handler.event_processor = self._wrap_processor_with_protection(
                    handler.event_processor,
                    self.source_entity_uuid,
                    spell_level,
                )
            EventQueue.add_event_handler(handler)
            self._turn_end_handler_uuid = handler.uuid
            handler_uuids.append(handler.uuid)

        terrain_modifiers = self._apply_terrain_modifiers()
        self._commit_activation_footprint(parent_event=declaration_event)
        self._apply_light_modifiers()
        for incumbent_uuid in sorted(self._displaced_footprints, key=str):
            incumbent = BaseCondition.get(incumbent_uuid)
            if isinstance(incumbent, AreaCondition):
                incumbent._publish_pending_light_changes(declaration_event)
        self._publish_pending_light_changes(declaration_event)

        if declaration_event is not None:
            effect_event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        else:
            effect_event = None

        return terrain_modifiers, handler_uuids, [], spatial_handler_uuids, effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Remove the optical index before publishing owned light removal."""
        removed_event = super()._remove(event)
        if removed_event is not None and not removed_event.canceled:
            get_map().remove_spatial_condition(self.uuid)
        return removed_event

    def _release_owned_runtime_state(
        self,
        *,
        parent_event: Optional[Event] = None,
    ) -> None:
        """Release partial area mechanics during rejected application."""
        self.rollback_failed_install(parent_event=parent_event)

    def move_zone(
        self,
        new_center: Tuple[int, int],
        *,
        parent_event: Event,
    ) -> bool:
        """Move every zone-owned spatial fact using one position delta.

        This method:
        1. Computes removed, retained, and added positions
        2. Removes terrain and light facts only from removed cells
        3. Updates shared spatial handler indices once
        4. Applies terrain and light facts only to added cells

        Returns True on success.
        """
        old_positions = set(self.affected_positions)
        old_position = self.position
        self._validate_exact_anchor_position(new_center)
        self.position = new_center
        try:
            new_positions = self._compute_affected_positions()
        finally:
            self.position = old_position
        grid = get_map()
        new_positions = {
            position
            for position in self._iter_work_positions(new_positions)
            if grid.has_tile(*position)
        }
        removed_positions = old_positions - new_positions
        added_positions = new_positions - old_positions
        physical_positions = old_positions | new_positions
        physical_before = self._physical_optics_snapshot(grid, physical_positions)

        grid.validate_spatial_condition_positions(
            condition=self,
            layer=self.layer,
            occupancy_policy=self.occupancy_policy,
            positions=new_positions,
        )
        try:
            self._release_positions(removed_positions)
            self.position = new_center
            self.affected_positions = set(new_positions)
            self._sync_spatial_handler_positions()
            grid.set_spatial_condition_positions(
                condition=self,
                layer=self.layer,
                occupancy_policy=self.occupancy_policy,
                positions=new_positions,
            )
            self._restore_positions(added_positions)
        except BaseException:
            self._release_positions(added_positions)
            self.position = old_position
            self.affected_positions = set(old_positions)
            grid.set_spatial_condition_positions(
                condition=self,
                layer=self.layer,
                occupancy_policy=self.occupancy_policy,
                positions=old_positions,
            )
            self._restore_positions(removed_positions)
            self._pending_light_changed_positions.clear()
            self._pending_terrain_before_values.clear()
            self._settle_physical_optics(
                grid,
                physical_before,
                physical_positions,
                parent_event=parent_event,
            )
            raise

        self._settle_physical_optics(
            grid,
            physical_before,
            physical_positions,
            parent_event=parent_event,
        )
        self._publish_pending_runtime_facts(parent_event)

        self.apply_effect_exit_trigger(
            removed_positions,
            parent_event=parent_event,
        )
        self.apply_effect_entry_trigger(
            added_positions,
            parent_event=parent_event,
        )

        self._publish_change(
            SpatialEffectChangeOperation.FOOTPRINT_CHANGED,
            previous_positions=old_positions,
            parent_event=parent_event,
        )

        return True

    def relocate_anchor(
        self,
        position: Tuple[int, int],
        *,
        parent_event: Event,
    ) -> None:
        """Recenter an attached zone through the shared delta-movement path."""
        self.move_zone(position, parent_event=parent_event)
