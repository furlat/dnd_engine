"""Concrete creature techniques for the three approved high-level summon roots.

Actions compose native attacks, save bursts, movement, conditions and fields.
They are creature actions, distinct from their creation spell's provenance.
"""

from typing import Any, Literal, cast
from uuid import UUID

from pydantic import Field, PrivateAttr

from dnd.actions import (
    Attack,
    AttackEvent,
    commit_forced_movement,
    entity_action_economy_cost_applier,
    entity_action_economy_cost_evaluator,
    resolve_spell_attack_values,
)
from dnd.blocks.skills import SKILL_TO_ABILITY
from dnd.conditions import (
    Charmed,
    Concentrating,
    Prone,
    Restrained,
    Stunned,
)
from dnd.core.aoe import AoEShape, Cone, Sphere, objective_footprint
from dnd.core.action_types import ActionSelection
from dnd.core.attack_types import DamageDieValue
from dnd.core.base_actions import (
    ActionCategory,
    ActionEvent,
    ActionOutcomeProfile,
    BaseAction,
    Cost,
    DamageRollProfile,
    OutcomeApplicationScope,
    OutcomeResolution,
    TargetType,
)
from dnd.core.base_block import (
    BaseBlock,
    PreparedConditionApplication,
    PreparedConditionRemovals,
)
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import ConditionRemovalTrigger, ConditionTag, DurationType
from dnd.core.content.dependencies import ContentDependency, ContentDependencyRelation
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import (
    behavior_content_ref,
    behavior_identity,
    get_content_declaration,
)
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome
from dnd.core.effect_types import EffectOrigin, EffectOriginKind
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    Damage,
    DamageRollResultEvent,
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    ForcedMovementEvent,
    Healing,
    PortalTransferEvent,
    Range,
    RangeType,
    SavingThrowEvent,
    Trigger,
)
from dnd.core.geometry import (
    circle_positions,
    cone_positions,
    grid_distance_feet,
)
from dnd.core.gridmap import get_map
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
    NumericalModifier,
    ResistanceModifier,
    ResistanceStatus,
)
from dnd.core.saving_throw_types import SavingThrowContext
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.monsters.traits import NaturalAttack
from dnd.spatial.area_conditions import AreaCondition
from dnd.spatial.environmental_conditions import FireSurface, IceSurface, WetSurface
from dnd.spatial.ignition import apply_elemental_surface_contacts
from dnd.spatial.memberships import (
    MembershipAreaCondition,
    SpatialConditionMembershipSource,
)
from dnd.spells.illusion import SilenceZone
from dnd.spells.spell_utils import (
    condition_damage,
    condition_save,
    fire_heal_roll_result,
    seen_point_error,
    target_count_error,
    target_turn_expiry_handler,
)
from dnd.spells.transmutation import HasteEffect
from dnd.types.abilities import AbilityName
from dnd.types.discovery import ActorScan
from dnd.types.physical_access import PhysicalAccess
from dnd.types.world import WorldEdgeChannel
from dnd.types.spatial_effects import (
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
)


class ElementalSphere(Sphere):
    def max_radius_tiles(self):
        return (self.radius_feet + 4) // 5

    def positions_from(self, origin, aim):
        return {
            point
            for point in circle_positions(origin, self.max_radius_tiles())
            if 25 * ((point[0] - origin[0]) ** 2 + (point[1] - origin[1]) ** 2)
            <= self.radius_feet**2
        }


class ElementalCone(Cone):
    def max_radius_tiles(self):
        return (self.length_feet + 4) // 5

    def positions_from(self, origin, aim):
        return {
            point
            for point in cone_positions(
                origin, aim, self.max_radius_tiles(), self.angle_degrees
            )
            if 25 * ((point[0] - origin[0]) ** 2 + (point[1] - origin[1]) ** 2)
            <= self.length_feet**2
        }


def technique_origin(event: Event) -> EffectOrigin:
    actor = Entity.get(event.source_entity_uuid)
    return EffectOrigin(
        kind=EffectOriginKind.ACTION,
        source_id=event.behavior_id if isinstance(event, ActionEvent) else None,
        source_position=actor.position if actor is not None else None,
        source_event_lineage_uuid=str(event.lineage_uuid),
    )


def owns_fact(target: Entity, identity: str) -> bool:
    return any(
        condition.contributions_active()
        and (
            condition.get_semantic_key() == identity
            or identity in condition.immunity_names
        )
        for condition in target.active_conditions_by_uuid.values()
    )


class Shocked(BaseCondition):
    immunity_names: tuple[str, ...] = ("Shocked",)
    name: str = "Shocked"
    description: str = (
        "Two-turn reaction denial and disadvantage on DEX checks and saves."
    )
    duration: Duration = Field(
        default_factory=lambda: Duration(duration_type=DurationType.PERMANENT)
    )
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, event):
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if target is None:
            return [], [], [], [], event.cancel(status_message="Recipient absent")
        outputs = []
        value = target.action_economy.reactions
        ident = value.self_static.add_max_constraint(
            NumericalModifier(name=self.name, value=0, source_entity_uuid=target.uuid)
        )
        outputs.append((value.uuid, ident))
        values = [
            target.ability_scores.dexterity.check_bonus,
            target.saving_throws.get_saving_throw("dexterity").bonus,
        ]
        values.extend(
            target.skill_set.get_skill(skill).skill_bonus
            for skill, ability in SKILL_TO_ABILITY.items()
            if ability == "dexterity"
        )
        for value in values:
            ident = value.self_static.add_advantage_modifier(
                AdvantageModifier(
                    name=self.name,
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=target.uuid,
                )
            )
            outputs.append((value.uuid, ident))
        expiry = target_turn_expiry_handler(self, turn_ends=2)
        target.add_event_handler(expiry)
        return outputs, [expiry.uuid], [], [], event.phase_to(EventPhase.EFFECT)


class TremblingLegs(BaseCondition):
    name: str = "Trembling Legs"
    description: str = "Three-turn minus one DEX and minus eight feet speed."
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, event):
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if target is None:
            return [], [], [], [], event.cancel(status_message="Recipient absent")
        outputs = []
        for value, amount in [
            (target.ability_scores.dexterity.ability_score, -1),
            *((speed, -8) for speed in target.action_economy.speed_values),
        ]:
            ident = value.self_static.add_value_modifier(
                NumericalModifier(
                    name=self.name, value=amount, source_entity_uuid=target.uuid
                )
            )
            outputs.append((value.uuid, ident))
        expiry = target_turn_expiry_handler(self, turn_ends=3)
        target.add_event_handler(expiry)
        return outputs, [expiry.uuid], [], [], event.phase_to(EventPhase.EFFECT)


class Burning(BaseCondition):
    blocked_while_wet: bool = True
    immunity_names: tuple[str, ...] = ("Burning",)
    name: str = "Burning"
    description: str = (
        "Two turns of 1d4 fire at turn start; Wet prevents or removes it."
    )
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    removal_triggers: frozenset[ConditionRemovalTrigger] = frozenset(
        {ConditionRemovalTrigger.WET_APPLICATION}
    )

    def _apply(self, event):
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if target is None:
            return [], [], [], [], event.cancel(status_message="Burn recipient absent")

        def tick(boundary, _):
            condition_damage(
                self, target, boundary, count=1, die=4, damage_type=DamageType.FIRE
            )
            return None

        handler = EventHandler(
            name="Burning start damage",
            source_entity_uuid=target.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=target.uuid,
                )
            ],
            event_processor=tick,
        )
        expiry = target_turn_expiry_handler(self, turn_ends=2)
        target.add_event_handler(handler)
        target.add_event_handler(expiry)
        return (
            [],
            [handler.uuid, expiry.uuid],
            [],
            [],
            event.phase_to(EventPhase.EFFECT),
        )


class Chilled(BaseCondition):
    immunity_names: tuple[str, ...] = ("Chilled",)
    name: str = "Chilled"
    description: str = "Two-turn Cold vulnerability and Fire resistance."
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, event):
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if target is None:
            return [], [], [], [], event.cancel(status_message="Recipient absent")
        outputs = []
        value = target.health.damage_reduction
        for damage_type, status in (
            (DamageType.COLD, ResistanceStatus.VULNERABILITY),
            (DamageType.FIRE, ResistanceStatus.RESISTANCE),
        ):
            ident = value.self_static.add_resistance_modifier(
                ResistanceModifier(
                    name=self.name,
                    value=status,
                    damage_type=damage_type,
                    source_entity_uuid=target.uuid,
                )
            )
            outputs.append((value.uuid, ident))
        expiry = target_turn_expiry_handler(self, turn_ends=2)
        target.add_event_handler(expiry)
        return outputs, [expiry.uuid], [], [], event.phase_to(EventPhase.EFFECT)


class Brittle(BaseCondition):
    name: str = "Brittle"
    description: str = (
        "Three turns of Bludgeoning/Thunder vulnerability and 2d6 Cold at start."
    )
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, event):
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if target is None:
            return [], [], [], [], event.cancel(status_message="Recipient absent")
        value = target.health.damage_reduction
        outputs = []
        for kind in (DamageType.BLUDGEONING, DamageType.THUNDER):
            ident = value.self_static.add_resistance_modifier(
                ResistanceModifier(
                    name=self.name,
                    value=ResistanceStatus.VULNERABILITY,
                    damage_type=kind,
                    source_entity_uuid=target.uuid,
                )
            )
            outputs.append((value.uuid, ident))

        def tick(boundary, _):
            condition_damage(
                self, target, boundary, count=2, die=6, damage_type=DamageType.COLD
            )
            return None

        handler = EventHandler(
            name="Brittle cold",
            source_entity_uuid=target.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=target.uuid,
                )
            ],
            event_processor=tick,
        )
        expiry = target_turn_expiry_handler(self, turn_ends=3)
        target.add_event_handler(handler)
        target.add_event_handler(expiry)
        return (
            outputs,
            [handler.uuid, expiry.uuid],
            [],
            [],
            event.phase_to(EventPhase.EFFECT),
        )


class Dazed(BaseCondition):
    name: str = "Dazed"
    description: str = "Two-turn reaction denial, Wisdom-save disadvantage and no DEX contribution to AC."
    denies_dexterity_ac: bool = True
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, event):
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if target is None:
            return [], [], [], [], event.cancel(status_message="Recipient absent")
        outputs = []
        value = target.action_economy.reactions
        ident = value.self_static.add_max_constraint(
            NumericalModifier(name=self.name, value=0, source_entity_uuid=target.uuid)
        )
        outputs.append((value.uuid, ident))
        value = target.saving_throws.get_saving_throw("wisdom").bonus
        ident = value.self_static.add_advantage_modifier(
            AdvantageModifier(
                name=self.name,
                value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=target.uuid,
            )
        )
        outputs.append((value.uuid, ident))
        expiry = target_turn_expiry_handler(self, turn_ends=2)
        target.add_event_handler(expiry)
        return outputs, [expiry.uuid], [], [], event.phase_to(EventPhase.EFFECT)


class TransmutedToSteel(BaseCondition):
    name: str = "Transmuted to Steel"
    description: str = "Four turns of +2 AC and minus twenty feet speed."
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, event):
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if target is None:
            return [], [], [], [], event.cancel(status_message="Recipient absent")
        outputs = []
        for value, amount in [
            (target.equipment.ac_bonus, 2),
            *((speed, -20) for speed in target.action_economy.speed_values),
        ]:
            ident = value.self_static.add_value_modifier(
                NumericalModifier(
                    name=self.name, value=amount, source_entity_uuid=target.uuid
                )
            )
            outputs.append((value.uuid, ident))
        expiry = target_turn_expiry_handler(self, turn_ends=4)
        target.add_event_handler(expiry)
        return outputs, [expiry.uuid], [], [], event.phase_to(EventPhase.EFFECT)


class ElementalMud(AreaCondition):
    content_ref: ContentRef = behavior_content_ref(
        pack_id="content.srd_5_1_cc",
        content_id="spatial_effect.summon.mud",
        version=1,
        definition_kind=ContentDefinitionKind.CONDITION,
        runtime_behavior_kind=RuntimeBehaviorKind.CONDITION,
    )
    name: str = "Elemental Mud"
    description: str = "A temporary patch of difficult ground."
    layer: SpatialEffectLayer = SpatialEffectLayer.GROUND_SURFACE
    occupancy_policy: SpatialEffectOccupancyPolicy = (
        SpatialEffectOccupancyPolicy.OVERLAPPING
    )
    area: AoEShape = Sphere(radius_feet=3)
    adds_difficult_terrain: bool = True
    duration: Duration = Field(
        default_factory=lambda: Duration(duration=2, duration_type=DurationType.ROUNDS)
    )


def technique_cells(actor: Entity, origin: tuple[int, int], cells):
    """Use native physical propagation for an emitted technique."""
    return {
        cell
        for cell in cells
        if get_map().can_reach_between(
            origin, cell, PhysicalAccess.PROJECTILE, actor.uuid
        )
    }


def technique_area(action: BaseAction):
    targets, cells = action._resolve_area_targets()
    actor = Entity.get(action.source_entity_uuid)
    if actor is None or action.aoe_shape is None or action.end_position is None:
        return [], ()
    origin = action.aoe_shape.get_origin(action.end_position, actor.position)
    allowed = technique_cells(actor, origin, cells or ())
    return [
        identity
        for identity in targets
        if (target := Entity.get(identity)) is not None and target.position in allowed
    ], tuple(sorted(allowed))


class NativeSaveBurst(BaseAction):
    action_category: ActionCategory = ActionCategory.ATTACK
    """Concrete native creature burst composition, never levelled spell traffic."""
    target_type: TargetType = TargetType.POSITION_AOE
    harmful: bool = True
    include_self: bool = False
    valid_target_filter: str = "all"
    save_ability: AbilityName = "dexterity"
    save_dc: int = 13
    half_on_save: bool = True
    packets: tuple[DamageRollProfile, ...] = ()
    radius_feet: int = 10
    cone_feet: int = 0
    range_feet: int = 60
    self_centered: bool = False
    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Creature technique",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ]
    )

    def model_post_init(self, context):
        super().model_post_init(context)
        if self.aoe_shape is None:
            self.aoe_shape = (
                ElementalCone(
                    length_feet=self.cone_feet,
                )
                if self.cone_feet
                else ElementalSphere(
                    radius_feet=self.radius_feet,
                )
            )

    def get_range(self):
        return Range(type=RangeType.RANGE, normal=self.cone_feet or self.range_feet)

    def get_valid_positions(self):
        actor = Entity.get(self.source_entity_uuid)
        return (
            [actor.position]
            if self.self_centered and actor is not None
            else super().get_valid_positions()
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> str | None:
        actor = Entity.get(self.source_entity_uuid)
        destination = selection.positions[0] if selection.positions else None
        if self.self_centered and (
            actor is None or destination != actor.position
        ):
            return "This technique is centered on its actor"
        return technique_destination_error(self, scan, selection)

    def get_outcome_profile(self):
        return ActionOutcomeProfile(
            resolution=OutcomeResolution.SAVING_THROW,
            save_dc=self.save_dc,
            save_ability=self.save_ability,
            half_damage_on_save=self.half_on_save,
            damage_rolls=self.packets,
            application_scope=OutcomeApplicationScope.EACH_AFFECTED_ENTITY,
        )

    def _resolve_execution_targets(self):
        return (
            technique_area(self)
            if self.effective_target_type is TargetType.POSITION_AOE
            else super()._resolve_execution_targets()
        )

    def _finalize_aoe(self, event):
        for kind in {DamageType(packet.damage_type) for packet in self.packets}:
            apply_elemental_surface_contacts(
                event, set(event.resolved_area_positions or ()), kind
            )

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)

    def before_damage(self, target: Entity, event: ActionEvent):
        return None

    def after_damage(
        self, target: Entity, event: ActionEvent, saved: bool, previous: Any
    ):
        return None

    def _apply(self, event: ActionEvent):
        target = (
            Entity.get(event.target_entity_uuid)
            if event.target_entity_uuid is not None
            else None
        )
        actor = Entity.get(self.source_entity_uuid)
        if target is None or actor is None:
            return event
        effect = event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        previous = self.before_damage(target, effect)
        identity = effect.behavior_id or "action.monster.elemental_technique"
        request = SavingThrowEvent(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            ability_name=self.save_ability,
            dc=self.save_dc,
            parent_event=effect.uuid,
            saving_throw_context=SavingThrowContext(
                cause_id=identity, effect_id=identity + ".save", is_magical=True
            ),
        )
        saved = target.saving_throw(request)[2]
        origin = EffectOrigin(
            kind=EffectOriginKind.ACTION,
            source_id=identity,
            source_position=actor.position,
            source_event_lineage_uuid=str(effect.lineage_uuid),
        )
        if not saved or self.half_on_save:
            damages = []
            rolls = []
            amounts = []
            for packet in self.packets:
                damage = Damage(
                    source_entity_uuid=self.source_entity_uuid,
                    target_entity_uuid=target.uuid,
                    damage_dice=cast(DamageDieValue, packet.die_size),
                    dice_numbers=packet.dice_count,
                    damage_type=DamageType(packet.damage_type),
                    effect_origin=origin,
                    damage_bonus=ModifiableValue.create(
                        source_entity_uuid=self.source_entity_uuid,
                        base_value=packet.flat_bonus,
                    ),
                )
                damages.append(damage)
                if packet.dice_count:
                    roll = damage.get_dice(AttackOutcome.HIT).roll
                    rolls.append(roll)
                    amount = roll.total
                else:
                    amount = packet.flat_bonus
                amounts.append(amount // 2 if saved else amount)
            target.receive_damage(
                sum(amounts),
                damages[0].damage_type,
                self.source_entity_uuid,
                damages=damages,
                damage_rolls=rolls,
                component_amounts=tuple(amounts),
                parent_event=effect.uuid,
                effect_origin=origin,
                independent_resolution=True,
            )
        self.after_damage(target, effect, saved, previous)
        return effect


def add_status(
    kind: type[BaseCondition],
    actor: UUID,
    target: Entity,
    event: Event,
    *,
    turns: int | None = None,
):
    condition = kind(
        source_entity_uuid=actor,
        target_entity_uuid=target.uuid,
        effect_origin=technique_origin(event),
    )
    if turns is not None:
        condition.duration = Duration(duration=turns, duration_type=DurationType.ROUNDS)
    target.add_condition(condition, parent_event=event)


def patch(
    kind: "type[ElementalMud] | type[ElementalFire] | type[IceSurface] | type[WetSurface]",
    actor: UUID,
    center: tuple[int, int],
    radius: int,
    turns: int,
    event: Event,
):
    shape = ElementalSphere(radius_feet=radius)
    source = Entity.get(actor)
    cells = (
        technique_cells(source, center, objective_footprint(shape, center, center))
        if source is not None
        else set()
    )
    if not cells:
        return None
    zone = kind(
        source_entity_uuid=actor,
        position=center,
        affected_positions=cells,
        duration=Duration(duration=turns, duration_type=DurationType.ROUNDS),
        effect_origin=technique_origin(event),
    )
    zone.activate(parent_event=event)
    return zone


class ElementalWarp(BaseAction):
    name: str = "Elemental Warp"
    description: str = "Teleport to a visible unoccupied destination within sixty feet."
    target_type: TargetType = TargetType.POSITION_LOS
    range_feet: int = 60
    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Elemental Warp",
                cost_type="bonus_actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ]
    )

    def get_range(self):
        return Range(type=RangeType.RANGE, normal=self.range_feet)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> str | None:
        error = seen_point_error(self, scan, selection)
        if error is not None:
            return error
        if not get_map().is_walkable_for(
            *selection.positions[0], requesting_entity_uuid=self.source_entity_uuid, subjective=scan.subjective
        ):
            return "Destination is occupied or blocked"
        return None

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)

    def _apply(self, event):
        if self.end_position is None:
            return event.cancel(status_message="Destination absent")
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return event.cancel(status_message="Actor absent")
        effect = event.phase_to(EventPhase.EFFECT)
        if effect.canceled or actor is None:
            return effect
        crossing = PortalTransferEvent(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=actor.uuid,
            start_position=actor.position,
            end_position=self.end_position,
            effect_origin=technique_origin(effect),
            parent_event=effect.uuid,
        )
        crossing = crossing.phase_to(EventPhase.EXECUTION)
        if not crossing.canceled:
            crossing = crossing.phase_to(EventPhase.EFFECT)
        if crossing.canceled:
            return effect.cancel(status_message=crossing.status_message)
        Entity.commit_position_transfers(((actor, self.end_position, crossing.uuid),))
        crossing.phase_to(EventPhase.COMPLETION, committed=True)
        return effect


class PrimordialGales(NativeSaveBurst):
    name: str = "Primordial Gales"
    self_centered: bool = True
    radius_feet: int = 13
    save_ability: AbilityName = "strength"
    save_dc: int = 10
    packets: tuple[DamageRollProfile, ...] = (
        DamageRollProfile(dice_count=2, die_size=6, damage_type="Lightning"),
    )

    def after_damage(self, target, event, saved, previous):
        if not saved:
            add_status(Shocked, self.source_entity_uuid, target, event)


class GushingAir(NativeSaveBurst):
    allow_same_target: bool = True

    def _resolve_execution_targets(self):
        targets = self.get_all_targets()
        return (targets if len(targets) > 1 else targets * 2), None

    name: str = "Gushing Air"
    target_type: TargetType = TargetType.MULTI_ENTITY

    def get_multi_target_count(self):
        return 2

    def get_allocation_completion(self):
        return "fill_primary"

    def get_all_targets(self):
        targets = super().get_all_targets()
        return targets if len(targets) > 1 else targets * 2

    def get_outcome_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return (
            super()
            .get_outcome_profile()
            .model_copy(
                update={
                    "applications": 2,
                    "application_scope": OutcomeApplicationScope.ALLOCATED_TARGETS,
                }
            )
        )

    save_dc: int = 15
    packets: tuple[DamageRollProfile, ...] = (
        DamageRollProfile(
            dice_count=2, die_size=6, flat_bonus=1, damage_type="Thunder"
        ),
    )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> str | None:
        actor = Entity.get(self.source_entity_uuid)
        targets = selection.target_uuids
        if actor is None or not targets:
            return "Choose one or two jet recipients"
        if (error := target_count_error(self, selection, 2)) is not None:
            return error
        if any(
            (target := Entity.get(identity)) is None
            or grid_distance_feet(actor.position, target.position) > 60
            or identity not in scan.creatures
            or not get_map().can_reach_between(
                actor.position, target.position, PhysicalAccess.PROJECTILE, actor.uuid, subjective=scan.subjective
            )
            for identity in targets
        ):
            return "Jet recipient is unreachable"
        return None


class SeismicStrike(NativeSaveBurst):
    name: str = "Seismic Strike"
    self_centered: bool = True
    radius_feet: int = 13
    save_dc: int = 9
    packets: tuple[DamageRollProfile, ...] = (
        DamageRollProfile(dice_count=4, die_size=6, damage_type="Bludgeoning"),
    )

    def after_damage(self, target, event, saved, previous):
        if saved:
            return
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        dx = target.position[0] - actor.position[0]
        dy = target.position[1] - actor.position[1]
        step = (
            0 if dx == 0 else 1 if dx > 0 else -1,
            0 if dy == 0 else 1 if dy > 0 else -1,
        )
        destination = target.position
        for _ in range(2):
            candidate = (destination[0] + step[0], destination[1] + step[1])
            if not get_map().is_walkable_for(
                *candidate, requesting_entity_uuid=target.uuid
            ) or not get_map().spatial_crossing_allows(
                destination, candidate, WorldEdgeChannel.MOVEMENT, target.uuid
            ):
                break
            destination = candidate
        if destination != target.position:
            movement = ForcedMovementEvent(
                source_entity_uuid=actor.uuid,
                target_entity_uuid=target.uuid,
                start_position=target.position,
                end_position=destination,
                direction=step,
                intended_distance=10,
                actual_distance=grid_distance_feet(target.position, destination),
                parent_event=event.uuid,
            )
            movement = movement.phase_to(EventPhase.EXECUTION)
            if not movement.canceled:
                movement = movement.phase_to(EventPhase.EFFECT)
            if not movement.canceled:
                commit_forced_movement(target, movement, parent_event=event)
        request = SavingThrowEvent(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=9,
            parent_event=event.uuid,
            saving_throw_context=SavingThrowContext(
                cause_id=event.behavior_id or "action.earth_elemental.seismic_strike",
                effect_id=(event.behavior_id or "action.earth_elemental.seismic_strike")
                + ".rider",
                is_magical=True,
            ),
        )
        if not target.saving_throw(request)[2]:
            add_status(TremblingLegs, actor.uuid, target, event)


class CinderousSwipe(NativeSaveBurst):
    name: str = "Cinderous Swipe"
    radius_feet: int = 10
    save_dc: int = 11
    packets: tuple[DamageRollProfile, ...] = (
        DamageRollProfile(dice_count=4, die_size=6, damage_type="Fire"),
    )

    def _finalize_aoe(self, event):
        if self.end_position is None:
            return None
        super()._finalize_aoe(event)
        patch(ElementalFire, self.source_entity_uuid, self.end_position, 7, 1, event)


class WintersBreath(NativeSaveBurst):
    name: str = "Winter's Breath"
    cone_feet: int = 20
    save_dc: int = 16
    save_ability: AbilityName = "constitution"
    packets: tuple[DamageRollProfile, ...] = (
        DamageRollProfile(dice_count=4, die_size=6, damage_type="Cold"),
    )

    def before_damage(self, target, event):
        return tuple(
            condition.uuid
            for condition in target.active_conditions_by_uuid.values()
            if condition.contributions_active() and "Burning" in condition.immunity_names
        )

    def after_damage(self, target, event, saved, previous):
        for identity in previous:
            target.remove_condition_by_uuid(identity, parent_event=event)
        if not saved and previous:
            add_status(Brittle, self.source_entity_uuid, target, event)

    def _finalize_aoe(self, event):
        if self.end_position is None:
            return None
        super()._finalize_aoe(event)
        zone = IceSurface(
            source_entity_uuid=self.source_entity_uuid,
            position=self.end_position,
            affected_positions=set(event.resolved_area_positions or ()),
            duration=Duration(duration=2, duration_type=DurationType.ROUNDS),
        )
        zone.activate(parent_event=event)


class ElementalFire(FireSurface):
    content_ref: ContentRef = behavior_content_ref(
        pack_id="content.srd_5_1_cc",
        content_id="spatial_effect.summon.fire",
        version=1,
        definition_kind=ContentDefinitionKind.CONDITION,
        runtime_behavior_kind=RuntimeBehaviorKind.CONDITION,
    )
    name: str = "Elemental Fire"

    def _deal_damage(self, entity, event):
        condition_damage(
            self, entity, event, count=1, die=4, damage_type=DamageType.FIRE
        )


class ElementalContactBurst(BaseAction):
    action_category: ActionCategory = ActionCategory.ATTACK
    """Slam/touch composition: one native attack per creature in the impact."""
    target_type: TargetType = TargetType.POSITION_AOE
    harmful: bool = True
    include_self: bool = False
    valid_target_filter: str = "all"
    radius_feet: int = 3
    range_feet: int = 5
    technique: Literal["soil", "smouldering", "water", "icicle"] = "soil"
    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Elemental impact",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ]
    )

    def model_post_init(self, context):
        super().model_post_init(context)
        self.aoe_shape = ElementalSphere(
            radius_feet=self.radius_feet,
        )

    def get_range(self):
        return Range(type=RangeType.RANGE, normal=self.range_feet)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> str | None:
        return technique_destination_error(self, scan, selection)

    def _resolve_execution_targets(self):
        return technique_area(self)

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)

    def get_outcome_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        ability = "intelligence" if self.technique == "icicle" else "strength"
        baseline = actor.spell_attack_outcome_baseline(casting_ability=ability)
        advantage = baseline.advantage
        if self.technique == "icicle" and actor.is_threatened():
            advantage = (
                AdvantageStatus.NONE
                if advantage is AdvantageStatus.ADVANTAGE
                else AdvantageStatus.DISADVANTAGE
            )
        packets = {
            "soil": (
                DamageRollProfile(
                    dice_count=2, die_size=6, flat_bonus=6, damage_type="Bludgeoning"
                ),
            ),
            "smouldering": (
                DamageRollProfile(dice_count=2, die_size=6, damage_type="Fire"),
            ),
            "water": (
                DamageRollProfile(dice_count=2, die_size=6, damage_type="Cold"),
                DamageRollProfile(
                    dice_count=0, die_size=4, flat_bonus=5, damage_type="Bludgeoning"
                ),
            ),
            "icicle": (
                DamageRollProfile(dice_count=3, die_size=8, damage_type="Cold"),
            ),
        }[self.technique]
        return ActionOutcomeProfile(
            resolution=OutcomeResolution.ATTACK_ROLL,
            attack_bonus=baseline.attack_bonus,
            advantage=advantage,
            critical_threshold=baseline.critical_threshold,
            critical_extra_dice=baseline.critical_extra_dice,
            damage_rolls=packets,
            applications=3 if self.technique == "icicle" else 1,
            application_scope=OutcomeApplicationScope.EACH_AFFECTED_ENTITY,
        )

    def _apply(self, event):
        target = (
            Entity.get(event.target_entity_uuid)
            if event.target_entity_uuid is not None
            else None
        )
        effect = event.phase_to(EventPhase.EFFECT)
        if target is None or effect.canceled:
            return effect
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return event.cancel(status_message="Actor absent")
        if self.technique == "icicle":
            for _ in range(3):
                resolution = resolve_spell_attack_values(
                    actor,
                    target,
                    effect.uuid,
                    ranged=True,
                    casting_ability="intelligence",
                )
                if resolution.outcome in (AttackOutcome.HIT, AttackOutcome.CRIT):
                    damage = Damage(
                        source_entity_uuid=actor.uuid,
                        target_entity_uuid=target.uuid,
                        damage_dice=8,
                        dice_numbers=3,
                        damage_type=DamageType.COLD,
                        damage_bonus=ModifiableValue.create(
                            source_entity_uuid=actor.uuid, base_value=0
                        ),
                        effect_origin=technique_origin(effect),
                    )
                    roll = damage.get_dice(resolution.outcome).roll
                    target.receive_damage(
                        roll.total,
                        DamageType.COLD,
                        actor.uuid,
                        damages=[damage],
                        damage_rolls=[roll],
                        parent_event=effect.uuid,
                        critical_hit=resolution.outcome is AttackOutcome.CRIT,
                    )
            return effect
        packet = {
            "soil": (6, 2, 6, DamageType.BLUDGEONING),
            "smouldering": (6, 2, 0, DamageType.FIRE),
            "water": (6, 2, 0, DamageType.COLD),
        }[self.technique]

        def hit(attack_event):
            return attack_event

        attack = NaturalAttack(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=target.uuid,
            costs=[],
            name=self.name or "Elemental contact",
            natural_damage_dice=6,
            natural_dice_numbers=packet[1],
            fixed_damage_bonus=packet[2],
            natural_damage_type=packet[3],
            natural_range=Range(type=RangeType.REACH, normal=10),
            fixed_attack_bonus=actor.proficiency_bonus.normalized_score
            + actor.ability_scores.strength.modifier,
            magical=True,
        )
        declaration = attack._create_declaration_event(parent_event=effect)
        if declaration is None:
            return effect.cancel(status_message="Contact attack declaration refused")
        execution = declaration.phase_to(EventPhase.EXECUTION)
        if not isinstance(execution, AttackEvent):
            raise RuntimeError("Natural attack must produce an AttackEvent")
        handler = None
        if self.technique == "water":

            def fixed(boundary, _):
                if not isinstance(boundary, DamageRollResultEvent):
                    return None
                parent = (
                    EventQueue.get_event_by_uuid(boundary.parent_event)
                    if boundary.parent_event is not None
                    else None
                )
                if parent is None or parent.lineage_uuid != execution.lineage_uuid:
                    return None
                damage = Damage(
                    source_entity_uuid=actor.uuid,
                    target_entity_uuid=target.uuid,
                    damage_dice=4,
                    dice_numbers=0,
                    damage_type=DamageType.BLUDGEONING,
                    damage_bonus=ModifiableValue.create(
                        source_entity_uuid=actor.uuid, base_value=5
                    ),
                    attack_magical=True,
                )
                return boundary.append_damage_roll(
                    damage,
                    damage.get_dice(boundary.attack_outcome).roll,
                    "Water Slam",
                    "+5 Bludgeoning",
                )

            handler = EventHandler(
                name="Water Slam fixed component",
                source_entity_uuid=actor.uuid,
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.DAMAGE_ROLL_RESULT,
                        event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=actor.uuid,
                    )
                ],
                event_processor=fixed,
            )
            EventQueue.add_event_handler(handler)
        try:
            resolved = Attack.attack_consequences(
                execution,
                actor.uuid,
                physical_access=attack.get_physical_access(),
                on_hit=hit,
            )
            if resolved is not None and not resolved.canceled:
                if (
                    resolved.attack_outcome in (AttackOutcome.HIT, AttackOutcome.CRIT)
                    and target.is_active
                ):
                    add_status(
                        Prone
                        if self.technique == "soil"
                        else Burning
                        if self.technique == "smouldering"
                        else Chilled,
                        actor.uuid,
                        target,
                        resolved,
                    )
                resolved.phase_to(EventPhase.COMPLETION)
        finally:
            if handler is not None:
                EventQueue.remove_event_handler(handler)
        return effect

    def _finalize_aoe(self, event):
        if self.end_position is None:
            return None
        kind = (
            ElementalMud
            if self.technique == "soil"
            else ElementalFire
            if self.technique == "smouldering"
            else IceSurface
            if self.technique == "icicle"
            else WetSurface
        )
        patch(
            kind, self.source_entity_uuid, self.end_position, self.radius_feet, 2, event
        )


class SoilCloggedSlam(ElementalContactBurst):
    name: str = "Soil-Clogged Slam"
    technique: Literal["soil", "smouldering", "water", "icicle"] = "soil"


class SmoulderingTouch(ElementalContactBurst):
    name: str = "Smouldering Touch"
    technique: Literal["soil", "smouldering", "water", "icicle"] = "smouldering"


class WaterSlam(ElementalContactBurst):
    name: str = "Water Slam"
    technique: Literal["soil", "smouldering", "water", "icicle"] = "water"


class ExplosiveIcicle(ElementalContactBurst):
    name: str = "Explosive Icicle"
    technique: Literal["soil", "smouldering", "water", "icicle"] = "icicle"
    radius_feet: int = 7
    range_feet: int = 60


def technique_destination_error(
    action: BaseAction, scan: ActorScan, selection: ActionSelection
) -> str | None:
    """A seen impact point in range that a projectile from the actor reaches."""
    error = seen_point_error(action, scan, selection)
    if error is not None:
        return error
    if not get_map().can_reach_between(
        scan.position,
        selection.positions[0],
        PhysicalAccess.PROJECTILE,
        action.source_entity_uuid, subjective=scan.subjective
    ):
        return "Impact is behind a physical boundary"
    return None


class MyrmidonStrike(Attack):
    weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN
    rider: Literal["stun", "prone", "burn", "chill", "daze"] = "stun"
    rider_dc: int = 13

    def _apply(self, event):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return event.cancel(status_message="Actor absent")
        target = (
            Entity.get(event.target_entity_uuid)
            if event.target_entity_uuid is not None
            else None
        )
        if target is None:
            return event.cancel(status_message="Recipient absent")
        failed = False

        def hit(attack_event):
            nonlocal failed
            if attack_event.attack_outcome not in (
                AttackOutcome.HIT,
                AttackOutcome.CRIT,
            ):
                return attack_event
            request = SavingThrowEvent(
                source_entity_uuid=actor.uuid,
                target_entity_uuid=target.uuid,
                ability_name="constitution",
                dc=self.rider_dc,
                parent_event=attack_event.uuid,
                saving_throw_context=SavingThrowContext(
                    cause_id=event.behavior_id or "action.myrmidon.strike",
                    effect_id=(event.behavior_id or "action.myrmidon.strike")
                    + ".rider",
                    is_magical=True,
                ),
            )
            failed = not target.saving_throw(request)[2]
            return attack_event

        resolved = Attack.attack_consequences(
            event, actor.uuid, physical_access=self.get_physical_access(), on_hit=hit
        )
        if (
            failed
            and resolved is not None
            and not resolved.canceled
            and target.is_active
        ):
            kind = {
                "stun": Stunned,
                "prone": Prone,
                "burn": Burning,
                "chill": Chilled,
                "daze": Dazed,
            }[self.rider]
            add_status(
                kind,
                actor.uuid,
                target,
                resolved,
                turns=2 if kind in (Stunned, Prone) else None,
            )
        return resolved


class ElectrifiedFlail(MyrmidonStrike):
    name: str = "Electrified Flail"
    rider: Literal["stun", "prone", "burn", "chill", "daze"] = "stun"


class GroundedThunder(MyrmidonStrike):
    name: str = "Grounded Thunder"
    rider: Literal["stun", "prone", "burn", "chill", "daze"] = "prone"


class ScorchingStrike(MyrmidonStrike):
    name: str = "Scorching Strike"
    rider: Literal["stun", "prone", "burn", "chill", "daze"] = "burn"


class HiemalStrike(MyrmidonStrike):
    name: str = "Hiemal Strike"
    rider: Literal["stun", "prone", "burn", "chill", "daze"] = "chill"


class ConcussiveSmash(MyrmidonStrike):
    name: str = "Concussive Smash"
    rider: Literal["stun", "prone", "burn", "chill", "daze"] = "daze"
    rider_dc: int = 18


class SludgySling(NativeSaveBurst):
    name: str = "Sludgy Sling"
    self_centered: bool = True
    radius_feet: int = 10
    half_on_save: bool = False
    packets: tuple[DamageRollProfile, ...] = (
        DamageRollProfile(dice_count=2, die_size=6, damage_type="Bludgeoning"),
    )

    def _finalize_aoe(self, event):
        if self.end_position is None:
            return None
        patch(ElementalMud, self.source_entity_uuid, self.end_position, 10, 3, event)


class MyrmidonCinderousSwipe(NativeSaveBurst):
    name: str = "Cinderous Swipe"
    cone_feet: int = 17
    save_dc: int = 11
    packets: tuple[DamageRollProfile, ...] = (
        DamageRollProfile(
            dice_count=1, die_size=6, flat_bonus=7, damage_type="Slashing"
        ),
        DamageRollProfile(dice_count=3, die_size=6, damage_type="Fire"),
    )


class MyrmidonBurrow(ElementalWarp):
    name: str = "Myrmidon Burrow"
    range_feet: int = 40
    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Myrmidon Burrow",
                cost_type="bonus_actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            ),
            Cost(
                name="Burrow movement",
                cost_type="movement",
                cost=20,
                evaluator=entity_action_economy_cost_evaluator,
            ),
        ]
    )

    def _apply(self, event):
        effect = super()._apply(event)
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return event.cancel(status_message="Actor absent")
        if (
            not effect.canceled
            and actor is not None
            and actor.position == self.end_position
        ):
            landing = MyrmidonLanding(source_entity_uuid=actor.uuid, end_position=actor.position, costs=[])
            actor.perform(landing, landing.current_selection(), parent_event=effect)
        return effect


class MyrmidonLanding(NativeSaveBurst):
    name: str = "Burrow Landing"
    self_centered: bool = True
    radius_feet: int = 10
    packets: tuple[DamageRollProfile, ...] = (
        DamageRollProfile(dice_count=2, die_size=8, damage_type="Bludgeoning"),
    )


class MuckToMetal(BaseAction):
    name: str = "Muck to Metal"
    target_type: TargetType = TargetType.SELF
    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Muck to Metal movement",
                cost_type="movement",
                cost=17,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ]
    )

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return effect.cancel(status_message="Actor absent")
        if not effect.canceled:
            add_status(
                TransmutedToSteel,
                self.source_entity_uuid,
                actor,
                effect,
            )
        return effect


class HealingVapours(NativeSaveBurst):
    action_category: ActionCategory = ActionCategory.ABILITY
    name: str = "Healing Vapours"
    self_centered: bool = True
    radius_feet: int = 30
    include_self: bool = True
    harmful: bool = False
    packets: tuple[DamageRollProfile, ...] = ()

    def get_outcome_profile(self):
        return None

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return event.cancel(status_message="Actor absent")
        target = (
            Entity.get(event.target_entity_uuid)
            if event.target_entity_uuid is not None
            else None
        )
        if effect.canceled or target is None:
            return effect
        if owns_fact(actor, "Poisoned"):
            condition = BaseCondition(
                source_entity_uuid=actor.uuid, target_entity_uuid=target.uuid
            )
            condition_damage(
                condition, target, effect, count=2, die=8, damage_type=DamageType.POISON
            )
        else:
            healing = Healing(
                source_entity_uuid=actor.uuid,
                target_entity_uuid=target.uuid,
                healing_dice=8,
                dice_numbers=2,
                healing_bonus=ModifiableValue.create(
                    source_entity_uuid=actor.uuid, base_value=0
                ),
            )
            roll = fire_heal_roll_result(
                actor.uuid, target.uuid, healing, effect, self.name
            )
            target.receive_healing(roll.total, actor.uuid, parent_event=effect.uuid)
        return effect

    def _finalize_aoe(self, event):
        if self.end_position is None:
            return None
        patch(WetSurface, self.source_entity_uuid, self.end_position, 30, 3, event)


class RagingVortexZone(SilenceZone):
    name: str = "Raging Vortex"
    content_ref: ContentRef | None = None
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset(
        {
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.LEAVE,
            SpatialEffectTriggerKind.TURN_START,
        }
    )
    membership_trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset(
        {
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }
    )
    _contacts: set[tuple[UUID, object]] = PrivateAttr(default_factory=set)

    def _admit_trigger(self, kind, identity, event):
        admitted = AreaCondition._admit_trigger(self, kind, identity, event)
        entity = Entity.get(identity)
        if admitted and entity is not None and kind in self.membership_trigger_kinds:
            self.apply_membership(entity, parent_event=event)
        if admitted and kind in (
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        ):
            key = (
                identity,
                event.turn_execution_id
                or EventQueue.current_turn_execution_id()
                or event.lineage_uuid,
            )
            if key not in self._contacts:
                self._contacts.add(key)
                target = Entity.get(identity)
                if target is not None:
                    condition_damage(
                        self,
                        target,
                        event,
                        count=2,
                        die=8,
                        damage_type=DamageType.BLUDGEONING,
                    )
        return admitted

    def _create_zone_turn_start_handler(self):
        return EventHandler(
            name="Vortex start contact",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.TURN_START, event_phase=EventPhase.EXECUTION)
            ],
            event_processor=lambda event, source: None,
        )


class RagingVortexOwner(BaseCondition):
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    description: str = "Owns one ten-turn vortex and its exact replacement."
    name: str = "Raging Vortex Owner"
    child_removal_policy: Literal["none", "any", "last"] = "any"
    duration: Duration = Field(
        default_factory=lambda: Duration(duration=10, duration_type=DurationType.ROUNDS)
    )


class RagingVortex(ElementalWarp):
    name: str = "Raging Vortex"
    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Raging Vortex",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ]
    )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> str | None:
        return technique_destination_error(self, scan, selection)

    def _apply(self, event):
        if self.end_position is None:
            return event.cancel(status_message="Destination absent")
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return event.cancel(status_message="Actor absent")
        effect = event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        with BaseBlock.condition_removal_scope():
            owner = RagingVortexOwner(
                source_entity_uuid=actor.uuid,
                target_entity_uuid=actor.uuid,
                effect_origin=technique_origin(effect),
            )
            prepared = actor.prepare_condition_application(owner, parent_event=effect)
            if not isinstance(prepared, PreparedConditionApplication):
                return effect.cancel(status_message="Vortex replacement refused")
            zone = RagingVortexZone(
                source_entity_uuid=actor.uuid,
                position=self.end_position,
                content_ref=get_content_declaration(RagingVortexZone).ref,
                faction=actor.faction,
                duration=Duration(duration=10, duration_type=DurationType.ROUNDS),
                effect_origin=technique_origin(effect),
            )
            try:
                result = zone.activate(parent_event=effect)
                if result is None or result.canceled:
                    return effect.cancel(status_message="Vortex refused")
                owner.add_linked_condition(zone.uuid, zone.uuid)
                actor.commit_condition_application(prepared)
                actor.publish_condition_application(prepared)
                return effect
            finally:
                if not prepared.committed:
                    actor.cancel_condition_application(prepared, "Vortex refused")


class SweetplumRestrained(Restrained):
    name: str = "Sweetplum Restrained"
    description: str = "Restrained by one exact Sweetplum Gales field."
    immunity_names: tuple[str, ...] = ("Restrained",)

    def get_display_name(self):
        return "Restrained"


class SweetplumFieldOwner(BaseCondition):
    child_removal_policy: Literal["none", "any", "last"] = "any"
    name: str = "Sweetplum Field Owner"
    description: str = "Owns one independent Gales field through body retirement."
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    field_uuid: UUID

    def model_post_init(self, context):
        super().model_post_init(context)
        self.name = f"Sweetplum Field Owner:{self.field_uuid}"


class SweetplumMembership(SpatialConditionMembershipSource):
    description: str = "Owns restraint from one exact Gales field."

    def create_manifestation(self, target):
        return SweetplumRestrained(
            name=f"Sweetplum Restrained:{self.source_spatial_condition_uuid}",
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
        )


class SweetplumGalesZone(MembershipAreaCondition):
    description: str = (
        "Independent three-turn enemy restraint field with STR15 entry/start saves."
    )
    name: str = "Sweetplum Gales"
    area: AoEShape = Sphere(radius_feet=10)
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = (
        SpatialEffectOccupancyPolicy.OVERLAPPING
    )
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset(
        {
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.LEAVE,
            SpatialEffectTriggerKind.TURN_START,
        }
    )
    membership_trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset(
        {
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }
    )
    duration: Duration = Field(
        default_factory=lambda: Duration(duration=3, duration_type=DurationType.ROUNDS)
    )
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def membership_source_class(self):
        return SweetplumMembership

    def membership_applies_to(self, entity):
        actor = Entity.get(self.source_entity_uuid)
        return actor is not None and actor.is_enemy(entity)

    def apply_membership(self, entity, *, parent_event):
        if condition_save(
            self, entity, parent_event, "strength", 15, "action.djinni.sweetplum_gales"
        ):
            self.remove_membership(entity, parent_event=parent_event)
            return None
        return super().apply_membership(entity, parent_event=parent_event)

    def _create_zone_turn_start_handler(self):
        return EventHandler(
            name="Gales recovery",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.TURN_START, event_phase=EventPhase.EXECUTION)
            ],
            event_processor=lambda event, source: None,
        )


class SweetplumGales(ElementalWarp):
    name: str = "Sweetplum Gales"
    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Sweetplum Gales",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ]
    )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> str | None:
        return technique_destination_error(self, scan, selection)

    def _apply(self, event):
        if self.end_position is None:
            return event.cancel(status_message="Destination absent")
        effect = event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return event.cancel(status_message="Actor absent")
        zone = SweetplumGalesZone(
            source_entity_uuid=actor.uuid,
            position=self.end_position,
            content_ref=get_content_declaration(SweetplumGalesZone).ref,
            effect_origin=technique_origin(effect),
        )
        owner = SweetplumFieldOwner(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=actor.uuid,
            field_uuid=zone.uuid,
            effect_origin=technique_origin(effect),
        )
        with BaseBlock.condition_removal_scope():
            prepared = actor.prepare_condition_application(owner, parent_event=effect)
            if not isinstance(prepared, PreparedConditionApplication):
                return effect.cancel(status_message="Gales owner refused")
            try:
                result = zone.activate(parent_event=effect)
                if result is None or result.canceled:
                    return effect.cancel(status_message="Gales field refused")
                owner.add_linked_condition(zone.uuid, zone.uuid)
                actor.commit_condition_application(prepared)
                actor.publish_condition_application(prepared)
            finally:
                if not prepared.committed:
                    actor.cancel_condition_application(prepared, "Gales refused")
        return effect


class Immolation(BaseAction):
    name: str = "Immolation"
    target_type: TargetType = TargetType.SELF
    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Immolation",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ]
    )

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return event.cancel(status_message="Actor absent")
        if effect.canceled:
            return effect
        with BaseBlock.condition_removal_scope():
            concentration = Concentrating(
                source_entity_uuid=actor.uuid,
                target_entity_uuid=actor.uuid,
                spell_name=self.name,
                spell_id="action.fire_myrmidon.immolation",
            )
            prepared = actor.prepare_condition_application(
                concentration, parent_event=effect
            )
            if not isinstance(prepared, PreparedConditionApplication):
                return effect.cancel(status_message="Immolation concentration refused")
            application = None
            try:
                haste = HasteEffect(
                    source_entity_uuid=actor.uuid,
                    target_entity_uuid=actor.uuid,
                    caster_uuid=actor.uuid,
                    tags={ConditionTag.MAGICAL},
                    effect_origin=technique_origin(effect),
                    duration=Duration(duration=3, duration_type=DurationType.ROUNDS),
                )
                application = actor.prepare_condition_application(
                    haste, parent_event=effect
                )
                if not isinstance(application, PreparedConditionApplication):
                    return effect.cancel(status_message="Immolation refused")
                concentration.add_linked_condition(actor.uuid, haste.uuid)
                actor.commit_condition_application(prepared)
                actor.commit_condition_application(application)
                errors = []
                for token in (prepared, application):
                    try:
                        actor.publish_condition_application(token)
                    except BaseException as error:
                        errors.append(error)
                if errors:
                    raise BaseExceptionGroup("Immolation publication failed", errors)
            finally:
                if (
                    isinstance(application, PreparedConditionApplication)
                    and not application.committed
                ):
                    actor.cancel_condition_application(
                        application, "Immolation refused"
                    )
                if not prepared.committed:
                    actor.cancel_condition_application(prepared, "Immolation refused")
        return effect


class DrainingKiss(BaseAction):
    name: str = "Draining Kiss"
    description: str = (
        "Consume this Cambion's Charm Person on a Humanoid; WIS15 or 5d10+5 Psychic."
    )
    target_type: TargetType = TargetType.ENTITY
    harmful: bool = True
    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Draining Kiss",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ]
    )

    def get_range(self):
        return Range(type=RangeType.RANGE, normal=30)

    def get_outcome_profile(self):
        return ActionOutcomeProfile(
            resolution=OutcomeResolution.SAVING_THROW,
            save_ability="wisdom",
            save_dc=15,
            half_damage_on_save=False,
            damage_rolls=(
                DamageRollProfile(
                    dice_count=5, die_size=10, flat_bonus=5, damage_type="Psychic"
                ),
            ),
        )

    def charm(self, target):
        return next(
            (
                condition
                for condition in target.active_conditions_by_uuid.values()
                if isinstance(condition, Charmed)
                and condition.effect_origin is not None
                and condition.effect_origin.source_id in ("spell.charm_person", "charm_person")
                and condition.source_entity_uuid == self.source_entity_uuid
                and condition.contributions_active()
            ),
            None,
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> str | None:
        actor = Entity.get(self.source_entity_uuid)
        target = Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
        if actor is None or target is None or self.charm(target) is None:
            return "This Cambion must have charmed the target"
        if grid_distance_feet(
            actor.position, target.position
        ) > 30 or target.uuid not in scan.creatures:
            return "Kiss target out of range or unseen"
        return None

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        target = (
            Entity.get(event.target_entity_uuid)
            if event.target_entity_uuid is not None
            else None
        )
        if effect.canceled or target is None:
            return effect
        charm = self.charm(target)
        if charm is None:
            return effect.cancel(status_message="Charm ended")
        with BaseBlock.condition_removal_scope():
            prepared = PreparedConditionRemovals([])
            try:
                canceled = BaseBlock._prepare_condition_removal_tree(
                    charm,
                    condition_owner=target,
                    expire=False,
                    parent_event=effect,
                    prepared=prepared.entries,
                    visited=set(),
                )
                if canceled is not None:
                    return effect.cancel(status_message="Charm consumption refused")
                save = SavingThrowEvent(
                    source_entity_uuid=self.source_entity_uuid,
                    target_entity_uuid=target.uuid,
                    ability_name="wisdom",
                    dc=15,
                    parent_event=effect.uuid,
                    saving_throw_context=SavingThrowContext(
                        cause_id=effect.behavior_id,
                        effect_id=effect.behavior_id + ".save",
                        is_magical=True,
                    ),
                )
                if not target.saving_throw(save)[2]:
                    damage = Damage(
                        source_entity_uuid=self.source_entity_uuid,
                        target_entity_uuid=target.uuid,
                        damage_dice=10,
                        dice_numbers=5,
                        damage_type=DamageType.PSYCHIC,
                        damage_bonus=ModifiableValue.create(
                            source_entity_uuid=self.source_entity_uuid, base_value=5
                        ),
                    )
                    roll = damage.get_dice(AttackOutcome.HIT).roll
                    target.receive_damage(
                        roll.total,
                        DamageType.PSYCHIC,
                        self.source_entity_uuid,
                        damages=[damage],
                        damage_rolls=[roll],
                        parent_event=effect.uuid,
                    )
                BaseBlock.commit_owned_condition_removals(prepared)
                BaseBlock.publish_owned_condition_removals(prepared)
                return effect
            finally:
                if prepared.committed_result is None:
                    BaseBlock.cancel_owned_condition_removals(
                        prepared, "Kiss consumption refused"
                    )


class ElementalMultiattackBonus(BaseCondition):
    description: str = "Doubles native Multiattack dice against the authored status."
    name: str = "Elemental Multiattack Bonus"
    prerequisite: str
    packet_count: int = 1

    def _apply(self, event):
        actor = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if actor is None:
            return [], [], [], [], event.cancel(status_message="Recipient absent")

        def extra(boundary, _):
            if (
                not isinstance(boundary, DamageRollResultEvent)
                or not boundary.damage_packets
            ):
                return None
            ancestor = (
                EventQueue.get_event_by_uuid(boundary.parent_event)
                if boundary.parent_event is not None
                else None
            )
            while ancestor is not None and not (
                isinstance(ancestor, ActionEvent)
                and ancestor.behavior_id == "action.monster.multiattack"
            ):
                ancestor = (
                    EventQueue.get_event_by_uuid(ancestor.parent_event)
                    if ancestor.parent_event
                    else None
                )
            target = (
                Entity.get(boundary.target_entity_uuid)
                if boundary.target_entity_uuid is not None
                else None
            )
            if (
                ancestor is None
                or target is None
                or not owns_fact(target, self.prerequisite)
            ):
                return None
            changed = boundary
            for packet in boundary.damage_packets[: self.packet_count]:
                original = packet.damage
                damage = Damage(
                    source_entity_uuid=actor.uuid,
                    target_entity_uuid=target.uuid,
                    damage_dice=original.damage_dice,
                    dice_numbers=original.dice_numbers,
                    damage_type=original.damage_type,
                    attack_magical=original.attack_magical,
                    damage_bonus=ModifiableValue.create(
                        source_entity_uuid=actor.uuid, base_value=0
                    ),
                )
                changed = changed.append_damage_roll(
                    damage,
                    damage.get_dice(boundary.attack_outcome).roll,
                    self.name,
                    "Double elemental dice",
                )
            return changed

        handler = EventHandler(
            name=self.name,
            source_entity_uuid=actor.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.DAMAGE_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=actor.uuid,
                )
            ],
            event_processor=extra,
        )
        actor.add_event_handler(handler)
        return [], [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT)


class MyrmidonTenacity(BaseCondition):
    description: str = "A melee miss deals four Bludgeoning without becoming a hit."
    name: str = "Myrmidon Tenacity"

    def _apply(self, event):
        actor = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if actor is None:
            return [], [], [], [], event.cancel(status_message="Recipient absent")
        seen = set()

        def miss(boundary, _):
            if (
                not isinstance(boundary, AttackEvent)
                or boundary.attack_outcome
                not in (AttackOutcome.MISS, AttackOutcome.CRIT_MISS)
                or boundary.canceled
                or boundary.lineage_uuid in seen
            ):
                return None
            if boundary.range is None or boundary.range.type is not RangeType.REACH:
                return None
            target = (
                Entity.get(boundary.target_entity_uuid)
                if boundary.target_entity_uuid is not None
                else None
            )
            if target is not None:
                seen.add(boundary.lineage_uuid)
                target.receive_damage(
                    max(actor.ability_scores.strength.modifier, 1),
                    DamageType.BLUDGEONING,
                    actor.uuid,
                    parent_event=boundary.uuid,
                )
            return None

        handler = EventHandler(
            name=self.name,
            source_entity_uuid=actor.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=actor.uuid,
                )
            ],
            event_processor=miss,
        )
        actor.add_event_handler(handler)
        return [], [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT)


class DragonBreath(NativeSaveBurst):
    name: str = "Draconic Breath"
    cone_feet: int = 30
    allowance_uuid: UUID | None = None

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> str | None:
        if self.allowance_uuid is not None:
            owner = BaseCondition.get(self.allowance_uuid)
            if (
                not isinstance(owner, DraconicBreathCadence)
                or owner.free_action_uuid != selection.template_uuid
                or not owner.contributions_active()
            ):
                return "Free Breath allowance is absent"
        return NativeSaveBurst.rule_error(self, scan, selection)

    def _apply_costs(self, event):
        result = super()._apply_costs(event)
        if (
            self.allowance_uuid is not None
            and result is not None
            and not result.canceled
        ):
            owner = BaseCondition.get(self.allowance_uuid)
            if isinstance(owner, DraconicBreathCadence):
                owner.consume()
        return result


class DraconicBreathCadence(BaseCondition):
    description: str = (
        "After the first paid Multiattack grants one free Breath until own turn end."
    )
    name: str = "Draconic Breath Cadence"
    breath_type: DamageType = DamageType.FIRE
    save_dc: int = 15
    issued: bool = False
    free_action_uuid: UUID | None = None
    granted_lineage: UUID | None = None

    def consume(self):
        actor = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if actor is not None and self.free_action_uuid is not None:
            actor.unregister_action_by_uuid(self.free_action_uuid)
        self.free_action_uuid = None

    def _apply(self, event):
        actor = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if actor is None:
            return [], [], [], [], event.cancel(status_message="Recipient absent")

        def cadence(boundary, _):
            if boundary.event_type is EventType.TURN_END:
                self.consume()
                self.issued = False
                self.granted_lineage = None
            elif boundary.phase is EventPhase.CANCEL:
                if boundary.lineage_uuid == self.granted_lineage:
                    self.consume()
                    self.issued = False
                    self.granted_lineage = None
            elif (
                self.contributions_active()
                and isinstance(boundary, ActionEvent)
                and boundary.action_economy_spent
                and not self.issued
                and boundary.behavior_id == "action.monster.multiattack"
            ):
                action = DragonBreath(
                    source_entity_uuid=actor.uuid,
                    template=True,
                    costs=[],
                    name="Free Draconic Breath",
                    allowance_uuid=self.uuid,
                    save_dc=self.save_dc,
                    packets=(
                        DamageRollProfile(
                            dice_count=2, die_size=6, damage_type=self.breath_type.value
                        ),
                    ),
                )
                actor.register_action(action)
                self.free_action_uuid = action.uuid
                self.issued = True
                self.granted_lineage = boundary.lineage_uuid
            return None

        handler = EventHandler(
            name=self.name,
            source_entity_uuid=actor.uuid,

            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=actor.uuid,
                ),
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.CANCEL,
                    event_source_entity_uuid=actor.uuid,
                ),
                Trigger(
                    event_type=EventType.TURN_END,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=actor.uuid,
                ),
            ],
            event_processor=cadence,
        )
        actor.add_event_handler(handler)
        return [], [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT)

    def _release_owned_runtime_state(self, *, parent_event=None):
        self.consume()


class DragonSharedResistance(BaseCondition):
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    description: str = (
        "Shares one selected elemental resistance while the summoned spirit exists."
    )
    name: str = "Dragon Shared Resistance"
    damage_type: DamageType
    body_uuid: UUID

    def _apply(self, event):
        caster = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if caster is None:
            return [], [], [], [], event.cancel(status_message="Recipient absent")
        value = caster.health.damage_reduction
        modifier = ResistanceModifier(
            name=self.name,
            value=ResistanceStatus.RESISTANCE,
            damage_type=self.damage_type,
            source_entity_uuid=self.source_entity_uuid,
        )
        identity = value.self_static.add_resistance_modifier(modifier)
        return [(value.uuid, identity)], [], [], [], event.phase_to(EventPhase.EFFECT)


# Explicit content identities for this finite set of creature techniques.
SUMMON_ACTION_IDENTITIES = (
    (ElementalWarp, "action.elemental.warp"),
    (PrimordialGales, "action.air_elemental.primordial_gales"),
    (GushingAir, "action.air_elemental.gushing_air"),
    (SeismicStrike, "action.earth_elemental.seismic_strike"),
    (CinderousSwipe, "action.fire_elemental.cinderous_swipe"),
    (WintersBreath, "action.water_elemental.winters_breath"),
    (SoilCloggedSlam, "action.earth_elemental.soil_clogged_slam"),
    (SmoulderingTouch, "action.fire_elemental.smouldering_touch"),
    (WaterSlam, "action.water_elemental.slam"),
    (ExplosiveIcicle, "action.water_myrmidon.explosive_icicle"),
    (ElectrifiedFlail, "action.air_myrmidon.electrified_flail"),
    (GroundedThunder, "action.earth_myrmidon.grounded_thunder"),
    (ScorchingStrike, "action.fire_myrmidon.scorching_strike"),
    (HiemalStrike, "action.water_myrmidon.hiemal_strike"),
    (ConcussiveSmash, "action.deva.concussive_smash"),
    (SludgySling, "action.earth_myrmidon.sludgy_sling"),
    (MyrmidonCinderousSwipe, "action.fire_myrmidon.cinderous_swipe"),
    (MyrmidonBurrow, "action.earth_myrmidon.burrow"),
    (MyrmidonLanding, "action.earth_myrmidon.landing"),
    (MuckToMetal, "action.earth_myrmidon.muck_to_metal"),
    (HealingVapours, "action.water_myrmidon.healing_vapours"),
    (RagingVortex, "action.air_myrmidon.raging_vortex"),
    (SweetplumGales, "action.djinni.sweetplum_gales"),
    (Immolation, "action.fire_myrmidon.immolation"),
    (DrainingKiss, "action.cambion.draining_kiss"),
    (DragonBreath, "action.draconic_spirit.breath"),
)
SUMMON_CONDITION_IDENTITIES = (
    (Shocked, "condition.summon.shocked"),
    (TremblingLegs, "condition.summon.trembling_legs"),
    (Burning, "condition.summon.burning"),
    (Chilled, "condition.summon.chilled"),
    (Brittle, "condition.summon.brittle"),
    (Dazed, "condition.summon.dazed"),
    (TransmutedToSteel, "condition.summon.transmuted_to_steel"),
    (ElementalMud, "spatial_effect.summon.mud"),
    (ElementalFire, "spatial_effect.summon.fire"),
    (RagingVortexZone, "spatial_effect.summon.raging_vortex"),
    (RagingVortexOwner, "condition.summon.raging_vortex_owner"),
    (SweetplumMembership, "condition.summon.sweetplum_membership"),
    (SweetplumGalesZone, "spatial_effect.summon.sweetplum_gales"),
    (ElementalMultiattackBonus, "condition.summon.elemental_multiattack_bonus"),
    (MyrmidonTenacity, "condition.summon.tenacity"),
    (DraconicBreathCadence, "condition.summon.draconic_breath_cadence"),
    (DragonSharedResistance, "condition.spell.summon_dragon.shared_resistance"),
)
# Explicit finite closure; content installation stays above these runtime composers.
_TECHNIQUE_CONDITIONS = {
    PrimordialGales: (Shocked,),
    SeismicStrike: (TremblingLegs,),
    CinderousSwipe: (ElementalFire,),
    WintersBreath: (Brittle,),
    SoilCloggedSlam: (ElementalMud,),
    SmoulderingTouch: (Burning, ElementalFire),
    WaterSlam: (Chilled,),
    ElectrifiedFlail: (Stunned,),
    GroundedThunder: (Prone,),
    ScorchingStrike: (Burning,),
    HiemalStrike: (Chilled,),
    ConcussiveSmash: (Dazed,),
    SludgySling: (ElementalMud,),
    MuckToMetal: (TransmutedToSteel,),
    RagingVortex: (RagingVortexOwner, RagingVortexZone),
    SweetplumGales: (SweetplumFieldOwner, SweetplumGalesZone, SweetplumRestrained),
    Immolation: (Concentrating, HasteEffect),
    DrainingKiss: (Charmed,),
}
_TECHNIQUE_IDS: dict[type[BaseCondition], str] = dict(SUMMON_CONDITION_IDENTITIES)
_TECHNIQUE_IDS.update(
    {
        SweetplumFieldOwner: "condition.summon.sweetplum_field_owner",
        SweetplumRestrained: "condition.summon.sweetplum_restrained",
    }
)


def technique_dependencies(kind):
    dependencies = []
    for condition in _TECHNIQUE_CONDITIONS.get(kind, ()):
        reference = (
            behavior_content_ref(
                pack_id="content.srd_5_1_cc",
                content_id=_TECHNIQUE_IDS[condition],
                version=1,
                definition_kind=ContentDefinitionKind.CONDITION,
                runtime_behavior_kind=RuntimeBehaviorKind.CONDITION,
            )
            if condition in _TECHNIQUE_IDS
            else behavior_content_ref(
                pack_id="content.srd_5_1_cc",
                content_id="condition.spell.haste",
                version=1,
                definition_kind=ContentDefinitionKind.CONDITION,
                runtime_behavior_kind=RuntimeBehaviorKind.CONDITION,
            )
            if condition is HasteEffect
            else get_content_declaration(condition).ref
        )
        dependencies.append(
            ContentDependency(
                relation=ContentDependencyRelation.APPLIES_CONDITION,
                target_ref=reference,
            )
        )
    if kind is MyrmidonBurrow:
        dependencies.append(
            ContentDependency(
                relation=ContentDependencyRelation.GRANTS_ACTION,
                target_ref=behavior_content_ref(
                    pack_id="content.srd_5_1_cc",
                    content_id="action.earth_myrmidon.landing",
                    version=1,
                    definition_kind=ContentDefinitionKind.ACTION,
                    runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
                ),
            )
        )
    return tuple(dependencies)


for _action, _identity in SUMMON_ACTION_IDENTITIES:
    behavior_identity(
        pack_id="content.srd_5_1_cc",
        content_id=_identity,
        version=1,
        definition_kind=ContentDefinitionKind.ACTION,
        runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
        dependencies=technique_dependencies(_action),
        descriptor=ContentDescriptorSpec(
            display_name=_action.model_fields["name"].default,
            description="Approved summon creature technique using native actions.",
            visibility=ContentVisibility.PUBLIC,
            tags=("action", "summon"),
            presentation=ContentPresentation(icon_key=_identity),
        ),
        provenance=ContentProvenance(
            primary_source_id="wotc.srd_5_1_cc",
            source_anchor=_identity,
            relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION,
            adapted_from_source_id="wotc.srd_5_1_cc",
            notes="BG3-style techniques of the approved SRD summon adaptations; not verbatim SRD creature entries.",
            fidelity=ContentFidelity.PARTIAL,
            review_status=ContentReviewStatus.REVIEWED,
        ),
    )(_action)


class MyrmidonStrikeDice(BaseCondition):
    name: str = "Myrmidon Strike Dice"
    description: str = (
        "The authored elemental strike adds one d10 to its native weapon hit."
    )
    damage_type: DamageType
    action_id: str

    def get_action_damage_roll_profiles(self, action):
        if (
            action.behavior_binding is not None
            and action.behavior_binding.behavior_id == self.action_id
        ):
            return (
                DamageRollProfile(
                    dice_count=1, die_size=10, damage_type=self.damage_type.value
                ),
            )
        return ()

    def _apply(self, event):
        actor = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if actor is None:
            return [], [], [], [], event.cancel(status_message="Recipient absent")

        def append(boundary, _):
            if not isinstance(boundary, DamageRollResultEvent):
                return None
            attack = (
                EventQueue.get_event_by_uuid(boundary.parent_event)
                if boundary.parent_event is not None
                else None
            )
            if (
                not isinstance(attack, AttackEvent)
                or attack.behavior_id != self.action_id
            ):
                return None
            damage = Damage(
                source_entity_uuid=actor.uuid,
                target_entity_uuid=boundary.target_entity_uuid,
                damage_dice=10,
                dice_numbers=1,
                damage_type=self.damage_type,
                damage_bonus=ModifiableValue.create(
                    source_entity_uuid=actor.uuid, base_value=0
                ),
                attack_magical=True,
            )
            return boundary.append_damage_roll(
                damage,
                damage.get_dice(boundary.attack_outcome).roll,
                self.name,
                "+1d10",
            )

        handler = EventHandler(
            name=self.name,
            source_entity_uuid=actor.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.DAMAGE_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=actor.uuid,
                )
            ],
            event_processor=append,
        )
        actor.add_event_handler(handler)
        return [], [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT)


SUMMON_CONDITION_IDENTITIES += (
    (MyrmidonStrikeDice, "condition.summon.myrmidon_strike_dice"),
)

SUMMON_CONDITION_IDENTITIES += (
    (SweetplumRestrained, "condition.summon.sweetplum_restrained"),
    (SweetplumFieldOwner, "condition.summon.sweetplum_field_owner"),
)
