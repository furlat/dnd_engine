"""Cleric and Life Domain native actions and owning event processors."""

from uuid import UUID

from pydantic import Field

from dnd.actions import (
    entity_action_economy_cost_applier,
    entity_action_economy_cost_evaluator,
    entity_resource_cost_evaluator,
)
from dnd.classes.divine import Turned, turn_creature, turning_targets
from dnd.core.base_actions import BaseAction, Cost, TargetType
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.dice import AttackOutcome, Dice
from dnd.core.effect_types import EffectOrigin, EffectOriginKind
from dnd.core.events import (
    Damage,
    DamageRollResultEvent,
    ActionApplicationCommittedEvent,
    HealEvent,
    HealingAppliedEvent,
    HealRollResultEvent,
    EventPhase,
)
from dnd.core.geometry import grid_distance_feet
from dnd.core.values import ModifiableValue
from dnd.entity import Entity


class TurnUndead(BaseAction):
    name: str = "Turn Undead"
    target_type: TargetType = TargetType.SELF
    casting_source_id: UUID
    feature_owner_uuid: UUID | None = None
    effect_origin: EffectOrigin = Field(
        default_factory=lambda: EffectOrigin(
            kind=EffectOriginKind.ACTION,
            magical=True,
            source_id="class_feature.cleric.turn_undead",
        )
    )
    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Turn Undead",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
                resource_name="channel_divinity",
                resource_cost=1,
                resource_evaluator=entity_resource_cost_evaluator,
            )
        ]
    )

    def _validate(self, event):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return event.cancel(status_message="Actor absent")
        return super()._validate(event)

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        if not effect.canceled:
            actor = Entity.get(self.source_entity_uuid)
            if event.application is None:
                self._apply_target_batch(
                    event,
                    turning_targets(actor, (CreatureType.UNDEAD,)),
                    parent_event=effect,
                )
            else:
                turn_creature(
                    actor,
                    Entity.get(event.target_entity_uuid),
                    effect,
                    casting_source_id=self.casting_source_id,
                    feature_owner_uuid=self.feature_owner_uuid,
                )
        return effect

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)


class PreserveLife(BaseAction):
    name: str = "Preserve Life"
    target_type: TargetType = TargetType.SELF
    effect_origin: EffectOrigin = Field(
        default_factory=lambda: EffectOrigin(
            kind=EffectOriginKind.ACTION,
            magical=True,
            source_id="class_feature.cleric.preserve_life",
        )
    )
    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Preserve Life",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
                resource_name="channel_divinity",
                resource_cost=1,
                resource_evaluator=entity_resource_cost_evaluator,
            )
        ]
    )

    def _validate(self, event):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return event.cancel(status_message="Actor absent")
        return super()._validate(event)

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        actor = Entity.get(self.source_entity_uuid)
        if not effect.canceled:
            if event.application is None:
                targets = [
                    target.uuid
                    for target in Entity.get_all_entities()
                    if target.is_deployed
                    and target.faction == actor.faction
                    and grid_distance_feet(actor.position, target.position) <= 30
                    and target.creature_type
                    not in (CreatureType.UNDEAD, CreatureType.CONSTRUCT)
                ]
                self._apply_target_batch(event, targets, parent_event=effect)
            else:
                Entity.get(event.target_entity_uuid).receive_healing(
                    3 * len(actor.applied_class_levels),
                    actor.uuid,
                    parent_event=effect.uuid,
                    effect_origin=effect.get_effect_origin(),
                    source_description="Preserve Life",
                )
        return effect

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)


def disciple_of_life(event, source_uuid):
    if (
        isinstance(event, HealEvent)
        and event.effect_origin is not None
        and event.effect_origin.kind is EffectOriginKind.SPELL
        and (event.effect_origin.effective_spell_level or 0) > 0
    ):
        return event.with_updates(
            total_healing=event.total_healing
            + 2
            + event.effect_origin.effective_spell_level
        )


def blessed_healer(event, source_uuid):
    if (
        isinstance(event, HealingAppliedEvent)
        and event.target_entity_uuid != source_uuid
        and event.actual_healing > 0
        and event.effect_origin is not None
        and event.effect_origin.kind is EffectOriginKind.SPELL
        and (event.effect_origin.effective_spell_level or 0) > 0
    ):
        actor = Entity.get(source_uuid)
        if actor is not None:
            actor.receive_healing(
                2 + event.effect_origin.effective_spell_level,
                actor.uuid,
                source_description="Blessed Healer",
                parent_event=event.uuid,
            )


def supreme_healing(event, source_uuid):
    if (
        not isinstance(event, HealRollResultEvent)
        or event.effect_origin is None
        or event.effect_origin.kind is not EffectOriginKind.SPELL
    ):
        return None
    roll = event.final_roll
    dice = Dice.get(roll.dice_uuid)
    if dice is not None and isinstance(roll.results, list):
        results = [dice.value] * len(roll.results)
        return event.replace_roll(
            roll.model_copy(
                update={"results": results, "total": sum(results) + roll.bonus}
            ),
            "Supreme Healing",
            "Maximize owned spell healing dice",
        )


def divine_strike(event, source_uuid):
    actor = Entity.get(source_uuid)
    if (
        not isinstance(event, DamageRollResultEvent)
        or actor is None
        or not actor.is_my_turn
        or event.attack_kind != "weapon"
        or event.attack_outcome not in (AttackOutcome.HIT, AttackOutcome.CRIT)
        or not actor.action_economy.can_afford_resource("divine_strike", 1)
    ):
        return None
    level = sum(
        row.class_id.value == "class.cleric" for row in actor.applied_class_levels
    )
    damage = Damage(
        source_entity_uuid=source_uuid,
        target_entity_uuid=event.target_entity_uuid,
        name="Divine Strike",
        damage_dice=8,
        dice_numbers=2 if level >= 14 else 1,
        damage_type=DamageType.RADIANT,
        damage_bonus=ModifiableValue.create(
            source_entity_uuid=source_uuid, base_value=0
        ),
        effect_origin=EffectOrigin(
            kind=EffectOriginKind.ACTION, source_id="class_feature.cleric.divine_strike"
        ),
    )
    actor.action_economy.consume_resource("divine_strike", 1)
    return event.append_damage_roll(
        damage,
        damage.get_dice(event.attack_outcome).roll,
        "Divine Strike",
        "Once on own turn",
    )


def destroy_undead(event, source_uuid):
    if not isinstance(event, ActionApplicationCommittedEvent):
        return None
    origin = event.get_effect_origin()
    if origin is None or origin.source_id != "class_feature.cleric.turn_undead":
        return None
    target = Entity.get(event.target_entity_uuid)
    if target is None:
        return None
    condition = next(
        (
            condition
            for condition in target.active_conditions_by_uuid.values()
            if isinstance(condition, Turned) and condition.effect_origin == origin
        ),
        None,
    )
    if condition is None:
        return None
    condition.damage_break_armed = False
    try:
        damage = Damage(
            source_entity_uuid=source_uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=4,
            damage_type=DamageType.RADIANT,
            effect_origin=origin,
            damage_bonus=ModifiableValue.create(
                source_entity_uuid=source_uuid, base_value=0
            ),
        )
        roll = damage.get_dice(AttackOutcome.HIT).roll
        target.receive_damage(
            roll.total,
            DamageType.RADIANT,
            source_uuid,
            damages=[damage],
            damage_rolls=[roll],
            parent_event=event.uuid,
            effect_origin=origin,
        )
    finally:
        condition.damage_break_armed = True
