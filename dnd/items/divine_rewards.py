"""Permanent Devotee's Mace reward, composed from native weapon/item owners."""

from uuid import UUID, uuid4
from pydantic import Field

from dnd.core.aoe import AoEShape, Sphere
from dnd.actions import (
    entity_action_economy_cost_applier,
    entity_action_economy_cost_evaluator,
)
from dnd.blocks.base_item import UsableItem
from dnd.blocks.equipment import Weapon
from dnd.core.base_actions import BaseAction, Cost, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import ConditionTag, DurationType
from dnd.core.content.registration import get_content_declaration
from dnd.core.creature_types import DamageType
from dnd.core.effect_types import EffectOrigin, EffectOriginKind
from dnd.core.equipment_types import WeaponKind, WeaponProperty
from dnd.core.events import (
    EventHandler,
    EventPhase,
    EventType,
    Range,
    RangeType,
    Trigger,
    Healing,
)
from dnd.core.geometry import grid_distance_feet
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.spatial.area_conditions import AreaCondition
from dnd.spells.spell_utils import fire_heal_roll_result
from dnd.types.spatial_effects import (
    SpatialEffectAnchorKind,
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
)


class HealingIncenseZone(AreaCondition):
    name: str = "Healing Incense Aura"
    description: str = "Allies starting within ten feet regain1d4 HP from this item."
    source_item_uuid: UUID
    anchor_kind: SpatialEffectAnchorKind = SpatialEffectAnchorKind.ENTITY
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = (
        SpatialEffectOccupancyPolicy.OVERLAPPING
    )
    area: AoEShape = Sphere(radius_feet=10)
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset(
        {SpatialEffectTriggerKind.TURN_START}
    )
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    duration: Duration = Field(
        default_factory=lambda: Duration(duration=10, duration_type=DurationType.ROUNDS)
    )

    def contributions_active(self):
        item = BaseBlock.get(self.source_item_uuid)
        return (
            super().contributions_active()
            and isinstance(item, DevoteesMace)
            and item.is_equipped
            and item.owner_uuid == self.anchor_uuid
            and item.contributions_active()
        )

    def relocate_anchor(self, position, *, parent_event):
        return self.move_zone(position, parent_event=parent_event)

    def _create_zone_turn_start_handler(self):
        def heal(event, _):
            holder, target = (
                Entity.get(self.anchor_uuid),
                Entity.get(event.source_entity_uuid),
            )
            if (
                holder is None
                or target is None
                or holder.faction != target.faction
                or grid_distance_feet(holder.position, target.position) > 10
            ):
                return None
            healing = Healing(
                source_entity_uuid=holder.uuid,
                target_entity_uuid=target.uuid,
                healing_dice=4,
                dice_numbers=1,
                healing_bonus=ModifiableValue.create(
                    source_entity_uuid=holder.uuid, base_value=0
                ),
            )
            roll = fire_heal_roll_result(
                holder.uuid, target.uuid, healing, event, "Healing Incense"
            )
            target.receive_healing(
                roll.total,
                holder.uuid,
                source_description="Healing Incense",
                parent_event=event.uuid,
                effect_origin=EffectOrigin(
                    kind=EffectOriginKind.ITEM,
                    magical=True,
                    source_id="weapon.devotees_mace",
                ),
            )

        return EventHandler(
            name="Healing Incense start-turn healing",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.TURN_START, event_phase=EventPhase.EXECUTION)
            ],
            event_processor=heal,
        )


class HealingIncense(BaseAction):
    name: str = "Healing Incense Aura"
    description: str = "Bonus action: ten-turn ten-foot1d4 healing aura, once per long rest on this mace."
    target_type: TargetType = TargetType.SELF
    costs: list[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Healing Incense",
                cost_type="bonus_actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ]
    )

    def _validate(self, event):
        item = BaseBlock.get(self.source_item_uuid)
        if (
            not isinstance(item, DevoteesMace)
            or not item.is_equipped
            or item.owner_uuid != self.source_entity_uuid
        ):
            return event.cancel(status_message="The exact mace must be equipped")
        return super()._validate(event)

    def _apply_costs(self, event):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)

    def _apply(self, event):
        effect = event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        actor = Entity.get(self.source_entity_uuid)
        zone = HealingIncenseZone(
            source_entity_uuid=actor.uuid,
            anchor_uuid=actor.uuid,
            position=actor.position,
            source_item_uuid=self.source_item_uuid,
            faction=actor.faction,
            content_ref=get_content_declaration(HealingIncenseZone).ref,
            effect_origin=EffectOrigin(
                kind=EffectOriginKind.ITEM,
                magical=True,
                source_id="weapon.devotees_mace",
            ),
        )
        admitted = zone.activate(parent_event=effect)
        if admitted is None or admitted.canceled:
            return effect.cancel(status_message="Healing Incense was rejected")
        return effect


class DevoteesMace(Weapon, UsableItem):
    name: str = "Devotee's Mace"
    description: str = "+3 simple mace,1d6 bludgeoning plus1d8 radiant; bonus-action Healing Incense once per long rest."
    is_magical: bool = True
    is_consumable: bool = False
    is_pickable: bool = True
    charges: int = 1
    max_charges: int = 1
    recharge_on_long_rest: bool = True


def build_devotees_mace(source_entity_uuid: UUID) -> DevoteesMace:
    return DevoteesMace(
        source_entity_uuid=source_entity_uuid,
        item_id="weapon.devotees_mace",
        visual_item_name="Mace",
        weapon_kind=WeaponKind.MACE,
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.SIMPLE],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=source_entity_uuid, base_value=3
        ),
        damage_bonus=ModifiableValue.create(
            source_entity_uuid=source_entity_uuid, base_value=3
        ),
        extra_damage_dices=[8],
        extra_damage_dices_numbers=[1],
        extra_damage_type=[DamageType.RADIANT],
        extra_damage_bonus=[
            ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=0)
        ],
        use_action_templates=[
            HealingIncense(source_entity_uuid=uuid4(), template=True)
        ],
    )
