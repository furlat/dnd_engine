# Items & Inventory System — Design Document

This document describes the complete design for items, inventory, and environment objects. Every decision is final — no unresolved options.

---

## Implementation Status

| Section | Status | Notes |
|---------|--------|-------|
| 4. BaseItem | **IMPLEMENTED** | `dnd/blocks/base_item.py`. Location tracking (`tile_uuid`, `stored_in_uuid`, `get_position()`), lifecycle hooks with params, Health delegation, spatial overrides. 85 tests. |
| 5. EquippableItem | **IMPLEMENTED** | `_on_equip(slot, entity_uuid)`/`_on_unequip(slot, entity_uuid)` hooks. Weapon/Armor/Shield reparented. `owner_uuid`, `stored_in_uuid`, `is_equipped` tracking. 15 tests. |
| 6. UsableItem | **IMPLEMENTED** | `get_use_actions()`, `consume_charge()`, `use_action_templates` field, charges system. Environment discovery in `get_available_actions()`. 19 tests. |
| 7. Inventory | **IMPLEMENTED** | `dnd/blocks/inventory.py`. All methods including `get_all_use_actions()`. `transfer_to()` updates `stored_in_uuid`. |
| 8. Entity Orchestration | **IMPLEMENTED** | `loot_item`/`drop_item` + `equip_item`/`unequip_item` done with full location tracking (`owner_uuid`, `stored_in_uuid`, `is_equipped`). |
| 9. GridMap/Senses | **IMPLEMENTED** | Object registries, spatial predicates, FOV, `senses.objects`. |
| 10. Action System | **Partial** | PickUp/AttackObject/Drop done. Environment use action discovery done (source 3). `execute_use_action()` + `execute_by_index()` routing done. Inventory use actions (source 2) = Step d. |
| 11. Conditions on Items | **Partial** | Infrastructure done (items as condition hosts, linked cleanup). Item condition ticking deferred. |
| 12. Breakable Objects | **IMPLEMENTED** | Health delegation, `receive_damage`, `destroy`, AttackObject action. |
| 13. Looting System | Deferred | Entity→body transitions deferred. |
| 14. Implementation Steps | **Steps a–c DONE** | See restructured section. |

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Foundation](#2-foundation)
3. [Item Class Hierarchy](#3-item-class-hierarchy)
4. [BaseItem — The Foundation](#4-baseitem--the-foundation)
5. [EquippableItem — Gear & Equipment](#5-equippableitem--gear--equipment)
6. [UsableItem — Actions & Environment Objects](#6-usableitem--actions--environment-objects)
7. [Inventory Block](#7-inventory-block)
8. [Entity Orchestration](#8-entity-orchestration)
9. [GridMap & Senses Integration](#9-gridmap--senses-integration)
10. [Action System Integration](#10-action-system-integration)
11. [Conditions on Items](#11-conditions-on-items)
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

## 2. Foundation

This section describes the infrastructure that items build on — already implemented and tested.

### Polymorphic Spatial Blocking

BaseBlock provides polymorphic `blocks_walking()` and `blocks_vision()` methods with default `False` returns. Tile and Entity override these:

- **Tile**: `blocks_walking()` → `self.get_movement_cost(mode) <= 0`; `blocks_vision()` → `not self.visible`
- **Entity**: `blocks_walking()` → checks `self.non_blocking` flag and self-avoidance (`requesting_entity_uuid == self.uuid`)
- **GridMap predicates** (`is_walkable`, `is_walkable_for`, `is_blocking`, `is_visible`) all dispatch through these polymorphic methods

BaseItem will add its own overrides (see Section 4).

### Condition Management on BaseBlock

BaseBlock is the condition host for all block types (entities, tiles, and future items). The full condition lifecycle lives on BaseBlock:

- `add_condition()` / `remove_condition()` with full tree traversal via `_remove_condition_tree()`
- `remove_condition_by_uuid()` for cross-block cleanup
- `advance_duration(condition_name)` for simple duration ticking (no saving throws)
- Entity overrides `add_condition()` to add immunity checks and application saving throws
- Entity has `advance_duration_condition(condition_name)` for duration ticking WITH removal saving throws

**Tree cleanup** (`_remove_condition_tree()`) handles:
1. `sub_conditions` — child conditions on the same block (parent-child)
2. `linked_conditions` — conditions on OTHER blocks via `BaseBlock.get(target_uuid)` (works for entities, tiles, and items)
3. `cleanup_own_state()` — removes own modifiers and handlers

### Environment Step

`Encounter._environment_step()` runs at the end of each round, advancing tile condition durations. Uses `GridMap.get_tiles_with_conditions()`. Currently handles tiles only — needs extension for floor items (see Section 11).

### Modifier Scoping Architecture

The engine has a three-level modifier scoping system for attack and damage:

**Level 1 — Weapon-inherent modifiers** (scoped to ONE weapon automatically):
- `weapon.attack_bonus: ModifiableValue` — created in weapon factories
- `weapon.damage_bonus: Optional[ModifiableValue]` — defaults to None, created for magic weapons
- These are automatically selected by `Entity._get_attack_bonuses(weapon_slot)` which picks the ACTIVE weapon's own ModifiableValues
- A +1 sword is simply created with `base_value=1` on attack_bonus and damage_bonus. **No equip hook needed.**

**Level 2 — Equipment-wide modifiers** (global or weapon-type scoped):
- `equipment.attack_bonus` — applies to ALL attacks
- `equipment.melee_attack_bonus` / `equipment.ranged_attack_bonus` — weapon-type scoped
- `equipment.damage_bonus` / `equipment.melee_damage_bonus` / `equipment.ranged_damage_bonus`
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

### Current Item Classes

`Weapon`, `Armor` (Helmet, BodyArmor, Gauntlets, Greaves, Boots, Amulet, Ring, Cloak), `Shield` — all inherit `EquippableItem` → `BaseItem` → `BaseBlock`. Equipment block has 13 typed slots and 19+ ModifiableValues, with equip/unequip events and item hooks (`_on_equip`/`_on_unequip`).

---

## 3. Item Class Hierarchy

### The Resolved Three-Class Model

```
BaseItem(BaseBlock)                          ← dnd/blocks/base_item.py
│   Core: gridmap presence, looting, destruction, optional Health
│   Flags: is_pickable=True, is_equippable=False, is_usable=False
│   Hooks: _on_loot(), _on_drop(), _on_destroy()
│   Fields: weight, value, rarity, tags, stack_count, max_stack
│   Spatial: blocks_movement, blocks_vision_field (for when on ground)
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

**File location**: `dnd/blocks/base_item.py` — **IMPLEMENTED**

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
    blocks_vision_field: bool = False

    # Breakable (Section 12)
    is_targetable: bool = False
    health: Optional[Health] = None
    damage_immunities: List[DamageType] = [DamageType.POISON, DamageType.PSYCHIC]
    damage_reduction: Dict[str, int] = {}  # material-based, e.g. {"bludgeoning": 5}

    # Tracking
    equipped_slot: Optional[Any] = None  # Which slot this is in (None if not equipped)

    # Location tracking (Step a)
    tile_uuid: Optional[UUID] = None         # UUID of tile at position (set when on floor)
    stored_in_uuid: Optional[UUID] = None    # UUID of entity/item whose Inventory holds this
```

### Location Tracking — **IMPLEMENTED (Step a)**

Three location states tracked via `tile_uuid` and `stored_in_uuid`:

| State | `tile_uuid` | `stored_in_uuid` | `position` |
|-------|-------------|-------------------|------------|
| On floor | tile's UUID | `None` | `(x, y)` set by Entity.drop_item |
| In inventory | `None` | owner entity UUID | stale (ignore) |
| Nowhere (just created) | `None` | `None` | `(0, 0)` default |

**`get_position()`** — smart accessor, always use this instead of `self.position`:
```python
def get_position(self) -> Optional[Tuple[int, int]]:
    if self.stored_in_uuid is not None:
        container = BaseBlock.get(self.stored_in_uuid)
        if container is None:
            return None
        if isinstance(container, BaseItem):
            return container.get_position()  # Nested storage (chest in chest)
        return container.position  # Entity or other BaseBlock
    if self.tile_uuid is not None:
        # On floor — verify consistency with GridMap (raises ValueError on mismatch)
        gridmap_pos = get_map().get_object_position(self.uuid)
        if gridmap_pos != self.position:
            raise ValueError(f"Item position mismatch: self.position={self.position}, GridMap={gridmap_pos}")
        return self.position
    return None  # Not placed anywhere
```

**Who sets location fields** — Entity is the orchestrator:
- `Entity.loot_item()`: sets `stored_in_uuid = self.uuid`, clears `tile_uuid`
- `Entity.drop_item()`: sets `item.position`, `tile_uuid`, clears `stored_in_uuid`
- `Inventory.transfer_to()`: updates `stored_in_uuid` to new owner
- `BaseItem.destroy()`: clears both fields during cleanup

### Lifecycle Hooks — **IMPLEMENTED (Step a)**

Public + private pattern with explicit parameters. Items in `dnd/blocks/` cannot import Entity — the caller passes what the hook needs:

```python
    def loot(self, entity_uuid: UUID, inventory_uuid: UUID) -> None:
        """Called by Entity.loot_item() when item enters inventory."""
        self._on_loot(entity_uuid, inventory_uuid)

    def _on_loot(self, entity_uuid: UUID, inventory_uuid: UUID) -> None:
        """Override for item-specific loot behavior (e.g., cursed item applies condition)."""
        pass

    def drop(self, entity_uuid: UUID, position: Tuple[int, int]) -> None:
        """Called by Entity.drop_item() when item leaves inventory to ground."""
        self._on_drop(entity_uuid, position)

    def _on_drop(self, entity_uuid: UUID, position: Tuple[int, int]) -> None:
        pass

    def destroy(self) -> None:
        """Remove item from all registries. Called for consumables and broken objects."""
        self._on_destroy()
        # Clean up conditions on this item
        for cond_name in list(self.active_conditions.keys()):
            self.remove_condition(cond_name)
        # Clear location fields
        self.tile_uuid = None
        self.stored_in_uuid = None
        # Remove from GridMap if placed
        gridmap = get_map()
        if gridmap.get_object_position(self.uuid) is not None:
            gridmap.remove_object(self.uuid)
        # Remove from registry
        BaseBlock._registry.pop(self.uuid, None)

    def _on_destroy(self) -> None:
        """Override for item-specific destruction behavior (chest spills contents, etc.)."""
        pass
```

`destroy` is on BaseItem (not just UsableItem) because both consumable UsableItems and breakable BaseItems need destruction — shared foundation.

### The UUID Pattern

Hooks receive `entity_uuid` as an explicit parameter — no need to rely on `self.source_entity_uuid` for loot/drop context. Concrete subclasses (which live in high-level modules that CAN import Entity) call `Entity.get(entity_uuid)` in their hook bodies. BaseItem in `dnd/blocks/` never imports Entity.

### Spatial Methods

BaseBlock already provides `blocks_walking()` and `blocks_vision()` with default `False` returns. BaseItem overrides them to delegate to its fields:

```python
    def blocks_walking(self, requesting_entity_uuid: Optional[UUID] = None,
                       mode: MovementMode = MovementMode.WALKING) -> bool:
        return self.blocks_movement

    def blocks_vision(self, requesting_entity_uuid: Optional[UUID] = None) -> bool:
        return self.blocks_vision_field
```

### Dependency Direction

```
Entity → BaseItem → BaseBlock → BaseModel
```
BaseItem lives in `dnd/blocks/` at same level as other blocks. Imports `get_map()` from `dnd/core/gridmap.py` (downward, blocks → core). GridMap never imports BaseItem (uses BaseBlock polymorphism). Safe dependency direction.

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

## 6. UsableItem — Actions & Environment Objects — **IMPLEMENTED**

**File**: `dnd/blocks/base_item.py`

Inherits BaseItem, sets `is_usable = True`. Two usage patterns supported:

```python
class UsableItem(BaseItem):
    is_usable: bool = True
    is_consumable: bool = False  # Destroy when charges reach 0

    # Charges
    charges: int = -1       # -1 = unlimited, 0 = depleted
    max_charges: int = -1   # -1 = unlimited

    # Default pattern: stored action templates
    use_action_templates: List[BaseAction] = []

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """Default: returns stored templates with source_entity_uuid and
        source_item_uuid injected. Returns [] if charges == 0.
        Override in subclasses for adaptive behavior."""

    def consume_charge(self) -> bool:
        """Consume one charge. Returns False if depleted.
        Destroys item if is_consumable and charges reach 0."""
```

### Two Usage Patterns

**Pattern 1 — Default `use_action_templates` field** (simpler, no subclass override needed):
```python
# Create item with action templates in the field:
lever = TrapLever(
    use_action_templates=[PullLeverAction(source_entity_uuid=uuid4(), template=True)],
    charges=1,
)
# get_use_actions() auto-injects source_entity_uuid + source_item_uuid via model_copy
```

**Pattern 2 — Override `get_use_actions()`** (for state-dependent action names/types):
```python
class Door(UsableItem):
    is_open: bool = False

    def get_use_actions(self, user_entity_uuid):
        if self.is_open:
            return [CloseDoorAction(source_entity_uuid=user_entity_uuid,
                                    source_item_uuid=self.uuid, template=True)]
        return [OpenDoorAction(source_entity_uuid=user_entity_uuid,
                               source_item_uuid=self.uuid, template=True)]
```

Pattern 1 is preferred when the action name doesn't need to change with state. Pattern 2 is for items where different states surface different action classes/names.

### Charge System

- `charges=-1`: unlimited uses (default)
- `charges=N`: N uses remaining, decremented by `consume_charge()` after successful action execution
- `charges=0`: depleted — `get_use_actions()` returns `[]`
- `is_consumable=True`: item destroyed when charges reach 0

Charge consumption is automatic — `execute_use_action()` calls `item.consume_charge()` after a successful apply.

### Environment Objects = `UsableItem(is_pickable=False)`

No WorldObject class needed. Test items in `dnd/items/test_items.py`:

| Item | Pattern | Key Behavior |
|------|---------|-------------|
| TestDoorA | Override | State-dependent action names (Open Door / Close Door) |
| TestDoorB | Default | Single toggle action (Interact Door) |
| TrapLever | Default + charges=1 | Removes spatial handler, one-shot |
| StorageChest | Default + unlimited | LootAllAction transfers items, `_on_destroy` spills contents |
| Campfire | Default + multi-action | Two templates: RestAction (heal), CookAction (temp HP) |

### Environment Discovery Flow

In `Entity.get_available_actions()`, after OBJECT actions section:
1. Iterate `senses.objects`
2. Filter to `isinstance(obj, UsableItem)` within 5ft
3. Call `obj.get_use_actions(self.uuid)` for each
4. For SELF-target actions: `pre_validate()`, add to `result.self_actions` with `is_item_use=True`

### Execution Flow

`execute_use_action(entity, item_uuid, action_name, target)` in `actions_functional.py`:
1. Get item via `BaseBlock.get()`, verify `UsableItem`
2. Get templates via `item.get_use_actions(entity.uuid)`
3. Find matching template by name
4. `instantiate()` → `apply()` → `item.consume_charge()` on success

`execute_by_index()` routes `is_item_use` actions to `execute_use_action()` automatically.

### `source_item_uuid` Field

`source_item_uuid: Optional[UUID] = None` on `BaseAction`. Injected by `get_use_actions()`. `is_item_use: bool` + `source_item_uuid: Optional[UUID]` on `AvailableActionInfo` for UI routing.

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

## 8. Entity Orchestration — **IMPLEMENTED (Steps a + b)**

Entity wraps equip/unequip/loot/drop. Equipment and Inventory don't know about each other. Entity is the orchestrator that sets location fields and passes hook parameters.

```python
# On Entity — IMPLEMENTED (Step a):
def loot_item(self, item: BaseItem) -> bool:
    """Pick up item into inventory. Sets location fields, calls hook with params."""
    if not self.inventory.can_add(item):
        return False
    item.source_entity_uuid = self.uuid
    self.inventory.add_item(item)
    item.stored_in_uuid = self.uuid       # Location: now stored in this entity
    item.tile_uuid = None                  # No longer on floor
    gridmap = get_map()
    if gridmap.get_object_position(item.uuid) is not None:
        gridmap.remove_object(item.uuid)   # Remove from grid
    item.loot(entity_uuid=self.uuid, inventory_uuid=self.inventory.uuid)
    return True

def drop_item(self, item_uuid: UUID, position: Optional[Tuple[int, int]] = None) -> Optional[BaseItem]:
    """Drop item from inventory to ground. Position defaults to entity position, can be adjacent."""
    item = self.inventory.remove_item(item_uuid)
    if item is None:
        return None
    drop_pos = position if position is not None else self.position
    gridmap = get_map()
    tile = gridmap.get_tile(drop_pos[0], drop_pos[1])
    item.stored_in_uuid = None             # No longer stored
    item.position = drop_pos               # Update inherited BaseBlock.position
    item.tile_uuid = tile.uuid if tile else None
    gridmap.place_object(item.uuid, drop_pos)
    item.drop(entity_uuid=self.uuid, position=drop_pos)
    return item

# On Entity — NOT YET IMPLEMENTED (Step b):
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

**Drop action** (`dnd/actions.py`): Refactored to `TargetType.POSITION_LOS` with `item_uuid` bound at creation. Valid positions = entity position + adjacent visible cells within 5ft. Same pattern as future Use actions — actions created on the fly, bound to a specific item.

---

## 9. GridMap & Senses Integration

### 9.1 Existing Spatial Infrastructure

The polymorphic spatial interface is in place:

- `blocks_walking()` / `blocks_vision()` on BaseBlock with defaults (`False`)
- Tile overrides delegate to `get_movement_cost()` and `visible`
- Entity override checks `non_blocking` flag and self-avoidance
- GridMap predicates (`is_walkable`, `is_walkable_for`, `is_blocking`, `is_visible`) all use polymorphic dispatch
- **BaseItem will override** `blocks_walking()` → `return self.blocks_movement` and `blocks_vision()` → `return self.blocks_vision_field`

When items are added to the grid, the same polymorphic dispatch handles them with no predicate changes.

### 9.2 Object Registries (to build)

GridMap needs new registries for items on the ground:

```python
_object_positions: Dict[UUID, Tuple[int, int]] = {}
_objects_by_position: DefaultDict[Tuple[int, int], Set[UUID]] = defaultdict(set)
```

New methods:
- `place_object(item_uuid, position)` — register object on grid
- `remove_object(item_uuid)` — unregister from grid
- `get_objects_at(position) → Set[UUID]` — objects at position
- `get_object_position(item_uuid) → Optional[Tuple[int, int]]`
- `get_objects_with_conditions() → List[BaseItem]` — for environment step (analogous to `get_tiles_with_conditions()`)

Updates to existing methods:
- `is_walkable_for()` — also check `_objects_by_position[(x,y)]`, call `obj.blocks_walking(requesting_entity_uuid)`
- FOV computation — also check objects via `blocks_vision()`

### 9.3 Senses (to build)

Add `objects: Dict[UUID, Tuple[int, int]]` field to Senses (same pattern as `entities`). `Entity.update_entity_senses()` queries GridMap for visible objects, populates `senses.objects`. Senses does NOT import BaseItem — stores UUID + position only.

### 9.4 Door Toggle Example

`Door.open()` sets `blocks_movement=False`, `blocks_vision_field=False`, triggers senses update for nearby entities.

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

## 11. Conditions on Items

### 11.1 Condition Infrastructure

BaseBlock is the condition host for all block types. The condition management API on BaseBlock:

- **`add_condition(condition)`** — registers condition in `active_conditions`, calls `condition.apply()`. Entity overrides to add immunity check + saving throw.
- **`remove_condition(name)`** — calls `_remove_condition_tree()` for full cleanup:
  1. Recurses into `sub_conditions` (same block, parent-child)
  2. Follows `linked_conditions` to OTHER blocks via `BaseBlock.get(target_uuid)` — works for entities, tiles, and items
  3. Calls `condition.cleanup_own_state()` for modifiers/handlers
- **`remove_condition_by_uuid(uuid)`** — UUID-based lookup → delegates to `remove_condition(name)`. Used for cross-block cleanup.
- **`advance_duration(condition_name)`** — decrements duration, removes if expired. No saving throws. Returns `True` if removed.
- **`linked_conditions: List[Tuple[UUID, UUID]]`** on BaseCondition stores `(target_block_uuid, condition_uuid)` pairs. Added via `add_linked_condition()`. This is the mechanism for cross-object condition cleanup.

Entity adds:
- `add_condition()` override — immunity check + application saving throw
- `advance_duration_condition(condition_name)` — duration ticking WITH removal saving throws

Environment step: `Encounter._environment_step()` advances tile condition durations at round end via `GridMap.get_tiles_with_conditions()`.

### 11.2 Items as Condition Hosts

Since BaseItem inherits BaseBlock, every item automatically gets:
- `active_conditions` dict
- `add_condition()` / `remove_condition()` with full tree traversal
- `advance_duration()` for simple duration ticking
- Registration in `BaseBlock._registry` — findable via `BaseBlock.get(item.uuid)`

**Spells can target items directly.** Magic Weapon targets a weapon, not the entity. The condition lives ON the weapon block:

```python
# Magic Weapon spell: condition targets the WEAPON, not the entity
class MagicWeaponCondition(BaseCondition):
    name: str = "MagicWeaponCondition"

    def _apply(self, declaration_event):
        weapon = BaseBlock.get(self.target_entity_uuid)  # target is actually a weapon
        modifier_uuid = weapon.attack_bonus.self_static.add_value_modifier(
            NumericalModifier(name="Magic Weapon", value=1, ...)
        )
        # Also add to damage_bonus if weapon has one
        return [(weapon.attack_bonus.uuid, modifier_uuid)], [], [], [], effect_event
```

**Cross-object cleanup chain** (the key pattern):

```
Caster: Concentrating(spell_name="Magic Weapon")
            │ linked_conditions → (weapon.uuid, magic_weapon_cond.uuid)
            └──► Weapon: MagicWeaponCondition
                        │ modifiers on weapon.attack_bonus, weapon.damage_bonus
```

When concentration breaks:
1. `caster.remove_condition("Concentrating")` fires
2. `_remove_condition_tree()` follows `linked_conditions`
3. `BaseBlock.get(weapon_uuid)` finds the weapon (it's in `BaseBlock._registry`)
4. `weapon.remove_condition_by_uuid(magic_weapon_cond_uuid)` removes it
5. `cleanup_own_state()` removes the modifiers from weapon.attack_bonus

This works with zero changes to the condition infrastructure — the only prerequisite is Weapon inheriting BaseBlock (which it already does, and will continue to via BaseItem → BaseBlock).

### 11.3 Equip-Driven Conditions

When an equipped item's `_on_equip` hook applies a condition on the ENTITY:

```python
class CloakOfProtection(EquippableItem):
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

**Key point**: The condition lives on the ENTITY, not the item. The item's `_on_unequip` is responsible for removal. No `linked_conditions` needed here — the hook handles lifecycle directly.

**When to use `linked_conditions` instead**: If the item itself has a condition (e.g., a cursed item where the curse lives on the item and the effect lives on the entity), link them:

```python
class CursedSword(EquippableItem):
    def _on_equip(self, slot):
        entity = Entity.get(self.source_entity_uuid)
        # Curse condition on the ITEM
        curse_condition = CursedSwordCurse(source_entity_uuid=self.source_entity_uuid, ...)
        self.add_condition(curse_condition)  # Condition on the item block
        # Effect condition on the ENTITY
        effect = CursedSwordEffect(source_entity_uuid=self.source_entity_uuid,
                                    target_entity_uuid=self.source_entity_uuid)
        entity.add_condition(effect)
        # Link them: destroying the item cleans up the entity effect
        curse_condition.add_linked_condition(entity.uuid, effect.uuid)
```

### 11.4 Item Destruction and Condition Cleanup

When `item.destroy()` is called:
1. Iterates `active_conditions` and calls `remove_condition()` for each
2. Each removal triggers `_remove_condition_tree()`
3. Any `linked_conditions` pointing to other blocks (entities, tiles) get cleaned up automatically

This means: a magic item with buffs on its wielder will properly clean up those buffs when the item is destroyed. No manual cleanup code needed in `_on_destroy()` IF the conditions were linked via `linked_conditions`.

### 11.5 Condition Progression — Two Tracks

| Track | What | When | How |
|-------|------|------|-----|
| **Entity turn** | Entity's own conditions | During `on_turn_start()` | `Entity.advance_duration_condition()` (with saves) |
| **Entity turn** | Conditions on equipped/inventory items | During `on_turn_start()` | Entity iterates items, calls `item.advance_duration(cond_name)` — **needs implementing** |
| **Environment step** | Conditions on tiles | End of full round | `Encounter._environment_step()` — **exists today** |
| **Environment step** | Conditions on floor items | End of full round | Extend `_environment_step()` — **needs implementing** |

**What needs building:**
- Entity's `on_turn_start()` needs to iterate equipped items and inventory items, calling `advance_duration()` on their conditions
- `_environment_step()` needs to also iterate floor objects (once GridMap has object registries)
- GridMap needs `get_objects_with_conditions()` (analogous to existing `get_tiles_with_conditions()`)

**Round lifecycle:**
```
Round N:
  Entity 1 Turn (advance entity conds + equipped/inventory item conds)
  Entity 2 Turn → ... → Entity N Turn
  → ROUND_END event
  → ENVIRONMENT STEP
      1. Tile conditions advance_duration()
      2. Floor item conditions advance_duration()
      3. Environmental dynamics (fire spreads, objects react)
  → round_number++
  → ROUND_START event
```

### 11.6 When to Use Conditions vs Direct Modifiers

- `_equip`/`_unequip` can directly add/remove modifiers — no condition needed for simple static bonuses
- Use conditions when you need: event handlers, sub-conditions, expiration/duration, cross-entity cleanup, removal saving throws
- A Defender Sword's +1 AC from `_equip` hook: direct modifier on `equipment.ac_bonus`
- A cursed sword that blocks unequip: condition with event handler on WEAPON_UNEQUIP
- A Cloak of Protection (+1 AC + +1 all saves): condition pattern (many modifiers across many ModifiableValues — condition provides centralized tracking for cleanup)

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

## 14. Implementation Steps

> Replaces the original 9-phase plan. Phase 1 core infrastructure (BaseItem, Inventory, GridMap object registries, Senses, PickUp/AttackObject/Drop actions, Breakable) is complete with 85 tests.

### Step a: Item Location Tracking + Lifecycle Hooks — **DONE**

- Added `tile_uuid`, `stored_in_uuid` fields to BaseItem for location tracking
- Added `get_position()` smart accessor (floor → own position with GridMap consistency check, inventory → container's position, nowhere → None)
- Fixed hook signatures: `loot(entity_uuid, inventory_uuid)`, `drop(entity_uuid, position)` — items can't import Entity, callers pass what hooks need
- Updated `Entity.loot_item()` / `drop_item()` to set location fields and pass hook params
- `drop_item()` accepts optional position (adjacent tiles, distance ≤ 1)
- `Inventory.transfer_to()` updates `stored_in_uuid` to new owner
- Refactored Drop action to `TargetType.POSITION_LOS` with `item_uuid` bound at creation
- Test items with real game effects: OilBarrel (tile conditions on destroy), CursedGem (Poisoned on loot), AuraStone (+2 AC on loot/drop), HealingHerb (heals on loot)
- 22 new tests in `examples/test_items_lifecycle_hooks.py`, all 85 tests pass
- **Files**: `dnd/blocks/base_item.py`, `dnd/entity.py`, `dnd/actions.py`, `dnd/actions_functional.py`, `dnd/blocks/inventory.py`

### Step b: Equip/Unequip Hooks [IMPLEMENTED]

- Reparented Weapon/Armor/Shield → EquippableItem → BaseItem → BaseBlock
- `_on_equip(slot, entity_uuid)` / `_on_unequip(slot, entity_uuid)` hooks in EquippableItem
- Hook calls inserted in Equipment.equip()/unequip() for all slot types
- Location tracking: `owner_uuid` (entity/item), `stored_in_uuid` (inventory/equipment block), `is_equipped` flag
- `Equipment.get_item_by_slot()` for unified slot lookup
- `Equipment.unequip()` returns the unequipped item
- Entity `equip_item()` / `unequip_item()` orchestration (inventory ↔ equipment)
- Moved `BodyPart`, `RingSlot` to `dnd/core/events.py`, added `EquipmentSlot` type alias
- 15 tests in `examples/test_items_equip_hooks.py`:
  - DefenderSword: direct modifier (+1 AC on equipment.ac_bonus)
  - CloakOfProtection: condition pattern (+1 AC + all saves)
  - Flaming sword: reparented weapon with extra fire damage in combat
- Dependencies: Step a

### Step c: UsableItem — Environment Object Discovery [IMPLEMENTED]

- `UsableItem.get_use_actions()` with two patterns: default `use_action_templates` field, or override for state-dependent behavior
- `use_action_templates: List[BaseAction]` field — default `get_use_actions()` returns these with `source_entity_uuid` and `source_item_uuid` injected via `model_copy`
- Charge system: `charges` (-1=unlimited, 0=depleted), `max_charges`, `consume_charge()`, `is_consumable` (destroy on depletion)
- `source_item_uuid` on BaseAction, `is_item_use` + `source_item_uuid` on AvailableActionInfo
- Environment object discovery: `senses.objects` → `isinstance(obj, UsableItem)` → `get_use_actions()`, within 5ft, integrated into `get_available_actions()` after OBJECT actions section
- `execute_use_action()` in `actions_functional.py` — instantiate + apply + consume_charge on success
- `execute_by_index()` routes `is_item_use` actions to `execute_use_action()`
- `Inventory.get_all_use_actions()` ready for Step d
- Test items in `dnd/items/test_items.py`:
  - TestDoorA: override pattern — `get_use_actions()` returns OpenDoorAction or CloseDoorAction based on state
  - TestDoorB: default pattern — `use_action_templates=[InteractDoorAction]`, single toggle action
  - TrapLever: default pattern + charges=1, PullLeverAction removes spatial handler
  - StorageChest: unlimited charges, LootAllAction transfers items, `_on_destroy` spills contents
  - Campfire: plain UsableItem with two action templates (RestAction, CookAction)
- 19 tests in `examples/test_usable_items.py`, all pass
- **Files**: `dnd/blocks/base_item.py`, `dnd/core/base_actions.py`, `dnd/entity.py`, `dnd/actions_functional.py`, `dnd/blocks/inventory.py`, `dnd/items/test_items.py`
- Dependencies: Step a

### Step d: Full Inventory Use Actions [NOT STARTED]

- `Inventory.get_all_use_actions()` for inventory item actions
- Three-source discovery in `get_available_actions()` (registered → inventory → environment)
- `execute_by_index()` three-source search
- Consumable destruction in `BaseAction.apply()` after `_apply_costs()`
- Test items: Potion of Healing (consumable, SELF), Scroll of Fireball
- Dependencies: Step c

### Deferred (future — entity transitions / spawning)

- Loot body on death (entity → body transition, LootAction)
- Encumbrance penalties
- Item condition ticking on entity turn / environment step
- Object AC

### Dependency Graph

```
Step a (Location Tracking + Hooks) ← DONE
    ├── Step b (Equip/Unequip Hooks) ← DONE
    ├── Step c (UsableItem + Environment Objects) ← DONE
    │       └── Step d (Inventory Use Actions)
    └── Deferred (entity transitions, encumbrance)
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
| **Environment Step** | Encounter lifecycle phase after all entity turns. Progresses tile and floor object conditions. |
| **`linked_conditions`** | `List[Tuple[UUID, UUID]]` on BaseCondition. Stores `(target_block_uuid, condition_uuid)` pairs for cross-object condition cleanup. Added via `add_linked_condition()`. |
