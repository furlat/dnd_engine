# Performance repair results — September 12, 2026

The user authorized implementation after the source audit, reviewed repair plan
and plain timing baseline. This is a running results record, not a declaration
that the performance recovery is complete.

[Plan](PERFORMANCE_FIX_PLAN_2026-09-12.md) ·
[Starting baseline](PERFORMANCE_BASELINE_2026-09-12.md)

## First checkpoint: startup ownership, media reuse, native query duplication

Removed the built-in source audit and its dead consumers, empty-external-pack
transaction detour, historical content population gates and the visual ledger's
self-digest/census/collision recomputation. Actual content lookup identity and
registry construction remain. The existing content-set identity contract is a
separate planned review; no replacement source certificate or cache was added.

Shipped assets load directly. Deleted the pending duplicate offline validator
instead of relocating runtime audits into a new tool. The removed negative tests
also covered catalog shape/count expectations; semantic recipe/rig binding checks
and actual media decoding/pixel tests remain. Existing importers own source
conversion. No source folders were rescanned or assets regenerated for timings.

Each presentation session now owns its existing body-row dictionary. Scene
admission, equipment and action/reaction media add missing rig/clip/category/row
keys. Appearance remains a historical value, and tint/condition composition works
on pixel copies. No process-global cache, fingerprint or additional asset manager.
The first preload still loads the existing set of available clips/directions;
this checkpoint does not claim to eliminate that initial decode cost.

The common painter no longer imports native demo production. Reference and
capture composition have explicit commands, documented in their README. Normal
play does not collect duplicate painter evidence or retain a GameFrame per frame.
The active opportunity reaction is sampled once, and legal actor/layer resolution
is reused within the frame. Diagnostic callers explicitly request their evidence.
Gallery export no longer walks and hashes sources/assets; branch/commit/dirty
metadata and actual saved inputs remain.

Native boundary membership reads the relevant Tile bands without temporary
ordered snapshots/full edges. It preserves the current directed optical and
propagation policy; movement/elevation queries still use their existing owner.
Remembered AI fallbacks are copied only when absent from the fresh projection.
BaseBlock no longer performs the same field discovery twice. Pending value and
immutable-item-copy changes were included in validation.

### Same workloads, serial fresh processes

All values are medians of three runs under the same WSL/Python/Pygame setup as
the baseline. Native outcomes retain the same observed variation; timings are
not a proof of semantic equivalence. No diagnostic hashes, video exports,
source verification or asset auditing were added.

| Work | Starting baseline | First checkpoint |
|---|---:|---:|
| Native imports | 4.648s | 4.280s |
| Built-in installation after imports | 0.0209s | 0.0168s |
| Native encounter setup | 0.471s | 0.415s |
| Native activity: eight human turns plus AI | 3.889s | 3.355s |
| Of that, 30 controller advances | 3.068s | 2.670s |
| Of that, eight human moves | 0.535s | 0.426s |
| Whole native process | 10.155s | 9.008s |
| Saved playback imports | 3.989s | 2.657s |
| First actor media preload | 2.363s | 2.227s |
| All 244 four-corner view renders | 0.689s | 0.640s |
| Whole saved playback process | 8.404s | 6.577s |
| Construct a separate 4,096-tile rectangle | 1.642s | 1.412s |

The native runs retain 1,175 event versions, eight human turns/four rounds,
30 controller advances and the same positions. Fighter/sorcerer HP remains
35/24 or 41/18, with goblins at 10/1. Native import samples span 4.167–4.638s;
report the range instead of assigning every difference to a particular edit.
Native controller cost fell about 13%; overall active work about 14%. Cold import
cost and the initial actor preload remain substantial.

The projection workload's median capture cost is 0.373s versus 0.179s previously;
its earlier samples ranged up to 0.421s. Preserve that result rather than claiming
all stages improved. Capture was not changed in this checkpoint. Its scaling
and remaining allocation costs are still a separate planned unit. Public root
reduction remains approximately 0.004s for the 75 received lineages.

Raw outputs are in `.runtime/performance-recovery/repair-1-20260912/`, including
native/project/render samples, external process timings and grid outputs. The
original runners remain under `current-20260912`; `summarize_repairs.py` aggregates
existing elapsed spans without executing or authenticating the game.

### Behavior and design review

- 173 tests pass for authored timing, imported rigs, real pixels, assets, attack
  and opportunity movement, player projection, visible movement and equipment
  sequences (`startup-media-checks.log`).
- 16 continuity checks pass for the actual encounter while history is paused,
  lifecycle/corpse rendering, condition recovery and authored child recovery
  (`continuity-checks.log`).
- 21 modifier/equipment pixel checks pass (`value-equipment-checks.log`).
- Native reviewer: 25 tests pass for built-in construction, direct premades,
  session actions, Dretch and True Seeing/provider/layer behavior. Four-file
  Pyright passes.
- Native query reviewer: 41 block/geometry/AI/perception tests pass. Pyright
  reports pre-existing errors in unchanged native sections; none at these edits.
- Painter reviewer: 14 map-pixel, evidence-on/off, native-demo progression and
  saved-input boundary checks pass. No gallery video export.
- Eight edited media/sampler modules pass Pyright. Syntax compilation and diff
  checks pass after correcting a mechanical keyword-position error in diagnostic
  callers. Earlier test collection attempts that referenced a nonexistent test
  filename or the temporarily incomplete import migration were not test passes.

The anti-slop review confirmed that shared pixel sources do not replace historical
appearance, placement or state; that completed reaction consequences still fold;
and that frame collection has no role in encounter control. The anti-OOP review
kept actual Tile membership ownership and rejected a special stop-only AI world
projection: continuing moves still need ordinary observation memory/cursor/epoch
updates.

## Second checkpoint: passive public owners and explicit AI values

Moved the existing public reducer/codec to `game/player_reduction.py` and native
actor folding to `game/actor_projection.py`. `actor_facts.py` owns its passive
records, including PresentationTarget. The existing sensory snapshot and its
reducer now live in `dnd/types/senses.py`; the native sensory block explicitly
re-exports them. A fresh-process check confirms the public decoder/sampler/painter
does not import native actions, conditions, entity construction or projection.
This is an eager import DAG with the same public data, not a new schema or codec.
The gallery CLI still imports the legacy native-v2 converter; the narrower
public playback boundary is what was tested and measured here.

Replaced the internal AI outcome/exposure dump-and-revalidate bridge with explicit
owned value conversion. Enum meaning, UUID-to-string conversion and mutable
native exposure detachment remain. A walking tile's normalized cost is evaluated
once for its walkability/cost fields. Per-step world-memory refresh remains intact.
Sensory snapshot containers and mutable SenseMode leaves stay detached; sharing
frozen contacts does not authorize sharing mutable modes.

| Work | Starting baseline | Second checkpoint |
|---|---:|---:|
| Native imports | 4.648s | 4.377s |
| Native encounter setup | 0.471s | 0.429s |
| Native activity: eight human turns plus AI | 3.889s | 3.392s |
| Whole native process | 10.155s | 9.172s |
| Capture in the paired projection workload | 0.179s | 0.166s |
| Public projection in that workload | 0.0444s | 0.0424s |
| Public reduction in that workload | 0.00447s | 0.00377s |
| Saved playback imports | 3.989s | 1.993s |
| First actor media preload | 2.363s | 2.341s |
| All 244 four-corner view renders | 0.689s | 0.637s |
| Whole saved playback process | 8.404s | 5.853s |

These are again three serial fresh-process medians. The second checkpoint's
native timings are slightly slower than the first; do not attribute a measured
speedup to the AI adapter edit. Capture was unchanged in both measurements and
varies between runs. The saved renderer still loads all available actor clips at
this checkpoint. Its process times range 5.740–5.870s. The scripts changed only
their moved public-reducer import; scene, event input, view count and timestamps
are unchanged. Raw outputs are under `repair-2-20260912/`.

Validation: 21 public projection/discovery/visibility and fresh import-boundary
checks; seven sensory/history/mutable-mode/True Seeing checks; 12 AI adapter and
actual native AI checks pass. Focused production typechecks pass. A real saved
doorway input decodes, reduces, binds and samples without native event generation
(native cursor zero), retaining its one root, two visible movement legs,
833.33ms duration and final public cursor 93. Typed data roundtrip equality is
the contract; byte order of JSON sets is not an added acceptance rule.

### Remaining native import cost

A separate cProfile run of native bootstrap/session imports took 6.646s wall and
4.836s CPU with instrumentation. Its cumulative times are nested, not additive:
806 Pydantic class constructions account for 4.129s; 1,493 filesystem `stat`
calls account for 1.152s, with 1,481 coming from ordinary Python import lookup.
This is not the removed source audit. The profiled process is not a replacement
for the uninstrumented 4.377s measurement.

The eager native content/type graph and WSL mounted-filesystem import I/O remain
costly. There is no evidence here for adding import caches or reviving source
validation. A broad Pydantic rewrite or mass deferred model construction has not
been undertaken. Profile and readable rows are
`repair-2-20260912/native-import.prof` and `native-import.txt`.

### Initial media overloading found by measuring row ownership

A separate plain-timer request of the actual two-actor doorway scene loads
**1,008 body rows: 247,726,080 surface pixels, about 945 MiB at 32 bits/pixel**.
The first request takes 2.372s. Two identical requests using the session's loaded
row dictionary take 0.627ms and 0.532ms and decode no new rows. These are one
diagnostic run, not three-run medians (`repair-2-20260912/media-rows.json`).

Reuse works; initial selection was excessive. The scene asked for every
available clip. The third checkpoint narrows it to standing/dead poses and the
actual clips/loadouts in the next bound complete head. Existing typed motion and
choreography cues supply those requests, including reactions, body actions,
equipment, forced movement, damage, recovery and lifecycle changes. The same
session map and existing loaders own media. No frame simulation, new asset
manager, global cache or per-spell loading system is needed.

## Further owner-local changes included in the third checkpoint

`apply_world_fact` now reports whether it applied a supported world after-value.
Public projection computes world differences only then or after this observer's
sensory update. The sensory child still folds a spatial ancestor's committed
after-value before the parent's terminal record. All actor facts, nodes and
admission processing remain. Thirteen existing public projection/discovery tests
and the two-file typecheck pass. No world signature/cache/dirty-event bus.

Gallery export no longer computes per-frame pixel SHA. Its existing explicit
pause diagnostic compares current RGB bytes directly with one retained paused
frame and releases that reference on resume. This is separate from normal play;
no video has been exported for performance timing.

## Capture growth through actual native equipment and doorway history

A bounded diagnostic constructs the existing two-actor doorway experiment, then
performs 9, 33 or 129 actual alternating shortsword/dagger equipment operations
on the unseen subject during its current turn. Every experiment ends with the
same native seven-point Force damage and discovered movement from `(8, 4)` to
`(8, 10)`, crossing the visible doorway. No event is injected or reconstructed
inside EventQueue. Native setup, equipment/damage/movement execution and imports
are outside the following capture clocks.

Each row uses a separate native experiment. Its median is three consecutive
read-only captures of that same live history, not three fresh processes. The
full-history measurement captures both actual observers from their recorded
baseline, including each observer's initialization. Single-operation values
below are for the external observer; both observers' raw samples are retained.

| Actual swaps | Source versions | Complete roots per view | Last equipment operation, four roots | Same doorway Move, one root | Entire history, both observers |
|---:|---:|---:|---:|---:|---:|
| 9 | 195 | 38 | 1.48ms | 5.15ms | 0.0472s |
| 33 | 435 | 134 | 3.58ms | 5.49ms | 0.1826s |
| 129 | 1,395 | 518 | 11.86ms | 7.40ms | 1.7993s |

The larger batch demonstrates material growth from repeatedly reconstructing
source history. It does not establish that the ordinary live receive path is
the dominant native cost: this workload's individual operations still capture
in milliseconds. Nor does it authorize a persistent cross-operation actor fold.
The source-backed next distinction is between sharing one batch's already
recorded source index and changing actor admission ownership.

The semantic checks accompany the timing: the final equipment operation has
four distinct terminal roots, including one pair of overlapping source
intervals. They remain separate complete lineages. Both captured views retain
the actual root identities and completion order. The observer's admission of
the subject carries its current **33 HP and equipped dagger**, anchored on an
actual sensory child rather than the movement root's completion. Capturing does
not add native events. These are concrete retained-history checks, not a claim
that equal event counts prove the entire game equivalent.

Raw samples and the finite script are
`.runtime/performance-recovery/capture-growth.json`, `capture-growth.log` and
`capture_growth.py`. They contain no source fingerprints or video work. The
world-difference guard was present; the subsequently proposed removal of frozen
contact leaf copies was not yet applied during these samples.

### Batch indexing repair

The existing capture owner now indexes native versions once for a requested
batch, then selects and source-orders each complete root's versions. Single-root
capture uses the same function. The batch still advances its known-actor set
after each returned root in the existing order. `_capture_actor_admissions` is
unchanged: no persistent actor fold, new registry or admission-time rule.

A separate non-timing run compares complete typed outputs against an ephemeral
copy of the preceding capture function on the **same live native history**.
Both perspectives match at all three sizes, including overlapping equipment
roots and the actual sensory-child admission. Thirty-one existing discovery,
concealment, recorded replay, gameplay/condition/OA and equipment checks pass;
the two-file typecheck passes.

| Actual swaps | Previous paired batch | After indexing/contact-sharing changes |
|---:|---:|---:|
| 9 | 0.0472s | 0.0447s |
| 33 | 0.1826s | 0.1534s |
| 129 | 1.7993s | 1.5002s |

The largest batch is about 17% faster. The existing private actor-history
refold still grows superlinearly and is **not fixed** by this indexing change.
Individual-root measurements are roughly unchanged: the largest observer
equipment operation is 12.08ms versus 11.86ms, and the reveal Move is 7.63ms
versus 7.40ms; the other viewpoint's equipment result is slightly lower.
These samples establish neither a material live regression nor a live speedup.
No special single-root path was added to chase that noise.

The after run also includes frozen-contact sharing, so indexing alone cannot
claim its entire gain. Original samples remain unchanged. New raw outputs are
`capture-growth-after.json`, `capture-growth-after.log` and
`capture-growth-typed-comparison.log` in the same diagnostic directory.

## Third checkpoint: request the media actually used

Scene preparation now loads only its standing/dead poses. The next complete
bound head supplies its movement, action, reaction, equipment, damage, recovery
and lifecycle clips through the existing typed cues. All required facing rows
and retained loadout variants use the same session dictionary. Live play and the
recorder request staged/after standing poses at each head, covering revival and
newly disclosed actors without changing when they are displayed.

The existing world SurfaceCache now decodes each requested canonical raster on
first use. Its scaled/tinted/cropped derivatives keep their existing ownership
and keys. The world painter requests water textures only when it has water
rows. No new cache manager, lazy import, custom mapping or asset audit.

All timing rows below are three-run medians of the same workloads. The saved
renderer still uses the same input, 61 timestamps and four camera corners.
It now explicitly prepares the bound motion, as required by the narrower API.

| Work | Starting baseline | Third checkpoint |
|---|---:|---:|
| Native imports | 4.648s | 4.236s |
| Native encounter setup | 0.471s | 0.424s |
| Native activity: eight human turns plus AI | 3.889s | 3.308s |
| Of that, 30 controller advances | 3.068s | 2.622s |
| Whole native process | 10.155s | 8.952s |
| Capture in the projection workload | 0.179s | 0.171s |
| Public projection in that workload | 0.0444s | 0.0131s |
| Public reduction in that workload | 0.00447s | 0.00363s |
| Saved playback imports | 3.989s | 2.013s |
| Initial actor poses | 2.363s (all clips) | 0.164s |
| Actor poses plus the actual movement head | 2.363s (all clips) | 0.322s |
| All 244 four-corner view renders | 0.689s | 0.733s |
| First four views, including first-use preparation | 0.0768s | 0.1846s |
| Mean per view for the remaining 240 views | 2.549ms | 2.286ms |
| Whole saved playback process | 8.404s | 3.493s |

The full saved process ranges 3.475–3.524s. World-cache construction now takes
0.005s rather than decoding all 72 world resources up front. **Required world
decoding moved into first-use drawing**: the larger first-four-view number and
244-view total include that cost. The whole-process result, not the empty cache
constructor, establishes the gain. The steady view times describe this small
saved scene; they do not establish interactive frame rate while native AI runs.

The initial body set is **72 rows / 17,694,720 pixels / 67.5 MiB**. Preparing the
actual movement raises that to **136 rows / 33,423,360 pixels / 127.5 MiB**,
versus **1,008 rows / 945 MiB** before. In a separate one-run reuse diagnostic,
the two repeated scene requests take 0.080ms and 0.028ms; repeated movement
preparation takes 0.374ms. None decodes additional body rows. These reuse spans
are individual samples, not medians.

Native outcomes retain the original 1,175 event versions, eight human turns,
four rounds and final positions. The original fighter/sorcerer HP variation
also appears in the projection runs. Native imports range 4.210–4.304s.
The separate rectangle-construction result remains the first checkpoint's
1.412s; no tile representation change occurred afterward.

Validation for this checkpoint:

- Demand media: **124 pass, six existing terrain-occlusion xfails**. Covers
  motion, jump, forced movement, equipment, reaction/body action, condition,
  healing, lifecycle, public projection and discovery. Four raised-jump rear
  views and two forced stair cases remain known painter failures; they were
  not changed or newly marked as expected failures here.
- This selection inadvertently included two existing gallery export tests
  (paused lifecycle and healing). They passed, including actual paused RGB
  comparison. They were incidental correctness exports, not timing workloads;
  no additional export was run to repeat them.
- World assets/water/boundaries and the actual paused-history encounter:
  **132 pass in 19.66s**. Required media still decodes into the same pixel
  expectations. This batch contains no gallery export.
- Fourteen demand-media source/test files and three world/encounter production
  files pass focused Pyright. Final diff check passes.

The anti-slop/anti-OOP reviews verified actual cue/loadout selection, unchanged
sampling/clocks, detached condition pixel work, same-map ownership, and the
world cache's unchanged derivative semantics. No gameplay feature or new
animation recipe was added during this repair.

Raw outputs and runnable scripts are under
`.runtime/performance-recovery/repair-3-20260912/`. Correctness logs are
`demand-world-encounter-checks.log` and `demand-world-encounter-types.log` in its
parent; demand-media logs are preserved there as `demand-media-checks.log` and
`demand-media-types.log`.

## Open work and limits

The measured repairs remove audit obligations, excess preloading, import
coupling and repeated native/projection work. They do **not** close performance
recovery. The remaining large owners are explicit:

1. Native cold imports still take about 4.24s. The existing profile identifies
   eager native Pydantic class construction and module I/O. The next import
   design must address actual dependencies/representation; adding schema caches,
   late imports or mass unchecked construction would preserve the wrong premise.
2. Private admission capture still refolds actor history per root. A retained
   source-ordered fold needs the plan's acquisition-time/overlapping-root design
   review. Batch completion order is not an acceptable replacement for that.
3. The separate 4,096-tile construction remains 1.41s. No terrain representation
   redesign, root-compilation rewrite or content identity redesign was smuggled
   into these bounded repairs. Those remain the plan's separately bounded work.

Legacy external-pack/SDK limitations from the earlier checks remain: the broad
pack-loader selection had 13 failures, and full SDK generation is blocked by
the retired server's missing `dnd.core.senses` dependency. No claim is made that
those retired paths pass. The removed field's compatibility cleanup is not a
reason to revive that server. The current game/presentation checks above are
the exercised paths. Feature/VFX development has not resumed.
