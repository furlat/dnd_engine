# Content push (Triskelion Outer Ward): content on existing owners, no new systems

Status: plan, 23 October 2026, branch `content_push_opus` (from `feature/rules-checking` 1f044792b1).
It keeps the correct parts of [the Triskelion backend content plan](TRISKELION_BACKEND_CONTENT_PLAN_2026-10-23.md)
and applies the human's decisions of 23 October. No implementation has started.
The thieves' tools rules wait for the human's BG3 tool handout (§4.E).

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
  others, and DCs hidden. One schema bump; both SDKs regenerated.

### F. Check-gated storage (decided)

A Search use-action on desks, remains, racks, floorboards and caches. It's a skill check
(Investigation or Perception) against an authored DC; on success the contents become
lootable, on failure nothing moves. Searchable furniture keeps its own footprint; it does
not become a chest-shaped obstacle. Nested canisters and under-bed boxes keep separate
inventories.

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

### H. Shove Object (R63 barricade; decided)

An action moving a prop **one cell per step**, each step admitted through the existing
crossing rules (`can_transition` and the footprint at the new cells), the way forced
movement steps a creature. Multi-cell props check the whole footprint per step. A failed
step leaves the prop where it is and the route closed. The action has a cost, and a
Strength check for heavy props. No autonomous furniture planner.

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
| 1 | A and B on one dense representative room | Placement, pickup/equip/loot conservation, destruction, client-visible facts. Paired timing: dense room vs empty room, under load. |
| 2 | C and D | Correct recipients only; saves, durations and cures; one activation; no cost for distant actors (paired timing). |
| 3 | E (after the BG3 handout) and F | Locked/unlocked/forced/picked transitions; wrong key or canceled action preserves state; secrecy of key identity; SDK reduction of the new field. |
| 4 | G and H | Haunted fires every N rounds only for its owner; cures; shove steps can't pass walls or overlap; failed steps keep state. |
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

- Thieves' tools rules: from the BG3 handout.
- Which keys exist on this floor, and which are carried by creatures.
- Source counts against layout capacity (beds in rooms 48/53/55, the armory stacks).
- The tunable rounds for Haunted, and its sound table.
