# Playable encounter recovery: diagnosis and implementation plan

Date: 2026-10-06. Status: base design and engine/startup audit amendment independently approved; implementation resumed by the human. See the review receipt in section 14.

## Latest October 7 direction — design before further migration

The human subsequently paused the pygame/OpenGL implementation and requested a
deep design for a direct NeuroClient/PixiJS port and narrow replacement server.
The [current network/Studio plan](NETWORK_SERVER_NEUROCLIENT_STUDIO_PLAN_2026-10-07.md)
changes the proposed delivery platform. All P01–P31, prior UI constraints, native
performance work and acceptance requirements here remain required. The exclusions
below concerning TypeScript and broad renderer migration belong to the earlier
authorization; the new planning request does not itself start implementation.

## October 7 rendering amendment

The human rejected continued small CPU fixes and requested a first-principles
pygame-ce/OpenGL and asset-preloading solution, with shader reuse by a later
PixiJS client. The [full GPU migration addendum](GPU_RENDERER_AND_MEDIA_READINESS_2026-10-07.md)
governs sections 5–6 and step 3's rendering/preparation implementation, including
all world/creature/spell/UI families, resource preparation, picking, export and
removal of the CPU compositor. Its G0–G8 packages include measured transparency,
resource and input gates before production cutover. Both independent plan and
implementation reviews are required. Packing repair precedes memory-budget
selection; the human explicitly retains 32 FPS and also requests a full audit
of spell playback speed, independent of the number of exported frames.
All complaints and native-engine/UI acceptance below remain required; this is
not a replacement of the complete recovery with a graphics demonstration.

## 1. Scope and authority

The deliverable is a responsive, understandable Lantern Crypt encounter with the fixed Fighter/Sorcerer party. It must retain exploration, traps, loot and the authored goblin encounter, show everything witnessed by that controlled party, and make clicks, routes, resource use and animations agree. A gallery of working spells is insufficient.

This plan supersedes earlier claims that the current player UI is complete. The human has authorized implementing this reviewed repair plan. Existing uncommitted changes remain provisional. This document does not authorize new art, new spells, an AI redesign, campaign/save infrastructure, multiplayer, a TypeScript migration or a broad `/game` rewrite. It preserves portable presentation data and the existing combat log. No separate narrative renderer returns.

The [complaint ledger](audits/PLAYER_PLAYTEST_REPAIRS_2026-10-06.md) retains P01–P31. The [earlier UI report](audits/PLAYER_UI_REPAIR_2026-10-06.md) records the preceding layout and environment requirements; its per-character map-switching contract is explicitly superseded by P26. This plan includes those prior requirements as regression gates, without restarting artwork production.

**Completion means every P row has native, presentation or live-input evidence appropriate to its boundary, both independent implementation reviews pass, and the real app meets the performance gates.** Passing tests or source review alone cannot certify usability or visual quality. Any remaining gap must be named, not counted as completion.

## 2. What is actually wrong

There are several connected causes, not one bad cache or a slow operating system:

1. **The application equates the active actor with the viewer.** It keeps separate projections and switches maps/history when turns change. This explains disappearing battles, missing witnessed enemy actions and some missing portraits. The player's audience must be independent of the acting creature.
2. **The apparent asynchronous loop performs expensive synchronous operations.** Native discovery, commands, AI decisions, capture, projection and media preparation run in the SDL loop. An `await` after this work does not keep input or animation responsive while it happens.
3. **Drawing repeatedly copies and computes per-pixel masks.** Existing media caches do not remove repeated alpha extraction, wall cutaway and selection composition. Camera panning exposes this every frame. Some provisional fixes add more work.
4. **Input modes and native choices are insufficiently coherent.** Unavailable choices can lead into targeting, self-actions get unnecessary confirmation, and UI gestures can be confused with world commands. Haste variants expose internal resource alternatives as duplicate verbs.
5. **Visible geometry, interaction geometry and effect disclosure have diverged.** Walls can hide clickable doors; grid is an overlay instead of a ground layer; native affected tiles have been used as a stencil for continuous artwork. These need common boundaries, not per-spell/per-camera exceptions.
6. **Some genuine domain and event defects also exist.** Ally transit permission was missing. Door reach inherited full-tile assumptions. Event-time identity can be lost after death. These belong to native owners, not renderer workarounds.

### Evidence and its limits

Evidence is under `.runtime/ui-repair-20261006/path-check/`, outside version control. Relevant files: `profile_play.py`, `profile-current.log`, `profile.txt`, `windows-profile.log`, `windows-stable.log`, `door-cameras.py`, `door-cameras.json`, `probe.py`, `probe.json`, `fireball-probe.py`, `identity-focused.log`.

| Measurement / reproduction | Observed result | What it establishes |
| --- | --- | --- |
| Bounded WSL run, 2560×1440, SDL dummy, 35 frames | Imports 5.89 s; session 506 ms; animation metadata 4.40 s; first scene media 451 ms | Startup has several distinct costs. It does not establish how much is caused by `/mnt/c`. |
| Same bounded run | Median draw 24.4 ms; sampled playback 2.1 ms; HUD 1.0 ms; first draw 315 ms | Drawing alone already exceeds a 60 Hz frame budget in this sample. These are not real-screen frame percentiles. |
| Five cProfile draws | 861 `array_alpha` calls; pixel copying 78 ms cumulative; cutaway 54 ms; interaction composition 23 ms | Repeated masks are a measured hotspot. These cumulative figures overlap and must not be summed. |
| Earlier native Windows sample | Median draw 27.4 ms; metadata 3.34 s; scene media 636 ms; imports 21.27 s | Native Windows has not demonstrated better drawing performance. The sample followed a separately logged Application Control failure and lacks matched repeated conditions; that does not prove security policy caused its import duration. |
| Four actual camera draw/pick outputs | Vault door selectable pixels: 0, 5692, 5662, 0. Passage door: 0, 0, 5709, 5662; both known in every case | Camera-dependent door picking is reproduced, not hypothetical. Numbers describe this provisional tree only. |
| Fireball breach probe | Door art exists before authored clearance, but its retained `blocked_channels` is already empty | Removing the tile stencil exposed a separate before/after-state timing defect. Restoring the ugly stencil is not a repair. |
| Live dice source and recorded screenshot | Native attack constructs 1d20, live launcher has no fixed seed/faces; log shows a short low-roll streak | No RNG defect established. Recorded roll transport still deserves an exact comparison; changing luck would be wrong. |

The profile script forces a `.016` simulation delta and changes the camera supplied to drawing. It does not exercise actual WASD event routing, display presentation, combat resolution or a long session. Its numbers locate work; they cannot certify smooth play. Earlier before/after samples lack a sufficiently strict source/configuration manifest for a strong paired speedup claim.

One new opportunity-death test reaches a privacy assertion that assumes a spare creature cannot see the victim. That assumption fails; pytest then spends excessive time recursively formatting the native object graph. The observed test stall is **not** evidence that the gameplay operation hung. The test is not passing, and its privacy fixture must be corrected without weakening the required privacy behavior.

### Mandatory engine and startup regression audit — human clarification

The human explicitly challenges whether accumulated features and fixes have made the engine itself slow. **Engine performance has not been cleared.** The current short renderer profile and one small session/discovery timing cannot establish native performance across combat. Investigate this before treating worker isolation or renderer optimization as sufficient remedies. Startup is a first-class defect, not background polish.

Step 0 must produce a measured cost breakdown through the actual launcher and through bounded native-only operations:

| Boundary | Measure | Regression hypotheses to confirm or reject |
| --- | --- | --- |
| Interpreter/module imports | Per-module import time and repeat cold/warm runs, matched environment | Growing static dependency graph, repeated registration/materialization or import-time data reads. No late-import workaround. |
| Content bootstrap and encounter construction | Separate registry/catalog construction, validation, creature/item construction, deployment and initial sense/light updates | Whole-library work repeated per entity/session, redundant deep validation/copying, startup updates emitted one at a time when existing batching is appropriate. |
| Asset startup | Files/bytes read, JSON parsing/validation, rig/bundle assembly, image decode/conversion and first frame | Reading unused assets or validating the same data repeatedly; distinguish CPU work from filesystem wait. |
| Discovery / targeting | Actual normal turn and Sorcerer discovery, unchanged repeated query, changed state and ordered-target previews | Cartesian growth across abilities/variants/targets, repeated area/path calculations, missing or over-broad invalidation. |
| Movement / doors | One step, ordinary legal route, ally passage, opening a door | Recomputing paths, sight, lighting or navigation for unaffected actors/cells; unnecessary per-step reconstruction. |
| Attack / spell / enemy decision | Ordinary attack, reaction/death, Scorching Ray and Fireball; isolate native decision cost from execution | Handler scans/callback cascades, repeated modifiers/condition queries, propagation work and rule evaluation. This is profiling current AI, not redesigning it. |
| Event retention / public capture | Native event versions/callback counts, copying/serialization bytes, projection work, early/late equivalent operations | Extra events or copies added by fixes, repeated traversal of growing history, unnecessary observer multiplication. Preserve required causal phases and recorded results. |

Reuse `dnd/action_timing.py` and existing action, grid/FOV and EventQueue timing hooks. Supplement with bounded sampling/profiling where an uninstrumented stage is material; do not create a telemetry framework. Report call counts and exclusive/inclusive costs separately so nested timings are not added twice. Profile with optional video/frame/diagnostic export disabled first, then measure its incremental overhead explicitly. Required native EventQueue retention/subscribers and normal player capture/projection remain active in the actual-launch baseline; the separately labelled native-only lane isolates their costs without claiming equivalent full-app performance.

Compare the current dirty snapshot with compatible earlier commits using the same Python/dependencies, scene, scripted native commands, asset inputs and deterministic test-only seed. Record the exact revision and fixture differences. Use isolated temporary snapshots; never reset the shared working tree or attribute a speedup to missing features/assets. Commit titles such as “cleaned up rendering” are not evidence of a fast baseline. If a historical revision cannot run the equivalent workload, report that limit and compare the compatible native operations; do not spend the repair rewriting old releases.

Use small controlled fixtures to vary only the suspected dimension: active actors, visible cells, conditions/handlers, offered abilities and retained history. Features absent from that scene should not force repeated heavy work merely because their content is installed. Diagnostic variations omit features from fixture construction; they must not silently disable live rules or subscribers to obtain faster numbers.

Deliver a ranked startup/native hotspot table with source owner, current cost/call count, comparable earlier cost where available, correctness obligation and smallest proposed removal of repeated work. Proven native regressions become explicit repairs in their existing owners before worker scheduling can be accepted. Do not add another cache until the repeated computation, stable key and invalidation are established. Neither a responsive loading screen nor a responsive window while a five-second command runs counts as resolving the underlying delay.

## 3. Complete complaint coverage

States below refer to the current uncommitted tree. “Candidate” is not “accepted fix.”

| ID | Cause / current confidence | Repair and decisive acceptance |
| --- | --- | --- |
| P01: doors/corner movement | Door revision invalidation exists; initial probe refreshes paths. Missing ally traversal is confirmed. Exact two-door failure has not yet been reproduced completely. | Use the actual two-door route with ally in passage; compare discovery epoch, chosen route, committed steps and native termination. Fix native occupancy/topology dependency, not a frontend reroute. |
| P02: preview versus actual path | Both paths use `prefers_safe_movement_path`; native dispatch retains the discovered route. | Show that exact route and affordable endpoint; compare every step in an uninterrupted case. Interruptions show the committed prefix and actual reason. |
| P03: walk through ally | Prior traversal allowed only the origin-size exception; endpoint occupancy is a separate rule. Ally candidate is at the correct owner. | Admit ally transit in `Entity.can_traverse_creature_space`; retain enemy/origin rules, terrain costs and occupied endpoint rejection. Test passage and occupied destination independently. |
| P04: automatic wall transparency | New per-frame cutaway exists, is costly and cuts selections to a base strip. | Shared visual-cut/pick policy for walls covering party-visible ground; no Alt requirement, no physical boundary changes. Covered ground becomes clickable while the visible door leaf/handle remains usable. |
| P05: slow startup | Imports, eager metadata validation and initial media all contribute; filesystem share unquantified. | Stage startup, remove duplicate metadata work inside existing loader, preload actual initial/next-use dependencies; measure installed native Windows warm/cold startup separately from uv installation. |
| P06: slow pan/rotation/FPS | Repeated alpha/mask work measured. Observer handoff replaces presentation/history state and may trigger preparation, but loaded body/world media caches survive. Eviction may contribute but is not proven. | Complete the GPU addendum and remove observer-driven scene replacement; profile preparation/residency and validate real pan/rotation/zoom and return-to-view costs. |
| P07: enemy without portrait | Two causes: exact skeleton media keys were missing; initiative is filtered through active observer. Media candidate exists. | Exact delivered portrait bindings plus party audience. Every visibly identified enemy has an appropriate portrait; no hidden enemy portrait leak. |
| P08: Fireball / Scorching Ray orientation | October 7 live report reconfirms incorrect projectile orientation; Scorching Ray residual rotation was disabled. A data flag alone is not acceptance. | Verify both nearest directional sprite selection and residual alignment to the actual projected trajectory, including camera rotation and elevation. Inspect actual pixels for both spells and the shared path. Profile Fireball stalls separately in native execution, preparation and drawing. No new trajectory system. |
| P09: hand/spell palette | Authored colours differ; candidate uses sampled spell palette. | One owning spell palette feeds Magic/Effect replacement unless explicit approved override; verify Scorching Ray and related fire/lightning examples with real pixels, never multiply tint. |
| P10: absent target previews | Hover was not using the proposed native selection prefix effectively; candidate now asks native preview. | Cached, asynchronous native preview of point/area/multi-target/ordered positions; ground-conforming shape, impact and actual route; stale results cannot paint. See input table. |
| P11: FPS counter | Candidate shows FPS and recent worst frame time. | One small readable counter; detailed bounded traces are opt-in. Name average/worst correctly; do not average away stalls. |
| P12: Windows runtime | Separate launcher/environment exists; first `pygame.time` import was blocked by Code Integrity, later clean environment clock works. | Repeat native launch and actual play with locked dependencies; keep Linux environment; no security bypass. Performance comparison controls source, scene, resolution and state. |
| P13: door one tile too far | Edge-door contact uses an old extra-neighbour rule. Candidate sets zero reach for all boundary-mounted objects, which is broader than requested. | Limit rule to native door/edge-handle contact semantics using existing object capabilities; two incident supports only. Verify discovery, approach and execution, all orientations/heights; do not change unrelated wall props. |
| P14: Fireball chunks | Native disclosed affected cells used as artwork stencil; removing it reveals physical-clearance timing bug. | Render admitted effect geometry continuously, separately from unseen terrain/entity grants; preserve real barriers at authored before/after times. Shared Fireball/Sunburst/Sleep tests and imagery. |
| P15: blocked zoom | Start was at maximum level. Candidate adds inward levels. | Zoom both directions, preserve world point at cursor and stable picks, capture wheel over panels; verify at 1280×720, 1920×1080, 2560×1440. |
| P16: ranged attack on skeleton | User means player firing **at** skeleton; exact cause remains unverified. | Trace selected loadout → native Attack → motion/weapon/release facts → recipe. Test Fighter bow at modular skeleton and goblin, then skeleton archer firing. Explicit ranged never silently becomes melee. |
| P17: old encounter enemies | Crypt used skeleton content despite authored goblins. Goblin candidate now present. | Preserve dungeon geometry/loot/traps; use exact authored goblin recipes and portraits. Keep skeleton regression as a test case. |
| P18: cannot revisit unseen known area | Native retained routes exist; ground picking required current sight. Candidate broadens picking. Party knowledge remains missing. | Click party-explored supports and native known routes; no hidden blockers disclosed in preview. Unknown obstacle interrupts at actual contact, with native cause. |
| P19: self-action double click/depleted spell confirm | UI choice admission and confirmation paths inconsistent. Candidate guards main selection and auto-submits SELF. | All entry paths share admission/generation gate. Action Surge one click; invalid/depleted ability never targets/confirms; remove redundant ✓ tooltip. |
| P20: Dash/Haste Dash duplicates | Action families expose budget variants. Candidate hides them but chooses restricted budget in UI. | One Dash verb; native typed budget preference resolves exact admitted row, preserving native restrictions and revealing resource in tooltip. No frontend Haste rule. |
| P21: known dead enemy becomes unknown | Turn-end event after deletion loses current perception; event-time identity candidate added. | Preserve witnessed identity through turn termination, without granting location. Check ordinary/departing/surprised turn producers, OA death, party projection and replay after engine reset. |
| P22: camera changes interactable set | Reproduced. Final post-cut masks can erase known door regions. New base-strip cut worsens selection. | One projection-aware cut/pick owner, exact door leaf/handle proxy from registered geometry where needed, Alt set based on authorized interactable identities. All four views must expose the same known doorway affordances. |
| P23: door visible / floor missing | Boundary contact and cell visibility/support composition differ; exact pixel cause remains unverified. | Trace each incident support's disclosure, height, authored pivot and draw order. Draw only authorized room-side support/threshold geometry; never fabricate a tile or reveal the next room. |
| P24: forever error | Transient state had no expiry. Candidate adds 3 s expiry/new-input clear. | Human wording; clock-based expiry through idle, failed/retried interaction and view change; no engine-language status left on screen. |
| P25: low dice | No fixed live RNG found; actual d20 constructor verified. | Compare roll identity, faces, advantage/disadvantage selection, bonuses and native/projected/log arithmetic once. No statistical flaky test and no bias patch. |
| P26: incompatible party views | Confirmed single-observer architecture. | One authorized party audience before projection; one causal stream/history/log, combined current/explored view, native knowledge-aware discovery. Actor mechanics remain individual. Section 4. |
| P27: fake async/stalls | Confirmed direct native/discovery/capture/media work on input thread. | One serialized native owner, detached replies, responsive SDL loop and measured media preparation; retain complete-lineage playback. Section 5. |
| P28: accidental/double input | Several independent branches route clicks with changing target state. General failure surface confirmed; individual clicks need trace. | Explicit UI gesture ownership/state table, generation validation, one-spend command, no click-through or queued stale click. Section 8. |
| P29: grid above walls | Old overlay was painted after scene. Candidate inserts commands by list-slice bookkeeping and is unverified. | Ground grid commands belong to support rendering, after floor before walls/props/actors, with elevation and cut semantics; no screen-top overlay or command-count slicing. |

### Earlier requests that remain binding

| Topic | Required retained behavior / remaining work |
| --- | --- |
| Wall/door light | Prior shared observed-light correction has bounded pixel evidence. Recheck with party light composition, four cameras and closed/open doors; never borrow hidden-side light. |
| Table and wall alignment | Crypt table moved away from wall. Preserve it; broader asset audit remains in the [human handoff](WALL_FLOOR_ASSET_ALIGNMENT_HANDOFF_2026-10-06.md). No arbitrary sprite pivot offsets to conceal bad placement. |
| Animated walls | Seven solid families lack registered destruction media. Confirm delivered art provenance; bind compatible existing sequences if present. If missing, report the exact asset list for the human; do not invent break art or claim all walls animated. An idle stone wall is not expected to wiggle. |
| Launch/experience | `play-windows.cmd` / `python -m game --fullscreen` enters the actual fixed party crypt, not character creation or a gallery. Exploration, chest loot, lever/trap and combat remain reachable. |
| Bar and layout | Four small icon blocks: base actions with explicit melee/ranged, spells, class, carried usable items. Multiple rows/paging where needed. No bar movement on log opening; no text flood or permanent target instructions. |
| Choices | Same-size hover strip above owner icon; consistent level symbols, authored form/element/summon choices, including Sorcerer conversion. No large choice panel or repeated confirmation. |
| Log | Flush-right glass panel, narrow deliberate padding, aligned readable antialiased text. Native recorded dice/modifiers; movement children and blood aftermath under causal parents; copy works. No new log/narrative generator. |
| Inventory/details | Shared glass, native equipment slots, owned carried grid, compatible replacements on slot hover and actual native equip/use. Hidden inventories stay private. |
| Visual composition | Small portraits, consistent hierarchy and icon size, accepted icon brightness, only essential text. Current maximum is 2560×1440, not 4K. Artwork pixel-density regeneration stays deferred until composition is accepted. |

## 4. One player audience, individual actors

### Decision

Introduce a small immutable audience value at the existing capture/projection boundary: controlled actor identities, observing actor identities, and audience revision. A session derives it from actual control ownership. In this phase both controlled party members supply their native observations. Friendly NPCs do not automatically disclose their inventories or add their view. Dead/incapacitated observers contribute only what their native recorded senses actually provide; remembered terrain is retained.

`current_actor_uuid` remains the native turn owner. UI selection is a separate identity for inspection. Neither changes the audience, clears the map or replaces history. The camera stays where the player put it; an explicit portrait-focus gesture recentres it. No automatic turn-change camera teleport.

### Capture and projection

- Extend existing `presentation.py` capture APIs and `player_projection.py`; do not merge already-redacted `PlayerLineage` packets.
- Retain each observing entity's event-time identity, visual/location, effect and sensory grants under that observer identity. Project each native event UUID/version once for the audience, keeping parent/lineage identity and source cursors.
- A semantic result can be admitted if an authorized member witnessed it. Field disclosure still uses the grants for that field: hearing does not become sight, identity does not become current location, and seeing a destination does not reveal a hidden attacker.
- Reduce each member's sensory updates independently. Party-visible cells are the union of current authorized visual cells; explored cells retain the union of learned cells. A contact disappears from current display only when no member still authorizes it. Last-known object state is chosen by native cursor, never active actor or dictionary order.
- Select one complete authorized current tile observation using its already-recorded effective-light treatment, then stable observer identity as tie-breaker. Keep that complete observation and its observer provenance; use it consistently for floor, walls and doors. Current snapshots do not record whether each cell was established by ordinary or special sight, so do not infer such a distinction from global sense modes or current world light. Never combine maxima from unrelated fields into invented lighting or a super-observer.
- Combine disclosed effect geometry only for the same effect identity, version and world coordinate frame. Finite VFX artwork need not use that geometry as an affected-cell alpha mask.
- Combat-log projection already accepts observer/controlled sets. Use that existing facility once per audience; deduplicate by native append/node identity, not sentence text. Identical legitimate multi-hit messages remain distinct.
- Controlled gear/resources for both party members are authorized through control, independently of mutual line of sight. Enemy HP, gear and status retain existing disclosure rules.

Public schema changes are explicit: advance the `PlayerSequence` schema from 2 to 3 for audience and observer-tagged sensory ownership. Provide one boundary conversion for old singleton recordings into a singleton audience; do not keep two renderer implementations. Initialization, lineages, HUD/log appends and reset/generation semantics remain replayable with the native engine reset. One `latest`, one `historical`, one pending playback queue.

### Knowledge for actions

Rendering a party map alone does not enable legal navigation on it. Add a typed native discovery-knowledge input in a dependency-neutral domain types module. It contains current authorized contacts plus retained authorized support/object facts, their observation cursors and scope revision. The application adapter assembles it from the existing recorded observation/projection memory. It is not a `game.PlayerState` imported into the engine, a second simulated map, or a list of known coordinates used to read hidden live after-values.

Thread the scope through existing discovery, position preview, subjective route blockers/costs/hazards, endpoint occupancy and object contact/approach queries. Bind that same retained scope to knowledge-dependent submission validation of the exact discovered row, including `Move.validate_path` and `BaseAction._validate_target_filter`; discovery and validation cannot use different audiences. An omitted scope preserves actor-only behavior for existing native callers. The acting entity remains origin, payer and physical requester. Do not mutate its senses, borrow another actor's cached path or make the UI run A*.

Remembered support/door queries must use the last authorized recorded values. Current `GridMap.is_walkable_for` and `Entity.materialize_navigation` consult live walkability/cost/hazard data; audit those subjective branches so a hidden change cannot alter the preview before discovery or contact. Objective execution still checks the real world at each committed step/contact and records a collision/changed-state interruption. Do not reject an entire route up front using a hidden distant blocker and thereby disclose it. The retained knowledge is query evidence, not authority to walk through an actual closed door.

Candidate knowledge and legal execution are separate. The party can expose a known enemy for inspection and potential targeting, but the acting caster must still satisfy that spell's physical range, path and personal-sight requirements. For example, wall vertices requiring caster sight remain illegal through an unseen wall. Reject with a short meaningful reason, not by hiding the entire scene. Route/cache identity includes knowledge revision alongside actor, occupancy, topology and movement resources; teammate movement/opening a door invalidates relevant discovery.

Acceptance: split the two heroes between rooms; only Fighter sees a goblin; let Sorcerer become turn owner; goblin actions witnessed by Fighter still play exactly once. Repeat with both seeing it, each seeing different subevents, one losing sight, death, mixed effective-light/special-sense overlap, a teammate opening a door, and an inaccessible but party-known spell target. Both heroes leave a doorway and it changes unseen: preview retains the known state, execution encounters the real obstruction. A route known only by the other hero must be discoverable and executable. Compare saved replay, wall/door/floor lighting, portraits, sounds, damage and log counts.

## 5. Responsive loop and one native owner

### Existing defect

`encounter_play.py` performs discovery before `pygame.event.get`, invokes session actions/controller advancement directly, captures each returned root separately for each observer, and loads choreography media before returning to input. `capture_lineages` rebuilds source indexes once per invocation and actor admissions scan history. The current caller multiplies that work unnecessarily. The loop's final `await asyncio.sleep(0)` changes none of these blocking costs.

### Planned ownership boundary

Use one long-lived **isolated worker process**, launched by the same Python interpreter as `python -m game.runtime_worker`, for the native session and its complete operation boundary. This avoids main-thread GIL contention from CPU-bound domain work and makes detached ownership enforceable. It is a local application boundary, not a server or generic job framework.

This supersedes the old recovery commitment to a same-thread/in-process live frame pump only for scheduling. Native mechanics remain synchronous within each transaction and retain their current ECS owners. Content bootstrap must happen once inside the worker: the installed content runtime and native registries are process-local and are not inherited by the new interpreter. The parent imports only the passive protocol, not the worker module to obtain a callable target. Worker bootstrap imports stay static in the independently launched module, with a guarded entry point. Never pass a loaded registry or bound Session method into process creation.

Suggested files: `game/runtime_protocol.py` for frozen typed requests/replies; `game/runtime_worker.py` for the process entry/dispatch/lifecycle. Keep `game/session.py` as the existing native API owner. `encounter_play.py` composes them. No new controller hierarchy, OOP runtime-manager framework, event bus or duplicate action implementation.

Worker owns creation/reset/close, native commands, AI advancement, discovery, preview, HUD extraction, event capture and public projection. SDL owns event pump, display, fonts, surfaces, media and historical playback. The worker never sends `Session`, live Event/Entity objects, executable action templates, callbacks or native caches.

Requests use a discriminated operation kind and explicit fields: runtime generation, request identity, actor identity, discovery epoch, exact row/target indices and ordered extra targets/positions where relevant. Replies contain existing detached discovery/preview/public-lineage/HUD/log values plus request identity, resulting cursor and timing data. Existing DTO serialization is reused; only the transport envelope is new. Existing `Operation` stays inside the worker because it contains live roots.

`AdvanceResult` also participates in native registries; return only its passive status/actor/revision fields. Serialize the public fields of discovery using the existing dump/validate boundary, never pickle original discovery objects: their private attributes retain executable templates. Move the existing plain equip/unequip/handler intents from `ui/types.py` into the shared headless command module rather than copying them or importing Pygame UI into the worker. Detached ownership is required even where an existing DTO contains mutable nested values; the UI must never mutate the worker's source.

One mutation can be outstanding. The worker validates exact retained choices and generation again, executes the native operation, reaches terminal roots, captures/projects its entire result, and publishes a detached reply before starting another mutation. Capture all roots with existing `capture_lineages` batching; do not repeatedly rebuild history indexes per root or per party member. No provisional partial events or predicted damage are rendered.

The UI never queues spending clicks while busy. It can pan, zoom, inspect already disclosed facts, read/copy logs and quit. For AI, request the next existing controller boundary after the prior result is safely captured, allowing bounded computation to overlap playback. Keep a maximum small lookahead (one completed operation beyond the current playback group); never simulate an unbounded encounter ahead of the viewer or human input.

Latest native HUD/discovery does not become the visible historical HUD early. Commit displayed resources, initiative and log facts at their existing causal presentation markers. Enable a human command only when playback has reached that native decision boundary; otherwise an ahead-of-playback reply could allow targeting a future scene or reveal an enemy outcome too early.

Discovery is revision-driven, not per-frame. Preview requests are latest-only: replace pending hover requests, identify actor/epoch/ordered prefix/candidate, discard superseded replies. A commitment invalidates pending preview replies. Native validation rejects stale command epochs, then returns fresh discovery; it never silently maps a stale index to a different action.

Shutdown stops accepting work, signals the owner, lets any current native operation finish, and closes/reset there. No SDL `finally` mutates worker session state. If the worker fails, the window stays responsive, command input stops and a readable failure is reported; no automatic command retry that can double spend. Forced shutdown can terminate the isolated process after a bounded grace period because this app has no live persistent transaction to recover; it must not claim the encounter was saved.

Process startup/serialization overhead is measured. DTO replies send newly completed facts, not the entire growing history each frame. Local length-framed byte pipes carry the typed public payloads; the child's protocol output is reserved for those frames, and diagnostics go to stderr/a bounded log. Parent byte intake can use one bounded reader owned by the runtime adapter, so Windows pipe reads never block SDL. That reader does not execute game rules or own a second playback queue. The existing native EventQueue and the one presentation pending queue remain authoritative. No second event schema is introduced for combat.

Measure encode/transfer/decode time and payload bytes as well as worker execution. A nonblocking poll followed by an enormous blocking receive is still a freeze. Use bounded packet intake at the composition boundary; add a byte-transport helper only if measured payload costs require it, retaining one logical operation reply and one playback queue.

### Media work is a separate part of responsiveness

Native work leaving SDL does not remove decode/material stalls. Follow the GPU addendum's shared source selectors, bounded resource ownership and group admission. Preserve existing authored sources/registrations while replacing Surface-based caches with immutable resources and GPU residency. Prepare the initial disclosed scene and complete pending choreography dependencies before its playback clock begins. Avoid loading the entire asset library as a guessed fix.

Separate file reads/metadata preparation from display-dependent conversion. Use bounded preparation steps between input pumps, reuse immutable decoded resources with bounded GPU uploads, and budget preparation against the frame target. Do not access Pygame display/font objects from the native worker. Measure single decode/conversion outliers; where one exceeds the budget, use the existing asset pipeline's compatible prepared representation or a narrowly scoped byte-preparation stage, not a new media framework or placeholder art. No first-use spell may begin its animation and then freeze while its own frames load.

## 6. Drawing, masks, caches and startup

### Replace pixel work with resident resources

The GPU addendum supersedes the earlier CPU-cache-only strategy. One immutable source identity and explicit byte-bounded readiness/residency replace transformed-image cache chains. Exact palette replacement, registered XYZ/ownership and physical coverage are evaluated by concrete shaders where needed; authored selectors, timing and native rules retain their existing owners. No per-palette/zoom/time resource duplication or persistent `id(surface)` keys.

Object masks/apertures remain original asset-local data. Pan changes transforms, not decoded resources. Physical geometry changes on its historical revision, not on every input frame. Preserve registration and pixel rounding at fractional pan/zoom. The addendum specifies ordered composition and point picking against the same presented frame, including faded walls and nonselectable blockers.

Do not reuse a final `InteractionFrame` across moving actors, door changes or alpha changes. Publish a frame-matched interaction snapshot after presentation. G0 measures complete working sets after packing repair; G2 enforces byte limits, pins and bounded preparation. Rotation must not initiate a sample-time load. Final acceptance includes source-read/decode/upload diagnostics, input latency and memory stability rather than assuming the user's RAM hides waste.

For cutaway, first perform cheap projected bounds/depth candidate filtering; only intersect covered visible-support geometry for candidate boundaries. Avoid scanning every wall against every visible tile and recopying every image each frame. Reuse the faded surface treatment by source frame. Physical ray, movement and VFX propagation boundaries remain separate from this camera readability treatment.

### Startup

`load_animation_data` eagerly validates the root materialized draft, authored bundles and supplied rig records; `_run` currently supplies all rig files, and installed rig identities are read again. Profile read/parse/validation/assembly separately. Remove duplicate reads and cache metadata within the existing loader's lifetime. Select required scene rigs through the current explicit loader interface where correctness permits, with explicit loading for later revealed/summoned rigs; keep full installed-manifest validation in the existing authoring validation lane. Do not introduce late Python imports or bypass missing-binding validation.

Profile parent and independent-child import DAGs separately. Current `__main__.py` eagerly imports bootstrap and `encounter_play` before a window can draw. Move native bootstrap's static import to the independently launched worker module and remove obsolete native-runtime imports from the SDL composition as that ownership moves; keep domain DTO/renderer imports static. The parent must not import the worker module itself. Do not move imports inside functions to hide initialization. Any remaining expensive shared import needs measured dependency evidence before a bounded module split, not a blanket startup refactor.

The import phase has no responsive window and must be counted honestly. After static imports and SDL initialization, enter the loading event pump while the native worker initializes and renderer metadata/media prepare in bounded steps. No half-initialized encounter becomes clickable. Report time-to-first-responsive-window and time-to-play separately. uv provisioning is separate again. Do not move assets/repository or change image quality to conceal startup costs.

## 7. Geometry, effects and path correctness

### Render and pick the same scene

Ground rendering owns floor/support polygons, grid and target footprint overlays. Order: floor artwork → ground grid/footprint → world walls/doors/props/actors under the existing depth rules. Elevated supports retain their actual height; upper floors can occlude lower overlays. The grid never creates selectable ground outside authorized current/remembered supports.

Foreground walls covering party-visible ground are faded automatically. Their faded opaque silhouettes must not block clicks to that authorized ground. Interactive door leaves/handles retain explicit visible hit regions; plain wall attack remains available on the retained base/edge through Ctrl/context selection. Avoid invisible rectangular click shields. A typed selection role/cut policy in existing draw-command data may distinguish ground, barrier and interactive insert if current roles cannot express this; no object-name or camera-number branches.

Alt highlight enumerates authorized interactables, then uses the same projected geometry and cuts. A known door cannot vanish from the interaction affordances just because its wall faces the camera. Handle placement comes from registered door geometry; a narrow proxy may remain where wall fading removes most pixels, but it must be visibly indicated and cannot intercept unrelated ground clicks. Unknown objects never receive proxies.

For P23, inspect incident-cell support facts before changing pixels. If the room-side support is observed, it must be drawn beneath the door at its registered elevation. If only a boundary surface is known, draw only a legitimately disclosed threshold/aperture already belonging to that object; do not invent the unseen floor beyond. Asset pivot defects go to the existing asset audit, not hardcoded coordinate nudges.

### Continuous effects and physical clearance

An admitted Fireball is one continuous visual volume. Unknown affected cells are not holes in that volume. Visibility still controls terrain, entities and outcomes independently. The render operator must distinguish receiving an effect, its authored geometry, physical occlusion and who knows its damage. Use the same distinction for Sunburst, Sleep and other finite areas.

Do not erase physical blockers merely because a wall is faded for camera readability. For an animated door destruction, preserve the **event-time pre-change** boundary channels through the authored clearance marker and use the post-change channels afterward. Capture the before-state from native version facts at the relevant cause, not the mutable destroyed object after mutation. Existing formation/clearance authoring drives the visual transition. No duplicated special Fireball delay or recomputation from live world state.

The gameplay engine can resolve synchronously within its owner; historical presentation samples the recorded before/after facts on the authored timeline. Damage, door break and visibility changes must remain causally ordered in replay and in the live app.

### Routes and door reach

Use the existing native route selected by `prefers_safe_movement_path` for both preview and submission. Never run a second UI pathfinder. Include occupied ally traversal, different support heights, door revisions and party knowledge in native route admission. Cost display uses that route's native cost, including existing terrain/occupancy cost rules. The endpoint cannot be occupied.

Door interaction uses either incident support, not the old five-foot neighbour ring. Automatic approach selects an admitted native destination to a legal handle contact. If the current movement allowance cannot reach it, do not silently send the actor into an unrelated corner or open remotely: show the admitted affordable route/endpoint and reject unachievable interaction as such. A later resource/obstacle interruption records its cause; the UI displays that committed prefix rather than pretending the original destination was reached.

## 8. Input and action affordances

Keep the existing menu/focus state and typed hits; consolidate routing rather than add a second UI state machine. Each gesture captures its owner on mouse-down and is consumed through mouse-up, even if a popup closes or becomes disabled. Keyboard equivalents use the same command admission path.

| User gesture / state | Required result |
| --- | --- |
| Hover a normal valid action | Tooltip only; no spending. |
| Hover a choice family | Same-size choice strip above icon; crossing the gap does not close it. |
| Click valid immediate self-action (Action Surge, native self conversion) | Submit exact native choice once. No world target/✓ step. |
| Click depleted/unavailable action/rank | Consume UI click; short reason in tooltip/status. Never enter targeting or fall through to world. |
| Click single-target action then legal target | Commit once, unless native selection contract requires another input. Invalid target never spends. |
| Allocate repeat/multi-target spell | Ordered native target indices, including repeated identities. Use native min/max/partial rules; one-target-all-projectiles only where the action's existing policy says so. Confirm only genuinely incomplete/optional allocations. |
| Ordered wall / teleport / summon positions | Native ordered position contract and prefix preview; completed legal selection commits, optional prefixes can confirm under native rules. Wall hot side remains endpoint order. |
| Hover AoE target | Native current-prefix affected geometry, range/impact indication; no mass of unrelated selectable dots. Geometry is drawn on support planes. |
| Explicit melee/ranged mode | Per-character choice selects that native weapon set/row. Never substitute a different attack because it is convenient. |
| Click world interactable | Native default interaction + legal approach when needed; Ctrl selects attack. Window traversal uses its native interaction. |
| Click known ground | Native route preview/commit, including currently unseen explored party ground; no line-of-sight-only UI veto. |
| UI panel / popup / tooltip gap / scroll gesture | Consumed by owning UI; never moves/attacks behind it. |
| Command pending / playback before current decision point | No spending input queued. Camera/log/inspection remain responsive. |
| Actor/epoch changes or escape | Clear stale targeting/preview; a late reply cannot re-arm it. |
| Hover target then commit | Hover/selection outline ends at commitment, not throughout the attack. |

**Dash budget choice:** show one family. The native discovery adapter exposes a typed preferred exact row for semantically identical budget alternatives: spend an available restricted action that covers the whole chosen verb before a general action, preserving general flexibility. This is a declared application policy, implemented using native eligibility/cost facts; UI does not infer it from “Haste” labels. Show which resource will pay in the tooltip. Preserve explicit native alternatives for API callers. Do not collapse Attack/Extra Attack alternatives with different effects/capacity into one silently interchangeable row. Test normal-only, restricted-only, both, depleted restricted, Slow and Extra Attack/Action Surge combinations through actual costs.

Transient errors expire after three seconds and clear on a new relevant attempt/selection. They describe the failure in human terms. Persistent invalidity belongs in disabled affordances/tooltips. No engine identifiers, “admitted safe approach” language or diagnostic paragraphs appear in normal play.

## 9. Event identity, dice and log

Keep the existing native log and its rich text/math. The renderer formats recorded structure; it neither rolls nor reconstructs results. Preserve movement-parent/step grouping and blood tile aftermath beneath damage, without aggregating separate hits, deaths or reactions into misleading single entries.

Turn identity is an event producer concern. A creature identified during the turn remains identified in that turn's terminal events after death/removal. Carry event-time identity grants, not current location. Check ordinary turn end, active creature removal and surprised/skipped turn paths. The provisional scan must be bounded to the correct turn/generation and include both turn-start and later reaction witnesses; it must not admit an uninformed observer. Replay after native reset must print the same name and math.

For dice, compare one representative native attack's roll UUID, die sides, individual results, selected advantage/disadvantage result and modifiers against projected DTO and rendered/copied text. The current live constructor is d20 and no fixed RNG was found. Retain deterministic dice helpers only in explicit tests/demos; never adjust gameplay RNG to avoid an unlucky streak.

## 10. File ownership and removal rules

| Responsibility | Existing owners to change | New data allowed / old behavior to remove |
| --- | --- | --- |
| Audience capture/reduction | `game/presentation.py`, `player_projection.py`, `player_facts.py`, `player_reduction.py`, `session.py` | Audience + observer-tagged observations; v3 boundary conversion. Remove per-active-actor map/log/head switching. |
| Native knowledge-aware discovery and validation | `dnd/actions_functional.py`, `actions.py` movement validation, `entity.py`, `core/gridmap.py`, `core/base_actions.py`, existing `types/senses.py` and query owners | One dependency-neutral knowledge value, retained observed facts and explicit query/validation inputs. No engine import of UI types or private world copied into a second map. |
| Native worker | `game/session.py`, `encounter_play.py` | Two bounded protocol/worker modules. Remove direct SDL access to live native state/templates. |
| GPU renderer and readiness | Existing authored loaders/sample owners, `app.py`, world/creature/media/UI modules; concrete new owners named in the GPU addendum | G0–G8 replace CPU pixel/material/depth/selection rasterization with portable passive records, shared source resolution, bounded residency and concrete GL functions. Remove old production dispatch/caches; retain native facts and authored timing. No generic backend framework. |
| Scene overlays/picking | `game/app.py`, `draw_commands.py`, `environment_draw.py`, `interaction_frame.py` | Typed roles if needed; remove top-overlay grid and provisional tail-slice insertion. |
| Input/choice behavior | `game/controls.py`, `ui/action_bar.py`, `ui/variants.py`, `ui/targeting.py`, `ui/world_interaction.py`, `encounter_play.py` | Existing typed selection and focus; remove duplicate confirmation branches and UI budget inference. |
| Native corrections | `dnd/entity.py`, `core/gridmap.py`, `encounter.py`, relevant event producers | Ally transit, narrow door reach, retained turn identity. No generalized rules expansion. |
| Spell/portrait/content corrections | Existing recipe JSON, palette owners, UI media bindings, crypt content | Existing registered art/recipes; no new spell handlers, generated assets or new roster abstraction. |

Import direction remains domain types → domain owners → session/capture/projection → runtime composition; public presentation types → renderer/UI. The worker and entry point import these lower owners, never vice versa. No late imports, `getattr` compatibility shortcuts, dynamic type checks concealing missing contracts or circular imports.

Each new state field must name its owner, mutation trigger, reset and serialization policy. Every new cache must identify stable key, invalidation and memory bound. Remove the superseded path in the same phase; do not leave old/new pipelines permanently selectable.

### Provisional changes: explicit disposition

- **Retain as candidates, validate:** ally transit, delivered portrait bindings, bounded static item material cache, FPS counter, Windows launcher, inward zoom levels, Scorching Ray authored correction, explored-ground picking, readable expiring errors.
- **Revise before acceptance:** all-boundary manual reach → door/contact capability scope; UI restricted-budget preference → native exact-row policy; actor-only targeting/discovery → authorized party knowledge; current cutaway → shared geometry/picking with reusable masks.
- **Complete, not revert the symptom fix:** continuous Fireball volume plus correct physical-clearance before-state; turn identity plus corrected privacy fixture/all producers.
- **Replace provisional glue:** grid tail-slice insertion; direct sync native calls inside SDL; per-observer live map switching.
- Earlier UI/layout/source changes are shared dirty-tree work. No blanket reset, unrelated refactor or mass reformat. Record the exact source state before implementation for reproducible comparison.

## 11. Execution sequence and gates

| Step | Work | Must be true before continuing |
| --- | --- | --- |
| 0 — evidence and boundaries | Freeze source/config manifest; complete the mandatory engine/startup regression audit in section 2, including ranked native costs and compatible historical comparisons. Record baseline actual SDL route, frames and input trace. Confirm P16/P23 exact causes. Specify audience v3 and runtime packet schemas with anti-slop/ECS review. Freeze representative native-operation scenarios and the total-latency budgets below before changes. | All complaints mapped; engine/startup cost explicitly assessed rather than presumed healthy; no unbounded worker/media plan or ambiguous disclosure owner. Slow native execution remains in scope even if the UI becomes responsive. |
| 1 — party view and native routes | Audience capture/replay, knowledge-aware discovery, ally transit and narrow door contact. Preserve native budgets/rules. | Split-room causal replay once; all audience/privacy cases; exact two-door preview/execution; old singleton recording compatibility. |
| 2 — native operation isolation | Single worker, exact epochs, coalesced previews, bounded AI lookahead, batch capture, lifecycle/error handling. | SDL can pan/inspect/quit through costly native work; no duplicate command/event; no live object crosses protocol; deterministic reply completion tests. |
| 3 — full GPU migration and media readiness | Complete addendum G0–G8: packing repair, sampled records, preparation/residency, all world/creature/VFX/UI families, point picking, all entry points and old-code removal. Integrate steps 4–5 before final cutover. | Real frame/input/startup budgets; full composition/picking coverage and bounded memory; no hidden Surface fallback; all original art/timing contracts retained except explicitly recorded repairs. |
| 4 — interaction correctness | Complete gesture table, disabled/self/choice flows, native budget preference, route/area previews, portraits, zoom and transient errors. | Physical SDL input journey; no click-through/double spend; old multi-target forms and weapon modes still work. |
| 5 — specific visual/event repairs | Fireball physical timeline, Scorching Ray rotation/palette, ranged skeleton regression, door floor/light, turn identity/dice/log; retained UI polish. | Real frames at all four quarters plus native/replay facts; all P rows closed or exact unavailable-art dependency explicitly handed back. |
| 6 — combined acceptance | Real native Windows crypt play, long-session performance, affected/full suites, final reviews, indexed evidence. | Both independent implementation approvals; full truthful failure reconciliation; human can launch and exercise encounter without a gallery. |

Steps may refine implementation inside their named owners; they do not reopen unrelated systems. At each boundary reviewers inspect the actual implementation and evidence before the next phase depends on it. Do not stop at a good first spell/route sample and call the whole app repaired.

## 12. Performance acceptance, not average-FPS reassurance

Targets below are engineering acceptance targets, not current measured results. Native Windows at 2560×1440 is the primary real-display platform. Repeat key scenes at 1920×1080 and 1280×720. WSL is a controlled secondary comparison. No 4K requirement.

Record build/diff hash, Python/Pygame/SDL versions, scene/content IDs, viewport, zoom/quadrant, render settings, process/native vs WSL, cold/warm status and instrumentation overhead. Use monotonic wall time, actual display presentation and actual input events, not injected frame deltas. Report p50/p95/p99/max, not only FPS averages.

| Scenario / metric | Acceptance target |
| --- | --- |
| Warm idle, WASD pan, zoom, camera rotation and return; panels/log open | Whole-frame work excluding deliberate 60 Hz sleep: p95 ≤16.7 ms, p99 ≤25 ms; no reproducible >50 ms frame in the stable route. Record display and wait separately. |
| Mouse/keyboard/camera response while native work runs | Input-to-next-displayed acknowledgement p95 ≤50 ms, max ≤100 ms. Native action completion latency is separately reported; a busy command does not freeze camera/input. |
| Warm hover preview | Latest valid preview p95 ≤100 ms; old replies never flash. Camera/render frames stay within budget while computing it. |
| First/repeated spell, door opening/destruction, new enemy rig | Same responsive event-pump requirement; no mid-animation asset-decode stall. First-use preparation latency reported separately; aim ≤250 ms after native reply, do not conceal misses inside a frozen frame. |
| Ordinary completed native command to playback readiness | Report engine, capture, transport and media stages independently; warm capture/transport/preparation p95 ≤100 ms for single-action samples. Long AI/large spell resolution stays visible in diagnostics and does not block UI. |
| Total warm command commitment → complete reply ready for playback, including native execution and queue/transport/media time | Representative crypt movement (up to one turn's legal route), door operation and ordinary weapon attack: p95 ≤250 ms, max ≤500 ms. Fireball in the encounter: p95 ≤1 s, max ≤2 s. One ordinary enemy controller decision: p95 ≤500 ms, max ≤1 s. Freeze exact scene/targets and repeat counts in step 0. Authored animation duration is excluded; computation hidden behind it is still measured. |
| Installed-game startup | Warm OS cache: first responsive loading frame ≤2 s, playable crypt ≤5 s. Cold process/media: first responsive loading frame ≤5 s, playable crypt ≤10 s. Count both parent/child static imports; no interpreter exemption. Separately report uv provisioning and first-run security prompts. |
| Long session / cache growth | Revisit same scene, four views, zooms and spells over 15 minutes / at least 100 completed operations. No continuing cache-byte growth after the repeated working set stabilizes; explain intentional history growth. Comparable late-operation capture cost ≤1.25× early warm cost. |

If targets fail, keep the phase open and identify the measured stage. Do not disable transparency, remove VFX, lower user resolution, skip outcomes, reduce authored animation quality or manipulate the FPS counter to pass. These budgets are baseline smoothness, not a promise that every imported asset is already optimal.

If total command latency fails because native execution dominates, profile that operation's existing domain producers (path/contact/discovery/senses/event work) and repair the measured duplication or invalidation there. Moving a multi-second stall to a worker does not satisfy this plan. Budgets may not be silently raised after a failed run; a changed product target requires discussion with the human.

Bounded diagnostics extend existing timing support. Normal HUD gets only the requested compact FPS/frame-time counter. Deep traces must not become a permanent per-frame JSON dump or new tracked megabyte artifact.

## 13. Acceptance cases and evidence delivery

Read `HOW_TO_TEST.MD` before changes. Native scenarios and serialized presentation are primary correctness boundaries; actual SDL events/frames validate input and imagery. No mocks of our own route/selection rules as proof. Tests await replies/revisions, not arbitrary sleeps.

Process isolation changes two existing test assumptions. A parent `random.seed` does not seed the worker, and 90 or 240 synthetic frames are not a readiness signal. Test startup may pass an explicit seed; normal launch never does. Keep `player_input` callbacks and UI event instrumentation in the main process, and synchronize on public startup/operation completion. Preserve in-process native session tests, adding only a small real worker/SDL lane for the ownership boundary.

1. **Playable crypt journey:** launch directly, both heroes, loot supplies, open both doors, ally blocks corridor but can be passed, explore unseen-known room, lever/trap, loot vault, encounter goblins, switch weapons, cast, end turn, witness enemy actions, win. Capture the native command/path/resource trace and a short real gameplay recording.
2. **Party evidence matrix:** one observer, both observers, disjoint child witnesses, sight loss, death, turn change, heard-only enemy, unseen attacker, revealed door and personally illegal wall target. One event/log/impact/sound per real outcome. Serialize and replay after engine reset; compare facts and bounded frames.
3. **Geometry matrix:** four quarters and return; base/raised support, closed/open/breaking door, foreground faded wall, floor grid, remembered terrain, Alt, Ctrl and default door click. Known interactables and exposed ground must stay available, without hidden-room reveal.
4. **Controls matrix:** mouse/keyboard/spellbook/context entry, disabled rank, self action, partial/repeated targets, walls/rings/endpoint order, summons, element choices, conversion; popup gap; mouse-down then invalidation; late preview; busy click; explicit melee/ranged. Costs occur once and only after a legal commitment.
5. **Visual regressions:** actual Scorching Ray across directions/heights and hand palette, Fighter bow at skeleton/goblin, continuous Fireball at fog edge and physical door before/after clearance, Sunburst/Sleep area shape. Inspect real pixels; numeric geometry alone is insufficient.
6. **Log and math:** named opportunity-death turn end, surprised turn, damage/save/reaction, repeated hits, grouped path steps/blood tiles, copy and wrapping at supported resolutions. Native faces/modifiers match displayed/copied values; uninformed audience learns nothing extra.
7. **Performance route:** actual WASD/rotations/zoom/UI plus first/repeated spells and 100-operation long session. Capture stage percentiles and cache diagnostics with exact source/environment identity. Dummy SDL profiles remain diagnostic only.
8. **Regression completion:** run the full engine/game/architecture suites in bounded partitions using existing supported lane/environment; inventory all failures and distinguish prior fixture assumptions, genuine source defects and missing delivered assets. Do not delete or weaken expectations to obtain green. No unrelated rule expansion to satisfy obsolete fixtures; document separately and discuss if outside this repair.

The evidence index maps every P ID to its reproduction, changed owner, test result, relevant native recording and live screenshot/clip. Clips are issue-focused and tied to real input, not another 298-case review burden. Screenshots do not substitute for input/performance traces. Repeated suite counts must not be summed as unique coverage.

## 14. Independent review

Two independent local reviewers are required: anti-slop/performance and anti-OOP/ECS/causality. No communication with other user chats.

Initial read-only reviews have already identified the active-observer design defect, repeated history capture, synchronous UI-thread operations, mask-copy hotspots, provisional door-picking regression, overly broad reach change, frontend budget policy and missing turn-end producer coverage. Those findings are incorporated above.

The base plan approvals and subsequent engine/startup audit amendment reviews are recorded in the linked [review receipt](audits/PLAYER_PLAYTEST_PLAN_REVIEWS_2026-10-06.md), with their document identities. Plan approval authorizes a design recommendation, not a claim that implementation or live acceptance has passed. The human resumed implementation; the implementation receipt tracks unfinished steps and measured acceptance.
