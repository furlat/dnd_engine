# Combat.md - Implementation Notes

## Status: SUBSTANTIAL COVERAGE

Combat is the most feature-rich area of our engine. Core attack/damage loop is solid. Missing turn structure and some tactical options.

---

## Fully Implemented

### Attack System
- **Attack rolls**: d20 + ability mod + proficiency vs AC
- **Critical hits**: Natural 20 always hits, doubles damage dice (in `Dice._roll()`)
- **Critical miss**: Natural 1 always misses
- **Auto-hit/Auto-miss**: From conditions (e.g., Charmed can't attack charmer)
- **Auto-crit**: From conditions (e.g., Paralyzed gives melee auto-crits within 5ft)
- **Attack outcome determination**: `determine_attack_outcome()` in `entity.py:40-64`

### Damage System
- **All 13 damage types**: Acid, Bludgeoning, Cold, Fire, Force, Lightning, Necrotic, Piercing, Poison, Psychic, Radiant, Slashing, Thunder (`modifiers.py:40-53`)
- **Resistance**: Half damage
- **Vulnerability**: Double damage
- **Immunity**: No damage
- **Correct order**: Modifiers first, then resistance/vulnerability (`health.py:367`)
- **Damage reduction**: Flat subtraction after multiplier

### Hit Points
- **Max HP**: From hit dice + CON modifier per level
- **Current HP**: Tracked via `damage_taken` field
- **Temporary HP**:
  - Doesn't stack (takes higher value) - correct per SRD
  - Healing doesn't restore temp HP - correct per SRD
  - Absorbed before real HP
  - `health.py:350-398`

### Action Economy (`action_economy.py`)
- **Actions**: 1 by default (ModifiableValue)
- **Bonus Actions**: 1 by default (ModifiableValue)
- **Reactions**: 1 by default (ModifiableValue)
- **Movement**: 30ft by default (ModifiableValue)
- **consume()**: Deduct from resource
- **can_afford()**: Check before action
- **reset_all_costs()**: For new turn

### Actions Implemented
| Action | Implementation | Notes |
|--------|----------------|-------|
| **Attack** | `actions.py:Attack` | Full flow with range/LOS validation |
| **Move** | `actions.py:Move` | Path following, movement cost deduction |
| **Dash** | `conditions.py:Dashing` | Adds movement equal to base speed |
| **Dodge** | `conditions.py:Dodging` | Disadvantage to attackers, advantage on DEX saves |

### Other Combat Features
- **Opportunity attacks**: `reactions.py:opportunity_attack_processor` - triggers when leaving reach
- **Weapon reach**: 5ft for melee, variable for ranged
- **Line of sight**: `validate_line_of_sight()` uses `Senses.entities`
- **Unarmed strikes**: 1 + STR mod bludgeoning damage

---

## Partially Implemented

### Range System
**What works:**
- Basic range validation in `Attack.validate_range()` (`actions.py:230-250`)
- Distinguishes REACH vs RANGE weapon types

**Gaps:**
- No **long range disadvantage**
  - SRD: "Your attack roll has disadvantage when your target is beyond normal range"
  - Our code just blocks attacks beyond normal range for RANGE type
- No **ranged-in-melee disadvantage**
  - SRD: "You have disadvantage on the attack roll if you are within 5 feet of a hostile creature who can see you and who isn't incapacitated"
  - Not checked anywhere

### Creature Size
**What works:**
- Size enum exists: Tiny, Small, Medium, Large, Huge, Gargantuan (`modifiers.py:32-38`)

**Gaps:**
- Size doesn't affect **space occupied**
  - SRD: Medium = 5ft, Large = 10ft, Huge = 15ft, Gargantuan = 20ft+
  - Our entities all occupy 1 tile regardless of size
- No **squeezing** rules (disadvantage, enemies have advantage)

### Prone Condition
**What works:**
- Condition exists with correct attack modifiers (melee advantage, ranged disadvantage)

**Gaps:**
- **Standing up cost** not explicit (SRD: costs half your movement)
- **Crawling** not implemented (SRD: every foot costs 1 extra foot)
- **Drop prone** is free (SRD correct, but we don't have explicit action for it)

---

## Not Implemented

### Turn-Based Combat Structure
| Feature | SRD Description | Priority |
|---------|-----------------|----------|
| Rounds | 6 seconds each, all combatants act | Medium |
| Turns | One per combatant per round | Medium |
| Initiative | DEX check to determine turn order | Low (just a ModifiableValue) |
| Surprise | Stealth vs Passive Perception, can't act first turn | Low |

*Note: Without turn structure, initiative is meaningless. When we add turns, initiative is trivial.*

### Death and Unconsciousness
| Feature | SRD Description | Priority |
|---------|-----------------|----------|
| Death Saving Throws | d20 at start of turn when at 0 HP, 10+ = success, 3 successes = stable, 3 failures = death | Medium |
| Instant Death | If remaining damage after 0 HP >= max HP, instant death | Medium |
| Stabilization | DC 10 Medicine check as action | Low |
| Damage at 0 HP | Causes death save failure (crit = 2 failures) | Medium |

*Note: Unconscious condition exists, but no death spiral mechanics.*

### Missing Standard Actions
| Action | SRD Effect | Implementation Difficulty |
|--------|------------|---------------------------|
| **Disengage** | Movement doesn't provoke OAs this turn | Easy - flag on entity |
| **Help** | Ally gets advantage on next check/attack | Easy - apply advantage modifier |
| **Hide** | Stealth check to become hidden | Medium - needs hidden state tracking |
| **Ready** | Hold action for trigger, use reaction | Hard - needs trigger system |
| **Search** | Perception or Investigation check | Easy - just a skill check |
| **Use an Object** | Interact with item as action | Medium - needs item interaction system |

### Combat Options
| Feature | SRD Description | Implementation Difficulty |
|---------|-----------------|---------------------------|
| **Two-Weapon Fighting** | Bonus action attack with light off-hand, no ability mod to damage | Medium - need to check weapon properties, modify damage calc |
| **Grappling** | Athletics vs Athletics/Acrobatics contest, target gets Grappled | Medium - need contest system |
| **Shoving** | Athletics vs Athletics/Acrobatics contest, prone or push 5ft | Medium - need contest system |

### Cover
| Type | AC/DEX Save Bonus | Implementation Notes |
|------|-------------------|---------------------|
| Half | +2 | Need cover calculation from position/obstacles |
| Three-quarters | +5 | Same |
| Total | Can't be targeted | Need to block targeting entirely |

*Cover requires spatial analysis - checking what's between attacker and target.*

### Terrain and Movement
| Feature | SRD Description | Notes |
|---------|-----------------|-------|
| Difficult terrain | Each foot costs 1 extra foot | Tiles could have `difficult` flag |
| Flying speed | Separate movement pool | ActionEconomy could have `flying_movement` |
| Swimming speed | Separate movement pool | Same |
| Climbing | Usually half speed | Could be modifier on movement cost |

### Advanced Combat (Low Priority)
- **Mounted combat**: Mount has own initiative or shares rider's, movement options
- **Underwater combat**: Disadvantage on most melee, auto-miss ranged beyond normal range

---

## Implementation Priority Suggestions

### High Priority (Affects Balance)
1. **Ranged attack disadvantages**
   - In melee (within 5ft of hostile)
   - At long range
   - These significantly affect ranged vs melee balance

2. **Cover system**
   - Very common tactical element
   - +2/+5 AC is significant

### Medium Priority (Common Mechanics)
3. **Two-weapon fighting**
   - Many builds rely on this
   - Rogue, Ranger, Fighter all use it

4. **Disengage action**
   - Necessary counter to opportunity attacks
   - Without it, ranged characters are stuck

5. **Death saving throws**
   - Core to player character survival
   - Less important for monsters (usually just die at 0)

### Low Priority (Nice to Have)
6. **Grappling/Shoving** - Situational but fun
7. **Difficult terrain** - Map variety
8. **Help action** - Team tactics
9. **Ready action** - Complex trigger system

---

## Code Locations Reference

| Feature | File | Key Functions/Classes |
|---------|------|----------------------|
| Attack action | `actions.py` | `Attack`, `attack_consequences()`, `validate_range()` |
| Move action | `actions.py` | `Move` |
| Attack outcome | `entity.py` | `determine_attack_outcome()` |
| Damage types | `modifiers.py` | `DamageType` enum |
| Resistance system | `modifiers.py` | `ResistanceModifier`, `ResistanceStatus` |
| Health/damage | `health.py` | `Health.take_damage()`, `heal()` |
| Action economy | `action_economy.py` | `ActionEconomy` |
| Opportunity attacks | `reactions.py` | `opportunity_attack_processor()` |
| Conditions | `conditions.py` | `Dashing`, `Dodging`, `Prone`, etc. |
| Creature size | `modifiers.py` | `Size` enum |
