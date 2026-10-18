# Remembered state and reconnect under stateless publication (read-only design note, low priority)

Tree: `/home/tommaso/.codex/worktrees/event-native-deltas/dnd_engine`, HEAD `9397ebca6`. That is one docs commit after `55bf034cc`, which the study docs cite. Nothing was edited, run or measured. Byte and time figures are estimates from the progress log, not probes.

Frame (decided, revision 2 plus the human's answers):

- Publication is stateless. A thing perceived before and after an event gets the event's change. A thing entering perception gets its current state. A thing leaving perception gets nothing.
- Reconnect is "the same as having been there from the start": journal replay of the seat's spool.
- "Remembered" is client memory: the explored map, last known positions, discovered traps.
- The engine keeps only the explored mask, the discovered effect ids and the turn-scoped collisions.
- The server AI keeps its own fold.
- Remembered-cell pathfinding is deferred.

---

## 0. Answers in one page

1. **Client memory plus journal replay is already the shape of the system.**
   - Record 0 is the initialization and every operation is one numbered spool record (worker.py:96-101, 199-224).
   - A fresh client reads `/initialization` and then `/events?after=0` (app.py:181-189, 233-283).
   - It cannot submit a command until it has acked the catch-up cursor (host.py:222-223, 276-277). So "same as from the start" is enforced today.
   - What changes is the client's fold: it must own four memory rules and apply them deterministically.
   - The hard part is not determinism. It is **absence**. For each remembered keyed collection, the wire must say which keys or cells are authoritative at an event. Otherwise "not perceived" and "perceived and gone" look the same, and two folds can disagree.
2. **There is a cheaper path that stays exact: client-side persistence**, with journal replay as the fallback.
   - It needs one small server change: a *new* attachment cannot resume after a cursor today. It starts at `highest_sent = -1` (host.py:33, 175-176), and `/events` refuses `after > highest_sent` (app.py:236-237).
   - A server-side "seat memory snapshot" (the reference fold over the spool up to k) is exact only for clients that run the reference fold. It also brings the deleted mirror back as a wire type. Don't build it unless measured replay time forces it.
3. **The server AI's memory is already "replay from the start".** Each assignment opens with a cold fold of the whole native history (knowledge_system.py:56-63). This includes summons opened mid-game (summoning/system.py:362, 518).
   - It needs nothing on a restart *if* the native history is restored.
   - It breaks, and does more than forget, if history is pruned or a save omits it: its objective world and actors are folded from cursor 0.
4. **The engine's rule memory** is `Senses.seen`, the discovered effect ids and the collision layers.
   - There is no save/load today. A server restart ends the game: the engine lives in the worker process and the spool index is in memory.
   - When save/load comes, an event-sourced restore rebuilds all three exactly.
   - A model-dump state save would silently drop `seen` and the collision layers, which are `exclude=True` (sensory.py:94-95, 113-121).
5. **Recommendation:**
   - keep journal replay as the normative path;
   - specify the client memory rules, with their authoritative domains, as protocol, and check them with golden vectors;
   - add client persistence plus resume as the fast path;
   - defer server snapshots;
   - keep the engine memory per character;
   - measure spool bytes and fresh-client replay time on the long game, after asking the human.

---

## 1. Client-owned memory and journal replay

### 1a. What exists

- **Spool.**
  - One file per seat. Each frame is a 4-byte length plus the exact JSON bytes (recording.py:31-45, 56-66).
  - The offsets are kept in memory only (`AudienceSpool.offsets`, recording.py:21).
  - The default quota is 1 GiB per seat (config.py:33), out of a 64 GiB service budget reserved per game (config.py:21, service.py:40).
  - At the quota, delivery is blocked (`has_capacity`, recording.py:47-51; host.py:145, 282-283).
- **Records are written only when the seat has something to receive.** Choices and previews write no record. An operation is skipped for a seat when it has no lineages, log, content, HUD or boundary change (worker.py:203-205).
- **Fold.**
  - `reduce_initialization` and `reduce_operation` (reduction.py:552, 654) are pure functions of the bytes.
  - Each operation copies the whole state first (`copy_target`, reduction.py:119), so replay costs O(ops × state).
  - The SDKs ship no fold: "Consumers own reduction". The Godot fold is outside the repository.
- **Content.** Descriptors arrive inside the records (`content_additions`) and through `/content/{revision}`, which is held as `host.content` (app.py:221-227). Both are replay inputs.

### 1b. The memory rules that must be deterministic

Each rule is a pure function of the committed facts in occurrence order. Each one names its **authoritative domain**: the places where absence on the wire means "gone".

1. **Explored map: `seen_m |= visible_m`, per member, after every sensory fact.**
   - Union is commutative and idempotent, so granularity cannot change the result, provided every intermediate view is folded. A corridor seen mid-move is in the step facts.
   - It must be kept **per member**, not only as the seat union (audience.py:423). The deferred "allow a remembered Move target" rule checks the *moving character's* own `Senses.seen`. A client that shows the union would offer targets the engine rejects.
   - The engine ORs exactly its visible cells (sensory.py:1808-1812). Per-member client seen therefore equals the engine's mask by construction, as long as the composed view keeps exact per-member attribution (human answer 1).
   - `initial` must carry visible cells only. Today it sends the whole seen layer (sensory.py:404-414).
   - `seen_cells_added` (events.py:3378) can then leave the *player* wire. It stays in the native event for the engine and the AI.
2. **Object forgetting.**
   - Rule: a remembered object is forgotten at an event where one of its remembered positions is visible to the seat and the seat does not observe it.
   - It must be judged **per event, against the view at that event**, as the projector does today (projection.py:1210-1213), not once per operation.
   - Risk: the server's grant rule `_object_observed` (projection.py:1001) also grants boundary objects through an adjacent visible support cell. The client's rule and the engine's contact rule must coincide on edge objects (walls, doors). Either:
     - ship the edge geometry as shared code, or
     - (simpler) have entering cells carry the uuids of the objects observed there, so absence is explicit.
3. **Wall-face merge.**
   - Rule: an observed face replaces the remembered face, and unobserved faces are kept.
   - The update must list every observed face, **including faces that are now empty**. Otherwise a visible face that was cleaned cannot be told apart from a face out of sight.
   - Today the server does this merge (`_observed_object`, projection.py:1022-1065).
4. **Effect footprints.**
   - Rule: a remembered cell of effect e is retired when it is visible and e's current sighting lacks it. The effect is forgotten when its footprint is empty.
   - Under the stateless rule the engine publishes current sightings only, so this becomes client code: the audience.py absence logic (audience.py:76-110, 629-671), which is already shared.
5. **Bodies**, already client memory (reduction.py:172-179, 382-418):
   - kept on contact loss;
   - the last position changes only on a visual contact;
   - entering view replaces the body whole, conditions included;
   - a terminal body is never resurrected.

Other determinism conditions:

- **Fold every committed fact in occurrence order.** Presentation folds of timed partial groups (`reduce_nodes`, "including a timed partial group") must never write memory.
- **No order-dependent iteration over unordered sets.** Python string hashing is randomized per process. Godot dictionaries keep insertion order. Any ordering that reaches state, such as condition order, must come from the wire.
- **Memory rules are versioned with the protocol, not with the client app.** Every record carries `protocol_identity()` (worker.py:97, 212). A client updated between sessions replays old bytes with its new fold, which is still "as if from the start" for that fold. Conformance is checked per protocol.
- **Cross-implementation conformance.** The Python reference fold is the specification. Golden vectors are pairs (gallery spool, reference memory at record k). The Godot fold must reproduce the memory part.
- **Oracle:**
  - `fold(0..n) == fold(state_k) ∘ fold(k+1..n)` for persisted states;
  - per-member client `seen` == engine `Senses.seen` at each op end, which is also the deferred pathfinding guard.

  This is projector_state.md §3 O2/O4, rebased on the client fold.

### 1c. What the spool must keep, and its growth

- **What it must keep:**
  - every record from 0, uncompacted, for the whole game (human answer 4);
  - the content catalog at its revision;
  - the protocol identity per record.

  Nothing else: the fold needs no server state.
- **Sizes from the progress log:**
  - initialization up to 5.2 MB for the largest seat (progress :200);
  - end turn about 6 KB;
  - spell ops 50–250 KB (progress :432, :517).

  Revision 2 adds re-entry bytes (about 12–23 KB per room re-opened) and removes sensory restatements. The net is unknown.
- **The long game** (about 8,300 requests, the caller's figure; queries write no record). At a blended 10–30 KB per record that is at most **about 80–250 MB per seat**. That is under the 1 GiB default, but a game 4–10× longer reaches it.
  - "Kept for the whole game" makes the quota a game-length limit.
  - This is already true today, since the spool is already kept whole.
- **Server memory:** the offsets list is about 70 B per record, so under 1 MB. Negligible.
- **Fresh-client cost:**
  - it downloads the whole spool (64 KiB chunks under delivery credits, app.py:141-155) and folds about 8,000 operations;
  - the client cannot act until it acks the catch-up cursor;
  - the order is tens of seconds to minutes late in a long game. This is unmeasured.
- **Cheap lever, exact:** compress the records (per record or HTTP). JSON with repeated keys shrinks several-fold. This changes download size, not fold time.

---

## 2. Cheaper exact alternatives

### 2a. Client-side persistence (recommended fast path)

- **Mechanism.**
  - At each op end, or every N ops, the client stores `(fold state, cursor, acquisition_id, game_epoch, audience_id, protocol)`.
  - On restart it loads that state and streams after its cursor.
  - It is exact by construction: it *is* the client's own fold.
- **Server side.**
  - The same acquisition id keeps the attachment and its `highest_sent` (host.py:169-171), so resume works today if nobody replaced it.
  - A replaced or new attachment starts at `highest_sent = -1` (host.py:33, 175-176), `/initialization` raises it only to 0 (app.py:188), and `/events?after=n` is refused for n > `highest_sent` (app.py:236-237). The client must then replay from 0.
  - The change: let a new attachment declare a resume cursor ≤ the published head. `check_cursor` already validates the epoch and audience (host.py:197-204). Catch-up gating stays as it is.
- **Format.** The client's state format is private to each client, so nothing becomes protocol.
- **Failure.** If the stored state is missing or corrupt, or its epoch, audience or protocol does not match, the client falls back to journal replay.

### 2b. Server-side seat memory snapshot (fold of the spool up to k)

- **Mechanism.** Run the reference fold over spool records 0..k and send the result as a new record kind. The client loads it and streams after k.
  - The fold needs no engine ("without native event projection", reduction.py:1).
  - The host already imports `dnd.player` for the wire schema (server/protocol.py:11-17), so running the fold outside the game worker adds no new kind of import edge.
- **Exactness.** It is exact by construction **only for clients whose fold is the reference fold**. A Godot fold would have to load the reference `PlayerState` shape. That makes the whole fold state protocol, including its internal cursors:
  - `reducer_cursor`;
  - the perception members;
  - the contact and effect cursors, and `effect_absences`;
  - `spatial_commit_cursors`;
  - the HUD and the combat log.

  That is the deleted mirror, back as a wire type.
- **No compaction in today's vocabulary.** Remembered, out-of-view things have no "entering" form: they are not perceived. A compacted journal therefore needs a new message kind anyway.
- **Is it a per-seat copy?**
  - On demand (built, sent, dropped): no. It is transient, derived and off the publication path.
  - Cached checkpoints every N records on disk: yes. It is a per-seat copy of client values (the mirror moved to disk). It is deletable and recomputable, but still a copy, so it needs the human's explicit OK.
- **Cost.** One full replay of server CPU per reconnect, in exchange for MBs instead of hundreds of MBs on the network.
- **Verdict.** Build it only if fresh-client replay is measured too slow *and* the slow clients use the reference fold.

### 2c. Rejected

A current-perception-only snapshot (revision 2 option (a)) is not exact: it loses the explored map, which violates human answer 4.

| Path | Exact | Server state | New protocol | Cost |
|---|---|---|---|---|
| Journal replay from 0 | yes | none | none | download + fold O(history) |
| Client persistence + resume | yes | none | resume cursor on a new attachment | client storage (MBs) |
| Server snapshot on demand | reference-fold clients only | transient | client state as a wire type | server CPU per reconnect |
| Cached server checkpoints | reference-fold clients only | per-seat copy on disk | same | disk; needs the human's OK |
| Record compression | yes (transport) | none | encoding | CPU per record |

---

## 3. The server AI

- **Memory.**
  - `AIKnowledge` folds the unredacted native `EventQueue` (knowledge_system.py:37-39).
  - It is opened by a cold fold from cursor 0 (knowledge_system.py:56-63) at assignment start (assignment.py:173).
  - Summons open assignments mid-game (summoning/system.py:362, 518), and each of those cold-folds the whole history.
  - It is a pure fold "without world queries" (knowledge_reduction.py:1). A test replays it from audience-retained events with identical results (tests/ai/test_event_knowledge.py:97-121).
  - So the AI already lives by the human's reconnect rule, over the native stream.
- **Server restart today.**
  - Nothing survives. The engine is in-process and has no save/load.
  - A new host makes a new epoch and a new spool directory (host.py:96-99; recording.py:31-32, `exist_ok=False`).
  - The spool offsets are in memory. The frames are length-prefixed, so a linear scan could recover them.
  - So a restart ends the game. The AI question becomes live only when save/load exists.
- **With save/load:**
  - **Native history restored:** the AI needs nothing; the cold fold rebuilds it exactly.
  - **State snapshot without history** (likely if the memory refactor prunes `EventQueue`): the AI does not just forget, it starts blind. `world` and `actors` come from births and world facts since cursor 0 (knowledge_reduction.py:195-221). It then needs either:
    - its own checkpoint, the client-persistence pattern; or
    - a synthetic initial entry from current state (objective world plus current senses, like `initial` sensory events), accepting the loss of REMEMBERED hostiles.

    The loss is small. Only `basic.py:858-897` (approach last-known hostiles) and the content-pack tactical focus read AI memory.
- **The same pruning risk exists at runtime.** A mid-game summon cold-folds from 0, so a pruned history breaks it the same way. Its cost is also O(history) per summon. That belongs to the memory refactor.

---

## 4. What the engine must remember for rules, and save/load

- **M1. Explored mask `Senses.seen`.**
  - Declared at sensory.py:94-95, OR-ed at 1808-1812, never cleared.
  - Per character, and it is the route domain.
  - It also drives the deferred "remembered Move target within movement distance" check.
- **M2. Discovered effect ids.**
  - Today it is the whole `Senses.spatial_effects` with footprints (sensory.py:97-99; retention 2384-2408). The rules read only its keys.
  - Under client-owned footprints it becomes an id set. The current sighting still uses it as the discovery gate (sensory.py:2346).
  - Today an entry is dropped only when every remembered cell is re-observed empty (2401-2402), which needs the footprint. With ids only, drop the id when the effect ends objectively. This is engine-internal: no rule can read a removed effect, so nothing leaks. The path-cache signature (gridmap.py:1004) just changes.
- **M3. Collision layers** (sensory.py:113-121).
  - Cleared at turn start (encounter.py:887-898).
  - Live at a save point, because the human-input boundary is mid-turn.
- **If R-bits pathfinding is chosen later:** one byte per explored cell per character. Engine "what" memory, under the same save rules.
- **Save/load does not exist.** When it comes:
  - **Event-sourced restore:** all three are folds of native events: sensory updates (visible and seen cells), spatial effects changed or removed, and movement-collision events since the last turn start. They rebuild exactly, and so do the AI and the spool's continuity.
  - **State save:** it must list M1–M3 explicitly. `seen` and both collision layers are `exclude=True` on the pydantic model, so a `model_dump`-based save drops them **silently**. Routes would collapse to visible cells and an invisible blocker would be retried. `spatial_effects` is not excluded, so it would be saved whole, footprints included.
  - **A test** comparing route sets before and after save/load catches both cases.

---

## 5. Risks

1. **The memory rules become protocol** (§1b), with two implementations, Python and Godot. Each rule needs its authoritative domain on the wire: observed faces including empty ones, and observed objects at visible positions. Otherwise the folds diverge silently.
2. **Granularity.** Forgetting is judged per event against the view at that event. A fold run per operation is wrong.
3. **The spool quota caps game length** (1 GiB per seat by default; at the quota, delivery is blocked). Long campaigns need a larger quota, compression, or the human's OK for checkpoints.
4. **Fresh-client replay time grows linearly**, and the client is blocked until it catches up. Unmeasured.
5. **Resume on a replaced attachment is refused today** (`highest_sent = -1`). Client persistence across devices needs the small server change in §2a.
6. **A server restart loses the game today** (no engine save/load; the spool index is in memory). "Reconnect after a restart" waits on save/load.
7. **Pruning `EventQueue`** (the memory refactor) breaks the AI's cold folds, at restart and for mid-game summons, and any event-sourced save.
8. **A pydantic-dump save drops `seen` and the collision layers** (`exclude=True`).
9. **Server snapshots** bring the mirror back as a wire type and force the reference state shape on every client.
10. **Per-member versus union seen.** If the client keeps only the seat union, the deferred Move-target rule offers cells that the moving character never saw.

## 6. Recommendation

1. **Normative reconnect: journal replay from 0.** It exists, is exact and keeps no server state. Keep it as it is.
2. **Specify the client memory rules as protocol:**
   - per-member `seen |= visible`;
   - object forgetting per event, with explicit observed objects on entering cells;
   - the wall-face merge, with every observed face listed, empty included;
   - effect cell retirement;
   - bodies as today.

   Check them with golden vectors from the reference fold over gallery spools, and with the oracle in §1b. Drop `seen_cells_added` from the player wire once the rule is in place.
3. **Fast path: client persistence plus resume after a cursor.** The server change is a resume cursor on a new attachment. Falling back to replay keeps it exact.
4. **No server snapshots or checkpoints now.** Revisit only if fresh-client replay on the long game is measured unacceptable and the slow clients use the reference fold. If built: on demand, off the game worker, transient.
5. **Engine:**
   - M1 per character;
   - M2 as ids only, dropped on objective removal;
   - M3 as it is.

   Any future save/load must carry all three. An event-sourced save gets them for free, together with the AI and spool continuity. A state save must list them, because of the `exclude=True` trap.
6. **AI: nothing now.** If save/load or pruning removes history, add an initial-from-current-state entry, accepting the memory loss, or checkpoint `AIKnowledge`.
7. **Before deciding (3) or (4), measure** spool bytes per seat and fresh-client replay time on the long game. This is a probe, so ask the human first.

Any plan built from this note needs the AGENTS.md antislop and antiOOP reviewers.
