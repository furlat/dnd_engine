# Presentation and tooling audit — September 12, 2026

Status: **read-only audit after the user's implementation hard stop**. No
production/test changes, executions, benchmarks, imports of game modules, asset
generation or gallery recording were performed for this audit. The only new
artifact is this document. The earlier uncommitted asset-loader changes remain
on disk and are reviewed below; their presence is not approval to continue them.

Checkout: `codex/recovery-design`, HEAD `14b27f7`, with pending changes. Locations
below refer to that working copy. This is one part of the root's whole-codebase
audit, not a claim that native rules, server, SDK or all tests have been audited
here. Read the final combined audit before selecting further implementation.

## Scope and evidence

Inventoried **57 executable source files, 20,791 lines**: 37 under `game`, 17
under `devtools` (including the 396-line gallery JavaScript), two executable
audit scripts under `agent_docs`, and `setup.py`. The Python/TypeScript subset
is 56 files and 20,395 lines. Every inventoried file received an import/entry-point and machinery
scan; detailed caller/callee reads concentrated on the paths below. Large
declarative schema, mapping and numerical sections were classified by owner;
this is not a line-by-line proof of every formula or content row. The complete
file list and entry/cadence classification are at the end.

The imported NeuroClient source subtree contains **14 JSON files and zero
Python/TypeScript files**. The TypeScript materializer and source oracle execute
only through explicit devtools against the external reference checkout. The
JSON source copies, materialized output, rig mappings and PNGs are data, not
hundreds of thousands of new executable lines.

Method: filesystem inventory, static AST/import inspection, targeted source
reads, caller searches, and Git source/history reads. No grep count is used as
evidence that work is expensive. Unless explicitly attributed to the earlier
profile, findings below are **source-only**: repeated operations are established,
their wall-time contribution is not.

The existing measured reference is
`agent_docs/STARTUP_PROFILE_2026-09-12.md:49`: at `57fe2d6`, the older map
diagnostic took 8.973s in one stage run: imports 3.897s, native producer including
capture 2.457s, catalog validation 0.948s, asset decode 0.439s, twelve frames
0.348s, interval reduction 0.0006s. That is **not** a playable encounter or gallery
profile. Its water subspan was 0.077s; the producer's three interval captures
totaled 0.049s. These nested values must not be added to their enclosing spans.
No new timings or predicted seconds saved are claimed here.

`git ls-tree 16a6bfe` confirms the July base already contained `game/app.py`,
`assets.py`, `presentation.py`, `projection.py`, `water.py`, and the five older
content/contract devtools. The world validation/evidence/water machinery is not
all a September regression. The action playback, recording, public projection
and paired-view paths were added during recovery. The relevant later checkpoints
include `12ae1eb` recorded history, `767e0e7` paired public projection and
`55c7994` concealment. They were already present before this performance unit.

## Actual execution paths

**Native encounter:** `game/__main__.py:34` installs native content; the normal
branch calls `game/encounter_play.py:339`. `game/session.py:57` composes entities
and the battlefield. Discovery uses the engine's existing action owner; the
application does not validate D&D rules independently. Each returned operation
supplies terminal roots through `game/session.py:126`.

**Live intake:** `game/encounter_play.py:140` calls `capture_lineage`, then
`project_lineage`, then the public `reduce_lineage` once per contributed root.
It appends that public lineage to both pending playback and retained history.
This path does **not** serialize/decode a complete PlayerSequence for every
action. The smaller log/cost normalization inside native capture is separate.

**Historical playback:** when a pending root starts, the encounter reduces its
successor, stages actor media, binds motion or choreography and loads media
(`game/encounter_play.py:233`). Frames sample retained data through
`game/playback_frame.py:43`, then call the common painter and labels. The rules
clock may advance while this historical clock is paused. The states and queues
serve different positions in history and must not be collapsed to save copies.

**Explicit gallery:** `devtools/animation_review/__main__.py:54` captures native
input once per experiment and persists both observers. Default replay reads saved
public packets; historical native-v2 inputs can be projected without native
execution. `record_case` reduces latest, preflights framing/media, then samples
four cameras per frame. Video encoding, per-frame hashes, trace files and review
export are offline work, never the encounter's per-action requirement.

## Findings and their boundaries

### 1. Each new native lineage rescans and refolds old history

`game/presentation.py:767` builds a tuple of the entire EventQueue, a latest
version dictionary for all its lineages, walks the selected child tree, then
filters the entire history again. `_capture_actor_admissions` at line705 starts
actor/contact accumulation from empty and refolds native events from birth to
this root's last selected version. `capture_interval` at line259 also collects
the history for admissions.

Caller cadence is each operation root in live `receive`, and each root for each
observer in `game/replay.py:44`. The latter also recaptures initialization and
can recapture a primary view already represented by a producer's convenience
fields. **The whole-history traversal is a clear repeated-work candidate.**
Full terminal ancestry, source version ordering and acquisition-time state are
required; recreating indexes and birth-to-current folds for every root is not
the contract. Any later change must preserve hidden changes before reacquisition,
late observer initialization and actual roots unseen by the primary observer.
This audit does not propose dropping old events or merging observer histories.

### 2. World differences are recomputed for unrelated event nodes

`game/player_projection.py:308` calls `_world_update` after every noncanceled
node, including action/roll/cost nodes after which `apply_world_fact` did nothing.
`_world_update` at line281 sorts visible cells, compares terrain, rebuilds observed
floor-object records, compares remembered objects and scans connectors.

The projection's private world and last-observed memory are necessary: an unseen
door must not leak its new state. Repeatedly reconstructing the same world diff
for nodes with neither world nor sensory change is a **source-demonstrated
redundancy**. A future narrower cadence must account for sensory children that
precede their spatial parent's completion, already handled at line335. Merely
moving updates to top-level completion would lose that timing.

### 3. One active movement reaction is sampled three times per view/frame

`game/motion.py:340` samples each reached reaction; line349 samples the active
reaction again for its body. `game/playback_frame.py:79` samples the returned
active group a third time. These calls use the same active local timestamp.
`sample_choreography` at `game/choreography.py:416` calls `observe_actors`, whose
`copy_target` copies all public state containers. Thus this is more than repeated
arithmetic. Four-corner review repeats the path for each camera.

Finished reactions may still supply prior vitals during movement, which has an
actual purpose. The duplicate active samples do not establish another history
position. Reusing their result is a concrete candidate, with no new controller,
clock or mutable sampling cache implied by this observation.

### 4. Binding rebuilds prefix and subtree states repeatedly

`game/choreography.py:102` finds an event's first version, filters preceding
terminal nodes and reduces that prefix. Many visits call it for action, damage,
condition/life and equipment entry. `lineage_branch` at
`game/player_projection.py:557` reconstructs a lineage index and filters records
on each invocation. Attack/cast/equipment/forced-motion binders also reduce their
branches; the encounter already computed the head's final successor, and
`bind_choreography` computes it again at line410. Root attack staging also asks
for a successor at line128.

The different prefix states have real semantic meaning; using final state for
every child would break reaction and condition timing. The avoidable part is
repeated derivation of the same prefix/subtree/final state during one compile.
This is a **candidate requiring measurement**, not authorization for a general
snapshot engine. Existing immutable derived states and an already-computed
successor are sufficient concepts to investigate first.

### 5. Mutable-container ownership is real; broad copy scope is a separate issue

Public `copy_target` (`game/player_projection.py:411`) makes shallow copies of
tile/object/actor dictionaries and mutable sensory sets/dictionaries; frozen
actor/fact values remain shared. This protects previous history and seekable
samples. Native `copy_target` (`game/presentation.py:494`) uses `_copy_snapshot`
at line337, which additionally deep-copies contacts and sense modes. Sampling
choreography copies terrain and sensory containers even when it only changes
actors. Staging copies even when no new actor is admitted.

These are potential granularity/cadence improvements, **not proof that all copies
are defensive waste**. PlayerState is deliberately mutable, so simply deleting
copies would mutate before/history. `VisualPosition` (`game/visual_position.py:9`)
also is necessary presentation state: legal tile origin and a body's interrupted
subtile pose intentionally differ after lethal/paralyzing movement.

### 6. Native detachment contains extra normalization, but also a real boundary

`game/presentation.py:599` projects a log, JSON-dumps and validates that log,
shallow-copies a selected native event without executable value graphs,
normalizes each Action cost through JSON at line658, then deep-copies the result.
Unknown/condition families additionally build a passive Event header at line564.
These operations happen during live capture, not just file export.

Detaching mutable native event graphs before subsequent native actions/reset is
required. Original grants and terminal values must survive, and ordinary native
constructors must not register replay objects or acquire ambient turn/provider
metadata. The repeated conversion deserves review at its actual field ownership;
removing it because a tuple/list appears equivalent would recreate the earlier
recorded-input defects. The log comment records why JSON value normalization was
introduced. A cheaper representation must demonstrate the same value semantics.

`game/event_record.py:78` separately reconstructs the set of required model fields
for every decoded native event, converts its payload dictionary back to JSON,
then uses the native passive schema. This is **archive decode**, not the live
encounter path. Its fixed model map prevents arbitrary class loading; it is not
a runtime reflection-based rules dispatcher. Repeated required-field discovery
is an offline decode candidate; passive construction remains necessary.

### 7. Actor appearance lookup repeats invariant catalog work each frame

`game/playback_frame.py:87` and line105 call `scene_actors` twice on the same
displayed state. `game/scene.py:31` resolves every drawable actor's contact and
equipment layers. `game/animation_data.py:54` scans the entire authored item
variant category catalog for each equipped item to find its factory/slot match,
although the mechanical/presentation catalog is invariant during play. Only its
initial lookup by base category is indexed. Fixed-rig unique-category checks
also repeat on every resolution. Condition composition is sorted and rebuilt
again per actor/frame at `game/playback_frame.py:119`.

Equipment and conditions can change at authored event anchors, so persistent
results cannot ignore loadout/membership. Repeated catalog matching and resolving
the identical displayed actor twice are **concrete candidates**. No measured
frame cost is yet attached to them.

### 8. Media preload is repeatedly performed despite already loaded body rows

Startup `load_scene_media` (`game/scene.py:56`) loads every compatible clip and
all eight facing rows for each current appearance. Head start loads complete
scene media again on observations/equipment changes
(`game/encounter_play.py:238`, line259), while
`game/choreography_draw.py:26` independently loads every attack/cast's body media.
`game/animation_draw.py:97` opens and decodes requested PNGs each call and copies
their rows into a new mapping. There is no caller-shared body-row reuse in that
function. Per-call deduplication does not prevent cross-head reloads.

Owning cropped row pixels permits releasing large full atlases and is not itself
a defect. Re-decoding rows already in `body_media` is avoidable work. Observation
may introduce genuinely new gear, so an exact missing-row check is needed rather
than disabling observation preloading. This was outside my approved loader patch
and remains unmodified.

### 9. Ordinary play computes and retains diagnostic evidence unconditionally

`game/app.py:309` creates expected/actual calculation sets. The painter emits
evidence tuples alongside draw commands, constructs expected/actual draw lists
and a full `FrameEvidence` (`game/app.py:996`) before checking `show_debug` at
line1011. The current encounter and recorder discard `draw_frame`'s return;
the older map/cast diagnostic tests consume it. `game/encounter_play.py:313`
also appends a GameFrame record every frame, including normal interactive play,
and returns the accumulated tuple only on exit. This grows for the whole session.

Draw identity/depth information used for label placement, ordering and review is
not all optional. But duplicate expected/actual proof containers and unbounded
per-frame test evidence are **diagnostic work in the ordinary game path**.
In particular, expected_draws and actual_draws follow the same command list;
their equality is not independent pixel correctness evidence. Moving diagnostic
ownership would require reading the affected behavior tests, not replacing them
with another tautological counter or adding a telemetry framework.

### 10. Some validation is still on hot drawing/sampling paths

`body_clip` (`game/animation.py:216`) checks body resource availability each call;
idle, hit, move, forced-motion and body-action samplers call it repeatedly.
Scalar finite-time checks repeat in those samplers. `Camera.__post_init__`
(`game/projection.py:32`) checks already-valid camera fields on every pan-created
camera, including zero-delta panning; projection helpers also recheck quadrants.

Water shading (`game/water.py:47`, line54, line107) repeatedly validates and
converts the same bundled scalar/vector material fields per owner chunk/frame.
`render_water_batch` at line241 additionally extracts the mask alpha, constructs
the support pixel grid and crop indices each batch even for an unchanged mask.
Dynamic wave/shading calculations are real render work. Invariant material/mask
preparation is a different category. The existing 0.077s water subspan over twelve
diagnostic frames is not enough to claim this dominates normal gameplay.

These checks should be evaluated by cadence and owner. The costs of a few scalar
branches must not be equated with full filesystem scans. Removing tiny guards
as a purity exercise would repeat the scope problem that prompted this audit.

### 11. Pixel copies and caches have specific purposes

`game/assets.py:75` keeps canonical world surfaces and scaled/tinted/cropped/RGB
derivatives keyed by actual rendering inputs. The finite zoom/treatment tables
bound normal usage. These caches remove repeated work; there is no source-hash
cache added here. `game/animation_draw.py:185` composites modular body layers,
and `_colored` at line54 and `game/condition_draw.py:18` copy pixels before
tint/filter mutation. Sharing those mutable working surfaces would corrupt
canonical assets. Some identity-tint copies and successive filter passes could
be combined, but are **pixel-work candidates**, not pointless serialization.
No pixel optimization or cache redesign is implemented or authorized here.

### 12. Presentation imports still pull native and regression owners together

The painter's module (`game/app.py:13`) imports native Entity/Game, door actions,
torch and battlefield fixture owners because it also contains the old diagnostic
producer. The encounter imports that painter. `game/__main__.py:9` also eagerly
imports the old cast reference runner alongside the normal encounter. Public
projection imports native capture/world types, so a standalone public decoder
still imports native schemas even though it does not execute native rules.

The gallery case catalog (`devtools/animation_review/cases.py:14`) imports all
native scenario helpers even in saved-input replay or `--list`. Top-level
`record`/`trace` imports additionally construct their Pydantic adapters, including
animation timeline types containing large authored records.

These are **dependency-boundary candidates**, with prior import cost evidence
only for the older diagnostic. There is no supported claim that late imports
are the fix; repository policy explicitly excludes them. Keep imports as a DAG
and separate actual owners if subsequent evidence warrants it. Archive replay's
existing no-native-execution proof does not prove no-native-import cost.

### 13. Capability gates must not be confused with validation overhead

`compile_cast` (`game/animation.py:676`) mixes materialized-data checks with
explicit unsupported feature cases: area delivery, tangent rows, palette swaps,
alternate travel assets, death media and some dying/revival combinations.
Other binders reject unsupported actor/media fields. Several errors say
"selected family" or "await source parity proof". The shared compositor captures
such errors as presentation gaps (`game/choreography.py:177` onward).

This is a real completeness/design inventory: imported JSON does not make every
field executable. Some gates could be authoring-time compatibility checks;
others reflect genuinely absent drawing or timing behavior. Deleting them
without implementing that behavior would silently misrender data. This audit
does not turn them into new VFX work or propose bypasses. Simple `isinstance`
dispatch over the closed PlayerFact union is ordinary sum-type dispatch here,
not reflective access to live entities.

### 14. Existing private/native and public reducers are not interchangeable

`ActorState` and `PresentationTarget` are private retained aggregates;
`PlayerActor` and `PlayerState` contain permitted observations and owner-only
inventory. Their overlapping HP/equipment updates are not a second D&D rules
engine: both apply committed after-values, and public facts have a disclosure
boundary the private record lacks. There is still older surface area:
`game/presentation.py:536` exports `seed_actors`, now used by old tests only;
no production caller was found. Private reduce/stage functions also support
native reference tests and the old map diagnostic. That is concrete surviving
compatibility/test scaffolding, not evidence that the public system needs to
accept live side-channel actor state again.

## Offline tooling, hashes and serialization

| Owner and exact location | Actual cadence / role | Audit judgment |
| --- | --- | --- |
| `devtools/animation_review/__main__.py:33` | One source fingerprint per explicit gallery run; `git ls-files` across game/dnd/content/devtools/tests, then reads and hashes every listed file, including binary assets | Broad audit I/O and large manifest copied into each input/trace. Useful dirty-checkout provenance, but not a gameplay requirement or proof of semantic equivalence. It should not become a play-start verification gate. |
| `devtools/animation_review/__main__.py:54`, line207 | Native capture projects to public JSON; wraps parsed JSON in RecordedInput; saves, reparses, later saves/reparses the run input and reserializes its nested sequence for decode | The first render consuming persisted bytes is the requested replay contract. Additional wrapper roundtrips and duplicate source manifests are packaging overhead, not necessary native mechanics. Old native-v2 reprojection is an explicit historical path. |
| `devtools/animation_review/record.py:35`, line87, line155 | Reduces latest, derives framing/media over history, then binds/reduces again for playback; four view samples; hashes each RGB frame; writes complete trace | Offline framing and four-view evidence have user purpose. Repeated state/motion derivation and loading can be reviewed separately. Pixel hashes enable pause/replay comparison; no live engine hash requirement follows. |
| `devtools/animation_review/trace.py:20` | Module-level TypeAdapters for state, lineages, timelines; JSON emission only during recording | Schema construction at gallery import; serialization is the debugging product. No ordinary encounter caller. |
| `devtools/animation_review/gallery.js:1` | Static browser review; reads manifest once, traces/input on explicit export; stores verdicts locally | No rules/reduction execution. Same-origin paths, run/case association and restoring bounded review fields protect an actual user-selected trace. Schema/check machinery is local tooling, not native-turn latency. |
| `devtools/animation_review/serve.py:10` | Local HTTP byte ranges and static serving | Threading belongs only to the video server. Range parsing/stat is needed for browser seeking, not a return of the multithreaded game server. |
| `devtools/import_neuroclient_presentation.py:246` | Explicit pinned source export via original TS materializer; validates selected media, source consistency, output paths; hashes source/output provenance | Correct offline ownership. Rechecking every parent path and rereading source files is conservative authoring machinery. Do not import it into gameplay or automatically require it before every test. |
| `devtools/import_fixed_rig.py:32` | Explicit ZIP import/check; hashes whole purchased archive and each selected member, validates PNG shape and destinations | Exact-source import proof, offline. Whole-archive hash can cost much more than selected media; no reason to repeat at playback. Existing test uses a two-sheet temporary archive. |
| `devtools/import_codexfx_presentation.py:42` | Explicit export conversion, one deep-copied selected recipe, hashes manifest/sheet/source, compares outputs | Recipe copy intentionally protects baseline while constructing another data artifact. No runtime converter or VFX generation in the game. |
| `devtools/trace_neuroclient_animation.ts:14`, line382 | Explicit external Bun/Pixi source oracle; source pin and output checks; controlled source execution, hashes trace owners | Offline historical evidence with stated substitutions. It mocks telemetry/GPU I/O and cannot certify the server event mapper. No runtime TS dependency. |
| `devtools/generate_event_contract.py:32`, line82 | Explicit generator imports all dnd modules, walks BaseModel descendants/annotations, hashes generated event contract | Reflection intentionally discovers schema at generation. No production importer found. Broad imports can make generator tests expensive; not native per-turn work. |
| `devtools/generate_typescript_sdk.py:138`, line214 | Explicit generator extends the event contract traversal, introspects API model roots/bounds, uses one `getattr` for Pydantic root metadata | Old offline OOP/reflection surface, not ECS entity composition. It should not be justified as a gameplay need, but rewriting it is unrelated to the current frame loop. |
| `devtools/generate_srd_5_1_source_coverage.py:98`, line921 | Offline source ledger/PDF extraction, digest pin, reflection for source locators; optional refresh from existing ledger | Import-time source contract read and large content imports belong to this tool's execution. No game caller found. |
| `devtools/import_neuroclient_item_visual_inventory.py:388` | Offline pinned inventory parsing, category adaptation and canonical digests | Authoring identity/provenance; generated dnd consumer belongs in root/native audit. |
| `devtools/import_neuroclient_content_icon_bindings.py:1420` | Offline manifest + content ledger conversion; reconstructs metadata models and definition/icon hashes; emits generated binding table | Broad old tooling machinery. Its output can enter native content bootstrap, but the generator itself is not called by game. Distinguish generated output validation from generation. |
| `agent_docs/research/d80-test-rework-coverage-audit/generate_coverage_map.py:500` | Explicit Git/AST lexical coverage comparison | Documentation tool; its own docstring warns lexical similarity is not runtime equivalence. No game imports. |
| `agent_docs/research/d80-test-rework-coverage-audit/manage_legacy_migration_manifest.py:1315` | Explicit manifest completeness/selector validation with cached ASTs | Fixed historical 1,458-row audit contract, not production gameplay. AST cache avoids rereading each selector's file. |
| `setup.py:3` | setuptools package discovery at installation | Six lines, no source verification or game runtime controller. |

## Critical review of the pending asset patch

The uncommitted patch changes `game/assets.py:42` to direct world-catalog
assembly and moves old checks into
`devtools/validate_presentation_assets.py:125`. The validator calls the **same**
assembly; it does not build a parallel catalog. Runtime world paths use ordinary
joins instead of repeated resolve/stat. `game/animation_data.py:169` no longer
parses each JSON solely to detect duplicate keys, and line179 no longer resolves
and stats every animation resource. Additional-rig header checks moved offline.

These changes address the measured world-file scan and align with trusting
shipped data. They are not yet a complete answer to the user's complaint:

- `game/animation_draw.py:97` and line133 **still** check decoded sheet dimensions
  and selected appearance/media compatibility. My earlier statement that runtime
  validation was "fully gone" was too broad; only the approved loader files had
  changed. The draw loader's per-head repetition remains.
- Runtime authored Pydantic records still enforce bounds/layout/state-only
  invariants (`game/animation_types.py:52`, line430;
  `game/condition_types.py:156`). Types, tuples and frozen maps are useful runtime
  values; exhaustive compatibility validation need not be attached to every
  repeated use. Replacing these with unchecked nested dictionaries is not a
  zero-cost architectural simplification.
- `game/animation_data.py:148` retains heterogeneous source context/action
  dictionaries. Selected subtrees are dumped back to JSON and decoded into
  their typed records at line254 and line344. Removing the complete duplicate-key
  pass did not remove these subtree roundtrips. Direct typed source fields are
  a possible future simplification; no conversion framework is warranted.
- The new offline validator at line274 scans all JSON under source/bundle
  directories for duplicates, rereads bindings to check paths, then lets the
  loader reread them for typed assembly. It also validates root-rig PNGs, broader
  than the old additional-rig header loop. This is offline rather than live cost,
  but it is **extra duplicated parsing and some expanded checks**. Moving checks
  offline must not become permission to grow an elaborate assurance program.
- `_contained_asset_path` and `_validate_local_resources` in the new tool retain
  separate world/animation containment conventions; there is already PNG/path
  checking in importers. The patch relocates checks without unifying authoring
  ownership. That duplication is a maintenance consideration, not a reason to
  move them back into runtime.
- The pending tests move malformed/missing/escaping-asset expectations to that
  explicit tool and add one PNG-size mismatch row. Valid-runtime image assertions
  remain. Their execution was stopped; this document claims no new pass or
  measured improvement.

## Test surfaces inspected, without running them

The root owns the exhaustive test inventory. This audit inspected the relevant
boundaries: `tests/game/test_assets.py:30` verifies real catalog/pixel dimensions;
the invalid-data rows at line235 now target offline validation.
`tests/game/test_animation.py:116` and
`tests/game/test_animation_rig_data.py:80` contain the relocated rejection cases.
The fixed-rig import test at line155 verifies exact copied members and changed
output detection, not a live archive dependency.

`tests/game/test_passive_event_replay.py:25` checks that absent turn/provider
metadata and nested records do not register into native runtime. Those are real
recording boundaries, not merely imagined hostile input. `test_recorded_history`
and the fresh-process gallery tests (`tests/game/test_animation_review.py:164`,
line243) cover saved bytes with production/bootstrap disabled. Their subprocess,
encoding and trace work must not be treated as native action throughput.

The old `tests/game/test_app_smoke.py` gates a complete diagnostic child process,
not the encounter's native turn. Tests consuming expected/actual painter evidence
need separate review for whether they assert a rendered contract or mirror the
implementation. `seed_actors` callers remain in old gameplay/equipment tests;
passing those tests alone would not establish the current event-only public
initialization contract.

## Complete owned source inventory

`Live` means reachable from the current application; `shared` also serves saved
replay. `Reference` means an explicit old diagnostic/oracle, not the normal
encounter route. Every path has a line locator; line counts are inventory facts,
not complexity or priority scores.

| File | Lines | Entry/cadence and audit classification |
| --- | ---: | --- |
| `game/__init__.py:1` | 2 | Package docstring only. |
| `game/__main__.py:1` | 58 | Live CLI composition; eager reference + encounter imports. |
| `game/actor_facts.py:1` | 135 | Private native after-value fold; reconstructs appearance and item deltas. |
| `game/animation.py:1` | 939 | Shared pure compile/sample geometry/timing; repeated resource/scalar guards, explicit capability gaps. |
| `game/animation_data.py:1` | 398 | Shared load and actor-layer resolution; pending loader patch, per-frame catalog scan. |
| `game/animation_draw.py:1` | 589 | Shared media loading and pixel composition; repeated decode, validations, working-pixel copies. |
| `game/animation_preview.py:1` | 217 | Explicit synthetic authoring preview; modifies draft JSON once at entry, no native encounter route. |
| `game/animation_types.py:1` | 777 | Authored immutable schemas; eager Pydantic construction and load-time validators. |
| `game/app.py:1` | 1487 | Shared painter plus old native door/light diagnostic; per-frame evidence and broad imports. |
| `game/assets.py:1` | 237 | Shared world loader/surface caches; pending validation relocation. |
| `game/attack.py:1` | 367 | Shared attack profile binding and sampling; native after-values, branch re-reduction. |
| `game/body_action.py:1` | 131 | Shared body/frame cue binding; finite data capability checks, no new rules owner. |
| `game/choreography.py:1` | 488 | Shared causal binding/sampling; repeated prefix reductions and state copies. |
| `game/choreography_draw.py:1` | 68 | Shared group media/draw dispatch; per-node media loads and body ownership. |
| `game/combat.py:1` | 220 | Shared contacts/cast/equipment binding; native-derived values and subtree reduction. |
| `game/combat_demo.py:1` | 196 | Explicit native cast regression producer, also gallery capture; no default gameplay loop. |
| `game/condition_animation.py:1` | 188 | Shared condition recipe composition and absolute sampling; repeated sort/finite guards. |
| `game/condition_draw.py:1` | 36 | Shared mutable working-pixel color filter; copy protects source surface. |
| `game/condition_types.py:1` | 183 | Authored condition schemas and one load; metadata/invariants remain runtime-loaded. |
| `game/controls.py:1` | 233 | Live selection/drawing of native discovered options; no parallel mechanics. |
| `game/damage.py:1` | 105 | Shared packet ownership and hit/life sampling; exact committed HP, finite-time guards. |
| `game/encounter_play.py:1` | 358 | Live native intake + historical clock; repeated bind/load, unconditional frame retention. |
| `game/event_record.py:1` | 102 | Native archive codec; fixed family map, passive schemas, per-event field scan/JSON. |
| `game/feedback.py:1` | 153 | Shared independently timed decorative tracks; frozen launch contact and finite guards. |
| `game/forced_movement.py:1` | 197 | Shared retained route/contact sampling; branch reduction, explicit unsupported media. |
| `game/motion.py:1` | 387 | Shared visible-route binding/sample; necessary retained states, duplicate reaction samples. |
| `game/play.py:1` | 406 | Explicit cast/equipment reference loop; separate old playback runner and frame evidence. |
| `game/playback_frame.py:1` | 161 | Shared frame composition; duplicate scene resolution and active-group sampling. |
| `game/player_facts.py:1` | 389 | Public immutable facts and mutable aggregate; no live lookup/registration. |
| `game/player_projection.py:1` | 582 | Private-to-public projection/reduction; world diff every node, copied aggregates. |
| `game/presentation.py:1` | 967 | Native retained capture + old/private reducer; whole-history scans, detachment, old test seeding. |
| `game/projection.py:1` | 377 | Shared camera/grid/painter geometry; scalar camera checks, no native rule calls. |
| `game/replay.py:1` | 105 | Private archive and explicit observer capture; same-run histories, repeat capture/folding. |
| `game/scene.py:1` | 104 | Shared visible actors/labels/all-clip preload; per-frame layer resolution. |
| `game/session.py:1` | 171 | Live ECS/native composition and commands; validates current UI ownership, no rendering. |
| `game/visual_position.py:1` | 21 | Shared persistent rendering offset relative to legal origin; required after interruptions. |
| `game/water.py:1` | 335 | Shared dynamic software material; repeated trusted parameter checks/mask preparation. |
| `devtools/animation_review/__init__.py:1` | 1 | Package docstring only. |
| `devtools/animation_review/__main__.py:1` | 238 | Explicit capture/replay CLI, source hashes and wrapper JSON I/O. |
| `devtools/animation_review/cases.py:1` | 259 | Catalog schemas + native producer dispatch; eager tests/game imports in replay process. |
| `devtools/animation_review/record.py:1` | 327 | Explicit four-view video, framing, pixel/hash/trace evidence. |
| `devtools/animation_review/serve.py:1` | 83 | Local static/range HTTP only. |
| `devtools/animation_review/trace.py:1` | 115 | Offline serializers + schema adapter construction. |
| `devtools/generate_event_contract.py:1` | 345 | Offline reflective native event schema generator. |
| `devtools/generate_srd_5_1_source_coverage.py:1` | 1028 | Offline PDF/content coverage ledger, hashes and locators. |
| `devtools/generate_typescript_sdk.py:1` | 511 | Offline reflective API/SDK contract generator. |
| `devtools/import_codexfx_presentation.py:1` | 148 | Offline converter/source checks/recipe copy; no media authoring runtime. |
| `devtools/import_fixed_rig.py:1` | 104 | Offline exact ZIP-member importer/checker. |
| `devtools/import_neuroclient_content_icon_bindings.py:1` | 1574 | Offline declarative icon/content bindings and generated hash table. |
| `devtools/import_neuroclient_item_visual_inventory.py:1` | 593 | Offline declarative item inventory conversion/hash provenance. |
| `devtools/import_neuroclient_presentation.py:1` | 343 | Offline original TS materializer + exact selected data/media export. |
| `devtools/trace_neuroclient_animation.ts:1` | 417 | Explicit external source timing oracle, mocks only stated I/O boundaries. |
| `devtools/validate_presentation_assets.py:1` | 317 | Pending explicit offline validator; shared runtime assembly, duplicate offline reads. |
| `agent_docs/research/d80-test-rework-coverage-audit/generate_coverage_map.py:1` | 740 | Offline historical test AST/lexical audit. |
| `agent_docs/research/d80-test-rework-coverage-audit/manage_legacy_migration_manifest.py:1` | 1377 | Offline historical manifest + AST selector checks. |
| `setup.py:1` | 6 | Installation package discovery. |

Additional browser source completing the 57-file code count:
`devtools/animation_review/gallery.js:1`, 396 lines; review UI only.
`devtools/animation_review/gallery.html:1` (43 lines) and
`devtools/animation_review/gallery.css:1` (568 lines) were read in full separately.
They contain static local UI markup/styles, no embedded execution, remote script,
font dependency, hidden engine bridge or hashing/validation machinery. The HTML
loads the local stylesheet and deferred gallery script; video markup is built
by the inspected JS with metadata-only preload. CSS handles layout and visibility,
not state validation. These 611 markup/style lines are excluded from code counts.

The 14 imported JSON source files, all under `game/data/neuroclient/source/`:

- `public/studio/spell-projectile-assets.json`
- `public/studio/spell-studio-drafts.json`
- `src/render/data/actorVisualProfileBindings.json`
- `src/render/data/actorVisualProfiles.json`
- `src/render/data/ancestryVisualProfileBindings.json`
- `src/render/data/ancestryVisualProfiles.json`
- `src/render/data/animation/actionContextPresentation.json`
- `src/render/data/animation/actionMediaAssets.json`
- `src/render/data/animation/actionPresentationDispositions.json`
- `src/render/data/animation/conditionPresentation.json`
- `src/render/data/animation/contentActionPresentationRecipes.json`
- `src/render/data/animation/generatedSpellPresentationProfile.json`
- `src/render/data/animation/paletteMap.json`
- `src/render/data/animation/vfxSourceHues.json`

## What this audit authorizes

Nothing beyond analysis. The whole-codebase findings must be assembled first.
The strongest source-established repeated-work candidates are whole-history
capture, world diff per unrelated node, duplicate reaction sampling, repeated
media decode, repeated actor-layer matching and ordinary-play diagnostics. Their
relative performance importance remains to be measured on the same workload.
Lineage completeness, observer grants, recorded initialization, passive replay,
history independence, body placement and actual unsupported capability boundaries
remain contracts, not optional defensive machinery.

The subsequent combined proposal still needs the required anti-slop review
(workload/semantic equivalence and measured claims) and anti-OOP review (existing
data owners/import DAG, no added controller/cache/validation framework). This
audit does not substitute reviewer agreement for either source understanding or
behavior evidence.
