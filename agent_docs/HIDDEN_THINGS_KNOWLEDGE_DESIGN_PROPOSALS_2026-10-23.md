# One system for hidden things and who knows them: design proposals

23 October 2026, branch `content_push_opus` (HEAD 7c485db1fb). Companion to
[HIDDEN_THINGS_AND_KNOWLEDGE_STUDY_2026-10-23.md](HIDDEN_THINGS_AND_KNOWLEDGE_STUDY_2026-10-23.md),
which lists today's problems (cited here as study §n). These are proposals, not a plan. No code was changed.

## 1. The model

There are four kinds of state. Today they are mixed together.

| State | Example | Who owns it | When it changes |
| --- | --- | --- | --- |
| **Concealment** | The trap's DC, armed or sprung; a Hide result; a false back's DC | The concealing condition | When the thing changes (fires, re-arms, a new Hide) |
| **Knowledge** | Brakka found the trap; Ilse searched and missed | Section 5 (proposal A: the concealing condition) | Only at the discrete events of §2 |
| **Perception** | What is in Brakka's view right now | Sensory, recomputed at every settlement | Every movement, light change and door |
| **Display memory** | The last shape of the trap Brakka saw | The observer's senses | When a cell is seen again; used only to draw |

The rule that follows from this split:

> **Knowledge is acquired, stored and read. It is never recomputed from perception when something asks.**
> Perception produces the events that create knowledge. It does not store knowledge, and nothing asks it "does X know Y".

This one rule is behind both the bugs and the cost:

- **The bugs.** Today, "knows" is a function every reader evaluates for itself: the DC against passive Perception right now, or "is it in senses memory". So five places decide it and they disagree (study §2.1).
  - A drop in Perception makes a creature forget.
  - A failed search leaves no trace.
  - Firing clears the DC for everyone, forever.
- **The cost.** Every read of that function pays a full passive Perception evaluation, 12.7 µs, and nothing is cached. It runs once per pair of observer and concealed thing:
  - in the hazard layer;
  - in each spatial observation;
  - in every hazard probe of a route search.

  That is the single largest per-trap term on the sensory path (§6).

## 2. The events that change knowledge (the complete list)

| Event | Effect | Produced by | How often |
| --- | --- | --- | --- |
| **Notice** | A concealed thing is in an observer's perception and passive Perception clears its DC. The observer joins the knowers. | The sensory settlement. It already has each observer's passive Perception (`passives`, sensory.py:1715) and the candidates in view. | Once per pair, ever |
| **Search** | A rolled check against the DC. The searcher joins the knowers, or the failed list. | The search action (traps, Search Body, the Search action for creatures) | Per action |
| **Exposure** | The thing gives itself away (a trap fires, a false back is broken open). Every creature perceiving it at that moment joins the knowers. | The concealing condition's own handler marks itself exposed. The next settlement delivers that to the creatures that perceive it. | Per firing |
| **Told** | A knower points the thing out to others. | A rule to decide (§7): automatic within a party, an action, or none | Rare |
| **Re-concealment** | A creature hides again: a new Hidden condition, a new record, no knowers. Or an owner re-hides a trap. | The new condition | Per Hide |
| **Retry clearance** | The failed list is cleared when the retry rule's circumstance happens. | The condition's handler for that event (study §4.2) | Rare |

Senses produce only Notice and the delivery of Exposure. Each is one write when a pair first meets.

**One root, no new event, no second sensory pass** (decided 23 October):

- **Every knowledge change has exactly one root:** the move step, light change, door, search or firing that caused it.
- **Notice adds no event of its own.**
  - The settlement already emits one `SensoryUpdateEvent` per observer as a child of that cause (`parent_event=cause`, sensory.py:624).
  - The notices ride on it as one more field: the concealed things this observer noticed in this settlement.
  - A notice always changes what the observer draws, so that event is always emitted anyway.
- **The same pass publishes the right view.** Within one settlement, "known" means "already in the record, or noticed now". The hazard layer, the observations and the contacts are already correct, so there is nothing to redo.
- **The concealing condition records the notice.** As the settlement emits the event, each noticed thing's condition receives it through its own handler (`on_noticed`).
  - Sensory events are completion facts, which never reach event handlers, so the settlement makes this hand-off itself.
  - The handler publishes nothing.
  - It bumps only the knower's knowledge revision. That marks routes dirty, and they are rebuilt lazily at turn start or at the end of a move.
  - It does not bump the condition's observation revision, because nobody else's view changed.
- **It cannot start sensory again.** A sensory event skips the pre-completion systems (events.py:2028), and the record write emits nothing.
- **Search and Exposure follow the same pattern.**
  - Search writes the record in its action's effect. The settlement that runs when the action completes then shows the result: that is the action's own settlement, not a second one.
  - A firing marks the trap exposed. Its own settlement delivers notices to every creature that perceives it.

## 3. The readers: one question

Every consumer asks only `knows(observer, thing)`. It is a lookup, not a rule evaluation:

- **Sensory publication:** draw the trap; keep the hidden creature in the contacts.
- **Hazard layer and route search:** avoid what you know.
- **Action availability:** Disarm, loot hidden contents, target a hidden creature.
- **Player projection and world publication:** trap disclosure; container contents (this fixes the leak in study §2.3).
- **AI knowledge reduction:** it receives the same answer, so its view stops disagreeing with the rules.

Display memory stays in senses, for drawing a shape last seen out of view. It never answers the question.

## 4. How each existing setup fits

| Setup | Concealing condition | Acquired by | Study items it fixes |
| --- | --- | --- | --- |
| Traps, triggers, Spike Growth, gas vents, portals, jaws, the container needle | Its spatial condition | Notice, Search, Exposure | §2.1: the five decision places become one. The six "in senses memory" overrides and `detected_by` go. The DC stays after firing, and a re-armed trap is still hidden from those who never knew. The failed list is recorded, so there are no free retries. |
| Tile and object hazards (`BaseBlock.is_hazardous_for`) | The condition on the tile or object (the DC already lives on BaseCondition) | Notice, Search | §2.1 item 4: Search for Traps finds these too, and safe paths agree |
| Hidden hardware (`perception_condition_uuid`) | Delegates to its trap's condition, as today | Its trap's | §2.3: it inherits the fix |
| Hidden creatures | `Hidden` (the DC is the Stealth result) | Notice, Search action, Exposure (attacking ends Hidden, so the record ends with it) | §2.2: noticed stays noticed until it hides again |
| Searchable furniture | `SearchGate` | Search Body, Exposure (broken open) | §2.3: per finder or global becomes a choice about knowers. Publication reads the record, which closes the leak. |
| Seats | No condition of their own | A seat knows what any member knows, computed when published | §2.4: the seat view agrees with the rules. Explored cells (P18) are map knowledge, not concealment, so they stay a separate decision. |

The "world/dungeon" attacker (study §4.7) is not part of this system.

## 5. Where knowledge lives: three proposals

All three share §1–§4. They differ only in where the knower lists are kept.

### A. On the concealing condition (what the human asked for)

- **Data.** One small record replaces the existing `condition_stealth_dc` field on BaseCondition:
  - `dc`;
  - `known_by` and `failed_by`, both sets of knower UUIDs;
  - `exposed`;
  - a revision.

  The net core change is one field swapped for one field. The record's type and the `knows` rule go in a dependency-free leaf module, the same kind as `condition_types.py`.
- **Handlers.** The condition's own hooks apply the events in §2 (`on_noticed`, `on_searched`, `on_exposed`, retry clearance), in the same style as the existing `on_owner_opened` hooks. Subclasses stop overriding the knowledge rule; at most they decide when they are exposed.
- **Sensory changes:**
  - The settlement gains one step, before the hazard layer and the observations read knowledge. For concealed things in view, it compares the DC with the passive Perception it already holds. New pairs count as known for the rest of the pass, ride on the observer's sensory event, and reach `on_noticed` (§2, "One root").
  - The `discovered=` input to `get_spatial_observation` is removed.
  - The creature contacts mask gains an "already known" term: a per-settlement lookup over the few hidden targets.
- **One new piece of state on the knower.** A per-knower knowledge revision, an int bumped whenever any record adds that knower. Route caches use it as their key instead of the sorted `senses.spatial_effects` (gridmap.py:1014). Without it, "did anything this creature knows change" means asking every record.
- **ECS fit.** Concealment and knowledge are data of the component that conceals. The rule is a pure function. Removing the condition removes its knowledge with it, so nothing is orphaned.
- **Risks.**
  - Knowledge is spread across conditions, so "everything Brakka knows" means walking the concealed things in reach. The readers only ever ask that within reach.
  - A record is not a pydantic field cheat. It must be declared on BaseCondition, not attached with `setattr`.

### B. A central knowledge table

- **Data.**
  - Conditions keep only the DC and the exposure state.
  - One table maps each knower (creature or party, with a stable index) and each concealed thing (stable index) to a bit for "known" and a bit for "failed".
  - Parties are rows: a seat's knowledge is the bitwise OR of its members' rows, or a party row.
  - Explored cells (P18) could be another bit layer per knower in the same table.
- **Handlers.** The events in §2 write into the table. Conditions call it on removal to free their column.
- **Sensory changes.** As in A, plus the hazard layer can read a whole knowledge column in one array operation.
- **ECS fit.** A world resource, not a component. Knowledge leaves the concealing condition, which is the opposite of the ownership the human asked for. It is also a new system, and the content scope says no new systems.
- **Risks.**
  - Every removal path must free its column, or a stale index lingers.
  - Concealing conditions depend on the table's module, which is acceptable only if that module is a low leaf.

### C. Knowledge as conditions on the knower

- **Data.** A `Knows(thing)` condition on each knower for each concealed thing it knows, linked from the concealing condition so that forward cleanup removes it.
- **Handlers.** Each Notice, Search or Exposure is a condition application, with its event and log.
- **ECS fit.** Knowledge as a component of the knower is legitimate. But the question "who knows this trap" (needed for Exposure, seats and the AI) means scanning knowers, and each pair is a full condition object.
- **Risks.** Weight. See §6.

Not proposed: keeping knowledge in senses columns. It is the fastest to read, but it is exactly the split this study exists to remove.

## 6. Scaling: measured today, predicted for each proposal

**Method.**
- **Setup:** a 40×40 map and 6 observers with passive Perception 9 to 15. N hidden traps (half Spike Traps, half finite traps) sit at random cells with DCs 11 to 18.
- **Measurement:** 5 rounds, median, base and variant interleaved, under load 6.4. Scripts are in the session scratchpad (`trap_scaling.py`, `trap_scaling_memo.py`).
- **What each column is:**
  - **Refresh** recomputes all 6 observers' senses at once, as at encounter start or after a big map change.
  - **Move** is one creature walking 4 cells; every step settles senses. This is the most frequent cost.
  - **Fire** is one trap firing, which takes one settlement.
- **The "proxy" variant** reads passive Perception once per observer, not once per pair. It measures what it costs to take the Perception evaluation off the read path, which is what §1's rule does in all three proposals.

| Traps | Refresh ms, today / proxy | Move ms, today / proxy | Fire ms, today / proxy | Remembered pairs |
| --- | --- | --- | --- | --- |
| 0 | 62 / 61 | 35 / 34 | n/a | 0 |
| 10 | 83 / 77 | 37 / 34 | 2.9 / 2.2 | 18 |
| 50 | 105 / 89 | 48 / 37 | 4.6 / 2.8 | 71 |
| 100 | 129 / 115 | 59 / 47 | 7.2 / 3.8 | 137 |
| 200 | 178 / 137 | 79 / 50 | 12.3 / 5.6 | 248 |
| 400 | 282 / 193 | 121 / 64 | 21.6 / 8.5 | 504 |
| 1000 (linear extrapolation) | ~610 / ~390 | ~250 / ~110 | ~50 / ~18 | ~1,260 |

The two per-trap costs that don't change with the proxy:
- A rolled search is about 1 ms at every N.
- An action listing grows from 8 to 15 ms between 0 and 400 traps.

**Where each trap's cost goes today (the slope from 0 to 400 traps):**

- **Refresh:** 0.55 ms per trap.
  - 40% is passive Perception re-evaluated per pair.
  - Most of the rest is route search that avoids hazards (`_search_paths` is 0.149 s of 0.447 s profiled at 400 traps), plus the bookkeeping for each drawn effect.
  - That remainder exists because traps are hazards that get drawn and avoided. All three proposals keep it.
- **Move:** 0.22 ms per trap, two thirds of it passive re-evaluation inside route hazard probes.
- **Fire:** 0.048 ms per trap, two thirds of it passive re-evaluation.
  - Fire grows with the total number of traps, not just the one that fired. The settlement after a firing re-asks every hazard in reach, for every observer.

**Predictions.**

| | Read path (refresh, move, fire) | Cost of acquiring knowledge | Memory at 1000 traps |
| --- | --- | --- | --- |
| **A** | About the proxy column. A read is a set lookup (0.05 µs, against 12.7 µs today); passive Perception is read only at Notice, from the value the settlement already has. Possibly a little under the proxy, because a known pair skips the rule entirely. At 100 traps: refresh ~115, move ~47, fire ~4 ms. At 1000: ~390, ~110, ~18. | One write per pair, ever (504 at 400 traps). It is carried on the sensory event the settlement already emits: microseconds each, under 1 ms per game, with no extra event and no extra settlement. | Two sets per concealing condition, under 1 MB. Empty sets should default to a shared empty value. |
| **B** | The same as A on every read. The hazard layer can also read knowledge as one array operation, but the residual fire slope (0.016 ms per trap) is mostly the per-owner hazard-filter calls (ALL, ENEMIES), which B does not remove. A and B differ by less than 1 ms at 400 traps. | Like A: one bit set per pair. | Bits: about 6 KB for 50 knowers × 1000 things, plus the index maps. |
| **C** | Like A, if each knower keeps an index by thing. Without one, worse. | One condition application per pair: an estimated 0.2–1 ms each, so the same 20-trap reveal costs 4–20 ms (not measured). | One condition object per pair: about 1,260 objects at 1000 traps, likely several MB. |

**What this means for the sensory path:**

- **The proposals do not differ much in speed.** A and B both take the largest per-trap term (passive Perception) off every read and cost about the same. C costs more when knowledge is acquired.
- **The choice between A and B is about ownership and parties, not milliseconds.**
- **What stays the same at any N in A:** the settlement's acquisition step. It is one comparison per concealed candidate in view (the settlement already has every observer's passive Perception) plus a write per new pair. Hidden creatures add a lookup over the few hidden targets.
- **The cost that remains under every proposal:** about 0.33 ms per trap per full refresh, from hazard-aware routing and effect bookkeeping. If 1000-trap maps matter, that is the next thing to study. It is outside this problem.

## 7. Decisions for the human

Each question stands on its own. My recommendation is marked.

**Answered 23 October:** every recommendation was accepted except 12. Question 12 was decided as "the event, rooted in its cause, never a second sensory pass" (§2, "One root").

**Revised 24 October,** after a side agent noted that party members would still walk into a trap one of them had found:

- **Question 3: the knower is the party, which is the faction.** A creature with no faction is its own party. Failed searches stay per creature.
- **Question 4 (Point Out) is moot,** because the party shares what it knows.
- **Question 13 is replaced** by the human's framing: a route, built lazily as always, uses the party's view (cells any member sees or has explored) and the party's trap knowledge. What a creature physically sees, its range and its targeting stay its own.

- **Later on 24 October:**
  - Hidden things on tiles and objects join one model with two kinds: hidden presence and hidden nature. A trap is a special case of hidden presence.
  - Passive Perception notices hidden objects and secret doors.
  - One area Search replaces Search for Traps.
  - Hidden creatures come as the plan's last step.
  - A hiding creature, once noticed, is known only to the creature that noticed it, as in the SRD. Traps and objects stay shared with the party.
  - A communication system for sharing sightings is for later.

The plan is [PARTY_KNOWLEDGE_AND_HIDDEN_THINGS_PLAN_2026-10-24.md](plans/PARTY_KNOWLEDGE_AND_HIDDEN_THINGS_PLAN_2026-10-24.md).

1. **Where does knowledge live?**
   - **A (recommended):** on the concealing condition: the trap, Hidden or the search gate holds who knows and who failed.
   - **B:** one central table of knowers and hidden things.
   - **C:** a "Knows" condition on each knower for each thing.
2. **What is covered in the first pass?**
   - **Recommended:** traps, hazards, tile and object hazards, hidden trap parts and searchable furniture now; hidden creatures in a second pass, since that touches the creature-contact part of sensory.
   - Or: hidden creatures in the same pass.
3. **Who is a "knower"?**
   - **Recommended:** each creature knows on its own, and a player's seat shows everything any of its members knows.
   - Or: the whole party knows whatever one member knows.
   - Or: strictly per creature, including on the player's screen.
4. **Can a creature point a found trap out to others?**
   - **Recommended:** not for now. The seat already shows what its members found, so players are covered.
   - Or: automatically, to allies who can see or hear the finder.
   - Or: as an explicit "Point Out" action.
5. **Passive Perception against a DC: does a tie notice?**
   - **Recommended:** yes, the score only has to meet the DC, the same as a rolled search already does.
   - Or: no, it must beat the DC, as the passive rule does today.
6. **After a failed search, can the same creature search that same thing again?**
   - **Recommended:** one try per creature per hidden thing.
   - Or: one try per party.
   - Or: retry allowed once something changes: better light, a Perception buff, or a new round of exploring outside combat.
7. **A false back or hidden compartment found by one creature: found for whom?**
   - **Recommended:** for everyone. Finding it opens it, and the contents are then visible like any open container.
   - Or: only for the finder, until they point it out.
8. **A trap that fires: who knows it is there afterwards?**
   - **Recommended:** every creature that perceived it firing, and nobody else. When it re-arms it stays known to them and hidden from the rest.
   - Or: everyone, forever, as today.
9. **A trap re-armed or re-set by whoever built it: is it hidden again from those who knew it?**
   - **Recommended:** no, they still know where it is.
   - Or: yes, a re-set clears who knows it.
10. **A hidden creature that has been noticed: does it stay noticed?**
    - **Recommended:** yes, until it hides again with a new Stealth check (5e).
    - Or: no, it is re-checked at every settlement, as today: if the observer's Perception drops, the creature is hidden from them again.
11. **Can hiding fool blindsight and tremorsense?**
    - **Recommended:** no, within those senses' range hiding does not work.
    - Or: yes, as today.
12. **The first time a creature passively notices something: a direct call or an event?**
    - **Decided:** the observer's existing sensory event, rooted in its cause, carries the notice, and the condition's handler records it. It adds no new event and starts no second sensory pass (§2).
    - **Correction:** I had claimed a "hazard detected" log row is already produced at that point. It is not: `HazardDetectedLogData` exists as a type, but nothing in `dnd/` or `server/` creates one. The notice field would be its natural source, if the row is wanted.
13. **Explored map cells: should they belong to the party?** The case is a summon that explores and then leaves.
    - **Recommended:** leave it for later. It is about the map, not hidden things, and it is outside the content push.
    - Or: make explored cells a party fact now, so the summon's exploring stays usable.

Whichever proposal is chosen, its implementation plan gets an anti-slop reviewer and an anti-OOP reviewer, and a plan-adherence agent while it is built (AGENTS.md).
