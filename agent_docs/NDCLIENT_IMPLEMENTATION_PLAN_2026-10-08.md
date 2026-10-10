# NDClient — complete client and authoring implementation plan

Date: 8 October 2026. Source baseline: engine `804b0f7e073`.
Status: **the human resumed foundation repair later on October 8; review in the running app, not exported screenshot/video galleries**.
This resumption supersedes historical stop language below. Source constraints and
withdrawn readiness/acceptance claims remain unchanged. Begin with foundation A0–A4.
The [asset recovery handoff](NDCLIENT_ENVIRONMENT_ASSET_RECOVERY_HANDOFF_2026-10-08.md)
now precedes foundation implementation. It records the rejected arbitrary wall/door
pairing and the existing assembly/adjacency records that must be recovered.
The earlier implementation-ready verdict is withdrawn.
The animated-wall author's [positioning notes](PIXI_WALL_DOOR_ELEVATION_POSITIONING_HANDOFF_2026-10-08.md)
are incorporated into asset recovery §3.5 and foundation A0–A4: compatible source
assembly first, then exact owner/pose/base/contact registration and matched
Pygame/Pixi comparison before depth diagnosis. These corrections supersede any
generic placement assumptions below. Earlier reviews do not certify this amendment.
The immediate work is the [foundation repair plan](NDCLIENT_FOUNDATION_REPAIR_PLAN_2026-10-08.md).
It takes precedence for repairing the existing setup before wider N0–N5 work
resumes. The complete release and partial client exist, but the reported raised
world/door placement and reviewed lifecycle defects are not accepted.
The [post-stop review](audits/ndclient-implementation-20261008/REVIEW_AFTER_USER_STOP.md)
is the current implementation assessment; §0.3 records the earlier scaffold stop.
No implementation resumes merely because a plan review approves the design.

The documentation cleanup removed speculative budgets and unnecessary prerequisites.
Those remain removed. Correctness and complete delivery remain the objective;
N0–N5 are the full scope, not serial approval gates. The repair phase is not a
replacement demo or a claim that incomplete content, Studio or UI is delivered.
Earlier anti-slop and anti-OOP/ECS/DAG/privacy reviews covered the design, including
§0.4 and the required chapters. They did not establish a measured basis for the
resource quotas or prerequisites removed here. Review approval does not approve
the scaffold, certify runtime behavior or resume work. Findings and verdicts are in the
[review receipt](audits/ndclient-plan-20261008/PLAN_REVIEWS.md).

This is the current client plan. It supersedes the client destination and delivery
sequence in [the October 7 plan](NETWORK_SERVER_NEUROCLIENT_STUDIO_PLAN_2026-10-07.md).
The current R01–R23 operation obligations and P01–P31 complaint mapping are assembled
in §§13–14 below. The older source/function ledgers remain evidence, not instructions
to translate Python algorithms. The implemented server's
[closure receipt](audits/server-implementation-20261007/WARM_WORKERS.md) is the
server status; historical planned endpoints are not a competing API specification.

## Reading and execution contract — one plan, linked technical chapters

This document is the entry point, scope, dependency order and completion contract
for the entire next phase. The linked chapters are part of this plan, not independent
alternatives or optional follow-ups. No requirement needs to be recovered from chat.
The consolidated review receipt names the exact documents reviewed together.

| Required chapter | Owns the detailed decision | Delivery stages |
|---|---|---|
| [Immediate foundation repair](NDCLIENT_FOUNDATION_REPAIR_PLAN_2026-10-08.md) | Current stop, source-grounded geometry/appearance repairs, shared clocks/resources/scope, actual visual evidence and independent reviews | Before wider N0–N5 work resumes |
| [Environment recovery handoff](NDCLIENT_ENVIRONMENT_ASSET_RECOVERY_HANDOFF_2026-10-08.md) and [source positioning notes](PIXI_WALL_DOOR_ELEVATION_POSITIONING_HANDOFF_2026-10-08.md) | Compatible assemblies and adjacency; exact owner/edge, frame/bank pose, height, stair/cliff contacts and source registration; limitations distinguished from proven failures | Incorporated into the resumed foundation A0–A4 |
| This master, §§1–16 | Scope, module boundaries, stream/history, release, Studio/UI, complete work list and acceptance | N−1–N5 |
| [NeuroClient/Pixi component review](NDCLIENT_PIXI_NEUROCLIENT_COMPONENT_REVIEW_2026-10-08.md) | Existing source to retain/adapt/replace and official API checks for each component | All |
| [Media representation](NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md) | Selected compact colour/geometry fields, blood/landing/ground algorithms and implementation acceptance | N−1, integrated N1–N3 |
| [Occlusion mathematics and Pixi execution](NDCLIENT_OCCLUSION_MATH_AND_PIXI_2026-10-08.md) | Surface depth versus volume distribution, finite shader/pass design, shared wall/light geometry, silhouette preservation, Globe/Antimagic and lighting-library study | N−1, integrated N1–N3 |
| [Fireball export and interactive proof handoff](FIREBALL_SINGLE_VIEW_PIXI_HANDOFF_2026-10-08.md) | Human-requested single-view, 24 FPS, two RGBA8 planes per depth layer; local depth peeling; mouse casts with floor/wall/Globe/light interactions | Existing bounded proof; N1 integration reference |
| [Actual Fireball proof receipt](audits/ndclient-plan-20261008/FIREBALL_PROOF.md) | Delivered demo, measured depth/light behavior, rejected cutout, remaining contact/streaming work and source fingerprints | Completed subset of N−1; N1 integration reference |
| [Depth/material/light design](NDCLIENT_DEPTH_MATERIAL_LIGHTING_2026-10-08.md) | Coordinates, elevation, composition, palette/material, lighting, picking/cutaway | N1–N3 |
| [Assets and rig authoring](NDCLIENT_ASSETS_AND_RIG_AUTHORING_2026-10-08.md) | All selected art, modular/fixed rigs, environment, source preservation and inspectors | N0–N3 |
| [Interaction parity](NDCLIENT_INTERACTION_PARITY_2026-10-08.md) | Each player gesture, native preview/command boundary and usability check | N2, N4–N5 |
| [Authoring field ledger](NEUROCLIENT_AUTHORING_COVERAGE_2026-10-07.md) and [nested source inventory](audits/ndclient-plan-20261008/source-inventory.json) | Existing field/type/source ownership; editable versus derived versus tool-only | N0, N3 |
| [Selected content](audits/ndclient-plan-20261008/selected-content-index.json) and [rig/asset inventory](audits/ndclient-plan-20261008/asset-authoring-inventory.json) | Every registered identity, not just the example scenes | N0–N5 |
| [Review receipt](audits/ndclient-plan-20261008/PLAN_REVIEWS.md) | Independent findings, repairs, approval scope and unproven implementation claims | Each independent boundary, final N5 |

Precedence is explicit: this current plan and these revised companions govern
implementation. October 6/7 documents retain complaint/source evidence only where
referenced. Their old server proposals, Pygame/OpenGL destination, fixed lookahead,
full-runtime-XYZ requirement and exact Python depth-statistics algorithms are
superseded. A historical R09 label saying “GPU XYZ” is not an implementation mandate.
If a source defect is encountered, repair the appropriate existing owner; do not
silently substitute another protocol, geometry model or spell-specific exception.

The complete delivery is planned. The first **implemented standalone baseline**
is the linked Fireball proof: one view, two true depth bands, two RGBA8 planes per
band, GPU scene depth and local depth peeling for transparent crossings. It uses
24 FPS; the selected v4 has 46 frames over 1.916667 seconds. Other assets retain
their current rates. Whole-effect
normal-based receiving light and independently authored emitted light now work
with real floor/wall/arch assets. N−1 now fixes all family representations and
contracts. N1/N3 measure their combined production cost and visual acceptance.
There is no open-ended compositor choice to rediscover during implementation.
Named representation failures can require a bounded correction; this is not
permission to discover missing content families during the bulk port.

The October 8 mathematical refinement fixes the required operations and selected
data at the existing exporter owners. Godot is an offline producer; all rendering runs
in Pixi/WebGL. Native affected/disclosed cells are never a pixel stencil for an
admitted burst, cloud or decorative sprite overhang. The refinement names one
source-confirmed prerequisite: preserve existing typed Antimagic cancellation
attribution where a disclosed provider response is needed. It does not authorize
new spell rules or a second client propagation/light simulation. The requested
normal/light proof is required; its cosmetic lighting remains distinct from
authoritative effective-light-field parity.

## 0. Current delivery status and the work still ahead

Returning from the Fireball study does not make it the whole client plan. The
server and SDKs are delivered. **The NDClient repository exists, but its
implementation is incomplete and unaccepted; production is stopped for foundation repair planning.**
The ignored standalone demo exists and has been exercised in Pixi; it is not the
production client. R01–R23 and P01–P31 remain the full coverage denominator in §§13–14.

| Workstream | Existing foundation | Remaining delivery |
|---|---|---|
| Server/session | Delivered scoped HTTP/SSE, TS/Python SDKs, replay and warm workers | Browser connection/origin setup and durable client intake; separately track remaining native latency |
| Renderer foundation | NeuroClient camera/grid/resource helpers; registered world/support data | Shared projection, depth-capable world batches, elevation, walls/doors/apertures, picking and automatic cutaway |
| Volumes and light | Accepted v4 Fireball; depth/normal/light shaders; native-reach two-room wall/doorway example; versioned camera/playback evidence | General wall-region compilation and private reach evidence, destruction/elevation cases, concurrent buffering, Globe/Antimagic, other volumes, combined scenes and production light/disclosure policy |
| Blood and ground | Native release/landing schedules, finite particle templates and residue records | Batched analytic flight, shared landing, receiver-local deposits, old/new isolation and seek/removal/eviction |
| Asset delivery | Accepted private art and complete selected-source inventory | Relocatable release, coupled-plane decode/upload, bounded leases/residency, source-preserving packing and context restoration |
| Event presentation | Native subjective facts, ancestry, recipes and Python reduction | One TS subjective reducer, causal compiler and absolute-time sampler; independent received/consumed/displayed positions |
| All current content | 44 rigs, modular equipment, existing action/spell/condition/environment authoring | Every selected binding/field consumed by shared operators; sockets, palettes, trajectories, markers, destruction and lifecycle |
| Studio | Useful NeuroClient inspector/timeline/view utilities | Actual SDK-recorded cases in the production runtime; complete rig/action/spell/condition/world/material editors and canonical save |
| Playable UI | NeuroClient widget helpers, new icon bank, accepted portraits, full interaction matrix | Compact four-block bar, variants/targets, inventory, readable exact log, party view and real Fighter/Sorcerer crypt play |
| Acceptance | Source inventories, issue mapping and independent design reviews | Real browser performance, all named regression cases, full selected-content mapping and final implementation reviews |

The narrow Fireball proof establishes a working baseline with recorded limits. It cannot close
blood/ground, other transparent families, history, Studio or the playable encounter.
Existing Globe assets/registration are sufficient: no new Globe export is requested.
The eight-byte Fireball format is not imposed on the other asset families; §6.1
fixes that distinction. Approval of this document is not a delivered-client claim.

### 0.1 Continue from the proof, without waiting for replacement artwork

After the foundation repair, the full implementation continues from this plan.
The demo at `.runtime/ndclient-fireball-proof/`
already covers Fireball decode, depth composition, real wall registration and
receiving/emitted light. Preserve its shader/math decisions; do not restart them.
The improved **v4 Fireball is now selected and connected to the demo**; its exact
source/copy/hash and retimed playback/light curve are in the
[handoff's current-default section](FIREBALL_SINGLE_VIEW_PIXI_HANDOFF_2026-10-08.md#current-default-delivery--v4-selected-8-october-2026).
This is a versioned asset replacement, not a new renderer or a dependency for
geometry, light, resource, Globe, blood or ground work. The original proof's v1
measurements remain historical; do not attribute them to v4.

Production is currently stopped. The foundation repair plan is the immediate
planning scope. After the human resumes implementation, repair that setup and then
continue the full N0–N5 scope using actual dependencies, preserving the existing
repository and reference snapshots. Do not recreate or delete them. The accepted
Fireball demo remains unchanged. No artwork-thread communication is authorized.

N−1's contract decisions are written in §0.4 and its owning chapters. The existing
study provides evidence; it is not permission to substitute another small client,
walk-only release or demo UI for the full delivery. Measurements that require new
code remain implementation obligations, not claims made by the planning receipt.

### 0.2 Accepted v4 and native-reach shader findings

The human accepted the current demo as a useful baseline. Keep the **v4** source,
paired depth/normal data, material and timing selected in §0.1. Its small ignition
is four frames; all later source frames are retained. Frame selection, prefetch,
retirement and the fitted emitted-light curve must read the manifest, with no
48-frame/two-second assumption. Retained originals and private physical copies
follow the existing asset runbook; this is not a new asset pipeline.

The separate **solid wall / open doorway** examples now connect native propagation
results to per-fragment depth clipping. The offline fixture calls the same native
objective query as Fireball for 132 cast cells in each layout. The two obstacle-free
rooms permit an exact reduction from those results to two room permissions;
the exporter checks that equivalence for every one of the 264 footprints. At the
initial cast, the wall reaches 36 cells and the open doorway reaches 49.

The shader reconstructs each near/far fragment's world point, tests its permitted
continuous room interval and the actual solid wall/arch boxes, then performs the
existing camera-depth comparison. The real stone face bounds the region; internal
cell seams, the mechanical radius and floor visibility do not crop the artwork.
Lighting uses its own light-to-receiver test. No propagation ray from the blast
centre, tile alpha texture, new GPU texture or extra effect pass was added.

**Carry the ownership, not the two-room shortcut, into production.** Native code
owns connected spread, barrier damage, newly reached stages and protection rules.
The existing presentation compiler owns when a stage becomes visible, including
destruction clearance; the renderer consumes passive geometry at displayed time.
The proof's one-axis interval and complete objective fixtures do not generalize
to arbitrary walls or private network records. This is 2D reach extruded vertically,
not fluid flow or an implementation of propagation over low walls.

The production prerequisite and exact remaining cases are in
[occlusion §1.1](NDCLIENT_OCCLUSION_MATH_AND_PIXI_2026-10-08.md#11-native-reach-to-continuous-render-regions).
In particular, `SpellFact.resolved_area_positions` and `AreaReachFact` expose
disclosed positive cells; missing cells do not distinguish blocked from hidden.
Implement the now-specified producer/projection amendment in N0 before general
region compilation in N1. Do not make the GPU, the client or a new server-side subsystem
run a competing spell propagation simulation.

[Versioned evidence](audits/ndclient-plan-20261008/FIREBALL_PROOF.md#october-8--v4-and-the-two-room-reach-example)
separates the v3 reach-example playback timings, the v4 46-frame hookup and the
older v1 multi-cast observations. No figure is a production benchmark. Remaining
N1/N3 acceptance work is specific: arbitrary/finite/L-shaped barriers and openings, subjective
reach disclosure, destruction stages, low-wall/elevation semantics, Globe/Antimagic,
concurrent residency and combined blood/ground cases. The accepted simple example
does not need to be rebuilt or repeatedly re-reviewed to begin those cases.

### 0.3 Historical first scaffold stop: why it was not a completed foundation

The table below records the earlier 197-file scaffold, not the current source tree.
The later implementation and latest stop are assessed in the
[post-stop review](audits/ndclient-implementation-20261008/REVIEW_AFTER_USER_STOP.md)
and repaired under the [foundation plan](NDCLIENT_FOUNDATION_REPAIR_PLAN_2026-10-08.md).

The authorized destination was the complete client in this document. The following
work exists at `/home/tommaso/Dev/NDClient` on `codex/ndclient`, with no commit or
remote created. Its smaller `docs/FOUNDATION.md` scope did not supersede this plan.

| Existing work | Actual extent | Disposition when implementation resumes |
|---|---|---|
| Reference preservation and repository | Private source/history snapshots, ignored media/runtime paths, dependency lockfile and packaged existing SDK | Retain; no repeat setup or new repository |
| Authoring export/types | Existing AnimationData export and generated types; separate world/image types | Reuse applicable generated types after the complete existing-owner export is defined; no copied SDK models |
| Asset copies | First 197-file Idle/Run/terrain closure; later a selected fixed-rig closure | Partial copies, not the asset migration. Originals remain intact. Replace the selection mechanism with the full release contract in §5.4 |
| `SceneRelease` and `install-foundation.py` | Six of 53 AnimationData fields and terrain; no complete environment, equipment, UI or VFX release | Do not preserve this as a second runtime/export format. The complete canonical exporter must own the browser boundary |
| `render/scene.ts` | Floor sprites and body/shadow Idle/Run; modular composition rejected; no common depth/material world pipeline | Unaccepted implementation, not R01–R23 coverage. Retain useful pure helpers only in final modules; no second scene renderer |
| `presentation/playback.ts` | Committed walking steps only; non-walking visual operations can advance to their final state without presentation | Not N2. Replace the reduced interpretation with the complete shared causal compiler before claiming full event playback |
| Session/reduction/journal | Initial SDK integration and retained-record/reducer code | Review against §4's entire privacy/history contract; build success and a captured command are not correctness acceptance |
| UI/Studio | Diagnostic controls only; no completed playable UI or authoring workspace | Not product UI; §8, §9 and the entire interaction matrix remain required |

The new development client and its temporary native test server were stopped on
the user's instruction. No production fixes were made during this reconciliation.
The original Fireball demo, NeuroClient/NeuroMapEditor sources and original artwork
were not stopped or changed.

The problem was not that 197 files is intrinsically too few for one scene. The
problem was treating a scene's dependencies as the migration boundary. Full
installation and bounded runtime residency must coexist:

1. **Complete selected library:** every currently authored family and its transitive
   dependencies are present in the relocatable private release.
2. **Demand loading:** a displayed scene and upcoming history load only their needed
   pages from that complete release, with shared leases and bounded upload work.
3. **Complete functional support:** every selected recipe, rig, environment state
   and UI binding reaches its production consumer and Studio controls.

These are separate completion columns over one source inventory, not three new
registries. A file count, complete generated type file or one working creature
cannot mark the other columns complete. The existing selected-content/source
inventories remain the denominator; scene fixtures may not reduce it.

### 0.4 Settled implementation contracts

The previous reconciliation correctly withheld implementation-readiness approval.
This revision closes its five design gaps with the following decisions. They are
specifications for implementation, not assertions that runtime acceptance passed.

| Contract | Existing owner | Selected implementation |
|---|---|---|
| Reach exclusion versus unknown | Native area traversal, `event_facts.py`, existing spell/reach events, retained AreaCondition observations and subjective projection | Full physical stage samples plus connected frontiers or line-of-effect occluder witnesses; one local geometry arrangement labelled by those samples. Incomplete disclosure produces no exclusion inference. Exact fields and algorithm: occlusion §1.1 |
| Low walls and raised supports | Existing 2D native reach; registered finite faces/supports | Reach classifications extrude vertically; actual wall height controls solids, camera depth and light. No invented over-wall gameplay. Unknown cosmetic fringe survives; this is not fluid simulation. Limits and counterexamples: occlusion §1.1 |
| Antimagic cancellation attribution | Existing `Event`, capture header and `PlayerNode.cancellation` | Reuse `SpellSuppression` as an optional typed cancellation cause; filter its provider at event time; preserve area suppression separately. Exact changes: §5.5 |
| Compact media, blood and deposits | Existing media/storage/rig/environment types and export tools | Finite plane/ellipsoid/scalar-depth representations, explicit appearance/geometry encoding, shared analytic particle schedules and receiver-local deposits. Exact fields, conversions and family table: representation chapter §§2–4 |
| Resources and retained replay | One `render/resources` owner and one session journal | Immutable release pin, durable raw prefix before ACK, atomic displayed checkpoint, explicit frame leases and bounded worker/upload scheduling. Exact records, lifecycle and failure behavior: §§4.2 and 7.1 |

The later foundation review additionally specifies the human-approved partial-stair
shape observation at `WorldTileState`, derived/projected by existing native fact
owners. Its exact minimal fields and privacy policy are in
[repair A3](NDCLIENT_FOUNDATION_REPAIR_PLAN_2026-10-08.md#partial-stairs-one-explicit-proposed-observation-not-a-hidden-fallback).
Include this source-owned addition in the existing SDK amendment; do not create
another server or stacked-floor gameplay model. The repair also makes the local
absolute-time journal and atomic displayed-frame/resource replacement explicit.

Complete source sections, all creature clips, environment destruction, spell/action
recipes, icons, portraits and editor fields are **already specified obligations**.
They do not require a new scope decision or permission to include. §5.4 makes
their export/copy/consumer relationship explicit. Full UI and Studio stay in this
same delivery; no extra MVP, demo application, shader framework, asset service or
second event compiler is introduced.

N−1 now denotes these completed design decisions and their independent review.
There is no additional standalone demo or candidate-selection stage before N0.
Numerical performance and appearance are tested in the production pipeline at
N1/N3/N5. A failed acceptance case is repaired at its named owner; it does not
justify another renderer or a spell-specific bypass. Production remains stopped
until the user resumes it, even after implementation-readiness approval.

## 1. Destination and scope

**Design the renderer from Pixi/GPU principles, not by translating the Pygame
renderer. This applies to every family, not only expensive effects.** Existing
content data tells us what happens and how it should look. Pygame source is useful
evidence of requirements and failures; its raster algorithms, intermediate arrays,
cache layout, draw-command schema and module boundaries are not the target design.

Preserve the server contract, disclosed facts, authored visual semantics, sockets,
timing and accepted artwork. Choose runtime geometry, batching, material programs,
render passes and resource formats using the pinned Pixi APIs and measurements.
Reuse a pure formula only when it is the simplest correct choice (for example an
absolute-time trajectory); never require a Python-shaped implementation to prove
coverage. Pixel-for-pixel reproduction of known clipping/ordering defects is not
acceptance. Shader-derived approximations must preserve the intended result and
explicit physical/privacy requirements, with visual comparisons for tradeoffs.

NeuroClient's existing non-VFX renderer is the first reuse reference. Follow the
[component-by-component NeuroClient/Pixi review](NDCLIENT_PIXI_NEUROCLIENT_COMPONENT_REVIEW_2026-10-08.md):
existing grid shader, texture sharing, body/gear rendering, camera/input, resource
preparation, UI and Studio helpers are concrete candidates, not an ignored old app.
A fresh repository does not mean rebuilding these capabilities unnecessarily.

Follow the settled [compact volume, blood and ground-effect contract](NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md).
The user permits simpler extracted/static geometry and shaders: preserve accepted
appearance and gameplay/disclosure, not enormous runtime XYZ banks or Python
painter heuristics. Implement the specified schema/release in N0 and measure the
integrated families in N1/N3. Another pre-migration demo is not required.

Retain the newly created WSL repository at `/home/tommaso/Dev/NDClient` on
`codex/ndclient`. It is a separate Git repository, not a NeuroClient branch/worktree.
Preserve NeuroClient's current committed and relevant working state in a private
reference snapshot before salvaging selected components. Keep the engine/server
repository and existing private production-art repository in place. The exact
snapshot, repository bootstrap, ignored local media copies, SDK package and launch
steps are required work in [asset/setup §2.1](NDCLIENT_ASSETS_AND_RIG_AUTHORING_2026-10-08.md#21-repository-and-local-copy-runbook).
No new backend, SDK or duplicate art repository is required.

The [reference-revision receipt](audits/ndclient-plan-20261008/reference-revisions.json)
pins this study's source hashes. NeuroClient's tracked tree was clean at inspection;
NeuroMapEditor had existing tracked edits, so its inspected working-file hashes,
not just its HEAD, matter. Neither reference repository was modified.

Deliver one production client, its real-event Studio, and the tool-side presentation
release exporter. The client uses **PixiJS 8.22.0 / WebGL2**, TypeScript and Vite.
Retain/adapt compatible existing Pixi icon-HUD, equipment and portrait layout/drawing
functions; DOM owns selectable log text, forms and Studio controls. This replaces
the earlier blanket HTML/CSS-interface assumption. One implementation per widget,
with shared SDK-fed view data and input ownership; no forced UI technology rewrite.
Browser UI is allowed to improve on both old clients. No React/state framework,
shader framework, ECS runtime or plugin manager
is needed just to begin. Add a dependency only for a demonstrated need.

The server remains the current Python service, on Windows or WSL as selected by
the user. Client startup must not import the engine, start a second rules service,
generate SDKs, scan private art trees, or materialize all content. Use the delivered
`@neurodragon/player-sdk` from `sdk/player-typescript`. The old
`@neurodragon/dnd-engine-sdk` is a different protocol, not an interchangeable alias.

Full destination includes existing spells, ordinary actions, reactions, movement,
conditions, equipment, environment interactions, geometry and deposits. It does not
add undead creation, surface chemistry, new spells or new art designs. The requested
Fireball re-export is the explicit exception detailed in §16. Keep authored
32 FPS media and clip-specific body rates, except the explicitly requested 24 FPS
Fireball proof. There is no general FPS conversion.

## 2. What the source study established

The [fresh inventory](audits/ndclient-plan-20261008/source-inventory.json) and
[selected identities](audits/ndclient-plan-20261008/selected-content-index.json)
were produced from the current loaders without decoding image banks. They record
53 AnimationData fields, 15 AssetCatalog fields and 23 WorldBindingsSource fields;
149 draft keys including aliases, 85 body-action recipes, 160 condition recipes,
44 rigs, 1,112 media declarations and 1,090 storage records. Counts are identities,
not a claim of that many unique spells or shaders.

The [field-by-field authoring ledger](NEUROCLIENT_AUTHORING_COVERAGE_2026-10-07.md)
still matches these denominators. Every field needs a destination: editable source,
derived read-only value, or tool-only provenance. None may disappear because the
old Studio only had a strip editor.

Confirmed weaknesses to replace:

1. NeuroClient consumes the old SDK/store/mapper and constructs synthetic Studio
   results. Those are incompatible with current initialization/operation records.
2. Some Studio hosts omit vitals/equipment handlers. A visually similar scene is
   insufficient; Studio and play need the same complete reducer and renderer.
3. Current media registration retains `kind: projectile` and eight-row frame
   constraints even for clouds, ground fields and markers. Storage already supports
   sparse layers, four-camera registered XYZ, owners and footpoints. Tooling must
   expose source registration and the chosen compact runtime representation;
   it must not force every source plane into the browser's active working set.
4. Python's public presentation export covers AnimationData only. World,
   environment, UI bindings, source ownership and dependency packaging need one
   coherent release too. Some old fixture/export labels still say player-v2.
5. The Python draw command already contains raster surfaces/arrays. It is too late
   in the pipeline to be the portable schema. Identify the visual requirements
   upstream and design Pixi render inputs from them; do not port that command path.
6. Old `worldDepth.ts` sorts mostly by ground X+Y and sometimes screen Y. Old
   `MultiTintFilter` is not our exact palette/material implementation.
7. Pygame acquired substantial interaction functionality that the old client lacks.
   The [interaction matrix](NDCLIENT_INTERACTION_PARITY_2026-10-08.md) specifies it.

Official Pixi guides and pinned APIs are saved in the
[local reference](references/pixijs-8.22.0-20261008/README.md). Detailed geometry,
shader and lighting decisions are in the
[rendering study](NDCLIENT_DEPTH_MATERIAL_LIGHTING_2026-10-08.md).
Complete asset delivery and both modular/fixed-sprite authoring are specified in
[the asset and rig plan](NDCLIENT_ASSETS_AND_RIG_AUTHORING_2026-10-08.md).

## 3. Ownership and module structure

These are ordinary modules exporting functions and passive records. Pixi's own
objects remain renderer handles; entities do not become client classes.
The renderer's small target-native records are compiled views of existing authored
data and displayed facts, not copies of Python intermediates or another wire model.

| Directory | Owns | Must not own |
|---|---|---|
| `src/session/` | SDK connection, attachment, receipts, consumption, scoped recording | Event reinterpretation, rules, animation waits |
| `src/player/` | One reduction/index/history implementation over SDK values | HTTP DTO copies, art, UI decisions |
| `src/presentation/` | Recipe resolution, causal grouping, compilation, retained state, sampling | Networking, DOM, texture decoding, new outcomes |
| `src/render/` | Projection, registered media, ordered draws, material shaders, resources, point picking | Spell-name rules or native validity decisions |
| `src/ui/` | Adapted Pixi HUD and DOM text/tool views, local interaction state, SDK preview/command gestures | Its own paths, damage math or visibility model |
| `src/studio/` | Workspace, cases, inspector, timeline, edit history, source changes | Second renderer/compiler or fabricated gameplay |
| `src/app/` | Composition of the above for play or Studio | General service locator or global mutable registry |
| `tools/` | Development-only source editing, case production, release packaging | Browser-accessible native world/state |

Import direction: SDK types and authored types → pure player/presentation functions
→ renderer/UI adapters → application composition. Studio composes the same player,
presentation and renderer functions. GPU resource ownership is passed explicitly.
DOM widgets never import native Python or the old NeuroClient store.

Do not create a duplicate generated player-contract directory. Import SDK exports.
For authoring, export JSON Schema from existing Python source types and produce one
TS authored-type artifact per schema revision, as a deliberate maintenance step.
Do not regenerate during boot, tests, every edit or every command. JSON validation
is at external boundaries; already-admitted values do not bounce through JSON again.

Python subjective player reduction and TS reduction cannot literally share executable Python
code. They share the **same protocol and semantics**; Python replay calls the same
`dnd/player/reduction.py` used elsewhere in Python, and both browser modes call one
TS port. Differential tests compare these two language implementations. There is no
separate headless rules oracle or third simplified browser reducer.

## 4. Delivered API integration, with independent clocks

Pinned current protocol identity: protocol 1, player schema 4; the SDK's
`protocol-identity.json` supplies the digest. Do not hardcode another digest in UI.
Use SDK initialization, operations, content, choices, preview, commands, receipts,
attachment and follower facilities. One authorized party audience can contain many
controlled units; changing inspected character does not reconnect its stream.

Native descriptors and static artwork are different inputs. Admit observed native
names/descriptions/related references through the SDK's `content_additions` before
their dependent lineages; its existing public-metadata endpoint remains available
for public descriptors. A presentation release does not grant knowledge of a
creature/item/spell or contain the full private native UIContentManifest. Browser
Startup and Studio recording replay never recover hidden native data from art keys.

Ingestion sequence:

1. Decode/admit through the SDK; retain exact scoped received records and unplayed
   presentation prerequisites before advancing consumption. Retention is mandatory;
   a user choosing to export a recording is a separate operation.
2. Admit referenced public content before consuming dependent lineages.
3. Reduce the operation and advance the contiguous consumed cursor. The follower's
   consumer awaits this work, not texture loads or animation completion.
4. Queue affected presentation groups for compilation/resource preparation.
5. Sample and display at a separate presentation clock. The displayed cursor and
   latest received state remain distinct. Command availability uses native current
   authorization; history inspection never grants command authority.

Preserve event-time observations, before/after values, nullable roots, one-past
occurrence cursors and scoped references. `lineage_branch`/index semantics are
ported, not guessed by walking every child recursively for every frame. Grouping
related reaction roots is a presentation view, never a rewrite of event ancestry.
Do not await VFX inside an SSE read loop or block the render loop on a preview.

Resource shortage may delay a group's visual start; later receipts/content still
consume. Show an honest preparation status in diagnostics. Never silently omit
required art, drop a condition handler, or substitute a placeholder as acceptance.
Loss/reconnect/retry/duplicate delivery must use SDK behavior rather than a second
retry journal. Scope changes cannot reuse private state from a previous audience.

### 4.1 Non-negotiable: server progress does not set animation time

Track received cursor, contiguously reduced/consumed cursor and displayed
occurrence plus presentation time separately. These are positions in one received
history, not three copies of the game. Latest state serves command discovery and
transport recovery; the displayed projection drives scene, vitals, portraits,
light/visibility and timed combat-log reveal. Never update those visual consumers
directly from the latest state while an older group is playing.

AI/native advancement may finish many turns ahead. Retain every admitted operation
and queue each animatable disclosed occurrence exactly once in causal order. No
last-update-wins coalescing of attack/reaction/death/movement/condition transitions,
no automatically skipped AI turns, no “catch up” by replacing the scene with latest
state. Source frame interpolation may skip sampled picture frames at low FPS, but
must not omit semantic occurrences, contacts or required state commits. Parallel
effects are allowed only where the authored causal grouping permits them.

Compilers may prepare ahead, but groups start on the presentation timeline only
when their prerequisites/resources are ready. Pausing or slow Studio playback does
not pause SDK ingestion. Use a compact retained operation journal/checkpoints and
bounded decode/compile lookahead; don't retain all possible GPU frames for queued
turns. Pruning cannot remove unplayed occurrences or data required by the selected
history window. Retaining ACKed-but-unplayed records is **mandatory**, regardless
of optional recording export. One journal owned by `session/`, scoped by the SDK's
game/stream identity, persists admitted raw records to IndexedDB before consumption
completes and the SDK ACKs them. Checkpoint and displayed-position publication are
atomic with their required retained-prefix references. Bounded memory can discard
old decoded objects after their persistent records exist. This is application
retention over the SDK consumer, not another transport/retry implementation.

The API has **no client pause-native-advancement control**. At actual local capacity
exhaustion, stop before accepting/ACKing another record. The service may continue
into its existing spool until its quota; report that real capacity/error state.
Never ACK discarded records, silently drop animations or invent a server-control
call. Ordinary render lag must not make native execution wait for animation duration.

An existing SDK follower resumes the network at **consumed**. Presentation restores
**displayed** from retained records/checkpoints. A fresh follower initializes using
the SDK's existing initialization path, not an arbitrary displayed cursor; reconcile
already-retained record identities during replay without queuing them twice. Local
unplayed records remain usable if server history expires. Missing required records,
content or the pinned presentation release is an explicit recovery failure, never
a reason to pretend intervening animations already played. Scope changes clear
active private state; do not expose a previous audience through a new attachment.

Player spending actions are enabled only when the displayed interaction context
matches the current authoritative choice/turn lease. Camera, inspection and history
controls remain responsive. Do not let clicking a character from the old visual
state accidentally spend an action in a later turn already reached by the server.
Action-bar resources, inventory contents, condition labels and tooltips also use
displayed state. Prefetched latest choices may disable stale spending, but may not
show tomorrow's inventory, cooldown or learned ability in the turn still playing.

Mandatory stress case: delay asset readiness, play at 0.25× and pause while native
AI delivers several turns, including movement interrupted by a lethal opportunity
attack and a door/light change. Verify cursor divergence, complete playback and
correct names/positions/HP/light at each contact; reconnect mid-backlog and restore
presentation from its displayed checkpoint while network consumption resumes
independently. Also test fresh-follower initialization, browser reload and server
history expiry with retained unplayed records; no duplicate or future-state leaks.
The acceptance harness asserts the sequence of semantic presentation commits in
addition to rendering frames. This replaces the old queue/FSM, not another queue
feeding it.

### 4.2 Exact retained-history contract

`src/session/journal.ts` owns IndexedDB, using the SDK's existing scope and record
identity. `src/player/history.ts` owns pure prefix restoration; it does not open
another database or network connection. The database has three passive records:

| Record/key | Fields and meaning |
|---|---|
| Recording / local recording ID | SDK scope (game, epoch, audience), protocol identity/digest, `presentationReleaseId`, authored schema digest, presentation semantics version and compiler build ID; creation time is diagnostic only |
| Operation / recording ID + SDK sequence | Exact received bytes and their existing SDK cursor/identity; immutable. Duplicate same identity must have the same bytes. Content additions remain in their original operation ordering |
| Progress / recording ID | Durable contiguous received sequence, successfully reduced/consumed sequence, displayed occurrence identity and phase-local time, prerequisite prefix sequence, optional derived checkpoint reference |

These are local persistence metadata, not new player-protocol DTOs. SDK decoded
values are passed directly to reduction. Checkpoints serialize the existing passive
TS player state and displayed retained-state records, tagged by their schema/build;
never store Pixi handles, promises, closures, credentials or another world model.
A compiler build change may reuse records only when its presentation semantics version
is compatible. A schema/build mismatch invalidates derived checkpoints; an
incompatible semantics version gives an explicit replay compatibility error, not
silent retiming. The raw recording/release remains intact for its compatible build.
This phase guarantees reload/reconnect replay with the delivered runtime; it does
not invent a historical JavaScript-build distribution service.
Raw operations remain the replay source; an incompatible checkpoint is discarded
and its retained prefix replayed. Add derived checkpoints where observed restoration
cost warrants them. Their frequency is an implementation tuning choice, not a
prerequisite or fixed operation count.

The existing SDK consumer retains each admitted operation and completes reduction
before acknowledging it. Unplayed acknowledged operations must survive reload.
Use one journal; transaction layout follows that invariant, without prescribing
two disk commits per operation or a new acknowledgement protocol. Records and
their contiguous durable-prefix metadata commit together. A consumed checkpoint
may never reference records that have not been retained successfully.

Publish displayed occurrence/time with its required durable prefix and release pin
at semantic commits and pause/seek. Choose any additional progress-write cadence
from actual playback/recovery needs, without a timer quota. An interrupted write
may replay unfinished visuals; it must not skip an occurrence. Recovery reduces
the retained suffix from a valid checkpoint and reconciles SDK duplicate delivery
by its existing identity. A later received prefix never overwrites the displayed
scene. Storage failure prevents acknowledgement; no unload callback or duplicate
transport/retry journal supplies correctness.

Local replay opens **without a connection to the native server**: select the scoped
recording explicitly, load its pinned immutable presentation release, restore a
checkpoint and replay only its needed suffix. This promises server-independent
history, not a first-ever offline download of missing artwork. The same local media
installation serves replay. Missing release bytes produce an exact release/resource
diagnostic, never substitution of the newest art or skipping to the end.

Old immutable release directories stay installed while any retained recording pins
them. Removing recordings/releases is an explicit local-library operation, not GPU
eviction. Studio drafts use a separate in-memory candidate revision and cannot
mutate a recording's release identity. A saved candidate becomes a new immutable
release; changing a case to it is an explicit Studio preview operation.

Use actual browser storage availability and handle transaction failures without
acknowledging lost records. Do not impose an invented journal quota or automatically
prune unplayed data. If storage is exhausted, keep local playback/input live and
report it; the existing server spool has its own lifetime. Capacity monitoring
must not become a synchronous per-operation scan or a new server-control API.

On audience/epoch change, increment an application generation, clear canvas, HUD,
private reduced/retained data and active groups, and cancel old preparation leases
before presenting the new scope. Every asynchronous completion checks generation.
Public immutable media may share bytes by hash; private state/recordings never join
across scope. Auth tokens remain in the SDK's session handling, not in recordings.

## 5. Presentation release and minimum schema work

The native player schema already supplies height, slope, support, apertures,
constructions, perception and causal facts. No broad gameplay-schema expansion is
justified by this study. The work below is in presentation export/authoring.

### 5.1 One complete release

Extend the current exporter to emit a versioned release index with content hash,
authored-schema version and references to these existing sections:

* AnimationData, including all recipes, rig registrations and bindings;
* WorldBindingsSource/AssetDocument, water and residue materials;
* EnvironmentDocument for doors, traps, props, wrecks and animated banks;
* exact item-visual, icon, choice-icon and portrait bindings;
* the resource table: immutable resource ID, URL, hash, byte size, format,
  dimensions/frame layout, coupled plane references and dependencies;
* a **tool-only source map** identifying canonical file, JSON pointer, inherited
  source and override for each editable authored value.

Release sections reference shared IDs rather than duplicating payloads. `media_root`
and filesystem paths become tool input or release-relative URLs. Private native
events, hidden map data and absolute author filesystem paths never reach the browser.
Current `content_data/ledgers/neuroclient_authored_item_visuals.json` remains the
item-visual source; do not accidentally move ownership into a Studio draft.

### 5.2 Remove the strip-only authoring assumption once

Evolve the existing media registration type to describe physical source layout
independently of its consumer: flat frame bank, layered/sparse bank, or registered
surface bank with the geometry specified by N−1. Preserve existing IDs and decoded phase data. Carry explicit
direction/camera basis, frame count/rate/time map, dimensions/crop/pivot and
RGBA/XYZ/owner/footpoint/colour-mask relationships. A spell recipe says how media is
used; a cloud's storage is not required to pretend it is a flying projectile.
Those are source relationships, not a mandate for all full-size runtime planes.
N−1 specifies the representation contract at this existing owner; N0 implements
its export and N1/N3 measure its production behavior.
N0 implements that decision in the source/export types, performs one versioned
migration and generates authored TS types. Source layout, geometric representation,
appearance/blend encoding and consumer role remain distinct; a historical
`projectile` kind is not a new render-class hierarchy. No duplicate particle,
residue or gameplay schema is needed.

Use a versioned offline migration of legacy row/kind fields into that representation.
Do not maintain old/new parallel runtime registries or rewrite all spell recipes
solely to rename a field. Packing addresses remain derived; source frame/registration
edits remain authored. Semantic validators still enforce aligned companions,
exclusive storage sources, valid palettes, finite envelopes and supported bases.

The exact minimal registration migration in `game/animation_types.py` is:

* Keep the existing `AuthoredProjectileAsset` owner/asset IDs; its historical Python
  name is not behavior. Remove its constant `kind: Literal["projectile"]` field.
  Consumer role already belongs to the action/spatial/condition/particle binding;
  do not replace this constant with a competing role enum or asset class hierarchy.
* Change `ProjectileFrame.rows` from `Literal[8]` to a positive integer. Retain
  positive width/height/cols, existing `rowOrder: tuple[Facing8, ...]` and phase
  frame counts. For grid sheets, rowOrder must be unique, cover the declared rows
  and fit the image; phase start/count must fit the columns. Shared one-view sources
  use rows=1 and their actual source facing. Directional banks retain their rows.
* Make `sheet: Identifier | None = None`. A declared phase either has its existing
  `ProjectileStorage.phases` entry or uses this grid-sheet fallback. Every selected
  phase must resolve completely. `sheet=None` is legal only when all selected
  phases resolve through storage; never emit a dummy sheet to satisfy a validator.
* Retain the **existing** exclusive storage selectors: grid sheet, layer pattern,
  `pages`, `parts`, `partsByFacing`, or source-only `surfaceFrames`. Do not add a
  second `layout` discriminant expressing the same choice. `parts` shares its
  appearance across requested views; `partsByFacing` resolves declared directional
  keys. Geometry's explicit camera/object basis is separate from this storage
  selection. Existing `viewFacing` bindings choose fixed banks where authored.
* N0's one offline source migration removes the obsolete `kind` key, relaxes the
  row constraint, and removes only placeholder sheets for phases fully covered
  by storage. Preserve IDs, anchors, phases, rates, tags, palette and source
  provenance. The selected v4 is registered as its real one-view bank. Convert
  legacy `surfaceFrames` to the selected layer/part contract in the **derived
  browser release**; retain full source packets privately. No dual runtime parser
  and no second canonical media registry remain.

The source document/export schema version changes once for these fields and the
representation chapter's additions together. Generate authored TS types from that
owner schema once; player SDK generation is separate and occurs only for §5.5 /
reach evidence. An asset's binding remains valid throughout the migration.

### 5.3 Full materials on isolated layers

Reuse the finite material operators already used by body/action materials for hand,
Magic and Effect masks. If a layer cannot reference the existing treatment, extend
that layer with one optional typed material reference and parameters; extract the
shared material record to a lower-level source module only if needed for the import
DAG. Do not clone each operator into a second hand-material schema.

Retain the resolved spell/variant palette, explicit overrides, source mask, donor
texture, noise phase, alpha and authored blend. Existing accepted palette swaps
remain valid. Material texture transfer is not multiplication tint and does not
recolour the already-accepted external Godot effect without an authored instruction.

### 5.4 Complete export, dependency closure and consumers

This is the single production data boundary. Extend `game/presentation_export.py`
and its schema export using the specified owners;
do not assemble a narrower `scene.json` in a client-side installer. The release
may contain separately addressable sections to avoid parsing a large monolith on
startup. Section splitting is derived packaging, not a second authored model.

| Canonical source/type | Complete release section and dependency roots | Production consumer / Studio responsibility |
|---|---|---|
| `AnimationData` / existing `PresentationCatalogExport` | All 53 fields with the ledger's executable/tool-only dispositions; every selected recipe, context, material and binding, not a six-field Pick | Shared compiler/sampler and corresponding inspectors; tool-only source strings stay out of executable data |
| `BodyRig`, `BodyClip`, rig tables and exact creature bindings | All 44 rigs; every declared clip, category, facing, body/shadow/accent/gear/Magic/Effect reference, pose context and socket | One modular/fixed rig path; rig inspector and action timeline. An Idle/Run resource set cannot satisfy declarations for attacks/death/flight |
| `AssetDocument` and `WorldBindingsSource` | All resource/animation/water inputs and all 23 world fields, including cliffs, stairs, faces, constructions, spatial media and deposits | Shared support/world/material consumers and world inspector. Do not also serialize derived `AssetCatalog` dictionaries as editable sources |
| `EnvironmentDocument` | All 368 banks, 17 door, 12 trap, 40 wreck and 113 prop bindings; open/closed/engaged/damage/destruction paths and all companions | World transition compilation, physical drawing, picking/light geometry and registration/transition editors |
| Item visual ledger, `ItemAppearanceDocument`, source palettes and existing material/attachment owners | Canonical visual categories/variants, 100 hand and 404 ground appearance rows, item material treatments, attached effects and their dependencies | Shared owned-item appearance while equipped/dropped/looted; item/material inspector. Never reconstruct these from the old client’s generated output |
| Current projectile/media registrations and storage | All 1,112 declarations / 1,090 storage records in the pinned selection, plus condition/action/particle/blood/construction/lifecycle dependencies and the selected Fireball v4 replacement | Finite media/material operators. The word `projectile` in an old source type does not restrict the package to flying sprites |
| `ui_media.json`, `UIPresentationDocument`, `ChoiceRecord`, selected skin/font registrations and current icon handoff | Exact icon/portrait roles, choices and selected UI resources; 620 icon-key replacements backed by 594 smooth144 images and 103 choice bindings | Shared UI binding lookup; portrait/icon preview and binding inspector. Exclude the complete native `UIContentManifest`; no knowledge gained from an art key |
| Existing source documents and exporter provenance | Tool-only document identity, JSON pointer, source revision and override origin; packing metadata is derived/read-only | Inspector/timeline edit and canonical save. Public release cannot expose filesystem paths or a browser-supplied write path |

Counts are the pinned planning inventory, with aliases and shared resources; they
are not unique files. New source revisions update that same inventory once, rather
than generating a rival list. Authoring types come from these existing owners.
Where a passive source type currently lives beside Pygame code, move only that
definition to its existing family's lower-level type module if necessary for the
export import DAG; do not duplicate its model or port its image loader.

The release builder has a finite sequence:

1. Read every selected source section and typed reference. Classify each existing
   field as runtime data, derived metadata or tool-only provenance using the field
   ledger. Explicit references, not filename suffix guesses, define dependencies.
2. Follow every registered clip/layer/phase and companion edge. Retain all animation
   frames, authored rates/sample times, pivots, crop offsets, masks and source
   registration. An archive containing paired planes is an offline dependency to
   convert at the selected media owner; it is not a whole-bank startup download.
3. Reuse suitable sheets. Apply the selected conversions only where required by
   the representation/packing chapters. Fireball v4 and the smooth icon handoff
   supersede their exact old bindings; unrelated selected media remains included.
4. Record resource byte hashes, lengths, encoding/sampling descriptors, companion
   groups, section dependencies and source-to-output mapping. Deduplicate bytes by
   hash while retaining distinct declared sampling/material uses. Derive immutable
   release identity from section contents **and referenced byte hashes**; changing
   artwork without changing its JSON must still change the release identity.
5. Produce an unresolved-reference report by source pointer/family. A missing
   selected resource prevents its dependent capability from being ready and prevents
   claiming the final release complete. It does not block integration of unrelated
   available dependencies. Do not remove identities to hide gaps. Unselected/archive
   resources remain separately accounted for, not promoted into new gameplay content.
6. Physically copy the complete resolved release to ignored staging and publish
   atomically. Reinstalling identical bytes is a no-op; a conflicting existing
   release is an error. Neither operation overwrites originals or performs Git
   publication. The app never hashes/scans the library during ordinary startup.
7. Runtime scene/upcoming-group demand addresses resources within that release.
   Loading five sheets for one scene does not reduce installation coverage. Report
   inventory identities, installed unique bytes, decoded bytes and resident GPU
   bytes separately.

The existing coverage inventory gains status/evidence columns for source mapping,
resolved dependencies, copied release, runtime consumer and Studio editor. This is
a build/review report, never a runtime registry or hand-maintained duplicate of the
asset catalog. N0 cannot close on the current installer. N3 cannot close merely
because all binaries were copied. N5 requires the full behavior/UI/Studio results.

The complete export extends `PresentationCatalogExport` at its existing owner;
it does not retain `SceneRelease`. Its additional sections are typed references to
existing `AssetDocument`, `WorldBindingsSource`, `EnvironmentDocument`, item
appearance/palette/material/attachment documents, and the passive UI presentation,
choice, skin and font declarations listed above. Move passive UI declarations to
their dependency-neutral owner if necessary; do not import Pygame into the exporter
or copy the native `UIContentManifest` into public artwork metadata.

`releaseId` is the hash of canonical exported metadata plus the sorted resource
hash/length list. Resource records carry existing resource ID, release-relative
payload path, hash, byte length and decoded dimensions/format. Source provenance
(document identity, source pointer, expected revision, source hash) is tool-only;
the runtime manifest never exposes local filesystem paths. Packing outputs derived
parts in this same export. The exporter enumerates the whole selected catalog,
with no scene/creature selector that reduces the coverage denominator. Generate
authored types only when their owner schema changes, not on ordinary asset installs
or parameter edits. During implementation, available dependency closures can run
through this same catalog, loader and production consumers while other families
are being connected. No second partial-release format or demo renderer is needed.
Final delivery requires complete installation and supported consumers; partial
availability is progress, never a completion claim.

### 5.5 Typed protection cancellations and exact native amendment

Reuse `dnd/types/spell_suppression.py::SpellSuppression`; it already contains
`antimagic`, provider UUID, affected positions, optional provider ContentRef,
`AoEPresentationGeometry` and anchor elevation. Do not invent a client protection
type, infer a provider from status prose or reuse an entity UUID field for a
condition UUID.

The owner changes are finite:

1. `dnd/core/events.py::Event` gains optional
   `cancellation_protection: SpellSuppression | None = None` (a cold type with no
   handler import). `cancel()` retains it through the existing versioned event.
   `dnd/player/capture.py::_event_header` preserves this cold value. No event bus,
   new registry or new capture family is added.
2. Antimagic's existing source, target, path and transfer-endpoint cancellation
   branches in `dnd/spells/abjuration.py` populate that field using their **already
   computed** protected positions and provider UUID, and set the stable outcome
   code `spell.antimagic_field.blocked`. Portal/forced movement use their existing
   path/endpoints; there is no new path calculation. Globe's targeted cancellation
   uses the same field and retains its existing outcome code. A terminal cancellation
   is recorded once here, not also appended to `SpellFact.suppressions`.
3. Existing `ActionCancellation` in `dnd/player/facts.py` becomes the single
   `EventCancellation` value used by the existing `PlayerNode.cancellation` field:
   `phase`, `action_economy_spent: bool | None`, `outcome_code`,
   `protection: SpellSuppression | None`. `None` spending means this non-action
   event has no independent action cost; the parent action owns it. There is no
   second parallel record or legacy alias. Ordinary action cancellation behavior
   is retained; projected non-action cancellations are added only when their fact
   is admitted. Schema/SDK revision is the single deliberate update in N0.
4. `dnd/player/projection.py` uses one local pure projection helper for these
   protection values, area `SpellFact.suppressions`, staged reach suppressions and
   the existing construction-suppression projection. It selects the event-time
   admitted `PerceivedSpatialEffect`, filters positions by the existing event-time
   position admission predicate, and copies permitted content/geometry/elevation
   from that contact. It must preserve the `antimagic` flag for disclosed providers.
   Missing provider/contact means no provider identity, geometry, content or cells.
   Redact a protection-specific outcome code to generic cancellation when its
   provider is undisclosed. No hidden provider is inferred from a blocked endpoint.
5. Existing content-attribution/admission collection includes the new optional
   permitted provider ContentRef before dependent nodes. The shared Python
   presentation adapter and new TS compiler consume `node.cancellation.protection`;
   update the old Globe terminal consumer once instead of duplicating provenance
   for compatibility. No other Pygame rendering work is part of this change.

Area exclusions remain in `SpellFact.suppressions` or the current reach stage;
they are partial application, not cancellation. Maintained suppression/resume and
expiry continue using existing condition/item/spatial facts. Event records capture
the cause before the provider can move or disappear; projection must never use its
latest live entity/condition lookup. The existing observed-construction helper in
`projection.py` already demonstrates the historical admitted-geometry join.

During staged playback, use **only the active `AreaReachFact.suppressions` snapshot**.
The root's final union is a terminal summary and must not suppress an earlier
frame retroactively. At maintained-field takeover, use that lifetime's retained
`PerceivedSpatialEffect` evidence/suppressions and existing revision/commit timing.

Presentation selects the authored response by the admitted provider's content
binding. If the fact authorizes a boundary impact, intersect the authored trajectory
with its admitted geometry as occlusion §3 defines; that is visual placement, not
collision/outcome simulation. A disclosed cancel without usable geometry plays a
generic cancellation at its authored actor release, with no invented dome contact.
Source-suppressed casts never fabricate a travelling projectile. Delayed/native
children respect the recorded cancellation phase and parent cost.

Decisive cases: known/hidden Antimagic source, endpoint and path; canceled magical
forced movement/portal; Globe inside/outside/partial area; provider moving after
capture; suppression expiry without revival; replay after provider removal. All
must use the same records in Python replay, TS play and Studio. This work and the
reach evidence in occlusion §1.1 amend existing engine types/producers, **not** the
server transport, authentication, rules or worker architecture.

## 6. Renderer delivery and the difficult work

Implement all R01–R23 families from the prior inventory. The full field ledger and
selected identities determine coverage, not a fixed number of attractive examples.
This is **capability and content coverage**, not a requirement for R01–R23 to become
23 modules or 23 shaders. Shared geometry/material operations serve multiple families.
Archive/tool-only metadata remains outside active runtime resources.
One family implementation normally serves many spells without per-spell Python/TS
branches. Existing named content selects recipes through exact references.

Connect usable exported data and accepted media to the production renderer as their
consumers are implemented. Complete the library and required geometry conversions
alongside those consumers; do not require every asset to be converted or optimized
before rendering and event integration can proceed. The largest work is depth and alpha composition, followed by shared
temporal presentation, complete source-aware authoring, and UI interactions. A
simple sprite renderer is a small part of the port. The companion rendering study
defines the projection/depth rules, shader operations, lighting and proof scenes.

Required families include ordinary terrain/slopes/cliffs; doors/windows/props;
modular and fixed bodies; original item appearance before/drop/transfer; particles,
projectiles/beams/areas; walls/domes/rings; condition body and head effects;
flight/jump/forced movement/portals; reactions/counterspell; blood/water/residue;
damage/heal/death/summon feedback; persistent suppression and expiry; world picking.

Retain actual artwork capabilities. Fire-wall diagonals and fixed-radius rings
**do exist** in current files and later ASSETS entries, despite an earlier stale
paragraph. The complete-ring/partial-disclosure ownership limitation is a distinct
case to verify, not a reason to announce the whole ring artwork missing.

### 6.1 Concrete representations, with a common renderer

The existing media/rig/material types, world/environment bindings and presentation
export remain the source owners. These are choices of data and shared operations,
not one new registry or shader framework for each row.

| Family | Selected baseline and remaining proof |
|---|---|
| Floors, slopes, walls, doors and simple props | Original textures on registered geometry; derive depth and face normals. Prove alignment, apertures, elevation, lighting and cutaway. |
| Modular/fixed bodies, equipment and irregular props | Shared layered quads with authored contacts, sockets and rest coordinates; compact depth detail only where required by intersections. Prove large bodies, flight/prone, equipment changes and compatible batching. |
| Projectiles and beams | Quads/ribbons with selected directional bank, residual rotation and trajectory tangent at absolute height. Prove socket release and all four camera rotations. |
| Globe | Existing front/back colour and analytic sphere intersection supply depth/normals. Retain its authored 32 FPS; no new export or registration copy. |
| Fireball | Selected v4: one view, 46 frames at 24 FPS (1.916667 seconds), two true depth bands, appearance RGBA8 plus packed depth/normal RGBA8 per band. Eight bytes per band texel; two occupied bands cost sixteen. Measure the linked handoff, not a flattened approximation called two layers. |
| Other bursts/clouds | Exact family assignments in representation §2: two quarter-chord contributions for flattened clouds; original component appearance on fitted surfaces for radial front/back media; scalar depth for directional source components. Preserve component count and clocks; test Sleep/Fog/Sunburst intersections. |
| Airborne blood | Compact release/landing buffers and finite shape atlas; analytic GPU flight at presentation time. Prove concurrent release, vapor/fragments and landing continuity. |
| Settled deposits/residue | Receiver-local coverage with existing finite material/response parameters; update changed regions and retain old/new isolation. Prove removal, eviction, seek and no duplicate stain/deposit rendering. |
| Markers and UI | Existing media and placement policies. World markers still respect authored occlusion; ordinary Pixi Sprite batching serves depth-free UI and already resolved overlays. |

All world draws participate in the common depth/material path. Depth-writing world
quads use explicit batched geometry/state; ordinary Sprite batching is not assumed
to acquire world depth automatically. Material rest coordinates remain separate
from projected depth, so palette/mask sampling does not swim with camera rotation.

The selected sequence is solid colour/depth, directly ordered transparency where
valid and local depth peeling at crossings, then shared bloom and UI. Peeling uses
separate selection attachments, stable ties and a conservative finite pass bound;
transparent accumulation does not overwrite solid scene depth. One shared shader
program does not mean one total pass or a silent transparent-layer cap.

Fireball's appearance is encoded combined radiance/transmittance, not ordinary
straight-alpha colour or isolated emission. The proof preserves that radiance and
adds reflected light across the whole effect using existing normals/depth and an
authored neutral reflectance. Emitting and receiving are independent material
properties; no recovered smoke mask or extra texture is needed. This approximation
and its existing-owner schema mapping are specified in [lighting §4.1](NDCLIENT_DEPTH_MATERIAL_LIGHTING_2026-10-08.md#41-proven-emitting-and-receiving-material).
Bloom remains a shared bright-pass approximation from mixed visible radiance.
Materials with separately authored albedo/emission keep those channels. Native
effective light and disclosure remain authoritative; the synthetic demo lights
are not a replacement for the production policy.

## 7. Assets, packing and readiness

Follow [asset §2.2](NDCLIENT_ASSETS_AND_RIG_AUTHORING_2026-10-08.md#22-animated-assets-pixi-source-check-and-packing-policy)
for the checked Pixi loading/animation policy: retain good existing sheets and usable
frame payloads, preserve full-cell anchors and companion alignment, and avoid eager
multipack loading of large effects. The accepted v4 frame payloads are a usable
starting format. One shared
source/page owner manages all cast ages; world frames follow displayed time rather
than independent AnimatedSprite tickers. Repack only for an actual texture limit,
required access/conversion or a demonstrated delivery improvement. Packing is not
a prerequisite to client integration or a separate optimization programme.

The source assets remain private and immutable. Release packaging is derived and
does not import artwork into Git. Share identical resources and retain their IDs
as references. Where packing is needed, retain original pivots and explicit
colour/geometry registration. The representation chapter selects proxy or scalar-depth geometry by family
instead of shipping full XYZ. Preserve exact source archives and
source-to-derived calibration/error receipts. Numeric depth and ownership must not
accidentally undergo colour/gamma/premultiplication or categorical interpolation.
Keep source/effective duration and 32 FPS intact outside the explicitly requested
24 FPS Fireball proof; selected v4 plays its manifest-defined 46 frames over
1.916667 seconds. Do not retain the earlier export’s two-second clock.

Browser delivery uses bounded independently loadable pages/chunks, not a full
3.57 GB four-camera Fireball impact decode on startup. Cropping alone was insufficient
in the existing audit; the representation chapter specifies compact geometry and colour
delivery together. Convert nested ZIP/gzip archival layouts offline when
they force whole-bank access; keep the lossless source archive for provenance.
Publish resource byte totals and CPU/GPU residency estimates before/after packing.
Maximum texture size comes from the actual renderer; no giant atlas assumption.

Loading owns four explicit states: fetched, decoded, uploaded, ready. Shared
TextureSource/texture views avoid copies for facing/crop reuse. Integer planes use
explicit formats and nearest sampling. UI smooth icons use linear sampling.
Preload the visible scene, active actors and dependency closure of upcoming groups;
background-fetch likely action choices within a byte budget. Release inactive
scene/Studio leases. Camera pan only changes transforms/culling; it does not decode
images, recolour source pixels or rebuild all terrain. Switching camera may need
another authored bank, but not duplicated unrelated resources.

Appearance/depth/normal companions become ready and release as one coherent frame
set. The existing resource owner shares sources across crop views, cameras and cast
ages; destroy a source only after all its leases release. Evicting one region must
not invalidate another live crop or companion-plane consumer.

Decode/unpack in bounded worker jobs, upload under a measured frame budget, and
prepare the finite shader variants before their first interaction. Use Pixi's
pinned GC API and explicit leases; GC is not a substitute for ownership. Handle
WebGL context loss by rebuilding GPU resources from retained release references,
not reconnecting/replaying game rules or losing the current recording.

### 7.1 Exact resource records, leases and scheduling

`src/render/resources.ts` is the only page/source owner. Its passive map is keyed
by `(payload hash, width, height, GPU format, dimensional layout, encoding,
sampling, alpha convention)`; logical asset IDs and
cropped Texture views point into it. Existing source data decides compatible sharing.
Numeric and colour interpretations never accidentally share a TextureSource merely
because their byte hashes match. Immutable downloaded payload bytes may share by
hash alone; texture interpretations may not. No per-spell manager, camera cache
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
draft replacement, seek or scope reset. Shared references keep a source alive until
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

At export/install, verify all selected resource hashes, plane geometry and source
references once. Boot loads metadata plus the active closure, not a full-library
decode/hash pass. First/repeat/rotated/seek/context-loss cases report fetch/decode/
upload counts to expose accidental reloads. Implementation may tune numerical
budgets to measured hardware; it may not add another owner or discard content.

## 8. Studio: actual engine cases, one production runtime

### 8.1 Case inputs and recording

The primary fixture is current SDK **InitializationResponse + ordered
PlayerOperation records**, with the release hash, authorized audience, case label,
public content, playback interval and review tags. Record once and replay many
times/cameras/material revisions. Native `native.json` is never served to Studio.

Live cases run the engine through normal SDK choices/preview/commands. Existing
native review producers can also supply deterministic difficult cases; extract
reusable scenario setup from test-module imports into one development producer
owner, preserving actual native execution. Export their subjective output through
the current protocol projection. Do not construct success, damage or condition
application inside a TypeScript preview helper.

Old saved player-sequence review files need an explicit one-time import/recapture
tool with source-version validation. Remove stale player-v2 labels. Never turn that
compatibility tool into a second live decoder. Pure visual fixtures for geometry
are allowed and clearly labelled; they cannot demonstrate a gameplay trigger.

### 8.2 Workspace and inspectors

One workspace provides spell, action, condition, environment and material views.
They are different selections/inspectors over the same runtime and source map.

| View | Complete required editing/inspection |
|---|---|
| Creature/rig | Modular and fixed rigs: source/semantic clips, actual frames/rates, facing rows, pivots, depth/rest anchors, per-frame sockets, context bindings, original accents, native wings and explicit missing capabilities |
| Cast/action | Exact content/variant, rig/clip, FPS/rate, release and contact frames, sockets, recovery/hold, Magic/Effect/gear layers and masks |
| Spell delivery | Repeated/multiple targets, path curves, camera/direction basis, banks, release/travel/arrival, areas, directed media, cancellation and child attacks |
| Condition/lifecycle | Actual causes and expiry, suppressed/active state, application/removal phases, size anchors, head playlist, concurrent body/ground materials |
| World | Registration, slope/elevation, walls/doors/apertures, formation/visibility commits, surfaces, construction sections, receiving faces |
| Materials | Exact palette/override, ramp/gamma/noise, isolated source mask and donor texture, alpha/blend/depth behavior, item versus body ownership |
| Resources | Source/packed bytes, planes, original/effective FPS, camera bank, residency, source provenance; derived packing fields read-only |
| Timeline | Recorded event tree/cause links, release/contact/commit anchors, received versus displayed state, condition intervals, material envelopes |

The existing motion/effect semantics remain authoritative reference:
`agent_docs/art/MODULAR_CASTING_CATALOG_2026-10-04.md` and its JSON. Ground impact,
sky invocation, pointing and beam gestures have meaning. Do not reset assignments
to one action/Magic2/Effect4, and do not distribute effects just to vary a chart.
Show the actual combined body, modular layers and external VFX at matched palette.
Original source animation and compiled timing can be compared side by side.

#### Channel timeline: animator workspace over the real presentation data

Retain the Adobe/Godot animator-style workspace: hierarchical channel list on the
left, aligned clip/curve lanes against a shared time ruler, a playhead and loop
range, and the selected channel's inspector beside the production viewport. Recover
NeuroClient's `StudioTimelineLayout`, `StudioTimelinePixi` and useful view controls;
replace old spell/action/condition-specific timeline construction with projections
of the shared presentation compiler output and existing authored records.

The timeline is a view of what playback actually samples, not another animation
format or executable editor graph. Load the canonical presentation release/source
map and the selected subjective recording, compile through the production path,
then derive rows and their source references. The same compiled occurrence has the
same timing whether Studio is open or closed. No second Studio schedule may guess
release/arrival, expand targets differently or hide missing runtime channels.

| Channel group | Actual data shown |
|---|---|
| Body and attached layers | Rig/clip frames, equipment, Magic/Effect layers, recovery/hold, socket/anchor samples |
| Delivery and motion | Each actual projectile/beam/area occurrence, travel path, repeated recipients, movement/portal phases and attachments |
| Material and appearance | Existing palette/material bindings, authored envelope points, fades, supported timing maps and enabled layers |
| Reactions and lifecycle | Damage/healing/death, interrupts, condition application/sustain/removal/suppression, summon/despawn and marker intervals |
| World and deposits | Formation/retirement, door/prop transitions, blood release/landing, ground/deposit contributions and presentation commits |
| Causality and recorded facts | Read-only event ancestry, recipient/outcome identity, release/contact dependencies and displayed-state commit markers |

Group by actual occurrence/owner and cause, with expandable channels and distinct
lanes for repeated applications. Do not force every recording into one caster,
one projectile and one target. Source-time/frame ruler and resolved presentation
time remain distinguishable; mixed source FPS, playback speed and loops never
become one fictitious fixed frame clock.

Generic lane/clip/curve/marker widgets operate on a lightweight **derived UI view**.
Finite typed adapters connect each supported authored record kind to its existing
fields, units and editing constraints. JSON shape alone cannot infer whether a
number means source frames, milliseconds, strength or an event identity. No
spell-name branches, reflection guessing or general-purpose keyframe/node DSL.
Not every property is arbitrarily animatable: curve handles appear only for actual
authored point/envelope/time-map fields; fixed parameters use their inspector.

Dragging an editable clip edge, offset, source-frame marker or curve point produces
the same typed source edit as its inspector. Preserve the authored clock/reference:
moving release updates dependent occurrences through recompilation, not by saving
a second set of absolute times. Derived arrival times and native damage/outcomes
are read-only; selecting them reveals their cause/source. A shared recipe edit is
labeled as shared and updates all its usages; a per-use override is available only
where an existing source field supports it. Unsupported gestures are disabled.

Expansion, zoom, selection, scroll, diagnostic mute/solo and loop range are editor
preferences, never a competing saved presentation model. Mute/solo hides visuals
only; it does not remove native events, shift causality or change outcomes. Authored
enablement is a separate explicit source edit. Undo/redo uses the same draft edit
history as inspectors; save/reload follows §8.3, with canonical fields preserved.

Required acceptance: a repeated-target projectile cast, an interrupted movement/
reaction, and a persistent condition/world lifecycle expose every sampled channel
and its provenance. Timeline/inspector edits, undo and save/reload produce identical
production sampling at matching times, including backward seek. With the timeline
closed, those cases still play identically. New content using existing record kinds
appears without adding a spell-specific lane builder.

### 8.3 Time, save and preview

Pause, speed, single-frame step, scrub backwards/forwards, loop selection, switch
cameras and compare an A/B draft all use an absolute sample time. Seeking restores
a retained checkpoint and reduces the required prefix; it never reruns native rules,
adds new damage or assumes a constant 15/30-frame clock. Gear/vitals/condition/portal
handlers run exactly as in play. Missing a handler is an error with its case/ref.

Edit a source draft in memory; compile its dependency closure and preview with that
draft revision. Saving sends exporter-issued document identities, typed pointer
edits and expected base revision to the local tool. Identities resolve through an
explicit allowlist of editable canonical source owners; root confinement alone is
insufficient and browser-supplied filesystem paths are not accepted. Validate the
edited document against existing semantic rules and its expected revision, then
write a temporary sibling and atomically replace that canonical document. Never
overwrite a merged effective catalog over source files. Reuse the exporter's
dependency mapping to refresh affected presentation data and publish a complete
index only when its referenced resources exist; unchanged assets are reused.
Failed publication leaves the previous release active and reports saved-versus-active
revision honestly. A parameter edit does not trigger a full-library repack or SDK
generation. Do not build a generic multi-file transaction/recovery service for
ordinary document edits. If an actual supported edit must change several owners
together, scope coordinated saving to that operation and prevent partial activation;
never claim that individual file replacements alone make such an operation atomic.

Distinguish saved source revision, compiled preview revision and active release.
An active play group pins its revision through completion. Studio deliberately
restarts/reseeks affected presentation when applying a new draft. Conflicting source
edits return a concrete conflict instead of silently overwriting another author.
The tool is development-only, root-restricted and not part of the public game server.

Creating a rig from an already registered source bank uses a tool-side create-draft
operation. The tool checks the existing rig identity namespace and allocates the
canonical source document identity under the rig source directory; the browser
submits typed rig data and a source-bank reference, never a path. That new identity
joins the same source map/allowlist and document-save path. Production selection and
creature binding remain explicit edits; a draft cannot overwrite an existing rig.

### 8.4 Diagnostics available during actual use

Show optional FPS/frame-time graph, CPU reduction/compile/sample/submit cost, GPU
time when the extension is available, decode/upload bytes, draw calls, residency,
long tasks, queue age and command/receipt/consumed/displayed latency. Display
"unavailable" for unsupported GPU timing, not an invented number. Switching camera,
panning, casting and editing use the same instrumentation in play and Studio.

Export a shareable recording/reference and optional capture from the current view.
Video rendering is optional documentation, not the proof that interactive FPS works.

## 9. UI and interaction parity

Use [the explicit comparison matrix](NDCLIENT_INTERACTION_PARITY_2026-10-08.md),
including Pygame's final-frame picking, cutaway, party knowledge and native targeting.
Reuse useful NeuroClient grid/input/UI functions only after removing its old store
and SDK assumptions. Preserve behavior; copying a module name is not a requirement.

Four compact bar blocks: base actions with separate melee/ranged, spells, class
abilities, usable carried items. Multiple rows only as needed. Uniform same-size
hover icons for upcast levels and real variants; no excessive text, fake buttons,
duplicate Dash, second click on a legal self action, or confirmation for an action
already unavailable. World interactions are click/Alt driven, not bar clutter.

Small party and initiative portraits; selected party member and current actor are
distinct. Copyable, aligned combat log with recorded dice/modifiers, grouped movement
legs and blood/deposit children, retained event-time names for dead/out-of-sight
actors. No new narrative engine. Inventory and details use the same restrained glass
panels; log open does not move the bar. Tooltips carry explanations, not permanent
HUD labels. Text remains readable antialiased text.

Install the delivered [new icon bank](UI_ICONS_BG3_FULL_BANK_HANDOFF_2026-10-07.md):
620 exact keys / 594 glyphs and 103 choice bindings, using smooth 144px sources to
start. Keep touching slot layout and authored images; disabled/selection states are
clear overlays, not darkening every icon. Keep existing accepted portraits. Exact
content/direct-feature/direct-item namespaces remain distinct. Final in-game sizing
and readability need visual acceptance; file validation is not art approval. Icon colour does
not decide spell VFX colour. No fallback to the old bank to hide a missing binding.

## 10. Concrete delivery sequence

Stages organize the full scope and ownership; they are not all-or-nothing gates.
Use the specified field owners and integrate each capability as its actual inputs
become available. Current work is foundation repair planning under the linked
[repair phase](NDCLIENT_FOUNDATION_REPAIR_PLAN_2026-10-08.md). After explicit
resumption, complete that repair, then execute the remaining full scope;
checkpoints are progress reports, not substitute
deliverables or a reason to stop after making a creature walk. Do not create a
new demo app, a reduced release protocol or another temporary renderer. Preserve
the accepted Fireball study only as the already named representation evidence.

| Step | Implementation | Required evidence and review |
|---|---|---|
| N−1 — completed design, before implementation | Exact owner-local fields, family representations, native reach/cancellation amendment, resources/history and full release contract | Source-grounded full-plan anti-slop + ECS readiness review; accepted demo remains evidence, no additional standalone app |
| N0 — source and contract integration | Retain repo/reference snapshot; SDK connection; shared TS reduction; existing-owner export/source map and complete asset installation; integrate usable media immediately and convert where the consumer requires it | Real SDK command/streaming in production client; scoped prefix comparison; final asset closure accounts for all selected dependencies; anti-slop + ECS review of changed boundaries |
| N1 — depth/material foundation | Integrate the proven compact representation, production projection, alpha/depth composition, grid, point picking, colour/material/light sampling and resources | Four-camera elevated/aperture/transparent overlap scenes against recorded state snapshots; honest frame/byte measurements; no temporary alternative reducer |
| N2 — shared temporal path | TS reduction/index/history; causal compiler, retained state, absolute sampler; live follower; first real-event Studio workspace | Python/TS prefix parity on scoped actual recordings; A/B/A targets, reaction/death, equipment/conditions, backwards seek; no display-blocked consumption |
| N3 — complete operator families | All R01–R23 production consumers and schema fields; world/action/condition/material inspectors; canonical edit/save | Per-family real events plus all selected references resolve; no unhandled fallbacks; source edit/reload preserves other fields; review at independent family boundaries |
| N4 — playable UI | Entire parity matrix; new icons; fighter+sorcerer crypt and goblins; multi-controller audience behaviors | Real browser exploration/doors/loot/trap/combat, multi-target/variants, reconnect, party split sight; keyboard/pointer/focus coverage |
| N5 — full acceptance | Complete authored-catalog and scenario coverage, real-time profiles, docs/launch scripts, final cleanup | Independent anti-slop and anti-OOP/ECS/DAG approvals against final code; issue-indexed Studio cases, not just a few clips |

N−1 records the design. N0 establishes the existing-owner data boundary and starts
complete asset installation; it does not hold the application until every conversion,
checkpoint optimization or receipt is finished. N1 integrates the selected representation into the
one production renderer. It does not reproduce Python's alpha-dependent mean-depth
sorting, full runtime XYZ arrays or restart a compositor competition. If a measured
combined wall/dome/blood/ground case fails, correct the responsible shared operator;
do not let later spells invent workarounds.

N0 establishes the single TS reduction path. N1 consumes its displayed data; N2
connects real operation playback. N3 completes catalog and Studio support, while N4
UI work uses the same working capabilities as they land. Each runs in the production
application. Unrelated incomplete families do not block integration; they remain
required work before full delivery. No separate demo release substitutes for it.

N0–N3 include **all installed selected assets**, not just VFX: modular sheets and
equipment, all 44 rigs including the 43 fixed sprite registrations, animated
environments/doors/windows/props/destruction, masks/companions, UI and any currently
registered audio. Resource migration is a private derived release, not deleting
the originals or tracking binaries in NDClient Git. Selected release bytes are
explicitly copied into its ignored local media directory (§2.1 of the asset chapter).
N3 includes the
full creature/rig editor, not merely a human-body dropdown. NeuroMapEditor's
multilayer-grid concepts are mapped in the rendering study; its authoring ZGrid
document does not become another gameplay world model.

## 11. Acceptance and performance without gate theatre

Use existing native cases and one parameterized browser harness; do not create a
test file per spell. Every authored identity is accounted for, while coverage cases
exercise meaningful combinations: repeated targets, outcome branches, lifecycle,
rig sizes, four cameras, elevation, materials and privacy. User-reported defects
each link to a visible Studio case, expected behavior and evidence.
Use exact parity for native reductions/recorded outcomes, timing dependencies and
explicit palette substitution. Judge rendering against intended appearance,
registration, physical intersections and disclosed information—not equality with
Pygame's intermediate pixels, draw counts, cuts or cache entries. Reviewers must
reject mechanical ports that preserve those costs without a target-native reason.

Measure independently: server command work; wire/SDK reduction; asset fetch/decode/
upload; compiler/sample; GPU render; HUD/DOM. Do not call a fast End Turn benchmark
proof of Fireball or a prerecorded capture proof of a responsive client.

Proposed baseline: 1280×720, 1920×1080 and actual monitor resolution, up to 2560×1440
when that is the available display. Record physical framebuffer size and browser
DPR. Do not claim 4K visual acceptance without the user's monitor. Measure
frame-time distributions and worst frames during idle, continuous camera movement,
input, dense effects and condition/equipment changes. The goal is smooth interactive
play on the actual display with responsive input and no recurring loading hitches.
Separately report cold/warm first play, first/repeated casts, upload stalls and
native/network time. Do not turn unmeasured startup, first-use, percentile or memory
numbers into pass/fail requirements; a number below an invented threshold is not
evidence that the experience is acceptable.
Exercise repeated scene/cast lifecycles and real encounter play to find accumulating
resource leaks, separating retained history from live working resources. Choose
targeted run length from the suspected failure, not a fixed minutes/operations
ritual. Preserve artwork, source rates and all semantic outcomes. The separately
requested Fireball remains 24 FPS with its selected v4 manifest duration.

Run targeted checks after meaningful changes, then one complete acceptance pass.
Regenerate authored types only on deliberate schema changes. Do not repeatedly run
an expensive full suite, regenerate both SDKs or expand unrelated rules to satisfy
a speculative gate. Two independent reviewers assess the final implementation and
each independent boundary; record findings and fixes, never claim approval from a
test count alone.

## 12. Completion and remaining proof

Completion means a playable encounter and fully working in-engine authoring/replay
for current content, with the interaction matrix and renderer families covered.
No requirement is satisfied by a screenshot of a disabled control. Missing accepted
source capabilities must name the exact binding and affected cases; no generic
"other VFX later" category hides omissions.

The initial planning pass downloaded docs, read source and enumerated metadata.
The later standalone demo now proves the bounded depth/normal/light behavior and
reports real browser observations in the [proof receipt](audits/ndclient-plan-20261008/FIREBALL_PROOF.md).
It does not complete NDClient, general wall contact, concurrent streaming, combined
families, production audience lighting, SDK browser integration or the playable UI.
The later stopped scaffold in §0.3 adds repository/setup work but does not change
those acceptance limits.
No fresh runtime tests are required merely to reconcile these documents.
Review findings and disposition are recorded in
[PLAN_REVIEWS.md](audits/ndclient-plan-20261008/PLAN_REVIEWS.md).

## 13. Complete renderer coverage in the current design

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
| R07 Media/resources | Existing source registration, compact derived delivery specified in the representation chapter, shared source/region views and bounded readiness | Coupled crop/pivot/mask alignment, first-use, four-camera switching and unload; N0/N1/N3 |
| R08 Projectiles/beams | Absolute path/socket sampling, bank plus permitted residual alignment, release/arrival and child application timing | Oblique elevated Fireball/rays, beam source continuity, Magic Missile A/B/A, interception; N2/N3 |
| R09 Areas/volumes | Compact registered geometry, actual ownership/exclusions, support/aperture and transparent composition; no floor-visibility stencil | Continuous Fireball/Sunburst/Sleep, inside/outside actors, suppressed or upper-only regions; N−1/N1/N3 |
| R10 Layer/blend ordering | Shared physical composition with stable ties, sibling order, normal/add/screen and complementary samples | Two transparent volumes and a body, checkerboard alpha, near/far crossing; N−1/N1/N3 |
| R11 Directed materials | Finite authored ribbon/mesh/plasma operators and donor sampling | Existing noise ribbon, darkness mesh and plasma trail with moved/raised endpoints; N3 |
| R12 Constructions | Source-authored paths/sections/rings/domes and formation/retirement commits | All installed wall types, arbitrary permitted angle, fire hot/safe side and dome destruction; N3 |
| R13 Particles/trails/intake | Analytic seeded tracks and bounded shared geometry; item/weapon/body attachment follows presented sockets | Blood/bone/vapor, critical/multiple victims, weapon trail, orbit/intake and backwards seek; N−1/N3 |
| R14 Conditions | Current owner/phase/suppression data, shared body/ground effects and head-only marker playlist | Multiple owners, size variants, suppressed expiry/removal; no overlap or body-VFX rotation; N3 |
| R15 Owned lifetimes | Shared retained item/spatial/concentration state with occurrence identity and cold-acquisition rules | Suppressed Shield expires; re-observation is not reapplication; removal retires only its owner; N2/N3 |
| R16 Movement/portals | Received legs/modes/connectors with reaction holds, relocation/absence and ground-to-ground flight | Ally corridor, jump/window, interrupted movement, ledge landing, one-end portal visibility; N2/N3 |
| R17 Feedback/lifecycle | Actual damage/heal/save/temporary-HP/death/summon facts revealed at authored contacts | Lethal OA at doorway; sleep/rest/death; summon/despawn/hostility and real blood impacts; N2/N3 |
| R18 Deposits/ground/water | Native contribution ownership; receiver-local settled coverage and finite changing materials | Fresh/old stains, wall soot, raised floor, response/removal, witnessed break, rewind; N−1/N3 |
| R19 Spatial contacts | Recorded entry/exit/activation/response facts resolve existing recipe primitives | Hot-side spread before feedback, ignition/extinguish already implemented, suppression; N3 |
| R20 Temporal orchestration | One typed reduction/index, causal compiler, retained facts and absolute sampler; no animation-owned gameplay | Delayed resources, slow/pause, queued AI, reconnect/reload and historical scene/HUD/log agreement; N2 |
| R21 Picking/highlights | Presented supports/physical masks and common transform/occlusion/cutaway policy | Known door/item set stable across cameras, click through cutaway, Alt, Ctrl attack; N1/N4 |
| R22 Player UI | Recovered/adapted Pixi widgets and DOM text panels on shared displayed views and exact SDK gestures | Complete interaction matrix, four bar blocks, multi-target/variants, inventory, copied exact log; N4 |
| R23 Studio/capture/replay | Same production runtime, actual SDK recordings, canonical authoring source and optional capture | Seek/edit/save/reload actual spell/action/condition/rig/world case with diagnostics; N2/N3/N5 |

Lighting spans R02–R06/R09/R18/R21 rather than becoming another world simulation.
Recorded categorical effective light is smoothed only across admitted compatible
supports; body/item receiver treatment, emitters and head/UI exemptions follow the
rendering chapter. Existing audio, if selected in current registrations, follows
the same contact/lifetime clock and resource owner; seeking does not replay all past
one-shots. No new sound content or independent audio-event schema is implied.

All selected identities remain required, including aliases and rare outcome paths.
An example proves its capability; catalog mapping/semantic validation establishes
that every selected recipe and rig has a supported consumer. Both kinds of evidence
are needed. New source content appearing during implementation is compared against
the pinned inventory once and folded into its existing family, not silently omitted.

## 14. All reported playtest problems remain acceptance cases

The [original ledger](audits/PLAYER_PLAYTEST_REPAIRS_2026-10-06.md) preserves source
reports and historical diagnoses. The table below is the current acceptance contract,
not a claim that every old native bug remains unfixed. Use the delivered native
behavior where already corrected; do not reimplement it in the browser. Each row
gets a real recording or live input case plus a result in the final issue index.

| ID | Required result in NDClient | Principal proof boundary |
|---|---|---|
| P01 | Two opened doors and an ally in the corridor do not route into a corner | Native preview/committed path + live click |
| P02 | Visible path is the submitted route; interruption shows its committed prefix | Native route + presentation |
| P03 | Pass through allies, finish on an admitted free destination | Native movement + presented overlaps |
| P04 | Walls covering visible ground fade automatically and allow intended picking | Rendering/picking |
| P05 | First playable scene meets separately measured cold/warm startup targets | Server/import, release/decode/upload and browser stages |
| P06 | Continuous WASD/pan/zoom/rotate does not rebuild or decode the scene | Interactive frame profile |
| P07 | Disclosed enemy initiative entry has the correct portrait | Admitted identity, binding and historical HUD |
| P08 | All projectile families select direction and align to travel; authored speeds make sense | Four-camera oblique/elevated real-event cases |
| P09 | Hand/cast material matches the resolved spell palette unless explicitly overridden | Shared source material and visual comparison |
| P10 | Native AoE/path/impact preview is visible and matches the command | Preview, geometry, ordered target input |
| P11 | Optional readable FPS/frame-time diagnostics work during actual play | Browser instrumentation |
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

Earlier UI requirements also remain explicit: restrained consistent proportions,
small party/initiative portraits, readable non-pixelated text, no permanent helper
text flood, no gratuitous icon darkening, stable compact four-block bar, minimal
same-sized hover choices, aligned glass log/details/inventory and working copy.
Combat log uses existing typed dice/modifier data; movement steps and blood/tile
children group under their cause. No narrative/log duplicate is introduced.

Prior spell review regressions are included in R08–R19 cases: palette failures and
missing hand layers; incorrect sockets/beam jumps and oblique directions; clipped
area silhouettes; delayed curse/chains, condition scale/markers; sleep pose and
prone death; physical/visibility/light commits ahead of formed art; portal timing;
and inappropriate motion/effect combinations. Existing fixes are regression inputs,
not an invitation to reauthor accepted spells. Studio must expose the corresponding
case and timeline so review does not again require hundreds of videos to locate it.

## 15. Implementable work packages and dependencies

The stage table in §10 gives the order. These tasks identify concrete ownership,
output and the proof that closes each stage. Review is at independent boundaries;
it does not require permission or full-suite reruns after every function.

### N−1: settled design and independent readiness review

This is documentation work completed before production resumes. Its outputs are
§0.4, §4.2, §5.5, §7.1, the representation chapter's exact type/family/algorithm
contract and occlusion §1.1. No new proof app, art production or benchmark run is
required to finish planning. Reviewers must assess the **complete implementation
specification**, including source fields, import direction, unknown/private cases,
release/lease lifetimes and delivery of every R/P row—not just approve its scope.

Known measured limits remain evidence: the historical v1 four-distinct-age run
buffered about 1.87 seconds; the v4 single-cast hookup did not measure that repaired.
N1 must resolve production paging/decode/upload scheduling and N3 must pass the
combined volume/blood/deposit cases. The selected representation is fixed; acceptance
failures cause bounded repairs, not per-spell representation design.

### N0: establish the reusable client and complete source boundary

1. Retain and verify the existing WSL NDClient repository, reference/proof snapshots,
   ignore rules and packaged SDK setup. Complete the unfinished parts of the asset
   chapter's §2.1 runbook: build/copy the complete selected private release locally
   and keep the pinned dependencies. Do not recreate the repository or repeat
   snapshots/installations merely to count a new checkpoint. Verify ignored media
   and a source-only candidate change set.
   Adapt only selected source functions with old ownership dependencies removed.
   Start with ordinary modules, not a client framework.
2. Import the delivered SDK. Configure the actual browser origin in the server's
   existing `allowed_origins`; exercise bootstrap/seat attachment/streaming fetch,
   content admission, preview and one legal command from the Windows browser against
   the chosen Windows or WSL host. Verify reconnect. Do not add a new socket transport
   or loosen CORS globally to bypass a local setup mistake.
3. Establish the single TS `player/` reducer and indexes over SDK records using
   native recorded prefixes. Introduce checkpoint data only as derived retained
   state for seeking; do not generate another wire type or transport serializer.
4. Extend `game/presentation_export.py`/`game/export_schema.py` at their existing
   presentation boundary with complete world/environment/UI/resource sections and
   tool-only source map. Use source types/validators from the field ledger. Implement
   the exact contract specified in N−1, generate authored TS types once, and perform the
   one-time media-registration migration. Authoring export does not regenerate the
   player SDK. **One narrow exception:** if the finalized native reach/cancellation
   attribution changes the player facts, update those existing producers/projectors,
   export their owner schema and regenerate the existing SDKs once, then pin that
   revision. No copied protocol, second SDK, repeated per-edit generation or new
   server architecture is authorized by that correction.
5. Package the entire selected dependency inventory to private immutable resources.
   Player startup loads the scene closure, not the archive. Test clean relocatable
   loading without private absolute paths and verify no selected identity is lost.

Concrete file boundaries (ordinary functions, no new framework):

| Owner | Implementation responsibility |
|---|---|
| `dnd/types/event_facts.py`, `dnd/core/gridmap.py`, existing spell/event owners | Cold reach evidence from existing connected/FOV queries; AoEShape/base-action publication and AreaCondition/PerceivedSpatialEffect retention; existing stages/revisions |
| `dnd/core/events.py`, `dnd/player/{capture,facts,projection}.py`, `dnd/spells/abjuration.py` | §5.5 cancellation record, privacy projection and admitted content references |
| `game/animation_types.py`, `game/environment_art.py`, existing rig/world/prop type owners | Representation chapter's finite fields; existing clocks/IDs retained |
| `game/presentation_export.py`, `game/export_schema.py`, existing media packers and fracture exporter | Complete export, canonical schema, geometry conversion and derived private release |
| `src/session/{connection,journal}.ts` | SDK adapter and §4.2 durable retention; only these open transport/database |
| `src/player/{reduction,history}.ts` | SDK-value reduction, native-compatible indexes, passive prefix checkpoints |
| `src/render/{resources,projection,geometry,materials,compositor,picking}.ts` | §7.1 leases, coordinates, compact geometry, finite shaders, depth composition and shared presented picker |
| `src/presentation/{compile,sample,retained}.ts` | Existing recipe/causal/lifetime semantics across every fact family; immutable compiled views and absolute-time samples |
| `src/ui/`, `src/studio/`, `src/app/` | Interaction matrix, actual-event timeline/editing, explicit application composition |

Names may follow an already equivalent module in the scaffold; responsibilities
may not split into duplicate implementations. Native types never import `game/`;
player projection never imports raster/media code; source export depends on cold
authoring values, not the running browser. `session` may call pure player reduction;
`player`/`presentation` cannot import session/UI/render. Renderer receives passive
sampled draws and explicit resources; it does not call back into the event compiler.

### N1: integrate shared rendering and interaction geometry

1. Adapt projection/grid/sprite/resource functions into `render/`; integrate the
   N−1 geometry/material functions once. Depth-capable world quads explicitly batch
   compatible inputs; ordinary Sprite batching serves depth-free UI/resolved overlays.
2. Implement §6.1's common depth/alpha passes, registration, support-light and cutaway paths.
   Floor, wall, actor, item and VFX must use the same spaces and declared receivers.
3. Build the pointwise picker on the presented scene with the same masks/transforms;
   return admitted identities/supports, never independently decide action legality.
4. Exercise every rendering chapter proof scene on known snapshots, including scale,
   alpha and device-pixel ratio. Historical transition correctness completes in N2.
   Check resource ownership and recovery as those paths are integrated. Do not hold
   unrelated content/UI work behind those checks or claim ordinary sprite success
   proves volume success.

### N2: one event-to-presentation path in play and Studio

1. Complete the durable journal/consumption and displayed-checkpoint protocol in §4.
   Use existing SDK follower/receipts; prepare resources independently from intake.
2. Compile existing event ancestry and authored recipes into causal groups with
   release/contact/commit dependencies. Preserve repeated targets, interruption and
   multiple concurrent causes; sample retained actors/items/effects at absolute time.
   Account for every implemented fact branch as a presented occurrence, retained
   state change, or explicitly nonvisual observation. Do not give an unsupported
   attack/reaction/condition/world transition zero duration and jump to its final
   state. Port existing lineage-index/branch and retained-lifetime semantics from
   `dnd/player/reduction.py`, `game/presentation_group.py` and
   `game/presentation_retained.py`; do not copy Python raster intermediates.
3. Bind displayed world, light, vitals, equipment, portraits, bar and log to those
   commits. Preserve latest state solely for transport and authoritative choice checks.
4. Create the first Studio case loader/timeline on these exact functions. Import or
   recapture versioned subjective recordings through the current SDK format; never
   synthesize native success/damage. Enable pause/step/reseek/camera and diagnostics.
5. Close the slow-playback/backlog/reload/history-expiry/privacy case in §4.1 and
   replay N1 scene transitions through actual operations. There is one TS reducer,
   one compiler/sampler and one resource owner for play, Studio and captures.
   Retained local playback must open without contacting a still-live server. Pin
   the presentation release/authoring revision with the retained record prefix and
   displayed occurrence/time; do not substitute whatever release is current after
   reload. Scope changes clear the actual canvas/HUD and invalidate pending old
   preparation before a new audience attaches. Idle clips, persistent materials,
   environment loops, emitters and feedback use the presentation clock too; passing
   browser wall time to those consumers defeats pause and deterministic seeking.

### N3: all authored content and all editor fields

1. Complete remaining R families using shared primitives. Record selected recipe,
   binding and rig support against the existing inventories; inspect every field's
   current source owner, including validators and external item visual ledgers.
2. Deliver rig/action/spell/condition/world/material inspectors with meaningful
   controls, source provenance, original/effective timing and visual handles. A raw
   JSON display is not the completed editor. Use all 44 rigs through the same path.
3. Implement typed candidate edits, dependency recompilation, A/B preview and canonical
   save/create-draft operations from §8.3. Keep source/preview/active revisions distinct,
   test conflict/interrupted save and preserve unchanged fields/override ownership.
4. Run family boundary cases and parameterized catalog checks. Existing fixture
   producers remain native; share their setup without importing test modules in the
   application. All selected media/resources/rig contexts must resolve before N4
   can be described as content-complete, even if UI development overlaps.

### N4: actual encounter and complete interaction

1. Adapt existing NeuroClient HUD/inventory/portrait and DOM-log helpers to shared
   displayed views. Integrate delivered icon/portrait banks with exact namespaces.
2. Complete every interaction row: camera/focus, local hover, automatic cutaway,
   Alt/Ctrl/world defaults, approach/rediscover, ordered targets and native previews,
   bar/resource variants, one-click self actions, loot/equipment and copied log.
3. Default directly into the authored Fighter/Sorcerer crypt; no character-creation
   detour. Prove exploration, split rooms, trap, loot, doors and goblin fight in real
   browser input. Check party-controller, per-unit controller, all-AI opposing side
   and mixed human/AI configurations using current server seats; no new lobby.
4. Check live window sizing/focus/fullscreen, keyboard/pointer cancellation and
   sustained play at supported resolutions. UI coherence requires visual inspection
   of whole screens and actual gestures, not only aligned isolated widgets.

### N5: finish, measure and hand over

1. Run the finite full acceptance corpus, with exact recorded reduction/commit
   comparisons plus family/issue-indexed Studio views. Ensure every R/P and selected
   identity is accounted for; correct defects in the responsible owner.
2. Measure actual warm/cold session startup, idle/pan/rotation/casts, first use and
   sustained encounter play. Attribute native, network, browser CPU and GPU time
   separately. Media packing, uploads and retained history each report their bytes.
3. Provide repeatable launch commands for the existing server and WSL frontend,
   connection/seat setup, private release copy/install, Studio case import/edit/save and
   profiling. A fresh launch must not depend on an agent's orphaned preview process.
4. Remove superseded experiment paths, old SDK/FSM imports, debug-only defaults and
   temporary double renderers. Preserve source/reference repos and source artwork.
5. Both reviewers inspect the final implementation and the requirement/evidence
   matrix. Close only after blockers and required behavioral/visual/performance
   failures are fixed; a test count or a nice clip is not whole-product acceptance.

## 16. Scope control and exact meaning of validation

This is one client/authoring delivery using the existing server. It does not restart
server design, introduce a third reducer, commission new art designs, add missing gameplay,
revive narrative rendering, redesign AI or build a campaign/account/lobby service.
The explicitly requested Fireball re-export is the sole new artwork-author task;
Globe appearance/registration and existing scene art are reused. No new weapon,
UI or creature artwork, or messaging of the artwork thread, is implied.
Replay/history restoration is not a claim of whole-world save/load. Native browser
integration defects belong to existing native owners and are reported separately;
remaining engine latency is measured against the server closure evidence, never
hidden by responsive GPU drawing or counted as a new frontend achievement.

The plan fixes ownership, fields, algorithms, coverage, sequence and required
outcomes now. N−1 is design closure; performance and visual measurements belong
to N1/N3/N5 implementation acceptance. Implementation can
still expose defects; each has a named capability/owner and required case, rather
than permission for another ad hoc system. A changed requirement updates its one
owning chapter and the corresponding master row, not another competing plan.

Plan review is source/design review, not proof of running code. The shared receipt
records full-bundle anti-slop and anti-OOP/ECS/DAG/privacy findings and their disposition.
Interactive frame rates, final lighting/composition, browser SDK integration and
user-facing quality remain concrete implementation acceptance obligations.
