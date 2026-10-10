OUR OBJECTIVE IS A COMPLETE IMPLEMENTATION

# NDCLIENT IMPLEMENTATION PLAN — complete consolidated edition

Date: 8 October 2026; scope and source references corrected on 10 October 2026 after the user's rollback and directory renaming.
**Current status: the fresh repository, selected artwork and core tracked client
authoring are prepared. The 10 October review's missing door/timber connection
is now implemented in the existing typed authoring (§6.1). The asset/authoring
pre-phase and initial replacement/relocation adapter are complete.
Complete application-release integration, client scaffold/SDK integration,
renderer, Studio and UI are not implemented.** N0 is partial.

**Committed starting point:** NDClient `df5397e` (`first push - pre implementation`)
records the completed tracked preparation. It is a reference checkpoint, not an
instruction to reset the user's current worktree or restore rolled-back code.
Artwork remains installed and Git-ignored. This is
the client checkpoint, not a claim that the separate engine worktree is committed
or that a playable client exists. Do not recreate the repository, repeat asset
intake or reopen the completed authoring connection.

**Plan location:** the [engine master](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/NDCLIENT_IMPLEMENTATION_PLAN_COMPLETE_2026-10-08.md)
is the maintained document. The
[NDClient repository copy](/home/tommaso/Dev/NDClient/agent_docs/NDCLIENT_IMPLEMENTATION_PLAN_COMPLETE_2026-10-08.md)
contains the same specification for work in that repository. Update the master
and refresh that copy together; the copy is not a second plan. Evidence links use
the existing engine locations so both copies carry the same text.
Unless prefixed with `NDClient/`, source-code paths refer to the engine repository;
client `authoring/`, `.media/` and `tools/` paths are identified in their sections.

## Working rules — read before choosing the next task

1. **No backend changes are allowed.** Engine, server, wire schema, SDK and obsolete
   Python applications are read-only inputs. Launching/configuring the delivered
   service and using its SDK are allowed; changing its implementation is not.
2. **Implement the agreed design; do not innovate around a mismatch.** If a planned
   approach cannot work, do not invent another architecture, add hidden assumptions,
   patch individual assets/spells, fabricate data or silently change requirements.
3. **A noncritical uncertainty does not stop the project.** Record the affected
   requirement, concrete evidence, what cannot yet work and the decision needed in
   the existing status section (§12). Leave that part honestly incomplete and move
   to the next specified, unblocked task. Do not turn the note into a new subsystem,
   research campaign, provisional fix or automatic backend task.
4. **Discuss genuine blockers with the user.** A blocker is a demonstrated missing
   input/contradiction that prevents the dependent work, not an optional edge case
   or a wish for more complete data. Explain it without taking a new approach;
   continue independent planned work while the decision is pending.
5. **Keep the whole delivery in view.** There is plenty of agreed work to do. Pick
   the next task whose inputs and method are known before entering uncertain work.
   Do not spend repeated turns perfecting one tiny detail while other required
   components remain untouched. Report progress and limitations honestly; never
   mark a skipped requirement complete or conceal it with a fallback.

**Reading and execution order:** use the current status and §1.2 for the prepared
inputs, then §10 for the next work item. Read its relevant contract in §§3–9 and
existing source examples before editing. §11 supplies focused acceptance cases;
§§13–14 keep complete coverage visible. Read history only for a specific needed
fact. Repeatedly rereading this whole plan is not progress.

**Scope for implementation:** NDClient source, its tracked authoring and client-side
SDK capture/configuration tools only. Consume `dnd/`, `server/` and `sdk/` as delivered;
this plan contains no engine, server, transport, projection or SDK implementation
work. A missing native capability is reported to the user, not silently added or
simulated in the client. Existing server launch/configuration and SDK consumption
remain part of client integration. The implemented movement preference is already
available (§4.8).

**Source paths after renaming:** `server/` is the active thin service formerly named
`player_server/`. `game_obsolete/`, `ai_obsolete/` and `server_obsolete/` are archived
reference implementations. Active enemy AI remains in `dnd/ai/`. Do not revive,
repair or migrate imports inside the archived packages to execute this plan.
`devtools/player_server_acceptance/` is an existing tool directory, not the service
package; its name has not changed.

**Resume at §1.2 / N0:** connect the prepared authoring to application loading,
source-derived TypeScript types and the current SDK, then build the one shared
play/Studio rendering path. N1–N5 remain the full delivery scope. The renderer
must consume the completed layer/contact/elevation/material data; another asset
preparation pass or standalone preview does not substitute for that work.

- `/home/tommaso/Dev/NDClient`, branch `codex/ndclient`, is the authorized fresh
  source repository. The previously deleted application is not a baseline.
- `.media/smallscale/modular/` holds the complete unified Fantasy V1.3 library;
  `.media/smallscale/authored/` holds all ten owned fixed-creature packs, including
  unimplemented creatures, using combined/with-shadow bodies. Existing mapping
  studies and canonical rig bindings remain authoritative; no new B bindings.
- Fantasy environment artwork, its companions and the 60-record metadata supplement
  are copied. Six generated indoor-door mounts and the fractional timber flight
  have their delivered corrections connected to typed bank/door/library owners
  (§6.1). No new artwork or physical measurement is requested.
- UI selection is smooth48 icons and 192×256 portraits only. Their existing UI
  source sections are now adopted under `authoring/ui/`; §5.7 records the exact
  mappings, choice values and remaining art gaps. Runtime UI is still pending.
- Ordinary VFX and the completed Factory replacement delivery are copied:
  28 spell families, 193 paired banks, 400 media IDs and all 38 previously pending
  XYZ references, including ground-fire/Web aliases. No retired XYZ is imported.
  Existing spell/condition lifecycles, flat media and live procedural resources
  are preserved. **Tracked `authoring/` now connects existing IDs to the selected
  files and bank semantics.** §5.1.1 records this implemented preparation and the
  remaining application integration.

[ASSETS.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/ASSETS.md) is the compact current location/selection guide;
[the VFX intake](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/NDCLIENT_VFX_ASSET_INTAKE_2026-10-09.md) records copy evidence.
The recovery and asset diaries are historical references, not extra instructions
or documents to reread routinely. Further implementation follows the next
user-authorized step; asset preparation has not silently resumed renderer work.

This is the single specification for the next NDClient implementation. It contains the required behavior, existing source owners, rendering algorithms, Studio and UI features, asset installation, network integration, delivery sequence and acceptance cases. Source files and historical documents linked as evidence do not contain additional mandatory plan chapters: the implementation requirements are here.

**Subsequent group D authorization and completion:** the user supplied
`/mnt/c/Users/tommaso/Documents/assets/dnd-engine-icons-and-portraits/README.md`
and requested production-size copies. The [intake record](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/NDCLIENT_UI_ASSET_INTAKE_2026-10-09.md)
locates 594 new icons (620 keys, 103 choices) and 661 new portraits: 43 exact
existing creature associations, 186 unassigned NPC/source entries and 432
selectable character portraits. Preserve the delivered replacement/choice and
portrait lookups. The user's final selection is **smooth48 icons and 192×256
portraits only**. Local smooth144/CIE28 and the five other portrait-size payloads
were removed; source originals remain untouched. Use the same 192×256 image for
smaller UI views, scaling or deliberately cropping on need. The classic 110×170
exports changed aspect ratio and cut away side content; they are not proportional
resizes of the selected 3:4 portrait. Final UI artwork is 65,509,677 bytes;
masters, old/rejected banks and duplicate earlier outfits remain at source.
Do not recreate every available export variant.

The original `agent_docs/NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md` was copied before editing this document and remains unchanged as historical evidence. This edition supersedes its execution instructions and the competing client repair/addendum instructions. It does not retroactively change historical evidence.

**Deleted-client boundary:** the earlier NDClient was deleted. Do not recover it
as the implementation baseline. The later user-authorized fresh repository above
now exists; reuse it and its prepared assets rather than recreating or resetting it.

**Navigate this plan:** [Scope and completion](#0-completion-contract-and-scope) · [Sources/repository](#1-source-recovery-repository-and-assets-exact-starting-work) · [Coverage/types](#2-full-source-coverage-and-type-ownership) · [Architecture](#3-ownership-execution-and-minimum-duplication) · [Server/SDK/playback](#4-delivered-server-sdk-playback-and-recording-integration) · [Authored presentation data](#5-complete-client-presentation-release) · [Renderer](#6-production-renderer-shared-data-geometry-material-and-composition) · [Assets](#7-asset-delivery-and-authored-rig-data) · [Studio](#8-studio-read-only-inspection-of-the-production-runtime) · [Player UI](#9-complete-player-ui-and-interaction) · [Implementation](#10-implementation-sequence-with-concrete-outputs) · [Verification](#11-verification-visual-scenarios-and-performance) · [Completion status](#12-delivery-status-and-acceptance-language) · [Renderer families](#13-complete-production-renderer-capability-coverage) · [Complaints/parity](#14-complaint-and-requirement-closure--migration-versus-existing-parity) · [Reviews](#15-review-responsibilities-and-recorded-disposition) · [Source evidence](#16-sourceapi-evidence-and-scope-boundary).

## 0. Completion contract and scope

The result is a playable browser client using the delivered server/SDK and a Studio interface over its production rendering machinery. Studio reads actual server-origin event streams recorded through the current SDK, without requiring a live game-server connection during replay. It is not a floor/body demo, a clip gallery, a six-field scene export, an Idle/Run asset installer or a diagnostic timeline passed off as the Studio.

| Required outcome | What must actually work |
|---|---|
| Play | The authored dungeon opens with the human Fighter/Sorcerer party. Exploration, split-room party perception, doors/windows, movement, traps, loot, equipment, ordinary attacks, class abilities, spells, reactions and the goblin encounter work through real native commands. |
| Rendering | Existing authored positions, contacts, assembly compatibility, view banks, phases and original sprite proportions survive. Floors, elevation, stairs/cliffs, walls, inserts, props, bodies and effects compose consistently in all four cameras. |
| Event playback | Server progress, durable consumption and displayed time are independent. Every implemented event family is presented; queued AI actions are neither skipped nor used to reveal future state. Play and Studio use the same reduction, compiler, sampler, renderer and resource owner. |
| Full content | Every selected authored binding and dependency is installed and has an explicit supported consumer. Scene demand controls residency, not which content gets migrated. |
| Studio | The existing Neuro Studio capabilities return: hierarchical source-aware layer tracks, preview thumbnails, meaningful time/rulers, actual event cases, read-only rig/action/spell/condition/world/material inspection. Canonical JSON is edited manually and reloaded through the same compiler; an editor/save UI is not required for this phase. |
| Interface | A coherent minimal HUD with four icon blocks, small portraits, proper targeting and variants, useful inventory/details/reactions, and a readable, copyable, exact-math combat log. |
| Responsiveness | Input and display do not wait for native turns, bulk JSON validation/reduction, file scans or texture decode. Actual stalls are attributed; client stalls are repaired and upstream delays reported; correctness and complete delivery are not traded for an invented quota. |
| Handoff | Repeatable server/client/Studio launch and source-edit workflow, an installed private asset release, source-only Git history, and an issue-indexed in-app review of the complete product. |

### 0.0 The production renderer is the central deliverable

The failure to correct is an incomplete, patched rendering implementation with no consistently enforced data contract. Missing Studio previews were one visible symptom. Recovering a timeline widget, or displaying a few scenes successfully, does not fix that failure.

There is one transformation:

```text
Game: current SDK initialization + operation stream ─┐
                                                   ├─ same admitted-record consumer
Studio: recorded server initialization + operations ───┘
    → current subjective reduction and causal occurrence indexing
    + canonical authored recipes / rigs / registrations / materials
    → compiled timed presentation tracks and retained state commits
    → absolute-time sample of world, bodies, equipment, effects and UI state
    → registered support/surface geometry + resource readiness
    → common depth/material/light composition → animated Pixi scene
```

Studio exposes this transformation explicitly. Its tracks, effects and timings are the production presentation program itself viewed through an interface. It does not manufacture a preview program, call the game server to discover test outcomes, or substitute simplified scene data. Scrubbing changes the same presentation time that drives the renderer. The game host supplies live records; the Studio host supplies prerecorded records. That input-source difference is not a second executor or renderer special case.

The shared runtime must consume every supported field and fact family before delivery is called complete. It has consistent principles: native ownership of outcomes; source ownership of visual semantics; authored registration of original art; support identity separate from physical elevation and composition role; one comparable depth space; one absolute clock; one displayed-state/resource commit; shared geometry for rendering and picking; and GPU evaluation of finite materials/particles. No spell/window/fixture-specific correction can override those principles to make one preview look plausible.

Production draws are passive compiled views, not a second serialized world/event schema. They retain native/cause/occurrence identity, source binding/layer/frame, displayed transform, support/receiver, geometry/material/blend and dependencies. Existing native facts and client-authored fields are consumed through their common presentation owner; a missing native value is not an instruction to expand the API. Play, Studio and any capture call those functions directly; sharing type declarations while maintaining independent render loops does not satisfy this design.

### 0.1 Requirements that remain in force

- Use TypeScript, PixiJS **8.22.0 with WebGL2**, and Vite for the new WSL client. Preserve the pinned, studied API baseline. A version bump requires a concrete benefit, not another preliminary migration.
- Keep the current Python engine/server on Windows or WSL as configured. It owns rules, legality, rolls, movement, perception, propagation, lifecycle and AI. The client owns presentation and user interaction, not a second simulation.
- Use current `@neurodragon/player-sdk` from `sdk/player-typescript`; the older `@neurodragon/dnd-engine-sdk` is a different protocol. Do not revive the Omni server, old WebSocket/store/FSM architecture or old synthetic Studio result generator.
- Preserve all existing selected spells, action/class/item abilities, attacks, reactions, movement modes, creatures, modular equipment, non-modular rigs, conditions, animated/destructible environment, particles, deposits and current surface responses. New surface chemistry, new gameplay, a campaign/lobby/account system, a new AI, and narrative rendering are outside this phase.
- Human readable text and exact recorded combat math; no UUID/debug labels in normal UI, no permanent instruction clutter. The combat log is the sole prose event view.
- Current authored media rates remain intact. The selected Factory Fireball retains the explicit 24 FPS exception; other VFX may remain 32 FPS and body clips retain their own rates. Do not silently normalize all media.
- No arbitrary cosmetic class/creature scaling. Use source units, registered art conversion and explicit authorized size/condition authoring once. Existing accepted animal enlargement and actual halfling/enlarge/reduce data are distinct from invented class-size corrections.
- A new complaint is checked against its shared owner and relevant family, not patched only for the named spell or screenshot. Record its required result in this file's coverage tables.
- Review the running app with meaningful cases. Screenshots/video may be internal diagnostic evidence, but are not the requested product, required review workflow or substitute for opening the app.
- Keep this file as the plan of record. The user-requested NDClient repository copy mirrors this specification; it must not acquire competing requirements. Other repository documentation explains current layout, ownership and launch commands.

### 0.2 What this edition deliberately removes

There is no 8 MiB page-pair rule, universal decoded-memory ceiling, arbitrary loading-time quota, fixed lookahead duration, required decode concurrency, universal source-fringe pixel limit, fixed light-fit error threshold or mandatory benchmark run length. Report measured sizes and timings and optimize identified costs. Hardware texture limits and actual format constraints still apply.

No source feature is postponed behind a cosmetic “foundation complete” label. There is no second reduced scene format, fake ability button, preview-only event executor, full-grid clipping stencil, class-dependent body normalization, guessed compatibility or runtime XYZ-array reconstruction. No repeated schema generation on startup, ordinary asset installation, unrelated parameter edits or every test run.

Historical Pygame failures are **parity/regression requirements**, not evidence that the deleted NDClient caused those earlier failures. Migration failures are separately identified below. Consume existing corrected engine behavior. A demonstrated native defect is reported separately to the user; it does not authorize a backend repair in this client plan.

### 0.3 Evidence and remaining uncertainty

The accepted standalone Fireball demo at engine `.runtime/ndclient-fireball-proof/` is a useful, explicitly authorized result. It established smooth bounded Pixi rendering with the selected v4, real wall/floor assets, depth/normal data, receiving light and independent emission. The simple two-room native-reach example is a verified fixture reduction, not a general geometry or privacy algorithm. Do not rebuild this demo as the next deliverable or call its measurements production benchmarks.

The server and TS/Python SDK are implemented. This phase connects the browser to that existing contract without changing it. The deleted client is not an available implementation baseline. This plan is source/design work; plan approval cannot certify unbuilt geometry, live browser behavior, performance or art quality.

The following input and scope decisions are settled; they must not be rediscovered
as backend prerequisites during N0–N5:

| Client requirement | Existing input / implementation decision |
|---|---|
| Authoring types and release | Use NDClient `authoring/schemas/*.schema.json` and tracked section indexes. Generate TS declarations locally. No Python type relocation, engine exporter repair or re-import is needed. |
| Action selection and movement | `ActionSelection.prefer_safe` already defaults to true; preview and execution already forward it and both SDKs check the echo. Implement only the ordinary/Shift client controls and exact request reuse (§4.8). |
| Interaction, inventory and character panels | Use `AvailableActionsResult.world_interactions`, native preview routes/targets, existing equip/unequip/toggle intents, `PlayerCharacterSheet.compatible_item_slots`, resources and handler details. No new endpoints or client rules. |
| Area timing and damage | Use existing `SpellFact.resolved_area_positions`, `suppressions`, `area_geometry` and `AreaReachFact` stage/destruction links. These are received outcomes, not an exhaustive blocked-region map or pixel stencil. |
| Cancellation | Use current `PlayerNode.canceled`, `ActionCancellation` and any actually supplied suppression/interception facts. Stop the canceled track; do not promise an exact provider/shell hit when the record contains none. |
| Explosion coverage | Admitted cosmetic VFX can overlap dark/unseen space. Use registered depth for visible wall/surface composition; do not reconstruct undisclosed propagation or clip the plume by visibility cells. |
| Elevation | Keep existing support heights, authored stair contacts and installed compatible assemblies. Independently walkable stacked supports are outside the delivered API; the renderer still handles layered visual surfaces at different heights. |
| Studio cases | Configure existing `ServerConfig`/`EncounterRecipe` fields and drive current SDK commands from client capture tools. Record real responses. Do not expand native setup types or add engine test hooks to manufacture a case. |
| Performance | Attribute server/network wait separately, keep browser input/rendering responsive, and repair client costs here. Native latency is evidence to report, not another backend optimization task. |

Known source limits remain explicit: exact hidden 3D interiors cannot be recovered
from RGBA-only art; unavailable closed light-blocking faces are not guessed; only
supported authored rises/joins are used in required scenes. Use supplied companions
where present and the defined cutout behavior elsewhere. Library-only art does not
acquire new gameplay bindings. The two UI art gaps remain optional (§5.7); remaining
spell world-light curves are deferred as agreed, with Fireball first (§6). These
are stated limits, not demands for another source audit or a server extension.


## 1. Source recovery, repository and assets: exact starting work

### 1.1 Existing components to recover deliberately

The [9 October environment migration handoff](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/ndclient-environment-assets-20261009/README.md)
consolidates the exact current engine, source-workshop, prefab and corrected editor
inputs for this chapter, including actual registration/contact values and known
gaps. It also records the subsequent user-authorized environment copy and exact
local receipt. It creates no new bindings or implementation prerequisites;
unselected artwork and unresolved authoring remain explicitly identified.

The subsequent [9 October metadata delivery](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/ndclient-environment-assets-20261009/README.md#missing-metadata-received--9-october)
supplies all 60 named records: 3 disputed Misc, 30 additional Misc, 9 interiors,
6 indoor-door assemblies and 12 decals. Exact JSON, schema notes and measurement
evidence are retained in tracked `authoring/environment/source-records/`;
normalized runtime data lives at the existing environment owners, while raw
intake receipts remain ignored. Use those owners rather than another registry or
requesting these profiles again. Preserve the source/measurement/estimate
distinctions and source pivot versus physical contact. That earlier delivery left all six door records
with an unvalidated shared physical mount: measured S/N pose
conventions disagree with the recovered montage anchors. The generated timber
flight's measured fractional rise is distinct from selected two-step stairs.
The 10 October closure, retained in client source records, supplies their explicit
physical mount corrections and timber support sequence. The review in §6.1 found
the missing typed connection, which is now implemented. Consume those values;
never renderer offsets, row swaps or geometry stretching.
The supplement changes no current content selection or runtime code and supplies
no new depth/normal exports.

The spell/VFX inventory and authorized copies are now complete. The selected
Factory delivery in §7.1 replaces the previously deferred banks, while ordinary
spell/condition/action media remain in their own folders. The next integration
work is application integration of the tracked client authoring in §5.1.1, not
another source census, import or copy campaign. Retain the Fireball proof as
math/reference evidence. `authoring/media/{storage,banks}/` owns the current
client selections and paths; raw Factory manifests are intake provenance only.

| Existing source | Recover or adapt | Reject / replace |
|---|---|---|
| `/home/tommaso/Dev/NeuroClient/app/src` | Camera/input math, reusable grid/control helpers, icon-HUD/equipment/portrait layout, text/log widgets, timeline ruler/clip previews, read-only inspector grouping and source provenance | Old SDK/store/mapper, synthetic result cases, actor/global-state ownership, incomplete handlers, old ground-only depth calculation, crude multi-tint material behavior |
| Neuro Studio `SpellStudioPreview.ts`, `StudioTimelinePixi.ts`, `StudioTimelineView.ts` | Actual `drawProjectileFramePreviews` / `drawActorLayerFramePreviews`, thumbnail beds, playhead/rulers/markers, source frame/FPS/direction display | Replacing them with a few generic bars; saving a second independent timeline; synthetic native outcomes |
| `/home/tommaso/Dev/NeuroMapEditor/src` | Distinction between composition phase, spatial group/ZGrid identity, support elevation and source calibration; existing layered-world examples | Treating every editor layer as a new engine entity or blindly importing its many UI layers into runtime |
| Archived Pygame `game_obsolete/animation_types.py`, `animation_data.py`, presentation grouping/retained/semantic owners | All authored fields, recipes, causal/timing/lifecycle meaning and owner-local semantic checks | Pygame surfaces, Python pixel loops, CPU per-pixel XYZ buffers, renderer callbacks as portable data |
| Archived `game_obsolete/data/{assets.json,world_bindings.json,environment_art.json}` and their typed loaders | Authoritative registrations, pivots, contacts, faces, pose offsets, transitions, item/environment relationships | Guessing offsets from a PNG's bounding box, art names or a screenshot |
| `/mnt/c/Users/tommaso/Documents/assets/environment-production-audit/placement-registration-53/` | Authored placement/registration evidence and already integrated patches | Applying integrated patches twice or replacing values with visual guesses |
| `/mnt/c/Users/tommaso/Documents/assets/arena-study/prototype-v1/grid-kit/` and its constructor rules/delivery | Family adjacency, matching insert/wall assemblies, valid stairs/cliffs/closures and upper/lower composition | Combining unrelated door and wall families, open-sided elevated examples or unsupported stretched cliff pieces |
| Engine `.runtime/ndclient-fireball-proof/` | Proven v4 decoding, registration, material/depth/normal/light math; native-reach fixture evidence | Its objective fixture knowledge, one-axis two-room shortcut, demo controls as final UI, or separate production renderer |
| Current native `dnd/player`, `server`, `sdk/player-typescript` | Protocol, scoped facts, choices, content admission, reduction semantics, follower and receipts | Old transport proposals, parallel wire models, extra native simulation in browser |

Record the relevant source revision and any local changes used; a HEAD alone does not describe uncommitted working files. No working-file hashing campaign is required. Read relevant complete source functions and matching registrations before adapting them. “Ported” requires named original behavior and a demonstrated new consumer. A source path alone is not implementation evidence.

### 1.2 Completed inputs and remaining integration sequence

**Complete and committed at `df5397e`; do not repeat:** `/home/tommaso/Dev/NDClient` on `codex/ndclient`,
Git ignore rules, readable family artwork folders, selected copies, the initial
VFX replacement/relocation import and Git-tracked `authoring/`. The copy tools and
original sources remain available for an intentional new delivery or a fresh
installation; ordinary builds, launches and JSON edits do not invoke them.

**Next implementation chunk:** make these prepared inputs load through the real
application and current SDK. Its finite outputs are:

1. Extend the existing package and lockfile (already pinned to PixiJS 8.22.0)
   with TypeScript/Vite and the module DAG of §3; install the delivered
   `@neurodragon/player-sdk`. Preserve the working character material/review
   tool while connecting that material to the production renderer.
   Generate authored TS types from the prepared client section schemas once. No new transport, ECS framework, plugin manager or actor
   hierarchy is required. Preserve useful old-client code references read-only;
   reuse existing snapshots rather than cloning another media library.
2. Connect the existing `PresentationCatalogExport` sections to the application
   using the tracked client source described in §5.4. Catalog/world/assets/environment are already
   assembled. Environment family organization and the 60 delivered source-record
   copies/links are complete, including existing wall corner rules, restored
   water registrations and the static geometry companion slot. The §6.1 physical
   contacts, camera registration, door members and timber supports are now connected
   in typed authoring. Consume those fields; do not redo their adoption or read
   supplier records at runtime.
   Item appearance/material/variant/source-palette documents are now adopted and
   assembled from `authoring/items/index.json`, preserving existing owners and
   values. Another 325 equipment sheet references connect already installed
   modular files across the existing authored actions; no clocks, sockets or
   body dimensions changed. UI metadata, exact assignments and relocated paths
   are also adopted in `authoring/ui/`. Connect these existing sections to the
   application loader; do not reload obsolete bindings from Pygame or rerun
   intake. Preserve the two explicit artwork follow-ups in §5.7.
3. Serve the installed `.media/` directly at `/media/`; serve generated metadata
   from a separate ordinary static route. Keep both outside Vite's `public/`
   copying and application `dist/`. No asset-library copy or scan during startup.
4. Configure the existing server's allowed browser origin and explicit API URL.
   Windows server plus WSL frontend is supported. Exercise the real SDK bootstrap,
   audience attachment, choices, command receipt and event follower; install its
   package without copying generated wire models into the client.
5. Start the shared reduction/compilation/resource/renderer path against that
   input. A Studio case is a recorded current-server SDK stream consumed through
   the same functions. Its first functioning family is implementation progress;
   it does not close N1–N5 or justify a throwaway preview renderer.
6. Document repeatable server, client and Studio launch commands. They must not
   depend on orphaned preview processes, Python rendering, boot-time schema
   generation or receipt files.

The delivered engine/server/SDK are inputs to this client work. Ordinary
asset/authoring work does not regenerate the player SDK. N0–N5 remain the complete delivery scope; no additional certification
or packing milestone is inserted between these steps.

Installation coverage and runtime demand remain distinct. All selected artwork
is installed; current and upcoming presentation demand determines residency.
Publish a prepared metadata/resource change together before displaying it, while
keeping the existing scene usable on failure. This does not require an atomic
full-library filesystem installer or a copy per recording.

## 2. Full source coverage and type ownership

The current passive owner has **55 AnimationData fields**, including
`paired_banks` and `sheet_components`. Default-valued fields need not appear in
every JSON file: the current 54-key client index omits only the defaulted
`movement_reference_speed_feet`.
The tracked client copy retains **149 spell/effect drafts, 85 body-action recipes,
160 condition recipes, 44 rigs, 1,054 selected media definitions, 1,051 storage
records and 193 paired banks**. The source study also covers 15 derived AssetCatalog
fields and 24 WorldBindingsSource fields, excluding their schema metadata.
The earlier 1,112 declarations/1,090 storage records describe the historical
engine selection before replacement and unused-registration pruning. Do not
restore retired registrations to satisfy those counts. Counts are coverage
evidence, not distinct spells/files or shader quotas.

The existing machine inventories (`audits/ndclient-plan-20261008/{source-inventory,selected-content-index,asset-authoring-inventory,reference-revisions}.json`) remain identity/source evidence. Add implementation/result columns to the existing report; do not hand-maintain a second catalog. One source revision comparison accounts for newly supplied current content. Do not drop identities to make coverage pass.

Every field has one of three dispositions: canonical source values editable manually in JSON and inspectable in Studio; derived read-only values; or tool-only provenance. Every runtime field has a production consumer, not merely a generated type. Current Studio delivery is read-only: no browser save endpoint, draft document framework or editable timeline is required. Playback, seek, camera, track expansion and diagnostic inspection expose the production path; manual canonical edits are explicitly reloaded/recompiled. Studio and play cannot silently ignore values that the exporter successfully serialized. Source field dispositions are included later in this document.

The browser receives a complete source-derived presentation release with separately addressable sections, plus subjective native SDK state. Static art availability never grants knowledge of unseen native entities or private descriptors. Native types never import rendering or authoring modules. Use the prepared client section schemas for authored types and import SDK wire types directly. Do not relocate engine/Pygame definitions or duplicate them beside each consumer.


### 2.1 New capabilities versus recovered behavior

**9 October user correction:** old spell/VFX XYZ assets are abandoned and fully
replaced. They are historical evidence only, never migration inputs, offline
conversion inputs for NDClient or temporary runtime fallbacks. This supersedes
the earlier XYZ-conversion instructions and historical companion algorithms.
Preserve originals without deletion. Preserve the complete authored recipes,
condition/spatial lifecycles and existing data owners while substituting selected
new media. Depth/normal coverage across world spell and condition VFX is the
preferred eventual direction; exports will arrive over time. Do not turn
"probably everything" into an unapproved requirement for every HUD marker or an
all-library export gate. The shared renderer supports differing delivered channel
coverage per layer and reports remaining coverage honestly. Environment geometry
and existing environment depth are distinct from these retired VFX XYZ banks.

Depth/normal inputs, shared GPU material evaluation, surface-aware occlusion and receiving/emitted light are new production capabilities. They are not claimed as already solved in Pygame or NeuroClient. Those references supply placement, source registration, interaction and temporal behavior; they do not supply the finished new GPU renderer.

Every supported VFX with exported depth/normal channels uses those actual channels through the common source registration and material/depth passes. Available channels must not be discarded in favor of a generic flat quad or fitted dome. Walls and other registered surfaces use exported depth/normals where supplied, or derive equivalent quantities from their explicitly registered geometry. Numeric channels remain raw and calibrated, separate from appearance color and alpha interpretation. The read-only Studio exposes source color, depth, normals, sampled geometry and timed effect tracks from that same production machinery.

Any supported source-authored approximate shape remains explicitly approximate. It cannot substitute for a required replacement that has not arrived, justify recovering a retired XYZ bank, or override supplied measured channels. Channel/component count follows the new source's actual semantics; Fireball's two bands are not a mandatory format for every effect.

## 3. Ownership, execution and minimum duplication

The browser is a presentation client over the delivered subjective API. The native engine owns rules, dice, action economy, perception, movement legality, propagation, destruction, effects and AI. The client owns how admitted events and authored data become an interactive display. A shader, preview, tooltip or timeline must not become another rules implementation.

Use ordinary modules exporting functions and passive records. Pixi objects are renderer handles; actors, spells, conditions and worlds do not become class hierarchies. Keep mutable resources in explicit owners passed to functions. Do not introduce a service locator, plugin framework, generic ECS runtime, event bus hiding dependencies, per-spell renderer classes or a second application store beside the existing state owners.

| Module | Sole responsibility | Forbidden responsibility |
|---|---|---|
| `src/session/` | Delivered SDK calls, attachment/receipt lifecycle, scope, exact recording journal and worker entry point | Rules, animation timing, another SSE parser/retry service |
| `src/player/` | One TS implementation of subjective reduction, occurrence indexing, historical-prefix restoration and displayed-state commit semantics | HTTP DTO copies, art selection, DOM or native simulation |
| `src/presentation/` | Authored recipe resolution, causal grouping, relative-time compilation, retained visual lifetimes and absolute-time sampling | Network transport, texture decoding, invented hits/conditions/geometry |
| `src/render/` | Authored registration/projection, resource leases, geometry, ordered GPU draws, materials, lighting and displayed-scene picking | Native action legality, guessed wall compatibility, spell-name exceptions |
| `src/ui/` | Adapted HUD widgets, DOM text/forms, local gesture/selection state and current SDK choice/preview calls | Paths, damage calculations, a second perception or inventory model |
| `src/studio/` | Prerecorded real-event case selection, detailed timeline, read-only inspectors, source provenance and reloading manually edited canonical data | Browser editing/save APIs, draft/undo frameworks, live game-server queries, a second renderer, fake native event generator or alternate replay engine |
| `src/app/` | Explicit composition of those functions for play or Studio | Global mutable registry, hidden ownership or environment-specific behavior in pure modules |
| `tools/` | Client authoring assembly, explicit future asset intake and actual-server SDK capture before Studio opens | A new Studio tools server/save API, browser access to an objective world or runtime dependency on Python rendering |

The import DAG starts with SDK types and source-derived authored types, then pure player/presentation functions, then renderer/UI adapters, then composition. Studio composes these same layers. Render/presentation types do not leak into native engine types. Client modules follow that DAG using the prepared section schemas and SDK exports. Archived Python imports are not a client dependency and are not repaired or rearranged.

### 3.1 Wire types, authored types and derived state

Import native API and fact types directly from `@neurodragon/player-sdk`. There is no handwritten `PlayerOperation` subset, copied generated-contract directory, camel-case event mapper or different Studio JSON wire format. Preserve nullability, discriminants, IDs, source occurrence intervals, reference semantics and enum variants.

The package exports wire contracts, not a complete browser state implementation. A TS `PlayerState`/occurrence index and compiled presentation records are legitimate derived structures: they implement the existing Python semantics and selected GPU/presentation needs. They are not new server schemas. Neither those structures nor admitted SDK values need a JSON serialize/parse trip between client layers.

Produce authored TS types from the prepared NDClient `authoring/schemas/*.schema.json`, derived during the completed preparation, as an explicit client build operation. Validate external recordings/releases/API packets at their admission boundary. Do not repeatedly validate already-admitted values inside sampling/draw loops. A client-authored field change stays with its client schema and derived TS types. Consume the delivered SDK unchanged; no wire-contract update is planned. Ordinary asset imports, authoring value edits, launches, tests and commands do not regenerate the SDK.

Python replay uses the actual `dnd/player/reduction.py`; it does not get a new test-only reducer. Browser play and Studio use one TS port of that owner. Cross-language differential tests compare the same scoped records and reducer semantics. This does not require a Python interpreter in the browser and does not justify a third simplified reducer.

### 3.2 Worker and main-thread responsibilities

For play, place SDK reception/JSON admission, journal persistence, latest-state reduction and ahead-of-display causal compilation in one browser worker owned by `session/`. Current SDK `decode()` performs synchronous JSON parsing/Ajv admission, so moving only `fetch()` off the render path would not isolate that work. The worker imports the delivered SDK rather than wrapping its protocol in another transport implementation. Studio feeds prerecorded initialization/operation bytes through the same admission/reduction/compilation functions from a local recording adapter; it creates no connection, attachment, follower, choice query or game-server dependency.

The main thread owns Pixi/DOM handles, input, the displayed absolute clock, sampling of prepared channels, GPU preparation and atomic displayed-frame publication. It must continue drawing and accepting camera/inspection input while native processing, SDK admission, recording or compilation is busy. Compilation/preparation jobs yield between meaningful units so a long historical request does not monopolize the worker's status/journal work.

There is one pure reducer/compiler implementation, imported by the owners that need it:

- The worker maintains the **latest reduced state** for current authority and indexing. It restores a requested historical prefix through the same reducer when preparing a group or a seek, using the journal and disposable derived checkpoints.
- The main thread maintains the **displayed state**, at an older position when playback is behind. It applies prepared, admitted facts at authored commit points through the same reduction/commit functions. These are two necessary positions in one history, not competing rules models. Do not transfer the entire latest world after every incoming record or overwrite the displayed state with it.
- Prepared groups carry original fact/occurrence references, relative-time channels, the existing typed values required by their commits, and resource identities. The main thread assigns their actual absolute start when they can be displayed. A historical seek may replace displayed state with a prepared prefix snapshot; normal animation does not serialize the whole world every frame.
- The internal bridge has explicit request ID and application/scope generation. Its request bodies reuse existing SDK request types, and its responses reuse SDK values or named derived presentation values. It is an in-process boundary, not another versioned game protocol, mini RPC framework or duplicate schema hierarchy. Use structured cloning/transferable buffers as appropriate; no JSON stringify/parse round trip to communicate with the worker.
- New seek/camera/choice requests supersede only their local older requests. Replies with stale generation/request ID cannot publish state, UI or resources. Private network state remains owned by the session worker; it is not placed in a process-wide shared worker spanning unrelated audiences.

This is an execution choice inside the module DAG. Both modes still consume the same data and functions. GPU resources stay in the rendering owner, recordings in the session owner, and neither worker nor main thread creates its own competing asset/journal framework.

### 3.3 One production presentation path

The common path is **admitted recorded facts → historical reduction → causal/recipe compilation → retained lifetimes and channels → absolute-time sampling → registered geometry/materials/resources → ordered production render passes → displayed-state UI/picking**. Live play supplies those facts from the SDK; Studio supplies them from a pre-recorded local case. This must be the same executable pipeline, not two executors that merely share types or a sprite helper. Studio timeline/inspectors read that pipeline's actual source/compiled channels; they do not own a preview renderer or recreate native events. Capturing test streams happens beforehand by driving the actual current server through its SDK, outside Studio; direct native exports are setup/reference evidence, not delivered-server recordings.

Studio is read-only in this phase. Edit the tracked NDClient `authoring/` JSON, assemble changed metadata with the client build tool, then reload the recording/presentation release and recompile through the same runtime. Source Pygame files and Factory snapshots are provenance; the one-time importer is not an edit/reload step. Keep field inspection and exact source-path/value provenance so an author knows what to edit. Do not build a browser save API, edit-transaction protocol, draft/undo framework, new rig-authoring workspace or tools server for this read-only workflow.

Full spells, actors, geometry, lighting, particles, retained conditions and state transitions must progress through the live game path and the recorded Studio path alike. A polished timeline or a standalone scene that renders selected sprites cannot substitute for that coherent production renderer.

**Source owners:** `sdk/player-typescript/src/index.ts` (`decode`, `Consumer`, `follow`); `dnd/player/reduction.py`; `game_obsolete/presentation_group.py`; `game_obsolete/presentation_retained.py`; `game_obsolete/choreography.py`; `game_obsolete/timing_evidence.py`.

## 4. Delivered server, SDK, playback and recording integration

### 4.1 Install and connect to the service that exists

Consume the ESM package at engine `sdk/player-typescript`, package name `@neurodragon/player-sdk`. Build/package that source once for local installation and pin the resulting package/revision through the normal dependency lockfile. Browser startup never invokes a generator or Python; building the delivered package is not permission to modify its owners. The older `@neurodragon/dnd-engine-sdk`, Omni server, WebSocket store and old NeuroClient result mapper are not compatible replacements.

The delivered protocol identity is protocol 1 / player schema 5, as recorded in `server/protocol.py` and `sdk/player-typescript/src/protocol-identity.json`. Let the SDK perform its packaged identity check; do not hardcode another digest or regenerate contracts for this client implementation. Inner recording/fact schema versions are separate values and remain unchanged.

The native service can run on Windows or WSL independently of the WSL frontend. Use the existing launch/configuration path:

```text
python -m server --config <private-server-config.json> --host <reachable-address> --port <server-port>
```

Configure the actual frontend origin in `ServerConfig.allowed_origins`; the current default is empty. Select an API port independently of the existing standalone Fireball proof. The browser uses an explicit API base URL that reaches the configured service. Windows/WSL networking must be checked on the actual machine rather than copying a stale adapter address. Do not create a proxy/rules service or bind the server publicly merely to conceal an incorrect local URL.

Use an existing seat credential supplied through local runtime configuration/input and held in session memory. Never put it in a query string, committed source, public presentation release, exported recording or frontend build-time environment variable that is shipped to the browser bundle. This phase needs the existing credential/seat setup, not a new account or lobby system.

Use these exports directly:

```ts
import {
  connect, attach, status, choices, preview, submitCommand, receipt,
  content, createFollower, follow, waitForCursor,
  PlayerApiError, ProtocolError,
} from '@neurodragon/player-sdk';
import type {
  InitializationResponse, PlayerOperation, PlayerCursor,
  ChoicesRequest, PreviewRequest, CommandRequest, ActionSelection,
} from '@neurodragon/player-sdk';
```

The SDK owns `Authorization: Bearer …`, `X-Game-Epoch`, `X-Audience-Id`, `X-Attachment-Epoch`, request/response admission and authenticated-redirect rejection. UI code does not assemble those headers itself.

| Existing route | Meaning and client use |
|---|---|
| `GET /health` | Liveness only; not confirmation that a player's encounter is ready. |
| `GET /api/v1/bootstrap` | Authenticated protocol/status, audience, encounter name and content revision. |
| `GET /api/v1/games/{game_id}/status` | Current authoritative lifecycle, input actor/revision, cursors, attachment and command numbering. |
| `POST …/attachment` | Acquire the consumer attachment with an acquisition ID and expected attachment epoch. |
| `GET …/initialization` | Subjective initialization at sequence **0**; consumed by the existing follower. |
| `POST …/ack` | Acknowledge SDK consumption, not visual completion; owned by `follow()`. |
| `GET …/events?after=N` | SSE of exact retained subjective operation bytes, with ready/status/error control records. |
| `POST …/choices` / `POST …/preview` | Native action discovery and selected action/route/AoE/target preview. |
| `POST …/commands` / `GET …/commands/{number}` | Numbered command submission and receipt reconciliation. |
| `GET /api/v1/content/{revision}` | Existing public content descriptors for that revision. It is not an objective world download. |

There is no current browser create-game, engine-pause, arbitrary displayed-state snapshot or live audience reassignment endpoint. Do not design UI dependencies on them. Operator configuration creates the encounter/controllers; the client attaches to what is configured.

**Source owners:** `server/{README.md,__main__.py,config.py,app.py,protocol.py}`; `sdk/player-typescript/{README.md,package.json,src/index.ts}`; `sdk/protocol/README.md`.

### 4.2 Scope, audience and attachment

The stream identity is `{game_id, game_epoch, audience_id}`. A `PlayerCursor` is that identity plus `sequence`; it is not an unscoped integer. `PlayerAudience` supplies controlled entity UUIDs, observer entity UUIDs and revision. Faction, control and granted observation are different things.

One controller may own several units and receive one authorized team audience stream. One controller per entity and mixed human/AI configurations also work through existing seat/controller configuration. There is no invented two-seat limit, no socket per controlled character and no inference that sharing a faction grants all of that faction's information. Changing selected/inspected party member keeps the same granted audience connection. Native action legality still belongs to the current acting entity, even where the UI can see a teammate's admitted view.

Use the delivered audience projection/reduction: member senses, contact/effect cursors, absences, event-time observations and known-empty retirements. Do not create a client union of objective maps. Public art availability does not admit a hidden entity, its name, item, position or current visibility. Render placement derived from an explicitly allowed assembly observation likewise does not become a new seen tile or target.

Bootstrap/status may be `starting`; show connection/preparation state and wait for real readiness. Acquire with `{acquisition_id, expected_attachment_epoch}` from current status. Retry an uncertain acquisition with the **same** acquisition ID/body. A replacement attachment invalidates the previous attachment; it is not permission for two consumers to fight for a seat. Surface `attachment_replaced` and require the explicit local session transition rather than repeatedly stealing the attachment back.

`StatusSnapshot.boundary` contains `lifecycle`, `input_actor_uuid`, `state_revision` and optional reason/incident. The lifecycle is `starting`, `waiting_for_human`, `advancing`, `delivery_blocked`, `terminal`, `failed`, `closing` or `closed`. Keep those states visible in appropriate diagnostics without filling the normal HUD with engine prose. The snapshot also gives `published_cursor`, `final_cursor`, `catch_up_cursor`, `acknowledged_cursor`, `attachment_epoch`, `next_command_number` and `pending_command_numbers`.

**Source owners:** `dnd/player/audience.py`; `dnd/player/projection.py`; `server/protocol.py`; `server/host.py`.

### 4.3 Ingestion and ACK: preserve every admitted operation

The existing SDK `createFollower(connection, consumer)` and `follow(follower, options)` own initialization, SSE admission, scope/protocol checks, contiguous sequences, duplicate network frames, ACK and network reconnect. The consumer receives both the admitted `InitializationResponse | PlayerOperation` and its `Uint8Array` raw payload.

Implement its awaited body in this order:

1. Check the captured application/scope generation. Choose the journal by exact scoped recording identity.
2. Retain the immutable raw record and its required release/protocol/prefix metadata durably. Duplicate keys must agree with the retained identity and bytes; a conflicting record is corruption, not an overwrite.
3. Admit `content_additions` into the existing content index before dependent lineages. Reduce the initialization/operation with the one TS reducer and advance its contiguous latest prefix only after successful reduction.
4. Publish the new consumed/latest bookkeeping and make the retained operation available to causal preparation. Return from the consumer. Do not wait for media decoding, shader compilation, a selected camera, a visual group or animation duration.
5. The follower advances its consumed cursor and performs the native ACK. It then continues receiving while presentation may still be far behind.

No acknowledgement is sent for discarded/unpersisted records. A recording failure stops acceptance and reports that real fault; it is not hidden by a catch-all or solved by dropping old unplayed actions. A reducer/admission error retains an identifiable incident and prefix for diagnosis rather than silently skipping a node. The server's existing spool/capacity behavior remains its own responsibility.

**Important SDK behavior:** `waitForCursor()` means the follower's consumer has accepted the cursor. In current `follow()`, consumed/waiter notification occurs **before the awaited ACK request completes**. Therefore `await waitForCursor(...)` alone does not establish server-side input admission. Use current status/catch-up/acknowledged cursors for command readiness, and handle a returned `catch_up_required` by waiting for the actual required SDK catch-up/ACK state, not resubmitting a spending action blindly.

`ready`, `status` and `error` SSE records are control values, not numbered presentation operations. The server's authoritative boundary may change without inventing an animation. A terminal stream has a final cursor; finish presenting its retained prefix. A failed/closed stream keeps its valid recorded prefix inspectable while reporting the failure. Do not manufacture a completed encounter from a disconnected stream.

**Source owners:** `sdk/player-typescript/src/index.ts` (`Consumer`, `consume`, `follow`, `waitForCursor`); `server/protocol.py`; `dnd/player/reduction.py`.

### 4.4 A complete causal reducer and compiler

Port the actual `dnd/player/reduction.py` invariants, not merely its common examples:

- Sequence/operation cursors and source occurrence cursors are different coordinate systems. Preserve one-past occurrence boundaries, nullable roots/facts, disclosed source ranges and references to retained observations.
- Content identity is immutable and additions arrive before their uses. An event-time contact supplies the right historic identity/pose/position even when the latest view can no longer see that actor.
- `stage_lineage` admits absent actors/known support needed by the occurrence without advancing an already-known actor into future state. Late observations cannot resurrect a terminal actor.
- A committed nested spatial change supersedes its enclosing operation's older closing observation. Preserve actual before/after values and their occurrence order.
- `lineage_branch` respects admitted occurrence ranges even where private ancestry means a disclosed descendant has no public parent. Do not fabricate missing parents or recursively guess an objective tree.
- Ordered HUD/combat-log after-values are revealed at their actual commits. The display never looks up a dead/departed actor's name only in the latest visible-contact table.

Every current `PlayerFact` variant needs its actual consequence: attack/spell/application and area-reach stages; path and movement steps, forced movement, jump/portal/shove; damage stages, healing, temporary HP, life/death saves; equipment/item/charge changes; conditions and concentration; spatial effects, world/mechanism/object damage and destruction; faction/turn/action/sensory changes; saves and cancellation. A legitimate nonvisual fact still participates in causal state/log/authority updates. An unimplemented variant is not a zero-duration success.

Use `game_obsolete/presentation_group.py` as the source for grouping consecutive reaction roots that refer to the following root. Grouping is a scheduling view; reduction remains in original admitted order and event ancestry is unchanged. Cast release, missile contacts, saves, reactions, damage, death, condition application, topology/light changes and aftermath must be scheduled from the source authored timing/evidence and native causes, including multiple applications/projectiles and nested interruptions.

The action compiler must stop or alter the affected occurrence on its actual cancellation/interruption. It cannot let a character perform a planned jump after a lethal opportunity attack because a top-level motion track was compiled independently. Visual media can be sampled at the current clock, but required occurrences, contacts and state commits cannot be omitted under load.

Retained visual state uses the six existing lifetime families: conditions, spatial effects, item effects, construction, concentration and deposits. Restore an existing lifetime at cold acquisition/seek without replaying its creation as a new cast. End/expire/suppress/resume/transfer each lifetime from its admitted event/state; do not rebuild it every frame, restart it upon camera rotation or revive it after historical expiry. Timeline/editor views inspect these same compiled and retained records.

**Source owners:** `dnd/player/{facts.py,reduction.py,application.py,recorded.py}`; `game_obsolete/{presentation_group.py,presentation_retained.py,choreography.py,timing_evidence.py}`; existing authored recipe owners covered in the source inventory.

### 4.5 Separate native progress from displayed time

Track received/consumed progress and displayed occurrence/time separately. They are positions in one retained history. The latest state supports current authority and query bookkeeping. **Only displayed state** drives scene geometry, actors, inventory/vitals, portraits, conditions, light/visibility, picking and timed combat-log reveal.

AI may finish several turns while the client is playing an earlier action. Queue every admitted animatable occurrence once in causal order. Do not coalesce to the newest operation, jump to a later turn because resources are late, expose future UI values, or require native computation to wait for animation completion. Authored parallelism is allowed; a generic backlog speed-up/skip is not implied by this design. A low render FPS may skip image samples, not semantic outcomes.

Use one absolute displayed clock for all animated visual families, including idle bodies, environmental water/flames, condition loops, material motion, lights and transitions. A group has an actual `presentationStartMs`; its local time is derived from the absolute clock. Source frame rates and authored durations remain source values. Do not make every effect's progress depend on a separate ad-hoc wall-clock timer. Studio manipulates that same clock over its prerecorded local event source; it does not need a running server.

Store local presentation progress as:

```text
PlaybackPosition:
  absoluteTimeMs
  sequence       # last fully presented operation
  timeMs         # local time into the next/current presentation operation

Started operation metadata:
  sequence -> presentationStartMs
```

These are application recording metadata, not additions to server packets. If a compiled presentation group spans source operations, retain its source operation ranges and commit mapping so the operation-level position stays meaningful; never invent a replacement transport sequence.

- Idle between operations advances absolute time while the last completed sequence and zero next-operation offset remain stable. Existing loops continue.
- A prepared next group starts at the current displayed clock when it is ready. Time spent waiting for an asset does not become a hidden gap inside a cast that has not started.
- Pause freezes the displayed clock. In live play, network reception/journaling continues. In Studio, the available source is already prerecorded. Seek/replay prepares and samples the requested absolute position through the same implementation in either mode.
- Restoring a local recording restores the saved absolute position and starts. It does not advance by elapsed wall-clock time while the app was closed.
- A raw recording without local playback starts receives deterministic consecutive starts from compiled durations. A different authored release/compiler deliberately rebuilds its derived schedule; it cannot silently claim the old timings are identical.

Player-spending gestures are enabled only when their displayed actor/context matches the current native input actor/state revision and acknowledged catch-up state. Camera, inspection and history remain responsive independently. Prefetched current choices may make a stale display non-spendable, but may not reveal a future inventory/cooldown/condition in its still-playing HUD.

### 4.6 One durable journal, reconnect and offline replay

Use one session-owned IndexedDB recording store scoped by game/epoch/audience and recording identity. It contains:

- Protocol/content/presentation-release identities and authored/compiler semantic versions needed to reproduce the display. Credentials are excluded.
- Immutable exact initialization and operation payloads keyed by their sequence, plus the contiguous durable-prefix metadata.
- Local displayed position/absolute start metadata, prerequisites and disposable derived checkpoints produced by the same reducer/retained-presentation functions.

Checkpoints contain passive state/index data, never Pixi objects, live SDK connections, callbacks or a second normalized event format. An incompatible checkpoint can be rebuilt from retained raw records. An incompatible authored release is an explicit compatibility decision/failure, not permission to invent missing frames or retime the recording without notice.

Publishing a displayed checkpoint/progress record must also preserve the retained-prefix references it needs. Persist at meaningful state/lifecycle/playback boundaries; do not write a complete world every render frame. Use the simplest IndexedDB transaction ownership that gives the required durability. Do not invent a transaction-count ritual, arbitrary storage quota, fixed checkpoint cadence or recording-limit gate to satisfy this plan.

Decoded memory, prepared groups and GPU textures are disposable once their retained prerequisites are safe. Unplayed ACKed records are not disposable just because the user has not chosen “Export recording.” Disk retention is mandatory for that backlog; exporting/sharing a recording is separate UI. Retaining an old presentation release on disk does not require keeping all its textures decoded/resident or copying it once per recording.

The current follower has two distinct recovery behaviors:

1. **A running follower reconnects** from its consumed cursor, after re-establishing its native ACK. The application leaves that transport path to the SDK.
2. **A newly created follower starts with initialization at sequence 0.** `follow()` has no arbitrary restore-at-local-consumed argument. Reconcile the duplicate initialization/prefix with the existing journal, rebuild a fresh latest reducer as needed, and avoid queuing those occurrences twice. Do not mutate `follower.consumed` from the saved displayed position or invent an SDK resume API.

Restore presentation independently from its local displayed checkpoint/prefix. Local unplayed records remain replayable even if live server retention has expired. Current server retention is a live-process history policy, not whole-world save/load across a server restart. If live history or a needed pinned release is unavailable, report that actual boundary; do not pretend intervening animations have already played. Offline replay of a locally retained record/release uses the same runtime without a server. This does not promise that media never downloaded will be magically available offline.

When real storage capacity is exhausted, stop acceptance before ACKing another record. There is no client pause-native endpoint. The server may continue until its own existing spool policy applies. Expose that failure and recovery options without dropping occurrences, adding a new server control plane or imposing invented numerical budgets.

**Source owners:** `sdk/player-typescript/src/index.ts`; `server/{host.py,config.py,README.md}`; `dnd/player/{recorded.py,reduction.py}`; derived clock metadata is the explicit client responsibility above.

### 4.7 Prepare resources and publish one coherent displayed frame

Resource readiness applies to the **candidate displayed state**, not only whatever actors existed before the next commit. Preparation gathers the current frame, all state changes inside the next prepared group, transition-only media, newly admitted actors/equipment, world changes, lights/materials, before/after poses and any paired planes needed by their selected camera/frame.

Perform a displayed replacement in this order:

1. Sample a candidate complete displayed state/channels for the requested time/camera/release and compute its required resources.
2. Acquire the new demand while keeping the old displayed demand alive. Complete decoding/upload/preparation for all required frame companions.
3. Publish the candidate time, player/retained state, projection, drawn content, picking, light/visibility and HUD together at one frame boundary.
4. Release resources no longer needed after that swap. Dispose canceled candidates without touching the still-displayed owner's leases.

If not ready, keep the previous complete frame/state/time. Continue network work, UI and camera intent; do not advance invisible state behind a frozen image. Requested camera/seek/release and displayed camera/seek/release are distinct until commit. Picking must use the projection actually drawn, not the requested rotation whose images are still loading.

Use one rendering resource owner with explicit demand/lease records; texture interpretation includes resource URL/revision, dimensions/layout, encoding, sampling and alpha convention. Public identical payloads can share bytes, while a numeric plane and a color texture cannot accidentally share incompatible TextureSource settings merely because their URL matches. Registered frame planes are acquired/swapped together. There is no separate loader per spell, actor, Studio pane or camera.

Scope/case/release/seek generation tags every asynchronous preparation. A stale completion releases what it acquired and cannot install itself. Context loss invalidates the GPU generation and rebuilds resources from current demand through this same owner; it does not rerun the engine, reset the recording, duplicate conditions or restart all effect clocks.

### 4.8 Choices, variants, routes and commands are native contracts

This section applies to live game interaction. Studio does not discover choices, preview legal actions, issue spending commands or synthesize a stream from button clicks. It renders supplied test streams through the production path.

`choices()` receives `{actor_uuid, state_revision, force_attack, correlation_id}`. The result echoes revision/correlation/force-attack and returns `AvailableActionsResult`. Keep each row's original discovery index while visually grouping it. The native flattened order is entity actions, position actions, self actions, then object actions; UI sorting does not become command indexing.

Consume the fields that already carry behavior instead of rebuilding it from a label:

- `behavior_id`, `provided_by_id`, `origin_root_id`, `configured_action_ref`, category and target type identify the actual action and variant.
- `can_afford`, `availability_status`, costs, `restricted_action_budget`, charges and item fields determine whether the offered action can currently be used. The client does not recompute action economy from a class name.
- `weapon_slot`/`performs_attack` separate real melee/ranged attack affordances. `spell_level`, `cast_at_level`, `is_spell_variant`, concentration and `variant_facets` drive actual upcasts/choices.
- `num_projectiles`, `allow_same_target`, `allocation_completion` (`selected_only` or `fill_primary`) and target selection data describe allocation. Preserve repeated target indices and order; do not assume distinct targets, always demand a maximum count, or distribute projectiles with client rules.
- `interaction_affordance`, `connector_traversal`, `world_interactions`, handler details and item provenance feed their corresponding UI. World interactions are descriptors, not a substitute executable command.

The current `ActionSelection` contains `action_index`, ordered `target_indices`, optional `extra_target_positions` and `prefer_safe` (default true). Preview, execution and SDK echo checks already support that same selection. Those targets are native indices and coordinates; negative map coordinates are valid and unrelated to invalid list indices. Secondary targets use the selected primary's native target pool when supplied. Never regenerate pools from currently drawn entities.

For a changed selection call `preview()` with `{actor_uuid, state_revision, discovery_generation, correlation_id, selection}`. The SDK verifies the echoed request. Use `AvailableSelectionPreview.can_confirm`, `reason`, `effective_target_uuids`, `next_targets`, `next_positions`, `geometry`, `affected_positions` and `selected_route`. A route supplies its actual path, `cost_feet`, affordable endpoint, normal/safe policy, opportunity-attack exposures and hazard flag. Show that route and geometry. Do not have a separate UI pathfinder or approximate spell footprint decide the execution gesture.

Ordinary movement sends `prefer_safe: true`; Shift sends `false`. A modifier change
invalidates the local preview even on the same hovered tile; submit exactly the
selection that produced the displayed current route. The returned route policy is
a result, not a guarantee: safe preference may legitimately fall back to normal.
Focus loss clears Shift. The feature is delivered; no backend or SDK task remains.

A world click requiring approach uses the admitted native route and then refreshes discovery/preview at the reached state before executing the interaction. A door/window/trap/lever is not activated from an invented range because its descriptor exists. If the route or state changes, retain user intent only where it remains valid and ask the native preview again; do not send an old discovery index.

Selection-changing hover/input can supersede an earlier request. Match reply scope, actor, revision, discovery generation, correlation and local request generation before rendering or enabling confirmation. `stale_state`, `stale_discovery` and `query_superseded` retire obsolete local data. They are not reasons to loop indefinitely on the same request or display a valid-looking stale confirmation.

Submit the existing `CommandRequest` using the authoritative next command number, actor UUID, state revision and one supported intent: `execute_selection` with discovery generation/selection; `end_turn`; `equip`; `unequip`; or `toggle_handler` with its native discovery/handler value. The native host still validates ownership, turn, state and ACK catch-up. Self actions that need no target execute through that actual intent once; they do not acquire a fake extra confirmation just because targeted spells use one.

Command receipts are `pending`, `committed(cursor)`, `rejected(reason)`, `indeterminate(incident_id)`, `expired` or `unknown`:

- Pending means accepted for processing, not success or a visible state commit. Committed identifies the native operation cursor; its animation still waits for normal display preparation.
- A lost HTTP reply is reconciled with `receipt(number)` or an identical numbered submission. Never spend twice by retrying with a fresh number, or mutate a numbered command's payload after uncertain submission.
- Admission errors need not consume a command number. A command accepted as pending can later receive a stable native rejection. Use returned status/receipt data rather than guessing the counter from button clicks.
- Do not automatically turn `indeterminate`, expired history, a conflicting numbered payload or an unknown receipt into another spending action. Keep the unresolved identity visible for correct reconciliation.
- One local command remains pending for its native admission lifecycle. Input/preview UI does not optimistically apply damage, decrement resources or remove an item. Actual displayed outcomes come from the admitted operation at their authored commits.

**Source owners:** `dnd/core/base_actions.py` (`AvailableActionInfo`, `AvailableActionsResult`, `AvailableSelectionPreview`); `dnd/player/{commands.py,selection.py,session.py}`; `server/{protocol.py,host.py,worker.py}`; `sdk/player-typescript/src/index.ts`.

### 4.9 Teardown, privacy and stale callbacks

Changing audience/game/epoch is an explicit scope replacement. Before awaiting any new connection or asset work: increment the application generation, stop new old-scope actions, clear old private canvas/HUD/selection/picking/tooltip state, abort the old follower and requests, and release the old scope's owned demands when no displayed owner remains. If the new connection fails, show an empty scoped error state rather than the old audience's world underneath it.

Aborting alone is insufficient. In the current SDK, `consume()` races the consumer promise against the AbortSignal; an already-running consumer callback can finish after `follow()` has rejected. Every awaited consumer stage and its publication must verify the captured generation/scope before mutating active state or queuing display work. A durable write already in progress may finish in its original recording namespace, but may not install that record/state into the replacement session. Apply the same rule to choices, previews, receipts, workers, checkpoints, decodes, uploads, release reloads and case switches.

Keep an old private recording only as an explicitly selected local record with its own scope; never merge it with a newly authorized audience or use it to enrich that audience. Public immutable art bytes can be shared safely. Private discovered identities, state, logs and query caches cannot be global caches keyed only by a spell or creature ID.

Do not catch errors and continue with a fabricated scene. Errors identify operation/occurrence, scope, recipe/asset and relevant source value where available. Report unsupported content/registration clearly in diagnostics while preserving the last valid scoped state. A narrow fault boundary may keep controls usable, but it cannot mark a missing consumer or failed frame as delivered.

### 4.10 Focused integration checks for these boundaries

Use actual-server SDK recordings (§8.2.1), not a new fake browser rules generator. This section specifies semantic coverage, not a repeated validation ceremony:

| Case | Required observable result |
|---|---|
| Fresh attach and subsequent reattach | Real init 0, exact scope, acquisition retry identity, no duplicate queue and no attachment-stealing loop. |
| Slow/paused display while AI advances | Durable consumed progress runs ahead; every admitted event plays once; displayed names/HP/items/visibility/light/log remain historical until each commit. |
| Lethal nested interruption | Original native ancestry/ranges preserved; lethal opportunity attack prevents the subsequent planned jump/movement where canceled; no actor identity lost to later perception. |
| Loss immediately before/after consumer or ACK | Identical retained prefix, no double reduction/queue/spending; `waitForCursor` is not treated as completed server ACK. |
| Reload with ACKed-but-unplayed backlog | Fresh SDK init 0 reconciles journal; display restores its saved absolute time and native reception follows SDK semantics. |
| Native terminal/failure and local capacity failure | Retained prefix remains inspectable; final cursor respected; no ACK of discarded bytes and no invented engine-pause call. |
| Release/case/audience switch during async work | Every late response/callback is scoped; old private pixels and UI clear synchronously; candidates cannot overwrite the new session. |
| Resource stall, seek, camera rotation and context loss | One complete displayed state/projection/HUD/picking transaction; no half-uploaded companion maps or effect-clock restart. |
| Variant/allocation/route/receipt | Current discovery indices survive bar grouping; native target order/multiplicity and route are executed; uncertain command cannot spend twice. |
| Offline recording and checkpoint rebuild | Same reducer/compiler/renderer and retained lifetimes; no hidden native fetch or alternate Studio event interpretation. |

Native, HTTP/stream, SDK admission, journaling, compilation, resource preparation, sampling and GPU work are separately attributable. Tests/builds can establish a boundary invariant; they do not establish visual quality or complete content support by their count. Run these checks when the corresponding implementation changes and once as integrated coverage, then move on to delivery rather than repeatedly regenerating schemas or rerunning unchanged gates.

## 5. Complete client presentation release

The native player schema supplies the current world and causal facts. This chapter
connects prepared client authoring and its existing schemas to the application.
It does not extend native facts or maintain an obsolete Python renderer.

### 5.1 One complete release

Connect the already assembled client sections through the existing
`PresentationCatalogExport` envelope/defaults and source-derived schemas. Add
the generated release index and resource descriptors needed by the application
loader; this is not another authoring adoption or editable catalog. The release contains:

* AnimationData, including all recipes, rig registrations and bindings;
* WorldBindingsSource/AssetDocument, water and residue materials;
* EnvironmentDocument for doors, traps, props, wrecks and animated banks;
* exact item-visual, icon, choice-icon and portrait bindings;
* the resource table: existing resource ID, readable URL, byte size, format,
  dimensions/frame layout, coupled plane references and dependencies;
* source-file/JSON-pointer locations from `authoring/catalog-index.json` and the
  corresponding existing section files for read-only inspection. Preserve
  supplied historical provenance; do not reconstruct inheritance histories or
  build a separate per-field revision database.

Release sections reference shared IDs rather than duplicating payloads. `media_root`
and filesystem paths become tool input or release-relative URLs. Private native
events, hidden map data and absolute author filesystem paths never reach the browser.
The item visual ledger at `content_data/ledgers/neuroclient_authored_item_visuals.json`
was the source for the now-adopted `authoring/items/` sections. Consume the tracked
client values; do not import them again, substitute old generated-client tables
or make Studio a separate source owner.

### 5.1.1 Connect canonical recipes to the prepared artwork

**Present state:** the initial adapter and editable client copy are implemented.
`NDClient/tools/import_vfx_authoring.py` uses the existing effective engine export,
joins delivered bindings by existing ID, then writes tracked `authoring/`. It
refuses to overwrite that directory. Pygame's original authoring stays unchanged;
subsequent NDClient JSON edits belong to this client copy. This is complete asset
connection preparation, not renderer implementation or the whole release in §5.1.

`tools/build_authoring.py` assembles the existing catalog/world/assets shapes from
`authoring/catalog-index.json`, without engine imports, raw delivery manifests or
copy receipts. With the subsequent environment/item/UI adoption it resolves
126,959 distinct media references. Four world maps
have one editable owner in `world.json`, referenced by JSON pointers from the
catalog index. Source schema checks and focused authoring cases cover this boundary.

The connection uses existing identities, with no filename guessing:

```text
server fact / content ID
  → current canonical spell/action/condition/world recipe
  → recipe's existing assetId or resource ID
  → selected media binding (ordinary source or delivered replacement)
  → selected phase / facing / component / frame and its registered material
  → relocated resource URL under /media/ + matching geometry companions
```

Use the existing `AnimationData` and `PresentationCatalogExport` owners. The
initial importer joins the effective engine authoring with selected Factory
media bindings and copy locations once. Future complete-release assembly reads
the tracked client copy; play and Studio consume that same release. `.runtime/*/files.jsonl` records where a source was copied; it
is an installer input, not a browser lookup service or a second editable catalog.
Factory `consumers` and `production_definition` snapshots provide provenance and
comparison evidence. They do not overwrite subsequent canonical authoring edits.

| Existing owner/input | Required treatment in the existing export path |
|---|---|
| `AnimationData.drafts`, action/condition recipes and `WorldBindingsSource` | Keep content IDs, motion choices, sockets, release/contact/cancellation, lifecycle ownership, palette/materials and gameplay causes. Moving artwork does not rename these identities or rewrite a recipe per camera. |
| Delivered `spells[].media[assetId].binding` | The importer resolves replacements by the exact existing asset ID, then computes the selected dependency closure. Replace selected media storage and source frame interpretation; never load both replacement and retired storage. A shared ID has one consistent selected definition. |
| `paired_component`, `directional_paired_component`, `directional_paired_composite` | Preserve bank references, half-open windows, explicit playback FPS or bank FPS, facing aliases, ordered parts/material meaning and authored coalescing. Coalesce only the matching layers of one effect occurrence, never unrelated casts sharing a bank. |
| `preserved_actor_or_projectile_layer` and `runtime_resources` | Keep packed frame regions, condition sockets, hand layers, textures and operator meshes. Procedural Lightning/Chain Lightning still use their live operators despite having zero paired banks. |
| `ProjectileFrameLayer`, `ProjectileFramePart`, `PairedMediaSelection`, `PairedFrameBank`, `CaptureMatrices`, `RayDepthGeometry`, `BytePlaneSource` | These passive owners already exist. Consume their delivered storage, calibration and material semantics; generate authored TS types from them once. Do not add competing models or repeat the completed paired-owner extension. |
| Existing file/resource paths and copy receipts | Relocate actual file fields into `/media/<readable path>` resources without changing their logical IDs. Resolve root-manifest paths relative to that manifest and packet paths relative to each bank. Preserve operator JSON sibling paths. All selected files lie under the one installed media root; absolute source/provenance paths stay tool-only. |

The paired consumer must implement the fields already present in the tracked
source. These are shared operators, not separate per-spell systems:

| Authored input | Production behavior and same Studio inspection |
|---|---|
| `frame_window`, `playback_fps`, `loop`, bank FPS | Sample the half-open source window at the authored effective rate; absent override uses bank FPS. Loop only the selected window. Playback speed applies once; source phase age and native commits stay distinct. |
| `selection_basis`, `banks`, `parts_by_facing` | Facing uses the registered effect direction/camera mapping. `wall_axis` uses the authored wall orientation; Frigid Air's `d0…d3` are not actor-facing rows. Preserve explicit facing aliases rather than deriving bank indices from row order. |
| Frame `camera_matrices` and bank `camera_matrices` | A supplied per-frame calibration overrides the bank calibration; null uses the bank value. Decode depth for that sampled frame, then apply the supplied source-to-host and registered occurrence transform. Normals use the corresponding inverse transpose, including mirrors. Do not replace the delivered calibration with one global camera. |
| Full canvas, crop, pivot, `source_to_host`, depth range and partition | Register all appearance/geometry companions once in the common space. Cropping or atlas placement does not change contact or physical size. Geometry validity and opacity remain different quantities. |
| Composite parts, blend and `material_semantics` | Retain authored part order and appearance meaning, including Ice Knife coverage debris plus additive zero-opacity flash. Do not erase flash pixels by testing opacity alone or relabel every component as a volume half. |
| `coalescing_group`, `replace_historical_halves_with_one_instance` | Replace aliases only inside the same logical effect occurrence. Independent casts/conditions sharing a bank remain independent; near/far packets are sampled once for that occurrence. |
| `removal.kind = consumer_opacity_fade`, `seconds` | On the owning lifetime's presented removal, apply the declared fade to radiance and opacity together, retaining the source sample/lifetime until fade completion. Expiry/interruption cannot loop forever or restart an unrelated effect. Native removal commits remain authoritative. |
| `receiving`, optional `emitter` | Receiving and world-light emission are independent. Preserve actual supplied emitter keys. A phase-specific emitter supplies that phase's light; otherwise use the bank default if present, once per logical occurrence rather than per packet/alias. No association means no invented world light. |

**Concrete Fireball trace from the copied data:** the impact recipe still names
`shared.fireball.20ft-ground.smoke.v3`. The delivered binding for that exact ID
selects `core:fireball`, window `[0,46)`, playback FPS `24`. Its bank is:

```text
authoring/media/banks/core-fireball.json
  → /media/vfx/areas/fireball/explosion/near/0005.appearance.rgba8.gz
  → /media/vfx/areas/fireball/explosion/near/0005.geometry.rgba8.gz
  → matching far/ appearance + geometry files
```

The `.v3` in the stable ID is not an instruction to load old v3 pixels. The
preserved source recipe still contains impact `fps:32` and
`composition:xyz_volume`; the source definition also retains old dimensions and
scale. The client copy uses the new bank's source clock, canvas,
registration and paired depth composition, while preserving the recipe's
gesture, release/contact timing and independent artistic controls. Do not apply
obsolete asset calibration as another scale/pivot or a second hand displacement.
Unchanged travel still resolves through its own `.travel` asset and flat packed
pages. `/spritesheets/Magic2/Attack5.png` remains the logical casting resource;
its selected file is `/media/smallscale/modular/Magic2/Attack5.png`.

Likewise Sleep's impact selects the new bank while its asleep sustain layers keep
their independent condition lifetime under `vfx/conditions/`. Wall formation,
hold, destruction/removal and ground-fire/Web aliases resolve through existing
world owners; directory grouping does not change semantics. Ice Knife's
`requested_burst_asset` is an explicit authoring amendment: its burst is enabled
at the client impact owner while retaining travel. Do not broadly enable
disabled layers merely because matching files were copied.

The preparation checks confirm selected references resolve to installed resources
and no retired XYZ storage is selected. Preserve the verified recipe timing,
directions and independent lifetimes while integrating the complete release.
Then use that release in the common
play/Studio machinery. No library recopy, startup scan, new registry, SDK
regeneration for ordinary authoring changes or repeated validation loop is needed.

### 5.2 Existing source schema: retain, do not repeat the migration

Current source inspection confirms that `PresentationCatalogExport` already contains the full cold catalog, assets, world, environment, item appearance/material/visuals/palettes, UI resources/presentation/choices/skin/fonts and byte planes. `catalog_documents`, `export_catalog` and `catalog_dependencies` are existing functions in `game_obsolete/presentation_export.py`; they establish the original source shape and initial-seed path. Ongoing client assembly belongs to `NDClient/tools/build_authoring.py` over tracked client JSON. Its catalog/world/assets/environment, item/palette and UI sections are already assembled. Connect their release envelope/defaults, indexed dependencies and application loading; do not regenerate client authoring from the engine or add a second producer.

`ProjectileFrame.rows` already accepts a positive integer; `AuthoredProjectileAsset.kind` has already been removed; `sheet` is already optional; `distinct_source_rows` already checks declared unique row coverage. `ImageResourceSource.geometry: MediaGeometry | None` also already exists. These source changes survived the deleted client. Preserve them, their IDs and current source revisions. No second remove-kind/relax-rows migration is required.

Keep the existing selected-media storage selectors: grid sheet, layer pattern, `pages`, `parts` and `partsByFacing`. The old XYZ `surfaceFrames` records remain historical engine-source descriptions and are replaced in the NDClient selection. Do not create a duplicate asset class hierarchy or second catalog. The new delivery's binding variants are already translated through the paired media owners in §5.1.1. Implement their consumers; do not repeat that translation or add duplicate schemas. Role comes from the consuming binding. A phase without `sheet` must resolve completely through registered storage; do not invent placeholder sheets. Direction/camera basis, counts/rates/time maps, dimensions/crop/pivot and companion calibration remain explicit. Retired XYZ/owner packets remain in their original archives, outside the NDClient migration.

The replacement/relocation import in §5.1.1 is complete. Remaining work is connecting the full existing release sections, their dependencies and client loading. Keep one client assembly path over tracked authoring and use its file/JSON-pointer index for inspection. The prepared artwork is reused. No second engine-side client release builder, reconstructed inheritance map, artwork checksum processing or library copy is required.

Use the prepared client media/geometry fields and section schemas, including defaults. Generate authored TS types from those schemas; ordinary installs and parameter edits do not generate types. The archived `game_obsolete/export_schema.py` is historical evidence, not an executable dependency or a schema repair task. Current initialization/operation types come from the delivered SDK.

### 5.3 Full materials on isolated layers

The authoring connection is implemented: `RigLayer.material` and
`StudioActorLayer.material` optionally carry the existing `ConditionBodyRamp`
record. Reuse its finite material operators for hand, Magic and Effect masks;
do not add another hand-material schema or repeat this owner extension. No new
artistic treatment was automatically assigned. An explicit `material` supplies
the full operation instead of the legacy palette/tint operation on that layer;
`None` preserves the existing authored palette, automatic spell-colour resolution
and tint path. Visibility, opacity, coverage, blend and clocks keep their existing
owners. Shader consumption remains runtime implementation.

Retain the resolved spell/variant palette, explicit overrides, source mask, donor
texture, noise phase, alpha and authored blend. Existing accepted palette swaps
remain valid. Material texture transfer is not multiplication tint and does not
recolour the already-accepted external Godot effect without an authored instruction.

### 5.4 Complete export, dependency closure and consumers

The existing Python passive owners and `PresentationCatalogExport` define the
shape; NDClient `authoring/` owns adopted client values. `game_obsolete/presentation_export.py`
supplied the initial effective seed. `tools/build_authoring.py` is the current
client assembly entry, already producing catalog/world/assets/environment, the
four item/palette sections and five UI sections without engine imports.
The current source-derived section schemas are in `authoring/schemas/*.schema.json`;
use these for authored TS declarations, separately from SDK-owned wire types.
The remaining envelope follows `game_obsolete/presentation_export.py`: schema version 2,
milliseconds, cells, five feet per elevation step and the existing default-empty
`byte_planes` field. These are existing source values, not a new release schema.
Complete release indexing/dependencies and application loading; do not add a competing exporter or
narrow scene-only format. Separately addressable sections avoid parsing all
metadata at startup without creating another editable model.

| Current boundary | Remaining action in the next integration chunk |
|---|---|
| `catalog`, `world`, `assets` | Already tracked and assembled. Load with schema defaults and existing IDs; do not re-import. Keep shared world mappings single-owned. |
| `environment` | Selected `EnvironmentDocument` is assembled from `authoring/environment/index.json` and family/state files, retaining the original 1,030 bank/pose/mask paths and adding the adopted companion/library sources in §6.1. The six-door/timber physical contacts, camera registration, effective mounts, compatible members and fractional supports are now connected at their typed owners. Existing clocks, depth and attachment states are preserved. The 60 supplemental records are tracked under `source-records/`, linked from the six relevant doors and three relevant props through optional `authoring_record`. These inspection records retain source IDs, installed-media addresses and source qualifications; they are not runtime geometry inputs. Shared rendering consumers remain to implement. |
| `item_appearances`, `item_materials`, `item_visuals`, `source_palettes` | Adopted and assembled through `authoring/items/index.json`: 100 hand and 404 ground selections, nine material recipes, 85 categories/318 variants and 118 palettes. Existing typed-owner values, factory/slot associations, ground registration and unsupported classifications are preserved; the ledger contributes its inventory, not its import wrapper. Equipment references use existing root-rig clips and `/media/smallscale/modular/` resources. Existing attached effects remain single-owned in the catalog. Shared runtime consumption remains to implement. |
| `ui_resources`, `ui_presentation`, `ui_choices`, `ui_skin`, `ui_fonts` | Adopted in tracked `authoring/ui/index.json`, using existing owners and delivered smooth48/192×256 assignments; all 103 choice mappings retained. Skin is empty because no legacy chrome was selected. No full native content manifest. Shared runtime UI consumption remains pending. |
| `byte_planes` and resource dependencies | Include references where existing representations use them; paired banks already declare their files/encoding/calibration and are not duplicated here as a second bank registry. |

Once adopted, these client files are tracked and edited in NDClient. The original
engine documents, Factory exports and `.runtime/` snapshots remain reference
inputs; none silently overwrites current client edits. The full release uses
these same source values rather than serializing them repeatedly between client
layers.

| Canonical source/type | Complete release section and dependency roots | Production consumer / Studio responsibility |
|---|---|---|
| `AnimationData` / existing `PresentationCatalogExport` | All 55 fields with the ledger's executable/tool-only dispositions; every selected recipe, context, material and binding, not a six-field Pick | Shared compiler/sampler and corresponding inspectors; tool-only source strings stay out of executable data |
| `BodyRig`, `BodyClip`, rig tables and exact creature bindings | All 44 rigs; every declared clip, category, facing, body/shadow/accent/gear/Magic/Effect reference, pose context and socket | One modular/fixed rig path; rig inspector and action timeline. An Idle/Run resource set cannot satisfy declarations for attacks/death/flight |
| `AssetDocument` and `WorldBindingsSource` | All resource/animation/water inputs and all 24 current world fields, including cliffs, stairs, faces, constructions, spatial media and deposits | Shared support/world/material consumers and world inspector. Do not also serialize derived `AssetCatalog` dictionaries as editable sources |
| `EnvironmentDocument` | Current selected non-Desert copy: 324 banks, 11 door, 12 trap, 28 wreck, 113 prop and two wall-destruction mappings; open/closed/engaged/damage/destruction paths and all companions. Desert remains deferred. | World transition compilation, physical drawing, picking/light geometry and registration/transition inspectors |
| Item visual ledger, `ItemAppearanceDocument`, source palettes and existing material/attachment owners | Canonical visual categories/variants, 100 hand and 404 ground appearance rows, item material treatments, attached effects and their dependencies | Shared owned-item appearance while equipped/dropped/looted; item/material inspector. Never reconstruct these from the old client’s generated output |
| Current projectile/media registrations and storage | Current selected 1,054 definitions / 1,051 storage records and 193 paired banks, including condition/action/particle/blood/construction/lifecycle dependencies | Finite media/material operators. The word `projectile` in an old source type does not restrict the package to flying sprites |
| `ui_media.json`, `UIPresentationDocument`, `ChoiceRecord`, selected skin/font registrations and current icon handoff | Exact icon/portrait roles, choices and selected UI resources; 620 icon-key replacements backed by 594 selected smooth48 images and 103 choice bindings | Shared UI binding lookup; portrait/icon preview and binding inspector. Exclude the complete native `UIContentManifest`; no knowledge gained from an art key |
| Tracked client documents and supplied source provenance | Canonical file/JSON pointer from the existing index; retain supplied historical provenance. Packing metadata is derived/read-only | Read-only source/track inspection and manual canonical-source reload. Public release cannot expose filesystem paths or a browser-supplied write path |

Counts are the pinned planning inventory, with aliases and shared resources; they
are not unique files. New source revisions update that same inventory once, rather
than generating a rival list. Authoring types come from these existing owners.
The prepared client schemas already describe these records. No Python import
DAG refactor, type extraction or old image-loader port is needed.

The ordinary client assembly has a finite sequence:

1. Read the tracked selected sections and their references. Apply source-schema
   defaults and preserve required discriminants/nullability; omission of a
   default is not a new behavior or permission to remove a union tag.
2. Follow registered clips, phases and companions, including paired selections
   and `paired_banks`. Use their installed `/media/` URLs. Raw Factory manifests,
   old `surfaceFrames`, source `.runtime/` receipts and vendor archives are not
   runtime or ordinary-build inputs.
3. Generate the section index/resource descriptors needed by the loader from
   those same references: format, dimensions, sampling and coupled dependencies.
   Resolve unknown references with a file/field diagnostic. Do not create a new
   handwritten registration list or regenerate types for parameter edits.
4. Reuse installed artwork unchanged. Intentional future asset delivery/packing
   is a separate tool operation justified by a new source or measured problem;
   it is not part of launch or every metadata assembly.
5. Publish prepared metadata as one selected release and let the common runtime
   fetch current/upcoming dependencies. Retain the old active release until a
   requested replacement is ready. Shared media is not copied per release/case.

**Metadata follows demand too.** The 10 October intake measurement, before the
assembly amendment, recorded 278,204,654 bytes of environment JSON and 66,888,190
bytes of media JSON (historical source sizes, not transfer or memory budgets).
Loading one giant environment/catalog section
would defeat the startup policy even without decoding a texture. Preserve the
existing indexed bank, family, rig, recipe and resource records as separately
addressable generated records where needed. The small release index locates those
existing IDs and their dependency references; it does not inline every frame or
library sample. Load/admit the current and upcoming scene's metadata closure in
the worker before compilation, and load additional inspection records on demand.
Use the existing member types and defaults, not handwritten partial wire models
or another editable catalog. Whole-catalog enumeration remains an offline assembly
operation. `build_authoring.py --output` is a preparation artifact, not the browser
bootstrap payload. Complete installed coverage does not require every unused
library family to be fetched, parsed, validated or transferred at startup.

A missing selected dependency prevents claiming its capability complete, not work
on unrelated supported content. Coverage records the exact source/capability;
no selected identity is removed to hide a gap. Installed vendor artwork without
implemented bindings does not acquire invented gameplay assignments.

The existing coverage inventory gains status/evidence columns for source mapping,
resolved dependencies, copied release, runtime consumer and read-only Studio inspection. This is
a build/review report, never a runtime registry or hand-maintained duplicate of the
asset catalog. A scene-only installer cannot close N0. N3 cannot close merely because all binaries were copied; actual rendering and read-only source/track inspection remain required. N5 requires the full behavior/UI/Studio results.

The complete export uses the existing `PresentationCatalogExport` owner;
it does not introduce `SceneRelease`. Its existing sections use typed references to
existing `AssetDocument`, `WorldBindingsSource`, `EnvironmentDocument`, item
appearance/palette/material/attachment documents, and the passive UI presentation,
choice, skin and font declarations listed above. Use the prepared client UI section schemas; do not move Python declarations,
import Pygame into the assembler or copy the native `UIContentManifest` into
public artwork metadata.

Keep the existing exported release/catalog revision. Resource records carry the
existing resource ID, readable relative path, byte length and dimensions/format.
Supplied historical provenance is tool-only; current editable locations come from the client file/JSON-pointer index;
the runtime manifest never exposes local filesystem paths. Packing outputs derived
parts in this same export. The client assembly enumerates the whole selected catalog,
with no scene/creature selector that reduces the coverage denominator. Generate
authored types only when their owner schema changes, not on ordinary asset installs
or parameter edits. During implementation, available dependency closures can run
through this same catalog, loader and production consumers while other families
are being connected. No second partial-release format or demo renderer is needed.
Final delivery requires complete installation and supported consumers; partial
availability is progress, never a completion claim.

### 5.5 Full AnimationData field disposition

The counts in the selected-content index describe effective identities, including
aliases; they are not independent executable spells. Actual nested fields/types
are recorded in the source inventory. Each source-authored field must survive a manual client-JSON edit, assembly and explicit reload, including untouched fields. The current edit destination is the file referenced by `authoring/catalog-index.json`; source-family names below explain origin, not an instruction to edit Pygame. In the table, "Edit" identifies a manually editable canonical value, not a required browser editor or save service.

| Field | Canonical source disposition / read-only inspection | Source family / production destination |
|---|---|---|
| interruptions | Edit reaction/cancel timing and media | interruptions.json; causal compiler + R08/R17/R20 |
| devices | Edit registered device presentation | spell_devices.json; R03/R08 |
| device_wrecks | Edit wreck selection/registration | device-art registrations; R03 |
| drafts | Edit complete spell/effect recipes | selected spell-studio-drafts.json; R04/R06/R08–R20 |
| attack_recipes | Edit attack selection/media/contacts | attack-profiles.json; R04–R08/R17 |
| shove_recipes | Edit attempt/displacement presentation | action recipes; R16/R17 |
| body_action_recipes | Edit ordinary gesture/layers/timing | action recipes; R04/R17 |
| body_action_bindings | Edit exact content-to-recipe binding | selected action bindings; compiler |
| condition_recipes | Edit pose/body/marker/media/lifecycle | condition-recipes/overrides; R04/R14 |
| condition_media | Registration inspector | condition-media.json; R07/R14 |
| projectile_assets | Registration/phase inspector, source provenance read-only | projectile-assets.json; R07–R09 |
| projectile_storage | Edit selected bank/phase windows, directions, components and coalescing; inspect derived packed regions | `authoring/media/storage/`; R07–R12 |
| paired_banks | Inspect/edit delivered clock, registration, planes and material semantics; keep measured calibration tied to its source pixels | `authoring/media/banks/`; R07/R09/R10/R11 |
| media_root | Tool-local read-only; replaced by release URL base in client | export/manifest |
| rig | Edit root rig tables through source rig inspector | root rig source; R04 |
| resources | Existing-ID-to-installed-URL mapping; edit only for intentional resource changes | `authoring/catalog/resources.json`; R07 |
| root_rig | Edit validated default rig reference | root bindings; R04 |
| rigs | Edit clip/pose/socket/slot registration | rigs/*.json; R04/R05 |
| creature_rigs | Edit exact creature-to-rig binding | creature rig registrations; R04 |
| sheet_components | Source selection/composition method and registered body/shadow/accent inputs; availability is not activation | `authoring/characters/sheet-components.json`; R04/R05/R06, physical coverage and resource closure |
| damage_context | Edit reaction/body/flash/feedback/media | actionContextPresentation; R17 |
| healing_context | Edit healing presentation | actionContextPresentation; R17 |
| death_save_context | Edit actual result feedback | actionContextPresentation; R17 |
| life_state_context | Edit dying/stable/recovery poses | life-state-poses/context; R04/R17 |
| death_context | Edit death/remains/disintegration presentation | actionContextPresentation; R04/R17 |
| equipment_context | Edit body/media/visual commit boundary | actionContextPresentation; R05 |
| movement_context | Edit gait/flight/jump/landing tracks | movement/context source; R04/R16 |
| movement_reaction_context | Edit reaction holds and release behavior | action context; R16/R20 |
| forced_movement_context | Edit displacement/landing feedback | action context; R16/R17 |
| forced_movement_profile | Edit presentation curve/facing/recovery | action context; R16 |
| shove_feedback | Edit explicit native outcome feedback | action context; R17 |
| number_style | Edit readable floating-number style | feedback context; R17 |
| badge_style | Edit status/feedback style | feedback context; R17 |
| dart_style | Edit supported geometric projectile style | existing source context; R08, only selected consumers |
| bolt_style | Edit supported geometric projectile style | existing source context; R08, only selected consumers |
| vfx_source_hues | Inspect source-conversion metadata; not automatic tint fallback | conversion sources; explicit palette policy R06 |
| context_source_json | Read-only source/provenance; excluded from executable bundle | exporter |
| world_animations | Edit transitions/frame ranges/state mappings | world bindings/animation source; R02/R03 |
| spatial_media | Edit phases/geometry/contact/removal commits | world/bundle bindings; R09/R12/R19 |
| action_media_assets | Registration/particle source inspector | action-media assets; R07/R13 |
| body_release_media | Edit releases attached to actual body events | movement/residue media; R13/R18 |
| relocation_actions | Edit explicit presentation alias classification | source action bindings; R16 |
| portals | Edit endpoint art/timing/registration | portal/dimension-door bindings; R16 |
| blood_responses | Edit actual response-to-media selection | authored blood source; R17/R18 |
| action_playback_rates | Edit explicit body rates; preview source vs effective | movement-media/action source; R04/R20 |
| action_deliveries | Edit reference to owned draft, not copied draft | bundle bindings; compiler |
| movement_reference_speed_feet | Edit animation reference only; never native speed | movement-media/context; R16 |
| deposit_media | Edit footprint/reveal/material tracks | world bindings; R18 |
| concentration_media | Edit retained spatial manifestation | world/bundle bindings; R15 |
| construction_media | Edit material/phases/sections/commit offsets | construction bindings; R12 |
| body_materials | Edit manifestation material | summon/body source; R06/R17 |
| entity_lifecycle_media | Edit summon/departure/hostility visual phases | summon lifecycle source; R17 |
| item_attachments | Edit item-owned attached media | item visual source; R05/R15 |
| action_materials | Edit finite body/hand/recipient material tracks | authored action material source; R06 |
| action_intakes | Edit selected intake/pull presentation | action-media source; R13 |

Current client selections include 149 spell/effect draft keys, five attack
recipes, 85 body action recipes, 160 condition recipes, 44 rigs, 1,054 media
definitions, 1,051 storage records and 193 paired banks. They may share pictures
or behavior; older engine counts are historical source evidence. The selected-content JSON
lists every key; no requirement to create 1,112 new shaders follows from this.

### 5.6 Full world/environment field disposition

`AssetCatalog` is another current input: merely porting AnimationData would omit
world art/materials. Its 15 fields have the following disposition:

| Field | Disposition |
|---|---|
| world_source | Edit typed WorldBindingsSource below |
| resources | Inspect derived AssetDocument resource registrations |
| bindings | Derived view of world_source; never a second editable copy |
| flame_frames, flame_fps | Edit source torch animation registration/rate |
| water | Edit source water material parameters; GPU R18 |
| props | Derived from world_source.props; edit that source |
| spatial_effects | Derived from matching world-source field |
| spatial_tethers | Derived tether registration inside spatial_effects |
| spatial_residue_overlays | Edit source spatial residue bindings |
| residue_particles | Edit source emitter/media parameters |
| residue_ground | Edit source residue-to-ground media mappings |
| residue_surfaces | Edit source receiving-surface material parameters |
| residue_wall_faces | Edit source wall-face registration/projection |
| liquid_surfaces | Edit existing liquid material parameters; no new chemistry |

WorldBindingsSource fields: schema_version is read-only version metadata. `terrain`,
`terrain_cliff`, `terrain_stairs`, `stone_wall_straight`, `stone_wall_corner`,
`wood_wall_straight`, `wood_wall_corner`, `stone_door_frame`, `wood_door_closed`,
`wood_door_open`, `props`, `treatments`, `spatial_effects`, `residue_wall_faces`,
`residue_particles`, `residue_ground`, `residue_surfaces`, `liquid_surfaces`,
`spatial_media`, `concentration_media`, `construction_media`, `deposit_media`, `lighting` are
source-editable structured references/parameters. Current source has 24 fields including `lighting`; the historical 23-field census predates it. `WorldLightingPolicy` already owns `edgeHalfWidthCells`, `treatmentSpace`, `baseResponse`, `directCeilingLinear` and `directFalloff`; edit these existing fields rather than inventing another light policy. Where AnimationData consumes
one of them it is the same source document and edit, not an additional owner.

AssetDocument fields: schema_version is version metadata; resources and animations
use the registration inspector; water uses the world material inspector. Importing
new binary artwork remains the existing explicit private pipeline. Manual source edits and export
do not overwrite original source images or embed binary media in JSON.

`EnvironmentDocument` (`environment_art.json`) is independently exported too:
version is read-only; banks, doors, traps, wrecks and props have registration and
transition inspectors. Bank crop/pivot/rows/frame-count/uneven-sample-times/depth
planes, state/release frames, door pose offsets, prop destruction variants,
selection/aperture masks and passage points must survive manual source changes, export and reload. Packed
addresses are derived; authored geometry/registration is editable with validation.
`WaterSource` in AssetDocument is the canonical material input; do not recover its
values from opaque runtime dictionaries. No second environment source is generated
from the old NeuroClient world store.

### 5.7 UI data versus native content

`ui_media.json` and `ui_presentation.json` supply the existing typed UI source
shapes. **Adoption is complete (9 October)** in client `authoring/ui/index.json`;
edit that tracked copy, not Pygame's source JSON. It connects 620 icon keys to
594 smooth48 images, 43 delivered creature portrait assignments, 618 selectable
free portraits and five documented new premade defaults. All 462 currently bound
native icon definitions resolve through the selected resource map. It preserves
48 direct-feature records, 374 direct-item records, eight common selections and
all 103 delivered choice icons. No native descriptor catalog is duplicated.
`ImageResourceSource`, `UIPresentationDocument`, `ChoiceRecord`, `SkinSource` and
the existing font map remain their passive owners. The assembler reads them
without engine imports, source snapshots or copy receipts.

The existing ChoiceRecord now also carries optional native `field` and
`field_value`, nullable `facet` and integer-or-string values/requirements, retaining
the 26 configuration-only choices omitted by the old 77-row Pygame UI copy.
Facet prerequisites retain facet names (wall `form`); native names are supplied
by the same owner's field/facet mappings (`wall_form`). Field-only prerequisites
retain native names and integer values (Bestow Curse). Spirit Guardians keeps
the delivered lowercase facet values and distinct uppercase native enum values.
No availability rules, minimum-slot logic or creature recipes move into this UI
artwork data. Runtime matching/submission must consume server-provided options.
These records do not reinstate unnecessary wall-side controls.

The modular Skeleton Warrior is the sole currently registered creature-rig identity
without a delivered portrait assignment. Common Unarmed still has no dedicated
icon in this bank. Both remain explicit art gaps; no unrelated image is assigned
silently. The five human premade defaults are clearly labelled as newly selected
defaults, not claimed as delivered exact assignments. Details and source locations
are in client `authoring/ui/README.md`. UI resource adoption is complete; shared
UI lookup, widgets, SDK admission and HUD rendering are not implemented.

Do not restore obsolete
Pygame image selection over the new smooth48/192×256 bank. Native content
IDs/names/descriptions/available actions/item statistics and recorded combat-log
math are read-only in visual Studio. It does not become a character/rule editor.
Include `ui_skin.json` resources/insets/state variants, UI choice records and fonts
in the versioned presentation release. Their source metadata can be edited with
validation; gameplay HUD layout is browser view code, not another JSON UI engine. Current Studio inspects these values; edits are manual canonical JSON changes followed by reload.
NeuroClient was more advanced but incomplete: the human did not approve wholesale
reuse. Evaluate components against current requirements as specified in this document. Revised icons/portraits are supplied separately; stable bindings and release
revisions admit those assets without making asset replacement the whole UI task.
This does not reinstate rejected bulky chrome: only selected accepted resources
are used by the minimal UI. The pygame skin drawing function is not ported into
the browser views automatically.

Native descriptor admission uses the delivered SDK: observed descriptors arrive in
InitializationResponse/PlayerOperation `content_additions` and are folded before
dependent lineages; the existing metadata endpoint supplies public descriptors.
Do not install the complete private UIContentManifest from a presentation release.
Static versioned artwork/binding metadata is a separate input, never authority to
reveal native content or an unseen entity. Existing item visual ledgers outside game_obsolete/data (notably
`content_data/ledgers/neuroclient_authored_item_visuals.json`) supply the initial
item-section values; preserve that provenance when adopting tracked client data. Do not silently
substitute the old NeuroClient generated equipment/palette files.

## 6. Production renderer: shared data, geometry, material and composition

### Source ownership and the boundary of this work

The data path is:

`native subjective facts + existing authored presentation data → shared pure presentation sampling → passive visible draws/receivers → Pixi resources and GPU execution`.

Play and Studio use this same path. Neither supplies an alternative asset placement algorithm, scene renderer, animation clock or spell-name switch. Native code retains traversal, collision, spell propagation, light/perception authority and action legality. GPU geometry controls visual composition and cosmetic lighting; it does not become a second game engine.

The source references are:

- `game_obsolete/projection.py`, `game_obsolete/environment_draw.py`, `game_obsolete/fixture_depth.py`, `game_obsolete/scene_actors.py`, the motion/contact samplers, `game_obsolete/asset_types.py`, `game_obsolete/animation_types.py`, and their authored JSON owners.
- NeuroClient's existing projection, camera, grid, modular/fixed appearance and interaction functions. Its `render/worldDepth.ts` contains contact-depth bands and stable ties, not a complete solution for intersecting elevated geometry; do not copy its limitations as a new universal painter algorithm.
- NeuroMapEditor's `src/model/{types,lattice}.ts`, `src/render/{orderPhaseOne,spritePresentation,alphaPicking}.ts` and `docs/PHASE_ONE_IMPLEMENTATION_RECORD.md`. Preserve its distinction between Z-grid identity, placement calibration and composition policy. Do not reinterpret composition order as physical elevation.
- `agent_docs/PIXI_WALL_DOOR_ELEVATION_POSITIONING_HANDOFF_2026-10-08.md`, `NDCLIENT_ENVIRONMENT_ASSET_RECOVERY_HANDOFF_2026-10-08.md`, the actual `environment-production-audit` registrations and the selected `arena-study` delivery.
- `agent_docs/audits/ndclient-plan-20261008/FIREBALL_PROOF.md` and the v4 Fireball handoff. These certify bounded prototype observations, not the full renderer.

Current source already defines `MediaGeometry` (`plane`, `mesh`, `ellipsoid`, `ray_depth`), `ReceivingMaterial`, `VisualEmitter`, `PairedMediaSelection`, `PairedFrameBank`, `CaptureMatrices`, source/rest ownership planes and `ImageResourceSource.geometry`. The older foundation document says that last field must be added; that is stale. Consume their prepared client-schema equivalents; do not extend the archived Python owners. Do not introduce a second asset registry, transformation language, material hierarchy, entity renderer class tree, renderer-specific world snapshot or handwritten copy of generated types.

This is a new GPU renderer, not a request to stop at Python/NeuroClient parity. Source registration, semantics, temporal behavior and existing successful controls are recovered. Canonical sampled depth/normals, material transfer, receiving/emitting light and physical cross-surface composition are new functionality. Whenever an asset supplies depth/normal channels, those channels take precedence and are actually consumed. A convenient constant cutout or fitted ellipsoid must never replace available measured channels. The fallbacks below exist only for source artwork that genuinely lacks that data and state their approximation explicitly.

### 6.1 Environment companion adoption and shared lighting — 10 October decision

**Companion adoption and assembly-authoring connection implemented, 10 October.**
42,805 required companion files (1114.43 MiB) were copied into the existing readable
family folders. Tracked authoring includes all 324 selected banks (24,632 pose/frame
associations), static resources, device/hatch layers and 725 library families
(67,272 explicit samples). All seven delivered assembly closures are connected to
typed bank/door/library data; source records remain inspection provenance.

The companion source schema, effective receipt normalization and required copies
are installed; the ordinary assembler consumes those tracked values, including
the completed assembly amendment recorded below. Renderer/light
consumption and live visual acceptance remain future implementation. The
corrected supplier selection is recorded in
`ENVIRONMENT_GEOMETRY_INTAKE_RESPONSE_2026-10-10.md`; the client local intake report
is `.runtime/environment-geometry/adoption.json`. Do not rerun this preparation
or interpret the supplier receipts at application runtime.

#### Keep the artwork; enrich its existing owners

| Input already in NDClient | Decision |
|---|---|
| Selected colour sheets, source pixels, source rectangles, pivots, scales, animation frames/clocks | Keep. This delivery supplies companions for these exact sources, not replacement beauty artwork. No recopy, rescale, repack or FPS conversion is required. |
| Existing resource/bank/item IDs and state/animation selections | Keep. Attach companions to the same static image, pose/frame, device pitch/camera/aim/frame or hatch layer. Library artwork does not acquire a new gameplay assignment. |
| Adjacency, parent/insert/leaf relationships, stair contacts, support/elevation and native map mechanics | Preserve the existing owners and consume the delivered physical-mount/assembly corrections now installed at their client metadata records. A raw image pivot and physical floor mount are different quantities. |
| New depth/normal packets, support/component/shadow masks and calibrated meshes | Already copied into readable environment family folders, with original filenames within `geometry/` where needed. Consume their existing associations; no repeat copy. |
| Active calibration and layer-role metadata | Already normalized into tracked client authoring at the existing owners, including corrected active calibrations. Superseded records remain provenance, not competing runtime choices. |
| Old valid RG16LE environment contact depth | Retain its decoder/registration wherever selected; attach the delivered separate normals. New RG16BE packets do not retroactively change old byte meanings. |
| Export proofs, raw XYZ arrays, source scenes, alternative enlarged packets and validation dumps | Leave at source unless a specifically selected runtime representation actually requires a file. Do not recursively copy the delivery or both native and enlarged copies of the same packet. |

Examples: bed colour remains its 384×384 cells while its geometry samples the
delivered native 192×192 grid. Crate destruction keeps its existing 26 colour
frames; the effective geometry uses its corrected frame-0 receipt and animation
frames 1–25. D6 keeps its colour/aperture, adding its ray packet and actual arch
receiving mesh. The six door physical-mount closures and fractional timber rise
update their named assembly data, without inventing generic offsets or changing
unrelated G17 stairs. Pygame JSON and supplier originals remain untouched.

For example, bed companions belong beside `.media/environment/props/bed/` under
`geometry/`; source-original library companions stay with their existing library
family. Calibration belongs in `authoring/`, never hidden in `.media`. Existing
aliases reuse the installed reference. No hashed filenames, content-addressed
store, second library, arbitrary size limit or new deduplication system.

#### What the Fireball proof actually provides

Read source, not just its earlier screenshots:
`.runtime/ndclient-fireball-proof/{shaders.js,renderer.js,scene.js,frames.js}`.

| Actual proof code | Production disposition |
|---|---|
| `effectFragment`: RG16BE depth, BA oct normals, reconstructed surface, received light added to preserved radiance | Recover these small mathematical functions in the existing common renderer paths; use actual authored matrices/sampling and the production material policy. |
| `wallFragment`: intersections with `wallRunBox`, normals calculated from box faces | This never consumed exported environment normal/depth maps. Replace its approximation for delivered assets with their actual registered samples. It is not the new environment shader. |
| `directLight`: Lambert term, range attenuation, light-to-point obstruction | Share the calculation between surfaces and VFX; supply displayed, admitted light/geometry data and the existing world policy. |
| Effect's diagonal `uHostScale` plus `unCamera` | Replace with the full delivered source-to-local and occurrence transforms, and explicit normal transport. Do not assume every asset shares Fireball's capture camera or diagonal metric. |
| 24 boxes, six lights, constant ambient, hard opacity cutoff, fixed depth range and 128 MiB cache | Proof settings only. Do not promote them to production limits, defaults, source metadata or acceptance gates. |
| One-axis reach interval and hardcoded doorway pieces | Fixture-only. Consume existing area outcomes separately from finite apertures and physical camera composition (§6). The demo shortcut is not a general propagation implementation. |

In particular, the proof's hardware depth expression includes `X+Z+H`; the common
production depth convention above/below is `d=X+Z`. Use one production depth
function throughout surfaces, effects and composition; do not mix these formulas
between shader families. The fixture's numeric range is not a world extent.

#### Minimum source shape, without a second binding system

The five companion associations below and the assembly amendment are already
implemented in passive source types. Consume them and generate authored TypeScript
declarations once from the current schemas; do not redo these owner extensions. Parameter or
file-path edits do not regenerate SDKs.

1. **Static images:** retain `ImageResourceSource.geometry` and `geometry_region`
   as their existing active reconstruction association. Existing `geometry_sampling`
   carries the explicit frame-local colour-index→packet-index scale/offset and
   the source pixel convention; geometry rectangles need not equal colour size.
   For the delivered 2× cases the lookup is `floor(colourIndex/2)` and calibration
   uses the resulting native pixel centre. Atlas origins affect texture lookup,
   not physical placement or a second pivot subtraction.
2. **Normals:** use one passive normal registration with source region, encoding,
   sampling and effective `normalToLocal` matrix. It can refer to BA of the same
   packet or to the selected separate normal image. It works beside both existing
   depth encodings; normals cannot be available only inside `RayDepthGeometry`.
   A BA reference does not cause a second file copy/upload. Derive effective
   transport from the receipt's declared basis. Export-time normal transforms
   already baked into bytes remain provenance and are not applied a second time.
3. **Receiving geometry:** preserve an optional `receiving_geometry` plane/mesh
   alongside sampled ray reconstruction where both are supplied, such as D6.
   They serve distinct purposes; do not overwrite one with the other or rasterize
   an aperture into a filled wall. A receiving mesh is not automatically a closed
   solid or a complete arbitrary-direction light blocker.
4. **Roles and coverage:** preserve typed support, shadow/component selection and
   receiver inheritance at the existing image/layer owner. Reuse current source
   RGBA bounds/mask selection mechanics from `game_obsolete/sprite_components.py`; keep
   environment meanings such as solid fragment, ground shadow, dust, cloth and
   surface paint explicit. Neutral selection primitives must remain below their
   consumers in the import DAG, not create an `asset_types`↔`sprite_components`
   circular import. Colour alpha and roles own coverage; packet A is normal data.
5. **Animation/device/portal frames:** reuse these same passive sample/normal/role
   primitives in a frame-companion record attached to the owner's existing axes.
   Keep frame-zero overrides local to that frame. Device pitch, camera quadrant,
   aim row and frame remain independent indices. Portal front and moving overlay
   keep separate companions. Use the selected colour clock to select them together;
   introduce no independent geometry animation timer.

For new ray packets, sampling and calibration supply the same calculation for
walls, props and effects:

```text
sourcePixel = authored pixel-centre mapping for this frame
code = 256*R + G
t = lo + (code-1)*(hi-lo)/65534       # code 0: no surface sample
P_local = sourceToLocal * (pixelToRayOrigin*[u,v,1] + rayDirection*t)
P_world = occurrenceTransform * P_local
N_world = normalize(occurrenceNormalTransform * normalToLocal * decodedNormal)
```

Do not normalize `rayDirection` independently of its depth parameter. Compose
normal transport once, including nonuniform scale and mirrors. Preserve legacy
contact reconstruction for legacy bytes. Unsupported samples classified as
shadow/dust/paint follow their supplied receiver/layer treatment; they do not
vanish because the solid packet has no sample. A material pixel with genuinely
missing required geometry is a named data defect, not permission for arbitrary
silhouette cropping or invented black-pixel geometry.

The original draft `tools/adopt_environment_geometry.py` was replaced during
adoption: the current importer normalizes explicit `receipt_selection.effective`
records. Draft `geometry_delivery` tuples and recursive `source_documents`
assembly were removed; no runtime receipt interpreter is installed. Provenance can remain in source records;
the normal build and renderer read the adopted typed authoring only. That cleanup
is complete; do not implement a second importer or repeat it as a renderer task.

#### Assembly connection — completed bounded pre-phase

**Implemented, 10 October.** The concrete implementation steps, passive field shapes, exact
source inventory, coordinate conversions and completion checks are consolidated in
[the assembly-authoring pre-phase plan](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/NDCLIENT_ASSEMBLY_AUTHORING_PREPHASE_PLAN_2026-10-10.md),
created at the user's request on 10 October. It records the completed data phase
and exact field semantics; its implementation steps are not outstanding work.

The existing six indoor-door closures and library-only timber staircase are now
connected from inspection source records to the existing typed bank/door/library
owners: 30 banks, six door definitions, 5,736 door library samples, 124 timber
samples and seven compatible-member camera registrations. Twelve passive-schema
tests and eleven installed-authoring/projection tests pass; the before/after check
preserved all unrelated fields and owners. Preserve source artwork, raw pivots, scales, clocks and IDs. Distinguish
physical orientation from capture-camera registration and use each frame's own
canvas/calibration. Keep compatible header/partition pairs together; retain
continuous timber tread/landing data without a new native stair assignment.

Completion is normal assembled authoring carrying those values without a supplier
receipt interpreter. No artwork recopy, client renderer or SDK work belongs to
that pre-phase. Shared-renderer placement, layers, depth and lighting acceptance
remain later implementation work; data completion alone does not claim them.

#### One material/light calculation, three different geometric questions

- **Camera ordering:** reconstructed visible samples compete in the shared world
  depth/composition path. Authored support, layer order and same-support treatment
  still apply; depth maps do not replace source placement or map elevation.
- **Receiving illumination:** compute light direction at `P_world`, use the
  decoded/transformed normal, then apply the existing `ReceivingMaterial` and
  `WorldLightingPolicy`. The environment colour is already shaded artwork, not
  guaranteed unlit albedo. Preserve that appearance and use the existing bounded
  relighting treatment; do not invent an albedo/emission decomposition.
  **Human clarification, 10 October:** existing baked shading and shadows are
  acceptable. Removing them and replacing them with simulated shadows is an
  optional future choice, not a prerequisite or task for this migration. Consume
  the already delivered masks/roles correctly; do not start another shadow
  extraction, artwork cleanup or physical-material recovery project.
- **Light obstruction:** test light→receiver segments against currently displayed,
  finite authored blocking faces/apertures and assembly profiles. Per-view visible
  depth alone does not reconstruct unseen sides or certify a solid volume. Use
  the delivered D6 aperture and source-qualified wall/leaf profiles, not a universal
  box or the camera depth texture as an omnidirectional shadow map. Identify a
  genuinely missing blocker representation at its owner; do not silently claim it
  supplied by a visible-surface packet.

Native affected cells/reach and subjective visibility remain separate from all
three. A light shadow never deletes a wedge of Fireball colour. A visible effect
is not cropped to floor visibility diamonds. Source ground shadows are receiving
layers, not solid occluders. Closed/open/broken displayed door state updates its
visual blockers at the same presented time as the art; server-ahead state must
not make its shadow disappear early.

Both environment and Fireball use shared receiving-light functions. Combined
Fireball radiance retains its emission while receiving light across the whole
effect. Its light cast onto neighbours remains the separately authored
`VisualEmitter` identified later in this chapter; bright pixels do not create that
association. Fireball’s accepted proof curve is now authored at its existing impact
storage owner, explicitly requested by the user on 10 October. Preserve it as
described below; do not add a second bank emitter or a global intensity multiplier.
Cosmetic lighting supplements the admitted native baseline and cannot disclose
unknown geometry or change mechanics.

#### Pixi resource path and work sequence

Pinned NDClient is PixiJS 8.22.0. Its
[Texture/TextureSource separation](https://pixijs.com/8.x/guides/components/textures)
allows many frame views over one uploaded sheet. Use the existing shared resource
owner, with colour and geometry as separately registered coupled dependencies.
Decode numeric PNG channels losslessly to bytes in the worker; do not pass them
through a colour-managed/premultiplying canvas. Supplied raw packets use their
declared decoder. [BufferImageSource](https://pixijs.download/v8.22.0/docs/rendering.BufferImageSource.html)
receives explicit format, no-premultiply alpha mode, nearest data sampling and no
averaged mipmaps. Normal/depth bytes never use the colour sampler's filtering.
Keep existing colour filtering and uniform camera zoom; do not fix data sampling
by degrading colour motion or changing the isometric projection.

Registered surfaces use the shared
[Mesh/Shader path](https://pixijs.com/8.x/guides/components/scene-objects/mesh) and
[depth/blend state](https://pixijs.download/v8.22.0/docs/rendering.State.html).
Lighting evaluates in the surface/effect fragment path, not a fullscreen filter
per asset. This does not promise one total pass: opaque/transparent composition
and shared bloom retain their separately justified passes. No CPU full-frame
XYZ/normal reconstruction, recolouring, GPU readback or per-camera texture copies.

The next implementation is deliberately staged within the existing milestones:

1. **Completed input:** the passive companion owners, importer, companion copies
   and source/frame associations are installed. Consume their tracked values;
   do not repeat copying or intake. Assembly placement consumption is addressed
   explicitly below; it must not be inferred from a companion map.
2. **Connect N1/N3 renderer:** load raw channels, sample them on the selected
   colour frame, reconstruct geometry and consume it for shared ordering and
   lighting. Derive finite light-blocking geometry from displayed authored state;
   cache it by its actual consumed changes, not by pan/zoom. Reuse existing
   production functions in Studio; this is not a new isolated preview engine.
3. **Review in the live application:** use the finite cases below, then continue
   the master plan. Record specific failures and fix those; do not launch another
   export/schema/checksum/regeneration campaign after the checks pass.

#### Finite visual acceptance through the production machinery

Use source-compatible assemblies and actual server-recorded transitions, with
Studio exposing the same sampled tracks/data. Authoring-only material inspection
may move a labelled test light without pretending it is a gameplay event.

| Case | What must visibly hold |
|---|---|
| Intact wall/door/prop, four cameras; unlit then lit | Original colour, size, pivot and placement remain stable. Depth/normal debug shows registered surfaces; light turns with world geometry, not the screen. |
| Bed 192→384, darts 128→256 and one retained RG16LE bank with separate normals | Correct native sampling, byte order and matching colour frame; no half-size geometry, coloured normal leakage or alpha-based holes. |
| D6 and compatible door, open/closed | Arch aperture stays open; leaf depth and its light obstruction follow the displayed animation. Matching wall and door receive consistent light from their actual faces/supports. |
| Properly enclosed raised area with its authored stair, a body and a prop | No open cliff ends, altered perspective, chopped feet or buried furniture. Normals/depth supplement the correct layers, contacts and elevation. |
| Crate destruction frame 0→1 and settled end; spike paint or layered hatch | Correct frame provenance, intact→animated registration and preserved ground shadow/non-solid roles. Overlays retain their receiver; no new fake solid. |
| Current Fireball beside those walls | Actual near/far ordering, light received and emitted, aperture obstruction and separately governed native reach. No invented wedges; smoke can receive light after its own emitter fades. |

Measure cold upload and repeated playback/camera movement on these same cases;
fix measured stalls or excess work. Do not impose a new global asset/page/frame
budget. Metadata checks alone close only adoption, never renderer acceptance.

### One coordinate and image-registration contract

Use the existing world basis and quarter-camera rotations. Native ground coordinates have east `+x`, north `+y`. Write the rotated host coordinates as `(X,H,Z)`, where `H` is physical elevation in native steps. The ground rotations are:

```text
q0: (X,Z) = ( x,  y)
q1: (X,Z) = (-y,  x)
q2: (X,Z) = (-x, -y)
q3: (X,Z) = ( y, -x)

u = 64 (X-Z)
v = 32 (X+Z) - 64 H
d = X+Z                         # larger d is nearer the camera
```

Map origin and camera pivot contribute translation. They are not hardcoded to Python's historical 64×64 map center. Pan and uniform zoom are applied once at the common world transform. No independent x/y fit scaling, affine deformation of sprites to fake another view, or per-asset perspective correction is allowed.

At an unzoomed image-space point `(u,v)`, a depth `d` defines the view ray point:

```text
R(u,v,d) = ((d+u/64)/2, (32d-v)/64, (d-u/64)/2)
```

All depth sources convert into this one comparable world coordinate before depth testing. A sprite rectangle's bottom, screen Y, source PNG height, asset ID and composition layer are not replacements for `d`.

For source pixel `s`, placement is the existing registration:

```text
screen(s) = cameraTransform(
    project(ownerContact, ownerBaseHeight)
    + occurrenceOffsetPx
    + occurrenceAffine.translationPx
    + occurrenceAffine.linear * (sourceScale * (s-sourcePivot))
)
```

The source pivot is measured on the original source canvas. An atlas rectangle changes sampling coordinates only. Actual trimming uses its separate source-local trim offset. Apply neither atlas x/y nor an ingestion owner rebase as an additional placement offset. Packed color, depth, normals, face masks, sockets and auxiliary ownership planes share the same source-frame mapping.

The physical boundary has an incident pair and a canonical native owner. The image has its selected source owner and registration. A rebase performed when importing the source is not another runtime displacement. For the already corrected Lantern Crypt placement, the entry passage uses `(7,y)E` for `y=5..7`, the entry vault uses `(x,8)N` for `x=4..7`, and the passage/hall `(12,y)W` remains unchanged. These are source corrections for that assembly, not shader constants.

At q0 the physical E/N/W/S faces select e/s/w/n art respectively in the legacy
view convention; quarter-camera rotation advances the selected pose. For doors
without an explicit capture-camera crosswalk, compute the bank pose from the
physical pose and authored `pose_offset`. In `[e,s,w,n]` order:

```text
bankPose = poses[(index(physicalPose) - pose_offset + 4) % 4]
```

An external frame uses the physical pose; the leaf bank uses the bank pose and that pose's pivot. C1/C3's nonzero offset is a required concrete case. For the corrected indoor families, §6.1's explicit capture-camera map replaces the assumed source-view order while preserving that physical-edge relationship. Select colour and all companions together and use the delivered physical contact separately from the raw pivot. Preserve each family's existing internal-versus-external frame choice. A depth ground origin is a depth registration, not another sprite mounting pivot.

### Layers, supports and physical depth are separate

Every derived world contribution retains these distinctions from its existing source owner:

1. Source image/layer identity and stable authored sibling order.
2. Native owner, support contact and currently displayed placement/state.
3. Registered source-to-world transform and selected camera/pose/frame.
4. Surface/depth representation and receiving normal.
5. Semantic composition role, blend law and picking behavior.

The engine currently delivers one `WorldTileState` support per XY, with `elevation_steps`, `surface_kind` and optional slope axis. `WorldObjectPlacement` supplies base/top height, covered support tile identities, footprint and boundary orientation. Ground/flying occupancy is not a stacked-floor identifier. The renderer must draw multiple visual pieces at different heights over the same XY, but this phase does not fabricate independently walkable stacked floors which the current native protocol does not represent. NeuroMapEditor's independent Z-grids remain richer authoring input; a source assembly requiring stacked playable supports is explicitly outside the current engine capability.

An upper floor overhang, stair tread, lower floor, cliff return, door, table, body, shadow and effect can nevertheless share screen pixels and XY. Their physical surfaces participate in the same depth coordinate. No global `all floors first`, `all upper layers last`, or screen-Y-only rule is sufficient.

#### The explicit same-support cutout rule

The previous renderer already had a necessary semantic rule: `game_obsolete/fixture_depth.py:_floor_below_contacts` puts a body's own support covering below that body and its contact shadow. Dropping that rule while adding physically varying floor depth causes exactly the chopped feet, prone sprites and buried prop bases reported in the deleted client. The new implementation preserves the behavior on the GPU, without copying Python's CPU image partitioning or merely adding a depth epsilon.

For an ordinary source sprite without per-pixel geometry, retain its original camera-facing cutout and source contact. Above its own receiving surface it uses its registered contact depth `d_c`. Its authored bottom overhang is represented as a depth-only continuation on that receiving surface. On a horizontal receiving surface of height `H_s`, its depth at a source-covered screen point is:

```text
d_s(u,v) = (v + 64 H_s) / 32
d_visual(u,v) = max(d_c, d_s(u,v))
```

This is a registered 2.5D cutout proxy. It changes neither screen vertices nor UVs, colors, alpha, dimensions, animation frames or sprite silhouette. It says that art extending below the contact line lies on top of its receiving support, rather than physically underneath it. It is not body morphing, an invented character size, an arbitrary depth offset or a new physical collider.

Apply the continuation only to the actor/prop's declared receiving surface and its admitted continuous support patch. A support patch is derived from actual touching source surfaces with compatible support identity/height and no native structural separation; it is not every tile at a matching numeric height. Ground overlays and contact shadows sample those same physical receiving faces directly. A table or chest without a depth companion uses the same explicit supported-cutout policy and its existing corrected pivot/footprint; it does not require a new depth export merely to stand correctly on a floor.

This patch membership selects a depth formula; it never becomes an alpha/discard mask. At a boundary with no own receiver, retain the original cutout sample instead of deleting it. Neighboring coplanar receiver faces have the same `d_s`, so crossing their cell seam cannot create a depth seam. At a true step/wall boundary, the independent physical surface decides what occludes the remaining art. Do not clamp an overhang to a different-height neighboring floor merely because its projected pixel covers that tile.

Keep the meanings of the sampled values explicit: `P_visual=R(u,v,d_visual)` is the cutout's approximate render/light receiving point; support identity/contact selects its native baseline light; its original declared cutout normal controls diffuse response. None of these inferred cutout samples become native occupancy, spell reach, a solid light blocker or a substitute for a provided physical mesh. Registered-depth media instead supplies a genuine registered surface sample to both camera composition and its receiving light. A source-edge raster continuation is likewise kept separate from the finite physical faces used as blockers.

For a sloped receiving plane with equation `n·P+c=0`, solve `n·R(u,v,d_s)+c=0`. Use the receiving continuation only when the contact-cutout point is below that admitted receiving face and the view ray enters its upper half-space. Treads are their authored individual finite faces, not one invented ramp. A registered edge-on/vertical face is not a receiving floor and is handled by the separate source-face rule below. A pixel outside the declared receiving patch keeps its cutout depth; this does not cut away its artwork.

Resolve actual coplanar contributions by semantic ties, not physical depth bias: support top → owned settled ground coating/grid/ground feedback → contact shadow → supported body/prop. Body and equipment then retain the source rig's authored sibling order. A wall/door's frame/leaf and material siblings retain their source assembly order only where their physical depths coincide. Semantic ties never reorder different physical surfaces.

Consequences are specified rather than left to later discovery:

- A body's own flat floor cannot chop off source pixels below its contact line.
- A real upper floor still has `d_upper > d_s` at overlapping pixels and correctly covers the lower supported body. Its underside/edge is drawn only if supplied by the selected assembly. The lower body's support exception does not apply to the upper floor.
- A wall behind the cutout remains behind it; a nearer calibrated wall face remains in front. Door frame, current leaf and aperture retain their different depths.
- Grounded motion samples the receiving surfaces associated with the displayed movement position. Crossing a stair uses the native retained support contacts and authored tread faces. It does not interpolate an arbitrary ground height solely to fit the art.
- Prone, sleeping, dying and dead actors use their authored frame and contact/pivot. The supported-cutout continuation prevents floor clipping without flattening or rotating the source image.
- During free flight/jump, the body uses the displayed world contact/height and its free cutout proxy. It does not acquire a fabricated receiver at its flight height or borrow the floor from the latest server position. A ground shadow remains a separately registered receiver contribution. The body switches back to the actual receiving-support rule at its presented landing event. Interrupted/no-takeoff motion never enters the airborne path.
- Registered depth/mesh companions override the cutout approximation. Their physical points are not clamped onto the floor; invalid source penetration is reported as registration/asset evidence rather than concealed by a generic correction.
- A large prop whose provided geometry spans several receiving supports retains that footprint and those surfaces. A cutout-only prop provides approximate interpenetration behavior, as it did in the reference renderers. Its contact, full silhouette and floor precedence are supported; exact volumetric intersection through its interior is not claimed. No renderer can recover an exact hidden 3D shape from RGBA alone. Use existing registered depth/mesh when that interaction matters, or a source-calibrated finite surface at the existing image owner. Do not invent geometry from the PNG bounding rectangle.

This policy is derived at presentation time from existing support, role and geometry data. It is not an additional asset registry or a new event schema. The old numeric `support_height_steps` alone is insufficient to identify all receiving relationships; the client already has tile/placement/support identities and must preserve them in its passive derived draw record.

#### Finite source faces and edge-on artwork

World physical faces and their raster coverage are related but not identical. Some authored pixels remain visible at a mathematically edge-on face. An instruction to require empty artwork for a parallel ray would discard source data and is removed.

Use a registered depth companion when present. Otherwise use the selected `MeshGeometry` vertices, UVs, face IDs and source polygons. The source polygon identifies which original pixels belong to a face. Inside a nondegenerate source UV triangle, interpolate that triangle's world depth and normal from its calibrated vertices. It remains valid for source art that deliberately gives a physically narrow face visible raster width; the art is not squeezed to zero pixels. For a source-degenerate edge continuation, the existing face polygon bounds the art and the nearest point on the registered source edge gives its clamped endpoint interpolation. The face's own normal and stable sibling order are retained. This is a depth proxy for an authored edge, not an invented finite wall thickness.

For the actual G17 w/n flight, use the supplied lower/middle/upper contact chain as that edge-depth registration: project each source-covered pixel onto the nearest segment in the authored source contact chain, clamp to the segment and interpolate the corresponding world support contact/depth. This chooses the flight's registered center support path when the ideal sloping plane is edge-on, instead of ambiguously choosing one of several collapsed side edges. Its visible narrow source stripe stays intact. With a new sampled depth companion, the source samples replace this approximation automatically.

Use the physical face for actual cosmetic light barriers and world intersections. Its source-edge continuation supplies raster depth/picking only. `residue_wall_faces` is a source-face mapping for deposits, not automatically a complete 3D wall mesh: lift it into a physical plane only where that plane and source calibration are known. This avoids both deleting edge art and pretending a 2D source polygon contains missing 3D information.

### Environment assembly: use the author's actual pieces

The environment selection function consumes native state plus a source-compatible assembly. It emits passive registered pieces; it does not choose arbitrary mutually incompatible stone assets because their names sound similar.

- Recover the `environment-production-audit/audit.json` and `HANDOFF.txt` entries for the selected family, including parent/insert evidence and prefab assembly references.
- For the arena constructor, use `DELIVERY.json` to select the build and preserve its `RULES.md`, placement contract, adjacency, scene and game-data records. These close its layer perimeters and define its receiving cross-sections. They are not a universal adjacency matrix for unrelated art families.
- Preserve `placement-registration-53` and the larger-footprint corrections. The B37/B38 table pivot is `(192,204.5)` in its original source space. That correction is not a reason to add another runtime offset if current source already contains it. B13's documented unresolved classification is not silently changed into a floor decal.
- Use the known compatible D1/D6/A1 examples as such. The unsupported Elegant-door/D1-wall pairing is not made valid by an offset patch.
- For a legacy composite wall corner, replace exactly the two matching perpendicular contributions sharing native owner, base and material with their registered corner image; retain both physical faces and provider identities. Do not also draw the two replaced straight images. Opposite faces and T-junctions are not that corner case.
- The q0 wall corner pose table NE→E, ES→S, SW→W, WN→N is distinct from the cliff corner profile. For the documented cliff source, e means E+S, s means N+E, w means W+N, n means S+W. Each table belongs to its existing family owner, never a shader filename heuristic.
- The actual opening remains an aperture. No full wall is emitted behind a door/window insert whose assembly already contains its frame/opening. Current open/close/break sampling retains leaf and frame registrations.
- Keep animated banks' per-pose frame pivots, ground origins and registered depth. Empty `surface_geometry_by_pose` does not mean an existing useful depth companion should be ignored.
- Do not claim every installed wall has an animation. The legacy directional/D2 sources are static, and seven inspected imported solid siblings have intact-only banks and empty destruction bindings. Match already delivered break art at the original source owner; do not substitute a window-wall bank or generate a duplicate animation system.

#### Floors, retaining faces and stairs

Floor tops and their source edge skirts use their different registered surfaces. Equal-height neighboring tops form a continuous floor; their skirts do not paint across those tops because they now compete at the correct depth. Do not erase all edge art to hide a sorting bug.

Select a retaining face only from a known physical support-height difference or an explicit native boundary. A visibility frontier is not a physical cliff. Use authored `upper_support_offset`, `rise_steps`, side returns and corner profiles. No blanket lower earth floor is generated below each raised tile. A known raised example must close all exposed physical perimeter faces, including stair side returns; a partly disclosed map must not manufacture an enclosure across unknown space.

The installed two-step cliff cannot be stretched into every positive height difference. A repeated assembly is allowed only where its source supports that join. Other rises produce a specific unsupported-profile result tied to the native support and missing family/rise; they do not silently receive fake geometry. That is a content coverage gap, not permission to crash ordinary partial disclosure.

For the installed whole-flight stair, preserve `support_offsets`, lower anchor, orientation and per-pose source contacts. The documented offsets are `[[0,0,0],[-1,0,1],[-2,0,2]]`; the supplied three-contact registration is:

| Pose | Lower | Middle | Upper |
|---|---|---|---|
| e | (160,224) | (96,128) | (32,32) |
| s | (96,224) | (160,128) | (224,32) |
| w | (96,192) | (160,160) | (224,128) |
| n | (160,192) | (96,160) | (32,128) |

Each projected native support must coincide with that source contact after the registered transform. The installed G17 e/s art is a sloping whole-flight raster; its current four registered source corners and three contacts define a usable sloping depth proxy. The w/n art is a narrow edge-on stripe and uses the registered contact-chain continuation above. Keep this explicit representation rather than claiming that its generic face name `slope` provides separately measured tread/riser topology. There is no need to invent or export hypothetical individual steps just to replace the word "slope." Other stair artwork with actual registered treads/risers uses those surfaces, and newly supplied sampled depth takes precedence. Source contacts alone do not establish an unrelated family's width/side faces. The imported study's G16 edge lane and G17 width extension share the same rise; width extension does not mean stacking another rise. Do not emit a full intermediate flat floor over the flight.

The calibration table below records the installed source data and remaining renderer consumers. Consume those prepared values; it does not request another authoring pass.

### Actors, gear, projectiles and condition media

Use the existing modular rig layer order and fixed-sprite authoring. Do not normalize monsters to a shared silhouette height. The effective scale chain is original rig units → source-to-world conversion → explicitly authored appearance scale/width → gameplay size effect → common camera zoom. Apply each exactly once to the body, gear, feet, sockets, hit regions, shadows and attached effects.

Do not add class-dependent cosmetic scales to client authoring or rendering. Preserve delivered gameplay size facts and do not rewrite historical recording appearance on load. Unexpected upstream scale values are reported, not patched in engine producers under this plan. Keep documented animal enlargements, explicit halfling/build appearance scales and authored Enlarge/Reduce. Current source does not prove a separate automatic halfling multiplier, so do not invent one. Retained `persistent.bodyScale` data and the existing transition interval supply a single shared scale sample for application, removal, suppression/resumption and seeking. No spell-name dispatch or duplicate scale table is needed.

Equipment visibility is slot-specific. Hiding a casting main weapon must not hide the offhand unless that slot's policy says so. Each modular channel, mask, material, motion and socket remains an observable Studio track. Fixed goblin/animal/demon sources retain their authored poses and frame registrations; they are not modularized or warped to another camera.

Projectile orientation has two independent operations: choose the authored view/direction bank from the world trajectory and current camera, then align the source's registered projectile axis with the projected tangent when that family permits in-plane alignment. Do not rotate baked world-plane/wall art as if it were a flat dart. Release positions are sampled from the authored animation socket/keypoint on the actual displayed pose/time and then transformed by the same actor scale/camera. Persistent attached media remains attached; released media does not jump to another source socket mid-flight. Missing socket/art registration is a source coverage error, not an invitation to use the actor center.

Condition body material, body pose, ground effect and overhead marker are separate contributions from the existing condition recipe. Any marker playlist only multiplexes the authored overhead marker channel; it must not remove or rotate the condition's other media. Active intervals and source IDs come from retained causes, including suppression, expiry and removal. The GPU does not infer conditions from names or look at latest native state while displaying history.

### Existing body/condition/feedback behavior made explicit by the source scan

These are production capabilities already present in the inspected Pygame sources, not new condition rules or a request to port CPU drawing loops. They use the same passive compiled channels, GPU material/geometry paths, retained native owners and displayed clock as the rest of §6.

- **Condition phase sampling:** retain source `startOffsetMs`, `phaseOffsetMs`, fade-in, sequential versus crossfaded application, sustain start, loop overlap, finite removal-bank crossfade and removal masks. Early removal samples the actual interrupted formation age; it must not finish forming first or restart the source bank. Activity and life-state eligibility apply to all contributing layers. Head-marker deduplication groups the same semantic symbol across owners, chooses a complete declared bank bundle, and leaves every owner's native lifetime intact. Different active symbols cycle deterministically on the displayed clock. Source: `game_obsolete/condition_sampling.py::{sample_condition_media,_loop_samples,select_condition_markers}` and `condition_media_lifetime.py::sample_condition_lifetimes`.
- **Additional body presentations:** consume the actual `liveCopies`, `bodyDistortion`, `bodyRamp`, `frozenPose` and `absenceEcho` operands from current condition recipes. Live copies mirror the presented body/gear and their native owner/count/consumption state, but do not become actors, legal targets or duplicate hit regions. Frozen pose retains the captured presentation frame rather than substituting frame zero. Distortion contours and their ramps are finite authored material/copy tracks; they are not a general camera warp. An absence echo can use its retained witnessed pose and separately admitted return pose only; it cannot reveal an unseen destination or keep a targetable actor alive. Source: `game_obsolete/condition_media_lifetime.py`, `absence_media.py::{absence_poses,absence_draw_commands}`, and `animation_draw.py::{actor_draw_commands,condition_rig_layers}`.
- **Historical body afterimages:** source-defined trail ages sample the same body/gear/condition pose resolver at those earlier displayed times. Retain only the source-required history and its necessary predecessor, not full per-frame worlds or screenshots. Cuts at relocation/portal transitions and loss of visual admission prevent a trail connecting separated positions or exposing an unseen segment. Camera rotation reprojects the same samples rather than accumulating a new screen-space trail. Source: `game_obsolete/body_history.py::{retain_body_head,sample_body_trails}`. This is distinct from projectile/weapon trails and settled blood.
- **Appearance composition and selection:** canonical base appearance plus currently active source-owned overrides determines effective body/gear. Removing one contribution reveals remaining owners rather than restoring a stale snapshot. Respect existing helmet/head visibility, crown exceptions, slot-specific equipment hiding and compatible transient anatomy; an already winged rig does not acquire duplicate generated wings. Shadow, aura, accents, copies and excluded rig categories do not inflate physical actor picking. Preserve those semantics as declared rig/layer policy, not a new per-creature renderer.
- **Independent readable feedback:** damage/heal amounts and outcome badges retain their recorded application identity, contact and authored duration even after the parent action head completes. Their source text/font/color/time remain unchanged by layout. Arrange concurrent text against actual visible actor bounds and other feedback, clamp to the usable viewport, and use a stable least-overlap fallback when crowded; do not shrink text to unreadability or use empty atlas padding as body bounds. Source: `game_obsolete/feedback.py`, `playback_frame.py::sample_playback_frame`, and `animation_draw.py::{actor_screen_bounds,place_feedback_rect,arrange_feedback_commands}`. UI feedback is a screen-space annotation over the presented contact, not physical occlusion geometry or a second combat log.
- **Environment endpoint state:** opening/closing, trap activation and cold/restored state select the actual declared source endpoint or state frame. Closing can sample the authored opening bank in reverse when that source selects it; a newly observed open door is already at its open endpoint. Wreck selection retains the source's open/closed/swing/mechanism/material/outcome and supported-item distinctions instead of a universal broken-prop image. Source: `game_obsolete/environment_animation.py::{door_pose,trap_pose,remnant_bank}` and `environment_art.py`.

Acceptance adds server-recorded early application/removal, two simultaneous owners followed by one removal, consumed illusion copies, frozen pose, visible absence/return, a moving distortion trail crossing a portal or sight boundary, overlapping numeric feedback persisting into the next action, and cold acquisition of an open door/activated trap. Inspect and seek those same recordings in Studio; do not manufacture condition membership or outcomes there.

The following source cases refine the existing renderer families; they do not add parallel effect systems:

- **World-launched projectiles:** `game_obsolete/mechanism_projectile.py::{mechanism_projectile_duration,mechanism_projectile_target,sample_mechanism_projectile}` uses an admitted mechanism's world origin, elevation and pose-dependent muzzle instead of an actor socket. The common trajectory channel supports both source kinds, retained target contacts, camera-independent travel duration, directional bank choice and permitted residual rotation. A hidden muzzle must not produce a revealing launch flash or synthesized caster; separately admitted travel/impact facts may still render.
- **Portal transfer:** `game_obsolete/portal_draw.py::{portal_draw_commands,_doorway_commands,clip_portal_bodies}` supplies entrance/exit front/back media and local aperture clipping during transfer. A body and its decorative copies/trails enter or emerge through that registered aperture; its contact shadow follows the actual transfer phase. Use the shared geometry/material path, not a global tile mask or copied CPU raster loop. One admitted endpoint never becomes a window into an undisclosed remote room.
- **Prop disintegration:** `game_obsolete/object_dust.py::object_dust_commands` retains the object's alpha silhouette, contact and deterministic seed for its retirement effect. Support this through the existing particle/material owner, separately from actor blood and wall debris. At the native destruction commit the retired prop is no longer an interactive/blocking object merely because decorative dust remains. No new CPU XYZ payload or second debris engine is required.
- **Appearance-only updates:** the old NeuroClient's `AnimatedEntity` recomposition/patch/readiness methods show the needed behavior: preserve the active source clip/frame while changing equipment or temporary appearance layers, prepare the complete replacement atomically, and remove only an ending modifier's contribution. Do not restore an old tint/slot snapshot over more recent admitted changes or copy the old class/visibility-closure design.

Exercise these with server-recorded device shots, partially witnessed portal transfers, prop destruction and overlapping appearance changes, including backward seek and camera changes.

### GPU compositor and shader families

Use a common world render group for its transform/lifetime and a separate screen UI. Pixi `RenderLayer`/container order is useful for semantic/UI grouping, but cannot solve intersecting world geometry alone. Physically composited world media uses shared explicit `Mesh` geometry/shaders/state; ordinary `Sprite` is sufficient for UI and already-resolved flat composites. Sharing a compiled shader alone does not make independent custom meshes batched; compatible draws must share buffers/attributes and state deliberately.

The finite shader/path families are:

| Family | Source inputs | Result |
|---|---|---|
| Registered static/animated surface | Source UV/frame, calibrated mesh/plane or depth, masks, normal/material | Floor, stair, wall, prop, frame/leaf and finite construction surface |
| Supported/free cutout | Source layer, contact/support, source registration, rig sibling order | Bodies, gear, cutout props, ordinary flat cast/marker/projectile art |
| Compact volumetric sample | C/T appearance, scalar depth or ellipsoid sample, optional normal/owner plane | Fireball/cloud/dome/burst contributions at comparable physical depth |
| Finite ribbon/mesh | Existing authored path/noise/material parameters, absolute time | Beams, trails, orbits, intake, darkness/plasma/ribbon effects |
| Receiver material/deposit | Receiving face UV, historical contribution fields, material clock | Water, ground conditions, blood, soot, frost, runes and settled residue |
| Analytic particle | Existing release/landing template attributes, absolute time | Blood, bone/vapor/spark particles without per-particle CPU images |
| Shared composition | Physical/visual depth, original blend operator, stable sibling key | Opaque/transparent resolve and optional bloom |
| Highlight/feedback | Same displayed source mask or receiving surface | Silhouette outline, ground/path/AoE feedback and cutaway selection |

These are finite functions over the existing union data, not a new DSL or renderer class per spell. Reuse same sampling/material helpers in the appropriate shader stages.

#### Opaque and transparent ordering

1. Derive the displayed registered contributions and conservative overlap bounds. Use one lexicographic sample order `(physicalDepthCode, semantic/sibling order, stable contributor identity)` in every pass. Physical depth is primary; at equal depth the authored support order puts floor below its shadow and the shadow below the supported body/gear. Identity resolves only remaining ties.
2. Draw truly opaque samples into common world color/depth, retaining the winning sample's tie order alongside its depth (or resolving the same-depth group coherently). Only final opacity exactly one belongs here. Fractional antialiasing, fades, clouds and additive media remain transparent. A bright additive pixel with zero alpha must not disappear merely because alpha is zero.
3. Sort disjoint transparent depth intervals directly. For locally overlapping contributions whose depth order can cross, use local depth peeling with that same full sample order, a separate previous-peel texture and current render target. In the logical larger-depth-is-nearer convention, retain the greatest opaque key and select transparent keys strictly in front of it. Front-to-back peels select the greatest remaining transparent key strictly below the previous peel key. Hardware depth mapping must preserve that logical comparator. Depth-only LESS would drop a valid floor shadow; depth-only LEQUAL would allow that shadow to paint over coplanar body pixels. Neither is sufficient alone. Preserve original normal/add/screen operators in the selected order; use no artificial depth offset to encode semantic ties.
4. Bound a crossing group's work from its actual finite participating primitive/contribution count, with a conservative per-pixel intersection bound. There is no invented global four-layer truncation. Do not synchronously read GPU queries to decide every next peel; use known finite scene data. Optimize bounds and compatible batches if measured cost requires it.
5. Composite the world result and optional bloom, then the independent UI.

Do not sample a texture attached to the framebuffer currently being written; disabling depth writes does not make a feedback loop legal. Depth near/far normalization is shared across participating passes. The world convention has larger `d` nearer; hardware depth mapping converts that once to the chosen comparison convention. Coplanar semantic order is explicit, rather than a collection of arbitrary tiny z offsets.

Opaque and transparent use the same per-fragment source registration, support cutout continuation and physical geometry. A global opaque floor prepass plus an unqualified constant-depth body is specifically forbidden because it reintroduces the reported floor clipping. Cutaway-faded wall color leaves the opaque path and participates as transparent color while its physical blocker representation remains intact.

The pipeline may use several passes. The Fireball proof's small pass count is evidence about that prototype, not a promise that lighting, material evaluation, depth resolution and all scene transparency fit into one pass. Use floating render targets only where the radiance/blend representation requires them, and test the actual WebGL2 attachment/renderability/blend capability used. Do not require unrelated float extensions as a blanket gate.

### Compact media representations and exact sampling

Consume the new replacement VFX exports; do not copy or convert the retired XYZ banks. A pending replacement remains pending instead of acquiring an invented shape or a legacy fallback. Use supplied registered normals or normals from a known calibrated surface; never infer claimed physical normals from beauty-color pixels. Any normal estimate derived from the new sampled geometry must identify its method and limitations in source metadata. Choose from the existing finite geometry types and the new source's actual topology. Packing preserves selected source timing and release/impact markers. General authored spell rates remain their authored rates; the user's explicit 24 FPS exception is the new single-view Fireball, not a blanket conversion of all VFX.

| Existing family | Current chosen representation | What remains source-authored |
|---|---|---|
| Selected Factory Fireball (v4-derived) | Single camera-facing appearance, two depth bands; gzip RGBA8 linear premultiplied radiance/opacity and RG16BE+oct8 geometry packets | 46 frames at 24 FPS, 1.916667 s, original layer meaning and release/impact; accepted demo world-light curve is authored on the impact storage as specified below |
| Fog/Cloudkill/Stinking Cloud/Incendiary Cloud/Darkness/insects/sleep-like soft volumes | Supplied registered depth/normal channels are canonical. Only source art genuinely lacking them may use the explicitly authored ellipsoid fallback and complementary near/far quarter-chord samples | Original components, sampled geometry when supplied, silhouette, color, opacity and timing; ellipsoid interior approximation is never presented as measured data |
| Real front/back Globe/Antimagic/Shatter/Sunburst components | Preserve actual source components and assign their registered near/far surface or compact depth | No relabeling arbitrary original components as interchangeable near/far halves |
| Ice Knife and similar multiple blend parts | Preserve normal/additive source components with compact depth | Blend and chronology; components are not automatically volume bands |
| Directional Burning Hands/Gust/Color Spray/Sunbeam/Sleet and comparable families | Retain directional banks and scalar depth where their shape requires it | Authored viewpoint and directional silhouette |
| Thunderwave | Selected Factory whole-crest paired banks, four cube orientations with authored eight-facing aliases | Delivery explicitly replaces eighteen historical cell/side draws. Preserve native admitted-cell reach and retained contact delays; do not also replay the old components. |
| Walls/rings/constructions | Registered finite source meshes or sculpted depth; rest-piece data for disassembly where needed | Apertures, current state, assembly placement and original material behavior |
| Ground/runes/water/shadows | Receiving planes/meshes and local face UVs | Actual support, original field/material and timeline |
| Flat projectile/cast/condition strips | Source-registered cutout, authored sockets and blend | Original frame/layer rate, axes, masks and contact points |

The Factory packet stores premultiplied radiance `C` (restore `radiance_scale`) and opacity `A`; derive transmittance `T=1-A`, rather than reading alpha as transmittance. Zero-alpha radiance remains valid emission. For C/T premultiplied radiance and transmittance, compositing is `C_out=C_front+T_front*C_back` and `T_out=T_front*T_back`. For splitting one image into two equal-transmittance proxy samples, `T_h=sqrt(T)`, `A_h=1-T_h`, `C_h=C/(1+T_h)`. Unoccluded composition reconstructs the original appearance exactly; moving walls between the samples is an explicit interior approximation. Do not halve alpha/color directly or apply this transformation to already distinct source layers.

For the compact RG16BE ray-depth texture:

```text
code = 256*R + G
code == 0 means no valid sample
t = rangeLow + (code-1)*(rangeHigh-rangeLow)/65534
P_source = pixelRayOrigin(sourcePixel) + t*rayDirection
P_world = registeredSourceToWorld(P_source)
```

BA stores octahedral normal encoding. Transform decoded normals with the inverse transpose of the corresponding registered object/camera transform, including any mirror. Numeric planes use raw nearest samples, no premultiplication, gamma transform, lossy compression or automatically generated averaged mips. Color decoding is declared independently; these planes are not ordinary sRGB sprites.

The older environment RG16LE contact companion instead decodes `R+256*G`, uses its registered depth range and per-pose pixels-per-unit, applies asset scale, then the ground-origin versus mounting-pivot offset exactly once. Convert that registered contact depth into the common `d` coordinate. Do not feed it through the Fireball byte order or assume a depth origin is a mounting offset.

The source exporter emits color/transmittance and depth/normal companions in one declared frame/camera/basis registration, preserving the actual distinct source component/blend layers. Static walls/props can supply the same registered scalar depth/normal contract when exported; they do not require a separate wall-specific shader implementation. Regular calibrated geometry can derive depth/normals without redundant textures. The client reports which supplied channels were loaded and consumed; a type field or copied companion file is not evidence that the renderer used it. No RGB/luminance threshold reconstructs fake depth or normals. Existing source albedo/emission separation is honored when supplied, while combined appearance retains the documented bounded relighting approximation.

For postprocessed glow pixels outside valid source surface depth, retain the glow's own pixel view ray and intersect a tangent continuation from the nearest valid registered sample. Do not copy that neighboring pixel's XYZ directly, because it lies on a different view ray and recreates the misregistered wall cuts. The source supplies/derives the local valid continuation. There is no universal sixteen-source-pixel admission gate; the actual source fit/error is recorded where meaningful.

For fractured/rest-anchored materials, retain the existing source-piece owner ID and per-frame current-to-rest transform. Sample current depth for camera composition, then derive rest coordinates only for the material that requires them. Use `M_rest * inverse(M_current)` for the supplied piece, not the rest position as its current camera depth. The source exporter already has current piece positions; preserve them in the compact source representation rather than adding a runtime rigid-body simulation.

### Effect coverage, camera depth and existing outcomes

An admitted effect samples its authored full appearance and registered geometry,
then composes against the displayed scene in the shared depth space. Per-pixel
wall/door depth determines front/behind; a sprite's screen bounding box or draw
insertion order does not. Open apertures and displayed destruction state use their
actual geometry. This is camera occlusion, not a second propagation simulation.

An explosion's cosmetic pixels may extend over dark/unseen regions. Do not use
visible tiles, absent cells or the complement of received hit cells as an alpha
stencil. This does not disclose hidden actors, items, terrain, lights or targets,
change legal movement, or change which creatures were hit. Full physical blast
stopping/deformation through every obstacle is not promised by this raster effect;
registered scene depth and the supplied appearance remain the rendering inputs.

Consume existing `SpellFact.resolved_area_positions` and `AreaReachFact` stage,
newly-reached positions and destruction prerequisites for causal timing and
received outcomes. Preserve None versus an empty resolved result. Do not infer
negative provider evidence from their absence, rerun propagation, or add a
continuous blocked-region compiler requiring undisclosed information.

Current cancellation and suppression facts control presentation lifetimes. A
canceled action does not continue its canceled track; received suppression,
resumption and expiry retain their actual timing. Only place a specific boundary
impact when existing facts and admitted geometry identify that interception.
Otherwise present the available cancellation outcome without inventing a dome hit,
provider identity or traveling projectile. Globe and Antimagic are not interchangeable
obstacles, and visible dome artwork alone cannot decide mechanical applicability.

### Materials, receiving light and emission

Recover existing finite material operations and their source masks rather than replacing all material work with tint. This includes the already authored maximum-RGB/luminance transfer, bark, wither, fracture wave, energy burn, rising bands, etched burn, flowing film and frost families. Additional entries are ported from the actual source union/formula, not inferred from spell names. The per-fragment order is declared:

`source decode → source palette/material operation → receiving light → authored emission → displayed physical-depth composition → original blend`.

Original alpha/coverage is preserved unless that particular authored operation changes it. Equipment and body have their correct separate owned material modifiers. Shared immutable source pages do not cache another entity's material result. No camera-specific recolored image copies or CPU XYZ/color calculations are introduced.

Native effective light is the admitted baseline. A finite authored `WorldLightingPolicy` supplies linear-space treatment gains, smoothing width and cosmetic direct-light response. Those are artist-tunable rendering values, not invented performance/validation quotas. Convert source color to the declared working space once and premultiply once. Do not mix the old sRGB multiplication constants into a purported linear-light calculation.

For a receiving face, interpolate the native treatment only across admitted physically connected compatible receiving surfaces. Smooth neighboring cell transitions with the selected smoothstep width; use renormalized product weights at compatible corners. A diagonal sample requires both connecting cardinal routes. Do not smooth through a wall, aperture still blocked by a current leaf, magical darkness discontinuity, unknown/memory boundary or incompatible height. Floor light, door light and wall light use their actual corresponding receiving support/face rather than sampling the tile under the top of the image.

Cosmetic disclosed emitters add a bounded response, without introducing undisclosed lights or a second visibility simulator:

```text
I_base = mix(1, smoothedNativeTreatment, baseResponse)
I_direct = sum(
    visible(light, receiver)
    * lightColor * intensity * authoredAttenuation(distance, range)
    * max(dot(receiverNormal, lightDirection), 0)
)
I_receive = I_base + min(I_direct, max(0, directCeiling-I_base))
```

The selected material's diffuse reflectance controls its direct response. The shadow/visibility term tests a light-to-receiver segment against the same current calibrated finite blocking faces and apertures used elsewhere; camera occlusion is a different ray/test. Derive the compact barrier list when its consumed displayed geometry/state changes. Pan/zoom does not rebuild it. Walls joined for a continuous receiving surface do not fill an aperture's shadow geometry.

Geometry supplies normals for known planes/meshes; a second full-size normal texture is unnecessary there. Compact irregular effect depth can carry oct8 normals in BA. A cutout-only body/prop uses its declared billboard surface normal for cosmetic diffuse response, transformed with its camera/source basis; a depth-only bottom continuation does not suddenly turn its material normal into an upward-facing floor normal. The native baseline still comes from its displayed support/contact. This is explicitly flat-surface lighting for art without a normal companion, not a claim of anatomical or carved-surface relief. Existing supplied normals take precedence; absent normals do not trigger mandatory new artwork exports.

The whole combined Fireball can receive light while emitting light. Decode the selected Factory appearance as radiance/opacity with its declared radiance scale, then apply the bounded source-defined diffuse contribution; no old separate smoke system is recovered merely to receive light. Emission is a separate authored timeline curve with position/color/intensity/range keys.

**Fireball emitter adopted, 10 October, at the user's explicit request.** The existing
impact storage `authoring/media/storage/shared.fireball.20ft-ground.smoke.v3.json`
owns the seven keys from the accepted v4 example. Playback times are converted to
milliseconds unchanged: peak 0.44 s, low tail at 1.64375 s, zero at 46/24 s. The
current Factory bank has the same duration, so no retiming or new export is needed.
Positions already include the demo’s source-to-host transform and are occurrence-local
host `[x,height,z]`; radius remains host grid units. Intensity includes the example’s
×4 gain in each key. Apply occurrence placement once, with no repeated source
transform or runtime multiplier. Preserve one light per logical impact, not per
near/far packet. The demo curve is fitted cosmetic authoring, not reconstructed
physical emission or a native gameplay rule. This data association is complete;
the shared renderer still needs to consume the existing `VisualEmitter` field.

The current spell-media inventory had zero such curves before this addition.
Per the user's 10 October decision, test Fireball in the shared renderer first
and author the remaining spell light curves in a later phase. This work does not
hold the asset/authoring pre-phase open. Do not silently
make every glowing sprite illuminate the world, and do not create a separate
emitter system for other spells.
Visible emission in the packets alone does not create this world-light association. The bank's ignition/burst/tail frame ranges are source animation timing, not by themselves an emission-intensity curve. Other illumination may continue lighting smoke after the Fireball's own emitter has faded.

`pixijs-light2d` and the old `pixijs-userland/lights` are design references, not new runtime dependencies or a substitute for this world geometry. A two-dimensional first-hit shadow algorithm does not by itself solve elevated receivers, open arches or native subjective disclosure. The accepted demo proves a narrow material/depth/light path; it does not prove every world light case.

### Blood particles, settled deposits and ground fields

Keep the existing data owners: `WorldParticle`, landing/release templates, blood response, `MaterialDepositSource` and `TileResidueState`. Do not create a new particle simulation or recompute native injury chemistry.

Expand a release template once into batched numeric attributes: source/goal, start/delay, duration, gravity, size/tail/shape and stable identity. The vertex shader samples absolute displayed time. With duration `T`, source `S`, goal `G` and vertical gravity `g`:

```text
V_xy = (G_xy-S_xy)/T
V_h  = (G_h-S_h + 0.5*g*T*T)/T
P_xy(t) = S_xy + V_xy*t
P_h(t)  = S_h + V_h*t - 0.5*g*t*t
```

Use the actually presented injured body's contact, including interrupted movement. Preserve the existing critical-flight styling, non-red/bone/vapor/frozen response and original release law; a longer dramatic flight does not increase deposited native amount. A shared custom mesh supplies world depth and the same particle/deposit sampling functions. Pixi ParticleContainer is optional for simple independent cosmetic sprites; it is not adopted as an extra adapter layer for particles requiring this custom analytic depth/material pipeline.

The source's `particle_schedule`/`landed_fraction` is shared by air motion and deposition so a mark appears when its own particle arrives. Receiving deposits are keyed to actual support/face local UVs. Wall soot stays on the registered wall face; it does not tint an entire provider or use the floor's UVs.

Cache settled coverage per receiving surface/chunk and update only arriving/changed contributions. The cache key does not contain camera quadrant, zoom, current light or the whole world JSON. Keep settled older material separate from the active incremental response so a fresh injury does not restart all old blood's material clock. For the existing kernel, preserve the source's `sqrt(fraction*weight)` footprint evolution, source centers/radii, and `max(0,1-q/1.5)^2` density rather than replacing it with arbitrary circles. Owned deposit media suppresses any duplicate generic deposit drawing.

Receiver fields are a derived cache, never authority. Seeking backward, removal, rollback, scope replacement and eviction rebuild the affected receiver from retained source contribution state; they do not replay every historic injury into every tile. A witness's observed deposition animation and a cold-discovered settled residue are distinct source facts. Water, ice/frost/burning transitions and other ground fields use their existing material state/timing and actual receiving geometry; no new chemistry is introduced.

Chunk shape, gutter and texel density are concrete tunable implementation choices, not human requirements or fixed readiness gates. The earlier 4×4/64-texel suggestions must not become a repacking/validation campaign. Choose a useful source-scale layout, preserve face seams, record actual memory and visual behavior, and continue delivery unless a real failure requires adjustment.

### Picking, grid, highlights and automatic cutaway

Use the same displayed samples for world draw, source alpha hit testing, receiving-surface selection, highlight and visual light inputs. Native SDK facts decide eligibility. Rotating the camera changes projection and source pose, not whether a disclosed door exists.

Floor picking intersects actual admitted receiving surfaces and chooses the visible exposed valid support. Source alpha picking handles props/doors; keep the authored meaningful hit region distinct from decorative canopy overhang or a coarse collision cell. Use existing CPU source masks/compact geometry where available; do not read the entire framebuffer on each mouse move.

Grid, movement path, AoE and impact feedback lie on the selected receiving top/tread faces. Their tie order is above ground appearance and below supported bodies, walls and props. They are not a fullscreen grid overlay or an unoccluded green polygon. Target previews use the native targeting/choice contract and preview facts; the renderer does not recompute a different path/area algorithm.

Automatic cutaway is required when a foreground wall covers an admitted visible interactive receiving area. Determine this from the calibrated projected wall faces against those exposed target surfaces, not an asset ID, a selected-character radius or Alt. Fade the visual covering faces while keeping native blocking and cosmetic light barriers unchanged. A direct visible door/object remains targetable; picking through the faded covering wall can reach the exposed support. Alt highlights admitted usable objects and does not toggle the existence of cutaway. Restore the normal visual contribution when it no longer covers the relevant visible space. Hover/target emphasis clears when its action is committed; it does not remain painted over the entire ensuing animation.

Cutaway, target feedback and source outlines share geometry and current camera/time. They do not get a separate projection, stale latest-state picker or an independent wall-placement table.

### Honest remaining source gaps and removed stale requirements

The architecture and composition rules above are concrete. The following are actual source/coverage tasks, rather than algorithm discovery disguised as implementation readiness:

#### Current calibration and connection ledger

The earlier missing-export list is superseded by the 10 October delivery.
Source measurements and historical qualifications remain in the supplied records;
they are not new authoring tasks. Use current client selections and the following
remaining consumers. The assembly-authoring connection is complete.

| Existing owner/family | Current data and remaining action |
|---|---|
| D1 straight stone walls, D2 corners and wood wall families | New selected depth/normal/role registrations are installed. Consume them through shared geometry/material code. Preserve each family's compatible joining cross-section and suppress only internal faces of actually joined pieces. Visible receiving samples do not by themselves certify unseen closed light-blocking faces. |
| D6 stone door frame | Sampled ray packet and aperture-preserving receiving mesh are installed. Consume the delivered arch; do not recreate the prototype's rectangular shell or three-box doorway approximation. |
| G17 selected stairs | Existing three support offsets, twelve source contacts and new companions remain authoritative. Preserve top/foot joins and authored enclosing returns. No missing tread-export task or timber substitution. |
| Stone/earth/wood floor tops and skirts; G12/G13 cliffs and returns | Delivered geometry/normal/support metadata replaces the old missing-calibration tasks. Consume real support elevations, skirt/face registration and complete enclosure. Wall-corner and cliff-corner maps remain separate. |
| Existing animated doors and destruction banks | Preserve existing RG16LE companions and their decoder where selected; consume new registered RG16BE/normal companions with their own byte meanings. Six generated indoor doors now carry the physical mount/camera/member data from §6.1; shared-renderer placement must consume it and still requires visual acceptance. |
| Chest B1, plain table, covered table and other props | New companions are installed where supplied. Original pivots remain per-source: chest B1 `(192,271.36)`, plain table `(192,272)`, covered table `(192,204.5)`. Consume geometry plus role/support masks; unsupported cutout-only art uses the explicit same-support rule, not another object's pivot. |
| Fractional timber flight | Delivered mount/tread/landing correction is already connected to typed library metadata (§6.1); consume it. It remains library-only. No new native stair binding or change to G17. |
| `world.residue_wall_faces` | Retain as deposit UV/source-face mappings on their corresponding physical receiving faces. These are neither full solid colliders nor a new material registry. |
| `assets.water` and static companion references | Water mask/normal/ripple registrations and static `geometry_region`/sampling associations are restored. Implement their consumers; do not repeat metadata restoration or request new exports. |

The complete installed library remains available. Existing source-compatible
assembly selection must reach the consumer through typed current owners, not
inspection text. Missing geometry for a genuinely distinct use, such as unseen
light-blocking faces, remains a named limitation at that owner; do not improvise
a universal box or turn it into another full-library artist audit. Replacement
VFX retain delivered components, blend and timing; retired XYZ is not a fallback.

Exact volumetric interiors of cutout-only actors/props and a physically flowing smoke simulation are not promised. The supported cutout rule has a clear behavior and source-compatible result now; exact irregular depth is used when supplied. Stacked playable supports require an explicit future native design, not a renderer-side fabricated solution. These limitations must remain visible without being expanded into unrelated backend or artwork work.

Remove old universal 8 MiB page-pair limits, sixteen-pixel fringe gates, fixed curve-fitting tolerances, fixed particle chunk quotas and unsourced actor size normalization. Retain source constants and measurements where they define actual art or equations. Remove stale claims that the deleted client's paths/resources are current, that all walls are animated, that mere generated type presence proves consumption, and that the Fireball prototype certified Globe or the whole production world renderer. No new optimizer, renderer framework or validation-regeneration loop is a prerequisite for delivering the already defined system.


## 7. Asset delivery and authored rig data

The client must install the complete selected presentation library and support its registered behavior. Installation, production consumption and Studio inspection are distinct completion facts. A scene's small loading set cannot replace library coverage; a complete copy cannot stand in for implemented rendering or inspection.

### 7.1 Existing sources and complete selection

Selection follows typed references from canonical source documents. It does not recursively copy every directory, select files by name fragments, or infer current artwork from modification times. The planning inventory contains 44 rigs including 43 fixed-rig documents, 368 environment banks, 17 door definitions, 12 traps, 40 wrecks and 113 props. These counts describe the pinned registrations, with shared files and aliases; they are coverage evidence, not quotas or immutable future counts. The selected source graph now uses the 9 October Factory replacement delivery below and the final smooth48/192×256 UI selections. The Fireball v4 proof remains reference evidence.

| Family | Existing source authority | Required release and consumer behavior |
|---|---|---|
| Terrain, walls and architectural details | `game_obsolete/data/assets.json`, `game_obsolete/data/world_bindings.json`, environment registrations and source assembly records | Preserve source family, compatible adjoining pieces, physical placement, pose, pivot, scale, support/face registration, animated frames and source companions. Material names alone do not establish compatibility. |
| Doors and windows | `game_obsolete/data/environment_art.json` and named source receipts | Include frame, leaf and insert states, open/closed/break variants, parent/insert destruction, exact sample times and commits, selection/aperture masks and passage points. Physical pose and source-bank pose remain separate. |
| Props, traps and wrecks | Existing environment and prop registrations | Native state selects intact/engaged/open/broken/destroyed art and transition timing. Include all selected companions and post-destruction variants, not only intact banks. |
| Modular characters | Root `BodyRig`, rig tables and layer registrations | Include all declared clips and facings, body/shadow/gear/Magic/Effect slots, masks, source palettes/materials, sockets, layer order and exclusions. Idle/Run alone is not support for a rig. |
| Fixed goblins, animals, demons and monsters | `game_obsolete/data/rigs/*.json` and exact creature associations | Use the same `BodyRig`/`BodyClip` sampling path. Preserve original shadows and accents, semantic aliases, native wing clips, rest anchors and accepted appearance scales. Baked equipment does not become removable modular art. |
| Equipped and ground items | Existing item appearance/material/attachment documents and `content_data/ledgers/neuroclient_authored_item_visuals.json` | Preserve exact owned item appearance across held, dropped, looted and re-equipped states, including coatings/enchantments. Do not substitute old generated NeuroClient equipment tables as canonical data. |
| Spell, action, condition and lifecycle media | Current recipes, media registrations and storage selections | Include each selected phase/layer/direction and its dependencies. Preserve original source frame count, duration, uneven timing, crop/pivot, masks and companions. The historical source type name `projectile` does not restrict selection to flying sprites. |
| Water, blood, deposits and residue | Current world/material/particle/release/landing registrations | Export the selected compact production representation, receivers and ownership without adding new chemistry or a particle simulation. Retain the full originals privately. |
| Icons, portraits and choices | `ui_media.json`, `ui_presentation.json`, current icon handoff, accepted portrait registrations, choice records and selected font/skin sources | Install exact content/direct-feature/direct-item/choice roles. Use the selected smooth48 icons and 192×256 portraits. Native names, stats, discovery and private descriptors are not recovered from the art catalog. |
| Audio, where currently selected | Existing authored media references | Use the same release and presented contact/lifetime clock. Seeking does not replay historical one-shots. No new sound production or audio-event schema is added. |

Every selected identity retains its source pointer, dependencies and intended consumer. The tracked client selection owns the adopted media dependency graph; Factory deliveries and Pygame source are provenance, not automatic override authorities; pending depth/normal exports do not cause retired XYZ banks to be converted or imported. Tool-only provenance remains tool-only. Derived resource paths and packing addresses do not become a second editable catalog. The complete canonical field disposition elsewhere in this document governs which values are source-authored, derived or excluded from browser execution. Studio inspection remains read-only throughout this phase.

**9 October replacement delivery:** the selected source is
`/mnt/c/Users/tommaso/Documents/assets/VFXFactory/exports/selected-23-completion-20261009/delivery/manifest.json`.
It covers the 23 replacement families plus Sleep, Burning Hands, Thunderwave,
Color Spray and Ice Knife's burst: 193 paired banks and all 38 previously pending
XYZ references, including ground-fire/Web aliases. Its existing bindings own
frame windows, directions, component order and wall coalescing. Preserve live
procedural lightning resources and unaffected casting/projectile/condition
layers. Source `production_storage` for a replaced layer is historical evidence,
not an additional load path. The selected Fireball remains 46 frames at 24 FPS;
other clocks remain authored. Geometry RG carries depth16 and BA the octahedral
normal, not opacity; appearance permits additive radiance at zero alpha.
Follow the adopted bank matrices, pivots, cropping and radiance scale. The Ice
Knife burst is enabled in tracked client authoring; its paired debris/flash
consumer still needs renderer implementation. Asset
delivery does not certify renderer integration or replace the common production
renderer/Studio path. Current intake locations and remaining work are in ASSETS.md.

### 7.2 One private installation, explicit footprint

The repository's source, authoring JSON/schema, shaders, tools and small fixtures are tracked. Artwork, private recordings, intake receipts, dependency caches, captures and builds are ignored. The installation and core authoring are prepared; full release assembly/loading and application consumers remain to be implemented.

Use one physical private media installation outside Vite's `public/` tree and outside `dist/`:

| Location / status | Contents |
|---|---|
| `NDClient/.media/smallscale/`, `environment/`, `ui/`, `vfx/` | Actual artwork in family/source subfolders, retaining original meaningful filenames. Spells, conditions, areas and actions have separate VFX folders. No hash filenames or checksum/deduplication machinery. |
| `NDClient/authoring/` — tracked, present | Editable client values; `catalog-index.json` resolves canonical files/JSON pointers. Environment, item/palette and UI sections are also adopted under their own indexes, using existing owners. |
| `NDClient/.runtime/releases/<release-id>/` — generated when integrated | Prepared metadata/section index referencing the single installed artwork tree. Serve through an ordinary static metadata route; no binary copy per release. |
| `NDClient/.runtime/` | Local SDK package, development recordings, captures and bounded diagnostic output. It is not another media installation. |
| `NDClient/dist/` | Built application code only; no duplicate library or copied `.media` tree. |
| Existing source/art owners | Original artwork, accepted handoffs and canonical authoring documents remain untouched. Their preservation is separate from browser-ready installed bytes. |

This is a directory convention for the client assembly and static serving, not a new asset server, package registry or authoring database. The release resource table is the single dependency list; no parallel hand-maintained payload registry is introduced. Configure one media root URL, `/media/`, and one selected release manifest. Resource paths resolve relative to that configured media root. Development and deployment serve `/media/` from the same installed `.media/` tree using ordinary static-file mapping. Vite's `public` copy mechanism does not process these bytes; building the app does not reinstall or duplicate them. A deployed static app and its private media mapping may have separate filesystem locations while keeping the same URL convention.

The copy tools follow the agreed selections into those readable folders. Preserve
source archives and canonical authoring; keep copied art ignored by Git. Update
exported resource URLs alongside locations. No object-store indirection, checksum
pass, deduplication machinery or browser path-rewriting workaround is required.

Report these quantities separately from the same existing manifests: selected source identities; required unique browser payload bytes; installed unique payload bytes; active and retained release manifests; app build bytes; runtime recordings/captures; decoded CPU bytes; resident GPU bytes. Disk installation is not GPU residency, and a sum over release references is not unique installed size. Explain any growth by changed payloads or retained recordings rather than presenting one unexplained directory total.

Retained recordings pin immutable release identities, not complete duplicate payload directories. A release still referenced by a retained recording remains available. Removing a recording or unused release is an explicit library operation; ordinary startup, app builds and GPU eviction do not delete it. Unreferenced payload cleanup follows those release references when such cleanup is requested; no recurring cleanup daemon or mandatory retention count is added. Metadata-only authoring changes reuse unchanged payloads.

Fresh setup documents the media install command, selected manifest, server URL/origin, SDK package installation and static URL mapping. Starting the client does not hash or scan the source art tree, copy releases, regenerate SDKs or launch another rules engine. A launch must not depend on an agent's orphaned preview process.

### 7.3 Preserve useful sheets and actual animation clocks

**Current Smallscale source/layout selection (9 October):** use the complete
unified Fantasy Character Creator V1.3 archive under `.media/smallscale/modular/`,
with original layer/action paths. Do not preserve the older limited modular copy
as another library or automatically promote its differing images to overrides.
Both supplied V1.3 vendor packages agree on those images. Existing authoring and
resource IDs remain the metadata authority; artwork comes from this unified source.
All owned fixed-creature packs belong under `.media/smallscale/authored/`, including
unimplemented creatures. Backend rig coverage does not limit which creatures are
copied. Keep original pack/creature/action subfolders; existing direct rig references
reuse those pack files, with genuinely derived shadows named inside their own packs.
Shared modular casting effects use the same modular library, not another VFX copy.

**9 October B selection:** the human chose combined/with-shadow creature sheets
over duplicate shadowless body versions. The A/B intake omits a B shadowless body
only when its combined source counterpart exists, including duplicate installed
body aliases. Retain separate authored effects/shadows and all A media; preserve
original archives and existing rig/action authoring.

**9 October clarification:** separate body, shadow and swoosh/glow components
are desired where useful. The with-shadow choice avoids redundant body variants;
it is not a ban on separate components. Author the method and its inputs per
character/action and operation. Shadow suppression, body material changes,
swoosh recolouring and depth coverage may require different methods; do not turn
every task into the same colour/alpha gate or hardcode creature branches in the
renderer. Reuse original layers where their composition is known, source-RGBA
selection where sufficient, and registered masks where colour cannot distinguish
the components. No source method is accepted merely because all URLs resolve.

**9 October layer-control delivery:** `authoring/characters/sheet-components.json`
now connects all 1,368 Goblin/Orc and Demon combined sheets (65 characters) to their
original clean bodies, shadows and available effects. Clean bodies are authorized
components, installed in each pack's `Bodies/` folder; source artwork is unchanged.
The existing 43 fixed rigs and modular rig retain their IDs, clips, contacts,
facing rows, timing and source sockets. This does not invent rigs for library-only
creatures.

`source_interaction` is the authored method on those combined URLs.
`src/rendering/character-material.mjs` implements one reusable Pixi WebGL2 material;
the asset review imports that material and supports the entire two-pack selection,
frame/facing/playback, body/shadow/VFX strengths and independent body/VFX hue/tint.
Original combined C, clean body B, shadow S and effect E share one UV region.
The material preserves C at neutral settings and uses the original separate
sources for body-off and effect-off endpoints. It preserves the artist's overlap
instead of painting the full separate effect over the body. No runtime CPU image
processing or generated signed-residual texture library is required.

The user's signed-subtraction experiment established exact reconstruction. The
implemented extension retains the observed body/effect interaction while varying
the original endpoints. Mixed shadow removal uses a bounded observed-shadow
contribution; overlapping colour attribution is a nonnegative material convention,
not recovered physical geometry. No-effect sheets ignore the VFX knob and return
the actual clean body at shadow-off. Detailed equations, limits and consumption
rules are in the compact client `authoring/characters/README.md`.

All source URLs/dimensions were checked. GPU checks cover seven endpoints on 69
actions spanning all 65 characters: 483 source-image comparisons with zero byte
error on the tested backgrounds; full-sheet neutral comparisons cover 360
frames/facings of Goblin 08 Attack 5/6 and Demon Beast 1 Attack 1. Recolouring keeps
alpha and the review's real controls run without browser errors. These are
composition checks on Chromium/SwiftShader, not native performance measurements
or acceptance of every frame by eye.

The material consumes `source_layers` as inputs, not extra draws. All 330 registered
semantic clip uses retain a matching shadow slot. All 85 uses with nonempty
original effects now have an explicit `BodyClip.layers` owner: 19 enabled and 66
disabled. Consume companions once at that clip/frame occurrence, retaining unrelated
aura/spell layers. `has_accent` declares availability; `RigLayer.enabled` declares
contribution activation. Disabled is not a request for an extra draw and must not
leave the baked effect visible through the combined source. Preserve these authored
defaults; do not automatically enable every available effect. Apply the existing rig shadow alpha once, and
keep ground shadow separate from body depth/hit coverage.
This leaf material and asset inspection page are complete; game/Studio stream,
world ordering, common resource ownership and the rest of N0/N1 remain pending.
Other fixed packs retain their initial partition qualifications. Their remaining
experimental material masks are unaccepted and are not inputs to this method.
Do not generalize the Goblin/Demon result to those different source structures.

Most fixed rigs and animated environment registrations already use sheets or frame rectangles. A numbered file path is not proof that every frame is stored separately. Reuse those sources and their shared texture regions. Loose accepted frame payloads, including the selected Factory Fireball, are also valid initial delivery units; an atlas is not automatically smaller or faster.

Packing is justified by an actual renderer texture limit, required format/access conversion, or demonstrated production loading improvement. No invented page-byte target, universal codec conversion, library-wide repacking campaign or artwork downscaling is a prerequisite to implementation. Preserve full-cell dimensions, trim offsets, pivots, sockets and timing. Where lossless trimming is used, coupled planes share registration; radiance with RGB at zero alpha must not be discarded as empty. Numeric validity, categorical owner data and depth must not undergo color-space conversion, premultiplication or lossy compression. Do not rotate atlas regions unless the existing registration and every companion consumer explicitly support it.

Use nearest sampling for the accepted pixel-art/numeric sources and appropriate linear sampling for the selected smooth UI sources. Mipmaps, padding and UV clamping follow the actual representation; numeric padding does not acquire valid depth. Existing flat sheets remain in their delivered formats. The new Factory banks use lossless gzip RGBA8 byte packets for appearance and geometry, with dimensions/crops declared by their manifests; do not image-decode those packets as PNG or repack them merely for uniformity. Source frame rates are preserved: VFX commonly use 32 FPS, creatures have their own rates, some environments use uneven sample times. The selected Factory Fireball retains the explicit 46-frame, 24 FPS, 1.916667-second exception. Globe retains its current 32 FPS. No blanket resampling is authorized.

All world animation is sampled from presented time. `AnimatedSprite` may be used as a frame view only with independent autoplay/ticker ownership disabled. Source frame selection, state commits and resource lifetimes are not driven by `onComplete`. Playback speed is applied once. Shared pages and aligned companions become ready together through the one production resource owner; a thumbnail or a second cast does not create an unrelated loader/cache.

### 7.4 Complete modular and fixed-rig data support

**9 October character authoring preparation: complete.** Source composition and
the authoring connections are implemented; animation and full material consumption
are pending. The initial scan confirmed 43 fixed rigs matched the engine sources.
The client now contains the intentional source/control additions below, retaining
44 rig identities, 452 semantic clips and 767 body-context bindings. Existing gameplay rigs use 322 of the 1,368 interaction-backed sheets,
across 24 of the 65 library characters. The remaining sheets need no invented
binding merely to inspect them. Client `authoring/characters/README.md`, section
“Pygame integration scan”, records the exact owner/consumer map and remaining work.

Reuse `resolve_body_context`'s exact/default/shared precedence, `context_frame`
and `context_anchor_ms`, and `adapt_cast_body`/`resolve_cast_recipe`'s actual
rig-specific conversion rules. Existing `BodyRig`, `BodyClip`, `BodyContext`,
`RigLayer`, `StudioActorLayer`, `PaletteTreatment`, condition and finite-material
records are the data foundation. Source aliases, reversal/rest/frame keys, source
sockets, hidden slots, `owns_cast_preparation` and original clip accents remain
functional inputs. Do not replace these with the inspection page's 128px cells,
eight-row indexing, temporary sliders or library-only 12 FPS clock.

The leaf shader's hue/tint controls do not implement the authored palette/texture
material operators. Implement those consumers using their existing records.
§5.3's optional `material: ConditionBodyRamp` is now present on
`StudioActorLayer`/`RigLayer`; implement its consumer, not another authoring extension
or parallel hand/glow material type or preset store.
Production sampling derives controls from the authored appearance/condition/action
owners and consumes companions once. Clean-body coverage supplies physical
selection/outline masks; ground shadows retain their receiving support independently
of airborne body/effect colour. These are required consumer connections before
calling the character animation path integrated, not reasons to repeat asset intake.


**Closed pre-phase contract — consume these static authored inputs:**

| Owner | Completed state | Required later consumer behavior |
|---|---|---|
| `authoring/catalog/rigs.json`: fixed `BodyClip.layers` | Original 19 source effects explicitly enabled; 66 previously unused source effects explicitly disabled. Eleven rigs gained an effect slot/category to hold the actual existing companion. Existing clips, aliases, contexts, sockets, scale and timing are preserved. | `enabled` controls the contribution, not source availability or companion deduplication. Disabled layers still reserve their clip-owned slot; they cannot become always-on appearance defaults. |
| `BodyClip.sheets` and `catalog/resources.json` | Every selected/nonselected original effect has its exact source reference, using the existing resource/category structure. No second creature binding map. | Resolve once through current resources and match to `SheetComponents.source_layers`; consume a matching companion once even when disabled. Unrelated spell/condition effects remain independent. |
| `characters/sheet-components.json` | All 420 existing fixed body/shadow pairs connected; this step adds 98 animal/dinosaur links across 18 rigs and 99 semantic clip uses. Source aliases share the same record. | Use original RGBA/mask selection for those animals and the declared source-interaction method for Goblins/Demons. Apply rig shadow alpha once. No inferred clean-body data, new animation or new animal size. |
| Existing `RigLayer` | `enabled: bool = true`; existing clip `alpha`/`tint` are editable rather than restricted to opaque white; optional `material` reuses `ConditionBodyRamp`. | Sample the chosen source contribution using those values. Existing effect ownership, frame and release timing remain independent of whether the visual is hidden. |
| Existing `StudioActorLayer` | Optional `material` added; existing enabled/hidden, colours, palette, blend and source overrides retained. Generated authoring schema reflects both layer owners. | Follow §5.3 precedence. Do not turn the inspection slider state into gameplay state or add a preset database. |

`owns_cast_preparation` values are unchanged. A clip may own preparation while its
original visual is disabled: do not reactivate a generic hand effect or move a
release marker as a side effect of the FX toggle. New material fields default to
absent; no speculative visual treatments were authored. Original Pygame JSON is
untouched, and future client edits belong to the tracked NDClient copy.

This closes the character authoring-connections preparation only. Do not repeat
asset copying, component derivation, initial rig import or source inventories as
runtime prerequisites. No game sampler, renderer, shader-operator expansion or
Studio work was performed in this step. Library-only creatures remain available
without invented gameplay assignments; other packs retain their explicit source
separation limitations. The earlier asset-view composition evidence does not
certify the production event path. The client README contains the concrete FX
edit example and source-owner audit. Both anti-slop and data-owner/ECS review apply
here; later implementation consumes this settled contract rather than reopening it.

The read-only rig inspector displays the existing `BodyRig` and `BodyClip` data and samples it through the production body sampler and renderer. Its inspection covers all current rigs and declared contexts, not only a human-body selector. Changes are made manually to canonical JSON outside Studio and reloaded through the existing export/compile path.

| Inspector | Required inspected data and distinctions |
|---|---|
| Identity and selection | Rig identity, exact creature associations, canonical source/provenance and declared slots; shared changes clearly identify affected usages. |
| Clip bank | Actual source clip versus semantic alias, frame count/FPS/sample times, facing rows, sheet/region/crop/full-cell pivot, loop and frame step. |
| Registration | Ground origin, body/head/face/hand/weapon sockets, per-frame socket samples, rest and ground-depth anchors. Show source/full-cell coordinates separately from their projected screen location; this phase adds no draggable authoring handles. |
| Timing and roles | Prepare/release/contact/effect/commit, recovery/hold and normalized travel; typed contexts for idle/run/walk/fly/jump, melee/ranged/cast, damage/avoidance/shove/equipment and condition entry/hold/exit/death. |
| Constituent layers | Body, shadow, modular equipment, Magic/Effect and original fixed-rig accents, exclusions/order, palette and source/material masks. Slot-specific policies remain slot-specific. |
| Rest and death | Final-rest/source-death selection, permitted entry reversal, disappearance/remains and prone-to-death continuity. Do not use one generic death clip as every condition pose. |
| Scale | Show source pixels, accepted appearance scale, native size and real size-effect scale separately. No class-based cosmetic percentages or normalization to human height. |
| Capabilities | Declared source clips/facings/sockets, native wings, explicit supported fallbacks and missing source poses. Visual source changes do not grant gameplay abilities. |
| Real-case preview | The selected rig in native movement/action/condition recordings, with its existing gear/palette, external VFX and all camera views. |

Goblin17's original accent follows its body but does not create a second attack/projectile. GreyWolf retains the explicitly accepted 200% artwork scale at its appearance owner, not a scale inferred from rules size. Imp05's lying/Explode/rest behavior stays distinct; prone-to-death must not stand up first. Semantic aliases reuse source images. A fixed sprite may have several original layers while its baked gear remains indivisible.

Missing required rig contexts stay explicit and use the existing canonical semantic checks. Current delivery includes inspection and rendering of all registered rigs, not a browser new-rig wizard or rig-draft system. No new creature renderer class, invented facing mirror or duplicated spell definition is introduced.

### 7.5 Environment and item data support

The read-only environment inspector exposes the selected source-compatible assembly; owner versus boundary edge; physical versus bank pose; committed support/base height; per-pose source frames/pivots; sample times; selection/aperture/depth/normal registration; separate parent/insert/leaf; release/state-change/clearance frames; destruction-without-attachment variants; passage points; and authored stair/cliff contacts. Preview actual transitions with actors on both sides and four cameras. Use the same derived physical data as production drawing, lighting and picking. This inspects production visual/environment data; it neither rewrites NeuroMapEditor nor implicitly adds stacked gameplay supports to the backend.

The read-only item inspector displays existing appearance, attachment and material sources. It compares held, floor and re-equipped presentation for the same owned item, including coatings/enchantments. Native item rules/statistics remain read-only. Shared recipes, per-item effects and source art are distinct; an item material edit cannot mutate an unrelated body or another item's cached appearance.

### 7.6 Exact resource records, leases and scheduling

`src/render/resources.ts` is the only page/source owner. Its passive map is keyed
by `(resource URL/revision, width, height, GPU format, dimensional layout, encoding,
sampling, alpha convention)`; logical asset IDs and
cropped Texture views point into it. Existing source data decides compatible sharing.
Numeric and colour interpretations never accidentally share a TextureSource merely
because their URL matches. Repeated uses of one URL can share downloaded bytes;
texture interpretations must remain compatible. No per-spell manager, camera cache
or actor-owned copy is added.

Each entry stores release-relative URL, byte length, dimensions/format, pending
fetch/decode/upload handle, CPU/GPU byte counts, current GPU generation, lease IDs
and last-use order. Its stage is `absent | fetching | decoded | uploading | ready |
failed`. Companion sets are derived from authored frame parts, not maintained in
another asset registry. One frame is ready only when every required plane is ready
in the current GPU generation. Optional tracks obey only their existing authored
omission policy.

Lease identity is `(scope generation, consumer kind, consumer identity, revision)`.
Consumers are displayed scene, active occurrence, lookahead occurrence or Studio
candidate. Acquire the complete required frame set before publishing its readiness.
Retain current sampled pages, next source sample pages and persistent displayed
lifetimes; release on sample-page transition, occurrence retirement, lifetime end,
candidate release replacement, seek or scope reset. Shared references keep a source alive until
the last lease ends. Recorded history pins **disk release identity**, not GPU pages.

Scheduling must keep current/next samples ahead of speculative loading and keep
intake and interaction independent from asset preparation. Measure actual decoded
and GPU residency in the integrated client before selecting resource budgets.
The previous fixed concurrency, memory and lookahead numbers were unmeasured
proposals and are withdrawn as implementation requirements. Retained
compressed responses use the browser HTTP cache/local release files; no second
unbounded JavaScript archive cache is retained.

Preserve the accepted frames and suitable existing atlases. Do not split or repack
them to satisfy an invented byte target. Use the actual renderer's texture limits;
if a source exceeds them, use lossless existing part/region registration. Further
packing needs a measured loading/upload problem and an end-to-end improvement.
Never resize artwork to satisfy packing.

Measure upload cost/bytes separately from GPU completion. Pixel decoding and gzip
unpacking must not block interaction; worker scheduling is chosen from integrated
measurements, without a prescribed worker count or per-frame millisecond cap.
Hold typed decoded planes
while both plane uploads complete. Shader programs and first visible scene pages
are prepared before enabling its first action; intake remains independent.

If the next semantic group/current next-frame prerequisites are unavailable, hold
the presentation clock at the last complete boundary/frame while the render/UI/SDK
loops continue. Do not retire its planes and display a half-ready frame. If measured
memory pressure requires eviction, release unleased resources first; never omit a
cast or stall playback to enforce an unmeasured quota. The current scene's
lease transitions must acquire the replacement set before releasing the old one.
Use the existing distinct-age Fireball case to detect actual resource churn and
buffering in production. Repair the demonstrated cause; it does not block unrelated
UI, event or Studio integration and does not justify an arbitrary cache cap.

With explicit ownership, use pinned Pixi `TextureSource.autoGarbageCollect=false`
and `source.unload()` for unleased GPU eviction. Destroy region views only when
their consumer releases them; destroy a source only when its entry has no leases.
Context loss increments GPU generation, pauses presentation and recreates leased
sources/targets/programs from retained resource references. SDK intake/retained
history stay live. Upload completions from old scope/GPU generations are discarded.
Camera transforms/light uniforms never invalidate decoded pages or receiver fields.

Consume the authored plane geometry and source references; do not add an artwork
checksum pass to copying or loading. Boot loads the small release index and the
active metadata/media closure (§5.4), not full-library metadata or a full-library
decode pass. First/repeat/rotated/seek/context-loss cases report fetch/decode/
upload counts to expose accidental reloads. Implementation may tune numerical
budgets to measured hardware; it may not add another owner or discard content.


## 8. Studio: read-only inspection of the production runtime

### 8.1 Concrete existing components to recover

Existing source paths below are relative to `/home/tommaso/Dev/NeuroClient/app/src`. Recover their useful behavior and calculations, not their old global-store/SDK/FSM ownership. The current data and source field inventory remains authoritative when an old component is narrower.

| Existing source | Recover | Adaptation in this client |
|---|---|---|
| `ui/studio/StudioTimelineLayout.ts` | Aligned label/time geometry and time-to-pixel/inverse mapping | Current time domains and zoom; no separate timeline schedule. |
| `ui/studio/StudioTimelinePixi.ts` | Hierarchical tracks, ruler, playhead, release/contact markers, preview beds and palette swatches | Compiler-derived channels; its default colored-bar drawing alone is insufficient. |
| `ui/studio/StudioTimelineView.ts` | Row sizing and source frame/FPS/direction metadata | Actual owner/occurrence/cause groups, not fixed caster/projectile/target assumptions. |
| `ui/SpellStudioPreview.ts::drawTrack`, `drawProjectileFramePreviews`, `drawActorLayerFramePreviews` | Clip thumbnail strips for the actual body/equipment/effect layer and media phase | Extract helpers; production sampling and shared resources replace old class/store and simplistic sequential frame loops. |
| `ui/spellStudio/{actorPreviewDom,assetPreviewDom}.ts`, `ui/actionStudio/actionMediaPreviewDom.ts` | Actor strips, asset cards and actual registered-media previews | Current layouts/companions and material interpretation. |
| `ui/studio/StudioInspectorControls.ts` | Readable field rendering, units and grouping | Read-only adapters to current canonical fields; do not recover editing widgets for this phase. |
| `ui/actionStudio/{actionStudioFieldSchema,actionContextFieldSchema}.ts` | Action/anchor/projectile/item/VFX/context field groupings and labels | Read-only current-type inspection; remove obsolete ownership assumptions. |
| `ui/conditionStudio/conditionStudioFieldSchema.ts` | Transition, persistent, equipment, appearance and media field groupings | Inspect current multi-owner/lifecycle/suppression and head-marker behavior. |
| `ui/studio/StudioModalBoundary.ts` | Exclusive focus/input ownership and cleanup | Studio controls cannot issue game commands or move the game camera. |
| `ui/studio/StudioPixiSurface.ts`, `StudioPixiLifecycle.ts` | Mount/resize/stale-mount handling and complete teardown | Shared current renderer/resource lifecycle; no separate family renderer or destruction of another consumer's texture source. |
| `ui/boardViewportController.ts`, `iso.ts`, `grid.ts` | Camera gestures, focus suppression, pointer zoom and shader-grid approach | Current calibrated support projection/picking and change-only updates. |
| `render/SpriteAssetRegistry.ts`, `facing.ts`, `visualAnchors.ts`, compatible layer calculations in `AnimatedEntity.ts` | Shared source/region reuse, facing and source-anchor handling, complete appearance replacement | Current registered dimensions/sockets, one modular/fixed path; no actor-owned clip/FSM system. |
| `ui/actionBar.ts`, `actionBarModel.ts`, `equipmentPanel.ts` | Icon/slot/layout/input helpers and compact inventory behavior | Current displayed SDK-fed views, four action groups and native choices. |
| `ui/initiativeBar.ts`, `combatHistoryPanel.ts` | Portrait selection/turn distinction and DOM log docking/resize/follow | Current audience/displayed state and typed log; these inspected widgets need not be rewritten into Pixi. |
| `render/pixiRendering.ts`, `pretextLayout.ts`, existing portrait/icon helpers | Readable text, measured layout and shared image use | Current selected artwork/roles; no repeated text rasterization during simple movement. |

A component is not recovered because a similarly named file exists. Its required function must be connected to current data. Conversely, preserving a capability does not require copying the old class or global singleton around it. Old synthetic Studio battle hosts, old protocol adapters and spell/action/condition-specific schedule builders are replaced by the one production path.

### 8.2 Cases and shared execution

Studio is an offline input adapter and inspection workspace for the actual production renderer. It digests prerecorded test streams through the same TS subjective reducer, ancestry/index handling, causal compiler, retained presentation state, absolute-time sampler, renderer and resource owner used by live play. Spell/action/condition/rig/item/world/material views select and inspect that shared machinery; they are not family preview renderers or another orchestrator. The complete displayed world, actors, equipment, materials, effects and commits must compose coherently through that production path. A complete timeline or a successful isolated clip cannot establish that the renderer is delivered.

A gameplay case contains the actual current SDK initialization and ordered operation payloads received from the running server, its authorized audience, admitted content, case label/interval/tags and pinned presentation release. Capture tools run beforehand, outside Studio, by driving the real host through the current SDK. Schema-valid synthetic records and direct native projected sequences are not accepted substitutes. Studio only reads the resulting recorded input. It does not connect or attach to the game server, open a live follower, query choices/previews/content, send gameplay commands or generate native events. No TypeScript preview helper fabricates success, damage, movement interruption, condition application or death. All descriptors needed by the case are admitted in its recorded data; missing content is a case error, not a reason to query the server. Native private recordings are not exposed as browser cases.

Old-protocol and direct-engine gameplay examples must be recaptured through the actual server. A format conversion cannot manufacture server provenance, and no alternate legacy decoder belongs in Studio. Source/registration diagnostics inspect geometry and channels without creating event outcomes or synthetic all-visible observations. Browsing includes all selected recipe/rig/environment families, with actual content and issue tags used to find relevant cases, not only a shortlist of successful examples.

Only the source of input differs: the live game receives admitted operations from its SDK session; Studio supplies prerecorded initialization and operations to the same production pipeline. The same recording samples identically at matching presentation times whether the timeline is visible or not. Pausing/seeking affects presentation, not native rules. Studio requires no running game server. It loads its recorded input and installed release locally; missing operations or resources produce an exact diagnostic rather than a server query, substitution of newest artwork or jump to the final state. Canonical JSON changes are made manually outside Studio and reloaded through the existing source/export/compile path; Studio has no save endpoint or editing protocol.

#### 8.2.1 Gameplay examples originate at the actual server

**Server-origin recording is mandatory, independently of schema validity.** Create a gameplay case by starting the current `server`, driving its real API with the current SDK, and recording the exact subjective initialization and operation payloads delivered to an authorized SDK consumer. Studio may then load those files as static local examples with the server stopped. No locally constructed event-shaped object, direct-engine export or wrapped legacy sequence qualifies as that capture.

```text
existing ServerConfig / EncounterRecipe and native setup
    → actual server host and engine worker
    → current SDK choices / preview / command / receipt
    → authorized SDK follower receives real initialization and operations
    → save the raw received payloads and their complete scoped prefix
    → offline Studio feeds those records to the shared production runtime
```

Use the existing owners, without a new scenario language or event-injection endpoint:

| Existing source owner | Actual role and required reuse |
|---|---|
| `server/config.py::ServerConfig`, `server/app.py::create_app`, ordinary server CLI | Run the real service/engine worker. Current encounter recipes, seat/controller configuration and private test seeds are already supported. |
| `devtools/player_server_acceptance/fixtures.py::{configuration,combat_configuration}` | Existing actual native setups cover controller arrangements, the crypt, melee/ranged, Magic Missile, Scorching Ray, Fireball, Hold Person, Wall of Fire and Conjure Animals. Use their supported configuration as reference for client-side capture scripts; do not extend native setup owners. |
| `devtools/player_server_acceptance/run.py::run_case` with `python_player.py`, `typescript_player.mjs`, `crypt_player.py` | Existing host launch, independent current-SDK command drivers and per-seat numbered raw capture files. The crypt driver uses the production Python reducer over received records to choose its next command; it does not invent outcomes. |
| `devtools/player_server_acceptance/http_run.py`, `test_host.py`, `http_performance.py::client`, `combat_http.py::intent` | Another existing real-HTTP host/client lane, including repeated targets and spell/wall selections. Reuse the ordinary capture/driver functions without requiring its performance monitor, profiling, quotas, repeat-submission probes or deadlines for every Studio case. |
| `devtools/player_server_acceptance/{http_replay,replay}.py` | Existing current-packet admission/prefix/reduction checks. Reuse a focused check when its boundary changes; do not turn each visual edit into a schema/benchmark ritual. |

The complete capture procedure is:

1. Prepare the intended scene through existing native encounter/roster/battlefield setup. Existing grants, starting damage/conditions, damage affinities and resource state are legitimate setup; a client-generated damage/condition event is not. A deterministic private `test_seed` can make a test reproducible, but is recorded as test setup and never changes ordinary player launch or permits editing received dice.
2. Start the ordinary host outside Studio. Configure the actual observing/controlling audience needed for the case; do not synthesize an omniscient observation, leak the objective map or introduce an authoring backdoor. The map and compatible asset assembly are real native setup plus canonical presentation bindings.
3. Attach a current SDK follower and save each `consume(packet, raw)` payload before returning. The existing clients write `000000.json`, `000001.json`, and so on from genuine scoped cursor sequences. Complete input comes from real `choices → preview → submit → receipt` calls with current authority and ACK catch-up. The driver chooses commands, not hit/save/cancel/death outcomes.
4. Keep initialization and the complete operation prefix needed for the selected interval. A case that highlights a later cast keeps its earlier references; it does not cut/renumber operations into a fictional independent fight. Advance legitimate turns/commands to record suppression, expiry, removal or consumption. An initially granted condition demonstrates cold existing state, not a witnessed application transition.
5. End after the actual terminal cursor or after the chosen durably received completed operation. A shorter capture is explicitly a prefix, not a fabricated terminal. Disconnect and shut down owned host/worker processes through the existing lifecycle helpers; no abandoned server is needed for replay.
6. Install only the selected audience's packet files and a small existing case-index entry—label/tags, recording location, viewing interval and pinned presentation release—into ignored local case storage. Preserve the original admitted content additions. Keep credentials, launch configuration, objective diagnostics and host spool outside the served case directory. Missing descriptors are a capture defect, not a reason for Studio to query the full catalog or server.
7. Load those exact packets with the host stopped, using the same admission/reduction/compilation/sampling/rendering path as live play. Manual canonical presentation JSON edits can change authored visuals against that preserved outcome; they do not rewrite the outcome, scope, cursor or native record.

The current Python recording client needs the existing `sdk/python` package installed in its selected environment; it is not a declared dependency of a fresh engine-root environment. Follow that SDK's existing install instructions, or use the independent installed-client lane. TS capture uses the current `@neurodragon/player-sdk`. This is package setup, not schema regeneration. For reference, the existing real-HTTP runner accepts `uv run --no-sync python -m devtools.player_server_acceptance.http_run --output .runtime/ndclient-studio-captures/magic-missile --combat-case magic_missile --port 8796` in an appropriately prepared environment. That command also runs its current performance monitor; it was not executed in this planning scan, and the monitor is not a new Studio requirement.

Reuse the existing runner receipts for source driver/configuration identity, source revision and local-change note, captured interval/end cursor and terminal-versus-prefix status; keep private setup private. Packet scope/protocol/content remain authoritative in the packets. No signing system, parallel event schema, case registry or provenance certification service is required. The proof is the actual host/SDK capture path, followed by offline replay—not a JSON filename or a passing SDK assertion.

The following are useful references but **not conforming server captures**:

- `devtools/animation_review/{produce,capture}.py` and `devtools/player_server_acceptance/corpus.py` execute/project native cases directly. Their broader case setup is useful; their `player-v2`/`PlayerSequence` exports cannot be relabeled as delivered SDK traffic. Adapt setup/commands and recapture through the host.
- `devtools/export_world_authoring.py` constructs a synthetic full-map observation/sequence. Keep any useful map-construction information as an offline source reference; do not feed its invented observer/event IDs or all-visible world into Studio as a gameplay stream.
- Old NeuroClient `SpellStudioPreview.buildCurrentPreviewTransaction`, `ActionStudioPreview` and `ConditionStudioPreview.replay` use local subjective-frame builders before `compileStudioScenario`/SDK assertion. Recover timeline/thumbnail/inspection helpers and its separate real-recording import behavior, never those synthetic outcome generators or old wire types.

No blanket geometry-case exception permits fake gameplay records. Registration diagnostics and asset-layer thumbnails inspect the actual source/rendered geometry of a real recorded scene without inventing native observations. Pure geometry unit tests can still test pure functions; they are not Studio server-stream evidence. Capture a new real-host recording when a required current behavior lacks one. Ordinary material, timing, icon or UI changes reuse a compatible recording. Client-side capture scripts use supported configuration and public SDK calls; an unavailable setup/outcome is reported rather than unlocked by changing the engine or fabricating packets.

### 8.3 Hierarchical channel timeline, previews and clocks

Recover the animator workspace: expandable channel list aligned with shared ruler, clips/curves/markers, playhead, loop range and selected-source inspector beside the production viewport. The timeline is a derived view of actual compiled occurrences and canonical authored fields, not another executable animation format.

| Channel group | Required visible content |
|---|---|
| Body and attached layers | Rig/source clip, body/shadow, each equipment slot, Magic, Effect, original fixed-rig accents, recovery/hold and socket samples. |
| Delivery and motion | Each actual projectile, beam, area and repeated recipient; movement legs, flight/jump/portal phases, attachment and path. |
| Material and appearance | Resolved palette/override, masks/donor selection, existing material envelopes, fades/time maps and authored enablement. |
| Reaction and lifecycle | Damage/heal/death, interrupts, condition entry/sustain/removal/suppression, head-marker intervals and summon/despawn. |
| World and deposits | Formation/retirement/clearance, door/prop transitions, blood release/landing, ground contributions and relevant state commits. |
| Recorded causes | Event ancestry, actual recipient/outcome and release/contact/commit dependencies; these native facts are read-only. |

Group by actual occurrence, owner and cause. Repeated A/B/A applications have distinct lanes even when two target identities match. A case is not reduced to one caster, one projectile and one target. New content using supported record kinds automatically appears through those shared projections; it does not need a spell-specific timeline builder.

**Sprite-backed clips show actual frame thumbnails.** Recover the existing actor-layer and projectile-phase strip capability. Thumbnails use the selected source clip/phase/facing and current resolved palette/material, preserving full-cell registration. Their positions correspond to samples on that lane's actual source-to-presentation time mapping. Selecting a sample reveals source frame/sample time and resolved time. The inspector can compare the original layer with the resolved composition. Empty source intervals, missing resources and intentionally hidden diagnostic layers are distinct states.

Thumbnail generation uses production sampling and the same texture sources/material functions. It does not decode every asset, create a second animation scheduler or cache full candidate worlds. Draw the visible rows/samples and update their static thumbnails when selection, revision, facing or layout changes; moving the playhead alone does not rebuild every strip. Sample density follows visible lane space/zoom, not a project-wide count copied from the old UI. For procedural/material channels without source pictures, display their actual supported curves/parameters and a production-sampled preview where useful, not fabricated sprites pretending to be source frames.

Resolved seconds/milliseconds form the common ruler. Selected channels also expose source frames or uneven sample times, source FPS and effective playback rate. Measured render FPS is a separate diagnostic. Source-frame stepping follows the selected track's real sample boundaries; there is no fictitious global 24/30 FPS editor clock. Release/contact/commit/removal markers indicate whether their value is authored or derived from recorded causality.

Provide play/pause, rate, source-frame step, forward/backward scrub, loop range, camera rotation, fit/pan/zoom, track selection/expansion and optional equal-time comparison of explicitly loaded baseline/candidate source versions when straightforward. A seek restores a retained prefix/checkpoint and samples the same runtime; it cannot reroll or redispatch gameplay. Persistent loops, condition effects, environment frames, light and feedback all use the same presentation time.

Timeline clips, authored timing markers, curves and source values are read-only. Selecting them exposes their source document/field, units, resolved value and recorded cause. Playhead and loop-range gestures control playback only; they do not rewrite clip edges, release offsets, curves or outcomes. Manually changing an authored release in canonical JSON then reloading recompiles dependent timing through the same compiler, rather than storing another schedule.

Expand/collapse, scrolling, zoom, selected track, loop range and diagnostic mute/solo are preferences. Mute/solo hides visual channels only; it never deletes native events, changes damage, shifts causality or disables a death outcome. Authored enablement changes only when canonical JSON is manually changed and reloaded. Closing the timeline leaves production playback unchanged.

### 8.4 Full inspectors and canonical source ownership

The complete field ledger in this plan is the denominator. Every relevant current source field has a production destination and a readable inspection path showing source ownership, actual units and resolved meaning. Source-authored, derived and tool-only values are distinguished. Structured read-only inspection plus source references is sufficient; this phase does not require field editors, draggable source handles or a browser save tool.

| Inspector | Required coverage |
|---|---|
| Creature/rig | All registration, clips, semantic contexts, slots, source layers, sockets, rests, scale distinctions and capabilities in §7.4. |
| Cast/action | Exact content/variant, compatible body gesture, source/effective rates, release/contact/recovery, hand/weapon sockets, gear visibility, Magic/Effect and isolated material layers. |
| Spell delivery | Repeated/multiple targets, bank/camera/direction basis, paths/height, release/travel/arrival, area/directed media, interruption/protection response and actual child applications. |
| Conditions/lifecycles | Actual cause, owner count, entry/sustain/removal, suppression/expiry, size anchors, concurrent body/ground materials and head-only playlist. |
| World/environment | Source-compatible family/assembly, pose/base/contact, registration and masks, formation/visibility/light/clearance commits, construction paths/sections and receiving faces. |
| Items | Existing visual categories, hand/ground association, item-owned attached effects/materials, held/drop/re-equip comparison. |
| Materials | Palette and explicit overrides, source masks/donor texture, ramps/gamma/noise/rest coordinates, alpha/blend/depth, receiving/emitted light where represented, separate item/body ownership. |
| Feedback | Existing damage/heal/save/temporary-HP/life-state effects, numbers/badges, body releases/intakes, summons/hostility and deposits; recorded amounts and outcomes remain read-only. |
| Resources | Source and derived bytes, window/rate/loop, facing versus wall-axis, ordered components/coalescing/removal, frame-versus-bank calibration, paired planes, registration and residency; inspect the same values consumed by the renderer. Derived packing fields remain read-only. |
| UI visual data | Exact icon/portrait/choice roles, selected font/skin resource parameters and bindings. Native content descriptions/stats/availability and combat-log math are not visual-authoring fields. |

Retain the existing motion/effect semantics from the authored modular casting catalog: ground strike, invocation, pointing, beam and bow gestures have different meanings. Studio displays the combined body, attached layers and external effect at the actual palette and timing. Supporting all source data is not permission to redistribute accepted spell assignments or invent variety.

### 8.5 Manual canonical JSON changes and reload

The first Studio is read-only. Change tracked `NDClient/authoring/` JSON with a
text editor. This intentionally adopted effective catalog is the client source,
not a temporary export to be regenerated from Pygame. Native records/outcomes are
not authoring controls. Original engine/Factory files remain unchanged.

Inspectors obtain editable file/JSON-pointer locations from `catalog-index.json`
and the remaining section files. Show the selected values and supplied historical
provenance where useful. Do not require a second field registry, reconstructed
override history, provenance server or browser write endpoint. Public releases
contain no absolute author filesystem paths.

Run the client assembly for changed metadata, then explicitly reload/recompile
the same recorded stream through the common production machinery. Parameter
changes reuse media and do not rerun `import_vfx_authoring.py`, copy assets,
regenerate the SDK or start the game server. Schema/type generation is required
only for an actual owner-shape change. A source error names its file/field and
leaves the previous loaded input usable.

Default recording playback retains its declared release. An explicit local candidate reload is visibly identified as a candidate against that recording; it cannot silently mutate the immutable recorded release. Source values and resolved time are inspectable after reload. Reload reseeks/restarts affected presentation deliberately, while recorded native outcomes remain unchanged. A simple baseline/candidate comparison can reuse two explicitly loaded configurations at equal time; building a draft-management or version-control product is not required.

Browser editing can be a later phase if requested: recover useful typed inspector controls and history from NeuroClient against these same canonical owners and production compiler. Drag editing, undo/redo, unsaved-draft recovery, save endpoints, revision transactions and new-rig creation are not current requirements or prerequisites for complete renderer delivery.

### 8.6 Diagnostics and Studio acceptance

Optional diagnostics expose frame-time distribution, available GPU timing, reduction/compile/sample/submit time, decode/upload work, draw calls, CPU/GPU residency and recorded-input/displayed positions. The live game's received/consumed positions, network latency and queue age are reported only where that live session exists; Studio does not create one to populate diagnostics. Unsupported timing is marked unavailable. Diagnostics use the shared production instrumentation; an exported video does not demonstrate responsiveness. A recording/reference can be shared or captured, but the running application is the primary review surface.

The finite Studio acceptance set includes:

- After capturing from the actual host through the current SDK (or selecting an existing compatible capture with that provenance), stop the host: the recorded initialization and operation stream renders the complete production scene and all of its sampled world/body/equipment/material/effect/condition/deposit channels. The case performs no game-server bootstrap, attachment, choice, preview, content or command request. Loading local static media is separate; Studio exposes no source-save endpoint.
- A combined recorded scene exercises the same renderer used by live gameplay, including elevation, source-compatible structures, actors, equipment and intersecting effects. No Studio-only geometry, draw order, clock or simplified scene consumer supplies the result.
- A repeated-target spell showing real thumbnail strips and all contributing layers, with distinct source/resolved time and source provenance.
- Interrupted movement/reaction/death with correct causal lanes and semantic commits, unchanged when the timeline is hidden.
- Mixed source clocks, including uneven environment samples, at pause/slow/fast/backward seek without timing drift.
- Multi-owner condition sustain, suppression/expiry and removal; head-marker cycling does not rotate body/ground effects.
- Modular human, Goblin original accent, approved wolf scale, winged flight and prone/death through the same rig path, alongside complete mapping of every declared rig/context.
- Item held/drop/loot/re-equip and environment open/break/clearance across cameras with the same source registration used in play.
- Manually edit a canonical presentation JSON, run its existing export step where required, then explicitly reload the same recording: source fields and resolved rendering update through the same compiler without changing recorded native outcomes, creating a browser draft or regenerating the SDK.
- Invalid or incomplete replacement source/release produces an exact diagnostic and retains the previous loaded case; it cannot silently replace a recording's pinned art. An explicitly selected candidate is labeled as such.
- Case/rig/source reload during loading, resize/DPR change and workspace teardown; old asynchronous results cannot populate the new selection or leave input/resource ownership behind.

Catalog coverage and behavioral cases complement each other. A handful of working cases does not establish that every selected recipe/field has a consumer; a complete generated schema does not establish that production rendering/inspection/playback works.

## 9. Complete player UI and interaction

This section specifies the current app to deliver. Existing Pygame and NeuroClient functions are behavioral/source references, not a list of new NDClient incidents or a demand to copy old drawing code. Neither old UI is accepted wholesale.

### 9.1 App composition and visual treatment

The default playable entry opens the authored Fighter and Sorcerer crypt, including exploration, loot, traps, doors and authored goblin combat. It does not detour through character creation or a new lobby. Existing server seat configurations cover party control, per-unit control and human/AI combinations; the client does not introduce another control protocol or arbitrary entity cap.

Recover useful Pixi icon/slot widgets and DOM portrait/log/tool controls with current SDK-fed displayed views. The old equipment and action bars are Pixi; the inspected initiative bar and combat history are DOM. Use those useful implementations without imposing a framework rewrite. One implementation owns each widget's state/input; UI controls do not own pathfinding, damage, visibility or turn rules.

Keep the world visible. Use restrained compact groups, small party/initiative portraits, readable antialiased text and consistent transparent/glass log, inventory and details. The bar remains in place when panels open. No permanent instructions, debug banners, raw identifiers, gratuitous margins or full-screen gameplay panels. Descriptions and tooltips carry help. Studio is an inspection workspace and may use its own full workspace layout without changing the gameplay HUD requirement.

Use the selected smooth icon bank and accepted portraits at exact existing content/direct-feature/direct-item/choice roles. Disabled/selection states remain clear without darkening every icon. Missing current roles are reported, not concealed by a rejected old icon fallback. Icon color does not choose the spell VFX palette. Fonts remain readable non-pixelated text even when surrounding artwork is pixel art.

### 9.2 Camera, focus, picking and world commands

- WASD/drag pan, cursor-anchored wheel zoom, Q/E rotation, optional G grid and fullscreen/window resize recover the useful existing browser behavior. Camera changes update transforms/culling rather than decoding or rebuilding the world.
- Pointer focus and capture are explicit. Typing/searching/scrolling in a panel cannot move the camera or issue a world command. Focus loss releases Alt/Ctrl/drag state; a modal/Studio owns its input until closed.
- Escape consumes the most local transient interaction: choices/context popup, targeting/approach, panel/pinned tooltip, then the application menu. Dismissal never falls through into a world command. User UI scale is adjustable independently of camera zoom through the shared layout; it changes neither world projection nor sprite proportions. No native-process restart or new browser menu framework is implied.
- The presented-scene picker uses the same transforms, physical coverage and cutaway policy as drawing. It returns an admitted object/actor/support identity; it does not decide native action legality.
- Contextual cursors use that same presented hit and current native preview: text selection, enabled UI/interaction, admitted attack/target, ordinary movement and unavailable action. Hovering does not issue a command or trigger a second authority query, and artwork alone cannot mark an action legal.
- An explicitly offered native `next_positions` coordinate can use a neutral target handle where no terrain/object has been disclosed. This does not create an observed tile, occupant, light state, name or hidden elevation. Received supports use real geometry; a protocol plane coordinate denotes that selection plane, not an invented hidden floor. A scene-only picker must not make such an admitted positional option unreachable.
- Hover outlines the actual visible silhouette rather than padded image bounds. Committing a spending gesture clears targeting highlights; they do not remain over the whole attack animation.
- Walls covering received visible ground fade automatically, preserving registered bases/openings and native blocking. Intended targets can be picked through the faded upper face. Fading never reveals unreceived gameplay.
- Alt shows admitted interactable names/highlights and clickable labels consistently across four camera views. Hidden items do not acquire labels from the static asset index.
- Normal world click uses the native unique default for movement/open/close/loot/lever/window/trap interactions. Idle context selection exposes native alternatives; canceling an active targeting gesture does not also activate that world alternative.
- Ctrl force attack is an explicit current native mode, separate from Ctrl+C in selectable log text. World affordances stay on the world/context interaction, not extra action-bar rows.
- Approach-and-interact retains its intent, uses the native safe approach, executes its admitted movement, then rediscovers the exact interaction. It never silently spends Dash or a bonus resource. Actor/blockage/door changes invalidate stale previews.
- Ordinary route requests prefer safe; Shift deliberately requests normal through §4.8's existing selection contract. A modifier change refreshes the preview without requiring another hovered tile; release restores the preference. Display the native returned policy, including legitimate normal fallback. Submit the same preference that produced the displayed route; stale replies, UI capture and focus loss cannot silently change the committed route.
- Known explored ground remains navigable according to native knowledge. Current loss of line of sight is not an invented client prohibition. Door reach and window traversal use the native incident-support/affordance result.
- Grid, route and AoE feedback follow actual receiving supports and their elevations, between ground and occluding bodies/walls, rather than drawing as a screen overlay.

### 9.3 Four-block action bar and native targeting

The compact bar has four groups: base actions including explicit melee and ranged attacks; spells; class abilities; and usable carried items. Absent groups do not consume space. Multiple rows are available when needed, with recognizable spacing and the same icon scale. No fake button is rendered as if it were actionable.

When a group overflows its available rows/columns, retain an independent page for that group, compact controls and wheel ownership. Paging spells does not page inventory or zoom the map. Recover the visible-slot digit/minus/equals shortcuts and shifted row from `game_obsolete/ui/action_bar.py` and encounter input. They dispatch the same currently painted enabled control as a click, with the same actor, discovery, page and focus checks; an old slot cannot survive a changed page/actor as an executable shortcut. Do not preserve old arbitrary column limits or add permanent filter rows, a drag/drop editor or a keybinding framework under the name of parity.

Melee/ranged selection is deliberate, including the recovered preference shortcut; the UI does not silently substitute another weapon. Group the single Dash verb with its native resource alternatives rather than inventing a Haste Dash action. A legal self action executes once with one click; unavailable actions cannot enter meaningless targeting or confirmation.

Hover choices appear directly above the relevant icon at the same icon size. Spell level selection is uniform. Actual sub-choice icons handle walls, summons, resistance/element variants and resource conversion where the native choice exposes them. Do not create a separate oversized wizard for each spell or invent options from display names. Choice selection resolves an actual discovered native choice and cost.

Facets are conditional on preceding native dimensions. Preserve compatible later choices when an earlier facet changes; otherwise resolve another actual discovered row, never an invented Cartesian combination. Intermediate choices only change selection and do not spend. Maintain a continuous hover/capture region from the origin icon to the popup and viewport-safe scrolling, so crossing a gap cannot close the choices before they are selected. Depleted choices may be inspected but cannot execute.

One transient targeting record retains acting entity, exact choice/ref, discovery revision/cursor, ordered recipient/position prefix and local preview request sequence. An asynchronous result applies only while all these remain current. Cancel, actor change, authority change and reconnect clear stale spending gestures. Pointer movement may request a newer preview without a slower old reply repainting it. Changed intent drives requests; the app does not refetch identical choices every frame.

Target lists preserve order and repeats, including A/B/A. Maximum count does not authorize automatic submission or UUID-map deduplication. Fewer than the maximum, repeated application to one recipient and confirmation are permitted exactly when the native prefix exposes them. Undo removes the last selected entry and recomputes the real next choices. Native path/AoE/impact/cost/hazard/opportunity-exposure preview matches the prefix ultimately submitted; the client does not substitute its own route or area algorithm.

Show compact per-recipient allocation counts from native `effective_target_uuids`, including `fill_primary` completion. These counts describe the effective preview, not just raw clicks; never reconstruct or deduplicate the submitted ordered prefix from the displayed badges.

Visible controls/resources derive from displayed state. Prefetched latest choices may prevent stale spending but may not reveal future cooldowns, inventory or ability changes. A spending control is enabled only when the displayed interaction context matches the current authoritative choice/turn authority. History selection grants no command rights. Camera and non-spending inspection remain usable while waiting.

### 9.4 Party, initiative, character details and abilities

Party and initiative are distinct small portrait views. Clearly distinguish the inspected party member, the controllable entity and the current turn actor. Their HP/conditions/equipment/turn indicators update at displayed commits, not the newest received state. An authorized party audience shares witnessed actions across rooms; selecting another controlled body does not reconnect its stream. Undisclosed enemies do not appear through portrait bindings, and a dead/stale slot does not offer spending authority. Existing first-member keyboard shortcuts do not limit the full list.

An explicit focus gesture, including the existing portrait double click, centers the camera on the actor's presented admitted contact, without spending, acquiring authority or jumping to its future received location. Keep pinned shortcuts and melee/ranged preference per controlled actor during the session; changing inspected actor cannot overwrite another actor's choices. Carried-item actions remain inventory-driven. Session persistence is the demonstrated Pygame behavior, not a requirement for a new account/preferences API.

Expose the active actor's current action, bonus-action, reaction and movement resources with compact legible indicators derived from displayed native resources. Tooltips carry names and maxima. Spending, grants and expiry update at their corresponding presented commits; the UI does not independently apply action economy or add permanent explanatory text.

A compact recognizable End Turn control and the existing Space shortcut issue the same native end-turn intent once. They are enabled only when the displayed turn/context agrees with current admitted human input authority and there is no pending spending command or required catch-up. Neither history inspection nor an incapacitated/dead portrait grants authority. Typing in a field, a focused panel consuming Space, or Studio playback focus suppresses the gameplay shortcut. End Turn stays visible and usable without adding a text-heavy status panel.

The character sheet displays admitted species/background/class levels, abilities, proficiency, skills/expertise/saves, resources and equipment. This is inspection of existing character facts, not a new character-creation or leveling system.

The on-demand Abilities/spellbook panel supports search/filter of currently admitted spells/actions/items, their readable descriptions and real costs, selection of a legal family, and pin/unpin of supported shortcuts. It uses the current native action surface/category and exact reference. It does not reproduce the old action bar's many permanent filter rows. Abilities unavailable at the current displayed/authoritative state have a meaningful status rather than a fake flow.

The automatic-reaction panel exposes current disclosed triggers, costs and native enabled toggles. It does not invent reaction variants or preview hidden conditions. The current `game_obsolete/ui/panels.py` behaviors for sheet, ability library and reactions are required reference functionality; calling all three a generic details pane is insufficient.

An encounter has an intelligible finish. After its final admitted occurrence and feedback have been presented, show a compact dismissible/minimizable native outcome/reason; disable spending while retaining the final scene, camera, inventory/detail inspection and log. Receiving terminal state early does not skip the queued final attack/death. Only show victory/defeat when native data supplies that meaning: one observer's life state is not a team-result rule. Connection failures are distinct from a native terminal. This uses current terminal/session cleanup; it does not add a restart API, lobby, directory or statistics service.

### 9.5 Inventory and equipment

Recover the compact equipment-around-portrait and inventory-grid interaction, with search/filter/scroll and readable details. Preserve body-part, ring, melee-main/off and ranged-main/off slots rather than collapsing their meanings. Hovering or selecting a slot shows the disclosed compatible carried items from native compatibility information; it does not infer equip rules from artwork or item names.

Show actual quantity, charge counts, equipped state, effects and coatings. Equip, unequip, use, drop and loot issue the corresponding admitted native command once. The UI does not optimistically fabricate inventory results or wait for the renderer to become the rules authority. While a command is outstanding, stale repeats cannot spend again. Inventory, body equipment and owned item effects commit together on the presented timeline.

The same owned appearance survives equip/drop/loot/re-equip. Material effects are attached to their item/condition owner, not a shared cached body. Disclosed item statistics/descriptions remain native read-only facts. Missing/undisclosed inventory is represented honestly; the static media release is not an inventory source. Panel scrolling, selection and shortcut use cannot fall through to the world.

### 9.6 Combat log, tooltips and errors

Use one DOM combat log over the current typed subjective log data. Render and copy the recorded dice, modifiers, totals and outcomes; never reroll, infer or regenerate math. Movement legs and blood/deposit/tile children are grouped under their real causes. Event-time admitted names remain available for a known actor after death or sight loss. Reveal follows presentation time rather than racing ahead to received state.

The log is a readable aligned right sidebar with restrained transparent/glass treatment, no pointless empty margins and no movement of the action bar when opened. Recover fold/filter/follow, selection, clipboard copy and useful resize/lock behavior. Copy uses the same formatted row data as display. User scrolling suspends automatic following appropriately; new entries do not prevent reading older ones. A narrative renderer or another event formatter is not added.

Filters cover entry category and actor participation as source or target, preserving causal ancestors as context. Folding must not silently hide independently meaningful reaction/death/save outcomes. Retain global compact/detailed text with a per-row override. Copy the selected displayed substring/row or current filtered tree through the same formatter; latest-but-unpresented entries cannot leak through a separate copy path. Appending entries while the user is scrolled away preserves the reading anchor.

Where the current typed log admits them, expose actual advantage/disadvantage causes and ordered reroll/replacement/interceptor adjustments with recorded before/after totals and reasons. Do not infer adjustment history from the final die or copy the old HTML regex enrichment/objective-event fallback. Display and clipboard consume the same native typed values.

Delayed hover tooltips, pinning and clipped scrolling provide descriptions and details. Human-facing labels come from admitted descriptors or explicit presentation labels, not UUIDs, raw JSON paths or underscored identifiers. Diagnostic provenance remains available in Studio/diagnostics without leaking into ordinary HUD copy.

On-demand ground/environment inspection shows displayed admitted terrain, movement cost, effective illumination, tile conditions, visible features and known connector state. Condition details include their recorded descriptions and actually disclosed remaining duration. A pinned dossier refreshes on displayed commits even when the pointer stays still, and is cleared/restricted when its admission ends. Use an explicit inspection gesture/context that cannot first spend a movement click; copying an unsafe double-click fallthrough is not parity. Raw coordinates/directions/IDs belong in diagnostics. The old `itemDetails.ts` icon/name/position stub is not a complete inventory or environment interaction implementation.

Transient interaction errors report the native reason, expire or dismiss, and clear when intent changes. Expected command rejection is shown without crashing; programming/schema/resource failures retain useful cause and context rather than being swallowed by broad catch-all handling. Clipboard or browser permission failure is reported accurately rather than falsely claiming copy succeeded.

### 9.7 Complete interaction acceptance

Use the actual app, recorded events and real pointer/keyboard actions. These cases are current behavior obligations; they are not claims that every old native bug is still present.

| Case | Required result |
|---|---|
| Crypt play | Fighter and Sorcerer explore, open doors, loot, trigger a trap, split rooms and fight authored goblins; End Turn works from its compact control and Space with current authority. It is a playable encounter rather than a movement diagnostic. |
| Native route | Two doors and an ally corridor show the submitted route and its actually committed interrupted prefix. Known explored ground remains pointable. Shift changes the native preference and invalidates an old reply; preview and execution agree, including native normal fallback when safe is unavailable. |
| Four-camera interaction | The admitted door/item/prop set remains consistent; cutaway, Alt, thresholds and click-through agree with physical registration. |
| Actions and choices | Separate melee/ranged, one-click self action, one Dash family, upcast/wall/summon/element/conversion choice and unavailable-action behavior all use real native options. Overflow pages independently by group; visible-slot hotkeys never dispatch a former page/actor's action. Conditional facets and a reachable hover popup resolve actual rows without spending on intermediate choices. |
| Ordered targets | Repeated/fewer-than-maximum targets, undo and cancel preserve the native prefix; effective allocation badges match native completion. Explicit neutral positional options remain selectable without disclosing hidden terrain/elevation/occupants; displayed area/impact/route is the submitted preview. |
| Inventory and panels | Compatible-slot hover, search/filter/scroll, equip/use/drop/loot, sheet, ability search/pinning and reaction toggles function with the correct disclosed state. |
| Log | Exact native dice/modifiers, admitted adjustment history and retained names, grouped movement/blood, category/actor filters with ancestors, row/global detail and actual selection/clipboard copy work while animation plays. Appended entries preserve a scrolled reading anchor; copy cannot include future entries. |
| Async authority | Incoming operations, slow playback and loading do not freeze input, skip occurrences or allow a stale displayed control to spend a later turn. |
| Input ownership | Ctrl attack versus copy, Alt/Shift/focus loss, End Turn/Space versus typing and Studio playback, group/panel wheel/search, modal focus, actor selection and ordered Escape cancellation produce no duplicate/fall-through command. Cursors distinguish actual admitted hits without submitting commands. |
| Visual layout | Whole screens at 1280×720, 1920×1080 and the actual available monitor/DPR remain readable and coherent with log and inventory opened independently. No 4K acceptance claim without the display. |
| Lifecycle | Death, turn changes, temporary item/condition effects and ownership changes update portraits/bar/inventory/log at the correct displayed commits, including backward Studio replay. |
| Focus and inspection | Actor-local pins/weapon preference survive switching; portrait focus uses the displayed contact. Ground/condition dossiers update on displayed commits and admission changes. UI scaling does not alter world projection. Action-economy indicators show current native resources without permanent explanatory text. |
| Encounter finish | Terminal received during queued final damage/death waits for its presented completion. Compact result uses only native meaning; final scene/log remain inspectable and spending is disabled. No fabricated team result, restart API or statistics service. |
| Frame-time display | The toggleable real-play FPS/frame-time counter measures the same scene while panning/casting; it needs no alternate render path. |

Implement a compact toggleable FPS/frame-time display during actual play: visibility is the player's choice, but providing it is required. Use actual browser timings from the shared loop, not Pygame constants or a diagnostic-only renderer. The same instrumentation measures cold/warm startup, first/repeat interactions, camera movement and combined effects, separating native/network, browser reduction, resource preparation, compiler/sample and GPU work. No unspecified startup target, guessed memory quota, repeated full-suite ritual or prerecorded video substitutes for actual responsiveness and complete functionality.

## 10. Implementation sequence with concrete outputs

These packages describe dependencies and completed functionality, not serial permission gates. Independent UI/source-inspection work can proceed while geometry consumers are implemented. Use the complete production types/runtime from the beginning; an available family can run before another is finished without creating a second reduced release or demo renderer. The whole scope stays visible in the coverage matrix.

| Package | Concrete output | Actual dependency and completion evidence |
|---|---|---|
| N0 — source boundary and setup (partial: repository/artwork/core authoring prepared) | Existing source-only WSL repository; existing SDK imported; complete canonical export/type boundary; complete selected private installation | Copies and §6.1 assembly authoring complete; finish application integration. Real bootstrap/attachment/current operation/choice/receipt with configured CORS; source identities accounted for; clean source-only Git candidate. |
| N1 — common world and resource foundation | One projection/registration/support geometry path, depth/material/composition path, resource owner, presented picker and cutaway | N0 source data. Physically valid matched-family scenes from existing registrations; all four views, high/low supports and original art sizes. This package cannot close on flat floors and Idle/Run. |
| N2 — complete event playback | One reducer/compiler/sampler, durable intake, retained lifetimes, independent absolute clock, atomic displayed frame/HUD/log | SDK types and ordinary source recipes; geometry integrates as available. Every current fact branch classified; recorded causal prefixes, resource delay/backlog/reload and subjective replay behave correctly. |
| N3 — content and Studio | Every selected recipe/rig/environment/media binding supported; complete read-only layered timeline with source time and previews; full source/track inspection and manual-JSON reload | Shared N1/N2 runtime and canonical sources. Selected-identity matrix and actual source-edit/reload/source-semantic cases, including fixed rigs, item ownership and rare condition/removal paths. |
| N4 — playable encounter and complete UI | Fighter/Sorcerer dungeon and all current click/target/choice/inventory/log/party/reaction workflows | Native choices and displayed projection. Real browser use across exploration and combat; no fake controls or automatic wrong weapon/resource spending. |
| N5 — integrated repair and delivery | Full issue-indexed in-app review, measured startup/interaction/combined-effect behavior, repeatable launch/JSON-reload/install instructions | All functional coverage. Address real remaining failures, remove temporary competing code paths; final independent anti-slop and anti-OOP/ECS reviews. |

### Work order and what to do when one item is blocked

1. **Finish N0:** application scaffold, prepared schema/types and indexed release,
   installed media serving, current SDK connection. No copying or reauthoring work.
2. **Build N1 and N2 on those inputs:** registered world/resource/render functions
   and the shared stream/reducer/compiler/sampler. Integrate them continuously;
   do not finish a standalone world preview before connecting real event playback.
3. **Connect N3 and N4 as shared capabilities land:** full authored content and
   Studio tracks/inspection use the same path as playable interaction and UI.
   Start with available real recordings and the existing crypt configuration;
   additional family coverage fills the same production path.
4. **Finish N5:** close recorded client defects, exercise the complete playable
   encounter and Studio, and provide working launch instructions. Focused checks
   accompany each meaningful change; final integration does not replace them.

If one family or case cannot follow the agreed approach, apply the working rules
above: document it in §12 and select an independent ready item from these tasks.
Do not replan the architecture, touch the backend, build a substitute demo, or keep
circling that case. Deferred issues stay visible for discussion with the user and
cannot be counted as delivered. The same rule applies to review findings.

### N0 tasks and ownership

1. §6.1's narrow door/timber authoring connection is complete; no new asset intake. Reuse completed repository/reference/media setup in §1 and extend its existing package/lockfile. Install the current SDK package without copying its generated models. Add the ordinary application scaffold and static routes; keep source references read-only.
2. Use the existing passive owners and authored-schema export; `game_obsolete/presentation_export.py` remains the original seed/reference, not a second current producer. §5.1.1's initial replacement/relocation import is complete; consume tracked client authoring and complete the full release shape, existing release/catalog revision, resource descriptors and tool-only source provenance. No media-content hashing is required. Reuse the prepared installation, client section schemas and existing storage/geometry types; no engine-side field changes. No `SceneRelease`, reduced `Pick<AnimationData,…>` or hand-maintained client asset catalog.
3. Complete release indexing, resource dependencies and application loading in §5.4 over the already assembled client sections. Preserve accepted sheets and rates; do not re-copy artwork or rerun initial authoring import. Report unresolved references at their owning files; affected capabilities remain incomplete while unrelated consumers proceed.
4. Establish SDK worker intake, durable journal, one TS reduction and source-derived types. Exercise bootstrap, attach, content admission, legal choice/preview/command, receipt and reconnect with the existing server. Do not introduce new endpoints to avoid learning delivered ones.

### N1 tasks and ownership

1. Adapt source camera controls with one calibrated projection and inverse. Apply owner contact, pose/bank offset, source pivot/crop and elevation exactly once. Implement current world geometry from registered source data before judging draw order.
2. Register support, wall, aperture, stair/cliff and prop surfaces in the common draw/light/pick geometry. Use the explicit support-aware cutout policy for art without detailed geometry. Recover compatible assemblies/adjacency; do not introduce new arbitrary scenes to conceal a mismatch.
3. Build finite material operators, batching and solid/transparent composition. Integrate the accepted Fireball v4 math and other selected representations into this renderer, not a second proof app. Couple all planes and source interpretation to one resource owner.
4. Produce the valid in-app foundation set described in §11. Compare the recovered source registrations/order and available prior evidence for those same assets. Archived Pygame remains read-only; fixing its imports or restoring an executable Pygame app is not a prerequisite.
5. Use the displayed scene for picking and automatic wall cutaway. Camera intent, resources, draw state, light and picker publish together. Ordinary pan/zoom changes transforms rather than rebuilding/decompressing the scene.

### N2 tasks and ownership

1. Port current native reduction semantics and causal/retained presentation meanings into the one pure TS implementation. Enumerate the actual `PlayerFact` union; no default branch silently skips unsupported action families.
2. Compile occurrence/recipient/cause identity, body and all attached layers, trajectories, reactions, commit points and retained lifetimes. Missing parents caused by projection remain absent. A shared recipe is not copied per test case.
3. Latest reduction remains available for discovery and command admission; the displayed projection supplies every visible scene/HUD/log consumer. Pause/slow playback/resource waits do not block intake or advance one subsystem secretly.
4. Save exact SDK records before acknowledging consumption, retain started-operation timing and compatible checkpoints, and restore acknowledged-but-unplayed work after reload. Test offline playback after host history expiry and scope replacement during pending callbacks.
5. Load the first actual-server SDK recordings from §8.2.1 using these same functions. Timeline is a view over compiled channels. Do not implement a throwaway timeline, synthetic server-shaped input or temporary alternate event model.

### N3 tasks and ownership

1. Complete all R01–R23 consumers and selected identities, including non-modular creatures, modular equipment, spell materials, conditions, constructions, directed media, spatial interactions, blood/ground and all environment states.
2. Restore actual Studio features from the named Neuro Studio components. Implement the read-only source/track views in §8, inline field disposition and thumbnail lanes as views of the production result. Derived/native values remain read-only; source inspection must identify the fields that actually produced the displayed tracks and render result.
3. Exercise semantic motion/effect choices through actual source recipes. Shared gesture timings/sockets are authored once per animation/rig and reused; accepted effects are not redistributed arbitrarily to inflate variety.
4. Expose source identity/values alongside the compiled tracks. After a manual NDClient authoring JSON edit, assemble changed metadata and reload/recompile the same prerecorded case. Keep active release and candidate reload distinct until preparation succeeds. Do not build a browser editing/save API, draft framework or new rig authoring UI in this phase.
5. Use the actual-server SDK capture procedure in §8.2.1 for outcomes and lifecycle triggers. Write client-side SDK capture drivers/configuration using the supported existing setup fields; never synthesize client events or all-map observations. Selected-content coverage and meaningful server-recorded family cases are complementary; neither replaces the other.

### N4 tasks and ownership

1. Compose adapted Pixi and DOM widgets over shared displayed views. The UI requirements in §9 are the acceptance contract; choosing one old widget does not waive missing functions.
2. Implement exact SDK choice/preview/command gestures, variants and ordered targets. Keep action bar, inventory and world input ownership explicit. Legal self actions spend once; errors and unavailable actions do not open fake confirmation flows.
3. Launch directly into the authored dungeon and complete exploration, door/window/trap/loot, split-party views, inventory/equipment, melee/ranged, class abilities, spell choices and combat. Test the existing controller/AI configurations without inventing a lobby or seat cap.
4. Check entire screens and actual gesture sequences at supported sizes/DPR, including the current monitor. Verify readable text, consistent icon treatment, small portraits, stable bar and aligned glass panels together.

### N5 tasks and completion

Run focused tests after substantive changes, then the complete acceptance corpus once the required families are connected. Broaden/repeat only for changed behavior or real failures. Measure native/network waits separately from worker, journal, resource, sample, GPU and UI costs. Repair client bottlenecks in this phase; report native or SDK defects without modifying their owners. There is no SDK/type-generation dance around every test or asset edit.

Provide one working launch/install/edit workflow and an in-app case index for the full requirements. Remove superseded temporary parsers, reduced exports, debug defaults, duplicate formatters and preview-only executors. Do not delete source artwork/reference repositories to tidy the delivered code. Final reviewers inspect actual consumer coverage and exercised behavior; a test count, screenshot or build success is not a complete application.

## 11. Verification, visual scenarios and performance

Read `HOW_TO_TEST.MD` before writing implementation tests. Use existing native scenarios as setup/behavior references and actual-server SDK capture tools for Studio input. Keep exact delivered prefixes; do not import test modules into the application, wrap direct-engine sequences as invented transport packets or create a second rules generator. A new test must protect an actual semantic/geometry/lifecycle boundary, not mirror implementation details.

### 11.1 Physically valid visual case set

The user reviews these in the running application. All cases use source-compatible assets, known registrations and full physical enclosures where a raised area requires them. Distinct existing floor treatments identify upper/lower supports. An unknown disclosure boundary is not falsely built into a cliff. Whole-area construction references do not provide synthetic observations to Studio; gameplay scenes use the actual configured server audience. Source geometry overlays remain diagnostic inspection of those recorded scenes.

| Case | Required construction and result |
|---|---|
| Continuous flat room | Adjacent floor tops/skirts in varied insertion order; rotated cameras; original seams continuous; grid/path/AoE below bodies/walls; no ground fragments cutting through props or feet. |
| Matched wall assembly | Straight/corner/T/opposite-edge relationships within each compatible source family. A registered corner replaces only its matching contributors. No duplicated faces or mismatched heights. |
| All door families | Parent aperture, matching frame/insert/leaf, physical orientation versus bank pose, ground mount versus depth origin; inward/outward/open/close/break in four views. Include families with nonzero pose offsets. |
| Windows and wall inserts | Both wall orientations, nearby doors/corners, intact/broken parent and insert, consistent join and threshold. Same known interactive identity set across camera rotation. |
| Props and equipment | Chest, table, statue, multi-cell prop and dropped equipment; original pivot/overhang, no floor cut, no alpha halo. A large table is placed/rotated legally rather than shrunk into the room. |
| Enclosed raised room | Higher platform with every physically exposed side closed using valid cliff pieces, top-to-side joins/corners and stair returns. Different upper/lower floor art; actor/prop/wall at each support. |
| Stairs | Lower/intermediate/upper contacts, real tread/riser or registered face shape, correct width lanes, both ascent/descent and all cameras. No intermediate flat floor painted over flight art. |
| Overlapping elevations | A lower actor and a separate raised receiver/wall overlap on screen; own support precedence never makes the lower actor draw over a physically nearer upper floor. Ground feedback stays on its receiver. |
| Pose/size/flight | Original-size humanoid, explicitly enlarged animal, halfling/size effect if selected, prone/rest/death, jump and native wing flight. Sockets, gear, shadow and marker scale follow one chain; no standing revival in a prone death. |
| Attack and trajectory | Shortbow and modular ranged weapons; hand/weapon release contact, fixed-rig accent, moving target, elevated diagonal shot, all camera banks; residual rotation only where authored/allowed. |
| Volumes against surfaces | Selected Factory Fireball, Sunburst, Fog/Sleep and Globe with near/far sides, finite/L/angled walls, arch/window opening, upper receiver and overlapping bodies. Preserve source silhouettes; no tile-grid sawtooth or blast-centre hard shadow hack. |
| Effect depth and outcomes | Recorded wall versus open doorway, displayed break, full cosmetic plume at a dark boundary and existing suppression/cancellation. Actual damage/stage/lifetime follows received facts; unavailable provider/shell data does not produce an invented impact. |
| Transparency/light | Two intersecting transparent effects with a body/wall, grazing alpha edges, stable tie order, combined radiance/transmittance; whole Fireball receives light and emits independently through its authored envelope. |
| Blood/deposits/water | Concurrent impacts, fragments/vapor, airborne-to-ground continuity, wall/raised receiver, old versus fresh deposits, removal/seek/reobserve and existing liquid response without duplicate stain systems. |
| Camera/sampling | Pan/zoom/resize/DPR/rotate while idle, casting and reloading source data; no skew/non-uniform body stretching, unstable pixel scale, incorrect RGB data interpretation or alpha fringes. |
| Detailed condition/body phases | Finite application, loop crossfade and early removal, frozen pose, live copies, absence echo, historical trails and independently lasting feedback preserve source ages/owners. Head/helmet/crown/wings and owner-only appearance changes keep the current clip/frame without decorative hit targets. |
| Mechanisms, portals and prop retirement | A device uses its admitted elevated muzzle; an unseen source cannot leak through launch flashes. Transferring bodies/copies pass through registered local portal apertures without revealing the other room. Destroyed prop dust retains its silhouette while gameplay picking/blocking follows the native commit. |

Parameterize four views and appropriate elevations over shared cases instead of writing a new miniature map for each failure. Whole-area construction references use existing valid assemblies; every Studio gameplay scene uses actual server-delivered admitted facts, with no synthetic all-map observation exception. Unsupported genuine source registrations are named with affected bindings rather than disguised by guessed offsets.

### 11.2 Causal, resource and privacy cases

| Boundary | Required result |
|---|---|
| Native versus TS reduction | Same exact current records yield matching actor/world/audience observations, occurrence order, nested spatial commits, content admission, HUD/log and terminal state. Existing Python reducer is the semantic reference; no extra headless rules implementation. |
| Reactions and repeated targets | A/B/A, interrupted movement, lethal/nonlethal opportunity attacks and spell cancellation retain actual distinct occurrences and author-controlled release/contact/application timing. |
| Delayed preparation | Block one needed body/gear/world/VFX companion; old complete frame remains, intake continues, no hidden clock advances, then correct full frame appears atomically. |
| Backlog | AI advances while playback is paused/slowed. Every admitted turn plays when resumed, with displayed HP/light/equipment/log/portraits aligned; no jump to latest. |
| Reload/reconnect | ACKed unplayed records remain replayable; fresh SDK follower init0 is reconciled; running follower resumes consumed; displayed local time restores independently; duplicate/failed/missing history is handled truthfully. |
| Scope replacement | Switch audience/recording during fetch/SDK consumer/decode/upload; old private pixels/UI/picker clear immediately and late completions cannot install in the new scope. |
| GPU restoration | Context loss holds displayed time; current leased sources reupload with a new GPU generation; native rules/history are not restarted. |
| Command ambiguity | Lost submission reply queries/retries the identical numbered payload; no second spending action. Consumed cursor does not falsely imply confirmed host ACK. |
| Source reload | Manual canonical JSON edit/re-export/reload or failed publication retains an explicit candidate versus active release, correct pinned occurrence and unchanged media reuse; no browser save workflow is required. |
| Studio parity | Same record/release/time yields same scene with timeline open/closed and in play/offline Studio. Thumbnails use the actual sample mapping. |

### 11.3 What to measure and repair

Measure cold and warm separately: native process/import/content/encounter readiness; network/bootstrap/current SDK validation; worker reduction/compilation; journal writes and transfer; media request/decode/upload; main-thread sampling/submission; GPU passes; DOM/layout/input. A server warm cache across games remains server-owned; a responsive frontend does not make native latency disappear.

The first playable scene prepares only its actual dependency closure from the installed complete library. There is no boot-time art scan/hash/repack, whole-catalog texture decode, SDK generation or engine import. Native computation never runs on the browser render thread. SDK parsing/validation/reduction and ahead compilation are off that thread as specified in §3.2.

Measure idle, sustained WASD/pan/zoom, rotation with new genuine banks, first/repeated spell use, mixed-age Fireballs, queued AI, dense blood/ground, inventory/log changes and Studio source reloads. CPU and GPU timings, peak/decode/resident bytes, upload counts and repeated lifecycle ownership make causes inspectable. If GPU timers are unavailable, display “unavailable,” not a fabricated CPU-derived GPU number.

Fix actual repeated decoding/upload, geometry rebuilds, global dirty propagation, scene sorting, material compilation, widget re-layout or unbounded resident resources. Camera-only changes update transforms; operation changes invalidate only affected source/fact dependencies. Color swaps/rest-coordinate/material sampling belong on the GPU; no port of Python per-pixel arrays. Do not demand an optimization in advance merely to satisfy a made-up number, and do not accept persistent frame drops without tracing the stage that causes them.

## 12. Delivery status and acceptance language

Current checkpoint, committed in NDClient at `df5397e` on 10 October: **asset copying and
tracked authoring preparation, including the reviewed assembly connection, are
complete (§6.1).** The earlier premature closure was corrected by connecting the
actual values, not by treating source records as runtime data. **N0 remains
partial** for application setup/integration. Fresh Git repository, ignored organized
media, full selected Smallscale library, Fantasy environment/metadata, selected
UI assets, ordinary VFX, Factory replacements and tracked core authoring are
prepared. Initial ID/path/replacement linkage and its passive schema are done.
Environment, item/palette and UI section adoption is now complete, as are the
registered Goblin/Demon/animal authoring connections in §7.4. UI artwork retains
the two explicit, non-blocking artwork follow-ups in §5.7 (Skeleton Warrior
portrait and dedicated Unarmed icon). The assembler resolves 126,959 media references. Environment companion adoption
in §6.1 includes both companions and the completed door/timber typed mount connection. Fireball’s accepted demo world-light curve is now authored
on its existing impact storage; only its shared runtime consumer remains.
Other spell light curves are deferred until Fireball is tested in that shared
renderer, per the user's decision; no further emitter authoring is required to
close this pre-phase.
Remaining: connect release envelope/defaults, dependency indexing and TS types/loading, SDK/scaffold and application consumers;
N1–N5 remain planned. Existing backend/SDK/source and Fireball proof capabilities
are reference inputs, not evidence that the recreated application works.

**Uncertainties and blockers:** keep each new issue beside its existing capability
or in this section with: affected requirement/source; observed contradiction;
what remains incomplete; decision needed; and the independent task being continued.
Do not create another tracker or speculative repair plan. The accepted source
limits in §0.3 and deferred light/art work above already have a disposition; they
are not requests for new decisions or reasons to stop N0. No implementation is
started by this documentation update.

During implementation, keep evidence beside the corresponding row here or in the existing machine coverage report: source owner, implemented consumer, native/visual/interaction case, observed result and any exact remaining defect. Do not create a competing plan or replace whole-product status with the latest locally fixed screenshot. Existing catalog identifiers remain the coverage denominator.

Full completion requires the playable encounter, complete selected content, complete read-only Studio inspection and all interaction/ordering/history requirements. A disabled button, source JSON printed on screen, correct arithmetic without matched art, files copied without consumers, or a successful build is not completion. Show unresolved required failures honestly without relabeling the product complete; repair client defects in their existing owner and report any native/source limitation separately.

## 13. Complete production renderer capability coverage

This table replaces the implementation prescriptions in the older R01–R23 table.
The IDs continue to link the existing field/function ledgers to one delivery. They
are capabilities, not a requirement for 23 executors, event types or renderer classes.
“N3” means complete catalog coverage; it does not postpone every first example until
N3. Each capability first runs in the shared real-event path as its dependencies land.

| ID / capability | Current implementation responsibility | Decisive case / closure stage |
|---|---|---|
| R01 Camera/projection | Adapt existing camera/math; explicit world, support, source, camera and screen spaces; high-DPI and inverse picking | Four views of elevated contact, pointer zoom and negative coordinates; N1 |
| R02 Ground/world | Retained support/face geometry with current animated terrain banks; grid and feedback participate in physical order | Slopes, upper/lower floors, floor holes and grid below actors/walls; N1/N3 |
| R03 Boundaries/devices | Registered wall/door/window/prop/trap state and aperture geometry; displayed state commits update draw/pick/light together | Open, break, parent/insert destruction and threshold from four views; N1/N3 |
| R04 Body rigs | Shared modular/fixed clip sampler and layer operations; source frames, original accents, sockets, explicit scales | Every one of 44 rigs mapped; native wing flight, wolf 200%, prone death without standing; N3 |
| R05 Equipment/floor items | Existing item identity, attachment and material data; same owned appearance across locations | Coated/enhanced item equipped, dropped, looted and re-equipped; no ghost floor copy; N3 |
| R06 Palette/material | Finite shared GPU operations over isolated masks and authored donor textures; explicit override wins | Hand/Magic/Effect/external-VFX correspondence and item/body independence; N1/N3 |
| R07 Media/resources | Existing source registration, compact derived delivery specified in §6, shared source/region views and bounded readiness | Coupled crop/pivot/mask alignment, first-use, four-camera switching and unload; N0/N1/N3 |
| R08 Projectiles/beams | Absolute path/socket sampling, bank plus permitted residual alignment, release/arrival and child application timing | Oblique elevated Fireball/rays, beam source continuity, Magic Missile A/B/A, interception; N2/N3 |
| R09 Areas/volumes | Compact registered geometry, received ownership/suppression, support/aperture and transparent composition; no floor-visibility stencil | Continuous Fireball/Sunburst/Sleep, inside/outside actors, received suppression and elevated surfaces; N1/N3 |
| R10 Layer/blend ordering | Shared physical composition with stable ties, sibling order, normal/add/screen and complementary samples | Two transparent volumes and a body, checkerboard alpha, near/far crossing; N1/N3 |
| R11 Directed materials | Finite authored ribbon/mesh/plasma operators and donor sampling | Existing noise ribbon, darkness mesh and plasma trail with moved/raised endpoints; N3 |
| R12 Constructions | Source-authored paths/sections/rings/domes and formation/retirement commits | All installed wall types, arbitrary permitted angle, fire hot/safe side and dome destruction; N3 |
| R13 Particles/trails/intake | Analytic seeded tracks and bounded shared geometry; item/weapon/body attachment follows presented sockets | Blood/bone/vapor, critical/multiple victims, weapon trail, orbit/intake and backwards seek; N3 |
| R14 Conditions | Current owner/phase/suppression data, shared body/ground effects and head-only marker playlist | Multiple owners, size variants, suppressed expiry/removal; no overlap or body-VFX rotation; N3 |
| R15 Owned lifetimes | Shared retained item/spatial/concentration state with occurrence identity and cold-acquisition rules | Suppressed Shield expires; re-observation is not reapplication; removal retires only its owner; N2/N3 |
| R16 Movement/portals | Received legs/modes/connectors with reaction holds, relocation/absence and ground-to-ground flight | Ally corridor, jump/window, interrupted movement, ledge landing, one-end portal visibility; N2/N3 |
| R17 Feedback/lifecycle | Actual damage/heal/save/temporary-HP/death/summon facts revealed at authored contacts | Lethal OA at doorway; sleep/rest/death; summon/despawn/hostility and real blood impacts; N2/N3 |
| R18 Deposits/ground/water | Native contribution ownership; receiver-local settled coverage and finite changing materials | Fresh/old stains, wall soot, raised floor, response/removal, witnessed break, rewind; N3 |
| R19 Spatial contacts | Recorded entry/exit/activation/response facts resolve existing recipe primitives | Hot-side spread before feedback, ignition/extinguish already implemented, suppression; N3 |
| R20 Temporal orchestration | One typed reduction/index, causal compiler, retained facts and absolute sampler; no animation-owned gameplay | Delayed resources, slow/pause, queued AI, reconnect/reload and historical scene/HUD/log agreement; N2 |
| R21 Picking/highlights | Presented supports/physical masks and common transform/occlusion/cutaway policy | Known door/item set stable across cameras, click through cutaway, Alt, Ctrl attack; N1/N4 |
| R22 Player UI | Recovered/adapted Pixi widgets and DOM text panels on shared displayed views and exact SDK gestures | Complete interaction matrix, four bar blocks, multi-target/variants, inventory, copied exact log; N4 |
| R23 Studio/capture/replay | Same production runtime, actual SDK recordings, canonical source inspection/manual reload and optional capture | Load/seek/inspect actual spell/action/condition/rig/world case; manual JSON reload uses the same production compiler; N2/N3/N5 |

Lighting spans R02–R06/R09/R18/R21 rather than becoming another world simulation.
Recorded categorical effective light is smoothed only across admitted compatible
supports; body/item receiver treatment, emitters and head/UI exemptions follow
§6. Existing audio, if selected in current registrations, follows
the same contact/lifetime clock and resource owner; seeking does not replay all past
one-shots. No new sound content or independent audio-event schema is implied.

All selected identities remain required, including aliases and rare outcome paths.
An example proves its capability; catalog mapping/semantic validation establishes
that every selected recipe and rig has a supported consumer. Both kinds of evidence
are needed. An explicitly supplied new delivery updates the existing family inventory once.
Do not automatically expand scope by continuously scanning unrelated upstream changes.

## 14. Complaint and requirement closure — migration versus existing parity

### 14.1 Migration-specific requirements and failures

This table covers all 55 entries in the migration-only post-mortem ledger. Number references identify those existing entries, not new incident claims. Earlier Pygame behavior belongs to the separate parity table below. Historical stops, deletion and review failures become working constraints, not obsolete runtime features to implement.

| Migration ledger entries | Required correction in this implementation | Evidence that closes it |
|---|---|---|
| 01, 07, 21, 51 | Recover full spell/action/condition/fixed-rig Studio on current actual events, with every authored channel, frame previews and proper source/resolved timing | Complete read-only Studio stream/track/source inspection and inline field ledger, not colored bars or a JSON inspector |
| 02, 03, 12 | Selectively recover working NeuroClient capabilities in a new clean repository; neither wholesale old architecture nor tiny rewrite that discards features | Named source-to-new-consumer mapping for camera, grid, HUD, inventory, timeline and inspectors |
| 04, 15, 23 | Use checked Pixi APIs and finite data representations suited to the effects; Godot supplies offline data | Component decisions and actual shared-source/batch/material/resource implementation |
| 05, 08, 30, 37, 45, 48, 49 | Use composition roles AND receiving supports/elevations AND physical depth, with authored faces/contacts; floors cannot cut feet, props or reactions | All layer/elevation scenarios in §11, arbitrary insertion order and four cameras, verified registrations |
| 06, 16 | Shared physical geometry for depth/light/picking; native effective-light/disclosure data remains authoritative | Wall/arch/raised receiver, source-depth, receiving/emitting and hidden-provider cases |
| 09 | Display cursor independent of native progress; every admitted event can animate | Pause/slow/queued-AI/backlog/reload cases with HUD/log/world at the same displayed time |
| 10, 11 | Compact GPU representation for all effects including blood/ground, without Python pixel arrays or copied CPU algorithms | Combined effects and landing/deposit cases with attributed CPU/GPU/resource measurements |
| 13, 25, 26, 27, 39 | One complete, source-grounded implementation specification and honest reviewer verdict | This file contains the actual decisions and feature coverage; no required companion chapters or inherited readiness claim |
| 14, 18, 19, 20 | Keep accepted Fireball v4 and bounded demo findings, real assets, source timing and independent receiving/emission | Shared production integration with walls, openings, reach and other effects; no claim that the earlier prototype proves the whole client |
| 17 | Do not crop admitted isometric art with missing cells or a hard tile mask; physical camera depth is separate from gameplay reach | Dark frontier, nearby wall, open doorway and decorative-overhang cases without visibility-stencil cuts |
| 22, 24, 53 | Repo/ignore rules, selected copies and core authoring linkage are complete; finish SDK/full release/application integration | Reuse installed folders and tracked authoring. No repeated Git creation or copy campaign; installed/consumer/inspection coverage stays distinct |
| 28, 29 | Remove speculative constraints and validation loops; complete required work with meaningful checks | No invented packing/time/byte gates or per-edit SDK regeneration; measured changes have a specific reason |
| 31 | Prevent local-fix overfocus from replacing the full delivery | N0–N5 and complete R/UI/Studio coverage remain visible; status states exact completed and remaining capabilities |
| 32, 34 | Remove unauthorized cosmetic scaling and own assistant-authored mistakes | Scale decomposition shows source calibration, explicit accepted appearance and actual size effect exactly once; no 90%/110% class multipliers |
| 33, 41 | Use physically valid, enclosed raised examples and readable high/low support treatments | Real compatible cliff/stair side returns and top joins, distinct existing floor materials, all cameras |
| 35, 36, 42 | Read existing art studies and match door/wall families, offsets and adjacency before inventing placement | Same registered input compared with working source renderer; all family-specific mounts and pose offsets consumed |
| 38, 43 | Read the full relevant plan/source and incorporate new evidence durably | Current requirements updated in this one file; source handoff values reach the actual consumer, not only commentary |
| 44 | Review via running app | Reproducible launch plus navigable Studio cases; no forced export-video review workflow |
| 46 | Correct projectile launch/alignment and fixed-rig layer meaning; no camera morphing | Real shortbow release socket, declared source bank, original goblin accent and four-camera path alignment |
| 47, 48 | Correct camera/DPR/sampling and alpha conventions; preserve sprite proportions and edges | Smooth pan/resize/zoom with original scale, no chest halo or non-uniform transformation |
| 50, 52, 54 | Honor stop/deletion boundaries | Planning does not inspect or recreate the deleted application; future implementation starts only when authorized |
| 55 | Keep phase and evidence scope correct | Migration complaints above, previous-system parity below; no unsupported deleted-code diagnosis presented as fact |

### 14.2 Earlier-system parity requirements for the new client

These outcomes were requested while developing earlier renderers and remain required app behavior. They are not a claim that every original native defect is still open. Consume current implemented native behavior. A newly demonstrated native defect is reported separately; this plan authorizes client implementation only.

| ID | Required result in NDClient | Principal proof boundary |
|---|---|---|
| P01 | Two opened doors and an ally in the corridor do not route into a corner | Native preview/committed path + live click |
| P02 | Visible path is the submitted route; interruption shows its committed prefix | Native route + presentation |
| P03 | Pass through allies, finish on an admitted free destination | Native movement + presented overlaps |
| P04 | Walls covering visible ground fade automatically and allow intended picking | Rendering/picking |
| P05 | Cold/warm startup prepares the actual scene closure without library scans or avoidable main-thread stalls; stages and remaining latency are measured | Server/import, release/decode/upload and browser stages |
| P06 | Continuous WASD/pan/zoom/rotate does not rebuild or decode the scene | Interactive frame profile |
| P07 | Disclosed enemy initiative entry has the correct portrait | Admitted identity, binding and historical HUD |
| P08 | All projectile families select direction and align to travel; authored speeds make sense | Four-camera oblique/elevated real-event cases |
| P09 | Hand/cast material matches the resolved spell palette unless explicitly overridden | Shared source material and visual comparison |
| P10 | Native AoE/path/impact preview is visible and matches the command | Preview, geometry, ordered target input |
| P11 | Required readable FPS/frame-time diagnostics work during actual play; the player can hide them | Browser instrumentation |
| P12 | Configured native Windows server and WSL client are independently launchable | Existing Windows uv host, browser/CORS/stream integration; no Pygame dependency for client |
| P13 | Wall-edge door is operated from native incident supports, not an extra tile ring | Affordance, approach and execution |
| P14 | Admitted explosion/cloud art stays continuous without revealing hidden gameplay | Volume ownership/disclosure + physical composition |
| P15 | Useful inward/outward zoom keeps pointer anchoring and respects UI wheel capture | Browser input |
| P16 | Selected ranged attack uses the appropriate body/weapon action | Modular ranged regression even with goblin encounter |
| P17 | Playable crypt uses authored goblins with exploration, loot and traps | Whole encounter, not gallery |
| P18 | Known explored ground remains navigable without current sight | Remembered-support picking + native knowledge preview |
| P19 | Legal self-action takes one click; unavailable actions cannot enter targeting | Current native choice/lease and input |
| P20 | One Dash verb with native permitted resource alternatives | Action grouping without changed action economy |
| P21 | Known victim's name survives opportunity-death and turn end | Event-time identity in typed log/history |
| P22 | Camera rotation cannot change the known interactable set | Door/prop/item coverage, Alt and point picking |
| P23 | Visible door's admitted threshold is readable without revealing the next room | Support registration/disclosure/light |
| P24 | Interaction errors are meaningful, expire/dismiss and clear on new intent | Transient UI state |
| P25 | Attack roll values/modifiers are the recorded native math, not test dice or rerolls | Native-recorded-to-rendered/copied log |
| P26 | One authorized party view includes allied witnessed actions across rooms | SDK audience + displayed scene, portraits and log |
| P27 | Native processing, decoding and queued AI never freeze camera/input or skip turns | Independent stream, clock and stage timings |
| P28 | One intentional spending gesture; UI clicks cannot fall through into world commands | Pointer capture, focus, stale preview cancellation |
| P29 | Grid/path/AoE sit on actual supports between ground and occluding geometry | Multilayer projection and ordering |
| P30 | Haste potion/inventory updates cannot erase a retained companion contact | Scoped reduction prefix + presented actor |
| P31 | Zero-HP actors do not receive a spurious actionable human turn | Native life/turn admission + historical controls |


### 14.3 Authored spell/action/condition behavior that must survive the migration

These are explicit current regression/authoring cases derived from the user's accepted direction. They are not an instruction to reopen every accepted spell or reintroduce earlier abandoned mechanics. Confirm the current canonical recipe/native fact and preserve it through the new shared consumer.

| Family / case | Required current behavior and what Studio must expose |
|---|---|
| Motion/effect semantics | Special1 is a kneeling/open-arms invocation suited to sky/release; Attack4 is ground contact; Attack5 is a pointing release; Attack6 can be thrust/beam; Attack3 is bow-like and reserved for compatible arrows. Source animation keypoints/sockets drive reuse. Source labels constrain assignments; combinations are not selected randomly for diversity. |
| Allowed modular effects | Effect4/5 supply palette-colored casting aura. Effect1 on Attack5/6 is comparatively delicate; Special1/Attack4 carry larger ground effects. Effect2 is intrusive except the more usable Attack6 and conditional ground/invocation uses. Effect3 Special1 is useful; its ground-heavy Attack4/6 require compatible intent; Attack5's skeleton was reserved for Blight in the accepted direction. Preserve reviewed canonical assignments and make every contributing layer inspectable. |
| Electricity | Shocking Grasp, Lightning Bolt and Chain Lightning use their resolved source palette, not an invented yellow overlay. Hand/body/external media correspondence, source socket, beam continuity and bank/tangent alignment are visible in Studio. |
| Barkskin / warm shields | Cast layer uses the resolved recipe/material rather than an unintended white default. Persistent body/material and cast are separately owned but visually consistent. |
| Produce Flame | The user's later damage-only implementation supersedes the earlier request for a held flame. Preserve that current backend/action presentation; do not restore a fake persistent hand-flame condition merely to satisfy the older complaint. |
| Grease / sleep / prone | Native triggers and resulting prone/sleep/life state drive the appropriate entry/rest/recovery poses. Eyebite sleep is not displayed as an upright pseudo-condition. No renderer recomputation of saving throws or status rules. |
| Frightened / exhaustion / debuffs | Use the delivered overhead marker artwork and current native identities, with restrained animation and no wiggle. Marker dimensions follow accepted blindness/deafness sizing. Cycle only head markers; do not rotate/remove body/ground effects. No invented Hunter's Mark condition or reintroduced removed grapple mechanic. |
| Slow / reduced movement | Slow spell condition and movement-speed reduction such as Ray of Frost retain distinct icon bindings and real triggers. Do not collapse them by similar prose. |
| Curse / hold | Application contact timing and body-centered cage/chains follow authored anchors; test different creature sizes with the same attachment policy, without slow arbitrary reconnection. |
| Hypnotic Pattern | Preserve its current authored ground persistence/rotation and native lifetime instead of treating every media source as a disposable projectile strip. |
| Walls / ground spells | Source gesture semantics support actual ground strike where authored. Construction formation/retirement and native walkable/visible/light commits align with authored timing rather than latest-state arrival. Use higher-level effect layering only where the reviewed source actually selects it. |
| Sunbeam / Sunburst / Fireball | Source release from correct hands/anchor at the right phase; whole dome/burst art remains continuous and physically ordered. Use the selected Factory Fireball and retain the proven depth/normal/light treatment; do not restore the earlier clipped fallback. |
| Scorching Ray / Eyebite / missiles | Correct directional source choice AND permitted residual orientation; real release/travel/impact timing, repeated recipients and damage-reaction transition. Source FPS, body rate and travel duration are distinct inspectable values. |
| Power Word / necrotic outcomes | Actual damage/death/blood/remains response uses native facts and the selected recipe; no universal skeleton overlay or missing impact hidden by a generic cast effect. |
| Dimension Door | Source entry/absence/exit timing follows the authored paired-endpoint sequence, with no unnecessary gap; only admitted endpoints render. |
| Condition provenance / Antimagic | Suppression, expiry and removal retain causal owner identity. Expired suppressed Shield never revives, Guiding Bolt mark obeys actual suppression, and hidden providers do not leak via the effect. |
| Equipment and body material | Owned item visual modifiers do not contaminate cached body materials or vanish on drop/re-equip. Real item identity, sockets, palette/material and source layer masking are separate. |

### 14.4 Current interface/design constraints remain product requirements

Small party/initiative portraits; four minimal icon blocks with multi-row support; no automatic weapon selection; same-sized hover choices and minimal level selection; glass/transparent readable log, inventory and details; bar position unchanged by panels; readable antialiased text; no needless margins or permanent explanatory text. Full inventory/sheet/abilities/reactions and exact typed combat-log math are specified in §9. These cannot be replaced by a visually minimal diagnostic screen with missing functions.

### 14.5 Executable-source parity scan — 9 October 2026

After consolidating the plan, three reviewers and the primary agent compared it with the current Pygame implementation, the surviving old NeuroClient checkout (`/home/tommaso/Dev/NeuroClient`, inspected HEAD `d274f2d`) and current server/SDK capture paths. This was an executable-source/wiring comparison, not another reading of feature titles. No deleted NDClient files, other chats or runtime were inspected. A gap here means a missing or insufficiently specified requirement in the plan; it is not a claim that a new client has been implemented or tested.

| Actual source checked | Concrete additions/disposition in this edition |
|---|---|
| `game_obsolete/encounter_play.py`; `game_obsolete/ui/{hud,action_bar,variants,targeting,layout}.py`; `game_obsolete/controls.py` | §§9.2–9.4 now specify contextual cursors, action-economy indicators, independent block paging/current-slot hotkeys, conditional/reachable hover facets, neutral native positional targets, effective allocation counts, actor-local preferences, focus gestures, Escape precedence and independent UI scale. These remain functions/state in existing input/layout owners. |
| `game_obsolete/ui/{combat_log,panels}.py`; old `ui/{eventSidebar,combatHistoryPanel,tileInspector,conditionTooltip}.ts` | §9.6 adds category/participation filters with causal context, per-row/global detail, displayed-only selection/copy, stable reading anchors, typed roll adjustment history and displayed-time tile/condition dossiers. One log formatter; no narrative or objective-state fallback. |
| Pygame `settled_end`; old `render/clips/EncounterResultClip.ts`, `ui/encounterResultShell.ts`, `engine/encounterResult.ts` | §9.4/§9.7 require the final queued outcome to be presented before a compact native terminal notice, with continued non-spending inspection. No old directory, summary or observer-survival-as-victory rule. Real-play FPS/frame-time display is required, though visibility is optional. |
| Old `ui/targeting.ts`; current `dnd/player/{commands,session}.py`, `server/{protocol,worker}.py`, both SDK echo checks | The delivered selection now includes `prefer_safe`; §4.8/§9.2 consume it for preview and submission without another API change. No second route solver or wire envelope. |
| `game_obsolete/{condition_sampling,condition_media_lifetime,absence_media,body_history,feedback,animation_draw,environment_animation}.py`; old `AnimatedEntity` and `ConditionOverlayController` | §6 explicitly retains application/removal/loop phases, early-removal source age, live copies/frozen poses/absence, historical trails, finite activity/life filters, independently lasting feedback, source-bound label layout, current appearance recomposition and environment endpoint frames. No extra actors, snapshot restoration or per-effect state machines. |
| `game_obsolete/{mechanism_projectile,portal_draw,object_dust}.py` | §6/§11 add world-muzzle trajectories, actual local portal-aperture body clipping and silhouette-based prop retirement to existing projectile/geometry/particle consumers. |
| Old `ui/{SpellStudioPreview,ActionStudioPreview,conditionStudio/ConditionStudioPreview}.ts`, `ui/studio/{StudioScenarioCompiler,StudioEvidenceWorkspace,StudioPlayerReplayImport}.ts` | The wired legacy previews manufacture frame-shaped data; SDK assertion is not server provenance. Recover useful timeline/thumbnail/inspection/replay-import behavior, not those generators. §8.2.1 requires exact current host→SDK captures, offline replay and shared production consumers. |
| `devtools/player_server_acceptance/{fixtures,run,http_run,http_performance,combat_http,python_player,crypt_player}.py`, `typescript_player.mjs`; `devtools/animation_review/{produce,capture}.py`; `devtools/export_world_authoring.py`; `dnd/player/recorded.py` | Existing real-host fixtures/drivers are usable capture foundations. Direct-engine reduction sequences and synthetic all-map authoring exports are not equivalent evidence. §8.2.1 distinguishes them and specifies client-side drivers over supported current configuration for missing recordings without a new transport, provenance service or mandatory benchmark ritual. |

The wider scan also checked old camera/focus/viewport, grid/target feedback, static-board invalidation, modular rigs/equipment/anchors, conditions, recoloring, inventory/abilities/initiative, Studio lifecycle/transport/source coverage and connector/item details. Their applicable feature families already have owners in §§4–9 and R01–R23. The scan does **not** certify every legacy implementation as correct or suitable to copy. Old planar `worldDepth` bands/hash ties do not solve elevated physical composition; flat grid and latest-state picking are superseded. `connectorPresentation.ts` draws retained endpoint lines with interaction disabled, so it is not complete connector traversal. `itemDetails.ts` is a small presentation stub, not full inventory. Old maximum-target auto-submit, positive-only camera bounds, large portraits, opaque panels, actor classes/FSMs and captured previous-visibility closures must not override the current plan. Creation/lobby/directory products stay excluded.

Depth/normal material planes, physical VFX/wall composition and receiving/emitting light remain new capabilities specified in §§5–7; this parity scan does not demote them to whatever the older renderers could do. Likewise, source identity/consumer coverage and server-recorded behavioral cases are complementary: existing actual-server captures cover a subset, not every installed spell, condition, rig and environment state. N2/N3 extend those cases through the real server as their consumers land. No claim of an already-complete capture corpus is made.

## 15. Review responsibilities and recorded disposition

### 10 October scope cleanup

The primary agent checked the plan for direct and indirect requirements to modify
engine/server/SDK code, undeclared inputs and choices deferred until implementation.
Anti-slop and anti-OOP/ECS reviewers independently cross-checked those boundaries;
the plan-adherence reviewer checked that this edit remained documentation-only.

Current preparation results remain in §§5–7/12; historical test counts are not
acceptance of an unbuilt client.

The corrections remove backend implementation and regeneration tasks from setup,
rendering, Studio capture, acceptance and delivery criteria, not just their original
chapters. Current SDK movement preference is an input, client authoring schemas
already live in NDClient, and archived renderers remain read-only references.
§0.3 records existing inputs and accepted limits; it does not create another phase.

During implementation, keep a plan-adherence sub-agent focused on the full delivery.
Use anti-slop and anti-OOP/ECS reviews for concrete ownership/duplication defects;
rendering and UI reviews inspect real consumers and behavior. Findings identify
an actual contradiction or failing case. Review only changed requirements and
identified defects; no repeating certification, checksum or SDK-regeneration cycle.
No review finding authorizes a backend expansion or an improvised workaround.
For noncritical uncertainty, record it and continue known planned work; discuss
a necessary design change with the user before implementing it.

Final targeted readback found no remaining backend-work obligation in this
cleanup. Anti-slop/adherence findings corrected accidental prose path replacements
and a stale instruction to repeat calibration authoring. The ECS review confirmed
that current event lifetimes, depth/lighting, geometry and the shared play/Studio
path remain required. Local document links and removed-section references were
checked; the NDClient copy matches this master. These are documentation checks,
not runtime tests or a claim that every unbuilt component has been validated.

This document update is not a runtime, visual or performance acceptance result.

## 16. Source/API evidence and scope boundary

Existing repository source and the user's explicit requirements are authoritative inputs. The preserved original and historical companion files explain provenance; this consolidated file owns current execution instructions. The post-mortem is migration-only. Do not read other chat threads or contact artwork threads as part of implementation; refer to the supplied source handoffs.

Current official Pixi documentation was rechecked for the implementation choices below. Pinned local API source at `agent_docs/references/pixijs-8.22.0-20261008/` resolves discrepancies in moving guide examples.

| Component | Official reference and implementation consequence |
|---|---|
| Loading and texture views | [Assets](https://pixijs.com/8.x/guides/components/assets) and [Textures](https://pixijs.com/8.x/guides/components/textures): reuse loaded sources and frame views; extend numeric-plane parsing deliberately. Promise-based loading does not imply CPU work is off-thread. |
| Layer roles | [Render Layers](https://pixijs.com/8.x/guides/concepts/render-layers): control ordering separately from parenting; this does not supply world elevation or intersecting-volume depth. Restore layer attachment deliberately after removal. |
| Physical geometry/materials | [Mesh](https://pixijs.com/8.x/guides/components/scene-objects/mesh): use explicit geometry/shaders/state and group compatible draws. A custom mesh does not automatically batch like ordinary sprites. |
| Composed effects | [Filters](https://pixijs.com/8.x/guides/components/filters): reserve composed-image passes for effects that need them; source-local palette/mask treatment lives in shared material shaders. |
| Time | [Render loop](https://pixijs.com/8.x/guides/concepts/render-loop): application presentation time is explicit; do not equate ticker elapsed time, source FPS and server progress. |

Do not upgrade/rewrite the architecture just because a guide offers a new feature. Use existing engine APIs, current source registrations and the finite renderer defined here. The future app remains one browser client plus development-only canonical authoring tools and the existing native server.

Whole-world native save/load, a new account/lobby/campaign service, new spell rules, new surface chemistry, arbitrary stacked walkable supports, new AI and new artwork commissioning are not silently added. Retained subjective recordings and manual canonical source editing and explicit reload are required and fully specified. A real limitation in native/source data is reported with its binding and supported behavior, not hidden behind guessed art or a second runtime model.
