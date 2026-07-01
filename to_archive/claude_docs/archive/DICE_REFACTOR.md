# Dice System Technical Reference

This document provides a comprehensive technical reference for the dice system in the D&D Engine. It covers the core architecture, flow of dice rolls, event-based interception, combat log integration, and proposed improvements for deterministic testing and semantic clarity.

---

## 1. Overview

### Purpose of This Document

This document serves as:
1. **Technical reference** for understanding how dice rolls work end-to-end
2. **Guide for implementing new dice manipulation features** (feats, class abilities)
3. **Analysis of architectural issues** needing future refactoring
4. **Design exploration** for deterministic testing approaches

### Key Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    DICE SYSTEM ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Configuration Layer:                                            │
│  ┌─────────────┐                                                │
│  │    Dice     │  count, value, bonus (ModifiableValue),        │
│  │             │  roll_type, attack_outcome, crit_extra_dice    │
│  └─────┬───────┘                                                │
│        │ .roll (computed property)                              │
│        ▼                                                         │
│  Result Layer:                                                   │
│  ┌─────────────┐                                                │
│  │  DiceRoll   │  results, total, bonus, advantage_status,      │
│  │             │  critical_status, auto_hit_status              │
│  └─────┬───────┘                                                │
│        │ Used by                                                 │
│        ▼                                                         │
│  Outcome Layer:                                                  │
│  ┌──────────────────┐                                           │
│  │ AttackOutcome    │  HIT, MISS, CRIT, CRIT_MISS               │
│  │ (via determine_  │  determine_attack_outcome()               │
│  │  attack_outcome) │  ← Used for ALL d20 rolls (semantic issue)│
│  └──────────────────┘                                           │
│                                                                  │
│  Event Layer:                                                    │
│  ┌───────────────────┐  ┌───────────────────┐                   │
│  │ DamageRolledEvent │  │ SavingThrowEvent  │                   │
│  │ (damage dice      │  │ (d20 save rolls)  │                   │
│  │  manipulation)    │  │                   │                   │
│  └───────────────────┘  └───────────────────┘                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Classes

### 2.1 Dice (Configuration)

The `Dice` class (`dnd/core/dice.py:120-341`) represents a set of dice to be rolled. It is a **configuration object** that produces an immutable `DiceRoll` when evaluated.

**Key Fields:**

```python
# dnd/core/dice.py:120-188
class Dice(BaseModel):
    uuid: UUID = Field(default_factory=uuid4)
    count: int = Field(..., ge=1)  # Number of dice
    value: Literal[4, 6, 8, 10, 12, 20] = Field(...)  # Die size
    bonus: ModifiableValue = Field(...)  # All bonuses (6-channel system)
    roll_type: RollType = Field(default=RollType.ATTACK)
    attack_outcome: Optional[AttackOutcome] = Field(default=None)  # Required for DAMAGE
    crit_extra_dice: int = Field(default=0)  # Brutal Critical, etc.
```

**Validators:**

```python
# dnd/core/dice.py:206-236
@model_validator(mode="after")
def check_attack_outcome(self) -> Self:
    # Damage rolls REQUIRE attack_outcome (needed for crit doubling)
    if self.roll_type == RollType.DAMAGE and self.attack_outcome is None:
        raise ValueError("Attack outcome must be provided for damage rolls")
    # Non-damage rolls must NOT have attack_outcome
    elif self.roll_type != RollType.DAMAGE and self.attack_outcome is not None:
        raise ValueError("Attack outcome must be None for non-damage rolls")

@model_validator(mode="after")
def check_num_dice(self) -> Self:
    # d20 rolls (ATTACK, SAVE, CHECK) must have exactly 1 die
    if self.roll_type != RollType.DAMAGE and self.count > 1:
        raise ValueError("Cannot have more than one die for non-damage rolls")
```

**The `roll` Computed Property:**

```python
# dnd/core/dice.py:308-341
@computed_field
@cached_property
def roll(self) -> DiceRoll:
    if self.roll_type == RollType.DAMAGE:
        # Roll damage dice (possibly doubled on crit)
        results = [roll[0] for roll in self._roll(crit=(self.attack_outcome == AttackOutcome.CRIT))]
        total = sum(results) + self.bonus.normalized_score
    else:
        # d20 roll with advantage/disadvantage handling
        roll_result = self._roll()[0]
        selected_value = roll_result[0]
        all_rolls = roll_result[1]
        results = all_rolls if all_rolls else [selected_value]
        total = selected_value + self.bonus.normalized_score

    return DiceRoll(
        dice_uuid=self.uuid,
        roll_type=self.roll_type,
        results=results,
        total=total,
        bonus=self.bonus.normalized_score,
        advantage_status=self.bonus.advantage,
        critical_status=self.bonus.critical,
        auto_hit_status=self.bonus.auto_hit,
        source_entity_uuid=self.source_entity_uuid,
        target_entity_uuid=self.target_entity_uuid,
        attack_outcome=self.attack_outcome
    )
```

### 2.2 DiceRoll (Immutable Result)

The `DiceRoll` class (`dnd/core/dice.py:21-118`) stores the **result** of a dice roll. It is immutable after creation and auto-registers in a global registry.

**Key Fields:**

```python
# dnd/core/dice.py:21-101
class DiceRoll(BaseModel):
    _registry: ClassVar[Dict[UUID, 'DiceRoll']] = {}  # Global lookup

    roll_uuid: UUID = Field(default_factory=uuid4)
    dice_uuid: UUID = Field(...)  # Links back to Dice that created this
    roll_type: RollType = Field(...)  # DAMAGE, ATTACK, SAVE, CHECK

    # Roll data
    results: Union[List[int], int] = Field(...)  # Individual die results
    total: int = Field(...)  # Sum + bonus
    bonus: int = Field(...)  # Numerical bonus applied

    # Status from ModifiableValue
    advantage_status: AdvantageStatus = Field(...)  # ADVANTAGE, DISADVANTAGE, NONE
    critical_status: CriticalStatus = Field(...)    # AUTOCRIT, NOCRIT, NONE
    auto_hit_status: AutoHitStatus = Field(...)     # AUTOHIT, AUTOMISS, NONE

    # Entity tracking
    source_entity_uuid: UUID = Field(...)
    target_entity_uuid: Optional[UUID] = Field(default=None)
    attack_outcome: Optional[AttackOutcome] = Field(default=None)
```

**The `results` Field:**

For d20 rolls with advantage/disadvantage, `results` contains **both dice** (e.g., `[15, 8]`). The `advantage_status` indicates which was used:
- `ADVANTAGE`: `max(results)` is used
- `DISADVANTAGE`: `min(results)` is used
- `NONE`: Single die, `results[0]`

### 2.3 AttackOutcome & RollType Enums

```python
# dnd/core/dice.py:9-19
class AttackOutcome(str, Enum):
    HIT = "Hit"
    MISS = "Miss"
    CRIT = "Crit"
    CRIT_MISS = "Crit Miss"

class RollType(str, Enum):
    DAMAGE = "Damage"
    ATTACK = "Attack"
    SAVE = "Save"
    CHECK = "Check"
```

**Note:** `AttackOutcome` is currently used for ALL d20 rolls, not just attacks. This is a semantic mismatch addressed in Section 9.

---

## 3. D20 Roll Flow

### 3.1 Entity.roll_d20()

The entry point for all d20 rolls is `Entity.roll_d20()` (`dnd/entity.py:1048-1059`):

```python
# dnd/entity.py:1048-1059
def roll_d20(self, bonus: ModifiableValue, roll_type: RollType = RollType.ATTACK) -> DiceRoll:
    """
    Roll a d20 with the given bonus.

    Args:
        bonus: ModifiableValue containing all bonuses, advantage, etc.
        roll_type: ATTACK, SAVE, or CHECK

    Returns:
        DiceRoll: The immutable result
    """
    attack_dice = Dice(count=1, value=20, bonus=bonus, roll_type=roll_type)
    return attack_dice.roll
```

### 3.2 Advantage/Disadvantage Mechanics

Advantage and disadvantage are handled in `Dice._roll()` (`dnd/core/dice.py:286-307`):

```python
# dnd/core/dice.py:260-284
def _roll_with_advantage(self) -> Tuple[int, List[int]]:
    """Roll 2 dice, return (max_value, [both_rolls])"""
    rolls = [random.randint(1, self.value) for _ in range(2)]
    return max(rolls), rolls

def _roll_with_disadvantage(self) -> Tuple[int, List[int]]:
    """Roll 2 dice, return (min_value, [both_rolls])"""
    rolls = [random.randint(1, self.value) for _ in range(2)]
    return min(rolls), rolls

# dnd/core/dice.py:286-307
def _roll(self, crit: bool = False) -> List[Tuple[int, List[int]]]:
    """
    Perform dice roll based on configuration.

    For crits: dice are doubled (count * 2) plus crit_extra_dice (Brutal Critical)
    """
    count = self.count if not crit else (self.count * 2 + self.crit_extra_dice)
    advantage_status = self.bonus.advantage

    if advantage_status == AdvantageStatus.ADVANTAGE:
        return [self._roll_with_advantage() for _ in range(count)]
    elif advantage_status == AdvantageStatus.DISADVANTAGE:
        return [self._roll_with_disadvantage() for _ in range(count)]
    else:
        return [(random.randint(1, self.value), []) for _ in range(count)]
```

**Key Insight:** The actual `random.randint()` call happens inside `_roll()`. There is no interception point between requesting a roll and getting the result.

### 3.3 Critical Hit Dice Doubling

On a critical hit, damage dice are doubled:

```python
# dnd/core/dice.py:299-300
# In _roll():
count = self.count if not crit else (self.count * 2 + self.crit_extra_dice)
```

- Normal: 2d6 → roll 2 dice
- Crit: 2d6 → roll 4 dice (doubled)
- Crit with Brutal Critical (+1): 2d6 → roll 5 dice (doubled + 1 extra)

The crit check happens when creating the DiceRoll:

```python
# dnd/core/dice.py:318
results = [roll[0] for roll in self._roll(crit=(self.attack_outcome == AttackOutcome.CRIT))]
```

---

## 4. Outcome Determination

### 4.1 determine_attack_outcome() Analysis

The `determine_attack_outcome()` function (`dnd/entity.py:51-93`) resolves d20 rolls against a target number:

```python
# dnd/entity.py:51-93
def determine_attack_outcome(
    roll: DiceRoll,
    ac: Union[int, ModifiableValue],
    crit_threshold: int = 20
) -> AttackOutcome:
    """
    Determine attack outcome based on roll and AC.

    Args:
        roll: The dice roll result
        ac: The armor class (or DC for saves/checks)
        crit_threshold: Minimum natural roll for crit (20, 19 for Improved Critical, 18 for Superior)
    """
    target_ac = ac.normalized_score if isinstance(ac, ModifiableValue) else ac
    natural_roll = get_natural_roll(roll)  # Handles advantage/disadvantage

    # Priority 1: AUTOMISS (Charmed vs charmer, etc.)
    if roll.auto_hit_status == AutoHitStatus.AUTOMISS:
        return AttackOutcome.MISS

    # Priority 2: AUTOHIT (guaranteed hit, check for crit)
    elif roll.auto_hit_status == AutoHitStatus.AUTOHIT:
        if roll.critical_status == CriticalStatus.AUTOCRIT or natural_roll >= crit_threshold:
            return AttackOutcome.CRIT
        else:
            return AttackOutcome.HIT

    # Priority 3: Natural 1 = auto-miss (BG3-style: applies to ALL rolls!)
    elif natural_roll == 1:
        return AttackOutcome.CRIT_MISS

    # Priority 4: Check if roll meets/exceeds target
    elif roll.total >= target_ac:
        if roll.critical_status == CriticalStatus.AUTOCRIT or natural_roll >= crit_threshold:
            return AttackOutcome.CRIT
        else:
            return AttackOutcome.HIT

    # Priority 5: Miss
    else:
        return AttackOutcome.MISS
```

### 4.2 The 5-Layer Priority System

| Priority | Condition | Result | Notes |
|----------|-----------|--------|-------|
| 1 | `AUTOMISS` | MISS | Charmed can't attack charmer |
| 2 | `AUTOHIT` | HIT/CRIT | Paralyzed attacker still crits |
| 3 | Natural 1 | CRIT_MISS | **BG3-style**: applies to saves too! |
| 4 | Total ≥ target | HIT/CRIT | Check crit_threshold |
| 5 | Otherwise | MISS | Didn't meet target |

### 4.3 Semantic Issues (AttackOutcome for all rolls)

**Current Usage:**

```python
# dnd/entity.py:1150 - Saving throws use determine_attack_outcome
outcome = determine_attack_outcome(roll, dc)
success = outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]

# dnd/entity.py:1193 - Skill checks use determine_attack_outcome
skill_check_outcome = determine_attack_outcome(roll, dc)
```

**Problem:** A save that succeeds is reported as `AttackOutcome.HIT`, which is confusing. The attack-specific concepts (CRIT_MISS, AUTOHIT) leak into non-attack contexts.

### 4.4 BG3 vs 5e RAW Behavior

| Roll Type | 5e RAW Nat 1 | 5e RAW Nat 20 | Current (BG3-style) |
|-----------|--------------|---------------|---------------------|
| Attack | Auto-miss | Auto-hit + crit | Same |
| Save | No effect | No effect | **Auto-fail!** |
| Check | No effect | No effect | **Auto-fail!** |

**Impact on Tests:**

Tests expecting "guaranteed" save outcomes are flaky:
- Target with -5 WIS vs DC 15: Expected always fail, but nat 20 gives 15 = DC (succeeds!)
- Target with +17 CON vs DC 15: Expected always pass, but nat 1 auto-fails

---

## 5. Damage Dice Pipeline

### 5.1 Weapon → Damage → Dice → DiceRoll

Complete flow from weapon definition to HP reduction:

```
┌────────────────────────────────────────────────────────────────────┐
│                     DAMAGE DICE PIPELINE                            │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Weapon Definition (dnd/items/weapons.py)                       │
│     └─► damages: List[Damage]  # e.g., 1d8 slashing                │
│                                                                     │
│  2. Entity.get_damages() (dnd/entity.py:724-732)                   │
│     └─► Returns List[Damage] with ability bonuses applied          │
│                                                                     │
│  3. Damage.get_dice() (dnd/core/events.py:1152-1153)               │
│     └─► Creates Dice with attack_outcome for crit detection        │
│                                                                     │
│  4. Dice.roll (computed property)                                   │
│     └─► DiceRoll with results, total, etc.                         │
│                                                                     │
│  5. DamageRolledEvent (HANDLERS INTERCEPT HERE!)                   │
│     └─► Handlers can modify final_rolls                            │
│                                                                     │
│  6. TakeDamageEvent                                                │
│     └─► Resistance/vulnerability applied                           │
│                                                                     │
│  7. Health.take_damage() (dnd/blocks/health.py:350-378)            │
│     └─► Apply multiplier, subtract from HP                         │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

### 5.2 The Damage Class

```python
# dnd/core/events.py:1136-1153
class Damage(BaseObject):
    name: str = Field(default="Damage")
    damage_dice: Literal[4, 6, 8, 10, 12, 20] = Field(...)  # d4, d6, d8, d10, d12, d20
    dice_numbers: int = Field(...)  # Number of dice (e.g., 2 for 2d6)
    damage_bonus: Optional[ModifiableValue] = Field(default=None)  # Flat bonus
    damage_type: DamageType = Field(...)  # Slashing, Fire, etc.

    def get_dice(self, attack_outcome: AttackOutcome, crit_extra_dice: int = 0) -> Dice:
        return Dice(
            count=self.dice_numbers,
            value=self.damage_dice,
            bonus=self.damage_bonus,
            roll_type=RollType.DAMAGE,
            attack_outcome=attack_outcome,  # Enables crit doubling
            crit_extra_dice=crit_extra_dice  # Brutal Critical
        )
```

### 5.3 Crit Dice Doubling Location

Crit dice doubling happens in `Dice._roll()` when creating the DiceRoll:

```python
# dnd/core/dice.py:299-300
count = self.count if not crit else (self.count * 2 + self.crit_extra_dice)
```

This is called from the `roll` computed property:

```python
# dnd/core/dice.py:318
results = [roll[0] for roll in self._roll(crit=(self.attack_outcome == AttackOutcome.CRIT))]
```

### 5.4 Resistance/Vulnerability Application

After dice manipulation but before HP subtraction:

```python
# dnd/blocks/health.py:340-378
def damage_multiplier(self, damage_type: DamageType) -> float:
    resistance = self.get_resistance(damage_type)
    if resistance == ResistanceStatus.IMMUNITY:
        return 0
    elif resistance == ResistanceStatus.RESISTANCE:
        return 0.5
    elif resistance == ResistanceStatus.VULNERABILITY:
        return 2
    else:
        return 1

def take_damage(self, damage: int, damage_type: DamageType, source_entity_uuid: UUID) -> int:
    damage_after_multiplier = max(0, int(damage * self.damage_multiplier(damage_type)) - self.damage_reduction.score)
    # Handle temp HP, then apply to real HP
    ...
```

### 5.5 Full Pipeline in Attack._apply()

```python
# dnd/actions.py:806-876 (simplified)
# Step 1: Roll damage dice
crit_extra_dice = source_entity.get_crit_extra_dice(weapon_slot)
original_rolls = []
for damage in damages:
    dice = damage.get_dice(attack_outcome=attack_event.attack_outcome, crit_extra_dice=crit_extra_dice)
    roll = dice.roll  # ← random.randint() called here!
    original_rolls.append(roll)

# Step 2: Create DAMAGE_ROLLED event (handlers intercept at EFFECT)
damage_rolled_event = DamageRolledEvent(
    weapon_slot=weapon_slot,
    attack_outcome=attack_event.attack_outcome,
    damages=damages,
    original_rolls=original_rolls,
    final_rolls=list(original_rolls),  # Handlers replace entries here
)

# Step 3: Transition to EFFECT (handlers fire!)
damage_rolled_event = damage_rolled_event.phase_to(EventPhase.EFFECT)

# Step 4: Use final_rolls (possibly modified)
damage_rolls = damage_rolled_event.final_rolls
total_damage = sum(roll.total for roll in damage_rolls)

# Step 5: Create TAKE_DAMAGE event and apply
take_damage_event = TakeDamageEvent(total_damage=total_damage, ...)
# ... health.take_damage() called
```

---

## 6. Event-Based Dice Interception

### 6.1 DamageRolledEvent Architecture

The `DamageRolledEvent` (`dnd/core/events.py:1160-1199`) enables damage dice manipulation:

```python
# dnd/core/events.py:1160-1199
class DamageRolledEvent(Event):
    """
    Event fired after damage dice are rolled but before damage is applied.

    Handlers create new DiceRoll versions - original rolls are immutable.
    """
    event_type: EventType = Field(default=EventType.DAMAGE_ROLLED)

    # Context (read-only)
    weapon_slot: WeaponSlot = Field(...)
    attack_outcome: AttackOutcome = Field(...)  # HIT or CRIT
    damages: List[Damage] = Field(...)  # Damage specifications

    # IMMUTABLE: Never modified
    original_rolls: List[DiceRoll] = Field(...)

    # MUTABLE: Handlers replace entries here
    final_rolls: List[DiceRoll] = Field(...)

    # AUDIT: Track changes [(handler_name, roll_index, old_total, new_total, reason), ...]
    roll_modifications: List[Tuple[str, int, int, int, str]] = Field(default_factory=list)

    def replace_roll(self, index: int, new_roll: DiceRoll, handler_name: str, reason: str) -> None:
        """Helper for handlers to replace a roll and track the change."""
        old_roll = self.final_rolls[index]
        self.roll_modifications.append((handler_name, index, old_roll.total, new_roll.total, reason))
        self.final_rolls[index] = new_roll
```

### 6.2 SavingThrowEvent Architecture

The `SavingThrowEvent` (`dnd/core/events.py:734-845`) enables save reroll features:

```python
# dnd/core/events.py:734-845
class SavingThrowEvent(D20Event):
    """An event that represents a saving throw."""
    ability_name: AbilityName = Field(...)  # "strength", "dexterity", etc.
    event_type: EventType = Field(default=EventType.SAVING_THROW)

    # Inherited from D20Event:
    # dc: Optional[Union[int, ModifiableValue]]
    # bonus: Optional[Union[int, ModifiableValue]]
    # dice_roll: Optional[DiceRoll]  # The roll result
    # result: Optional[bool]  # Success/failure
```

Handlers at EFFECT phase can replace the entire roll and result:

```python
# Example: Indomitable replaces dice_roll and result
return event.model_copy(update={
    "dice_roll": new_roll,
    "result": new_success,
    "modified": True
})
```

### 6.3 Handler Registration Pattern

Event handlers are registered via `Entity.add_event_handler()`:

```python
# Pattern from dnd/classes/fighter.py:411-421
handler = EventHandler(
    name="Great Weapon Fighting",
    source_entity_uuid=source_entity_uuid,
    trigger_conditions=[
        Trigger(
            event_type=EventType.DAMAGE_ROLLED,
            event_phase=EventPhase.EFFECT  # After roll, before application
        )
    ],
    event_processor=great_weapon_fighting_processor
)
target.add_event_handler(handler)  # Auto-registers with EventQueue too
```

**IMPORTANT:** Only use `entity.add_event_handler()`. Do NOT also call `EventQueue.add_event_handler()` - this would register twice and the handler would fire twice!

### 6.4 Canonical Example: Great Weapon Fighting

Full implementation (`dnd/classes/fighter.py:300-364`):

```python
# dnd/classes/fighter.py:300-364
def great_weapon_fighting_processor(
    event: DamageRolledEvent,
    source_entity_uuid: UUID
) -> Optional[DamageRolledEvent]:
    """Rerolls 1s and 2s on damage dice for two-handed melee weapons."""

    # 1. Check ownership - only process own attacks
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # 2. Check weapon eligibility
    weapon = entity.equipment._get_weapon_by_slot(event.weapon_slot)
    if not weapon or isinstance(weapon, Shield):
        return None
    if not isinstance(weapon, Weapon):
        return None

    # Must be melee with Two-Handed or Versatile property
    is_melee = weapon.range.type == RangeType.REACH
    has_two_handed = WeaponProperty.TWO_HANDED in weapon.properties
    has_versatile = WeaponProperty.VERSATILE in weapon.properties

    if not is_melee or not (has_two_handed or has_versatile):
        return None

    # 3. Process each damage roll
    any_modified = False
    for i, original_roll in enumerate(event.final_rolls):
        results = original_roll.results if isinstance(original_roll.results, list) else [original_roll.results]

        # Check if any dice are 1 or 2
        needs_reroll = any(r <= 2 for r in results)
        if not needs_reroll:
            continue

        # Reroll 1s and 2s (must use new result per RAW)
        new_results = []
        rerolled_dice = []
        for r in results:
            if r <= 2:
                new_result = random.randint(1, weapon.damage_dice)
                new_results.append(new_result)
                rerolled_dice.append(f"{r}→{new_result}")
            else:
                new_results.append(r)

        # Replace the roll using helper
        new_roll = create_modified_dice_roll(original_roll, new_results)
        event.replace_roll(i, new_roll, "Great Weapon Fighting", f"Rerolled: {', '.join(rerolled_dice)}")
        any_modified = True

    if any_modified:
        return event.model_copy(update={"modified": True})
    return None
```

### 6.5 Canonical Example: Indomitable

Save reroll implementation (`dnd/classes/fighter.py:1456-1508`):

```python
# dnd/classes/fighter.py:1456-1508
def indomitable_processor(
    event: Event,
    source_entity_uuid: UUID
) -> Optional[Event]:
    """Reroll failed saving throws."""

    # 1. Only process own saves
    if event.target_entity_uuid != source_entity_uuid:
        return None

    if not isinstance(event, SavingThrowEvent):
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # 2. Check if save failed
    if event.result is not False:
        return None  # Save succeeded or not yet resolved

    # 3. Check and consume resource
    if not entity.action_economy.can_afford_resource("indomitable", 1):
        return None
    entity.action_economy.consume_resource("indomitable", 1)

    # 4. Reroll (must use new result per RAW)
    ability_name = event.ability_name
    save_bonus = entity.saving_throw_bonus(event.source_entity_uuid, ability_name)
    new_roll = entity.roll_d20(save_bonus, RollType.SAVE)

    # Determine new result
    dc = event.get_dc()
    new_outcome = determine_attack_outcome(new_roll, dc)  # ← Semantic mismatch!
    new_success = new_outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]

    # 5. Return modified event
    return event.model_copy(update={
        "dice_roll": new_roll,
        "result": new_success,
        "modified": True,
        "status_message": f"{entity.name} uses Indomitable! Reroll: {new_roll.total} vs DC {dc}"
    })
```

---

## 7. Combat Log Integration

### 7.1 Automatic Generation at COMPLETION

Events auto-generate combat log entries when transitioning to COMPLETION phase via `generate_combat_log()`. This happens in `Event.phase_to()`:

```python
# No explicit call needed - phase_to(COMPLETION) triggers it
completion_event = effect_event.phase_to(EventPhase.COMPLETION)
# ↑ This internally calls generate_combat_log() if the event implements it
```

### 7.2 DiceRollDisplay Serialization

The `DiceRollDisplay` model (`dnd/core/combat_log.py:47-66`) serializes dice rolls for logs:

```python
# dnd/core/combat_log.py:47-66
class DiceRollDisplay(BaseModel):
    """Display information for a dice roll."""
    dice_str: str = Field(...)  # "1d6", "d20"
    results: List[int] = Field(default_factory=list)  # Individual die results
    bonus: int = Field(default=0)  # Total bonus
    total: int = Field(...)  # Final total

    # For advantage/disadvantage on d20 rolls
    all_d20_rolls: Optional[List[int]] = Field(default=None)  # Both dice for adv/dis
    d20_used: Optional[int] = Field(default=None)  # Which was used
    advantage_status: Optional[str] = Field(default=None)  # "advantage" or "disadvantage"
```

### 7.3 Three Verbosity Levels

Each `CombatLogEntry` contains three formatted strings (`dnd/core/combat_log.py:257-310`):

| Level | Field | Format | Example |
|-------|-------|--------|---------|
| COMPACT | `compact` | One-liner | `"{cyan:Hero} {green:hits} {yellow:Skeleton} for {red:7} damage"` |
| VERBOSE | `verbose` | Summary + details | Attack line + damage breakdown |
| DETAILED | `detailed` | Full breakdown | All modifier sources |

**Markdown Formatting:**
- `{color:text}` → Colored text (rendered by Rich)
- `**text**` → Bold
- Colors: `cyan` (actors), `yellow` (targets), `green` (success), `red` (failure/damage)

### 7.4 Modifier Breakdown Extraction

`ModifiableValue.get_breakdown()` (`dnd/core/values.py:2155-2185`) extracts modifiers with cleaned names:

```python
# dnd/core/values.py:2155-2185
def get_breakdown(self) -> List[Dict[str, Any]]:
    """
    Get a breakdown of all numerical modifiers.

    Returns list of: {name: str, value: int, source: str}
    """
    # Name cleanup mapping
    name_cleanup = {
        "proficiency_bonus_base_value": "Prof",
        "strength Ability Score_base_value": "STR",
        "dexterity Ability Score_base_value": "DEX",
        "constitution Ability Score_base_value": "CON",
        "intelligence Ability Score_base_value": "INT",
        "wisdom Ability Score_base_value": "WIS",
        "charisma Ability Score_base_value": "CHA",
        # ... more mappings
    }
    # Iterates all 6 channels, collects non-zero numerical modifiers
    # Returns cleaned name, value, and source channel
```

### 7.5 Formatting Helpers

```python
# dnd/core/combat_log.py:436-488

def md_color(text: str, color: str) -> str:
    """Wrap text: {color:text}"""
    return f"{{{color}:{text}}}"

def md_d20_roll(roll: DiceRollDisplay) -> str:
    """
    Format d20 with advantage display.

    Normal: "d20({cyan:15})"
    Advantage: "ADV d20(15,8→{green:15})"
    Disadvantage: "DIS d20(15,8→{red:8})"
    """
    if roll.advantage_status == "advantage" and len(roll.all_d20_rolls) >= 2:
        return f"ADV d20({roll.all_d20_rolls[0]},{roll.all_d20_rolls[1]}→{md_color(str(roll.d20_used), 'green')})"
    elif roll.advantage_status == "disadvantage" and len(roll.all_d20_rolls) >= 2:
        return f"DIS d20({roll.all_d20_rolls[0]},{roll.all_d20_rolls[1]}→{md_color(str(roll.d20_used), 'red')})"
    else:
        return f"d20({md_color(str(roll.d20_used), 'cyan')})"

def md_breakdown(breakdown: List[ModifierBreakdown]) -> str:
    """Format: [Prof +2, DEX +2]"""
    if not breakdown:
        return ""
    parts = [f"{m.name} {'+' if m.value >= 0 else ''}{m.value}" for m in breakdown if m.value != 0]
    return f"[{', '.join(parts)}]" if parts else ""
```

---

## 8. Deterministic Testing Design

This is a critical section analyzing how to enable deterministic dice rolls for testing, using a **unified event hierarchy** that supports presets, handler interception, and extensibility to all roll types.

### 8.1 Current State: Where Rolls Happen

Dice rolls happen **synchronously inside action `_apply()` methods**, not as separate interceptable events:

| Context | Location | Phase | Code Path |
|---------|----------|-------|-----------|
| Attack d20 | `Attack._apply()` | EXECUTION | `dnd/actions.py:770` → `source.roll_d20(bonus)` → `Dice.roll` → `random.randint()` |
| Attack damage | `Attack._apply()` | EFFECT | `dnd/actions.py:811-813` → `damage.get_dice().roll` → `random.randint()` per die |
| Shove contest | `Shove._apply()` | EXECUTION | `dnd/actions.py:1970` → `source.roll_d20(athletics_bonus)` |
| Saving throw | `Entity.saving_throw()` | EXECUTION | `dnd/entity.py:1149` → `self.roll_d20(save_bonus)` |
| Skill check | `Entity.skill_check()` | EXECUTION | `dnd/entity.py:1192` → `self.roll_d20(skill_check)` |
| Spell attack | `SpellAction._apply()` | EXECUTION | `caster.roll_d20(spell_attack)` |
| Spell damage | `SpellAction._apply()` | EFFECT | `damage.get_dice().roll` |

**Key Insight:** The `Dice.roll` computed property calls `random.randint()` immediately (`dnd/core/dice.py:286-307`). There is no interception point between "request roll" and "get result".

### 8.2 Existing Workaround: Outcome-Based Forcing

Current utilities in `dnd/utils/test_utils.py:63-129`:

```python
# dnd/utils/test_utils.py:63-79
def force_attack_hit(entity: Entity) -> UUID:
    """Add +100 attack bonus to guarantee hits."""
    modifier = NumericalModifier.create(
        source_entity_uuid=entity.uuid,
        name="Forced Hit",
        value=100
    )
    mod_uuid = entity.equipment.melee_attack_bonus.self_static.add_value_modifier(modifier)
    return mod_uuid

# dnd/utils/test_utils.py:82-98
def force_attack_miss(entity: Entity) -> UUID:
    """Add -100 attack penalty to guarantee misses."""
    modifier = NumericalModifier.create(
        source_entity_uuid=entity.uuid,
        name="Forced Miss",
        value=-100
    )
    mod_uuid = entity.equipment.melee_attack_bonus.self_static.add_value_modifier(modifier)
    return mod_uuid

# dnd/utils/test_utils.py:101-118
def force_attack_crit(entity: Entity) -> UUID:
    """Add AUTOCRIT modifier to guarantee critical hits."""
    modifier = CriticalModifier(
        name="Forced Crit",
        value=CriticalStatus.AUTOCRIT,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid
    )
    mod_uuid = entity.equipment.melee_attack_bonus.self_static.add_critical_modifier(modifier)
    return mod_uuid
```

**Limitations:**
- ✅ Works for attack hit/miss/crit
- ❌ Cannot force specific roll values (e.g., "roll exactly 15")
- ❌ Cannot force damage dice values
- ❌ Cannot control multiple sequential rolls with specific values
- ❌ Cannot test edge cases like "nat 20 with low bonus still hits"

### 8.3 Unified Dice Roll Event Hierarchy

The key insight is that **all dice roll events share common patterns** for presets, handler interception, and audit trails. Rather than treating d20 rolls and damage rolls as completely separate systems, we define a **two-level hierarchy**:

```
DiceRollResultEvent (base class - any dice roll)
│
├── D20RollResultEvent (d20 rolls: attacks, saves, checks)
│   └── Fields: dc, result, single dice_roll
│
└── DamageRollResultEvent (damage dice: weapon, spell, etc.)
    └── Fields: original_rolls, final_rolls, replace_roll(), roll_modifications
```

This design consolidates deterministic testing AND reactive ability support into a single, event-driven system. No global dice queue is needed—presets flow through events, and the same code path handles both random and deterministic rolls.

#### 8.3.1 Base Class: DiceRollResultEvent

The base class provides common fields and preset support for ALL dice roll types:

```python
class DiceRollResultEvent(Event):
    """
    Base class for all dice roll result events.

    Provides unified preset support and handler interception
    for d20 rolls, damage rolls, healing rolls, etc.
    """
    event_type: EventType = Field(default=EventType.DICE_ROLL_RESULT)

    # === Entity Context (common to all rolls) ===
    source_entity_uuid: UUID = Field(...)          # Who made the roll
    target_entity_uuid: Optional[UUID] = None      # Who is affected (if any)

    # === Roll Type ===
    roll_type: RollType = Field(...)  # ATTACK, SAVE, CHECK, DAMAGE

    # === Preset Support (common mechanism) ===
    preset: bool = Field(default=False)  # True if ANY roll was preset

    # === Handler Context ===
    context: Dict[str, Any] = Field(default_factory=dict)  # Arbitrary context for handlers
    modified: bool = Field(default=False)  # Set True when handler modifies

    # === Audit Trail ===
    roll_modifications: List[Tuple[str, str]] = Field(default_factory=list)
    # Format: [(handler_name, reason), ...]

    def add_modification(self, handler_name: str, reason: str) -> None:
        """Track that a handler modified this roll."""
        self.roll_modifications.append((handler_name, reason))
        self.modified = True
```

**Key design decisions:**

1. **`preset` flag at event level** - Indicates whether the roll(s) used preset values, important for combat log display and debugging
2. **Common `context` dict** - Handlers can filter on arbitrary context (weapon_slot, spell_name, etc.)
3. **Unified audit trail** - All roll types track modifications the same way

#### 8.3.2 D20 Subclass: D20RollResultEvent

The d20-specific event extends the base with single-roll semantics:

```python
class D20RollResultEvent(DiceRollResultEvent):
    """
    Event for d20 roll results (attacks, saves, checks).

    Fired after initial result determined, before outcome.
    Handlers can replace the roll (Lucky, Portent, Silvery Barbs).
    """
    event_type: EventType = Field(default=EventType.D20_ROLL_RESULT)

    # === The Roll (single d20) ===
    roll: DiceRoll = Field(...)           # Initial roll result
    original_roll: DiceRoll = Field(...)  # Immutable copy for audit
    final_roll: Optional[DiceRoll] = None # After handler modifications

    # === D20-Specific Fields ===
    dc: Optional[int] = None                    # Difficulty class (if known)
    bonus: Optional[ModifiableValue] = None     # All modifiers applied
    result: Optional[bool] = None               # Success/failure (set after outcome)

    # === Context for Specific Roll Types ===
    ability_name: Optional[AbilityName] = None  # For saves
    skill_name: Optional[SkillName] = None      # For checks

    # === Preset Value ===
    preset_d20: Optional[int] = None  # Natural d20 value for tests

    def replace_roll(self, new_roll: DiceRoll, handler_name: str, reason: str) -> None:
        """Replace the roll result. Handler helper method."""
        old_total = self.roll.total
        self.final_roll = new_roll
        self.add_modification(handler_name, f"{reason} ({old_total} → {new_roll.total})")

    def get_effective_roll(self) -> DiceRoll:
        """Return final_roll if set, otherwise original roll."""
        return self.final_roll if self.final_roll else self.roll

    @model_validator(mode="after")
    def set_preset_flag(self) -> Self:
        """Set preset=True if preset_d20 was used."""
        if self.preset_d20 is not None:
            self.preset = True
        return self
```

**Handler interception points:**
- **Lucky feat**: See roll, decide to reroll, keep better
- **Portent (Divination Wizard)**: Replace with stored d20 result
- **Silvery Barbs**: Force enemy to reroll, use lower
- **Halfling Lucky**: Reroll nat 1s
- **Indomitable**: Reroll failed saves

#### 8.3.3 Damage Subclass: DamageRollResultEvent

The damage-specific event handles multiple dice with detailed audit trails:

```python
class DamageRollResultEvent(DiceRollResultEvent):
    """
    Event for damage roll results.

    Fired after damage dice rolled, before damage applied.
    Handlers can modify individual rolls (GWF, Savage Attacker).

    REPLACES the old DamageRolledEvent - all usages must be updated.
    """
    event_type: EventType = Field(default=EventType.DAMAGE_ROLL_RESULT)

    # === Weapon/Attack Context ===
    weapon_slot: WeaponSlot = Field(...)
    attack_outcome: AttackOutcome = Field(...)  # HIT or CRIT
    damages: List[Damage] = Field(...)          # Damage specifications

    # === The Rolls (multiple damage dice) ===
    original_rolls: List[DiceRoll] = Field(...)  # Immutable originals
    final_rolls: List[DiceRoll] = Field(...)     # After handler modifications

    # === Preset Values ===
    preset_damage: Optional[List[List[int]]] = None  # Per-damage die results
    # e.g., [[4, 3], [6]] for 2d6 slashing + 1d6 fire

    # === Detailed Audit Trail ===
    roll_modifications: List[Tuple[str, int, int, int, str]] = Field(default_factory=list)
    # Format: [(handler_name, roll_index, old_total, new_total, reason), ...]

    def replace_roll(self, index: int, new_roll: DiceRoll, handler_name: str, reason: str) -> None:
        """Replace a specific roll. Helper for handlers."""
        old_roll = self.final_rolls[index]
        self.roll_modifications.append((handler_name, index, old_roll.total, new_roll.total, reason))
        self.final_rolls[index] = new_roll
        self.modified = True

    @model_validator(mode="after")
    def set_preset_flag(self) -> Self:
        """Set preset=True if preset_damage was used."""
        if self.preset_damage is not None:
            self.preset = True
        return self
```

**Handler interception points:**
- **Great Weapon Fighting**: Reroll 1s and 2s
- **Savage Attacker**: Reroll weapon damage, keep better
- **Elemental Adept**: Treat 1s as 2s for elemental damage
- **Empowered Spell**: Reroll Cha mod number of damage dice

#### 8.3.4 The DiceRoll.preset Flag

When a roll is created from a preset value, it carries a `preset` flag:

```python
class DiceRoll(BaseModel):
    # ... existing fields ...

    preset: bool = Field(default=False)  # True if this roll used a preset value
```

This flag travels with the roll everywhere, enabling:
- Combat log to show `[preset]` indicator
- Handlers to know if they're seeing a "real" or test roll
- Debugging to track which rolls were deterministic

#### 8.3.5 Unified Hierarchy Diagram

```
                    ┌─────────────────────────────────┐
                    │     DiceRollResultEvent         │
                    │        (base class)             │
                    ├─────────────────────────────────┤
                    │ source_entity_uuid: UUID        │
                    │ target_entity_uuid: Optional    │
                    │ roll_type: RollType             │
                    │ preset: bool                    │
                    │ context: Dict                   │
                    │ modified: bool                  │
                    │ roll_modifications: List        │
                    └───────────────┬─────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
        ┌───────────▼───────────┐       ┌───────────▼───────────┐
        │  D20RollResultEvent   │       │ DamageRollResultEvent │
        ├───────────────────────┤       ├───────────────────────┤
        │ roll: DiceRoll        │       │ original_rolls: List  │
        │ original_roll         │       │ final_rolls: List     │
        │ final_roll: Optional  │       │ weapon_slot           │
        │ dc: Optional[int]     │       │ attack_outcome        │
        │ bonus: ModValue       │       │ damages: List         │
        │ result: Optional[bool]│       │ preset_damage         │
        │ ability_name          │       │ replace_roll(idx,...) │
        │ skill_name            │       │                       │
        │ preset_d20            │       │                       │
        │ replace_roll(...)     │       │                       │
        │ get_effective_roll()  │       │                       │
        └───────────────────────┘       └───────────────────────┘
                    │                               │
                    │ Handlers:                     │ Handlers:
                    │ - Lucky                       │ - Great Weapon Fighting
                    │ - Portent                     │ - Savage Attacker
                    │ - Silvery Barbs               │ - Elemental Adept
                    │ - Indomitable                 │ - Empowered Spell
                    │ - Halfling Lucky              │
                    └───────────────────────────────┘
```

### 8.4 Test Usage Patterns

Both event types support presets consistently through their respective preset fields.

#### Setting D20 Presets in Tests

```python
# Test: Attack with natural 20 (crit)
attack_event = AttackEvent(
    name="test_attack",
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
    preset_d20=20  # Force natural 20
)
attack = Attack(...)
result = attack.apply()
assert result.attack_outcome == AttackOutcome.CRIT

# Test: Save with natural 1 (auto-fail in BG3 mode)
save_event = SavingThrowEvent(
    ability_name="wisdom",
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target.uuid,
    dc=15,
    preset_d20=1  # Force nat 1
)
result = entity.saving_throw(save_event)
assert result.result == False  # Failed
```

#### Setting Damage Presets in Tests

```python
# Test: Specific damage dice values
attack_event = AttackEvent(
    preset_d20=15,  # Hits
    preset_damage=[[4, 3]]  # 2d6 weapon rolls [4, 3] = 7
)
# Expected: 7 + STR modifier damage

# Test: Multiple damage types
attack_event = AttackEvent(
    preset_d20=15,
    preset_damage=[[4, 3], [5]]  # 2d6 slashing + 1d6 fire
)
# Expected: 7 slashing + 5 fire + modifiers
```

#### Testing Edge Cases

```python
# Test: Nat 20 with low bonus still crits
attack_event = AttackEvent(
    preset_d20=20,  # Natural 20
    # Even with -5 attack bonus, this crits!
)

# Test: Roll exactly meets DC
save_event = SavingThrowEvent(
    ability_name="dexterity",
    dc=15,
    preset_d20=10  # With +5 bonus = 15 = DC (tie = success)
)

# Test: Roll just misses DC
save_event = SavingThrowEvent(
    ability_name="dexterity",
    dc=15,
    preset_d20=9  # With +5 bonus = 14 < 15 (failure)
)
```

### 8.5 Reactive Abilities Support

The unified hierarchy means handlers follow the same pattern regardless of roll type. The only difference is which event class they handle and which fields they access.

#### D20 Handler Pattern: Lucky Feat

```python
def lucky_processor(
    event: D20RollResultEvent,
    source_entity_uuid: UUID
) -> Optional[D20RollResultEvent]:
    """Spend luck point to reroll, keep better result."""

    # Only trigger on own rolls
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity.action_economy.can_afford_resource("luck_points", 1):
        return None

    # AI/player decision: should we use Lucky?
    original_total = event.roll.total
    if original_total >= 15:  # Don't waste on good rolls
        return None

    # Consume resource and reroll
    entity.action_economy.consume_resource("luck_points", 1)
    new_roll = entity.roll_d20(event.bonus, event.roll_type)

    # Keep better result
    if new_roll.total > original_total:
        event.replace_roll(new_roll, "Lucky", f"Rerolled {original_total} → {new_roll.total}")
        return event.model_copy(update={"modified": True})

    return None  # Keep original
```

#### Damage Handler Pattern: Great Weapon Fighting

```python
def great_weapon_fighting_processor(
    event: DamageRollResultEvent,
    source_entity_uuid: UUID
) -> Optional[DamageRollResultEvent]:
    """Rerolls 1s and 2s on damage dice for two-handed melee weapons."""

    # 1. Check ownership - only process own attacks
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # 2. Check weapon eligibility
    weapon = entity.equipment._get_weapon_by_slot(event.weapon_slot)
    if not weapon or isinstance(weapon, Shield):
        return None

    is_melee = weapon.range.type == RangeType.REACH
    has_two_handed = WeaponProperty.TWO_HANDED in weapon.properties
    has_versatile = WeaponProperty.VERSATILE in weapon.properties

    if not is_melee or not (has_two_handed or has_versatile):
        return None

    # 3. Process each damage roll
    any_modified = False
    for i, original_roll in enumerate(event.final_rolls):
        results = original_roll.results if isinstance(original_roll.results, list) else [original_roll.results]

        # Check if any dice are 1 or 2
        needs_reroll = any(r <= 2 for r in results)
        if not needs_reroll:
            continue

        # Reroll 1s and 2s
        new_results = []
        rerolled_dice = []
        for r in results:
            if r <= 2:
                new_result = random.randint(1, weapon.damage_dice)
                new_results.append(new_result)
                rerolled_dice.append(f"{r}→{new_result}")
            else:
                new_results.append(r)

        # Replace using helper
        new_roll = create_modified_dice_roll(original_roll, new_results)
        event.replace_roll(i, new_roll, "Great Weapon Fighting", f"Rerolled: {', '.join(rerolled_dice)}")
        any_modified = True

    if any_modified:
        return event.model_copy(update={"modified": True})
    return None
```

#### Unified Handler Registration

Both handler types register the same way, just with different event types:

```python
# D20 handler (Lucky)
lucky_handler = EventHandler(
    name="Lucky",
    source_entity_uuid=source_entity_uuid,
    trigger_conditions=[
        Trigger(
            event_type=EventType.D20_ROLL_RESULT,
            event_phase=EventPhase.EFFECT
        )
    ],
    event_processor=lucky_processor
)
entity.add_event_handler(lucky_handler)

# Damage handler (GWF)
gwf_handler = EventHandler(
    name="Great Weapon Fighting",
    source_entity_uuid=source_entity_uuid,
    trigger_conditions=[
        Trigger(
            event_type=EventType.DAMAGE_ROLL_RESULT,
            event_phase=EventPhase.EFFECT
        )
    ],
    event_processor=great_weapon_fighting_processor
)
entity.add_event_handler(gwf_handler)
```

### 8.6 Implementation Considerations

#### Event Classes to Create/Modify

| Event | Status | Changes Needed |
|-------|--------|----------------|
| `DiceRollResultEvent` | **New** | Create base class with common fields |
| `D20RollResultEvent` | **New** | Create with d20-specific fields, preset_d20 |
| `DamageRolledEvent` | **Refactor** | Rename to `DamageRollResultEvent`, extend base class, update all usages |
| `AttackEvent` | Existing | Add `preset_d20`, `preset_damage` fields |
| `SavingThrowEvent` | Existing | Add `preset_d20` field |
| `SkillCheckEvent` | Existing | Add `preset_d20` field |

#### DiceRoll Modifications

```python
class DiceRoll(BaseModel):
    # ... existing fields ...

    # NEW: Track if this roll was preset
    preset: bool = Field(default=False)
```

#### EventType Changes

```python
class EventType(str, Enum):
    # ... existing types ...

    # NEW (add these)
    DICE_ROLL_RESULT = "DICE_ROLL_RESULT"
    D20_ROLL_RESULT = "D20_ROLL_RESULT"
    DAMAGE_ROLL_RESULT = "DAMAGE_ROLL_RESULT"

    # REMOVE (replace all usages)
    # DAMAGE_ROLLED - replaced by DAMAGE_ROLL_RESULT
```

#### Migration Path

1. **Add base `DiceRollResultEvent`** to `dnd/core/events.py`
2. **Add `D20RollResultEvent`** extending base
3. **Rename `DamageRolledEvent` to `DamageRollResultEvent`**, extend base, update all usages in codebase
4. **Add `preset` field** to `DiceRoll`
5. **Add preset fields** to action events (AttackEvent, SavingThrowEvent, etc.)
6. **Update roll creation code** to use presets when provided
7. **Wire up D20RollResultEvent** in attack/save/check flows
8. **Add reactive ability handlers** as features are implemented

#### Combat Log Compatibility

The hierarchy preserves existing combat log integration:

- `DiceRollDisplay.from_dice_roll()` works unchanged
- `md_d20_roll()` formatting works unchanged
- `roll_modifications` audit trail available on both event types
- New `preset` flag enables `[preset]` indicator in logs

#### Benefits of Unified Hierarchy

| Aspect | Separate Systems | Unified Hierarchy |
|--------|------------------|-------------------|
| Code duplication | High (preset logic in 2 places) | Low (base class) |
| Handler registration | Different patterns | Same pattern |
| Preset mechanism | Different per roll type | Consistent |
| Adding new roll types | Copy/paste entire system | Extend base class |
| Combat log compat | Must implement twice | Inherits from base |
| Audit trail format | Different structures | Unified structure |
| Future extensibility | Add third system for healing? | Just extend base |

The unified approach means:
- Tests set `event.preset_d20` or `event.preset_damage`
- Production leaves preset fields `None`
- Same code path handles both
- Handler interception available at the same point
- Healing dice (future) just extends `DiceRollResultEvent`

### 8.7 Module Hierarchy and Import Rules

**CRITICAL**: The dice roll event hierarchy must respect the core module dependency order. NO circular imports. NO late imports to "fix" circular dependencies.

#### Core Module Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                 CORE MODULE DEPENDENCY ORDER                     │
│                    (imports flow DOWNWARD)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   base_object.py                                                │
│   └── No dnd imports (only pydantic, typing, uuid)              │
│            │                                                     │
│            ▼                                                     │
│   modifiers.py                                                  │
│   └── Imports: base_object                                      │
│   └── Defines: DamageType, AdvantageModifier, etc.              │
│            │                                                     │
│            ▼                                                     │
│   values.py                                                     │
│   └── Imports: base_object, modifiers                           │
│   └── Defines: ModifiableValue, AdvantageStatus, etc.           │
│            │                                                     │
│            ▼                                                     │
│   dice.py                                                       │
│   └── Imports: values                                           │
│   └── Defines: Dice, DiceRoll, AttackOutcome, RollType          │
│            │                                                     │
│            ▼                                                     │
│   events.py  ◄─── ALL NEW EVENT CLASSES GO HERE                 │
│   └── Imports: base_object, values, modifiers, dice, combat_log │
│   └── Defines: Event, EventType, EventPhase, all event classes  │
│   └── Defines: WeaponSlot, AbilityName, SkillName, Damage, etc. │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### What events.py CAN Import

| Module | Can Import? | Types Available |
|--------|-------------|-----------------|
| `base_object.py` | ✓ | `BaseObject` |
| `modifiers.py` | ✓ | `DamageType`, modifiers |
| `values.py` | ✓ | `ModifiableValue`, `AdvantageStatus`, etc. |
| `dice.py` | ✓ | `Dice`, `DiceRoll`, `AttackOutcome`, `RollType` |
| `combat_log.py` | ✓ | `CombatLogEntry`, formatters |

#### What events.py CANNOT Import

| Module | Why Not |
|--------|---------|
| `entity.py` | Entity imports events.py → circular |
| `actions.py` | Actions import events.py → circular |
| `conditions.py` | Conditions import events.py → circular |
| `blocks/*.py` | Blocks import events.py → circular |
| `spells/*.py` | Spells import events.py → circular |

#### Why the Unified Hierarchy is Safe

All types needed for `DiceRollResultEvent` are already available in events.py's allowed imports:

```python
# events.py current imports (verified):
from dnd.core.dice import Dice, DiceRoll, AttackOutcome, RollType  # ✓
from dnd.core.values import ModifiableValue                         # ✓

# Already defined IN events.py:
class WeaponSlot(str, Enum): ...    # ✓
class AbilityName(str, Enum): ...   # ✓
class SkillName(str, Enum): ...     # ✓
class Damage(BaseObject): ...       # ✓
```

Therefore, the entire hierarchy can be implemented in `events.py`:

```python
# All in dnd/core/events.py - NO circular imports

class DiceRollResultEvent(Event):
    """Base class - uses Event, RollType, DiceRoll (all available)"""
    ...

class D20RollResultEvent(DiceRollResultEvent):
    """D20 subclass - uses ModifiableValue, AbilityName, SkillName (all available)"""
    ...

class DamageRollResultEvent(DiceRollResultEvent):
    """Damage subclass - uses WeaponSlot, AttackOutcome, Damage, DiceRoll (all available)"""
    ...
```

#### Anti-Patterns to NEVER Use

**❌ WRONG: Late import to "avoid" circular dependency**

```python
# In events.py - NEVER DO THIS
class SomeEvent(Event):
    def some_method(self):
        from dnd.entity import Entity  # ← LATE IMPORT = DESIGN SMELL
        entity = Entity.get(self.source_entity_uuid)
```

If you need Entity in events.py, the method is in the wrong place. Move it to Entity or pass data as parameters.

**❌ WRONG: Import inside function body**

```python
# NEVER - this hides the circular dependency, doesn't fix it
def process_event(event):
    from dnd.core.events import SomeEvent  # Already imported at top? Redundant late import
```

**✓ CORRECT: Pass data as parameters**

```python
# Events carry data, consumers (Entity, Actions) do lookups
class D20RollResultEvent(DiceRollResultEvent):
    source_entity_uuid: UUID  # Just the UUID
    # Consumer code in entity.py or actions.py does: Entity.get(event.source_entity_uuid)
```

#### Existing Late Import Violations (Tech Debt)

These exist in the codebase and should be cleaned up:

| File | Line | Import | Issue |
|------|------|--------|-------|
| `entity.py` | 1128 | `from dnd.core.events import EventPhase` | Redundant - already imported at line 13 |
| `actions.py` | 1940 | `from dnd.core.events import ForcedMovementEvent` | Should be at top with other event imports |
| `conditions.py` | 1046 | `from dnd.core.events import TakeDamageEvent` | Should be at top |
| `conditions.py` | 1073 | `from dnd.core.events import SavingThrowEvent` | Should be at top |

None of these are true circular dependency issues - just lazy coding. Fix by moving to top-level imports.

#### Implementation Checklist

When implementing the unified hierarchy:

- [ ] All new classes go in `dnd/core/events.py`
- [ ] No new imports needed in events.py (all types already available)
- [ ] Update `EventType` enum in events.py
- [ ] Consumers (actions.py, fighter.py, etc.) update their imports to use new names
- [ ] Run `python -c "from dnd.core.events import *"` to verify no import errors
- [ ] Run `pyright` to catch any type issues

---

## 9. Architectural Issues Summary

### 9.1 Semantic Mismatch (AttackOutcome for all rolls)

**Problem:** `determine_attack_outcome()` returns `AttackOutcome` for saves and checks, not just attacks.

**Impact:**
- A successful save is `AttackOutcome.HIT` - confusing in logs and code
- Attack-specific concepts (`CRIT_MISS`, `AUTOHIT`) leak into non-attack contexts
- Code like `outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]` is hard to understand

**Proposed Fix:** Separate outcome types (see Section 10).

### 9.2 BG3 vs 5e RAW Nat 1/20 Behavior

**Current (BG3-style):**
- Nat 1 = auto-fail for ALL d20 rolls
- Nat 20 = auto-success for ALL d20 rolls

**5e RAW:**
- Nat 1/20 only have special meaning for **attack rolls**
- Saves/checks: just add bonus, compare to DC

**Impact:**
- Tests expecting guaranteed save outcomes are 5% flaky
- Must use extreme bonuses (+18 to guarantee pass on nat 1)

**Proposed Fix:** Configuration flag for rule variant.

### 9.3 Coupling Analysis

| Component | Coupled To | Issue |
|-----------|------------|-------|
| `determine_attack_outcome()` | All d20 rolls | Single function handles attacks, saves, checks |
| `AttackOutcome.CRIT` | Damage dice doubling | Tight coupling via `attack_outcome` field |
| `Dice.roll` | `random.randint()` | No seam for testing/interception |
| Combat log generation | `AttackOutcome` names | Logs show "HIT" for saves |

---

## 10. Desiderata for Future Refactoring

### 10.1 Semantic Clarity

**Goal:** Outcome types should match roll context.

```python
# Proposed separate outcome types
class AttackOutcome(str, Enum):
    HIT = "Hit"
    MISS = "Miss"
    CRIT = "Crit"
    CRIT_MISS = "Crit Miss"  # Nat 1 auto-miss

class SaveOutcome(str, Enum):
    SUCCESS = "Success"
    FAILURE = "Failure"
    # No crits for saves in 5e RAW

class CheckOutcome(str, Enum):
    SUCCESS = "Success"
    FAILURE = "Failure"
    # No crits for checks in 5e RAW

# Separate resolution functions
def determine_attack_outcome(roll, ac, crit_threshold=20) -> AttackOutcome:
    """Nat 1 = CRIT_MISS, Nat 20+ = CRIT"""

def determine_save_outcome(roll, dc, nat1_auto_fail=False) -> SaveOutcome:
    """Optional BG3-style nat 1 auto-fail"""

def determine_check_outcome(roll, dc, nat1_auto_fail=False) -> CheckOutcome:
    """Optional BG3-style nat 1 auto-fail"""
```

### 10.2 Configurable Rule Variants

**Goal:** Support both 5e RAW and BG3-style nat 1/20.

```python
# Configuration-based approach
class D20Rules(BaseModel):
    nat1_auto_fail: bool = False
    nat20_auto_success: bool = False
    crit_threshold: int = 20
    crit_enabled: bool = True

# Presets
ATTACK_RULES_5E = D20Rules(nat1_auto_fail=True, nat20_auto_success=True, crit_enabled=True)
SAVE_RULES_5E = D20Rules()  # No auto-fail/success
SAVE_RULES_BG3 = D20Rules(nat1_auto_fail=True, nat20_auto_success=True)

# Can be set per-game or per-roll
```

### 10.3 Combat Log Compatibility

Any refactoring must preserve:
- `CombatLogEntry` generation at COMPLETION
- `DiceRollDisplay` serialization format
- Three verbosity levels with markdown
- `ModifiableValue.get_breakdown()` modifier extraction

### 10.4 Event Handler Compatibility

Existing handlers must continue working:
- `DamageRolledEvent` with `original_rolls`/`final_rolls` pattern
- `SavingThrowEvent` with `dice_roll`/`result` replacement
- GWF processor checks `event.weapon_slot`, `event.attack_outcome`
- Indomitable processor checks `event.result is False`

### 10.5 Open Questions

1. **Should crits exist for saves?** Some homebrew/variant rules have "natural 20 on save = no damage". Support this?

2. **How to handle Reliable Talent?** (Rogues treat d20 rolls of 9 or lower as 10). Event interception? Modifier?

3. **Portent (Divination Wizard)**: Requires storing d20 results at dawn, using them for any creature's roll. This is a significant architectural challenge.

4. **Luck Points (Lucky feat)**: Reroll any d20, keep either result. Requires post-roll interception.

5. **Halfling Lucky**: Reroll nat 1 on d20, must use new result. Similar to Indomitable pattern but for any roll.

---

## 11. Related Files Reference

| Component | File | Key Lines |
|-----------|------|-----------|
| **Core Dice Classes** | | |
| Dice class | `dnd/core/dice.py` | 120-341 |
| DiceRoll class | `dnd/core/dice.py` | 21-118 |
| AttackOutcome enum | `dnd/core/dice.py` | 9-13 |
| RollType enum | `dnd/core/dice.py` | 15-19 |
| Dice._roll() | `dnd/core/dice.py` | 286-307 |
| Dice.roll property | `dnd/core/dice.py` | 308-341 |
| **Outcome Determination** | | |
| determine_attack_outcome() | `dnd/entity.py` | 51-93 |
| get_natural_roll() | `dnd/entity.py` | 32-48 |
| Entity.roll_d20() | `dnd/entity.py` | 1048-1059 |
| Entity.saving_throw() | `dnd/entity.py` | 1122-1180 |
| Entity.skill_check() | `dnd/entity.py` | 1182-1196 |
| **Events** | | |
| DamageRolledEvent | `dnd/core/events.py` | 1160-1199 |
| SavingThrowEvent | `dnd/core/events.py` | 734-845 |
| SkillCheckEvent | `dnd/core/events.py` | 847-899 |
| TakeDamageEvent | `dnd/core/events.py` | 1205-1241 |
| Damage class | `dnd/core/events.py` | 1136-1153 |
| **Combat Log** | | |
| CombatLogEntry | `dnd/core/combat_log.py` | 257-310 |
| DiceRollDisplay | `dnd/core/combat_log.py` | 47-66 |
| md_d20_roll() | `dnd/core/combat_log.py` | 461-475 |
| md_breakdown() | `dnd/core/combat_log.py` | 478-488 |
| format_attack_verbose() | `dnd/core/combat_log.py` | 515-559 |
| **Dice Manipulation** | | |
| GWF processor | `dnd/classes/fighter.py` | 300-364 |
| Indomitable processor | `dnd/classes/fighter.py` | 1456-1508 |
| create_modified_dice_roll() | `dnd/classes/fighter.py` | 283-298 |
| dice_processor_utils | `dnd/classes/dice_processor_utils.py` | 1-100 |
| **Actions** | | |
| Attack.attack_consequences() | `dnd/actions.py` | 687-879 |
| Attack damage roll loop | `dnd/actions.py` | 806-837 |
| Shove contest roll | `dnd/actions.py` | ~1970 |
| **Health/Damage** | | |
| Health.take_damage() | `dnd/blocks/health.py` | 350-378 |
| Health.damage_multiplier() | `dnd/blocks/health.py` | 340-348 |
| **Test Utilities** | | |
| force_attack_hit() | `dnd/utils/test_utils.py` | 63-79 |
| force_attack_miss() | `dnd/utils/test_utils.py` | 82-98 |
| force_attack_crit() | `dnd/utils/test_utils.py` | 101-118 |
| remove_attack_modifier() | `dnd/utils/test_utils.py` | 121-129 |
| **Modifiable Values** | | |
| ModifiableValue.get_breakdown() | `dnd/core/values.py` | 2155-2185 |
| ModifiableValue class | `dnd/core/values.py` | various |

---

## Appendix A: Dice Processor Utilities

The `dnd/classes/dice_processor_utils.py` module provides reusable roll modification functions:

**Deterministic (for testing/special abilities):**

```python
# dnd/classes/dice_processor_utils.py:25-61
maximize_all(roll, dice_size)      # All max: [6,6,6] for d6s
minimize_all(roll)                  # All 1s
set_all_to(roll, value)            # All same value
substitute_value(roll, from, to)   # Replace specific value
floor_results(roll, minimum)        # No result below min (Elemental Adept)
ceiling_results(roll, maximum)      # No result above max
```

**Stochastic (random element):**

```python
# dnd/classes/dice_processor_utils.py:68-99
reroll_below_and_substitute(roll, threshold, dice_size)  # GWF pattern
reroll_below_keep_best(roll, threshold, dice_size)       # Halfling Lucky
reroll_ones_once(roll, dice_size)                        # Savage Attacker
```

**Core utility (in fighter.py):**

```python
# dnd/classes/fighter.py:283-298
def create_modified_dice_roll(original: DiceRoll, new_results: List[int]) -> DiceRoll:
    """Create new DiceRoll with different results but same metadata."""
    new_total = sum(new_results) + original.bonus
    return DiceRoll(
        dice_uuid=original.dice_uuid,
        roll_type=original.roll_type,
        results=new_results,
        total=new_total,
        bonus=original.bonus,
        advantage_status=original.advantage_status,
        critical_status=original.critical_status,
        auto_hit_status=original.auto_hit_status,
        source_entity_uuid=original.source_entity_uuid,
        target_entity_uuid=original.target_entity_uuid,
        attack_outcome=original.attack_outcome
    )
```

---

## Appendix B: Test Flakiness Patterns

### Guaranteed Fail Pattern

**Problem:** Test expects target to always fail save, but nat 20 can succeed.

```python
# FLAKY: Target has WIS -5 vs DC 15
# Expected: Always fail (max roll = 20-5=15, needs >15)
# Actual: Nat 20 gives exactly 15 = DC, which ties (succeeds in current impl!)
```

**Fix:** Increase DC so nat 20 + bonus < DC:

```python
# FIXED: Target has WIS -5 vs DC 16
# Now: max roll = 20-5=15 < 16, always fails
```

### Guaranteed Success Pattern

**Problem:** Test expects target to always pass save, but nat 1 auto-fails.

```python
# FLAKY: Target has +17 CON save vs DC 15
# Expected: Always pass (1+17=18 > 15)
# Actual: Nat 1 auto-fails in BG3-style!
```

**Fix:** Increase bonus so even BG3-style works, or adjust DC:

```python
# Current workaround: +100 bonus or accept 5% flakiness
# Future: Configuration flag to disable nat 1 auto-fail for saves
```

---

## Appendix C: Migration Path

If refactoring the outcome system:

1. **Phase 1:** Add `SaveOutcome`/`CheckOutcome` types alongside `AttackOutcome`
2. **Phase 2:** Create `determine_save_outcome()` and `determine_check_outcome()`
3. **Phase 3:** Update `Entity.saving_throw()` and `Entity.skill_check()` to use new functions
4. **Phase 4:** Add `nat1_auto_fail` configuration option for BG3-style house rules
5. **Phase 5:** Update combat log generation for new outcome types
6. **Phase 6:** Deprecate `AttackOutcome` usage for non-attack rolls
