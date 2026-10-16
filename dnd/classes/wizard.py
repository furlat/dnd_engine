"""Wizard native recovery and source-owned Evocation event processors."""

from uuid import uuid4
from pydantic import Field

from dnd.actions import (
    SpellEvent,
    entity_action_economy_cost_applier,
    entity_action_economy_cost_evaluator,
    entity_resource_cost_evaluator,
)
from dnd.core.base_actions import BaseAction, Cost, TargetType, spell_slot_cost_type
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import DurationType, ConditionCategory
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome, Dice, RollType
from dnd.core.effect_types import EffectOriginKind
from dnd.core.events import (
    EventHandler,
    EventPhase,
    EventType,
    Trigger,
    SpellDamageRollResultEvent,
    EffectApplicationEvent,
    ActionCostsCommittedEvent,
    RestCompletedEvent,
    RestResourcesRecoveredEvent,
)
from dnd.core.values import ModifiableValue
from dnd.entity import Entity


class WizardRecoveryState(BaseCondition):
    """Retained rest expenditure; grants no casting or class bonuses by itself."""

    name: str = "Wizard Recovery State"
    description: str = "Retains Wizard recovery expenditure and Overchannel uses until the actual rest boundary."
    condition_category: ConditionCategory = ConditionCategory.INTERNAL
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=None, duration_type=DurationType.PERMANENT
        )
    )
    resource_spent: dict[str, int] = Field(default_factory=dict)

    def _apply(self, event):
        actor = Entity.get(self.target_entity_uuid)
        handlers = [
            EventHandler(
                name="Wizard completed rests",
                source_entity_uuid=actor.uuid,
                runs_while_suppressed=True,
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.REST_COMPLETED,
                        event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=actor.uuid,
                    ),
                    Trigger(
                        event_type=EventType.REST_RESOURCES_RECOVERED,
                        event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=actor.uuid,
                    ),
                ],
                event_processor=self._rest,
            ),
            EventHandler(
                name="Wizard committed expenditure",
                source_entity_uuid=actor.uuid,
                runs_while_suppressed=True,
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.ACTION_COSTS_COMMITTED,
                        event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=actor.uuid,
                    )
                ],
                event_processor=self._spent,
            ),
        ]
        for handler in handlers:
            actor.add_event_handler(handler)
        return (
            [],
            [handler.uuid for handler in handlers],
            [],
            [],
            event.phase_to(EventPhase.EFFECT),
        )

    def _rest(self, event: RestCompletedEvent | RestResourcesRecoveredEvent, context):
        if isinstance(event, RestResourcesRecoveredEvent):
            self.resource_spent = {
                name: spent
                for name, spent in self.resource_spent.items()
                if name not in event.resource_names
            }
            return None
        if event.rest_type == "long_rest":
            actor = Entity.get(self.target_entity_uuid)
            if actor is not None:
                actor.spellcasting.overchannel_uses = 0
            self.resource_spent.clear()
        else:
            self.resource_spent = {
                key: value
                for key, value in self.resource_spent.items()
                if not key.startswith("signature_spell.")
            }

    def _spent(self, event: ActionCostsCommittedEvent, context):
        for name, amount in event.named_resource_costs:
            if name == "arcane_recovery" or name.startswith("signature_spell."):
                self.resource_spent[name] = self.resource_spent.get(name, 0) + amount
        origin = event.effect_origin
        if (
            origin is None
            or not origin.maximize_damage_dice
            or origin.source_event_lineage_uuid != str(event.action_lineage_uuid)
        ):
            return None
        actor = Entity.get(self.target_entity_uuid)
        if actor is None:
            return None
        actor.spellcasting.overchannel_uses += 1
        if actor.spellcasting.overchannel_uses > 1:
            rank = origin.effective_spell_level or 0
            dice = Dice(
                count=actor.spellcasting.overchannel_uses * rank,
                value=12,
                roll_type=RollType.DAMAGE,
                attack_outcome=AttackOutcome.HIT,
                bonus=ModifiableValue.create(
                    source_entity_uuid=actor.uuid, base_value=0
                ),
            )
            actor.receive_damage(
                dice.roll.total,
                DamageType.NECROTIC,
                actor.uuid,
                parent_event=event.uuid,
                ignores_resistance_immunity=True,
            )


def recovery_state(actor: Entity) -> WizardRecoveryState | None:
    return next(
        (
            condition
            for condition in actor.active_conditions_by_uuid.values()
            if isinstance(condition, WizardRecoveryState)
        ),
        None,
    )


class ArcaneRecovery(BaseAction):
    name: str = "Arcane Recovery"
    description: str = "Outside combat, spend recovery points equal to a rank1–5 slot to restore that spent slot."
    target_type: TargetType = TargetType.SELF
    slot_rank: int = Field(default=1, ge=1, le=5)

    def get_discovery_variants(self, entity):
        return [
            self.model_copy(update={"uuid": uuid4(), "slot_rank": rank})
            for rank in range(1, 6)
            if entity.has_spell_slot_capacity(rank)
        ]

    def get_discovery_template_name(self):
        return f"Arcane Recovery [Level {self.slot_rank}]"

    def get_discovery_display_name(self):
        return f"Arcane Recovery (Level {self.slot_rank})"

    def get_source_dynamic_costs(self):
        return [
            Cost(
                name="Arcane Recovery",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
                resource_name="arcane_recovery",
                resource_cost=self.slot_rank,
                resource_evaluator=entity_resource_cost_evaluator,
            )
        ]

    def _validate(self, event):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None or actor.active_encounter_uuid is not None:
            return event.cancel(
                status_message="Arcane Recovery requires being outside an encounter"
            )
        if not actor.has_spell_slot_capacity(
            self.slot_rank
        ) or not actor.action_economy.get_cost_modifiers(
            spell_slot_cost_type(self.slot_rank)
        ):
            return event.cancel(status_message="There is no spent slot of this rank")
        return super()._validate(event)

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        if not effect.canceled:
            actor = Entity.get(self.source_entity_uuid)
            if actor.action_economy.recover_spell_slots(self.slot_rank) != 1:
                return effect.cancel(
                    status_message="The spent slot is no longer available"
                )
        return effect

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)


def sculpt_application_admitted(origin, source_uuid, target_uuid):
    actor, target = Entity.get(source_uuid), Entity.get(target_uuid)
    return not (
        origin.kind is EffectOriginKind.SPELL
        and origin.spell_school == "evocation"
        and origin.area_application
        and origin.harmful
        and actor is not None
        and target is not None
        and (actor.uuid == target.uuid or actor.is_ally(target))
    )


def sculpt_spells(event, source_uuid):
    if (
        isinstance(event, SpellEvent)
        and event.application is not None
        and not sculpt_application_admitted(
            event.get_effect_origin(), source_uuid, event.target_entity_uuid
        )
    ):
        return event.cancel(
            status_message="Sculpt Spells protects this allied spell application"
        )


def sculpt_field_application(event, source_uuid):
    if isinstance(event, EffectApplicationEvent) and not sculpt_application_admitted(
        event.effect_origin, source_uuid, event.target_entity_uuid
    ):
        return event.cancel(
            status_message="Sculpt Spells protects this allied field application"
        )


def sculpt_retained_damage(event, source_uuid):
    if isinstance(
        event, SpellDamageRollResultEvent
    ) and not sculpt_application_admitted(
        event.effect_origin, source_uuid, event.target_entity_uuid
    ):
        return event.cancel(
            status_message="Sculpt Spells protects this allied field contact"
        )


def potent_cantrip(event, source_uuid):
    if (
        isinstance(event, SpellDamageRollResultEvent)
        and event.effect_origin.base_spell_level == 0
        and event.save_success
        and event.success_damage_fraction == 0
    ):
        return event.with_updates(success_damage_fraction=0.5)


def empowered_evocation(event, source_uuid):
    if (
        not isinstance(event, SpellDamageRollResultEvent)
        or event.effect_origin.spell_school != "evocation"
    ):
        return None
    actor = Entity.get(source_uuid)
    if actor is None:
        return None
    bonus = actor.ability_scores.intelligence.get_combined_values(
        use_register=False
    ).normalized_score
    roll = event.final_roll
    return event.replace_roll(
        roll.model_copy(
            update={"bonus": roll.bonus + bonus, "total": max(0, roll.total + bonus)}
        ),
        "Empowered Evocation",
        "INT modifier on this Evocation damage instance",
    )


def select_overchannel(event, source_uuid):
    if (
        not isinstance(event, SpellEvent)
        or event.retained_effect_origin is not None
        or event.application is not None
        or not 1 <= event.cast_at_level <= 5
        or event.spell_level == 0
        or not event.can_deal_damage
    ):
        return None
    actor = Entity.get(source_uuid)
    source = (
        actor.spellcasting.sources.get(event.spellcasting_source_id)
        if actor is not None
        else None
    )
    if source is not None and source.provider_id == "class.wizard":
        return event.with_updates(maximize_damage_dice=True)


def maximize_selected_spell(event, source_uuid):
    if (
        not isinstance(event, SpellDamageRollResultEvent)
        or not event.effect_origin.maximize_damage_dice
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
            "Overchannel",
            "Maximize the selected cast's original spell dice",
        )
