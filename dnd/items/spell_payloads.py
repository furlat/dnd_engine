"""Concrete Freezing Sphere and Delayed Blast Fireball items and ending owners.

This module sits below spell roots so temporary-item actions never import a
spell school. Payload power and source are retained data, independent of holder.
"""

from collections.abc import Mapping
from typing import Literal, Optional, Tuple
from uuid import UUID

from pydantic import Field, PrivateAttr

from dnd.actions import (
    PreparedSpellConcentration,
    SpellAction,
    SpellEvent,
    entity_action_economy_cost_applier,
    entity_action_economy_cost_evaluator,
)
from dnd.blocks.base_item import BaseItem, PreparedItemRetirement, UsableItem
from dnd.core.action_types import ActionSelection, ActionVariantFacet, selection_facet
from dnd.core.aoe import Sphere, objective_footprint
from dnd.core.base_actions import BaseAction, Cost, TargetType
from dnd.core.base_block import BaseBlock, PreparedConditionApplication
from dnd.core.base_conditions import BaseCondition, Duration, SpellProtectionRegistry
from dnd.core.condition_types import ConditionTag, DurationType
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome
from dnd.core.effect_types import EffectOrigin
from dnd.types.event_facts import GroupEntryKind, HandlerGroupDispatch
from dnd.core.events import (
    Damage,
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Range,
    RangeType,
    SavingThrowEvent,
    Trigger,
)
from dnd.core.geometry import grid_distance_feet
from dnd.core.gridmap import PreparedObjectPlacement, get_map
from dnd.core.saving_throw_types import SavingThrowContext
from dnd.core.values import ModifiableValue
from dnd.core.spell_damage import roll_spell_damage
from dnd.core.effect_applications import admit_effect_application
from dnd.entity import Entity
from dnd.spatial.area_reach import ReachStage, resolve_staged_area
from dnd.spatial.environmental_conditions import IceSurface
from dnd.spatial.ignition import apply_elemental_surface_contacts
from dnd.spells.content_metadata import srd_action_identity
from dnd.spells.spell_utils import placement_error
from dnd.types.discovery import ActorScan, ScanRecord
from dnd.types.physical_access import PhysicalAccess


def payload_blast(
    source_uuid: UUID,
    center: tuple[int, int],
    *,
    kind: Literal["freezing", "delayed_fire"],
    dc: int,
    dice_count: int,
    origin: EffectOrigin | None,
    parent: Event,
) -> None:
    """Native connected reach, saves, independent packets and material contacts."""
    damage_type = DamageType.COLD if kind == "freezing" else DamageType.FIRE
    spell_id = (
        "spell.freezing_sphere"
        if kind == "freezing"
        else "spell.delayed_blast_fireball"
    )
    level = 6 if kind == "freezing" else 7
    emitted = origin.model_copy(update={"source_position": center, "area_application":True,"harmful":True}) if origin else None
    shape = Sphere(radius_feet=20, propagation="line_of_effect" if kind == "freezing" else "connected")
    excluded = SpellProtectionRegistry.get_excluded_positions(center, level)

    def footprint() -> set[tuple[int, int]]:
        cells = set(objective_footprint(shape, center, center)) - excluded
        if kind == "freezing":
            cells = {cell for cell in cells
                     if get_map().can_reach_between(center, cell, PhysicalAccess.PROJECTILE, source_uuid)}
        return cells

    def recipients(reached: frozenset[tuple[int, int]], contacts: Mapping[UUID, tuple[int, int]]) -> list[UUID]:
        identities = {identity for cell in reached for identity in get_map().get_entities_at(cell)}
        if kind == "delayed_fire":
            identities.update(identity for identity in contacts
                if isinstance(item := BaseBlock.get(identity), BaseItem) and item.is_breakable())
        return sorted(identities, key=str)

    def resolve(stage: ReachStage) -> bool:
        effect = SpellEvent(
            name="Freezing Sphere explosion"
            if kind == "freezing"
            else "Delayed Blast Fireball explosion",
            source_entity_uuid=source_uuid,
            source_position=center,
            effect_source_position=center,
            retained_effect_origin=emitted,
            spell_id=spell_id.removeprefix("spell."),
            spell_level=level,
            cast_at_level=level,
            event_type=EventType.BASE_ACTION,
            target_type=TargetType.POSITION_AOE,
            resolved_area_positions=tuple(sorted(stage.reached)),
            parent_event=parent.uuid,
            phase=EventPhase.EFFECT,
        )
        if effect.canceled:
            return False
        for identity in stage.recipients:
            target = BaseBlock.get(identity)
            if target is None:
                continue
            success = False
            if emitted is not None and not admit_effect_application(source_uuid, target.uuid,
                    origin=emitted, parent=effect, source_position=center, target_position=target.position):
                continue
            if isinstance(target, Entity):
                request = SavingThrowEvent(
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=target.uuid,
                    ability_name="constitution" if kind == "freezing" else "dexterity",
                    dc=dc,
                    parent_event=effect.uuid,
                    saving_throw_context=SavingThrowContext(
                        cause_id=spell_id,
                        effect_id=spell_id + ".explosion",
                        is_magical=True,
                    ),
                )
                success = target.saving_throw(request)[2]
            damage = Damage(
                name=effect.name,
                source_entity_uuid=source_uuid,
                target_entity_uuid=target.uuid,
                damage_dice=6,
                dice_numbers=dice_count,
                damage_type=damage_type,
                effect_origin=emitted,
                damage_bonus=ModifiableValue.create(
                    source_entity_uuid=source_uuid, base_value=0
                ),
            )
            roll = roll_spell_damage(damage, parent_event=effect, attack_outcome=AttackOutcome.HIT, effect_origin=emitted)
            amount = roll.total // 2 if success else roll.total
            if isinstance(target, Entity):
                target.receive_damage(
                    amount,
                    damage_type,
                    source_uuid,
                    damages=[damage],
                    damage_rolls=[roll],
                    parent_event=effect.uuid,
                    effect_origin=emitted,
                    independent_resolution=True,
                )
            elif isinstance(target, BaseItem):
                target.receive_damage(
                    amount,
                    damage_type,
                    source_uuid,
                    damages=[damage],
                    damage_rolls=[roll],
                    parent_event=effect,
                )
        apply_elemental_surface_contacts(effect, stage.newly_reached, damage_type)
        effect.phase_to(EventPhase.COMPLETION)
        return True

    # Every creature in the blast takes it at once, from one damage roll.
    with EventQueue.group(GroupEntryKind.AREA_APPLICATION, root=parent, shares_damage_rolls=True):
        displayed = resolve_staged_area(footprint, recipients, resolve,
            geometric_positions=shape.geometric_positions(center, center), origin=center)
    if kind == "freezing" and displayed:
        ice = IceSurface(
            source_entity_uuid=source_uuid,
            position=center,
            affected_positions=set(displayed),
            slip_save_dc=dc,
            duration=Duration(duration=10, duration_type=DurationType.ROUNDS),
            effect_origin=emitted,
        )
        ice.activate(parent_event=parent)


class SpellPayloadItem(UsableItem):
    name: str = "Spell payload"
    description: str = (
        "Temporary sphere retaining its original caster, saving throw DC and power."
    )
    payload_kind: Literal["freezing", "delayed_fire"]
    original_caster_uuid: UUID
    spell_dc: int
    dice_count: int
    effect_origin: EffectOrigin | None = None
    lifetime_uuid: UUID | None = None
    is_magical: bool = True
    is_consumable: bool = False
    is_pickable: bool = True
    weight: float = 0.1
    charges: int = -1
    max_charges: int = -1
    discharged: bool = False
    detonation_requested: bool = False
    defer_detonation: bool = False
    impact_position: tuple[int, int] | None = None
    _destruction_parent: Event | None = PrivateAttr(default=None)

    def payload_position(self) -> tuple[int, int] | None:
        current: BaseItem = self
        seen: set[UUID] = set()
        while current.stored_in_uuid is not None and current.uuid not in seen:
            seen.add(current.uuid)
            container = BaseBlock.get(current.stored_in_uuid)
            if not isinstance(container, BaseItem):
                break
            current = container
        holder = Entity.get(current.owner_uuid) if current.owner_uuid else None
        return (
            holder.position
            if holder is not None
            else get_map().get_object_position(current.uuid)
        )

    def get_use_actions(self, user_entity_uuid: UUID):
        actions = super().get_use_actions(user_entity_uuid)
        held = self.owner_uuid == user_entity_uuid or self.stored_in_uuid is not None
        return [
            action
            for action in actions
            if isinstance(action, ThrowSpellPayload)
            and (held or self.payload_kind == "freezing")
            or isinstance(action, TouchDelayedFireball)
            and not held
            and self.payload_kind == "delayed_fire"
        ]

    def _on_destroy(self, parent_event: Event | None):
        self.impact_position = self.payload_position()
        self.detonation_requested = True
        self._destruction_parent = parent_event

    def commit_retirement(
        self, prepared: PreparedItemRetirement, *, publish: bool = True
    ):
        try:
            super().commit_retirement(prepared, publish=publish)
        finally:
            if (
                prepared.committed
                and self.detonation_requested
                and not self.defer_detonation
            ):
                # A bead broken inside a simultaneous area detonates after it (plan §5.6).
                parent = prepared.parent_event or self._destruction_parent
                EventQueue.after_group(lambda: self.explode(parent))

    def explode(self, parent: Event | None):
        if self.discharged:
            return
        self.discharged = True
        if self.impact_position is not None and parent is not None:
            payload_blast(
                self.original_caster_uuid,
                self.impact_position,
                kind=self.payload_kind,
                dc=self.spell_dc,
                dice_count=self.dice_count,
                origin=self.effect_origin,
                parent=parent,
            )
        caster = Entity.get(self.original_caster_uuid)
        owner = (
            caster.active_conditions_by_uuid.get(self.lifetime_uuid)
            if caster is not None and self.lifetime_uuid
            else None
        )
        if caster is not None and owner is not None and owner.applied:
            caster.remove_condition_by_uuid(owner.uuid, parent_event=parent)

    def retire(self, parent_event=None):
        if (
            self.detonation_requested
            and not self.defer_detonation
            and parent_event is not None
        ):
            center = self.impact_position or self.payload_position()
            if center is None:
                return False
            return self.detonate(center, parent_event)
        return super().retire(parent_event)

    def detonate(self, center: tuple[int, int], parent: Event) -> bool:
        if self.discharged or BaseBlock.get(self.uuid) is not self:
            return False
        self.impact_position = center
        self.detonation_requested = True
        caster = Entity.get(self.original_caster_uuid)
        owner = (
            caster.active_conditions_by_uuid.get(self.lifetime_uuid)
            if caster is not None and self.lifetime_uuid
            else None
        )
        if caster is not None and owner is not None and owner.applied:
            accepted = caster.remove_condition_by_uuid(owner.uuid, parent_event=parent)
            if not accepted:
                self.detonation_requested = False
                self.impact_position = None
            return accepted
        with BaseBlock.condition_removal_scope():
            prepared = self.prepare_retirement(parent)
            if prepared is None:
                self.detonation_requested = False
                self.impact_position = None
                return False
            self.commit_retirement(prepared)
        return True


def payload_destination_error(
    action: BaseAction, scan: ActorScan, selection: ActionSelection
) -> str | None:
    """An existing, seen impact tile in throw range that a projectile from the actor reaches."""
    error = placement_error(action, scan, selection)
    if error is not None:
        return error
    if not get_map().can_reach_between(
        scan.position, selection.positions[0], PhysicalAccess.PROJECTILE, action.source_entity_uuid, subjective=scan.subjective
    ):
        return "A physical boundary blocks the throw"
    return None


@srd_action_identity(
    content_id="action.spell.payload.throw",
    display_name="Throw Spell Sphere",
    description="Throw a retained sphere, retiring the item before its explosion.",
    parent_spell_name="Freezing Sphere",
    source_page=149,
    sort_order=3480,
)
class ThrowSpellPayload(BaseAction):
    name: str = "Throw Spell Sphere"
    description: str = "Throw the retained Freezing Sphere or delayed fireball bead."
    target_type: TargetType = TargetType.POSITION_LOS
    harmful: bool = True
    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Throw sphere",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ]
    )

    def get_range(self):
        item = BaseBlock.get(self.source_item_uuid) if self.source_item_uuid else None
        return Range(
            type=RangeType.RANGE,
            normal=60
            if isinstance(item, SpellPayloadItem) and item.payload_kind == "freezing"
            else 40,
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        actor = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(self.source_item_uuid) if self.source_item_uuid else None
        if actor is None or not isinstance(item, SpellPayloadItem):
            return "Sphere absent"
        if item.payload_kind == "delayed_fire" and item.owner_uuid != actor.uuid:
            return "Touch the floor bead before throwing it"
        return payload_destination_error(self, scan, selection)

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)

    def _apply(self, event):
        item = BaseBlock.get(self.source_item_uuid) if self.source_item_uuid else None
        effect = event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        if not isinstance(item, SpellPayloadItem) or self.end_position is None:
            return effect.cancel(status_message="Sphere absent")
        return (
            effect
            if item.detonate(self.end_position, effect)
            else effect.cancel(status_message="Sphere retirement refused")
        )


@srd_action_identity(
    content_id="action.spell.delayed_blast_fireball.touch",
    display_name="Touch Delayed Fireball",
    description="Touch the bead: DEX failure detonates; success permits pickup or a same-action throw.",
    parent_spell_name="Delayed Blast Fireball",
    source_page=133,
    sort_order=3490,
)
class TouchDelayedFireball(BaseAction):
    throw_after_touch: bool = False
    name: str = "Touch Delayed Fireball"
    description: str = "Touch an adjacent bead, then pick it up or throw up to forty feet on a successful DEX save."
    target_type: TargetType = TargetType.SELF
    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Touch bead",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ]
    )

    def get_range(self):
        return Range(type=RangeType.RANGE, normal=40)

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        return ((ActionVariantFacet(key="form", value="pickup", label="Touch and pick up"),),
                (ActionVariantFacet(key="form", value="throw", label="Touch and throw"),))

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        throw = selection_facet(selection, "form") == "throw"
        return {**super()._selection_overrides(selection), "throw_after_touch": throw,
                "target_type": TargetType.POSITION_LOS if throw else TargetType.SELF}

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        actor = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(self.source_item_uuid) if self.source_item_uuid else None
        center = item.payload_position() if isinstance(item, SpellPayloadItem) else None
        if (
            actor is None
            or not isinstance(item, SpellPayloadItem)
            or center is None
            or item.payload_kind != "delayed_fire"
            or item.owner_uuid is not None
        ):
            return "Touch requires a floor bead"
        if (
            grid_distance_feet(actor.position, center) > 5
            or center not in scan.visible
            or not get_map().can_reach_between(
                actor.position, center, PhysicalAccess.HAND, actor.uuid, subjective=scan.subjective
            )
        ):
            return "Bead is outside visible hand reach"
        if self.throw_after_touch:
            return payload_destination_error(self, scan, selection)
        if selection.positions:
            return "Choose the touch-and-throw form"
        return None

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)

    def _apply(self, event):
        actor = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(self.source_item_uuid) if self.source_item_uuid else None
        effect = event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        if actor is None or not isinstance(item, SpellPayloadItem):
            return effect.cancel(status_message="Bead absent")
        center = item.payload_position()
        if center is None:
            return effect.cancel(status_message="Bead location absent")
        request = SavingThrowEvent(
            source_entity_uuid=item.original_caster_uuid,
            target_entity_uuid=actor.uuid,
            ability_name="dexterity",
            dc=item.spell_dc,
            parent_event=effect.uuid,
            saving_throw_context=SavingThrowContext(
                cause_id="spell.delayed_blast_fireball",
                effect_id="spell.delayed_blast_fireball.touch",
                is_magical=True,
            ),
        )
        if not actor.saving_throw(request)[2]:
            return (
                effect
                if item.detonate(center, effect)
                else effect.cancel(status_message="Bead retirement refused")
            )
        if self.end_position is not None:
            return (
                effect
                if item.detonate(self.end_position, effect)
                else effect.cancel(status_message="Bead retirement refused")
            )
        return (
            effect
            if actor.loot_item(item, parent_event=effect)
            else effect.cancel(status_message="Bead pickup refused")
        )


class SpellPayloadLifetime(BaseCondition):
    name: str = "Spell Payload Lifetime"
    description: str = "Original-caster clock and exact post-retirement detonation."
    item_uuid: UUID
    turn_ends_remaining: int = 10
    duration: Duration = Field(
        default_factory=lambda: Duration(duration_type=DurationType.UNTIL_LONG_REST)
    )
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    rollback: bool = False
    _seen_turn_ends: set[UUID] = PrivateAttr(default=set())
    _retirement: PreparedItemRetirement | None = PrivateAttr(default=None)
    _item: SpellPayloadItem | None = PrivateAttr(default=None)

    def model_post_init(self, context: object):
        super().model_post_init(context)
        self.name = f"Spell Payload Lifetime:{self.uuid}"

    def _apply(self, event):
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return [], [], [], [], event.cancel(status_message="Payload caster absent")

        def tick(boundary: Event, _):
            if boundary.lineage_uuid in self._seen_turn_ends:
                return None
            self._seen_turn_ends.add(boundary.lineage_uuid)
            item = BaseBlock.get(self.item_uuid)
            if not isinstance(item, SpellPayloadItem):
                caster.remove_condition_by_uuid(self.uuid, parent_event=boundary)
                return None
            if self.turn_ends_remaining > 0:
                if item.payload_kind == "delayed_fire":
                    item.dice_count += 1
                self.turn_ends_remaining -= 1
            if self.turn_ends_remaining <= 0:
                caster.remove_condition_by_uuid(self.uuid, parent_event=boundary)
            return None

        def defeated(boundary: Event, _):
            caster.remove_condition_by_uuid(self.uuid, parent_event=boundary)
            return None

        handlers = [
            EventHandler(
                name="Original caster payload clock",
                source_entity_uuid=caster.uuid,
                runs_while_owner_inactive=True,
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.TURN_END,
                        event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=caster.uuid,
                    )
                ],
                event_processor=tick,
            ),
            EventHandler(
                name="Payload caster ending",
                source_entity_uuid=caster.uuid,
                group_dispatch=HandlerGroupDispatch.AFTER_GROUP,
                runs_while_owner_inactive=True,
                trigger_conditions=[
                    Trigger(
                        event_type=kind,
                        event_phase=EventPhase.EFFECT,
                        event_target_entity_uuid=caster.uuid,
                    )
                    for kind in (EventType.DEATH, EventType.INSTANT_DEATH)
                ],
                event_processor=defeated,
            ),
        ]
        for handler in handlers:
            caster.add_event_handler(handler)
        return (
            [],
            [handler.uuid for handler in handlers],
            [],
            [],
            event.phase_to(EventPhase.EFFECT),
        )

    def on_world_closed(self, parent_event=None):
        self.rollback = True
        caster = Entity.get(self.source_entity_uuid)
        if caster is not None and self.applied:
            if not caster.remove_condition_by_uuid(
                self.uuid, parent_event=parent_event
            ):
                raise RuntimeError("Payload administrative retirement refused")

    def cancel_creation(self, parent=None):
        self.rollback = True
        caster = Entity.get(self.source_entity_uuid)
        if caster is not None:
            caster.remove_condition_by_uuid(self.uuid, parent_event=parent)

    def prepare_removal_state(self, event):
        item = BaseBlock.get(self.item_uuid)
        if not isinstance(item, SpellPayloadItem):
            return event
        self._item = item
        if not item.detonation_requested:
            item.impact_position = item.payload_position()
        self._retirement = item.prepare_retirement(event)
        return (
            event
            if self._retirement is not None
            else event.cancel(status_message="Payload retirement refused")
        )

    def cancel_prepared_removal(self, reason: str):
        if self._retirement is not None and not self._retirement.committed:
            self._retirement.item.cancel_retirement(self._retirement)
        self._retirement = None
        self._item = None

    def _remove(self, event=None):
        if self._retirement is not None and self._item is not None:
            self._item.detonation_requested = not self.rollback
            self._item.defer_detonation = True
            self._item.commit_retirement(self._retirement)
        return event

    def on_membership_changed(self, event):
        if (
            not self.applied
            and self._retirement is not None
            and self._retirement.committed
            and self._item is not None
        ):
            item = self._item
            self._item = None
            self._retirement = None
            if not self.rollback:
                item.explode(event)


def build_spell_payload(
    caster_uuid: UUID,
    *,
    kind: Literal["freezing", "delayed_fire"],
    dc: int,
    dice_count: int,
    origin: EffectOrigin | None,
) -> SpellPayloadItem:
    templates: list[BaseAction] = [
        ThrowSpellPayload(source_entity_uuid=caster_uuid, template=True)
    ]
    if kind == "delayed_fire":
        templates.append(
            TouchDelayedFireball(source_entity_uuid=caster_uuid, template=True)
        )
    return SpellPayloadItem(
        source_entity_uuid=caster_uuid,
        original_caster_uuid=caster_uuid,
        payload_kind=kind,
        spell_dc=dc,
        dice_count=dice_count,
        effect_origin=origin,
        is_pickable=kind == "freezing",
        name="Portable Freezing Sphere"
        if kind == "freezing"
        else "Delayed Fireball Bead",
        item_id="spell_payload.freezing_sphere"
        if kind == "freezing"
        else "spell_payload.delayed_fireball",
        health=BaseItem.create_item_health(caster_uuid, 1),
        armor_class=10,
        use_action_templates=templates,
    )


def commit_payload_cast(
    action: SpellAction,
    event: SpellEvent,
    item: SpellPayloadItem,
    *,
    recipient: Entity | None = None,
    placement: PreparedObjectPlacement | None = None,
) -> SpellEvent:
    """Admit this sphere's ending owner and concentration before its delivery."""
    caster = Entity.get(action.source_entity_uuid)
    if caster is None or (recipient is None) == (placement is None):
        return event.cancel(status_message="Payload delivery absent")
    if event.canceled:
        return event
    owner = SpellPayloadLifetime(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        item_uuid=item.uuid,
    )
    with BaseBlock.condition_removal_scope():
        application = caster.prepare_condition_application(owner, parent_event=event)
        if not isinstance(application, PreparedConditionApplication):
            return event.cancel(status_message="Payload lifetime refused")
        concentration = None
        try:
            if action.concentration:
                concentration = action.prepare_concentration(event)
                if not isinstance(concentration, PreparedSpellConcentration):
                    return event.cancel(status_message="Payload concentration refused")
            item.lifetime_uuid = owner.uuid
            publication_error = None
            try:
                if recipient is not None:
                    if not recipient.loot_item(item, parent_event=event):
                        return event.cancel(status_message="Payload inventory refused")
                else:
                    assert placement is not None
                    item.synchronize_floor_placement(
                        get_map().commit_object_placement(placement)
                    )
            except BaseException as error:
                delivered = (
                    item.owner_uuid == recipient.uuid
                    if recipient is not None
                    else placement is not None
                    and get_map().get_object_position(item.uuid)
                    == placement.placement.position
                )
                if not delivered:
                    raise
                publication_error = error
            caster.commit_condition_application(application)
            if concentration is not None:
                action.commit_prepared_concentration(concentration, caster, owner)
            errors = []
            try:
                caster.publish_condition_application(application)
            except BaseException as error:
                errors.append(error)
            if concentration is not None:
                try:
                    action.publish_prepared_concentration(concentration)
                except BaseException as error:
                    errors.append(error)
            if publication_error is not None:
                errors.insert(0, publication_error)
            if errors:
                raise BaseExceptionGroup("Payload publication failed", errors)
            return event
        finally:
            if not application.committed:
                caster.cancel_condition_application(
                    application, "Payload cast rejected"
                )
            if (
                concentration is not None
                and isinstance(concentration, PreparedSpellConcentration)
                and concentration.application is not None
                and not concentration.application.committed
            ):
                concentration.owner.cancel_condition_application(
                    concentration.application, "Payload cast rejected"
                )
