# Antislop review: EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18.md

Reviewer: antislop (read-only). Worktree `/home/tommaso/.codex/worktrees/event-native-deltas/dnd_engine` at `f84729140`. Nothing was run. Paths are relative to the worktree.

The plan's cited lines hold: projection.py:808-811 (ItemChargeFact goes to the controller only), :1224 (connectors read from `world.world`), :1466 (the member's `visible_cells_added`); audience.py:161 (`owner_revision` join), :396-405, :711; capture.py:808, :877; sensory.py:2379-2403, :2516-2534; cause_occurrence == parent_event (sensory.py:606/608, the only constructor). The problems are in design and gating, not in the citations.

## Findings

**1. BLOCKER: remembered effect footprints are still published.**
- Plan text: §1 "publication keeps no remembered state"; §1 "Native behaviour is unchanged"; §3.8 "effect-footprint retirement when seen empty" (a client rule); E3 "Composed seat facts".
- Problem:
  - Native sightings keep hidden cells' last observation (sensory.py:2384-2399, "Hidden parts retain their last observation").
  - The seat composition merges the members' *remembered* footprints using last-seen cursors: `contact_cursors`, `effect_cursors`, `effect_absences` (audience.py:69-74, 94-117).
  - stateless/remembered.md §3a says this "directly contradicts the new rule".
  - The plan never says whether a published sighting is visible-only. It also never resolves revision-2 decision 7 / sensory R1 (the cursors), and the human never answered that one.
  - So §3.8's client retirement and the server's retained cells would both exist: two paths.
- Fix:
  - The projector publishes only the visible part of each composed sighting; the client owns retention (§3.8).
  - Either drop the cursors from the publication path or ask the human about them explicitly.
  - O1 compares effects on visible cells only.

**2. MAJOR: "attribution" is unconfirmed and has no wire design.**
- Plan text: §3.1 "every perceived thing keeps its attribution: the bits of the seat members who perceive it"; listed under "The decided rules".
- Problem:
  - The design doc records this as "the integrator's reading (to confirm)". The human's words were "which characters does what", which is ambiguous.
  - No unit (cells, contacts, effects, lights), encoding or byte estimate is given.
  - Exact per-cell attribution is the per-member visible masks, which are today's `fact.sensory` bit lists (16.0 / 60.7 / 164.3 / 45.9 KB in the census). That would cancel most of the 1−1/N saving from composing.
  - "Member A loses a cell member B keeps" is a new kind of keyed change that is not listed anywhere.
- Fix:
  - Confirm the meaning with the human before E3.
  - Specify the encoding, e.g. a member bitset per identity, and added/removed masks per member for cells, with an estimate.
  - O1 checks attribution against the server's member perception.

**3. MAJOR: O1 copies itself and cannot run on the head.**
- Plan text: "a snapshot built from the session fold by the same functions that build entering snapshots"; "written before the change and run on the current head".
- Problem:
  - The session fold and the snapshot builder are E3 code, so E0 (which allows no engine change) cannot run O1. It would have to write E3 code early or keep two builders.
  - A bug in the snapshot builder (a missing field, a wrong disclosure) appears on both sides. That is the old replica flaw (test_emitted_update_replica.py:84).
  - The restriction is "what the seat perceives". If that means the server's perceived set, a ghost object the client failed to drop is filtered out. Yet §5 relies on O1 for exactly that "touches the entered cells" risk.
- Fix:
  - Build O1's reference from the live engine at op end, passed through the disclosure functions (an independent producer).
  - Restrict to client-held records located in visible cells or keyed by perceived ids.
  - On the head, O1 must fail exactly on E1 bugs 1-4. List that expectation.

**4. MAJOR: O2 cannot fail.**
- Problem:
  - The spool stores the exact packets (server/recording.py:55-64), and live and replay folds call the same pure reducer.
  - The spool quota is 1 GiB per seat (server/config.py:33). That caps the "kept for the whole game" rule, and the plan does not mention it.
- Fix:
  - Replay through the transport resume path (sdk/python/src/dnd_player/transport.py `follow`) in a fresh process with a different PYTHONHASHSEED, from 0 and from mid-game.
  - Compare the whole client state, including out-of-view memory.
  - Measure spool growth on `long_game`.

**5. MAJOR: O3's base is undefined.**
- Problem:
  - Run on the head, O3 compares the head with itself.
  - After E1, the base must differ at the E1 bug sites.
  - Folding schema-15 recordings after E3 needs the old reducer, a hidden second path.
- Fix:
  - E0 stores the folded perceived states (per seat, per op) as data.
  - Re-record after the E1 merge, and list the expected differences.

**6. MAJOR: E1 ∥ E2 is wrong, and E3 deletes some E1 fixes.**
- E1.1's fix ("built from the engine fold's own case") is E2's `ActorChange`, so E1.1 depends on E2.
- E1.6 fixes `acquired` (capture.py:808, 877), which E3 deletes.
- E1.2's fix is rewritten in E3, because E3 deletes `_holdings` and `EquipmentFact`.
- E1.5 is harmless under today's diff (stateless/world.md §2), so no failing-first test exists for it.
- E1.7 was "not reproduced", and E3 removes client composition anyway.
- Fix:
  - E1 = fixes 3 and 4, which are preconditions that survive E3, plus failing-first tests for 1 and 2 that turn green in E3.
  - Move 5 into E3. Drop 6 and 7; O1 on G1 covers them.

**7. MAJOR: E3 has an escape hatch, and there is no E4.**
- Plan text: "if that is too large for this phase, it is logged as its own step".
- Problem:
  - The same phase reads "the session fold as of the occurrence", which needs event-major projection (stateless/world.md §5.7).
  - Leaving the per-seat `ProjectionState.world` in place means 30 world folds on G2, which is exactly the layout the ms gate uses.
- Fix: decide now. Either event-major projection is sub-phase E3a, gated on G2 ms, or it is a named E4 with its dependency stated.

**8. MAJOR: E2 contradicts itself and adds a second sensory path.**
- Problem:
  - E2's header says "engine events gain fields; nothing else changes", but `ActorChange` is built in `advance_capture` (capture code), while the gate says "capture unchanged".
  - Lights and effects that "become" added/patched break the N5 consumers (the AI knowledge reducer, audience, capture, recordings). Adding patches beside the whole rows duplicates retained events instead.
  - For composed seats the wire needs the composed before/after, which audience.py:736-758 already holds. Native member patches are therefore a second path.
  - The study keeps `remove_previous_item_holdings` "as the fallback" for the previous holder.
- Fix:
  - Compute composed patches in the projector (one path for G1, G2 and G3), and drop the native sensory patches.
  - Pick one source for the previous holder.
  - E2 gate: published updates byte-identical (`gallery_transcript.py compare`), and events identical under a representation that drops the new fields.

**9. MAJOR: the out-of-scope combat log is changed silently.**
- Problem:
  - E3 deletes `remembered.actors` / `.connectors` and "the permanent known set". These feed the log's `known_entity_names` and `known_connector_uuids` (application.py:67, 73-74, 83-84).
  - "Connector names in the log" is still open with the human.
  - §3.5's envelope cut can reach `CombatLogAppend` (sensory study §2 #1).
- Fix:
  - Rebuild the log's inputs from the static-sent set and the connectors visible now.
  - Gate: combat-log appends byte-identical through E3, on every layout.
  - Leave `CombatLogAppend` alone.

**10. MAJOR: the human's targets are never a gate.**
- Plan text: E6 "Report every row over 100 ms or 100 KB".
- Problem:
  - Nothing in the plan can fail on the targets.
  - Fireball's largest update is 197 KB, with the combat log at 25 %. The design doc estimates about 140 KB with the log left out of scope, and the plan does not say this.
  - "ms" is undefined: which timer, whether it covers every seat, and whether it includes the client fold ("total cost counts").
- Fix:
  - Define the metrics: the maximum encoded `PlayerUpdate` per seat, and op `total_ms` including every seat's publication plus the reference client fold.
  - E3 gate: no G2 row regresses against E0.
  - List the known over-target rows and who owns each (the log belongs to the human).

**11. MAJOR: "sweep 0 new" is impossible.**
- Problem: about 70 test files reference fields the plan deletes or reshapes, e.g. tests/player/test_projection_local_world.py ("preserve remembered geometry").
- Fix:
  - E0 lists the tests whose expected output changes by design, each with the rule clause that justifies it (HOW_TO_TEST).
  - The gate becomes "0 unlisted failures".

**12. MINOR: E3 is one mega-lane.** It covers world, bodies, sensory, the restatements, the session fold, the client and the SDK. Split it by family, with O1 per family.

**13. MINOR: the root-only spell declaration has no parity argument** (sensory study R6). A child disclosed under a withheld root loses its declaration. Either put the declaration on the group's first disclosed node or prove parity.

**14. MINOR: missing deletions and one undecided field.**
- `LightRow.revision`, `owner_revision`, `light_removal_revisions` and the dead `affected_tiles` are not listed as deleted, although §3.7 exists to stop leaking counts.
- `seen_cells_added` must be either on the wire or derived by the client (§3.8), not both.

**15. MINOR: wrong framing of what is decided.**
- "The one declared exception … in RULE_VIOLATIONS": the human has not decided the HUD, and RULE_VIOLATIONS_2026-10-18.md is the getattr/isinstance census. Write "unchanged, pending the decision".
- §1's per-seat state list omits the HUD snapshot, the numbering maps and the cursors.
- "Defaults … logged": list the defaults taken (static once per seat, packed columns, `SLOT_LINEAGE` exact or cheap).

**16. MINOR: the baseline matrix is too broad and partly broken.**
- "Every case × 3 layouts × 3 runs" is about 300 processes, including `long_game`, and memory says to ask before new probes.
- G2 breaks `seat == 'blue'` (gallery_crowd.py:866, 913).
- Name the case list instead.

**17. MINOR: an estimate is stated as fact.** "The room re-entry case is the new worst case, mostly wall placements" is a stateless/world.md §6 estimate.
