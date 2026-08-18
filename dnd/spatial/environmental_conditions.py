"""Authored mechanics for persistent non-spell environmental materials."""

from __future__ import annotations

from typing import Optional, Set, Tuple
from uuid import UUID

from pydantic import Field

from dnd.types.world import LightLevel
from dnd.types.abilities import AbilityName
from dnd.core.base_conditions import Duration
from dnd.types.conditions import (
    ConditionCategory,
    ConditionTag,
    DurationType,
    HazardFilter,
)
from dnd.types.damage import DamageType
from dnd.types.rolls import AttackOutcome
from dnd.core.events.resolution_events import (
    Damage,
)
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventType,
    Trigger,
)
from dnd.core.events.world_events import (
    SpatialChangeEvent,
)
from dnd.types.spatial_effects import (
    SpatialEffectChangeOperation,
    SpatialEffectTriggerKind,
)
from dnd.core.gridmap import get_map
from dnd.core.values import ModifiableValue
from dnd.conditions import Prone, Wet
from dnd.entities.entity import Entity
from dnd.spatial.area_conditions import AreaCondition
from dnd.spatial.memberships import (
    SpatialConditionMembershipSource,
    MembershipAreaCondition,
)


class FixedFootprintCondition(AreaCondition):
    """Area condition whose authored cells are supplied by its creator."""

    condition_category: ConditionCategory = ConditionCategory.INTERNAL
    def resolve_area_footprint(self) -> Set[Tuple[int, int]]:
        """Use the exact material cells admitted by the transition authority."""
        return set(self.affected_positions)


class WetSurfaceMembership(SpatialConditionMembershipSource):
    """Internal exact source lease manifesting the public Wet condition."""

    description: str = Field(
        default="Tracks wetness contributed by one exact water-bearing effect.",
    )

    def create_manifestation(self, target: Entity) -> Wet:
        return Wet(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            parent_condition=self.uuid,
            potency_rank=(0,),
        )


class WetAreaCondition(MembershipAreaCondition):
    """Shared continuous Wet membership for ground water and steam."""

    condition_category: ConditionCategory = ConditionCategory.INTERNAL
    membership_tags: frozenset[ConditionTag] = frozenset()
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=None,
            duration_type=DurationType.PERMANENT,
        ),
    )
    hazard_filter: Optional[HazardFilter] = None
    membership_trigger_kinds: frozenset[
        SpatialEffectTriggerKind
    ] = frozenset({
        SpatialEffectTriggerKind.APPEAR,
        SpatialEffectTriggerKind.ENTER,
    })

    def membership_source_class(
        self,
    ) -> type[SpatialConditionMembershipSource]:
        return WetSurfaceMembership

    def resolve_area_footprint(self) -> Set[Tuple[int, int]]:
        """Use exact cells admitted by the material transition authority."""
        return set(self.affected_positions)

    def _apply_appearance_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        """Membership admission is the complete appearance consequence."""
        del entity, parent_event

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create the entry boundary whose wrapper admits membership."""
        return EventHandler(
            name=f"{self.name} Membership Entry",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=self._membership_entry_processor,
        )

    def _membership_entry_processor(
        self,
        event: Event,
        source_entity_uuid: UUID,
    ) -> Optional[Event]:
        """No-op after the shared admission wrapper creates membership."""
        del event, source_entity_uuid
        return None

    def _create_zone_exit_handler(self) -> EventHandler:
        """Remove only this effect's membership after leaving its footprint."""
        condition = self

        def processor(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent):
                return None
            if event.entity_uuid is None:
                return None
            if event.old_position in condition.affected_positions:
                return None
            entity = Entity.get(event.entity_uuid)
            if entity is not None:
                condition.remove_membership(entity, parent_event=event)
            return None

        return EventHandler(
            name=f"{self.name} Membership Exit",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_LEFT,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=processor,
        )


class WaterSurface(WetAreaCondition):
    """Navigable wet surface layered independently over structural terrain."""

    name: str = Field(default="Water Surface")
    description: str = Field(
        default=(
            "A shallow wet surface applies Wet without replacing the tile's "
            "structural movement mode."
        ),
    )


class IceSurface(FixedFootprintCondition):
    """Frozen ground: difficult terrain plus a source-authored slip save."""

    name: str = Field(default="Ice Surface")
    description: str = Field(
        default="Slippery frozen ground is difficult terrain and can knock creatures prone.",
    )
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=None,
            duration_type=DurationType.PERMANENT,
        ),
    )
    adds_difficult_terrain: bool = True
    hazard_filter: Optional[HazardFilter] = HazardFilter.ALL
    slip_save_dc: int = Field(default=10, ge=0)
    def _apply_slip_save(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        if "Prone" in entity.active_conditions:
            return
        request = entity.create_saving_throw_request(
            target_entity_uuid=entity.uuid,
            ability_name=AbilityName.DEXTERITY,
            dc=self.slip_save_dc,
            parent_event=parent_event.uuid,
        )
        _, _, success = entity.saving_throw(request)
        if success:
            return
        prone = Prone(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=entity.uuid,
        )
        prone.suppress_immediate_stand_for_application()
        entity.add_condition(prone, parent_event=parent_event)

    def _apply_appearance_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        self._apply_slip_save(entity, parent_event=parent_event)

    def _create_zone_entry_handler(self) -> EventHandler:
        condition = self

        def processor(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent):
                return None
            if event.entity_uuid is None:
                return None
            entity = Entity.get(event.entity_uuid)
            if entity is not None:
                condition._apply_slip_save(entity, parent_event=event)
            return None

        return EventHandler(
            name="Ice Surface Entry Slip",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=processor,
        )

    def _create_zone_turn_end_handler(self) -> EventHandler:
        condition = self

        def processor(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if event.event_type is not EventType.TURN_END:
                return None
            entity = Entity.get(event.source_entity_uuid)
            if (
                entity is not None
                and entity.position in condition.affected_positions
            ):
                condition._apply_slip_save(entity, parent_event=event)
            return None

        return EventHandler(
            name="Ice Surface Turn End Slip",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_END,
                event_phase=EventPhase.EXECUTION,
            )],
            event_processor=processor,
        )


class ElectrifiedWater(WetAreaCondition):
    """Wet ground carrying one exact first-per-turn lightning consequence."""

    name: str = Field(default="Electrified Water")
    description: str = Field(
        default="Electrified water applies Wet and deals 1d4 lightning damage.",
    )
    hazard_filter: Optional[HazardFilter] = HazardFilter.ALL
    membership_trigger_kinds: frozenset[
        SpatialEffectTriggerKind
    ] = frozenset({
        SpatialEffectTriggerKind.APPEAR,
        SpatialEffectTriggerKind.ENTER,
        SpatialEffectTriggerKind.TURN_START,
    })

    def _deal_damage(self, entity: Entity, parent_event: Event) -> None:
        source_uuid = self.source_entity_uuid
        damage_bonus = ModifiableValue.create(
            source_entity_uuid=source_uuid,
            target_entity_uuid=entity.uuid,
            base_value=0,
            value_name="Electrified Water Damage",
        )
        damage = Damage(
            source_entity_uuid=source_uuid,
            target_entity_uuid=entity.uuid,
            damage_dice=4,
            dice_numbers=1,
            damage_bonus=damage_bonus,
            damage_type=DamageType.LIGHTNING,
        )
        damage_roll = damage.get_dice(
            attack_outcome=AttackOutcome.HIT,
        ).roll
        entity.receive_damage(
            damage_roll.total,
            DamageType.LIGHTNING,
            source_uuid,
            damage_rolls=[damage_roll],
            damages=[damage],
            parent_event=parent_event.uuid,
            effect_id=self.content_ref.identity_key,
        )

    def _apply_appearance_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        self._deal_damage(entity, parent_event)

    def _membership_entry_processor(
        self,
        event: Event,
        source_entity_uuid: UUID,
    ) -> Optional[Event]:
        del source_entity_uuid
        if not isinstance(event, SpatialChangeEvent):
            return None
        if event.entity_uuid is None:
            return None
        entity = Entity.get(event.entity_uuid)
        if entity is not None:
            self._deal_damage(entity, event)
        return None

    def _create_zone_turn_start_handler(self) -> EventHandler:
        condition = self

        def processor(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if event.event_type is not EventType.TURN_START:
                return None
            entity = Entity.get(event.source_entity_uuid)
            if (
                entity is not None
                and entity.position in condition.affected_positions
            ):
                condition._deal_damage(entity, event)
            return None

        return EventHandler(
            name="Electrified Water Turn Start Damage",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=processor,
        )


class SteamCloud(WetAreaCondition):
    """Short-lived wet obscuring cloud produced by vaporized surface water."""

    name: str = Field(default="Steam Cloud")
    description: str = Field(
        default="Steam obscures its cells and applies Wet to occupants.",
    )
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=2,
            duration_type=DurationType.ROUNDS,
        ),
    )
    sets_light_level: Optional[LightLevel] = LightLevel.DIM_LIGHT
    light_is_obscurement: bool = True


class OilSurface(FixedFootprintCondition):
    """Persistent slippery oil awaiting an authored environmental transition."""

    name: str = Field(default="Oil Surface")
    description: str = Field(
        default="Slippery flammable oil creates hazardous difficult terrain.",
    )
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=None,
            duration_type=DurationType.PERMANENT,
        ),
    )
    adds_difficult_terrain: bool = True
    hazard_filter: Optional[HazardFilter] = HazardFilter.ALL


class FireSurface(FixedFootprintCondition):
    """Short-lived burning ground with light and typed fire damage."""

    name: str = Field(default="Fire Surface")
    description: str = Field(
        default="Burning ground sheds light and deals 2d4 fire damage.",
    )
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=3,
            duration_type=DurationType.ROUNDS,
        ),
    )
    sets_light_level: Optional[LightLevel] = LightLevel.BRIGHT_LIGHT
    hazard_filter: Optional[HazardFilter] = HazardFilter.ALL
    def _deal_damage(self, entity: Entity, parent_event: Event) -> None:
        source_uuid = self.source_entity_uuid
        damage_bonus = ModifiableValue.create(
            source_entity_uuid=source_uuid,
            target_entity_uuid=entity.uuid,
            base_value=0,
            value_name="Fire Surface Damage",
        )
        damage = Damage(
            source_entity_uuid=source_uuid,
            target_entity_uuid=entity.uuid,
            damage_dice=4,
            dice_numbers=2,
            damage_bonus=damage_bonus,
            damage_type=DamageType.FIRE,
        )
        damage_roll = damage.get_dice(
            attack_outcome=AttackOutcome.HIT,
        ).roll
        entity.receive_damage(
            damage_roll.total,
            DamageType.FIRE,
            source_uuid,
            damage_rolls=[damage_roll],
            damages=[damage],
            parent_event=parent_event.uuid,
        )

    def _create_zone_entry_handler(self) -> EventHandler:
        condition = self

        def processor(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent):
                return None
            if event.entity_uuid is None:
                return None
            entity = Entity.get(event.entity_uuid)
            if entity is not None:
                condition._deal_damage(entity, event)
            return None

        return EventHandler(
            name="Fire Surface Entry Damage",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=processor,
        )

    def _create_zone_turn_start_handler(self) -> EventHandler:
        condition = self

        def processor(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if event.event_type is not EventType.TURN_START:
                return None
            entity = Entity.get(event.source_entity_uuid)
            if (
                entity is not None
                and entity.position in condition.affected_positions
            ):
                condition._deal_damage(entity, event)
            return None

        return EventHandler(
            name="Fire Surface Turn Start Damage",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=processor,
        )


class SpikeTrap(FixedFootprintCondition):
    """Permanent hidden ground hazard owned by one trap-network effect."""

    name: str = Field(default="Spike Trap")
    description: str = Field(
        default="Sharp spikes deal 2d4 piercing damage when entered.",
    )
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=None,
            duration_type=DurationType.PERMANENT,
        ),
    )
    hazard_filter: HazardFilter = HazardFilter.ALL
    def extend_footprint(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Extend this network without changing its stable condition identity."""
        expanded = set(self.affected_positions) | set(positions)
        if expanded == self.affected_positions:
            return
        previous = set(self.affected_positions)
        get_map().set_spatial_condition_positions(
            condition=self,
            layer=self.layer,
            occupancy_policy=self.occupancy_policy,
            positions=expanded,
        )
        self.affected_positions = set(expanded)
        self._sync_spatial_handler_positions()
        self._publish_change(
            SpatialEffectChangeOperation.FOOTPRINT_CHANGED,
            previous_positions=previous,
            parent_event=parent_event,
        )

    def _reveal(self, *, parent_event: Event) -> None:
        """Reveal the complete linked trap network after its first trigger."""
        if self.condition_stealth_dc is None:
            return
        self.publish_revealed(parent_event=parent_event)

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create one position-indexed typed damage handler for the network."""
        condition = self

        def processor(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent):
                return None
            if event.entity_uuid is None:
                return None
            entity = Entity.get(event.entity_uuid)
            if entity is None:
                return None

            condition._reveal(parent_event=event)
            source_uuid = condition.source_entity_uuid
            damage_bonus = ModifiableValue.create(
                source_entity_uuid=source_uuid,
                target_entity_uuid=entity.uuid,
                base_value=0,
                value_name="Spike Trap Damage",
            )
            damage = Damage(
                name="Spike Trap",
                source_entity_uuid=source_uuid,
                target_entity_uuid=entity.uuid,
                damage_dice=4,
                dice_numbers=2,
                damage_bonus=damage_bonus,
                damage_type=DamageType.PIERCING,
            )
            damage_roll = damage.get_dice(
                attack_outcome=AttackOutcome.HIT,
            ).roll
            entity.receive_damage(
                damage_roll.total,
                DamageType.PIERCING,
                source_uuid,
                damage_rolls=[damage_roll],
                damages=[damage],
                parent_event=event.uuid,
                effect_id=condition.content_ref.identity_key,
            )
            return None

        return EventHandler(
            name="Spike Trap Entry Damage",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=processor,
        )


__all__ = [
    "ElectrifiedWater",
    "FireSurface",
    "FixedFootprintCondition",
    "IceSurface",
    "OilSurface",
    "SpikeTrap",
    "SteamCloud",
    "WaterSurface",
    "WetAreaCondition",
    "WetSurfaceMembership",
]
