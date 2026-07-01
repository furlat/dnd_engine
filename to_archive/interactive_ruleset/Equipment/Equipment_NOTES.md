# Equipment - Implementation Notes

## Status: EXCELLENT FOUNDATION

Our equipment system is already **more advanced than base D&D** - it's ARPG-style with multiple armor slots. Solid weapon system. Missing consumables/inventory.

---

## Equipment Slots Comparison

### Our System (11 slots - ARPG style!)
| Slot | Type | Field |
|------|------|-------|
| Head | Helmet | `helmet` |
| Body | BodyArmor | `body_armor` |
| Hands | Gauntlets | `gauntlets` |
| Legs | Greaves | `greaves` |
| Feet | Boots | `boots` |
| Neck | Amulet | `amulet` |
| Ring 1 | Ring | `ring_left` |
| Ring 2 | Ring | `ring_right` |
| Back | Cloak | `cloak` |
| Main Hand | Weapon | `weapon_main_hand` |
| Off Hand | Weapon/Shield | `weapon_off_hand` |

### SRD D&D (3 slots)
- Armor (one piece)
- Shield (optional)
- Weapons (main + off-hand)

**Our system is already superior for loot variety!**

---

## Armor System

### What We Have

**ArmorType Enum:**
```python
LIGHT = "Light"    # Full DEX to AC
MEDIUM = "Medium"  # DEX capped at +2
HEAVY = "Heavy"    # No DEX to AC
CLOTH = "Cloth"    # Unarmored
```

**Armor Class (BaseBlock with):**
- `ac`: ModifiableValue - base AC from armor
- `max_dex_bonus`: ModifiableValue - DEX cap (default 5, set to 2 for medium)
- `strength_requirement`: Optional[int] - STR needed (heavy armor)
- `stealth_disadvantage`: Optional[bool] - disadvantage on Stealth
- All 6 ability requirements for magic item prereqs

**Specialized Armor Classes:**
- `Helmet`, `BodyArmor`, `Gauntlets`, `Greaves`, `Boots`
- `Amulet`, `Ring`, `Cloak`

**Shield:**
- `ac_bonus`: ModifiableValue (typically +2)

### SRD Armor Table Implementation Status

| Armor | Base AC | DEX | STR Req | Stealth | Status |
|-------|---------|-----|---------|---------|--------|
| **Light** |
| Padded | 11 | Full | - | Disadv | Can create |
| Leather | 11 | Full | - | - | Can create |
| Studded Leather | 12 | Full | - | - | Can create |
| **Medium** |
| Hide | 12 | Max +2 | - | - | Can create |
| Chain Shirt | 13 | Max +2 | - | - | Can create |
| Scale Mail | 14 | Max +2 | - | Disadv | Can create |
| Breastplate | 14 | Max +2 | - | - | Can create |
| Half Plate | 15 | Max +2 | - | Disadv | Can create |
| **Heavy** |
| Ring Mail | 14 | None | - | Disadv | Can create |
| Chain Mail | 16 | None | 13 | Disadv | Can create |
| Splint | 17 | None | 15 | Disadv | Can create |
| Plate | 18 | None | 15 | Disadv | Can create |

**All armor types can be represented with current system!**

### Unarmored Defense

```python
class UnarmoredAc(str, Enum):
    BARBARIAN = "Barbarian"        # 10 + DEX + CON
    MONK = "Monk"                  # 10 + DEX + WIS
    DRACONIC_SORCERER = "Draconic Sorcerer"  # 13 + DEX
    MAGIC_ARMOR = "Magic Armor"    # 13 + DEX (Mage Armor spell)
    NONE = "None"                  # 10 + DEX (default)
```

### What's Missing in Armor

| Feature | SRD Rule | Difficulty |
|---------|----------|------------|
| **Speed penalty** | Heavy armor without STR req = -10 speed | Easy - check in movement |
| **Stealth disadvantage application** | Flag exists but not auto-applied | Easy - check in Stealth rolls |
| **Proficiency check** | Non-proficient = disadvantage on attacks, saves, checks | Medium - need proficiency tracking |
| **Don/Doff time** | Light=1min, Medium=5min, Heavy=10min | Low priority |

---

## Weapon System

### What We Have

**Weapon Class (BaseBlock with):**
```python
damage_dice: Literal[4,6,8,10,12,20]  # d4, d6, d8, d10, d12, d20
dice_numbers: int                      # 1 for 1d8, 2 for 2d6
damage_bonus: ModifiableValue          # Flat damage bonus
attack_bonus: ModifiableValue          # Attack roll bonus
damage_type: DamageType                # All 13 types supported
properties: List[WeaponProperty]       # Special properties
range: Range                           # Reach or ranged
# Extra damage support (flaming, etc.)
extra_damage_dices: List[...]
extra_damage_type: List[DamageType]
```

**WeaponProperty Enum:**
```python
FINESSE = "Finesse"       # Use DEX or STR
VERSATILE = "Versatile"   # One or two hands
RANGED = "Ranged"         # Ranged weapon
THROWN = "Thrown"         # Can be thrown
TWO_HANDED = "Two-Handed" # Requires two hands
LIGHT = "Light"           # Good for dual-wield
HEAVY = "Heavy"           # Small creatures disadvantage
MARTIAL = "Martial"       # Requires martial proficiency
SIMPLE = "Simple"         # Anyone can use
```

### SRD Weapon Properties - Implementation Status

| Property | SRD Effect | Our Status |
|----------|------------|------------|
| **Ammunition** | Need ammo to fire, draw is free, recover half | NOT IMPLEMENTED - no ammo tracking |
| **Finesse** | Use STR or DEX | IMPLEMENTED in `Weapon.get_main_damage()` |
| **Heavy** | Small creatures have disadvantage | NOT ENFORCED - no size check |
| **Light** | Good for two-weapon fighting | TRACKED but TWF not implemented |
| **Loading** | Only one attack per action | NOT IMPLEMENTED |
| **Range** | Normal/long range, disadvantage beyond normal | PARTIAL - no long range disadvantage |
| **Reach** | +5 ft reach | IMPLEMENTED via Range type |
| **Special** | See weapon description | NOT IMPLEMENTED (lance, net) |
| **Thrown** | Can throw for ranged attack | TRACKED but throw action not separate |
| **Two-Handed** | Requires two hands | TRACKED but not enforced |
| **Versatile** | Different damage two-handed | NOT IMPLEMENTED - no two-hand mode |

### SRD Weapons - Can We Create Them?

| Weapon | Damage | Properties | Createable? |
|--------|--------|------------|-------------|
| Dagger | 1d4 piercing | Finesse, light, thrown 20/60 | YES |
| Shortsword | 1d6 piercing | Finesse, light | YES |
| Longsword | 1d8 slashing | Versatile (1d10) | PARTIAL (no versatile) |
| Greatsword | 2d6 slashing | Heavy, two-handed | YES |
| Rapier | 1d8 piercing | Finesse | YES |
| Longbow | 1d8 piercing | Ammo 150/600, heavy, two-handed | PARTIAL (no ammo) |
| Crossbow, Heavy | 1d10 piercing | Ammo 100/400, heavy, loading, two-handed | PARTIAL |

### Global Equipment Bonuses

The Equipment block tracks global bonuses that apply to all attacks:

| Bonus | Purpose |
|-------|---------|
| `attack_bonus` | All attack rolls |
| `damage_bonus` | All damage rolls |
| `melee_attack_bonus` | Melee attack rolls |
| `melee_damage_bonus` | Melee damage |
| `ranged_attack_bonus` | Ranged attack rolls |
| `ranged_damage_bonus` | Ranged damage |
| `unarmed_attack_bonus` | Unarmed attack rolls |
| `unarmed_damage_bonus` | Unarmed damage |
| `ac_bonus` | All AC |

**This is great for magic items that give "+1 to all attacks"!**

### Damage Calculation Flow

```python
# In Weapon.get_main_damage():
1. Start with weapon damage_bonus
2. Add equipment.damage_bonus (global)
3. If RANGED: add DEX mod + equipment.ranged_damage_bonus
4. If FINESSE: add max(DEX, STR) + equipment.melee_damage_bonus
5. Else: add STR mod + equipment.melee_damage_bonus
6. Return Damage object with combined bonus
```

---

## Equipment Events

Full event support for equip/unequip:

| Event | Trigger |
|-------|---------|
| `WeaponEquipEvent` | Weapon equipped |
| `WeaponUnequipEvent` | Weapon unequipped |
| `ArmorEquipEvent` | Armor piece equipped |
| `ArmorUnequipEvent` | Armor piece unequipped |
| `ShieldEquipEvent` | Shield equipped |
| `ShieldUnequipEvent` | Shield unequipped |

**Events fire through the full lifecycle (DECLARATION → EXECUTION → EFFECT → COMPLETION)**

This enables:
- Cursed items that can't be unequipped
- Set bonuses that trigger on equip
- Reactions to equipment changes

---

## NOT IMPLEMENTED

### Inventory System
Currently items are either equipped or don't exist. Need:
- `Inventory` class with capacity
- Item stacking
- Item categories (consumable, equipment, quest, etc.)
- Weight/encumbrance (optional)

### Consumables (from Gear.md)

| Item | Effect | Implementation |
|------|--------|----------------|
| Potion of Healing | 2d4+2 HP | Need consumable item type |
| Antitoxin | Advantage vs poison for 1 hour | Need timed buff system |
| Acid | 2d6 acid damage (thrown) | Need throwable item action |
| Alchemist's Fire | 1d4 fire/turn until DC 10 DEX | Need DoT condition |
| Holy Water | 2d6 radiant to fiend/undead | Need creature type tags |
| Basic Poison | DC 10 CON or 1d4 poison | Need weapon coating system |

### Ammunition
Need:
- Ammo as inventory item with count
- Auto-consume on ranged attack
- Recovery mechanic (half after combat)

### Weapon Proficiency
Need:
- Simple/Martial weapon proficiency flags
- Class-based proficiency
- Non-proficient penalty (no proficiency bonus)

### Two-Weapon Fighting
Need:
- Check both weapons are Light
- Bonus action attack
- No ability mod to off-hand damage (unless Fighting Style)

### Versatile Weapons
Need:
- Track one-hand vs two-hand mode
- Different damage dice per mode
- Can't use shield while two-handing

---

## ARPG Enhancement Ideas

Since you want more ARPG-style loot:

### Item Rarity System
```python
class ItemRarity(str, Enum):
    COMMON = "Common"       # White - basic gear
    UNCOMMON = "Uncommon"   # Green - minor magic
    RARE = "Rare"           # Blue - significant magic
    EPIC = "Epic"           # Purple - powerful
    LEGENDARY = "Legendary" # Orange - unique effects
```

### Magic Item Affixes

**Prefixes (offense):**
- Keen (+1 crit range)
- Vicious (+1d6 damage)
- Flaming (+1d6 fire)
- Vampiric (heal on hit)

**Suffixes (defense):**
- of Protection (+1 AC)
- of Resistance (resistance to damage type)
- of Health (+max HP)
- of Speed (+movement)

### Set Bonuses
```python
class ItemSet:
    name: str
    pieces: List[str]  # Item names in set
    bonuses: Dict[int, List[Modifier]]  # pieces_equipped -> bonuses

# Example: "Warrior's Regalia"
# 2 pieces: +2 STR
# 4 pieces: +10% damage
# 6 pieces: Cleave on kill
```

### Item Sockets
```python
class Socket:
    type: Literal["red", "blue", "green", "prismatic"]
    gem: Optional[Gem]

class Gem:
    type: str
    bonus: Modifier  # +5 fire damage, +10 HP, etc.
```

### Unique Items
Items with special effects that break normal rules:
- "Boots of Blinding Speed" - +50% movement, -20% hit chance
- "Staff of the Magi" - Store spells, release as AoE
- "Vorpal Sword" - Natural 20 decapitates

---

## Implementation Priority

### Phase 1: Core Fixes
1. Enforce stealth_disadvantage on Stealth checks
2. Enforce strength_requirement speed penalty
3. Add long range disadvantage to ranged attacks
4. Add ranged-in-melee disadvantage

### Phase 2: Combat Features
1. Two-weapon fighting (bonus action attack)
2. Versatile weapon mode switching
3. Heavy weapon disadvantage for Small creatures

### Phase 3: Inventory
1. Basic Inventory class
2. Consumable items (potions)
3. Ammunition tracking

### Phase 4: ARPG Features
1. Item rarity system
2. Magic item prefixes/suffixes
3. Set bonuses
4. Sockets and gems

---

## Code Locations

| Feature | File | Line |
|---------|------|------|
| Equipment block | `equipment.py` | 366 |
| Armor class | `equipment.py` | 98 |
| Weapon class | `equipment.py` | 224 |
| Shield class | `equipment.py` | 212 |
| WeaponProperty enum | `equipment.py` | 76 |
| ArmorType enum | `equipment.py` | 70 |
| BodyPart slots | `equipment.py` | 87 |
| equip() method | `equipment.py` | 580 |
| unequip() method | `equipment.py` | 706 |
| AC calculation | `equipment.py` | 554-578 |
| Damage calculation | `equipment.py` | 285-324 |
