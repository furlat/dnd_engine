"""Authored environmental conditions with independent world ownership."""

from typing import Optional, Set, Tuple
from uuid import UUID, uuid4

from pydantic import Field

from dnd.core.base_block import BaseBlock, LightLevel
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import (
    ConditionCategory,
    ConditionTag,
    DurationType,
    HazardFilter,
)
from dnd.core.content.spatial_effect_definitions import (
    SpatialEffectTransitionDefinition,
)
from dnd.core.content.identities import (
    ContentDefinitionKind,
    ContentRef,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.dice import AttackOutcome
from dnd.core.events import (
    Damage,
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    SpatialChangeEvent,
    SpatialEffectInteractionEvent,
    Trigger,
)
from dnd.core.gridmap import get_map
from dnd.core.modifiers import ResistanceModifier, ResistanceStatus
from dnd.core.values import ModifiableValue
from dnd.conditions import Poisoned, Prone
from dnd.core.saving_throw_types import SavingThrowContext, SavingThrowEffectTag
from dnd.entity import Entity
from dnd.spatial.area_conditions import AreaCondition, SpatialCondition
from dnd.spatial.memberships import (
    MembershipAreaCondition,
    SpatialConditionMembershipSource,
)
from dnd.spatial.transitions import bind_spatial_interactions
from dnd.types.senses import OpticalObscurement, PerceivedSpatialEffect
from dnd.types.traps import TrapConditionPayload, TrapDamage, TrapPayload, TrapState
from dnd.types.world import OccupancyLayer
from dnd.types.spatial_effects import (
    SpatialEffectBlockingPolicy,
    SpatialEffectChangeOperation,
    SpatialEffectInteractionOperation,
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
    SpatialEffectTransitionAction,
)
from dnd.core.creature_types import DamageType


SPIKE_TRAP_CONTENT_REF = ContentRef(
    pack_id="content.neurodragon",
    definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.environment.spike_trap",
    content_version=1,
    definition_contract_hash=(
        "8b800db652bc295c51d9bb1db2bf8470"
        "b6975083ecc7e241318c5426a2d90066"
    ),
)
POISON_DAMAGE_SPIKE_CONTENT_REF = SPIKE_TRAP_CONTENT_REF.model_copy(update={
    "content_id": "spatial_effect.environment.spike_trap.poison_damage",
})
SICKENING_SPIKE_CONTENT_REF = SPIKE_TRAP_CONTENT_REF.model_copy(update={
    "content_id": "spatial_effect.environment.spike_trap.poisoned",
})

PLAIN_SPIKE_PAYLOAD = TrapPayload()
POISON_DAMAGE_SPIKE_PAYLOAD = TrapPayload(damages=(
    *PLAIN_SPIKE_PAYLOAD.damages,
    TrapDamage(dice_count=1, dice_sides=4, damage_type=DamageType.POISON),
))
SICKENING_SPIKE_PAYLOAD = TrapPayload(condition=TrapConditionPayload(
    save_dc=12, duration_rounds=2,
))

FIRE_SURFACE_CONTENT_REF = ContentRef(
    pack_id="content.neurodragon",
    definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.material.fire",
    content_version=1,
    definition_contract_hash=(
        "a74aa0ee0fa241101b5c7d3b2551d638"
        "6e4817a8ae5ad5e5cadbc4a15d5fdeb0"
    ),
)
FIRE_SURFACE_RECIPE = ContentRecipe.create(
    ref=FIRE_SURFACE_CONTENT_REF,
    parameters={},
)

WET_SURFACE_CONTENT_REF = ContentRef(
    pack_id="content.neurodragon",
    definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.material.water_surface",
    content_version=1,
    definition_contract_hash=(
        "a74aa0ee0fa241101b5c7d3b2551d638"
        "6e4817a8ae5ad5e5cadbc4a15d5fdeb0"
    ),
)
WET_SURFACE_RECIPE = ContentRecipe.create(
    ref=WET_SURFACE_CONTENT_REF,
    parameters={},
)

ICE_SURFACE_CONTENT_REF = ContentRef(
    pack_id="content.neurodragon",
    definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.material.ice",
    content_version=1,
    definition_contract_hash=(
        "a74aa0ee0fa241101b5c7d3b2551d638"
        "6e4817a8ae5ad5e5cadbc4a15d5fdeb0"
    ),
)
ICE_SURFACE_RECIPE = ContentRecipe.create(
    ref=ICE_SURFACE_CONTENT_REF,
    parameters={},
)

ELECTRIFIED_WATER_CONTENT_REF = ContentRef(
    pack_id="content.neurodragon",
    definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.material.electrified_water",
    content_version=1,
    definition_contract_hash=(
        "a74aa0ee0fa241101b5c7d3b2551d638"
        "6e4817a8ae5ad5e5cadbc4a15d5fdeb0"
    ),
)
ELECTRIFIED_WATER_RECIPE = ContentRecipe.create(
    ref=ELECTRIFIED_WATER_CONTENT_REF,
    parameters={},
)

STEAM_CLOUD_CONTENT_REF = ContentRef(
    pack_id="content.neurodragon",
    definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.material.steam",
    content_version=1,
    definition_contract_hash=(
        "a74aa0ee0fa241101b5c7d3b2551d638"
        "6e4817a8ae5ad5e5cadbc4a15d5fdeb0"
    ),
)
STEAM_CLOUD_RECIPE = ContentRecipe.create(
    ref=STEAM_CLOUD_CONTENT_REF,
    parameters={},
)

BURNING_WEB_CONTENT_REF = ContentRef(
    pack_id="content.srd_5_1_cc",
    definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.spell.web.burning",
    content_version=1,
    definition_contract_hash=(
        "a74aa0ee0fa241101b5c7d3b2551d638"
        "6e4817a8ae5ad5e5cadbc4a15d5fdeb0"
    ),
)
BURNING_WEB_RECIPE = ContentRecipe.create(
    ref=BURNING_WEB_CONTENT_REF,
    parameters={},
)

FIRE_SURFACE_TRANSITIONS = (
    SpatialEffectTransitionDefinition(
        operation=SpatialEffectInteractionOperation.DOUSE,
        action=SpatialEffectTransitionAction.REMOVE_AFFECTED,
    ),
)

WET_SURFACE_TRANSITIONS = (
    SpatialEffectTransitionDefinition(
        operation=SpatialEffectInteractionOperation.FREEZE,
        action=SpatialEffectTransitionAction.REPLACE_AFFECTED,
        replacement_recipe=ICE_SURFACE_RECIPE,
    ),
    SpatialEffectTransitionDefinition(
        operation=SpatialEffectInteractionOperation.ELECTRIFY,
        action=SpatialEffectTransitionAction.REPLACE_AFFECTED,
        replacement_recipe=ELECTRIFIED_WATER_RECIPE,
    ),
    SpatialEffectTransitionDefinition(
        operation=SpatialEffectInteractionOperation.VAPORIZE,
        action=(
            SpatialEffectTransitionAction
            .REMOVE_AFFECTED_AND_CREATE_SECONDARY
        ),
        replacement_recipe=STEAM_CLOUD_RECIPE,
    ),
)

ICE_SURFACE_TRANSITIONS = (
    SpatialEffectTransitionDefinition(
        operation=SpatialEffectInteractionOperation.VAPORIZE,
        action=(
            SpatialEffectTransitionAction
            .REMOVE_AFFECTED_AND_CREATE_SECONDARY
        ),
        replacement_recipe=STEAM_CLOUD_RECIPE,
    ),
)

ELECTRIFIED_WATER_TRANSITIONS = (
    SpatialEffectTransitionDefinition(
        operation=SpatialEffectInteractionOperation.FREEZE,
        action=SpatialEffectTransitionAction.REPLACE_AFFECTED,
        replacement_recipe=ICE_SURFACE_RECIPE,
    ),
    SpatialEffectTransitionDefinition(
        operation=SpatialEffectInteractionOperation.VAPORIZE,
        action=(
            SpatialEffectTransitionAction
            .REMOVE_AFFECTED_AND_CREATE_SECONDARY
        ),
        replacement_recipe=STEAM_CLOUD_RECIPE,
    ),
)

BURNING_WEB_TRANSITIONS = (
    SpatialEffectTransitionDefinition(
        operation=SpatialEffectInteractionOperation.DOUSE,
        action=SpatialEffectTransitionAction.REMOVE_AFFECTED,
    ),
)


class FireSurface(AreaCondition):
    """Short-lived burning ground with direct dousing reactions."""

    name: str = Field(default="Fire Surface")
    description: str = Field(
        default="Burning ground sheds light and deals 2d4 fire damage.",
    )
    content_ref: ContentRef = Field(default=FIRE_SURFACE_CONTENT_REF)
    layer: SpatialEffectLayer = Field(
        default=SpatialEffectLayer.GROUND_SURFACE,
    )
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        default=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
    )
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=lambda: frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }),
    )
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=3,
            duration_type=DurationType.ROUNDS,
        ),
    )
    sets_light_level: Optional[LightLevel] = LightLevel.BRIGHT_LIGHT
    hazard_filter: HazardFilter = Field(default=HazardFilter.ALL)

    def _apply(
        self,
        execution_event: Event,
    ) -> tuple[
        list[Tuple[UUID, UUID]],
        list[UUID],
        list[UUID],
        list[UUID],
        Event,
    ]:
        """Install area mechanics and one direct reaction handler."""
        modifiers, handlers, children, spatial_handlers, effect = super()._apply(
            execution_event,
        )
        interaction_handler = bind_spatial_interactions(
            condition=self,
            transitions=FIRE_SURFACE_TRANSITIONS,
        )
        spatial_handlers.append(interaction_handler.uuid)
        return modifiers, handlers, children, spatial_handlers, effect

    def _deal_damage(self, entity: Entity, parent_event: Event) -> None:
        """Deal this surface's typed entry or turn-start damage."""
        damage_bonus = ModifiableValue.create(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=entity.uuid,
            base_value=0,
            value_name="Fire Surface Damage",
        )
        damage = Damage(
            name="Fire Surface",
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=entity.uuid,
            damage_dice=4,
            dice_numbers=2,
            damage_bonus=damage_bonus,
            damage_type=DamageType.FIRE,
        )
        damage_roll = damage.get_dice(AttackOutcome.HIT).roll
        entity.receive_damage(
            damage_roll.total,
            DamageType.FIRE,
            self.source_entity_uuid,
            damage_rolls=[damage_roll],
            damages=[damage],
            parent_event=parent_event.uuid,
            effect_id=self.content_ref.identity_key,
        )

    def _create_zone_entry_handler(self) -> EventHandler:
        """Deal fire damage when an entity enters the surface."""
        condition = self

        def damage_entering_entity(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent):
                return None
            entity = Entity.get(event.entity_uuid) if event.entity_uuid else None
            if isinstance(entity, Entity):
                condition._deal_damage(entity, event)
            return None

        return EventHandler(
            name="Fire Surface Entry Damage",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.SPATIAL_ENTITY_ENTERED,
                    event_phase=EventPhase.EFFECT,
                ),
            ],
            event_processor=damage_entering_entity,
        )

    def _create_zone_turn_start_handler(self) -> EventHandler:
        """Deal fire damage at an occupant's turn start."""
        condition = self

        def damage_occupant(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if event.event_type is not EventType.TURN_START:
                return None
            entity = Entity.get(event.source_entity_uuid)
            if (
                isinstance(entity, Entity)
                and entity.position in condition.affected_positions
            ):
                condition._deal_damage(entity, event)
            return None

        return EventHandler(
            name="Fire Surface Turn Start Damage",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EFFECT,
                ),
            ],
            event_processor=damage_occupant,
        )


class Wet(BaseCondition):
    """One source-specific public Wet manifestation."""

    name: str = Field(default="Wet")
    description: str = Field(
        default=(
            "Resists fire damage and is vulnerable to cold and lightning "
            "damage."
        ),
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.STATUS,
        frozen=True,
    )

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[
        list[Tuple[UUID, UUID]],
        list[UUID],
        list[UUID],
        list[UUID],
        Event,
    ]:
        """Install this source's exact damage relationships."""
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(
                status_message="Wet target is unavailable",
            )
        modifiers: list[Tuple[UUID, UUID]] = []
        for damage_type, resistance in (
            (DamageType.FIRE, ResistanceStatus.RESISTANCE),
            (DamageType.COLD, ResistanceStatus.VULNERABILITY),
            (DamageType.LIGHTNING, ResistanceStatus.VULNERABILITY),
        ):
            modifier_uuid = (
                target.health.damage_reduction.self_static
                .add_resistance_modifier(ResistanceModifier(
                    name=f"Wet {damage_type.value}",
                    source_entity_uuid=self.source_entity_uuid,
                    target_entity_uuid=target.uuid,
                    damage_type=damage_type,
                    value=resistance,
                ))
            )
            modifiers.append((
                target.health.damage_reduction.uuid,
                modifier_uuid,
            ))
        effect = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Wet to {target.name}",
        )
        return modifiers, [], [], [], effect


class WetSurfaceMembership(SpatialConditionMembershipSource):
    """Exact Wet lease contributed by one water-bearing condition."""

    def create_manifestation(self, target: Entity) -> Wet:
        return Wet(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
        )

    @staticmethod
    def _find_wet(target: Entity) -> Optional[Wet]:
        """Return the entity's one public Wet manifestation, if present."""
        for condition in target.active_conditions_by_uuid.values():
            if isinstance(condition, Wet):
                return condition
        return None

    def _apply(
        self,
        execution_event: Event,
    ) -> tuple[
        list[Tuple[UUID, UUID]],
        list[UUID],
        list[UUID],
        list[UUID],
        Event,
    ]:
        """Acquire one source lease while sharing the public Wet mechanics."""
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if not isinstance(target, Entity):
            return [], [], [], [], execution_event.cancel(
                status_message="Wet membership target is unavailable",
            )
        if self._find_wet(target) is None:
            manifestation = self.create_manifestation(target)
            result = target.add_condition(
                manifestation,
                parent_event=execution_event,
            )
            if result is None or result.canceled:
                return [], [], [], [], execution_event.cancel(
                    status_message="Wet manifestation was rejected",
                )
        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
        )
        return [], [], [], [], effect

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Release Wet only after the entity's final source lease ends."""
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if not isinstance(target, Entity):
            return event
        has_other_source = any(
            isinstance(condition, WetSurfaceMembership)
            and condition.uuid != self.uuid
            for condition in target.active_conditions_by_uuid.values()
        )
        manifestation = self._find_wet(target)
        if not has_other_source and manifestation is not None:
            target.remove_condition_by_uuid(
                manifestation.uuid,
                parent_event=event,
            )
        return event


class WetAreaCondition(MembershipAreaCondition):
    """Continuous Wet membership shared by water-bearing conditions."""

    membership_tags: frozenset[ConditionTag] = frozenset()
    membership_trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=lambda: frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
        }),
    )
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=lambda: frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.LEAVE,
            SpatialEffectTriggerKind.EFFECT_ENTERS_OCCUPANT,
        }),
    )

    def membership_source_class(
        self,
    ) -> type[SpatialConditionMembershipSource]:
        return WetSurfaceMembership

    def _apply_effect_entry_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        self.apply_membership(entity, parent_event=parent_event)


class WetSurface(WetAreaCondition):
    """Persistent water surface with exact source-owned Wet membership."""

    name: str = Field(default="Wet Surface")
    content_ref: ContentRef = Field(default=WET_SURFACE_CONTENT_REF)
    layer: SpatialEffectLayer = Field(
        default=SpatialEffectLayer.GROUND_SURFACE,
    )
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        default=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
    )
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=None,
            duration_type=DurationType.PERMANENT,
        ),
    )

    def _apply(self, execution_event: Event):
        result = super()._apply(execution_event)
        modifiers, handlers, children, spatial_handlers, effect = result
        interaction_handler = bind_spatial_interactions(
            condition=self,
            transitions=WET_SURFACE_TRANSITIONS,
            build_replacement=build_environmental_replacement,
        )
        spatial_handlers.append(interaction_handler.uuid)
        return modifiers, handlers, children, spatial_handlers, effect


class IceSurface(AreaCondition):
    """Frozen difficult ground with an authored Dexterity slip save."""

    name: str = Field(default="Ice Surface")
    content_ref: ContentRef = Field(default=ICE_SURFACE_CONTENT_REF)
    layer: SpatialEffectLayer = Field(
        default=SpatialEffectLayer.GROUND_SURFACE,
    )
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        default=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
    )
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=lambda: frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_END,
        }),
    )
    first_per_turn_trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=lambda: frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_END,
        }),
    )
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=None,
            duration_type=DurationType.PERMANENT,
        ),
    )
    adds_difficult_terrain: bool = True
    hazard_filter: HazardFilter = Field(default=HazardFilter.ALL)
    slip_save_dc: int = Field(default=10, ge=0)

    def _apply_slip_save(self, entity: Entity, *, parent_event: Event) -> None:
        if "Prone" in entity.active_conditions:
            return
        request = entity.create_saving_throw_request(
            target_entity_uuid=entity.uuid,
            ability_name="dexterity",
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

        def slip(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if isinstance(event, SpatialChangeEvent) and event.entity_uuid:
                entity = Entity.get(event.entity_uuid)
                if isinstance(entity, Entity):
                    condition._apply_slip_save(entity, parent_event=event)
            return None

        return EventHandler(
            name="Ice Surface Entry Slip",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=slip,
        )

    def _create_zone_turn_end_handler(self) -> EventHandler:
        condition = self

        def slip(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            entity = Entity.get(event.source_entity_uuid)
            if (
                isinstance(entity, Entity)
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
            event_processor=slip,
        )

    def _apply(self, execution_event: Event):
        result = super()._apply(execution_event)
        modifiers, handlers, children, spatial_handlers, effect = result
        interaction_handler = bind_spatial_interactions(
            condition=self,
            transitions=ICE_SURFACE_TRANSITIONS,
            build_replacement=build_environmental_replacement,
        )
        spatial_handlers.append(interaction_handler.uuid)
        return modifiers, handlers, children, spatial_handlers, effect


class ElectrifiedWater(WetAreaCondition):
    """Wet ground carrying first-per-turn lightning damage."""

    name: str = Field(default="Electrified Water")
    content_ref: ContentRef = Field(default=ELECTRIFIED_WATER_CONTENT_REF)
    layer: SpatialEffectLayer = Field(
        default=SpatialEffectLayer.GROUND_SURFACE,
    )
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        default=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
    )
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=lambda: frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.LEAVE,
            SpatialEffectTriggerKind.TURN_START,
            SpatialEffectTriggerKind.EFFECT_ENTERS_OCCUPANT,
        }),
    )
    first_per_turn_trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=lambda: frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }),
    )
    hazard_filter: HazardFilter = Field(default=HazardFilter.ALL)

    def _deal_damage(self, entity: Entity, parent_event: Event) -> None:
        damage_bonus = ModifiableValue.create(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=entity.uuid,
            base_value=0,
            value_name="Electrified Water Damage",
        )
        damage = Damage(
            name="Electrified Water",
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=entity.uuid,
            damage_dice=4,
            dice_numbers=1,
            damage_bonus=damage_bonus,
            damage_type=DamageType.LIGHTNING,
        )
        damage_roll = damage.get_dice(AttackOutcome.HIT).roll
        entity.receive_damage(
            damage_roll.total,
            DamageType.LIGHTNING,
            self.source_entity_uuid,
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

    def _create_zone_entry_handler(self) -> EventHandler:
        condition = self

        def damage(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if isinstance(event, SpatialChangeEvent) and event.entity_uuid:
                entity = Entity.get(event.entity_uuid)
                if isinstance(entity, Entity):
                    condition._deal_damage(entity, event)
            return None

        return EventHandler(
            name="Electrified Water Entry Damage",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=damage,
        )

    def _create_zone_turn_start_handler(self) -> EventHandler:
        condition = self

        def damage(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            entity = Entity.get(event.source_entity_uuid)
            if (
                isinstance(entity, Entity)
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
            event_processor=damage,
        )

    def _apply(self, execution_event: Event):
        result = super()._apply(execution_event)
        modifiers, handlers, children, spatial_handlers, effect = result
        interaction_handler = bind_spatial_interactions(
            condition=self,
            transitions=ELECTRIFIED_WATER_TRANSITIONS,
            build_replacement=build_environmental_replacement,
        )
        spatial_handlers.append(interaction_handler.uuid)
        return modifiers, handlers, children, spatial_handlers, effect


class SteamCloud(WetAreaCondition):
    """Short-lived wet, heavily obscuring cloud."""

    name: str = Field(default="Steam Cloud")
    content_ref: ContentRef = Field(default=STEAM_CLOUD_CONTENT_REF)
    layer: SpatialEffectLayer = Field(default=SpatialEffectLayer.CLOUD)
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        default=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
    )
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=2,
            duration_type=DurationType.ROUNDS,
        ),
    )
    optical_obscurement: Optional[OpticalObscurement] = (
        OpticalObscurement.HEAVY
    )


class BurningWeb(FireSurface):
    """One round of burning web fire."""

    name: str = Field(default="Burning Web")
    content_ref: ContentRef = Field(default=BURNING_WEB_CONTENT_REF)
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=lambda: frozenset({
            SpatialEffectTriggerKind.TURN_START,
        }),
    )
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=1,
            duration_type=DurationType.ROUNDS,
        ),
    )

    def _apply(self, execution_event: Event):
        result = AreaCondition._apply(self, execution_event)
        modifiers, handlers, children, spatial_handlers, effect = result
        interaction_handler = bind_spatial_interactions(
            condition=self,
            transitions=BURNING_WEB_TRANSITIONS,
        )
        spatial_handlers.append(interaction_handler.uuid)
        return modifiers, handlers, children, spatial_handlers, effect


OIL_SURFACE_CONTENT_REF = ContentRef(
    pack_id="content.neurodragon",
    definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.material.oil",
    content_version=1,
    definition_contract_hash=(
        "a74aa0ee0fa241101b5c7d3b2551d638"
        "6e4817a8ae5ad5e5cadbc4a15d5fdeb0"
    ),
)

OIL_SURFACE_TRANSITIONS = (
    SpatialEffectTransitionDefinition(
        operation=SpatialEffectInteractionOperation.IGNITE,
        action=SpatialEffectTransitionAction.REPLACE_AFFECTED,
        replacement_recipe=FIRE_SURFACE_RECIPE,
    ),
)


class OilSurface(AreaCondition):
    """Persistent slippery oil transformed directly by ignition."""

    name: str = Field(default="Oil Surface")
    description: str = Field(
        default="Slippery flammable oil creates hazardous difficult terrain.",
    )
    content_ref: ContentRef = Field(default=OIL_SURFACE_CONTENT_REF)
    layer: SpatialEffectLayer = Field(
        default=SpatialEffectLayer.GROUND_SURFACE,
    )
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        default=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
    )
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=None,
            duration_type=DurationType.PERMANENT,
        ),
    )
    adds_difficult_terrain: bool = True
    hazard_filter: HazardFilter = Field(default=HazardFilter.ALL)

    def _apply(
        self,
        execution_event: Event,
    ) -> tuple[
        list[Tuple[UUID, UUID]],
        list[UUID],
        list[UUID],
        list[UUID],
        Event,
    ]:
        """Install oil mechanics and its one direct ignition handler."""
        modifiers, handlers, children, spatial_handlers, effect = super()._apply(
            execution_event,
        )
        interaction_handler = bind_spatial_interactions(
            condition=self,
            transitions=OIL_SURFACE_TRANSITIONS,
            build_replacement=build_environmental_replacement,
        )
        spatial_handlers.append(interaction_handler.uuid)
        return modifiers, handlers, children, spatial_handlers, effect


def build_environmental_replacement(
    recipe: ContentRecipe,
    replaced: SpatialCondition,
    event: SpatialEffectInteractionEvent,
    positions: Set[Tuple[int, int]],
) -> SpatialCondition:
    """Construct the exact authored material selected by one transition."""
    condition_type: type[SpatialCondition]
    if recipe == FIRE_SURFACE_RECIPE:
        condition_type = FireSurface
    elif recipe == ICE_SURFACE_RECIPE:
        condition_type = IceSurface
    elif recipe == ELECTRIFIED_WATER_RECIPE:
        condition_type = ElectrifiedWater
    elif recipe == STEAM_CLOUD_RECIPE:
        condition_type = SteamCloud
    elif recipe == BURNING_WEB_RECIPE:
        condition_type = BurningWeb
    else:
        raise ValueError("Environmental transition selected an unknown recipe")

    fields: dict[str, object] = {
        "source_entity_uuid": event.source_entity_uuid,
        "faction": replaced.faction,
        "position": min(positions),
        "affected_positions": set(positions),
    }
    if event.duration_rounds is not None:
        fields["duration"] = Duration(
            duration=event.duration_rounds,
            duration_type=DurationType.ROUNDS,
        )
    return condition_type(**fields)


class SpikeTrap(SpatialCondition):
    """One persistent spike mechanism, its footprint and authored payload."""

    name: str = Field(default="Spike Trap")
    description: str = Field(
        default="Retractable spikes with a persistent mechanical state.",
    )
    trap_state: TrapState = TrapState.READY
    payload: TrapPayload = Field(default=PLAIN_SPIKE_PAYLOAD)
    affected_occupancy_layers: frozenset[OccupancyLayer] = frozenset({OccupancyLayer.GROUND})
    content_ref: ContentRef = Field(default=SPIKE_TRAP_CONTENT_REF)
    layer: SpatialEffectLayer = Field(
        default=SpatialEffectLayer.GROUND_SURFACE,
    )
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        default=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
    )
    blocking_policy: SpatialEffectBlockingPolicy = Field(
        default=SpatialEffectBlockingPolicy.NONE,
    )
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=lambda: frozenset({SpatialEffectTriggerKind.ENTER}),
    )
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=None,
            duration_type=DurationType.PERMANENT,
        ),
    )
    hazard_filter: HazardFilter = Field(default=HazardFilter.ALL)

    def is_hazard_perceived_by(
        self, requesting_entity_uuid: Optional[UUID] = None,
    ) -> bool:
        """A previously discovered mechanism stays known to that observer."""
        if self.trap_state is TrapState.ACTIVATED:
            return True
        observer = BaseBlock.get(requesting_entity_uuid) if requesting_entity_uuid else None
        senses = observer.get_senses() if observer is not None else None
        return bool(senses is not None and self.uuid in senses.spatial_effects) or super().is_hazard_perceived_by(
            requesting_entity_uuid,
        )

    def is_hazardous_for(
        self, entity_uuid: Optional[UUID] = None, *,
        occupancy_layer: OccupancyLayer = OccupancyLayer.GROUND,
    ) -> bool:
        """Disabled installed spikes retain identity without threatening entry."""
        return self.trap_state is not TrapState.DEACTIVATED and super().is_hazardous_for(
            entity_uuid, occupancy_layer=occupancy_layer,
        )

    def describe_trap(self) -> str:
        """Describe the current mode and the authored effects of entering it."""
        if self.trap_state is TrapState.DEACTIVATED:
            return "Retracted and disabled. Entry has no effect."
        state = ("Retracted and armed; entry raises the spikes."
                 if self.trap_state is TrapState.READY else "Raised spikes remain active.")
        effects = [f"{row.dice_count}d{row.dice_sides} {row.damage_type.value.lower()} damage"
                   for row in self.payload.damages]
        condition = self.payload.condition
        if condition is not None:
            effects.append(f"DC {condition.save_dc} {condition.save_ability} save or Poisoned "
                           f"for {condition.duration_rounds} rounds")
        return state + (" Entry: " + "; ".join(effects) + "." if effects else "")

    def get_spatial_observation(
        self, positions: Set[Tuple[int, int]], *, observer_uuid: UUID,
        discovered: bool = False,
    ) -> Optional[PerceivedSpatialEffect]:
        """Provide only the requested perceivable cells, with native state text."""
        if not discovered and not self.is_hazard_perceived_by(observer_uuid):
            return None
        return PerceivedSpatialEffect(
            content_ref=self.content_ref, name=self.name,
            description=self.describe_trap(), positions=tuple(sorted(positions)),
            trap_state=self.trap_state,
        )

    def set_trap_state(self, state: TrapState, *, parent_event: Event) -> bool:
        """Commit a mode; raising releases the payload on current occupants."""
        if not self.is_active_spatial_condition() or self.trap_state is state:
            return False
        positions = set(self.affected_positions)
        effect = self._open_change(
            SpatialEffectChangeOperation.STATE_CHANGED,
            previous_positions=positions, affected_positions=positions,
            parent_event=parent_event, trap_state=state,
            previous_trap_state=self.trap_state,
        )
        self.trap_state = state
        if state is TrapState.ACTIVATED:
            self.reveal(parent_event=effect)
            occupants = {identity for position in positions
                         for identity in get_map().get_entities_at(position)}
            for identity in sorted(occupants, key=str):
                entity = Entity.get(identity)
                if isinstance(entity, Entity):
                    self.apply_payload(entity, parent_event=effect)
        self._complete_change(effect)
        return True

    def apply_payload(self, entity: Entity, *, parent_event: Event) -> None:
        """Compose the finite spike payload through ordinary native rule owners."""
        if not self.affects_occupancy_layer(entity.get_occupancy_layer()):
            return
        for component in self.payload.damages:
            bonus = ModifiableValue.create(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=entity.uuid, base_value=0,
                value_name="Spike Trap Damage",
            )
            damage = Damage(
                name=self.name, source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=entity.uuid,
                damage_dice=component.dice_sides, dice_numbers=component.dice_count,
                damage_bonus=bonus, damage_type=component.damage_type,
            )
            roll = damage.get_dice(AttackOutcome.HIT).roll
            entity.receive_damage(
                roll.total, component.damage_type, self.source_entity_uuid,
                damage_rolls=[roll], damages=[damage], parent_event=parent_event.uuid,
                effect_id=self.content_ref.identity_key,
            )
        condition = self.payload.condition
        if condition is None:
            return
        request = entity.create_saving_throw_request(
            target_entity_uuid=entity.uuid, ability_name=condition.save_ability,
            dc=condition.save_dc, parent_event=parent_event.uuid,
            saving_throw_context=SavingThrowContext(
                cause_id=self.content_ref.content_id,
                effect_id=f"{self.content_ref.content_id}.poisoned_save",
                condition_id=condition.condition_id, is_magical=False,
                effect_tags=(SavingThrowEffectTag.POISON,),
            ),
        )
        _, _, success = entity.saving_throw(request)
        if not success:
            entity.add_condition(Poisoned(
                source_entity_uuid=self.source_entity_uuid, target_entity_uuid=entity.uuid,
                duration=Duration(duration=condition.duration_rounds, duration_type=DurationType.ROUNDS,
                                  source_entity_uuid=self.source_entity_uuid, target_entity_uuid=entity.uuid),
            ), parent_event=parent_event)

    def _apply(
        self,
        execution_event: Event,
    ) -> tuple[
        list[Tuple[UUID, UUID]],
        list[UUID],
        list[UUID],
        list[UUID],
        Event,
    ]:
        """Install one footprint and one shared entry handler."""
        modifiers, handlers, children, spatial_handlers, effect = super()._apply(
            execution_event,
        )
        handler = self._create_entry_handler()
        EventQueue.add_spatial_handler(
            handler,
            set(self.affected_positions),
            EventType.SPATIAL_ENTITY_ENTERED,
            EventPhase.EFFECT,
        )
        spatial_handlers.append(handler.uuid)
        return modifiers, handlers, children, spatial_handlers, effect

    def _create_entry_handler(self) -> EventHandler:
        """Build the sole entry handler owned by this trap network."""
        condition = self

        def damage_entering_entity(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent):
                return None
            if not condition.admits_occupancy_transition(event):
                return None
            if event.entity_uuid is None:
                return None
            entity = Entity.get(event.entity_uuid)
            if not isinstance(entity, Entity):
                return None

            if condition.trap_state is TrapState.DEACTIVATED:
                return None
            if condition.trap_state is TrapState.READY:
                condition.set_trap_state(TrapState.ACTIVATED, parent_event=event)
            else:
                condition.apply_payload(entity, parent_event=event)
            return None

        return EventHandler(
            name="Spike Trap Entry Damage",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.SPATIAL_ENTITY_ENTERED,
                    event_phase=EventPhase.EFFECT,
                ),
            ],
            event_processor=damage_entering_entity,
        )

    def reveal(self, *, parent_event: Event) -> bool:
        """Reveal the complete network once after its first trigger."""
        if not self.is_active_spatial_condition():
            return False
        if self.condition_stealth_dc is None:
            return False
        previous = set(self.affected_positions)
        change_effect = self._open_change(
            SpatialEffectChangeOperation.REVEALED,
            previous_positions=previous,
            affected_positions=previous,
            parent_event=parent_event,
        )
        self.condition_stealth_dc = None
        self._complete_change(change_effect)
        return True

    def extend_footprint(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> bool:
        """Extend this stable network identity through the footprint writer."""
        expanded = set(self.affected_positions) | set(positions)
        if expanded == self.affected_positions:
            return False
        return self.change_footprint(expanded, parent_event=parent_event)


def materialize_spike_trap_condition(
    positions: Set[Tuple[int, int]],
    *,
    condition_uuid: Optional[UUID] = None,
    stealth_dc: Optional[int] = None,
    source_entity_uuid: Optional[UUID] = None,
    parent_event: Optional[Event] = None,
    trap_state: TrapState = TrapState.READY,
    payload: TrapPayload = PLAIN_SPIKE_PAYLOAD,
    content_ref: ContentRef = SPIKE_TRAP_CONTENT_REF,
) -> SpikeTrap:
    """Construct and activate one exact physical spike-trap network."""
    if not positions:
        raise ValueError("Spike trap requires at least one position")
    source_uuid = source_entity_uuid or uuid4()
    owns_root = parent_event is None
    cause = parent_event
    if cause is None:
        declaration = EventQueue.publish_declaration(Event(
            name="Install Spike Trap",
            source_entity_uuid=source_uuid,
            source_entity_name="Environment",
            event_type=EventType.BASE_ACTION,
            phase=EventPhase.DECLARATION,
            use_register=False,
        ))
        if declaration.canceled:
            raise RuntimeError("Spike-trap installation was canceled")
        execution = declaration.phase_to(EventPhase.EXECUTION)
        if execution.canceled:
            raise RuntimeError("Spike-trap installation was canceled")
        cause = execution.phase_to(EventPhase.EFFECT)
        if cause.canceled:
            raise RuntimeError("Spike-trap installation was canceled")

    assert cause is not None
    condition = SpikeTrap(
        uuid=condition_uuid or uuid4(), source_entity_uuid=source_uuid,
        position=min(positions), affected_positions=set(positions),
        condition_stealth_dc=stealth_dc, trap_state=trap_state, payload=payload,
        content_ref=content_ref,
    )
    result = condition.activate(parent_event=cause)
    if result is None or result.canceled or not condition.applied:
        raise RuntimeError("Spike-trap activation failed")
    if owns_root:
        cause.phase_to(EventPhase.COMPLETION)
    return condition


def extend_spike_trap_condition(
    condition: SpikeTrap,
    positions: Set[Tuple[int, int]],
    *,
    parent_event: Event,
) -> bool:
    """Extend an installed trap without changing its stable identity."""
    return condition.extend_footprint(positions, parent_event=parent_event)


__all__ = [
    "BURNING_WEB_CONTENT_REF",
    "BURNING_WEB_RECIPE",
    "BURNING_WEB_TRANSITIONS",
    "BurningWeb",
    "ELECTRIFIED_WATER_CONTENT_REF",
    "ELECTRIFIED_WATER_RECIPE",
    "ELECTRIFIED_WATER_TRANSITIONS",
    "ElectrifiedWater",
    "FIRE_SURFACE_CONTENT_REF",
    "FIRE_SURFACE_RECIPE",
    "FIRE_SURFACE_TRANSITIONS",
    "FireSurface",
    "ICE_SURFACE_CONTENT_REF",
    "ICE_SURFACE_RECIPE",
    "ICE_SURFACE_TRANSITIONS",
    "IceSurface",
    "OIL_SURFACE_CONTENT_REF",
    "OIL_SURFACE_TRANSITIONS",
    "OilSurface",
    "POISON_DAMAGE_SPIKE_CONTENT_REF",
    "SICKENING_SPIKE_CONTENT_REF",
    "SPIKE_TRAP_CONTENT_REF",
    "STEAM_CLOUD_CONTENT_REF",
    "STEAM_CLOUD_RECIPE",
    "SteamCloud",
    "SpikeTrap",
    "WET_SURFACE_CONTENT_REF",
    "WET_SURFACE_RECIPE",
    "WET_SURFACE_TRANSITIONS",
    "Wet",
    "WetAreaCondition",
    "WetSurface",
    "WetSurfaceMembership",
    "build_environmental_replacement",
    "extend_spike_trap_condition",
    "materialize_spike_trap_condition",
]
