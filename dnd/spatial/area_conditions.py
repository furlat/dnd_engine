"""Independent spatial conditions and reusable area mechanics."""

from typing import Callable, Dict, List, Optional, Set, Tuple
from uuid import UUID

from pydantic import Field, PrivateAttr, StrictInt, model_validator

from dnd.core.base_block import BaseBlock, LightLevel, MovementMode
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.condition_types import DurationType, HazardFilter
from dnd.core.content.identities import ContentRef
from dnd.core.effect_types import EffectOriginKind
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    SpatialChangeEvent,
    SpatialEffectChangeEvent,
    Trigger,
    TurnEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.aoe import Cone, Cube, Cylinder, Line, Sphere
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.types.senses import OpticalObscurement
from dnd.types.spatial_effects import (
    SpatialEffectAnchorKind,
    SpatialEffectBlockingPolicy,
    SpatialEffectChangeOperation,
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
)


class SpatialCondition(BaseCondition):
    """One condition that directly owns its world footprint and mechanics."""

    name: str = Field(default="Spatial Condition")
    content_ref: ContentRef = Field(
        description="Exact authored identity of this spatial condition.",
    )
    faction: Optional[str] = Field(default=None)
    position: Tuple[StrictInt, StrictInt] = Field(
        description="Authoritative anchor position.",
    )
    affected_positions: Set[Tuple[int, int]] = Field(default_factory=set)
    layer: SpatialEffectLayer
    occupancy_policy: SpatialEffectOccupancyPolicy
    anchor_kind: SpatialEffectAnchorKind = SpatialEffectAnchorKind.FIXED_POSITION
    anchor_uuid: Optional[UUID] = None
    blocking_policy: SpatialEffectBlockingPolicy = SpatialEffectBlockingPolicy.NONE
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=frozenset,
    )
    first_per_turn_trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=frozenset,
    )
    arbitration_potency: int = Field(default=0, ge=0)
    optical_obscurement: Optional[OpticalObscurement] = None
    blocks_physical_optics: bool = False

    _activation_positions: Optional[Set[Tuple[int, int]]] = PrivateAttr(
        default=None,
    )
    _displaced_footprints: Dict[
        UUID,
        Tuple[Set[Tuple[int, int]], Set[Tuple[int, int]]],
    ] = PrivateAttr(default_factory=dict)
    _removal_operation: SpatialEffectChangeOperation = PrivateAttr(
        default=SpatialEffectChangeOperation.REMOVED,
    )
    _removal_previous_positions: Optional[Set[Tuple[int, int]]] = PrivateAttr(
        default=None,
    )

    @model_validator(mode="after")
    def validate_spatial_identity(self) -> "SpatialCondition":
        """Require coherent anchors and trigger declarations."""
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

    def get_position(self) -> Tuple[int, int]:
        """Return the condition anchor."""
        return self.position

    def resolve_condition_footprint(self) -> Set[Tuple[int, int]]:
        """Return the intended activation footprint."""
        return set(self.affected_positions) or {self.position}

    def material_arbitration_rank(self) -> Tuple[int, int]:
        """Rank matching exclusive conditions by potency and spell level."""
        spell_level = (
            self.effect_origin.effective_spell_level
            if self.effect_origin is not None
            and self.effect_origin.effective_spell_level is not None
            else 0
        )
        return self.arbitration_potency, spell_level

    def is_active_spatial_condition(self) -> bool:
        """Verify activity against the authoritative map collection."""
        return get_map().get_spatial_condition(self.uuid) is self

    def get_optical_obscurement_at(
        self,
        position: Tuple[int, int],
    ) -> Optional[OpticalObscurement]:
        """Return this condition's optical contribution in its footprint."""
        if position not in self.affected_positions:
            return None
        return self.optical_obscurement

    def blocks_physical_optics_at(self, position: Tuple[int, int]) -> bool:
        """Return whether this condition physically blocks optics here."""
        return self.blocks_physical_optics and position in self.affected_positions

    def blocks_walking_at(
        self,
        position: Tuple[int, int],
        requesting_entity_uuid: Optional[UUID] = None,
        mode: MovementMode = MovementMode.WALKING,
    ) -> bool:
        """Apply the condition's explicit traversal-blocking policy."""
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
        """Resolve a concealed hazard against passive perception."""
        if requesting_entity_uuid is None or self.condition_stealth_dc is None:
            return True
        observer = BaseBlock.get(requesting_entity_uuid)
        return (
            observer is None
            or self.condition_stealth_dc < observer.get_passive_perception()
        )

    def is_hazardous_for(self, entity_uuid: Optional[UUID] = None) -> bool:
        """Resolve the inherited hazard filter for one entity."""
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
        """Track one child and its reverse link to this independent owner."""
        self.linked_conditions.append((target_block_uuid, condition_uuid))
        child = BaseCondition.get(condition_uuid)
        if isinstance(child, BaseCondition):
            child.parent_link = (self.uuid, self.uuid)

    def _apply(
        self,
        execution_event: Event,
    ) -> Tuple[list[Tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event]:
        """Install the prepared footprint under its CREATED effect."""
        application_effect = execution_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
        )
        change_effect = self._open_change(
            SpatialEffectChangeOperation.CREATED,
            previous_positions=set(),
            affected_positions=set(self._activation_positions or ()),
            parent_event=application_effect,
        )
        self._commit_activation_footprint()
        get_map().invalidate_spatial_caches({"movement", "optical", "propagation"})
        event_handler_uuids: list[UUID] = []
        anchor_handler = self._create_anchor_handler()
        if anchor_handler is not None:
            EventQueue.add_event_handler(anchor_handler)
            event_handler_uuids.append(anchor_handler.uuid)
        return (
            [],
            event_handler_uuids,
            [],
            [],
            change_effect,
        )

    def _resolve_activation_admission(
        self,
        positions: Set[Tuple[int, int]],
        replacing_condition_uuid: Optional[UUID],
    ) -> Set[Tuple[int, int]]:
        """Resolve one exclusive footprint before any world mutation."""
        grid = get_map()
        normalized = set(positions)
        if not normalized:
            raise ValueError("Spatial condition footprint cannot be empty")
        if any(not grid.has_tile(*position) for position in normalized):
            raise ValueError(
                "Spatial condition positions must identify existing tiles",
            )
        if self.occupancy_policy is SpatialEffectOccupancyPolicy.OVERLAPPING:
            grid.validate_spatial_condition_positions(
                condition=self,
                layer=self.layer,
                occupancy_policy=self.occupancy_policy,
                positions=normalized,
            )
            self._displaced_footprints.clear()
            return normalized

        authorized: Optional[SpatialCondition] = None
        if replacing_condition_uuid is not None:
            candidate = grid.get_spatial_condition(replacing_condition_uuid)
            if not isinstance(candidate, SpatialCondition):
                raise ValueError("Authorized replacement condition is unavailable")
            if candidate.layer is not self.layer:
                raise ValueError("Authorized replacement must use the same layer")
            if not normalized.issubset(candidate.affected_positions):
                raise ValueError(
                    "Authorized replacement does not cover the intended cells",
                )
            authorized = candidate

        admitted = set(normalized)
        displaced: Dict[UUID, Set[Tuple[int, int]]] = {}
        incoming_rank = self.material_arbitration_rank()
        for position in sorted(normalized):
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
                if authorized is not None and incumbent.uuid == authorized.uuid:
                    displaced.setdefault(incumbent.uuid, set()).add(position)
                    continue
                if incumbent.content_ref != self.content_ref:
                    raise ValueError(
                        f"{self.layer.value} cell {position} requires an "
                        "authored material transformation",
                    )
                if incumbent.material_arbitration_rank() > incoming_rank:
                    admitted.discard(position)
                    continue
                displaced.setdefault(incumbent.uuid, set()).add(position)

        self._displaced_footprints = {}
        for incumbent_uuid, removed in displaced.items():
            incumbent = grid.get_spatial_condition(incumbent_uuid)
            if not isinstance(incumbent, SpatialCondition):
                raise RuntimeError("Admitted incumbent disappeared")
            original = set(incumbent.affected_positions)
            self._displaced_footprints[incumbent_uuid] = (
                original,
                original - removed,
            )
        return admitted

    def _commit_activation_footprint(self) -> None:
        """Swap preflighted Tile membership before installing mechanics."""
        if self._activation_positions is None:
            raise RuntimeError("Spatial condition has no prepared footprint")
        grid = get_map()
        for incumbent_uuid in sorted(self._displaced_footprints, key=str):
            incumbent = grid.get_spatial_condition(incumbent_uuid)
            if not isinstance(incumbent, SpatialCondition):
                raise RuntimeError("Admitted incumbent disappeared")
            _, remaining = self._displaced_footprints[incumbent_uuid]
            incumbent.affected_positions = set(remaining)
            if remaining:
                grid.set_spatial_condition_positions(
                    condition=incumbent,
                    layer=incumbent.layer,
                    occupancy_policy=incumbent.occupancy_policy,
                    positions=set(remaining),
                )
            else:
                grid.remove_spatial_condition(incumbent.uuid)

        grid.set_spatial_condition_positions(
            condition=self,
            layer=self.layer,
            occupancy_policy=self.occupancy_policy,
            positions=set(self._activation_positions),
        )
        self.affected_positions = set(self._activation_positions)

    def _release_positions(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Release subclass mechanics from successfully displaced cells."""
        del positions, parent_event

    def _finalize_displacements(self, *, parent_event: Event) -> None:
        """Settle incumbents only after incoming mechanics have succeeded."""
        for incumbent_uuid in sorted(self._displaced_footprints, key=str):
            incumbent = BaseCondition.get(incumbent_uuid)
            if not isinstance(incumbent, SpatialCondition):
                raise RuntimeError("Displaced spatial condition disappeared")
            original, remaining = self._displaced_footprints[incumbent_uuid]
            removed = original - remaining
            if remaining:
                change_effect = incumbent._open_change(
                    SpatialEffectChangeOperation.TRANSFORMED,
                    previous_positions=original,
                    affected_positions=remaining,
                    parent_event=parent_event,
                )
                incumbent._release_positions(
                    removed,
                    parent_event=change_effect,
                )
                for handler_uuid in incumbent.spatial_handler_uuids:
                    EventQueue.update_spatial_handler_positions(
                        handler_uuid,
                        set(remaining),
                    )
                incumbent._complete_change(change_effect)
                continue
            if not incumbent._deactivate(
                parent_event=parent_event,
                operation=SpatialEffectChangeOperation.TRANSFORMED,
                previous_positions=original,
                allow_detached=True,
            ):
                raise RuntimeError(
                    "Displaced spatial condition rejected retirement",
                )
        self._displaced_footprints.clear()

    def _restore_displaced_footprints(self) -> None:
        """Restore only Tile membership after incoming application failure."""
        grid = get_map()
        for incumbent_uuid in sorted(self._displaced_footprints, key=str):
            incumbent = BaseCondition.get(incumbent_uuid)
            if not isinstance(incumbent, SpatialCondition):
                continue
            original, _ = self._displaced_footprints[incumbent_uuid]
            incumbent.affected_positions = set(original)
            grid.set_spatial_condition_positions(
                condition=incumbent,
                layer=incumbent.layer,
                occupancy_policy=incumbent.occupancy_policy,
                positions=set(original),
            )
        self._displaced_footprints.clear()

    def _create_anchor_handler(self) -> Optional[EventHandler]:
        """Create one direct movement binding for an attached condition."""
        if self.anchor_kind not in {
            SpatialEffectAnchorKind.ENTITY,
            SpatialEffectAnchorKind.WORLD_OBJECT,
        }:
            return None
        assert self.anchor_uuid is not None
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

        def move_with_anchor(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            condition = BaseCondition.get(condition_uuid)
            if not isinstance(condition, SpatialCondition):
                return None
            if not isinstance(event, SpatialChangeEvent):
                return None
            if anchor_kind is SpatialEffectAnchorKind.ENTITY:
                if event.entity_uuid != anchor_uuid:
                    return None
                if event.event_type is EventType.SPATIAL_ENTITY_ENTERED:
                    condition.relocate_anchor(event.position, parent_event=event)
                elif event.old_position is None:
                    condition.deactivate(parent_event=event)
                return None
            if event.object_uuid != anchor_uuid:
                return None
            if event.event_type is EventType.SPATIAL_OBJECT_REMOVED:
                condition.deactivate(parent_event=event)
            elif event.placement is not None:
                condition.relocate_anchor(
                    event.placement.position,
                    parent_event=event,
                )
            return None

        return EventHandler(
            name=f"{self.name} Anchor Movement",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=event_type,
                    event_phase=EventPhase.EFFECT,
                )
                for event_type in event_types
            ],
            event_processor=move_with_anchor,
        )

    def relocate_anchor(
        self,
        position: Tuple[int, int],
        *,
        parent_event: Event,
    ) -> bool:
        """Translate an attached footprint with its authoritative anchor."""
        if not self.is_active_spatial_condition():
            return False
        if position == self.position:
            return False
        previous_anchor = self.position
        delta = (
            position[0] - previous_anchor[0],
            position[1] - previous_anchor[1],
        )
        translated = {
            (cell[0] + delta[0], cell[1] + delta[1])
            for cell in self.affected_positions
        }
        self.position = position
        try:
            return self.change_footprint(
                translated or {position},
                parent_event=parent_event,
            )
        except BaseException:
            self.position = previous_anchor
            raise

    def activate(
        self,
        *,
        parent_event: Event,
        replacing_condition_uuid: Optional[UUID] = None,
    ) -> Optional[Event]:
        """Activate the condition and publish its terminal after world commit."""
        grid = get_map()
        if self.applied or grid.has_spatial_condition(self.uuid):
            raise ValueError("Spatial condition is already active")
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
        self._activation_positions = set(admitted)
        try:
            effect = self.apply(parent_event=parent_event)
        except BaseException:
            self.discard_from_runtime_owner()
            raise
        if effect is None or effect.canceled or not self.applied:
            self.discard_from_runtime_owner()
            return effect
        if not isinstance(effect, SpatialEffectChangeEvent):
            raise RuntimeError(
                "Spatial condition application did not return its change effect",
            )
        self._finalize_displacements(parent_event=effect)
        self._complete_change(effect)
        application_effect = (
            EventQueue.get_event_by_uuid(effect.parent_event)
            if effect.parent_event is not None
            else None
        )
        if application_effect is None:
            raise RuntimeError(
                "Spatial condition change is missing its application effect",
            )
        self._activation_positions = None
        return application_effect.phase_to(EventPhase.COMPLETION)

    def _change_footprint(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> Optional[SpatialEffectChangeEvent]:
        """Commit the base footprint and return its open change effect."""
        if not self.is_active_spatial_condition():
            return None
        normalized = set(positions)
        previous = set(self.affected_positions)
        if normalized == previous:
            return None
        change_effect = self._open_change(
            SpatialEffectChangeOperation.FOOTPRINT_CHANGED,
            previous_positions=previous,
            affected_positions=normalized,
            parent_event=parent_event,
        )
        get_map().set_spatial_condition_positions(
            condition=self,
            layer=self.layer,
            occupancy_policy=self.occupancy_policy,
            positions=normalized,
        )
        self.affected_positions = normalized
        for handler_uuid in self.spatial_handler_uuids:
            EventQueue.update_spatial_handler_positions(
                handler_uuid,
                normalized,
            )
        get_map().invalidate_spatial_caches({"movement", "optical", "propagation"})
        return change_effect

    def change_footprint(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> bool:
        """Replace the footprint and close its change after all mechanics."""
        change_effect = self._change_footprint(
            positions,
            parent_event=parent_event,
        )
        if change_effect is None:
            return False
        self._complete_change(change_effect)
        return True

    def _open_change(
        self,
        operation: SpatialEffectChangeOperation,
        *,
        previous_positions: Set[Tuple[int, int]],
        affected_positions: Set[Tuple[int, int]],
        parent_event: Optional[Event],
    ) -> SpatialEffectChangeEvent:
        """Publish the non-vetoable phases that directly cause a spatial change."""
        declaration = SpatialEffectChangeEvent(
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=self.source_entity_name,
            phase=EventPhase.DECLARATION,
            use_register=False,
            parent_event=(
                parent_event.uuid if parent_event is not None else None
            ),
            operation=operation,
            spatial_effect_uuid=self.uuid,
            spatial_effect_content_ref=self.content_ref,
            spatial_effect_name=self.name,
            layer=self.layer,
            anchor_position=self.position,
            affected_positions=tuple(sorted(affected_positions)),
            previous_positions=tuple(sorted(previous_positions)),
        )
        execution = declaration.phase_to(EventPhase.EXECUTION)
        effect = execution.phase_to(EventPhase.EFFECT)
        EventQueue.publish_preflighted(declaration)
        EventQueue.publish_preflighted(execution)
        return EventQueue.publish_preflighted(effect)

    @staticmethod
    def _complete_change(
        effect: SpatialEffectChangeEvent,
    ) -> SpatialEffectChangeEvent:
        """Complete one spatial change after every mandatory consequence."""
        return effect.phase_to(EventPhase.COMPLETION)

    def _release_owned_runtime_state(
        self,
        *,
        parent_event: Optional[Event] = None,
    ) -> None:
        """Release the authoritative footprint during cleanup or rollback."""
        del parent_event
        if get_map().has_spatial_condition(self.uuid):
            get_map().remove_spatial_condition(self.uuid)
            get_map().invalidate_spatial_caches(
                {"movement", "optical", "propagation"},
            )

    def discard_from_runtime_owner(self) -> bool:
        """Discard an uncommitted independently owned condition."""
        self.discard_uncommitted_runtime_state()
        for child_uuid in list(self.sub_conditions):
            child = BaseCondition.get(child_uuid)
            if isinstance(child, BaseCondition):
                owner = BaseBlock.get(child.target_entity_uuid)
                if isinstance(owner, BaseBlock):
                    owner._discard_condition_indexes(child)
                    owner._discard_uncommitted_condition_tree(child)
                else:
                    child.discard_from_runtime_owner()
        self.sub_conditions.clear()
        for owner_uuid, child_uuid in list(self.linked_conditions):
            child = BaseCondition.get(child_uuid)
            if not isinstance(child, BaseCondition):
                continue
            owner = BaseBlock.get(owner_uuid)
            if isinstance(owner, BaseBlock):
                owner._discard_condition_indexes(child)
                owner._discard_uncommitted_condition_tree(child)
            else:
                child.discard_from_runtime_owner()
        self.linked_conditions.clear()
        self.affected_positions.clear()
        self.remove_from_register()
        return True

    def discard_uncommitted_runtime_state(self) -> None:
        """Discard incoming mechanics and restore displaced Tile membership."""
        super().discard_uncommitted_runtime_state()
        self.affected_positions.clear()
        self._activation_positions = None
        self._restore_displaced_footprints()

    def remove_from_runtime_owner(
        self,
        *,
        expire: bool = False,
        parent_event: Optional[Event] = None,
        prepared_removal_effect: Optional[Event] = None,
    ) -> bool:
        """Remove this independent owner, or commit its accepted removal."""
        if prepared_removal_effect is None:
            return self.deactivate(
                expire=expire,
                parent_event=parent_event,
            )
        if not isinstance(prepared_removal_effect, SpatialEffectChangeEvent):
            raise TypeError(
                "Prepared spatial removal must be a spatial-change effect",
            )
        condition_effect = (
            EventQueue.get_event_by_uuid(prepared_removal_effect.parent_event)
            if prepared_removal_effect.parent_event is not None
            else None
        )
        if (
            condition_effect is None
            or condition_effect.event_type is not EventType.CONDITION_REMOVAL
            or condition_effect.canceled
        ):
            raise RuntimeError(
                "Prepared spatial removal is missing its condition effect",
            )

        removed = self.cleanup_own_state(
            expire=expire,
            parent_event=prepared_removal_effect,
            removal_effect=prepared_removal_effect,
        )
        if removed is None or removed.canceled:
            raise RuntimeError("Accepted spatial-condition removal failed")
        self.affected_positions.clear()
        if self.parent_link is not None:
            _, parent_condition_uuid = self.parent_link
            parent = BaseCondition.get(parent_condition_uuid)
            if isinstance(parent, BaseCondition):
                parent.linked_conditions = [
                    link
                    for link in parent.linked_conditions
                    if link[1] != self.uuid
                ]
            self.parent_link = None
        self.remove_from_register()
        self._complete_change(prepared_removal_effect)
        condition_effect.phase_to(EventPhase.COMPLETION)
        return True

    def publish_removal_effect(
        self,
        declaration_event: Event,
    ) -> Event:
        """Accept removal and expose its exact spatial cause before cleanup."""
        condition_effect = super().publish_removal_effect(declaration_event)
        if condition_effect.canceled:
            return condition_effect
        previous_positions = (
            set(self.affected_positions)
            if self._removal_previous_positions is None
            else set(self._removal_previous_positions)
        )
        return self._open_change(
            self._removal_operation,
            previous_positions=previous_positions,
            affected_positions=set(),
            parent_event=condition_effect,
        )

    def _remove_spatial_graph(
        self,
        *,
        expire: bool,
        parent_event: Optional[Event],
        operation: SpatialEffectChangeOperation,
        previous_positions: Optional[Set[Tuple[int, int]]] = None,
        allow_detached: bool = False,
    ) -> bool:
        """Preflight the finite owned graph, then commit it child-first."""
        if not self.applied or (
            not allow_detached and not self.is_active_spatial_condition()
        ):
            return False
        prepared: List[
            Tuple[Optional[BaseBlock], BaseCondition, Event, bool]
        ] = []
        prior_operation = self._removal_operation
        prior_positions = self._removal_previous_positions
        self._removal_operation = operation
        self._removal_previous_positions = (
            None if previous_positions is None else set(previous_positions)
        )
        try:
            canceled = BaseBlock._prepare_condition_removal_tree(
                self,
                condition_owner=None,
                expire=expire,
                parent_event=parent_event,
                prepared=prepared,
                visited=set(),
            )
        finally:
            self._removal_operation = prior_operation
            self._removal_previous_positions = prior_positions
        if canceled is not None:
            BaseBlock._cancel_prepared_condition_removals(prepared, canceled)
            return False
        BaseBlock._commit_prepared_condition_removals(prepared)
        return True

    def deactivate(
        self,
        *,
        expire: bool = False,
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Settle owned descendants and mechanics before the terminal."""
        return self._remove_spatial_graph(
            expire=expire,
            parent_event=parent_event,
            operation=SpatialEffectChangeOperation.REMOVED,
        )

    def _deactivate(
        self,
        *,
        expire: bool = False,
        parent_event: Optional[Event] = None,
        operation: SpatialEffectChangeOperation,
        previous_positions: Optional[Set[Tuple[int, int]]] = None,
        allow_detached: bool = False,
    ) -> bool:
        """Run the one removal lifecycle for ordinary or transformed exit."""
        return self._remove_spatial_graph(
            expire=expire,
            parent_event=parent_event,
            operation=operation,
            previous_positions=previous_positions,
            allow_detached=allow_detached,
        )

    def progress_spatial_duration(
        self,
        *,
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Advance inherited duration and deactivate on expiry."""
        if not self.progress():
            return False
        return self.deactivate(expire=True, parent_event=parent_event)

    def schedule_retirement(self, rounds: int) -> None:
        """Shorten the inherited round duration when the deadline is earlier."""
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


class AreaCondition(SpatialCondition):
    """Shared geometry and cell mechanics owned by one spatial condition."""

    zone_shape: str = Field(default="sphere")
    zone_radius_feet: int = Field(default=20, ge=0)
    zone_width_feet: int = Field(default=5, ge=5)
    zone_direction: Optional[Tuple[int, int]] = None
    adds_difficult_terrain: bool = False
    sets_light_level: Optional[LightLevel] = None
    light_is_cap: bool = False

    _terrain_modifiers: Dict[Tuple[int, int], Tuple[UUID, UUID]] = PrivateAttr(
        default_factory=dict,
    )
    _light_positions: Set[Tuple[int, int]] = PrivateAttr(default_factory=set)
    _last_trigger_turn_by_target: Dict[UUID, UUID] = PrivateAttr(
        default_factory=dict,
    )

    def _compute_affected_positions(self) -> Set[Tuple[int, int]]:
        """Compute the objective authored geometry around the anchor."""
        if self.zone_shape in {"cone", "line"}:
            if self.zone_direction is None:
                raise ValueError(
                    f"{self.zone_shape} area conditions require a direction",
                )
            target = (
                self.position[0] + self.zone_direction[0],
                self.position[1] + self.zone_direction[1],
            )
            shape = (
                Cone(
                    source_entity_uuid=self.source_entity_uuid,
                    target=target,
                    length_feet=self.zone_radius_feet,
                )
                if self.zone_shape == "cone"
                else Line(
                    source_entity_uuid=self.source_entity_uuid,
                    target=target,
                    length_feet=self.zone_radius_feet,
                    width_feet=self.zone_width_feet,
                )
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
        elif self.zone_shape == "sphere":
            shape = Sphere(
                source_entity_uuid=self.source_entity_uuid,
                target=self.position,
                radius_feet=self.zone_radius_feet,
            )
        else:
            raise ValueError(f"Unsupported area shape: {self.zone_shape}")
        shape.compute_objective(self.position)
        return set(shape.affected_positions)

    def resolve_condition_footprint(self) -> Set[Tuple[int, int]]:
        """Resolve authored geometry, map bounds, and spell protection."""
        grid = get_map()
        computed = (
            set(self.affected_positions)
            if self.affected_positions
            else self._compute_affected_positions()
        )
        positions = {
            position for position in computed if grid.has_tile(*position)
        }
        spell_level = self._protection_spell_level()
        source = Entity.get(self.source_entity_uuid)
        if spell_level is not None and self.magical_origin and source is not None:
            positions -= SpellProtectionRegistry.get_excluded_positions(
                source.position,
                spell_level,
            )
        return positions

    def move_zone(
        self,
        position: Tuple[int, int],
        *,
        parent_event: Event,
    ) -> bool:
        """Move an independently movable area and recompute its geometry."""
        if not self.is_active_spatial_condition() or position == self.position:
            return False
        previous_position = self.position
        self.position = position
        try:
            grid = get_map()
            positions = {
                cell
                for cell in self._compute_affected_positions()
                if grid.has_tile(*cell)
            }
            spell_level = self._protection_spell_level()
            source = Entity.get(self.source_entity_uuid)
            if (
                spell_level is not None
                and self.magical_origin
                and source is not None
            ):
                positions -= SpellProtectionRegistry.get_excluded_positions(
                    source.position,
                    spell_level,
                )
            return self.change_footprint(positions, parent_event=parent_event)
        except BaseException:
            self.position = previous_position
            raise

    def _protection_spell_level(self) -> Optional[int]:
        """Return the base spell level used by existing globe protection."""
        if (
            self.effect_origin is None
            or self.effect_origin.kind is not EffectOriginKind.SPELL
        ):
            return None
        return self.effect_origin.base_spell_level

    def _create_zone_entry_handler(self) -> EventHandler:
        raise NotImplementedError

    def _create_zone_exit_handler(self) -> EventHandler:
        raise NotImplementedError

    def _create_zone_turn_start_handler(self) -> EventHandler:
        raise NotImplementedError

    def _create_zone_turn_end_handler(self) -> EventHandler:
        raise NotImplementedError

    def _apply_appearance_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        del entity, parent_event
        raise NotImplementedError

    def _apply_effect_entry_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        del entity, parent_event
        raise NotImplementedError

    def _apply_effect_exit_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        del entity, parent_event
        raise NotImplementedError

    def _admit_trigger(
        self,
        kind: SpatialEffectTriggerKind,
        target_entity_uuid: UUID,
        event: Event,
    ) -> bool:
        """Apply the exact first-per-turn fence declared by this condition."""
        if kind not in self.first_per_turn_trigger_kinds:
            return True
        turn_execution_id = event.turn_execution_id
        if turn_execution_id is None:
            return True
        if self._last_trigger_turn_by_target.get(target_entity_uuid) == turn_execution_id:
            return False
        self._last_trigger_turn_by_target[target_entity_uuid] = turn_execution_id
        return True

    def _wrap_trigger_admission(
        self,
        processor: Callable[[Event, UUID], Optional[Event]],
        kind: SpatialEffectTriggerKind,
    ) -> Callable[[Event, UUID], Optional[Event]]:
        """Fence one existing handler without adding another dispatch path."""
        def admitted(event: Event, source_uuid: UUID) -> Optional[Event]:
            target_uuid = (
                event.entity_uuid
                if isinstance(event, (SpatialChangeEvent, TurnEvent))
                else event.target_entity_uuid
            )
            if target_uuid is None or not self._admit_trigger(
                kind,
                target_uuid,
                event,
            ):
                return None
            return processor(event, source_uuid)

        return admitted

    def _install_declared_handlers(
        self,
    ) -> Tuple[List[UUID], List[UUID]]:
        """Install one existing EventQueue handler for each declared trigger."""
        event_handlers: List[UUID] = []
        spatial_handlers: List[UUID] = []
        declarations = (
            (
                SpatialEffectTriggerKind.ENTER,
                self._create_zone_entry_handler,
                EventType.SPATIAL_ENTITY_ENTERED,
                True,
            ),
            (
                SpatialEffectTriggerKind.LEAVE,
                self._create_zone_exit_handler,
                EventType.SPATIAL_ENTITY_LEFT,
                True,
            ),
            (
                SpatialEffectTriggerKind.TURN_START,
                self._create_zone_turn_start_handler,
                EventType.TURN_START,
                False,
            ),
            (
                SpatialEffectTriggerKind.TURN_END,
                self._create_zone_turn_end_handler,
                EventType.TURN_END,
                False,
            ),
        )
        for kind, build_handler, event_type, positional in declarations:
            if kind not in self.trigger_kinds:
                continue
            handler = build_handler()
            handler.event_processor = self._wrap_trigger_admission(
                handler.event_processor,
                kind,
            )
            if positional:
                EventQueue.add_spatial_handler(
                    handler,
                    set(self.affected_positions),
                    event_type,
                    EventPhase.EFFECT,
                )
                spatial_handlers.append(handler.uuid)
            else:
                EventQueue.add_event_handler(handler)
                event_handlers.append(handler.uuid)
        return event_handlers, spatial_handlers

    def _apply_terrain_positions(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Optional[Event],
    ) -> List[Tuple[UUID, UUID]]:
        """Apply one owned walking-cost modifier per admitted position."""
        if not self.adds_difficult_terrain:
            return []
        grid = get_map()
        owned: List[Tuple[UUID, UUID]] = []
        for position in sorted(positions):
            if position in self._terrain_modifiers:
                continue
            tile = grid.get_tile(*position)
            if tile is None:
                continue
            before = tile.get_movement_cost(MovementMode.WALKING)
            modifier = NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid,
                name=f"{self.name} Difficult Terrain",
                value=1,
            )
            modifier_uuid = tile.walking_cost.self_static.add_value_modifier(
                modifier,
            )
            row = (tile.walking_cost.uuid, modifier_uuid)
            self._terrain_modifiers[position] = row
            owned.append(row)
            if tile.get_movement_cost(MovementMode.WALKING) != before:
                grid.invalidate_spatial_caches({"movement"})
                grid.publish_tile_mechanics_changed(
                    position,
                    source_entity_uuid=self.source_entity_uuid,
                    parent_event=(
                        parent_event.uuid if parent_event is not None else None
                    ),
                )
        return owned

    def _remove_terrain_positions(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Optional[Event],
    ) -> None:
        """Remove exactly this condition's walking-cost modifiers."""
        grid = get_map()
        for position in sorted(positions):
            row = self._terrain_modifiers.pop(position, None)
            if row is None:
                continue
            value_uuid, modifier_uuid = row
            tile = grid.get_tile(*position)
            before = (
                tile.get_movement_cost(MovementMode.WALKING)
                if tile is not None
                else None
            )
            value = ModifiableValue.get(value_uuid)
            if value is not None:
                value.remove_modifier(modifier_uuid)
            tracked = self.modifers_uuids.get(value_uuid)
            if tracked is not None:
                self.modifers_uuids[value_uuid] = [
                    uuid for uuid in tracked if uuid != modifier_uuid
                ]
                if not self.modifers_uuids[value_uuid]:
                    self.modifers_uuids.pop(value_uuid)
            if (
                tile is not None
                and before != tile.get_movement_cost(MovementMode.WALKING)
            ):
                grid.invalidate_spatial_caches({"movement"})
                grid.publish_tile_mechanics_changed(
                    position,
                    source_entity_uuid=self.source_entity_uuid,
                    parent_event=(
                        parent_event.uuid if parent_event is not None else None
                    ),
                )

    def _apply_light_positions(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Optional[Event],
    ) -> None:
        """Apply one source-owned objective light contribution."""
        if self.sets_light_level is None:
            return
        get_map().apply_light_modifier(
            self.uuid,
            set(positions),
            self.sets_light_level,
            cap=self.light_is_cap,
            parent_event=(parent_event.uuid if parent_event is not None else None),
        )
        self._light_positions.update(positions)

    def _remove_light_positions(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Optional[Event],
    ) -> None:
        """Remove this condition's objective light contribution."""
        owned = set(positions) & self._light_positions
        if not owned:
            return
        get_map().remove_light_modifier(
            self.uuid,
            owned,
            parent_event=(parent_event.uuid if parent_event is not None else None),
        )
        self._light_positions -= owned

    def _occupants_at(self, positions: Set[Tuple[int, int]]) -> List[Entity]:
        """Resolve each deployed occupant once in deterministic order."""
        grid = get_map()
        entity_uuids = {
            entity_uuid
            for position in positions
            for entity_uuid in grid.get_entities_at(position)
        }
        return [
            entity
            for entity_uuid in sorted(entity_uuids, key=str)
            if isinstance(entity := Entity.get(entity_uuid), Entity)
        ]

    def _apply(
        self,
        execution_event: Event,
    ) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Event]:
        """Install footprint, handlers, and cell mechanics under one owner."""
        modifiers, event_handlers, children, spatial_handlers, effect = super()._apply(
            execution_event,
        )
        added_event_handlers, added_spatial_handlers = self._install_declared_handlers()
        event_handlers.extend(added_event_handlers)
        spatial_handlers.extend(added_spatial_handlers)
        modifiers.extend(
            self._apply_terrain_positions(
                set(self.affected_positions),
                parent_event=effect,
            ),
        )
        self._apply_light_positions(
            set(self.affected_positions),
            parent_event=effect,
        )
        if SpatialEffectTriggerKind.APPEAR in self.trigger_kinds:
            for entity in self._occupants_at(set(self.affected_positions)):
                if self._admit_trigger(
                    SpatialEffectTriggerKind.APPEAR,
                    entity.uuid,
                    effect,
                ):
                    self._apply_appearance_effect(entity, parent_event=effect)
        return modifiers, event_handlers, children, spatial_handlers, effect

    def _change_footprint(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> Optional[SpatialEffectChangeEvent]:
        """Move area mechanics and return the open footprint-change effect."""
        if not self.is_active_spatial_condition():
            return None
        normalized = set(positions)
        previous = set(self.affected_positions)
        if normalized == previous:
            return None
        grid = get_map()
        grid.validate_spatial_condition_positions(
            condition=self,
            layer=self.layer,
            occupancy_policy=self.occupancy_policy,
            positions=normalized,
        )
        change_effect = self._open_change(
            SpatialEffectChangeOperation.FOOTPRINT_CHANGED,
            previous_positions=previous,
            affected_positions=normalized,
            parent_event=parent_event,
        )
        removed = previous - normalized
        added = normalized - previous
        if SpatialEffectTriggerKind.EFFECT_LEAVES_OCCUPANT in self.trigger_kinds:
            for entity in self._occupants_at(removed):
                self._apply_effect_exit_effect(
                    entity,
                    parent_event=change_effect,
                )
        self._remove_terrain_positions(removed, parent_event=change_effect)
        self._remove_light_positions(removed, parent_event=change_effect)
        grid.set_spatial_condition_positions(
            condition=self,
            layer=self.layer,
            occupancy_policy=self.occupancy_policy,
            positions=normalized,
        )
        self.affected_positions = normalized
        for handler_uuid in self.spatial_handler_uuids:
            EventQueue.update_spatial_handler_positions(handler_uuid, normalized)
        new_modifiers = self._apply_terrain_positions(
            added,
            parent_event=change_effect,
        )
        for value_uuid, modifier_uuid in new_modifiers:
            self.modifers_uuids.setdefault(value_uuid, []).append(modifier_uuid)
        self._apply_light_positions(added, parent_event=change_effect)
        if SpatialEffectTriggerKind.EFFECT_ENTERS_OCCUPANT in self.trigger_kinds:
            for entity in self._occupants_at(added):
                if self._admit_trigger(
                    SpatialEffectTriggerKind.EFFECT_ENTERS_OCCUPANT,
                    entity.uuid,
                    change_effect,
                ):
                    self._apply_effect_entry_effect(
                        entity,
                        parent_event=change_effect,
                    )
        grid.invalidate_spatial_caches({"movement", "optical", "propagation"})
        return change_effect

    def _release_positions(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Release exact terrain and light mechanics after displacement."""
        self._remove_terrain_positions(positions, parent_event=parent_event)
        self._remove_light_positions(positions, parent_event=parent_event)

    def _release_owned_runtime_state(
        self,
        *,
        parent_event: Optional[Event] = None,
    ) -> None:
        """Release cell mechanics, then the authoritative footprint."""
        self._remove_terrain_positions(
            set(self._terrain_modifiers),
            parent_event=parent_event,
        )
        self._remove_light_positions(
            set(self._light_positions),
            parent_event=parent_event,
        )
        super()._release_owned_runtime_state(parent_event=parent_event)
