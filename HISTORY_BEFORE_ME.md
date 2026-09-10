# History before the current recovery effort

Studied and written: 2026-09-08. This is the historical companion to [RECOVERY_PLAN.md](RECOVERY_PLAN.md).

This document explains the original engine/client intention, the successive server/content/reduction experiments, the July reconstruction, the 2.5D work, and the overnight experiment preceding `codex/recovery-design`. It records what existed, what went wrong, what survived, and what remains unproven. Implementation direction and work stages belong in the plan, not here.

## 1. Scope and evidence

The study used Git history and source at pinned commits, current July-derived source, the NeuroClient checkout, and existing implementation/audit records. Historical source was inspected with `git show`; neither failed branch was checked out to perform the study. No gameplay tests, old servers, Godot exports or historical application stacks were run in this documentation pass.

Three kinds of evidence are distinguished throughout:

- **Source observation:** a field, dependency, branch, operation or lifecycle is present in the inspected code.
- **Recorded result:** a historical ledger reports a test, benchmark, screenshot inspection or acceptance. It applies to that recorded candidate and has not been freshly reproduced here.
- **Interpretation:** an explanation of the architectural consequence. Source coupling can be established without claiming that every possible race, information leak or gameplay regression was reproduced.

Commit messages and filenames are navigation aids, not proof of correctness. In particular, `broken` contains the end of several successive experiments; it is not one unchanged multi-threaded server implementation.

### Reference map

| Reference | Date | Historical role |
| --- | --- | --- |
| `b2b3930` | July 25 | Existing engine/server/AI separation during the multi-game period. |
| `4ebe523` | July 30 | July ECS/event owner layout; common ancestor of the later failed line and reconstruction. |
| `e745f38` | August 1 | Authored-content checkpoint, including condition lifecycle changes examined below. |
| `74cc1f9` / `52acf56` | August 10 / 11 | Later server/client/content design; `52acf56` exposes the hosting and preview machinery used in this study. |
| `036df81` through `547fa96` | August 14-15 | Hard-cut/deprecation period following server and content audits. |
| `513dd97` | August 27 | Recorded accepted Phase 6 geometry/content behavior, before the final reduction failure. |
| `1f2e525` (`broken`) | August 29 | Failed reduction/Event-orchestration tip. |
| `205fd67` | August 30 | Reconstruction checkpoint whose parent is `4ebe523`, not `broken`. |
| `ab56a24` / `1e65f61` | September 1 / 2 | Direct-item and direct-character recovery checkpoints. |
| `24f293d` / `16a6bfe` | September 3 / 7 | World/torch and Pygame/height baseline on `codex/july-reconstruction`. |
| `1afad37`, `674fab2`, `a297f16`, `18bae0b` | September 8 | Overnight playable recovery, expanded encounters/Studio effects, next-step notes and frost-ray study on `astra_gogogo`. |
| `codex/recovery-design`, created at `16a6bfe` | September 8 | New branch for the present design effort; no overnight gameplay implementation was inherited. |

The important ancestry is:

```text
July 4ebe523
  +-- August server/content/spatial changes --> 513dd97 --> broken 1f2e525
  +-- reconstruction 205fd67 --> ab56a24 --> 1e65f61 --> 24f293d --> 16a6bfe
                                                                  +-- astra_gogogo 18bae0b
                                                                  +-- codex/recovery-design
```

NeuroClient is a separate repository. The inspected checkout is `/home/tommaso/Dev/NeuroClient` at `d274f2d`. Its installed SDK points into the D&D checkout, whose current API does not match that frontend's expected journal API. Matching historical SDK source exists at `74cc1f9`; this is source correspondence, not evidence of a currently runnable combined stack.

## 2. The original engine was solving real D&D composition

The engine was not an empty framework awaiting hand-coded gameplay. By July it already composed Entity blocks for health, abilities, saves, skills, equipment, action economy, senses and spellcasting. Actions, reactions, conditions and spatial effects provided authored rules through their existing owners.

`ModifiableValue` separated self, outgoing and imported target contributions, including static and contextual values. This supported source-specific modifiers, situational effects and relationships between participants without flattening everything into final numeric stats. Removing a condition needed to remove its own contributions, not reconstruct the entire creature.

The ownership pattern was concrete:

| Owner | Historical responsibility |
| --- | --- |
| Entity | Aggregate/composer; entity-specific immunity, saving-throw and application prerequisites. |
| BaseBlock | Condition indexes and traversal/removal of the condition ownership graph, including linked conditions. |
| BaseCondition | Authored application/removal hooks and the exact modifiers, handlers and children it produced. |
| BaseAction | Declaration, validation, costs and the handler-visible authored action lifecycle. |
| GridMap and spatial systems | Placement, occupancy, traversal, spatial consequences and sensory inputs. |
| EventQueue | Typed phase dispatch, storage, lineage and dependency-inverted observation seams. |

These component methods were part of the ECS adaptation. The later problem was not the existence of methods or subclasses for authored rules. It was moving orchestration into records or generic frameworks that did not own those rules.

July also legitimately used synchronous Event payloads containing live components. A `ConditionApplicationEvent` could carry the condition being applied while a handler participated in mechanics. That did not make the same object suitable for delayed rendering, serialization or generic archival. The synchronous bus and a detached presentation boundary had different requirements.

**Source evidence:** `4ebe523:dnd/core/values.py:1344`; `dnd/core/base_conditions.py:573`; `dnd/entity.py:887`; `dnd/core/base_block.py:819`. The later recovery study at `broken:DND_JULY_EVENT_ARCHITECTURE_RECOVERY_STUDY_2026-08-29.md` explicitly retracted blanket proposals to ban live synchronous payloads or replace legitimate component methods with free functions.

## 3. Product expansion accumulated several systems inside content

The original product intention extended beyond drawing combat: authored characters, progression, equipment, encounters, AI decision sources, reconstructible game content and multiple hosted games all had real use cases. The architectural expansion came from making one generic content mechanism responsible for too many of them.

The content system combined semantic identity and construction with external Python packs, import validation, content hashes, runtime behavior attribution, durable character revisions, scenario composition and renderer catalogs. A `ContentRef` carried pack/kind/ID/version/hash; recipes added parameters and their own digest. Runtime gateways and parallel binding maps made content registration part of ordinary rule execution.

Stable identity and reproducible construction were useful intentions. Character progression and encounter composition were also real domains. They became difficult to change when constructor identity, executable behavior, persistence compatibility and visual presentation all participated in the same registry/bootstrap boundary.

The August 14 content audit reported 80 production files and 31,148 Python lines in its measured content surface, 712 declarations, and no installed external packs in the configured default root. It also reported an approximately 16.2-second bootstrap and 246 MB maximum resident memory. These are **historical measurements**, not current counts or fresh benchmarks. Their significance is the amount of infrastructure serving built-in content, rather than a numerical deletion target.

The later reconstruction audit found a different inventory at its July-based checkpoint. The two inventories are not contradictory: they measured different trees. The accepted recovery objective was to preserve authored capabilities and values while recovering direct owners, not to copy whichever branch had the largest catalog.

**Evidence:** `broken:CONTENT_SYSTEM_ARCHITECTURE_AUDIT_2026-08-14.md`; [reconstruction content audit](DND_JULY_RECONSTRUCTION_CONTENT_RECOVERY_AUDIT_AND_MIGRATION_PLAN_2026-08-30.md), sections 1-3. The renderer/hash coupling below was additionally checked in source.

## 4. Hosting complexity and backend presentation coupling were distinct

### Hosting and runtime isolation

The multi-game system at `52acf56` launched a Uvicorn subprocess with a private Unix socket and process group for each game. This matched process-global state in Entity/BaseBlock registries, EventQueue and the global map. The inspected code does not establish that separate games concurrently mutated one mechanics universe through shared threads.

Inside a worker, combat advanced synchronously to an action boundary, then cooperatively yielded to asyncio. Threads appeared around preview-worker operations. Hosting additionally managed assignment, warm workers, capabilities, directory/persistence state, terminal ownership and shutdown. Nested teardown code demonstrates many coordinated lifetimes; it does not by itself prove a particular race.

By the final `broken` tree, much of this server code was deprecated. Therefore, the statement that removing the multi-game server would alone fix the final failure is not supported by the chronology.

**Source evidence:** `52acf56:server/hosted_worker.py:392`; `server/event_server.py:1061`, `:1149`, `:2120`, `:2132`; `dnd/core/base_block.py:162`; `dnd/core/events.py:1189`. Removal context: `broken:SERVER_SINGLE_GAME_HARDCUT_AUDIT_2026-08-14.md` and `deprecated/server_deprecated/`.

### Visual changes affected mechanical compatibility and availability

Backend content descriptors contained sprite/layer identities, tint, VFX/audio and UI metadata. The installed content-set digest hashed those descriptors. Consequently, changing a visual descriptor could change a backend compatibility identity even when no D&D rule changed.

Composition also waited for a visual-preview subprocess; preview failure was converted into request failure. The preview worker materialized another engine and built visual loadouts. A renderer-oriented operation therefore became part of whether game creation succeeded.

The source establishes a dependency chain: visual descriptors influence content identity, and visual preview influences composition success. It does not establish that every historical art edit actually caused a deployment failure.

**Source evidence:** `52acf56:dnd/core/content/descriptors.py:29`, `:108`; `dnd/content_system/pack_loader.py:1731`; `server/event_server.py:6522`; `server/game_creation_preview_worker.py:39`, `:64`.

### Information rules and choreography shared a server contract

The server mapper correctly contained knowledge rules: identity and exact location were separate grants, and movement could require an observer to know both endpoints. Those are D&D information semantics.

The same mapper also chose contact/effect frames, playback speeds and hidden equipment layers. Projected actors required visual loadouts; subjective presentation used separately identified cues with cursors and parent/child graphs. Objective replay consumed concrete Events, while subjective replay consumed another frame/cue vocabulary.

Separate public and privileged views were justified by the game. Backend-selected animation timing was a different responsibility. Their combination increased the number of contracts touched by a new mechanic or presentation requirement.

**Source evidence:** `broken:deprecated/server_deprecated/player_replication/mapper.py:3719`, `:3905`; `deprecated/server_deprecated/player_replication_contract.py:432`, `:1689`; `deprecated/server_deprecated/objective_replay.py:52`; `deprecated/server_deprecated/player_replay.py:65`. The broader [August 15 leak audit at the historical ref](#13-source-navigation) records twelve surfaces, including terrain filenames, appearance blocks, visual catalogs, map persistence and preview construction.

## 5. NeuroClient had the temporal behavior the recovery was trying to retain

The useful player-facing model was a world that remained legible while the engine advanced. A projectile did not accelerate because more messages arrived; a target reacted to its own impact; modular body and gear layers agreed about facing and frame; the user selected a new action from an appropriately presented state.

The later inspected NeuroClient source separated intake from presentation:

1. Intake reduced the authoritative replica and retained accepted frames.
2. An independent drain selected one exact presentation candidate from the previously presented state.
3. Authored visual work executed on elapsed presentation time.
4. Required visual completion and scene convergence preceded committing that candidate's presentation token.

The latest ClipQueue was not another backlog owner beside the SDK journal. It executed one active causal presentation unit; groups ran sequentially and siblings could run concurrently. This was asynchronous separation on the JavaScript event loop, not evidence that rendering and Event handling required independent OS threads.

The history was not uniform. July 31 (`20832db`) and August 1 (`a3ccc80`) ingestion awaited presentation inline; the stream awaited that callback, which awaited visual lineage completion. The inline wait remained at August 5 (`4ae11ef`). By August 10 (`f403f8b`), accepted frames woke the independent drain and returned, as in the later `d274f2d` source.

The earlier frontend already had a separate Pixi ticker. The source chain therefore establishes that incoming envelope consumption could be paced by animation completion; it does not establish that server mechanics or the render ticker stopped. Older queue-idle/replay reports cannot describe every later checkpoint. The later transport/journal classes were also not automatically necessary for in-process Python.

**Source evidence in NeuroClient `d274f2d`:** `app/src/engine/eventIngestion.ts:309`, `:541`, `:804`; `app/src/render/clipQueue.ts:491`; `app/src/render/presentationRuntimeHost.ts:152`; `app/src/main.ts:191`; `app/src/render/sceneRenderer.ts:440`. Matching journal source: D&D `74cc1f9:sdk/typescript/src/subjectiveJournal.ts:229`, `:285`, `:440`. Historical inline-await chain: NeuroClient `a3ccc80:app/src/engine/eventIngestion.ts:136`, `:236`; `a3ccc80:app/src/engine/eventStream.ts:324`; D&D `74cc1f9:sdk/typescript/src/subjectiveClient.ts:555`. Later wake behavior: NeuroClient `f403f8b:app/src/engine/eventIngestion.ts:241`, `:803`.

### Casts were composed concurrent activities

The caster's authored frame triggered release while its body animation continued. Delivery arrival dispatched the corresponding disclosed target effects. The cast joined body and delivery completion before optional recovery. Volleys launched members at individual stagger times, retaining each member's application and target effects.

Damage feedback used authored boundaries and disclosed resulting HP. This is why one timer per text-log entry could reproduce neither the original overlap nor the ownership of repeated hits.

**Source evidence:** NeuroClient `d274f2d:app/src/render/clips/CastClip.ts:67`, `:103`, `:353`, `:401`; `app/src/render/clips/TakeDamageClip.ts:47`, `:126`; `app/src/render/dispatcher.ts:86`.

### The timeline editor already expressed the authored design

Studio's written product contract distinguished causal time from render-layer composition. Cast, projectile/contact and target reaction were causal containers with nested body, equipment, glow, effect and feedback layers. The body was one pose clock for its attached layers. The editor's intended time matched preview time, including pause, speed and scrub.

This design also existed in the implementation: timeline controls changed recipe fields, serialization published those choices, and preview construction reused production mapping and playback. Scrubbing rebuilt the scene and advanced that same controlled runtime. The timeline was therefore an authoring/observation surface for gameplay presentation, not merely a decorative diagram or a collection of sprite metadata. Its large classes and separately estimated timeline windows did not erase that design.

The inspected checkout already contained saved Fire Bolt and Acid Splash JSON overrides, a generated spell profile, action recipes, condition recipes, context timing, media and palette data. TypeScript materialized complete generated spell recipes and merged exact saved overrides. Actor-dependent equipment resolution remained dynamic. These were reusable authored inputs and data-generation behavior; no runtime export was executed during this study.

**Source evidence:** NeuroClient d274f2d, agent_docs/studio_goal.md and agent_docs/SPELL_STUDIO_INTERACTION_PIPELINE_PLAN.md; app/src/ui/SpellStudioPreview.ts:1193, :1213, :1258, :2246, :2827; app/src/ui/spellStudio/serialize.ts:12; app/src/render/spellAuthoring/validation.ts:89; app/src/render/spellAuthoring/generatedBaseline.ts:31; app/public/studio/spell-studio-drafts.json.

### Studio data, runtime composition and editor views had distinct responsibilities

`PersistedStudioSpellDraft` stored authored cast/equipment/layer/delivery/feedback/recovery choices. `CastPresentationPhaseGraph` described visual resources and effect anchors while leaving targets and causal ownership to authoritative input. `StudioTimelineModel` additionally described editor labels, controls, selection, thumbnails and calculated display windows.

Modular identities and exact asset conventions mattered independently of the editor. The appearance resolver combined body/head/hair identity with the actual equipment loadout and active weapon set, checking that the loadout belonged to the actor. Armor, boots and weapon sets contributed distinct layers. Modifiable gear was part of the character experience, not an optional embellishment; this does not establish that every historical item binding worked.

Body and equipment shared the selected frame/facing and layer order. For example, temporary `equipment.kind="hidden"` hid the main weapon; it did not mechanically unequip it or hide every apparel/offhand layer. Some layer color behavior was category-specific, so retaining a color-mode string alone did not prove equivalent rendering.

The original runtime still executed through mutable rigs, state transitions and promises; it was not already a renderer-independent pure sampler. Studio supplied controlled time to that runtime. The overnight Python sampler was a new, limited adaptation of selected contracts, rather than a direct copy of an already pure core.

Source fidelity also had limits: Studio's nominal body duration used 15 frames, while the actor FSM ended when reaching frame 14; prepare timing differed under playback speed. The source therefore established intended relationships and actual discrepancies, rather than one perfectly uniform timing formula ready to copy.

**Source evidence:** NeuroClient `d274f2d:app/src/render/spellAuthoring/types.ts:147`; `app/src/render/types.ts:59`, `:492`; `app/src/render/resolveEntityAppearance.ts:36`; `app/src/render/equipmentVisuals.ts:18`; `app/src/ui/studio/StudioTimelineModel.ts:67`; `app/src/ui/studio/StudioTransportController.ts:22`; `app/src/render/controllers/ActionVfxController.ts:73`; `app/src/render/vfxFilters.ts:50`; `app/src/ui/spellStudio/timelineBuild.ts:1310`; `app/src/render/AnimationFSM.ts:236`.

## 6. Accepted August recovery preceded the final reduction failure

The August line was not uniformly discarded work. The accepted `513dd97` checkpoint supplied evidence for direct characters/items/monsters/scenarios and later Tile/world-item, spatial and geometry capabilities. Reconstruction records use it as a behavior/value reference while rejecting whole-file restoration of its changed owners, reflective access and remaining generic runtime debt.

The hard reduction problem was real: an observer may identify someone without locating them, retain remembered information after sight loss, see a child effect without knowing its cause, or receive a later disclosure while rendering older facts. Phase versions, causal children, reaction interruptions and state-only changes had to remain distinguishable.

The final experiment tried to solve these problems through generic knowledge paths, archives, deliveries, batches, provenance and consumer accounting. Some proposed documents used `CanonicalEventView`; the inspected final implementation instead retained concrete Event classes behind knowledge/delivery wrappers. Describing every proposal as implemented would misstate the history.

### Generic archival crossed the live-object boundary

`EventArchive.capture_queue_range` deep-copied every captured Event. A condition-removal Event could still contain a live `BaseCondition`. Later knowledge masking denied access to that field, but the archive had already copied the component payload. A retained reference could also reflect mutations by capture time rather than the original Event phase.

That is structurally different from an owner publishing an immutable after-value at the correct phase. It made asynchronous reduction depend on payload graphs designed for synchronous mechanics.

Unsupported entries were recorded as errors while the reducer still advanced its source cursor. This proves that source progress alone was not successful presentation or recovery; it does not prove every consumer mishandled those errors.

**Source evidence:** `broken:dnd/core/events/knowledge.py:144`, `:250`, `:393`; `dnd/core/base_conditions.py:312`; `dnd/event_reduction.py:1882`, `:1995`.

### Closing Event trees reversed domain ownership

Completion invoked `resolve_sub_events`. A spatial Event imported and executed GridMap and sensory work. A life-state Event searched global condition state and initiated removals. Tests explicitly permitted those late imports and omitted them from one dependency check.

The historical recovery study reported nine local imports and a seven-module cycle for that candidate. Those counts were not rerun here; the reverse calls and test exceptions were inspected directly.

A related historical lifecycle problem explains why a presentation reducer could not simply compensate: at `e745f38`, condition cleanup published a parent's completion before BaseBlock subsequently removed its children. If a consumer assumed the terminal meant mandatory descendants had finished, that assumption disagreed with the producer's actual lifecycle. Moving all cleanup into Event records did not restore the original ownership contract.

**Source evidence:** `broken:dnd/core/events/events_registry.py:540`; `dnd/core/events/world_events.py:621`; `dnd/core/events/encounter_events.py:166`; `tests/architecture/test_dependency_boundaries.py:350`, `:995`. Earlier lifecycle: `e745f38:dnd/core/base_conditions.py:952`; `dnd/core/base_block.py:1225`.

## 7. July reconstruction recovered owners and later capabilities selectively

The ancestry matters: `205fd67` directly follows `4ebe523`. The reconstruction was a new line from July, with later capabilities recovered through July's owners. It was not a continuation that assumed the failed reduction machinery was sound.

| Reconstruction step | Concrete change |
| --- | --- |
| `205fd67` | Recovered later spatial/world/lifecycle capabilities in the July owner layout, including completed Entity birth, provisional cleanup and an in-process Game deployment owner. |
| `ab56a24` | Added direct item builders and removed item runtime-binding/materializer modules. Behavior runtime dependencies still remained; this was not deletion of the entire generic content system. |
| `1e65f61` | Replaced generic character materialization/grant paths with direct definitions, builds, progression and class-specific grants. Custom choices and progression were retained rather than reduced to fixed premades. |
| `24f293d` | Added world-authoring support and expanded structural Event/Tile/GridMap facts before the visual application. |
| `16a6bfe` | Committed Pygame, selected client assets, passive capture, projection, picking and structural drawing. General actor/action animation remained absent. |

The recovered foundation included provisional Entity construction, one committed aggregate birth, explicit Game deployment, cold world initialization, structural after-values, sensory replay and same-model subjective combat logs. Failed provisional construction had a cleanup path. Cold authored state and ordinary dynamic activation were distinguished so initialization did not fabricate gameplay transitions or publish a partially composed creature.

`WorldModifiedEvent` grouped completed structural edits. Ordinary movement, door opening, damage and light changes retained their own concrete causes; structural publication was not a second cascade of mechanics.

The content recovery was staged. Primitive behavior attribution became `behavior_id`, `provided_by_id` and optional `origin_root_id`, while an internal owner UUID guarded rebinding. Direct items and characters were recovered through authored Python owners rather than a new persistence service. Character construction composed origins, progression, equipment and grants before publishing birth.

The item and character ledgers record accepted cuts, including Fighter/Champion, Barbarian/Berserker, Sorcerer/Draconic progression and maintained premades. They also record deferred islands and old consumers. The presence of some generic content modules and backend appearance/presentation fields at `16a6bfe` was remaining migration debt, not evidence that the full hard cut was finished.

**Source evidence at `16a6bfe`:** `dnd/entity.py:820`, `:1123`, `:1233`; `dnd/content/characters/builds.py:270`; `dnd/content/characters/premades.py:395`; `dnd/core/content/runtime.py:34`; `dnd/subjective_combat_log.py:17`. Intermediate source: `205fd67:dnd/game.py:10`; `ab56a24:dnd/content/items/authored_item_builders.py:719`; `1e65f61:dnd/content/characters/builds.py:270`; `24f293d:dnd/world_authoring.py`. Recorded scope: [primitive behavior ledger](DND_CONTENT_RECOVERY_PRIMITIVE_BEHAVIOR_FACT_IMPLEMENTATION_LEDGER_2026-08-31.md), [item ledger](DND_CONTENT_RECOVERY_DIRECT_ITEM_CR1_CR3_IMPLEMENTATION_LEDGER_2026-08-31.md), [character ledger](DND_CONTENT_RECOVERY_CR4_CR5_CHARACTER_IMPLEMENTATION_LEDGER_2026-09-01.md).

## 8. Pygame established a temporal seam and a 2.5D foundation

The in-process client direction already appeared in the August 27 Pygame study and was restated in the September 2 roadmap. The goal was one real encounter, initially demonstrated through a small observable seam, with independent engine/presentation progress and observer reduction before rendering.

At `16a6bfe`, the actual application builds the visual battlefield and an observer, then performs ordinary open/close door actions. An async producer queues each completed interval and yields without awaiting visual playback. Pygame advances its own presentation time. Ambient flame/water animation continues independently of source cursor changes.

Capture admits four selected concrete families: world initialization, standing-torch item state, door spatial state and observer sensory changes. Reduction checks generation and contiguous intervals and uses detached values. Frame evidence establishes the selected display obligations.

This proves a useful boundary, but only for that bounded example. Reduction consumes the next interval when the current display work permits it; a fully general action backlog and concurrent actor choreography were not implemented. The roadmap explicitly named ordinary-action withholding as an unresolved prerequisite. Its three cursors distinguished mechanically committed, inspected/reduced and visibly settled source progress; they were not three animation speeds.

The map's objective full-world debug data was also explicit. Hiding or dimming geometry in that local view did not turn its envelope into a general observer-safe protocol.

**Source evidence:** `16a6bfe:game/app.py:1231`, `:1307`, `:1361`, `:1364`; `game/presentation.py:153`, `:197`, `:304`. Detailed intent: [architecture roadmap](DND_IN_PROCESS_PYGAME_SYSTEM_ARCHITECTURE_ROADMAP_2026-09-02.md), sections 4 and 6; [P0 study](PYGAME_P0_NEUROCLIENT_SYSTEM_STUDY_2026-09-02.md).

### Height work preserved distinct kinds of space

The adopted world has one support per XY. Support height is an engine fact in five-foot steps; the renderer projects a 128x64 diamond and applies 64 pixels of lift per step. The map is 2.5D presentation of that topology, not stacked mechanical floors or arbitrary 3D physics.

Tile support, object base/top, sprite pivot, composition role, camera pose and painter depth remained distinct. Cliffs and stairs used explicit source contacts and support identities. Decorative beds did not add walkable supports. Picking considered actual support planes; lifted screen Y did not replace semantic world depth.

The selected stair flight had three progressive supports and retained their separate knowledge/light state. Static drawing, movement legality and source art were related through those facts rather than by interpreting sprite filenames or editor sorting layers as height.

Records contain real visual/contact and movement checks, including climbing and rejecting an ordinary cliff crossing. They also preserve limits: finite stair families, one support per XY, diagnostic grid/picking limitations, and no certification of arbitrary topology or universal effect occlusion. The last recorded full-map interaction run missed its median target at the widest view. That is a historical performance result, not a newly reproduced failure or a reason to discard the established spatial design.

**Source evidence:** `16a6bfe:game/projection.py:10`, `:124`, `:214`, `:268`; `dnd/core/events.py:4381`. Recorded proof and limitations: [height study](DND_PYGAME_HEIGHT_STAIRS_STUDY_AND_NEXT_STEP_PLAN_2026-09-03.md), [cliff/stair record](DND_PYGAME_CLIFF_STAIR_IMPLEMENTATION_PLAN_2026-09-03.md), including September 4 follow-ups.

## 9. The overnight experiment expanded the product before closing the contract

The overnight branch started from the clean `16a6bfe` checkpoint. Its breadth was authorized as an experiment: playable combat, maps, assets, gear, source study and VFX work were requested. The issue was how prototype decisions became architecture, not that investigating those features was unauthorized.

The four commits added direct monster/scenario construction, a playable Pygame shell, actor rigs, equipment interaction, portraits/icons, selected Studio effects, authored encounter/map content and a separate Godot frost-ray study. The implementation record reports 57 monster roots and 39 authored encounters with direct construction; those catalog counts are not equivalent to 39 fully illustrated playable maps or complete behavior coverage.

### Playback converted logs into a second scheduling interpretation

`Playback` held one selected `CombatLogEntry`, one index and one reset elapsed timer. Actor clip selection followed log kind; nonmovement entries defaulted to 1.25 seconds. Completed action/damage logs were enriched with lineage/spell/application fields, sorted and flattened. Magic Missile received additional allocation handling.

Consequently, successful cast and damage entries became separate visual steps where the original system needed overlapping body, delivery and target activity. A proposed adjacent Fire Bolt log span would have patched that representation without establishing the general causal contract. The proposal was stopped before code changes after the user redirected the work to source study.

**Source evidence:** `astra_gogogo:game/play.py:43`, `:132`, `:163`, `:475`; `game/presentation.py:394`; `game/effects.py:38`.

### Source-shaped data did not equal executable compatibility

The experiment preserved selected Studio JSON names, source snapshots and pure projectile calculations. It did not execute the complete body/equipment/layer/recovery relationship. Recovery was restricted to disabled values in the accepted schema. Spell selection also occurred inside the raster adapter.

That distinction explains why a useful isolated projectile sampler did not establish the desired whole animation system. Asset fidelity, schema fidelity, executable feature support and temporal composition were separate claims.

**Source evidence:** `astra_gogogo:game/animation_types.py:198`, `:398`; `game/animation.py:197`; `game/effects.py:38`; `agent_docs/ASTRA_EFFECT_TIMELINES.md:81`.

### The small encounter leaked into application structure

The application fixed Fighter and Sorcerer identities, built a four-actor roster with a crypt-specific enemy branch, and replaced rolled initiative with authored order. These were documented fixture choices, but their location meant a different party or encounter could require application edits despite an existing scenario-composition domain.

Actor after-values were admitted based on roster membership, including facts whose display was later suppressed. For example, hiding enemy HP in drawing did not establish that the detached actor payload itself was authorized for the observer. This is an architectural boundary gap, not a claim that a remote attacker received these local values.

**Source evidence:** `astra_gogogo:game/combat.py:36`, `:71`, `:103`; `game/presentation.py:229`; `game/play.py:534`.

### Height-aware drawing introduced choices that still needed design

Effects normalized July's projection into NeuroClient's 64x32 reference units. Duration was calculated from a fixed quadrant's projected endpoint distance, then current-camera geometry was used for drawing. This prevented camera rotation changing duration, but selected a particular distance meaning without resolving it as a shared contract.

Before art offsets and minimum duration, a grid displacement `(1,1)` projects to 32 reference pixels in one quadrant and 64 after a quarter turn. One support-height step can cancel the first projected separation even though the contacts differ. The fixed-quadrant metric is camera-stable, but it is neither grid distance nor three-dimensional distance.

Other open relationships included when a moving target's contact was sampled, the difference between rig root and ground contact, and curved effect artwork whose painter contact followed a straight XY/height interpolation. The static terrain work did not automatically settle those animation questions.

**Source evidence:** `astra_gogogo:game/effects.py:54`, `:87`, `:157`; `16a6bfe:game/projection.py:124`, `:214`; NeuroClient `d274f2d:app/src/iso.ts:3`, `app/src/render/visualAnchors.ts:8`.

### VFX authoring was separate experimental output

The frost-ray work used Godot source geometry and exported comparisons for beams/projectiles. Its captures, manifests and review page were evidence for art direction and reproducible export, not a new gameplay Event schema. These exports were not bound into the current recovery branch's gameplay.

The intended art sources remain identifiable: NeuroClient supplies modular humanoids, portraits and spell icons; purchased packs provide fixed orc/goblin/demon/undead/animal sprites; NeuroVFX/CodexFX supplies Godot-authored spell media. Runtime gameplay and backend identity did not need to depend on the source authoring applications or Downloads folders.

## 10. What the size and validation records actually establish

The apparent 800k-line change was consistent with comparing the experiment against the old `main`, not just the overnight work. The measured `main` was `2160564`; the measured `astra_gogogo` was `18bae0b`. A direct Git comparison produced:

| Comparison | Files | Added text lines | Deleted text lines |
| --- | ---: | ---: | ---: |
| `2160564` (`main`) to `18bae0b` | 2,725 | 838,818 | 50,463 |
| `16a6bfe` to `astra_gogogo` | 458 | 24,928 | 3,020 |

The overnight comparison includes 299 binary files, for which Git does not report text-line counts. Its text additions include 7,363 lines in generated frost-ray validation JSON. The broader text breakdown was 6,253 additions/1,891 deletions in application source/config, 2,501/553 in tests, 3,735/575 in documentation/reference snapshots, 1,763/1 in data/manifests, and 10,676/0 in experimental artifacts. This categorization describes the diff, not code quality.

The overnight ledger records a final 311-case Pygame run, selected import/type checks, visual inspection and interaction benchmarks. It also records failures and repairs during development and frame-time tails far above the median. Those records demonstrate substantial implementation work and particular observed outcomes; they do not certify the missing concurrency/disclosure design or full Studio compatibility. None of those gameplay checks was rerun for this history.

Similarly, earlier passing geometry and content records remain evidence for their particular capabilities. A later branch called `broken` does not retroactively invalidate every accepted spatial rule, and a passing final state does not prove each intermediate visual state was correct.

**Evidence:** Git `diff --numstat` at the refs above; `astra_gogogo:agent_docs/ASTRA_IMPLEMENTATION_PLAN.md`, implementation/continuation records; [cliff/stair record](DND_PYGAME_CLIFF_STAIR_IMPLEMENTATION_PLAN_2026-09-03.md).

## 11. What the history explains

Across the attempts, several distinctions repeatedly collapsed:

| Distinction | Consequence when collapsed |
| --- | --- |
| Semantic game identity versus renderer identity | An art edit changed backend compatibility or creation behavior. |
| A live synchronous Event versus a detached fact | Generic capture acquired component graphs and capture-time aliasing concerns. |
| Passive data versus authorized knowledge | A copied value was treated as safe for an observer without establishing disclosure. |
| Source order versus causal ownership versus visual time | Logs or cursors substituted for overlapping release, delivery and reaction relationships. |
| Latest target state versus currently presented state | Rendering risked borrowing future facts while lagging behind engine execution. |
| Authored format versus executed support | Preserved fields or parsed JSON overstated what the runtime could actually perform. |
| Support contact versus art pivot versus projected depth | Static art placement choices were treated as sufficient for moving and airborne effects. |
| A working fixture versus a scalable content owner | Parties, creature choices or spell exceptions accumulated in application code. |
| Recorded validation versus general architectural acceptance | Passing selected checks made temporary choices appear settled. |

The history supports the user's diagnosis that the difficult work is ownership and compositional design. It does not establish that all networking, classes, authored hooks, content definitions or animation graphs are inherently wrong. Nor does it establish a finished replacement for ordinary-Event disclosure, exact Studio lifecycle endpoints or height-aware delivery geometry. Those remain forward design work in [RECOVERY_PLAN.md](RECOVERY_PLAN.md).

## 12. Asset/source provenance retained from the study

| Source | Historical role |
| --- | --- |
| `/home/tommaso/Dev/NeuroClient` | Studio types/runtime, modular bodies and gear, portraits, icons and animation/media conventions. |
| `/home/tommaso/Dev/NeuroMapEditor` | Explicit layer/Z-grid/placement/pivot/composition evidence. Studied as a separate spatial authoring source, not an engine or animation authority. |
| `/home/tommaso/Dev/MapEditor` | Earlier map authoring and fantasy asset evidence. |
| `C:\Users\tommaso\Downloads\2D Orcs and Goblins - TopDown - V1.0.zip` | User-provided fixed monster sprite source. |
| `C:\Users\tommaso\Downloads\2D Demons - TopDown assetpack v1.1.zip` | User-provided demon art source. |
| `C:\Users\tommaso\Documents\assets\smallscale` | User-provided undead, other fixed humanoids, animals and related art. |
| NeuroVFX/CodexFX and `astra_gogogo:experiments/frost_ray/` | Godot authoring/export source and the overnight beam study. |

## 13. Source navigation

Historical references use `REF:path:line`, where the line belongs to that ref. For example, `git show broken:dnd/core/events/world_events.py` reads historical source without changing the working branch. NeuroClient references belong to that separate repository. Source paths in a grouped evidence paragraph share the explicitly named repository/ref unless stated otherwise.

The principal historical records are:

- `broken:CONTENT_SYSTEM_ARCHITECTURE_AUDIT_2026-08-14.md`
- `broken:SERVER_SINGLE_GAME_HARDCUT_AUDIT_2026-08-14.md`
- `broken:BACKEND_FRONTEND_RESPONSIBILITY_LEAK_AUDIT_2026-08-15.md`
- `broken:DND_EVENT_REDUCTION_FIRST_PRINCIPLES_STUDY_2026-08-27.md`
- `broken:DND_JULY_EVENT_ARCHITECTURE_RECOVERY_STUDY_2026-08-29.md`
- [Reconstruction content audit](DND_JULY_RECONSTRUCTION_CONTENT_RECOVERY_AUDIT_AND_MIGRATION_PLAN_2026-08-30.md) and the implementation ledgers linked above.
- [Pygame architecture roadmap](DND_IN_PROCESS_PYGAME_SYSTEM_ARCHITECTURE_ROADMAP_2026-09-02.md), [P0 NeuroClient study](PYGAME_P0_NEUROCLIENT_SYSTEM_STUDY_2026-09-02.md), and the height records linked above.
- `astra_gogogo:agent_docs/ASTRA_IMPLEMENTATION_PLAN.md`, `agent_docs/ASTRA_EFFECT_TIMELINES.md` and `experiments/frost_ray/`.

These documents have different dates and levels of authority. Their proposed replacement designs, large inventories and historical test totals are not silently adopted by this history. The current plan is the separate forward-looking document.
