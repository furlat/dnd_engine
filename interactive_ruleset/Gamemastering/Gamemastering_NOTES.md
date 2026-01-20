# Gamemastering - Implementation Notes

## Status: CONDITIONS SOLID, REST NOT IMPLEMENTED

We have excellent condition coverage. Diseases, poisons, objects, and traps are future systems.

---

## Conditions

### SRD vs Our Implementation

| Condition | SRD Effects | Our Implementation | Status |
|-----------|-------------|-------------------|--------|
| **Blinded** | Can't see, auto-fail sight checks, disadvantage attacks, attackers have advantage | `Blinded` class - all effects implemented | COMPLETE |
| **Charmed** | Can't attack charmer, charmer has advantage on social checks | `Charmed` class - auto-miss vs charmer, social advantage | COMPLETE |
| **Deafened** | Can't hear, auto-fail hearing checks | `Deafened` class - auto-fail hearing skills | COMPLETE |
| **Exhaustion** | 6 levels with cumulative effects (see below) | **NOT IMPLEMENTED** | MISSING |
| **Frightened** | Disadvantage when source visible, can't approach source | `Frightened` class - contextual disadvantage, speed=0 toward source | COMPLETE |
| **Grappled** | Speed = 0, no speed bonuses | `Grappled` class - speed max constraint | COMPLETE |
| **Incapacitated** | Can't take actions or reactions | `Incapacitated` class - all action economy = 0 | COMPLETE |
| **Invisible** | Can't be seen (heavily obscured), advantage on attacks, attackers have disadvantage | `Invisible` class - contextual advantages | COMPLETE |
| **Paralyzed** | Incapacitated, can't move/speak, auto-fail STR/DEX saves, attackers have advantage, auto-crit within 5ft | `Paralyzed` class - includes Incapacitated as sub-condition | COMPLETE |
| **Petrified** | Incapacitated, can't move/speak, auto-fail STR/DEX saves, resistance to all damage, immune to poison/disease | **NOT IMPLEMENTED** | MISSING |
| **Poisoned** | Disadvantage on attacks and ability checks | `Poisoned` class - disadvantage on all attacks/checks | COMPLETE |
| **Prone** | Crawl only, disadvantage attacks, melee advantage / ranged disadvantage against | `Prone` class - contextual attack modifiers | COMPLETE |
| **Restrained** | Speed = 0, disadvantage attacks, attackers advantage, disadvantage DEX saves | `Restrained` class - all effects | COMPLETE |
| **Stunned** | Incapacitated, can't move, auto-fail STR/DEX saves, attackers advantage | `Stunned` class - includes Incapacitated | COMPLETE |
| **Unconscious** | Incapacitated, can't move/speak, unaware, drops items, falls prone, auto-fail STR/DEX, attackers advantage, auto-crit within 5ft | `Unconscious` class - includes Incapacitated | COMPLETE |

### Additional Conditions We Have (Not in SRD Core)
| Condition | Effect | Notes |
|-----------|--------|-------|
| **Dashing** | +movement = base speed | Dash action effect |
| **Dodging** | Attackers have disadvantage, advantage on DEX saves | Dodge action effect |

### Exhaustion System (NOT IMPLEMENTED)

This is a significant system for survival/hardcore gameplay:

| Level | Effect | Cumulative |
|-------|--------|------------|
| 1 | Disadvantage on ability checks | |
| 2 | Speed halved | + Level 1 |
| 3 | Disadvantage on attacks and saves | + Levels 1-2 |
| 4 | HP maximum halved | + Levels 1-3 |
| 5 | Speed reduced to 0 | + Levels 1-4 |
| 6 | **Death** | |

**Key mechanics:**
- Effects are cumulative (level 3 = all of levels 1-3)
- Long rest reduces by 1 level (with food/drink)
- Some spells/effects grant exhaustion
- Forced march, starvation, dehydration cause exhaustion

**Implementation approach:**
```python
class Exhaustion(BaseCondition):
    level: int = Field(default=1, ge=1, le=6)

    def _apply(self, event):
        # Apply modifiers based on level
        if self.level >= 1:
            # Disadvantage on ability checks
        if self.level >= 2:
            # Speed halved (multiply by 0.5)
        if self.level >= 3:
            # Disadvantage on attacks and saves
        if self.level >= 4:
            # Max HP halved
        if self.level >= 5:
            # Speed = 0
        if self.level >= 6:
            # Death (reduce HP to 0, apply death)
```

### Petrified Condition (NOT IMPLEMENTED)

Unique condition with special properties:
- Incapacitated (can't act)
- Can't move or speak
- Unaware of surroundings
- Auto-fail STR/DEX saves
- Attackers have advantage
- **Resistance to ALL damage** (unique!)
- **Immune to poison and disease**
- Weight × 10
- Ceases aging

**Why it's special**: It's the only condition that grants damage resistance. Would need special handling in damage calculation.

---

## Diseases (NOT IMPLEMENTED)

Diseases are long-term afflictions with:
- Infection vector (bite, contact, ingestion)
- Incubation period (hours to days)
- Symptoms (conditions, exhaustion, penalties)
- Progression (saves at long rest)
- Cure (magic or special items)

### Sample Diseases

| Disease | Vector | Effect | Cure |
|---------|--------|--------|------|
| **Cackle Fever** | Humanoid contact | 1 exhaustion, stress = psychic damage + incapacitated laughing | DC 13 CON saves reduce DC until 0 |
| **Sewer Plague** | Bite/filth contact | 1 exhaustion, half healing, no long rest HP | DC 11 CON saves at long rest |
| **Sight Rot** | Tainted water | -1 to -5 attack/sight checks, then Blinded | Eyebright flower ointment |

### Implementation Approach

```python
class Disease(BaseCondition):
    name: str
    incubation_hours: int
    infected_at: datetime
    current_penalty: int = 0

    def on_long_rest(self) -> bool:
        """Called at end of long rest. Returns True if cured."""
        # Make saving throw
        # Adjust severity
        # Return cure status

class SightRot(Disease):
    def _apply(self, event):
        # Apply attack/check penalty based on current_penalty
        if self.current_penalty >= 5:
            # Apply Blinded condition
```

**Diseases require:**
- Time tracking (incubation, progression)
- Long rest hooks
- Stacking penalties
- Cure tracking

---

## Poisons (NOT IMPLEMENTED)

Four delivery types with different mechanics:

| Type | Delivery | Trigger |
|------|----------|---------|
| **Contact** | Smeared on object | Touch with exposed skin |
| **Ingested** | In food/drink | Swallow entire dose |
| **Inhaled** | Powder/gas | 5ft cube, can't hold breath |
| **Injury** | Weapon coating | Piercing/slashing damage |

### Sample Poisons

| Poison | Type | DC | Effect |
|--------|------|-----|--------|
| Basic Poison | Injury | 10 | 1d4 poison damage |
| Drow Poison | Injury | 13 | Poisoned 1hr, fail by 5+ = unconscious |
| Purple Worm | Injury | 19 | 12d6 poison damage |
| Crawler Mucus | Contact | 13 | Poisoned + Paralyzed 1 min |
| Assassin's Blood | Ingested | 10 | 1d12 + Poisoned 24hr |
| Burnt Othur Fumes | Inhaled | 13 | 3d6, then 1d6/turn until 3 saves |
| Truth Serum | Ingested | 11 | Can't lie for 1 hour |
| Midnight Tears | Ingested | 17 | No effect until midnight, then 9d6 |

### Implementation Approach

```python
class PoisonType(str, Enum):
    CONTACT = "Contact"
    INGESTED = "Ingested"
    INHALED = "Inhaled"
    INJURY = "Injury"

class Poison(BaseModel):
    name: str
    poison_type: PoisonType
    dc: int
    damage_dice: Optional[int]
    damage_count: Optional[int]
    condition: Optional[str]  # "Poisoned", "Paralyzed", etc.
    duration_minutes: Optional[int]

class PoisonedWeapon:
    """Tracks poison on a weapon."""
    weapon_uuid: UUID
    poison: Poison
    applied_at: datetime
    uses_remaining: int = 1  # Injury poison: one use

def apply_poison_on_hit(target: Entity, poison: Poison):
    # CON save vs DC
    # Apply damage
    # Apply condition if failed
```

**Poisons require:**
- Weapon coating system
- Consumable application action
- Duration/expiration tracking
- Condition application

---

## Objects (NOT IMPLEMENTED)

Objects can be attacked and destroyed:

### Object AC by Material
| Material | AC |
|----------|-----|
| Cloth, paper, rope | 11 |
| Crystal, glass, ice | 13 |
| Wood, bone | 15 |
| Stone | 17 |
| Iron, steel | 19 |
| Mithral | 21 |
| Adamantine | 23 |

### Object HP by Size
| Size | Fragile | Resilient |
|------|---------|-----------|
| Tiny | 2 (1d4) | 5 (2d4) |
| Small | 3 (1d6) | 10 (3d6) |
| Medium | 4 (1d8) | 18 (4d8) |
| Large | 5 (1d10) | 27 (5d10) |

### Object Properties
- **Immune to poison and psychic damage**
- Vulnerable/resistant to logical damage types (fire vs paper)
- **Damage Threshold**: Must deal X damage in one hit to affect (castle walls)

### Implementation Approach

```python
class DestructibleObject(BaseBlock):
    """An object that can be attacked."""
    name: str
    material: Material  # Determines AC
    size: Size
    fragile: bool = False
    hp: ModifiableValue
    damage_threshold: int = 0

    # Immunities
    immunities: List[DamageType] = [DamageType.POISON, DamageType.PSYCHIC]

    def take_damage(self, damage: int, damage_type: DamageType) -> int:
        if damage_type in self.immunities:
            return 0
        if damage < self.damage_threshold:
            return 0  # Superficial
        # Apply damage
        return actual_damage
```

**Objects require:**
- New entity type or BaseBlock subclass
- Material enum
- Damage threshold mechanic
- Immunity handling

---

## Traps (NOT IMPLEMENTED)

Two types of traps:

### Mechanical Traps
- Pressure plates, trip wires, mechanisms
- Detect: Perception check
- Disable: Thieves' tools + DEX check
- Examples: Pits, darts, falling blocks, nets

### Magic Traps
- Spell effects or magical devices
- Detect: Perception OR Arcana check
- Disable: Dispel magic or Arcana check
- Examples: Glyph of warding, fire statue

### Trap Scaling

| Danger Level | Save DC | Attack Bonus |
|--------------|---------|--------------|
| Setback | 10-11 | +3 to +5 |
| Dangerous | 12-15 | +6 to +8 |
| Deadly | 16-20 | +9 to +12 |

| Character Level | Setback | Dangerous | Deadly |
|-----------------|---------|-----------|--------|
| 1st-4th | 1d10 | 2d10 | 4d10 |
| 5th-10th | 2d10 | 4d10 | 10d10 |
| 11th-16th | 4d10 | 10d10 | 18d10 |
| 17th-20th | 10d10 | 18d10 | 24d10 |

### Complex Traps
- Act like creatures in combat
- Roll initiative
- Take actions on their turn
- Example: Flooding room (water rises each turn)

### Implementation Approach

```python
class Trap(BaseModel):
    """A trap on the map."""
    name: str
    position: Tuple[int, int]
    trap_type: Literal["mechanical", "magical"]

    # Detection
    perception_dc: int
    investigation_dc: Optional[int]

    # Disabling
    disable_dc: int
    disable_skill: str = "thieves_tools"

    # Trigger
    trigger_type: str  # "pressure_plate", "trip_wire", "proximity"
    trigger_weight: int = 20  # pounds to trigger

    # Effect
    save_type: str  # "dexterity", "constitution"
    save_dc: int
    damage_dice: int
    damage_count: int
    damage_type: DamageType
    condition: Optional[str]

    triggered: bool = False

    def check_trigger(self, entity: Entity) -> bool:
        """Check if entity triggers this trap."""
        # Check position, weight, etc.

    def activate(self, target: Entity) -> TrapEvent:
        """Trigger the trap against target."""
        # Roll attack or force save
        # Deal damage
        # Apply conditions
```

**Traps require:**
- Tile or position-based placement
- Detection checks (passive or active)
- Trigger conditions
- Damage/effect application
- Complex trap initiative (optional)

---

## Madness (NOT IMPLEMENTED)

Madness comes in three severities:
- **Short-term**: 1d10 minutes
- **Long-term**: 1d10 × 10 hours
- **Indefinite**: Until cured

Examples:
- Short: Stunned, frightened, incapacitated with screaming
- Long: Compulsion to repeat action, hallucinations, paranoia
- Indefinite: Compulsion to eat strange things, powerful delusions

**Lower priority** - more RP than mechanical.

---

## Implementation Priority

### High Priority
1. **Exhaustion** - Core survival mechanic, affects balance
2. **Petrified** - Complete condition coverage

### Medium Priority
3. **Objects** - Destructible environment
4. **Poisons (Injury type)** - Weapon coating is common
5. **Basic Traps** - Pit, darts, pressure plate

### Low Priority
6. **Diseases** - Long-term campaign mechanic
7. **Complex Traps** - Combat-like traps
8. **Poisons (other types)** - Contact, ingested, inhaled
9. **Madness** - RP-focused

---

## Code Locations

| Feature | File | Notes |
|---------|------|-------|
| All conditions | `conditions.py` | 15 conditions implemented |
| BaseCondition | `core/base_conditions.py` | Base class with _apply pattern |
| Condition modifiers | `core/modifiers.py` | Advantage, AutoHit, Critical modifiers |
| Sub-conditions | `conditions.py:Paralyzed` | Example of parent-child conditions |
