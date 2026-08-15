"""Runtime owners for persistent ground, cloud, and field effects."""

from typing import ClassVar, Optional, Set, Tuple
from uuid import UUID

from pydantic import Field, PrivateAttr

from dnd.core.base_block import BaseBlock
from dnd.types.world import MovementMode
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.types.conditions import ConditionCategory, DurationType
from dnd.core.content.identities import ContentRef
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.core.events.world_events import (
    SpatialChangeEvent,
    SpatialEffectChangeEvent,
    SpatialEffectInteractionEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.spatial_effect_runtime import (
    SpatialEffectInteractionContext,
    apply_spatial_effect_interaction,
)
from dnd.types.spatial_effects import (
    SpatialEffectAnchorKind,
    SpatialEffectBlockingPolicy,
    SpatialEffectLayer,
    SpatialEffectChangeOperation,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
)


class SpatialEffectController(BaseCondition):
    """Typed mechanics controller installed on one spatial-effect owner."""

    name: str = Field(
        default="Spatial Effect Controller",
        description="Abstract spatial-effect controller name.",
    )
    description: str = Field(
        default="Owns the mechanics and lifetime of one persistent spatial effect.",
        description="Abstract spatial-effect controller description.",
    )
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=frozenset,
        description="Exact mechanical occupant moments implemented by this controller.",
    )
    first_per_turn_trigger_kinds: frozenset[
        SpatialEffectTriggerKind
    ] = Field(
        default_factory=frozenset,
        description=(
            "Trigger kinds admitted at most once per target in one encounter "
            "turn execution."
        ),
    )
    arbitration_potency: int = Field(
        default=0,
        ge=0,
        description=(
            "Rules-facing strength used only when exact matching materials "
            "compete for the same exclusive cell."
        ),
    )
    _installation_footprint_override: Optional[
        Set[Tuple[int, int]]
    ] = PrivateAttr(default=None)

    def resolve_effect_footprint(self) -> Set[Tuple[int, int]]:
        """Return the exact valid cells the controller intends to occupy."""
        raise NotImplementedError

    def rollback_failed_install(self) -> None:
        """Remove partial runtime leases after an exceptional installation."""
        return None

    def prepare_installation_footprint(
        self,
        positions: Set[Tuple[int, int]],
    ) -> None:
        """Freeze the overlap-resolved footprint consumed by controller apply."""
        self._installation_footprint_override = set(positions)

    def resolve_installation_footprint(self) -> Set[Tuple[int, int]]:
        """Return a prepared footprint once, otherwise resolve normally."""
        if self._installation_footprint_override is None:
            return self.resolve_effect_footprint()
        positions = set(self._installation_footprint_override)
        self._installation_footprint_override = None
        return positions

    def material_arbitration_rank(self) -> tuple[int, int]:
        """Rank exact matching material instances without display-name inference."""
        spell_level = (
            self.effect_origin.effective_spell_level
            if self.effect_origin is not None
            and self.effect_origin.effective_spell_level is not None
            else 0
        )
        return (self.arbitration_potency, spell_level)

    def transition_footprint(
        self,
        remaining_positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Remove controller-owned mechanics outside a transformed footprint."""
        raise NotImplementedError

    def apply_appearance_trigger(self, *, parent_event: Event) -> None:
        """Apply any explicitly authored effect-appearance consequences."""
        del parent_event

    def apply_effect_entry_trigger(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Apply consequences when the effect footprint moves onto occupants."""
        del positions, parent_event

    def relocate_anchor(
        self,
        position: Tuple[int, int],
        *,
        parent_event: Event,
    ) -> None:
        """Recenter controller mechanics after its attached anchor moves."""
        del position, parent_event
        raise NotImplementedError(
            f"{type(self).__name__} does not implement attached relocation",
        )


class SpatialEffectRetirementCountdown(BaseCondition):
    """Internal delayed removal admitted by an authored transition rule."""

    name: str = Field(default="Spatial Effect Retirement Countdown")
    description: str = Field(
        default="Retires its spatial-effect owner when this countdown expires.",
    )
    condition_category: ConditionCategory = ConditionCategory.INTERNAL


class SpatialEffect(BaseBlock):
    """Independent world owner for one persistent spatial phenomenon.

    A source entity remains causal attribution. It does not own this block's
    lifetime. The effect owns its controller condition and grid footprint.
    """

    content_ref: ContentRef = Field(
        description="Exact authored identity of this spatial phenomenon.",
    )
    anchor_kind: SpatialEffectAnchorKind = Field(
        default=SpatialEffectAnchorKind.FIXED_POSITION,
        description="Authored policy controlling how this footprint moves.",
    )
    anchor_uuid: Optional[UUID] = Field(
        default=None,
        description="Attached entity or world-object UUID when the policy requires one.",
    )
    layer: SpatialEffectLayer = Field(
        description="World layer occupied by this effect.",
    )
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        description="Overlap policy within the selected world layer.",
    )
    blocking_policy: SpatialEffectBlockingPolicy = Field(
        default=SpatialEffectBlockingPolicy.NONE,
        description="Exact footprint subset that physically blocks traversal.",
    )
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=frozenset,
        description="Exact occupant triggers authenticated by the content definition.",
    )
    first_per_turn_trigger_kinds: frozenset[
        SpatialEffectTriggerKind
    ] = Field(
        default_factory=frozenset,
        description="Authenticated trigger kinds fenced once per target and turn.",
    )
    affected_positions: Set[Tuple[int, int]] = Field(
        default_factory=set,
        description="Exact grid cells currently occupied by this effect.",
    )
    allow_events_conditions: bool = Field(
        default=True,
        description="Spatial effects own lifecycle conditions and handlers.",
    )

    _primary_controller_uuid: Optional[UUID] = PrivateAttr(default=None)
    _retiring: bool = PrivateAttr(default=False)
    _created_event_published: bool = PrivateAttr(default=False)
    _reveal_in_progress: bool = PrivateAttr(default=False)
    _interaction_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _anchor_handler_uuid: Optional[UUID] = PrivateAttr(default=None)
    _retirement_countdown_uuid: Optional[UUID] = PrivateAttr(default=None)
    _effect_registry: ClassVar[dict[UUID, "SpatialEffect"]] = {}

    def model_post_init(self, __context: object) -> None:
        """Register the independent effect identity."""
        attached = self.anchor_kind in {
            SpatialEffectAnchorKind.ENTITY,
            SpatialEffectAnchorKind.WORLD_OBJECT,
        }
        if attached is (self.anchor_uuid is None):
            raise ValueError(
                "Attached spatial effects require exactly one anchor UUID",
            )
        super().model_post_init(__context)
        self._effect_registry[self.uuid] = self

    def blocks_walking_at(
        self,
        position: Tuple[int, int],
        requesting_entity_uuid: Optional[UUID] = None,
        mode: MovementMode = MovementMode.WALKING,
    ) -> bool:
        """Apply the authored blocking policy to one indexed effect cell."""
        del requesting_entity_uuid, mode
        if self.blocking_policy is SpatialEffectBlockingPolicy.NONE:
            return False
        if self.blocking_policy is SpatialEffectBlockingPolicy.ANCHOR:
            return position == self.position
        return position in self.affected_positions

    @classmethod
    def get_effect(cls, effect_uuid: UUID) -> Optional["SpatialEffect"]:
        """Resolve an active spatial effect by encounter-local UUID."""
        return cls._effect_registry.get(effect_uuid)

    @classmethod
    def active_effects(cls) -> tuple["SpatialEffect", ...]:
        """Return active effects in deterministic UUID order."""
        return tuple(
            cls._effect_registry[effect_uuid]
            for effect_uuid in sorted(cls._effect_registry, key=str)
        )

    def install_controller(
        self,
        controller: SpatialEffectController,
        *,
        parent_event: Event,
    ) -> Optional[Event]:
        """Resolve material overlap, then atomically install one controller."""
        if self._primary_controller_uuid is not None:
            raise ValueError("SpatialEffect already has a primary controller")
        if controller.trigger_kinds != self.trigger_kinds:
            raise ValueError(
                "SpatialEffect controller triggers differ from authored content",
            )
        if (
            controller.first_per_turn_trigger_kinds
            != self.first_per_turn_trigger_kinds
        ):
            raise ValueError(
                "SpatialEffect controller admission differs from authored content",
            )
        controller.set_target_entity(self.uuid)
        try:
            intended_positions = controller.resolve_effect_footprint()
            active_positions, displaced = self._resolve_material_overlap(
                intended_positions,
                controller=controller,
            )
        except Exception:
            controller.remove_from_register()
            self.retire(parent_event=parent_event)
            raise
        if not active_positions:
            controller.remove_from_register()
            self.retire(parent_event=parent_event)
            return parent_event

        grid = get_map()
        for incumbent, _original, remaining in displaced:
            grid.set_spatial_effect_positions(
                effect_uuid=incumbent.uuid,
                layer=incumbent.layer,
                occupancy_policy=incumbent.occupancy_policy,
                positions=remaining,
            )
        controller.prepare_installation_footprint(active_positions)
        try:
            self.synchronize_footprint(active_positions)
            result = self.add_condition(controller, event=parent_event)
        except Exception:
            controller.rollback_failed_install()
            controller.remove_from_register()
            self.retire(parent_event=parent_event)
            for incumbent, original, _remaining in displaced:
                grid.set_spatial_effect_positions(
                    effect_uuid=incumbent.uuid,
                    layer=incumbent.layer,
                    occupancy_policy=incumbent.occupancy_policy,
                    positions=original,
                )
            raise
        if result is None or result.canceled or not controller.applied:
            self.retire(parent_event=parent_event)
            for incumbent, original, _remaining in displaced:
                grid.set_spatial_effect_positions(
                    effect_uuid=incumbent.uuid,
                    layer=incumbent.layer,
                    occupancy_policy=incumbent.occupancy_policy,
                    positions=original,
                )
            return result
        self._primary_controller_uuid = controller.uuid
        for incumbent, _original, remaining in displaced:
            if remaining:
                incumbent.transition_footprint(
                    remaining,
                    parent_event=parent_event,
                )
            else:
                incumbent.retire(
                    parent_event=parent_event,
                    operation=SpatialEffectChangeOperation.TRANSFORMED,
                )
        self._install_interaction_handler()
        self._install_anchor_handler()
        created_event = self._publish_change(
            SpatialEffectChangeOperation.CREATED,
            previous_positions=(),
            parent_event=parent_event,
        )
        self._created_event_published = True
        controller.apply_appearance_trigger(
            parent_event=created_event or parent_event,
        )
        return result

    def _resolve_material_overlap(
        self,
        positions: Set[Tuple[int, int]],
        *,
        controller: SpatialEffectController,
    ) -> tuple[
        Set[Tuple[int, int]],
        tuple[tuple["SpatialEffect", Set[Tuple[int, int]], Set[Tuple[int, int]]], ...],
    ]:
        """Split exact same-material overlap while retaining stronger incumbents."""
        if self.occupancy_policy is SpatialEffectOccupancyPolicy.OVERLAPPING:
            return set(positions), ()

        active_positions = set(positions)
        removals_by_effect: dict[UUID, Set[Tuple[int, int]]] = {}
        grid = get_map()
        incoming_rank = controller.material_arbitration_rank()
        for position in sorted(positions):
            for occupant_uuid in grid.get_spatial_effect_uuids_at(
                position,
                layer=self.layer,
            ):
                incumbent = SpatialEffect.get_effect(occupant_uuid)
                if incumbent is None:
                    raise RuntimeError(
                        "Spatial-effect index references a missing runtime owner",
                    )
                if incumbent.content_ref != self.content_ref:
                    raise ValueError(
                        f"{self.layer.value} cell {position} requires an "
                        "authored material transformation",
                    )
                incumbent_controller = (
                    BaseCondition.get(incumbent._primary_controller_uuid)
                    if incumbent._primary_controller_uuid is not None
                    else None
                )
                if not isinstance(incumbent_controller, SpatialEffectController):
                    raise RuntimeError(
                        "Exclusive spatial effect has no active controller",
                    )
                if incumbent_controller.material_arbitration_rank() > incoming_rank:
                    active_positions.discard(position)
                    continue
                removals_by_effect.setdefault(incumbent.uuid, set()).add(position)

        displaced: list[
            tuple[SpatialEffect, Set[Tuple[int, int]], Set[Tuple[int, int]]]
        ] = []
        for effect_uuid in sorted(removals_by_effect, key=str):
            incumbent = SpatialEffect.get_effect(effect_uuid)
            if incumbent is None:
                raise RuntimeError("Overlapping spatial effect disappeared")
            original = set(incumbent.affected_positions)
            remaining = original - removals_by_effect[effect_uuid]
            displaced.append((incumbent, original, remaining))
        return active_positions, tuple(displaced)

    def _install_anchor_handler(self) -> None:
        """Follow an attached entity/object through authoritative spatial events."""
        if self.anchor_uuid is None:
            return
        if self._anchor_handler_uuid is not None:
            raise ValueError("SpatialEffect already owns an anchor handler")

        effect_uuid = self.uuid
        anchor_uuid = self.anchor_uuid
        anchor_kind = self.anchor_kind
        if anchor_kind is SpatialEffectAnchorKind.ENTITY:
            event_types = (EventType.SPATIAL_ENTITY_ENTERED,)
        elif anchor_kind is SpatialEffectAnchorKind.WORLD_OBJECT:
            event_types = (
                EventType.SPATIAL_OBJECT_PLACED,
                EventType.SPATIAL_OBJECT_CHANGED,
                EventType.SPATIAL_OBJECT_REMOVED,
            )
        else:
            raise ValueError(
                f"{anchor_kind.value} cannot own an attached anchor UUID",
            )

        def processor(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            effect = SpatialEffect.get_effect(effect_uuid)
            if effect is None or not isinstance(event, SpatialChangeEvent):
                return None
            matches_anchor = (
                event.entity_uuid == anchor_uuid
                if anchor_kind is SpatialEffectAnchorKind.ENTITY
                else event.object_uuid == anchor_uuid
            )
            if not matches_anchor:
                return None
            if event.event_type is EventType.SPATIAL_OBJECT_REMOVED:
                anchor = BaseBlock.get(anchor_uuid)
                if anchor is not None and anchor.position != event.position:
                    return None
                effect.retire(parent_event=event)
                return None
            controller = (
                BaseCondition.get(effect._primary_controller_uuid)
                if effect._primary_controller_uuid is not None
                else None
            )
            if not isinstance(controller, SpatialEffectController):
                raise RuntimeError(
                    "Attached SpatialEffect primary controller is unavailable",
                )
            controller.relocate_anchor(event.position, parent_event=event)
            return None

        handler = EventHandler(
            name="Spatial Effect Anchor Movement",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[
                Trigger(event_type=event_type, event_phase=EventPhase.EFFECT)
                for event_type in event_types
            ],
            event_processor=processor,
        )
        self.add_event_handler(handler)
        self._anchor_handler_uuid = handler.uuid

    def create_default_controller(
        self,
        *,
        positions: Set[Tuple[int, int]],
        duration_rounds: Optional[int],
    ) -> SpatialEffectController:
        """Build content-owned mechanics for a transition-created effect."""
        raise ValueError(
            f"{self.content_ref.identity_key} has no default transition controller",
        )

    def install_default_controller(
        self,
        *,
        positions: Set[Tuple[int, int]],
        duration_rounds: Optional[int],
        parent_event: Event,
    ) -> Optional[Event]:
        """Install the effect type's explicit default mechanics controller."""
        controller = self.create_default_controller(
            positions=positions,
            duration_rounds=duration_rounds,
        )
        return self.install_controller(controller, parent_event=parent_event)

    def _install_interaction_handler(self) -> None:
        """Index one generic interaction handler across this effect footprint."""
        if self._interaction_handler_uuid is not None:
            raise ValueError("SpatialEffect already owns an interaction handler")

        effect_uuid = self.uuid

        def processor(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if not isinstance(event, SpatialEffectInteractionEvent):
                return None
            apply_spatial_effect_interaction(
                effect_uuid,
                SpatialEffectInteractionContext(
                    operation=event.operation,
                    positions=event.positions,
                    intensity=event.intensity,
                    duration_rounds=event.duration_rounds,
                    damage_type=event.damage_type,
                    source_object_uuid=event.source_object_uuid,
                    source_content_ref=event.source_content_ref,
                    parent_event_uuid=event.uuid,
                ),
            )
            return None

        handler = EventHandler(
            name="Spatial Effect Interaction",
            source_entity_uuid=self.source_entity_uuid,
            event_processor=processor,
        )
        EventQueue.add_spatial_handler(
            handler,
            set(self.affected_positions),
            EventType.SPATIAL_EFFECT_INTERACTION,
            EventPhase.EFFECT,
        )
        self._interaction_handler_uuid = handler.uuid

    def synchronize_footprint(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Optional[Event] = None,
        operation: SpatialEffectChangeOperation = (
            SpatialEffectChangeOperation.FOOTPRINT_CHANGED
        ),
    ) -> Optional[SpatialEffectChangeEvent]:
        """Atomically replace the indexed cells owned by this effect."""
        normalized = set(positions)
        previous = set(self.affected_positions)
        get_map().set_spatial_effect_positions(
            effect_uuid=self.uuid,
            layer=self.layer,
            occupancy_policy=self.occupancy_policy,
            positions=normalized,
        )
        self.affected_positions = normalized
        if self._interaction_handler_uuid is not None:
            EventQueue.update_spatial_handler_positions(
                self._interaction_handler_uuid,
                normalized,
            )
        if self._created_event_published and normalized != previous:
            return self._publish_change(
                operation,
                previous_positions=previous,
                parent_event=parent_event,
            )
        return None

    def _build_change_declaration(
        self,
        operation: SpatialEffectChangeOperation,
        *,
        previous_positions: Set[Tuple[int, int]] | Tuple[Tuple[int, int], ...],
        parent_event: Optional[Event],
    ) -> SpatialEffectChangeEvent:
        """Build one exact unregistered spatial-effect change declaration."""
        return SpatialEffectChangeEvent(
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=self.source_entity_name,
            phase=EventPhase.DECLARATION,
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
        previous_positions: Set[Tuple[int, int]] | Tuple[Tuple[int, int], ...],
        parent_event: Optional[Event],
    ) -> Optional[SpatialEffectChangeEvent]:
        """Publish one exact child lifecycle fact after a committed change."""
        return EventQueue.publish_lifecycle(
            self._build_change_declaration(
                operation,
                previous_positions=previous_positions,
                parent_event=parent_event,
            ),
        )

    def publish_revealed(
        self,
        *,
        parent_event: Event,
    ) -> Optional[SpatialEffectChangeEvent]:
        """Publish the one-way transition from hidden to globally revealed."""
        if not self._created_event_published:
            raise RuntimeError("Cannot reveal an uninstalled spatial effect")
        if self.stealth_dc is None:
            return None
        if self._reveal_in_progress:
            return None
        self._reveal_in_progress = True
        try:
            current = EventQueue.publish_declaration(
                self._build_change_declaration(
                    SpatialEffectChangeOperation.REVEALED,
                    previous_positions=set(self.affected_positions),
                    parent_event=parent_event,
                ),
            )
            if current.canceled:
                return None
            current = current.phase_to(EventPhase.EXECUTION)
            if current.canceled:
                return None
            current = current.phase_to(EventPhase.EFFECT)
            if current.canceled:
                return None
            self.stealth_dc = None
            return current.phase_to(EventPhase.COMPLETION)
        finally:
            self._reveal_in_progress = False

    def transition_footprint(
        self,
        remaining_positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Atomically shrink controller mechanics and the effect index."""
        if not remaining_positions:
            raise ValueError("Empty spatial-effect transition must retire")
        controller = (
            BaseCondition.get(self._primary_controller_uuid)
            if self._primary_controller_uuid is not None
            else None
        )
        if not isinstance(controller, SpatialEffectController):
            raise RuntimeError("SpatialEffect primary controller is unavailable")
        controller.transition_footprint(
            remaining_positions,
            parent_event=parent_event,
        )
        self.synchronize_footprint(
            remaining_positions,
            parent_event=parent_event,
            operation=SpatialEffectChangeOperation.TRANSFORMED,
        )

    def schedule_retirement(
        self,
        rounds: int,
        *,
        parent_event: Event,
    ) -> None:
        """Keep the shortest admitted delayed-removal countdown."""
        if rounds < 1:
            raise ValueError("Spatial-effect retirement delay must be positive")
        current = (
            BaseCondition.get(self._retirement_countdown_uuid)
            if self._retirement_countdown_uuid is not None
            else None
        )
        if isinstance(current, SpatialEffectRetirementCountdown):
            current_rounds = current.duration.duration
            if isinstance(current_rounds, int) and current_rounds <= rounds:
                return
            self._retirement_countdown_uuid = None
            BaseBlock.remove_condition(
                self,
                current.name,
                parent_event=parent_event,
            )

        countdown = SpatialEffectRetirementCountdown(
            source_entity_uuid=parent_event.source_entity_uuid,
            target_entity_uuid=self.uuid,
            duration=Duration(
                duration=rounds,
                duration_type=DurationType.ROUNDS,
            ),
        )
        result = self.add_condition(countdown, event=parent_event)
        if result is None or result.canceled or not countdown.applied:
            raise RuntimeError("Spatial-effect retirement countdown was rejected")
        self._retirement_countdown_uuid = countdown.uuid

    def remove_condition(
        self,
        condition_name: str,
        expire: bool = False,
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Retire the effect when its primary controller is removed."""
        controller = self.active_conditions.get(condition_name)
        controller_uuid = controller.uuid if controller is not None else None
        retirement_countdown = (
            controller_uuid == self._retirement_countdown_uuid
        )
        if retirement_countdown:
            self._retirement_countdown_uuid = None
        removed = super().remove_condition(
            condition_name,
            expire=expire,
            parent_event=parent_event,
        )
        if (
            removed
            and controller_uuid == self._primary_controller_uuid
            and not self._retiring
        ):
            self.retire(parent_event=parent_event)
        elif removed and retirement_countdown and not self._retiring:
            self.retire(parent_event=parent_event)
        return removed

    def retire(
        self,
        *,
        parent_event: Optional[Event] = None,
        operation: SpatialEffectChangeOperation = (
            SpatialEffectChangeOperation.REMOVED
        ),
    ) -> None:
        """Remove all owned mechanics, footprint indexes, and registries."""
        if self._retiring:
            return
        self._retiring = True
        previous_positions = set(self.affected_positions)
        for condition_name in list(self.active_conditions):
            BaseBlock.remove_condition(
                self,
                condition_name,
                parent_event=parent_event,
            )
        if self._interaction_handler_uuid is not None:
            EventQueue.remove_spatial_handler(self._interaction_handler_uuid)
            self._interaction_handler_uuid = None
        if self._anchor_handler_uuid is not None:
            handler = self.event_handlers.get(self._anchor_handler_uuid)
            if isinstance(handler, EventHandler):
                self.remove_event_handler(handler)
            self._anchor_handler_uuid = None
        self._retirement_countdown_uuid = None
        get_map().cleanup_block_light_sources(self.uuid)
        get_map().remove_spatial_effect(self.uuid)
        self.affected_positions.clear()
        if self._created_event_published:
            self._publish_change(
                operation,
                previous_positions=previous_positions,
                parent_event=parent_event,
            )
            self._created_event_published = False
        self._effect_registry.pop(self.uuid, None)
        BaseBlock.unregister(self.uuid)
        self._retiring = False


class GroundEffect(SpatialEffect):
    """Exclusive, transforming material occupying the ground layer."""

    layer: SpatialEffectLayer = Field(
        default=SpatialEffectLayer.GROUND_SURFACE,
        frozen=True,
    )
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        default=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
        frozen=True,
    )


class CloudEffect(SpatialEffect):
    """Exclusive, transforming atmospheric material."""

    layer: SpatialEffectLayer = Field(
        default=SpatialEffectLayer.CLOUD,
        frozen=True,
    )
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        default=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
        frozen=True,
    )


class FieldEffect(SpatialEffect):
    """Freely overlapping magical or physical influence field."""

    layer: SpatialEffectLayer = Field(
        default=SpatialEffectLayer.FIELD,
        frozen=True,
    )
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        default=SpatialEffectOccupancyPolicy.OVERLAPPING,
        frozen=True,
    )


__all__ = [
    "CloudEffect",
    "FieldEffect",
    "GroundEffect",
    "SpatialEffect",
    "SpatialEffectController",
    "SpatialEffectRetirementCountdown",
]
