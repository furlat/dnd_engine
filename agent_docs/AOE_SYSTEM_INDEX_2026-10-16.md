# Area-of-effect system index — 2026-10-16

Read-only study of the adopted base **`d13e6ad083f`**
(`/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`, committed clean).
It indexes every multi-target, area, zone, surface, wall, trap and monster area
mechanic. It classifies them by resolution pattern and records where each pattern
cascades and where iteration order is load-bearing.

Five read-only agents (core machinery, evocation, conjuration/summoning, other
schools/classes, walls/traps/environment/monsters) produced the raw inventories.
Claims marked ✓ were re-read in code by the coordinator. Paths are relative to the
base root.

| Abbreviation | Path |
| --- | --- |
| BA | `dnd/core/base_actions.py` |
| ACT | `dnd/actions.py` |
| AC | `dnd/spatial/area_conditions.py` |
| EV | `dnd/core/events.py` |
| GM | `dnd/core/gridmap.py` |
| SEN | `dnd/blocks/sensory.py` |
| EVO | `dnd/spells/evocation.py` |
| CONJ | `dnd/spells/conjuration.py` |
| ABJ | `dnd/spells/abjuration.py` |
| ENV | `dnd/spatial/environmental_conditions.py` |
| MON | `dnd/monsters/spell_summon_actions.py` |

Human direction this answers: the simultaneous group applies to **all
area-of-effect resolution, not only Fireball**. Index everything, find where it's
problematic, and do all the work.

## 1. Shared machinery

- **Action entry.** `BaseAction.apply` (BA:2360-2371) wraps every action in
  `EventQueue.batch_on_event_callbacks`. That scope only delays passive batch
  observers, and nothing registers one. `SpellAction.apply` (ACT:4881-4888) adds
  `spell_execution_scope`, already shared by every application in a cast.
- **Convolution branch.** `_apply_action` handles MULTI_ENTITY/POSITION_AOE at
  BA:2514-2545 ✓:
  1. resolve targets once;
  2. EFFECT;
  3. `_apply_target_applications` (default `_apply_target_batch`);
  4. `_finalize_aoe` (area only);
  5. concentration cleanup;
  6. COMPLETION.
- **Per-target loop** (`_apply_target_batch`, BA:2192-2234 ✓):
  - mutates `self.target_entity_uuid`;
  - builds an `ApplicationMembership`;
  - registers a per-target EXECUTION copy (handlers may cancel it);
  - runs `_apply` → EFFECT;
  - publishes a committed `ActionApplicationCommittedEvent`;
  - completes the target.
  - It never checks the parent for cancellation and never skips targets that died
    earlier in the loop.
- **Sensory reducer.** `SpatialSensesSystem` runs at the COMPLETION of every
  DEATH / CONDITION_* / LIFE_STATE / TURN_START / SPATIAL_* event (SEN:646-692).
  Two direct calls bypass that: AC:972 (duration tick) and AC:1510 (zone
  creation) ✓.
- **Light.**
  - Recompute happens before spatial completion (GM:3179-3191) and publishes one
    event per in-range source (GM:5985-6042).
  - Light modifiers go out as one batch per call (GM:5257-5283).
- **Existing "settle once" precedents:**
  - `SpatialRemovalPublication` (AC:48-55, 835-858);
  - light-child deferral to the geometry parent (SEN:1638-1643);
  - Forcecage formation and full removal of Ice/Stone/Force walls, which publish
    after the commit (`dnd/spells/wall_constructions.py:346-351, 783-816`).
- **Sort keys disagree:**

  | Key | Where |
  | --- | --- |
  | `target_resolution_sort_key` (x, y, name, uuid) | BA:110 |
  | `str(uuid)` | AC:1482 (APPEAR/occupants); `dnd/items/spell_payloads.py:134` |
  | Fireball's own (support depth, contact, name, uuid) | EVO:993 |
  | Registry insertion order | class features via `Entity.get_all_entities()` |

## 2. Resolution patterns

| # | Pattern | Entry | Where cascades happen today |
| --- | --- | --- | --- |
| P-a | Generic convolution | BA:2514-2545 → `_apply_target_batch` | Per target: lifecycle (~6 versions + rule events). Each perception-relevant child (death, condition, perceivability, forced move, light) settles at its own completion: one sensory pass over V observers per child. |
| P-b | Overridden `_apply_target_applications` | Fireball EVO:929 (staged reach); Sunbeam EVO:3656; Call Lightning CONJ:268 (marker then super); Freezing Sphere EVO:6784 (→ P-g1) | Fireball: per stage, a reach event, per-target batches, IGNITE, and another stage on any `propagation_revision` change |
| P-c | `get_all_targets` repetition or selection | darts/rays/beams EVO:614, 767, 2785, MON:826; HP pools Sleep `enchantment.py:1022`, Color Spray `illusion.py:738` (frozen at validation); Chain Lightning EVO:3764/3775; Twinned (`sorcerer.py:1039`) | as P-a; repeats on one target are sequential |
| P-d | Persistent AreaCondition install | `SpatialCondition.activate` AC:580-627 | Three-channel invalidation + one tile event **per terrain cell** (AC:1374, `requires_paths=True` → full recompute per covering observer) + light batch + **manual reducer call** (AC:1510) + APPEAR loop (str uuid) + completion (**second reduction**). Removal: per-cell tile events published from the removal accumulator. |
| P-e | Moving or anchored zones | `move_with_anchor`/`relocate_anchor` AC:500-578; `move_zone` AC:1124; `_change_footprint` AC:1521-1593 | Per move: occupants leave → per-cell terrain remove → reindex/invalidate → light → per-cell terrain add → light → occupants enter |
| P-f | Secondary propagation (materials) | `ignite_surface_contacts` / `apply_elemental_surface_contacts` (`dnd/spatial/ignition.py:11-56`) → `apply_spatial_interaction` (`dnd/spatial/transitions.py:41-101`); residues `dnd/residues.py:203-304` | Per surface owner: retire, change footprint, or replace (CREATED + TRANSFORMED + per-cell terrain out and in + light). Per residue cell: one condition lifecycle. |
| P-g1 | Free loops outside the action machinery | `payload_blast` (`spell_payloads.py:53-206`); Ice Knife burst (`ice_knife.py:109-170`); Glyph trigger (ABJ:3453); Moonbeam initial exposure (EVO:5999); traps (`mechanisms.py:207`, ENV:1108, `jaws.py:139`, `gas_traps.py:192`); portals (`portals.py:111`); Blade Barrier release (`wall_fields.py:391`); stone escapes (`wall_constructions.py:517`); Opulent Revival (`divine_intervention.py:263`) | Each iteration settles separately; no application commits |
| P-g2 | SELF action opening a nested batch | Turn Undead `cleric.py:63`, Preserve Life `cleric.py:117`, Sunder `divine_intervention.py:129`, Turn the Unholy `paladin.py:1117` | as P-a; targets in registry order |
| P-h | Wall formation by sections | `ConstructWall._apply` (`wall_constructions.py:641-715`) | Per section: prepare/commit/publish + a sensory pass. Then per displaced creature: forced movement (which fires ENTER triggers). |
| P-i | Event-driven zone triggers (not in any action) | ENTER/LEAVE spatial handlers (inside the mover's action); TURN_START/TURN_END (encounter turns); round step `_environment_step` (`dnd/encounter.py:712-716`) | Per trigger: admission event + save + effect. Per round: each ROUNDS zone emits STATE_CHANGED over its whole footprint with **two reductions** (AC:964-974 ✓). Zones expire one by one. |

## 3. Index by pattern

Notation:

| Mark | Meaning |
| --- | --- |
| PT | damage rolled per target. Only Ice Knife rolls once (`ice_knife.py:139`); 5e rolls once for area damage. |
| T | adds difficult terrain (per-cell tile events) |
| O | heavy obscurement |
| L | light change |
| fit | **C** = clean as a simultaneous group; **ORD** = order-dependent (reason given) |

### P-a / P-c — instantaneous area and multi-target spells

| Spell | Location | Shape | World | Fit |
| --- | --- | --- | --- | --- |
| Burning Hands | EVO:1144 | 15-ft cone | IGNITE in finalize | C |
| Lightning Bolt | EVO:1292 | line 100×5 | IGNITE + ELECTRIFY | C |
| Shatter | EVO:1647 | r10 sphere | — | C |
| Circle of Death | EVO:1799 | r60 sphere | area not recorded | C |
| Cone of Cold | EVO:1935 | 60-ft cone | area not recorded | C |
| Sunburst | EVO:2155 | r60 sphere | deactivates magical darkness (L) | C |
| Ice Storm | EVO:3314 | r20 cylinder | IceStormTerrain (T) | C |
| Prismatic Spray | EVO:3894 | 60-ft cone | random color per target | C |
| Flame Strike | EVO:4161 | r10 cylinder | — | C |
| Vitriolic Sphere | EVO:6268 | r20 sphere | — | C |
| Faerie Fire | EVO:5577 | r20 sphere | concentration created by the first failure | C (minor) |
| Thunderwave | EVO:1438 | 15-ft cube | pushes vs live occupancy; reads `senses.position` ✓ | **ORD** |
| Gust of Wind | EVO:3168 | 60×10 line | pushes + zone (T) | **ORD** |
| Chain Lightning | EVO:3683 | primary + secondaries | each secondary re-derived from `caster.senses` mid-loop | **ORD** |
| Magic Missile / Scorching Ray / Eldritch Blast | EVO:566 / 717 / 2752 | repeats | same-target repeats sequential; Shield buff blocks later darts on that target (self-scoped) | C across targets |
| Mass Heal | EVO:4996 | ≤20 targets | shared pool on the action ✓ | **ORD** |
| Prayer of Healing, Mass Healing Word, Mass Cure Wounds, Divine Word | EVO:4671, 4750, 4836, 5229 | multi | — | C |
| Call Lightning / Strike | CONJ:226 / 180 | r7 | marker before targets (caster can hit itself and lose concentration) | C |
| Acid Splash | CONJ:385 | 1–2 targets | — | C |
| Banishment | ABJ:1449 | multi, `include_self=True` ✓ | caster banishing self ends its concentration mid-batch | **ORD** |
| Aid, Beacon of Hope | ABJ:2736, 3136 | multi | — | C |
| Holy Aura | ABJ:3752 | multi, no cap | one light per target (L) | C (cascades per target) |
| Blindness/Deafness | `necromancy.py:595` | multi | own-senses change per target | C (cascades) |
| Necrotic Bless | `necromancy.py:755` | multi | — | C |
| Charm Person / Monster, Hold Monster, Bane, Bless, Heroism, Animal Friendship | `enchantment.py` | multi | some read `get_visible_enemies` | C |
| Calm Emotions | `enchantment.py:2472` | r20 | — | C |
| Sleep | `enchantment.py:961` | r20, HP pool | frozen at validation, no refunds | ordered pre-pass + C |
| Color Spray | `illusion.py:693` | 15-ft cone, HP pool | blinds per target; eligibility reads perception | ordered pre-pass + C |
| Fear | `illusion.py:293` | 30-ft cone | — | C |
| Hypnotic Pattern | `illusion.py:518` | 30-ft cube | — | C |
| Weird | `illusion.py:1684` | 30-ft sphere | — | C |
| Slow | `transmutation.py:472` | 40-ft cube | — | C |
| Longstrider, Fly | `transmutation.py:2036, 2121` | multi | — | C |
| Create/Destroy Water | `transmutation.py:2400` | sphere | reveals invisibility per target; DOUSE/DRY + WetSurface | **ORD** (perception) |
| Exhale Dragon's Breath | `transmutation.py:2484` | 15-ft cone | grant re-checked per target; caster in cone can lose concentration mid-cone | **ORD** |
| Twinned Spell | `sorcerer.py:1032` | ×2 | perception spells per target | **ORD** (perception) |
| Turn Undead, Turn the Unholy, Preserve Life, Sunder | P-g2 | — | registry order | C (sort key) |
| Monster save bursts, Dragon Breath | MON:511, 2158 | sphere/cone | material contacts in finalize | C |
| Seismic Strike | MON:882 | 13-ft sphere | pushes | **ORD** |
| Winter's Breath, Cinderous Swipe, Sludgy Sling, Healing Vapours | MON:952, 937, 1383, 1487 | — | surface patch (T) | C |
| Dragonborn breath, acid flask | `origins/dragonborn.py:51`, `items/spell_items.py:255` | area not recorded | — | C |

### P-b — staged

- **Fireball** (EVO:880/929). **ORD** by stage: reach depends on barriers
  destroyed. Parent objects first, because destroying one removes its inserts.
  Parent cancellation is checked after each target. Ash per cell and boundary face
  in finalize.
- **Delayed Blast Fireball** (EVO:6807; `spell_payloads.py:53-206`, 590-627):
  - staged reach via `payload_blast`;
  - the 1-HP bead explodes when it is destroyed, so it can detonate inside another
    AoE's loop;
  - it also explodes on caster death or concentration loss.
  **ORD.**
- **Freezing Sphere** (EVO:6723 → `payload_blast`): str-uuid order, no faction
  filter; IceSurface (T). C.

### P-d / P-e / P-i — zones (conjuration, abjuration, transmutation, others)

| Zone | Location | Install work | Triggers | Per round | Fit |
| --- | --- | --- | --- | --- | --- |
| Grease | CONJ:647 | T | APPEAR, ENTER, TURN_END (EXECUTION phase); shared fence | — | install C; triggers fence issue |
| Web | CONJ:941 | T; IGNITE → BurningWeb | APPEAR, ENTER, TURN_START, LEAVE | — | C; ignition ORD |
| Entangle | CONJ:1315 | T | APPEAR | tick | C |
| Black Tentacles | CONJ:1526 | T | ENTER, TURN_START, shared fence | tick | C |
| Cloudkill | CONJ:1806 | O; moves each caster turn | ENTER, TURN_START | footprint change | C; overlap raises |
| Spirit Guardians | CONJ:2224 | anchored; membership | ENTER, TURN_START, LEAVE, EFFECT_ENTERS/LEAVES | tick + every caster step | C; membership leased before admission |
| Fog Cloud | CONJ:2595 | O | — | — | C |
| Darkness | CONJ:2779 | L cap + magical darkness | — | — | C |
| Daylight | CONJ:2980 | L; removes overlapping Darkness in map order | — | — | ORD (mild) |
| Insect Plague | CONJ:3180 | T | APPEAR (str-uuid order, deaths), ENTER, TURN_END, shared fence | — | **ORD** |
| Incendiary Cloud | CONJ:3419 | O; moves | APPEAR, ENTER, TURN_END, shared fence | footprint change | **ORD** |
| Stinking Cloud | CONJ:3759 | O | TURN_START | tick after disperse | C |
| Sleet Storm | CONJ:3962 | C≈200 T + O; DOUSE published **inside its own install**; per-flame dousing (L) | ENTER, TURN_START (EXECUTION phase; can remove concentration) | tick | **ORD** |
| Guardian of Faith | CONJ:4498 | object + zone | ENTER, shared 60-damage budget | tick for 4,800 rounds (2 passes per round) | **ORD** (budget) |
| Heroes' Feast lifetime | CONJ:4985 | — | — | tick | C |
| Globe of Invulnerability | ABJ:1099 | filter on other spells | — | — | C |
| Pass without Trace, Aura of Life | ABJ:3331, 3635 | anchored membership | APPEAR/ENTER/LEAVE | — | C |
| Glyph of Warding | ABJ:3435 | one-shot | detonation pushes in uuid order | — | damage C; detonation **ORD** |
| Antilife Shell | ABJ:3882 | anchored; blocks crossing | — | — | N/A |
| Silence | `illusion.py:1255` | Deafened per occupant (perception) | APPEAR/ENTER/LEAVE | — | C (cascades) |
| Spike Growth | `transmutation.py:124` | T; hidden hazard | ENTER per cell | — | C |
| Plant Growth | `transmutation.py:2338` | ×4 cost | — | tick | N/A |
| Moonbeam | EVO:5834 | movable | APPEAR, ENTER, EFFECT_ENTERS, TURN_START; cast exposure skips the fence | — | C at cast |
| Gust of Wind zone | EVO:2911 | T; DISPERSE | ENTER, TURN_START | — | C |
| Paladin auras | `paladin.py:882` | anchored membership | live recheck | — | C |
| Draconic Presence | `sorcerer.py:618` | anchored | TURN_START per hostile | — | C |
| Holy Nimbus | `paladin.py:1493` | L | global TURN_START | — | C |
| Raging Vortex, Sweetplum Gales | MON:1540, 1697 | membership | APPEAR/ENTER/TURN_START | — | C |
| Flaming Sphere aura | `monsters/spell_summons.py:81-171` | L; fire patch on every vacated cell | TURN_END; per step | — | ORD (objects) |

### P-f / P-h / P-g1 — walls, surfaces, traps, environment

| Mechanic | Location | Notes | Fit |
| --- | --- | --- | --- |
| Wall of Fire | `walls.py:43` | opaque; IGNITE after activation | C |
| Wall of Thorns, Wind Wall, Blade Barrier | `wall_fields.py:133, 145, 382` | Wind Wall reacts to cloud changes | C / ORD vs clouds / C |
| Wall of Ice/Stone/Force, Forcecage | `wall_constructions.py:557+, 907` | per-section placement; displacement plan; stone escapes run Moves in sequence | **ORD** (Forcecage already batched) |
| Section destroyed, Frigid Air | `wall_constructions.py:252, 40` | — | C |
| Fire, Burning Web, Oil, Water, Electrified, Steam, Ice surfaces | ENV:250, 865, 913, 526, 567, 720, 844, 598 | no cell-to-cell spread exists | C |
| Material transitions | `transitions.py:41-101` | op order within a burst matters | **ORD** |
| Spike trap, gas vent, jaw trap, finite traps | ENV:1093, `gas_traps.py:192`, `jaws.py:126`, `mechanisms.py:182` | — | C |
| Pressure plate | `triggers.py:35` | multi-pulse | **ORD** |
| Portal | `portals.py:110` | single exit cell | **ORD** |
| Liquid barrel spill | `content/items/environment_item_builders.py:90` | earlier spills filter later ones; fire hit ignites own spill | **ORD** |
| Chest spill | `items/environment_interactables.py:603` | — | C |
| Destruction debris | `content/items/world_prop_builders.py:705` | one T zone per destroyed prop | C |
| Supported-item collapse | `blocks/base_item.py:758` | parent before child | **ORD** |
| Residues: tile, area ash, blood | `residues.py:203, 265`, `body_responses.py:84` | per-cell condition lifecycle | C (dependent: each vetoable) |

## 4. Where order is load-bearing (complete list)

1. **Forced movement against live occupancy:** Thunderwave, Gust of Wind, Seismic
   Strike, Glyph detonation, wall displacement and stone escapes. Each push steps
   cell by cell and fires zone ENTER on the way (`ACT:372-449`).
2. **Shared mutable pools or budgets:** Mass Heal pool, Guardian of Faith 60-damage
   budget, Sleep/Color Spray HP pools (frozen at validation, no refund on
   cancellation).
3. **Self-interference via concentration:**
   - Banishment of self.
   - Exhale Dragon's Breath on the original caster.
   - Call Lightning/Sunbeam markers.
   - Sleet Storm TURN_START removing concentration.
   - Faerie Fire creating concentration on the first failure.
4. **Perception-dependent selection mid-loop:** Chain Lightning secondaries
   (`caster.senses`), Thunderwave `senses.position`, Color Spray eligibility.
   Perception changes published per target: Blindness, Silence, Color Spray,
   Banishment, Holy Aura lights, Create Water reveals, twinned perception spells.
5. **Stage dependency on destruction:** Fireball and `payload_blast`. Supported-item
   depth order. Delayed Blast bead nested detonation.
6. **Material and surface:** transition op order; barrel spills filtered by earlier
   surfaces; exclusive same-layer surface **raises** on different content
   (AC:354-358 ✓). Only `LiquidBarrel` guards against it; Flaming Sphere trail,
   Winter's Breath, `patch()` and oil→fire replacement over debris can raise
   (static reading).
7. **Single-exit and multi-pulse:** portal exit, pressure-plate pulses.
8. **Fences and order keys:**
   - The first-per-turn fence is one map per zone keyed by target, not by trigger
     kind (AC:1244-1246 ✓). Grease, Black Tentacles, Cloudkill, Insect Plague and
     Incendiary Cloud suppress second triggers in a turn.
   - Inconsistent sort keys (§1).
   - Turn triggers split across EXECUTION (Sleet, Grease) and EFFECT phases.
   - Zones tick and expire one by one in map order.
9. **Reactions inside loops:** Hellish Rebuke retaliates immediately on damage ✓
   (`dnd/spells/infernal.py:140-200`). Shield (self-scoped) cancels a dart and
   blocks later darts on the same target. Concentration saves fire on the spot and
   can release sustained zones/lights mid-loop. The full handler inventory is §7.

## 5. Cascade cost per pattern (per invocation, open room, V observers)

| Pattern | Now (sensory passes) | Driver |
| --- | --- | --- |
| P-a/c, N targets, D deaths, Pc per-target perception changes | D·(V+1) + Pc·V (+ corpse lights · V) | each child settles at its own completion |
| P-b Fireball stage, B destroyed props | above + B·(V·(3+f) + K·V′) + ash C·V hazard-only | per-prop object change, debris zone, light per source |
| P-d install, C cells | (2 + T·C + L)·V | per-cell tile events + manual + completion reductions |
| P-d removal | (1 + T·C + L)·V | per-cell tile events |
| P-e move | V + 2·ΔC·T·V + L·V | footprint change + per-cell terrain out/in |
| P-f replacement (oil → fire, c cells) | (2c + 7)·V | CREATED + TRANSFORMED + terrain out/in + light |
| P-h wall, S sections, D displaced | S·V + 2V + 3D·V + 2E·p·V | per section + per displacement step |
| P-i round step, R ROUNDS zones | 2R·V | STATE_CHANGED with two reductions each |

## 6. Natural group boundaries

- **Widest:** `BaseAction.apply` / `SpellAction.apply`. Covers P-a, P-b, P-c, P-d
  at cast, everything `_finalize_aoe` triggers (P-f, residues), P-g2, and in-cast
  P-g1 (Ice Knife, Moonbeam/Glyph initial exposure, Freezing Sphere).
- **Entry points outside any action scope,** each a natural group of its own:
  - one mover step (ENTER/LEAVE);
  - one creature's turn start or turn end;
  - one round step (all zone ticks/expiries);
  - one anchored-zone relocation;
  - one trap/plate fire;
  - one payload detonation;
  - one material interaction;
  - one concentration-loss cascade (nested in its damaging event).
- **Do not reuse `GridMap.disable_events`:** it skips veto phases.

## 7. Handlers that fire inside one target's application (D7a)

**Structural fact ✓.** Each per-target copy is registered at EXECUTION
(BA:2218), so **every CAST_SPELL/BASE_ACTION execution handler runs again for
every target**. CAST_SPELL effect handlers also run once per target. Declaration
handlers run once. Nothing re-checks that the caster can still act.

### Self-scoped (S): keep inline

- **Shield** (dart block and reaction, ABJ:228/383). The ShieldBuff blocks later
  darts only on its holder.
- **Damage caps:** Death Ward (ABJ:2043), Relentless Rage
  (`classes/barbarian.py:851`), Relentless Endurance, Undead Fortitude
  (`monsters/traits.py:1057`).
- **Resilient Sphere boundary** (EVO:6440).
- **Own-roll modifiers:** Indomitable, Lucky (all grant copies), Bless/Bane d4 on
  own roll, Resistance.
- **Leadership d4** (an anchored aura, so it depends on the leader's position).
- **Concentration check** (`conditions.py:2300`): the save itself is S, the
  release is O.
- **HasTakenDamage tracker.**
- **Own-condition breaks on damage:** Charm Person, Sleep, Animal Friendship,
  Hideous Laughter, Hypnotic Pattern, Phantasmal Force, Eyebite, Turned, Glyph
  Sleep.
- **Hidden reveal.**
- **Rage end.**
- **Feeblemind cure.**
- **Per-application admission filters** (correctly per target): Sculpt Spells
  (`classes/wizard.py:230`, acts only when `application` is set), Globe blockers
  (ABJ:1209/1269), Forcecage boundary, Wet admission, Divine Health.
- **Caster-owned damage changes:** Sculpt retained damage, Potent Cantrip,
  Empowered Evocation, Overchannel; spell hit riders.
- **Destroy Undead** (one Turn Undead recipient).
- **Caster bookkeeping:** Sanctuary self-break, Vicious Mockery (consumed by the
  first ray), MetamagicAutoRemove.
- **Restraint repair.**
- **Fall damage on forced movement.**

### Acts on others or starts new actions (O)

- **Reactions:** Hellish Rebuke (`spells/infernal.py:253`, fires at TAKE_DAMAGE
  EFFECT, before HP changes), Barbarian Retaliation (`barbarian.py:1131`), Fire
  Shield retaliation (EVO:5361), Holy Aura blindness of a fiend/undead toucher
  (ABJ:3733).
- **Concentration release** (`conditions.py:2236-2290` → `base_block.py:1966-1990`).
  Removes linked effects on other creatures immediately: Bless d4, Holy Aura,
  Globe, Hypnotic Pattern, summons, Haste. Includes the caster's own Call
  Lightning/Sunbeam marker, created before the targets.
- **Paladin aura refresh** (`paladin.py:1000/1072`). When the paladin drops, allies
  lose Aura of Protection before their saves against the same spell.
- **Anchored zone movement** (AC:534): Paladin aura, Leadership, Spirit Guardians
  (damages newly covered occupants), Antilife Shell, Draconic Presence, Flaming
  Sphere, Gust, Pass without Trace, Healing Incense. A pushed anchor drags its
  zone mid-group.
- **Summoning departure system and summoner death** (`summoning/system.py:79/402`,
  `summoning/conditions.py:83`). Retires summons that may be later targets; can
  trigger the encounter-end check.
- **Payload caster-death ending and destroyed payload explosion**
  (`spell_payloads.py:614/261`). Damages later targets mid-group.
- **Zone/trap/residue/portal spatial handlers** fired by forced movement.
- **Paid-entry retreat** (`actions.py:333`): starts a Move, which can draw
  opportunity attacks.

### World/derived (W): settle at group close

- Life-state commit (occupancy, light suppression, perceivability).
- Sensory reducer.
- GridMap perceivability cache.
- Body response residue.
- Item destruction cascade (barrel spill, chest spill, wall section).
- Surface transitions (during a group only Fireball's between-stage IGNITE).
- Sleet douse.
- Doorway close, pending return, residue-fear removal.

### Record (R)

Combat log, passive batch callbacks, dispatch observers. No handlers on
TEMPORARY_HP, CONDITION_STATE_CHANGED or ITEM_DESTRUCTION.

### One target changing another target's outcome today

1. Concentration release (above).
2. Paladin aura stripped mid-spell.
3. Pushed anchors moving their zones.
4. Push order against live occupancy; corpses stop blocking.
5. Retaliation damaging, killing, blinding or breaking the caster's concentration
   while the loop continues.
6. Summon retirement and encounter end mid-group.
7. Item destruction: supported items skipped, payload explosions, loss of
   intact-item conditions.
8. **Counterspell re-dispatched per target** ✓. It has no root-only guard
   (ABJ:939-965), so a counterspeller who saw nothing at root execution can see the
   caster after the root-EFFECT reveal and cancel later targets individually.
9. Greater Invisibility rolls Stealth per application (`conditions.py:2834-2880`).
   A mid-loop failure removes later rays' hidden-attacker advantage.
10. Light/visibility changes from deaths and destruction feed Hidden reveal and
    reaction eligibility (Hellish Rebuke, Counterspell).

### Counterspell placement

Counterspell, Silence, Globe and Forcecage attach at **root execution**
(BA:2492): after costs, before the root EFFECT and before the group. Sanctuary
ward and Charmed attach at root declaration. So Counterspell already runs before
the targets, and also again per target (item 8).
