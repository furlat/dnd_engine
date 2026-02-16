"""Example UsableItems for testing the UsableItem system.

Contains: Door (two approaches), Lever, StorageChest, Campfire actions,
SpellScroll, HealingPotion, WeaponCoat, WandOfFire, ArcaneDevice, environment spell objects.
These are pattern examples, not final game items.
"""

import random
from typing import Optional, List, Tuple, cast as type_cast
from uuid import UUID, uuid4
from pydantic import Field

from dnd.core.base_actions import BaseAction, ActionEvent, TargetType, Cost
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration, DurationType
from dnd.core.events import Event, EventPhase, EventQueue, WeaponSlot, SkillName
from dnd.core.modifiers import DamageType
from dnd.core.values import ModifiableValue
from dnd.core.gridmap import get_map
from dnd.blocks.base_item import UsableItem
from dnd.blocks.equipment import Weapon
from dnd.blocks.inventory import Inventory
from dnd.entity import Entity
from dnd.actions import entity_action_economy_cost_evaluator, SpellAction
from dnd.conditions import Concentrating, GreaterInvisibilityEffect
from dnd.spells.evocation import BurningHands, FireBolt, Fireball, MagicMissile
from dnd.spells.enchantment import HoldPerson
from dnd.spells.abjuration import MageArmor
from dnd.spells.transmutation import SpikeGrowth


# =============================================================================
# Door Actions
# =============================================================================

class OpenDoorAction(BaseAction):
    """Opens a closed door."""
    name: str = Field(default="Open Door")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not door or not isinstance(door, TestDoorA):
            return declaration_event.cancel(status_message="Door not found")
        if door.is_open:
            return declaration_event.cancel(status_message="Door already open")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, TestDoorA):
            return execution_event.cancel(status_message="Door not found")
        old_blocks_movement = door.blocks_movement
        old_blocks_vision = door.blocks_vision_field
        door.is_open = True
        door.blocks_movement = False
        door.blocks_vision_field = False
        door._notify_blocking_changed(old_blocks_movement, old_blocks_vision)
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Door opened")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Door opened")


class CloseDoorAction(BaseAction):
    """Closes an open door."""
    name: str = Field(default="Close Door")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not door or not isinstance(door, TestDoorA):
            return declaration_event.cancel(status_message="Door not found")
        if not door.is_open:
            return declaration_event.cancel(status_message="Door already closed")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, TestDoorA):
            return execution_event.cancel(status_message="Door not found")
        old_blocks_movement = door.blocks_movement
        old_blocks_vision = door.blocks_vision_field
        door.is_open = False
        door.blocks_movement = True
        door.blocks_vision_field = True
        door._notify_blocking_changed(old_blocks_movement, old_blocks_vision)
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Door closed")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Door closed")


class TestDoorA(UsableItem):
    """Door using get_use_actions override — item decides which action to surface."""
    name: str = Field(default="Door")
    is_pickable: bool = Field(default=False)
    map_char: str = Field(default="\u03c0")
    blocks_movement: bool = Field(default=True)
    blocks_vision_field: bool = Field(default=True)
    is_open: bool = Field(default=False)

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """State check HERE: return different action class based on door state."""
        if self.is_open:
            return [CloseDoorAction(
                source_entity_uuid=user_entity_uuid,
                source_item_uuid=self.uuid,
                template=True,
            )]
        return [OpenDoorAction(
            source_entity_uuid=user_entity_uuid,
            source_item_uuid=self.uuid,
            template=True,
        )]


# =============================================================================
# Door Approach B — Single toggle action, default use_action_templates
# =============================================================================

class InteractDoorAction(BaseAction):
    """Toggles door open/closed based on current state."""
    name: str = Field(default="Interact Door")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, TestDoorB):
            return declaration_event.cancel(status_message="Door not found")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, TestDoorB):
            return execution_event.cancel(status_message="Door not found")
        old_blocks_movement = door.blocks_movement
        old_blocks_vision = door.blocks_vision_field
        door.is_open = not door.is_open
        door.blocks_movement = not door.is_open
        door.blocks_vision_field = not door.is_open
        door._notify_blocking_changed(old_blocks_movement, old_blocks_vision)
        status = "opened" if door.is_open else "closed"
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message=f"Door {status}")
        return effect.phase_to(EventPhase.COMPLETION, status_message=f"Door {status}")


class TestDoorB(UsableItem):
    """Door using default use_action_templates — no override needed."""
    name: str = Field(default="Door")
    is_pickable: bool = Field(default=False)
    map_char: str = Field(default="\u03c0")
    blocks_movement: bool = Field(default=True)
    blocks_vision_field: bool = Field(default=True)
    is_open: bool = Field(default=False)
    # No get_use_actions override — uses default with use_action_templates.
    # Created with: TestDoorB(..., use_action_templates=[InteractDoorAction(..., template=True)])


# =============================================================================
# Lever — One-shot deactivation (default pattern + charges)
# =============================================================================

class PullLeverAction(BaseAction):
    """Pulls a lever to remove a spatial handler (deactivate a trap)."""
    name: str = Field(default="Pull Lever")
    description: str = Field(default="Deactivates a trap")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)
    trap_handler_uuid: Optional[UUID] = Field(default=None)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if not self.trap_handler_uuid:
            return declaration_event.cancel(status_message="No trap linked")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        if self.trap_handler_uuid:
            EventQueue.remove_spatial_handler(self.trap_handler_uuid)
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Trap deactivated")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Lever pulled")


class TrapLever(UsableItem):
    """A lever that deactivates a trap. Uses default use_action_templates with charges=1."""
    name: str = Field(default="Trap Lever")
    is_pickable: bool = Field(default=False)
    map_char: str = Field(default="\u03bb")


# =============================================================================
# Storage Chest — Inventory transfer (default pattern)
# =============================================================================

class LootAllAction(BaseAction):
    """Transfer all items from a container to the entity's inventory."""
    name: str = Field(default="Loot All")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No chest linked")
        chest = BaseBlock.get(self.source_item_uuid)
        if not isinstance(chest, StorageChest):
            return declaration_event.cancel(status_message="Chest not found")
        if not chest.chest_inventory.items:
            return declaration_event.cancel(status_message="Chest is empty")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No chest linked")
        chest = BaseBlock.get(self.source_item_uuid)
        if not isinstance(chest, StorageChest):
            return execution_event.cancel(status_message="Chest not found")
        looted = 0
        for item_uuid in list(chest.chest_inventory.items.keys()):
            item = chest.chest_inventory.remove_item(item_uuid)
            if item and entity.loot_item(item):
                looted += 1
        effect = execution_event.phase_to(
            EventPhase.EFFECT, status_message=f"Looted {looted} items")
        return effect.phase_to(
            EventPhase.COMPLETION, status_message=f"Looted {looted} items from chest")


class StorageChest(UsableItem):
    """A chest that can be looted. Optionally breakable."""
    name: str = Field(default="Chest")
    is_pickable: bool = Field(default=False)
    map_char: str = Field(default="\u03a9")
    is_targetable: bool = Field(default=False)
    chest_inventory: Inventory = Field(
        default_factory=lambda: Inventory(source_entity_uuid=uuid4(), name="Chest Storage"))

    def _on_destroy(self) -> None:
        """Spill all contents onto the ground at chest's position."""
        pos = self.position
        if pos is None:
            return
        grid = get_map()
        for item_uuid in list(self.chest_inventory.items.keys()):
            item = self.chest_inventory.remove_item(item_uuid)
            if item:
                item.owner_uuid = None
                item.stored_in_uuid = None
                tile = grid.get_tile(pos[0], pos[1])
                item.tile_uuid = tile.uuid if tile else None
                item.position = pos
                grid.place_object(item.uuid, pos)


# =============================================================================
# Campfire — Multi-action item (default pattern)
# =============================================================================

class RestAction(BaseAction):
    """Rest at a campfire to heal."""
    name: str = Field(default="Rest")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")
        heal_amount = random.randint(1, 6)
        entity.health.heal(heal_amount)
        effect = execution_event.phase_to(
            EventPhase.EFFECT, status_message=f"Healed {heal_amount}")
        return effect.phase_to(
            EventPhase.COMPLETION, status_message="Rested at campfire")


class CookAction(BaseAction):
    """Cook at a campfire for temporary HP."""
    name: str = Field(default="Cook")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")
        entity.health.add_temporary_hit_points(3, self.source_entity_uuid)
        effect = execution_event.phase_to(
            EventPhase.EFFECT, status_message="Gained 3 temp HP")
        return effect.phase_to(
            EventPhase.COMPLETION, status_message="Cooked at campfire")


# =============================================================================
# SpellScroll — Reuses actual SpellAction classes
# =============================================================================

class SpellScroll(UsableItem):
    """A scroll/wand containing spell(s). Configurable charges and consumability.

    For scrolls: charges=1, is_consumable=True (destroyed after use).
    For wands: charges=N, is_consumable=False (stays at 0 charges).
    For unlimited: charges=-1 (environment objects).

    Scrolls stack up to 20 by default (same spell + level = same stack_id).
    Wands don't stack (stack_id=None).
    """
    name: str = Field(default="Spell Scroll")
    is_pickable: bool = Field(default=True)
    map_char: str = Field(default="\u03c3")
    is_consumable: bool = Field(default=True)
    charges: int = Field(default=1)
    max_charges: int = Field(default=1)
    max_stack: int = Field(default=20)
    scroll_cast_level: int = Field(default=1)

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """Create spell variants at scroll's cast level with no spell slot cost."""
        if self.charges == 0 or not self.use_action_templates:
            return []
        result = []
        for template in self.use_action_templates:
            # Check if item has enough charges for this action's charge_cost
            template_charge_cost = template.charge_cost
            if self.charges != -1 and self.charges < template_charge_cost:
                continue

            if isinstance(template, SpellAction):
                # SpellAction — create variant with action-only cost, no spell slot
                cast_level = template.spell_level
                if cast_level == 0:
                    cast_level = 0  # Cantrip
                else:
                    cast_level = max(cast_level, self.scroll_cast_level)
                scroll_costs = [Cost(
                    name="Use Item", cost_type="actions", cost=1,
                    evaluator=entity_action_economy_cost_evaluator
                )]
                variant = template._create_variant(
                    cast_at_level=cast_level,
                    costs=scroll_costs,
                    source_item_uuid=self.uuid,
                    source_entity_uuid=user_entity_uuid,
                    template=True,
                    charge_cost=template_charge_cost,
                )
                result.append(variant)
            else:
                # Non-spell action — default copy pattern
                action = template.model_copy(deep=True, update={
                    'uuid': uuid4(),
                    'source_entity_uuid': user_entity_uuid,
                    'source_item_uuid': self.uuid,
                    'charge_cost': template_charge_cost,
                })
                result.append(action)
        return result


def create_scroll_of_fireball(owner_uuid: UUID, cast_level: int = 3) -> SpellScroll:
    spell = Fireball(source_entity_uuid=uuid4(), caster_level=5, template=True)
    return SpellScroll(source_entity_uuid=owner_uuid, name="Scroll of Fireball",
        scroll_cast_level=cast_level, use_action_templates=[spell],
        stack_id=f"scroll_fireball_l{cast_level}")


def create_scroll_of_magic_missile(owner_uuid: UUID, cast_level: int = 1) -> SpellScroll:
    spell = MagicMissile(source_entity_uuid=uuid4(), caster_level=1, template=True)
    return SpellScroll(source_entity_uuid=owner_uuid, name="Scroll of Magic Missile",
        scroll_cast_level=cast_level, use_action_templates=[spell],
        stack_id=f"scroll_magic_missile_l{cast_level}")


def create_scroll_of_hold_person(owner_uuid: UUID, cast_level: int = 2) -> SpellScroll:
    spell = HoldPerson(source_entity_uuid=uuid4(), caster_level=3, template=True)
    return SpellScroll(source_entity_uuid=owner_uuid, name="Scroll of Hold Person",
        scroll_cast_level=cast_level, use_action_templates=[spell],
        stack_id=f"scroll_hold_person_l{cast_level}")


def create_scroll_of_mage_armor(owner_uuid: UUID, cast_level: int = 1) -> SpellScroll:
    spell = MageArmor(source_entity_uuid=uuid4(), caster_level=1, template=True)
    return SpellScroll(source_entity_uuid=owner_uuid, name="Scroll of Mage Armor",
        scroll_cast_level=cast_level, use_action_templates=[spell],
        stack_id=f"scroll_mage_armor_l{cast_level}")


def create_scroll_of_spike_growth(owner_uuid: UUID, cast_level: int = 2) -> SpellScroll:
    spell = SpikeGrowth(source_entity_uuid=uuid4(), caster_level=3, template=True)
    return SpellScroll(source_entity_uuid=owner_uuid, name="Scroll of Spike Growth",
        scroll_cast_level=cast_level, use_action_templates=[spell],
        stack_id=f"scroll_spike_growth_l{cast_level}")


def create_scroll_of_fire_bolt(owner_uuid: UUID, caster_level: int = 5) -> SpellScroll:
    spell = FireBolt(source_entity_uuid=uuid4(), caster_level=caster_level, template=True)
    return SpellScroll(source_entity_uuid=owner_uuid, name="Scroll of Fire Bolt",
        scroll_cast_level=0, use_action_templates=[spell],
        stack_id=f"scroll_fire_bolt_cl{caster_level}")


def create_wand_of_magic_missiles(owner_uuid: UUID, charges: int = 3) -> SpellScroll:
    spell = MagicMissile(source_entity_uuid=uuid4(), caster_level=1, template=True)
    return SpellScroll(source_entity_uuid=owner_uuid, name="Wand of Magic Missiles",
        scroll_cast_level=1, charges=charges, max_charges=charges,
        is_consumable=False, is_pickable=True, use_action_templates=[spell])


def create_wand_of_fire(owner_uuid: UUID, charges: int = 7) -> SpellScroll:
    """Wand with Burning Hands (1 charge), Fireball (3 charges), Fireball L4 (4 charges)."""
    burning = BurningHands(source_entity_uuid=uuid4(), caster_level=1, template=True, charge_cost=1)
    fireball = Fireball(source_entity_uuid=uuid4(), caster_level=5, template=True, charge_cost=3)
    fireball_l4 = Fireball(source_entity_uuid=uuid4(), caster_level=7, template=True, charge_cost=4)
    return SpellScroll(
        source_entity_uuid=owner_uuid, name="Wand of Fire",
        scroll_cast_level=1, charges=charges, max_charges=charges,
        is_pickable=True, is_consumable=False,
        use_action_templates=[burning, fireball, fireball_l4],
    )


# =============================================================================
# Environment Spell Objects
# =============================================================================

def create_arcane_machine_gun(owner_uuid: UUID, position: Tuple[int, int] = (0, 0)) -> SpellScroll:
    """Environment object: unlimited Magic Missile (MULTI_ENTITY)."""
    spell = MagicMissile(source_entity_uuid=uuid4(), caster_level=1, template=True)
    item = SpellScroll(
        source_entity_uuid=owner_uuid, name="Arcane Machine Gun",
        scroll_cast_level=1, charges=-1,
        is_pickable=False, is_consumable=False,
        use_action_templates=[spell],
    )
    grid = get_map()
    grid.place_object(item.uuid, position)
    return item


def create_fireball_cannon(owner_uuid: UUID, position: Tuple[int, int] = (0, 0), charges: int = 3) -> SpellScroll:
    """Environment object: 3-shot Fireball cannon (POSITION_AOE)."""
    spell = Fireball(source_entity_uuid=uuid4(), caster_level=5, template=True)
    item = SpellScroll(
        source_entity_uuid=owner_uuid, name="Fireball Cannon",
        scroll_cast_level=3, charges=charges, max_charges=charges,
        is_pickable=False, is_consumable=False,
        use_action_templates=[spell],
    )
    grid = get_map()
    grid.place_object(item.uuid, position)
    return item


# =============================================================================
# HealingPotion — SELF consumable
# =============================================================================

class DrinkPotionAction(BaseAction):
    """Drink a potion to heal."""
    name: str = Field(default="Drink Potion")
    description: str = Field(default="Drinks a healing potion")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)
    heal_amount: int = Field(default=7)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")
        entity.health.heal(self.heal_amount)
        effect = execution_event.phase_to(EventPhase.EFFECT,
            status_message=f"Healed {self.heal_amount} HP")
        return effect.phase_to(EventPhase.COMPLETION,
            status_message=f"Drank healing potion")


class HealingPotion(UsableItem):
    """Potion of Healing. Single use, consumable. Stacks up to 10."""
    name: str = Field(default="Potion of Healing")
    is_pickable: bool = Field(default=True)
    map_char: str = Field(default="\u03b8")
    is_consumable: bool = Field(default=True)
    charges: int = Field(default=1)
    max_charges: int = Field(default=1)
    max_stack: int = Field(default=10)


def create_healing_potion(owner_uuid: UUID, heal_amount: int = 7) -> HealingPotion:
    action = DrinkPotionAction(
        source_entity_uuid=uuid4(), source_item_uuid=uuid4(),
        heal_amount=heal_amount, template=True,
    )
    return HealingPotion(source_entity_uuid=owner_uuid, use_action_templates=[action],
        stack_id=f"healing_potion_{heal_amount}")


# =============================================================================
# Weapon Coat of Flame — Adds 1d6 fire damage to a specific weapon
# Three variations: permanent, concentration, timed
# =============================================================================

class WeaponCoatCondition(BaseCondition):
    """Adds 1d6 elemental damage to a specific weapon's extra_damage lists.

    Applied on the ENTITY. Tracks which weapon it coated and the damage type,
    cleans up on removal. Supports any DamageType (fire, lightning, etc.).
    """
    name: str = "Weapon Coat"
    coated_weapon_uuid: Optional[UUID] = Field(default=None)
    coat_damage_type: DamageType = Field(default=DamageType.FIRE)

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="No target")
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")
        if not self.coated_weapon_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="No weapon specified")
        weapon = BaseBlock.get(self.coated_weapon_uuid)
        if not weapon or not isinstance(weapon, Weapon):
            return [], [], [], [], declaration_event.cancel(status_message="Weapon not found")

        # Add 1d6 elemental damage to weapon's extra damage lists
        bonus_mv = ModifiableValue.create(
            source_entity_uuid=self.target_entity_uuid,
            base_value=0, value_name=f"{self.name} Bonus"
        )
        weapon.extra_damage_dices.append(6)
        weapon.extra_damage_dices_numbers.append(1)
        weapon.extra_damage_bonus.append(bonus_mv)
        weapon.extra_damage_type.append(self.coat_damage_type)

        effect = declaration_event.phase_to(EventPhase.EFFECT,
            update={"condition": self}, status_message=f"Weapon coated with {self.coat_damage_type.value}")
        return [], [], [], [], effect

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up elemental dice from the coated weapon."""
        if self.coated_weapon_uuid:
            weapon = BaseBlock.get(self.coated_weapon_uuid)
            if weapon and isinstance(weapon, Weapon):
                for i in range(len(weapon.extra_damage_type) - 1, -1, -1):
                    if weapon.extra_damage_type[i] == self.coat_damage_type:
                        weapon.extra_damage_dices.pop(i)
                        weapon.extra_damage_dices_numbers.pop(i)
                        weapon.extra_damage_bonus.pop(i)
                        weapon.extra_damage_type.pop(i)
                        break
        return super()._remove(event)


# Backward-compatible alias
FlamingCoatCondition = WeaponCoatCondition


class ApplyCoatAction(BaseAction):
    """Apply weapon coat to a specific weapon slot. Pre-validates weapon exists."""
    name: str = Field(default="Coat Main Hand")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)
    weapon_slot: str = Field(default="MELEE_MAIN")
    coat_duration: Optional[int] = Field(default=None, description="Duration in rounds (None=permanent)")
    use_concentration: bool = Field(default=False)
    coat_damage_type: DamageType = Field(default=DamageType.FIRE)

    def pre_validate(self) -> bool:
        """Only show action if a weapon is equipped in the target slot."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False
        slot = WeaponSlot(self.weapon_slot)
        weapon = entity.equipment._get_weapon_by_slot(slot)
        return weapon is not None and isinstance(weapon, Weapon)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        slot = WeaponSlot(self.weapon_slot)
        weapon = entity.equipment._get_weapon_by_slot(slot)
        if not weapon or not isinstance(weapon, Weapon):
            return declaration_event.cancel(status_message="No weapon in slot")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")
        slot = WeaponSlot(self.weapon_slot)
        weapon = entity.equipment._get_weapon_by_slot(slot)
        if not weapon or not isinstance(weapon, Weapon):
            return execution_event.cancel(status_message="No weapon in slot")

        # Build duration
        if self.coat_duration is not None:
            duration = Duration(
                duration=self.coat_duration, duration_type=DurationType.ROUNDS,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.source_entity_uuid,
            )
        else:
            duration = Duration(
                duration_type=DurationType.PERMANENT,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.source_entity_uuid,
            )

        # Derive condition name from damage type (e.g., "Flaming Coat", "Lightning Coat")
        damage_name_map = {
            DamageType.FIRE: "Flaming Coat",
            DamageType.LIGHTNING: "Lightning Coat",
            DamageType.COLD: "Frost Coat",
            DamageType.ACID: "Acid Coat",
            DamageType.POISON: "Poison Coat",
        }
        coat_name = damage_name_map.get(self.coat_damage_type, f"{self.coat_damage_type.value.title()} Coat")

        coat = WeaponCoatCondition(
            name=coat_name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            coated_weapon_uuid=weapon.uuid,
            coat_damage_type=self.coat_damage_type,
            duration=duration,
        )
        entity.add_condition(coat)

        # If concentration variant, apply Concentrating and link
        if self.use_concentration:
            concentration = Concentrating(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.source_entity_uuid,
                spell_name=f"{coat_name} Weapon",
            )
            entity.add_condition(concentration)
            concentration.add_linked_condition(entity.uuid, coat.uuid)

        effect = execution_event.phase_to(EventPhase.EFFECT, status_message=f"Applied {coat_name.lower()}")
        return effect.phase_to(EventPhase.COMPLETION, status_message=f"Weapon coated with {self.coat_damage_type.value}")


class WeaponCoat(UsableItem):
    """Weapon Coat. Single use, consumable. Stacks up to 10 by damage type."""
    name: str = Field(default="Weapon Coat of Flame")
    is_pickable: bool = Field(default=True)
    is_consumable: bool = Field(default=True)
    charges: int = Field(default=1)
    max_charges: int = Field(default=1)
    max_stack: int = Field(default=10)


def create_weapon_coat(owner_uuid: UUID) -> WeaponCoat:
    """Fire weapon coat. Permanent coating (no duration). Consumable, destroyed on use."""
    coat_main = ApplyCoatAction(
        source_entity_uuid=uuid4(), source_item_uuid=uuid4(),
        name="Coat Main Hand", weapon_slot="MELEE_MAIN",
        coat_damage_type=DamageType.FIRE, template=True,
    )
    coat_off = ApplyCoatAction(
        source_entity_uuid=uuid4(), source_item_uuid=uuid4(),
        name="Coat Off Hand", weapon_slot="MELEE_OFF",
        coat_damage_type=DamageType.FIRE, template=True,
    )
    return WeaponCoat(source_entity_uuid=owner_uuid, name="Weapon Coat of Flame",
        use_action_templates=[coat_main, coat_off],
        stack_id="weapon_coat_fire")


def create_lightning_weapon_coat(owner_uuid: UUID) -> WeaponCoat:
    """Lightning weapon coat. Permanent coating. Consumable, destroyed on use."""
    coat_main = ApplyCoatAction(
        source_entity_uuid=uuid4(), source_item_uuid=uuid4(),
        name="Coat Main Hand", weapon_slot="MELEE_MAIN",
        coat_damage_type=DamageType.LIGHTNING, template=True,
    )
    coat_off = ApplyCoatAction(
        source_entity_uuid=uuid4(), source_item_uuid=uuid4(),
        name="Coat Off Hand", weapon_slot="MELEE_OFF",
        coat_damage_type=DamageType.LIGHTNING, template=True,
    )
    return WeaponCoat(source_entity_uuid=owner_uuid, name="Weapon Coat of Lightning",
        use_action_templates=[coat_main, coat_off],
        stack_id="weapon_coat_lightning")


def create_flaming_weapon_spell_coat(owner_uuid: UUID) -> WeaponCoat:
    """Variation A: Concentration-based coating. Consumable, lasts until concentration breaks."""
    coat_main = ApplyCoatAction(
        source_entity_uuid=uuid4(), source_item_uuid=uuid4(),
        name="Coat Main Hand", weapon_slot="MELEE_MAIN",
        use_concentration=True, template=True,
    )
    return WeaponCoat(source_entity_uuid=owner_uuid, use_action_templates=[coat_main])


def create_timed_weapon_coat(owner_uuid: UUID, rounds: int = 3) -> WeaponCoat:
    """Variation C: Timed coating (N rounds). Consumable, expires after duration."""
    coat_main = ApplyCoatAction(
        source_entity_uuid=uuid4(), source_item_uuid=uuid4(),
        name="Coat Main Hand", weapon_slot="MELEE_MAIN",
        coat_duration=rounds, template=True,
    )
    return WeaponCoat(source_entity_uuid=owner_uuid, use_action_templates=[coat_main])


# =============================================================================
# Arcane Device — Environment object with skill prerequisite
# =============================================================================

class ActivateDeviceAction(BaseAction):
    """Activate an arcane device. Requires Arcana proficiency (static pre_validate check)."""
    name: str = Field(default="Activate Device")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)
    heal_amount: int = Field(default=5)

    def pre_validate(self) -> bool:
        """Static prerequisite: entity must have proficiency in arcana."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False
        skill = entity.skill_set.get_skill(type_cast(SkillName, "arcana"))
        return skill.proficiency

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Device activated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")
        entity.health.heal(self.heal_amount)
        effect = execution_event.phase_to(EventPhase.EFFECT,
            status_message=f"Healed {self.heal_amount} HP")
        return effect.phase_to(EventPhase.COMPLETION,
            status_message="Arcane device activated")


class ArcaneDevice(UsableItem):
    """Environment object requiring Arcana proficiency to use."""
    name: str = Field(default="Arcane Device")
    is_pickable: bool = Field(default=False)


def create_arcane_device(owner_uuid: UUID, position: Tuple[int, int] = (0, 0)) -> ArcaneDevice:
    action = ActivateDeviceAction(
        source_entity_uuid=uuid4(), source_item_uuid=uuid4(), template=True,
    )
    device = ArcaneDevice(
        source_entity_uuid=owner_uuid,
        use_action_templates=[action],
    )
    grid = get_map()
    grid.place_object(device.uuid, position)
    return device


# =============================================================================
# Potion of Greater Invisibility — Applies BG3-style Greater Invisibility
# =============================================================================

class DrinkGreaterInvisibilityPotionAction(BaseAction):
    """Drink a potion to become invisible (BG3-style Greater Invisibility)."""
    name: str = Field(default="Drink Greater Invisibility Potion")
    description: str = Field(default="Drink to become invisible (Stealth check to maintain on attack/cast)")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity or not isinstance(entity, Entity):
            return execution_event.cancel(status_message="Entity not found")

        # Apply Greater Invisibility effect (no concentration — it's a potion)
        invis_effect = GreaterInvisibilityEffect(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        )
        entity.add_condition(invis_effect, parent_event=execution_event)

        effect = execution_event.phase_to(EventPhase.EFFECT,
            status_message=f"{entity.name} becomes invisible")
        return effect.phase_to(EventPhase.COMPLETION,
            status_message=f"Drank Potion of Greater Invisibility")


class PotionOfGreaterInvisibility(UsableItem):
    """Potion of Greater Invisibility. Single use, consumable."""
    name: str = Field(default="Potion of Greater Invisibility")
    is_pickable: bool = Field(default=True)
    map_char: str = Field(default="\u03b8")
    is_consumable: bool = Field(default=True)
    charges: int = Field(default=1)
    max_charges: int = Field(default=1)
    max_stack: int = Field(default=5)


def create_potion_of_greater_invisibility(owner_uuid: UUID) -> PotionOfGreaterInvisibility:
    action = DrinkGreaterInvisibilityPotionAction(
        source_entity_uuid=uuid4(), source_item_uuid=uuid4(), template=True,
    )
    return PotionOfGreaterInvisibility(
        source_entity_uuid=owner_uuid,
        use_action_templates=[action],
        stack_id="potion_of_greater_invisibility"
    )


# =============================================================================
# Torch — Light Source Item
# =============================================================================

class IgniteTorchAction(BaseAction):
    """Ignite a torch — creates a light source that follows the carrier."""
    name: str = Field(default="Ignite Torch")
    description: str = Field(default="Light the torch")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No torch linked")
        torch = BaseBlock.get(self.source_item_uuid)
        if not torch or not isinstance(torch, Torch):
            return declaration_event.cancel(status_message="Torch not found")
        if torch.is_lit:
            return declaration_event.cancel(status_message="Torch already lit")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No torch linked")
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, Torch):
            return execution_event.cancel(status_message="Torch not found")

        torch.ignite(self.source_entity_uuid)

        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Torch ignited")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Torch ignited")


class ExtinguishTorchAction(BaseAction):
    """Extinguish a lit torch — removes the light source."""
    name: str = Field(default="Extinguish Torch")
    description: str = Field(default="Put out the torch")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No torch linked")
        torch = BaseBlock.get(self.source_item_uuid)
        if not torch or not isinstance(torch, Torch):
            return declaration_event.cancel(status_message="Torch not found")
        if not torch.is_lit:
            return declaration_event.cancel(status_message="Torch not lit")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No torch linked")
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, Torch):
            return execution_event.cancel(status_message="Torch not found")

        torch.extinguish()

        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Torch extinguished")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Torch extinguished")


class Torch(UsableItem):
    """A torch that provides light when ignited.

    Bright light in 20ft radius, dim light in additional 20ft.
    When ignited, creates a light source anchored to the carrying entity.
    Light follows the entity as they move.
    """
    name: str = Field(default="Torch")
    description: str = Field(default="A torch that provides bright light in 20ft and dim light in 20ft")
    is_equippable: bool = Field(default=False)
    is_pickable: bool = Field(default=True)
    map_char: str = Field(default="\u2666")

    bright_radius_feet: int = Field(default=20)
    dim_radius_feet: int = Field(default=20)
    is_lit: bool = Field(default=False)
    _light_source_uuid: Optional[UUID] = None

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        if not self.is_lit:
            return [IgniteTorchAction(
                source_entity_uuid=user_entity_uuid,
                source_item_uuid=self.uuid,
            )]
        else:
            return [ExtinguishTorchAction(
                source_entity_uuid=user_entity_uuid,
                source_item_uuid=self.uuid,
            )]

    def ignite(self, carrier_entity_uuid: UUID) -> None:
        """Light the torch — creates a light source on the GridMap."""
        if self.is_lit:
            return
        self.is_lit = True
        grid = get_map()
        entity = Entity.get(carrier_entity_uuid)
        if entity:
            self._light_source_uuid = grid.add_light_source(
                position=entity.position,
                bright_radius_feet=self.bright_radius_feet,
                dim_radius_feet=self.dim_radius_feet,
                anchor_uuid=carrier_entity_uuid
            )

    def extinguish(self) -> None:
        """Put out the torch — removes the light source."""
        if not self.is_lit:
            return
        self.is_lit = False
        if self._light_source_uuid:
            grid = get_map()
            grid.remove_light_source(self._light_source_uuid)
            self._light_source_uuid = None

    def _on_destroy(self) -> None:
        """Extinguish before destruction."""
        self.extinguish()

    def _on_drop(self, entity_uuid: UUID, position: Tuple[int, int]) -> None:
        """Auto-extinguish when dropped."""
        self.extinguish()
        super()._on_drop(entity_uuid, position)


def create_torch(owner_uuid: UUID) -> Torch:
    """Create a torch item."""
    return Torch(source_entity_uuid=owner_uuid)


# =============================================================================
# Wall Torch — Fixed wall-mounted light source with on/off actions
# =============================================================================

class IgniteWallTorchAction(BaseAction):
    """Light a wall torch."""
    name: str = Field(default="Light Wall Torch")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No wall torch linked")
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, WallTorch) or torch.is_lit:
            return declaration_event.cancel(status_message="Cannot light")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No wall torch linked")
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, WallTorch):
            return execution_event.cancel(status_message="Wall torch not found")
        torch.light()
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Wall torch lit")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Wall torch lit")


class ExtinguishWallTorchAction(BaseAction):
    """Put out a wall torch."""
    name: str = Field(default="Extinguish Wall Torch")
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[Cost] = Field(default_factory=list)
    source_item_uuid: Optional[UUID] = Field(default=None)

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No wall torch linked")
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, WallTorch) or not torch.is_lit:
            return declaration_event.cancel(status_message="Cannot extinguish")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return execution_event.cancel(status_message="No wall torch linked")
        torch = BaseBlock.get(self.source_item_uuid)
        if not isinstance(torch, WallTorch):
            return execution_event.cancel(status_message="Wall torch not found")
        torch.put_out()
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Wall torch extinguished")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Wall torch extinguished")


class WallTorch(UsableItem):
    """A fixed wall-mounted torch. Cannot be picked up or moved."""
    name: str = Field(default="Wall Torch")
    is_pickable: bool = Field(default=False)
    is_equippable: bool = Field(default=False)
    map_char: str = Field(default="\u2666")

    bright_radius_feet: int = Field(default=10)
    dim_radius_feet: int = Field(default=10)
    is_lit: bool = Field(default=False)
    _light_source_uuid: Optional[UUID] = None
    _wall_torch_position: Optional[Tuple[int, int]] = None

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        if not self.is_lit:
            return [IgniteWallTorchAction(
                source_entity_uuid=user_entity_uuid,
                source_item_uuid=self.uuid,
            )]
        else:
            return [ExtinguishWallTorchAction(
                source_entity_uuid=user_entity_uuid,
                source_item_uuid=self.uuid,
            )]

    def light(self) -> None:
        """Light the wall torch — creates a fixed light source."""
        if self.is_lit:
            return
        self.is_lit = True
        if self._wall_torch_position is not None:
            grid = get_map()
            self._light_source_uuid = grid.add_light_source(
                position=self._wall_torch_position,
                bright_radius_feet=self.bright_radius_feet,
                dim_radius_feet=self.dim_radius_feet,
            )

    def put_out(self) -> None:
        """Extinguish the wall torch — removes the light source."""
        if not self.is_lit:
            return
        self.is_lit = False
        if self._light_source_uuid:
            grid = get_map()
            grid.remove_light_source(self._light_source_uuid)
            self._light_source_uuid = None


def create_wall_torch(position: Tuple[int, int], owner_uuid: UUID, lit: bool = True) -> WallTorch:
    """Create a wall torch at a fixed position and optionally light it."""
    torch = WallTorch(source_entity_uuid=owner_uuid)
    torch._wall_torch_position = position
    grid = get_map()
    grid.place_object(torch.uuid, position)
    if lit:
        torch.light()
    return torch
