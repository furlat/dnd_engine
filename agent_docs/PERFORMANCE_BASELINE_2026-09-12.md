# Current performance baseline — September 12, 2026

Measured the current working tree after the whole-source audit, **before any
implementation of the new fix plan**. The existing uncommitted performance edits
are included. This is the starting baseline for the next fixes, not a claim that
those pending edits are correct or that performance is acceptable.

Twelve successful fresh-process runs: three native, three native with capture/
projection, three render-only, three large-map construction. All were serial.
No cProfile instrumentation was enabled. The harness uses elapsed timers and
small workload/outcome records. It adds **no source hashes, frame hashes,
fingerprints, asset audits or replay certification**. No gallery, video, trace
export, SDK generator or test suite was run. Remaining checks inside the current
game are included in its cost; they were not bypassed to improve the numbers.

Environment: Python 3.12.3 in the project `.venv`, WSL2 Linux 6.6.87.2, project
under `/mnt/c/users/tommaso/documents/dev/dnd_engine`. Pygame runs with dummy video
and audio for the rendering workload. Fresh processes do not imply flushed OS
file caches. These measurements describe this environment, not Windows-native
Python or a monitor/GPU/vsync benchmark.

[Fix plan](PERFORMANCE_FIX_PLAN_2026-09-12.md) ·
[Raw summary](../.runtime/performance-recovery/current-20260912/summary.json)

## Native game only

Real four-actor encounter on `battlefield.open_floor_bright`, two player
characters and two native-AI goblins. The driver requests the shortest offered
Move, Dodge and EndTurn for each human turn. AI uses its existing controller
and discovered actions. Eight human turns, four rounds, 30 controller advances,
16 discovery calls, eight Moves and eight Dodges. All runs produced **1,175 event
versions** and the same final actor positions. Pygame is not imported.

| Work | Median | Range of three runs |
|---|---:|---:|
| Import native session/content | **4.648s** | 4.634–4.739s |
| Install content after imports | 0.0209s | 0.0204–0.0217s |
| Construct/deploy encounter | **0.471s** | 0.466–0.492s |
| Controller advancement, including actual AI, 30 calls | **3.068s** | 3.049–3.082s |
| Human action discovery, 16 calls | 0.225s | 0.219–0.229s |
| Execute eight human Moves | 0.535s | 0.522–0.537s |
| Execute eight Dodges | 0.0603s | 0.0587–0.0618s |
| End eight human turns | 0.00291s | 0.00284–0.00298s |
| All active native work above, excluding setup/import/close | **3.889s** | 3.855–3.911s |
| Close session | 0.0755s | 0.0747–0.0800s |
| Reset runtime | 0.0213s | 0.0203–0.0217s |
| Outside instrumented calls | 0.998s | 0.977–1.004s |
| **Whole process** | **10.155s** | **10.048–10.237s** |

The active-work row is calculated per run before taking its median; it includes
the five activity rows, which must not be added again. Whole process is measured
by the parent timer. The remainder includes interpreter/driver work, final
cleanup and output outside the named calls; this diagnostic does not attribute
all of it to one particular cause.

The seeded driver does **not** guarantee identical outcomes: the fighter/sorcerer
HP split was 35/24, 41/18, 35/24. Goblins ended at 10/1 in all runs. Final positions
were fighter (13,13), sorcerer (12,14), goblins (11,12)/(10,13). This is a stable
size/activity workload with real outcome variation, not a deterministic proof of
semantic equivalence. Future timing comparisons must retain the counts and
report outcome changes; focused behavior tests establish correctness separately.

## Native game plus public event processing

The same native driver additionally captures startup and each completed root for
the first player, projects its received lineage, and reduces public state. The
existing native driver timer excludes these capture calls from native action
spans, so the rows below measure additional named work directly.

| Additional work | Median | Range |
|---|---:|---:|
| Import projection modules | 0.0696s | 0.0687–0.0848s |
| Capture startup | 0.00581s | 0.00535–0.00587s |
| Project startup | 0.00121s | 0.00116–0.00131s |
| Reduce startup | 0.000223s | 0.000211–0.000316s |
| Capture 83 native roots | **0.179s** | **0.169–0.421s** |
| Project 83 roots | **0.0444s** | 0.0436–0.0450s |
| Reduce 75 received public lineages | **0.00447s** | 0.00447–0.00465s |
| Active native work in these runs | 3.904s | 3.825–3.954s |
| **Whole process, including native startup/setup** | **10.537s** | **10.476–10.601s** |

The capture maximum is retained, not discarded as an inconvenient outlier. No
extra profile was run to assign its cause. Public reduction is small in this
workload; repeated capture/history traversal is real source debt but currently
less expensive than native controller execution or imports. Long-history scaling
requires a separate bounded measurement when that owner is changed. This table
is not a promise that capture stays cheap as history grows.

## Saved-event playback and drawing — no native game execution

Input: the already-saved `sight-doorway-cross` public sequence from the paired
visibility run. One complete movement lineage, two actors across the observed
sequence. Read the existing wrapper, decode its sequence through the production
public decoder, and call the actual motion binder, frame sampler, painter and
labels. No native scenario producer, content bootstrap, AI or game turn runs.
Native schema imports still occur through the current dependency graph.

Render **61 timestamps across the 833.33ms movement, from four camera corners**:
244 individual 960×540 view renders. No sleeps, realtime pacing, video encoding,
frame hashes, full trace output or gallery preflight. This is a small doorway
movement scene, without an opportunity attack or spell/VFX workload.

| Preparation or execution | Median | Range |
|---|---:|---:|
| Import current render/decode owners | **3.989s** | 3.955–4.079s |
| Read saved input wrapper | 0.00522s | 0.00520–0.00546s |
| Decode public sequence and reduce initialization | 0.00357s | 0.00336–0.00371s |
| Reduce its one root | 0.0000861s | 0.0000849–0.0000897s |
| Load authored animation records/rig mappings | 0.0849s | 0.0843–0.0890s |
| Load world catalog | **0.00524s** | 0.00501–0.00525s |
| Decode world sprites | **0.414s** | 0.409–0.425s |
| Decode/crop actor body rows | **2.363s** | **2.292–2.375s** |
| Bind retained movement | 0.000823s | 0.000728–0.000865s |
| Sample all 244 views | 0.256s | 0.253–0.257s |
| Paint all 244 views | 0.305s | 0.303–0.306s |
| Draw actor labels for all views | 0.128s | 0.127–0.130s |
| Dummy display flips, all views | 0.000693s | 0.000576–0.000697s |
| **All view work: sampling + painting + labels + flips** | **0.689s** | **0.687–0.692s** |
| **Whole process, including imports/assets/exit** | **8.404s** | **8.358–8.518s** |

Pygame initialization, display setup, fonts and quit are separately recorded in
the raw data; combined they are small compared with imports/body decoding. Each
run reports `engine_bootstrapped=false`.

After excluding only the first timestamp in each corner, the 240 remaining view
renders average **2.549ms per view** (range 2.543–2.563ms across runs). Per-run
95th percentile is **2.770–2.867ms**. The first view costs **53.3–58.8ms**; the
first views in later corners cost about **6.3–9.1ms**. These initial costs remain
included in the 0.689s total. Do not confuse steady per-view timing with startup,
all-four-corner cost, or guaranteed gameplay FPS.

The actor preload requests the actual before/admitted/after appearances and the
existing scene loader's available clips/directions. The measured 2.36s belongs
to that current loading policy; it is not the time to draw two already-loaded
sprites. Future media changes should measure new rows and already-loaded rows
separately, with their actual identities.

## Large map construction, independently of the encounter

Direct `get_map().create_rectangle(0, 0, 64, 64)` in a fresh process. The same
4,096-cell construction call used in the earlier historical comparison. No
content bootstrap, Pygame, actors, capture or rendering.

| Work | Median | Range |
|---|---:|---:|
| Import GridMap/native dependencies | 1.092s | 1.087–1.148s |
| **Construct 4,096 tiles** | **1.642s** | **1.538–1.647s** |
| **Whole process** | **4.148s** | **4.045–4.208s** |

The process includes roughly 1.4s outside the two timed spans, including the
small postconstruction tile check, interpreter/driver overhead and final process
cleanup. This diagnostic does not attribute that remainder to a specific owner.
The 1.64s construction result and 0.47s encounter setup describe different map
sizes and composition work; neither may be substituted for the other.

## What these measurements prioritize

1. Ordinary imports and media preparation dominate starting both native play and
   saved playback. Remove the audited unnecessary work and separate imports at
   real owners; do not hide cost with source/schema caches or late imports.
2. Native controller/query/projection work dominates this turn workload. Start
   with proven discarded copies/edge construction, then review the actual AI
   projection consumer.
3. Current public reduction and small-scene drawing are much smaller costs.
   Fix their concrete duplication at the correct owners, without presenting
   scalar checks or single-spell graphics as the main performance project.
4. Capture scaling and compact terrain representation remain important, bounded
   design work. Their priority comes from the workload they actually affect.

These are measurements of the pending working tree, not a before/after result
for today's plan: **no production code changed in this session**. Earlier
figures in the audit have different sample counts and, in places, instrumentation;
use this current baseline for subsequent comparisons rather than claiming an
exact speedup from unmatched runs.

## Repeat the measurement

From the repository root, run these serially using the same virtual environment and a fresh result directory:

```bash
.venv/bin/python .runtime/performance-recovery/current-20260912/run_native.py .runtime/performance-recovery/next-checkpoint
.venv/bin/python .runtime/performance-recovery/current-20260912/run_render.py .runtime/performance-recovery/next-checkpoint
.venv/bin/python .runtime/performance-recovery/current-20260912/run_grid.py .runtime/performance-recovery/next-checkpoint
```

The scripts are ordinary local diagnostic files. The native script reuses
`.runtime/performance-recovery/native_session.py` without `--profile`; rendering
uses `render_saved.py`; the map case reuses `historical-grid-child.py`. They write
small timings/counts to the supplied result directory. The baseline remains at
`.runtime/performance-recovery/current-20260912/`. Use a new directory name for
each later comparison so earlier measurements remain available. No new benchmark plugin or
runtime dependency was introduced.

[Native measurements](../.runtime/performance-recovery/current-20260912/native-processes.json),
[render measurements](../.runtime/performance-recovery/current-20260912/render-processes.json),
[map measurements](../.runtime/performance-recovery/current-20260912/grid.json).

One renderer pilot failed because the diagnostic used `duration_ms` instead of
the existing motion field `complete_ms`. Only the diagnostic was corrected; the
pilot is excluded from successful timings and its log remains `render-pilot.log`.
No runtime behavior or correctness threshold was changed to make a measurement
pass. No additional correctness claim follows from the twelve successful runs.
