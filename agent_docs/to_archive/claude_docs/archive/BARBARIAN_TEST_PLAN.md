# Barbarian Feature Test Plan

Comprehensive testing plan for all Barbarian class features (SRD).

## Test Status Legend
- ✅ Tested and passing
- ⚠️ Partially tested
- ❌ Not tested
- 🚫 Not implemented

---

## Level 1: Rage

### Test File: `test_barbarian_rage.py`

| Test Case | Status | Description |
|-----------|--------|-------------|
| Rage activation | ✅ | Bonus action, applies Raging condition, consumes rage use |
| STR advantage | ✅ | Advantage on STR saves and Athletics while raging |
| Rage damage bonus | ✅ | +2/+3/+4 damage on melee attacks based on level |
| B/P/S resistance | ✅ | Bludgeoning/piercing/slashing damage halved |
| Non-B/P/S full damage | ✅ | Fire/cold/etc. damage NOT halved |
| KeepRage from attack | ✅ | Attacking applies KeepRage marker |
| KeepRage from damage | ✅ | Taking damage applies KeepRage marker |
| Rage ends no activity | ✅ | Rage ends at turn end without attack/damage |
| Cannot rage in heavy armor | ✅ | Rage action blocked by pre_validate |
| Heavy armor ends rage | ✅ | Equipping heavy armor mid-rage ends it |
| Rage ends unconscious | ❌ | Dropping to 0 HP should end rage |
| Voluntary end rage | 🚫 | Bonus action to end rage early (not implemented) |
| Rage uses per level | ❌ | 2/3/4/5/6/unlimited at different levels |
| Rage damage scaling | ❌ | +2 (L1-8), +3 (L9-15), +4 (L16+) |
| No spellcasting while raging | 🚫 | Not relevant until spells implemented |

---

## Level 1: Unarmored Defense

### Test File: `test_barbarian_rage.py`

| Test Case | Status | Description |
|-----------|--------|-------------|
| CON added to AC | ✅ | AC = 10 + DEX + CON when unarmored |
| Works with shield | ❌ | Shield AC bonus still applies |
| Disabled with armor | ❌ | No CON bonus when wearing any armor |

---

## Level 2: Reckless Attack

### Test File: `test_barbarian_rage.py`

| Test Case | Status | Description |
|-----------|--------|-------------|
| Melee attack advantage | ✅ | Advantage on own melee attacks |
| Attackers have advantage | ✅ | to_target_static gives attackers advantage |
| Free action | ❌ | No action/bonus action cost |
| Duration 1 round | ❌ | Expires at start of next turn |
| Only STR-based attacks | ❌ | Should only affect melee STR attacks (not DEX finesse) |

---

## Level 2: Danger Sense

### Test File: `test_barbarian_rage.py`

| Test Case | Status | Description |
|-----------|--------|-------------|
| DEX save advantage | ✅ | Advantage on DEX saves |
| Disabled when blinded | ⚠️ | Currently static, not contextual |
| Disabled when deafened | ⚠️ | Currently static, not contextual |
| Disabled when incapacitated | ⚠️ | Currently static, not contextual |
| Only visible effects | ⚠️ | Currently static, not contextual |

---

## Level 3: Frenzy (Berserker)

### Test File: `test_barbarian_frenzy.py` (NEW)

| Test Case | Status | Description |
|-----------|--------|-------------|
| Frenzy activation | ❌ | Bonus action, consumes rage use |
| Includes all rage benefits | ❌ | Raging is sub-condition of Frenzied |
| FrenziedStrike available | ❌ | Bonus action melee attack granted |
| FrenziedStrike costs BA | ❌ | Consumes bonus action |
| FrenziedStrike validates target | ❌ | Range, LOS, valid target checks |
| No exhaustion (BG3) | ❌ | Confirm no exhaustion on frenzy end |
| Cannot frenzy in heavy armor | ❌ | Same restriction as rage |
| Frenzy ends like rage | ❌ | Same maintenance rules apply |

---

## Level 5: Extra Attack

### Test File: `test_barbarian_extra_attack.py` (NEW)

| Test Case | Status | Description |
|-----------|--------|-------------|
| Two attacks per Attack action | ❌ | Uses Fighter's ExtraAttackFeature |
| Resource consumption | ❌ | extra_attack resource tracked |
| Works with Frenzy | ❌ | Extra Attack + Frenzied Strike = 3 attacks |

---

## Level 5: Fast Movement

### Test File: `test_barbarian_fast_movement.py` (NEW)

| Test Case | Status | Description |
|-----------|--------|-------------|
| +10 speed unarmored | ❌ | Speed increases by 10ft |
| +10 speed light armor | ❌ | Works with light armor |
| +10 speed medium armor | ❌ | Works with medium armor |
| Disabled heavy armor | ❌ | No bonus in heavy armor |
| Stacks with other speed | ❌ | Adds to base speed correctly |

---

## Level 6: Mindless Rage (Berserker)

### Test File: `test_barbarian_mindless_rage.py` (NEW)

| Test Case | Status | Description |
|-----------|--------|-------------|
| Blocks Charmed while raging | ❌ | Charmed condition canceled |
| Blocks Frightened while raging | ❌ | Frightened condition canceled |
| Works with Frenzy too | ❌ | Checks both Raging and Frenzied |
| No effect when not raging | ❌ | Conditions apply normally outside rage |
| Existing conditions suspended | 🚫 | Not implemented - remove on rage start |

---

## Level 7: Feral Instinct

### Test File: `test_barbarian_feral_instinct.py` (NEW)

| Test Case | Status | Description |
|-----------|--------|-------------|
| Initiative advantage | ❌ | Advantage on initiative rolls |
| Surprise handling | 🚫 | Act normally if rage first (not implemented) |

---

## Level 9/13/17: Brutal Critical

### Test File: `test_brutal_critical.py` (EXISTS - verify)

| Test Case | Status | Description |
|-----------|--------|-------------|
| +1 die at L9 | ❌ | One extra damage die on crit |
| +2 dice at L13 | ❌ | Two extra damage dice on crit |
| +3 dice at L17 | ❌ | Three extra damage dice on crit |
| Only melee attacks | ❌ | Uses crit_extra_dice_melee not general |
| Stacks with crit doubling | ❌ | Extra dice added after normal crit calculation |

---

## Level 10: Intimidating Presence (Berserker)

### Test File: `test_relentless_rage_intimidating.py` (EXISTS - verify)

| Test Case | Status | Description |
|-----------|--------|-------------|
| Costs action | ❌ | Consumes 1 action |
| DC calculation | ❌ | DC = 8 + proficiency + CHA mod |
| Target frightened on fail | ❌ | Frightened condition applied |
| 24h immunity on success | ❌ | IntimidatingPresenceImmunity applied |
| Range 30ft | ❌ | Target must be within 30ft |
| Target must see/hear | ❌ | Requires LOS |
| Duration 1 round | ❌ | Frightened until end of next turn |

---

## Level 11: Relentless Rage

### Test File: `test_relentless_rage_intimidating.py` (EXISTS - verify)

| Test Case | Status | Description |
|-----------|--------|-------------|
| CON save to survive | ❌ | DC 10 CON save when dropping to 0 HP |
| Drop to 1 HP on success | ❌ | Set HP to 1 instead of 0 |
| DC increases by 5 | ❌ | Each use increases DC |
| Only while raging | ❌ | No effect outside rage |
| DC resets on rest | 🚫 | Rest system not implemented |

---

## Level 14: Retaliation (Berserker)

### Test File: `test_barbarian_retaliation.py` (NEW)

| Test Case | Status | Description |
|-----------|--------|-------------|
| Reaction attack when hit | ❌ | Melee attack on damage from adjacent |
| Uses reaction | ❌ | Consumes reaction resource |
| Range 5ft | ❌ | Only triggers from adjacent creatures |
| Requires melee weapon | ❌ | Must have melee weapon equipped |
| No reaction = no trigger | ❌ | Doesn't trigger if reaction used |

---

## Level 15: Persistent Rage

### Test File: `test_barbarian_persistent_rage.py` (NEW)

| Test Case | Status | Description |
|-----------|--------|-------------|
| Rage doesn't end from inactivity | ❌ | Turn end without attack/damage OK |
| Still ends if unconscious | ❌ | Dropping to 0 HP ends rage |
| Still can end voluntarily | 🚫 | Voluntary end not implemented |
| Marker condition checked | ❌ | rage_maintenance_processor checks it |

---

## Level 18: Indomitable Might

### Test File: `test_barbarian_indomitable_might.py` (NEW)

| Test Case | Status | Description |
|-----------|--------|-------------|
| STR check minimum = STR score | ❌ | If total < STR score, use STR score |
| Only Athletics | ❌ | Only STR-based skill checks |
| Doesn't affect saves | ❌ | STR saves not affected |
| Works with low rolls | ❌ | Natural 1 + mods still uses STR score if lower |

---

## Level 20: Primal Champion

### Test File: `test_barbarian_primal_champion.py` (NEW)

| Test Case | Status | Description |
|-----------|--------|-------------|
| +4 STR | ❌ | STR score increases by 4 |
| +4 CON | ❌ | CON score increases by 4 |
| Affects derived stats | ❌ | HP, STR mod, CON mod all update |
| Max 24 | ❌ | Can exceed normal 20 cap |

---

## Integration Tests

### Test File: `test_barbarian_integration.py` (NEW)

| Test Case | Status | Description |
|-----------|--------|-------------|
| Full L1 barbarian combat | ❌ | Rage + attacks + damage resistance |
| Full L5 barbarian combat | ❌ | Extra Attack + Fast Movement |
| Berserker L6 combat | ❌ | Frenzy + Mindless Rage |
| High level barbarian | ❌ | Multiple features interacting |
| Barbarian vs Fighter | ❌ | PvP scenario with both classes |

---

## Test Priority

### High Priority (Core functionality)
1. ❌ Rage ends when unconscious
2. ❌ Frenzy full test suite
3. ❌ Extra Attack integration
4. ❌ Brutal Critical verification
5. ❌ Relentless Rage verification

### Medium Priority (Important features)
6. ❌ Fast Movement
7. ❌ Mindless Rage
8. ❌ Retaliation
9. ❌ Persistent Rage
10. ❌ Intimidating Presence verification

### Lower Priority (Edge cases)
11. ❌ Unarmored Defense with shield
12. ❌ Reckless Attack duration/scope
13. ❌ Danger Sense contextual conditions
14. ❌ Feral Instinct
15. ❌ Indomitable Might
16. ❌ Primal Champion

---

## New Test Files Needed

1. `test_barbarian_frenzy.py` - Frenzy + FrenziedStrike
2. `test_barbarian_extra_attack.py` - Extra Attack integration
3. `test_barbarian_fast_movement.py` - Fast Movement
4. `test_barbarian_mindless_rage.py` - Mindless Rage
5. `test_barbarian_feral_instinct.py` - Feral Instinct
6. `test_barbarian_retaliation.py` - Retaliation
7. `test_barbarian_persistent_rage.py` - Persistent Rage
8. `test_barbarian_indomitable_might.py` - Indomitable Might
9. `test_barbarian_primal_champion.py` - Primal Champion
10. `test_barbarian_integration.py` - Multi-feature scenarios

## Existing Test Files to Verify
1. `test_brutal_critical.py` - Verify covers barbarian use case
2. `test_relentless_rage_intimidating.py` - Verify comprehensive
