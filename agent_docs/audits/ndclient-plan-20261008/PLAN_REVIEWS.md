# NDClient plan review receipt — 8 October 2026

This file retains historical review entries. **Current work is documentation
cleanup; production remains stopped.** The earlier implementation-readiness
approvals did not justify the speculative quotas and prerequisite work the user
subsequently rejected. The cleanup below supersedes those prescriptions; historical
review comments and measurements remain evidence, not current implementation rules.
No review approves the partial scaffold or resumes production.

Scope of this cleanup: documentation only. No client implementation, runtime tests,
asset import/packing, GPU measurement or artistic approval occurs in this pass.

## October 8 — remove speculative prerequisites from the active plan

The master, recovery entry, asset and representation chapters, Fireball handoff,
lighting/occlusion notes and Pixi component review now agree on these corrections:

* Remove fixed page/cache/journal quotas, checkpoint/write frequencies and invented
  latency/startup/stability thresholds. Keep actual device limits, authored values,
  measured historical evidence and meaningful performance investigation.
* Reuse accepted media and suitable sheets. Convert for an actual consumer's format
  or access requirements; repack only for a demonstrated benefit. Full content
  delivery remains required, but complete-library optimization is not a prerequisite
  to production integration.
* Retain one durable private journal and independent presentation progress without
  mandating multiple disk commits per operation or a storage quota.
* Keep canonical source identities, revision checks and atomic document saving.
  Do not build a generic multi-file recovery service or repack the library for a
  normal Studio edit; coordinate multiple owners only when an actual edit needs it.
* Use source calibration and observed conversion errors rather than newly invented
  universal pixel/cell/normal tolerances.
* Organize N0–N5 by real dependencies. Integrate renderer, playback, Studio and UI
  as their inputs land, in one production application. Full R/P/content coverage
  and final independent reviews remain; no small demo replaces the requested game.
* Make the current stop explicit and remove conflicting resumption language.

Independent local reviewers `plan_cleanup_antislop` and `plan_cleanup_ecs` completed
one read-only pass on this correction. Both found two remaining instructions:
packing all loose frames and waiting for full installation before any integration.
Both were removed at their source. The anti-slop reviewer also found historical
Fireball delivery instructions still written as pending work; those now explicitly
record v4 and the preview as delivered. The ECS reviewer confirmed retained schema,
SDK, reducer/compiler/resource ownership, privacy/history and safe editing; its
stale receipt-status finding is corrected at the top of this file.

All concrete findings from that pass are addressed in the documents. Review scope
is this documentation correction, not renewed certification of every algorithm or
a runtime performance claim. No extra benchmark, schema-generation or implementation
review cycle was introduced.

The prior experimental packer/runtime changes are outside this documentation-only
request and remain unaccepted. These edits neither run nor endorse those defaults.

## Historical reviews (superseded where corrected above)

Reviewed documents:

* [Master plan](../../NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md)
* [Depth, materials and lighting](../../NDCLIENT_DEPTH_MATERIAL_LIGHTING_2026-10-08.md)
* [Interaction parity](../../NDCLIENT_INTERACTION_PARITY_2026-10-08.md)
* [Assets and rig authoring](../../NDCLIENT_ASSETS_AND_RIG_AUTHORING_2026-10-08.md)
* [Effect representation prerequisite](../../NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md)
* [NeuroClient/Pixi component decisions](../../NDCLIENT_PIXI_NEUROCLIENT_COMPONENT_REVIEW_2026-10-08.md)
* [Complete authoring field ledger](../../NEUROCLIENT_AUTHORING_COVERAGE_2026-10-07.md)

Independent local review roles: anti-slop/ownership (`server_implementation_antislop`)
and anti-OOP/ECS/DAG/privacy (`server_implementation_ecs`). Both inspected source,
then the written documents, then verified their requested amendments. Neither
edited implementation or contacted/read another chat.

## Anti-slop review

Initial result: architecture/coverage sound; one blocker and three amendments.

| Finding | Correction |
|---|---|
| Plan implied an API control could pause native advancement | Removed; client suspends intake before unsafe acceptance/ACK, server spool/quotas remain independent |
| ACKed unplayed history must survive regardless of export setting | Mandatory application retention before consumption/ACK; IndexedDB journal, pinned prerequisites and distinct displayed recovery |
| SDK resume versus animation recovery ambiguous | Existing follower resumes consumed; fresh follower initializes normally; presentation restores displayed checkpoint and deduplicates retained occurrences |
| Root-restricted source save insufficient | Exporter-issued allowlisted document identities, expected revision, recoverable multi-source transaction and interrupted-publication handling |
| Generic 60-FPS prose lost earlier budgets | Restored p95/p99/stall/input/cold/warm/first-use/15-minute-memory targets |
| Icons described as finally approved | Corrected to delivered smooth bank; runtime sizing/visual acceptance still required |

Final verdict: **Approved as a bounded implementation plan; no remaining plan
blockers.** GPU composition, browser integration, visual quality and performance
remain unproven implementation gates.

## Anti-OOP / ECS / import DAG / privacy review

Initial result: design sound; the same capacity-control and mandatory-retention
amendments were required. Final review verified both and their reload/history-expiry
and audience-isolation consequences.

Accepted design boundaries:

* SDK types/transport reused directly; one TS reducer/compiler/sampler, no native
  rules or duplicate wire schema in the client.
* Received/consumed/displayed progress remains separate; all admitted animatable
  occurrences retained, with no future-state overlay on historical playback.
* Categorical observer-effective light stays separate from visibility; smooth
  presentation does not invent light emitters or leak hidden sources.
* Source authoring stays in existing owners; fixed rigs use BodyRig and actual
  clips/sockets/accents/scales rather than creature-specific executors.
* NeuroMapEditor supplies compatible geometry concepts without introducing another
  gameplay world model.
* The original review required exact dynamic-clipping depth statistics as N1
  compositor proof. **Superseded by the later user-directed representation
  amendment below:** Python depth statistics are not the target contract.

Final verdict: **Approved at plan level; no remaining ECS/DAG, schema-ownership or
privacy blocker found.** Depth-compositor performance, lighting appearance and
browser integration are implementation proofs, not completed acceptance.

## Evidence retained

Current loader/type census and selected identities are in this directory. The
asset/rig inventory reads registered JSON, without decoding image banks.
`reference-revisions.json` records engine/NeuroClient/NeuroMapEditor revisions and
inspected reference hashes. NeuroMapEditor had existing working changes; its HEAD
alone is not treated as the inspected source.

The official PixiJS snapshot contains 47 Markdown guides and 17 selected pinned
v8.22.0 API files. Saved reference hashes were checked. Guide/API drift, including
the outdated GC-guide options, is noted in its README. Local link checking found
no missing companion document after this receipt was added.

No production code, SDK schema or artwork was modified. No tests/benchmarks were
run during this planning task; metadata/link/hash checks are document verification.

## Later amendment — Pixi-first rendering and concrete NeuroClient reuse

The user clarified that existing NeuroClient functionality must be studied and
recovered, and that huge runtime XYZ banks/CPU painter operations are not an
acceptable requirement for the new renderer. The revised master and companions
now include:

* [Compact representation prerequisite](../../NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md):
  N−1 precedes migration and covers colour delivery, volume/structure intersections,
  blood/bone/vapor and receiver-local ground effects. It compares bounded candidate
  representations against intended appearance, disclosure and combined-scene costs.
* [NeuroClient/Pixi component review](../../NDCLIENT_PIXI_NEUROCLIENT_COMPONENT_REVIEW_2026-10-08.md):
  actual existing source and relevant official documentation for each renderer/UI/
  Studio component. Reuse functions and resource guarantees, without importing old
  store/protocol/FSM ownership. No blanket rebuild of working non-VFX capabilities.
* Retained/adapted Pixi HUD and equipment rendering, DOM log/forms/Studio controls;
  no forced DOM rewrite and no duplicate implementation of the same widget.

Both independent local reviewers inspected the amendments and relevant source.
The anti-slop reviewer required a batching correction: shared custom shader
programs do not automatically batch separate Mesh objects. This is now explicit
in the depth document and component matrix; ordinary Sprite/Texture views remain
the normal path, and custom geometry must be combined/instanced and measured.
The ECS reviewer approved the ownership/privacy boundaries and requested correction
of the old HUD's inaccurate DOM description and the superseded exact-statistics
requirement. Both descriptions are corrected above and in interaction parity.

These are plan-level reviews. They do not certify new browser behavior, measured
performance or visual acceptance. The representation experiment and implementation
proofs remain delivery work, not reasons to restart schemas or SDK generation.

Final amendment verdicts: **anti-slop approved; anti-OOP/ECS/DAG/privacy approved.**
The anti-slop reviewer rechecked the completed component matrix, explicit custom
mesh batching limits, retained Pixi HUD/DOM split and updated receipt, finding no
remaining plan blocker. Final document checks found no missing local links or
named NeuroClient source files; reference hashes were checked, including the added
PrepareBase, Ticker and package exports. These checks are documentation evidence.

## Consolidated whole-phase review — complete plan assembled

At the user's request, both reviewers revisited the entire bundle, not merely the
last shader/reuse amendment. They included the inherited renderer/complaint and
authoring coverage. The master now owns a reading/precedence map, current R01–R23
capability table, individual P01–P31 obligations, and concrete N−1–N5 tasks with
dependencies and acceptance. The specialist chapters are required parts of that
one plan; older platform/algorithm prescriptions no longer compete with it.

| Whole-bundle finding | Disposition in assembled plan |
|---|---|
| Inherited text suggested a static full native content manifest | Master §4 and field ledger distinguish existing public metadata from stream-admitted observed `content_additions`; art never grants native knowledge |
| Real browser connection/origin setup was implicit | N0 explicitly covers existing `allowed_origins`, Windows browser to selected host, seat attachment, streaming fetch, preview/command and reconnect |
| N1 historical proofs depended on a reducer first introduced in N2 | One minimal shared reducer/checkpoint path starts in N0; N1 proves snapshots, N2 completes temporal playback and reuses the same scenes; no temporary reducer |
| New rig draft creation conflicted with existing-document-only save language | Tool allocates/allowlists canonical document identity from an existing registered bank; browser never supplies a path; same save transaction |
| Historical UI rule should name all controls | Action bar, inventory, conditions and tooltips use displayed state; latest authorization can disable but cannot expose future resources |
| Old “GPU XYZ” and exact-depth-statistics wording remained in inherited coverage | Current master §§13–14 own active coverage; historic algorithm mandates are explicitly superseded |

Anti-slop final verdict: **approved as the complete, executable next-phase plan;
no remaining plan blockers found.** This approval includes the final assembled
master and all four concrete repairs identified by that reviewer.

Anti-OOP/ECS/DAG/privacy final verdict: **approved as an integrated implementation
plan; no remaining ECS/DAG, schema-ownership, history or privacy blocker found.**
The reviewer read the master through §§13–16, all companions and inherited ledgers,
and confirmed that descriptor admission, historical algorithm precedence and
future-state UI leakage findings are resolved.

The selected compact geometry/colour representation is deliberately an N−1 output,
before migration. The plan fixes its candidates, scope, proof scenes and decision
record now; it does not fabricate experimental results or claim final runtime
fields have already been measured. Final local document checks account for all 23
R rows and 31 P rows exactly once in the master and no missing local chapter links.
No runtime tests, packing or client implementation were performed in this pass.


## October 8 — occlusion mathematics, wall/light reuse and compact data

The required [mathematical/Pixi chapter](../../NDCLIENT_OCCLUSION_MATH_AND_PIXI_2026-10-08.md)
was independently reviewed by the existing anti-slop and anti-OOP/ECS/DAG/history/
privacy reviewers. Master, representation prerequisite and depth/light chapter
now link it. Godot is an offline producer; export feasibility follows the math.

Source evidence includes seven additional pinned Pixi depth/state/texture files,
four installed SE Fireball frame decodes, and isolated read-only clones of the two
lighting libraries requested by the human. No packages installed, external project
scripts run, production code/assets modified, GPU prototype or gameplay test run.
The numerical read-only experiment is recorded in `volume-projection-samples.json`;
repository pins/file hashes are in `lighting-references.json`.

Findings addressed before final approval:

* Surface-depth reduction explicitly distinguishes native samples from borrowed
  fringe/glow coordinates, and flattened colour from a true depth distribution.
* The transparency reference specifies lexicographic equal-depth contributions,
  a conservative finite pass bound, disjoint exclusion intervals and transmittance
  limits; no silent layer cap or synchronous GPU query is accepted.
* Depth-writing world quads/meshes are explicitly different from depth-free ordinary
  Sprite batching. Required Pixi attachment/state/feedback rules are source-checked.
* Backend affected/disclosed cells are not alpha stencils for admitted art. The
  actual partial/upper-volume facts are retained without inferring native propagation
  from their incomplete footprint. Decorative overhang and physical cuts are separate.
* Globe and Antimagic remain separate native applicability/lifecycle cases. Existing
  transient suppression projection drops optional metadata; historical provider
  joins remain appropriate where available. Antimagic source/target/path cancellation
  lacks typed provider attribution for a specific response. This is now an explicit
  owner-local prerequisite, with no text parsing, hidden-source disclosure, invented
  impact artwork or new suppression system.
* The two lighting libraries contribute ideas, not new dependencies/singleton owners.
  Their flat-shadow/fixed-height limitations and actual Pixi peer versions are recorded.

Final verdicts: **anti-slop approved; ECS/DAG/history/privacy approved.** Neither
reviewer found a remaining plan blocker after the bounded corrections. Both explicitly
exclude browser performance and final visual quality from this approval. N−1's geometry/
compositor measurements and the identified attribution repair remain implementation
work. The study does not declare a mathematically optimal representation proven by
measurement or authorize wholesale library/exporter integration.

## October 8 — concrete Fireball export and interactive Pixi handoff

The latest human request selects a one-view, 24 FPS Fireball proof with two RGBA8
planes per depth layer, scene depth and local depth peeling. Its
[handoff](../../FIREBALL_SINGLE_VIEW_PIXI_HANDOFF_2026-10-08.md) now fixes the format,
two-band approximation, timing, interactive scene and finite memory measurements.
Existing Globe appearance/geometry are reused; no Globe export is requested.
Both independent reviewers approved the revised contract. The
[detailed receipt](FIREBALL_HANDOFF_REVIEWS.md) records three corrected findings,
source checks and the explicit limit: export, Pixi preview and measured runtime
acceptance remain to be delivered. This is the sole requested 24 FPS exception.

## October 8 — return to the complete master plan

The master now distinguishes the delivered server/SDK foundation from all remaining
client work, and explicitly retains all R01–R23 and P01–P31 obligations. NDClient
does not yet exist; the Fireball handoff is one representation proof, not a delivered
renderer or a substitute for the full migration.

The existing local anti-slop and anti-OOP/ECS reviewers independently checked this
reconciliation and returned **approved, no remaining blocker**. Their initial
findings were addressed in the master and its required companion chapters:

* Selected Fireball bands/peeling, existing Globe and remaining-family geometry are
  distinguished; no universal eight-byte export or repeated compositor selection.
* Depth-writing world geometry explicitly batches with compatible custom state;
  ordinary Sprite batching is limited to depth-free UI/resolved overlays.
* Combined Fireball radiance/transmittance cannot pretend to expose separate smoke
  or emission. Bloom approximation and bounded cosmetic receiver lighting are
  explicit; native effective light and displayed disclosure remain authoritative.
* Paired-plane readiness, shared source leases, one/four-cast proof budgets and
  full blood/deposit work are explicit. Fireball cannot close all N−1 work.
* The contradictory missing-owner-cell holes instruction is removed. Actual
  disclosed three-dimensional exclusions remain; missing floor entries cannot
  stencil admitted continuous artwork.
* N−1 selects/measures fields at existing owners; N0 implements/migrates once.
  Source layout, geometry, appearance encoding and consumer role remain distinct.
* Fireball's requested 24 FPS export and Globe's existing 32 FPS are consistently
  scoped. Independent proof work does not silently authorize production migration.

Review scope: amended master §§0,3,5–7,11,15–16 and corresponding representation,
depth/material/light, mathematics, assets and component-review text. Final document
checks found all 23 R rows and 31 P rows exactly once and no missing local chapter
links. No runtime code, source artwork, packing, browser tests or benchmarks changed
or ran during this reconciliation. Fidelity, combined-scene performance and resource
budgets remain implementation acceptance work. No external chat was contacted.

## October 8 — authored channel timeline clarification

Master §8.2 now explicitly retains the requested Adobe/Godot-style channel timeline.
Source inspection covered NeuroClient's timeline model/view/layout files and current
typed media/material tracks. Layout controls can be recovered; old fixed-owner and
per-Studio timeline builders do not become another scheduler.

Both existing local reviewers independently **approved** the bounded amendment,
with no blocker: timeline rows derive from production compilation and canonical
source references; finite typed adapters edit the same draft fields as inspectors;
native outcomes/derived times remain read-only; clocks, undo/save and presentation
ownership stay shared. No separately serialized animation model or Studio executor
is introduced. Approval is of the design; no editor implementation or runtime
acceptance was performed. The field ledger/component matrix link this requirement.

## October 8 — actual light/depth proof, repository setup and animated assets

Both local independent reviewers **approved the amended bundle with no remaining
blocker**: anti-slop and anti-OOP/ECS/DAG/data ownership/privacy. No other chat or
artwork author was contacted. This is review of the plan/evidence reconciliation,
not approval of a completed NDClient or the remaining renderer cases.

Reviewed scope: master status/§§0–1,6–7,12,15; lighting §4.1; asset chapter §§2.1–2.2;
math/preflight/component-review reconciliation; and the new
[actual Fireball proof receipt](FIREBALL_PROOF.md). Recovery/asset entry points now
link the same current status and setup, rather than saying the export is undelivered.

* Shared depth/normal/light functions are grounded in the delivered Pixi demo.
  Emitted appearance, whole-effect receiving response and neighbour-light curves
  stay independent passive authoring. No recovered smoke mask, extra texture/pass,
  per-spell renderer or replacement native light system is introduced.
* Camera occlusion, incoming-light shadows and natural wall contact are separated.
  The rejected angular cutout is recorded; contact, four-cast buffering and combined
  N−1 scenes remain open. Improved Fireball artwork is a release replacement and
  does not block other work.
* N0 explicitly preserves references/proof, creates the fresh WSL Git repository,
  installs ignore rules before physical private-media copies, and reuses existing
  server/SDK/art owners. Canonical authoring and derived release manifests are distinct.
* Animated asset review checked official Pixi documentation and installed 8.22.0
  source. The plan retains good sheets, packs remaining frames into bounded pages,
  preserves paired registration, avoids eager whole-bank multipacks and independent
  world-animation tickers, and uses shared page leases. The initial 2048 page cap
  is provisional; packing is not claimed to have already fixed memory/buffering.

Two findings were corrected before final approval:

1. The benchmark stores cumulative frame samples. Its proof table now uses the
   saved per-scenario suffixes (repeat p95 16.8 ms; four-cast p99 33.4 ms) and names
   session-wide high-water marks correctly. No benchmark was rerun to fix reporting.
2. A stale math-chapter statement that export/performance were wholly unproven now
   distinguishes the delivered standalone proof from remaining production work.

Both reviewers checked the follow-up packing amendment and final corrections.
Document links/anchors/whitespace and the master coverage denominator (23 R rows,
31 P rows, each unique) were checked. This update changes documentation only:
no repository created, media repacked/copied, dependency installed, runtime changed
or runtime test executed. Actual earlier proof measurements remain cited separately.

## October 8 — accepted v4 and native reach to continuous regions

Both independent local reviewers returned **APPROVE, no remaining blocker** for
the bounded amendment: anti-slop and anti-OOP/ECS/DAG/privacy. They reviewed master
§0.2/N−1, occlusion §1.1, the versioned proof receipt and companion reconciliation.
No other chat or artwork author was contacted.

* Native code retains propagation, damage, protection and stage ownership. The
  renderer receives passive continuous regions; the two-room interval is a bounded
  example, not a generic geometry schema or second propagation solver.
* Existing capture/projection must provide audience-safe obstruction evidence.
  Omitted positive cells remain unknown, not blocked. Art dimensions remain outside
  backend types; the existing compiler resolves displayed authored geometry.
* Destruction clearance, one explosion clock and backwards seeking stay explicit.
  Low-wall rendering cannot create new vertical gameplay rules. Exact owner-local
  fields and general region compilation remain N−1 work.
* Evidence distinguishes v1 concurrent buffering, v3 reach-example timings and
  the v4 46-frame hookup. The anti-slop reviewer verified all 11 current fingerprints
  and the saved 185-request/frame/expiry receipt. Neither reviewer treats these
  bounded observations as production performance certification.

The final consistency pass replaced stale current-version 48-frame/two-second
statements with v4’s 46 frames, 24 FPS and 1.916667-second manifest duration;
current packing evidence now names 184 paired-plane payloads. Historical evidence
is retained and labelled. Local links in the plan chapters/receipts/current
recovery entry, new anchors, whitespace and all 23 R / 31 P coverage rows were
checked. Unrelated historical recovery links were left unchanged. This was documentation work only; no runtime
changes, asset copies, browser runs or new benchmarks were performed in this turn.

## October 8 — production stopped; complete-scope reconciliation

The user rejected the newly created NDClient terrain/walking slice as a substitute
for full migration and explicitly stopped production. New client/test-server
processes were stopped; the accepted Fireball demo was left intact. Subsequent work
was local source inspection and documentation only. No runtime fixes, tests,
dependency installs, asset copies or packing ran during this reconciliation.

Independent local reviewers `plan_reset_antislop` and `plan_reset_ecs` inspected
the master/companions and actual scaffold. They did not read/message other chats,
edit code or run implementations. Both found the full scope already explicit in
the plan and identified concrete departures:

| Finding | In-place correction |
|---|---|
| Six-field `SceneRelease` and Idle/Run installer replaced the full source boundary | Master §0.3 labels it unaccepted; §5.4 names every existing source section, dependency root, consumer and editor; complete installation is separate from demand loading |
| Sprite scene omitted modular layers and world/depth consumers | No R-family or N0 completion credited; useful functions may move into final modules, with no second renderer retained |
| Step-only compiler collapses attacks/reactions/conditions into final state | N2 explicitly accounts for every fact branch and shared ancestry/contact/retained-lifetime semantics; no silent zero-duration unsupported operation |
| Release ID hashed JSON but not referenced bytes | §5.4 includes resource hashes in immutable release identity, deduplication and atomic complete installation |
| Retained journal lacks release pin/offline recovery; idle uses wall time; old scene can remain on scope change | N2 explicitly requires pinned presentation prerequisites, offline retained playback, one presentation clock and actual scene/UI/pending-work clearing |
| Native reach amendment anticipated SDK generation while N0 forbade it | One conditional owner-derived update if finalized reach/cancellation facts change; no new protocol, recurring generation or server redesign |
| Repository/status/runbook text remained pre-implementation | Master, asset chapter, RECOVERY and client `docs/FOUNDATION.md` now state production stopped and retain the existing setup |
| Complete scope was confused with finalized representation contracts | Master §0.4 distinguishes open reach, low-wall, cancellation, remaining media and resource/history contracts from already-required all-content implementation |

The source census found 11,080 installed files / 4,669,872,861 bytes. It includes
historical/unselected files and excludes separate newer handoffs. This is metadata
evidence of the source library, not a complete selected-release size or a claim of
browser readiness. The original source/selected-identity inventories remain the
coverage denominator; no new runtime catalog was created.

Both reviewers approved the **planning reconciliation**, conditional on replacing
two stale instructions to create the repository again. Those instructions in
master §1 and N0 item 1 were corrected to retain/verify existing setup; asset
runbook step 3 now does the same. This was a mechanical document correction, not
another runtime validation round.

**Verdict scope:** the amended status/scope/ownership account is accepted by both
reviewers. The plan is not yet certified end-to-end implementation-ready; §0.4's
open contracts remain open. Nothing in this review resumes production, approves
the scaffold or claims complete rendering/Studio/UI, release coverage, performance
or browser acceptance. Further design work belongs in the existing owning chapters.

## October 8 — complete implementation readiness

**Earlier verdict: APPROVE — implementation-ready plan.** Both independent local
reviewers approved the complete revised specification, not only the reconciliation
of scope. Production remains stopped on the user's instruction. The unaccepted
scaffold is preserved and receives no completion credit.

Reviewers: `implementation_ready_antislop` (duplication, ownership, unnecessary
systems and delivery completeness) and `plan_reset_ecs` (passive data, ECS/static
import DAG, privacy, history and lifecycle). They inspected the master, required
technical chapters, source inventories and relevant existing code owners. Neither
implemented these contracts. The final footprint-mutation clarification was checked
by both reviewers before this verdict was recorded. No other chat was read or
contacted.

### Previously open contracts now specified

| Contract | Concrete decision and owner |
|---|---|
| Native reach versus unknown space | Occlusion §1.1 defines cold reach values, captures the existing native query's results/witnesses, projects only admitted evidence and labels continuous regions against registered finite geometry. Connected spread and line of effect have distinct partition rules; no client propagation solver or tile-alpha stencil. |
| Low walls and decorative overhang | Native two-dimensional reach remains authoritative and is extruded vertically. Actual wall geometry handles depth/contact/light; unclassified decorative fringes remain unknown. This is an explicit approximation, not simulated flow over walls. |
| Protection and cancellation | Master §5.5 uses the existing suppression value and one cancellation owner, historical projection and provider admission. Only the active stage's suppression applies during staged presentation; later terminal state cannot retroactively alter it. |
| Remaining media, blood and ground | Representation §§2–4 and the depth chapter select finite geometry/material fields, per-family conversions, analytic particle flight and bounded receiver-local deposits. Existing source owners remain canonical. |
| History and resource scheduling | Master §§4.2/7.1 specify the durable journal, release/schema pins, received/consumed/displayed progress, recovery, quota behavior, page/companion leases, scheduling and context restoration. |

### Findings corrected during the full readiness review

| Review finding | Final correction |
|---|---|
| A raw-resource hash alone can alias differently shaped GPU textures | Resource identity also contains dimensions, layout, GPU format, encoding, sampling and alpha interpretation; byte sharing remains separate. |
| Legacy media types require eight rows and a constant projectile kind | Master §5.2 specifies the owner-local migration to actual row counts, removes the redundant constant, defines sheet/storage presence and retains one schema/export path. |
| Connected Fireball evidence does not cover cones, lines and beams | Occlusion §1.1 captures existing FOV/supercover results and admitted occluder witnesses for line-of-effect consumers. Its radial partition lines are not applied to connected spread. |
| Persistent areas can be observed without a witnessed cast | Existing AreaCondition/PerceivedSpatialEffect owners carry the same cold evidence. One passive projector handles event and observation disclosure; cold discovery, party joins and historical revisions are explicit. |
| Relocation, trimming and exclusive displacement can retain stale evidence | The existing footprint mutation boundary publishes fresh evidence after a query or invalidates it for non-query mutations. Rollback restores it; no-ops preserve it. Native removals stay lifetime/footprint facts, not new wall blockers. |
| Root terminal suppressions could cut earlier stages | Stage presentation consumes stage-local suppression only, followed by the normal retained-state commit. |
| Companion documents still implied another representation-selection/demo phase | N−1 now denotes the completed design closure. N0 implements the complete release/contracts; combined runtime acceptance belongs to N1/N3/N5. |

The full denominator remains all 53 AnimationData fields, all 44 rigs and authored
clips, modular equipment, animated/destructible environments, props/traps,
spells/actions/conditions, blood/deposits, UI assets, real-event Studio and playable
Fighter/Sorcerer interaction. R01–R23 and P01–P31 remain required. Complete private
release installation and bounded runtime residency are separate obligations;
the first 197 copied assets do not establish either full coverage or completion.

**Anti-slop final verdict:** APPROVE as implementation-ready; no remaining design
blocker. The final mutation clause adds no duplicate cache, observer query or
renderer rule.

**Anti-OOP/ECS/DAG/privacy final verdict:** APPROVE as implementation-ready; no
remaining blocking design omission found. Passive records, shared functions,
existing owner-derived schemas, independent temporal progress and conservative
private disclosure are coherent with the inspected source owners.

### What this verdict establishes

The plan now specifies what to implement, the fields/functions/modules that own
it, their migration and lifecycle, and the required acceptance cases. No open
design choice identified by these reviews is deferred to bulk porting. Runtime
failures can still require a bounded correction in the existing owner; approval
is not a guarantee that implementation cannot reveal a defect.

N1/N3/N5 still must establish combined workload performance, concurrent media
residency, visual quality, browser behavior, retained playback and all named
regressions. The accepted Fireball proof is bounded evidence; its earlier buffering
limits are not declared fixed. Selected geometric approximations and conservative
unknown-space handling remain explicit in the owning chapters.

This readiness pass changed documentation only. No runtime code, dependency,
asset copy/packing, test execution, browser run or benchmark was performed. No
commit or push was made. That revision prescribed a serial export/release-first
sequence. The later cleanup above supersedes it with actual capability dependencies;
the user's production stop remains in force.
