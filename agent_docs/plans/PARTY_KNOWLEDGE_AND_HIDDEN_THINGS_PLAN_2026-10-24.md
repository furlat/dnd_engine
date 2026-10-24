# Hidden things and party knowledge: one record, one rule

Status: plan, 24 October 2026, branch `hidden_knowledge_opus` (from `content_push_opus` b139f0569b).
Two rounds of anti-slop and anti-OOP review are folded in (§10). Not implemented.

Design: proposal A of [the proposals](../HIDDEN_THINGS_KNOWLEDGE_DESIGN_PROPOSALS_2026-10-23.md).
Background: [the study](../HIDDEN_THINGS_AND_KNOWLEDGE_STUDY_2026-10-23.md).

## 1. What the human decided (23–24 October)

| Topic | Decision |
| --- | --- |
| Where knowledge lives | On the concealing condition, as its data. |
| One model, two kinds | **Hidden presence:** the thing is not perceived until it is known, as with a note, loot, a lever in an alcove, a trap, a hidden hazard on a tile, or a hiding creature. **Hidden nature:** the thing is seen, but what it is or does stays hidden until it is known, as with a secret door that looks like wall and can't be opened, or a hidden button. Hidden contents (a desk, a false back) are hidden nature for what is inside. A trap is hidden presence that also hurts. |
| Who knows | **Traps, hazards, objects, doors and contents: the party, which is the faction.** A creature with no faction is its own party. **A hiding creature: only the creature that noticed it,** as in the SRD, where each creature checks its own passive Perception. Failed searches are always per creature. |
| Sharing sightings | A later communication system, outside this plan. |
| Routes | **When a route is built, it uses the party's view:** every cell a party member sees or has explored, and every hidden thing the party knows. What a creature physically sees, its range and its targeting stay its own. |
| Passive Perception | It notices hidden traps, hidden objects, secret doors and hiding creatures; a score equal to the DC notices. This replaces the content push's exclusion of passive hidden-object discovery. Contents are the exception: they are found only by searching that object. |
| Search | **One area Search:** a single Perception roll for every hidden thing within reach. A search of one piece of furniture stays the targeted check for its contents. |
| Retry | One search per creature per hidden thing. |
| Found contents | Finding them opens the compartment, a physical change, so they are then visible to everyone. |
| Fired trap | Known to whoever perceived it firing, the plate or tripwire included. It stays hidden from everyone else after it re-arms. Re-arming never clears knowledge. **Built 24 October, to be confirmed:** raised spikes and an open hatch are noticed by anyone who sees them while they stay so (the record's `in_plain_view`, set by the spike trap and the portal as they rise or open; the old code's rule for those two). An existing test pins authored raised spikes as perceptible, and creatures walking unseen into raised spikes would be absurd. Every other trap is learned only by those who watch it fire. |
| A creature's own hidden thing | Spike Growth, for example, starts known to its maker's party. |
| Notice | It rides on the observer's existing sensory event, rooted in its cause. No new event and no second settlement. |
| Hidden creatures | Part of this plan, as its last step, once the objects and traps path is validated. The creature check today is batched and fast; it moves for one shared path and the decided rules: noticed stays noticed until the creature hides again, and hiding does not fool blindsight or tremorsense within range. |

**Two places where the plan states something the decisions imply rather than ask:**
1. **Who writes the record.** "The condition records it" becomes "the record is the condition's data, written by one GridMap function". dnd/core conditions cannot import the map (base_block.py:8 imports base_conditions, gridmap.py:29 imports base_block), so a handler on the base condition could not compute the party or invalidate routes. The deciders (the settlement and the searches) call that one function.
2. **What a closed secret door shows.** To a party that doesn't know it, the door is published as the wall it is disguised as: the wall's identity and name, and no door fields. The human described it as "a hidden door that looks like a wall when hidden".

## 2. Rules for this work

- **AGENTS.md:**
  - ECS: data on components, systems compose.
  - No late imports or cycles; no getattr or type checks to cheat.
  - Tests per HOW_TO_TEST.md.
  - Anti-slop and anti-OOP review of each step's diff.
  - A plan-adherence agent while it is built.
- **The content push rules hold,** apart from the passive Perception decision: content on existing owners, and nothing that slows the game.
- **Removed, never kept alongside.** Each item lists the step that removes it.
  - **Step 1:**
    - `BaseCondition.condition_stealth_dc`;
    - `SpatialCondition.detected_by` and `mark_detected_by`;
    - `is_hazard_perceived_by` and its six overrides (SpikeTrap, JawTrap, FiniteTrap, Portal, GasVent, the container needle);
    - the `discovered` parameter everywhere: BaseCondition (base_conditions.py:400), the `SpatialConditionOwner` Protocol (gridmap.py:333), and about 19 overrides;
    - the Protocol members `condition_stealth_dc`, `is_hazard_perceived_by` and `mark_detected_by` (gridmap.py:309-316);
    - passive Perception in both `traversal_rule_inputs` (base_block.py:638-644, entity.py:2000-2008);
    - Search for Traps and every registration: `action.search_for_traps`, actions.py:5831, actions_functional.py:31 and 111, summoning.py:9 and 96, and the AI semantics at action_semantics.py:478-495 and 1272 (`information.search_for_traps`, `actor.known_traps_nearby`).
  - **Step 2:**
    - `dnd/items/searchables.py` (`SearchGate`, `SearchBody`, `install_search_gate`), replaced by `dnd/items/concealment.py`;
    - the `gates_owner_contents` hook;
    - every object-level `BaseBlock.stealth_dc` use. From step 2 the contact table reads an object's DC only from its record. A test that sets it today is test_window_attack_access.py:175.
  - **Step 4:**
    - `Hidden.stealth_result` (conditions.py:2544);
    - `BaseBlock.stealth_dc` and `set_stealth_dc`;
    - the reads at base_actions.py:1821 and encounter.py:61, moved to the record.

## 3. The design in code terms

### 3.1 The record (data)

- **A new leaf module, `dnd/core/concealment_types.py`.** It imports only the standard library, pydantic and uuid, like `condition_types.py`. It holds:
  - the frozen value `Concealment`:
    - `dc: int`;
    - `aspect: ConcealedAspect`;
    - `knowers: KnowerScope`, either PARTY or CREATURE;
    - `known_by: frozenset[str | UUID]`, holding the faction, or for a creature with no faction or CREATURE scope its UUID itself;
    - `failed_by: frozenset[UUID]`, holding creatures;
  - `ConcealedAspect`:
    - HAZARD: a condition hiding itself as a hazard or trap;
    - PRESENCE: hiding its host object or creature;
    - ACTIONS: hiding what its host does;
    - CONTENTS: hiding what its host holds;
  - the pure functions:
    - `knower_key(record, faction, uuid)`;
    - `knows(record, faction, uuid)`;
    - `notices(record, passive)`, true when passive ≥ dc;
    - `with_knowers(record, keys)` and `with_failure(record, uuid)`.
- **The holders.**
  - The record is held as data by `BaseCondition.concealment: Optional[Concealment]`, which replaces `condition_stealth_dc` field for field.
  - The holder kinds and their aspects:

    | Holder | Aspect |
    | --- | --- |
    | Spatial trap or hazard condition | HAZARD |
    | Hazard condition on a tile or object | HAZARD (the existing branch at base_block.py:752, now read through the record) |
    | `Concealed`, a new INTERNAL item condition in `dnd/items/concealment.py` | PRESENCE, ACTIONS or CONTENTS of its object |
    | `Hidden` (step 4) | PRESENCE, with CREATURE scope |

  - `BaseBlock.concealment_holder(aspect)` returns the condition holding that aspect. It is indexed at membership commit, like `ground_hazard_holders` (base_block.py:273, 1140-1145), so building the contact table doesn't scan every target's conditions.
- **Builders** that take `stealth_dc` build a `Concealment`. Spike Growth's starts with its maker's party.

### 3.2 One question, one write function

- **Reading.** Every reader holds a block and a creature, and asks `knows(record, faction, uuid)` directly. `is_hazardous_for` stays objective, because conjuration.py:4315 overrides it and conjuration.py:4334 and 4349 use it as an effect rule. Knowledge is applied once wherever a requester's hazard answers are combined:
  - `GridMap.is_position_hazardous_for` and `hazard_cells` (gridmap.py:2146-2163, 5266), for routes;
  - the hazard layer (sensory.py:2113), for what is drawn;
  - BaseBlock's condition loop (base_block.py:748-756), for conditions held by blocks.

  The other readers are Disarm Trap (`ready_trap_known_to`), the area Search, the targeted Search, hidden trap parts (`BaseItem.is_observable_to`, which asks its mechanism's record through the Protocol), and the settlement's observation gate. `get_spatial_observation` loses its knowledge gate in every override.
- **Writing.**
  - `GridMap.record_concealment(writes)` is the only writer. It takes (holder, new record) pairs, sets each record, then bumps MOVEMENT only, once, over the union of the holders' cells. It finds those cells the way `hazard_owners` does (gridmap.py:5476-5520): the spatial footprint, otherwise the tile's or object's placement.
  - A batch avoids one `drop_reading_entries` walk per thing (gridmap.py:236), and MOVEMENT alone avoids the optical and obscurement work that `spatial_condition_changed` does mid-settlement.
  - Callers: the settlement (one call per settlement), the area Search and the targeted Search.
- **The Protocol.** `concealment` replaces `condition_stealth_dc`. `SpatialConditionOwner` also gains `target_entity_uuid`, which makes a spatial condition a `ConcealmentHolder`, the small protocol `record_concealment` takes. `hazard_owners` also returns, per owner, its concealing holders and whether it hides itself (data that stands in for a type check).

### 3.3 Notice inside the settlement

All paths decide first, write through one `record_concealment` call, and only then run the publishing stages. So "no fact is stored while the stages run" (sensory.py:1786) still holds.

- **Traps and hazards (step 1).**
  - **Where:** in `_recompute` (sensory.py:1705), after the views are built.
  - **Candidates:** the reaching hazard owners of each view. They are computed once per view (`frame_index` and `np.unique`, as at sensory.py:2108-2110) and passed to the hazard layer, which then doesn't compute them again.
  - **Noticed:** every concealed one the observer's party doesn't know, when `notices(record, passive)` holds or a settled fact is its change event with `exposes=True` (§3.5).
- **Pulling what others found.** In every settlement, any concealed owner in view that the observer's knowers know, but that the observer hasn't drawn, is marked for re-observation the same way as a new notice.
  - This covers party members after another member's notice or search: they draw it at their next settlement, at the latest their turn start.
  - Same-settlement party views are marked at once.
  - The fixture stage's passive test in its early exit (sensory.py:2541) becomes "no marks for this view".
- **Hidden-presence objects (step 2).**
  - **The DC.** The contact table reads it from the record through `concealment_holder(PRESENCE)`. Installing or removing `Concealed` publishes the existing perceivability fact, as `Hidden.on_membership_changed` does (conditions.py:2623-2627), so the table row updates.
  - **The filter.** `stealth < passive` (sensory.py:2249, 2269) becomes "known to the observer's knowers, or passive ≥ DC". It is checked only on rows that have a record. The rows kept only by passive Perception are notices.
  - **Party members.** Such objects are volatile targets, the existing `table.volatile` path that trap parts use (sensory.py:1759), so party members' contacts pick up a knowledge change at their next settlement. The object scaling script measures the cost.
- **Hidden-nature objects (step 2).** A has-holder column marks the rows that have an ACTIONS record. Among the view's object contacts, the rows the party doesn't know and passive Perception meets are notices.
- **The event.**
  - `SensoryUpdateEvent.concealed_noticed: frozenset[UUID]` is a fact only. No handler writes from it.
  - It is filled by `_emit_settled` and by the refresh path: `_recompute` returns it, because `recompute_observer` (sensory.py:1627) builds its event later.
  - It is listed in `event_record.ADDITIVE_FIELDS`.
  - It is not on the player wire.

### 3.4 The area Search

- **Names.** "Search" is the 5e name. The targeted contents search becomes "Search Inside", which ends the name clash with today's `SearchBody`, also called "Search" (searchables.py:57).
- **What it covers.** One Perception roll for every concealed thing in visible cells within 10 feet whose aspect is HAZARD, PRESENCE or ACTIONS, that the searcher's knowers don't know and the searcher hasn't failed. Objects join in step 2.
- **What it writes.** A total that meets the DC adds the searcher's knowers; otherwise it adds the searcher to `failed_by`. All of it goes in one `record_concealment` call.
- **How the result is shown.** The searcher's senses refresh as one sensory event whose parent is the search's effect. `update_entity_senses` gains `parent_event` and passes it to `publish_observer_refresh` (entity.py:5357-5365).
  - There is no `REVEALED` change, whose "reveals" log would reach other factions' seats (events.py:3649, subjective_combat_log.py:92).
  - The AI semantics row becomes the area Search's.

### 3.5 Exposure: a fact on the firing's event

- **The flag lives on the event.** `SpatialEffectChangeEvent` gains `exposes: bool`, set through a parameter of the shared `_open_change` (area_conditions.py:751). It is listed in `ADDITIVE_FIELDS`.
- **Where it is set.** At the sites that cleared the DC on firing: mechanisms.py:130, portals.py:109, gas_traps.py:191, jaws.py:162, container_traps.py:130 and the spike trap's state change.
  - The spike network's separate `reveal` change is folded into its state change. That means one "Environment reveals" log row fewer.
  - A pressure plate's press change carries it.
  - A tripwire, which has no state, opens a `STATE_CHANGED` change with `exposes` on each crossing. That is a new "changes Tripwire" log row, seen by those who see the wire.
- **Who learns.** That change's settlement gives knowledge to the knowers of every creature perceiving it. "Sprung" no longer means known to all.
- **The `apparent_presence` flag keeps its meaning,** "never hidden", read as `concealment is None` (area_conditions.py:188).
  - It is set only by the base area observation: fire, wet, ice, electrified water, steam, oil and the electric floor (environmental_conditions.py:257-1344).
  - Every DC-clearing site above belongs to a trap whose own observation leaves the flag false. So keeping the DC after firing changes nothing that the client memory reads (reduction.py:387).

### 3.6 Hidden-nature objects and contents (`Concealed`)

- **ACTIONS** (a secret door, a hidden button or lever).
  - **The use-action gate.** `Entity.observed_world_use_sources()` (entity.py:7093-7100) offers no use action of an object whose ACTIONS record the actor's knowers don't know. Two other paths are routed through it, so the gate is the only one: the AI capability builder (decision_epoch.py:490-498) and the name fallback (actions_functional.py:824).
  - **Object-targeted rows.** Rows that target the object (Unlock, Pick Lock, Lock Shut, Shove Object, Attack Object, Force) exclude such objects as targets for those actors, in the object-target collection they share.
  - **Publication.** To a seat whose party doesn't know it, a closed secret door is published as its disguise: the wall identity and name authored on its profile, and no door fields (`is_open`, `door_mechanism`, `door_swing`, world_publication.py:81-95).
    - The knowledge travels the way all perception does. The settlement marks the observer's own object contact as known (it already decides per creature), the seat's view composes its members' contacts (`composed_view`, audience.py:437), and `disclosed_floor_item` picks the door or its disguise from that composed view. The server never needs factions, and replay stays a pure function of recorded facts.
    - If the contact flag reaches the wire, the schema goes up; that is accepted.
    - Once opened, the door is published as a door to everyone.
    - (On 24 October I first drafted "wall to everyone while closed" to avoid this path, without asking; the human objected, and this is the plan's version.)
- **CONTENTS** (a desk, a false back).
  - "Search Inside" uses the record's skill and DC.
  - **Success removes `Concealed(CONTENTS)`,** which is the physical change. The contents gate (`StorageChest.contents_gated`) is then "no CONTENTS holder". The body is republished with `publish_location_state(ItemLocation.FLOOR, parent_event=effect)` (environment_interactables.py:587-590).
  - **Failure** adds the searcher to `failed_by`.
- **The contents leak.**
  - `ItemPresentationState` gains a server-only `contents_concealed`, derived at snapshot time from the holder. It is not a stored item field.
  - `contents_granted` (world_publication.py:101) withholds the contents while it is set.
  - It is never sent to seats, because sending it would itself tell them the desk has a compartment.
- **Content.**
  - `install_concealment(obj, aspect, dc, skill)`.
  - One secret-door profile, with its wall disguise and open look.
  - The searchable furniture moves to `install_concealment(..., CONTENTS, ...)`.
  - The asset handoff gains the secret door's looks.

### 3.7 The party's view in routes

- **One Entity helper.** It returns the party members' visible and explored layers, members being the registered creatures in `spatial_senses_system.senses_by_observer` with the same faction, the creature included. No party registry is added. It feeds the three admission sites (entity.py:5325, 6490, 6600) and `record_navigation_read`.
- **Cost.** Measured at load 18: 27 µs for a party of 6 against 4 µs for one creature, per route build.
- **Staleness is pulled.**
  - `NavigationRead` (sensory.py:1157) stores the layer objects it read, compared with `is` and never with `id()`.
  - `navigation_current` (sensory.py:1370) compares them, and entity.py:7526 already rebuilds when it is false.
  - Sensory pushes no flags.
- **Blockers only an ally sees right now.** The route treats them as the moving creature perceives them, and the step stops at contact as today.
- **Limit.** A member that leaves takes its explored cells with it, as today. Its finds stay with the party.

### 3.8 Hidden creatures on the shared path (the last step)

- **Hidden holds a PRESENCE record with CREATURE scope.** The DC is the Stealth result. Hiding again makes a new Hidden, whose record has no knowers.
- **The governing record.** When several Hidden conditions coexist (conditions.py:2619-2622, test_senses_light_stealth.py:1000), the highest DC governs, as today's maximum does.
- **The same filter and Notice as hidden-presence objects (§3.3).** A creature that notices keeps knowing until the hider hides again. Its allies must notice for themselves.
- **One home for the DC.** `BaseBlock.stealth_dc`, `Hidden.stealth_result` and the table's copy are replaced by the record. base_actions.py:1821 and encounter.py:61 read it too, which brings them to the tie rule and to "noticed stays noticed".
- **Blindsight and tremorsense** within range perceive a hiding creature (sensory.py:2249).
- **Validated before and after** with the creature timing row (§6).

## 4. Steps

Each step is built in this order:
1. Its tests are written first (§5).
2. It is implemented.
3. The six suites run in parallel: tests/engine, tests/ai, tests/player, tests/progression, tests/manual and tests/architecture.
4. Both reviewers read the diff.
5. It is committed, with only my files.

The known failure is test_71, the monster roster, which is out of scope.

| Step | Content |
| --- | --- |
| 0 | Commit `devtools/performance/hidden_knowledge_timing.py` (§6) and record the base numbers on this branch before any change. |
| 1 | §3.1–§3.5 for traps and hazards (spatial, tile and object): the record, the one question and one writer, Notice and pulling, Exposure, and the area Search over HAZARD. |
| 2 | §3.3 and §3.6 for objects: `Concealed`, the table changes, the gates, Search over PRESENCE and ACTIONS, "Search Inside", the leak, the secret-door content. |
| 3 | §3.7 the party's view in routes. |
| 4 | §3.8 hidden creatures, after steps 1–3 meet §6. |
| 5 | Qualification (§6) and doc updates: the study, the proposals doc, the content push plan and the asset handoff. |

## 5. Tests (HOW_TO_TEST: behaviour as data at a stable boundary)

- **One new file, `tests/engine/test_party_knowledge.py`.** It uses one `check` helper. Each case names the factions, builds a small arena, and runs public actions (Move, Search, Search Inside, a trap firing, Hide). It then asserts what can be observed:
  - drawn effects, hazardous cells and contacts;
  - routes and move targets;
  - action rows;
  - published player objects and log rows.
- **Step 1, traps and hazards:**
  1. **Tie:** passive Perception equal to the DC notices the trap.
  2. **Noticed stays known:** a later Perception penalty changes nothing.
  3. **Never seen means not known:** a trap no party member has seen is not avoided, however high the Perception. This is a behaviour change.
  4. **Party:**
     - A (heroes) notices a trap.
     - B (heroes), settled in the same pass, draws it.
     - C (heroes), outside that settlement, routes around it at once and draws it at its next settlement.
     - G (goblins) does not know it.
  5. **Search success:** the heroes know the trap; G doesn't, and G's seat receives no fact or log row about it.
  6. **Search failure:** the searcher can't find it again, even with a high roll. A party member can. Nothing changes for anyone else.
  7. **Firing:** the watcher's party knows the trap; G, out of sight, doesn't, and the trap stays hidden from G after re-arming. The plate that fired it is exposed the same way.
  8. **No faction:** a creature with no faction knows only what it noticed itself.
  9. **One sensory event:** a notice yields exactly one sensory event per observer for its cause, and that event carries the notice.
  10. **Hidden trap parts:** the hidden lever and the needle's Disarm row show only for the party that knows the trap.
  11. **Tile hazard:** a hidden hazard on a tile is noticed, searched and avoided by the same rules. This converts test_grid_pathfinding.py:645-680, test_local_navigation_routes.py:111-115 and test_senses_light_stealth.py:1815-1833.
  12. **Maker's party:** Spike Growth is known to the caster's party from the start, and to no one else.
- **Step 2, objects:**
  13. **Hidden presence:** a hidden note isn't perceived until passive Perception meets its DC or a Search finds it. After that, party members perceive it at their next settlement.
  14. **Secret door:**
      - For the goblins, the closed door publishes as wall and has no door fields, no Open, Unlock, Pick Lock, Shove or Attack rows.
      - Once the heroes know it, they get those rows.
      - After it is opened, everyone sees an open door.
  15. **Contents:**
      - Only Search Inside finds them, never passive Perception.
      - Success opens them for everyone.
      - A failure binds only the creature that failed.
      - Contents are never published before they are found. This is the leak regression test, at the publication boundary.
- **Step 3, routes:**
  16. B is offered a move into a cell only A has explored. Once A, a summon, is dismissed, it is no longer offered.
- **Step 4, creatures:**
  17. **Stays noticed:** a hider noticed by A stays perceived by A after A's Perception drops, until it hides again.
  18. **Allies don't inherit it:** A's ally, who never noticed the hider, doesn't perceive it.
  19. **Blindsight:** blindsight within range perceives a hider.
- **Existing tests change only where a decided rule changes them.**
  - The DC field changes in eight test files are mechanical.
  - The semantic changes:
    - the tie rule;
    - a sprung trap known to all (test_spatial_conditions.py:1188);
    - retries in test_triskelion_hazards_and_traps;
    - routes that avoided unseen traps;
    - the tile-hazard tests (case 11);
    - the searchable-furniture tests (`SearchGate` becomes `Concealed`);
    - the Hidden tests changed by step 4.

  Each changed expectation is named in its step's commit message.

## 6. Performance qualification

`devtools/performance/hidden_knowledge_timing.py` is committed in step 0, from this session's scratch scripts. It always runs base against new, interleaved, under load, with a garbage collection before each sample.

**What it measures:**

| Row | Scene | Steps |
| --- | --- | --- |
| Trap scaling | 0 to 400 traps, 40×40 map, 6 observers, with all in one faction and again with six factions. Full refresh, a 4-cell move, one firing, a search, an action listing. | 0, 1, 5 |
| Burst | The first settlement in which 6 observers notice up to 400 traps, and an area Search that finds many. | 1, 5 |
| Objects | 0 to 200 hidden notes, levers and secret doors in view of 6 observers. Full refresh and a move. | 2, 5 |
| Room | The packed-room Fireball and looting scene from the content push. | 0, 5 |
| Party move | A 6-member party moving. | 3 |
| Creatures | 6 observers with 0 to 8 hiding creatures moving. | 4 |

**Acceptance.**
- Rows with no hidden things match the base within noise.
- No per-thing slope is above the base.
- The trap slopes are reported against the proxy (0.33, 0.074 and 0.016 ms per trap).
- The settlement count per move, read from the existing `sensory.reducer_call` count, does not change.

## 7. Risks

- **The `discovered` signature change** touches about 19 files. The reviewers check that nothing else changed in them.
- **Party knowledge is faction-wide,** enemies included, for traps and objects. Faction changes already clear route caches (`invalidate_allegiance`, gridmap.py:854).
- **Volatile hidden-presence objects** are asked at every settlement. The object row measures this.
- **The contact filter is the hottest batched step.** The known term touches only rows with a record.

## 8. Out of scope

- The communication system for sharing sightings, Point Out included.
- A party-owned explored layer that keeps a departed member's cells.
- The "world" attacker.
- `Revealed`, which is per caster but suppresses invisibility for everyone (study §2.2).
- Passive notice of contents.
- Room composition: placing hidden things in rooms.

## 9. Open points for the human

The two statements at the end of §1: who writes the record, and what a closed secret door shows.

## 10. Review record

**First round (24 October):**

| Finding | Change |
| --- | --- |
| Pushing dirty flags onto party members is never published (sensory.py:547-551). | Routes pull through `NavigationRead` (§3.7). |
| A knowledge stamp duplicated the traversal counters. | No stamp (§3.2). |
| Unclear who writes; the Protocol not mentioned. | One writer; the Protocol updated (§3.2). |
| `exposed_in` was a message stored as state. | `exposes` on the change event (§3.5). |
| Party members settled in the same pass were missed; the refresh path was not covered. | Marks and the returned notice set (§3.3). |
| Step order; leftovers. | Search in step 1; removal list (§2). |
| Tile hazards were dropped silently. | The human chose to unify them (§1). |
| Performance targets; candidate lookup. | Two faction modes; "no slower than base"; one owner index (§3.3, §6). |
| A `REVEALED` change leaked through the combat log. | A rooted refresh (§3.4); case 5. |
| Plates; Spike Growth's maker. | Exposed; the maker's party knows (§1). |
| Search Body published nothing; `Optional[bool]`. | Republish; server-only derived fact (§3.6). |

**Second round (24 October):**

| Finding | Change |
| --- | --- |
| A base condition can't compute a party or call the map (import order). | Data only on the condition; one `GridMap.record_concealment` writer, called by the deciders (§1, §3.2). |
| The aspect had no generic home, and HAZARD clashed with PRESENCE. | The aspect is in the record, a HAZARD value added, and an indexed `concealment_holder` (§3.1). |
| Party members never drew a known thing already in view. | Pull marks every settlement; volatile hidden-presence objects (§3.3). |
| A secret door leaked through published door fields and object-targeted rows; the AI built actions on its own path. | Per-seat disguise from server-only facts; every object-targeted row gated; one use-action gate shared by the AI and the fallback (§3.6). |
| Knowledge inside `is_hazardous_for` would corrupt zone effect rules (conjuration.py:4315). | `is_hazardous_for` stays objective; knowledge is applied where hazard answers are combined (§3.2). |
| Second homes: `Hidden.stealth_result`, a stale table DC, a stored `contents_concealed`, `is_found`. | All removed or derived; success removes the CONTENTS holder (§3.6, §3.8). |
| `spatial_condition_changed` does too much mid-settlement; one cache walk per write. | MOVEMENT-only, batched once per settlement (§3.2). |
| Schema 20 was unnecessary and the wire field would leak. | No schema change; server-only facts (§3.6). |
| `apparent_presence` was not addressed. | Checked: no behaviour change (§3.5). |
| Search for Traps registrations, the name clash, base_actions/encounter reads, object `stealth_dc` writes. | Listed (§2); "Search" and "Search Inside" (§3.4). |
| The refresh call does not recompute. | `update_entity_senses(parent_event=...)` (§3.4). |
| Timing scripts were not in the repo; no burst rows; unnamed scripts. | A committed script with named rows (§6). |
| Hiding creatures were shared by faction without asking, which is not SRD. | The human chose per creature (§1, cases 17–18). |
