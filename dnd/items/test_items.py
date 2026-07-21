"""Example UsableItems for testing the UsableItem system.

Contains: Door (two approaches), Lever, StorageChest, Campfire actions,
SpellScroll, HealingPotion, WeaponCoat, WandOfFire, ArcaneDevice, environment spell objects.
These are pattern examples, not final game items.
"""

import random
from typing import Any, Optional, List, Tuple, cast as type_cast
from uuid import UUID, uuid4
from pydantic import Field

from dnd.core.base_actions import (
    ActionSelfSetupProfile,
    ActionSetupDuration,
    ActionSetupMaintenanceFailure,
    ActionSetupMaintenanceProfile,
    ActionSetupMaintenanceTrigger,
    ActionPresentationKind,
    BaseAction,
    ActionEvent,
    TargetType,
    Cost,
)
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration, DurationType
from dnd.core.events import Event, EventPhase, EventQueue, ExposedFlameEvent, WeaponSlot, SkillName, RangeType, Range, Damage
from dnd.core.modifiers import DamageType
from dnd.core.values import ModifiableValue
from dnd.core.gridmap import get_map
from dnd.core.aoe import AoEShape, Cube
from dnd.core.dice import AttackOutcome
from dnd.blocks.base_item import UsableItem
from dnd.blocks.equipment import Weapon
from dnd.blocks.inventory import Inventory
from dnd.entity import Entity
from dnd.actions import (
    SpellAction,
    SpellEvent,
    entity_action_economy_cost_applier,
    entity_action_economy_cost_evaluator,
)
from dnd.conditions import Concentrating, GreaterInvisibilityEffect
from dnd.spells.evocation import BurningHands, FireBolt, Fireball, MagicMissile
from dnd.spells.enchantment import HoldPerson
from dnd.spells.abjuration import MageArmor
from dnd.spells.illusion import Invisibility
from dnd.spells.transmutation import SpikeGrowth, HasteEffect


class OpenDoorAction(BaseAction):
    """Opens a closed door."""

    name: str = Field(default="Open Door", description="Action name for opening a door.")
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Door actions target the source user and resolve through source_item_uuid.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for opening a door.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the door item this action opens.",
    )

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
        door._notify_blocking_changed(old_blocks_movement, old_blocks_vision, parent_event=execution_event.uuid)
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Door opened")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Door opened")


class CloseDoorAction(BaseAction):
    """Closes an open door."""

    name: str = Field(default="Close Door", description="Action name for closing a door.")
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Door actions target the source user and resolve through source_item_uuid.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for closing a door.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the door item this action closes.",
    )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not door or not isinstance(door, TestDoorA):
            return declaration_event.cancel(status_message="Door not found")
        if not door.is_open:
            return declaration_event.cancel(status_message="Door already closed")
        grid = get_map()
        door_pos = grid.get_object_position(door.uuid)
        if door_pos and grid.get_entities_at(door_pos):
            return declaration_event.cancel(status_message="Can't close door — someone is standing in the doorway")
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
        door._notify_blocking_changed(old_blocks_movement, old_blocks_vision, parent_event=execution_event.uuid)
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Door closed")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Door closed")


class TestDoorA(UsableItem):
    """Door using get_use_actions override — item decides which action to surface."""

    name: str = Field(default="Door", description="Display name for the test door.")
    is_pickable: bool = Field(default=False, description="Doors are fixed environment objects.")
    map_char: str = Field(default="\u03c0", description="Map glyph for the test door.")
    blocks_movement: bool = Field(default=True, description="Closed doors block movement.")
    blocks_vision_field: bool = Field(default=True, description="Closed doors block line of sight.")
    is_open: bool = Field(default=False, description="Whether the door is currently open.")

    def get_spatial_open_state(self) -> Optional[bool]:
        """Return the door-open state used by spatial event metadata."""
        return self.is_open

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """Return open or close actions according to the door state."""
        if self.is_open:
            grid = get_map()
            door_pos = grid.get_object_position(self.uuid)
            if door_pos and grid.get_entities_at(door_pos):
                return []
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


class InteractDoorAction(BaseAction):
    """Toggle a door open or closed through the default item-action pattern."""

    name: str = Field(default="Interact Door", description="Action name for toggling a door.")
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Door toggles target the source user and resolve through source_item_uuid.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for toggling a door.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the door item this action toggles.",
    )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if self.source_item_uuid is None:
            return declaration_event.cancel(status_message="No door linked")
        door = BaseBlock.get(self.source_item_uuid)
        if not isinstance(door, TestDoorB):
            return declaration_event.cancel(status_message="Door not found")
        if door.is_open:
            grid = get_map()
            door_pos = grid.get_object_position(door.uuid)
            if door_pos and grid.get_entities_at(door_pos):
                return declaration_event.cancel(status_message="Can't close door — someone is standing in the doorway")
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
        door._notify_blocking_changed(old_blocks_movement, old_blocks_vision, parent_event=execution_event.uuid)
        status = "opened" if door.is_open else "closed"
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message=f"Door {status}")
        return effect.phase_to(EventPhase.COMPLETION, status_message=f"Door {status}")


class TestDoorB(UsableItem):
    """Door fixture that uses inherited `use_action_templates` discovery."""

    name: str = Field(default="Door", description="Display name for the templated door.")
    is_pickable: bool = Field(default=False, description="Templated doors are fixed environment objects.")
    map_char: str = Field(default="\u03c0", description="Map glyph for the templated door.")
    blocks_movement: bool = Field(default=True, description="Closed templated doors block movement.")
    blocks_vision_field: bool = Field(default=True, description="Closed templated doors block line of sight.")
    is_open: bool = Field(default=False, description="Whether the templated door is currently open.")

    def get_spatial_open_state(self) -> Optional[bool]:
        """Return the door-open state used by spatial event metadata."""
        return self.is_open


class PullLeverAction(BaseAction):
    """Deactivate a linked trap and remove trap marker conditions from tiles."""

    name: str = Field(default="Pull Lever", description="Action name for pulling a trap lever.")
    description: str = Field(default="Deactivates a trap", description="Action description shown for trap levers.")
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Trap levers target the source user and resolve through source_item_uuid.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for pulling a trap lever.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the lever item this action pulls.",
    )
    trap_handler_uuid: Optional[UUID] = Field(
        default=None,
        description="Spatial handler UUID removed when this lever is pulled.",
    )
    trap_tile_uuids: List[UUID] = Field(
        default_factory=list,
        description="Tile UUIDs that should lose Spike Trap markers when deactivated.",
    )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        if not self.trap_handler_uuid:
            return declaration_event.cancel(status_message="No trap linked")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        if self.trap_handler_uuid:
            EventQueue.remove_spatial_handler(self.trap_handler_uuid)
        for tile_uuid in self.trap_tile_uuids:
            tile = BaseBlock.get(tile_uuid)
            if tile is not None and "Spike Trap" in tile.active_conditions:
                tile.remove_condition("Spike Trap", parent_event=execution_event)
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Trap deactivated")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Lever pulled")


class TrapLever(UsableItem):
    """Fixed lever fixture that usually has one charge and one use template."""

    name: str = Field(default="Trap Lever", description="Display name for the trap lever.")
    is_pickable: bool = Field(default=False, description="Trap levers are fixed environment objects.")
    map_char: str = Field(default="\u03bb", description="Map glyph for the trap lever.")


class LootAllAction(BaseAction):
    """Transfer all items from a container to the entity's inventory."""

    name: str = Field(default="Loot All", description="Action name for looting a chest.")
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Chest looting targets the source user and resolves through source_item_uuid.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for looting a chest.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the chest item this action loots.",
    )

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

    name: str = Field(default="Chest", description="Display name for the storage chest.")
    is_pickable: bool = Field(default=False, description="Chests are fixed environment objects by default.")
    map_char: str = Field(default="\u03a9", description="Map glyph for the storage chest.")
    is_targetable: bool = Field(default=False, description="Whether attacks can target this chest.")
    chest_inventory: Inventory = Field(
        default_factory=lambda: Inventory(source_entity_uuid=uuid4(), name="Chest Storage"),
        description="Inventory block containing nested chest contents.",
    )

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


class RestAction(BaseAction):
    """Rest at a campfire to heal."""

    name: str = Field(default="Rest", description="Action name for taking a campfire rest.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Campfire rest targets the acting entity.")
    costs: List[Cost] = Field(default_factory=list, description="No-cost action-economy payload for campfire rest.")
    source_item_uuid: Optional[UUID] = Field(default=None, description="UUID of the campfire item used for rest.")

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
        entity.receive_healing(
            heal_amount, entity.uuid,
            source_description="Campfire Rest",
            parent_event=execution_event.uuid
        )
        effect = execution_event.phase_to(
            EventPhase.EFFECT, status_message=f"Healed {heal_amount}")
        return effect.phase_to(
            EventPhase.COMPLETION, status_message="Rested at campfire")


class CookAction(BaseAction):
    """Cook at a campfire for temporary HP."""

    name: str = Field(default="Cook", description="Action name for cooking at a campfire.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Campfire cooking targets the acting entity.")
    costs: List[Cost] = Field(default_factory=list, description="No-cost action-economy payload for campfire cooking.")
    source_item_uuid: Optional[UUID] = Field(default=None, description="UUID of the campfire item used for cooking.")

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


class SpellScroll(UsableItem):
    """Reusable fixture for scrolls, wands, and spell-casting objects.

    Scroll-style items are usually consumable single-charge stacks. Wand-style
    items use finite charges without being consumed, while environment spell
    objects use unlimited charges.
    """

    name: str = Field(default="Spell Scroll", description="Display name for the scroll or wand.")
    is_pickable: bool = Field(default=True, description="Whether the spell item can be picked up.")
    map_char: str = Field(default="\u03c3", description="Map glyph for spell-scroll fixtures.")
    is_consumable: bool = Field(default=True, description="Whether the item is destroyed after its last charge is used.")
    charges: int = Field(default=1, description="Current item charges; -1 means unlimited uses.")
    max_charges: int = Field(default=1, description="Maximum finite charges the item can hold.")
    max_stack: int = Field(default=20, description="Maximum count for stackable scroll fixtures.")
    scroll_cast_level: int = Field(default=1, description="Minimum spell slot level used when creating scroll spell variants.")

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """Create spell variants at scroll's cast level with no spell slot cost."""
        if self.charges == 0 or not self.use_action_templates:
            return []
        result = []
        for template in self.use_action_templates:
            template_charge_cost = template.charge_cost
            if self.charges != -1 and self.charges < template_charge_cost:
                continue

            if isinstance(template, SpellAction):
                cast_level = template.spell_level
                if cast_level == 0:
                    cast_level = 0
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


class AcidFlaskSpell(SpellAction):
    """Item-backed thrown acid effect modeled through the spell action pipeline."""

    name: str = Field(default="Acid Flask", description="Action name for throwing an acid flask.")
    description: str = Field(
        default="Throw a flask of acid (2x2 area, 2d4 acid, DEX DC 11 half)",
        description="Action description shown for acid flask use.",
    )
    spell_level: int = Field(default=0, description="Acid flask is item-backed and does not consume spell slots.")
    spell_school: str = Field(default="evocation", description="School label used by the spell action model.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Acid flask targets a visible area.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=40),
        description="Throw range for the acid flask.",
    )
    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape generated for flask splash damage.")
    include_self: bool = Field(default=False, description="Whether the caster can be included in the splash.")
    valid_target_filter: str = Field(default="all", description="Target filter used by area target collection.")
    _fixed_dc: int = 11

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cube(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (0, 0),
                size_feet=10,
                centered=True
            )

    def get_range(self) -> Range:
        return self.spell_range

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(
                status_message=f"Target position {target_pos} not in line of sight"
            )

        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
            )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = self._fixed_dc

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, "dexterity").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"DEX save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        no_bonus = ModifiableValue.create(
            source_entity_uuid=caster.uuid, base_value=0, value_name="Acid Flask Damage"
        )
        acid_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=4,
            dice_numbers=2,
            damage_bonus=no_bonus,
            damage_type=DamageType.ACID
        )

        damage_dice = acid_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        final_damage = damage_roll.total // 2 if success else damage_roll.total

        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.ACID,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid
            )

        save_text = " (saved for half)" if success else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[acid_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Acid Flask deals {final_damage} acid damage to {target.name}{save_text}"
        )


def create_acid_flask(owner_uuid: UUID) -> SpellScroll:
    """Create a throwable Acid Flask (consumable, 2d4 acid AoE, DEX DC 11)."""
    spell = AcidFlaskSpell(source_entity_uuid=uuid4(), caster_level=1, template=True)
    return SpellScroll(
        source_entity_uuid=owner_uuid,
        name="Acid Flask",
        scroll_cast_level=0,
        use_action_templates=[spell],
        stack_id="acid_flask",
        map_char="!",
    )


def create_scroll_of_invisibility(owner_uuid: UUID, cast_level: int = 2) -> SpellScroll:
    """Create a Scroll of Invisibility (consumable, no spell slot cost)."""
    spell = Invisibility(source_entity_uuid=uuid4(), caster_level=3, template=True)
    return SpellScroll(
        source_entity_uuid=owner_uuid,
        name="Scroll of Invisibility",
        scroll_cast_level=cast_level,
        use_action_templates=[spell],
        stack_id=f"scroll_invisibility_l{cast_level}",
    )


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


class PotionDrinkAction(BaseAction):
    """Shared videogame rule for drinking a potion as a bonus action."""

    costs: List[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Drink Potion Cost",
                cost_type="bonus_actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ],
        description="One bonus action consumed by every potion-drinking action.",
    )
    presentation_kind: ActionPresentationKind = Field(
        default=ActionPresentationKind.DRINK,
        description="Tells presentation clients to render a potion-drinking action.",
    )

    def _apply_costs(self, completion_event: ActionEvent) -> Optional[ActionEvent]:
        """Consume the potion's bonus-action cost after successful resolution."""
        return entity_action_economy_cost_applier(
            completion_event,
            self.source_entity_uuid,
        )


class DrinkPotionAction(PotionDrinkAction):
    """Drink a potion to heal."""

    name: str = Field(default="Drink Potion", description="Action name for drinking this potion.")
    description: str = Field(
        default="Drinks a healing potion",
        description="Action description shown for potion use.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Healing potions target the user.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the potion item this action consumes.",
    )
    heal_amount: int = Field(default=7, description="Hit points restored by this potion action.")

    def get_fixed_healing(self, actor: Any) -> Optional[int]:
        """Return the potion's deterministic restoration amount."""
        return self.heal_amount

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")
        entity.receive_healing(
            self.heal_amount, entity.uuid,
            source_description="Potion of Healing",
            parent_event=execution_event.uuid
        )
        effect = execution_event.phase_to(EventPhase.EFFECT,
            status_message=f"Healed {self.heal_amount} HP")
        return effect.phase_to(EventPhase.COMPLETION,
            status_message=f"Drank healing potion")


class HealingPotion(UsableItem):
    """Potion of Healing. Single use, consumable. Stacks up to 10."""

    name: str = Field(default="Potion of Healing", description="Display name for the healing potion.")
    is_pickable: bool = Field(default=True, description="Healing potions can be picked up.")
    map_char: str = Field(default="\u03b8", description="Map glyph for the healing potion.")
    is_consumable: bool = Field(default=True, description="Healing potions are destroyed when their final charge is used.")
    charges: int = Field(default=1, description="Current charges for the top potion in the stack.")
    max_charges: int = Field(default=1, description="Maximum charges for each potion in the stack.")
    max_stack: int = Field(default=10, description="Maximum number of healing potions in one stack.")


def create_healing_potion(owner_uuid: UUID, heal_amount: int = 7) -> HealingPotion:
    """Create a stackable healing potion with one drink action."""
    action = DrinkPotionAction(
        source_entity_uuid=uuid4(), source_item_uuid=uuid4(),
        heal_amount=heal_amount, template=True,
    )
    return HealingPotion(source_entity_uuid=owner_uuid, use_action_templates=[action],
        stack_id=f"healing_potion_{heal_amount}")


class WeaponCoatCondition(BaseCondition):
    """Add 1d6 elemental damage to one equipped weapon.

    The condition lives on the entity, records the coated weapon UUID, and
    removes the matching extra damage packet when the condition is removed.
    """

    name: str = Field(default="Weapon Coat", description="Condition name for the active weapon coat.")
    coated_weapon_uuid: Optional[UUID] = Field(
        default=None,
        description="Weapon UUID that received the extra damage packet.",
    )
    coat_damage_type: DamageType = Field(
        default=DamageType.FIRE,
        description="Damage type added by the coat.",
    )

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

FlamingCoatCondition = WeaponCoatCondition


class ApplyCoatAction(BaseAction):
    """Apply weapon coat to a specific weapon slot. Pre-validates weapon exists."""

    name: str = Field(default="Coat Main Hand", description="Action name for applying a weapon coat.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Weapon coats target the acting entity.")
    costs: List[Cost] = Field(default_factory=list, description="No-cost action-economy payload for coat application.")
    source_item_uuid: Optional[UUID] = Field(default=None, description="UUID of the coat item being consumed.")
    weapon_slot: str = Field(default="MELEE_MAIN", description="Equipment weapon slot to coat.")
    coat_duration: Optional[int] = Field(default=None, description="Duration in rounds; `None` creates a permanent coat.")
    use_concentration: bool = Field(default=False, description="Whether applying the coat also creates concentration.")
    coat_damage_type: DamageType = Field(default=DamageType.FIRE, description="Damage type added to the coated weapon.")

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

    name: str = Field(default="Weapon Coat of Flame", description="Display name for the weapon coat item.")
    is_pickable: bool = Field(default=True, description="Weapon coats can be picked up.")
    is_consumable: bool = Field(default=True, description="Weapon coats are consumed when applied.")
    charges: int = Field(default=1, description="Current charges for the top coat in the stack.")
    max_charges: int = Field(default=1, description="Maximum charges for each coat item.")
    max_stack: int = Field(default=10, description="Maximum number of coats in one stack.")


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


class ActivateDeviceAction(BaseAction):
    """Activate an arcane device. Requires Arcana proficiency (static pre_validate check)."""

    name: str = Field(default="Activate Device", description="Action name for using an arcane device.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Arcane devices target the acting entity.")
    costs: List[Cost] = Field(default_factory=list, description="No-cost action-economy payload for device activation.")
    source_item_uuid: Optional[UUID] = Field(default=None, description="UUID of the arcane device item being used.")
    heal_amount: int = Field(default=5, description="Hit points restored by the arcane device.")

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
        entity.receive_healing(
            self.heal_amount, entity.uuid,
            source_description="Arcane Device",
            parent_event=execution_event.uuid
        )
        effect = execution_event.phase_to(EventPhase.EFFECT,
            status_message=f"Healed {self.heal_amount} HP")
        return effect.phase_to(EventPhase.COMPLETION,
            status_message="Arcane device activated")


class ArcaneDevice(UsableItem):
    """Environment object requiring Arcana proficiency to use."""

    name: str = Field(default="Arcane Device", description="Display name for the arcane device.")
    is_pickable: bool = Field(default=False, description="Arcane devices are fixed environment objects.")


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


class DrinkGreaterInvisibilityPotionAction(PotionDrinkAction):
    """Drink a potion to become invisible (BG3-style Greater Invisibility)."""

    name: str = Field(default="Drink Greater Invisibility Potion", description="Action name for drinking this potion.")
    description: str = Field(
        default="Drink to become invisible (Stealth check to maintain on attack/cast)",
        description="Action description shown for greater invisibility potions.",
    )
    target_type: TargetType = Field(default=TargetType.SELF, description="Greater invisibility potions target the user.")
    source_item_uuid: Optional[UUID] = Field(default=None, description="UUID of the potion item being consumed.")

    def get_self_setup_profile(self, actor: Any) -> ActionSelfSetupProfile:
        """Return the typed combat consequences of greater invisibility."""
        stealth_bonus = actor.skill_bonus(target_entity_uuid=None, skill_name="stealth")
        return ActionSelfSetupProfile(
            semantic_id="setup.greater_invisibility",
            duration=ActionSetupDuration.UNTIL_REMOVED,
            condition_fact_ids=("actor.condition.invisible",),
            active_condition_semantic_keys=frozenset({
                "dnd.conditions.GreaterInvisibilityEffect",
            }),
            grants_outgoing_attack_advantage=True,
            grants_incoming_attack_disadvantage=True,
            grants_invisibility=True,
            maintenance=ActionSetupMaintenanceProfile(
                trigger=ActionSetupMaintenanceTrigger.REVEALING_ACTION,
                skill_name="stealth",
                initial_dc=15,
                dc_increment_per_success=1,
                check_bonus=stealth_bonus.normalized_score,
                check_advantage=stealth_bonus.advantage,
                failure=ActionSetupMaintenanceFailure.REMOVE_SETUP,
            ),
        )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity or not isinstance(entity, Entity):
            return execution_event.cancel(status_message="Entity not found")

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

    name: str = Field(default="Potion of Greater Invisibility", description="Display name for the potion.")
    is_pickable: bool = Field(default=True, description="Greater invisibility potions can be picked up.")
    map_char: str = Field(default="\u03b8", description="Map glyph for the potion.")
    is_consumable: bool = Field(default=True, description="The potion is consumed when used.")
    charges: int = Field(default=1, description="Current charges for the top potion in the stack.")
    max_charges: int = Field(default=1, description="Maximum charges for each potion.")
    max_stack: int = Field(default=5, description="Maximum number of potions in one stack.")


def create_potion_of_greater_invisibility(owner_uuid: UUID) -> PotionOfGreaterInvisibility:
    action = DrinkGreaterInvisibilityPotionAction(
        source_entity_uuid=uuid4(), source_item_uuid=uuid4(), template=True,
    )
    return PotionOfGreaterInvisibility(
        source_entity_uuid=owner_uuid,
        use_action_templates=[action],
        stack_id="potion_of_greater_invisibility"
    )


class IgniteTorchAction(BaseAction):
    """Ignite a torch — creates a light source that follows the carrier."""

    name: str = Field(default="Ignite Torch", description="Action name for lighting a torch.")
    description: str = Field(
        default="Light the torch",
        description="Action description shown for torch ignition.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Torch actions target the source user and resolve through source_item_uuid.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for igniting a torch.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the torch item this action ignites.",
    )

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

        torch.ignite(self.source_entity_uuid, parent_event=execution_event.uuid)

        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Torch ignited")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Torch ignited")


class ExtinguishTorchAction(BaseAction):
    """Extinguish a lit torch — removes the light source."""

    name: str = Field(default="Extinguish Torch", description="Action name for putting out a torch.")
    description: str = Field(
        default="Put out the torch",
        description="Action description shown for torch extinguishing.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Torch actions target the source user and resolve through source_item_uuid.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for extinguishing a torch.",
    )
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the torch item this action extinguishes.",
    )

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

        torch.extinguish(parent_event=execution_event.uuid)

        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Torch extinguished")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Torch extinguished")


class Torch(UsableItem):
    """A torch that provides light when ignited.

    Very bright light in 10ft, bright light in additional 10ft, dim light in additional 20ft.
    When ignited, creates a light source anchored to the carrying entity.
    Light follows the entity as they move.
    """

    name: str = Field(default="Torch", description="Display name for the torch.")
    description: str = Field(
        default="A torch that provides very bright light in 10ft, bright light in 10ft, and dim light in 20ft",
        description="Item description shown for the torch.",
    )
    is_equippable: bool = Field(default=False, description="Torches are usable but not equippable in this test fixture.")
    is_pickable: bool = Field(default=True, description="Torches can be picked up.")
    map_char: str = Field(default="\u2666", description="Map glyph for the torch.")

    very_bright_radius_feet: int = Field(default=10, description="Very-bright light radius emitted while lit.")
    bright_radius_feet: int = Field(default=20, description="Bright light radius emitted while lit.")
    dim_radius_feet: int = Field(default=20, description="Dim light radius emitted while lit.")
    is_lit: bool = Field(default=False, description="Whether the torch currently has an attached light source.")
    _light_source_uuid: Optional[UUID] = None

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """Return the ignite or extinguish action according to lit state."""
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

    def ignite(self, carrier_entity_uuid: UUID,
               parent_event: Optional[UUID] = None) -> None:
        """Light the torch — creates a light source on the GridMap."""
        if self.is_lit:
            return
        self.is_lit = True
        grid = get_map()
        entity = Entity.get(carrier_entity_uuid)
        if entity:
            self._light_source_uuid = grid.add_light_source(
                position=entity.position,
                very_bright_radius_feet=self.very_bright_radius_feet,
                bright_radius_feet=self.bright_radius_feet,
                dim_radius_feet=self.dim_radius_feet,
                anchor_uuid=carrier_entity_uuid,
                parent_event=parent_event,
            )
            flame_event = ExposedFlameEvent(
                source_entity_uuid=carrier_entity_uuid,
                target_entity_uuid=self.uuid,
                item_uuid=self.uuid,
                position=entity.position,
                parent_event=parent_event,
                phase=EventPhase.DECLARATION,
            )
            flame_event = flame_event.phase_to(EventPhase.EFFECT)
            flame_event.phase_to(EventPhase.COMPLETION)

    def extinguish(self, parent_event: Optional[UUID] = None) -> None:
        """Put out the torch — removes the light source."""
        if not self.is_lit:
            return
        self.is_lit = False
        if self._light_source_uuid:
            grid = get_map()
            grid.remove_light_source(self._light_source_uuid, parent_event=parent_event)
            self._light_source_uuid = None

    def is_exposed_flame(self) -> bool:
        """Return whether the torch is currently burning."""
        return self.is_lit

    def douse_exposed_flame(self, parent_event: Optional[UUID] = None) -> bool:
        """Extinguish this torch as an exposed flame.

        Args:
            parent_event: Optional parent event UUID for light-removal lineage.

        Returns:
            True if the torch was lit and is now doused.
        """
        if not self.is_lit:
            return False
        self.extinguish(parent_event=parent_event)
        return True

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


class IgniteWallTorchAction(BaseAction):
    """Light a wall torch."""

    name: str = Field(default="Light Wall Torch", description="Action name for lighting a wall torch.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Wall torch actions target the user.")
    costs: List[Cost] = Field(default_factory=list, description="No-cost action-economy payload for lighting a wall torch.")
    source_item_uuid: Optional[UUID] = Field(default=None, description="UUID of the wall torch item being lit.")

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
        torch.light(parent_event=execution_event.uuid)
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Wall torch lit")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Wall torch lit")


class ExtinguishWallTorchAction(BaseAction):
    """Put out a wall torch."""

    name: str = Field(default="Extinguish Wall Torch", description="Action name for putting out a wall torch.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Wall torch actions target the user.")
    costs: List[Cost] = Field(default_factory=list, description="No-cost action-economy payload for extinguishing a wall torch.")
    source_item_uuid: Optional[UUID] = Field(default=None, description="UUID of the wall torch item being extinguished.")

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
        torch.put_out(parent_event=execution_event.uuid)
        effect = execution_event.phase_to(EventPhase.EFFECT, status_message="Wall torch extinguished")
        return effect.phase_to(EventPhase.COMPLETION, status_message="Wall torch extinguished")


class WallTorch(UsableItem):
    """A fixed wall-mounted torch. Cannot be picked up or moved."""

    name: str = Field(default="Wall Torch", description="Display name for the wall torch.")
    is_pickable: bool = Field(default=False, description="Wall torches are fixed environment objects.")
    is_equippable: bool = Field(default=False, description="Wall torches cannot be equipped.")
    map_char: str = Field(default="\u2666", description="Map glyph for the wall torch.")

    very_bright_radius_feet: int = Field(default=5, description="Very-bright light radius emitted while lit.")
    bright_radius_feet: int = Field(default=10, description="Bright light radius emitted while lit.")
    dim_radius_feet: int = Field(default=10, description="Dim light radius emitted while lit.")
    is_lit: bool = Field(default=False, description="Whether the wall torch currently has an attached light source.")
    _light_source_uuid: Optional[UUID] = None
    _wall_torch_position: Optional[Tuple[int, int]] = None

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """Return the light or extinguish action according to lit state."""
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

    def light(self, parent_event: Optional[UUID] = None) -> None:
        """Light the wall torch — creates a fixed light source."""
        if self.is_lit:
            return
        self.is_lit = True
        if self._wall_torch_position is not None:
            grid = get_map()
            self._light_source_uuid = grid.add_light_source(
                position=self._wall_torch_position,
                very_bright_radius_feet=self.very_bright_radius_feet,
                bright_radius_feet=self.bright_radius_feet,
                dim_radius_feet=self.dim_radius_feet,
                parent_event=parent_event,
            )
            flame_event = ExposedFlameEvent(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.uuid,
                item_uuid=self.uuid,
                position=self._wall_torch_position,
                parent_event=parent_event,
                phase=EventPhase.DECLARATION,
            )
            flame_event = flame_event.phase_to(EventPhase.EFFECT)
            flame_event.phase_to(EventPhase.COMPLETION)

    def put_out(self, parent_event: Optional[UUID] = None) -> None:
        """Extinguish the wall torch — removes the light source."""
        if not self.is_lit:
            return
        self.is_lit = False
        if self._light_source_uuid:
            grid = get_map()
            grid.remove_light_source(self._light_source_uuid, parent_event=parent_event)
            self._light_source_uuid = None

    def is_exposed_flame(self) -> bool:
        """Return whether the wall torch is currently burning."""
        return self.is_lit

    def douse_exposed_flame(self, parent_event: Optional[UUID] = None) -> bool:
        """Extinguish this wall torch as an exposed flame.

        Args:
            parent_event: Optional parent event UUID for light-removal lineage.

        Returns:
            True if the wall torch was lit and is now doused.
        """
        if not self.is_lit:
            return False
        self.put_out(parent_event=parent_event)
        return True


def create_wall_torch(position: Tuple[int, int], owner_uuid: UUID, lit: bool = True) -> WallTorch:
    """Create a wall torch at a fixed position and optionally light it."""
    torch = WallTorch(source_entity_uuid=owner_uuid)
    torch._wall_torch_position = position
    grid = get_map()
    grid.place_object(torch.uuid, position)
    if lit:
        torch.light()
    return torch


class DrinkHastePotionAction(PotionDrinkAction):
    """Drink a potion to gain Haste (no concentration, no lethargy)."""

    name: str = Field(default="Drink Haste Potion", description="Action name for drinking this potion.")
    description: str = Field(
        default="Drink to gain doubled speed, +2 AC, DEX advantage, +1 action for 10 rounds",
        description="Action description shown for haste potions.",
    )
    target_type: TargetType = Field(default=TargetType.SELF, description="Haste potions target the user.")
    source_item_uuid: Optional[UUID] = Field(default=None, description="UUID of the potion item being consumed.")

    def get_self_setup_profile(self, actor: Any) -> ActionSelfSetupProfile:
        """Return the typed combat consequences of the current Haste effect."""
        return ActionSelfSetupProfile(
            semantic_id="setup.haste",
            duration=ActionSetupDuration.UNTIL_REMOVED,
            maximum_duration_rounds=10,
            condition_fact_ids=("actor.condition.haste",),
            active_condition_semantic_keys=frozenset({
                "dnd.spells.transmutation.HasteEffect",
            }),
            armor_class_bonus=2,
            movement_speed_multiplier=2.0,
            extra_actions_per_turn=1,
            incapacitates_on_removal=True,
        )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")
        return declaration_event.phase_to(EventPhase.EXECUTION, status_message="Validated")

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity or not isinstance(entity, Entity):
            return execution_event.cancel(status_message="Entity not found")

        haste = HasteEffect(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            caster_uuid=entity.uuid,
        )
        haste.duration.duration_type = DurationType.ROUNDS
        haste.duration.duration = 10
        entity.add_condition(haste, parent_event=execution_event)

        effect = execution_event.phase_to(EventPhase.EFFECT,
            status_message=f"{entity.name} gains Haste")
        return effect.phase_to(EventPhase.COMPLETION,
            status_message="Drank Potion of Haste")


class PotionOfHaste(UsableItem):
    """Potion of Haste. Single use, consumable."""

    name: str = Field(default="Potion of Haste", description="Display name for the potion.")
    is_pickable: bool = Field(default=True, description="Haste potions can be picked up.")
    map_char: str = Field(default="\u03b8", description="Map glyph for the potion.")
    is_consumable: bool = Field(default=True, description="The potion is consumed when used.")
    charges: int = Field(default=1, description="Current charges for the top potion in the stack.")
    max_charges: int = Field(default=1, description="Maximum charges for each potion.")
    max_stack: int = Field(default=5, description="Maximum number of potions in one stack.")


def create_potion_of_haste(owner_uuid: UUID) -> PotionOfHaste:
    action = DrinkHastePotionAction(
        source_entity_uuid=uuid4(), source_item_uuid=uuid4(), template=True,
    )
    return PotionOfHaste(
        source_entity_uuid=owner_uuid,
        use_action_templates=[action],
        stack_id="potion_of_haste"
    )
