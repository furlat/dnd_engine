"""Authored environmental conditions with independent world ownership."""

from typing import ClassVar, NotRequired, Optional, Set, Tuple, TypedDict
from uuid import UUID, uuid4

from pydantic import Field, PrivateAttr

from dnd.core.base_block import BaseBlock, LightLevel
from dnd.core.base_conditions import BaseCondition, ConditionApplicationEvent, Duration
from dnd.core.condition_types import (
    ConditionCategory,
    ConditionRemovalTrigger,
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
from dnd.core.dice import AttackOutcome, roll_die_face
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
from dnd.core.gridmap import CrossingChannel, get_map
from dnd.core.modifiers import NumericalModifier, ResistanceModifier, ResistanceStatus
from dnd.core.values import ModifiableValue, Channel, Kind, add_modifier, parts, remove_modifier
from dnd.conditions import Coughing, Poisoned, Prone
from dnd.core.saving_throw_types import SavingThrowContext, SavingThrowEffectTag
from dnd.entity import Entity
from dnd.spatial.area_conditions import AreaCondition, SpatialCondition
from dnd.spatial.memberships import (
    MembershipAreaCondition,
    SpatialConditionMembershipSource,
)
from dnd.spatial.transitions import bind_spatial_interactions
from dnd.types.senses import OpticalObscurement, PerceivedSpatialEffect
from dnd.types.material_deposits import MaterialDepositSource
from dnd.types.traps import TrapConditionPayload, TrapDamage, TrapPayload, TrapState
from dnd.types.world import OccupancyLayer, SpatialChannel
from dnd.types.spatial_effects import (
    SpatialEffectAnchorKind,
    SpatialEffectBlockingPolicy,
    SpatialEffectChangeOperation,
    SpatialEffectInteractionOperation,
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
    SpatialEffectTransitionAction,
)
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import BodyPart
from dnd.types.materials import Material


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

DRY_TRANSITION = SpatialEffectTransitionDefinition(
    operation=SpatialEffectInteractionOperation.DRY,
    action=SpatialEffectTransitionAction.REMOVE_AFFECTED,
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
    DRY_TRANSITION,
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
    has_visible_presence: bool = True
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
        damage_bonus = ModifiableValue(
            source_entity_uuid=self.source_entity_uuid,
            base=0,
            name="Fire Surface Damage",
        )
        damage = Damage(
            name="Fire Surface",
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=entity.uuid,
            damage_dice=4,
            dice_numbers=2,
            damage_bonus=parts(damage_bonus),
            damage_type=DamageType.FIRE,
            effect_origin=self.effect_origin,
        )
        damage_roll = damage.get_dice(AttackOutcome.HIT).roll
        entity.receive_damage(
            damage_roll.total,
            DamageType.FIRE,
            self.source_entity_uuid,
            damage_rolls=[damage_roll],
            damages=[damage],
            parent_event=parent_event.uuid,
            effect_id=self.content_ref.identity_key, independent_resolution=True,
            effect_origin=self.effect_origin,
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
                    event_phase=EventPhase.EXECUTION,
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
                add_modifier(target.health.damage_reduction, Channel.SELF_STATIC, Kind.RESISTANCE, ResistanceModifier(
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
        def reject_incompatible(incoming: Event, _: UUID):
            if (isinstance(incoming, ConditionApplicationEvent) and not incoming.canceled
                    and self.applied and self.contributions_active()
                    and incoming.condition.blocked_while_wet):
                return incoming.cancel(status_message="Active Wet prevents this condition")
            return None

        handler = EventHandler(name="Wet condition admission", source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.CONDITION_APPLICATION,
                event_phase=EventPhase.DECLARATION, event_target_entity_uuid=target.uuid)],
            event_processor=reject_incompatible)
        target.add_event_handler(handler)
        return modifiers, [handler.uuid], [], [], effect


    def on_membership_changed(self,event: Event) -> None:
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if self.applied and target is not None:
            for condition in tuple(target.active_conditions_by_uuid.values()):
                if ConditionRemovalTrigger.WET_APPLICATION in condition.removal_triggers:
                    target.remove_condition_by_uuid(condition.uuid,parent_event=event)


class WetSurfaceMembership(SpatialConditionMembershipSource):
    """Exact Wet lease contributed by one water-bearing condition."""
    creates = (Wet,)

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
        manifestation = self._find_wet(target)
        if manifestation is None:
            manifestation = self.create_manifestation(target)
            manifestation.parent_condition = self.uuid
            result = target.add_condition(
                manifestation,
                parent_event=execution_event,
            )
            if result is None or result.canceled:
                return [], [], [], [], execution_event.cancel(
                    status_message="Wet manifestation was rejected",
                )
        self.add_shared_subcondition(manifestation)
        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
        )
        return [], [], [], [], effect

class WetAreaCondition(MembershipAreaCondition):
    """Continuous Wet membership shared by water-bearing conditions."""
    creates = (WetSurfaceMembership,)

    def _apply(self, execution_event: Event):
        modifiers, handlers, children, spatial, effect = super()._apply(execution_event)
        if effect is not None and not effect.canceled:
            handler = bind_spatial_interactions(condition=self, transitions=(DRY_TRANSITION,))
            spatial.append(handler.uuid)
        return modifiers, handlers, children, spatial, effect


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
    description: str = Field(default="Water makes creatures standing in it Wet.")
    has_visible_presence: bool = True
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
    creates = (Prone,)

    name: str = Field(default="Ice Surface")
    description: str = Field(default="Difficult terrain; creatures must make a Dexterity save or fall Prone.")
    has_visible_presence: bool = True
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
    description: str = Field(default="Electrified water makes creatures Wet and deals lightning damage.")
    has_visible_presence: bool = True
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
        damage_bonus = ModifiableValue(
            source_entity_uuid=self.source_entity_uuid,
            base=0,
            name="Electrified Water Damage",
        )
        damage = Damage(
            name="Electrified Water",
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=entity.uuid,
            damage_dice=4,
            dice_numbers=1,
            damage_bonus=parts(damage_bonus),
            damage_type=DamageType.LIGHTNING,
            effect_origin=self.effect_origin,
        )
        damage_roll = damage.get_dice(AttackOutcome.HIT).roll
        entity.receive_damage(
            damage_roll.total,
            DamageType.LIGHTNING,
            self.source_entity_uuid,
            damage_rolls=[damage_roll],
            damages=[damage],
            parent_event=parent_event.uuid,
            effect_id=self.content_ref.identity_key, independent_resolution=True,
            effect_origin=self.effect_origin,
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
                event_phase=EventPhase.EXECUTION,
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
    description: str = Field(default="Steam makes creatures Wet and heavily obscures the area.")
    has_visible_presence: bool = True
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
    creates = (FireSurface,)

    name: str = Field(default="Oil Surface")
    has_visible_presence: bool = True
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


class EnvironmentalReplacementFields(TypedDict):
    """Only the authored transition inputs forwarded to the selected material."""

    source_entity_uuid: UUID
    faction: str | None
    position: tuple[int, int]
    affected_positions: set[tuple[int, int]]
    deposit_source: MaterialDepositSource | None
    affected_occupancy_layers: NotRequired[frozenset[OccupancyLayer]]
    duration: NotRequired[Duration]


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

    fields: EnvironmentalReplacementFields = {
        "source_entity_uuid": event.source_entity_uuid,
        "faction": replaced.faction,
        "position": min(positions),
        "affected_positions": set(positions),
        "deposit_source": replaced.deposit_source,
    }
    if recipe in (FIRE_SURFACE_RECIPE, ICE_SURFACE_RECIPE, ELECTRIFIED_WATER_RECIPE):
        # A transformed ground material keeps its actual contact domain. Steam
        # is a cloud and deliberately retains its own occupancy defaults.
        fields["affected_occupancy_layers"] = replaced.affected_occupancy_layers
    if event.duration_rounds is not None:
        fields["duration"] = Duration(
            duration=event.duration_rounds,
            duration_type=DurationType.ROUNDS,
        )
    return condition_type(**fields)


class SpikeTrap(SpatialCondition):
    """One persistent spike mechanism, its footprint and authored payload."""
    creates = (Poisoned,)

    crossing_channels: ClassVar[frozenset[CrossingChannel] | None] = frozenset()

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

    def spatial_channels(self) -> frozenset[SpatialChannel]:
        return super().spatial_channels() | {SpatialChannel.MOVEMENT}

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
        observer = Entity.get(observer_uuid)
        return PerceivedSpatialEffect(
            content_ref=self.content_ref, name=self.name,
            description=self.describe_trap(), positions=tuple(sorted(positions)),
            trap_state=self.trap_state,
            anchor_item_uuid=(self.anchor_uuid if self.anchor_kind is SpatialEffectAnchorKind.WORLD_OBJECT
                and observer is not None and self.anchor_uuid in observer.senses.objects else None),
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
        self.observation_revision += 1
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
            bonus = ModifiableValue(
                source_entity_uuid=self.source_entity_uuid,
                base=0,
                name="Spike Trap Damage",
            )
            damage = Damage(
                name=self.name, source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=entity.uuid,
                damage_dice=component.dice_sides, dice_numbers=component.dice_count,
                damage_bonus=parts(bonus), damage_type=component.damage_type,
            )
            roll = damage.get_dice(AttackOutcome.HIT).roll
            entity.receive_damage(
                roll.total, component.damage_type, self.source_entity_uuid,
                damage_rolls=[roll], damages=[damage], parent_event=parent_event.uuid,
                effect_id=self.content_ref.identity_key, independent_resolution=True,
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


ELECTRIC_FLOOR_CONTENT_REF = SPIKE_TRAP_CONTENT_REF.model_copy(update={
    "content_id": "spatial_effect.environment.electric_floor",
})
GRAY_MOLD_CONTENT_REF = SPIKE_TRAP_CONTENT_REF.model_copy(update={
    "content_id": "spatial_effect.environment.gray_mold",
})


class ElectricFloor(AreaCondition):
    """Charged floor plates: every entered plate asks a Dexterity save against lightning."""

    name: str = Field(default="Electric floor")
    description: str = Field(default="Entering a charged plate requires a Dexterity save or deals 1d4 lightning.")
    has_visible_presence: bool = True
    content_ref: ContentRef = Field(default=ELECTRIC_FLOOR_CONTENT_REF)
    layer: SpatialEffectLayer = SpatialEffectLayer.GROUND_SURFACE
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.ENTER})
    hazard_filter: HazardFilter = HazardFilter.ALL
    duration: Duration = Field(default_factory=lambda: Duration(duration=None, duration_type=DurationType.PERMANENT))
    save_dc: int = Field(default=13, ge=0)

    def equipment_modifiers(self, entity: Entity) -> tuple[tuple[str, int], ...]:
        """Metal armor is -4 on the save; anything worn on the feet (boots or equivalent) is +2."""
        armor = entity.equipment.get_item_by_slot(BodyPart.BODY)
        footwear = entity.equipment.get_item_by_slot(BodyPart.FEET)
        return ((("Metal armor on charged plates", -4),) if armor is not None and Material.METAL.value in armor.tags
                else ()) + ((("Footwear on charged plates", 2),) if footwear is not None else ())

    def _shock(self, entity: Entity, *, parent_event: Event) -> None:
        save = entity.saving_throws.get_saving_throw("dexterity").bonus
        modifiers = tuple(NumericalModifier(name=name, value=value, source_entity_uuid=self.uuid,
                                            target_entity_uuid=entity.uuid)
                          for name, value in self.equipment_modifiers(entity))
        for modifier in modifiers:
            add_modifier(save, Channel.SELF_STATIC, Kind.VALUE, modifier)
        try:
            request = entity.create_saving_throw_request(target_entity_uuid=entity.uuid,
                ability_name="dexterity", dc=self.save_dc, parent_event=parent_event.uuid,
                saving_throw_context=SavingThrowContext(cause_id=self.content_ref.content_id,
                    effect_id=f"{self.content_ref.content_id}.entry", is_magical=False))
            _, _, saved = entity.saving_throw(request)
        finally:
            for modifier in modifiers:
                remove_modifier(save, modifier.uuid)
                modifier.remove_from_register()
        if saved:
            return
        damage = Damage(name=self.name, source_entity_uuid=self.uuid, target_entity_uuid=entity.uuid,
            damage_dice=4, dice_numbers=1, damage_type=DamageType.LIGHTNING,
            damage_bonus=parts(ModifiableValue(source_entity_uuid=self.uuid, base=0, name="Electric floor damage")))
        roll = damage.get_dice(AttackOutcome.HIT).roll
        entity.receive_damage(roll.total, DamageType.LIGHTNING, self.uuid, damage_rolls=[roll], damages=[damage],
            parent_event=parent_event.uuid, effect_id=self.content_ref.identity_key, independent_resolution=True)

    def _create_zone_entry_handler(self) -> EventHandler:
        def shock(event: Event, _source_entity_uuid: UUID) -> None:
            entity = Entity.get(event.entity_uuid) if isinstance(event, SpatialChangeEvent) and event.entity_uuid else None
            if isinstance(entity, Entity):
                self._shock(entity, parent_event=event)

        return EventHandler(name="Electric floor entry", source_entity_uuid=self.uuid,
            trigger_conditions=[Trigger(event_type=EventType.SPATIAL_ENTITY_ENTERED, event_phase=EventPhase.EFFECT)],
            event_processor=shock)


class GrayMold(AreaCondition):
    """A moldy floor whose spores erupt when someone steps in, once per continuous stay."""
    creates = (Coughing,)

    name: str = Field(default="Gray mold")
    description: str = Field(default="Stepping in makes the spores erupt: a Constitution save or 1d6 rounds of coughing.")
    has_visible_presence: bool = True
    content_ref: ContentRef = Field(default=GRAY_MOLD_CONTENT_REF)
    layer: SpatialEffectLayer = SpatialEffectLayer.GROUND_SURFACE
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({
        SpatialEffectTriggerKind.ENTER, SpatialEffectTriggerKind.LEAVE})
    hazard_filter: HazardFilter = HazardFilter.ALL
    duration: Duration = Field(default_factory=lambda: Duration(duration=None, duration_type=DurationType.PERMANENT))
    save_dc: int = Field(default=13, ge=0)
    _exposed_occupants: Set[UUID] = PrivateAttr(default_factory=set)  # rolled during their current stay

    def _erupt(self, *, parent_event: Event) -> None:
        for entity in self._occupants_at(set(self.affected_positions)):
            if entity.uuid in self._exposed_occupants:
                continue
            self._exposed_occupants.add(entity.uuid)
            request = entity.create_saving_throw_request(target_entity_uuid=entity.uuid,
                ability_name="constitution", dc=self.save_dc, parent_event=parent_event.uuid,
                saving_throw_context=SavingThrowContext(cause_id=self.content_ref.content_id,
                    effect_id=f"{self.content_ref.content_id}.spores", is_magical=False,
                    effect_tags=(SavingThrowEffectTag.POISON,)))
            _, _, saved = entity.saving_throw(request)
            if not saved:
                entity.add_condition(Coughing(source_entity_uuid=self.uuid, target_entity_uuid=entity.uuid,
                    duration=Duration(duration=roll_die_face(6), duration_type=DurationType.ROUNDS,
                                      source_entity_uuid=self.uuid, target_entity_uuid=entity.uuid)),
                    parent_event=parent_event)

    def _create_zone_entry_handler(self) -> EventHandler:
        def erupt(event: Event, _source_entity_uuid: UUID) -> None:
            if isinstance(event, SpatialChangeEvent) and event.entity_uuid is not None:
                self._erupt(parent_event=event)

        return EventHandler(name="Gray mold spores", source_entity_uuid=self.uuid,
            trigger_conditions=[Trigger(event_type=EventType.SPATIAL_ENTITY_ENTERED, event_phase=EventPhase.EFFECT)],
            event_processor=erupt)

    def _create_zone_exit_handler(self) -> EventHandler:
        def leave(event: Event, _source_entity_uuid: UUID) -> None:
            entity = Entity.get(event.entity_uuid) if isinstance(event, SpatialChangeEvent) and event.entity_uuid else None
            if isinstance(entity, Entity) and entity.position not in self.affected_positions:
                self._exposed_occupants.discard(entity.uuid)

        return EventHandler(name="Gray mold exit", source_entity_uuid=self.uuid,
            trigger_conditions=[Trigger(event_type=EventType.SPATIAL_ENTITY_LEFT, event_phase=EventPhase.EFFECT)],
            event_processor=leave)


def install_authored_area_condition(condition: AreaCondition, *, parent_event: Optional[Event] = None) -> None:
    """Activate one authored environmental area, under its own root cause when none is given."""
    cause = parent_event
    if cause is None:
        cause = EventQueue.publish_declaration(Event(name=f"Install {condition.name}",
            source_entity_uuid=condition.source_entity_uuid, source_entity_name="Environment",
            event_type=EventType.BASE_ACTION, phase=EventPhase.DECLARATION, use_register=False))
        for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
            if cause.canceled:
                raise RuntimeError(f"{condition.name} installation was canceled")
            cause = cause.phase_to(phase)
        if cause.canceled:
            raise RuntimeError(f"{condition.name} installation was canceled")
    result = condition.activate(parent_event=cause)
    if result is None or result.canceled or not condition.applied:
        raise RuntimeError(f"{condition.name} activation failed")
    if parent_event is None:
        cause.phase_to(EventPhase.COMPLETION)


def materialize_electric_floor(positions: Set[Tuple[int, int]], *,
                               parent_event: Optional[Event] = None) -> ElectricFloor:
    """The charged plates of an authored floor; safe cells such as carpet are simply left out."""
    identity = uuid4()
    floor = ElectricFloor(uuid=identity, source_entity_uuid=identity, position=min(positions),
                          affected_positions=set(positions))
    install_authored_area_condition(floor, parent_event=parent_event)
    return floor


def materialize_gray_mold(positions: Set[Tuple[int, int]], *, parent_event: Optional[Event] = None) -> GrayMold:
    """One authored moldy floor."""
    identity = uuid4()
    mold = GrayMold(uuid=identity, source_entity_uuid=identity, position=min(positions),
                    affected_positions=set(positions))
    install_authored_area_condition(mold, parent_event=parent_event)
    return mold


__all__ = [
    "BURNING_WEB_CONTENT_REF",
    "BURNING_WEB_RECIPE",
    "BURNING_WEB_TRANSITIONS",
    "BurningWeb",
    "ELECTRIC_FLOOR_CONTENT_REF",
    "ELECTRIFIED_WATER_CONTENT_REF",
    "ELECTRIFIED_WATER_RECIPE",
    "ELECTRIFIED_WATER_TRANSITIONS",
    "ElectricFloor",
    "ElectrifiedWater",
    "FIRE_SURFACE_CONTENT_REF",
    "FIRE_SURFACE_RECIPE",
    "FIRE_SURFACE_TRANSITIONS",
    "FireSurface",
    "GRAY_MOLD_CONTENT_REF",
    "GrayMold",
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
    "install_authored_area_condition",
    "materialize_electric_floor",
    "materialize_gray_mold",
    "materialize_spike_trap_condition",
]

