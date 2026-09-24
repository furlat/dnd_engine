# Production art size and measured reduction options — 24 September 2026

**Historical baseline:** this report analyzes the earlier 15.066 GB release.
The subsequently authorized support/cloud work is recorded in
[the cloud implementation record](CLOUD_LOOP_REDUCTION_2026-09-24.md). New
32 FPS support media adds 29.103 MB; replacing six maintained cloud banks saves
10.043 GB, bringing the complete production selection to 5.052 GB. The options
and recommendation below describe the earlier read-only investigation, not a
request to start another compression project.

This is a read-only analysis of production release `recovery-cleanup-20260924`
(`f7474408`), paired with code release `recovery-cleanup-20260924`. The exact
manifest is `/home/tommaso/Dev/neurodragon_art-production/art-manifest.json`.
It lists 24,783 files and 15,065,521,247 encoded bytes (15.066 decimal GB,
14.03 GiB). No production media, bindings, or source snapshot were changed.

## Where the installed bytes go

| Installed domain | Bytes | Decimal GB | Share |
| --- | ---: | ---: | ---: |
| Spell and liquid VFX, including Fire Bolt media | 14,926,266,964 | 14.926 | 99.0757% |
| Environment, objects, torch and water | 77,683,140 | 0.078 | 0.5157% |
| Smallscale character bodies, gear and overlays | 61,571,143 | 0.062 | 0.4089% |
| **Total** | **15,065,521,247** | **15.066** | **100%** |

The 187,492 bytes of Fire Bolt media live under `neuroclient` but are included
in the VFX total above. This is a useful scale check: character and environment
art together are under 0.14 GB; deleting character options cannot meaningfully
solve a 15 GB installation.

### Physical VFX family allocation

This is a canonical-folder rollup from the release manifest. `packed/VFX` is the
generated finite-effect bank folder; `persistent_spells` includes persistent
fields plus other persistent spell material. Individual logical spells may
reference shared files, so this reports where bytes physically live, not the
size of a standalone spell installer.

| Physical family | Bytes | Decimal GB |
| --- | ---: | ---: |
| Persistent spell banks | 11,889,640,055 | 11.890 |
| Packed finite VFX banks | 2,398,102,578 | 2.398 |
| Cantrips | 160,599,472 | 0.161 |
| Support spells | 110,060,394 | 0.110 |
| Pending spells | 85,477,954 | 0.085 |
| Healing spells | 81,590,267 | 0.082 |
| Liquid media | 60,164,651 | 0.060 |
| Ice spells | 55,766,393 | 0.056 |
| Other neuroclient VFX (Fire Bolt) | 187,492 | 0.0002 |
| Control spells | 45,384,583 | 0.045 |
| Globe media | 25,601,892 | 0.026 |
| Spell recovery | 12,698,553 | 0.013 |
| Counterspell media | 385,012 | 0.0004 |
| CodexFX | 362,758 | 0.0004 |
| Area spell data | 244,910 | 0.0002 |

These rows total 14,926,266,964 bytes. The physical folders show why the six
maintained volume spells dominate: they account for 11.486 GB, while the rest of
the persistent-spell folder contributes about 0.404 GB.

### Smallscale character art by rig/family

| Family | Bytes | Decimal MB |
| --- | ---: | ---: |
| Modular body/gear/overlay sheets | 52,284,914 | 52.285 |
| orc01 | 2,856,207 | 2.856 |
| goblin01 | 1,782,360 | 1.782 |
| demonbeast01 | 1,140,454 | 1.140 |
| demonbeast02 | 1,220,692 | 1.221 |
| demonbeast03 | 1,229,273 | 1.229 |
| skeletonarcher05 | 783,249 | 0.783 |
| greywolf | 273,994 | 0.274 |
| **Total** | **61,571,143** | **61.571** |

These figures cover installed production sheets only. The purchase/source archive
may contain additional full pack content and is not the same thing as this
release. Cross-referenced actor overlays must not be counted twice. Existing
character sheets are already sprite sheets; flattening modular clothes, gear,
and bodies into combinations would multiply storage and lose flexibility.

### Persistent volume fields

The six persistent volume banks alone use 11,485,840,285 bytes (11.486 GB,
76.24% of the complete release). Each row is the physical canonical-folder
allocation; shared page identities are not a spell-by-spell package estimate.

| Volume | Color bytes | Position bytes | Total bytes | Total GB |
| --- | ---: | ---: | ---: | ---: |
| Stinking Cloud | 599,635,803 | 2,530,663,954 | 3,130,299,757 | 3.130 |
| Cloudkill | 473,617,976 | 2,107,986,332 | 2,581,604,308 | 2.582 |
| Darkness | 252,706,607 | 2,098,032,005 | 2,350,738,612 | 2.351 |
| Fog Cloud | 565,895,956 | 1,218,025,812 | 1,783,921,768 | 1.784 |
| Incendiary Cloud | 320,677,028 | 1,063,166,151 | 1,383,843,179 | 1.384 |
| Insect Plague | 81,738,769 | 173,693,892 | 255,432,661 | 0.255 |
| **Total** | **2,294,272,139** | **9,191,568,146** | **11,485,840,285** | **11.486** |

There are 6,601 position PNGs (61.01% of all installed bytes) and 9,996 color
PNGs (2.294 GB). Position images are data maps. `registered_media.py` decodes RG
and BA byte pairs as two uint16 coordinate channels; the persistent bindings
declare bounds `[-4, 4]` and reference footpoint files. They are not ordinary
color RGBA images and should never be passed through color/alpha treatment.
These fields use XY coordinates; newer finite AoE packets can separately carry
XYZ and ownership data.

### Other representative VFX banks

These ZIP_STORED package allocations are exact current manifest bytes. ZIPs
reduce loose-file count and retain the original gzip XYZ packets; they do not
substantially recompress those packets.

| Bank | Bytes | Decimal GB |
| --- | ---: | ---: |
| Fireball impact/explosion | 998,477,981 | 0.998 |
| Gust of Wind | 607,964,446 | 0.608 |
| Sleep | 380,790,040 | 0.381 |
| Thunderwave | 154,414,038 | 0.154 |
| Burning Hands | 78,231,964 | 0.078 |
| Color Spray front + back | 100,858,418 | 0.101 |
| Shatter front + back | 47,520,546 | 0.048 |
| Ice Knife impact | 25,209,069 | 0.025 |
| Eldritch Blast | 2,296,243 | 0.0023 |
| Acid Splash | 1,419,858 | 0.0014 |
| Guiding Bolt | 759,998 | 0.0008 |

Protection/defense media is another 375,942,583 bytes: energy 290,932,210;
shield 37,001,327; mage 32,043,048; hit 12,057,714; sanctuary 3,908,284.
The supplied production inventory and current owner ledgers cover the other
selected spells and conditional alternatives; do not infer one independent
package's logical dependency size by summing shared physical folders.

## What packaging already saved

The preserved installed-art snapshot has 62,769 files / 26,660,655,022 bytes.
The production inventory excludes 5,551 archive-only files (5,959,706,594
bytes) and shares exact retained payload aliases (5,781,548,704 duplicate
bytes). Its pre-new-packing unique candidate is 14,919,399,724 bytes. The final
production manifest is 15,065,521,247 bytes: 43.49% smaller than the full
installed snapshot, but 146,121,523 bytes above the earlier unique-payload
candidate after the corrected selections, indexes, and packed products.

The release replaced 29,075 base files with 23,976 retained files and 807
generated packed files; the final count is 24,783. Packaging means selecting
reachable content, sharing identical physical payloads, and bundling frames,
pages, and packets with explicit indices. It does not mean a matching 44%
compression ratio. Original PNGs remain PNGs, and selected geometry gzip
packets are stored unchanged in ZIP banks. No blanket frame thinning or broad
downsampling was used; the selected clocks, timing, cameras, and approved output
were kept.

Full purchased vendor packs are not represented by the 15.066 GB number. The
preserved installed-art snapshot is 26.661 GB; full external source packs and
unintegrated handoffs may be larger still. Keep them archived separately from
the current runtime installation.

## Bounded reduction opportunities

### Exact coordinate-page encoding: promising, not yet a release estimate

An existing probe tested ten 2048×2048 persistent-position pages. Each is
16,777,216 decoded bytes. A reversible uint16 delta + byte-plane + zlib encoding
round-tripped every sample exactly. The best axis per sample produced
12,413,438 bytes from 20,049,221 PNG bytes in aggregate: 7,635,783 bytes less
(38.1%) across only those ten pages. Individual changes ranged from 4.3% to
42.7%. Candidate decode times were approximately 31–105 ms/page versus 30–48
ms for PNG in that probe, and encoding took roughly 0.6–1.8 seconds/page.

This is a small sample, not a justified 38% multiplier across 6,601 pages. It
would require a new numeric decoder/installer path and full coordinate,
footpoint, occupancy, wall/contact and camera regression evidence. First expand
the offline sample across every volume, all page indices, and difficult edge
values; then compare decoded arrays and gameplay-visible projections exactly.
Do not quantize coordinate precision or reinterpret channels as color.

### Repeated temporal data and exact page sharing

Exact aliases already saved 5.782 GB relative to retained source paths. Continue
to use the ownership/alias ledger to identify any unshared identical pages or
repeated sequences before considering lossy transforms. Shared content should
be charged once physically and attributed to each logical owner separately.
Temporal delta coding is a second bounded experiment after page-level sampling:
compare adjacent-frame XOR/delta entropy per bank, and preserve random access,
frame timing, all camera rows and exact reconstruction. No savings estimate is
available yet.

### Packed-page compaction and small bakes

The inventory already identifies concrete fixed bake candidates (Color Spray
front/back and Ashen floor motifs) and selected-cell compaction in atlases.
These are bounded asset subsets, not a plausible multi-GB reduction. Rebuild a
small candidate page with explicit cell remaps, compare every selected frame
against the current output at supported zooms and all cameras, and only count
encoded bytes after a release-like pack. Existing spritesheets need no conversion
to loose frames. Environment strip paging and frame bundling mainly reduce file
count and load overhead; they do not necessarily reduce encoded payload.

### Resize / frame reduction

No broad resize or frame deletion is supported by this evidence. Many assets
render at native pixels at supported zoom 1, and 144 FPS source phases can be
sampled at arbitrary elapsed times. Removing frames risks clock and visual
changes. Any later quality tradeoff needs an explicitly approved scope and
all-camera output comparisons. Keep current complete selected timelines.

## New offline study: FPS reduction, loop duration, and matrix factorization

The following experiment reads production `bindings.json` and referenced pages
without modifying production. It probes the east-facing `q0` sequence for
Stinking Cloud, Darkness, and Incendiary Cloud. These three sequences represent
two 28-second clouds and one 16-second cloud; they are a diagnostic sample, not
the six-bank release total. For frame-size/delta comparisons it measures the
first 120 source frames (0.833 seconds at 144 FPS), at native crop dimensions
registered to a shared 832x640 canvas. An SVD diagnostic samples at most 96
24-FPS timestamps over each full hold and nearest-samples the registered frame
to 64x64. It is not a production format or a visual acceptance test.

### Candidate clocks and loop policy

Current hold lengths in `world_bindings.json` are Stinking Cloud, Cloudkill,
Darkness and Fog Cloud: 4,032 frames (28 seconds at 144 FPS); Incendiary Cloud:
2,304 frames (16 seconds); Insect Plague: 1,152 frames (8 seconds). Current
`maintained_media_frame()` wraps the elapsed-time sample at `holdFrames`.

At a 24-FPS output clock, preserving those durations requires 672, 384, and 192
frames respectively. At 32 FPS, it requires 896, 512, and 256. Both keep the
same real-time cycle duration when sampled on source timestamps; 32 FPS is a
rational 144-to-32 resample, not every Nth frame. The 60-FPS game loop will
repeat/hold some asset frames at either rate. A 24-FPS clock retains 1/6 of the
144-FPS samples (83.3% fewer); 32 FPS retains 2/9 (77.8% fewer). Encoded bytes
will not necessarily fall by those exact percentages because atlas pages,
metadata, padding and page repacking add fixed costs.

The shared four 28-second cloud cycles look long for visual loops. A shorter
loop must be newly authored and re-exported to make the wrap seamless; cropping
the current loop or selecting a convenient segment cannot guarantee a perfect
transition. The cloud owner inspected native lifecycle timing and reported
these new candidate periods, both integral at 144 and 32 FPS:

| Effect family | Candidate full period | Cohort/lifetime model | Candidate reduction from existing hold |
| --- | ---: | --- | ---: |
| Smoke clouds (Stinking Cloud, Cloudkill, Darkness, Fog Cloud) | 5.625s | Two deterministic alternating cohorts; about 2.8125s lifetime, under 0.5% adjustment from current 2.8s lifetime; re-author shader timing together with geometry for the shorter cycle | 79.9% from current 28s hold |
| Fire cloud (Incendiary Cloud) | 3.25s | Two deterministic cohorts; about 1.625s lifetime, under 2% adjustment from current 1.6s lifetime; re-author shader timing together with geometry for the shorter cycle | 79.7% from current 16s hold |
| Insect Plague | Not selected yet | Requires new closed trajectories preserving the 360 insect count and speed; do not just speed up playback | Not estimated |

These are authoring targets reported by production, not approved durations or
completed exports. Re-export the paired color and position data together,
retain original 28/16/8-second assets, and validate the new loop through the
boundary for density, motion and appearance in all four cameras before
replacing any runtime binding. Lowering playback FPS remains separate from
shortening the authored visual cycle.

Selection must use source timestamps and apply the same selected source-frame
index to both the color crop and its paired coordinate/footpoint crop. Preserve
per-phase durations and camera/facing coverage. For 168-FPS Sacred Flame or
288-FPS Web media, derive target indices from elapsed source time rather than
assuming a common integer stride. Never thin only the color or only geometry.

### Measured frame and compression probe

`volume_temporal_probe.py` and its JSON output live under the ignored
`.runtime/asset-size-experiments/` directory. For each spell, the table compares
independent PNG encoding of selected crops to a single zlib stream of XOR-coded
registered RGBA frames. Key intervals 24 and 120 insert raw key frames at those
sample intervals. The XYZ/coordinate position bytes are RGBA-packed uint16
coordinates, so ordinary visual image compression expectations do not apply.

| Spell, field | Source 144-FPS crop PNGs, 120 frames | 144-FPS XOR zlib, key 24 | 32-FPS PNGs, 26 frames | 32-FPS XOR zlib, key 24 | 24-FPS PNGs, 20 frames | 24-FPS XOR zlib, key 24 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Stinking Cloud color | 2,262,239 | 649,102 | 489,497 | 299,543 | 376,705 | 262,241 |
| Stinking Cloud position | 18,030,515 | 15,079,110 | 3,903,472 | 4,578,211 | 3,004,451 | 3,680,077 |
| Darkness color | 1,101,726 | 438,173 | 238,239 | 164,125 | 183,441 | 139,551 |
| Darkness position | 11,757,901 | 8,895,478 | 2,545,627 | 2,763,784 | 1,960,093 | 2,218,571 |
| Incendiary Cloud color | 1,931,676 | 1,322,802 | 420,769 | 471,639 | 322,784 | 384,499 |
| Incendiary Cloud position | 8,531,887 | 9,429,901 | 1,844,488 | 4,010,380 | 1,421,049 | 3,295,081 |

This is a short, first-120-frames microbenchmark; different frame counts are
shown explicitly and must not be compared as if they covered equal durations.
The data do not support claiming that temporal XOR alone compresses every bank:
it helps color strongly but often expands the packed coordinate channel. The
frames also do not support a blanket 1/7 reduction estimate. The three sampled
crop-PNG totals consistently fall 78.35% at 32 FPS and 83.33% at 24 FPS, close
to the frame-count ratios because the same selected frames and crops are
retained. If (only as a scale illustration) the entire 11.486-GB volume
allocation behaved identically, those percentages would imply about 9.00 GB
saved at 32 FPS or 9.57 GB at 24 FPS. That is not a release forecast: the sample
is three effects, one camera/facing and one short time window, and the measured
crops are independently PNG-encoded rather than repacked atlas pages. Release
savings require full coverage and measured output pages. A 120-frame source
window has only about 0.83s of timeline, so these measurements say nothing about
full-loop deduplication or periodicity.

### NumPy SVD/factorization trial

The NumPy prototype decodes the coordinate channel as two normalized uint16
fields, registers it at the authored offset, samples each field to 64x64, then
computes temporal low-rank SVD over up to 96 24-FPS samples. This is a
representational diagnostic, not an asset encoding trial: reconstructing a
low-rank factorization as float32 uses 4-byte values and the table's theoretical
factor-size ratio excludes headers, quantization and decode costs.

At rank 8, the sampled color sequences explain 52–55% of variance (normalized
RMSE 0.099–0.140); position sequences explain 56–61% (RMSE 0.062–0.134). At
rank 32, they explain 79–87% (color RMSE 0.053–0.096) and 85–90% (position RMSE
0.030–0.083). Rank 32 factors still require about 33.5% of the full sampled
float32 matrix for color and 33.7% for position, before quality/codec overhead.
That is not lossless, and the results do not establish pixel-art quality.
Therefore plain global SVD/tensor factorization is not a credible way to turn
these banks into a tiny representation. A lossless uint16 coordinate transform
has better evidence so far (the separate ten-page exact round-trip trial above
saved 38.1% on that sample), but requires broad validation and a new decoder.

### Flattening layers that have no independent visual role

This is a sensible upstream export optimization when pieces never need separate
timing, transforms, visibility, tint, blend mode, reuse, or interaction. Merge
those parts in the art export and pack only the resulting frames. Keep a
component separate when any of those behaviors matters. For paired spatial
effects, flattening color alone is not enough: the exported position/footpoint
data must remain registered to the final composite and its alpha/occlusion.

The installed persistent-spell binding inventory has 117 phase definitions,
and every phase currently declares exactly one runtime composition layer. So
the existing 11.486-GB volume banks do not show an obvious stack of runtime
layers to remove. It remains possible that source art contains redundant
editorial layers before export, but that cannot be established from the PNG
pages alone. Treat this as an artist-side audit and re-export candidate, not a
measured reduction for the current release. Compare the composited output and
paired position data across all four cameras before accepting any flattened
export.

PyTorch was not installed or added; NumPy was enough to evaluate the SVD idea.
No generated encoding was installed. Production originals, bindings, and
release outputs remain unchanged.

### Production handoff

The production task received the user's request to finish its active tasks
before intervening, then study lower-FPS frame selection and shorter cloud
loops. It confirmed the production originals and bindings would remain
untouched during this read-only analysis. Its subsequent status says support
integration resumed and owns a new 32-FPS support billboard batch with
144-FPS originals preserved; it asked that this report focus on the existing
15-GB release. These are separate scopes: no existing-release asset was
resampled here.

## Decision

The only current multi-GB reduction already proved is production dependency
selection plus exact payload sharing. The strongest remaining measurable lead is
lossless compression of persistent position maps, which account for 9.192 GB;
however, the ten-page probe is not enough to forecast savings. Extend the probe
and exact semantic comparisons before changing the storage format. Preserve all
originals and the present release while doing that evaluation.

## Evidence consulted

- Current recovery docs: `ASSETS.md`, `RECOVERY_PLAN.md`,
  `game/data/PRESENTATION_CONTRACT.md`,
  `agent_docs/PRODUCTION_ASSET_INVENTORY_2026-09-24.md`, and
  `agent_docs/CLEANUP_IMPLEMENTATION_STATUS_2026-09-24.md` from the current
  recovery checkout at `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine`.
- Actual release manifest: `/home/tommaso/Dev/neurodragon_art-production/art-manifest.json`.
- Existing exact ownership, alias and frame ledgers:
  `/home/tommaso/.codex/worktrees/5b97/dnd_engine/.runtime/vfx-usage-audit/`.
- Existing coordinate compression probe:
  `.runtime/vfx-usage-audit/compression-probe.json` in that same audit folder.
- Offline NumPy temporal/XOR/SVD experiment:
  `.runtime/asset-size-experiments/volume_temporal_probe.py` and
  `.runtime/asset-size-experiments/temporal-probe.json` in this recovery
  checkout; only the three named q0/E hold sequences were sampled.
- Release and packaging records:
  `/home/tommaso/Dev/neurodragon_art/records/cleanup-release-20260924/`.
