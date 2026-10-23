# Hidden things and who knows them: a first-principles study

23 October 2026, branch `content_push_opus` (HEAD 7c485db1fb). This is a study, not a plan.
Nothing here has been changed in code. It was written because the content push stored
"who found a trap" in a field and kept "who has seen it" in the observer's senses, while the
human asked, repeatedly, for all of it to live in the trap's condition. The question goes
beyond traps: the same split runs through hidden creatures, hidden objects, container contents,
and the player seats.

Evidence: three read-only surveys of the code (creatures; spatial effects; objects, seats and the
client), with their key claims spot-checked against the source. Citations are file:line at HEAD.

## 1. The problem from first principles

There are two different kinds of truth about a hidden thing:

1. **Facts about the thing.** How hard it is to notice (a DC), and its state (armed, sprung,
   disarmed, its compartment opened). These belong to the thing. Every rule that needs them asks
   the thing.
2. **What each creature knows about the thing.** Whether this character has noticed it, by a
   glance (passive Perception), by a rolled search, or by watching it fire, and whether they
   already tried and failed. This is also the thing's business, because it is created by
   interacting with it. A trap the character searched for and missed is a fact about that trap
   and that searcher.

D&D frames it this way:
- A hidden trap has a DC.
- A character notices it by passive Perception or an active check.
- Once noticed, it is known to that character, who can point it out.
- A failed search does not entitle the player to roll again until circumstances change: the DM's
  call, usually "no".
- A creature that is Hidden stops being hidden from a creature that notices it.

From that, the **ownership principle** the human is asking for:

- **The concealing condition owns the concealment and the knowledge about it.** For a trap that
  is the trap's own condition; for a hidden creature, its Hidden condition; for a cache, its
  search gate. It stores:
  - the DC;
  - who knows (noticed passively, found by search, saw it fire);
  - who tried and failed.

  Its own handlers update that state when the triggering things happen.
- **Senses are a derived view.** An observer's senses show what the rules decide: what to draw,
  what paths to avoid. They are not the place where knowledge is decided or remembered, and they
  are never fed back as an input to the rule.

## 2. What the code does today

### 2.1 Hidden traps and hazards (spatial conditions)

| Knowledge | Where it lives | Notes |
| --- | --- | --- |
| DC | `condition_stealth_dc` on the condition (base_conditions.py:653) | Set to None when a trap fires, for good (mechanisms.py:130, gas_traps.py:191, jaws.py:162, portals.py:109, environmental_conditions.py:1254, container_traps.py:130). A re-armed trap stays visible to everyone forever. |
| Found by a search | `detected_by` on the condition (area_conditions.py:77), added by this push | Written only by Search for Traps (actions.py:3143); never cleared. |
| Has seen it | The observer's `Senses.spatial_effects` (sensory.py:100) | A display memory: kept while unseen, dropped only when every remembered cell is re-observed empty (sensory.py:2621-2696). |
| Failed a search | **Nowhere** | So a search can be retried for free. |

"Does observer X know trap Y" is decided in **five places that don't agree**:
1. **The base rule.** `SpatialCondition.is_hazard_perceived_by` (area_conditions.py:248): no DC,
   or in `detected_by`, or DC < passive Perception.
2. **Six overrides that also accept "in X's senses memory".** SpikeTrap, JawTrap, FiniteTrap,
   Portal, GasVent and the container needle (environmental_conditions.py:1058, jaws.py:80,
   mechanisms.py:96, portals.py:71, gas_traps.py:162, container_traps.py:101). SpikeTrap and
   Portal also treat "sprung" as known to all.
3. **The perception refresh's `discovered=` flag.** It is fed from senses memory into every
   observation (sensory.py:2640), a third gate.
4. **Tile and object hazards use passive Perception only.** `BaseBlock.is_hazardous_for`
   (base_block.py:752) ignores both found-by and memory. Search for Traps never sees these.
5. **The path cache, subjective crossing and the player projection.** These read senses memory
   only (gridmap.py:994-1016, gridmap.py:2516, projection.py:684-735).

So, for pressure plates, tripwires and Spike Growth, which don't override the rule:
- the display memory keeps a hazard drawn after passive Perception drops;
- the hazard layer, safe paths and Search treat it as unknown, so a search can find it again.

The tie rule also differs: passive Perception must beat the DC, while a search only has to meet it.

### 2.2 Hidden creatures

| Knowledge | Where it lives | Notes |
| --- | --- | --- |
| Stealth DC | `Hidden.stealth_result` on the condition (conditions.py:2544) | Copied to `BaseBlock.stealth_dc` (base_block.py:192, via conditions.py:2615) and again into the senses system's contact table. |
| Who notices me now | Recomputed at every settlement: stealth < passive and (sight or special sense) (sensory.py:2245-2251) | Stored only as each observer's current `Senses.entities`, a cache overwritten each settlement. |
| Who has noticed me | **Nowhere** | In D&D, a creature that notices you stops being fooled. Here, if its passive Perception later drops, you are hidden from it again. |
| Last known position | Only in the AI's `AIKnowledge` (knowledge_reduction.py:34-46) | There are also two separate implementations of "remembered creature". |

Rule questions found along the way:
- Hidden is applied before blindsight and tremorsense, so hiding also defeats non-visual senses
  (sensory.py:2249).
- `Revealed` (Faerie Fire and others) is per caster but suppresses invisibility for everyone.
- The encounter treats a stealth DC of 0 as "not hidden" (encounter.py:61).

### 2.3 Hidden objects, containers and locks

- **Hidden hardware** (trap levers, blades): `BaseItem.perception_condition_uuid` delegates the
  object's visibility to a spatial condition's observation (base_item.py:527-536). It inherits
  every inconsistency in 2.1.
- **Searchable furniture (this push):** `SearchGate.found` is one shared flag
  (searchables.py:36). It is not per finder, unlike the traps, and there is no failed-by.
- **A leak in this push's code: the client is sent a searchable body's contents before anyone
  has searched.**
  - The engine refuses to loot until the gate is open (environment_interactables.py:626-645).
  - The player publication sends contents whenever the container is open or broken and in
    sight, and never asks the gate (world_publication.py:101-106).
  - So opening a false-backed wardrobe shows the hidden contents on the player's screen before
    any search.
- **Locks:** an objective "Locked"/"Barred" item effect, the same for everyone who sees the
  object. There is no knowledge state, which is correct for a visible padlock.

### 2.4 Player seats, the client and the AI

- **Each observer's `Senses.seen`** (sensory.py:98) remembers explored cells. Only that
  creature's own routing reads it (entity.py:5325, 6490).
- **The seat's view is recomposed from its members' current senses, with no seen cells**
  (audience.py:455-461). The seat's explored cells exist only in the client, grow forever and
  never shrink.
- **This is the open summon question.** Cells a summon explored stay explored on screen after it
  leaves, but no remaining member can route through them, and the AI's knowledge keeps the
  departed observer's cells. It is the long-open "party explored knowledge" item (P18).

## 3. What the principle changes

If the concealing condition owns concealment and knowledge:

1. **One concealment record per concealing condition** (a trap's condition, Hidden, a search gate)
   holds:
   - `dc`;
   - `known_by`: noticed by passive Perception, found by search, or watched it fire;
   - `failed_by`: searched and missed.

   Every check of "does X know this" reads this one record. The DC stays a fact even after the
   trap fires; firing adds the creatures who saw it to `known_by` instead of clearing the DC. A
   re-armed trap stays known to those who know it and hidden from the rest.
2. **The record's handlers update it:**
   - a successful passive check, when the thing comes into the observer's view, adds to
     `known_by` once, so a later drop in Perception doesn't make the observer forget;
   - Search adds to `known_by` or `failed_by`;
   - firing adds the witnesses.
3. **Senses read the record and stop feeding back.**
   - The six overrides lose their "in senses memory" clause.
   - The `discovered=` flag no longer decides knowledge.
   - Senses keep only what to display and route.
   - Paths and crossings key on the record's knowledge, not on display memory.
4. **One rule everywhere:** spatial effects, tile and object hazards, hidden hardware.
5. **Search** skips anything in the searcher's `failed_by`, so there is one try per character
   per hidden thing unless the human picks a different retry rule.

Blast radius, from the surveys (approximate):
- the base `SpatialCondition` and its six trap subclasses;
- the triggers and Spike Growth;
- `BaseBlock.is_hazardous_for` and the tile trap;
- the sensory observation call and the path cache key;
- the player projection's trap disclosure;
- Search for Traps;
- the search gate and its publication.

Hidden creatures and seat memory are separate decisions below.

## 4. Decisions for the human

1. **Scope of the ownership change.** All hidden spatial effects (traps, hazards, hidden
   hardware) now, with creatures later? Or creatures (Hidden) in the same pass?
2. **Retry rule.** Choose one:
   - one try per character per hidden thing (the side agent's suggestion);
   - one try per party;
   - a retry allowed once something changes (a light, a buff, a new turn of exploration).
3. **Searchable contents.** Found for everyone (the false back is physically opened), or per
   finder like traps?
4. **A sprung trap.** Known to the creatures that saw it fire, or to everyone, as today?
5. **Hidden creatures.** Should "noticed once, stays noticed until it hides again" hold, which is
   5e and needs a `known_by` on Hidden? And should hiding defeat blindsight and tremorsense?
6. **Seat and party memory (P18).** Should explored cells be the party's, so that a summon's
   discoveries stay usable, or stay per creature? This is outside the content push.
7. **The "world" attacker** for the R49 darts. Attacks in this engine come from a creature on the
   map, so a passive world or dungeon attacker needs its own small study: where it stands, its
   faction, its turn, and what the client is told. Not covered here.

## 5. To fix whatever is decided

- The contents leak in 2.3 is this push's bug: the publication must respect the search gate.
- This push's loose `detected_by` field should be replaced by whatever record decision 1 picks,
  not extended.
- Uncommitted in the working tree: the human-requested deletion of the Haunted fungus (module,
  catalog rows and tests, with the Shove tests moved to `tests/engine/test_triskelion_shoving.py`).
  The plan and handoff still mention it.
- Per AGENTS.md, any implementation plan from this study gets an anti-slop and an anti-OOP
  reviewer, and a plan-adherence agent while it is built.
