# D&D recovery: plan of action

Updated 2026-09-10 after the user's correction: **develop the game, not a
sequence of spell demonstrations.** Working branch: **codex/recovery-design**,
based on **codex/july-reconstruction at 16a6bfe**. The existing working tree
contains the implementation; HEAD alone is not its full state.

**Objective:** a playable in-process D&D encounter using the existing engine and
NeuroStudio data through Python/Pygame. Complete subjective lineages reduce
independently of historical playback. The engine already owns the rules; the
application must connect movement, actions, turns, reactions and state into a
coherent game. Hundreds of spells exercise shared capabilities and data, rather
than receiving separate executors or becoming serial release milestones.

**Available foundation:** retained lineages, independent latest/history, the
map/camera/picker, rig drawing, authored cast sampling, repeated applications and
equipment playback work. The finite Fire Bolt/Magic Missile programs remain
regression references. Their success does not constitute the game. The earlier
Magic Missile geometry was a generated fallback; the actual CodexFX Rune Dart
is now imported through the original Studio schema, independently of gameplay.

## Active work — playable encounter through shared capabilities

**Current gallery feedback — interrupted poses and legible feedback.** The
human observed a lethal opportunity attack snapping the corpse back to the
legal tile center. Keep authoritative positions and Step results intact;
preserve the rendered stop/death contact through head completion and later
idle frames. Study the equivalent walking/jumping/paralysis boundaries and
the next action's attachment before choosing the shared correction. Review
the imported Paralyzed color recipe against NeuroClient, and report what it
actually applies. Place floating feedback clear of the animation, choosing
above/below according to screen space instead of covering bodies or clipping.
The anti-slop reviewer checks real captured cases and removes assertions that
mistakenly equate visual contacts with legal tile centers. The anti-OOP
reviewer checks that retained visual placement belongs to playback, with no
backend animation data, second mechanics implementation or new clock/queue.
Regenerate the affected four-corner clips for human review.

**Finding and selected correction:** NeuroClient's Move/Jump completion also
restored the authoritative origin. The human explicitly superseded that
behavior: an uncommitted Step keeps its legal origin while playback retains
the contact at which the reaction stopped. This affects living paralysis and
lethal walking/jumping reactions. Playback owns a small geometry-only placement
map alongside facings; fresh historical actor facts and visibility still own
HP, conditions, gear and admission. A later legal relocation supersedes the
placement; a later bound motion starts at the visible pose. Body lift is
separate from support elevation so actors and their attachments agree while
shadows stay on the support plane. Head completion uses the same global idle
clock as the following idle frame. There are no new landing or gravity rules.

The Paralyzed appearance is unchanged original data: no RGB tint, saturation
`0.35`, brightness `0.86`, alpha `1`. Pygame's color transform matches the
NeuroClient filter. `Ghoul Paralysis` is a state-only wrapper without its own
body color or feedback. Floating messages and actor labels now share placement
against actual nontransparent body bounds: above first, below when necessary,
clamped to the usable viewport and stacked away from other labels. Recipe
timing, text, fonts and opacity are preserved.

**Correction validated 2026-09-10:** full run `20260910T164415Z-666bea`
passes all 22 capture cases, with 88 views and 1,881 frames. The existing Goblin
ranged body/slash media gap remains the only reported gap. Side-by-side trace
checks for walk/jump × death/paralysis show identical actor screen coordinates
before completion, at completion and on the next idle frame in all four views;
the old run visibly changed those coordinates. Evidence is in
`.runtime/animation-review/interruption-validation.json`, with a four-corner
feedback frame at `.runtime/animation-review/paralyzed-feedback-four-corners.png`.
Movement, placement, text layout, recorder, encounter, geometry and original
timing regressions pass, as do import-direction/DAG checks and changed-file
Pyright. Anti-slop/anti-OOP review found no blocking issue. The captured source
hash matches the current game/devtool files. Review the new run at
`http://127.0.0.1:8767/runs/20260910T164415Z-666bea/index.html`.

**Visual review checkpoint — requested 2026-09-10.** Maintain a named catalog
of real standardized event sequences and generate tagged video snippets plus a
local HTML review gallery with one command. The reviewer can play the clips in
parallel, pause/seek, mark a case and time, add a note, and export the selected
cases' debug traces. Preserve run/source identity so feedback refers to the
pixels and retained facts that were actually reviewed.

The user's current emphasis is **engine as clip extractor**. Execute each
scenario once and sample all four camera corners at the same presentation
times in one pass. Encode a synchronized 2×2 video per case. Every recorded
frame retains the common state and each corner's draw evidence. This visual
checkpoint is the immediate work; the encounter remains the shared source of
playback behavior. Run the affected catalog cases at each implementation step,
and the full catalog at a checkpoint; human visual approval remains separate
from automatic state/capture checks.

The implemented entry is `python -m devtools.animation_review`, with 22
catalog entries under `devtools/animation_review/catalog.json` and instructions
in its README. The local `.serve` entry supports video byte ranges, so browser
frame stepping and pinned-time seeking work. Each unique generated run keeps
its clips, traces and source hashes; exported reviews include the selected
frame index, all four view samples and the actual retained root identity.
The shared scene composition was extracted from `game/encounter_play.py` into
`game/playback_frame.py`; clocks, queues and head transitions kept their owners.
The scenario builders were moved into shared test support without importing
pytest into the extractor or test support into the game.

The anti-slop/anti-OOP review corrected two recorder gaps: source hashing now
includes the consumed `content_data` visual ledger, and unbound movement remains
an explicit coverage failure. The full capture also exposed a Fire Bolt trace
serialization error; using the existing typed authoring serializers preserves
its frozen maps. Six recording/HTTP tests pass, including that real cast; 52
scenario regressions, six encounter checks and four import-direction/DAG checks
pass. Browser checks cover parallel playback, native fullscreen, pin/step,
per-run review persistence, complete exports and visible failure handling.
These checks do not approve the animations visually on the human's behalf.
The completed full run `20260910T150620Z-42c3df` records all 22 cases successfully
as four-corner videos (88 views). Its manifest/traces are under
`.runtime/animation-review/runs/20260910T150620Z-42c3df`; the only reported media
gaps are the existing fixed Goblin ranged body/slash clips. The browser review
URL is `http://127.0.0.1:8767/`, served by the local review tool. Future runs get
their own directory and become the latest report at that URL.

Use existing public scenario producers, retained lineages, reducers and the
same Pygame scene sampling/drawing as the game. Extract the existing frame
composition only as needed to share it; do not create another animation
implementation. Keep catalog entries as data. Initial coverage includes melee,
ranged, walking/jumping opportunity reactions (save/miss/paralysis/death),
existing casts and repeated targets, varied camera views, and reduction facts.
Each clip records its seed/setup, actual complete event ancestry, authored
anchors, sampled states, gaps and validation results. A failed capture or check
must remain visible in the report. Generated videos/traces stay under ignored
`.runtime`; checked-in code/catalog and instructions make each run repeatable.

The **anti-slop reviewer** checks whether the gallery makes failures selectable
and exportable, rather than merely showing attractive clips, and whether adding
a case reuses existing producers. The **anti-OOP reviewer** checks shared frame
ownership, passive trace data, original lineage identity, no engine imports of
review tooling and no additional gameplay clock/queue. Validate generated media
and the review/export flow as well as the existing encounter regressions.

**Current correction — reaction composition and ranged delivery.** A successful
encounter demonstration is not evidence that the authored degrees of freedom
survived the port. Compare original Move/Jump, Attack, TakeDamage and Condition
recipes/primitives with the Python owners. Restore the complete reaction-child
join and its authored effect anchors; validate a real configured longsword
paralysis rider, successful saves, death and continued movement using actual
committed Step facts. Implement the existing ranged attack recipe in the same
chunk. Keep condition rules and continuation decisions in the engine.

The anti-slop reviewer must distinguish imported-but-unused data from executed
data, and reject content-name branches or flattened child effects. The anti-OOP
reviewer must check passive composition, original causal identities, the import
DAG and the single historical-head owner. Document coded event-family reduction
semantics honestly; moving them into arbitrary JSON would not by itself recover
the authored animation design. The source has condition recipes, but no current
general weapon-on-hit spell executor was found; a configured existing paralysis
rider is not a full Hold Person spell.

This supersedes the spell-by-spell expansion order and the suggestion that the
next main task should be another terrace VFX correction. Keep existing hard
terrain regressions, but develop and exercise gameplay on flat, bright land too.

1. **Use current game composition.** Build the existing direct fighter and
   sorcerer premades, canonical Goblins, a current bright battlefield, Game and
   Encounter. Install the existing opportunity-attack hook and native enemy
   controller. Do not revive obsolete player-creature catalog references or
   build a second rules system. Live session values belong to the application;
   rendering continues to consume retained facts.
2. **Connect complete gameplay histories.** Capture every actual root completed
   by each public action/controller/turn operation, then retain each root's own
   lineage. Extend the existing family capture/reducer for movement, attacks,
   rolls, condition lifecycle and turns using actual observed payloads. Senses
   already owns committed positions. Retain state facts and existing grants;
   do not copy live condition/handler/value graphs or invent a simulated condition.
   Ordinary causal/log-only events remain visible in coverage without owning
   duplicate mechanics.
3. **Replace fixed input with discovered choices.** The existing
   `get_available_actions` / `execute_available_action` boundary supplies action
   rows, typed targets, paths, costs and target allocation. Add a simple Pygame
   action/target surface and End Turn. Human commands wait for their settled
   presentation boundary; native enemy decisions can proceed ahead. One pending
   lineage deque and one active historical head remain the owners. Scripted
   validation uses this same command boundary.
4. **Represent the whole encounter.** Draw all known historical actors, resources,
   conditions and outcome text. Use existing authored body/movement/feedback
   contexts and installed spell capabilities; missing decorative media must not
   halt game progression. Asset completeness is explicit and separate from
   semantic/state coverage. Do not turn unknown recipes into fabricated authored
   VFX, silently lose their actual consequences, or create one executor per spell.
5. **Validate arrangements and play, not just one effect.** Use data cases for
   flat land at several distances/directions, swapped caster/recipient positions,
   all four cameras, and raised/lowered support. Execute movement, attacks,
   actual reactions, condition application/expiry, player changes and native
   enemy turns. Verify latest can advance during paused history and that player
   input resumes on the corresponding displayed state. Inspect real windows.
   Shared space defects belong to projection/depth owners; don't retune every
   spell against the same difficult stair.
6. **Keep asset work independent.** Dedicated work may import already-authored
   CodexFX exports and extend shared presentation capabilities. Existing source
   materializers/catalog mappings choose assets and recipes. Preserve their
   provenance and distinguish saved authoring from generated fallbacks. No Godot
   authoring or individual spell polish becomes a prerequisite to the game lane.
7. **Review the structure at working checkpoints.** Anti-slop review asks whether
   a change advances actual gameplay or merely expands a demonstration. Anti-OOP
   review checks existing ECS/public owners, passive histories, no second queue,
   and the import DAG. Use actual traces and playable results; do not accumulate
   hypothetical repair prerequisites. Continue the game work when an asset task
   finishes or the user asks a question.

**Current source findings:** direct premades already install standard actions and
publish their own births. Canonical Goblins need their normal composition call.
The obsolete encounter assembler's player-creature reference is unavailable;
use current direct builders without restoring it. Native controller action
boundaries already support independent enemy progression. Public probes emit
Move/Step, Attack/OA, Jump, damage-roll/applied facts, condition markers/expiry and
independent turn/round roots. These observations guide family-level integration.

## Playable checkpoint — 2026-09-10

`python -m game` now opens the actual encounter. The finite spell programs are
explicit references (`--reference`, `--magic-missile`, and their existing options).

| Owner | Connected behavior |
| --- | --- |
| `game/session.py` | Direct fighter/sorcerer builds, canonical Goblins, current Game/Encounter/native AI, actual action discovery, execution and terminal roots. |
| `game/controls.py` | Discovered actions/targets, multi-target allocation, map previews, costs/reasons and End Turn; no mechanics or scheduling. |
| `game/presentation.py` | Passive movement, attacks, conditions, HP, senses, corpses and turn histories, retaining actual grants and causal identities. |
| `game/encounter_play.py` | One pending deque and active historical head. Native decisions advance independently; human commands require the displayed human boundary. |
| `game/motion.py` | Original walk/jump clocks and heights; complete shared reaction groups, committed continuation or retained interrupted visual contact. |
| `game/visual_position.py`, `game/playback_frame.py` | Passive placement distinct from legal tiles, carried through head completion/idle; one shared game/review frame compositor. |
| `game/attack.py` | Original profile selection, melee contact/ranged release and body/delivery/damage join. No per-weapon implementation. |
| `game/choreography.py` | Shared standalone/reaction subtree compilation, authored child anchors and postorder recovery joins. |
| `game/scene.py`, existing drawers | All known historical actors, actual equipment/rig layers, visible conditions, HP, feedback and shared map projection. |

The independent art lane imported the existing CodexFX Rune Dart, the actual
premade appearance layers, and existing modular/Goblin movement and attack
clips. No new artwork was authored. The bright map's stone floor uses four
original Ground D1 poses, with source hashes in `game/data/stone_floor_source.json`.
The current local sprite totals are 273 NeuroClient PNGs (37.7 MB), one CodexFX
PNG (0.36 MB), and 14 fixed-rig PNGs (1.78 MB); these totals include earlier work.

Three integration corrections came from actual play, not injected mechanics:

- Portable-torch movement emits `SpatialChangeEvent.LIGHT_CHANGED` with a Tile
  identity. Capture must not classify that identity as a character.
- A dead actor's later TurnEnd can lack identity grants. Existing encounter
  projection retains the transition and hides the acting identity; capture now
  follows that rule instead of rejecting the entire operation.
- An observer can witness an opportunity attack and then die during it. Its
  historical attachment can use that child lineage's own initial grants;
  terminal grants and actual sensory removal remain unchanged.

Public validation covers a full round with paused history and independent enemy
progress, four flat layouts/cameras with swapped roles, real melee and A/B/A
volleys, and an actual encounter ending in round two. The ending run checks
movement/action/slot costs, condition membership, exact retained HP and closed
input afterward. Real X11 captures and results are in
`.runtime/encounter-layouts/validation.json` and
`.runtime/encounter-layouts/x11-completion-summary.json`. Pure history tests
also replay these retained facts after engine reset.

Validation results: the broad game suite completed with 471 passing tests and
two failures. The asset expectation now includes the four added stone poses;
all 49 asset checks pass. The remaining failure is the older door/light demo's
eight-second fresh-process startup budget: its functional assertions pass, but
an isolated normal-cache run takes 8.596 seconds on this workspace. Profiling
shows imports, tile construction and filesystem validation dominate; it does
not establish a new gameplay regression. The budget was not weakened. After
the final integration changes, 50 focused gameplay/history/drawing checks pass;
the encounter-completion check also passes. Changed production modules pass
Pyright, and the import-direction/cycle checks pass.

The anti-slop/anti-OOP checkpoint corrected stale input-readiness reporting,
starting a new head while paused, unreported unsupported payloads, and conversion
of jump lift from NeuroClient reference pixels. There is no new backend clock,
rules dispatcher, event registry, synthetic action root or second playback queue.

**Practical limits remain explicit:** the current encounter retains one player
viewpoint and an initially known actor set. Unbound action presentation shows
the actual resulting state/projected log and records coverage; it does not
invent authored media or block the engine. Shortbow/projectile delivery and
Jump reactions now use the shared composition. The current Goblin pack has no
bow body clip; it displays Idle with an explicit media gap while its authored
ranged delivery and damage play. The pre-motion reaction badge now executes.
Area/self/persistent spell presentation and broader roster/map/inventory UI
remain shared capability/content work. These are not prerequisites for each new
spell and must not turn into individual spell-polishing sessions.

The next implementation checkpoint should choose a **shared missing gameplay
capability from actual play**, consume its existing authored data where present,
and repeat the same full encounter, varied-space and history checks. Continue to
keep asset work parallel to that main lane. Do not call this first playable
encounter completion of the entire D&D game.

## Reaction composition checkpoint — 2026-09-10

The source comparison and honest coverage inventory are in
[ANIMATION_COMPOSITION_AUDIT.md](agent_docs/ANIMATION_COMPOSITION_AUDIT.md).
Imported JSON is not evidence that every field executes. Three spell drafts are
bound locally; Fire Bolt and Magic Missile execute, while Acid Splash requires
the unimplemented area primitive. Five attack recipe rows load, three with
selectable variants; the original source contains 88 action recipe rows.

The shared compositor keeps the actual hierarchy through technical events:
movement edge → reaction → direct on-hit or nested damage effects. Conditions
use their owning contact/condition frame, actual UUID membership and original
appearance recipes. Postorder composition waits for the complete children
before cast recovery. Neither continuation nor timing uses a condition-name
switch. Exact creature-to-rig associations now live in the packaged rig data.

The native longsword test configures the existing paralysis rider with its real
CON10 save. A failed save stops a living mover, a successful save or miss permits
the actual committed continuation, and death stops the edge. These outcomes
are checked for both walking and jumping after engine reset. Changing only the
Paralyzed alpha/duration extends the reaction join without changing engine facts.
A separate real Fire Bolt/concentration-removal lineage verifies that an
authored long fade delays cast recovery while release/impact/HP anchors stay fixed.
There is still no general item-on-hit spell executor; the configured rider is
not advertised as a full Hold Person proc.

All 141 original condition rows round-trip through the typed schema. Current
execution covers body color, alpha, composition and transition feedback;
equipment modifiers/replacement layers and other unimplemented domains remain
explicit. The Pygame adapter preserves the source per-slot color matrix,
hit-flash precedence and whole-actor alpha. Decorative feedback uses passive
tracks on the existing presentation clock, retains its frozen launch anchor and
outlives a finished root without delaying it or adding another action queue.

Verification: 40 combined attack/movement/condition/feedback checks pass, plus
two native cast-recovery cases. A final five-case feedback run adds a real
opportunity-reaction badge toggle check: authoring controls its display without
changing movement timing or the settled state. Six full-encounter cases and 13 existing
cast/equipment/history integration cases pass. Ranged coverage also includes
20 map arrangements/views and four settled death frames. The earlier shared
animation/source regression run passed 147 cases. Changed production modules
pass Pyright and all four selected import-DAG/direction checks pass.
The paused encounter test's frame guard is now 240: the actual newly animated
ranged attacks and Jump legs settle at frame 202; its state/timing assertions
were preserved. Evidence lives under `.runtime/reaction-composition`, including
32 real X11 frames of held reactions, condition appearance and final positions.
The final X11 encounter run ends in victory at frame 200, with all 26 retained
lineages settled and historical state equal to latest. Its only media gaps are
the fixed Goblin rig's missing ranged body/slash clips; captures and the exact
result are in `.runtime/reaction-composition/final-encounter.json` and the
adjacent `final-encounter` directory.

The anti-slop/anti-OOP review is recorded in the audit. Remaining source
capabilities should be connected through these owners, never through a growing
collection of spell-name or creature-name branches. Nested casts share the
compiler path but do not yet have a native weapon-proc gameplay test.

## 1. Authority and evidence

- [HISTORY_BEFORE_ME.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/HISTORY_BEFORE_ME.md) records historical intent, the failed architecture, July reconstruction and the overnight experiment.
- [CURRENT_CODEBASE_STUDY.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CURRENT_CODEBASE_STUDY.md) records present owners, source coverage and observed behavior. Its injected diagnostics and unverified concerns are not an implementation backlog.
- This plan defines the current objective, implementation sequence and acceptance. The appendices retain completed source/data/timing work so it is reused.

Read the affected owner notes and actual code before editing. The [branch guide](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CURRENT_BRANCH_DESIGN_GUIDE.md) and [in-process architecture roadmap](/mnt/c/users/tommaso/documents/dev/dnd_engine/DND_IN_PROCESS_PYGAME_SYSTEM_ARCHITECTURE_ROADMAP_2026-09-02.md) locate the existing architecture. Old branches and NeuroClient are references for intent, not replacement runtime dependencies.

A requirement belongs in the active work when it follows from the user's design or the concrete behavior being implemented. A gameplay bug needs a named mechanic, its supported interception point and an observable violation. A diagnostic that installs an arbitrary handler does not establish those semantics by itself. Optional robustness work becomes necessary when the selected caller or adapter actually introduces that exposure; it is not an automatic prerequisite to the first integration.

## 2. Foundation already available

| Area | Existing work to use | Actual integration work |
| --- | --- | --- |
| Mechanics | Entity/component composition, actions, conditions, modifiers, handlers, resources, spatial owners, Game and Encounter | Invoke the current public owners and retain their results. |
| Causality | EventQueue versions/lineages, parent-child references, reaction-trigger links and multi-target application identity; selected completed-cast capture | Feed retained casts to the application. Add other causal shapes when their gameplay case is selected. |
| Subjectivity | Event-time grants, senses/contact history and subjective combat-log projection | Apply existing disclosure meaning to the finite facts needed by this presentation. |
| NeuroStudio data | Original JSON plus output from the original offline TypeScript materializer | Load the local records through Python; do not remake recipes or generated defaults. |
| Animation | `compile_cast`, `sample_cast`, `crossed_anchors`, Python data loader/drawer and real cast binding in `game/combat.py` | Use the bound historical input in actual map playback. |
| Actor history | Explicit known-actor startup, passive actor facts, shared latest/historical reduction and authored appearance binding | Connect these values to the frame pump; demonstrate changing gear/contact when those actions are selected. |
| Height and rigs | Detached G5 support/duration adaptation, modular root rig and Goblin recipient rig | Use their metadata with actual map composition and actor identity. |
| Current Pygame app | `game.play` integrates input, independent latest reduction, historical playback and the existing map painter; `game.app.run` retains the door/light regression demo | Extend the selected combat outcome using these same owners. |
| Creature content | Existing declared builders and canonical creature materialization, including Goblin | Use the current creation/composition/deployment path and bind identity to presentation. |

The old P1/P2/G5 labels describe completed reference work. Their evidence is in appendix A; they are not tasks to restart.

## 3. Design commitments

### Existing mechanics remain authoritative

Entities compose data and systems. Conditions, modifiers, receipts, handlers, equipment and spatial effects retain their concrete owners and exact cleanup identities. Presentation must not reroll, apply conditions, tick durations, decide death, simulate targeting or manage a second copy of mechanics.

Interception is defined by the concrete Event family and producer. Counterspell interrupts CAST_SPELL/EXECUTION; Shield blocks the child TAKE_DAMAGE/EXECUTION; Death Ward modifies TAKE_DAMAGE/EFFECT before HP changes. DAMAGE_APPLIED records an already committed result. The same phase name does not imply universal cancellation, rollback or refund semantics. Preserve committed costs and the actual resulting lineage.

### Render complete lineages

Use the actual version UUIDs, logical lineages, parent-child references and explicit reaction-trigger links. Multi-target applications retain their existing identity, including repeated A/B/A targets. Fire Bolt does not need an invented AttackEvent child or a new application ID.

A delivery batch is not a render job. Follow the selected producer through its real required children and completion. Completeness follows the observer-permitted lineage being presented, using the existing relationship semantics.

### Retain the facts the presentation consumes

Latest backend state may advance while old work is on screen. Historical HP, life, support/contact, identity and equipment therefore cannot be fetched from current live entities during playback.

For each consumed fact, identify its producer, observation authority and capture boundary. Use existing passive values such as damage resolutions, item facts and sensory snapshots where applicable. Keep the existing finite ordinary Event space; do not introduce a parallel cue taxonomy or a universal object serializer.

For the selected cast, `capture_lineage` runs after the synchronous public operation and copies the consumed terminal facts from its actual descendants. This boundary preserves the values the current consumer needs. Reconsider a field's capture point when a selected gameplay case demonstrates a different lifetime.

Use the existing subjectivity rules without changing permitted detail. Unknown source, identification and location have distinct meanings. Resolve representation questions for the consumed family with valid examples and affected consumers; do not solve global source nullability or change information policy to make a fixture easy. The first fully observed cast can establish the connection without claiming unknown-observer support is complete.

### Separate current reduction from historical playback

Maintain latest subjective state and the historical state for the active lineage. The same reducer meaning should produce both latest results and the expected successor of the displayed history. Pending work retains facts; it does not need a world snapshot per action.

The active animation uses its own historical actor/contact/result values. Later reduction cannot change its elapsed time, gear or endpoints. When that animation finishes, the following lineage starts from the corresponding historical result. Preserve one owner of pending causal work and one active head; the sampler does not acquire another pending queue.

Use current cursors and generation information where the actual application needs them. The retained cast reducer already produces both latest and historical successors; the application should use that same operation.

### Preserve authored execution, space and rigs

NeuroStudio already defines preparation, body release, travel, impact, feedback, recovery and their overlap. Use the existing Python compiler/sampler and original timing oracle. Absolute elapsed time preserves pause, seek and large-delta behavior; queue depth never retimes the animation. TypeScript/Godot remain offline tools, not runtime requirements.

Packaged sprite groups map clips, rows, frames, FPS, slots and pivots to the root modular vocabulary. Use real clip capability and data overrides where necessary. Historical equipped items are distinct from temporary authored hiding/glow. Fixed sprites do not gain removable gear layers.

Use the existing 2.5D supports, map projection and painter ordering. The implemented G5 duration metric stays independent of camera movement. Engine range, visual travel distance, sprite padding and draw depth are different quantities; do not redesign them as one metric.

## 4. Earlier connection sequence — retained implementation evidence

### Step 1 — Close the first real lineage's contract

**Implemented for the selected known-actor positive hit.** The field mapping and actual public trace are in the [first cast contract](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CURRENT_CODEBASE_STUDY.md#first-cast-integration-contract--2026-09-09). The requirements below record that completed work.

Use one public Fire Bolt cast between known actors with the unchanged imported recipe. Start with the already-supported positive hit. Record only the facts needed to connect that real history to the sampler:

1. The public action/Encounter entry, actual root and child order, damage result and relevant life/contact changes. Reuse the existing hit/death traces; investigate only a missing junction.
2. A compact field mapping: source owner, permitted fact, capture point, passive representation, reducer use and authored consequence.
3. Historical actor/appearance/equipment/support initialization through current owners. Identify which values are already supplied and which finite binding is missing.
4. The files/functions that change and one concrete retained input example. Check the design with anti-slop and anti-OOP reviewers before editing shared contracts.

**Exit:** we can explain this actual cast from public input through its retained complete lineage to the existing `CastInput`-level requirements.

### Step 2 — Capture and reduce that history

**Implemented and verified for that case.** `seed_actors`, `capture_lineage` and `reduce_lineage` retain the startup/history and produce separate successors. Replay after engine reset passes.

Extend [game/presentation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/presentation.py) at the selected boundaries. Reuse EventQueue and existing information/log owners. Retain final accepted facts that the chosen reducer consumes, preserving exact causal relationships. Observation-only combat text continues through the existing log path; do not synthesize mechanics from prose.

Keep mechanics synchronous within each public operation. The async application yields between ordinary operations. Determine the selected lineage's completion from its actual producer/children. If a consumed required fact is missing or capture fails, report that failure; do not silently claim a complete cast. This does not require a fault-recovery or transaction framework.

Extend the current passive presentation data with the actor/vital/contact values this case needs. Keep latest reduction separate from the active historical scene; never alias a mutable latest target into that scene. Reuse one reduction meaning rather than implementing the rules twice.

**Exit:** the actual cast's retained facts survive later backend mutation and reduce to its expected values. No live Entity/GridMap lookup or rule execution occurs during that retained replay. This checks the selected families, not arbitrary engine-object serialization.

### Step 3 — Bind the existing authored executor

**Implemented and verified for positive hits and ordinary misses.** `bind_cast` supplies real contact, support, appearance, result and causal identity to the existing compiler. `resolve_actor_layers` uses existing rig metadata and the authored equipment ledger. The integration fixture uses stationary, unequipped modular actors; equipment variants and fixed-rig layers have separate binding tests.

Use semantic identity bindings to select the imported recipe. Adapt the existing [animation_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_types.py), [animation_data.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_data.py) and [animation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation.py) inputs only where the real history exposes a fixture limitation: absent single-target application ID, historical appearance/contact, or exact consequences.

Normal HP, temporary HP, packet damage and life state remain distinct facts in presentation state. A projectile arriving does not infer damage or death. Use actual child results without also applying aggregate totals. Preserve the source's joins, anchors, equipment overrides and disabled settings. The detached preview remains a reference.

**Exit:** the real retained positive hit uses the same compiler/sampler as the existing preview and matches its authored timing. Check immediate death when that selected result is added; use the actual later life fact. Extend other outcomes when selected, without claiming the first hit proves them all.

### Step 4 — Connect the same-thread frame pump and actual map

**Implemented for the selected two-cast scene.** `game.play` owns input time, one pending lineage deque and one active historical cast. `game.app.draw_frame` accepts already-built draw commands; it does not import animation schemas or own playback. The shared painter places boundaries at their actual half-edge sort contacts while preserving authored image pivots.

Read the affected [game/app.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/app.py) drawing/projection helpers before editing; the earlier study did not reread all of them. Intake/reduction can advance while Pygame handles input/camera and samples the current historical animation. Preload required media before starting its visual clock.

Integrate [animation_draw.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_draw.py) into the existing map painter. Reuse current support/shadow/depth conventions and the G5 adapter. Check an actual raised/lowered support and a wall/door/cliff occlusion case; detached stage rendering alone does not prove map composition.

Reuse ordinary sample → draw → display.flip → progress accounting. The displayed values/pose must match the current historical result before starting the next head. The sampler remains a pure function of its retained input and elapsed time, with authored durations controlling playback.

**Exit:** the selected cast appears on the real map with correct contacts/depth and authored timing. Camera rotation changes projection without changing duration. Existing map/door/light behavior remains correct. Run the existing loader/drawing checks and add only integration-specific coverage.

### Step 5 — Prove independent progression and open the next capability

**Application proof now passes.** `test_combat_play.py` exercises actual SDL input, map draw and publication: later reduction occurs during the first displayed travel, and a paused first sample stays fixed while latest HP advances. Each next head begins at elapsed zero from its historical predecessor. A real X11 window also completed the two-cast run; the earlier library-only proof remains useful for retained replay.

Use a finite script of two legal public casts, through the current action/turn owners. Advance the first animation into release/travel, execute/capture/reduce the later cast, then continue rendering the first.

**Central acceptance:** later reduction advances, while the first cast's samples, historical appearance/contact/HP and timing match the run with no later cast pending. The next head begins from the first head's historical result. A second compatible target/distance changes input, not the executor design.

Once this proof works, select the next real case from section 5. Before allowing unrestricted player choices, support the outcomes those choices can actually produce or clearly limit the exposed capability. Ordinary misses, Counterspell, temporary HP and concentration are useful real next cases; they are not all prerequisites to showing the first positive cast.

## 5. Expand by actual gameplay need

Each next case extends the demonstrated structure through the current mechanic and existing presentation data. Select a concrete case after the integrated two-cast proof. Reuse the same capture/reduction, semantic binding, authored executor and painter; extend the affected owner when the new case needs a capability. This table is a capability roadmap, not a prerequisite checklist or permission for a broad engine cleanup.

| Next case | What to preserve and demonstrate |
| --- | --- |
| Miss/prevention/reaction | Use the actual attack result, damage prevention or Counterspell lineage. Reuse supported no-damage contact/disposition behavior and existing recipes; do not invent cast-EFFECT vetoes. |
| Temporary HP, concentration and additional life states | Retain actual damage/cleanup/life facts. DYING, STABLE and DEAD come from the engine. |
| Repeated A/B/A applications | Existing Magic Missile data, one cast body, three real applications and separate arrival/consequence values. Check against original runtime semantics rather than collapsing by target. |
| Weapons and equipment changes | Preserve historical item identity/loadout, actual damage facts and existing causal relationships as equipment changes during playback. |
| Movement, opportunity attacks and terrain | Follow real Move/Step/sensory histories, committed positions and reactions. Jump, forced movement and connectors retain their own trajectories and cost points. |
| Conditions, areas, healing and other delivery shapes | Reuse existing Studio unions/context recipes and current condition/spatial/healing owners. Add only primitives the concrete case needs. |
| Fixed creatures and additional rigs | Use existing canonical creature creation, then identity-to-rig binding. `materialize_creature` already builds a real Goblin through current content owners; a new monster migration is not required merely to use the Goblin recipient rig. |
| Small playable encounter | Author backend map/height/doors/light/objects/actors together. Script and human input use the same legal action/turn path. Include a meaningful selected reaction or condition and two rigs when their bindings are ready. |

Use [dnd/content_system/creature_materialization.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content_system/creature_materialization.py) and current declared builders before declaring a creature capability missing. The older [content migration record](/mnt/c/users/tommaso/documents/dev/dnd_engine/DND_JULY_RECONSTRUCTION_CONTENT_RECOVERY_AUDIT_AND_MIGRATION_PLAN_2026-08-30.md) is background; its cut numbers are not present-day gates.

Portraits/icons, further demon/undead/animal rigs and offline Godot VFX enter when selected gameplay needs them. Preserve original assets/provenance and report data/binary sizes separately. Old machinery is retired only when the actual replacement is established; no cleanup campaign is implied by a visual integration task.

## 6. Verification proportional to the change

Read [HOW_TO_TEST.MD](/mnt/c/users/tommaso/documents/dev/dnd_engine/HOW_TO_TEST.MD). State the requested behavior, real boundary, input and observable result before writing tests. Existing authored timing, rig, drawing and mechanics tests are assets to reuse.

The first integration needs these proofs:

- Real public cast, actual required children/results and permitted retained facts.
- Retained replay without live mechanics lookups, and separate ownership of active history and latest state.
- Existing authored timing and actual map composition after that layer is connected.
- The two-cast ahead-of-display proof.
- Relevant regressions/type/import checks for the changed owners, with unrelated baseline failures reported honestly.

Add tests for errors actually introduced by the adapter: a required value/media cannot silently disappear, and an incomplete capture cannot be reported as success. Reuse existing reset and loader behavior. Further robustness work follows the actual exposure introduced by a selected capability.

Match claims to evidence. A successful finite cast does not certify all player actions; a dummy renderer does not certify real map output; source inspection is not a gameplay reproduction. Conversely, a hypothetical API misuse is not evidence that shipped mechanics need repair.

## 7. Review and code discipline

**Anti-slop reviewer:** first verify that each proposed requirement comes from the user's design, the selected feature or an actual owner contract. Identify the real gameplay subscriber before approving a mechanics-interception fix. Check source reuse and the independent-history proof. Reject mandatory hypothetical hardening, copied timelines, invented IDs, blanket graph closure and unrelated cleanup.

**Anti-OOP reviewer:** check specialized ECS ownership, exact modifier/condition/receipt cleanup, data-oriented rig/appearance binding and the import DAG. Reject new managers, generic rollback/contribution frameworks, late imports and reflection used to bypass dependencies.

Reviewers may cover multiple roles. Inspect the first concrete retained example before shared-contract edits and review the actual two-cast/map results before expanding. A review count is not evidence that its premise was correct; reviewers must challenge the requirement itself.

Production dependencies remain a DAG: the application calls public mechanics and presentation; capture reads allowed facts; animation consumes passive data; drawing owns Pygame/assets. Backend mechanics contain no sprite paths, authored timing or renderer readiness. Add a module/class only for a demonstrated responsibility; no module is mandated merely because the plan names an ownership concern.

Report production code, tests, original JSON, generated output and media separately. Continue within the active cut; ask only about an actual unresolved change to accepted gameplay/design. Do not ask the user to repeat the established framing or treat every source observation as a new blocker.

## 8. Completed integration checkpoints

The first retained cast connection is implemented. No backend mechanics repair was needed for it.

| Work | Current evidence |
| --- | --- |
| Public producer and complete lineage | Two discovered Fire Bolt casts through `Encounter.execute_action`, spending actual actions on successive legal turns. |
| Historical reduction and authored binding | Five passing integration cases in `tests/game/test_combat_history.py`, including Goblin survival/death; unchanged historical samples and replay after engine reset. |
| Appearance binding | Existing body/rig metadata and item-visual ledger feed neutral `RigLayer` values. Separate appearance tests cover authored equipment, visibility/active set and fixed Goblin layers. |
| Actual app scheduling and map composition | Five SDL frame-loop cases pass, including input/reduction during paused playback, miss and canonical Goblin survival/death. Earlier real X11 hit/miss playback completed both casts; six raster cases verify cliff and front/back straight/corner wall overlap. |
| Ordinary miss | Public MISS/CRIT_MISS bind to the existing no-damage input, retain the projected miss text and replay after engine reset. A third SDL app case verifies an actual missed second cast through the same map loop. |
| Canonical fixed creature | Actual materialization supplies full identity, 10 HP, scale 0.82, darkvision and default equipment. The existing fixed rig renders hit/miss/death results. The real internal damage marker and death/perceivability/sensory descendants remain retained causal children. |

**Current equipment cut completed:** retained replacement now drives actual playback using NeuroClient's original context, imported Melee3 media and shared actor drawing. Anti-slop and anti-OOP reviews found no blocking issue in the selected contract. One pending deque handles both cast and equipment roots. Item identities change at historical completion, independently of latest state.

**Repeated-application checkpoint:** the roadmap's A/B/A Magic Missile case tests multiple applications within one complete cast lineage. Its actual producer and existing materialized recipe were studied together before extending the executor, as recorded below. Equipment playback alone did not establish this contract; its implementation now shares the same cast executor and queue.

### Implemented: one Magic Missile lineage, ordered A/B/A applications

The public producer and original runtime have now been traced by anti-OOP and
anti-slop reviewers. A raised-map probe succeeds with the existing capture and
reducer unchanged: caster (16,25), A (16,20), B (18,20), supports 0/2/2. Public
`execute_by_index` supplies `extra_target_uuids=[B,A]` during an actual Encounter
turn. Two casts spend two actions and two level-1 slots. Each complete root
retains three distinct Spell applications with indices 0/1/2, each with its own
TakeDamage → DamageApplied descendants. Join terminal records through their
existing lineage links; parent version UUIDs can refer to intermediate phases.

**Contract:** the first root applies damage 5/5/2 (A 80→75→73, B 80→75); the next
root applies 3/2/4 (A 73→70→66, B 75→73). Latest may reach those final values while
the first root is still displayed. A/B/A remains three applications under one
cast body, one historical head and one queue. Each packet retains its actual
after-value and identity; actor deduplication is only for drawing one body.

1. Generalize the existing cast input/timeline to an ordered application tuple.
   Fire Bolt becomes the one-application case; do not retain duplicate singular
   fields or implement a second full cast executor for volleys. Samples expose
   per-actor vitals and distinct application effects. Existing body/equipment
   helpers and the same pending deque remain the owners.
2. Reuse the exact imported Magic Missile draft: Special1, speed 1, release frame
   8, launch stagger 80 ms, Bézier curvature .3 and same-target spread. Add the
   original Special1 sheets through the pinned importer. Geometry dart style
   already exists in the imported generated profile. Missing spell damage
   overrides preserve the imported global vital context and actual Force
   palette; do not edit the source JSON to fill the absence.
3. Use one body sample per recipient. Repeated TakingHit reenters and restarts
   that body, with source waiter/callback behavior accounted for. Current Magic
   Missile defaults put HP/flash/number at frame 0. Preserve separate packet
   feedback and absolute after-values. Sprite Fire Bolt retains its existing
   delayed anchors. Distinct sprite/geometry sample records avoid fake assets.
4. Preserve authored screen-space curvature and the existing independent
   height/support adaptation. Geometry has no sprite canvas offset and no
   separate impact sprite. Depth uses the curved head's ground position after
   removing support/apex lift; the trail shares its head's painter key. Original
   geometry keeps eight rendered-frame trail points; use a documented 60 Hz
   reference cadence for deterministic seeking, matching the game's nominal
   display cadence without coupling trail history to actual frame rate. This
   is a visual sampling adaptation, not a change to launch/arrival timing.
   Actual map inspection also showed geometry launching below the feet. The
   original helper forces an actor-art root despite the generated geometry's
   `tileCenter` basis; its default lift does not compensate that root. Honor the
   existing ground basis for point geometry in projection, preserving sprite
   registration and the compiled source clock. Compare actual frames and
   record this explicit source-runtime correction; do not invent a second
   alignment catalog or edit imported JSON.
   Keep the interpolated authored vertical lift in visual height during depth
   inversion too. Otherwise an above-floor dart moves backward in ground depth
   and its target tile covers the head, as the actual near-arrival frame showed.
   Forward/side offsets and screen curvature still belong to planar placement.
5. Connect optional `--magic-missile` to the finite three-actor script and actual
   map loop. Preserve the ordinary Fire Bolt/equipment variants. Validate two
   legal volleys, paused independent reduction, retained replay, repeated A
   body/HP/number samples, original launch/arrival timings, camera projection
   and map output. Extend the existing offline oracle using the unchanged
   source CastClip/TakeDamage/AnimatedEntity runtime, rather than copying the
   editor's per-target earliest-impact summary.
6. Review the resulting structure with both reviewers before completion. Record
   source/runtime parity, explicit visual adaptations, scoped code/media size
   and real-window evidence. No mechanics repair, new disclosure policy,
   reaction framework or new scheduling owner is part of this positive case.

**Result, 2026-09-10:** `python -m game --magic-missile` now runs the two real
volleys; `--replace-weapon` also works with all three actors. Paused playback
retains A/B at 80/80 while latest reaches 66/73. Each dart preserves its own
application ID, after-value and number; repeated A restarts one reaction body.
The original runtime oracle agrees on all 66 observed body frames and explicitly
accounts for its 1 ms callback pump. The existing Fire Bolt oracle still
reproduces byte for byte. Relevant history/playback/drawing/projection tests,
production type checking, four dependency checks and all 81 import outputs pass.
Both final reviews found the selected ownership coherent. Ten original Special1
PNGs add 1,409,000 bytes; no backend mechanics file changed in this session.

Actual X11 playback completed both casts and all six roots with the equipment
option, then matched historical to latest. Captures and a five-second recording
are under `.runtime/magic-missile-play/`; four camera views were inspected.
The observed target-floor coverage in the front view was corrected by separating
authored vertical lift from planar depth; the actual map regression now passes.
The whole-tile painter can still cover approaching darts in reverse views;
some mid-flight curves also remain occluded near the terrace.
Keep that concrete visual limitation distinct from timeline/state correctness.
The next visual review should use the recorded frames to distinguish path
placement from painter ordering before proposing another change; there is no new mechanics
repair or general collision-routing prerequisite here. Detailed source owners,
commands and evidence are in `agent_docs/CURRENT_CODEBASE_STUDY.md`.

**First equipment connection completed:** public same-slot dagger→shortsword replacement produces four separate completed roots. They remain unchanged; slot-transition roots explain the operation, and cold item-location after-values update retained items/slots. Completion order allows independent declarations to overlap. The public test proves immutable earlier appearances and replay after reset; ten cast/history/miss/import regressions pass. The original frame-4 callback changes active weapon set, while replacement item identities install at historical frame completion; this replacement keeps MELEE unchanged. Reuse that distinction rather than inventing a universal gear-change anchor.

### Completed equipment session: equipment between two casts

Budget approximately 2–3 hours of useful work; finish on evidence, not on elapsed time. The user need not supply another implementation plan or restart work after a question.

**Observable outcome:** run a legal Fire Bolt with a dagger equipped, replace it through the public equipment owner, then cast again with the shortsword. Latest reduction can reach the second cast while the first historical cast still plays. The old dagger remains throughout that cast and the equipment gesture; the shortsword appears at the gesture's completion and belongs to the second historical cast. Both actors remain on the real raised map.

1. **Contract and ownership review (about 25 minutes).** Anti-slop and anti-OOP reviewers inspect the actual producer, original context and current drawing/application boundaries. Keep all four roots separate. Attach the single gesture to the incoming item-location fact that changes resolved visible layers; consume cause-only and unchanged-appearance roots without invented animations. This adapts the original batch-attached loadout gesture to the current per-lineage boundary, rather than recreating old batch machinery.
2. **Authored body and media (about 30 minutes).** Type the existing `equipment_transition` JSON; reuse Taunt, speed 3 and last-index completion (388.889 ms on this rig). Frame 4 selects stance in the source; unchanged MELEE has no mutation there. Add Melee3 through the pinned importer. Extract shared body loading/drawing from the cast drawer so equipment does not need a fake spell or projectile.
3. **Real mixed playback (about 55 minutes).** Add an optional replacement to the finite public input script. Deliver the four roots at the equipment command's input deadline and the next legal cast at its own deadline. Use the existing single pending deque and one active head. Bind each historical head before its visual clock starts; preserve historical appearance, support, facing and the other actor's body. Load its required pixels before playback. No backend mechanics change is planned.
4. **Self-validation (about 35 minutes).** Exercise the pure body timeline at frame 4, completion and a large time step; replay retained inputs after reset. Use the actual SDL loop to show latest gear/HP advancing during an unchanged paused first sample, dagger during the gesture, shortsword on the next cast, and matching final historical/latest values. Run relevant source/timing/appearance/map regressions and type/import checks. Review real-window playback and visible gear in all four camera orientations; retain a reproducible clip.
5. **Design review and handoff evidence (about 25 minutes).** Anti-slop checks original timing, complete roots and scope; anti-OOP checks passive records, shared drawer ownership and the import DAG. Address concrete findings, remove unnecessary intermediate scaffolding, and document actual behavior, commands, limitations and code/data/media sizes. Do not expand into a new gameplay family merely to fill the time budget.

At each checkpoint, reconsider the overall structure before adding the next part. Passing tests alone do not justify a new abstraction. Completion is a runnable, reviewed mixed sequence with independent historical playback, not a collection of disconnected helpers.

**Session result:** all five checkpoints are complete. The three public commands deliver six separate completed lineages. Shared actor pixels are preloaded per head, old/new appearances are explicit immutable values, and equipment retains the previous displayed facing. The sampler remains renderer-independent; Pygame draws bodies through the same actor/shadow helper used by casts. The original context's nonempty media tracks and active-set changes remain outside this same-MELEE case.

Validation: seven SDL app cases, nine retained-history/miss cases, four dependency/import rules, the existing timing/rig/map/source regressions and changed-file Pyright all pass. Real X11 runs in quadrants 0–3 each complete six roots and reconcile history; the latter runs include canonical Goblin miss and death. Terrain still occludes actors where appropriate. `.runtime/equipment-play/playback.mp4` and `.gif` record the real frame loop, with source frames and wall-clock durations retained under `recording/`. Eight production Python files were extended/refactored, plus the offline importer; five original PNGs add **627,398 bytes**. The importer reproduces all **71** outputs, with original JSON and existing materialized recipes unchanged.

**Completed height adaptation:** one frozen presentation input, `travel_apex_steps`, defaults to zero. The existing finite terrace scene supplies 1 step: the full-cell support-envelope minimum, measured at the upper stair's entry rather than only its center. Both drawers consume the same sampled height; projected fine rotation follows the vertical tangent and retains the incoming tangent at impact. Original JSON, facing rows, offsets, authored clocks and backend targeting retain their owners. This is scene-authored presentation geometry, not automatic routing for arbitrary spells or terrain. Acceptance covers attachments, full-cell stair clearance, all four views, impact continuity and the existing independent-history app loop.

**Review checkpoint:** anti-slop and anti-OOP reviewers examined the integrated input/history/frame ownership and actual map result. The Goblin review checked canonical input, full content key and the real marker. Both roles then traced the lethal input: initial-root identity/location establishes its historical participants, later terminal grants remain unchanged, and actual contact loss still reduces. No condition simulator or serializer framework was added. Stair review confirmed the explicit scene apex, shared height ownership, original timing, fine-rotation adaptation and all four map views. Equipment review confirmed original body fields/bounds, completion-only item replacement, facing continuity, independent complete roots and the shared drawer's limited ownership.

The [plan audit record](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CURRENT_CODEBASE_STUDY.md#planning-requirement-audit--2026-09-09) names the withdrawn or narrowed items and why. It is a record of corrections, not another task list.

## Appendix A: completed foundation and source reference

These are retained evidence records from 2026-09-08, not fresh test results from this plan rewrite. They preserve what is implemented and why it should be reused. Detailed present mechanics and the later reread's exact test commands remain in CURRENT_CODEBASE_STUDY.

### A1. Local NeuroStudio data and original materialization

<a id="113-p1--import-source-data-and-export-what-already-exists-in-ts"></a>

The P1 source import is implemented in [devtools/import_neuroclient_presentation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/devtools/import_neuroclient_presentation.py); local usage/provenance is in [game/data/neuroclient/README.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/neuroclient/README.md). The legacy anchor above preserves the existing data README's link.

NeuroClient source is `/home/tommaso/Dev/NeuroClient/app` at `d274f2d62ca9c1c5ed62a77841cacf6cc0347491`. Original JSON stays byte-preserved beside generated outputs. The offline tool calls the original TypeScript validators/materializer with explicit current catalog evidence; Python does not recreate generated defaults or merge rules.

| Reused source under NeuroClient app | Recorded content |
| --- | --- |
| `public/studio/spell-studio-drafts.json` | Version 6; exact saved Fire Bolt and Acid Splash overrides. |
| `public/studio/spell-projectile-assets.json` | Twenty projectile asset descriptions. |
| `src/render/data/animation/generatedSpellPresentationProfile.json` | Version 8 generated defaults, consumed by the original materializer. |
| `contentActionPresentationRecipes.json` in the same animation directory | Version 13; 88 action recipes. |
| `actionContextPresentation.json` | Version 17; eight contexts. |
| `actionPresentationDispositions.json` | Version 4; three entries. |
| `conditionPresentation.json` | Version 12; 141 recipes. |
| `actionMediaAssets.json` | Version 1; 23 media descriptions. |
| Palette/hue and actor/ancestry profile/binding JSON | Original presentation/color/identity inputs retained as source material. |

The two saved overrides are not the full authored population: generated baselines and exact overrides are merged by the existing owner. The current exported set contains Fire Bolt, Acid Splash and a generated-only Magic Missile case. Their imported records do not certify that every delivery/media capability is executable.

The unmodified Fire Bolt reference retains Attack5/release frame 7, hidden main weapon, Magic2 glow and original colors; disabled Effect1; disabled Taunt recovery at speed 1; prepare at body frame 1; the existing `lelu_fire_strike_128_pixel_lab_fire24_px8` prepare/travel/impact sprite; travel at 180 reference pixels/second with 150ms minimum and 24 FPS; original source/target anchors; and damage delay 15ms with flash/number/death fields at frames 5/7/12. Those values are source data, not settings to redesign.

**Recorded P1 evidence:** initial export/check reproduced 57 outputs. Five detached artifact tests and an earlier combined run including 49 existing asset tests passed; importer Pyright was clean. Missing/corrupt output, destination collision and a temporary Git checkout with `core.autocrlf=true` exercised failure/byte-preservation. Initial import contained 14 original JSON files (22,100 existing authored lines), generated bindings/provenance and 38 PNGs (5,215,146 bytes).

P2 recovery subsequently added nine original Taunt sheets, yielding 47 PNGs/6,412,169 bytes and 66 reproducible enumerated source-import outputs. No old TS application, SDK runtime or server was vendored. Additional import follows this existing route with exact provenance and local URL bindings.

### A2. Python timing, drawing and actual source oracle

The implemented owners are [game/animation_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_types.py), [animation_data.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_data.py), [animation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation.py), [animation_draw.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_draw.py) and [animation_preview.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_preview.py). Typed source loading and passive rig metadata feed an absolute-time compiler/sampler. The drawer owns preloaded pixels/fonts and projection, without live Entity lookups or clock advancement. The preview uses this same execution path.

[devtools/trace_neuroclient_animation.ts](/mnt/c/users/tommaso/documents/dev/dnd_engine/devtools/trace_neuroclient_animation.ts) runs the original clip/queue/FSM owners offline. Its retained oracle is [tests/game/fixtures/neuroclient_animation_timing.json](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/fixtures/neuroclient_animation_timing.json). Original execution uses supplied 1ms frame delivery, with diagnostics/texture/font/GPU IO and watchdog timing substituted. It is source timing evidence, not a runnable current SDK integration or GPU pixel parity proof.

The source runtime ends a 15-frame body at its last index-14 boundary; the editor's count/FPS duration differs. In the recorded ordinary case release occurs at 584ms and settlement at 2611ms. At body speed 2, release-frame crossing occurs at 292ms but launch waits until 542ms because preparation still joins. The saved main-weapon override and cast layers clear at Casting exit. NeuroClient's separate `hiddenSlots` visibility scope restores after the body/delivery join; the selected oracle has `hiddenSlots=[]` and uses the action-VFX weapon override. Preserve these distinct owners when extending support. Editor bar estimates are not the execution oracle.

The original runtime also starts children late after a single 1500ms hitch. Python's absolute sampling deliberately corrects that large-delta behavior by evaluating remaining elapsed time and crossed anchors; it does not change saved recipe values or normal timing relationships. Repeated-target editor summaries choose the earliest impact per target and cannot replace application-specific runtime evidence.

Enabled recovery is already implemented; `--recovery` selects a validated variant without changing the saved disabled default. Required body/delivery work joins before recovery; decorative feedback tails do not become a new queue barrier. Disabled floating-number display does not remove the permitted HP anchor. Life uses the existing passive LifeState type; the selected death-only reference does not implement engine DYING/STABLE merely because a source animation FSM used the label “Dying.”

**Recorded P2 evidence:** 58 evaluator/data, five artifact and four Pygame boundary cases passed together (67 in 7.34s), alongside the three relevant architecture checks and clean changed-Python Pyright. Ordinary travel, lethal speed-2 and recovery captures were inspected. Preload failure, rendering after temporary source-link removal and seek pixel equality were exercised. Later G5/rig selections supersede the combined count without erasing its original scope.

Recorded P2 limits included tangent-facing/subpixel no-travel cases, selected optional-media policies and some color/blend/equipment modes. Original unused data remains present. Magic Missile's later selected implementation is recorded in §8; Acid Splash still has imported data without an executable-family claim.

The original Fire Bolt strip appears high over half-scale actors because of its actual cell content and pivot. No compensating art offset was introduced. Adjusting that visible authored binding would be a separate data decision, not a time-correction shortcut.

### A3. Implemented height/contact adaptation

The engine has one support per XY, with five-foot height steps. July's 128×64 projection and 64px lift per step are twice NeuroClient's 64×32 reference scale before zoom. Contacts, authored local offsets and camera transforms retain separate meanings.

The completed detached G5 adaptation keeps the camera-0 flat reference endpoint delta after authored offsets and adds height independently:

```text
distance_reference_px = hypot(flat_dx, flat_dy, 32 * difference_in_5ft_steps)
travel_ms = max(saved_minimum_ms, 1000 * distance_reference_px / saved_speed_px_per_second)
```

This preserves the original direction-dependent isometric flat timing. It is a visual reference metric, not engine range or Euclidean feet. Camera changes reproject frozen endpoints without recomputing duration. View-local sprite padding is not inverse-projected into world XY and rotated.

| Unmodified Fire Bolt; actor visual scale 0.5 | Flat delta | Height component | Recorded travel |
| --- | --- | --- | --- |
| `(0,0,0ft)` to `(3,-3,0ft)` | `(152,0)` reference px | 0px | 844.444444ms |
| Same target at 5ft | `(152,0)` | 32px | 862.955015ms |
| `(0,0,0ft)` to `(1,1,5ft)`, collapsed support projection in quadrant 0 | `(0,8)` after source inset clamping | 32px | 183.249139ms |

**Recorded G5 evidence:** 25 spatial cases added; 92 focused cases passed together in 8.42s, changed Python type-checks passed, and raised/four-view/collapsed/recovery captures were inspected. These prove detached contacts/time/reprojection. They do not prove joint wall/cliff/door occlusion; that remains step 4.

The reference preloader measured 150MiB of default four-view media buffers and 183.75MiB with recovery. A separate P2 SDL-dummy diagnostic measured preload 761ms and clear/draw median 0.52ms/p95 1.34ms over 121 samples with one warmup. These exclude full engine, UI and frame publication costs, may use warm filesystem data, and establish no integrated-game performance threshold.

### A4. Root and Goblin rig reference; other assets

`BodyClip`/`BodyRig` and `ActorContact.rig_id` already select per-actor metadata through the shared compiler, sampler and drawer. [game/data/rigs/goblin01.json](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/rigs/goblin01.json) maps Goblin 01 Idle, TakeDamage 1 and Die 1 to the root vocabulary. Six original body/shadow PNGs (695,418 bytes) are reproduced by [devtools/import_fixed_rig.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/devtools/import_fixed_rig.py); current combined imported media totals 53 PNGs/7,107,587 bytes.

The selected Goblin sheets have fifteen 128px frames in eight rows. 12 FPS, support pixel `(64,87)` and shadow alpha 0.5 are explicit reviewed adaptations, not claimed vendor metadata. Original PNG bytes, including alpha=1 residue, are preserved. Fixed weapons remain baked into the body. Goblin casting fails on missing clip/capability data; recipient compatibility is the implemented scope.

**Recorded rig evidence:** 141 combined animation/rig/drawer/artifact cases passed in 24.41s; three architecture checks passed in 4.84s; changed runtime/importer Pyright was clean. Actual ZIP reproduction, eight-direction row checks, unchanged root-stage pixels and raised Goblin travel/hit/death/recovery captures were verified. Hypothetical alternate-count metadata tests do not claim the real PNGs have different geometry.

Read-only source inventory also selected Demon Beast 1 and undead 5Archer as promising future groups. Their common naming is compatible enough for direct mapping, but actual clips/capabilities remain decisive. Goblin Block has six columns, Demon Beast Block seven; skeleton 6Warrior has truncated TakeDamage sheets and a blank Special1 column. Skeleton 5Archer row order was matched to named direction frames; the selected Goblin/demon PNG-only packs lack equivalent textual metadata. No broad rig inference or universal pack importer is needed.

User-supplied sources remain:

- NeuroClient modular layers, portraits, spell icons and authored JSON.
- `C:\Users\tommaso\Downloads\2D Orcs and Goblins - TopDown - V1.0.zip`.
- `C:\Users\tommaso\Downloads\2D Demons - TopDown assetpack v1.1.zip`.
- `C:\Users\tommaso\Documents\assets\smallscale`, including the undead pack.
- NeuroVFX/CodexFX, for offline Godot-authored and exported media.

Demons/skeletons, more maps, portraits/icons and beam media are future selected imports, not prerequisites for the first lineage connection. Record code/data/binary sizes separately when importing them. Runtime uses only contained local resources.

Existing preview commands remain useful regression/inspection tools:

```bash
python -m game.animation_preview
python -m game.animation_preview --target-rig smallscale.goblin01 --target-height-steps 1
python -m game.animation_preview --lethal --recovery --quadrant 3
python -m game.animation_preview --headless --at-ms 900 --capture /absolute/path/fire.png
```

Space pauses; replay/seek, Q/E camera turns, `--cast-speed`, `--playback-rate` and `--collapsed` exercise the same selected reference. None of these commands runs an integrated combat encounter.

### A5. Event registry correction

Event now inherits BaseModel directly and remains a typed runtime object with its existing fields/lifecycle. EventQueue owns every registered version; BaseObject no longer retains only the constructor version. Sneak Attack's maintained lookup uses EventQueue; sensory replay still rejects nested runtime Events. Required source UUID, UUID coercion, subjectivity, handler behavior and parent/turn semantics were preserved.

**Recorded evidence:** 152 relevant behavioral checks and three architecture checks passed. Common Event JSON schema matched except registry documentation; unregistered round-trip values and missing/null-source rejection remained intact. The two changed production files had 21 net new lines. Changed-production Pyright still reported two diagnostics also reproduced on isolated `16a6bfe`: the existing validator-proxy call in events.py and anchor_uuid override in traits.py. This is explicitly not a clean-type-check claim.

Registration opt-out still does not guarantee passive construction. Nested DiceRoll construction registers; Event/ActionEvent construction can perform parent/turn/binding work. A diagnostic invalid ActionEvent registered before an after-validator rejected it. Account for these contracts only where the selected retained fields require constructing those types; no global constructor rewrite is implied.

## Appendix B: prior public cast traces and unresolved evidence

These diagnostics preceded the broad owner reread. They are retained factual evidence, not a replacement forward sequence or a current passing gameplay milestone. The later study adds complete condition, handler, value, spatial and content context.

### B1. Public hit, miss and life ordering

`FireBolt.apply()` produced 15 stored versions for a nonlethal hit, 26 for an immediate-death hit and seven for a miss. Hit input used fixed d20=18/d10=8; miss used d20=2. Fire Bolt's SpellEvent carries the attack result; there is no AttackEvent child or explicit single-target application ID.

| Immediate-death target starts at 5 HP, death saves disabled | Recorded HP | Recorded life |
| --- | --- | --- |
| Spell execution after action cost | 5 | ALIVE |
| Attack-d20 completion / spell EFFECT | 5 | ALIVE |
| DamageApplied COMPLETION | -3 | ALIVE |
| Later sensory/life transition facts | -3 | DEAD |
| Death, TakeDamage and root Spell completions | -3 | DEAD |
| Action batch notification and public spell return | -3 | DEAD |

Both the damage after-value and subsequent life fact matter. Positive damage's EFFECT subscribers can add saves, concentration/condition removal and reactions. A later live snapshot cannot replace the earlier retained facts, and a damage child completion is not the whole rendering unit.

### B2. Cancellation, reaction and exception

- An ordinary CAST_SPELL/EFFECT handler canceled Fire Bolt, but its public return was CANCEL while HP still fell from 30 to 22 and DamageApplied completed with 8 damage. This used an injected handler, not a shipped mechanic. The subsequent speculative patch and its tests were withdrawn. This diagnostic is not evidence of a shipped gameplay defect.
- Real Counterspell produced six stored versions and no damage, with the caster's action already spent. Reaction events have `parent_event=None`; `triggered_event_uuid` and `triggered_lineage_uuid` carry their relationship.
- Deliberate fixed-dice exhaustion during damage raised after spending the action. The batch still flushed six versions ending at Spell EFFECT, without a completed root. This proves the failure boundary, not normal dice-source failure.
- Queue observer callbacks run before ordinary mechanical dispatch and swallow observer exceptions. A callback must retain its own failure status; throwing from capture neither stops mechanics nor guarantees valid delivery.

SpellAction releases cast-local contribution claims after BaseAction's inner batch exits, and Encounter can perform post-action death checks. This is why public-operation accounting must be named accurately while complete existing lineages remain the presentation units.

### B3. Information and passive representation

The current same-model combat-log projector and observer-specific sensory replay are established owners. The targeted study found no existing ordinary same-Event projector to reuse wholesale; legacy ProjectedEventSlot retains the original Event, and the old server mapper emits a separate cue vocabulary.

The old mapper is a bounded rule witness for the independently unknown attacker/identified victim case, preserving exact permitted damage/HP. It is not a runnable current adapter or an import target. The plan requires a valid selected Event representation following that existing meaning; it authorizes neither a new withholding policy nor the withdrawn global source-nullability change.

BaseCost, DamageResolution and item presentation facts already supply useful value contracts. DiceRoll is mutable and registers on construction. SpellEvent attack/AC/damage fields can retain live value graphs; condition application/removal Events retain live condition/duration/ownership graphs. Frozen outer envelopes and blanket deep copies do not resolve those boundaries.

Standalone observation-only combat text bypasses EventQueue history and uses the existing Encounter log range. Preserve that separate factual/log accounting; do not build a second mechanical Event from text.

### B4. Presentation gap before cast binding; exact NeuroClient reference

The studied `game.app` reduced only when `current is None`, then drew that same mutable target. Engine production could advance, but reduction waited for display. The subsequent `game.play` integration addresses that gap for the selected casts; the old map-only demo remains a regression tool. The detached sampler's fixed appearance and single-cast fixture did not supply actor initialization or general vital state; the retained actor/cast connection added since this study is recorded in section 8.

NeuroClient `eventIngestion.ts` accepts intake without awaiting visuals, previews one historical candidate, plays/checks/commits it, and uses a ClipQueue with no second causal backlog. `stateSync.ts` preserves existing actors' pre-head state while staging needed new actors. Recover those invariants.

The matching preview/commit journal API is historical D&D `74cc1f9e3d2d5524e3758ae3b7e73f7b8fd7b89e:sdk/typescript/src/subjectiveJournal.ts`. The SDK currently linked into NeuroClient has a different numeric commit API and no previewPresentationFrame. The source study pins the actual ranges/hashes; no current combined-runtime compatibility is claimed. Old frame-derived transaction identities must not replace current Event lineage IDs.

## Appendix C: review and correction record

The September 8 rewrite was reviewed for ownership and source reuse, but its reviewers missed the unsupported cast-EFFECT interception premise. Those approvals do not certify the withdrawn spell-defect claim or the larger set of prerequisites that grew around it.

The September 9 requirement audit checked the active plan against current mechanics, actual production subscribers, Python presentation ownership and the original NeuroClient source. It preserved complete lineages, established subjectivity, historical reduction, authored-data reuse, rigs and height. It removed or narrowed the items recorded in the study's planning audit. No new gameplay skill, disclosure policy, timeline system or backend repair campaign was introduced.

Source-import anchors and retained evidence links remain available. Historical test counts describe their recorded candidates; the withdrawn Fire Bolt tests are not current acceptance evidence. After removing that candidate, four existing spell/protection tests passed in 1.70s, including normal evocation, Shield, protective abjurations and Counterspell against cantrips.

After the retained cast integration, a bounded anti-slop/anti-OOP review updated
stale progress and the selected capture decision, and trimmed repeated discussion
of abandoned prerequisites. Three new integration tests passed; the broader
presentation/app and architecture run had 45 passes and the two previously
recorded server import-boundary failures. The [verification checkpoint](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CURRENT_CODEBASE_STUDY.md#verification-and-plan-checkpoint)
records the scope. At that checkpoint, actual Pygame scheduling and map composition
were the next implementation, with the independent retained reducer/sampler verified.

The subsequent map/frame-pump implementation and miss extension are recorded in
the [integrated playback study](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CURRENT_CODEBASE_STUDY.md#integrated-map-playback-and-ordinary-miss--2026-09-09).
The final selected app/map/projection/import run passed 171 tests in 81.15s,
including the existing startup timing test. Earlier timing overruns also occurred
with HEAD's map owners; the comparison is retained without changing the threshold.
