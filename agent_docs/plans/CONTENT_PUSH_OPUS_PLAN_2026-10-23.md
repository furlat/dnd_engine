# Content push (Triskelion Outer Ward): content on existing owners, no new systems

Status: plan, 23 October 2026, branch `content_push_opus` (from `feature/rules-checking` 1f044792b1).
It keeps the correct parts of [the Triskelion backend content plan](TRISKELION_BACKEND_CONTENT_PLAN_2026-10-23.md)
and applies the human's decisions of 23 October. Step 1 (§4.A) is implemented; the rest
follows §7.

## 1. Rules for this work (the human's)

- **Content only.** New conditions, items, spells, abilities, actions and spatial effects
  are fine. No new engine systems.
- **Nothing that slows the game.** Every new behavior works only for the object or the
  occupants it concerns, through existing indexed owners: position-indexed spatial
  handlers, owner turn triggers, and use actions. No global scans, no listeners on every
  prop, no new sensory or movement solver.
- **Excluded:** multi-Z/stacked floors, fluid or current simulation, a campaign clock,
  passive hidden-object discovery, and a new physical perception solver. Exploration mode
  (§6) is deferred, not built here.
- **Sources:** the book transcription, rules ledger and content index under
  `triskelion-backend/.../agent_docs/triskelion-outerward-floor-00/` (see the old plan's
  §1 links) and the [5e conversions](../TRISKELION_5E_CONVERSIONS_2026-10-23.md). The
  stopped worktree's code is not adopted.

## 2. Human decisions, 23 October

| Topic | Decision |
| --- | --- |
| Hidden storage | Contents gated by a check or condition: a Search use-action on the container with a skill check against an authored DC. The container stays visible; only its contents are gated. Sensory is unaffected. |
| Hallucinations (R65 fungus) | A **Haunted** condition. Every N rounds (tunable, any number) at the owner's turn start, one authored "sound" with a mechanical effect. Turn-based, not minutes; no clock. |
| Moving furniture (R63 barricade) | Handle it: a Shove Object action moving a prop one cell per step through the normal crossing rules, reusing forced-movement ideas and pick/drop. |
| Locks, keys, thieves' tools | In. Core D&D, and they need no new system. Rules details follow the BG3 tool handout. |
| Floors with no enemies | Avoid them for now: keep one hostile alive, for example a goblin in a cage behind a real locked door. Exploration vs combat is a later design task (§6). |

## 3. Reusable owners (verified in this checkout)

| Concern | Owner |
| --- | --- |
| Props, footprints, materials, destruction | [`WorldPropProfile`, `build_world_prop`](../../dnd/content/items/world_prop_builders.py) |
| Art-only variants | [`ItemVisualVariantParameters`](../../dnd/items/visual_variants.py) |
| Items, weapons, wearables | [`authored_item_builders.py`](../../dnd/content/items/authored_item_builders.py) |
| Containers and looting | [`StorageChest`](../../dnd/items/environment_interactables.py), [`Inventory`](../../dnd/blocks/inventory.py) |
| Doors and controls | [`DirectionalDoor`](../../dnd/items/environment.py), [`ControlLever`](../../dnd/items/environment_interactables.py) |
| Area hazards | [`AreaCondition`](../../dnd/spatial/area_conditions.py), position-indexed spatial handlers |
| Traps | [`FiniteTrap`](../../dnd/spatial/mechanisms.py), [`TrapPayload`](../../dnd/types/traps.py) |
| Darkness and light | [`DarknessZone`](../../dnd/spells/conjuration.py), [`Daylight`](../../dnd/spells/conjuration.py), torch/campfire builders |
| Spell items | [`SpellGrantingItem`](../../dnd/items/spell_items.py) |
| Conditions and cures | [`conditions.py`](../../dnd/conditions.py) (Frightened, Paralyzed), [`LesserRestoration`, `RemoveCurse`](../../dnd/spells/abjuration.py) |
| Moving objects | [`GridMap.move_object`, `can_transition`](../../dnd/core/gridmap.py), [`ForcedMovementEvent`](../../dnd/core/events.py) |
| Water | water tiles and [`Swim`](../../dnd/actions.py) |

`GridMap.move_object` validates the destination, not the path between, which matters
for §4.H.

## 4. Packages

**What this pass works on (human, 23 October):** tiles and surfaces, walls, doors,
items, conditions, interactions, traps and props. **No monsters or creatures**: no
rosters, no new creatures, no creature fixes. **Items: only what exploring the environment needs**
(keys, Thieves' Tools, Trap Disarm Toolkit, light sources, containers and their contents).
No weapons, armour or magic gear in this pass (§4.B waits).

**Scope of this pass: build the parts, not the rooms.** This push creates every content
definition (props, items, conditions, actions, spatial effects) and the matching art the
floor needs. Composing rooms (placements, layouts, per-room counts) is a separate later
pass. The full list of distinct assets, with states, breakability and every interaction
transition to animate, is the
[asset generation handoff](../TRISKELION_ASSET_GENERATION_HANDOFF_2026-10-23.md).

### A. Props, variants, stock and lights (old P1)

- Distinct content definitions for distinct bodies: corpses and bones, taxidermy, the
  threefold statue, the nymph fountain, coffins, tapestries, dressers, beds, baths, pumps,
  hearths, the bar, displays. Rooms supply position, orientation and initial state only.
- Truthful materials: bones aren't masonry, and big iron storage isn't the wooden chest.
  Use a visual variant only when mechanics are identical.
- Finite stock as exact items and stacks with one owner each: coins as stacks, useful gear
  as real items, nothing duplicated across displays.
- **Lights only where the source says they're lit.** Lights are the one content type that
  costs sensory work for every observer; dozens of described candles are not dozens of
  emitters.

**Step 1 as built (23 October):** the prop table gained the handoff's bodies, a
`visual_variants` list per body and an `ItemVisualVariantParameters` argument on
`build_world_prop` (composition calls `build_world_prop`, as the battlefields do). A
`CONTAINER_PROFILES` table gives the chest builder material, hit points and a footprint. The
continual-light rod is a prop whose profile installs the existing Continual Flame condition.
A lit hearth is a separate `environment.hearth_fire` fixed flame in front of the fireplace:
breaking the masonry leaves the fire burning on the hearth, and its actions still read
"Light/Extinguish Wall Torch" (a known stand-in; those labels key the non-revealing action
list). The handoff's §14 lists every id and variant. Measured under load (15 interleaved
rounds): all-actor senses 6.0 ms empty, 8.5 ms with 52 existing props, 8.5 ms with 52 new
props, 8.6 ms with them plus the lit rods and hearth; the cost is prop count, not the new
content.

### B. Items and magic items (old P8): **not in this pass** (human, 23 October)

Follow the 5e pass: historical weapon profiles, Potion of Heroism (temporary HP plus
Bless), the Light/Daylight wand, the protection cloak and boots, three separately
consumable scrolls. Use existing item and condition owners. Identify, Prestidigitation and
attunement stay listed gaps, not part of this push.

### C. Area hazards as conditions (old P6)

- **R14 darkness:** an authored permanent `DarknessZone`, removed by Daylight.
- **R15 electric floor:** an entered-cell condition. DC 13 Dexterity; on failure 1d4
  lightning. Metal armor −4 and protective footwear +2 as explicit modifiers; safe carpet
  cells authored. Not an ElectrifiedWater reskin (no Wet).
- **R26 gray mold:** a disturbance affects every occupant present. DC 13 Constitution; on
  failure **Coughing** for 1d6 rounds. Re-entry allows a new save; moving inside the same
  exposure doesn't.

Each uses position-indexed entry handlers: no cost for anyone elsewhere on the map.

**Step 2 as built (23 October):**
- R14: `materialize_authored_darkness` installs a permanent `DarknessZone` whose origin says
  environment, magical, second level.
- R15: `ElectricFloor` asks a save on every plate entered. Metal armor (a `metal` tag on
  the eight metal armors) and footwear (anything worn on the feet) are named −4 and +2
  modifiers on that save.
- R26: `GrayMold`. **Coughing's effect is a choice for the human:** the book says only
  "loud hacking and choking", so Coughing gives disadvantage on Dexterity (Stealth) checks
  and nothing else.

### D. Container traps (old P7)

A trap condition on the container reacting to its own committed open:

- **R49 darts:** four +5 attacks, 1d4 piercing each, as ordinary attack events with
  reactions and attribution.
- **R53 needle:** DC 13 Constitution, Paralyzed for up to one minute, repeat save at turn
  end.

One activation each. A canceled open spends nothing, destruction disarms, closing never
rearms.

**Detect and disarm (BG3 model, adapted):**
- **Detect, passively:** the existing hazard perception rule (the trap's stealth DC against
  the observer's passive Perception). Each character perceives for itself.
- **Detect, actively (human, 23 October):** a fixed passive score alone makes every trap
  either always or never found for a given party. So add a **Search for Traps** action:
  - a Wisdom (Perception) check, rolled, against each nearby hidden trap's detection DC;
  - a hidden mechanism counts too, e.g. Investigation for a false back;
  - success reveals that trap to the searching character through the same disclosure the
    passive rule uses.

  It's an explicit action over the objects near the actor (a bounded query), not a sweep
  on movement, so nothing runs per step.
- **Disarm:** a Disarm action, a Dexterity (Sleight of Hand) check against the trap's own
  disarm DC, which needs a **Trap Disarm Toolkit**.
  - Success: the trap is spent and the kit is kept.
  - Failure: the kit is consumed **and the trap triggers**.
- **Separate DCs:** detect, disarm, lock and the trap's saving throw are four different
  numbers on one object.

**Step 2 as built (23 October):**
- A container's committed open calls a new `on_owner_opened` condition hook.
- `ContainerTrap` is the R53 needle. Failing the save gives `NeedleParalysis`: Paralyzed,
  with a repeat save at turn end, for up to 10 rounds. Lesser Restoration ends it whole.
- Conditions gained a `detected_by` set, honoured by the one concealment rule
  (`is_concealed_from`).
- Search for Traps and Disarm Trap are standard actions.
  - Search makes one Perception roll with no DC in the event, over seen cells within 10 ft.
  - Step 3 removed the find log (see §4.E).
- The AI policies don't value Search yet; when an AI searches is exploration-mode work (§6).
- Not yet built:
  - The hidden mechanism found by Investigation is the false back's searchable body (§4.F).
  - **The R49 darts wait for the human.** A trap attack roll needs a new attack source kind
    in the player facts and an attacker that isn't a creature. The alternative is Dexterity
    saves through the existing `TrapSave`/`TrapPayload` data.
- Measured under load: the action listing rose from 6.15 to 6.35 ms with three trapped
  containers in reach. A move far from the hazards showed no difference beyond noise.

### E. Locks, keys and thieves' tools (decided; BG3 model, adapted)

Following the [BG3 research](../BG3_LOCKPICKING_AND_TRAP_DISARMING_RESEARCH_2026-10-23.md)
where it fits, not all of it.

- **Lock state on doors and containers:** locked, lock DC, and key identity (an exact key
  item or authored key id). Bars are one-sided: the access side comes from the existing
  boundary sides.
- **Pick Lock:** a **Dexterity (Sleight of Hand)** check against the lock DC, which needs
  **Thieves' Tools** in inventory.
  - Proficiency or expertise in Sleight of Hand adds as usual; anyone with the tools may try.
  - Success: the lock opens and the tools are kept.
  - Failure: one set of tools breaks, and another set may retry.
  - Because BG3 uses the existing skill instead of tool proficiency, **no tool-proficiency
    system is needed**.
- **Unlock / Lock** with the matching key: no roll. A key does not disarm a trap; opening a
  trapped container by key still triggers it, unless an object is authored otherwise.
- **Force:** a Strength (Athletics) check, or destroying the object, which already works
  and spills contents.
- **Knock (optional):** a new level-2 spell opening mundane locks. Ordinary spell content.
- **Who's good at it:** add an **Urchin** background (BG3's) with fixed skills Sleight of
  Hand and Stealth; backgrounds already grant fixed skills, so this is content. There's no
  Rogue class; expertise and Reliable Talent come with a Rogue later.
- **New items:** Thieves' Tools and Trap Disarm Toolkit (consumable on failure); keys.
- **Not adopted from BG3:**
  - party Inspiration rerolls;
  - BG3's natural-1/20 rule for ability checks (we keep the engine's existing check rules);
  - crime and ownership reactions to Knock;
  - linked multi-trap systems beyond what the floor needs.
- **Client contract:** one small addition for doors and containers together. Publish
  "locked" and "trap detected" to observers who know; keep key identity, trap presence for
  others, and DCs hidden. The same bump adds a bone material (the R35 dragon skeleton waits
  for it). One schema bump; both SDKs regenerated.

**Step 3 as built (23 October):**
- **Locks.** A `Lock` item condition holds passive data: locked, a pick DC (none for a bar),
  a force DC, the exact key item, and for a bar the side of the door's boundary it is
  worked from.
  - While locked it publishes one "Locked" or "Barred" row in the existing object
    `item_effects`, with no DC and no key.
  - Open actions and the door and chest open paths refuse while `is_held_shut`.
  - Unlock and Lock (key or bar side, no roll), Pick Lock (Sleight of Hand with Thieves'
    Tools, a failure breaks one set) and Force Lock (Athletics, breaks the lock for good) are
    standard object actions.
  - A key opens a trapped chest but the needle still springs; a key-safe trap ("unless an
    object is authored otherwise") is not built.
  - A bar sits on one side of a door's boundary (the owner tile or the tile across) and is
    worked only from there. Forcing a lock bursts its door or chest open.
- **Trap detected.** The container needle is now a spatial condition anchored to its chest,
  like trap hardware. Each observer who perceives it gets it through the existing per-observer
  spatial-effect facts.
- **Schema.** So the bump (player schema 19) only extends two enums: `bone` (the dragon
  skeleton is back, made of bone) and `background.urchin` (fixed skills Sleight of Hand and
  Stealth).
- **Not built:** Knock (optional).
- **Search for Traps** keeps its name and its one Perception roll, over seen cells within 10 ft.
  It writes no log row: what it finds reaches the finder through their own spatial-effect
  facts, so no DC is shown.
- Measured under load: the action listing rose from 5.34 to 5.85 ms with all seven new
  standard actions and seven lockable, trapped or searchable objects in reach. A move far from
  the hazards was unchanged.

### F. Check-gated storage (decided)

A Search use-action on desks, remains, racks, floorboards and caches. It's a skill check
(Investigation or Perception) against an authored DC; on success the contents become
lootable, on failure nothing moves. Searchable furniture keeps its own footprint; it does
not become a chest-shaped obstacle. Nested canisters and under-bed boxes keep separate
inventories.

**Step 3 as built (23 October), following the decision in §2:**
- `build_searchable_prop` makes a profiled body (a desk, a false-backed wardrobe, loose boards)
  into a container that keeps the prop's name, footprint, blocking, material and debris.
- Its `SearchGate` keeps the contents out of reach (no loot rows) until a **Search** of that
  body beats its DC in its own skill: Perception, or Investigation for a false back.
- The body stays in plain view and senses are unaffected.
- Every searchable body carries a gate, so the Search action tells nothing about what is
  inside.
- A success frees the contents for everyone.

### G. Haunted (R65 fungus; decided)

- Exposure: the fungus's trigger, then a DC 13 Constitution save. On failure, the actor
  gains **Haunted** for a tunable number of rounds.
- Every N rounds (tunable), at the owner's turn start, one random authored "sound" from a
  small table. Each has a mechanical effect through existing owners: a Wisdom save against
  Frightened, losing the reaction, a step in a random direction by forced movement, or a
  perception penalty until next turn.
- Cured by Lesser Restoration or poison-family removal; it ends on its duration. The player
  sees each sound as its effect and combat-log entry.
- No timer service, no fake creature or sound source, no new fact type.

**Step 4 as built (23 October):** `dnd/spatial/spore_fungus.py`.
- `SporeFungus` asks one Constitution save (DC 13, poison) at a creature's third turn end in
  its cells. One save per stay; leaving resets it.
- Failing gives `Haunted` for `haunt_rounds`, with a sound every `cue_interval_rounds`. Both
  are authored per fungus (defaults 100 and 3).
- Haunted is poison-family (`immunity_names=("Poisoned",)` plus the poison tag), so poison
  immunity prevents it and Lesser Restoration cures it.
- The book's d12 sounds, four each, act through existing owners:
  - **drawn:** a forced step toward the sound;
  - **startled:** `NoReactions` until the next turn;
  - **distracted:** −5 Perception, passive included, until the next turn.
- **Frightened is left out (a choice for the human):** with no frightener to sense, it does
  nothing in this engine. Each sound goes to the owner's log only.

### H. Shove Object (R63 barricade; decided)

An action moving a prop **one cell per step**, each step admitted through the existing
crossing rules (`can_transition` and the footprint at the new cells), the way forced
movement steps a creature. Multi-cell props check the whole footprint per step. A failed
step leaves the prop where it is and the route closed. The action has a cost, and a
Strength check for heavy props. No autonomous furniture planner.

**Step 4 as built (23 October):** `ShoveObject` (`dnd/items/shoving.py`) is a standard object
action.
- It pushes a blocking floor body one square straight away from an actor standing square
  against it.
- Only bodies authored as shoveable move. A `shoveable` profile flag, true by default, is
  false for fixtures built in place: the fireplace, pumps, fountain, statue, shrine, privy,
  toilet, bathtub and bar. **The default is a choice for the human.**
- Every step into a cell outside the body's own uses `can_transition` (terrain, walls, doors,
  height). The new cell must also be walkable, with no creature in it, and the map must admit
  the footprint.
- Heavy bodies (over one cell, or stone or metal) need Strength (Athletics) DC 15.
- A stopped or failed shove leaves the body where it was.
- Measured under load, garbage collected before each sample, with all eight new standard
  actions:
  - nothing in reach: the action listing went from 6.18 to 6.57 ms;
  - eight lockable, trapped or searchable objects in reach: from 7.10 to 7.93 ms.
- A move with R14's magical darkness in sight costs about 4 ms more: the existing
  DarknessZone cost, the same as a cast Darkness.

### I. Keep the session alive (decided workaround)

Each playable floor keeps one hostile in the encounter, for example a goblin in a cage
behind a locked door (§4.E). It costs one AI turn per round, measured. No dummy-enemy
mechanism and no change to the combat-end rule.

## 5. Out of this push

Multi-Z and the R07 hatch, fluid and currents, the full idol curse and its weight/Strength
progression, the bull's-eye lantern's beam and fuel, the pump's vessel capacity (R28; a
"fill an empty waterskin" item swap is enough if wanted), Dispel Magic, attunement,
creature spawning and random encounters, other floors.

## 6. Later design task: exploration vs combat

Today an encounter ends when one faction remains. A real exploration mode needs:

- its own end rule;
- what the AI does out of combat;
- turn order with several explorers;
- how combat starts.

That's a separate task with its own plan. Until then, §4.I.

## 7. Order and exit evidence

| Step | Work | Exit evidence |
| --- | --- | --- |
| 1 (done) | A (B is out) | Placement, loot conservation, destruction, client-visible facts. Paired timing: dense test room vs empty, under load. |
| 2 (done but darts) | C and D | Correct recipients only; saves, durations and cures; one activation; no cost for distant actors (paired timing). |
| 3 (done; SDK reduction unverified) | E (after the BG3 handout) and F | Locked/unlocked/forced/picked transitions; wrong key or canceled action preserves state; secrecy of key identity; SDK reduction of the new field. |
| 4 (done) | G and H | Haunted fires every N rounds only for its owner; cures; shove steps can't pass walls or overlap; failed steps keep state. |
| later (separate pass) | Room composition and floor assembly, with I | Not in this push. Placements, per-room counts, reachability, real HTTP commands, authoring export. |

Tests follow [HOW_TO_TEST.md](../../HOW_TO_TEST.MD): player-visible behavior through
public boundaries, with fixtures from ordinary character creation. Timing under load,
base and new interleaved (the measure-under-load rule).

## 8. Reviews

For each implementation step:

- an **adherence agent** tracks the step against this plan;
- an **anti-slop reviewer** checks scope, source truth and that nothing is faked;
- an **anti-OOP/ECS reviewer** checks passive data, ownership, lifecycle and import
  direction.

## 9. Open questions

- Which keys exist on this floor, and which are carried by creatures.
- Source counts against layout capacity (beds in rooms 48/53/55, the armory stacks).
- Haunted's defaults (100 rounds, a sound every 3) and the sound-to-effect table (§4.G), and
  whether Frightened should be one of the effects.
- The R49 darts: trap attack rolls (a new attack source in the contract) or Dexterity saves.
- Coughing's effect: disadvantage on Stealth only (§4.C).
- Whether to build the handoff's "later" interactions: taking things off walls, racks and
  stands (with rack full/empty states), pulling curtains aside (the R49 manikin reveal), and
  pumping water. They have no game action today; handoff §12.4, §12.5 and §12.7 mark them.
