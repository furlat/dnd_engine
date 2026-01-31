# Sorcerer Spell Analysis for D&D Engine

**Last Updated:** January 2026

## Overview

This document analyzes all **120 sorcerer spells** from D&D 5e SRD for implementation difficulty in the D&D Engine. It reflects the current state of the engine after significant development of the AoE system, concentration mechanics, and multi-target spells.

### Spell Count by Level

| Level | Count |
|-------|-------|
| Cantrips | 14 |
| Level 1 | 17 |
| Level 2 | 21 |
| Level 3 | 20 |
| Level 4 | 10 |
| Level 5 | 11 |
| Level 6 | 9 |
| Level 7 | 8 |
| Level 8 | 5 |
| Level 9 | 5 |
| **Total** | **120** |

### Currently Implemented Spells (12)

| Spell | Level | School | Type | Notes |
|-------|-------|--------|------|-------|
| Fire Bolt | 0 | Evocation | Attack | Cantrip scaling ✓ |
| Sacred Flame | 0 | Evocation | DEX Save | Cantrip scaling ✓ |
| Magic Missile | 1 | Evocation | MULTI_ENTITY | Upcasting, multi-target ✓ |
| Mage Armor | 1 | Abjuration | Buff | AC calculation ✓ |
| Burning Hands | 1 | Evocation | Cone AoE | 15ft cone, DEX save ✓ |
| Thunderwave | 1 | Evocation | Cube AoE + Push | 15ft cube, CON save, push ✓ |
| Hold Person | 2 | Enchantment | WIS Save + Conc | Paralyzed, repeat saves ✓ |
| Shatter | 2 | Evocation | Sphere AoE | 10ft sphere, CON save ✓ |
| Call Lightning | 3 | Conjuration | Conc + Repeatable | Grants strike action ✓ |
| Fireball | 3 | Evocation | Sphere AoE | 20ft sphere, DEX save ✓ |
| Lightning Bolt | 3 | Evocation | Line AoE | 100ft×5ft line, DEX save ✓ |

*Note: Sacred Flame is primarily a Cleric spell but is implemented. Call Lightning is Druid.*

---

## Implementation Patterns Catalog

These patterns document the tricks and techniques already used in the codebase. Recognizing which pattern a spell uses determines its difficulty rating.

### Pattern 1: Single-Target Attack Spell
**Used by:** Fire Bolt
**Effort:** TRIVIAL for new spells using this pattern

```
1. Get spell_attack_bonus from caster
2. Cross-propagate with target AC via set_from_target()
3. roll_d20() → determine_attack_outcome()
4. Apply damage on hit (with crit handling)
```

### Pattern 2: Single-Target Save Spell
**Used by:** Sacred Flame
**Effort:** TRIVIAL for new spells using this pattern

```
1. Get DC from caster.spell_save_dc()
2. Target makes saving_throw()
3. Apply full/half/no damage based on success
```

### Pattern 3: AoE Save Spell (Convolution)
**Used by:** Fireball, Lightning Bolt, Burning Hands, Thunderwave, Shatter
**Effort:** EASY - just clone and change shape/damage/save

```
1. target_type = POSITION_AOE
2. aoe_shape = Sphere/Cone/Line/Cube with parameters
3. Convolution loop calls _apply() per affected entity
4. Each target makes save → full/half damage
```
**Key insight:** FOV from explosion center blocks entities behind walls.

### Pattern 4: Multi-Target Explicit Selection
**Used by:** Magic Missile
**Effort:** EASY for similar spells

```
1. target_type = MULTI_ENTITY
2. Override get_all_targets() to handle dart/projectile distribution
3. Convolution loop applies per-projectile
```

### Pattern 5: Buff Condition (Concentration)
**Used by:** Mage Armor, Hold Person, Call Lightning
**Effort:** EASY once condition is written

```
1. Apply spell-effect condition to target
2. Apply Concentrating to caster (if concentration)
3. Link via external_conditions for auto-cleanup
4. Optional: repeat saves via EventHandler on TURN_END
```

### Pattern 6: Granted Action
**Used by:** Call Lightning (grants CallLightningStrike action)
**Effort:** MEDIUM - requires new action class

```
1. Concentration spell applies condition to caster
2. Condition's _apply() registers new action template
3. Action available each turn while concentrating
4. Cleanup: unregister action when concentration breaks
```

### Pattern 7: Forced Movement (Push/Pull)
**Used by:** Thunderwave
**Effort:** EASY - pattern is established

```
1. On failed save, calculate push direction (away from caster)
2. Move target tile by tile checking walkable
3. Use FORCED_MOVEMENT event type (no opportunity attacks)
```

### Pattern 8: Spatial Event Handlers (Zone/Terrain Effects)
**Could enable:** Wall of Fire, Cloudkill, Web, Fog Cloud
**Effort:** MEDIUM - infrastructure exists but no spell uses it yet

```
1. Create invisible "effect" or apply tile conditions at positions
2. Register EventHandler for SPATIAL_ENTITY_ENTERED
3. When entity enters affected tiles → trigger effect (damage/condition)
4. Cleanup: remove handlers when spell ends
```
**Key insight:** SPATIAL_ENTITY_ENTERED events already fire via GridMap - "terrain" spells are just event handlers!

### Pattern 9: HP-Threshold Effect
**Would enable:** Power Word Kill/Stun, Sleep, Color Spray
**Effort:** EASY for threshold check, MEDIUM for HP-pool

```
For threshold: Check target.get_hp() against threshold → instant effect
For HP-pool (Sleep): Subtract HP from pool, apply condition to each target
```

### Pattern 10: Reaction Spell
**Used by:** (Not yet, but ready for Shield, Counterspell)
**Effort:** EASY - uses existing EventHandler pattern (same as Protection fighting style)

**Key insight:** Reaction spells use the EXACT same pattern as opportunity attacks and Protection fighting style. NO new trigger system needed!

```
1. EventHandler listens for trigger event (ATTACK at EXECUTION phase)
2. Check conditions (target is me, have reaction, have spell slot)
3. Modify event (add AC modifier, add disadvantage, or cancel spell)
4. Consume reaction + spell slot
5. Apply duration condition if needed (Shield: "until start of next turn")
```

**Example - Shield (same pattern as Protection):**
- Protection: listens for ATTACK at EXECUTION, adds disadvantage to attack_bonus
- Shield: listens for ATTACK at EXECUTION, adds +5 to AC

Both `attack_bonus` and `ac` are attached to the ATTACK event at EXECUTION phase.

---

## Systems Status

| System | Status | Spells Enabled |
|--------|--------|----------------|
| **AoE Shapes (Sphere)** | ✅ COMPLETE | Fireball, Shatter, Circle of Death, Sunburst |
| **AoE Shapes (Cone)** | ✅ COMPLETE | Burning Hands, Cone of Cold, Fear |
| **AoE Shapes (Line)** | ✅ COMPLETE | Lightning Bolt, Sunbeam |
| **AoE Shapes (Cube)** | ✅ COMPLETE | Thunderwave, Hypnotic Pattern, Slow |
| **Multi-Entity Targeting** | ✅ COMPLETE | Magic Missile, Scorching Ray |
| **Concentration** | ✅ COMPLETE | Hold Person, Call Lightning, all conc. spells |
| **Cantrip Scaling** | ✅ COMPLETE | All cantrips |
| **Upcasting** | ✅ COMPLETE | All leveled spells |
| **Forced Movement** | ✅ COMPLETE | Thunderwave, Gust of Wind |
| **Spatial Events** | ✅ EXISTS (unused) | Infrastructure for zone spells |
| **Dead Entity Filter** | ✅ COMPLETE | AoE spells skip dead entities |
| **Zone/Terrain Spells** | 🟡 READY | Fog Cloud, Web, Wall of Fire (use Pattern 8) |
| **Reaction Casting** | 🟡 READY | Shield, Counterspell (use Pattern 10 = existing EventHandler) |
| **Simple Teleportation** | 🟡 READY | Misty Step (clone Jump pattern, fixed 30ft range) |
| **Complex Teleportation** | ❌ NOT STARTED | Teleport (accuracy table, familiarity system) |
| **HP-Pool Mechanics** | 🟡 READY | Sleep, Color Spray (AoE + sorted targets + HP pool) |
| **Attack Redirection** | ❌ NOT STARTED | Mirror Image |
| **Mind Control/AI** | ❌ OUT OF SCOPE | Dominate spells, Confusion |
| **Summoning** | ❌ OUT OF SCOPE | Animate Objects |
| **Polymorph** | ❌ OUT OF SCOPE | Complete stat replacement |

---

## Difficulty Categories (Updated)

| Category | Definition | Implementation Effort |
|----------|------------|----------------------|
| **DONE** | Already implemented | N/A |
| **TRIVIAL** | Clone existing spell, change parameters only | < 30 min |
| **EASY** | Uses established pattern with minor additions | 30 min - 2 hours |
| **MEDIUM** | New condition or moderate new code | 2-6 hours |
| **HARD** | New subsystem or significant architecture | 1-2 days |
| **VERY HARD** | Major new architecture (summoning, polymorph) | 1+ weeks |
| **BLOCKED** | No mechanical combat effect or requires GM adjudication | N/A |

---

## Cantrips (14 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Acid Splash** | Conjuration | DEX Save | 1d6 acid, 2 targets within 5ft | EASY | Pattern 2 + 2-target variant |
| **Chill Touch** | Necromancy | Attack | 1d8 necrotic, prevents healing | MEDIUM | Pattern 1 + new NoHealing condition |
| **Dancing Lights** | Evocation | Utility | Creates lights | BLOCKED | No combat effect |
| **Fire Bolt** | Evocation | Attack | 1d10 fire | **DONE** | Pattern 1 |
| **Light** | Evocation | Utility | Object sheds light | BLOCKED | No combat effect |
| **Mage Hand** | Conjuration | Utility | Spectral hand | BLOCKED | No combat effect |
| **Mending** | Transmutation | Utility | Repair objects | BLOCKED | No combat effect |
| **Message** | Transmutation | Utility | Whispered communication | BLOCKED | No combat effect |
| **Minor Illusion** | Illusion | Utility | Create sound/image | BLOCKED | No combat effect |
| **Poison Spray** | Conjuration | CON Save | 1d12 poison | TRIVIAL | Clone Sacred Flame |
| **Prestidigitation** | Transmutation | Utility | Minor tricks | BLOCKED | No combat effect |
| **Ray of Frost** | Evocation | Attack | 1d8 cold, -10 speed | EASY | Pattern 1 + speed condition |
| **Shocking Grasp** | Evocation | Melee Attack | 1d8 lightning, no reactions | MEDIUM | Melee spell attack pattern |
| **True Strike** | Divination | Buff | Advantage on next attack | MEDIUM | Delayed buff condition |

### Cantrip Summary
- **DONE**: 1 (Fire Bolt)
- **TRIVIAL**: 1 (Poison Spray)
- **EASY**: 2 (Acid Splash, Ray of Frost)
- **MEDIUM**: 3 (Chill Touch, Shocking Grasp, True Strike)
- **BLOCKED**: 7 (utility cantrips)

---

## Level 1 Spells (17 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Burning Hands** | Evocation | Cone AoE | 3d6 fire, 15ft cone | **DONE** | Pattern 3 |
| **Charm Person** | Enchantment | WIS Save | Charmed condition | EASY | Pattern 5, condition exists |
| **Color Spray** | Illusion | HP-pool | Blinds by HP pool, cone | EASY | HP-pool + AoE (Pattern 9 + 3) |
| **Comprehend Languages** | Divination | Utility | Understand languages | BLOCKED | No combat effect |
| **Detect Magic** | Divination | Utility | Sense magic | BLOCKED | No combat effect |
| **Disguise Self** | Illusion | Utility | Change appearance | BLOCKED | No combat effect |
| **Expeditious Retreat** | Transmutation | Buff | Bonus action Dash each turn | EASY | Pattern 6, Dash exists |
| **False Life** | Necromancy | Buff | 1d4+4 temp HP | EASY | Temp HP implemented |
| **Feather Fall** | Transmutation | Reaction | Slow falling | BLOCKED | Requires Z-axis & falling damage |
| **Fog Cloud** | Conjuration | Zone | 20ft sphere obscured | MEDIUM | Pattern 8 (spatial events) |
| **Jump** | Transmutation | Buff | Triple jump distance | EASY | Jump action exists |
| **Mage Armor** | Abjuration | Buff | AC = 13 + DEX | **DONE** | Pattern 5 |
| **Magic Missile** | Evocation | Auto-hit | 3× 1d4+1 force | **DONE** | Pattern 4 |
| **Shield** | Abjuration | Reaction | +5 AC | EASY | Pattern 10 (clone Protection) |
| **Silent Image** | Illusion | Utility | Create illusion | BLOCKED | No combat effect |
| **Sleep** | Enchantment | HP-pool | Unconscious by HP | EASY | AoE + sorted targets + HP pool (Pattern 9 + 3) |
| **Thunderwave** | Evocation | Cube AoE | 2d8 thunder, push | **DONE** | Pattern 3 + 7 |

### Level 1 Summary
- **DONE**: 4 (Burning Hands, Mage Armor, Magic Missile, Thunderwave)
- **EASY**: 7 (Charm Person, Color Spray, Expeditious Retreat, False Life, Jump, Shield, Sleep)
- **MEDIUM**: 1 (Fog Cloud)
- **BLOCKED**: 5 (utility spells + Feather Fall)

---

## Level 2 Spells (21 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Alter Self** | Transmutation | Buff | Aquatic/Weapons/Appearance | MEDIUM | Natural Weapons option |
| **Blindness/Deafness** | Necromancy | CON Save | Blinded or Deafened | TRIVIAL | Conditions exist |
| **Blur** | Illusion | Buff | Disadvantage on attacks vs you | EASY | to_target modifier |
| **Darkness** | Evocation | Zone | 15ft magical darkness | MEDIUM | Pattern 8 + light blocking |
| **Darkvision** | Transmutation | Buff | 60ft darkvision | MEDIUM | Vision system extension |
| **Detect Thoughts** | Divination | Utility | Read minds | BLOCKED | No combat effect |
| **Enhance Ability** | Transmutation | Buff | Advantage on ability checks | EASY | Ability check modifier |
| **Enlarge/Reduce** | Transmutation | Buff | Size change, ±1d4 damage | MEDIUM | Damage modifier |
| **Gust of Wind** | Evocation | Line | 60ft line, push 15ft | EASY | Pattern 3 + 7 |
| **Hold Person** | Enchantment | WIS Save | Paralyzed | **DONE** | Pattern 5 |
| **Invisibility** | Illusion | Buff | Invisible, ends on attack | EASY | Invisible condition exists |
| **Knock** | Transmutation | Utility | Unlock objects | BLOCKED | No combat effect |
| **Levitate** | Transmutation | Control | Lift creature 20ft | MEDIUM | Vertical position, restrained |
| **Mirror Image** | Illusion | Buff | 3 duplicates absorb attacks | HARD | Attack redirection |
| **Misty Step** | Conjuration | Teleport | Bonus action 30ft teleport | EASY | Clone Jump pattern, fixed 30ft range |
| **Scorching Ray** | Evocation | Multi-attack | 3× 2d6 fire | EASY | Pattern 4 (multi Fire Bolt) |
| **See Invisibility** | Divination | Buff | See invisible/ethereal | MEDIUM | Vision system |
| **Shatter** | Evocation | Sphere AoE | 3d8 thunder, 10ft sphere | **DONE** | Pattern 3 |
| **Spider Climb** | Transmutation | Buff | Climb speed | BLOCKED | Not combat-relevant |
| **Suggestion** | Enchantment | WIS Save | Compel action | VERY HARD | Mind control/AI |
| **Web** | Conjuration | Zone | 20ft cube, restrained | MEDIUM | Pattern 8 |

### Level 2 Summary
- **DONE**: 2 (Hold Person, Shatter)
- **TRIVIAL**: 1 (Blindness/Deafness)
- **EASY**: 6 (Blur, Enhance Ability, Gust of Wind, Invisibility, Misty Step, Scorching Ray)
- **MEDIUM**: 7 (Alter Self, Darkness, Darkvision, Enlarge/Reduce, Levitate, See Invisibility, Web)
- **HARD**: 1 (Mirror Image)
- **VERY HARD**: 1 (Suggestion)
- **BLOCKED**: 3 (utility spells)

---

## Level 3 Spells (20 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Blink** | Transmutation | Buff | 50% vanish to Ethereal | HARD | Untargetable state |
| **Clairvoyance** | Divination | Utility | Remote sensor | BLOCKED | No combat effect |
| **Counterspell** | Abjuration | Reaction | Cancel spell | MEDIUM | Pattern 10 on CAST_SPELL event |
| **Daylight** | Evocation | Light | 60ft bright light | BLOCKED | Light not modeled |
| **Dispel Magic** | Abjuration | Utility | End spells on target | MEDIUM | Condition removal |
| **Fear** | Illusion | Cone AoE | Frightened + forced Dash | EASY | Pattern 3 + conditions exist |
| **Fireball** | Evocation | Sphere AoE | 8d6 fire, 20ft | **DONE** | Pattern 3 |
| **Fly** | Transmutation | Buff | 60ft fly speed | MEDIUM | Flying movement mode |
| **Gaseous Form** | Transmutation | Transform | 10ft fly, resist, can't attack | HARD | Major stat transformation |
| **Haste** | Transmutation | Buff | Double speed, +2 AC, extra action | HARD | Complex multi-buff + lethargy |
| **Hypnotic Pattern** | Illusion | Cube AoE | Charmed + Incapacitated | EASY | Pattern 3, conditions exist |
| **Lightning Bolt** | Evocation | Line AoE | 8d6 lightning, 100ft | **DONE** | Pattern 3 |
| **Major Image** | Illusion | Utility | Detailed illusion | BLOCKED | No combat effect |
| **Protection from Energy** | Abjuration | Buff | Resistance to one type | TRIVIAL | Resistance exists |
| **Sleet Storm** | Conjuration | Zone | 40ft, obscured, prone, conc. break | MEDIUM | Pattern 8 + multiple effects |
| **Slow** | Transmutation | Cube AoE | Half speed, -2 AC, limited actions | MEDIUM | Pattern 3 + complex debuff |
| **Stinking Cloud** | Conjuration | Zone | Waste action on CON fail | MEDIUM | Pattern 8 |
| **Tongues** | Divination | Utility | Understand/speak all | BLOCKED | No combat effect |
| **Water Breathing** | Transmutation | Utility | Breathe underwater | BLOCKED | No combat effect |
| **Water Walk** | Transmutation | Utility | Walk on liquids | BLOCKED | No combat effect |

### Level 3 Summary
- **DONE**: 2 (Fireball, Lightning Bolt)
- **TRIVIAL**: 1 (Protection from Energy)
- **EASY**: 2 (Fear, Hypnotic Pattern)
- **MEDIUM**: 6 (Counterspell, Dispel Magic, Fly, Sleet Storm, Slow, Stinking Cloud)
- **HARD**: 3 (Blink, Gaseous Form, Haste)
- **BLOCKED**: 6 (utility spells)

---

## Level 4 Spells (10 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Banishment** | Abjuration | CHA Save | Remove from plane | HARD | Entity removal |
| **Blight** | Necromancy | CON Save | 8d8 necrotic | TRIVIAL | Pattern 2 |
| **Confusion** | Enchantment | WIS Save AoE | Random behavior | VERY HARD | AI behavior control |
| **Dimension Door** | Conjuration | Teleport | 500ft teleport + ally | MEDIUM | Hybrid targeting (position + optional ally), collision handling |
| **Dominate Beast** | Enchantment | WIS Save | Control beast | VERY HARD | Mind control/AI |
| **Greater Invisibility** | Illusion | Buff | Invisible, doesn't break | TRIVIAL | Invisible condition |
| **Ice Storm** | Evocation | Cylinder AoE | 2d8+4d6, difficult terrain | EASY | Pattern 3 (cylinder = tall sphere) |
| **Polymorph** | Transmutation | Transform | Transform into beast | VERY HARD | Complete stat replacement |
| **Stoneskin** | Abjuration | Buff | B/P/S resistance | TRIVIAL | Resistance exists |
| **Wall of Fire** | Evocation | Zone | 60ft wall, 5d8 fire | MEDIUM | Pattern 8 |

### Level 4 Summary
- **TRIVIAL**: 3 (Blight, Greater Invisibility, Stoneskin)
- **EASY**: 1 (Ice Storm)
- **MEDIUM**: 2 (Dimension Door, Wall of Fire)
- **HARD**: 1 (Banishment)
- **VERY HARD**: 3 (Confusion, Dominate Beast, Polymorph)

---

## Level 5 Spells (11 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Animate Objects** | Transmutation | Summon | Animate up to 10 objects | VERY HARD | Summoning system |
| **Cloudkill** | Conjuration | Zone | 20ft moving sphere, 5d8 poison | MEDIUM | Pattern 8 + movement |
| **Cone of Cold** | Evocation | Cone AoE | 8d8 cold, 60ft cone | TRIVIAL | Clone Burning Hands |
| **Creation** | Illusion | Utility | Create objects | BLOCKED | No combat effect |
| **Dominate Person** | Enchantment | WIS Save | Control humanoid | VERY HARD | Mind control/AI |
| **Hold Monster** | Enchantment | WIS Save | Paralyzed, any creature | TRIVIAL | Clone Hold Person |
| **Insect Plague** | Conjuration | Zone | 20ft sphere, 4d10 piercing | MEDIUM | Pattern 8 |
| **Seeming** | Illusion | Utility | Disguise multiple | BLOCKED | No combat effect |
| **Telekinesis** | Transmutation | Control | Move/restrain | MEDIUM | Contested check |
| **Teleportation Circle** | Conjuration | Utility | Portal to circle | BLOCKED | No combat effect |
| **Wall of Stone** | Evocation | Zone | Create stone wall | MEDIUM | Pattern 8 + destructible |

### Level 5 Summary
- **TRIVIAL**: 2 (Cone of Cold, Hold Monster)
- **MEDIUM**: 4 (Cloudkill, Insect Plague, Telekinesis, Wall of Stone)
- **VERY HARD**: 2 (Animate Objects, Dominate Person)
- **BLOCKED**: 3 (utility spells)

---

## Level 6 Spells (9 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Chain Lightning** | Evocation | Multi-target | 10d8, jumps to 3 targets | MEDIUM | Pattern 4 + chaining |
| **Circle of Death** | Necromancy | Sphere AoE | 8d6 necrotic, 60ft sphere | TRIVIAL | Clone Fireball |
| **Disintegrate** | Transmutation | DEX Save | 10d6+40 force | EASY | Pattern 2 + special death |
| **Eyebite** | Necromancy | WIS Save | Asleep/Panicked/Sickened | MEDIUM | Multiple condition options |
| **Globe of Invulnerability** | Abjuration | Buff | Block spells ≤5th | VERY HARD | Spell immunity |
| **Mass Suggestion** | Enchantment | WIS Save | Suggest to 12 | VERY HARD | Mass mind control |
| **Move Earth** | Transmutation | Terrain | Reshape terrain | BLOCKED | No immediate effect |
| **Sunbeam** | Evocation | Line AoE | 6d8 radiant + blind | EASY | Pattern 3 + 6 |
| **True Seeing** | Divination | Buff | Truesight 120ft | MEDIUM | Vision extension |

### Level 6 Summary
- **TRIVIAL**: 1 (Circle of Death)
- **EASY**: 2 (Disintegrate, Sunbeam)
- **MEDIUM**: 3 (Chain Lightning, Eyebite, True Seeing)
- **VERY HARD**: 2 (Globe of Invulnerability, Mass Suggestion)
- **BLOCKED**: 1 (Move Earth)

---

## Level 7 Spells (8 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Delayed Blast Fireball** | Evocation | Sphere AoE | 12d6+ accumulates | MEDIUM | Pattern 3 + delayed |
| **Etherealness** | Transmutation | Transform | Enter Ethereal | VERY HARD | Plane mechanics |
| **Finger of Death** | Necromancy | CON Save | 7d8+30, creates zombie | HARD | Pattern 2 + summon |
| **Fire Storm** | Evocation | Multi-cube | 7d10 fire, 10 cubes | EASY | Pattern 3 × 10 |
| **Plane Shift** | Conjuration | Teleport | Teleport/banish | VERY HARD | Plane mechanics |
| **Prismatic Spray** | Evocation | Cone AoE | Random effects | HARD | Pattern 3 + complex random |
| **Reverse Gravity** | Transmutation | Cylinder | Fall upward | HARD | Positional chaos |
| **Teleport** | Conjuration | Teleport | Long-range + accuracy | HARD | Teleportation system |

### Level 7 Summary
- **EASY**: 1 (Fire Storm)
- **MEDIUM**: 1 (Delayed Blast Fireball)
- **HARD**: 4 (Finger of Death, Prismatic Spray, Reverse Gravity, Teleport)
- **VERY HARD**: 2 (Etherealness, Plane Shift)

---

## Level 8 Spells (5 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Dominate Monster** | Enchantment | WIS Save | Control any creature | VERY HARD | Mind control/AI |
| **Earthquake** | Evocation | Zone | 100ft, prone, fissures | HARD | Massive AoE + terrain |
| **Incendiary Cloud** | Conjuration | Zone | 20ft moving, 10d8 fire | MEDIUM | Pattern 8 + movement |
| **Power Word Stun** | Enchantment | HP-based | Stunned if ≤150 HP | EASY | Pattern 9, Stunned exists |
| **Sunburst** | Evocation | Sphere AoE | 12d6 radiant + blind | TRIVIAL | Clone Fireball |

### Level 8 Summary
- **TRIVIAL**: 1 (Sunburst)
- **EASY**: 1 (Power Word Stun)
- **MEDIUM**: 1 (Incendiary Cloud)
- **HARD**: 1 (Earthquake)
- **VERY HARD**: 1 (Dominate Monster)

---

## Level 9 Spells (5 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Gate** | Conjuration | Portal | Interplanar portal + summon | VERY HARD | Plane mechanics |
| **Meteor Swarm** | Evocation | Multi-sphere | 40d6, 4×40ft spheres | EASY | Pattern 3 × 4 |
| **Power Word Kill** | Enchantment | HP-based | Death if ≤100 HP | EASY | Pattern 9 |
| **Time Stop** | Transmutation | Control | Extra turns | VERY HARD | Turn manipulation |
| **Wish** | Conjuration | Ultimate | Anything | VERY HARD | GM adjudication |

### Level 9 Summary
- **EASY**: 2 (Meteor Swarm, Power Word Kill)
- **VERY HARD**: 3 (Gate, Time Stop, Wish)

---

## Overall Summary by Difficulty

| Difficulty | Count | Percentage |
|------------|-------|------------|
| **DONE** | 11 | 9% |
| **TRIVIAL** | 11 | 9% |
| **EASY** | 25 | 21% |
| **MEDIUM** | 26 | 22% |
| **HARD** | 13 | 11% |
| **VERY HARD** | 17 | 14% |
| **BLOCKED** | 26 | 22% |

**Implementable with existing patterns**: 62 spells (DONE + TRIVIAL + EASY + MEDIUM)
**Require new subsystems**: 30 spells (HARD + VERY HARD)
**Out of scope for combat engine**: 26 spells (BLOCKED)

*Note: Shield moved HARD→EASY, Counterspell moved VERY HARD→MEDIUM, Feather Fall moved HARD→BLOCKED (requires Z-axis/falling damage), Misty Step moved HARD→EASY (clone Jump), Sleep/Color Spray moved MEDIUM→EASY (AoE + HP-pool override), Dimension Door moved HARD→MEDIUM (hybrid targeting)*

### Progress: 11 of 94 combat-relevant spells implemented (12%)
### With existing patterns: 62 of 94 combat-relevant spells implementable (66%)

---

## Implementation Priority

### Tier 0: Already Done (11 spells)
Fire Bolt, Sacred Flame, Magic Missile, Mage Armor, Burning Hands, Thunderwave, Hold Person, Shatter, Fireball, Lightning Bolt, Call Lightning

### Tier 1: Trivial Clones (11 spells, <30 min each)

Direct parameter changes from existing spells:

| Spell | Clone Of | Change |
|-------|----------|--------|
| Poison Spray | Sacred Flame | CON save, poison damage, 1d12 |
| Blindness/Deafness | (condition) | Apply Blinded/Deafened |
| Protection from Energy | (buff) | Single type resistance |
| Blight | Sacred Flame | 8d8, CON, necrotic, L4 |
| Greater Invisibility | (buff) | Invisible without attack break |
| Stoneskin | (buff) | B/P/S resistance |
| Cone of Cold | Burning Hands | 60ft cone, 8d8 cold, DEX |
| Hold Monster | Hold Person | Works on all creatures |
| Circle of Death | Fireball | 60ft sphere, 8d6 necrotic, CON |
| Sunburst | Fireball | 60ft sphere, 12d6 radiant, blind |
| Power Word Kill | (HP check) | Kill if ≤100 HP |

### Tier 2: Easy Extensions (23 spells, 30min-2hr each)

Use established patterns with minor additions:

| Spell | Level | What's Needed |
|-------|-------|---------------|
| Acid Splash | 0 | 2-target cantrip variant |
| Ray of Frost | 0 | Speed reduction condition |
| Charm Person | 1 | Duration timer on Charmed |
| Color Spray | 1 | Cone AoE + HP-pool sorted targets (clone Sleep pattern) |
| Expeditious Retreat | 1 | Granted Dash action |
| False Life | 1 | Temp HP application |
| Jump | 1 | Jump distance modifier |
| Shield | 1 | Reaction +5 AC (Pattern 10, clone Protection) |
| Sleep | 1 | Sphere AoE + HP-pool with sorted targets |
| Blur | 2 | to_target disadvantage |
| Enhance Ability | 2 | Ability check advantage |
| Gust of Wind | 2 | Line + push (Pattern 3+7) |
| Invisibility | 2 | Invisible with break on attack |
| Misty Step | 2 | Clone Jump pattern, fixed 30ft range, bonus action |
| Scorching Ray | 2 | 3× attack rolls |
| Fear | 3 | Cone + Frightened + forced Dash |
| Hypnotic Pattern | 3 | Cube + Charmed + Incap |
| Ice Storm | 4 | Cylinder + difficult terrain |
| Disintegrate | 6 | Single target + special death |
| Sunbeam | 6 | Line + blind + repeatable |
| Fire Storm | 7 | Multiple cubes |
| Power Word Stun | 8 | HP check + Stunned |
| Meteor Swarm | 9 | Multiple spheres |

### Tier 3: Medium Effort (26 spells, 2-6hr each)

New conditions or moderate new code:

| Spell | Level | What's Needed |
|-------|-------|---------------|
| Chill Touch | 0 | NoHealing condition |
| Shocking Grasp | 0 | Melee spell attack + no reactions |
| True Strike | 0 | Delayed advantage buff |
| Fog Cloud | 1 | Spatial event zone |
| Alter Self | 2 | Natural Weapons option |
| Darkness | 2 | Zone + light blocking |
| Darkvision | 2 | Vision extension |
| Enlarge/Reduce | 2 | Size-based damage modifier |
| Levitate | 2 | Vertical movement |
| See Invisibility | 2 | Vision extension |
| Web | 2 | Zone + Restrained on enter |
| Counterspell | 3 | Pattern 10 on CAST_SPELL event |
| Dispel Magic | 3 | Condition removal |
| Fly | 3 | Flying movement mode |
| Sleet Storm | 3 | Zone + multiple effects |
| Slow | 3 | Complex debuff condition |
| Stinking Cloud | 3 | Zone + action waste |
| Dimension Door | 4 | Hybrid targeting (position + optional ally), collision handling |
| Wall of Fire | 4 | Zone + damage on enter |
| Cloudkill | 5 | Moving zone |
| Insect Plague | 5 | Zone + difficult terrain |
| Telekinesis | 5 | Contested check |
| Wall of Stone | 5 | Zone + destructible |
| Chain Lightning | 6 | Multi-target with chaining |
| Eyebite | 6 | Multiple condition options |
| True Seeing | 6 | Vision extension |
| Delayed Blast Fireball | 7 | Delayed trigger |
| Incendiary Cloud | 8 | Moving zone |

### Tier 4: Hard (New Subsystems) (13 spells)

| System | Spells | Notes |
|--------|--------|-------|
| **Teleportation** | Teleport | Accuracy table, familiarity system |
| **Attack Redirection** | Mirror Image | Intercept pattern |
| **Entity Removal** | Banishment | Temporary removal |
| **Complex Transforms** | Gaseous Form, Blink | Untargetable states |
| **Complex Buffs** | Haste | Multi-buff + lethargy |
| **Random Effects** | Prismatic Spray | Complex random table |
| **Terrain Destruction** | Earthquake, Reverse Gravity | Major positional effects |
| **Partial Summon** | Finger of Death | Summon on kill |

*Note: Misty Step moved to EASY (clone Jump pattern), Dimension Door moved to MEDIUM (hybrid targeting is straightforward)*

### Tier 5: Skip (VERY HARD + BLOCKED)

| Category | Spells |
|----------|--------|
| **Mind Control** | Suggestion, Dominate Beast/Person/Monster, Confusion, Mass Suggestion |
| **Summoning** | Animate Objects |
| **Transformation** | Polymorph |
| **Plane Mechanics** | Etherealness, Plane Shift, Gate |
| **Meta/Ultimate** | Globe of Invulnerability, Time Stop, Wish |
| **Utility (BLOCKED)** | 25 spells with no combat effect |

---

## Recommended Next Steps

### Immediate: Tier 1 Trivial Clones
Implement all 11 trivial spells to quickly expand the spell list. Each takes <30 minutes and demonstrates the flexibility of existing patterns.

### Short-term: Tier 2 Easy Spells
Focus on:
1. **Scorching Ray** - Multi-attack pattern
2. **Fear, Hypnotic Pattern** - Showcase AoE + conditions
3. **Ice Storm, Meteor Swarm, Fire Storm** - Multi-AoE patterns
4. **Ray of Frost** - Speed reduction cantrip

### Medium-term: Zone Spells (Pattern 8)
Build the spatial event handler pattern with:
1. **Fog Cloud** - Simplest zone (just obscured)
2. **Web** - Zone + condition on enter
3. **Wall of Fire** - Zone + damage on enter/turn
4. **Cloudkill** - Moving zone

### Long-term: New Subsystems
1. **Teleportation** - Misty Step is now EASY (clone Jump), Teleport still needs accuracy table
2. **HP-Pool Mechanics** - Sleep/Color Spray are now EASY (AoE + sorted targets + HP pool override)

### Quick Win: Reaction Spells (Pattern 10)
**Shield** and **Counterspell** use the exact same EventHandler pattern as Protection fighting style and opportunity attacks. No new architecture needed!
- Shield: Clone Protection, add +5 AC instead of disadvantage
- Counterspell: Same pattern on CAST_SPELL event, call `event.cancel()`

---

## Conclusion

With the AoE system complete and the convolution pattern established, the spell implementation landscape has dramatically improved. Of 120 sorcerer spells:

- **11 spells (9%)** already implemented
- **36 more spells (30%)** use existing patterns (TRIVIAL + EASY)
- **26 spells (22%)** need moderate new work (MEDIUM)
- **13 spells (11%)** need new subsystems (HARD)
- **17 spells (14%)** need major architecture (VERY HARD)
- **26 spells (22%)** have no combat mechanics (BLOCKED)

**Key insight:** The AoE system unlocked the largest batch of damage spells. The next high-value system is **Zone/Terrain spells via Pattern 8**, which uses existing spatial events infrastructure.

**Reaction spells (Shield, Counterspell)** were previously marked HARD/VERY HARD but actually use the **same EventHandler pattern as Protection fighting style**. No new trigger system needed!

**Teleportation reassessed:** Misty Step is now EASY (clone Jump pattern with fixed 30ft range). Dimension Door is MEDIUM (hybrid targeting + collision handling). Only Teleport remains HARD due to its accuracy/familiarity system.

**HP-Pool spells reassessed:** Sleep and Color Spray are now EASY. The pattern is simply AoE targeting + sorted-by-HP targets + HP pool exhaustion. No new subsystem needed.

**Total implementable:** 73 spells (62%) are TRIVIAL/EASY/MEDIUM with current architecture.
