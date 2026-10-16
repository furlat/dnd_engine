"""Four finite BG3-style Divine Intervention actions and their permanent use."""

from uuid import UUID
from pydantic import Field, PrivateAttr

from dnd.actions import (
    entity_action_economy_cost_applier,
    entity_action_economy_cost_evaluator,
    entity_resource_cost_evaluator,
)
from dnd.blocks.action_economy import RechargeType
from dnd.blocks.base_item import BaseItem
from dnd.classes.divine import ClassFeatureLifetime
from dnd.content.items.environment_item_builders import build_storage_chest
from dnd.core.base_actions import BaseAction, Cost, TargetType
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome
from dnd.core.effect_types import EffectOrigin, EffectOriginKind
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    Damage,
    EventQueue,
    EventHandler,
    EventPhase,
    EventType,
    Trigger,
    PermanentFeatureUsedEvent,
    RestResourcesRecoveredEvent,
)
from dnd.core.geometry import grid_distance_feet
from dnd.core.gridmap import PreparedObjectPlacement, get_map
from dnd.core.life_types import LifeState, RemainsDisposition
from dnd.core.values import ModifiableValue
from dnd.core.saving_throw_types import SavingThrowContext
from dnd.entity import Entity
from dnd.items.divine_rewards import build_devotees_mace
from dnd.items.consumables import (
    build_healing_potion,
    build_haste_potion,
    build_greater_invisibility_potion,
    build_true_seeing_potion,
)


INTERVENTION_ID = "class_feature.cleric.divine_intervention"


class InterventionUseOwner(ClassFeatureLifetime):
    name: str = "Divine Intervention Use Owner"
    description: str = "Commits the exact permanent Intervention use after accepted native branch costs."

    def _apply(self, event):
        def spent(boundary, _):
            if not any(
                name == "divine_intervention" and amount > 0
                for name, amount in boundary.named_resource_costs
            ):
                return None
            actor = Entity.get(self.target_entity_uuid)
            if INTERVENTION_ID not in actor.permanent_feature_uses:
                actor.permanent_feature_uses = (
                    *actor.permanent_feature_uses,
                    INTERVENTION_ID,
                )
                fact = EventQueue.publish_committed_phase(
                    PermanentFeatureUsedEvent(
                        source_entity_uuid=actor.uuid,
                        target_entity_uuid=actor.uuid,
                        parent_event=boundary.uuid,
                        phase=EventPhase.EFFECT,
                        use_register=False,
                        permanent_feature_uses=actor.permanent_feature_uses,
                    )
                )
                fact.phase_to(EventPhase.COMPLETION)

        actor = Entity.get(self.target_entity_uuid)
        handler = EventHandler(
            name="Divine Intervention committed use",
            source_entity_uuid=actor.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ACTION_COSTS_COMMITTED,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=actor.uuid,
                )
            ],
            event_processor=spent,
        )
        actor.add_event_handler(handler)
        return [], [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT)


def intervention_costs():
    return [
        Cost(
            name="Divine Intervention",
            cost_type="actions",
            cost=1,
            evaluator=entity_action_economy_cost_evaluator,
            resource_name="divine_intervention",
            resource_cost=1,
            resource_evaluator=entity_resource_cost_evaluator,
        )
    ]


def intervention_origin():
    return EffectOrigin(
        kind=EffectOriginKind.ACTION,
        magical=True,
        source_id=INTERVENTION_ID,
    )


class SunderHeretical(BaseAction):
    name: str = "Divine Intervention: Sunder the Heretical"
    description: str = (
        "Once per character: enemies within50ft take8d10 radiant; WIS save for half."
    )
    target_type: TargetType = TargetType.SELF
    casting_source_id: UUID
    effect_origin: EffectOrigin = Field(default_factory=intervention_origin)
    costs: list[Cost] = Field(default_factory=intervention_costs)

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        actor = Entity.get(self.source_entity_uuid)
        if effect.canceled:
            return effect
        if event.application is None:
            targets = [
                target.uuid
                for target in Entity.get_all_entities()
                if target.is_deployed
                and actor.is_enemy(target)
                and grid_distance_feet(actor.position, target.position) <= 50
            ]
            self._apply_target_batch(event, targets, parent_event=effect)
        else:
            target = Entity.get(event.target_entity_uuid)
            request = actor.create_saving_throw_request(
                target.uuid,
                "wisdom",
                actor.spell_save_dc(spellcasting_source_id=self.casting_source_id),
                parent_event=effect.uuid,
                saving_throw_context=SavingThrowContext(
                    cause_id="class_feature.cleric.divine_intervention",
                    effect_id="class_feature.cleric.divine_intervention.sunder",
                    is_magical=True,
                ),
            )
            saved = target.saving_throw(request)[2]
            damage = Damage(
                source_entity_uuid=actor.uuid,
                target_entity_uuid=target.uuid,
                name="Sunder the Heretical",
                damage_dice=10,
                dice_numbers=8,
                damage_type=DamageType.RADIANT,
                damage_bonus=ModifiableValue.create(
                    source_entity_uuid=actor.uuid, base_value=0
                ),
                effect_origin=effect.get_effect_origin(),
            )
            roll = damage.get_dice(AttackOutcome.HIT).roll
            target.receive_damage(
                roll.total // 2 if saved else roll.total,
                DamageType.RADIANT,
                actor.uuid,
                damages=[damage],
                damage_rolls=[roll],
                parent_event=effect.uuid,
                effect_origin=effect.get_effect_origin(),
            )
        return effect


class OpulentRevival(BaseAction):
    name: str = "Divine Intervention: Opulent Revival"
    description: str = "Once per character: living allies within60ft recover HP/slots/rest resources; intact dead companions revive at half their own HP."
    target_type: TargetType = TargetType.SELF
    effect_origin: EffectOrigin = Field(default_factory=intervention_origin)
    costs: list[Cost] = Field(default_factory=intervention_costs)
    _revivals: list = PrivateAttr(default_factory=list)
    _living: tuple[UUID, ...] = PrivateAttr(default=())

    def apply(self, *args, **kwargs):
        try:
            return super().apply(*args, **kwargs)
        finally:
            for identity, revival in self._revivals:
                target = Entity.get(identity)
                if (
                    target is not None
                    and target.health.life_state is LifeState.DEAD
                    and not revival.canceled
                ):
                    revival.cancel(status_message="Intervention revival did not commit")
            self._revivals = []

    def _apply_costs(self, event):
        actor = Entity.get(self.source_entity_uuid)
        living = []
        self._revivals = []
        for target in Entity.get_all_entities():
            if (
                target.faction != actor.faction
                or grid_distance_feet(actor.position, target.position) > 60
            ):
                continue
            if target.health.life_state is LifeState.DEAD:
                if (
                    not target.is_player_companion
                    or target.health.remains_disposition
                    is RemainsDisposition.DISINTEGRATED
                ):
                    continue
                if (
                    not get_map().has_tile(*target.position)
                    or not get_map().is_walkable_for(*target.position, target.uuid)
                    or get_map().get_entities_at(target.position) - {target.uuid}
                ):
                    continue
                revival = target.prepare_revival(
                    max(1, target.get_max_hp() // 2),
                    reduce_exhaustion=False,
                    parent_event=event,
                )
                if revival is not None:
                    self._revivals.append((target.uuid, revival))
            elif target.is_deployed:
                living.append(target.uuid)
        self._living = tuple(living)
        if not self._living and not self._revivals:
            return event.cancel(status_message="There are no eligible recipients")
        return entity_action_economy_cost_applier(event, actor.uuid)

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        actor = Entity.get(self.source_entity_uuid)
        for index, (identity, revival) in enumerate(self._revivals):
            target = Entity.get(identity)
            eligible = (
                target is not None
                and target.is_player_companion
                and target.faction == actor.faction
                and grid_distance_feet(actor.position, target.position) <= 60
                and get_map().has_tile(*target.position)
                and get_map().is_walkable_for(*target.position, target.uuid)
                and not get_map().get_entities_at(target.position) - {target.uuid}
            )
            if not eligible or not target.commit_revival(revival):
                self._revivals[index] = (
                    identity,
                    revival.cancel(status_message="Admitted revival recipient changed"),
                )
        for identity in self._living:
            target = Entity.get(identity)
            if (
                target is None
                or not target.is_deployed
                or target.health.life_state is LifeState.DEAD
                or target.faction != actor.faction
                or grid_distance_feet(actor.position, target.position) > 60
            ):
                continue
            target.receive_healing(
                target.get_max_hp(),
                self.source_entity_uuid,
                source_description="Opulent Revival",
                effect_origin=effect.get_effect_origin(),
                parent_event=effect.uuid,
            )
            target.action_economy.reset_spell_slot_costs()
            recovered = []
            for name, resource in target.action_economy.resources.items():
                if resource.recharge_type in (
                    RechargeType.SHORT_REST,
                    RechargeType.LONG_REST,
                ):
                    resource.recharge()
                    recovered.append(name)
            fact = EventQueue.publish_committed_phase(
                RestResourcesRecoveredEvent(
                    source_entity_uuid=target.uuid,
                    target_entity_uuid=target.uuid,
                    parent_event=effect.uuid,
                    phase=EventPhase.EFFECT,
                    use_register=False,
                    resource_names=tuple(recovered),
                )
            )
            fact.phase_to(EventPhase.COMPLETION)
        return effect


class ArmThyServant(BaseAction):
    name: str = "Divine Intervention: Arm Thy Servant"
    description: str = (
        "Once per character: create a permanent Devotee's Mace and equip it when legal."
    )
    target_type: TargetType = TargetType.SELF
    effect_origin: EffectOrigin = Field(default_factory=intervention_origin)
    costs: list[Cost] = Field(default_factory=intervention_costs)
    _reward: BaseItem | None = PrivateAttr(default=None)

    def apply(self, *args, **kwargs):
        try:
            return super().apply(*args, **kwargs)
        finally:
            if self._reward is not None and self._reward.owner_uuid is None:
                for block in self._reward.owned_block_tree():
                    block.release_runtime_ownership()
            self._reward = None

    def _apply_costs(self, event):
        actor = Entity.get(self.source_entity_uuid)
        self._reward = build_devotees_mace(actor.uuid)
        if not actor.inventory.can_add(self._reward):
            return event.cancel(
                status_message="Inventory cannot accept the reward mace"
            )
        return entity_action_economy_cost_applier(event, actor.uuid)

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        actor = Entity.get(self.source_entity_uuid)
        if self._reward is None or not actor.loot_item(
            self._reward, parent_event=effect
        ):
            return effect.cancel(status_message="Reward inventory admission changed")
        equipped = actor.equip_item(self._reward.uuid, WeaponSlot.MELEE_MAIN)
        return effect.with_updates(
            status_message="Devotee's Mace equipped"
            if equipped
            else "Devotee's Mace retained in inventory"
        )


class GoldenGenerosity(BaseAction):
    name: str = "Divine Intervention: Golden Generosity"
    description: str = "Once per character: create a permanent chest holding four greater healing potions, Haste, Greater Invisibility and True Seeing."
    target_type: TargetType = TargetType.SELF
    effect_origin: EffectOrigin = Field(default_factory=intervention_origin)
    costs: list[Cost] = Field(default_factory=intervention_costs)
    _chest: BaseItem | None = PrivateAttr(default=None)
    _placement: PreparedObjectPlacement | None = PrivateAttr(default=None)

    def apply(self, *args, **kwargs):
        try:
            return super().apply(*args, **kwargs)
        finally:
            if self._placement is not None:
                get_map().cancel_object_placement(
                    self._placement, "Intervention reward did not commit"
                )
            if (
                self._chest is not None
                and get_map().get_object_position(self._chest.uuid) is None
            ):
                for item in tuple(self._chest.get_storage_block().items.values()):
                    for block in item.owned_block_tree():
                        block.release_runtime_ownership()
                for block in self._chest.owned_block_tree():
                    block.release_runtime_ownership()
            self._placement = None
            self._chest = None

    def _apply_costs(self, event):
        actor = Entity.get(self.source_entity_uuid)
        chest = build_storage_chest(
            "Golden Generosity",
            include_loot_all_action=True,
            is_open=True,
            source_entity_uuid=actor.uuid,
        )
        self._chest = chest
        chest.chest_inventory.install_initial_items(
            (
                build_healing_potion(
                    actor.uuid, stack_count=4, heal_amount=4, healing_dice_count=4
                ),
                build_haste_potion(actor.uuid),
                build_greater_invisibility_potion(actor.uuid),
                build_true_seeing_potion(actor.uuid),
            )
        )
        for position in sorted(
            get_map().get_all_tiles(),
            key=lambda cell: (grid_distance_feet(actor.position, cell), cell),
        ):
            if grid_distance_feet(actor.position, position) > 5:
                continue
            prepared = get_map().prepare_object_placement(
                chest.uuid, position, event.uuid
            )
            if prepared is not None:
                self._placement = prepared
                break
        if self._placement is None:
            return event.cancel(
                status_message="There is no legal nearby reward placement"
            )
        return entity_action_economy_cost_applier(event, actor.uuid)

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        if self._placement is None or not get_map().validate_prepared_object_placement(
            self._placement
        ):
            return effect.cancel(status_message="Reward placement changed")
        get_map().commit_object_placement(self._placement)
        self._placement = None
        return effect
