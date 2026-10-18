"""Independent spatial conditions and reusable area mechanics."""

from typing import Callable, ClassVar, Dict, FrozenSet, List, Optional, Set, Tuple
from uuid import UUID
from dataclasses import dataclass, field

from pydantic import Field, PrivateAttr, StrictInt, model_validator

from dnd.core.base_block import BaseBlock, LightLevel, MovementMode, PreparedConditionRemovals
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.condition_types import DurationType, HazardFilter
from dnd.core.item_types import ItemIntegrity
from dnd.core.content.identities import ContentRef
from dnd.core.effect_types import EffectOriginKind
from dnd.types.event_facts import GroupEntryKind
from dnd.types.event_facts import HandlerGroupDispatch, KeyedTileChange
from dnd.core.events import (
    EffectApplicationEvent,
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
from dnd.core.gridmap import CrossingChannel, get_map
from dnd.core.aoe import AoEShape, Sphere, objective_footprint
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import ModifiableValue, Channel, Kind, add_modifier, remove_modifier
from dnd.entity import Entity
from dnd.types.senses import OpticalObscurement, PerceivedSpatialEffect
from dnd.types.material_deposits import MaterialDepositSource
from dnd.types.traps import TrapState
from dnd.types.world import OccupancyLayer, SpatialChannel, WorldEdgeChannel, edge_revision_channels
from dnd.core.base_object import empty_frozenset, empty_set
from dnd.types.spatial_effects import (
    SpatialEffectAnchorKind,
    SpatialEffectBlockingPolicy,
    SpatialEffectChangeOperation,
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
)


@dataclass
class SpatialRemovalPublication:
    effect: SpatialEffectChangeEvent
    condition_effect: Event
    tile_changes: list[SpatialChangeEvent] = field(default_factory=list)
    light_changes: list[SpatialChangeEvent] = field(default_factory=list)
    published: bool = False


class SpatialCondition(BaseCondition):
    """One condition that directly owns its world footprint and mechanics."""

    # None keeps arbitrary crossing predicates global. A declared channel set
    # promises that only segments touching the committed footprint can block.
    # Families whose predicate stays the base's (blocks nothing) declare an empty
    # set, so their presence does not push every optical ray onto the global path.
    crossing_channels: ClassVar[frozenset[CrossingChannel] | None] = None

    name: str = Field(default="Spatial Condition")
    content_ref: ContentRef = Field(
        description="Exact authored identity of this spatial condition.",
    )
    faction: Optional[str] = Field(default=None)
    position: Tuple[StrictInt, StrictInt] = Field(
        description="Authoritative anchor position.",
    )
    affected_positions: Set[Tuple[int, int]] = Field(default_factory=empty_set)
    observation_revision: int = Field(default=0, ge=0, exclude=True)
    layer: SpatialEffectLayer
    occupancy_policy: SpatialEffectOccupancyPolicy
    anchor_kind: SpatialEffectAnchorKind = SpatialEffectAnchorKind.FIXED_POSITION
    anchor_uuid: Optional[UUID] = None
    blocking_policy: SpatialEffectBlockingPolicy = SpatialEffectBlockingPolicy.NONE
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=empty_frozenset,
    )
    first_per_turn_trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=empty_frozenset,
    )
    arbitration_potency: int = Field(default=0, ge=0)
    optical_obscurement: Optional[OpticalObscurement] = None
    blocks_physical_optics: bool = False
    blocks_sound: bool = False
    has_visible_presence: bool = False
    minimum_walking_cost: int = Field(default=1,ge=1)
    movement_expenditure_extra: float = Field(default=0, ge=0,
        description="Owned movement expenditure independent of difficult-terrain immunity.")
    _removal_publication: SpatialRemovalPublication | None = PrivateAttr(default=None)

    def movement_extra_cost_at(self, position: Tuple[int, int], mode: MovementMode) -> float:
        return (self.movement_expenditure_extra
                if position in self.affected_positions and self.allows_contribution_at(position)
                and mode is not MovementMode.BURROWING else 0)
    deposit_source: MaterialDepositSource | None = None

    def blocks_crossing_between(self, start: Tuple[int, int], end: Tuple[int, int],
                                channel: CrossingChannel, requester_uuid: Optional[UUID],
                                mode: MovementMode, terminal_provider_uuid: Optional[UUID] = None) -> bool:
        return False

    def missile_deflection_contact(self, start: Tuple[int, int], end: Tuple[int, int],
                                   missile_size: str) -> Tuple[float, float] | None:
        return None

    def spatial_channels(self) -> frozenset[SpatialChannel]:
        """Return the world channels whose derived state this condition's membership changes.

        Derived from the fields the GridMap-facing methods of this class read,
        including the structural channels declared for its crossing rule. A
        subclass overriding one of those methods adds what its override reads.
        Terrain modifiers and light contributions bump their own channels.
        """
        channels: Set[SpatialChannel] = set()
        if (self.blocking_policy is not SpatialEffectBlockingPolicy.NONE
                or self.movement_expenditure_extra
                or self.hazard_filter is not None):
            channels.add(SpatialChannel.MOVEMENT)
        if self.blocks_physical_optics:
            channels.add(SpatialChannel.OPTICAL)
        if self.optical_obscurement is not None:
            channels.add(SpatialChannel.OBSCUREMENT)
        declared = self.crossing_channels or frozenset()
        channels.update(edge_revision_channels(channel for channel in WorldEdgeChannel if channel in declared))
        return frozenset(channels)

    _activation_positions: Optional[Set[Tuple[int, int]]] = PrivateAttr(
        default=None,
    )
    _displaced_footprints: Dict[
        UUID,
        Tuple[Set[Tuple[int, int]], Set[Tuple[int, int]]],
    ] = PrivateAttr(default={})
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
        if self.blocks_physical_optics and self.anchor_kind is SpatialEffectAnchorKind.ENTITY:
            # A creature's presence changes do not re-light (GridMap.commit_entity_presence).
            raise ValueError("An Entity-anchored spatial condition cannot block physical optics")
        if not self.first_per_turn_trigger_kinds.issubset(self.trigger_kinds):
            raise ValueError(
                "first-per-turn triggers must be declared trigger kinds",
            )
        return self

    def get_position(self) -> Tuple[int, int]:
        """Return the condition anchor."""
        return self.position

    def get_spatial_observation(
        self, positions: Set[Tuple[int, int]], *, observer_uuid: UUID,
        discovered: bool = False,
    ) -> Optional[PerceivedSpatialEffect]:
        """Expose an authored visible presence only in already observed cells."""
        if not self.has_visible_presence:
            return None
        if not discovered and not self.is_hazard_perceived_by(observer_uuid):
            return None
        observer = Entity.get(observer_uuid)
        contact = observer.senses.entities.get(self.anchor_uuid) if observer is not None and self.anchor_uuid is not None else None
        return PerceivedSpatialEffect(
            content_ref=self.content_ref, name=self.name, description=self.description,
            positions=tuple(sorted(positions)),
            apparent_presence=self.condition_stealth_dc is None,
            anchor_position=self.position if self.position in positions else None,
            anchor_elevation_steps=get_map().get_support_elevation_feet(self.position)//5 if self.position in positions else None,
            anchor_item_uuid=(self.anchor_uuid if self.anchor_kind is SpatialEffectAnchorKind.WORLD_OBJECT
                and observer is not None and self.anchor_uuid in observer.senses.objects else None),
            anchor_entity_uuid=(self.anchor_uuid if self.anchor_kind is SpatialEffectAnchorKind.ENTITY
                and (self.anchor_uuid == observer_uuid or contact is not None and contact.visual) else None),
            deposit_source=self.deposit_source,
        )

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

    def contributions_active(self) -> bool:
        if not super().contributions_active():
            return False
        anchor = BaseBlock.get(self.anchor_uuid) if self.anchor_uuid else None
        return not (isinstance(anchor, Entity) and anchor.is_spatially_suspended)


    def is_active_spatial_condition(self) -> bool:
        """Verify activity against the authoritative map collection."""
        return get_map().get_spatial_condition(self.uuid) is self

    def optical_obscurement_value(self) -> Optional[OpticalObscurement]:
        """This condition's optical contribution over its committed, unsuppressed footprint
        (GridMap writes it as the condition's obscurement layer; it counts while active)."""
        return self.optical_obscurement

    def blocks_physical_optics_at(self, position: Tuple[int, int]) -> bool:
        """Return whether this condition physically blocks optics here."""
        return self.blocks_physical_optics and position in self.affected_positions and self.allows_contribution_at(position)

    def blocks_walking_at(
        self,
        position: Tuple[int, int],
        requesting_entity_uuid: Optional[UUID] = None,
        mode: MovementMode = MovementMode.WALKING,
    ) -> bool:
        """Apply the condition's explicit traversal-blocking policy."""
        del requesting_entity_uuid, mode
        if not self.allows_contribution_at(position):
            return False
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

    def is_hazardous_for(
        self, entity_uuid: Optional[UUID] = None, *,
        occupancy_layer: OccupancyLayer = OccupancyLayer.GROUND,
    ) -> bool:
        """Resolve the inherited hazard filter for one entity."""
        if self.hazard_filter is None or not self.affects_occupancy_layer(occupancy_layer):
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
        if application_effect.canceled:
            return [], [], [], [], application_effect
        change_effect = self._open_change(
            SpatialEffectChangeOperation.CREATED,
            previous_positions=set(),
            affected_positions=set(self._activation_positions or ()),
            parent_event=application_effect,
        )
        self._commit_activation_footprint(change_effect)
        event_handler_uuids: list[UUID] = []
        for anchor_handler in self._create_anchor_handlers():
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
                # Latest wins: a different material yields its cells; only a
                # stronger matching material keeps them.
                if (incumbent.content_ref == self.content_ref
                        and incumbent.material_arbitration_rank() > incoming_rank):
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

    def _commit_activation_footprint(self, parent_event: Event) -> None:
        """Swap preflighted Tile membership before installing mechanics."""
        self._removal_publication = None
        if self._activation_positions is None:
            raise RuntimeError("Spatial condition has no prepared footprint")
        self._commit_displaced_footprints()
        self._commit_footprint(set(self._activation_positions))

    def _commit_footprint(self, positions: Set[Tuple[int, int]]) -> None:
        """Own the new footprint, then commit its Tile membership.

        The map invalidates (and re-lights) at the membership commit, and this
        condition's per-cell answers read ``affected_positions``, so the field
        is written first: nothing the commit recomputes may see the old one.
        """
        previous = self.affected_positions
        self.affected_positions = set(positions)
        try:
            get_map().set_spatial_condition_positions(
                condition=self,
                crossing_channels=self.crossing_channels,
                layer=self.layer,
                occupancy_policy=self.occupancy_policy,
                positions=set(positions),
            )
        except BaseException:
            self.affected_positions = previous
            raise

    def _commit_displaced_footprints(self) -> None:
        """Shrink the Tile membership of every incumbent this footprint displaces."""
        grid = get_map()
        for incumbent_uuid in sorted(self._displaced_footprints, key=str):
            incumbent = grid.get_spatial_condition(incumbent_uuid)
            if not isinstance(incumbent, SpatialCondition):
                raise RuntimeError("Admitted incumbent disappeared")
            _, remaining = self._displaced_footprints[incumbent_uuid]
            incumbent.affected_positions = set(remaining)
            incumbent.observation_revision += 1
            if remaining:
                grid.set_spatial_condition_positions(
                    condition=incumbent,
                    crossing_channels=incumbent.crossing_channels,
                    layer=incumbent.layer,
                    occupancy_policy=incumbent.occupancy_policy,
                    positions=set(remaining),
                )
            else:
                grid.remove_spatial_condition(incumbent.uuid)

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
            incumbent.observation_revision += 1
            grid.set_spatial_condition_positions(
                condition=incumbent,
                crossing_channels=incumbent.crossing_channels,
                layer=incumbent.layer,
                occupancy_policy=incumbent.occupancy_policy,
                positions=set(original),
            )
        self._displaced_footprints.clear()

    def _create_anchor_handlers(self) -> List[EventHandler]:
        """Bind an attached condition to its anchor: losing it ends the condition
        at once; following its moves waits for the simultaneous group (phase B).
        """
        if self.anchor_kind not in {
            SpatialEffectAnchorKind.ENTITY,
            SpatialEffectAnchorKind.WORLD_OBJECT,
        }:
            return []
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

        def anchor_change(event: Event) -> Tuple[Optional[SpatialCondition], bool, Optional[Tuple[int, int]]]:
            """Return the condition, whether its anchor is lost, and where it moved."""
            condition = BaseCondition.get(condition_uuid)
            if not isinstance(condition, SpatialCondition) or not isinstance(event, SpatialChangeEvent):
                return None, False, None
            if anchor_kind is SpatialEffectAnchorKind.ENTITY:
                if event.entity_uuid != anchor_uuid:
                    return None, False, None
                if event.event_type is EventType.SPATIAL_ENTITY_ENTERED:
                    return condition, False, event.position
                anchor = Entity.get(anchor_uuid)
                lost = event.old_position is None and (anchor is None or not anchor.is_spatially_suspended)
                return condition, lost, None
            if event.object_uuid != anchor_uuid:
                return None, False, None
            if (event.event_type is EventType.SPATIAL_OBJECT_REMOVED
                    or event.object_state is not None
                    and event.object_state.integrity is ItemIntegrity.DESTROYED
                    and condition.requires_intact_item):
                return condition, True, None
            return condition, False, event.placement.position if event.placement is not None else None

        def end_with_anchor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            condition, lost, _ = anchor_change(event)
            if condition is not None and lost:
                condition.deactivate(parent_event=event)
            return None

        def move_with_anchor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            condition, lost, position = anchor_change(event)
            if condition is not None and not lost and position is not None:
                condition.relocate_anchor(position, parent_event=event)
            return None

        triggers = [Trigger(event_type=event_type, event_phase=EventPhase.EFFECT) for event_type in event_types]
        return [
            EventHandler(name=f"{self.name} Anchor Loss", runs_while_owner_inactive=True,
                source_entity_uuid=self.source_entity_uuid, trigger_conditions=list(triggers),
                event_processor=end_with_anchor),
            EventHandler(name=f"{self.name} Anchor Movement", group_dispatch=HandlerGroupDispatch.AFTER_GROUP,
                runs_while_owner_inactive=True, source_entity_uuid=self.source_entity_uuid,
                trigger_conditions=list(triggers), event_processor=move_with_anchor),
        ]

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
        self.observation_revision += 1
        try:
            return self.change_footprint(
                translated or {position},
                parent_event=parent_event,
            )
        except BaseException:
            self.position = previous_anchor
            self.observation_revision += 1
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
        # The install's terrain, light and displacements are one simultaneous
        # group; its own change completes after observers settled (plan §5.2-5.4).
        with EventQueue.group(GroupEntryKind.ZONE_INSTALL, root=parent_event, shares_damage_rolls=True) as group:
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
            group.completes_after.add(effect.lineage_uuid)
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
        begun = self._begin_footprint_change(positions, parent_event=parent_event)
        if begun is None:
            return None
        _, normalized, change_effect = begun
        self._commit_footprint(normalized)
        self.observation_revision += 1
        for handler_uuid in self.spatial_handler_uuids:
            EventQueue.update_spatial_handler_positions(
                handler_uuid,
                normalized,
            )
        return change_effect

    def _begin_footprint_change(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> Optional[Tuple[Set[Tuple[int, int]], Set[Tuple[int, int]], SpatialEffectChangeEvent]]:
        """Arbitrate a moved footprint exactly like activation (latest wins).

        Displaced incumbents are shrunk and settled under the opened change;
        returns (previous, admitted, change effect), or None when nothing moves.
        """
        if not self.is_active_spatial_condition():
            return None
        previous = set(self.affected_positions)
        normalized = self._resolve_activation_admission(set(positions), None)
        if not normalized:
            self._displaced_footprints.clear()
            self.deactivate(parent_event=parent_event)
            return None
        if normalized == previous:
            self._displaced_footprints.clear()
            return None
        change_effect = self._open_change(
            SpatialEffectChangeOperation.FOOTPRINT_CHANGED,
            previous_positions=previous,
            affected_positions=normalized,
            parent_event=parent_event,
        )
        self._commit_displaced_footprints()
        self._finalize_displacements(parent_event=change_effect)
        return previous, normalized, change_effect

    def change_footprint(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> bool:
        """Replace the footprint and close its change after all mechanics."""
        with EventQueue.group(GroupEntryKind.ZONE_MOVE, root=parent_event, shares_damage_rolls=True) as group:
            change_effect = self._change_footprint(
                positions,
                parent_event=parent_event,
            )
            if change_effect is not None:
                group.completes_after.add(change_effect.lineage_uuid)
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
        trap_state: Optional[TrapState] = None,
        previous_trap_state: Optional[TrapState] = None,
        pressed: Optional[bool] = None,
        previous_pressed: Optional[bool] = None,
        publish: bool = True,
    ) -> SpatialEffectChangeEvent:
        """Publish the non-vetoable phases that directly cause a spatial change."""
        if operation is not SpatialEffectChangeOperation.FOOTPRINT_CHANGED:
            self.observation_revision += 1
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
            trap_state=trap_state,
            previous_trap_state=previous_trap_state,
            pressed=pressed, previous_pressed=previous_pressed,
            layer=self.layer,
            anchor_position=self.position,
            affected_positions=tuple(sorted(affected_positions)),
            previous_positions=tuple(sorted(previous_positions)),
        )
        if not publish:
            return declaration.model_copy(update={"phase": EventPhase.EFFECT})
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
        """Release the authoritative footprint during cleanup or rollback.

        Light it shadowed is re-lit by the map; a removal publishes that light
        fact with its own facts, after the observers settled them.
        """
        grid = get_map()
        if not grid.has_spatial_condition(self.uuid):
            return
        publication = self._removal_publication
        light = grid.remove_spatial_condition(
            self.uuid, parent_event=parent_event.uuid if parent_event is not None else None,
            publish_light=publication is None)
        if light is not None and publication is not None:
            publication.light_changes.append(light)

    def discard_from_runtime_owner(self) -> bool:
        """Discard an uncommitted independently owned condition."""
        self.discard_uncommitted_runtime_state()
        for child_uuid in list(self.sub_conditions):
            child = BaseCondition.get(child_uuid)
            if isinstance(child, BaseCondition):
                owner = (BaseBlock.get(child.target_entity_uuid)
                         if child.target_entity_uuid is not None else None)
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
        publish: bool = True,
    ) -> bool:
        """Remove this independent owner, or commit its accepted removal."""
        if prepared_removal_effect is None:
            return self.deactivate(
                expire=expire,
                parent_event=parent_event,
            )
        if prepared_removal_effect.event_type is EventType.CONDITION_REMOVAL:
            condition_effect = prepared_removal_effect
            prepared_removal_effect = self._open_change(self._removal_operation,
                previous_positions=set(self.affected_positions), affected_positions=set(),
                parent_event=condition_effect, publish=False)
        elif isinstance(prepared_removal_effect, SpatialEffectChangeEvent):
            condition_effect = (EventQueue.get_event_by_uuid(prepared_removal_effect.parent_event)
                if prepared_removal_effect.parent_event is not None else None)
        else:
            raise TypeError("Prepared spatial removal must identify a condition or spatial removal")
        if (
            condition_effect is None
            or condition_effect.event_type is not EventType.CONDITION_REMOVAL
            or condition_effect.canceled
        ):
            raise RuntimeError(
                "Prepared spatial removal is missing its condition effect",
            )

        self._removal_publication = SpatialRemovalPublication(prepared_removal_effect, condition_effect)
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
                parent.unlink_condition(self.uuid, parent_event=removed)
            self.parent_link = None
        self.remove_from_register()
        if publish:
            self.publish_runtime_owner_removal(prepared_removal_effect)
        return True

    def publish_runtime_owner_removal(self, effect: Event) -> None:
        publication = self._removal_publication
        if publication is None or effect.uuid not in (publication.effect.uuid, publication.condition_effect.uuid):
            raise ValueError("Spatial removal publication does not match its commitment")
        if publication.published:
            return
        publication.published = True
        errors: list[BaseException] = []
        grid = get_map()
        # The released cells and lights are one instant; the removal's own
        # change completes after observers settled (plan §5.4).
        with EventQueue.group(GroupEntryKind.ZONE_REMOVE, root=publication.condition_effect) as group:
            group.completes_after.add(publication.effect.lineage_uuid)
            for change in (*publication.tile_changes, *publication.light_changes):
                try:
                    grid.publish_committed_spatial_event(change)
                except BaseException as error:
                    errors.append(error)
        try:
            self._complete_change(publication.effect)
        except BaseException as error:
            errors.append(error)
        try:
            publication.condition_effect.phase_to(EventPhase.COMPLETION)
        except BaseException as error:
            errors.append(error)
        if errors:
            raise BaseExceptionGroup("Committed spatial removal publication failed", errors)

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
        except BaseException as error:
            try:
                BaseBlock.cancel_owned_condition_removals(PreparedConditionRemovals(prepared),
                    "Spatial removal admission raised")
            except BaseException as cleanup_error:
                raise BaseExceptionGroup("Spatial removal and admission cleanup failed",
                    [error, cleanup_error]) from None
            raise
        finally:
            self._removal_operation = prior_operation
            self._removal_previous_positions = prior_positions
        if canceled is not None:
            BaseBlock._cancel_prepared_condition_removals(prepared, canceled)
            return False
        if not BaseBlock.validate_prepared_condition_removals(prepared):
            BaseBlock.cancel_owned_condition_removals(PreparedConditionRemovals(prepared),
                "Spatial removal destinations conflict or changed")
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

    def progress_duration_state(self, *, parent_event: Optional[Event] = None) -> bool:
        """Advance the native clock and publish a surviving owner's changed state."""
        before = self.snapshot_duration()
        expired = self.progress()
        if not expired and before != self.snapshot_duration():
            change = self._open_change(SpatialEffectChangeOperation.STATE_CHANGED,
                previous_positions=set(self.affected_positions), affected_positions=set(self.affected_positions),
                parent_event=parent_event)
            self._complete_change(change)
        return expired

    def progress_spatial_duration(self, *, parent_event: Optional[Event] = None) -> bool:
        """Advance inherited duration and deactivate on expiry."""
        if not self.progress_duration_state(parent_event=parent_event):
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
    crossing_channels: ClassVar[frozenset[CrossingChannel] | None] = frozenset()  # base predicate: blocks nothing

    area: AoEShape = Field(default=Sphere(radius_feet=20), description="The zone's area, aimed from its anchor.")
    area_aim_offset: Tuple[int, int] = Field(default=(0, 0),
        description="Aim relative to the anchor; the direction of a source-centered area.")
    adds_difficult_terrain: bool = False
    sets_light_level: Optional[LightLevel] = None
    light_is_cap: bool = False
    dims_light: bool = Field(default=False, description="Lowers its cells' light one level, never stacking.")

    _terrain_modifiers: Dict[Tuple[int, int], Tuple[UUID, UUID]] = PrivateAttr(
        default_factory=dict,
    )
    _light_positions: Set[Tuple[int, int]] = PrivateAttr(default=set())
    _last_trigger_turn_by_target: Dict[Tuple[UUID, SpatialEffectTriggerKind], UUID] = PrivateAttr(
        default_factory=dict,
    )

    def get_spatial_observation(
        self, positions: Set[Tuple[int, int]], *, observer_uuid: UUID,
        discovered: bool = False,
    ) -> Optional[PerceivedSpatialEffect]:
        """Retain disclosed geometry with the same visibility and discovery gate."""
        observed = super().get_spatial_observation(
            positions, observer_uuid=observer_uuid, discovered=discovered,
        )
        if observed is None:
            return None
        # Geometry registers an observed volume without claiming its center cell
        # is visible. Ground fields retain only a previously established frame.
        anchor = self.position if self.layer is not SpatialEffectLayer.GROUND_SURFACE else observed.anchor_position
        if anchor is None and self.anchor_kind is SpatialEffectAnchorKind.FIXED_POSITION:
            observer = Entity.get(observer_uuid)
            previous = observer.senses.spatial_effects.get(self.uuid) if observer is not None else None
            if previous is not None:
                return observed.model_copy(update={"area_geometry": previous.area_geometry,
                    "area_propagation": self.area.propagation,
                    "anchor_elevation_steps": previous.anchor_elevation_steps})
        geometry = (self.area.presentation_geometry(self.area_aim(anchor), anchor)
                    if anchor is not None else None)
        support = get_map().get_tile(*anchor) if anchor is not None else None
        return observed.model_copy(update={"area_geometry": geometry,
            "area_propagation": self.area.propagation,
            "anchor_elevation_steps": support.height if support is not None else None})

    def area_aim(self, anchor: Tuple[int, int]) -> Tuple[int, int]:
        """Return the zone's aim when its area is anchored at ``anchor``."""
        if self.area_aim_offset == (0, 0) and not self.area.emanates_from_aim():
            raise ValueError("cone/line area conditions require a direction")
        return (anchor[0] + self.area_aim_offset[0], anchor[1] + self.area_aim_offset[1])

    def area_footprint(self, anchor: Tuple[int, int]) -> FrozenSet[Tuple[int, int]]:
        """Return the objective footprint of the zone's area anchored at ``anchor``."""
        return objective_footprint(self.area, self.area_aim(anchor), anchor)

    def _compute_affected_positions(self) -> Set[Tuple[int, int]]:
        """Compute the objective authored geometry around the anchor."""
        return set(self.area_footprint(self.position))

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
        return self._apply_spell_protection(positions)

    def _apply_spell_protection(self, positions: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        """Resolve once, retaining the cause beside the resulting native cells."""
        spell_level = self._protection_spell_level()
        origin = self.effect_origin
        self.spatial_suppressions = ()
        if spell_level is not None and self.magical_origin and origin is not None and origin.source_position is not None:
            self.spatial_suppressions = SpellProtectionRegistry.get_suppressions(
                origin.source_position, spell_level, positions)
            for suppression in self.spatial_suppressions:
                positions.difference_update(suppression.positions)
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
        previous_suppressions = self.spatial_suppressions
        self.position = position
        self.observation_revision += 1
        try:
            grid = get_map()
            positions = {
                cell
                for cell in self._compute_affected_positions()
                if grid.has_tile(*cell)
            }
            positions = self._apply_spell_protection(positions)
            return self.change_footprint(positions, parent_event=parent_event)
        except BaseException:
            self.position = previous_position
            self.spatial_suppressions = previous_suppressions
            self.observation_revision += 1
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

    def get_trigger_positions(self, kind: SpatialEffectTriggerKind) -> Set[Tuple[int, int]]:
        """Return this trigger's subregion before its turn allowance is consumed."""
        return {position for position in self.affected_positions
            if kind in (SpatialEffectTriggerKind.LEAVE, SpatialEffectTriggerKind.EFFECT_LEAVES_OCCUPANT)
            or self.allows_contribution_at(position)}

    def _occupancy_admits_trigger(
        self,
        kind: SpatialEffectTriggerKind,
        target_entity_uuid: UUID,
        event: Event,
    ) -> bool:
        """Check spatial eligibility before membership or turn-fence changes."""
        if isinstance(event, SpatialChangeEvent) and kind in {
            SpatialEffectTriggerKind.ENTER, SpatialEffectTriggerKind.LEAVE,
        }:
            position = event.position
            return (position in self.get_trigger_positions(kind)
                    and self.admits_occupancy_transition(event))
        entity = Entity.get(target_entity_uuid)
        return (
            isinstance(entity, Entity)
            and entity.is_deployed
            and entity.position in self.get_trigger_positions(kind)
            and self.affects_occupancy_layer(entity.get_occupancy_layer())
        )

    def _admit_trigger(
        self,
        kind: SpatialEffectTriggerKind,
        target_entity_uuid: UUID,
        event: Event,
    ) -> bool:
        """Apply the exact first-per-turn fence declared by this condition."""
        if not self._occupancy_admits_trigger(kind, target_entity_uuid, event):
            return False
        if not self.admits_application(target_entity_uuid, event):
            return False
        if kind not in self.first_per_turn_trigger_kinds:
            return True
        turn_execution_id = event.turn_execution_id
        if turn_execution_id is None:
            return True
        # Arrival, start of turn and end of turn are separate SRD triggers, so
        # each has its own first-per-turn fence (bug C, human Q2).
        fence_kind = (kind if kind in (SpatialEffectTriggerKind.TURN_START, SpatialEffectTriggerKind.TURN_END)
            else SpatialEffectTriggerKind.ENTER)
        fence = (target_entity_uuid, fence_kind)
        if self._last_trigger_turn_by_target.get(fence) == turn_execution_id:
            return False
        self._last_trigger_turn_by_target[fence] = turn_execution_id
        return True

    def admits_application(self, target_entity_uuid: UUID, event: Event) -> bool:
        """Admit a recipient before any save or effect, independently of cadence."""
        if self.effect_origin is not None:
            admission = EventQueue.publish_declaration(EffectApplicationEvent(use_register=False, source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target_entity_uuid, parent_event=event.uuid,
                spatial_effect_uuid=self.uuid, source_position=self.position, target_position=Entity.get(target_entity_uuid).position,
                effect_origin=self.effect_origin.model_copy(update={"area_application":self.layer is SpatialEffectLayer.FIELD})))
            if admission.canceled:
                return False
            admission = admission.phase_to(EventPhase.EXECUTION)
            if admission.canceled:
                return False
            admission.phase_to(EventPhase.COMPLETION)
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
                    self.get_trigger_positions(kind),
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
        """Apply one owned walking-cost floor per admitted position.

        Difficult terrain is a floor of 2, never a +1: overlapping zones and
        naturally difficult ground don't stack (SRD; bug I).
        """
        minimum_cost = max(self.minimum_walking_cost, 2 if self.adds_difficult_terrain else 1)
        if minimum_cost == 1:
            return []
        grid = get_map()
        owned: List[Tuple[UUID, UUID]] = []
        changed: List[KeyedTileChange] = []
        for position in sorted(positions):
            if position in self._terrain_modifiers:
                continue
            tile = grid.get_tile(*position)
            if tile is None:
                continue
            before = tile.get_movement_cost(MovementMode.WALKING)
            if before <= 0:
                continue
            modifier = NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid,
                name=f"{self.name} Difficult Terrain",
                value=minimum_cost,
            )
            modifier.contribution_owner_uuid = self.uuid
            modifier.contribution_position = position
            value = tile.edit_movement_cost(MovementMode.WALKING)
            modifier_uuid = add_modifier(value, Channel.SELF_STATIC, Kind.MIN, modifier)
            row = (value.uuid, modifier_uuid)
            self._terrain_modifiers[position] = row
            owned.append(row)
            after = tile.get_movement_cost(MovementMode.WALKING)
            if after != before:
                changed.append(KeyedTileChange(position=position, fields={"walking_cost": after}))
        # One committed keyed traversal fact for the whole install (plan §5.5, Q4 (W)).
        grid.commit_tile_mechanics(changed, source_entity_uuid=self.source_entity_uuid,
            parent_event=parent_event.uuid if parent_event is not None else None)
        return owned

    def _remove_terrain_positions(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Optional[Event],
    ) -> None:
        """Remove exactly this condition's walking-cost modifiers."""
        grid = get_map()
        changed: List[KeyedTileChange] = []
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
                remove_modifier(value, modifier_uuid)
            tracked = self.modifers_uuids.get(value_uuid)
            if tracked is not None:
                self.modifers_uuids[value_uuid] = [
                    uuid for uuid in tracked if uuid != modifier_uuid
                ]
                if not self.modifers_uuids[value_uuid]:
                    self.modifers_uuids.pop(value_uuid)
            if tile is not None and before != (after := tile.get_movement_cost(MovementMode.WALKING)):
                changed.append(KeyedTileChange(position=position, fields={"walking_cost": after}))
        # One committed keyed traversal fact for the whole release; a removal
        # publication keeps it until the removal itself is published.
        deferred = self._removal_publication is not None
        change = grid.commit_tile_mechanics(changed, source_entity_uuid=self.source_entity_uuid,
            parent_event=parent_event.uuid if parent_event is not None else None, publish=not deferred)
        if deferred and change is not None:
            assert self._removal_publication is not None
            self._removal_publication.tile_changes.append(change)

    def _apply_light_positions(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Optional[Event],
    ) -> None:
        """Apply one source-owned objective light contribution."""
        if self.sets_light_level is None and not self.dims_light:
            return
        positions = {position for position in positions if self.allows_contribution_at(position)}
        parent_uuid = parent_event.uuid if parent_event is not None else None
        if self.sets_light_level is not None:
            get_map().apply_light_modifier(self.uuid, set(positions), self.sets_light_level,
                cap=self.light_is_cap, parent_event=parent_uuid)
        if self.dims_light:
            get_map().apply_light_dimmer(self.uuid, set(positions), parent_event=parent_uuid)
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
        grid = get_map()
        changed = grid.remove_light_modifier(
            self.uuid,
            owned,
            parent_event=(parent_event.uuid if parent_event is not None else None),
            publish=self._removal_publication is None,
        )
        if self._removal_publication is not None:
            change = grid.snapshot_light_change(list(changed),
                parent_event=parent_event.uuid if parent_event is not None else None)
            if change is not None:
                self._removal_publication.light_changes.append(change)
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
        begun = self._begin_footprint_change(positions, parent_event=parent_event)
        if begun is None:
            return None
        previous, normalized, change_effect = begun
        removed = previous - normalized
        added = normalized - previous
        if SpatialEffectTriggerKind.EFFECT_LEAVES_OCCUPANT in self.trigger_kinds:
            for entity in self._occupants_at(removed):
                if self._admit_trigger(
                    SpatialEffectTriggerKind.EFFECT_LEAVES_OCCUPANT,
                    entity.uuid,
                    change_effect,
                ):
                    self._apply_effect_exit_effect(
                        entity,
                        parent_event=change_effect,
                    )
        self._remove_terrain_positions(removed, parent_event=change_effect)
        self._commit_footprint(normalized)
        self.observation_revision += 1
        for handler_uuid in self.spatial_handler_uuids:
            EventQueue.update_spatial_handler_positions(handler_uuid, normalized)
        self._remove_light_positions(removed, parent_event=change_effect)
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
