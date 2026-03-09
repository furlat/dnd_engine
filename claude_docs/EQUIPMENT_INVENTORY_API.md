# Equipment & Inventory API Reference

REST API for reading equipment/inventory state and performing equip/unequip operations.

## Data Models

### APIItemSummary

Lightweight item metadata returned in all equipment/inventory responses.

```typescript
interface APIItemSummary {
  uuid: string;
  name: string;
  description: string | null;
  item_type: "weapon" | "armor" | "shield" | "usable" | "item";
  rarity: "common" | "uncommon" | "rare" | "very_rare" | "legendary";
  weight: number;
  is_equipped: boolean;
  equipped_slot: string | null;

  // Weapon-specific (only set when item_type === "weapon")
  damage_dice: string | null;        // e.g. "1d8", "2d6"
  damage_type: string | null;        // e.g. "Slashing", "Piercing", "Bludgeoning"
  weapon_properties: string[];       // e.g. ["Finesse", "Light", "Thrown"]

  // Armor-specific (only set when item_type === "armor")
  armor_type: string | null;         // "Light", "Medium", "Heavy", "Cloth"
  armor_ac: number | null;           // Base AC value (e.g. 16 for Chain Mail)

  // Shield-specific (only set when item_type === "shield")
  shield_ac_bonus: number | null;    // AC bonus (typically 2)

  // Usable-specific (only set when item_type === "usable")
  charges: number | null;            // -1 = unlimited, 0 = depleted
  max_charges: number | null;
  stack_count: number | null;
  is_consumable: boolean;            // true for potions, scrolls, etc.
}
```

### APIEquipmentSlot

Single equipment slot with its current item (or null if empty).

```typescript
interface APIEquipmentSlot {
  slot: string;                      // Slot identifier (see Slot Names below)
  slot_type: "weapon" | "armor" | "shield" | "ring";
  item: APIItemSummary | null;       // null = empty slot
}
```

### APIEquipmentOverview

Full equipment + inventory state for an entity.

```typescript
interface APIEquipmentOverview {
  slots: APIEquipmentSlot[];         // Always 13 slots (see Slot Names)
  ac: number;                        // Current total AC
  inventory: APIItemSummary[];       // All items in inventory (unequipped)
}
```

### Slot Names (13 total)

| Slot Name | Slot Type | Notes |
|-----------|-----------|-------|
| `weapon_melee_main` | weapon | Primary melee weapon |
| `weapon_melee_off` | weapon/shield | Off-hand: light weapon OR shield |
| `weapon_ranged_main` | weapon | Primary ranged weapon |
| `weapon_ranged_off` | weapon | Off-hand ranged (light only) |
| `helmet` | armor | Head slot |
| `body_armor` | armor | Body slot (main AC source) |
| `gauntlets` | armor | Hands slot |
| `greaves` | armor | Legs slot |
| `boots` | armor | Feet slot |
| `amulet` | armor | Amulet slot |
| `cloak` | armor | Cloak slot |
| `ring_left` | ring | Left ring |
| `ring_right` | ring | Right ring |

---

## Endpoints

### GET `/entity/{uuid}/equipment`

Returns full equipment and inventory state.

**Response:** `APIEquipmentOverview`

```json
{
  "slots": [
    {
      "slot": "weapon_melee_main",
      "slot_type": "weapon",
      "item": {
        "uuid": "abc-123",
        "name": "Longsword",
        "item_type": "weapon",
        "damage_dice": "1d8",
        "damage_type": "Slashing",
        "weapon_properties": ["Versatile"],
        "rarity": "common",
        "weight": 3.0,
        "is_equipped": true,
        "equipped_slot": "MELEE_MAIN"
      }
    },
    {
      "slot": "weapon_melee_off",
      "slot_type": "shield",
      "item": {
        "uuid": "def-456",
        "name": "Shield",
        "item_type": "shield",
        "shield_ac_bonus": 2,
        "rarity": "common",
        "weight": 6.0,
        "is_equipped": true,
        "equipped_slot": "MELEE_OFF"
      }
    },
    { "slot": "helmet", "slot_type": "armor", "item": null },
    ...
  ],
  "ac": 18,
  "inventory": [
    {
      "uuid": "ghi-789",
      "name": "Potion of Healing",
      "item_type": "usable",
      "charges": 1,
      "max_charges": 1,
      "stack_count": 1,
      "is_consumable": true,
      "rarity": "common",
      "weight": 0.0,
      "is_equipped": false
    },
    {
      "uuid": "jkl-012",
      "name": "Dagger",
      "item_type": "weapon",
      "damage_dice": "1d4",
      "damage_type": "Piercing",
      "weapon_properties": ["Finesse", "Light", "Thrown"],
      "rarity": "common",
      "weight": 1.0,
      "is_equipped": false
    }
  ]
}
```

---

### GET `/entity/{uuid}/equipment/item/{item_uuid}`

Returns detail for a single item (equipped or in inventory).

**Response:** `APIItemSummary` (as JSON object)

---

### GET `/entity/{uuid}/equippable-items`

Returns inventory items that can be equipped, grouped by valid target slot. Includes swap info (what's currently in each slot).

**Response:**

```json
{
  "entity_uuid": "abc-123",
  "equippable": {
    "weapon_melee_main": [
      {
        "item_uuid": "item-1",
        "item_name": "Dagger",
        "swap_item_name": "Longsword",
        "swap_item_uuid": "item-2"
      },
      {
        "item_uuid": "item-3",
        "item_name": "Handaxe",
        "swap_item_name": "Longsword",
        "swap_item_uuid": "item-2"
      }
    ],
    "weapon_melee_off": [
      {
        "item_uuid": "item-1",
        "item_name": "Dagger",
        "swap_item_name": "Shield",
        "swap_item_uuid": "item-4"
      }
    ],
    "body_armor": [
      {
        "item_uuid": "item-5",
        "item_name": "Leather Armor",
        "swap_item_name": "Chain Mail",
        "swap_item_uuid": "item-6"
      }
    ]
  }
}
```

**Slot rules:**
- Weapons only appear in compatible slots (ranged weapons in ranged slots, melee in melee)
- Only `Light` weapons can go in off-hand slots (`weapon_melee_off`, `weapon_ranged_off`)
- Shields always go in `weapon_melee_off`
- Armor slots are determined by the armor's body part
- `swap_item_name`/`swap_item_uuid` are null if slot is empty

---

### POST `/entity/{uuid}/equip`

Equip an item from inventory to a slot. If the target slot is occupied, the old item is automatically moved to inventory (swap).

**Request:**

```json
{
  "session_id": "session-uuid",
  "entity_uuid": "entity-uuid",
  "item_uuid": "item-uuid-to-equip",
  "slot": "weapon_melee_main"        // optional: auto-assign if omitted
}
```

- `slot` is optional. If omitted, the system auto-assigns based on item type (melee weapons go to `weapon_melee_main`, ranged to `weapon_ranged_main`, armor uses its body_part, shields go to `weapon_melee_off`).
- Requires active session with ownership of the entity and it being their turn.

**Response:**

```json
{
  "success": true,
  "message": "Equipped Longsword",
  "equipment": { /* full APIEquipmentOverview */ }
}
```

**Errors:**
- `400` — Item not equippable, invalid slot, slot type mismatch (e.g. melee weapon in ranged slot, non-light weapon in off-hand)
- `404` — Item not found in inventory

---

### POST `/entity/{uuid}/unequip`

Unequip an item from a slot to inventory.

**Request:**

```json
{
  "session_id": "session-uuid",
  "entity_uuid": "entity-uuid",
  "slot": "weapon_melee_main"         // required
}
```

**Response:**

```json
{
  "success": true,
  "message": "Unequipped Longsword",
  "equipment": { /* full APIEquipmentOverview */ }
}
```

**Errors:**
- `400` — Slot is empty, invalid slot name, or unequip was canceled by event handler

---

## APIEntityFull Includes Equipment

The existing `GET /entity/{uuid}` endpoint now includes the full equipment overview:

```json
{
  "uuid": "...",
  "name": "Hero",
  "hp": 45,
  "max_hp": 45,
  "ac": 18,
  "conditions": [],
  "equipment": {
    "slots": [...],
    "ac": 18,
    "inventory": [...]
  },
  ...
}
```

---

## Default Starter Inventories

All class factories give entities starter inventory items. Items are **duplicate-aware** — only items NOT already equipped are added to inventory, giving meaningful swap options.

### Fighter (preset: sword_shield / archery / etc.)
| Item | Type | Notes |
|------|------|-------|
| Potion of Haste | Usable | Consumable |
| Healing Potion x2 | Usable | Consumable, stackable |
| Handaxe | Weapon | Light, Thrown — off-hand option |
| Javelin | Weapon | Thrown ranged option |
| Dagger | Weapon | Light, Finesse, Thrown — off-hand option |
| Longsword | Weapon | Versatile main-hand swap |
| Leather Armor | Armor | Light armor swap (if not already wearing light) |
| Chain Mail | Armor | Heavy armor swap (if not already wearing heavy) |
| Shield | Shield | +2 AC (if not already equipped) |

*Items matching equipped gear are automatically excluded.*

### Barbarian (preset: greataxe / dual_axes / sword_shield)
| Item | Type | Notes |
|------|------|-------|
| Potion of Haste | Usable | Consumable |
| Healing Potion x2 | Usable | Consumable, stackable |
| Handaxe | Weapon | Light, Thrown — dual-wield option |
| Javelin | Weapon | Thrown ranged option |
| Dagger | Weapon | Light, Finesse, Thrown |
| Longsword | Weapon | Versatile main-hand swap |
| Shield | Shield | +2 AC (if not already equipped) |

*Items matching equipped gear are automatically excluded.*

### Sorcerer (preset: dagger / quarterstaff)
| Item | Type | Notes |
|------|------|-------|
| Potion of Haste | Usable | Consumable |
| Healing Potion x2 | Usable | Consumable, stackable |
| Dagger OR Quarterstaff | Weapon | Whichever isn't equipped |

*The arena setup (`setup_arena_combat`) adds additional items: Torch, Potion of Greater Invisibility, and spell scrolls (2x Magic Missile, 2x Fireball) for sorcerer characters.*

---

## Frontend Integration Guide

### Rendering the Equipment Panel

1. Fetch `GET /entity/{uuid}/equipment` to get `APIEquipmentOverview`
2. Render the 13 `slots` — each has `slot`, `slot_type`, and optional `item`
3. Render `inventory` list below slots
4. Display `ac` as the entity's total Armor Class

### Implementing Drag-and-Drop Equip

1. User drags inventory item onto a slot
2. Call `GET /entity/{uuid}/equippable-items` to validate which slots accept the item
3. Highlight valid drop targets
4. On drop, call `POST /entity/{uuid}/equip` with `item_uuid` and `slot`
5. Response includes updated `equipment` — re-render from that

### Implementing Unequip

1. User clicks unequip button on a slot (or drags item off)
2. Call `POST /entity/{uuid}/unequip` with `slot`
3. Response includes updated `equipment` — re-render from that

### Swap Behavior

When equipping to an occupied slot:
- The old item is automatically moved to inventory
- The response `equipment` reflects the final state (new item in slot, old item in inventory)
- No need for a separate unequip call

### Item Type Rendering Hints

| `item_type` | Icon | Key Fields to Display |
|-------------|------|----------------------|
| `weapon` | sword/bow | `damage_dice`, `damage_type`, `weapon_properties` |
| `armor` | shield/helm | `armor_type`, `armor_ac` |
| `shield` | shield | `shield_ac_bonus` |
| `usable` | potion/scroll | `charges`/`max_charges`, `stack_count`, `is_consumable` |
| `item` | generic | `description` |

### Slot Type Icons

| `slot_type` | Typical Visual |
|-------------|---------------|
| `weapon` | Sword icon (melee) or bow icon (ranged) |
| `armor` | Appropriate body part icon |
| `shield` | Shield icon |
| `ring` | Ring icon |
