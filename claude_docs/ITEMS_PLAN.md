# Items & Inventory System — Design Document

This document describes the complete design for items, inventory, and environment objects. Every decision is final — no unresolved options.

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Current State](#2-current-state)
3. [Item Class Hierarchy](#3-item-class-hierarchy)
4. [BaseItem — The Foundation](#4-baseitem--the-foundation)
5. [EquippableItem — Gear & Equipment](#5-equippableitem--gear--equipment)
6. [UsableItem — Actions & Environment Objects](#6-usableitem--actions--environment-objects)
7. [Inventory Block](#7-inventory-block)
8. [Entity Orchestration](#8-entity-orchestration)
9. [GridMap & Senses Integration](#9-gridmap--senses-integration)
10. [Action System Integration](#10-action-system-integration)
11. [Conditions on Items](#11-conditions-on-items--unifying-condition-management-on-baseblock)
12. [Breakable Objects](#12-breakable-objects)
13. [Looting System](#13-looting-system)
14. [Implementation Phases](#14-implementation-phases)
15. [Appendix: Terminology](#15-appendix--terminology)

---

## 1. Design Philosophy

Items are discrete objects in the game world with clear type separation. The design follows these principles:

**Three-class hierarchy**: `BaseItem` (foundation) → `EquippableItem` (gear) / `UsableItem` (actions). An item is NEVER both equippable AND usable — clean separation.

**Weapons/armor carry their own scoped ModifiableValues** — a +1 sword is created with `base_value=1` on `weapon.attack_bonus` and `weapon.damage_bonus`. No hook needed. The existing calculation chain automatically selects the active weapon's values.

**`_equip`/`_unequip` hooks are for effects BEYOND the item's inherent stats** — AC bonuses from a sword, granted actions from a wand, conditions from a ring. Three valid approaches inside hooks: direct modifiers, action registration, OR conditions — the item's choice. We do not want to wrap everything in conditions if not needed. The hooks can handle a lot of stuff like actions and modifiers directly.

**Usable items provide actions via `get_use_actions()`** — discovered at query time, adaptive to item state (charges, conditions, locks).

**Equipment and Inventory are flat peer blocks on Entity** — Entity orchestrates their interaction. No nesting.

**Environment objects are non-pickable UsableItems** — no separate WorldObject class needed.

**Each action defines its own cost** — no free-interaction model, no attunement system. Pick up/drop can be free actions.

**Don't overuse conditions** — hooks can work directly with modifiers/actions/handlers. The item itself holds causal responsibility for those modifiers/actions/hooks. Use conditions when you need: event handlers, sub-conditions, expiration/duration, cross-entity cleanup, or removal saving throws.

**Deferred**: encumbrance penalties, phase transitions (entity→body), object AC.

---

## 2. Current State

### What Exists Today

- **Item classes**: `Weapon`, `Armor` (Helmet, BodyArmor, Gauntlets, Greaves, Boots, Amulet, Ring, Cloak), `Shield` — all inherit `BaseBlock` directly. No shared item interface.
- **Equipment block**: 13 typed slots, 19+ ModifiableValues, equip/unequip with events but no item hooks.
- **Action templates**: registered on entity, queried via `get_available_actions()`, proven pattern.
- **GridMap**: tracks tiles + entities, no object concept.
- **Senses**: sees entities + cells, no objects.
- **Class features**: SecondWindFeature/RageFeature register actions via conditions — proven pattern for equip-granted actions.
- **Weapon equip auto-registration**: `actions_functional.py` event handlers register Attack templates on `WEAPON_EQUIP` event at EFFECT phase (lines 134–165) — proven pattern.

### Existing Modifier Scoping Architecture

The engine already has a three-level modifier scoping system for attack and damage. This is foundational for understanding what `_equip` hooks need to do vs what's already handled.

**Level 1 — Weapon-inherent modifiers** (scoped to ONE weapon automatically):
- `weapon.attack_bonus: ModifiableValue` — created in weapon factories (e.g., `create_club()` in `dnd/items/weapons.py`)
- `weapon.damage_bonus: Optional[ModifiableValue]` — defaults to None, created for magic weapons
- These are automatically selected by `Entity._get_attack_bonuses(weapon_slot)` which picks the ACTIVE weapon's own ModifiableValues
- A +1 sword is simply created with `base_value=1` on attack_bonus and damage_bonus. **No equip hook needed.**
- Switching weapons automatically switches which weapon's ModifiableValues are used

**Level 2 — Equipment-wide modifiers** (global or weapon-type scoped):
- `equipment.attack_bonus` — applies to ALL attacks
- `equipment.melee_attack_bonus` / `equipment.ranged_attack_bonus` — weapon-type scoped
- `equipment.damage_bonus` / `equipment.melee_damage_bonus` / `equipment.ranged_damage_bonus` — same pattern
- `equipment.ac_bonus` — AC modifier
- Fighting styles use these: Archery adds +2 to `equipment.ranged_attack_bonus`, Dueling adds contextual +2 to `equipment.melee_damage_bonus`

**Level 3 — Event handlers** (process-based, dice manipulation):
- Great Weapon Fighting: EventHandler on `DAMAGE_ROLL_RESULT`, rerolls 1s and 2s
- Registered via conditions or `_equip` hooks

**The combination chain** (in `Entity._get_attack_bonuses` + `attack_bonus` method):
```
proficiency_bonus.combine_values([
    weapon.attack_bonus,           ← Level 1: THIS weapon's inherent bonus
    equipment.attack_bonus,        ← Level 2: global equipment bonus
    equipment.melee_attack_bonus,  ← Level 2: weapon-type bonus (melee OR ranged)
    ability_score,                 ← STR, DEX, or FINESSE choice
    ability_modifier               ← ability mod
])
```

**For damage** (in `Weapon.get_base_damage`):
```
combine_values([
    weapon.damage_bonus,           ← Level 1: THIS weapon's inherent bonus
    equipment.damage_bonus,        ← Level 2: global
    ability_modifier,              ← STR/DEX/FINESSE
    equipment.melee_damage_bonus   ← Level 2: weapon-type bonus
])
```

**Why this matters for `_equip` hooks**: Weapons already have their own scoped ModifiableValues. `_on_equip` is for effects BEYOND the weapon's own stats — AC bonuses, granted actions, conditions, modifiers on equipment-wide values. If you put a weapon-specific bonus on `equipment.attack_bonus` instead of `weapon.attack_bonus`, it would leak to ALL weapons.

**Current weapon creation pattern** (`dnd/items/weapons.py`):
```python
def create_club(source_id: UUID) -> Weapon:
    return Weapon(
        source_entity_uuid=source_id,
        name="Club",
        damage_dice=4, dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.LIGHT],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"
        ),
        extra_damage_dices=[], extra_damage_dices_numbers=[],
        extra_damage_bonus=[], extra_damage_type=[]
    )
```

A +1 club would change `base_value=0` to `base_value=1` and add a `damage_bonus=ModifiableValue.create(..., base_value=1, ...)`. That's it — no `_equip` hook, no condition. The scoping is automatic.

---

## 3. Item Class Hierarchy

### The Resolved Three-Class Model

```
BaseItem(BaseBlock)                          ← dnd/core/base_item.py
│   Core: gridmap presence, looting, destruction, optional Health
│   Flags: is_pickable=True, is_equippable=False, is_usable=False
│   Hooks: _on_loot(), _on_drop(), _on_destroy()
│   Fields: weight, value, rarity, tags, stack_count, max_stack
│   Spatial: blocks_movement, blocks_vision (for when on ground)
│   Breakable: Optional[Health], damage_immunities, damage_reduction
│
├── EquippableItem(BaseItem)
│   is_equippable = True, is_pickable = True (always — you equip from inventory)
│   Hooks: _on_equip(slot), _on_unequip(slot) — item-anchored lifecycle callbacks
│   Three approaches inside hooks (all valid):
│     1. Direct modifiers on entity's ModifiableValues
│     2. Direct action registration on entity
│     3. Condition pattern (for complex effects)
│   Subclasses: Weapon, Armor (Helmet, BodyArmor, etc.), Shield, Ring
│   Slot enums: WeaponSlot, BodyPart, RingSlot
│
└── UsableItem(BaseItem)
    is_usable = True
    Method: get_use_actions(owner_uuid) → List[BaseAction]
    Adaptive: called at query time, can vary by charges/state/conditions
    is_consumable: bool (destroyed after use)
    Pickable: Potion, Scroll (in inventory)
    Not pickable: Lever, Door, Chest (environment objects on gridmap)
```

**The key rule**: An item is NEVER both equippable AND usable. If an equipped item needs to grant actions, it does so through `_on_equip` — either by directly registering action templates on the entity, or by applying a condition that does the same. The item NEVER implements `get_use_actions()`.

### Stress-Test Table

| Item | Class | Pickable | Notes |
|------|-------|----------|-------|
| Longsword +1 on ground | EquippableItem | yes | `weapon.attack_bonus(base=1)`, `weapon.damage_bonus(base=1)`. No `_equip` hook — scoping automatic |
| Potion of Healing | UsableItem | yes | Consumable. `get_use_actions` → DrinkPotionAction(target=SELF) |
| Lever on wall | UsableItem | no | Environment. `get_use_actions` → PullLeverAction(target=SELF) |
| Door | UsableItem | no | Environment + breakable (has Health). Open/Close toggles spatial |
| Ring of Fire Bolt | EquippableItem | yes | `_on_equip` registers Fire Bolt action via condition or directly |
| Scroll of Fireball | UsableItem | yes | Consumable. `get_use_actions` wraps existing Fireball SpellAction |
| Chest | UsableItem | no | Environment. Has own Inventory. `get_use_actions` → OpenChestAction |
| Coins | BaseItem | yes | Pure loot. No equip, no use. Stackable. |
| Statue | BaseItem | no | Breakable (has Health). Blocks movement. Decorative. |
| Barricade | BaseItem | no | Breakable. Blocks movement. No interaction actions. |
| Defender Sword | EquippableItem | yes | Weapon inherent +1 attack/damage (Level 1) + `_on_equip` adds +1 AC to `equipment.ac_bonus` (Level 2) |
| Wand of Fire Bolt | EquippableItem | yes | `_on_equip` registers Fire Bolt action directly on entity |
| Campfire | UsableItem | no | Environment. `get_use_actions` → RestAction? Doesn't block movement |

---

## 4. BaseItem — The Foundation

**File location**: `dnd/core/base_item.py`

```python
class BaseItem(BaseBlock):
    allow_events_conditions: bool = True  # Items CAN receive conditions

    # Identity
    name: str = "Item"
    description: Optional[str] = None

    # Physical
    weight: float = 0.0
    value: int = 0
    rarity: ItemRarity = ItemRarity.COMMON  # enum: COMMON, UNCOMMON, RARE, VERY_RARE, LEGENDARY

    # Type flags (subclasses override)
    is_pickable: bool = True
    is_equippable: bool = False
    is_usable: bool = False
    is_consumable: bool = False

    # Stacking
    stack_count: int = 1
    max_stack: int = 1  # 1 = not stackable

    # Tags for filtering
    tags: List[str] = []

    # Spatial (when on ground, not in inventory/equipped)
    blocks_movement: bool = False
    blocks_vision: bool = False

    # Breakable (Section 12)
    is_targetable: bool = False
    health: Optional[Health] = None
    damage_immunities: List[DamageType] = [DamageType.POISON, DamageType.PSYCHIC]
    damage_reduction: Dict[str, int] = {}  # material-based, e.g. {"bludgeoning": 5}

    # Tracking
    equipped_slot: Optional[Any] = None  # Which slot this is in (None if not equipped)
```

### Lifecycle Hooks

Public + private pattern, same as `BaseCondition.apply`/`_apply`:

```python
    def loot(self) -> None:
        """Called by Entity when item enters inventory."""
        self._on_loot()

    def _on_loot(self) -> None:
        """Override for item-specific loot behavior (e.g., cursed item applies condition)."""
        pass

    def drop(self) -> None:
        """Called by Entity when item leaves inventory to ground."""
        self._on_drop()

    def _on_drop(self) -> None:
        pass

    def destroy(self) -> None:
        """Remove item from all registries. Called for consumables and broken objects."""
        self._on_destroy()
        # Clean up conditions on this item
        for cond_name in list(self.active_conditions.keys()):
            self.remove_condition(cond_name)
        # Remove from BaseObject registry
        # Remove from GridMap if placed
        # Remove from Inventory if stored

    def _on_destroy(self) -> None:
        """Override for item-specific destruction behavior (chest spills contents, etc.)."""
        pass
```

`_destroy` is on BaseItem (not just UsableItem) because both consumable UsableItems and breakable BaseItems need destruction — shared foundation.

### The UUID Pattern

Same as conditions/actions: `self.source_entity_uuid` is set BEFORE hooks fire. Hook bodies call `Entity.get(self.source_entity_uuid)` in concrete subclasses (which live in high-level modules that CAN import Entity). BaseItem in `dnd/core/` never imports Entity.

### Spatial Methods

```python
    def blocks_walking(self, requesting_entity_uuid: Optional[UUID] = None,
                       mode: MovementMode = MovementMode.WALKING) -> bool:
        return self.blocks_movement

    def blocks_vision_check(self, requesting_entity_uuid: Optional[UUID] = None) -> bool:
        return self.blocks_vision
```

### Dependency Direction

```
Entity → BaseItem → BaseBlock → BaseModel
```
BaseItem lives at same level as Tile. Importable from anywhere safely.

### Migration

Reparenting `Weapon(BaseBlock)` → `Weapon(EquippableItem)` → `Weapon(BaseItem)` → `BaseBlock` is non-breaking. All new fields have defaults. Existing factories unchanged.

---

## 5. EquippableItem — Gear & Equipment

Inherits BaseItem, sets `is_equippable = True`, `is_pickable = True`.

### Primary Role: Carrying ModifiableValues

The main job of equippable items is carrying ModifiableValues consumed by the existing calculation chain:

**Weapon** (subclass of EquippableItem):
- `attack_bonus: ModifiableValue` — consumed by `Entity._get_attack_bonuses(weapon_slot)` which selects the ACTIVE weapon's attack_bonus
- `damage_bonus: Optional[ModifiableValue]` — consumed by `Weapon.get_base_damage()`
- `damage_dice`, `dice_numbers`, `damage_type`, `properties`, `range` — weapon stats consumed by Attack action
- A +1 weapon simply has `attack_bonus` with `base_value=1` and `damage_bonus` with `base_value=1`
- The scoping is AUTOMATIC: `_get_attack_bonuses(MELEE_MAIN)` picks `weapon_melee_main.attack_bonus`, not any other weapon's

**Armor (BodyArmor, Helmet, etc.)** (subclass of EquippableItem):
- `ac: ModifiableValue` — consumed by `Entity.ac_bonus()` which reads `body_armor.ac`
- `max_dex_bonus: ModifiableValue` — caps DEX contribution to AC
- `type: ArmorType` — LIGHT/MEDIUM/HEAVY, affects DEX cap and feature interactions
- A +1 armor has `ac` with `base_value=17` instead of 16 (for plate). No hook needed.

**Shield** (subclass of EquippableItem):
- `ac_bonus: ModifiableValue` — consumed by `Entity.ac_bonus()` which adds `shield.ac_bonus` when equipped
- A +1 shield has `ac_bonus` with `base_value=3` instead of 2. No hook needed.

These ModifiableValues are the items' INHERENT stats. The existing `Equipment.equip()` slots them into the right position, and `Entity.attack_bonus()` / `Entity.ac_bonus()` / `Weapon.get_base_damage()` already know how to find and combine them.

### Canonical vs Non-Canonical Slots

| Slot Type | Has dedicated calculation path? | `_equip` hook needed for? |
|-----------|-------------------------------|------------------------|
| Weapon (MELEE_MAIN, etc.) | Yes — attack_bonus, damage_bonus consumed by _get_attack_bonuses/get_base_damage | Only for EXTRA effects beyond attack/damage (e.g., Defender sword's AC bonus) |
| Body Armor | Yes — ac, max_dex_bonus consumed by ac_bonus() | Only for EXTRA effects (e.g., armor that also grants fire resistance) |
| Shield | Yes — ac_bonus consumed by ac_bonus() | Only for EXTRA effects |
| Ring | No | Almost always — ring effects (AC, saves, granted spells) all need hooks |
| Cloak | No | Almost always |
| Amulet | No | Almost always |
| Helmet/Boots/Gauntlets | No | Almost always |

### The `_equip`/`_unequip` Hooks

```python
class EquippableItem(BaseItem):
    is_equippable: bool = True
    is_pickable: bool = True
    equipped_slot: Optional[Union[WeaponSlot, BodyPart, RingSlot]] = None

    def equip(self, slot: Union[WeaponSlot, BodyPart, RingSlot]) -> None:
        """Called by Equipment.equip() after slot assignment."""
        self.equipped_slot = slot
        self._on_equip(slot)

    def _on_equip(self, slot: Union[WeaponSlot, BodyPart, RingSlot]) -> None:
        """Override in subclasses. Three valid approaches:
        1. Direct modifiers: add to entity's ModifiableValues
        2. Direct actions: register action templates on entity
        3. Condition: apply condition that handles complex effects
        The item holds causal responsibility. _on_unequip cleans up."""
        pass

    def unequip(self, slot: Union[WeaponSlot, BodyPart, RingSlot]) -> None:
        """Called by Equipment.unequip() before slot cleared."""
        self._on_unequip(slot)
        self.equipped_slot = None

    def _on_unequip(self, slot: Union[WeaponSlot, BodyPart, RingSlot]) -> None:
        """Override in subclasses. Clean up everything _on_equip set up."""
        pass
```

### When Hooks Are NOT Needed

- A +1 sword's attack/damage bonus: handled by `weapon.attack_bonus`/`weapon.damage_bonus` (Level 1 scoping). Just create the weapon with `base_value=1`.
- Standard armor AC: handled by `BodyArmor.ac`, already integrated in `Entity.ac_bonus()`.
- Standard shield AC bonus: handled by `Shield.ac_bonus`, already integrated.

### When Hooks ARE Needed — Three Approaches

**Approach 1 — Direct modifiers** (simplest, for static bonuses on equipment-wide values):
```python
class DefenderSword(Weapon):
    """A sword that also grants +1 AC (beyond its own attack/damage which are
    handled by weapon.attack_bonus/damage_bonus created at base_value=1)."""
    _ac_modifier_uuid: Optional[UUID] = None

    def _on_equip(self, slot):
        entity = Entity.get(self.source_entity_uuid)
        # The +1 attack/damage is already on weapon.attack_bonus/damage_bonus (Level 1).
        # The +1 AC is an ADDITIONAL effect → goes on equipment.ac_bonus (Level 2).
        self._ac_modifier_uuid = entity.equipment.ac_bonus.self_static.add_value_modifier(
            NumericalModifier(name="Defender Sword AC", value=1, ...)
        )

    def _on_unequip(self, slot):
        entity = Entity.get(self.source_entity_uuid)
        if self._ac_modifier_uuid:
            entity.equipment.ac_bonus.self_static.remove_modifier(self._ac_modifier_uuid)
```

**Approach 2 — Direct action registration** (for equip-granted actions):
```python
class WandOfFireBolt(EquippableItem):
    """A wand that grants the Fire Bolt cantrip when equipped."""
    def _on_equip(self, slot):
        entity = Entity.get(self.source_entity_uuid)
        entity.register_action(FireBolt(
            source_entity_uuid=entity.uuid, caster_level=5,
            template=True, name="Fire Bolt (Wand)"
        ))

    def _on_unequip(self, slot):
        entity = Entity.get(self.source_entity_uuid)
        entity.unregister_action("Fire Bolt (Wand)")
```

**Approach 3 — Condition pattern** (for complex effects needing event handlers, sub-conditions, expiration, cross-entity cleanup):
```python
class CloakOfProtection(EquippableItem):
    """Grants +1 AC and +1 to all saving throws. Uses condition because it
    needs modifiers on MULTIPLE targets (ac_bonus + all 6 saving throws)."""
    def _on_equip(self, slot):
        entity = Entity.get(self.source_entity_uuid)
        entity.add_condition(CloakOfProtectionCondition(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
        ))

    def _on_unequip(self, slot):
        entity = Entity.get(self.source_entity_uuid)
        if "CloakOfProtectionCondition" in entity.active_conditions:
            entity.remove_condition("CloakOfProtectionCondition")
```

**Why conditions are sometimes preferred**: A condition's `_apply` returns the 5-tuple `(modifier_uuids, handler_uuids, sub_condition_uuids, spatial_handler_uuids, event)`. The condition tracks all these for automatic cleanup via `cleanup_own_state()`. When an item applies many modifiers across different ModifiableValues, a condition provides centralized tracking. Without it, `_on_unequip` must manually track and clean up each modifier UUID.

### Modifier Placement Guide for `_equip` Hooks

| Effect | Where to add modifier | Why |
|--------|----------------------|-----|
| +1 to THIS weapon's attacks | `weapon.attack_bonus` (at creation, NOT in hook) | Level 1: auto-scoped to this weapon |
| +1 to THIS weapon's damage | `weapon.damage_bonus` (at creation, NOT in hook) | Level 1: auto-scoped to this weapon |
| +1 to ALL melee attacks | `equipment.melee_attack_bonus` (in hook) | Level 2: affects all melee weapons |
| +1 to ALL attacks | `equipment.attack_bonus` (in hook) | Level 2: global |
| +1 AC | `equipment.ac_bonus` (in hook) | Level 2: global defense |
| +1 to all saves | each saving_throw ModifiableValue (in hook, consider condition) | Many targets → condition pattern |
| Reroll damage dice | EventHandler on DAMAGE_ROLL_RESULT (in hook) | Level 3: process-based |
| Grant an action | `entity.register_action()` (in hook) | Direct registration |

### Cursed Item Example

```python
class CursedSwordCondition(BaseCondition):
    """Applied by cursed sword's _on_equip. Blocks unequip via event handler."""
    def _apply(self, declaration_event):
        handler = EventHandler(
            name="Cursed Sword - Block Unequip",
            event_processor=self._block_unequip,
            trigger_conditions=[Trigger(
                event_type=EventType.WEAPON_UNEQUIP,
                event_phase=EventPhase.EXECUTION,
                event_source_entity_uuid=self.target_entity_uuid,
            )]
        )
        target = Entity.get(self.target_entity_uuid)
        target.add_event_handler(handler)
        return [], [handler.uuid], [], [], effect_event
```

### Where Hooks Get Called — Insertion Points

**In `Equipment.equip()`** — AFTER slot assignment, BEFORE event EFFECT phase:
- Lines 784–791 (weapons): `setattr(self, slot_field, weapon)` → INSERT `item.equip(slot)`
- Line 740 (shields): `self.weapon_melee_off = item` → INSERT `item.equip(slot)`
- Lines 711–714 (rings): `self.ring_left/right = item` → INSERT `item.equip(slot)`
- Line 822 (armor): `setattr(self, attribute_name, item)` → INSERT `item.equip(slot)`

**In `Equipment.unequip()`** — BEFORE slot cleared to None:
- Line 892: INSERT `current_item.unequip(slot)` → then `setattr(self, attribute_name, None)`

### Reparenting Existing Classes

Weapon, Armor (all subtypes), Shield reparent from `BaseBlock` → `EquippableItem` → `BaseItem` → `BaseBlock`. Non-breaking — all existing fields (`attack_bonus`, `damage_bonus`, `ac`, `ac_bonus`, `max_dex_bonus`, etc.) are preserved. The existing calculation chain in `Entity._get_attack_bonuses()`, `Weapon.get_base_damage()`, `Entity.ac_bonus()` continues to work unchanged.

---

## 6. UsableItem — Actions & Environment Objects

Inherits BaseItem, sets `is_usable = True`.

```python
class UsableItem(BaseItem):
    is_usable: bool = True
    is_consumable: bool = False  # Destroyed after use

    def get_use_actions(self, owner_uuid: UUID) -> List[BaseAction]:
        """Return action templates this item provides.
        Called at query time — can be adaptive (charges, state, conditions).
        owner_uuid: entity who would use the item."""
        return []
```

### Adaptive Behavior

`get_use_actions()` is called fresh each time `get_available_actions()` runs:
- **Charge-based**: wand returns `[]` at 0 charges
- **State-dependent**: locked chest returns LockPickAction; unlocked returns OpenChestAction
- **Consumed**: `stack_count == 0` → returns `[]`

### Consumable Destruction

Handled centrally in `BaseAction.apply()` after `_apply_costs()` (line ~532 in `base_actions.py`). Check `source_item_uuid` → if `item.is_consumable` and action not canceled → `item.destroy()`. Automatic.

For stacks: use action decrements `stack_count`. When `stack_count` reaches 0, item is destroyed.

### Environment Objects = `UsableItem(is_pickable=False)`

No WorldObject class needed:

```python
class Lever(UsableItem):
    is_pickable: bool = False

    def get_use_actions(self, owner_uuid):
        return [PullLeverAction(source_entity_uuid=owner_uuid, template=True,
                                source_item_uuid=self.uuid)]

class Door(UsableItem):
    is_pickable: bool = False
    blocks_movement: bool = True   # when closed
    blocks_vision: bool = True     # when closed
    is_targetable: bool = True     # can be broken
    is_open: bool = False

    def get_use_actions(self, owner_uuid):
        if self.is_open:
            return [CloseDoorAction(source_entity_uuid=owner_uuid, ...)]
        return [OpenDoorAction(source_entity_uuid=owner_uuid, ...)]
```

### `source_item_uuid` Field

Add `source_item_uuid: Optional[UUID] = None` to `BaseAction`. All use-action templates carry this for consumable cleanup, UI display, and combat log.

---

## 7. Inventory Block

Flat block on Entity (NOT inside Equipment):

```
Entity
├── equipment: Equipment    (slots + combat stats, unchanged)
├── inventory: Inventory    (general item storage, NEW)
├── ... other blocks ...
```

```python
class Inventory(BaseBlock):
    """Container for BaseItems. Used by entities, chests, bags, loot bodies."""
    name: str = "Inventory"
    items: Dict[UUID, BaseItem] = {}
    weight_capacity: Optional[float] = None  # None = unlimited. Entity can set STR*15.
    max_slots: Optional[int] = None

    @property
    def total_weight(self) -> float:
        return sum(item.weight * item.stack_count for item in self.items.values())

    def add_item(self, item: BaseItem) -> bool:
        """Add item. Returns False if full/overweight."""

    def remove_item(self, item_uuid: UUID) -> Optional[BaseItem]:
        """Remove and return item."""

    def find_items_by_name(self, name: str) -> List[BaseItem]:
    def find_items_by_tag(self, tag: str) -> List[BaseItem]:
    def has_item(self, item_uuid: UUID) -> bool:
    def transfer_to(self, item_uuid: UUID, target: 'Inventory') -> bool:

    def get_all_use_actions(self, owner_uuid: UUID) -> List[BaseAction]:
        """Aggregate Use actions from all UsableItems. Called at query time."""
        actions = []
        for item in self.items.values():
            if hasattr(item, 'get_use_actions'):
                actions.extend(item.get_use_actions(owner_uuid))
        return actions
```

Inventory is independently usable: Chests have Inventory (no Equipment needed). Bags of Holding are items with Inventory. Loot bodies have Inventory.

**Dependency**: `Entity` → `Inventory` → `BaseItem` → `BaseBlock` (clean downward flow)

---

## 8. Entity Orchestration

Entity wraps equip/unequip/loot/drop. Equipment and Inventory don't know about each other.

```python
# On Entity:
def loot_item(self, item: BaseItem) -> bool:
    """Pick up item into inventory."""
    item.source_entity_uuid = self.uuid
    success = self.inventory.add_item(item)
    if success:
        item.loot()  # Calls _on_loot hook
    return success

def drop_item(self, item_uuid: UUID) -> Optional[BaseItem]:
    """Drop item from inventory to ground."""
    item = self.inventory.remove_item(item_uuid)
    if item:
        item.drop()  # Calls _on_drop hook
        gridmap.place_object(item.uuid, self.senses.position)
    return item

def equip_item(self, item_uuid: UUID, slot) -> bool:
    """Move item from inventory to equipment slot."""
    item = self.inventory.items.get(item_uuid)
    if item is None or not item.is_equippable:
        return False
    self.inventory.remove_item(item_uuid)
    self.equipment.equip(item, slot)  # Equipment.equip calls item.equip(slot) internally
    return True

def unequip_item(self, slot, to_inventory: bool = True) -> Optional[BaseItem]:
    """Move item from equipment slot to inventory (or drop)."""
    item = self.equipment.unequip(slot)  # Equipment.unequip calls item.unequip(slot) internally
    if item and to_inventory:
        self.inventory.add_item(item)
    elif item:
        gridmap.place_object(item.uuid, self.senses.position)
    return item
```

**Direct equip still works** for factories/setup — `Equipment.equip(item, slot)` doesn't require item to be in inventory. Essential for bestiary factories and initial entity setup.

---

## 9. GridMap & Senses Integration

### The Problem

Currently GridMap tracks only tiles and entities. No concept of objects on the ground.

### Solution: `blocks_walking()` / `blocks_vision()` Methods on BaseBlock

**On BaseBlock** (default implementations — non-spatial blocks return False):
```python
class BaseBlock:
    def blocks_walking(self, requesting_entity_uuid: Optional[UUID] = None,
                       mode: MovementMode = MovementMode.WALKING) -> bool:
        return False

    def blocks_vision_check(self, requesting_entity_uuid: Optional[UUID] = None) -> bool:
        return False
```

**Tile override:**
```python
class Tile(BaseBlock):
    def blocks_walking(self, requesting_entity_uuid=None, mode=MovementMode.WALKING):
        return self.get_movement_cost(mode) <= 0

    def blocks_vision_check(self, requesting_entity_uuid=None):
        return not self.visible
```

**BaseItem override** (for items on ground):
```python
class BaseItem(BaseBlock):
    def blocks_walking(self, requesting_entity_uuid=None, mode=MovementMode.WALKING):
        return self.blocks_movement

    def blocks_vision_check(self, requesting_entity_uuid=None):
        return self.blocks_vision
```

### Current State (from investigation)

- **Entity blocking**: GridMap uses `_entities_by_position` + `_non_blocking_entities` set. Entity blocks walking for others, not self. Dead entities marked non-blocking via `set_entity_blocking()`.
- **Vision blocking**: Purely `tile.visible` (hardcoded bool). Entities DON'T block vision.
- **Tile walking**: `tile.get_movement_cost(mode)` checks `walking_cost` ModifiableValue (line 100 in `base_tiles.py`).

### GridMap Changes

New registries:
```python
_object_positions: Dict[UUID, Tuple[int, int]] = {}
_objects_by_position: DefaultDict[Tuple[int, int], Set[UUID]] = defaultdict(set)
```

New methods:
- `place_object(item_uuid, position)` — register object on grid
- `remove_object(item_uuid)` — unregister from grid
- `get_objects_at(position) → Set[UUID]` — objects at position
- `get_object_position(item_uuid) → Optional[Tuple[int, int]]`

Updates to existing methods:
- `is_walkable_for()` — also check `_objects_by_position[(x,y)]`, call `obj.blocks_walking(requesting_entity_uuid)`
- FOV computation — also check objects via `blocks_vision_check()`

### Senses Changes

Add `objects: Dict[UUID, Tuple[int, int]]` field (same pattern as `entities`). `Entity.update_entity_senses()` queries GridMap for visible objects, populates `senses.objects`. Senses does NOT import BaseItem — stores UUID + position only.

### Spatial vs Non-Spatial

Blocks on the map (tiles, items on ground, entities) have meaningful spatial methods. Blocks inside entities (Equipment, Health, etc.) inherit the BaseBlock defaults (return False). No special flag needed — only blocks registered in GridMap are queried.

### Door Toggle Example

`Door.open()` sets `blocks_movement=False`, `blocks_vision=False`, triggers senses update for nearby entities.

---

## 10. Action System Integration

### Current `get_available_actions()` Flow

`Entity.get_available_actions()` (entity.py lines 1721–2013):
1. SELF actions: iterate `self_actions`, validate, add to result
2. ENTITY actions: iterate `entity_actions` × visible entities, `pre_validate` each
3. POSITION_PATH actions: iterate `position_actions` × reachable positions
4. POSITION_LOS actions: iterate × valid positions from template
5. POSITION_AOE actions: iterate × valid positions with shape computation

### Three Action Sources

| Source | Mechanism | Discovery Time |
|--------|-----------|----------------|
| 1. Registered | `entity.registered_actions` | At registration |
| 2. Inventory | `entity.inventory.get_all_use_actions(uuid)` | Query time |
| 3. Environment | `senses.objects` → `obj.get_use_actions(uuid)`, ≤5ft | Query time |

Sources 2 and 3 are inserted AFTER registered actions. Each discovered action is validated the same way (`pre_validate` per target, check costs, group by `target_type` into appropriate result category).

### New Fields on `AvailableActionInfo`

```python
is_item_use: bool = False               # True for Use actions (inventory or environment)
source_item_uuid: Optional[UUID] = None  # The item providing this action
```

No separate `source_object_uuid` — environment objects ARE UsableItems, so `source_item_uuid` serves for both.

### `execute_by_index()` Three-Source Search

Search registered first → inventory second → environment third. Once found, execution path unchanged (instantiate → apply).

### Fold Into Existing Categories

Use actions go into `self_actions`/`entity_actions`/`position_actions` based on their `target_type`. AI and UI see them as any other action. The `is_item_use` flag enables UI rendering (show item icon, "Use:" prefix).

---

## 11. Conditions on Items — Unifying Condition Management on BaseBlock

### Key Architectural Discovery

`BaseBlock._registry` (line 144 in `base_block.py`) contains ALL BaseBlock instances — entities, tiles, AND items. `BaseBlock.get(uuid)` can find any of them. This means `_remove_condition_tree()` CAN move to BaseBlock using `BaseBlock.get()` for cross-object lookups, with no circular imports.

**NOTE**: CLAUDE.md currently says `BaseObject → BaseBlock → Entity` but actual code is `BaseObject(BaseModel)` and `BaseBlock(BaseModel)` — separate hierarchies. CLAUDE.md needs correcting.

### Current State

| Feature | BaseBlock | Entity |
|---------|-----------|--------|
| `add_condition()` | Yes (line 585) | Yes (override — adds saving throw check) |
| `remove_condition()` | Yes (line 555, sub-conditions only) | Yes (override — full tree traversal, line 389) |
| `_remove_condition_tree()` | No | Yes (line 347 — handles external_conditions, terrain_conditions) |
| `remove_condition_by_uuid()` | No | Yes (line 422 — UUID lookup → `remove_condition(name)`) |
| `advance_duration_condition()` | No | Yes (line 436 — turn-based with removal saves) |

### The Refactor: Move Condition Management DOWN to BaseBlock

This makes tiles and items first-class condition hosts with full cross-object cleanup.

**What moves to BaseBlock:**

1. **`remove_condition_by_uuid()`** — simple UUID lookup in `active_conditions_by_uuid` → delegates to `self.remove_condition(name)`. No imports needed.

2. **`_remove_condition_tree()`** — uses `BaseBlock.get(target_uuid)` instead of `Entity.get()`:

```python
# In BaseBlock — NO Entity import needed
def _remove_condition_tree(self, condition, expire=False, parent_event=None):
    # Sub-conditions (same block)
    for sub_uuid in list(condition.sub_conditions):
        sub = BaseCondition.get(sub_uuid)
        if sub is not None and isinstance(sub, BaseCondition):
            self._remove_condition_tree(sub, expire, parent_event)

    # External conditions (ANY BaseBlock — entities, items, tiles)
    for target_uuid, cond_uuid in condition.external_conditions:
        target = BaseBlock.get(target_uuid)
        if target is not None:
            target.remove_condition_by_uuid(cond_uuid)

    # Terrain conditions (tiles — also BaseBlocks)
    for tile_uuid, cond_uuid in condition.terrain_conditions:
        target = BaseBlock.get(tile_uuid)
        if target is not None:
            target.remove_condition_by_uuid(cond_uuid)

    # Own state cleanup (modifiers, handlers)
    condition.cleanup_own_state(expire, parent_event)
```

**Why this works**: Entity, Tile, and (future) BaseItem all inherit BaseBlock. They all register in `BaseBlock._registry` via `__init__()`. `BaseBlock.get(uuid)` finds any of them.

3. **`remove_condition()` upgrade** — BaseBlock's version (line 555) currently handles sub-conditions with `cleanup_own_state()` but NOT cross-object cleanup. After refactor, it calls `_remove_condition_tree()` for full cleanup:

```python
# BaseBlock.remove_condition() — now with full tree traversal
def remove_condition(self, condition_name, expire=False, parent_event=None):
    condition = self.active_conditions.pop(condition_name)
    all_subs = self._collect_all_sub_conditions(condition)
    for sub in all_subs:
        self._remove_condition_from_dicts(sub)
    self._remove_condition_from_dicts(condition)
    self._remove_condition_tree(condition, expire, parent_event)  # Full tree
```

Entity's override still adds Entity-specific logic (saving throw checks, additional tracking) while tree traversal is inherited.

**What stays on Entity:**
- `advance_duration_condition()` — calls `self.saving_throw()` which is Entity-specific
- `add_condition()` override — Entity adds saving throw checks before application

### Key Implications

**For tiles**: Currently tiles only get same-block sub-condition cleanup. With this refactor, if a tile condition creates `external_conditions` on entities (e.g., a trap that applies Poisoned), removing the tile condition now properly cleans up the entity conditions too.

**For items**: Same benefit. If a magic item's condition creates `external_conditions` on the wielder, destroying the item (which calls `destroy` → `remove_condition`) now properly cleans up the entity conditions via the tree.

### Condition Progression — Two Tracks

| Track | What | When | How |
|-------|------|------|-----|
| **Entity turn** | Entity conditions + conditions on equipped/inventory items | During entity's `on_turn_start()` | `Entity.advance_duration_condition()` for own conditions. Entity iterates equipped items + inventory items and calls `advance_duration()` on their conditions |
| **Environment step** | Conditions on tiles + conditions on floor items (items on GridMap) | End of full round | `Encounter._environment_step()` iterates GridMap tiles and floor objects, calls `advance_duration()` on their conditions |

**Why this split**: Equipped/inventory items are "part of" their owner entity — their conditions progress on the owner's turn (e.g., a Magic Weapon spell duration ticks when the wielder's turn starts). Floor items and tiles have no owner — they need an "environment step" after all combatants have acted.

**`advance_duration()` on BaseBlock** (simpler than Entity's `advance_duration_condition`):
```python
# On BaseBlock — no saving throws, just duration ticking
def advance_duration(self, parent_event=None):
    for cond_name, condition in list(self.active_conditions.items()):
        if condition.duration is not None:
            condition.duration -= 1
            if condition.duration <= 0:
                self.remove_condition(cond_name, expire=True, parent_event=parent_event)
```

### Environment Step — New Encounter Lifecycle Concept

The environment step is a first-class concept in the Encounter lifecycle. Environmental dynamics happen independently of any entity: fire spreads from ignited oil, terrain changes, floor objects react, conditions progress.

**Encounter round lifecycle after this change:**
```
Round N:
  Entity 1 Turn → Entity 2 Turn → ... → Entity N Turn
  → ROUND_END event
  → ENVIRONMENT STEP ← NEW
      1. Tile conditions advance_duration()
      2. Floor item conditions advance_duration()
      3. Environmental dynamics (fire spreads, objects react)
  → round_number++
  → ROUND_START event
Round N+1: ...
```

**Insertion point**: `Encounter._advance_round()` (line 428) — between `_fire_round_end()` and `round_number += 1`:

```python
def _advance_round(self) -> None:
    self._fire_round_end()
    self._environment_step()  # NEW
    self.round_number += 1
    self.current_turn_index = 0
    for combatant in self.combatants.values():
        combatant.has_acted_this_round = False
    self._fire_round_start()
```

### When NOT to Use Conditions

- `_equip`/`_unequip` can directly add/remove modifiers — no condition needed for simple static bonuses
- Use conditions when you need: event handlers, sub-conditions, expiration/duration, cross-entity cleanup, removal saving throws
- A Defender Sword's +1 AC from `_equip` hook can be a direct modifier. A "cursed sword that blocks unequip" needs a condition with event handler.

### Conditions on Items Use Case

Magic Weapon spell → applies `MagicWeaponCondition` to the Weapon block (not the entity!) → adds +1 to `weapon.attack_bonus` ModifiableValue. Concentration on caster links via `external_conditions` → breaking concentration removes weapon condition via `_remove_condition_tree` on BaseBlock. The weapon is found via `BaseBlock.get(weapon_uuid)` — works because Weapon inherits from EquippableItem → BaseItem → BaseBlock.

---

## 12. Breakable Objects

### Design

No object AC — focus on HP and material-based damage reduction.

- `is_targetable: bool = False` on BaseItem
- `health: Optional[Health] = None` — sub-block for HP
- `damage_reduction: Dict[str, int] = {}` — by damage type or material
- `damage_immunities: List[DamageType] = [DamageType.POISON, DamageType.PSYCHIC]`

### Methods on BaseItem

```python
def is_breakable(self) -> bool:
    return self.is_targetable and self.health is not None

def receive_damage(self, amount, damage_type, source_uuid) -> int:
    if damage_type in self.damage_immunities: return 0
    if self.health is None: return 0
    actual = min(amount, self.health.current_hp)
    self.health.current_hp -= actual
    if self.health.current_hp <= 0:
        self.destroy()  # Calls _on_destroy then cleans up
    return actual
```

### AttackObject Action

Standard entity action registered like Move, Dash, Dodge (via `setup_standard_actions`). Targets adjacent objects with `is_targetable=True`. Separate from normal Attack action — objects are not entities.

### AoE Integration

Optional `include_objects: bool = False` flag on BaseAction. When True, separate damage pass after entity convolution applies damage to targetable objects in AoE zone.

---

## 13. Looting System

### Simplified Design (Defer Full Transitions)

Entity→body transitions (and wall→rubble, etc.) are deferred to a common transition framework later.

**On death:**
- Old Entity persists (for resurrection)
- Create a `UsableItem(is_pickable=False)` body at death position
- Body has its own Inventory, populated from dead entity's equipped items + inventory items
- Body placed on GridMap via `place_object()`. Discovered via `senses.objects`.
- Body's `get_use_actions()` returns `[LootAction]`

**Dropped items on ground:**
- `place_object(item.uuid, position)` — simple
- Adjacent entity gets "Pick Up" action via environment object discovery (Section 10, source 3)

**LootAction:**
- Transfers items from body's Inventory to looter's Inventory
- UI/AI layer handles selection of which items to loot

---

## 14. Implementation Phases

### Phase 0: Fix CLAUDE.md

- Correct the "Three-Tier Ownership Hierarchy" section: `BaseBlock(BaseModel)` is the true base for blocks, tiles, and entities. `BaseObject(BaseModel)` is a separate hierarchy for ModifiableValues, Modifiers, Events, Conditions, etc.
- Update `BaseBlock._registry` documentation to clarify it contains ALL BaseBlocks
- Dependencies: None

### Phase 1: Condition Management Refactor (BaseBlock)

Delicate refactor — touches core condition lifecycle. Incremental steps with tests after each.

**Step 1.1: Add `remove_condition_by_uuid()` to BaseBlock**
- Simple method: look up in `active_conditions_by_uuid`, delegate to `self.remove_condition(name)`
- Verify Entity's version can be replaced by calling super()
- File: `dnd/core/base_block.py`
- Test: Full pytest suite

**Step 1.2: Move `_remove_condition_tree()` to BaseBlock**
- Copy from Entity, replace `Entity.get()` with `BaseBlock.get()`, replace tile GridMap lookup with `BaseBlock.get(tile_uuid)`
- Keep Entity's version as pass-through to super()
- **Danger**: Don't change BaseBlock.remove_condition() yet — only Entity.remove_condition() should call the tree
- Files: `dnd/core/base_block.py`, `dnd/entity.py`
- Test: Full pytest. Concentration spell cleanup, zone spell cleanup, sub-condition chains.

**Step 1.3: Upgrade BaseBlock.remove_condition() to use `_remove_condition_tree()`**
- BaseBlock.remove_condition() now calls `_remove_condition_tree()` for full cross-object cleanup
- Entity.remove_condition() override still adds Entity-specific logic but delegates tree traversal
- **Danger**: Avoid double-cleanup — ensure override is clean
- Files: `dnd/core/base_block.py`, `dnd/entity.py`
- Test: Full pytest. Tile with condition that has external_conditions on entity → remove → verify cleanup.

**Step 1.4: Add `advance_duration()` to BaseBlock**
- Simple duration ticking: decrement, remove if expired. No saving throws.
- File: `dnd/core/base_block.py`
- Test: Tile with duration=3 condition, advance 3 times, verify removed.

**Step 1.5: Add Environment Step in Encounter**
- New `Encounter._environment_step()` called from `_advance_round()` (line 428)
- Queries GridMap for tiles and floor objects with active conditions
- Calls `advance_duration()` on each
- May need new GridMap iterators: `get_all_tiles_with_conditions()`, `get_all_objects_with_conditions()`
- Files: `dnd/encounter.py`, `dnd/core/gridmap.py`
- Test: Apply 2-round condition to tile, run 2 full rounds, verify expired after round 2's environment step.

**Phase 1 is a standalone major task.** Must be fully stable before any item work begins.
- Dependencies: Phase 0

### Phase 2: BaseItem + Hierarchy

- New file: `dnd/core/base_item.py` with BaseItem, EquippableItem, UsableItem
- Reparent Weapon, Armor (all subtypes), Shield from `BaseBlock` → `EquippableItem` → `BaseItem` → `BaseBlock`
- Add `blocks_walking()`/`blocks_vision_check()` to BaseBlock with defaults (return False)
- Override in Tile (delegates to existing `walking_cost`/`visible`)
- All existing tests must pass unchanged
- Dependencies: Phase 0

### Phase 3: Equip/Unequip Hooks

- Add hook calls in `Equipment.equip()` and `Equipment.unequip()` at insertion points from Section 5
- Create test items using each approach:
  - Direct modifier: DefenderSword with +1 AC via `_on_equip`
  - Direct action: WandOfFireBolt grants Fire Bolt action
  - Condition: CloakOfProtection grants +1 AC and +1 all saves
- Dependencies: Phase 2

### Phase 4: Inventory Block

- New `Inventory(BaseBlock)` class — flat peer to Equipment on Entity
- Add `inventory` field to Entity
- Add Entity orchestration methods (`loot_item`, `drop_item`, `equip_item`, `unequip_item`)
- Test: add items, remove items, weight tracking, transfers
- Dependencies: Phase 2

### Phase 5: GridMap/Senses for Objects

- Add object registries to GridMap (`_object_positions`, `_objects_by_position`)
- Add `place_object`/`remove_object`/`get_objects_at`/`get_object_position`
- Update `is_walkable_for()`/FOV to check objects via `blocks_walking`/`blocks_vision_check`
- Add `objects` field to Senses
- Update `Entity.update_entity_senses()` to populate `senses.objects`
- Test: place chest, verify entity sees it, verify movement blocked by door
- Dependencies: Phase 2

### Phase 6: Use Actions (Environment Objects First)

- Implement `get_use_actions()` on UsableItem
- Add `source_item_uuid` to BaseAction
- First items: Lever (removes dangerous terrain), Door (toggles spatial blocking)
- Integrate with `get_available_actions()` (source 3: environment objects via `senses.objects`, ≤5ft)
- Test: place lever, move entity adjacent, verify "Pull Lever" appears, execute it
- Dependencies: Phase 2, Phase 5

### Phase 7: Inventory Use Actions

- Integrate inventory actions with `get_available_actions()` (source 2: `inventory.get_all_use_actions`)
- Update `execute_by_index()` for three-source search (registered → inventory → environment)
- Add consumable destruction in `BaseAction.apply()` after `_apply_costs()`
- Create test items: Potion of Healing (consumable, SELF), Scroll of Fireball (wraps SpellAction)
- Dependencies: Phase 4, Phase 6

### Phase 8: Breakable Objects

- Health on BaseItem, `receive_damage`, `_on_destroy`
- AttackObject action registered via `setup_standard_actions`
- AoE `include_objects` flag (optional, incremental)
- Test: wooden door with HP, attack it, break it, verify spatial state changes
- Dependencies: Phase 5

### Phase 9: Looting

- Create loot body on death (simplified, defer full entity→body transitions)
- LootAction for item transfer from body Inventory to entity Inventory
- PickUpAction for items on ground
- Dependencies: Phase 4, Phase 5

### Phase 10: Integration Tests

- Full item lifecycle: create → place on ground → loot → equip → unequip → drop → loot by another
- Magic item: equip ring → +1 AC → unequip → AC back to normal
- Weapon scoping: equip +1 sword → verify +1 only on that weapon's attacks
- Condition on item: Magic Weapon spell on weapon → break concentration → verify condition removed via tree
- Environment: lever removes terrain, door opens/closes
- Breakable: door with HP → attack → break → permanent open
- Consumable: potion in inventory → drink → HP healed → potion destroyed
- Environment turn: tile condition with 3-round duration → verify decrements each round → removed after 3
- Dependencies: All phases

### Dependency Graph

```
Phase 0 (Fix CLAUDE.md)
    │
Phase 1 (Condition Mgmt Refactor + Environment Step) ── MAJOR
    │   Steps 1.1-1.5: delicate, test after each step
    │   Must be fully stable before proceeding
    │
Phase 2 (BaseItem + Hierarchy)
    ├── Phase 3 (Equip Hooks)
    ├── Phase 4 (Inventory)
    ├── Phase 5 (GridMap/Senses)
    │       ├── Phase 6 (Use Actions / Env Objects)
    │       ├── Phase 8 (Breakable)
    │       └── Phase 9 (Looting)
    └── Phase 7 (Inventory Use Actions) ← depends on Phase 4 + Phase 6
                                                       │
Phase 10 (Integration Tests) ← depends on all phases
```

---

## 15. Appendix — Terminology

| Term | Definition |
|------|-----------|
| **BaseItem** | Foundation class for all items. Handles gridmap presence, looting, destruction, optional Health. |
| **EquippableItem** | Item that occupies an equipment slot. Manages effects via `_equip`/`_unequip` hooks. |
| **UsableItem** | Item that provides actions via `get_use_actions()`. Can be consumable. |
| **Environment Object** | A UsableItem with `is_pickable=False`. Lives on GridMap, offers interaction actions. |
| **Equip Hook** | `_on_equip`/`_on_unequip` — item-anchored callbacks. Can use direct modifiers, action registration, or conditions. |
| **Use Action** | An action provided by a UsableItem, discovered at query time via `get_use_actions()`. |
| **Inventory Action** | A Use action discovered from `entity.inventory.get_all_use_actions()` at query time. Never registered on entity. |
| **Consumable** | A UsableItem destroyed after its action completes. Destruction handled in `BaseAction.apply()`. |
| **Loot Body** | A `UsableItem(is_pickable=False)` placed on GridMap at death position with Inventory. Offers "Loot" action. |
| **Level 1 Modifier** | Weapon-inherent ModifiableValue (`weapon.attack_bonus`, `weapon.damage_bonus`). Auto-scoped to one weapon. |
| **Level 2 Modifier** | Equipment-wide ModifiableValue (`equipment.attack_bonus`, `equipment.ac_bonus`). Affects all weapons/defense. |
| **Level 3 Modifier** | Event handler (dice manipulation). Registered via conditions or hooks. |
| **Canonical Slot** | Equipment slot with dedicated calculation path (weapon, body armor, shield). Inherent stats consumed automatically. |
| **Non-Canonical Slot** | Equipment slot without dedicated path (ring, cloak, amulet, etc.). Effects delivered via `_equip` hooks. |
| **Environment Step** | New encounter lifecycle phase after all entity turns. Progresses tile and floor object conditions. |
