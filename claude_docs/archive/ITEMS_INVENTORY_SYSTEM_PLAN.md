# Items, Inventory & Environment Objects — Design Document

This document explores the design space for the item/inventory/environment object system. It is **exploratory**, not prescriptive — it presents multiple options for the hardest problems and stress-tests each idea with concrete examples. The goal is to capture philosophical design thinking so that when implementation starts, every major tension has already been identified and weighed.

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [D&D 5e Rules Reference](#2-dd-5e-rules-reference)
3. [The Three Orthogonal Traits](#3-the-three-orthogonal-traits)
4. [BaseItem Architecture](#4-baseitem-architecture)
5. [The Use Action Interface (Deep Dive)](#5-the-use-action-interface-deep-dive)
6. [Equip/Unequip Hooks (Separate from Use)](#6-equipunequip-hooks-separate-from-use)
7. [Inventory Block](#7-inventory-block)
8. [GridMap and Senses Integration](#8-gridmap-and-senses-integration)
9. [Environment Objects Design](#9-environment-objects-design)
10. [Looting System](#10-looting-system)
11. [Integration with get_available_actions](#11-integration-with-get_available_actions)
12. [Implementation Phases](#12-implementation-phases)
13. [Conditions on Items](#13-conditions-on-items)
14. [Breakable/Targetable Objects](#14-breakabletargetable-objects)
15. [Inventory as Action Manager](#15-inventory-as-action-manager)
16. [Equipment.py Separation — Equipment Contains Inventory](#16-equipmentpy-separation--equipment-contains-inventory)

---

## 1. Current State Analysis

### What Exists Today

#### Item Hierarchy — No Shared Base

The current codebase has three equipment types, all inheriting directly from `BaseBlock` with no shared item abstraction:

```
BaseBlock (dnd/core/base_block.py)
├── Weapon   (dnd/blocks/equipment.py:224)  — damage_dice, properties, range, attack_bonus
├── Armor    (dnd/blocks/equipment.py:98)   — type, body_part, ac, max_dex_bonus, requirements
│   ├── Helmet, BodyArmor, Gauntlets, Greaves, Boots
│   ├── Amulet, Ring, Cloak
└── Shield   (dnd/blocks/equipment.py:212)  — ac_bonus
```

**What's missing**: No shared fields for weight, value, rarity, usability, or pickup semantics. A `Weapon` and an `Armor` share no interface beyond `BaseBlock`. There is no concept of an "item" that exists independently of being equipped.

#### Equipment Block — Slots and Bonuses, No Item Hooks

`Equipment` (`dnd/blocks/equipment.py:387`) is a `BaseBlock` that holds typed slots:

- 9 armor slots: helmet, body_armor, gauntlets, greaves, boots, amulet, ring_left, ring_right, cloak
- 4 weapon slots: weapon_melee_main, weapon_melee_off (can hold Shield), weapon_ranged_main, weapon_ranged_off
- Numerous `ModifiableValue` combat bonuses (ac_bonus, attack_bonus, damage_bonus, crit thresholds, etc.)

**`Equipment.equip()` flow** (lines 663–824):
1. Update item's `source_entity_uuid` to match equipment owner
2. Handle type-specific slot logic (Ring→ring slot, Shield→MELEE_OFF, Weapon→auto-detect)
3. Auto-unequip existing item in slot if occupied
4. Create equip event (`WeaponEquipEvent`/`ArmorEquipEvent`/`ShieldEquipEvent`)
5. If event canceled at EXECUTION → return early (handlers can block equip)
6. Assign item to slot field
7. Phase to EFFECT → COMPLETION

**`Equipment.unequip()` flow** (lines 826–894): mirrors equip — creates unequip event, phases through lifecycle, sets slot to None.

**Critically absent**: There is no `_on_equip()` or `_on_unequip()` call anywhere. The equip event fires and handlers can react, but the item itself has no hook. This is where equip hooks would be inserted — between step 6 (slot assignment) and step 7 (EFFECT phase).

#### Action Template System — Deep Mechanics

The action system (`dnd/core/base_actions.py`) is template-based:

1. **Registration**: `entity.register_action(MyAction(source_entity_uuid=..., template=True))` — stored in `entity.registered_actions` (line 1679 of `entity.py`)
2. **Query**: `entity.get_available_actions()` (lines 1721–2013) iterates over templates grouped by `target_type`:
   - SELF actions: validate once, single target index=0
   - ENTITY actions: `set_target_entity()` → `pre_validate()` per visible entity
   - POSITION_PATH: `set_target_position()` → `pre_validate()` per reachable path
   - POSITION_LOS: `template.get_valid_positions()` → validate per position
   - POSITION_AOE: `shape.compute_subjective()` → filter entities → validate per position
3. **Execution**: `execute_by_index()` finds template by name, finds target by index, calls `template.instantiate(**overrides)` → `instance.apply()` — the instance is ephemeral (line 431: `use_register=False`)
4. **Result**: `AvailableActionsResult` (line 775) groups into `entity_actions`, `position_actions`, `self_actions`, each containing `AvailableActionInfo` with `valid_targets`, `can_afford`, `is_attack`, `is_spell` flags

**This is the system Use actions must integrate into.** The consumer (AI or UI) sees a flat list of actions with targets — items must collapse into this same shape.

#### GridMap — No Object Concept

`GridMap` (`dnd/core/gridmap.py`) tracks tiles and entity positions:

```python
_tiles: Dict[Tuple[int,int], Tile]                    # line 39
_entity_positions: Dict[UUID, Tuple[int,int]]          # line 52
_entities_by_position: DefaultDict[Tuple[int,int], Set[UUID]]  # line 51
_non_blocking_entities: Set[UUID]                      # line 62
```

`is_walkable()` (line 257) checks tile movement cost. `is_walkable_for()` (line 271) also checks entity occupancy. `is_blocking()` (line 304) checks tile vision. `move_entity()` (line 468) fires `SPATIAL_ENTITY_ENTERED` and `SPATIAL_ENTITY_LEFT` events.

**There is no object registry.** A sword on the floor, a chest, or a lever have no spatial representation.

#### Senses — No Object Visibility

`Senses` (`dnd/blocks/sensory.py:21`) tracks:

```python
entities: Dict[UUID, Tuple[int,int]]  # Visible entities
visible: Dict[Tuple[int,int], bool]   # Visible cells
paths: DefaultDict[...]               # Reachable cells
```

No `objects` field. A potion on the ground is invisible to the system.

#### "Magic Item" Precedent — Circus Fighter Weapon Creation

`dnd/monsters/circus_fighter.py` shows how magic item effects work today as **direct weapon construction**:

- `create_longsword_plus_one()` (line 117): Sets `attack_bonus` and `damage_bonus` to `ModifiableValue.create(base_value=1)` — a +1 magic weapon via the weapon's own ModifiableValues
- `create_flaming_scimitar()` (line 68): Uses the `extra_damage_*` parallel lists (`extra_damage_dices=[6]`, `extra_damage_type=[DamageType.FIRE]`) to add 1d6 fire damage alongside the base 1d6 slashing
- `create_morningstar()` (line 155): Same pattern — 1d4 necrotic via `extra_damage_*` lists
- `create_dagger()` (line 32): Adds disadvantage post-construction via `dagger.attack_bonus.self_static.add_advantage_modifier()` — a rusty blade penalty

The conditions file (`circus_fighter_conditions.py`) complements this with entity-level effects (`DualWielder` for dual-wield AC, `ElementalWeaponMastery` for advantage with elemental weapons) applied via `entity.add_condition()`.

**Key insight**: Today, magic weapon bonuses are baked into the weapon at construction time — there's no way to dynamically add/remove them via equip/unequip. A +1 longsword IS always +1. Equip hooks would enable dynamic effects: "this sword grants +1 AC while held" or "this cursed blade drains 1 HP per turn while equipped" — effects that start and stop with the equip state.

#### Class Feature Action Registration — The Proven Pattern

Class features already demonstrate how conditions register actions on entities:

**SecondWindFeature** (`dnd/classes/fighter.py:830–849`):
```python
# _apply():
target.action_economy.add_resource("second_wind", 1, RechargeType.SHORT_REST)
target.register_action(SecondWind(source_entity_uuid=target.uuid, template=True))

# _remove():
target.action_economy.remove_resource("second_wind")
target.unregister_action("Second Wind")
```

**RageFeature** (`dnd/classes/rage.py:655–677`) registers TWO actions (Rage + End Rage) from one condition.

This exact pattern — condition._apply() registers actions, condition._remove() unregisters them — is how equip hooks and item Use actions should work.

---

## 2. D&D 5e Rules Reference

### Object Interaction (PHB)

- **Free Object Interaction**: Each turn, a character gets one free interaction with an object or the environment (open a door, draw a weapon, hand an item to ally, pick up a dropped item).
- **Use an Object Action**: More complex interactions require an action (using a healer's kit, applying oil, lighting a torch from a campfire, drinking a potion).
- **Multiple Interactions**: If you want to interact with two objects in one turn, the second requires your action.

### Inventory and Encumbrance

- **Carrying Capacity**: STR × 15 pounds (can carry but movement unaffected)
- **Push/Drag/Lift**: STR × 30 pounds
- **Variant: Encumbrance**: STR × 5 = no penalty, STR × 10 = -10 ft speed, above = -20 ft speed and disadvantage on STR/DEX/CON checks
- **Most games**: Ignore encumbrance entirely or use simplified "reasonable carry" rule

### Attunement (Magic Items)

- Requires short rest (1 hour) with the item
- Maximum 3 attuned items simultaneously
- Some items require attunement by a specific class, alignment, or creature type
- Breaking attunement: another short rest, 100+ ft away for 24 hours, death, or another creature attunes to it

### Using Items

| Item Type | Action Cost | Notes |
|-----------|-------------|-------|
| Potion (drink) | Action | Self-target, consumed on use |
| Potion (administer) | Action | Feed to incapacitated creature |
| Scroll | Matches spell's casting time | Must be spellcaster, consumed on use |
| Wand | Action (typically) | Requires attunement, has charges |
| Staff | Varies | Often usable as melee weapon AND spellcasting focus |
| Rod | Action | Varies by item |
| Ring (passive) | None | Effect while worn (Ring of Protection) |
| Ring (activated) | Action | Some rings have activated abilities |

### Picking Up and Dropping

- **Pick up**: Free object interaction (if within 5 feet)
- **Drop**: Free (no action cost at all)
- **Pick up + use in same turn**: Requires action for the use

---

## 3. The Three Orthogonal Traits

Objects in the game world have three independent traits that can combine freely:

### Trait 1: Pickable

**Can be taken from the environment into an entity's inventory.**

- Has weight, value, possibly rarity and tags
- Can exist: on the floor, in a container, in inventory, in an equipment slot
- Pickup requires adjacency and free object interaction (or action)
- Not all objects are pickable: a lever bolted to a wall is not. A statue is not. A door is not.
- Stacking: some pickable items stack (coins, arrows) — need `stack_count` and `max_stack`

### Trait 2: Equippable

**Can occupy an equipment slot, activating persistent effects via equip hooks.**

- Has `_on_equip()` and `_on_unequip()` hooks that fire when entering/leaving a slot
- Must be pickable first (you equip from inventory, not from the floor — pickup then equip)
- Equipping is NOT using — it changes what's worn/held, not what happens now
- Examples: weapons, armor, shields, rings, amulets, wands (for passive bonuses or spell access)
- Equip hooks almost always work through the condition pattern: apply condition on equip → condition registers modifiers/handlers → auto-cleaned on unequip via condition removal

### Trait 3: Usable

**Has one or more associated actions that can be triggered.**

- Each action has its own targeting, costs, and effects
- Use actions can come from any context: inventory, equipped, or environment
- A potion on the ground can be used (drink it) without equipping it
- A lever in the wall can be used (pull it) without picking it up
- A wand might be both equippable (for passive effects) AND usable (for casting spells)
- Consumable = usable + destroyed after use

### Non-Exclusive Combinations — Full Stress-Test Table

| Item | Pickable | Equippable | Usable | Targetable | Notes |
|------|----------|------------|--------|------------|-------|
| Sword on ground | yes | yes (melee slot) | no | no | Equipping makes attacks available — but equip ≠ use |
| Potion on ground | yes | no | yes (drink = SELF) | no | Consumable. Destroyed after use |
| Lever on wall | no | no | yes (pull = custom) | no | Fixed to environment. Custom action logic |
| Statue | no | no | no | yes (AC 17, HP 20) | Decorative. May block movement. Stone material |
| Ring of Fire Bolt | yes | yes (ring slot) | yes (cast = ENTITY) | no | Equipped for stats. Use action = cast spell |
| Scroll of Fireball | yes | no | yes (cast = POS_AOE) | no | Consumable. Wraps existing Fireball SpellAction |
| Chest | no | no | yes (open = custom) | yes (AC 15, HP 27) | Has Inventory. Blocks movement. Break = spills contents |
| Door | no | no | yes (open/close = custom) | yes (AC 15, HP 18) | Toggles blocks_movement + blocks_vision. Break = opens permanently |
| Bag of Holding | yes | no | yes (access inventory) | no | Item WITH Inventory. Use = browse contents |
| Cursed Ring | yes | yes (cursed) | no | no | _on_equip: applies curse condition, blocks unequip |
| Wand (2 spells) | yes | yes (ring/amulet) | yes (2 separate actions) | no | Multi-action item: Fire Bolt + Burning Hands |
| Coins | yes | no | no | no | Stackable, no use, no equip. Pure loot |
| Trapped Chest | no | no | yes (open = trap + loot) | yes (AC 15, HP 27) | Use triggers damage THEN shows inventory |
| Key | yes | no | yes (unlock = ENTITY) | no | Targets a locked door/chest. Consumable? Depends |
| Campfire | no | no | yes (rest? cook?) | no | Environment object, doesn't block movement |
| Bookshelf | no | no | no | no | Blocks movement AND vision. Pure decoration |
| Barricade | no | no | no | yes (AC 15, HP 12) | Blocks movement. Break = removed from grid |

### Edge Cases This Table Exposes

**Equipped AND Usable**: The Ring of Fire Bolt and the Wand expose a subtle distinction:
- The ring's `_on_equip` hook might grant a passive bonus (e.g., fire resistance) — that's an equip effect
- The ring's Use action (cast Fire Bolt) is separate — it requires spending an action, has its own targeting
- Both systems must coexist on one item without conflicting

**Equip hooks that grant actions vs Use actions**: Both mechanisms result in "entity gains an action". The distinction:
- **Equip-granted action**: Available as long as the item is equipped. The action lives on the entity, not the item. Removing the item removes the action. Example: Wand of Fire Bolt equipped → entity has "Fire Bolt" action. Unequip → action gone.
- **Use action**: Inherent to the item. Available whenever the item is accessible (inventory, environment, equipped). The action is defined BY the item. Example: Potion of Healing always has "Drink" as a Use action, whether it's in inventory or on the ground.

**Consumables**: When is the item destroyed?
- The Use action's `_apply()` must handle destruction: remove from inventory (or from GridMap position), unregister from BaseObject registry
- What if the action is multi-step? (Trapped Chest: damage first, THEN loot) — destruction should happen at the right point in the flow
- Single-use scrolls: destroy after the spell resolves, not before (what if the spell is canceled at EXECUTION phase?)

---

## 4. BaseItem Architecture

### The Core Insight

Today, `Weapon`, `Armor`, and `Shield` inherit directly from `BaseBlock`. There is no shared concept of "an item that can exist in the world". The first step is introducing `BaseItem` as a layer between `BaseBlock` and the equipment types.

### Proposed Hierarchy

```
BaseBlock (dnd/core/base_block.py)
│
├── BaseItem (dnd/core/base_item.py)  ← NEW
│   ├── Weapon   (dnd/blocks/equipment.py)  ← reparented
│   ├── Armor    (dnd/blocks/equipment.py)  ← reparented
│   │   ├── Helmet, BodyArmor, ...
│   └── Shield   (dnd/blocks/equipment.py)  ← reparented
│
└── Tile (dnd/core/base_tiles.py)  ← unchanged
```

### BaseItem Fields

```python
class BaseItem(BaseBlock):
    """An object that can exist in the world — on the floor, in inventory, or equipped."""

    # Enable condition/handler infrastructure (see Section 13)
    allow_events_conditions: bool = True  # Items CAN receive conditions (enchantments, etc.)

    # Identity
    name: str = "Item"
    description: Optional[str] = None

    # Physical properties
    weight: float = 0.0           # Pounds
    value: int = 0                # Gold pieces
    rarity: ItemRarity = ItemRarity.COMMON  # COMMON, UNCOMMON, RARE, VERY_RARE, LEGENDARY

    # Trait flags
    is_pickable: bool = True      # Can be taken into inventory
    is_equippable: bool = False   # Can go in equipment slot (subclasses override)
    is_consumable: bool = False   # Destroyed on use

    # Stacking
    stack_count: int = 1
    max_stack: int = 1            # 1 = not stackable

    # Tags for filtering/search
    tags: List[str] = []          # ["magic", "cursed", "fire", "weapon", "potion"]

    # Attunement (D&D 5e magic items)
    requires_attunement: bool = False
    attuned_to: Optional[UUID] = None  # Entity UUID

    # Spatial state (when on the ground)
    blocks_movement: bool = False
    blocks_vision: bool = False

    # Breakable/targetable properties (see Section 14)
    is_targetable: bool = False          # Can this object be attacked/targeted by AoE?
    object_ac: int = 15                  # AC based on material (D&D 5e: Wood=15, Stone=17, etc.)
    health: Optional[Health] = None      # If present and is_targetable, object has HP
    damage_immunities: List[DamageType] = [DamageType.POISON, DamageType.PSYCHIC]
```

### What Methods Belong on BaseItem

| Method | Purpose | Notes |
|--------|---------|-------|
| `can_pickup(entity_uuid)` | Check if entity can pick this up | Weight limits, fixed objects, curse checks |
| `get_use_actions(owner_uuid)` | Return action templates this item provides | Adaptive — can vary by charges, state, conditions. Each action carries its own target_type. See Section 5 |
| `is_usable` | Property: `len(get_use_actions()) > 0` | Quick check |
| `is_stackable` | Property: `max_stack > 1` | Quick check |
| `is_breakable()` | `is_targetable and health is not None` | Object can be attacked and broken (Section 14) |
| `receive_damage(amount, type, source)` | Apply damage to targetable object | Returns actual damage dealt. Checks immunities. Calls `_on_break()` at 0 HP |
| `_on_break()` | Override for break behavior | Door: opens permanently. Chest: spills contents. Barricade: removed from grid |
| `destroy()` | Remove from all registries and containers | For consumables after use. Cleans up conditions (Section 13) |

### The Four Lifecycle Hooks

BaseItem defines four no-op hooks that subclasses override. Each has a public method (called by Entity/Equipment) and a private hook (the override point on the item):

| Public (caller) | Private (item override) | Called When | Who Calls |
|-----------------|------------------------|-------------|-----------|
| `loot()` | `_on_loot()` | Item enters inventory | Entity.add_to_inventory() |
| `drop()` | `_on_drop()` | Item leaves inventory | Entity.remove_from_inventory() |
| `equip(slot)` | `_on_equip(slot)` | Item enters equipment slot | Equipment.equip() |
| `unequip(slot)` | `_on_unequip(slot)` | Item leaves equipment slot | Equipment.unequip() |

**The UUID pattern — same as conditions and actions**: Hooks do NOT receive the Entity as an argument. Instead, the item already has `self.source_entity_uuid` (updated by Equipment.equip() and Entity.add_to_inventory() to match the owning entity). The hook body calls `Entity.get(self.source_entity_uuid)` at runtime — exactly like `BaseCondition._apply()` does with `Entity.get(self.target_entity_uuid)`.

This is the established codebase pattern:
- `BaseCondition._apply(event)` → `Entity.get(self.target_entity_uuid)` inside the body
- `BaseAction._apply(event)` → `Entity.get(self.source_entity_uuid)` inside the body
- `BaseItem._on_equip(slot)` → `Entity.get(self.source_entity_uuid)` inside the body

The import happens in the concrete subclass module (e.g., `dnd/items/magic_items.py` imports Entity), not in the base class. BaseItem in `dnd/core/` never imports Entity.

```python
# In dnd/core/base_item.py — NO Entity import
class BaseItem(BaseBlock):
    equipped_slot: Optional[Any] = None  # Track which slot this item is in

    def loot(self) -> None:
        """Called by Entity when item enters inventory.
        Base: bookkeeping. Override _on_loot() for item-specific logic."""
        self._on_loot()

    def _on_loot(self) -> None:
        """Override in subclasses for item-specific loot behavior."""
        pass

    def drop(self) -> None:
        """Called by Entity when item leaves inventory.
        Base: bookkeeping. Override _on_drop() for item-specific logic."""
        self._on_drop()

    def _on_drop(self) -> None:
        """Override in subclasses for item-specific drop behavior."""
        pass

    def equip(self, slot: Any) -> None:
        """Called by Equipment when item enters slot.
        Base: records slot. Override _on_equip() for item-specific logic."""
        self.equipped_slot = slot
        self._on_equip(slot)

    def _on_equip(self, slot: Any) -> None:
        """Override in subclasses. Apply conditions, register modifiers on equip."""
        pass

    def unequip(self, slot: Any) -> None:
        """Called by Equipment when item leaves slot.
        Base: clears slot. Override _on_unequip() for item-specific logic."""
        self._on_unequip(slot)
        self.equipped_slot = None

    def _on_unequip(self, slot: Any) -> None:
        """Override in subclasses. Remove conditions, clean up on unequip."""
        pass
```

**Why this works**: Before calling `item.loot()`, Entity sets `item.source_entity_uuid = self.uuid`. Before calling `item.equip(slot)`, Equipment already updates `item.source_entity_uuid` (line 677 of current `Equipment.equip()`). So by the time the hook fires, `self.source_entity_uuid` points to the right entity.

**The public methods handle bookkeeping** (setting `equipped_slot`, etc.) — lightweight state that BaseItem can manage without importing anything. The private hooks (`_on_equip`, `_on_loot`) are where the actual entity-interacting logic lives, implemented by concrete subclasses in higher-level modules. This matches the `apply()` / `_apply()` pattern in BaseAction and BaseCondition: `apply()` handles the lifecycle machinery, `_apply()` is where subclasses put their logic.

**Why public + private?** The public method (`loot`, `equip`) is the stable API that Entity/Equipment calls. It can include shared logic (e.g., `loot()` could handle default Use action registration before calling `_on_loot()`). The private method (`_on_loot`, `_on_equip`) is the extension point that subclasses override for item-specific behavior. This mirrors the `apply()` / `_apply()` split in BaseAction and BaseCondition.

**BaseBlock access without Entity import**: Since BaseItem extends BaseBlock and Entity also extends BaseBlock, the hooks can access the full BaseBlock API (conditions, event handlers, ModifiableValues, block composition) on the entity through `BaseBlock.get(self.source_entity_uuid)` — no Entity import needed at all for many effects. Entity import is only needed for entity-specific methods like `register_action()`, `get_visible_enemies()`, etc.

### Use Action Discovery — Inventory Aggregates at Query Time

> **Revised**: Originally, Entity would register Use action templates when items entered inventory. The new design (Section 15) has Inventory aggregate actions dynamically. `get_use_actions()` is called at query time by `Inventory.get_all_use_actions()`, not at loot time.

Use action registration doesn't happen on loot. Instead, `get_available_actions()` queries `Equipment.inventory.get_all_use_actions()` (see Sections 7, 15, and 16). Items just implement `get_use_actions()` — the Inventory aggregates them.

**Most items need ZERO `_on_loot` override** — they just implement `get_use_actions()` and the query-time aggregation handles the rest. Subclasses only override `_on_loot` for extra behavior like cursed items that apply conditions when picked up.

### Where Does Use Logic Live?

This is explored in depth in Section 5. The key architectural constraint: `BaseItem` lives in `dnd/core/base_item.py` and must be importable by `Entity`. Therefore `BaseItem` **cannot** import `Entity`. Use logic that needs entity access must be structured accordingly (entity passed as parameter to hooks, or action classes that live in higher-level modules).

### All Hooks on BaseItem — No Duck-Typing

All four hook pairs live on BaseItem with no-op defaults. This is simpler than duck-typing (`hasattr` checks) or protocol/ABC approaches. A lever that can't be equipped still has `_on_equip` — it's just never called because the lever is never equipped. The cost is zero (unused no-op methods), the benefit is a uniform interface.

### Migration Path

Reparenting `Weapon(BaseBlock)` → `Weapon(BaseItem)` is non-breaking:
- `BaseItem` inherits from `BaseBlock`, so all existing BaseBlock fields/methods are preserved
- New fields (`weight`, `value`, `rarity`, etc.) all have defaults
- All existing weapon/armor factories (`create_longsword(source_id)`) gain the new fields automatically with zero changes needed
- Over time, factories can be updated to set weight/value/rarity for item richness

### Dependency Direction

```
Entity (dnd/entity.py)          ← imports BaseItem for inventory, action registration
    ↓
BaseItem (dnd/core/base_item.py) ← new file, safe position in hierarchy
    ↓
BaseBlock (dnd/core/base_block.py)
    ↓
BaseObject (dnd/core/base_object.py)
```

`BaseItem` is at the same level as `Tile` — importable from anywhere safely. Entity can import BaseItem. BaseItem never imports Entity. This is the correct dependency direction.

---

## 5. The Use Action Interface (Deep Dive)

This is the hardest design problem in the entire system. The Use interface must support:

- Items with 1 action (potion: drink)
- Items with multiple actions (wand: Fire Bolt + Burning Hands)
- Specific custom actions (lever: custom logic to disable trap)
- Wrapping existing actions (scroll: wraps Fireball SpellAction)
- Different targeting per action (potion=SELF, fireball scroll=POSITION_AOE, key=ENTITY)
- Consumable behavior (destroyed on use)
- The two-step flow: enumerate WHAT can be used → resolve specific targeting for each

### The Two Use Patterns

**Pattern 1 — Custom Specific Action**: A lever that removes a trap trigger. The action logic is unique to that lever instance — it references specific trap UUIDs, runs custom code, has no equivalent in any other system.

**Pattern 2 — Wrapping an Existing Action**: A Scroll of Fireball doesn't define new logic. It delegates to the existing `Fireball` SpellAction class. The scroll says "I am a Fireball with these parameters" and the system handles the rest.

Both patterns must be supported with the same interface.

### Option A: Item Declares Action Class(es)

The item provides a list of `(ActionClass, config_dict)` tuples. The system instantiates templates when the item becomes available.

```python
class BaseItem(BaseBlock):
    def get_use_actions(self) -> List[Tuple[type, Dict[str, Any]]]:
        """Return action classes and their config for Use actions."""
        return []  # Override in subclasses

# Example: Scroll of Fireball
class ScrollOfFireball(BaseItem):
    is_consumable: bool = True

    def get_use_actions(self):
        return [(Fireball, {"caster_level": 5, "source_item_uuid": self.uuid})]

# Example: Wand of Fire (2 spells)
class WandOfFire(BaseItem):
    def get_use_actions(self):
        return [
            (FireBolt, {"caster_level": 5, "source_item_uuid": self.uuid}),
            (BurningHands, {"caster_level": 3, "source_item_uuid": self.uuid}),
        ]
```

**Pros**:
- Reuses existing action infrastructure completely. Fireball's targeting, AoE, damage — all work as-is.
- Each Use action is a proper template with its own `target_type` → appears correctly in `get_available_actions()`.
- AI and UI see these as normal actions — no special handling.

**Cons**:
- Custom one-off actions (lever, trapped chest) need their own action classes, even if they're only used once.
- Import direction: `BaseItem.get_use_actions()` returns action classes. If those classes live in `dnd/actions.py` or `dnd/spells/`, BaseItem can't import them. The subclass that overrides `get_use_actions()` must live somewhere that CAN import those classes (in the same module or higher up).

**Import solution**: `BaseItem.get_use_actions()` returns `[]` by default. Concrete items like `ScrollOfFireball` are defined in a module that imports both `BaseItem` and `Fireball`. This works because the concrete item is high-level, not the base class.

**Two-step integration**:
1. When item enters inventory (or becomes available from environment): system calls `item.get_use_actions()`, creates templates, registers them on entity
2. Templates have `target_type` already set → appear in correct category in `get_available_actions()`
3. Consumer sees "Fireball (scroll)" as a normal action with targets

### Option B: Item Has `_use()` Method(s)

The item defines its own execution logic directly.

```python
class BaseItem(BaseBlock):
    def get_use_descriptors(self) -> List[UseDescriptor]:
        """Return descriptors for available Use actions."""
        return []

class UseDescriptor(BaseModel):
    name: str
    target_type: TargetType
    cost_type: CostType = CostType.ACTION
    cost_amount: int = 1
    description: str = ""

class PotionOfHealing(BaseItem):
    def get_use_descriptors(self):
        return [UseDescriptor(name="Drink", target_type=TargetType.SELF)]

    def _use(self, action_name: str, source_entity_uuid: UUID, **kwargs) -> Optional[Event]:
        """Execute the Use action."""
        entity = Entity.get(source_entity_uuid)
        entity.health.heal(2, 4, 2)  # 2d4+2
        if self.is_consumable:
            self.destroy()
```

**Pros**:
- Simple for custom logic. A lever just puts code in `_use()`.
- No need to create action classes for one-off items.

**Cons**:
- Doesn't integrate with the template/targeting system. How does `_use()` go through declaration → validation → execution → costs → completion?
- The item must import Entity to do anything useful — violates dependency direction.
- No event system integration means no combat log, no handler reactions, no cancellation.
- Targeting is declared in the descriptor but not enforced by any system.

**Verdict**: Option B alone is insufficient. It skips the event lifecycle, has no targeting enforcement, and violates dependency direction. However, the **idea** of items declaring their own logic is valid — it just needs to be wrapped in the action system.

### Option C: Hybrid — UseItemAction Wrapper

A generic `UseItemAction` wraps any item and delegates to the item's `_use()`. This gives items custom logic while running through the full action lifecycle.

```python
class UseItemAction(BaseAction):
    """Generic action that delegates to an item's _use method."""
    item_uuid: UUID
    use_action_name: str  # Which of the item's actions to invoke

    def _validate(self, declaration_event: Event) -> Event:
        # Standard validation (range, LOS, costs)
        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event: Event) -> Event:
        item = BaseItem.get(self.item_uuid)
        # Item performs its effect
        effect_event = item._use(self.use_action_name, execution_event)
        # Handle consumable
        if item.is_consumable:
            item.destroy()
        return effect_event
```

The item declares targeting and costs via descriptors:

```python
class TrapLever(BaseItem):
    is_pickable: bool = False

    def get_use_descriptors(self) -> List[UseDescriptor]:
        return [UseDescriptor(
            name="Pull Lever",
            target_type=TargetType.SELF,  # No target needed
            cost_type=CostType.FREE,      # Free object interaction
            description="Disarms the spike trap"
        )]

    def _use(self, action_name: str, event: Event) -> Event:
        # Custom logic: disarm the trap
        trap_condition = Tile.get(self.trap_tile_uuid)
        trap_condition.remove_condition("SpikeTrap")
        return event.phase_to(EventPhase.EFFECT)
```

**Pros**:
- Full event lifecycle (declaration → validate → apply → costs → completion)
- Combat log integration for free
- Handlers can react (e.g., Mage Slayer reacting to scroll use)
- Custom logic lives on the item (lever, trapped chest) via `_use()`
- Existing action wrapping: a scroll's `_use()` just instantiates and applies the wrapped action

**Cons**:
- `_use()` signature must be carefully designed — receives an event, returns an event
- Item needs enough information to do its job without importing Entity
- One extra layer of indirection

**Import direction**: `UseItemAction` lives in `dnd/actions.py` (high-level). It imports `BaseItem` (low-level). `BaseItem._use()` receives the event as parameter — it can use `Entity.get()` via the registry (UUID-based lookup, no import needed since `_use` is called from action-level code).

Wait — that still requires BaseItem to know about Entity. Let's refine:

### Option D: Best of Both — Action Classes + Fallback to UseItemAction

This combines Option A and Option C:

**For items that wrap existing actions** (scrolls, wands): Item returns the action class directly via `get_use_actions()`. The system creates proper templates. Zero custom code.

**For items with custom logic** (levers, trapped chests): Item returns a `UseItemAction` class with configuration. The `UseItemAction._apply()` calls a callback registered on the item.

```python
class BaseItem(BaseBlock):
    def get_use_actions(self, owner_uuid: UUID) -> List[BaseAction]:
        """Return fully-configured action templates for this item's Use actions.
        owner_uuid: the entity that would use the item (needed for source_entity_uuid)."""
        return []
```

**Scroll of Fireball** (wraps existing action):
```python
class ScrollOfFireball(BaseItem):
    is_consumable: bool = True

    def get_use_actions(self, owner_uuid: UUID) -> List[BaseAction]:
        return [Fireball(
            source_entity_uuid=owner_uuid,
            caster_level=5,
            template=True,
            name="Fireball (Scroll)",
            source_item_uuid=self.uuid,  # Track origin for consumable cleanup
        )]
```

**Lever** (custom action):
```python
# In a high-level module that can import everything:
class PullLeverAction(BaseAction):
    """Custom action for a specific lever."""
    target_type: TargetType = TargetType.SELF
    trap_tile_uuid: UUID
    # ... custom _validate and _apply
```

**Wand of Fire** (equip-granted, not Use):
```python
# In dnd/items/magic_items.py (can import Entity)
class WandOfFire(BaseItem):
    def _on_equip(self, slot: Any) -> None:
        entity = Entity.get(self.source_entity_uuid)
        entity.add_condition(WandOfFireCondition(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            # Condition._apply() registers FireBolt + BurningHands templates
        ))

    def _on_unequip(self, slot: Any) -> None:
        entity = Entity.get(self.source_entity_uuid)
        entity.remove_condition("WandOfFireCondition")
```

**The inheritance insight**: BaseItem extends BaseBlock, and Entity also extends BaseBlock. So even at the BaseItem level (without importing Entity), hooks can access everything BaseBlock provides — conditions, event handlers, ModifiableValues, the full block composition API via `BaseBlock.get(self.source_entity_uuid)`. Entity import is only needed for entity-specific methods like `register_action()`, `get_visible_enemies()`, etc. — but many equip effects only need BaseBlock-level access.

This mirrors the existing codebase pattern exactly:
- `BaseCondition` (in `dnd/core/`) defines `_apply(event)` — importable everywhere
- `Blinded` (in `dnd/conditions.py`) overrides `_apply()`, calls `Entity.get(self.target_entity_uuid)` — imports Entity
- `BaseItem` (in `dnd/core/`) defines `_on_equip(slot)` — importable everywhere
- `RingOfProtection` (in `dnd/items/`) overrides `_on_equip(slot)`, calls `Entity.get(self.source_entity_uuid)` — imports Entity

### Recommendation

**Option D is the strongest approach.** It handles all cases:

| Use Case | Mechanism |
|----------|-----------|
| Scroll of Fireball | `get_use_actions()` returns `[Fireball(template=True)]` |
| Potion of Healing | `get_use_actions()` returns `[DrinkPotionAction(template=True)]` |
| Wand of Fire Bolt (equip) | `_on_equip()` applies condition → condition registers action |
| Ring of Fire Bolt (use) | `get_use_actions()` returns `[FireBolt(template=True)]` |
| Lever (custom) | `get_use_actions()` returns `[PullLeverAction(template=True)]` |
| Trapped Chest | `get_use_actions()` returns `[OpenTrappedChestAction(template=True)]` |
| Wand with 2 spells | `get_use_actions()` returns `[FireBolt(...), BurningHands(...)]` |

Every Use action is a proper `BaseAction` template. It goes through the full lifecycle. It appears in `get_available_actions()`. AI and UI see it as any other action.

### `get_use_actions()` Is Adaptive, Not Static

**Critical design point**: `get_use_actions()` is a method, not a static declaration. It's called at query time and can return different actions based on current state. This enables:

- **Charge-based items**: A Wand of Fireballs (7 charges) returns `[Fireball(template=True)]` only while charges > 0. At 0 charges, returns `[]` — the action disappears.
- **Conditional use**: A Staff of Power returns different actions at different charge costs. 1 charge = Magic Missile, 5 charges = Fireball. Each appears as a separate action with its own cost.
- **State-dependent items**: A locked chest returns `[LockPickAction]` while locked, `[OpenChestAction]` once unlocked. The trap lever returns `[PullLever]` only once (then the lever is pulled and returns `[]`).
- **Roll-dependent**: An item that only works on a roll could gate its availability.

```python
class WandOfFireballs(BaseItem):
    charges: int = 7

    def get_use_actions(self, owner_uuid: UUID) -> List[BaseAction]:
        if self.charges <= 0:
            return []
        actions = []
        # 1 charge: single target
        if self.charges >= 1:
            actions.append(Fireball(
                source_entity_uuid=owner_uuid,
                caster_level=5,
                template=True,
                name="Fireball (Wand, 1 charge)",
                source_item_uuid=self.uuid,
            ))
        # 3 charges: upcast
        if self.charges >= 3:
            actions.append(Fireball(
                source_entity_uuid=owner_uuid,
                caster_level=7,  # Upcast to 5th level
                template=True,
                name="Fireball (Wand, 3 charges)",
                source_item_uuid=self.uuid,
            ))
        return actions
```

**Each action carries its own `target_type`**: A multi-action item can have actions with completely different targeting. A Staff of the Magi might return `[FireBolt(target_type=ENTITY), Fireball(target_type=POSITION_AOE), MageArmor(target_type=SELF)]` — each slots into the correct category in `get_available_actions()` (entity_actions, position_actions, self_actions respectively).

**Re-registration on state change**: When charges are consumed or item state changes, the registered action templates may need updating. Options:
1. Re-register on every use (simple, slightly wasteful)
2. Pre_validate gates it: the action template is always registered, but `pre_validate()` checks charges and fails if insufficient
3. Actions reference the item and check state dynamically in their `_validate()`

Option 2 or 3 is more efficient — register all possible actions once, let validation handle availability.

### The `source_item_uuid` Field

All Use-action templates should carry `source_item_uuid: Optional[UUID]` on `BaseAction`. This allows:
- Consumable cleanup: after action completes, check if source item is consumable → destroy it
- UI: display item icon/name alongside the action
- `AvailableActionInfo`: add `source_item_uuid` field for UI categorization
- Combat log: "Hero uses Scroll of Fireball" rather than just "Hero casts Fireball"

This field already exists as a potential addition — it's analogous to how SpellAction tracks the spell source.

### Consumable Destruction Timing

When should a consumable item be destroyed?

**Option 1: In `_apply()` of the action** — The action itself calls `item.destroy()` at the end.
Pro: Simple. Con: If an action is partially applied (multi-step), destruction happens at the wrong time.

**Option 2: At COMPLETION phase via callback** — A completion callback checks `source_item_uuid`, finds the item, destroys if consumable.
Pro: Only fires after the full action lifecycle. Con: More infrastructure.

**Option 3: In `BaseAction.apply()` after `_apply_costs()`** — The base apply method checks `source_item_uuid` after costs are applied and the action has fully resolved.
Pro: Centralized, automatic. Con: Need to be careful about edge cases (canceled actions shouldn't consume).

**Recommendation**: Option 3 — add a check in `BaseAction.apply()` (after line 633) that looks at `source_item_uuid`. If set and item is consumable and action wasn't canceled → call `item.destroy()`. This is centralized and applies to all Use actions uniformly.

---

## 6. Equip/Unequip Hooks (Separate from Use)

### Why This Is a Separate System

Equipping is about **entering or leaving an equipment slot**, not about performing an action. When you equip a Ring of Protection, there's no targeting, no action economy cost (beyond the free object interaction), no event to resolve — the ring simply starts applying its effect.

Compare:
- **Equip Ring of Protection**: slot occupancy changes → +1 AC modifier activates. No action, no target, no event lifecycle for the ring's effect.
- **Use Potion of Healing**: action spent → targeting resolved → dice rolled → HP gained → potion destroyed. Full action lifecycle.

These are fundamentally different operations that happen to both involve items.

### Hook Signatures

Defined on BaseItem (see Section 4 for full lifecycle hook table). The equip hooks follow the same pattern as `BaseCondition._apply()` and `BaseAction._apply()` — the item has `self.source_entity_uuid` already set, and the hook body calls `Entity.get()` in the concrete subclass:

```python
# In dnd/core/base_item.py — NO Entity import
class BaseItem(BaseBlock):
    def _on_equip(self, slot: Any) -> None:
        """Override in subclasses. Called when item enters equipment slot.
        self.source_entity_uuid is already set to the equipping entity.
        slot: WeaponSlot, BodyPart, or RingSlot — the slot this item entered.
        """
        pass

    def _on_unequip(self, slot: Any) -> None:
        """Override in subclasses. Called when item leaves equipment slot.
        self.source_entity_uuid is still set to the entity (cleared after hook returns).
        slot: the slot this item is leaving.
        """
        pass
```

This mirrors `_on_loot()` / `_on_drop()` — same UUID-based pattern throughout. Concrete subclasses in higher-level modules (e.g., `dnd/items/magic_items.py`) import Entity and call `Entity.get(self.source_entity_uuid)` in their hook bodies — exactly how conditions do it.

### Where Hooks Get Called

**In `Equipment.equip()`** (after line 806 in current code, after slot assignment):
```python
# Existing step 1 (line 677): item.source_entity_uuid = self.source_entity_uuid
# ... existing slot logic ...
# Existing step 6: setattr(self, attribute_name, item)
# NEW: call item hook — source_entity_uuid already set by step 1
item.equip(slot)   # public method calls _on_equip(slot)
# Existing step 7: phase to EFFECT
```

**In `Equipment.unequip()`** (before line 892, before slot is set to None):
```python
# NEW: call item hook before clearing — source_entity_uuid still valid
item.unequip(slot)  # public method calls _on_unequip(slot)
# Existing: setattr(self, attribute_name, None)
```

The hooks fire INSIDE the equip/unequip event lifecycle — between slot assignment and event completion. `item.source_entity_uuid` was already set to the owning entity's UUID at the start of `equip()` (line 677), so the hook body can call `Entity.get(self.source_entity_uuid)` just like conditions do.

### The Condition Pattern

The overwhelmingly common pattern for equip hooks is: **apply a condition on equip, remove it on unequip**. This leverages the entire existing condition infrastructure (modifiers, handlers, sub-conditions, cleanup).

```python
# In dnd/items/magic_items.py (high-level module, CAN import Entity)
from dnd.entity import Entity

class MagicItem(BaseItem):
    """Base for items that apply a condition on equip."""
    condition_class: type  # Set by subclass
    condition_name: str    # For removal

    def _on_equip(self, slot: Any) -> None:
        entity = Entity.get(self.source_entity_uuid)
        condition = self.condition_class(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
        )
        entity.add_condition(condition)

    def _on_unequip(self, slot: Any) -> None:
        entity = Entity.get(self.source_entity_uuid)
        if self.condition_name in entity.active_conditions:
            entity.remove_condition(self.condition_name)
```

**No late imports, no circularity.** This follows the exact pattern as BaseAction/BaseCondition:
- `BaseItem` (in `dnd/core/`) defines the hook with a no-op body — importable everywhere
- `MagicItem` (in `dnd/items/`) overrides the hook, imports Entity at the top level, calls `Entity.get(self.source_entity_uuid)` in the body
- Just as `BaseCondition` (in `dnd/core/`) defines `_apply()` and `Blinded` (in `dnd/conditions.py`) overrides it with `Entity.get(self.target_entity_uuid)`

### Concrete Examples

#### Ring of Protection (+1 AC)

```python
# In dnd/items/magic_items.py (can import Entity)
class RingOfProtection(Ring):  # Ring extends Armor extends BaseItem
    name: str = "Ring of Protection"
    rarity: ItemRarity = ItemRarity.RARE
    requires_attunement: bool = True

    def _on_equip(self, slot: Any) -> None:
        entity = Entity.get(self.source_entity_uuid)
        condition = ProtectionRingCondition(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
        )
        entity.add_condition(condition)

    def _on_unequip(self, slot: Any) -> None:
        entity = Entity.get(self.source_entity_uuid)
        if "ProtectionRingCondition" in entity.active_conditions:
            entity.remove_condition("ProtectionRingCondition")

class ProtectionRingCondition(BaseCondition):
    name: str = "ProtectionRingCondition"

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        target = Entity.get(self.target_entity_uuid)
        modifier_uuid = target.equipment.ac_bonus.self_static.add_value_modifier(
            NumericalModifier(name="Ring of Protection", value=1, ...)
        )
        return [(target.equipment.ac_bonus.uuid, modifier_uuid)], [], [], [], effect_event
```

When the ring is unequipped, `entity.remove_condition("ProtectionRingCondition")` runs the full condition cleanup — removing the +1 AC modifier automatically.

#### Cursed Sword (Can't Unequip)

```python
class CursedSwordCondition(BaseCondition):
    name: str = "CursedSwordCondition"

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        target = Entity.get(self.target_entity_uuid)

        # Register handler that cancels unequip events for this weapon
        handler = EventHandler(
            name="Cursed Sword - Block Unequip",
            event_processor=self._block_unequip,
            trigger_conditions=[Trigger(
                name="block_unequip",
                event_type=EventType.WEAPON_UNEQUIP,
                event_phase=EventPhase.EXECUTION,
                event_source_entity_uuid=self.target_entity_uuid,
            )]
        )
        target.add_event_handler(handler)
        return [], [handler.uuid], [], [], effect_event

    def _block_unequip(self, event: Event, source_entity_uuid: UUID) -> Optional[Event]:
        # Check if this is the cursed weapon being unequipped
        if event.item_uuid == self.cursed_weapon_uuid:
            return event.cancel("The weapon resists removal!")
        return event
```

#### Wand of Fire Bolt (Equip-Granted Action)

```python
class WandOfFireBoltCondition(BaseCondition):
    """Grants Fire Bolt action while wand is equipped."""
    name: str = "WandOfFireBoltCondition"

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        target = Entity.get(self.target_entity_uuid)

        # Register Fire Bolt as action template (same pattern as SecondWindFeature)
        fire_bolt = FireBolt(
            source_entity_uuid=target.uuid,
            caster_level=5,
            template=True,
            name="Fire Bolt (Wand)",
        )
        target.register_action(fire_bolt)

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        target = Entity.get(self.target_entity_uuid)
        if target:
            target.unregister_action("Fire Bolt (Wand)")
        return super()._remove(event)
```

This is exactly the SecondWindFeature/RageFeature pattern — condition registers action on apply, unregisters on remove.

### Key Distinction Reinforced

| Mechanism | When | What Happens | Action Economy Cost |
|-----------|------|-------------|---------------------|
| `_on_equip` hook | Item enters slot | Condition applied, modifiers/handlers activate | Free (object interaction) |
| `_on_unequip` hook | Item leaves slot | Condition removed, all effects cleaned up | Free |
| Use action | Entity spends action | Event lifecycle, targeting, effects, possible consumption | Action (or bonus action, etc.) |

---

## 7. Inventory Block

### Core Design: Inventory as Shared Infrastructure

Inventory is not entity-specific. It's a general-purpose container that **any object can have**:

- An entity has an Inventory (their carried items)
- A chest IS an object that has an Inventory
- A bag of holding IS an item that has an Inventory
- A dead entity's loot bag has an Inventory

This means `Inventory` must be a `BaseBlock` that can be owned by entities, items, or environment objects.

### Inventory Fields

```python
class Inventory(BaseBlock):
    """A container for BaseItems. Can be owned by entities, items, or environment objects."""
    name: str = "Inventory"

    items: Dict[UUID, BaseItem] = {}           # Items by UUID
    weight_capacity: ModifiableValue           # Max carry weight (modified by STR, Bag of Holding)
    max_slots: Optional[int] = None            # Optional slot limit (None = unlimited)

    # Computed
    @property
    def total_weight(self) -> float:
        return sum(item.weight * item.stack_count for item in self.items.values())

    @property
    def is_full(self) -> bool:
        if self.max_slots is not None:
            return len(self.items) >= self.max_slots
        return self.total_weight >= self.weight_capacity.normalized_score
```

### Key Methods

```python
class Inventory(BaseBlock):
    def add_item(self, item: BaseItem) -> bool:
        """Add item to inventory. Returns False if full or overweight."""

    def remove_item(self, item_uuid: UUID) -> Optional[BaseItem]:
        """Remove and return item from inventory."""

    def find_items_by_name(self, name: str) -> List[BaseItem]:
        """Find items by name (may return multiple for stacks)."""

    def find_items_by_tag(self, tag: str) -> List[BaseItem]:
        """Find items with a specific tag."""

    def has_item(self, item_uuid: UUID) -> bool:
        """Check if item is in this inventory."""

    def transfer_to(self, item_uuid: UUID, target_inventory: 'Inventory') -> bool:
        """Move item from this inventory to another. Returns success."""
```

### Action Discovery — Inventory Aggregates, Entity Queries

> **Revised in Section 15.** The original design had Entity orchestrating action registration on loot/drop. The revised design has Inventory aggregating actions at query time — no registration dance needed.

`Inventory` aggregates Use actions from all its items. Instead of registering/unregistering action templates when items enter/leave, Entity queries Inventory at `get_available_actions()` time:

```python
class Inventory(BaseBlock):
    items: Dict[UUID, BaseItem] = {}

    def get_all_use_actions(self, owner_uuid: UUID) -> List[BaseAction]:
        """Aggregate all Use actions from all items.
        Called by get_available_actions() at query time — not at loot time."""
        actions = []
        for item in self.items.values():
            actions.extend(item.get_use_actions(owner_uuid))
        return actions
```

Entity's `add_to_inventory()` and `remove_from_inventory()` become simpler — they just store/remove the item and call hooks:

```python
# On Entity (high-level, can import BaseItem):
def add_to_inventory(self, item: BaseItem) -> bool:
    """Add item to inventory, call item hook. No action registration needed."""
    success = self.inventory.add_item(item)
    if success:
        item.source_entity_uuid = self.uuid  # Set ownership
        item.loot()  # Call item's loot hook for extra behavior
    return success

def remove_from_inventory(self, item_uuid: UUID) -> Optional[BaseItem]:
    """Remove item from inventory, call item hook. No action unregistration needed."""
    item = self.inventory.items.get(item_uuid)
    if item:
        item.drop()  # Call item's drop hook for cleanup
    return self.inventory.remove_item(item_uuid)
```

**Why this is better than registration**: `get_use_actions()` is called at query time → charge-based items, conditional items, state-dependent items all work without re-registration. When a wand runs out of charges, its `get_use_actions()` returns `[]` — the action simply doesn't appear. No unregister needed.

**Items with extra loot behavior** (e.g., a cursed item that applies a condition when picked up) override `_on_loot()` in a high-level module that imports Entity:

```python
# In dnd/items/magic_items.py
class CursedAmulet(Amulet):
    def _on_loot(self) -> None:
        entity = Entity.get(self.source_entity_uuid)
        entity.add_condition(CursedAmuletCondition(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
        ))
```

> **Note**: Inventory is designed as a sub-block of Equipment (see Section 16). Equipment contains an Inventory for general item storage, while also managing typed equipment slots. But Inventory is independently useful — chests, bags, and loot containers have Inventory without Equipment.

### Containers — Chests, Bags, Loot

A chest is an environment object that HAS an Inventory. Its Use action exposes that inventory for browsing/looting:

```python
class Chest(WorldObject):  # Or whatever environment object class we choose
    inventory: Inventory    # The chest's contents
    is_locked: bool = False
    is_trapped: bool = False

    def get_use_actions(self, owner_uuid: UUID) -> List[BaseAction]:
        actions = []
        if self.is_locked:
            actions.append(LockPickAction(source_entity_uuid=owner_uuid, target_uuid=self.uuid))
        if not self.is_locked:
            actions.append(OpenChestAction(source_entity_uuid=owner_uuid, chest_uuid=self.uuid))
        if self.is_trapped and not self.trap_disarmed:
            # Trap triggers on open — handled inside OpenChestAction
            pass
        return actions
```

A Bag of Holding is an item that HAS an Inventory:

```python
class BagOfHolding(BaseItem):
    inventory: Inventory = Inventory(
        weight_capacity=ModifiableValue(base_value=500),  # 500 lbs
        max_slots=None,
    )

    def get_use_actions(self, owner_uuid: UUID) -> List[BaseAction]:
        return [AccessBagAction(source_entity_uuid=owner_uuid, bag_uuid=self.uuid)]
```

### Dependency Direction

```
Entity → Inventory → BaseItem → BaseBlock
```

Inventory imports BaseItem (DOWN). Entity imports Inventory (DOWN). Clean hierarchy.

---

## 8. GridMap and Senses Integration

### The Problem

Objects need spatial presence. A chest on the floor must:
- Occupy a grid position
- Block movement (or not)
- Block vision (or not)
- Be visible to entities via Senses
- Fire spatial events when entities interact with them

Currently GridMap only knows about Tiles and Entities. Senses only sees entities and cells.

### GridMap Changes

#### New Registries

```python
class GridMap:
    # Existing
    _tiles: Dict[Tuple[int,int], Tile]
    _entity_positions: Dict[UUID, Tuple[int,int]]
    _entities_by_position: DefaultDict[Tuple[int,int], Set[UUID]]

    # NEW: Object spatial tracking
    _object_positions: Dict[UUID, Tuple[int,int]]
    _objects_by_position: DefaultDict[Tuple[int,int], Set[UUID]]
```

#### New Methods

```python
def place_object(self, object_uuid: UUID, position: Tuple[int,int]) -> None:
    """Place an object at a grid position."""

def remove_object(self, object_uuid: UUID) -> None:
    """Remove an object from the grid."""

def get_objects_at(self, position: Tuple[int,int]) -> Set[UUID]:
    """Get all objects at a position."""

def get_object_position(self, object_uuid: UUID) -> Optional[Tuple[int,int]]:
    """Get an object's position."""
```

#### Movement and Vision Blocking

`is_walkable_for()` must check objects:

```python
def is_walkable_for(self, x: int, y: int, entity_uuid: UUID, mode: MovementMode = MovementMode.WALKING) -> bool:
    if not self.is_walkable(x, y, mode):
        return False
    # Check entity occupancy (existing)
    for eid in self._entities_by_position.get((x, y), set()):
        if eid != entity_uuid and eid not in self._non_blocking_entities:
            return False
    # NEW: Check object blocking
    for oid in self._objects_by_position.get((x, y), set()):
        obj = BaseObject.get(oid)  # or BaseItem.get(oid)
        if obj and getattr(obj, 'blocks_movement', False):
            return False
    return True
```

`is_blocking()` must check objects for vision:

```python
def is_blocking(self, x: int, y: int) -> bool:
    tile = self._tiles.get((x, y))
    if tile is None or not tile.visible:
        return True
    # NEW: Check object vision blocking
    for oid in self._objects_by_position.get((x, y), set()):
        obj = BaseObject.get(oid)
        if obj and getattr(obj, 'blocks_vision', False):
            return True
    return False
```

#### Dynamic Changes

A door's Use action (open/close) toggles `blocks_movement` and `blocks_vision`. After toggling:
1. Must recalculate FOV for all entities that can see the door's position
2. Must recalculate paths for nearby entities
3. Fire `SPATIAL_TILE_CHANGED` or a new `SPATIAL_OBJECT_CHANGED` event

This is analogous to how tile conditions work today — when a tile's walkability changes, senses must update.

### Senses Changes

#### New Field

```python
class Senses(BaseBlock):
    entities: Dict[UUID, Tuple[int,int]]   # Visible entities (existing)
    objects: Dict[UUID, Tuple[int,int]]     # NEW: Visible objects
    visible: Dict[Tuple[int,int], bool]     # Visible cells (existing)
    paths: DefaultDict[...]                 # Reachable cells (existing)
```

#### Update Logic

In `update_senses()`:

```python
def update_senses(self, entities, visible_cells, walkable_cells, paths, objects=None):
    self.entities = entities
    self.visible = visible_cells
    self.walkable = walkable_cells
    self.paths = paths
    if objects is not None:
        self.objects = objects
```

The caller (Entity.update_entity_senses) queries GridMap for objects in visible cells:

```python
# In Entity.update_entity_senses():
visible_objects = {}
for pos, is_visible in visible_cells.items():
    if is_visible:
        for oid in gridmap.get_objects_at(pos):
            visible_objects[oid] = pos
self.senses.update_senses(..., objects=visible_objects)
```

#### Dependency Direction

Senses does NOT import BaseItem or any object class. It stores `Dict[UUID, Tuple[int,int]]` — just UUIDs and positions. The caller (Entity) does the GridMap query and passes raw data down. This is the same pattern used for entities: Senses doesn't import Entity, it just stores UUIDs.

### Object Spatial Properties — Reference Table

| Object | blocks_movement | blocks_vision | Notes |
|--------|-----------------|---------------|-------|
| Closed door | True | True | Open door: both False |
| Open door | False | False | |
| Chest | True | False | Large enough to block path, not tall enough for vision |
| Lever | False | False | Small, wall-mounted |
| Statue | True | False | Blocks path, not tall enough (debatable) |
| Tall bookshelf | True | True | Full height obstacle |
| Item on ground | False | False | Sword, potion — tiny objects |
| Campfire | False | False | Could walk through (with damage?), doesn't block vision |
| Barricade | True | False | Cover but not vision block |

---

## 9. Environment Objects Design

This is the most open design question. The system needs to represent things that are NOT entities (they don't have turns, ability scores, or action economy) and NOT tiles (they're not the ground — they sit ON the ground) but exist in the game world with spatial presence and interactability.

### Option A: WorldObject(BaseBlock)

A new class specifically for environment objects:

```python
class WorldObject(BaseBlock):
    """An object in the environment that is not an entity or tile."""
    name: str = "Object"
    description: Optional[str] = None
    position: Tuple[int, int] = (0, 0)

    # Spatial properties
    blocks_movement: bool = False
    blocks_vision: bool = False

    # Optional inventory (for containers)
    inventory: Optional[Inventory] = None

    # Can be interacted with?
    def get_interaction_actions(self, entity_uuid: UUID) -> List[BaseAction]:
        """Return action templates for interacting with this object."""
        return []
```

**Registered with GridMap** via `gridmap.place_object()`. Has its own registry (inherits from BaseBlock).

**How it exposes actions to nearby entities**: The key question. Options:
1. Entity's `get_available_actions()` queries GridMap for nearby objects, calls `get_interaction_actions()` on each, adds results to a new `interaction_actions` category
2. Objects register temporary actions on entities when in range (complex, fragile)
3. A separate "interaction query" endpoint (breaks the "everything is an action" goal)

Option 1 is cleanest — it extends the existing `get_available_actions()` pattern.

**Pros**:
- Clean separation. Environment objects are not entities — they don't have unnecessary baggage (ability scores, health, senses, action economy)
- Lightweight — a lever is just a WorldObject with one action
- Natural for containers (has Inventory)

**Cons**:
- New class hierarchy to maintain
- `get_available_actions()` needs a new discovery path (GridMap query for nearby objects)
- WorldObject needs its own condition system? (BaseBlock already provides this)
- Missing some infrastructure that entities get for free (event handler registration, condition application)

Actually — `BaseBlock` already provides conditions, event handlers, and `ModifiableValue` storage. A `WorldObject(BaseBlock)` inherits all of that. It's not missing infrastructure — it's getting exactly what it needs without the entity overhead.

### Option B: Tile-Based

Add interaction capability to tiles. Instead of a separate object class, a tile can "have" interactable features.

```python
# A door as a tile:
door_tile = Tile.create(position=(5, 3), walkable=False, visible=False, name="Door")
door_tile.add_condition(DoorCondition(closed=True))
# DoorCondition has spatial handlers and interaction actions
```

**Pros**:
- Simplest implementation. No new class. Tiles already have conditions, position, spatial events.
- SpatialHandlers already fire at tile positions.

**Cons**:
- A chest IS NOT the tile it sits on. Multiple objects per tile becomes very awkward.
- A tile is the floor/wall — an object sits ON a tile. Conflating them breaks the spatial model.
- Tiles don't have inventory. Adding inventory to tiles is forced.
- "Floor with a chest on it" is not the same as "Chest Tile".

**Verdict**: Tile-based works for things that ARE the surface (difficult terrain, fire tiles, ice) but breaks for discrete objects (chests, levers, doors). A door could arguably be a tile (it IS the wall), but a chest cannot.

### Option C: Lightweight Entity

Use Entity with minimal config for environment objects.

```python
lever = Entity.create(
    name="Lever",
    source_entity_uuid=uuid4(),
    config=EntityConfig(
        ability_scores=AbilityScoresConfig(),  # Default 10s, unused
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=1, hit_dice_count=0)]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=0,
        position=(5, 3),
    ),
)
lever.register_action(PullLeverAction(source_entity_uuid=lever.uuid, template=True))
```

**Pros**:
- Everything works for free: GridMap tracks it, Senses sees it, conditions work, action registration works
- No new classes, no new discovery mechanism
- `get_available_actions()` already iterates registered actions

**Cons**:
- Extremely heavy for a lever: AbilityScores (6 blocks), SkillSet (18 skills), SavingThrowSet (6 saves), Health, Equipment, ActionEconomy, Senses — all meaningless for an object
- Entities have turns in combat. A lever doesn't take turns. How to exclude it from initiative?
- `_entity_registry` gets polluted with non-creature objects
- Semantic confusion: an entity is a creature that acts. A lever is not.

**Mitigation**: Could add `is_object: bool = False` flag on Entity to exclude from initiative, hide from "enemies" queries, etc. But this is a band-aid on a semantic mismatch.

### Option D: WorldObject(BaseItem)

What if environment objects ARE items — just non-pickable items with spatial presence?

```python
class Lever(BaseItem):
    is_pickable: bool = False
    blocks_movement: bool = False
    blocks_vision: bool = False

    def get_use_actions(self, entity_uuid: UUID) -> List[BaseAction]:
        return [PullLeverAction(source_entity_uuid=entity_uuid, template=True)]
```

This reuses BaseItem infrastructure. The lever is just a BaseItem that can't be picked up but can be used.

**Pros**:
- No new class — everything is a BaseItem. Simplifies the hierarchy.
- BaseItem already has spatial properties (`blocks_movement`, `blocks_vision`)
- Use actions are the same mechanism for items and environment objects
- Clear taxonomy: all things in the world are BaseItems. Some are pickable, some equippable, some usable, some none of the above (decorative).

**Cons**:
- A chest with inventory is a BaseItem with an Inventory. But BaseItem extends BaseBlock, and an Inventory is also a BaseBlock. Composition within composition — is this clean?
- Stacking, value, weight are meaningless for a lever. Harmless but semantically noisy.
- Large objects like buildings or complex terrain features feel wrong as "items".

### Analysis and Comparison

| Criterion | WorldObject | Tile-Based | Lightweight Entity | WorldObject(BaseItem) |
|-----------|-------------|------------|--------------------|-----------------------|
| New class? | Yes | No | No | No (reuses BaseItem) |
| Weight | Medium | Lightest | Heaviest | Light |
| Action discovery | New GridMap query | Via tile conditions | Existing | New GridMap query |
| Conditions/Handlers | Yes (BaseBlock) | Yes (Tile) | Yes (Entity) | Yes (BaseBlock) |
| Multiple per tile | Natural | Awkward | Natural | Natural |
| Inventory | Optional field | Forced addition | Heavy | Composition |
| Semantic fit | Good | Poor for objects | Poor | Good |
| Implementation effort | Medium | Low | Low | Low-Medium |

### Recommendation

**Option A (WorldObject) or Option D (WorldObject as BaseItem)** are the strongest choices. The decision between them depends on how we feel about the semantic question: "is everything in the world an item?"

**Option D is more elegant** if we accept that "BaseItem" is really "BaseWorldThing" — the fundamental building block for any discrete object that isn't the ground or a creature. The name `BaseItem` is slightly misleading for a bolted lever, but the interface is perfect.

**Option A is cleaner** if we want a clear distinction between items (things you interact with in your inventory/equipment) and world objects (things you interact with in the environment).

Both require the same GridMap integration (Section 8) and the same action discovery mechanism (Section 11).

---

## 10. Looting System

### Death → Loot Body (Equipment Block Transfer)

> **Revised**: With the Equipment-contains-Inventory design (Section 16), death-to-loot becomes much simpler. The entire Equipment block — with its Inventory of carried items and all equipped items — transfers to a body object.

When an entity dies:

1. **Entity condition cleanup runs automatically** via `_remove_condition_tree()`
   - Entity-dependent conditions are cleaned up (concentration, class features, rage, etc.)
   - Conditions on ITEMS that were entity-dependent (e.g., a spell buff on a weapon from this entity's concentration) get cleaned up via `external_conditions` traversal
   - Conditions on items that are intrinsic (permanent enchantments, poison applied by another entity) **persist** — they're on the item, not on the entity

2. **Create loot body** at the dead entity's position
   - The body IS a world object that receives the dead entity's Equipment block wholesale
   - No need to iterate slots and transfer items one by one — the Equipment block already contains everything (Inventory sub-block + equipped items in typed slots)
   - Item conditions that survived the cleanup persist naturally

```python
# In death handling (after Dead condition applied):
def _create_loot_body(dead_entity: Entity) -> LootBody:
    body = LootBody(
        name=f"{dead_entity.name}'s Body",
        position=dead_entity.senses.position,
        equipment=dead_entity.equipment,  # Transfer entire Equipment block
    )
    gridmap.place_object(body.uuid, body.position)
    return body
```

3. **Body persists** on the grid
   - The dead entity becomes non-blocking (existing: `_non_blocking_entities`)
   - The loot body is a separate world object at the same position

### Why Equipment Transfer Works

The key insight from Section 16: Equipment contains Inventory. When Equipment transfers to the body:
- All **carried items** (in `equipment.inventory`) come along
- All **equipped items** (in typed slots: weapons, armor, rings, etc.) come along
- Item conditions persist because they're on the items, not on the entity
- The body's Equipment is the same object — no copying, no re-creation

This is much cleaner than the old "iterate each slot, unequip, transfer" approach:
- No `_on_unequip` hooks fire (items aren't being unequipped — they're still in their slots)
- No action unregistration needed (the entity is dead — its actions don't matter)
- A permanent enchantment on a sword stays enchanted in the body
- A poison condition on a weapon from another entity stays active

### Looting Flow

1. Entity moves adjacent to loot body (or stands on it)
2. `get_available_actions()` discovers the body's "Loot" action via nearby object query
3. Entity uses "Loot" action → browses body's equipment/inventory
4. **Item transfer**: Select items to take → transfer to entity's Equipment.inventory
5. Each transferred item: `body.equipment.inventory.remove_item()` → `entity.equipment.inventory.add_item()` + `item.loot()`
6. Usable items appear automatically in `get_available_actions()` (Section 15 — discovered at query time, not registered)

### The "Loot" Action

**Option 3 is most practical**: The action takes `item_uuids: List[UUID]` — the consumer (AI/UI) first queries the body's contents, then issues the Loot action with selected items.

```python
class LootAction(BaseAction):
    container_uuid: UUID
    item_uuids: List[UUID] = []  # Items to take

    def _apply(self, execution_event: Event) -> Event:
        container = BaseBlock.get(self.container_uuid)  # LootBody or Chest
        entity = Entity.get(self.source_entity_uuid)
        for item_uuid in self.item_uuids:
            item = container.equipment.inventory.remove_item(item_uuid)
            if item:
                entity.add_to_inventory(item)
        return execution_event.phase_to(EventPhase.EFFECT)
```

### Dropped Items on Ground

Simpler case — no container. An item is just placed at a grid position:
- `gridmap.place_object(item.uuid, position)`
- Entity adjacent → "Pick Up" action appears
- Pick up = remove from GridMap → add to entity inventory

### Integration with Encounter Death Handling

The encounter already calls `encounter.check_deaths()`. The loot body creation hooks into the death handling. Because Equipment transfers wholesale, this is trivial:

```python
def _create_loot_body(dead_entity: Entity) -> LootBody:
    body = LootBody(
        position=dead_entity.senses.position,
        equipment=dead_entity.equipment,  # Wholesale transfer
    )
    gridmap.place_object(body.uuid, body.position)
    return body
```

---

## 11. Integration with get_available_actions

### The Three Sources of Actions

> **Revised**: With the Inventory-as-action-manager design (Section 15), inventory items are no longer registered on the entity. They're discovered at query time, alongside environment objects.

Currently, `get_available_actions()` iterates over `entity.registered_actions` — a flat list of templates registered on the entity. With the item system, actions come from **three sources**:

1. **Entity registered actions**: Move, Dash, Dodge, Attack, class features (SecondWind, Rage), equip-granted actions — these stay registered on Entity as today. ✅ Existing system.

2. **Inventory item actions**: Discovered dynamically from `Equipment.inventory.get_all_use_actions()` at query time. NOT registered on entity. Items' `get_use_actions()` is called fresh each query → naturally adaptive (charges, state, conditions). See Section 15.

3. **Environment objects**: Objects near the entity offer interaction actions, discovered via GridMap query for nearby visible objects. NOT registered on entity.

Sources 2 and 3 are both **discovered at query time** (new pattern). Source 1 is **registered on entity** (existing pattern). The key insight: **items in inventory don't register** — they're discovered.

### Environment Object Action Discovery

**Current flow** (simplified):
```python
def get_available_actions(self, target_filter="enemies", include_dead=False):
    result = AvailableActionsResult(entity_uuid=self.uuid, ...)

    for action in self.self_actions:     # TargetType.SELF
        # validate, add to result.self_actions
    for action in self.entity_actions:   # TargetType.ENTITY
        # validate per visible entity, add to result.entity_actions
    for action in self.position_actions: # TargetType.POSITION_*
        # validate per reachable position, add to result.position_actions

    return result
```

**Extended flow** with inventory actions and environment objects:
```python
def get_available_actions(self, target_filter="enemies", include_dead=False):
    result = AvailableActionsResult(entity_uuid=self.uuid, ...)

    # 1. Registered actions (existing: entity_actions, position_actions, self_actions)
    for action in self.registered_actions:
        # ... existing validation logic ...

    # 2. Inventory item actions (NEW: discovered from Equipment.inventory)
    for action in self.equipment.inventory.get_all_use_actions(self.uuid):
        # Validate and add to appropriate category based on action.target_type
        # Same validation as registered actions (pre_validate, cost check, etc.)
        if action.target_type == TargetType.SELF:
            result.self_actions.append(info)
        elif action.target_type in (TargetType.ENTITY, TargetType.MULTI_ENTITY):
            result.entity_actions.append(info)
        else:
            result.position_actions.append(info)

    # 3. Environment object actions (NEW: discovered from nearby visible objects)
    for obj_uuid, obj_pos in self.senses.objects.items():
        obj = BaseItem.get(obj_uuid)  # or WorldObject.get()
        if obj is None:
            continue
        distance = self.senses.get_feet_distance(obj_pos)
        if distance > 5:  # Must be adjacent (5 feet) for interaction
            continue
        for action in obj.get_use_actions(self.uuid):
            if action.pre_validate():
                info = AvailableActionInfo(
                    template_name=action.name,
                    target_type=action.target_type,
                    valid_targets=[...],
                    can_afford=True,
                    is_item_use=True,
                    source_item_uuid=obj.uuid,
                    ...
                )
                # Add to appropriate category based on target_type
                if action.target_type == TargetType.SELF:
                    result.self_actions.append(info)
                elif action.target_type in (TargetType.ENTITY, TargetType.MULTI_ENTITY):
                    result.entity_actions.append(info)
                else:
                    result.position_actions.append(info)

    return result
```

### AvailableActionInfo Extensions

```python
class AvailableActionInfo(BaseModel):
    # Existing
    template_name: str
    target_type: TargetType
    valid_targets: List[AvailableTarget]
    can_afford: bool
    is_attack: bool = False
    is_spell: bool = False

    # NEW
    is_item_use: bool = False           # True for item Use actions
    source_item_uuid: Optional[UUID] = None  # The item this action comes from
    source_object_uuid: Optional[UUID] = None  # For environment object interactions
```

### AvailableActionsResult Extensions

**Option A: New category**
```python
class AvailableActionsResult(BaseModel):
    entity_actions: List[AvailableActionInfo]
    position_actions: List[AvailableActionInfo]
    self_actions: List[AvailableActionInfo]
    interaction_actions: List[AvailableActionInfo]  # NEW: environment object interactions
    remaining_movement: int
```

**Option B: Fold into existing categories**
Environment object actions are added to the existing categories based on their `target_type`. A lever (SELF) goes into `self_actions`. A key targeting a door (ENTITY) goes into `entity_actions`.

**Recommendation**: Option B (fold into existing categories) with the `is_item_use` flag. This achieves the goal: "for AI or UI it would be better if we can consider them as any other action." The flags provide metadata for UI rendering (show item icon, show "Use:" prefix) without changing the action selection flow.

### Execute Flow — Three-Source Search

`execute_by_index()` must search all three action sources, not just `entity.registered_actions`:

```python
def execute_by_index(entity, template_name, target_index):
    # 1. Try registered actions first (existing: entity actions, class features)
    action = find_in_registered(entity, template_name)

    # 2. If not found, try inventory actions
    if action is None:
        action = find_in_inventory(entity, template_name)

    # 3. If not found, try environment objects
    if action is None:
        action = find_in_environment(entity, template_name)

    # Instantiate and apply
    if action is not None:
        instance = action.instantiate(target_entity_uuid=target.uuid)
        return instance.apply()
```

**Simplest approach**: All three sources return action templates with `source_entity_uuid` set to the using entity. Templates can be instantiated and applied identically. The only difference is WHERE they're discovered — registered vs. inventory vs. environment. The consumer (AI/UI) doesn't see the distinction — actions are actions.

---

## 12. Implementation Phases

### Phase 1: BaseItem Class + Migration (Foundation)

**Goal**: Introduce `BaseItem(BaseBlock)` in `dnd/core/base_item.py`. Reparent Weapon, Armor, Shield.

**Changes**:
- New file: `dnd/core/base_item.py` with BaseItem class
- Modify: `dnd/blocks/equipment.py` — Weapon, Armor, Shield inherit BaseItem instead of BaseBlock
- Modify: All weapon/armor factories — no changes needed (BaseItem fields have defaults)
- Test: All existing tests must pass unchanged

**Dependencies**: None. Pure refactor.

**Testable independently**: Yes. Run full pytest suite to verify no regression.

### Phase 2: Equip/Unequip Hooks

**Goal**: Add `_on_equip()` / `_on_unequip()` hooks to BaseItem and call them from Equipment.equip()/unequip().

**Changes**:
- Add default no-op hooks on BaseItem
- Modify `Equipment.equip()` to call `item._on_equip()` after slot assignment
- Modify `Equipment.unequip()` to call `item._on_unequip()` before slot clear
- Create test magic item (Ring of Protection) to validate the hook system

**Dependencies**: Phase 1

**Testable independently**: Yes. Create a test with a magic ring that adds +1 AC on equip and removes it on unequip.

### Phase 2.5: Enable Conditions on Items

**Goal**: Flip `allow_events_conditions=True` on BaseItem. Extend `_remove_condition_tree` to handle item external conditions.

**Changes**:
- Set `allow_events_conditions=True` on BaseItem (inherits from BaseBlock's default of `False`)
- Extend `Entity._remove_condition_tree()`: when traversing `external_conditions`, the first UUID may be a block UUID (item) rather than an entity UUID. Change `Entity.get(target_uuid)` to fall back to `BaseBlock.get(uuid)` for non-entity targets — or use `BaseBlock.get()` for ALL external condition cleanup (it works for entities too since Entity inherits BaseBlock)
- Test: Apply a condition to a weapon (e.g., MagicWeaponCondition), verify it adds modifiers. Remove it, verify cleanup. Test concentration linkage: caster's Concentrating condition has `external_conditions` pointing to item condition → breaking concentration removes item condition

**Dependencies**: Phase 1, Phase 2

**Testable independently**: Yes. Create a weapon, apply a condition, verify modifier applies. Break concentration, verify item condition cleaned up.

### Phase 3: Inventory Block (as Equipment Sub-Block)

**Goal**: Create `Inventory(BaseBlock)` as a sub-block of Equipment.

**Changes**:
- New: `Inventory` class with add/remove/find/transfer methods + `get_all_use_actions()` aggregator
- Modify: Equipment — add `inventory: Inventory` field (Equipment contains Inventory)
- Add: `entity.add_to_inventory()` / `entity.remove_from_inventory()` wrapper methods that delegate to `entity.equipment.inventory`
- Inventory is also independently usable (for chests, bags — see Phase 6)
- Test: Add items to inventory, verify weight tracking, test transfers

**Dependencies**: Phase 1

**Testable independently**: Yes. Create items, add to inventory, verify container operations.

### Phase 4: Use Action Interface (Query-Time Discovery)

**Goal**: Implement `get_use_actions()` on BaseItem and integrate with action template system via Inventory aggregation.

**Changes**:
- Add `get_use_actions(owner_uuid)` to BaseItem (returns `[]` by default)
- Add `source_item_uuid` field to BaseAction
- Modify `get_available_actions()` to query `equipment.inventory.get_all_use_actions()` (Section 15 — discovered at query time, NOT registered)
- Modify `execute_by_index()` to search inventory actions as a second source
- Create test items: Potion of Healing (consumable, SELF target), Scroll of Fireball (wraps existing action)
- Add consumable destruction logic to BaseAction.apply()

**Dependencies**: Phase 1, Phase 3

**Testable independently**: Yes. Create potion, add to inventory, verify "Drink Potion" appears in get_available_actions(), execute it, verify healing and potion destruction.

### Phase 5: GridMap/Senses Integration for Objects

**Goal**: Objects can exist on the grid and be seen by entities.

**Changes**:
- Add `_object_positions` and `_objects_by_position` to GridMap
- Add `place_object()`, `remove_object()`, `get_objects_at()` to GridMap
- Modify `is_walkable_for()` to check object blocking
- Modify `is_blocking()` to check object vision blocking
- Add `objects` field to Senses
- Modify Entity.update_entity_senses() to populate `senses.objects`

**Dependencies**: Phase 1 (BaseItem has blocks_movement/blocks_vision)

**Testable independently**: Yes. Place an object, verify entity can see it, verify movement blocked by chest, verify vision blocked by bookshelf.

### Phase 6: Environment Objects

**Goal**: Objects in the world with interaction actions.

**Changes**:
- Decide on WorldObject approach (Option A or D from Section 9)
- Create concrete examples: Door (open/close toggles spatial), Lever (custom action), Chest (has inventory)
- Extend `get_available_actions()` to discover nearby object interactions (third source)
- Extend execute flow to handle object-sourced actions (third source in `execute_by_index`)

**Dependencies**: Phase 4, Phase 5

**Testable independently**: Yes. Place a lever, move entity adjacent, verify "Pull Lever" appears in available actions, execute it.

### Phase 6.5: Breakable Objects

**Goal**: Subset of objects can be attacked and broken.

**Changes**:
- Add `is_targetable`, `object_ac`, `health`, `damage_immunities` fields to BaseItem (Section 14)
- Add `is_breakable()`, `receive_damage()`, `_on_break()` methods to BaseItem
- Create `AttackObject` action — dedicated melee action targeting adjacent objects with `is_targetable=True`
- AoE side-effects: Add `include_objects: bool = False` flag on BaseAction. When True, separate damage pass after entity convolution loop applies damage to targetable objects in AoE
- Concrete test: Wooden door (AC 15, HP 18) — attack it, break it, verify it opens permanently

**Dependencies**: Phase 5, Phase 6

**Testable independently**: Yes. Create a door with HP, attack it, verify damage applies, break it, verify spatial state changes.

### Phase 7: Looting System (Simplified by Equipment Transfer)

**Goal**: Death drops loot body, entities can loot.

**Changes**:
- Create LootBody (world object that receives dead entity's Equipment block wholesale)
- Hook into death handling: entity condition cleanup runs automatically, then Equipment block transfers to body
- Implement LootAction for picking up items from body/containers
- Implement PickUpAction for individual items on ground
- Item-intrinsic conditions persist through transfer. Entity-dependent conditions are already cleaned up.

**Dependencies**: Phase 3, Phase 6

**Testable independently**: Yes. Kill an entity, verify loot body created with intact Equipment, loot items, verify they enter inventory.

### Phase 8: Consumable Items as Test Cases

**Goal**: Create a set of representative items that stress-test the system.

**Items to implement**:
- Potion of Healing (consumable, SELF, custom action)
- Scroll of Fireball (consumable, wraps SpellAction)
- Ring of Protection (equip hook, +1 AC condition)
- Wand of Fire Bolt (equip hook, grants action via condition)
- Cursed Ring (equip hook, blocks unequip via event handler)
- Magic Weapon spell (condition on item via concentration — Section 13)
- Chest with trap (environment object, multi-step Use action)
- Door (environment object, breakable, toggles spatial properties)
- Wooden Barricade (breakable, blocks movement, no use action)

**Dependencies**: All previous phases

**Testable**: Full integration tests validating all pathways.

> **Note**: Equipment.py file splitting (separating modifiers from slots) should be re-evaluated after Phase 3 when the natural boundaries between Equipment and Inventory become concrete. See Section 16 for analysis.

### Dependency Graph

```
Phase 1 (BaseItem) ─────────────────────────────────────┐
    │                                                    │
    ├── Phase 2 (Equip Hooks) ──┐                        │
    │                           │                        │
    │            Phase 2.5 (Item Conditions) ─────────   │
    │                                                │   │
    ├── Phase 3 (Inventory/Equipment) ──┐            │   │
    │                                   │            │   │
    │         Phase 4 (Use Actions) ────┤            │   │
    │                                   │            │   │
    │         Phase 5 (GridMap) ────────┤            │   │
    │                                   │            │   │
    │         Phase 6 (Env Objects) ────┤            │   │
    │                                   │            │   │
    │         Phase 6.5 (Breakable) ────┤            │   │
    │                                   │            │   │
    │         Phase 7 (Looting) ────────┤            │   │
    │                                                │   │
    └───────────────────── Phase 8 (Test Cases) ─────────┘
```

Phases 2, 3, and 5 can run in parallel after Phase 1. Phase 2.5 needs 1+2. Phase 4 needs 1+3. Phase 6 needs 4+5. Phase 6.5 needs 5+6. Phase 7 needs 3+6. Phase 8 is the capstone.

---

## 13. Conditions on Items

### The Insight

Items are BaseBlocks. BaseBlock already has the full condition/handler infrastructure — `add_condition()`, `remove_condition()`, `add_event_handler()`, condition immunities, and the full cleanup tree (`base_block.py:540-604`). Today `allow_events_conditions=False` on BaseBlock (line 142), and Tiles already override this to `True` (`base_tiles.py:59`). Setting `allow_events_conditions=True` on BaseItem gives items the same capability at zero infrastructure cost.

### Why It's Nearly Free

BaseBlock provides:
- `add_condition()` (line 585) — applies condition, manages `active_conditions` dict
- `remove_condition()` (line 555) — removes condition and recursively collects sub-conditions via `_collect_all_sub_conditions()` (line 540)
- `add_event_handler()` — registers handlers for event reactions
- Full modifier channel system via ModifiableValues (already on Weapon: `attack_bonus`, `damage_bonus`)

Tiles demonstrate this works for non-entity blocks. Setting `allow_events_conditions=True` on BaseItem enables the same for items — weapon enchantments, door lubricants, poisoned blades, etc.

### Use Cases

**Weapon enchantment (Magic Weapon spell)**: Wizard casts "Magic Weapon" on a sword → applies `MagicWeaponCondition` to the Weapon block → condition adds +1 to the weapon's `attack_bonus` ModifiableValue → entity attacking with it automatically benefits because Attack already reads from `weapon.attack_bonus`.

**Poisoned blade**: Apply `PoisonCondition` to a weapon → condition registers an EventHandler on ATTACK events → when the weapon hits, the handler applies poison to the target entity.

**Flame enchantment**: Apply to weapon → adds extra fire damage via modifier on `extra_damage_*` fields → automatically included in attack damage computation.

**Door lubricant**: Apply `LubricatedCondition` to a door → modifies the door's "open difficulty" (a ModifiableValue on the door) → lower DC to force open.

### Concrete Example — Magic Weapon Spell

```python
class MagicWeaponSpell(SpellAction):
    def _apply(self, event):
        weapon = BaseBlock.get(self.target_item_uuid)  # Target is the weapon
        caster = Entity.get(self.source_entity_uuid)

        # Apply enchantment condition to the WEAPON
        enchantment = MagicWeaponCondition(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=weapon.uuid,  # target is the weapon block
            bonus=self.bonus,
        )
        weapon.add_condition(enchantment)

        # Concentration on the CASTER tracks the enchantment for cleanup
        concentrating = Concentrating(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            spell_name="Magic Weapon",
            external_conditions=[(weapon.uuid, enchantment.uuid)],
        )
        caster.add_condition(concentrating)
```

```python
class MagicWeaponCondition(BaseCondition):
    name: str = "MagicWeaponCondition"
    bonus: int = 1

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        weapon = BaseBlock.get(self.target_entity_uuid)  # "target" is the weapon
        modifier_uuid = weapon.attack_bonus.self_static.add_value_modifier(
            NumericalModifier(name="Magic Weapon", value=self.bonus, ...)
        )
        outs = [(weapon.attack_bonus.uuid, modifier_uuid)]
        # Also add to damage
        dmg_mod_uuid = weapon.damage_bonus.self_static.add_value_modifier(
            NumericalModifier(name="Magic Weapon", value=self.bonus, ...)
        )
        outs.append((weapon.damage_bonus.uuid, dmg_mod_uuid))
        return outs, [], [], [], effect_event
```

### Key Design Questions

**1. Who applies conditions to items?**
A spell targets an item (not an entity). The simplest approach: the spell's `_apply()` directly calls `item.add_condition(...)`. No need for a `TargetType.ITEM` — the spell knows it targets a weapon and handles it specifically. More formal targeting (e.g., "choose a weapon within range") can be added later if needed.

**2. Duration/expiration**: Same as entity conditions. Duration field, turn-end removal, concentration dependency. No new infrastructure needed.

**3. Concentration linkage**: Caster → Concentrating condition → `external_conditions` points to `(weapon.uuid, enchantment.uuid)`. When concentration breaks, Entity's `_remove_condition_tree()` traverses `external_conditions` and cleans up the item condition. This uses the EXISTING `external_conditions: List[Tuple[UUID, UUID]]` pattern — just the second UUID is an item UUID instead of an entity UUID.

**4. What happens when item changes hands?** Condition persists — it's on the item, not the entity. A poisoned sword stays poisoned when looted. An enchanted weapon stays enchanted when dropped.

**5. What happens when item is destroyed?** `item.destroy()` must clean up conditions: call `remove_condition()` for each active condition. Same cleanup pattern as entity death.

### `_remove_condition_tree` Extension

The existing Entity `_remove_condition_tree()` (entity.py:347-387) traverses `external_conditions` as `(target_uuid, condition_uuid)`:

```python
# Current code (entity.py:372-375):
for target_uuid, cond_uuid in condition.external_conditions:
    target = Entity.get(target_uuid)  # ← This returns None for items!
    if target:
        target.remove_condition_by_uuid(cond_uuid)
```

For items, the first UUID isn't an entity — it's a block UUID. The fix: use `BaseBlock.get()` as fallback (or for ALL external condition cleanup, since it works for entities too — Entity inherits BaseBlock):

```python
# Extended code:
for target_uuid, cond_uuid in condition.external_conditions:
    target = Entity.get(target_uuid)
    if target:
        target.remove_condition_by_uuid(cond_uuid)
    else:
        # Try as a BaseBlock (item, tile, etc.)
        block = BaseBlock.get(target_uuid)
        if block and hasattr(block, 'remove_condition_by_uuid'):
            block.remove_condition_by_uuid(cond_uuid)
```

**Do items need the full `_remove_condition_tree`?** Probably NOT — items don't usually host conditions that have `external_conditions` on other objects. Items receive conditions, they don't cascade them to other targets. The tree traversal only needs to work from the entity (caster) down to the item, not from the item outward. BaseBlock's simpler `remove_condition()` (which handles sub-conditions recursively) is sufficient for item-side cleanup.

### Code References

| Reference | What |
|-----------|------|
| `base_block.py:142` | `allow_events_conditions: bool = False` |
| `base_block.py:540-553` | `_collect_all_sub_conditions()` — recursive sub-condition traversal |
| `base_block.py:555-583` | `remove_condition()` — handles sub-conditions on same block |
| `base_block.py:585-604` | `add_condition()` — applies condition with event |
| `base_tiles.py:59` | Tile sets `allow_events_conditions=True` (precedent) |
| `entity.py:347-387` | `_remove_condition_tree()` — handles external + terrain conditions |

---

## 14. Breakable/Targetable Objects

### The Insight

Some objects should be attackable — doors, chests, wooden barricades. D&D 5e has rules for object AC and HP. Not ALL objects — a lever or campfire shouldn't be targetable. Breakability is **opt-in**, associated with having a Health sub-block and `is_targetable=True`.

### D&D 5e Object Rules

Objects have AC based on material and HP based on size:

| Material | AC | Examples |
|----------|---:|---------|
| Cloth/Paper/Rope | 11 | Tapestry, scroll case |
| Crystal/Glass/Ice | 13 | Window, vial |
| Wood/Bone | 15 | Door, chest, barricade |
| Stone | 17 | Statue, stone wall |
| Iron/Steel | 19 | Iron door, portcullis |
| Mithral | 21 | Mithral gate |
| Adamantine | 23 | Adamantine vault |

| Size | HP Range | Example |
|------|----------|---------|
| Tiny | 1d4 (2) | Vial, lock |
| Small | 1d6 (3) | Chest lid |
| Medium | 3d8 (13) | Barrel, door |
| Large | 4d10 (22) | Cart, tall bookshelf |
| Huge | 5d12 (32) | Large statue |

**Object immunities**: Poison and psychic damage. Objects automatically fail STR and DEX saves. Objects can't be charmed, frightened, etc.

### Proposed Design

BaseItem gains optional breakable fields (see updated Section 4):

```python
class BaseItem(BaseBlock):
    # ... existing fields ...

    # Breakable/targetable properties
    is_targetable: bool = False          # Can this object be attacked/targeted?
    object_ac: int = 15                  # AC (D&D material-based, not ModifiableValue)
    health: Optional[Health] = None      # If present and is_targetable, object has HP
    damage_immunities: List[DamageType] = [DamageType.POISON, DamageType.PSYCHIC]

    def is_breakable(self) -> bool:
        """Object can be broken = targetable + has health."""
        return self.is_targetable and self.health is not None

    def receive_damage(self, amount: int, damage_type: DamageType, source_uuid: UUID) -> int:
        """Apply damage to this object. Returns actual damage dealt."""
        if damage_type in self.damage_immunities:
            return 0
        if self.health is None:
            return 0
        actual = min(amount, self.health.current_hp)
        self.health.current_hp -= actual
        if self.health.current_hp <= 0:
            self._on_break()
        return actual

    def _on_break(self) -> None:
        """Override in subclasses for break behavior."""
        pass  # Door: permanently opens. Chest: spills contents. Barricade: removed.
```

**Why `object_ac` is a plain int, not a ModifiableValue**: Objects are simple. Their AC is a fixed property of their material. No conditions modify object AC in standard D&D 5e. A plain int avoids unnecessary complexity. If we later need modifiable object AC (reinforced doors?), we can upgrade.

### Attack Targeting for Objects

Objects are NOT mixed into the normal Attack action's entity targets. Instead, a dedicated `AttackObject` action (or `BreakObject`) targets an adjacent object:

```python
class AttackObject(BaseAction):
    """Attack a targetable object. Uses melee weapon, simple AC check."""
    target_type: TargetType = TargetType.ENTITY  # Target is the object (by UUID)
    target_object_uuid: UUID

    def _validate(self, event):
        obj = BaseBlock.get(self.target_object_uuid)
        if not obj or not obj.is_targetable:
            return event.cancel("Object is not targetable")
        # Check adjacency (5 feet)
        ...

    def _apply(self, event):
        obj = BaseBlock.get(self.target_object_uuid)
        # Roll attack vs object_ac
        # On hit: obj.receive_damage(damage, type, self.source_entity_uuid)
        ...
```

This is discovered in `get_available_actions()` from nearby visible objects that have `is_targetable=True`. It keeps the regular Attack action clean — Attack targets entities, AttackObject targets objects.

### Integration with AoE

Current AoE flow (`base_actions.py:271-313`) only targets entities:

```python
# In get_all_targets():
targets = list(shape.affected_entity_uuids)  # Only entities!
```

For breakable objects in AoE zones, we add a **separate damage pass after the entity convolution loop**, controlled by an opt-in flag:

```python
class BaseAction(BaseModel):
    include_objects: bool = False  # New flag, default False

# In apply(), after entity convolution (base_actions.py:539-633):
if self.include_objects:
    grid = get_map()
    for pos in shape.affected_positions:
        for oid in grid.get_objects_at(pos):
            obj = BaseBlock.get(oid)
            if obj and getattr(obj, 'is_targetable', False):
                obj.receive_damage(damage, damage_type, self.source_entity_uuid)
```

**Why a separate pass, not a unified target list**: The `apply()` convolution loop (base_actions.py:539-633) assumes targets are entities — calls `Entity.get()`, expects health, saving throws, AC from Equipment, etc. Objects are NOT entities. Mixing them into the entity loop would require extensive refactoring. A separate, simpler damage pass keeps the entity pipeline clean.

**Incremental approach**: Since this is additive, start with `include_objects=False` (default). Only specific spells opt in. Fireball might set `include_objects=True` because D&D says "The fire spreads around corners. It ignites flammable objects in the area that aren't being worn or carried." Most spells don't explicitly damage objects and keep the default.

### Breakable Objects — Reference Table

| Object | Targetable | AC | HP | Material | Break Effect |
|--------|-----------|---:|---:|----------|-------------|
| Wooden Door | Yes | 15 | 18 | Wood | Opens permanently, stops blocking movement/vision |
| Chest | Yes | 15 | 27 | Wood | Spills inventory contents on ground |
| Barricade | Yes | 15 | 12 | Wood | Removed from grid, stops blocking movement |
| Statue | Yes | 17 | 20 | Stone | Becomes rubble, stops blocking movement |
| Trapped Chest | Yes | 15 | 27 | Wood | Same as chest (trap is a condition, not HP-based) |
| Lever | No | — | — | — | Not targetable — interact, don't break |
| Potion | No | — | — | — | Not targetable — too small, use instead |
| Sword | No | — | — | — | Not targetable — weapons don't break in D&D 5e |

### Code References

| Reference | What |
|-----------|------|
| `base_actions.py:271-313` | `get_all_targets()` — entity-only targeting |
| `aoe.py:137-170` | `compute_objective()` — populates `affected_entity_uuids` only |
| `base_actions.py:539-633` | `apply()` convolution loop — entity-centric |
| `blocks/health.py` | Health block — potential sub-block for breakable objects |
| `gridmap.py` | `get_entities_at()` — parallel `get_objects_at()` needed |

---

## 15. Inventory as Action Manager

### The Insight

Instead of Entity manually registering/unregistering item actions when items enter or leave inventory, **Inventory manages the action lifecycle**. Item actions are "inventory actions" — discovered from Inventory at query time, not registered on Entity.

### The Problem with Registration

The original design (Sections 5/7) had Entity orchestrating action registration:

```
item enters inventory → Entity.add_to_inventory() calls item.get_use_actions()
→ registers each as template on Entity → appears in get_available_actions()
item leaves → Entity unregisters actions
```

This has problems:
1. **Registration/unregistration dance**: Every loot and drop requires register/unregister calls
2. **State changes require re-registration**: When a wand's charges change, its available actions change — but the registered templates are stale
3. **Complexity**: Entity must track which registered actions came from which items for cleanup

### The Better Design — Query-Time Discovery

```
item enters inventory → stored in Equipment.inventory
get_available_actions() asks inventory.get_all_use_actions(owner_uuid)
→ Inventory iterates items, calls each item.get_use_actions()
→ returns aggregated list → naturally adaptive, no registration needed
item leaves → action disappears automatically (not in inventory anymore)
```

### Why This Is Better

1. **No registration/unregistration dance**: Items don't need to register actions on Entity when looted and unregister when dropped. The action exists because the item is in the inventory.

2. **Naturally adaptive**: `get_use_actions()` is called at query time → charge-based items, conditional items, state-dependent items all work without re-registration. A Wand of Fireballs at 0 charges returns `[]` — no unregister needed.

3. **Inventory owns the mapping**: Inventory knows which items it has, which are usable, and can filter/gate them. E.g., "this item can't be used while you're in combat" is an Inventory-level check.

4. **Environment objects work the same way**: A chest's Inventory exposes its items' actions. No difference between "your inventory" and "a chest's inventory" — same `get_all_use_actions()` call.

5. **Execution path**: `execute_by_index()` searches inventory as a second source after `entity.registered_actions`.

### Inventory as Action Aggregator

```python
class Inventory(BaseBlock):
    items: Dict[UUID, BaseItem] = {}

    def get_all_use_actions(self, owner_uuid: UUID) -> List[BaseAction]:
        """Aggregate all Use actions from all items.
        Called by get_available_actions() at query time."""
        actions = []
        for item in self.items.values():
            actions.extend(item.get_use_actions(owner_uuid))
        return actions
```

### Three Action Sources Revisited

With this design, `get_available_actions()` draws from three sources:

| Source | Mechanism | Examples |
|--------|-----------|---------|
| 1. Entity registered actions | `entity.registered_actions` (existing) | Move, Dash, Dodge, Attack, SecondWind, Rage, equip-granted actions |
| 2. Inventory actions | `equipment.inventory.get_all_use_actions()` (NEW) | Potion, scroll, wand charges |
| 3. Environment object actions | GridMap query → `obj.get_use_actions()` (NEW) | Lever, chest, door |

Sources 1 are registered on Entity (existing pattern). Sources 2 and 3 are discovered at query time (new pattern). The key insight: **items in inventory don't register — they're discovered.**

### Impact on Existing Sections

- **Section 4** (BaseItem): `get_use_actions()` is still the item's responsibility. No change to the item interface.
- **Section 5** (Use Action Interface): Items still implement `get_use_actions()`. The recommendation (Option D) still holds. The change is in WHO calls it and WHEN.
- **Section 7** (Inventory): `add_to_inventory()`/`remove_from_inventory()` become simpler — just add/remove the item and call hooks. No action registration.
- **Section 11** (get_available_actions): Adds inventory action discovery as a new source alongside registered and environment actions.

---

## 16. Equipment.py Separation — Equipment Contains Inventory

### The Insight

Equipment.py currently does three things in one file:

1. **Item class definitions** (Weapon, Armor, Shield, subtypes) — lines 98-283
2. **Combat stat storage + computation** — 16+ ModifiableValues (ac_bonus, attack_bonus, damage_bonus, crit thresholds, etc.) + methods (get_damages, get_armored_ac_values, etc.) — lines 387-661
3. **Slot management + equip/unequip** — typed slots (13 slots), equip events, validation — lines 663-942

Additionally, the user identified that "equipment could contain inventory" — making Equipment the comprehensive item management block.

### Option A: Extract Item Definitions Only

With BaseItem, Weapon/Armor/Shield move to their own module(s). Equipment block stays unified but smaller.

```
dnd/core/base_item.py     → BaseItem
dnd/blocks/equipment.py   → Equipment block (slots + modifiers + computation + equip/unequip)
dnd/items/weapons.py      → Weapon class + factories (existing, add BaseItem parent)
dnd/items/armors.py       → Armor/Shield classes + factories (existing, add BaseItem parent)
```

**Pro**: Minimal disruption. Equipment keeps its cohesion.
**Con**: Still one large block doing multiple things.

### Option B: Split Equipment into CombatStats + EquipmentSlots

```
dnd/blocks/combat_stats.py → CombatStats block (ac_bonus, attack_bonus, damage_bonus,
                              crit thresholds, get_damages(), get_armored_ac_values())
dnd/blocks/equipment.py    → EquipmentSlots block (13 typed slots, equip/unequip, equip events)
```

Entity has both as blocks. EquipmentSlots calls into CombatStats when items change.

**Pro**: Each file has one responsibility.
**Con**: `equip()` needs to know about modifiers (weapon damage depends on equipment modifiers) → tight coupling between the two. Many methods need data from both (`get_damages` needs slot + modifiers + ability scores).

### Option C: Equipment Contains Inventory (Recommended)

Equipment block OWNS an Inventory as a sub-block. Equipment becomes the comprehensive "item management" block:

```python
class Equipment(BaseBlock):
    # Typed equipment slots (existing)
    helmet: Optional[Helmet] = None
    body_armor: Optional[BodyArmor] = None
    weapon_melee_main: Optional[Weapon] = None
    # ... all existing slots ...

    # NEW: General storage (carried items not in slots)
    inventory: Inventory = Inventory(...)

    # Existing combat modifiers (unchanged)
    ac_bonus: ModifiableValue = ...
    attack_bonus: ModifiableValue = ...
    # ... all existing modifiers ...

    # Equipping = moving from inventory to slot
    def equip(self, item_uuid: UUID, slot: ...):
        item = self.inventory.remove_item(item_uuid)
        if item:
            # ... existing slot assignment + events ...
            item.equip(slot)  # Hook

    # Unequipping = moving from slot back to inventory
    def unequip(self, slot: ...):
        item = self._get_item_at_slot(slot)
        if item:
            item.unequip(slot)  # Hook
            # ... existing slot clear + events ...
            self.inventory.add_item(item)

    # All items (equipped + carried)
    def get_all_items(self) -> List[BaseItem]:
        items = list(self.inventory.items.values())
        for slot in all_equipment_slots:
            item = self._get_item_at_slot(slot)
            if item:
                items.append(item)
        return items
```

### Why Option C Is Best

1. **Unified item management**: One block manages ALL items (carried + equipped). Entity asks Equipment for everything item-related.

2. **Equipping is an internal transfer**: Moving from `inventory` to a typed slot is a transfer within Equipment, not a separate system. Unequipping moves back to inventory. Clean and natural.

3. **`get_all_items()` returns everything**: For looting, death transition, serialization — one call gets all items on this entity.

4. **Inventory sub-block handles Use action aggregation** (Section 15): `equipment.inventory.get_all_use_actions()` is called by `get_available_actions()`. The path is `Entity → Equipment → Inventory → items → get_use_actions()`.

5. **Death → body transition is trivial**: Transfer the entire Equipment block to the body object. All items (carried + equipped), all item conditions, everything moves at once. See Section 10.

### Inventory Remains Independent

**Critical**: Inventory is independently useful. A chest has an Inventory but no Equipment. A bag of holding is an item with an Inventory. The relationship is composition, not inheritance:

- **Equipment** contains an Inventory (for entities that carry items)
- **Inventory** works standalone (for containers, bags, loot bodies)
- Equipment knows about Inventory. Inventory does NOT know about Equipment.

```
Equipment (entity item management)
    ├── typed slots (helmet, weapon_melee_main, ...)
    ├── combat modifiers (ac_bonus, attack_bonus, ...)
    └── inventory: Inventory (general storage)
            └── items: Dict[UUID, BaseItem]

Chest (environment object)
    └── inventory: Inventory (standalone, no Equipment needed)
            └── items: Dict[UUID, BaseItem]
```

### The Dead Entity → Body Transition

This design enables a clean death-to-loot flow:

```
Entity dies:
1. Entity._remove_condition_tree() for all entity conditions
   → Cleans up entity-dependent conditions (concentration, class features)
   → Item conditions that were entity-dependent get cleaned up
   → Item conditions that are intrinsic (permanent enchantments) PERSIST

2. Create LootBody at death position:
   body = LootBody(equipment=entity.equipment)  # Transfer entire Equipment block

3. LootBody placed on GridMap, has "Loot" Use action

4. Another entity loots → items transfer to their Equipment.inventory
```

**The Equipment block IS the loot** — it moves from the dead entity to the body. No copying, no iteration. Item conditions that survive entity cleanup persist naturally.

### Equipment.py File Splitting — Deferred

The question of whether to split `equipment.py` into separate files (combat stats vs. slot management) should be **re-evaluated after Phase 3** when the Inventory sub-block and BaseItem migration make the natural boundaries concrete. The current tight coupling between modifiers and slots (e.g., `get_damages()` needs both slot data and modifier data) suggests the split may cause more harm than good until we see the actual code.

**Recommendation**: Do Option A first (extract item class definitions to their own modules via BaseItem migration — this is Phase 1). Then add Inventory as Equipment sub-block (Phase 3). Then evaluate whether further splitting makes sense based on the resulting file size and coupling.

### Code References

| Reference | What |
|-----------|------|
| `equipment.py:98-283` | Item class definitions (migration to BaseItem targets) |
| `equipment.py:387-506` | Equipment modifier fields (16+ ModifiableValues) |
| `equipment.py:508-661` | Combat computation methods |
| `equipment.py:663-942` | Slot management + equip/unequip + create() |

---

## Appendix: Key Terminology

| Term | Definition |
|------|-----------|
| **BaseItem** | The fundamental "thing that exists as an object". Handles pickup, Use actions, spatial properties. Has `allow_events_conditions=True` (Section 13) |
| **Equip Hook** | `_on_equip` / `_on_unequip` — code that runs when item enters/leaves equipment slot |
| **Use Action** | An action provided by an item, executed through the full action lifecycle |
| **Equip-Granted Action** | An action registered on entity by an equip hook's condition — available while equipped |
| **Consumable** | An item destroyed after its Use action completes |
| **WorldObject** | An environment object with spatial presence and interaction actions (Option A) or a non-pickable BaseItem (Option D) |
| **Interaction Action** | A Use action on an environment object, discovered by proximity |
| **Loot Body** | A world object that receives the dead entity's Equipment block wholesale (Section 10/16) |
| **Item Condition** | A condition applied to an item (not an entity). E.g., weapon enchantment, poison on blade (Section 13) |
| **Targetable Object** | An object with `is_targetable=True` that can be attacked. Has `object_ac` and `health` (Section 14) |
| **Inventory Action** | A Use action discovered from Inventory at query time, not registered on Entity (Section 15) |
| **Equipment Transfer** | Moving an entire Equipment block from dead entity to loot body — all items and conditions intact (Section 16) |
