# Sorcerer Spell Analysis for D&D Engine

## Overview

This document analyzes all **120 sorcerer spells** from D&D 5e SRD for implementation difficulty in the D&D Engine.

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

### Currently Implemented Sorcerer Spells (4)

| Spell | Type | Status |
|-------|------|--------|
| Fire Bolt | Attack cantrip | ✅ Implemented |
| Magic Missile | Auto-hit L1 | ✅ Implemented |
| Mage Armor | Buff L1 | ✅ Implemented |
| Hold Person | Concentration L2 | ✅ Implemented |

*Note: Sacred Flame (Cleric) and Call Lightning (Druid) are also implemented but not on the sorcerer list.*

---

## Difficulty Categories

| Category | Definition | Implementation Effort |
|----------|------------|----------------------|
| **EASY** | Uses existing patterns only (attack roll, single-target save, buff) | < 1 hour |
| **MEDIUM** | Minor extensions needed (new damage type, new condition, new buff effect) | 1-4 hours |
| **HARD** | New subsystem required (AoE, multi-target, reaction timing, terrain effects) | 1-2 days |
| **VERY HARD** | Major new architecture (summoning, domination/mind control, polymorph) | 1+ weeks |
| **BLOCKED** | No mechanical combat effect or requires GM adjudication | N/A |

---

## Cantrips (14 spells)

| Spell | School | Type | Effect Summary | Difficulty | Notes |
|-------|--------|------|----------------|------------|-------|
| **Acid Splash** | Conjuration | DEX Save | 1d6 acid, can target 2 creatures within 5ft | HARD | Multi-target targeting |
| **Chill Touch** | Necromancy | Attack | 1d8 necrotic, prevents healing, disadv vs undead | MEDIUM | New condition: NoHealing |
| **Dancing Lights** | Evocation | Utility | Creates lights, concentration | BLOCKED | No combat effect |
| **Fire Bolt** | Evocation | Attack | 1d10 fire | ✅ DONE | Already implemented |
| **Light** | Evocation | Utility | Object sheds light | BLOCKED | No combat effect |
| **Mage Hand** | Conjuration | Utility | Spectral hand manipulates objects | BLOCKED | No combat effect |
| **Mending** | Transmutation | Utility | Repair objects | BLOCKED | No combat effect |
| **Message** | Transmutation | Utility | Whispered communication | BLOCKED | No combat effect |
| **Minor Illusion** | Illusion | Utility | Create sound/image | BLOCKED | No combat effect (Investigation check exists but not combat) |
| **Poison Spray** | Conjuration | CON Save | 1d12 poison | EASY | Like Sacred Flame |
| **Prestidigitation** | Transmutation | Utility | Minor magical tricks | BLOCKED | No combat effect |
| **Ray of Frost** | Evocation | Attack | 1d8 cold, -10 speed for 1 round | MEDIUM | New condition: Slowed |
| **Shocking Grasp** | Evocation | Attack | 1d8 lightning, no reactions, adv vs metal armor | MEDIUM | Melee spell attack, conditional advantage |
| **True Strike** | Divination | Buff | Advantage on next attack vs target | MEDIUM | Concentration, delayed effect buff |

### Cantrip Summary
- **EASY**: 1 (Poison Spray)
- **MEDIUM**: 4 (Chill Touch, Ray of Frost, Shocking Grasp, True Strike)
- **HARD**: 1 (Acid Splash)
- **BLOCKED**: 7 (Dancing Lights, Light, Mage Hand, Mending, Message, Minor Illusion, Prestidigitation)
- **DONE**: 1 (Fire Bolt)

---

## Level 1 Spells (17 spells)

| Spell | School | Type | Effect Summary | Difficulty | Notes |
|-------|--------|------|----------------|------------|-------|
| **Burning Hands** | Evocation | DEX Save AoE | 3d6 fire, 15ft cone | HARD | Cone AoE |
| **Charm Person** | Enchantment | WIS Save | Charmed condition, 1 hour | MEDIUM | Charmed implemented, needs duration timer |
| **Color Spray** | Illusion | HP-based AoE | Blinds by HP pool, 15ft cone | HARD | Cone AoE + HP pool mechanic |
| **Comprehend Languages** | Divination | Utility | Understand languages | BLOCKED | No combat effect |
| **Detect Magic** | Divination | Utility | Sense magic | BLOCKED | No combat effect |
| **Disguise Self** | Illusion | Utility | Change appearance | BLOCKED | No combat effect |
| **Expeditious Retreat** | Transmutation | Buff | Bonus action Dash each turn, concentration | MEDIUM | Granted action buff |
| **False Life** | Necromancy | Buff | 1d4+4 temp HP | EASY | Temp HP implemented |
| **Feather Fall** | Transmutation | Reaction | Slow falling | HARD | Reaction casting, falling damage system |
| **Fog Cloud** | Conjuration | AoE Terrain | 20ft sphere heavily obscured | HARD | AoE terrain modification |
| **Jump** | Transmutation | Buff | Triple jump distance | BLOCKED | Jump distance not modeled |
| **Mage Armor** | Abjuration | Buff | AC = 13 + DEX | ✅ DONE | Already implemented |
| **Magic Missile** | Evocation | Auto-hit | 3x 1d4+1 force | ✅ DONE | Already implemented |
| **Shield** | Abjuration | Reaction | +5 AC, blocks Magic Missile | HARD | Reaction casting |
| **Silent Image** | Illusion | Utility | Create visual illusion | BLOCKED | No combat effect |
| **Sleep** | Enchantment | HP-based AoE | Unconscious by HP pool, 20ft radius | HARD | AoE + HP pool mechanic |
| **Thunderwave** | Evocation | CON Save AoE | 2d8 thunder, push 10ft, 15ft cube | HARD | Cube AoE + forced movement |

### Level 1 Summary
- **EASY**: 1 (False Life)
- **MEDIUM**: 2 (Charm Person, Expeditious Retreat)
- **HARD**: 7 (Burning Hands, Color Spray, Feather Fall, Fog Cloud, Shield, Sleep, Thunderwave)
- **BLOCKED**: 5 (Comprehend Languages, Detect Magic, Disguise Self, Jump, Silent Image)
- **DONE**: 2 (Mage Armor, Magic Missile)

---

## Level 2 Spells (21 spells)

| Spell | School | Type | Effect Summary | Difficulty | Notes |
|-------|--------|------|----------------|------------|-------|
| **Alter Self** | Transmutation | Buff | Aquatic/Appearance/Natural Weapons | MEDIUM | Natural Weapons option useful |
| **Blindness/Deafness** | Necromancy | CON Save | Blinded or Deafened, repeat saves | EASY | Conditions implemented |
| **Blur** | Illusion | Buff | Disadvantage on attacks vs you | EASY | to_target modifier |
| **Darkness** | Evocation | AoE Terrain | 15ft sphere magical darkness | HARD | AoE terrain, dispels light |
| **Darkvision** | Transmutation | Buff | Grant darkvision 60ft | MEDIUM | Vision system extension |
| **Detect Thoughts** | Divination | Utility | Read minds | BLOCKED | No combat effect |
| **Enhance Ability** | Transmutation | Buff | Advantage on ability checks | MEDIUM | Ability check advantage |
| **Enlarge/Reduce** | Transmutation | Buff/Debuff | Size change, +/-1d4 damage | MEDIUM | Damage modifier, size not modeled |
| **Gust of Wind** | Evocation | AoE Line | 60ft line, push 15ft, difficult terrain | HARD | Line AoE + forced movement |
| **Hold Person** | Enchantment | WIS Save | Paralyzed, concentration | ✅ DONE | Already implemented |
| **Invisibility** | Illusion | Buff | Invisible condition, ends on attack/cast | EASY | Invisible implemented |
| **Knock** | Transmutation | Utility | Unlock objects | BLOCKED | No combat effect |
| **Levitate** | Transmutation | Control | Lift creature/object 20ft | HARD | Vertical movement, restrained variant |
| **Mirror Image** | Illusion | Buff | 3 duplicates absorb attacks | HARD | Attack redirection mechanic |
| **Misty Step** | Conjuration | Teleport | Bonus action, 30ft teleport | HARD | Bonus action spell, teleportation |
| **Scorching Ray** | Evocation | Multi-attack | 3 rays, 2d6 fire each | MEDIUM | Multiple attack rolls (can reuse Fire Bolt pattern) |
| **See Invisibility** | Divination | Buff | See invisible/ethereal | MEDIUM | Vision system extension |
| **Shatter** | Evocation | CON Save AoE | 3d8 thunder, 10ft sphere | HARD | Sphere AoE |
| **Spider Climb** | Transmutation | Buff | Climb speed, walk on walls | BLOCKED | Climbing not combat-relevant |
| **Suggestion** | Enchantment | WIS Save | Compel action | VERY HARD | Mind control/AI behavior |
| **Web** | Conjuration | AoE Terrain | 20ft cube, restrained, difficult terrain | HARD | AoE terrain + Restrained |

### Level 2 Summary
- **EASY**: 3 (Blindness/Deafness, Blur, Invisibility)
- **MEDIUM**: 6 (Alter Self, Darkvision, Enhance Ability, Enlarge/Reduce, Scorching Ray, See Invisibility)
- **HARD**: 7 (Darkness, Gust of Wind, Levitate, Mirror Image, Misty Step, Shatter, Web)
- **VERY HARD**: 1 (Suggestion)
- **BLOCKED**: 3 (Detect Thoughts, Knock, Spider Climb)
- **DONE**: 1 (Hold Person)

---

## Level 3 Spells (20 spells)

| Spell | School | Type | Effect Summary | Difficulty | Notes |
|-------|--------|------|----------------|------------|-------|
| **Blink** | Transmutation | Buff | 50% chance to vanish to Ethereal each turn | HARD | Turn-end randomness, ethereal state |
| **Clairvoyance** | Divination | Utility | Remote sensor | BLOCKED | No combat effect |
| **Counterspell** | Abjuration | Reaction | Cancel spell being cast | VERY HARD | Reaction, spell stack interruption |
| **Daylight** | Evocation | Light | 60ft bright light sphere | BLOCKED | Light not combat-relevant currently |
| **Dispel Magic** | Abjuration | Utility | End spells on target | HARD | Requires spell tracking on entities |
| **Fear** | Illusion | WIS Save AoE | Frightened + forced Dash, 30ft cone | HARD | Cone AoE + forced movement |
| **Fireball** | Evocation | DEX Save AoE | 8d6 fire, 20ft sphere | HARD | Sphere AoE |
| **Fly** | Transmutation | Buff | 60ft fly speed | MEDIUM | New movement type (fly) |
| **Gaseous Form** | Transmutation | Transform | 10ft fly, resist nonmagical, can't attack | HARD | Major stat transformation |
| **Haste** | Transmutation | Buff | Double speed, +2 AC, adv DEX saves, extra action | HARD | Complex multi-buff + lethargy on end |
| **Hypnotic Pattern** | Illusion | WIS Save AoE | Charmed + Incapacitated + speed 0, 30ft cube | HARD | Cube AoE |
| **Lightning Bolt** | Evocation | DEX Save AoE | 8d6 lightning, 100ft line | HARD | Line AoE |
| **Major Image** | Illusion | Utility | Create detailed illusion | BLOCKED | No combat effect |
| **Protection from Energy** | Abjuration | Buff | Resistance to one damage type | EASY | Resistance implemented |
| **Sleet Storm** | Conjuration | AoE Terrain | 40ft cylinder, heavily obscured, prone, concentration break | HARD | Cylinder AoE + multiple effects |
| **Slow** | Transmutation | WIS Save AoE | Half speed, -2 AC, no reactions, action OR bonus | HARD | 40ft cube AoE, complex debuff |
| **Stinking Cloud** | Conjuration | AoE Terrain | 20ft sphere, waste action on failed CON save | HARD | Sphere AoE, moving cloud |
| **Tongues** | Divination | Utility | Understand/speak all languages | BLOCKED | No combat effect |
| **Water Breathing** | Transmutation | Utility | Breathe underwater | BLOCKED | No combat effect |
| **Water Walk** | Transmutation | Utility | Walk on liquids | BLOCKED | No combat effect |

### Level 3 Summary
- **EASY**: 1 (Protection from Energy)
- **MEDIUM**: 1 (Fly)
- **HARD**: 11 (Blink, Dispel Magic, Fear, Fireball, Gaseous Form, Haste, Hypnotic Pattern, Lightning Bolt, Sleet Storm, Slow, Stinking Cloud)
- **VERY HARD**: 1 (Counterspell)
- **BLOCKED**: 6 (Clairvoyance, Daylight, Major Image, Tongues, Water Breathing, Water Walk)

---

## Level 4 Spells (10 spells)

| Spell | School | Type | Effect Summary | Difficulty | Notes |
|-------|--------|------|----------------|------------|-------|
| **Banishment** | Abjuration | CHA Save | Remove from plane, incapacitated | HARD | Plane removal mechanic |
| **Blight** | Necromancy | CON Save | 8d8 necrotic, no effect on undead/constructs | EASY | Single-target save damage |
| **Confusion** | Enchantment | WIS Save AoE | Random behavior table, 10ft sphere | VERY HARD | AI behavior control, random actions |
| **Dimension Door** | Conjuration | Teleport | 500ft teleport, can bring ally | HARD | Long-range teleportation |
| **Dominate Beast** | Enchantment | WIS Save | Control beast, concentration | VERY HARD | Mind control/AI takeover |
| **Greater Invisibility** | Illusion | Buff | Invisible, doesn't break on attack | EASY | Invisible condition variant |
| **Ice Storm** | Evocation | DEX Save AoE | 2d8 bludgeoning + 4d6 cold, 20ft cylinder | HARD | Cylinder AoE |
| **Polymorph** | Transmutation | Transform | Transform into beast | VERY HARD | Complete stat replacement |
| **Stoneskin** | Abjuration | Buff | Resist nonmagical B/P/S | EASY | Resistance implemented |
| **Wall of Fire** | Evocation | AoE Terrain | 60ft wall, 5d8 fire on one side | HARD | Wall creation + ongoing damage |

### Level 4 Summary
- **EASY**: 3 (Blight, Greater Invisibility, Stoneskin)
- **MEDIUM**: 0
- **HARD**: 4 (Banishment, Dimension Door, Ice Storm, Wall of Fire)
- **VERY HARD**: 3 (Confusion, Dominate Beast, Polymorph)

---

## Level 5 Spells (11 spells)

| Spell | School | Type | Effect Summary | Difficulty | Notes |
|-------|--------|------|----------------|------------|-------|
| **Animate Objects** | Transmutation | Summon | Animate up to 10 objects as creatures | VERY HARD | Summoning system |
| **Cloudkill** | Conjuration | AoE Terrain | 20ft sphere, 5d8 poison, moves | HARD | Moving AoE cloud |
| **Cone of Cold** | Evocation | CON Save AoE | 8d8 cold, 60ft cone | HARD | Cone AoE |
| **Creation** | Illusion | Utility | Create nonliving objects | BLOCKED | No combat effect |
| **Dominate Person** | Enchantment | WIS Save | Control humanoid, concentration | VERY HARD | Mind control/AI takeover |
| **Hold Monster** | Enchantment | WIS Save | Paralyzed, works on all creatures | EASY | Like Hold Person |
| **Insect Plague** | Conjuration | AoE Terrain | 20ft sphere, 4d10 piercing, difficult terrain | HARD | Sphere AoE + terrain |
| **Seeming** | Illusion | Utility | Disguise multiple creatures | BLOCKED | No combat effect |
| **Telekinesis** | Transmutation | Control | Move/restrain creatures/objects | HARD | Contested check, restrained |
| **Teleportation Circle** | Conjuration | Utility | Portal to known circle | BLOCKED | No combat effect |
| **Wall of Stone** | Evocation | AoE Terrain | Create stone wall/panels | HARD | Wall creation, destructible |

### Level 5 Summary
- **EASY**: 1 (Hold Monster)
- **MEDIUM**: 0
- **HARD**: 6 (Cloudkill, Cone of Cold, Insect Plague, Telekinesis, Wall of Stone)
- **VERY HARD**: 2 (Animate Objects, Dominate Person)
- **BLOCKED**: 3 (Creation, Seeming, Teleportation Circle)

---

## Level 6 Spells (9 spells)

| Spell | School | Type | Effect Summary | Difficulty | Notes |
|-------|--------|------|----------------|------------|-------|
| **Chain Lightning** | Evocation | DEX Save Multi | 10d8 lightning, jumps to 3 secondary targets | HARD | Multi-target with chaining |
| **Circle of Death** | Necromancy | CON Save AoE | 8d6 necrotic, 60ft sphere | HARD | Large sphere AoE |
| **Disintegrate** | Transmutation | DEX Save | 10d6+40 force, destroys if 0 HP | MEDIUM | Single-target save, special death effect |
| **Eyebite** | Necromancy | WIS Save | Asleep/Panicked/Sickened, repeat each turn | HARD | Multiple condition options, concentration |
| **Globe of Invulnerability** | Abjuration | Buff | Block spells ≤5th level | VERY HARD | Spell immunity zone |
| **Mass Suggestion** | Enchantment | WIS Save | Suggest to 12 creatures | VERY HARD | Mass mind control |
| **Move Earth** | Transmutation | Terrain | Reshape terrain slowly | BLOCKED | No immediate combat effect |
| **Sunbeam** | Evocation | CON Save Line | 6d8 radiant + blind, 60ft line, repeat each turn | HARD | Line AoE, repeatable action |
| **True Seeing** | Divination | Buff | Truesight 120ft | MEDIUM | Vision system extension |

### Level 6 Summary
- **EASY**: 0
- **MEDIUM**: 2 (Disintegrate, True Seeing)
- **HARD**: 4 (Chain Lightning, Circle of Death, Eyebite, Sunbeam)
- **VERY HARD**: 2 (Globe of Invulnerability, Mass Suggestion)
- **BLOCKED**: 1 (Move Earth)

---

## Level 7 Spells (8 spells)

| Spell | School | Type | Effect Summary | Difficulty | Notes |
|-------|--------|------|----------------|------------|-------|
| **Delayed Blast Fireball** | Evocation | DEX Save AoE | 12d6+ fire, accumulates damage | HARD | Delayed trigger, damage accumulation |
| **Etherealness** | Transmutation | Transform | Enter Ethereal Plane | VERY HARD | Plane mechanics |
| **Finger of Death** | Necromancy | CON Save | 7d8+30 necrotic, creates zombie | HARD | Single-target + summoning |
| **Fire Storm** | Evocation | DEX Save AoE | 7d10 fire, 10x10ft cubes | HARD | Multi-cube AoE |
| **Plane Shift** | Conjuration | Teleport/Attack | Teleport or banish enemy | VERY HARD | Plane mechanics |
| **Prismatic Spray** | Evocation | DEX Save AoE | Random effects, 60ft cone | VERY HARD | Cone AoE + random complex effects |
| **Reverse Gravity** | Transmutation | AoE Control | Fall upward, 50ft cylinder | VERY HARD | Falling, positional chaos |
| **Teleport** | Conjuration | Teleport | Long-range teleport with accuracy table | HARD | Complex teleportation |

### Level 7 Summary
- **EASY**: 0
- **MEDIUM**: 0
- **HARD**: 4 (Delayed Blast Fireball, Finger of Death, Fire Storm, Teleport)
- **VERY HARD**: 4 (Etherealness, Plane Shift, Prismatic Spray, Reverse Gravity)

---

## Level 8 Spells (5 spells)

| Spell | School | Type | Effect Summary | Difficulty | Notes |
|-------|--------|------|----------------|------------|-------|
| **Dominate Monster** | Enchantment | WIS Save | Control any creature | VERY HARD | Mind control/AI takeover |
| **Earthquake** | Evocation | AoE Terrain | 100ft radius, prone, fissures, structure damage | VERY HARD | Massive AoE + terrain destruction |
| **Incendiary Cloud** | Conjuration | AoE Terrain | 20ft sphere, 10d8 fire, moves | HARD | Moving AoE cloud |
| **Power Word Stun** | Enchantment | HP-based | Stunned if ≤150 HP | MEDIUM | HP threshold, Stunned implemented |
| **Sunburst** | Evocation | CON Save AoE | 12d6 radiant + blind, 60ft sphere | HARD | Large sphere AoE |

### Level 8 Summary
- **EASY**: 0
- **MEDIUM**: 1 (Power Word Stun)
- **HARD**: 2 (Incendiary Cloud, Sunburst)
- **VERY HARD**: 2 (Dominate Monster, Earthquake)

---

## Level 9 Spells (5 spells)

| Spell | School | Type | Effect Summary | Difficulty | Notes |
|-------|--------|------|----------------|------------|-------|
| **Gate** | Conjuration | Portal | Create interplanar portal, summon creature | VERY HARD | Plane mechanics + forced summoning |
| **Meteor Swarm** | Evocation | DEX Save AoE | 40d6 fire+bludgeoning, 4x40ft spheres | HARD | Multi-sphere AoE |
| **Power Word Kill** | Enchantment | HP-based | Instant death if ≤100 HP | EASY | HP threshold, kill effect |
| **Time Stop** | Transmutation | Control | Take 1d4+1 extra turns | VERY HARD | Turn order manipulation |
| **Wish** | Conjuration | Ultimate | Duplicate any spell or unique effects | VERY HARD | Meta-spell, GM adjudication |

### Level 9 Summary
- **EASY**: 1 (Power Word Kill)
- **MEDIUM**: 0
- **HARD**: 1 (Meteor Swarm)
- **VERY HARD**: 3 (Gate, Time Stop, Wish)

---

## Overall Summary by Difficulty

| Difficulty | Count | Percentage |
|------------|-------|------------|
| **EASY** | 11 | 9% |
| **MEDIUM** | 16 | 13% |
| **HARD** | 46 | 38% |
| **VERY HARD** | 18 | 15% |
| **BLOCKED** | 25 | 21% |
| **Already Implemented** | 4 | (not counted in percentages) |

**Implementable without major new systems**: 27 spells (EASY + MEDIUM)
**Require new subsystems**: 64 spells (HARD + VERY HARD)
**Out of scope for combat engine**: 25 spells (BLOCKED)

---

## Implementation Priority Matrix

### HIGH PRIORITY (Combat-relevant, uses existing or near-existing patterns)

| Spell | Level | Type | Why |
|-------|-------|------|-----|
| Poison Spray | Cantrip | CON Save | Clone of Sacred Flame |
| Blindness/Deafness | 2 | CON Save | Conditions already implemented |
| Blur | 2 | Buff | Simple to_target modifier |
| Invisibility | 2 | Buff | Invisible already implemented |
| Scorching Ray | 2 | Attack x3 | Multi Fire Bolt |
| Protection from Energy | 3 | Buff | Resistance implemented |
| Blight | 4 | CON Save | Single-target damage |
| Greater Invisibility | 4 | Buff | Invisible variant |
| Stoneskin | 4 | Buff | Resistance implemented |
| Hold Monster | 5 | WIS Save | Clone of Hold Person |
| Disintegrate | 6 | DEX Save | Single-target + special death |
| Power Word Stun | 8 | HP-based | Stunned implemented |
| Power Word Kill | 9 | HP-based | Simple instant kill |

### MEDIUM PRIORITY (Require moderate new work)

| Spell | Level | Type | What's Needed |
|-------|-------|------|---------------|
| Chill Touch | Cantrip | Attack | NoHealing condition |
| Ray of Frost | Cantrip | Attack | Speed reduction condition |
| Shocking Grasp | Cantrip | Attack | Melee spell attack, reaction removal |
| True Strike | Cantrip | Buff | Delayed advantage buff |
| Charm Person | 1 | WIS Save | Duration timer |
| Expeditious Retreat | 1 | Buff | Granted bonus action |
| False Life | 1 | Buff | Temp HP (may be implemented) |
| Alter Self | 2 | Buff | Natural Weapons option |
| Darkvision | 2 | Buff | Vision range extension |
| Enhance Ability | 2 | Buff | Ability check advantage |
| Enlarge/Reduce | 2 | Buff | Damage modifier, size change |
| See Invisibility | 2 | Buff | Vision extension |
| Fly | 3 | Buff | Flying movement type |
| True Seeing | 6 | Buff | Truesight vision |

### LOW PRIORITY (Require major new systems)

#### Requires AoE System
- Burning Hands, Thunderwave (Cone)
- Fireball, Shatter, Circle of Death (Sphere)
- Lightning Bolt, Sunbeam (Line)
- Sleep, Color Spray (HP-pool AoE)
- Hypnotic Pattern, Slow (Cube)
- Ice Storm, Sleet Storm, Cone of Cold (Cylinder/Cone)
- Chain Lightning, Fire Storm, Meteor Swarm (Multi-target)

#### Requires Terrain/Wall System
- Fog Cloud, Darkness, Web, Stinking Cloud, Cloudkill, Incendiary Cloud
- Wall of Fire, Wall of Stone

#### Requires Reaction Casting
- Shield, Feather Fall, Counterspell

#### Requires Mind Control/AI Takeover
- Suggestion, Dominate Beast, Dominate Person, Dominate Monster, Confusion

#### Requires Teleportation
- Misty Step, Dimension Door, Teleport, Plane Shift

#### Requires Transformation/Summoning
- Polymorph, Animate Objects, Finger of Death (zombie creation)

### SKIP (Blocked - No combat mechanics)

- Dancing Lights, Light, Mage Hand, Mending, Message, Minor Illusion, Prestidigitation
- Comprehend Languages, Detect Magic, Disguise Self, Jump, Silent Image
- Detect Thoughts, Knock, Spider Climb
- Clairvoyance, Daylight, Major Image, Tongues, Water Breathing, Water Walk
- Creation, Seeming, Teleportation Circle
- Move Earth
- Wish (partial - spell duplication is implementable)

---

## Systems Needed Summary

| System | Spells Requiring | Complexity | Priority |
|--------|------------------|------------|----------|
| **AoE Targeting** | ~30 spells | HARD | HIGH - unlocks most damage spells |
| **Cone/Line/Sphere/Cube** | Burning Hands, Fireball, Lightning Bolt, etc. | HARD | Part of AoE |
| **Terrain Modification** | Fog Cloud, Darkness, Web, Walls | HARD | MEDIUM |
| **Reaction Casting** | Shield, Feather Fall, Counterspell | HARD | MEDIUM |
| **Teleportation** | Misty Step, Dimension Door, Teleport | HARD | LOW |
| **Duration Timers** | Most concentration spells | MEDIUM | HIGH - needed anyway |
| **Mind Control/AI** | Dominate spells, Suggestion, Confusion | VERY HARD | LOW |
| **Summoning** | Animate Objects, undead creation | VERY HARD | LOW |
| **Polymorph** | Polymorph, True Polymorph | VERY HARD | LOW |
| **Plane Mechanics** | Banishment, Plane Shift, Etherealness | VERY HARD | SKIP |

---

## Recommended Implementation Order

### Phase 1: Quick Wins (12 spells)
Implement using existing patterns:
1. Poison Spray (like Sacred Flame)
2. Blindness/Deafness (conditions exist)
3. Blur (to_target modifier)
4. Invisibility (condition exists)
5. Scorching Ray (multi Fire Bolt)
6. Protection from Energy (resistance exists)
7. Blight (single-target save damage)
8. Greater Invisibility (condition variant)
9. Stoneskin (resistance exists)
10. Hold Monster (like Hold Person)
11. Power Word Stun (HP check + Stunned)
12. Power Word Kill (HP check + death)

### Phase 2: Minor Extensions (14 spells)
Add small new features:
1. Chill Touch, Ray of Frost, Shocking Grasp (new minor conditions)
2. True Strike, Expeditious Retreat (delayed/granted effects)
3. Charm Person (add duration tracking)
4. False Life (temp HP if not done)
5. Alter Self, Enlarge/Reduce (damage modifiers)
6. Darkvision, See Invisibility, True Seeing (vision extensions)
7. Enhance Ability (ability check advantage)
8. Fly (flying movement)
9. Disintegrate (special death handling)

### Phase 3: AoE System (~30 spells)
Build AoE infrastructure to unlock:
- Burning Hands, Thunderwave (cones)
- Fireball, Shatter (spheres)
- Lightning Bolt (lines)
- Hypnotic Pattern, Slow (cubes)
- Ice Storm, Cone of Cold (cylinders/cones)
- Chain Lightning (chaining)

### Phase 4: Terrain & Walls (~10 spells)
Add terrain modification:
- Fog Cloud, Darkness, Web
- Wall of Fire, Wall of Stone
- Cloudkill, Incendiary Cloud

### Phase 5: Advanced Features
- Reaction casting (Shield, Counterspell)
- Teleportation (Misty Step, Dimension Door)
- Mind control (Dominate spells) - may skip for AI complexity

---

## Conclusion

Of 120 sorcerer spells:
- **27 spells (23%)** can be implemented with existing or minor extensions (EASY + MEDIUM)
- **46 spells (38%)** require the AoE system (highest priority new feature)
- **18 spells (15%)** require complex new systems (mind control, summoning, polymorph)
- **25 spells (21%)** have no combat mechanics and can be skipped
- **4 spells** already implemented (Fire Bolt, Magic Missile, Mage Armor, Hold Person)

**Recommended next steps:**
1. Implement the 11 "quick win" spells immediately (EASY category)
2. Build the AoE targeting system to unlock the largest batch of spells
3. Add terrain modification for control spells
4. Consider mind control/summoning as stretch goals
