# Rendering cleanup and private asset migration — September 24

Work follows [the reviewed implementation plan](RENDERING_ASSET_CLEANUP_IMPLEMENTATION_PLAN_2026-09-24.md). No new spells or game rules are included. The required implementation, fresh production-only validation and current-checkout installation are complete. Code and private production are paired by the local release tag `recovery-cleanup-20260924`.

## Implemented

- **U0–U1:** cheap review provenance; strict public event decoding; passive native archive compatibility. Completed historical actions retain absent receipts as absent. Cancellations still require recorded expenditure. Current facts and native execution are unchanged.
- **U2:** importers preserve selected recipes and media. Partial deliveries merge with their existing owner. Archive addresses participate in selected-media detection.
- **U3:** named draw roles, owners, cells and device poses replace semantic reads of diagnostic tuples. Typed catalog intake produces the same passive values. Packed resource rectangles are supported by fixture and condition consumers.
- **U4–U5:** explicit billboard/XY/XYZ composition, source alternatives and coordinate bases; owner-specific packet registration; shared finite-media completion before recovery. Local spell schema v3 and condition schema v1 retain original NeuroStudio readers. Stationary contacts are resolved by their producers, including body-height Shield reactions.
- **U6:** visual wall caps and door silhouettes occlude far-side XYZ samples independently of native propagation. Near-face contact and above-wall samples remain visible.
- **U7:** initialized coverage includes objects, devices, portals, conditions, deposits and spatial media. Portable JSON fixtures and the presentation contract describe timing, rounding, sampling and ownership. No TS runtime or new queue is introduced.
- **A1–A3:** explicit private installer, exact payload aliases, XYZ ZIP indexes, color pages and environment paging. Public behavior stays in `game/data`; media is ignored and removed from the public Git index. Originals are preserved separately.
- **A4:** no blanket downsampling or frame thinning. Existing useful scales are retained. Optional small bakes/compression remain independently justified future work.

## Preservation and locations

| Location | Content |
| --- | --- |
| `/home/tommaso/Dev/neurodragon_art/` | Immutable installed-art snapshot: 62,769 files, 26,660,655,022 bytes; original inventories and source payloads. |
| `/home/tommaso/Dev/neurodragon_art-production/` | Local private Git LFS production repository: 24,783 payloads / 15,065,521,247 bytes, release `recovery-cleanup-20260924`, commit `f7474408`. No remote is configured. |
| `/home/tommaso/Dev/neurodragon_art-production-base-20260924/` | Selected pre-packing base, preserved for reproducible finalization. |
| `/home/tommaso/Dev/neurodragon_art-packed-media-20260924/` | Generated VFX pages/packet bundles and guarded binding records. |
| `/home/tommaso/Dev/neurodragon_art-packed-environment-20260924/` | Generated environment pages and guarded binding records. |
| `.runtime/cleanup-implementation-20260924/installed-before-migration/` | Prior working installation, preserved by same-filesystem rename. |
| `/home/tommaso/.cache/dnd-engine/cleanup-validation-20260924/` | Linux code copy with a fresh production-only installation; no original-file fallback. |

`ASSETS.md` is the concise operating guide, linked once from `AGENTS.md`; `PRIVATE_ART.md` contains explicit setup/build commands. Normal gameplay never installs, scans or hashes art. Private remote publication and removal from historical public Git commits remain separate.

## Evidence already complete

- Initial U1 lane: 125 replay/destruction/liquid tests. Follow-up: 35 receipt/archive cases across all seven registered action schemas, with original OA/jump/equipment histories replayed unchanged.
- Importer ownership: 46 focused cases, plus 27 cases after archive-aware delivery correction.
- Typed draw contracts: 91 raster/playback cases; typed catalogs: 167 cases and complete prior/current passive-value comparison.
- U4/U5: 104 focused cases, plus tiny storage/registration/finite-tail cases. U7 sampling/contracts: 165 cases, including 17 portable-value tests.
- U6: 186 wall/scene/projection cases. Original east-camera cap reproduction corrects 267 pixels; near-face reverse views remain unchanged.
- VFX packing/registration: 1,080 exact original/packed comparisons (18 phases × four cameras × three samples × five zooms).
- Environment packing: 640 exact color/placement/depth comparisons across four cameras and five zooms, plus 139 existing environment/mechanism cases.
- Color/XYZ sampling defect: 12,000 dimension pairs match SDL fixed-point center sampling. Forty before/after views retain identical color bytes/destinations; 1× composites are unchanged. Resized clipping changes are intentional and separately recorded.
- Fresh packed review: 22/22 saved-event observer clips pass at four cameras each. Run: `.runtime/animation-review/runs/20260924T000137Z-4f37ee/`. Includes OA death, preflight jump death, gear change, Fire Bolt, sleeping target, cannon destruction, Fireball/Globe/wall, raised fog, spill, healing and portal transit.
- Independent anti-slop and ECS reviews, plus fresh-packed visual inspection, are in `agent_docs/audits/CLEANUP_IMPLEMENTATION_*_REVIEW_2026-09-24.md` and `FRESH_PACKED_VISUAL_REVIEW_2026-09-24.md`.

## Integration closure

The broad selected game suite ran against the packed-only Linux install:
**2,290 passed, 67 failed, 12 errors, 15 deselected** in 1,660.75 seconds.
Every failure/error was addressed; none is waived as preexisting. The complete
12 affected modules plus receipt/portable-media contracts were then rerun:
**333 passed in 107.78 seconds**. This is a broad run followed by affected-module
closure, not a claim that the entire suite was rerun green in one invocation.

1. Historical reference tests assumed archived/unused sheets were production
   dependencies. They now preserve exact original bindings and decode selected
   clips/media. Offline palette tests use small real inputs; the explicit baker
   accepts the preserved source root. All ten actual-source regenerated palettes
   exactly match selected production RGBA and original alpha.
2. Catalog/combat/cannon tests assumed old raw addresses or unused cannon pitches.
   Current selector tests retain all four views and eight aim rows.
3. Two trap depth strips had both packed and unchanged consumers. Fixed the packer's
   shared-source rule, added a regression, restored both originals (103,883 bytes).
4. A ground-only stationary validator rejected already-resolved Shield body
   contacts. Removed that restriction without moving effects or changing timing.
5. Gust's maintained diagonal loop lacked frames 252–359. Repaired the exact
   selected inventory, base and four ZIP banks; frames 360–431 remain unused.
   Independent sibling review of the other 17 packed phases and 29 maintained
   variants found no other missing bank/window.

Final game/native-event typing: **zero errors, zero warnings**. Installer and
packing tools: **30 tests pass**, scoped typing clean. `git diff --check` is clean.
The initialized presentation coverage report is retained with the release evidence.

## Fresh-install visual and loading acceptance

The combined [26-clip review](http://127.0.0.1:8767/runs/20260924T002012Z-cleanup-acceptance/index.html)
links the 22-case saved-event run and four additional axial/diagonal Gust observer
clips. Each is a four-camera mosaic. All pass their existing event/presentation
checks. No game recapture, invented outcomes or new approval of artwork is implied.
These are fresh packed-only replays of retained inputs for human review.

A bounded cold-frame comparison uses current code in two fresh processes,
original versus selected bindings/media on the same Linux filesystem. The largest
environment bank's east frame 52 (`prop.interior-winged-statue.break`) loads in
**648.79 → 33.77 ms**; retained source/frame surfaces are **234.57 → 14.63 MiB**;
peak process memory is **557.14 → 117.11 MiB**. Initial RSS is approximately
88.6 MiB in both. This is one cold decoded-frame comparison, not whole-game
throughput; OS file caches were not cleared. Raw evidence and method are in the
ECS review and `.runtime/cleanup-implementation-20260924/a3-cold-frame/`.

Generated environment JSON contains 22,520 distinct frame rectangles referencing
638 pages, with the same 208 banks. Its large line diff is storage addressing,
not duplicated mechanics or spell executors. No new page-run schema was added.

## Installation and preservation closure

The original working art tree was renamed intact before installing production.
The first Windows-drive install exposed repeated ancestor filesystem checks; a
measured correction separates manifest metadata from copy-boundary checks and
reuses directory checks within each operation. The 160-path sample falls from
2.338 to 0.662 seconds, filesystem calls 4,638 to 326. Full manifest parsing now
takes about 0.09 seconds on the Windows drive. No cache survives the operation;
leaf/source/symlink safety remains covered, with no runtime or payload hashing.

The old installer was stopped after approximately 37 minutes. Its 22,792 known
atomic copies were recovered as a partial receipt from the original release;
installation then resumed using the corrected tool and latest release manifest.
This interrupted/resumed run is not a clean-install timing benchmark. The empty
Linux installation and full affected validation above are the clean-release proof.

The current checkout completed installation of all **24,783 files** (1,995
remaining/changed files copied after resumption, 236.53 seconds). Its receipt
exactly matches the final private release, including restored depth strips and
all four corrected Gust archives. This elapsed time includes NTFS validation and
copy work; it is not gameplay startup time. The public implementation and forward
media untracking are saved on `codex/recovery-design`, paired with private art
commit `f7474408` by the local release tag `recovery-cleanup-20260924`.
Release evidence is preserved in
`/home/tommaso/Dev/neurodragon_art/records/cleanup-release-20260924/`, including
corrected ledgers, packing records, source/packed comparisons, test logs and all
26 review clips. The full original trees stay in their preserved locations. Private remote publication and historical Git removal
remain explicitly deferred; forward untracking does not erase earlier commits.

Known content limits remain explicit: the preexisting missing modular equipment
categories are not supplied by this cleanup. Layer-level XYZ ordering is not a
general interpenetrating-transparency renderer. The source archive is an
installed-art snapshot, not every externally purchased vendor pack.
